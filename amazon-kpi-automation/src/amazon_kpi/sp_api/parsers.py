"""Parsers for converting SP-API response data into internal models.

Supports:
  - Sales & Traffic Data Kiosk JSONL → KPIData / MarketplaceKPIs
  - Search Query Performance JSONL → pandas DataFrame
  - Brand Analytics JSONL → pandas DataFrame
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

import pandas as pd
import structlog

from ..config.constants import Marketplace
from ..config.sku_categories import get_category_for_sku
from ..processing.models import KPIData, MarketplaceKPIs

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Sales & Traffic → KPIData
# ---------------------------------------------------------------------------


def parse_sales_traffic(
    records: list[dict[str, Any]],
    marketplace: Marketplace,
) -> MarketplaceKPIs:
    """Parse Data Kiosk salesAndTrafficByAsin JSONL records into MarketplaceKPIs.

    Each record is one JSONL line. The structure varies slightly depending on
    the Data Kiosk schema version, so we handle nested keys defensively.

    Args:
        records: Parsed JSONL records from Data Kiosk.
        marketplace: The marketplace these records belong to.

    Returns:
        MarketplaceKPIs with per-category KPIData and an overall total.
    """
    category_kpis: dict[str, list[KPIData]] = defaultdict(list)
    uncategorized: list[KPIData] = []

    for record in records:
        # Data Kiosk wraps data inside the query name key
        items = _extract_items(record, "salesAndTrafficByAsin")

        for item in items:
            kpi = _item_to_kpi_data(item)
            sku = item.get("sku", "")

            category = get_category_for_sku(sku) if sku else None
            if category:
                category_kpis[category.name].append(kpi)
            else:
                uncategorized.append(kpi)

    # Aggregate per category
    categories: dict[str, KPIData] = {}
    for cat_name, kpis in category_kpis.items():
        categories[cat_name] = _sum_kpis(kpis)

    # Include uncategorized as "other" if any
    if uncategorized:
        categories["other"] = _sum_kpis(uncategorized)

    # Overall total
    all_kpis = list(categories.values())
    total = _sum_kpis(all_kpis) if all_kpis else None

    logger.info(
        "Parsed sales & traffic data",
        marketplace=marketplace.value,
        categories=len(categories),
        total_records=len(records),
    )

    return MarketplaceKPIs(
        marketplace=marketplace,
        categories=categories,
        total=total,
    )


def parse_economics(
    records: list[dict[str, Any]],
    marketplace: Marketplace,
) -> MarketplaceKPIs:
    """Parse Data Kiosk economics JSONL records into MarketplaceKPIs.

    Extracts: ad_spend, ppc_sales (from ads), amazon_costs (fees), net_profit (netProceeds).
    """
    category_kpis: dict[str, list[KPIData]] = defaultdict(list)
    uncategorized: list[KPIData] = []

    for record in records:
        items = _extract_items(record, "economics")

        for item in items:
            kpi = _economics_item_to_kpi_data(item)
            sku = item.get("msku", "")

            category = get_category_for_sku(sku) if sku else None
            if category:
                category_kpis[category.name].append(kpi)
            else:
                uncategorized.append(kpi)

    categories: dict[str, KPIData] = {}
    for cat_name, kpis in category_kpis.items():
        categories[cat_name] = _sum_kpis(kpis)

    if uncategorized:
        categories["other"] = _sum_kpis(uncategorized)

    all_kpis = list(categories.values())
    total = _sum_kpis(all_kpis) if all_kpis else None

    logger.info(
        "Parsed economics data",
        marketplace=marketplace.value,
        categories=len(categories),
        total_records=len(records),
    )

    return MarketplaceKPIs(
        marketplace=marketplace,
        categories=categories,
        total=total,
    )


def _economics_item_to_kpi_data(item: dict[str, Any]) -> KPIData:
    """Convert a single economics item to KPIData (ads, fees, net proceeds).

    Schema: analytics_economics_2024_03_15
    - ads: list of {adTypeName, charge: {totalAmount: {amount, currencyCode}}}
    - cost: {costOfGoodsSold: {amount, currencyCode}}
    - netProceeds: {total: {amount, currencyCode}}
    """
    # Ad spend — sum across all ad types (Sponsored Products, Brands, etc.)
    ad_spend = Decimal("0")
    ads_list = item.get("ads", []) or []
    for ad in ads_list:
        charge = ad.get("charge", {}) or {}
        total_amount = charge.get("totalAmount", {}) or {}
        ad_spend += Decimal(str(total_amount.get("amount", 0)))

    # Net proceeds (= net profit from Amazon's perspective)
    net_proceeds = item.get("netProceeds", {}) or {}
    net_total = net_proceeds.get("total", {}) or {}
    net_profit = Decimal(str(net_total.get("amount", 0)))

    # COGS
    cost_obj = item.get("cost", {}) or {}
    cogs_obj = cost_obj.get("costOfGoodsSold", {}) or {}
    cogs = Decimal(str(cogs_obj.get("amount", 0)))

    # Sales data from economics (for PPC sales approximation)
    sales = item.get("sales", {}) or {}
    ordered_sales = sales.get("orderedProductSales", {}) or {}
    gross_sales = Decimal(str(ordered_sales.get("amount", 0)))

    # PPC Sales approximation: if there's ad spend, attribute the product's
    # sales as PPC-driven. This is an approximation — the actual PPC sales
    # come from the Amazon Ads API which we don't use yet.
    ppc_sales = gross_sales if ad_spend > 0 else Decimal("0")

    return KPIData(
        gross_sales=gross_sales,
        ad_spend=ad_spend,
        ppc_sales=ppc_sales,
        net_profit=net_profit,
        amazon_costs=Decimal("0"),
        cogs=cogs,
        units_sold=int(sales.get("unitsOrdered", 0)),
        orders=0,  # economics doesn't have order count
        refunds=Decimal(str(sales.get("unitsRefunded", 0))),
    )


def parse_sales_traffic_by_date(
    records: list[dict[str, Any]],
    marketplace: Marketplace,
) -> pd.DataFrame:
    """Parse salesAndTrafficByDate JSONL records into a DataFrame.

    Returns a DataFrame with columns: date, marketplace, ordered_sales,
    units_ordered, page_views, sessions, buy_box_pct, unit_session_pct.
    """
    rows: list[dict[str, Any]] = []

    for record in records:
        items = _extract_items(record, "salesAndTrafficByDate")

        for item in items:
            sales = item.get("sales", {})
            traffic = item.get("traffic", {})
            ordered_sales = sales.get("orderedProductSales", {})

            rows.append({
                "date": item.get("startDate", ""),
                "marketplace": marketplace.value,
                "ordered_sales": float(ordered_sales.get("amount", 0)),
                "currency": ordered_sales.get("currencyCode", ""),
                "units_ordered": int(sales.get("unitsOrdered", 0)),
                "units_refunded": int(sales.get("unitsRefunded", 0)),
                "refund_rate": float(sales.get("refundRate", 0)),
                "total_order_items": int(sales.get("totalOrderItems", 0)),
                "browser_page_views": int(traffic.get("browserPageViews", 0)),
                "mobile_page_views": int(traffic.get("mobileAppPageViews", 0)),
                "browser_sessions": int(traffic.get("browserSessions", 0)),
                "mobile_sessions": int(traffic.get("mobileAppSessions", 0)),
                "buy_box_pct": float(traffic.get("buyBoxPercentage", 0)),
                "unit_session_pct": float(traffic.get("unitSessionPercentage", 0)),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Search Query Performance → DataFrame
# ---------------------------------------------------------------------------


def parse_search_query_performance(
    records: list[dict[str, Any]],
    marketplace: Marketplace,
) -> pd.DataFrame:
    """Parse Search Query Performance JSONL records into a DataFrame.

    Returns a DataFrame with columns: search_query, asin, impressions, clicks,
    click_rate, cart_adds, purchases, purchase_rate.
    """
    rows: list[dict[str, Any]] = []

    for record in records:
        items = _extract_items(record, "searchQueryPerformanceByQueryASIN")

        for item in items:
            rows.append({
                "marketplace": marketplace.value,
                "start_date": item.get("startDate", ""),
                "end_date": item.get("endDate", ""),
                "search_query": item.get("searchQuery", ""),
                "asin": item.get("asin", ""),
                "impressions": int(item.get("queryImpressions", 0)),
                "clicks": int(item.get("queryClicks", 0)),
                "click_rate": float(item.get("queryClickRate", 0)),
                "cart_adds": int(item.get("queryCartAdds", 0)),
                "purchases": int(item.get("queryPurchases", 0)),
                "purchase_rate": float(item.get("queryPurchaseRate", 0)),
            })

    logger.info(
        "Parsed SQP data",
        marketplace=marketplace.value,
        rows=len(rows),
    )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Brand Analytics — Market Basket → DataFrame
# ---------------------------------------------------------------------------


def parse_market_basket(
    records: list[dict[str, Any]],
    marketplace: Marketplace,
) -> pd.DataFrame:
    """Parse Market Basket JSONL records into a DataFrame."""
    rows: list[dict[str, Any]] = []

    for record in records:
        items = _extract_items(record, "marketBasketByAsin")

        for item in items:
            rows.append({
                "marketplace": marketplace.value,
                "start_date": item.get("startDate", ""),
                "end_date": item.get("endDate", ""),
                "asin": item.get("asin", ""),
                "purchased_with_asin": item.get("purchasedWithAsin", ""),
                "purchased_with_title": item.get("purchasedWithTitle", ""),
                "combination_pct": float(item.get("combinationPercentage", 0)),
            })

    logger.info(
        "Parsed market basket data",
        marketplace=marketplace.value,
        rows=len(rows),
    )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Brand Analytics — Repeat Purchase → DataFrame
# ---------------------------------------------------------------------------


def parse_repeat_purchase(
    records: list[dict[str, Any]],
    marketplace: Marketplace,
) -> pd.DataFrame:
    """Parse Repeat Purchase JSONL records into a DataFrame."""
    rows: list[dict[str, Any]] = []

    for record in records:
        items = _extract_items(record, "repeatPurchaseByAsin")

        for item in items:
            rows.append({
                "marketplace": marketplace.value,
                "start_date": item.get("startDate", ""),
                "end_date": item.get("endDate", ""),
                "asin": item.get("asin", ""),
                "orders_total": int(item.get("ordersTotal", 0)),
                "orders_repeat": int(item.get("ordersRepeat", 0)),
                "repeat_purchase_rate": float(item.get("repeatPurchaseRate", 0)),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_items(record: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Extract data items from a JSONL record.

    Data Kiosk nests data under the schema version key, then the query name key.
    This traverses the structure to find the actual data list.
    """
    # Try direct key access first
    if key in record:
        data = record[key]
        return data if isinstance(data, list) else [data]

    # Try navigating nested structure (e.g., analytics_salesAndTraffic_2024_04_24.salesAndTrafficByAsin)
    for top_key, top_value in record.items():
        if isinstance(top_value, dict) and key in top_value:
            data = top_value[key]
            return data if isinstance(data, list) else [data]

    # Fall back to treating the entire record as a single item
    return [record]


def _item_to_kpi_data(item: dict[str, Any]) -> KPIData:
    """Convert a single sales & traffic item to KPIData."""
    sales = item.get("sales", {})
    ordered_sales = sales.get("orderedProductSales", {})

    return KPIData(
        gross_sales=Decimal(str(ordered_sales.get("amount", 0))),
        units_sold=int(sales.get("unitsOrdered", 0)),
        orders=int(sales.get("totalOrderItems", 0)),
        refunds=Decimal(str(sales.get("unitsRefunded", 0))),
        refund_rate=Decimal(str(sales.get("refundRate", 0))),
    )


def _sum_kpis(kpis: list[KPIData]) -> KPIData:
    """Sum a list of KPIData using the existing __add__ method."""
    if not kpis:
        return KPIData()
    result = kpis[0]
    for k in kpis[1:]:
        result = result + k
    return result
