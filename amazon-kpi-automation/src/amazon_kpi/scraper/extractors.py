"""KPI value extraction from Sellerboard dashboard."""

import re
from decimal import Decimal, InvalidOperation

import structlog
from playwright.async_api import Page

from ..processing.models import KPIData
from ..utils.exceptions import DataExtractionError

logger = structlog.get_logger(__name__)


class KPIExtractor:
    """Extracts KPI values from Sellerboard dashboard tiles."""

    def __init__(self, page: Page):
        """Initialize extractor."""
        self._page = page

    async def extract_all_kpis(self) -> KPIData:
        """
        Extract all KPI values from the current dashboard view.

        Returns:
            KPIData with extracted values
        """
        logger.info("Extracting KPI data from dashboard")

        try:
            # Wait for dashboard tiles to be fully loaded
            await self._wait_for_tiles()

            kpi_values = await self._extract_from_page()

            logger.info(
                "KPI extraction complete",
                sales=str(kpi_values.get("gross_sales", 0)),
                orders=kpi_values.get("orders", 0),
                net_profit=str(kpi_values.get("net_profit", 0)),
            )

            return self._build_kpi_data(kpi_values)

        except Exception as e:
            logger.error("KPI extraction failed", error=str(e))
            raise DataExtractionError(
                "Failed to extract KPI data",
                details={"error": str(e)},
            ) from e

    async def _wait_for_tiles(self, timeout_ms: int = 60000) -> None:
        """Wait for dashboard tiles to be visible and contain data."""
        import asyncio

        logger.debug("Waiting for dashboard tiles to load")

        # Wait for the page to have network idle state
        await self._page.wait_for_load_state("networkidle", timeout=timeout_ms)

        # Wait for text "7 days" to appear on the page (indicates tiles are loaded)
        try:
            await self._page.wait_for_selector(
                'text="7 days"',
                timeout=timeout_ms,
                state="visible",
            )
            logger.debug("Found '7 days' selector")
        except Exception as e:
            logger.warning("Could not find '7 days' selector", error=str(e))

        # Also try waiting for Sales tile specifically
        try:
            await self._page.wait_for_selector(
                'text="Sales"',
                timeout=5000,
                state="visible",
            )
            logger.debug("Found 'Sales' selector")
        except Exception:
            pass

        # Extra wait for dynamic content to fully render
        await asyncio.sleep(2)

        logger.debug("Dashboard tiles should be loaded")

    async def _extract_from_page(self) -> dict:
        """Extract KPIs by parsing the page text."""
        kpi_values = {}

        # Get the full page text
        page_text = await self._page.inner_text("body")

        # Log first 500 chars for debugging
        logger.debug("Page text preview", preview=page_text[:500] if len(page_text) > 500 else page_text)
        logger.debug("Page text length", length=len(page_text))

        # Check if "7 days" appears anywhere in the text
        if "7 days" in page_text:
            logger.debug("'7 days' found in page text")
        else:
            logger.warning("'7 days' NOT found in page text")
            # Try finding any day-related text
            for pattern in ["days", "Sales", "Orders", "Profit"]:
                if pattern in page_text:
                    logger.debug(f"Found '{pattern}' in page text")

        # Look for the "7 days" section which contains the weekly data
        # Parse the section between "7 days" and "14 days" (don't use "More" as it appears within each tile)
        section_text = self._extract_section(page_text, "7 days", ["14 days"])

        if section_text:
            logger.debug("Found 7 days section", length=len(section_text))
            kpi_values = self._parse_tile_section(section_text)
        else:
            # Fallback: try to extract from the whole page
            logger.warning("7 days section not found, using full page extraction")
            kpi_values = self._parse_full_page(page_text)

        # Calculate derived metrics
        kpi_values = self._calculate_derived_metrics(kpi_values)

        return kpi_values

    def _extract_section(self, text: str, start_marker: str, end_markers: list[str]) -> str | None:
        """Extract text section between markers."""
        start_idx = text.find(start_marker)
        if start_idx == -1:
            logger.debug(f"Start marker '{start_marker}' not found")
            return None

        logger.debug(f"Found start marker at index {start_idx}")

        # Find the earliest end marker after start (skip 100 chars to avoid matching within same tile)
        end_idx = len(text)
        for marker in end_markers:
            idx = text.find(marker, start_idx + 100)
            if idx != -1 and idx < end_idx:
                end_idx = idx
                logger.debug(f"Found end marker '{marker}' at index {idx}")

        section = text[start_idx:end_idx]
        logger.debug(f"Extracted section length: {len(section)}")
        return section

    def _parse_tile_section(self, section: str) -> dict:
        """Parse KPI values from a tile section."""
        kpi_values = {}

        logger.debug("Parsing tile section", section_preview=section[:200] if len(section) > 200 else section)

        # Parse Sales - format: "Sales\n+0.5%\n$27,681.32" or "Sales\n$27,681.32"
        # Match Sales followed by optional percentage, then dollar amount
        sales_match = re.search(r'Sales\s*\n?[+\-]?[\d.]*%?\s*\n?\$?([\d,]+\.?\d*)', section)
        if sales_match:
            kpi_values["gross_sales"] = self._parse_number(sales_match.group(1))
            logger.debug("Parsed sales", value=str(kpi_values["gross_sales"]))

        # Parse Orders / Units - format: "Orders / Units\n761 / 832"
        orders_match = re.search(r'Orders\s*/\s*Units\s*\n?\s*([\d,]+)\s*/\s*([\d,]+)', section)
        if orders_match:
            kpi_values["orders"] = int(orders_match.group(1).replace(",", ""))
            kpi_values["units_sold"] = int(orders_match.group(2).replace(",", ""))
            logger.debug("Parsed orders/units", orders=kpi_values["orders"], units=kpi_values["units_sold"])
        else:
            # Try just Orders
            orders_only = re.search(r'Orders\s*\n?\s*(\d[\d,]*)', section)
            if orders_only:
                kpi_values["orders"] = int(orders_only.group(1).replace(",", ""))
                logger.debug("Parsed orders only", orders=kpi_values["orders"])

        # Parse Refunds - format: "Refunds\n69"
        refunds_match = re.search(r'Refunds\s*\n?\s*(\d[\d,]*)', section)
        if refunds_match:
            kpi_values["refunds"] = Decimal(refunds_match.group(1).replace(",", ""))
            logger.debug("Parsed refunds", value=str(kpi_values["refunds"]))

        # Parse Adv. cost (advertising spend) - format: "Adv. cost\n-$3,342.63"
        ad_cost_match = re.search(r'Adv\.\s*cost\s*\n?\s*-?\$?([\d,]+\.?\d*)', section)
        if ad_cost_match:
            kpi_values["ad_spend"] = self._parse_number(ad_cost_match.group(1))
            logger.debug("Parsed ad spend", value=str(kpi_values["ad_spend"]))

        # Parse Gross profit - format: "Gross profit\n$12,625.66"
        gross_match = re.search(r'Gross\s*profit\s*\n?\s*\$?([\d,]+\.?\d*)', section)
        if gross_match:
            kpi_values["gross_profit"] = self._parse_number(gross_match.group(1))
            logger.debug("Parsed gross profit", value=str(kpi_values["gross_profit"]))

        # Parse Net profit - format: "Net profit\n+31.0%\n$12,616.63"
        net_match = re.search(r'Net\s*profit\s*\n?[+\-]?[\d.]*%?\s*\n?\$?([\d,]+\.?\d*)', section)
        if net_match:
            kpi_values["net_profit"] = self._parse_number(net_match.group(1))
            logger.debug("Parsed net profit", value=str(kpi_values["net_profit"]))

        # Parse Est. payout (optional) - format: "Est. payout\n$16,422.33"
        payout_match = re.search(r'Est\.\s*payout\s*\n?\s*\$?([\d,]+\.?\d*)', section)
        if payout_match:
            kpi_values["estimated_payout"] = self._parse_number(payout_match.group(1))
            logger.debug("Parsed payout", value=str(kpi_values["estimated_payout"]))

        return kpi_values

    def _parse_full_page(self, text: str) -> dict:
        """Fallback: parse KPIs from full page text."""
        kpi_values = {}

        # Find all dollar amounts
        dollar_matches = re.findall(r'\$?([\d,]+\.?\d*)', text)
        if dollar_matches and len(dollar_matches) > 0:
            # First significant dollar amount is likely Sales
            for match in dollar_matches:
                val = self._parse_number(match)
                if val and val > 100:
                    kpi_values["gross_sales"] = val
                    break

        return kpi_values

    def _parse_number(self, text: str) -> Decimal | None:
        """Parse a number string into Decimal."""
        if not text:
            return None

        try:
            # Remove commas and whitespace
            clean = text.replace(",", "").replace(" ", "").strip()
            if not clean:
                return None
            return Decimal(clean)
        except (InvalidOperation, ValueError):
            return None

    def _calculate_derived_metrics(self, kpi_values: dict) -> dict:
        """Calculate derived metrics like margin, ACOS, etc."""
        gross_sales = kpi_values.get("gross_sales", Decimal("0"))
        net_profit = kpi_values.get("net_profit", Decimal("0"))
        ad_spend = kpi_values.get("ad_spend", Decimal("0"))
        orders = kpi_values.get("orders", 0)
        refunds = kpi_values.get("refunds", Decimal("0"))

        # Calculate margin
        if gross_sales and gross_sales > 0:
            kpi_values["margin"] = (net_profit / gross_sales) * 100

            # Calculate ACOS (Ad Cost of Sales)
            if ad_spend:
                kpi_values["acos"] = (ad_spend / gross_sales) * 100
                kpi_values["tacos"] = kpi_values["acos"]

        # Calculate refund rate
        if orders and orders > 0 and refunds:
            kpi_values["refund_rate"] = (refunds / Decimal(str(orders))) * 100

        return kpi_values

    def _build_kpi_data(self, kpi_values: dict) -> KPIData:
        """Build KPIData model from extracted values."""
        return KPIData(
            gross_sales=Decimal(str(kpi_values.get("gross_sales", 0))),
            units_sold=int(kpi_values.get("units_sold", 0)),
            orders=int(kpi_values.get("orders", 0)),
            refunds=Decimal(str(kpi_values.get("refunds", 0))),
            refund_rate=Decimal(str(kpi_values.get("refund_rate", 0))),
            promo_rebates=Decimal(str(kpi_values.get("promo_rebates", 0))),
            amazon_costs=Decimal(str(kpi_values.get("amazon_costs", 0))),
            cogs=Decimal(str(kpi_values.get("cogs", 0))),
            net_profit=Decimal(str(kpi_values.get("net_profit", 0))),
            margin=Decimal(str(kpi_values.get("margin", 0))),
            roi=Decimal(str(kpi_values.get("roi", 0))),
            ad_spend=Decimal(str(kpi_values.get("ad_spend", 0))),
            acos=Decimal(str(kpi_values.get("acos", 0))),
            tacos=Decimal(str(kpi_values.get("tacos", 0))),
        )


async def extract_kpis_from_page(page: Page) -> KPIData:
    """Convenience function to extract KPIs from a page."""
    extractor = KPIExtractor(page)
    return await extractor.extract_all_kpis()
