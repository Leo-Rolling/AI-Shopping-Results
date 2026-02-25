"""Regional aggregation logic for KPI data."""

from decimal import Decimal

import structlog

from ..config.constants import (
    Marketplace,
    Region,
    REGIONS,
    EUR_TO_USD_RATE,
    CURRENCY_SYMBOLS,
)
from .models import KPIData, WeeklyReport, CategoryKPIs

logger = structlog.get_logger(__name__)


def aggregate_regions(report: WeeklyReport) -> WeeklyReport:
    """
    Add regional aggregations to a WeeklyReport.

    Calculates:
    - EU+UK: Sum of UK, DE, IT, FR, ES
    - US+CA: Sum of US, CA

    Args:
        report: WeeklyReport with per-marketplace data

    Returns:
        Updated WeeklyReport with regional aggregations
    """
    logger.info("Calculating regional aggregations")

    # Update each category with regional data
    updated_by_category: dict[str, CategoryKPIs] = {}

    for category_name, category_kpis in report.by_category.items():
        regions: dict[Region, KPIData] = {}

        # Calculate EU+UK
        eu_uk_data = _aggregate_marketplaces(
            category_kpis.marketplaces,
            REGIONS[Region.EU_UK],
        )
        if eu_uk_data:
            regions[Region.EU_UK] = eu_uk_data

        # Calculate US+CA
        us_ca_data = _aggregate_marketplaces(
            category_kpis.marketplaces,
            REGIONS[Region.US_CA],
        )
        if us_ca_data:
            regions[Region.US_CA] = us_ca_data

        updated_by_category[category_name] = CategoryKPIs(
            category_name=category_kpis.category_name,
            category_display_name=category_kpis.category_display_name,
            marketplaces=category_kpis.marketplaces,
            regions=regions,
        )

        logger.debug(
            "Category regional aggregation complete",
            category=category_name,
            eu_uk_gross=str(eu_uk_data.gross_sales) if eu_uk_data else None,
            us_ca_gross=str(us_ca_data.gross_sales) if us_ca_data else None,
        )

    # Calculate overall region totals
    region_totals = _calculate_region_totals(updated_by_category)

    return WeeklyReport(
        week_start=report.week_start,
        week_end=report.week_end,
        previous_week_start=report.previous_week_start,
        previous_week_end=report.previous_week_end,
        by_marketplace=report.by_marketplace,
        by_category=updated_by_category,
        region_totals=region_totals,
        grand_total=report.grand_total,
    )


def aggregate_total(report: WeeklyReport) -> WeeklyReport:
    """
    Calculate grand total across all regions in USD.

    Converts EU+UK from EUR to USD before summing with US+CA.

    Args:
        report: WeeklyReport with regional data

    Returns:
        Updated WeeklyReport with grand total
    """
    logger.info("Calculating grand total")

    if not report.region_totals:
        logger.warning("No regional totals available for grand total calculation")
        return report

    eu_uk_total = report.region_totals.get(Region.EU_UK)
    us_ca_total = report.region_totals.get(Region.US_CA)

    grand_total: KPIData | None = None

    if eu_uk_total and us_ca_total:
        # Convert EU+UK to USD
        eu_uk_usd = eu_uk_total.convert_currency(Decimal(str(EUR_TO_USD_RATE)))
        grand_total = eu_uk_usd + us_ca_total

        logger.info(
            "Grand total calculated",
            eu_uk_eur=str(eu_uk_total.gross_sales),
            eu_uk_usd=str(eu_uk_usd.gross_sales),
            us_ca_usd=str(us_ca_total.gross_sales),
            total_usd=str(grand_total.gross_sales),
        )
    elif eu_uk_total:
        grand_total = eu_uk_total.convert_currency(Decimal(str(EUR_TO_USD_RATE)))
    elif us_ca_total:
        grand_total = us_ca_total

    return WeeklyReport(
        week_start=report.week_start,
        week_end=report.week_end,
        previous_week_start=report.previous_week_start,
        previous_week_end=report.previous_week_end,
        by_marketplace=report.by_marketplace,
        by_category=report.by_category,
        region_totals=report.region_totals,
        grand_total=grand_total,
    )


def _aggregate_marketplaces(
    marketplace_data: dict[Marketplace, KPIData],
    marketplaces: list[Marketplace],
) -> KPIData | None:
    """
    Aggregate KPI data for a list of marketplaces.

    Args:
        marketplace_data: Marketplace -> KPIData mapping
        marketplaces: List of marketplaces to aggregate

    Returns:
        Aggregated KPIData or None if no data
    """
    data_to_sum: list[KPIData] = []

    for marketplace in marketplaces:
        if marketplace in marketplace_data:
            data_to_sum.append(marketplace_data[marketplace])

    if not data_to_sum:
        return None

    # Sum all KPI data
    result = data_to_sum[0]
    for kpi_data in data_to_sum[1:]:
        result = result + kpi_data

    return result


def _calculate_region_totals(
    by_category: dict[str, CategoryKPIs],
) -> dict[Region, KPIData]:
    """
    Calculate total KPIs for each region across all categories.

    Args:
        by_category: Category -> CategoryKPIs mapping

    Returns:
        Region -> KPIData totals
    """
    region_totals: dict[Region, KPIData] = {}

    for region in [Region.EU_UK, Region.US_CA]:
        region_data: list[KPIData] = []

        for category_kpis in by_category.values():
            if region in category_kpis.regions:
                region_data.append(category_kpis.regions[region])

        if region_data:
            total = region_data[0]
            for kpi_data in region_data[1:]:
                total = total + kpi_data
            region_totals[region] = total

    return region_totals


def get_marketplace_currency(marketplace: Marketplace) -> str:
    """Get currency symbol for a marketplace."""
    return CURRENCY_SYMBOLS.get(marketplace, "$")


def is_eur_marketplace(marketplace: Marketplace) -> bool:
    """Check if marketplace uses EUR currency."""
    return marketplace in [
        Marketplace.DE,
        Marketplace.IT,
        Marketplace.FR,
        Marketplace.ES,
    ]


def is_usd_marketplace(marketplace: Marketplace) -> bool:
    """Check if marketplace uses USD currency."""
    return marketplace in [Marketplace.US, Marketplace.CA]
