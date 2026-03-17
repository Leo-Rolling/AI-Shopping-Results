"""Import KPI data from Sellerboard CSV exports."""

import csv
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Any

import structlog

from .config.constants import Marketplace, Region
from .config.sku_categories import get_category_for_sku as _get_category_obj
from .processing.models import KPIData, WeeklyReport, MarketplaceKPIs, CategoryKPIs

logger = structlog.get_logger(__name__)

# Marketplace name mapping from CSV to our enum
MARKETPLACE_MAP = {
    "Amazon.com": Marketplace.US,
    "Amazon.ca": Marketplace.CA,
    "Amazon.co.uk": Marketplace.UK,
    "Amazon.de": Marketplace.DE,
    "Amazon.fr": Marketplace.FR,
    "Amazon.it": Marketplace.IT,
    "Amazon.es": Marketplace.ES,
}

# Region mappings
EU_MARKETPLACES = {Marketplace.UK, Marketplace.DE, Marketplace.FR, Marketplace.IT, Marketplace.ES}
US_MARKETPLACES = {Marketplace.US, Marketplace.CA}


def parse_decimal(value: str) -> Decimal:
    """Parse a decimal from CSV string (handles European formatting)."""
    if not value or value == "":
        return Decimal("0")
    # Handle European format: 1.234,56 -> 1234.56
    value = value.replace(" ", "").replace("\xa0", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value)
    except Exception:
        return Decimal("0")


def parse_int(value: str) -> int:
    """Parse an integer from CSV string."""
    if not value or value == "":
        return 0
    try:
        return int(float(value.replace(",", "").replace(" ", "")))
    except Exception:
        return 0


def get_category_for_sku(sku: str) -> str | None:
    """Determine category based on SKU prefix (delegates to sku_categories)."""
    cat = _get_category_obj(sku)
    return cat.name if cat else None


def parse_dashboard_goods_csv(file_path: Path) -> dict[str, dict[Marketplace, dict[str, Any]]]:
    """
    Parse DashboardGoods CSV file.

    Returns:
        dict[date_str, dict[marketplace, dict[sku, row_data]]]
    """
    data = defaultdict(lambda: defaultdict(dict))

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("Date", "")
            marketplace_str = row.get("Marketplace", "")
            sku = row.get("SKU", "")

            if not date_str or not marketplace_str or not sku:
                continue

            marketplace = MARKETPLACE_MAP.get(marketplace_str)
            if not marketplace:
                continue

            data[date_str][marketplace][sku] = row

    return data


def parse_dashboard_totals_csv(file_path: Path) -> dict[str, dict[str, Any]]:
    """
    Parse DashboardTotals CSV file.

    Returns:
        dict[date_str, row_data]
    """
    data = {}

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("Date", "")
            if date_str:
                data[date_str] = row

    return data


