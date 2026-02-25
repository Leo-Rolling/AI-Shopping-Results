"""Sheet layout templates for KPI reports - matching reference format exactly."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import structlog

from ..config.constants import Region, Marketplace
from ..config.sku_categories import CATEGORIES
from ..processing.models import WeeklyReport, KPIData

logger = structlog.get_logger(__name__)

# EUR/USD conversion rate
EUR_USD_RATE = Decimal("1.08")

# KPI definitions matching reference file format
# (display_name, attr_name_or_calculation, format_type, is_formula)
# is_formula: if True, the value will be calculated via Google Sheets formula
KPI_ROWS = [
    ("Revenue", "gross_sales", "currency", False),
    ("Net Profit", "net_profit", "currency", False),
    ("Net Margin", None, "percent", True),  # Formula: Net Profit / Revenue
    ("Refunds", "refunds", "integer", False),
    ("PPC", "ad_spend", "currency", False),
    ("PPC Sales", "ppc_sales", "currency", False),
    ("PPC Sales/Revenue", None, "percent", True),  # Formula: PPC Sales / Revenue
    ("ACOS", None, "percent", True),  # Formula: PPC / PPC Sales
    ("ROAS", None, "percent", True),  # Formula: PPC Sales / PPC (Return on Ad Spend)
    ("TACOS", None, "percent", True),  # Formula: PPC / Revenue
    ("Orders", "orders", "integer", False),
    ("AOV", None, "currency", True),  # Formula: Revenue / Orders
]

# Row indices for formula references (0-indexed from first KPI row)
ROW_REVENUE = 0
ROW_NET_PROFIT = 1
ROW_NET_MARGIN = 2
ROW_REFUNDS = 3
ROW_PPC = 4
ROW_PPC_SALES = 5
ROW_PPC_SALES_REV = 6
ROW_ACOS = 7
ROW_ROAS = 8
ROW_TACOS = 9
ROW_ORDERS = 10
ROW_AOV = 11


class SheetTemplate(ABC):
    """Base class for sheet templates."""

    @abstractmethod
    def build(self, report: WeeklyReport) -> list[list[Any]]:
        pass


class KPISummaryTemplate(SheetTemplate):
    """
    Template for the KPIs summary sheet.
    Matches the reference format with EU+UK, US+CA, Total columns.
    Includes overall section and category sections.
    """

    def build(self, report: WeeklyReport) -> list[list[Any]]:
        """Build KPIs summary sheet data matching reference format."""
        logger.info("Building KPIs summary template")

        data: list[list[Any]] = []

        # Get date range strings
        prev_week_str = f"{report.previous_week_start.strftime('%d-%d %b %Y').replace('-', '-').split(' ')[0][:2]}-{report.previous_week_end.strftime('%d %b %Y')}"
        last_week_str = f"{report.week_start.strftime('%d %b')} - {report.week_end.strftime('%d %b %Y')}"

        # Build overall section (rows 0-14)
        data.extend(self._build_overall_section(report, prev_week_str, last_week_str))

        # Build category sections from actual data
        # Use categories found in the report, with preferred display names
        category_display_names = {
            "trackers": "Trackers",
            "incharge": "inCharge",
            "edge_pro": "Edge Pro",
            "adapters": "Adapters",
            "power_banks": "Power Banks",
            "aircard": "AirCard",
            "cables": "Cables",
            "accessories": "Accessories",
            "bundles": "Bundles",
        }

        # Track current row for formula references
        current_row = len(data) + 1  # 1-indexed

        for category_name in report.by_category.keys():
            display_name = category_display_names.get(category_name, category_name.replace("_", " ").title())
            section_rows = self._build_category_section(
                report,
                display_name,
                category_name,
                prev_week_str,
                last_week_str,
                section_start_row=current_row + 4,  # 4 header rows before KPI data
            )
            data.extend(section_rows)
            current_row += len(section_rows)

        logger.info("KPIs summary template built", rows=len(data))
        return data

    def _build_overall_section(
        self,
        report: WeeklyReport,
        prev_week_str: str,
        last_week_str: str
    ) -> list[list[Any]]:
        """Build the overall KPI section (rows 0-14)."""
        rows: list[list[Any]] = []

        # Row 0: Headers + EUR/USD rate
        rows.append([
            "", "EU+UK", "", "", "",
            "US+CA", "", "", "",
            "Total", "", "", "",
            "", "", "EUR/USD", float(EUR_USD_RATE)
        ])

        # Row 1: Sub-headers
        rows.append([
            "", "Avg. Day L.Week", "", "", "Delta",
            "Avg. Day L.Week", "", "", "Delta",
            "Avg. Day L.Week", "Prev Week", "Last Week", "Delta",
            "", "", "", ""
        ])

        # Row 2: Date ranges
        rows.append([
            "", "", prev_week_str, last_week_str, "",
            "", prev_week_str, last_week_str, "",
            "", prev_week_str, last_week_str, "",
            "", "", "", ""
        ])

        # Get KPI data for each region
        eu_uk_data = report.region_totals.get(Region.EU_UK)
        us_ca_data = report.region_totals.get(Region.US_CA)

        # Previous week data (if available)
        eu_uk_prev = report.by_category.get("_overall_prev", {}).get("eu_uk")
        us_ca_prev = report.by_category.get("_overall_prev", {}).get("us_ca")

        # Section starts at row 4 (1-indexed)
        section_start_row = 4

        # Rows 3-13: KPI data rows
        for row_idx, (kpi_name, attr_name, format_type, is_formula) in enumerate(KPI_ROWS):
            # Start row number in sheet (1-indexed, row 4 is first KPI)
            sheet_row = section_start_row + row_idx

            row = self._build_kpi_row(
                kpi_name=kpi_name,
                attr_name=attr_name,
                format_type=format_type,
                is_formula=is_formula,
                eu_data=eu_uk_data,
                us_data=us_ca_data,
                eu_prev=eu_uk_prev,
                us_prev=us_ca_prev,
                sheet_row=sheet_row,
                section_start_row=section_start_row,
                is_overall=True,
            )
            rows.append(row)

        # Row 14: Blank row
        rows.append([""] * 17)

        return rows

    def _build_category_section(
        self,
        report: WeeklyReport,
        category_display_name: str,
        category_name: str,
        prev_week_str: str,
        last_week_str: str,
        section_start_row: int = 0,
    ) -> list[list[Any]]:
        """Build a category section (16 rows each)."""
        rows: list[list[Any]] = []

        # Row 0: Category name
        rows.append([category_display_name] + [""] * 16)

        # Row 1: Headers (EU, US instead of EU+UK, US+CA for categories)
        rows.append([
            "", "EU", "", "", "",
            "US", "", "", "",
            "Total", "", "", "",
            "", "", "", ""
        ])

        # Row 2: Sub-headers
        rows.append([
            "", "Avg. Day L.Week", "Last Week", "Last Week", "Delta",
            "Avg. Day L.Week", "", "", "Delta",
            "Avg. Day L.Week", "Prev Week", "Last Week", "Delta",
            "", "", "", ""
        ])

        # Row 3: Date ranges
        rows.append([
            "", "", prev_week_str, last_week_str, "",
            "", prev_week_str, last_week_str, "",
            "", prev_week_str, last_week_str, "",
            "", "", "", ""
        ])

        # Get category-specific data
        category_kpis = report.by_category.get(category_name)
        eu_data = None
        us_data = None
        if category_kpis:
            eu_data = category_kpis.regions.get(Region.EU_UK)
            us_data = category_kpis.regions.get(Region.US_CA)

        # If no category data, fall back to overall data for demo
        if not eu_data:
            eu_data = report.region_totals.get(Region.EU_UK)
        if not us_data:
            us_data = report.region_totals.get(Region.US_CA)

        # Rows 4-14: KPI data rows
        for row_idx, (kpi_name, attr_name, format_type, is_formula) in enumerate(KPI_ROWS):
            sheet_row = section_start_row + row_idx
            row = self._build_kpi_row(
                kpi_name=kpi_name,
                attr_name=attr_name,
                format_type=format_type,
                is_formula=is_formula,
                eu_data=eu_data,
                us_data=us_data,
                eu_prev=None,  # Would need previous week category data
                us_prev=None,
                sheet_row=sheet_row,
                section_start_row=section_start_row,
                is_overall=False,
            )
            rows.append(row)

        # Blank row
        rows.append([""] * 17)

        return rows

    def _build_kpi_row(
        self,
        kpi_name: str,
        attr_name: str | None,
        format_type: str,
        is_formula: bool,
        eu_data: KPIData | None,
        us_data: KPIData | None,
        eu_prev: KPIData | None,
        us_prev: KPIData | None,
        sheet_row: int,
        section_start_row: int,
        is_overall: bool,
    ) -> list[Any]:
        """Build a single KPI row with values and formulas."""
        row: list[Any] = [""] * 17
        row[0] = kpi_name

        # For formula-based rows, create formulas referencing other rows
        if is_formula:
            return self._build_formula_row(kpi_name, sheet_row, section_start_row)

        # Get current values
        eu_val = self._get_kpi_value(eu_data, attr_name) if eu_data and attr_name else None
        us_val = self._get_kpi_value(us_data, attr_name) if us_data and attr_name else None

        # Get previous values (for now, use same as current if not available)
        eu_prev_val = self._get_kpi_value(eu_prev, attr_name) if eu_prev and attr_name else eu_val
        us_prev_val = self._get_kpi_value(us_prev, attr_name) if us_prev and attr_name else us_val

        # Calculate totals (EU converted to USD + US)
        total_prev = None
        total_curr = None
        if eu_prev_val is not None and us_prev_val is not None:
            total_prev = float(eu_prev_val) * float(EUR_USD_RATE) + float(us_prev_val)
        elif us_prev_val is not None:
            total_prev = float(us_prev_val)
        if eu_val is not None and us_val is not None:
            total_curr = float(eu_val) * float(EUR_USD_RATE) + float(us_val)
        elif us_val is not None:
            total_curr = float(us_val)

        # EU+UK columns (B-E, indexes 1-4)
        if eu_val is not None:
            row[1] = self._format_number(float(eu_val) / 7)  # Avg. Day L.Week
            row[2] = self._format_number(eu_prev_val) if eu_prev_val else ""  # Prev Week
            row[3] = self._format_number(float(eu_val))  # Last Week
            row[4] = f"=(D{sheet_row}-C{sheet_row})/C{sheet_row}"  # Delta formula

        # US+CA columns (F-I, indexes 5-8)
        if us_val is not None:
            row[5] = self._format_number(float(us_val) / 7)  # Avg. Day L.Week
            row[6] = self._format_number(us_prev_val) if us_prev_val else ""  # Prev Week
            row[7] = self._format_number(float(us_val))  # Last Week
            row[8] = f"=(H{sheet_row}-G{sheet_row})/G{sheet_row}"  # Delta formula

        # Total columns (J-M, indexes 9-12)
        if total_curr is not None:
            row[9] = self._format_number(total_curr / 7)  # Avg. Day L.Week
            row[10] = self._format_number(total_prev) if total_prev else ""  # Prev Week
            row[11] = self._format_number(total_curr)  # Last Week
            row[12] = f"=(L{sheet_row}-K{sheet_row})/K{sheet_row}"  # Delta formula

        return row

    def _build_formula_row(self, kpi_name: str, sheet_row: int, section_start_row: int) -> list[Any]:
        """Build a row with formulas referencing other KPI rows."""
        row: list[Any] = [""] * 17
        row[0] = kpi_name

        # Calculate row offsets from section start
        revenue_row = section_start_row + ROW_REVENUE
        net_profit_row = section_start_row + ROW_NET_PROFIT
        ppc_row = section_start_row + ROW_PPC
        ppc_sales_row = section_start_row + ROW_PPC_SALES
        orders_row = section_start_row + ROW_ORDERS

        if kpi_name == "Net Margin":
            # Net Margin = Net Profit / Revenue
            row[1] = f"=B{net_profit_row}/B{revenue_row}"  # EU Avg
            row[2] = f"=C{net_profit_row}/C{revenue_row}"  # EU Prev
            row[3] = f"=D{net_profit_row}/D{revenue_row}"  # EU Last
            row[4] = f"=(D{sheet_row}-C{sheet_row})/C{sheet_row}"  # EU Delta
            row[5] = f"=F{net_profit_row}/F{revenue_row}"  # US Avg
            row[6] = f"=G{net_profit_row}/G{revenue_row}"  # US Prev
            row[7] = f"=H{net_profit_row}/H{revenue_row}"  # US Last
            row[8] = f"=(H{sheet_row}-G{sheet_row})/G{sheet_row}"  # US Delta
            row[9] = f"=J{net_profit_row}/J{revenue_row}"  # Total Avg
            row[10] = f"=K{net_profit_row}/K{revenue_row}"  # Total Prev
            row[11] = f"=L{net_profit_row}/L{revenue_row}"  # Total Last
            row[12] = f"=(L{sheet_row}-K{sheet_row})/K{sheet_row}"  # Total Delta

        elif kpi_name == "PPC Sales/Revenue":
            # PPC Sales/Revenue = PPC Sales / Revenue
            row[1] = f"=B{ppc_sales_row}/B{revenue_row}"
            row[2] = f"=C{ppc_sales_row}/C{revenue_row}"
            row[3] = f"=D{ppc_sales_row}/D{revenue_row}"
            row[4] = f"=(D{sheet_row}-C{sheet_row})/C{sheet_row}"
            row[5] = f"=F{ppc_sales_row}/F{revenue_row}"
            row[6] = f"=G{ppc_sales_row}/G{revenue_row}"
            row[7] = f"=H{ppc_sales_row}/H{revenue_row}"
            row[8] = f"=(H{sheet_row}-G{sheet_row})/G{sheet_row}"
            row[9] = f"=J{ppc_sales_row}/J{revenue_row}"
            row[10] = f"=K{ppc_sales_row}/K{revenue_row}"
            row[11] = f"=L{ppc_sales_row}/L{revenue_row}"
            row[12] = f"=(L{sheet_row}-K{sheet_row})/K{sheet_row}"

        elif kpi_name == "ACOS":
            # ACOS = PPC / PPC Sales
            row[1] = f"=B{ppc_row}/B{ppc_sales_row}"
            row[2] = f"=C{ppc_row}/C{ppc_sales_row}"
            row[3] = f"=D{ppc_row}/D{ppc_sales_row}"
            row[4] = f"=(D{sheet_row}-C{sheet_row})/C{sheet_row}"
            row[5] = f"=F{ppc_row}/F{ppc_sales_row}"
            row[6] = f"=G{ppc_row}/G{ppc_sales_row}"
            row[7] = f"=H{ppc_row}/H{ppc_sales_row}"
            row[8] = f"=(H{sheet_row}-G{sheet_row})/G{sheet_row}"
            row[9] = f"=J{ppc_row}/J{ppc_sales_row}"
            row[10] = f"=K{ppc_row}/K{ppc_sales_row}"
            row[11] = f"=L{ppc_row}/L{ppc_sales_row}"
            row[12] = f"=(L{sheet_row}-K{sheet_row})/K{sheet_row}"

        elif kpi_name == "TACOS":
            # TACOS = PPC / Revenue
            row[1] = f"=B{ppc_row}/B{revenue_row}"
            row[2] = f"=C{ppc_row}/C{revenue_row}"
            row[3] = f"=D{ppc_row}/D{revenue_row}"
            row[4] = f"=(D{sheet_row}-C{sheet_row})/C{sheet_row}"
            row[5] = f"=F{ppc_row}/F{revenue_row}"
            row[6] = f"=G{ppc_row}/G{revenue_row}"
            row[7] = f"=H{ppc_row}/H{revenue_row}"
            row[8] = f"=(H{sheet_row}-G{sheet_row})/G{sheet_row}"
            row[9] = f"=J{ppc_row}/J{revenue_row}"
            row[10] = f"=K{ppc_row}/K{revenue_row}"
            row[11] = f"=L{ppc_row}/L{revenue_row}"
            row[12] = f"=(L{sheet_row}-K{sheet_row})/K{sheet_row}"

        elif kpi_name == "AOV":
            # AOV = Revenue / Orders
            row[1] = f"=B{revenue_row}/B{orders_row}"
            row[2] = f"=C{revenue_row}/C{orders_row}"
            row[3] = f"=D{revenue_row}/D{orders_row}"
            row[4] = f"=(D{sheet_row}-C{sheet_row})/C{sheet_row}"
            row[5] = f"=F{revenue_row}/F{orders_row}"
            row[6] = f"=G{revenue_row}/G{orders_row}"
            row[7] = f"=H{revenue_row}/H{orders_row}"
            row[8] = f"=(H{sheet_row}-G{sheet_row})/G{sheet_row}"
            row[9] = f"=J{revenue_row}/J{orders_row}"
            row[10] = f"=K{revenue_row}/K{orders_row}"
            row[11] = f"=L{revenue_row}/L{orders_row}"
            row[12] = f"=(L{sheet_row}-K{sheet_row})/K{sheet_row}"

        return row

    def _format_number(self, value: float | None) -> float | str:
        """Return number rounded to 2 decimal places (as actual number, not text)."""
        if value is None:
            return ""
        # Return actual number rounded to 2 decimals - Google Sheets will format display
        return round(value, 2)

    def _get_kpi_value(self, data: KPIData, attr_name: str) -> float | None:
        """Get KPI value from data object."""
        if data is None:
            return None

        # Handle property-based calculations
        if attr_name == "ppc_sales_ratio":
            return float(data.ppc_sales_ratio)
        elif attr_name == "aov":
            return float(data.aov)

        # Regular attributes
        value = getattr(data, attr_name, None)
        if value is None:
            return None

        return float(value)


class ByCountryTemplate(SheetTemplate):
    """Template for detailed breakdown by country/marketplace with week comparison."""

    # All 7 marketplaces
    MARKETPLACES = [
        (Marketplace.US, "US"),
        (Marketplace.CA, "CA"),
        (Marketplace.UK, "UK"),
        (Marketplace.DE, "DE"),
        (Marketplace.FR, "FR"),
        (Marketplace.IT, "IT"),
        (Marketplace.ES, "ES"),
    ]

    # Category display names
    CATEGORY_DISPLAY_NAMES = {
        "trackers": "Trackers",
        "incharge": "inCharge",
        "edge_pro": "Edge Pro",
        "adapters": "Adapters",
        "power_banks": "Power Banks",
        "aircard": "AirCard",
        "cables": "Cables",
        "accessories": "Accessories",
        "bundles": "Bundles",
    }

    def build(self, report: WeeklyReport) -> list[list[Any]]:
        """Build By Country sheet data with all 7 marketplaces and week comparison."""
        logger.info("Building By Country template")

        data: list[list[Any]] = []

        # Title
        week_range = f"{report.week_start.strftime('%B %d, %Y')} to {report.week_end.strftime('%B %d, %Y')}"
        prev_week_range = f"{report.previous_week_start.strftime('%B %d, %Y')} to {report.previous_week_end.strftime('%B %d, %Y')}"
        data.append([f"Amazon KPIs by Country - Week of {week_range}"])
        data.append([])

        # Build overall section
        section_data = self._build_section(
            report=report,
            section_name="Overall",
            prev_week_range=prev_week_range,
            week_range=week_range,
            get_marketplace_data=lambda mp: report.by_marketplace.get(mp).total if report.by_marketplace.get(mp) else None,
            section_start_row=3,  # Row 3 is first header row (0-indexed in data, but 1-indexed in sheets)
        )
        data.extend(section_data)

        # Blank row
        data.append([])

        # Category breakdown sections
        current_row = len(data) + 1  # +1 for 1-indexed sheets
        for category_name, category_kpis in report.by_category.items():
            # Skip internal markers
            if category_name.startswith("_"):
                continue

            display_name = self.CATEGORY_DISPLAY_NAMES.get(category_name, category_name.replace("_", " ").title())

            section_data = self._build_section(
                report=report,
                section_name=display_name,
                prev_week_range=prev_week_range,
                week_range=week_range,
                get_marketplace_data=lambda mp, ck=category_kpis: ck.marketplaces.get(mp) if ck else None,
                section_start_row=current_row + 4,  # +4 for section header rows
            )
            data.extend(section_data)
            current_row += len(section_data)

        logger.info("By Country template built", rows=len(data))
        return data

    def _build_section(
        self,
        report: WeeklyReport,
        section_name: str,
        prev_week_range: str,
        week_range: str,
        get_marketplace_data: callable,
        section_start_row: int,
    ) -> list[list[Any]]:
        """Build a section (overall or category) with proper headers and data."""
        rows: list[list[Any]] = []

        # Number of columns: 1 (Metric) + 7 marketplaces * 3 (Prev, Current, Delta) + 3 (Total Prev, Current, Delta)
        num_mp = len(self.MARKETPLACES)
        total_cols = 1 + num_mp * 3 + 3

        # Section title row (only for category sections)
        if section_name != "Overall":
            title_row = [section_name] + [""] * (total_cols - 1)
            rows.append(title_row)
            rows.append([""] * total_cols)  # Blank row after title

        # Headers row - marketplace names spanning 3 columns each
        header_row = ["Metric"]
        for _, display_name in self.MARKETPLACES:
            header_row.extend([display_name, "", ""])  # Span 3 columns
        header_row.extend(["Total", "", ""])  # Total also spans 3 columns
        rows.append(header_row)

        # Sub-headers row (Prev Week, This Week, Delta for each)
        sub_header_row = [""]
        for _ in self.MARKETPLACES:
            sub_header_row.extend(["Prev Week", "This Week", "Delta"])
        sub_header_row.extend(["Prev Week", "This Week", "Delta"])
        rows.append(sub_header_row)

        # Date row
        date_row = [""]
        for _ in self.MARKETPLACES:
            date_row.extend([prev_week_range, week_range, ""])
        date_row.extend([prev_week_range, week_range, ""])
        rows.append(date_row)

        # KPI rows
        # Track the actual row numbers for formula references
        kpi_start_row = section_start_row + (2 if section_name != "Overall" else 0) + 3  # Adjust for section title and headers

        for row_idx, (kpi_name, attr_name, format_type, is_formula) in enumerate(KPI_ROWS):
            sheet_row = kpi_start_row + row_idx

            if is_formula:
                # Build formula row
                row = self._build_formula_row_by_country(kpi_name, sheet_row, kpi_start_row, num_mp)
            else:
                # Build data row
                row = self._build_data_row_by_country(
                    kpi_name, attr_name, format_type,
                    get_marketplace_data, sheet_row, num_mp
                )
            rows.append(row)

        # Blank row at end
        rows.append([""] * total_cols)

        return rows

    def _build_data_row_by_country(
        self,
        kpi_name: str,
        attr_name: str,
        format_type: str,
        get_marketplace_data: callable,
        sheet_row: int,
        num_mp: int,
    ) -> list[Any]:
        """Build a data row for By Country sheet."""
        row: list[Any] = [kpi_name]

        # Track column positions for Total formulas
        prev_cols = []
        curr_cols = []

        col_idx = 2  # Start at column B (1-indexed)

        for marketplace, _ in self.MARKETPLACES:
            mp_data = get_marketplace_data(marketplace)

            current_value = None
            if mp_data:
                current_value = self._get_kpi_value(mp_data, attr_name)

            # Prev Week (placeholder - would need previous week data)
            row.append("")
            prev_cols.append(self._col_letter(col_idx))
            col_idx += 1

            # This Week
            row.append(self._format_value(current_value, format_type))
            curr_cols.append(self._col_letter(col_idx))
            col_idx += 1

            # Delta formula: (This Week - Prev Week) / Prev Week
            prev_col = self._col_letter(col_idx - 2)
            curr_col = self._col_letter(col_idx - 1)
            delta_formula = f"=IFERROR(({curr_col}{sheet_row}-{prev_col}{sheet_row})/{prev_col}{sheet_row},\"\")"
            row.append(delta_formula)
            col_idx += 1

        # Total columns
        # Total Prev Week: sum of all prev week columns
        prev_sum = "+".join([f"{c}{sheet_row}" for c in prev_cols])
        row.append(f"=IF({prev_cols[0]}{sheet_row}<>\"\",{prev_sum},\"\")")
        total_prev_col = self._col_letter(col_idx)
        col_idx += 1

        # Total This Week: sum of all this week columns
        curr_sum = "+".join([f"{c}{sheet_row}" for c in curr_cols])
        row.append(f"=IF({curr_cols[0]}{sheet_row}<>\"\",{curr_sum},\"\")")
        total_curr_col = self._col_letter(col_idx)
        col_idx += 1

        # Total Delta
        row.append(f"=IFERROR(({total_curr_col}{sheet_row}-{total_prev_col}{sheet_row})/{total_prev_col}{sheet_row},\"\")")

        return row

    def _build_formula_row_by_country(
        self,
        kpi_name: str,
        sheet_row: int,
        kpi_start_row: int,
        num_mp: int,
    ) -> list[Any]:
        """Build a formula-based row for By Country sheet (Net Margin, ACOS, etc.)."""
        row: list[Any] = [kpi_name]

        # Calculate row references
        revenue_row = kpi_start_row + ROW_REVENUE
        net_profit_row = kpi_start_row + ROW_NET_PROFIT
        ppc_row = kpi_start_row + ROW_PPC
        ppc_sales_row = kpi_start_row + ROW_PPC_SALES
        orders_row = kpi_start_row + ROW_ORDERS

        col_idx = 2  # Start at column B

        # For each marketplace (3 columns each: Prev, Current, Delta)
        for _ in range(num_mp):
            for sub_col in range(3):  # Prev, Current, Delta
                col_letter = self._col_letter(col_idx)

                if sub_col < 2:  # Prev or Current column
                    formula = self._get_kpi_formula(
                        kpi_name, col_letter,
                        revenue_row, net_profit_row, ppc_row, ppc_sales_row, orders_row
                    )
                    row.append(formula)
                else:  # Delta column
                    prev_col = self._col_letter(col_idx - 2)
                    curr_col = self._col_letter(col_idx - 1)
                    # Delta for percentage KPIs should be percentage points difference
                    row.append(f"=IFERROR({curr_col}{sheet_row}-{prev_col}{sheet_row},\"\")")

                col_idx += 1

        # Total columns (3: Prev, Current, Delta)
        for sub_col in range(3):
            col_letter = self._col_letter(col_idx)

            if sub_col < 2:  # Prev or Current column
                formula = self._get_kpi_formula(
                    kpi_name, col_letter,
                    revenue_row, net_profit_row, ppc_row, ppc_sales_row, orders_row
                )
                row.append(formula)
            else:  # Delta column
                prev_col = self._col_letter(col_idx - 2)
                curr_col = self._col_letter(col_idx - 1)
                row.append(f"=IFERROR({curr_col}{sheet_row}-{prev_col}{sheet_row},\"\")")

            col_idx += 1

        return row

    def _get_kpi_formula(
        self,
        kpi_name: str,
        col_letter: str,
        revenue_row: int,
        net_profit_row: int,
        ppc_row: int,
        ppc_sales_row: int,
        orders_row: int,
    ) -> str:
        """Get the formula for a calculated KPI."""
        if kpi_name == "Net Margin":
            return f"=IFERROR({col_letter}{net_profit_row}/{col_letter}{revenue_row},\"\")"
        elif kpi_name == "PPC Sales/Revenue":
            return f"=IFERROR({col_letter}{ppc_sales_row}/{col_letter}{revenue_row},\"\")"
        elif kpi_name == "ACOS":
            return f"=IFERROR({col_letter}{ppc_row}/{col_letter}{ppc_sales_row},\"\")"
        elif kpi_name == "ROAS":
            return f"=IFERROR({col_letter}{ppc_sales_row}/{col_letter}{ppc_row},\"\")"
        elif kpi_name == "TACOS":
            return f"=IFERROR({col_letter}{ppc_row}/{col_letter}{revenue_row},\"\")"
        elif kpi_name == "AOV":
            return f"=IFERROR({col_letter}{revenue_row}/{col_letter}{orders_row},\"\")"
        return ""

    def _col_letter(self, col_num: int) -> str:
        """Convert column number (1-indexed) to letter (A, B, ..., Z, AA, AB, ...)."""
        result = ""
        while col_num > 0:
            col_num, remainder = divmod(col_num - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def _get_kpi_value(self, data: KPIData, attr_name: str) -> float | None:
        """Get KPI value from data object."""
        if data is None:
            return None

        if attr_name == "ppc_sales_ratio":
            return float(data.ppc_sales_ratio)
        elif attr_name == "aov":
            return float(data.aov)

        value = getattr(data, attr_name, None)
        if value is None:
            return None

        return float(value)

    def _format_value(self, value: Any, format_type: str) -> float | int | str:
        """Return value as actual number (Google Sheets will handle display formatting)."""
        if value is None or value == 0:
            return ""

        try:
            if format_type == "currency":
                return round(float(value), 2)
            elif format_type == "percent":
                return round(float(value), 2)
            elif format_type == "percent_decimal":
                return round(float(value), 2)
            elif format_type == "decimal":
                return round(float(value), 2)
            elif format_type == "integer":
                return int(value)
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)


class ComparisonTemplate(SheetTemplate):
    """Template for week-over-week comparison."""

    def build(self, report: WeeklyReport) -> list[list[Any]]:
        """Build comparison sheet data."""
        data: list[list[Any]] = []

        data.append([
            f"Week-over-Week Comparison: "
            f"{report.previous_week_start.strftime('%m/%d')} - {report.previous_week_end.strftime('%m/%d')} vs "
            f"{report.week_start.strftime('%m/%d')} - {report.week_end.strftime('%m/%d')}"
        ])
        data.append([])

        data.append(["KPI", "Previous Week", "Current Week", "Change", "% Change"])

        # Get data
        current = report.grand_total or report.region_totals.get(Region.US_CA)

        for kpi_name, attr_name, format_type, is_formula in KPI_ROWS:
            if current:
                value = getattr(current, attr_name, None) if attr_name != "ppc_sales_ratio" and attr_name != "aov" else None
                if attr_name == "ppc_sales_ratio":
                    value = current.ppc_sales_ratio
                elif attr_name == "aov":
                    value = current.aov

                if value is not None:
                    formatted = self._format_value(value, format_type)
                    data.append([kpi_name, "", formatted, "", ""])
                else:
                    data.append([kpi_name, "", "", "", ""])
            else:
                data.append([kpi_name, "", "", "", ""])

        return data

    def _format_value(self, value: Any, format_type: str) -> str:
        """Format a value based on type."""
        if value is None:
            return ""

        try:
            if format_type == "currency":
                return f"${float(value):,.2f}"
            elif format_type == "percent":
                return f"{float(value):.2f}%"
            elif format_type == "percent_decimal":
                return f"{float(value):.4f}"
            elif format_type == "decimal":
                return f"{float(value):.4f}"
            elif format_type == "integer":
                return f"{int(value):,}"
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)