def aggregate_kpi_data(rows: list[dict], totals_rows: list[dict] | None = None) -> KPIData:
    """Aggregate multiple rows into a single KPIData."""
    gross_sales = Decimal("0")
    ppc_sales = Decimal("0")
    units_sold = 0
    orders = 0
    refunds = Decimal("0")
    ad_spend = Decimal("0")
    net_profit = Decimal("0")

    for row in rows:
        # Sales
        gross_sales += parse_decimal(row.get("SalesOrganic", "0"))
        gross_sales += parse_decimal(row.get("SalesPPC", "0"))
        ppc_sales += parse_decimal(row.get("SalesPPC", "0"))

        # Units
        units_sold += parse_int(row.get("UnitsOrganic", "0"))
        units_sold += parse_int(row.get("UnitsPPC", "0"))

        # Orders (from product rows if available)
        orders += parse_int(row.get("Orders", "0"))

        # Refunds (as count)
        refunds += parse_decimal(row.get("Refunds", "0"))

        # Ad spend (sum of all ad types)
        ad_spend += abs(parse_decimal(row.get("SponsoredProducts", "0")))
        ad_spend += abs(parse_decimal(row.get("SponsoredDisplay", "0")))
        ad_spend += abs(parse_decimal(row.get("SponsoredBrands", "0")))
        ad_spend += abs(parse_decimal(row.get("SponsoredBrandsVideo", "0")))

        # Net profit
        net_profit += parse_decimal(row.get("NetProfit", "0"))

    # If totals_rows provided, use those for orders/refunds (more accurate)
    if totals_rows:
        orders = 0
        refunds = Decimal("0")
        for row in totals_rows:
            orders += parse_int(row.get("Orders", "0"))
            refunds += parse_decimal(row.get("Refunds", "0"))

    # Calculate derived metrics
    margin = (net_profit / gross_sales * 100) if gross_sales > 0 else Decimal("0")
    refund_rate = (refunds / Decimal(str(orders)) * 100) if orders > 0 else Decimal("0")
    acos = (ad_spend / gross_sales * 100) if gross_sales > 0 else Decimal("0")
    tacos = acos
    roas = (ppc_sales / ad_spend) if ad_spend > 0 else Decimal("0")

    return KPIData(
        gross_sales=gross_sales,
        ppc_sales=ppc_sales,
        units_sold=units_sold,
        orders=orders,
        refunds=refunds,
        refund_rate=refund_rate,
        net_profit=net_profit,
        margin=margin,
        ad_spend=ad_spend,
        acos=acos,
        tacos=tacos,
        roas=roas,
    )


def import_from_csv_folder(folder_path: str | Path) -> WeeklyReport:
    """
    Import KPI data from a folder of Sellerboard CSV exports.

    Args:
        folder_path: Path to folder containing CSV files

    Returns:
        WeeklyReport with aggregated data
    """
    folder = Path(folder_path)
    logger.info("Importing CSV data", folder=str(folder))

    # Find DashboardGoods files (product-level data)
    goods_files = list(folder.glob("*DashboardGoods*.csv"))
    totals_files = list(folder.glob("*DashboardTotals*.csv"))

    logger.info("Found files", goods=len(goods_files), totals=len(totals_files))

    # Parse totals files to get orders/refunds
    all_totals_rows = []
    for totals_file in totals_files:
        logger.info("Parsing totals file", file=totals_file.name)
        totals_data = parse_dashboard_totals_csv(totals_file)
        all_totals_rows.extend(totals_data.values())

    # Calculate total orders from totals files
    total_orders = sum(parse_int(row.get("Orders", "0")) for row in all_totals_rows)
    total_refunds = sum(parse_int(row.get("Refunds", "0")) for row in all_totals_rows)
    logger.info("Totals from summary files", orders=total_orders, refunds=total_refunds)

    # Parse all goods files
    all_rows = []
    marketplace_rows = defaultdict(list)
    category_marketplace_rows = defaultdict(lambda: defaultdict(list))

    for goods_file in goods_files:
        logger.info("Parsing goods file", file=goods_file.name)
        data = parse_dashboard_goods_csv(goods_file)

        for date_str, marketplaces in data.items():
            for marketplace, skus in marketplaces.items():
                for sku, row in skus.items():
                    all_rows.append(row)
                    marketplace_rows[marketplace].append(row)

                    # Determine category
                    category = get_category_for_sku(sku)
                    if category:
                        category_marketplace_rows[category][marketplace].append(row)

    logger.info("Total rows parsed", count=len(all_rows))

    # Determine date range from data
    dates = set()
    for goods_file in goods_files:
        data = parse_dashboard_goods_csv(goods_file)
        dates.update(data.keys())

    if dates:
        # Parse dates and find range
        parsed_dates = []
        for d in dates:
            try:
                parsed_dates.append(datetime.strptime(d, "%d/%m/%Y").date())
            except ValueError:
                pass

        if parsed_dates:
            week_start = min(parsed_dates)
            week_end = max(parsed_dates)
        else:
            from datetime import date, timedelta
            today = date.today()
            week_end = today
            week_start = today - timedelta(days=6)
    else:
        from datetime import date, timedelta
        today = date.today()
        week_end = today
        week_start = today - timedelta(days=6)

    from datetime import timedelta
    prev_week_end = week_start - timedelta(days=1)
    prev_week_start = prev_week_end - timedelta(days=6)

    # Aggregate by marketplace
    by_marketplace = {}
    for marketplace, rows in marketplace_rows.items():
        kpi_data = aggregate_kpi_data(rows)
        by_marketplace[marketplace] = MarketplaceKPIs(
            marketplace=marketplace,
            total=kpi_data,
        )
        logger.info(
            "Marketplace aggregated",
            marketplace=marketplace.value,
            sales=str(kpi_data.gross_sales),
            orders=kpi_data.orders,
        )

    # Aggregate by category
    by_category = {}
    for category, mp_rows in category_marketplace_rows.items():
        marketplaces_data = {}
        regions_data = {}

        for marketplace, rows in mp_rows.items():
            kpi_data = aggregate_kpi_data(rows)
            marketplaces_data[marketplace] = kpi_data

        # Aggregate regions
        eu_rows = []
        us_rows = []
        for marketplace, rows in mp_rows.items():
            if marketplace in EU_MARKETPLACES:
                eu_rows.extend(rows)
            elif marketplace in US_MARKETPLACES:
                us_rows.extend(rows)

        if eu_rows:
            regions_data[Region.EU_UK] = aggregate_kpi_data(eu_rows)
        if us_rows:
            regions_data[Region.US_CA] = aggregate_kpi_data(us_rows)

        by_category[category] = CategoryKPIs(
            category_name=category,
            category_display_name=category.replace("_", " ").title(),
            marketplaces=marketplaces_data,
            regions=regions_data,
        )
        logger.info("Category aggregated", category=category, marketplaces=len(marketplaces_data))

    # Aggregate region totals
    region_totals = {}

    eu_rows = []
    us_rows = []
    for marketplace, rows in marketplace_rows.items():
        if marketplace in EU_MARKETPLACES:
            eu_rows.extend(rows)
        elif marketplace in US_MARKETPLACES:
            us_rows.extend(rows)

    if eu_rows:
        region_totals[Region.EU_UK] = aggregate_kpi_data(eu_rows)
        logger.info(
            "EU+UK aggregated",
            sales=str(region_totals[Region.EU_UK].gross_sales),
            orders=region_totals[Region.EU_UK].orders,
        )

    if us_rows:
        region_totals[Region.US_CA] = aggregate_kpi_data(us_rows)
        logger.info(
            "US+CA aggregated",
            sales=str(region_totals[Region.US_CA].gross_sales),
            orders=region_totals[Region.US_CA].orders,
        )

    # Grand total (use totals_rows for accurate orders/refunds)
    grand_total = aggregate_kpi_data(all_rows, all_totals_rows) if all_rows else None
    if grand_total:
        logger.info(
            "Grand total",
            sales=str(grand_total.gross_sales),
            orders=grand_total.orders,
            net_profit=str(grand_total.net_profit),
        )

    return WeeklyReport(
        week_start=week_start,
        week_end=week_end,
        previous_week_start=prev_week_start,
        previous_week_end=prev_week_end,
        by_marketplace=by_marketplace,
        by_category=by_category,
        region_totals=region_totals,
        grand_total=grand_total,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = "/Users/leonardodol/Downloads/KPI 4 Feb"

    report = import_from_csv_folder(folder)
    print(f"\nReport: {report.week_start} to {report.week_end}")
    print(f"Marketplaces: {list(report.by_marketplace.keys())}")
    print(f"Categories: {list(report.by_category.keys())}")
    print(f"Region totals: {list(report.region_totals.keys())}")
    if report.grand_total:
        print(f"Grand total sales: ${report.grand_total.gross_sales}")
        print(f"Grand total orders: {report.grand_total.orders}")
