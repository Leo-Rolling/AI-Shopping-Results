"""Data fetching orchestration for the Streamlit dashboard.

Wraps SP-API clients with caching and parallel marketplace fetching.
"""

from __future__ import annotations

import json
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog

from ..config.constants import (
    MARKETPLACES,
    MARKETPLACE_SP_API_IDS,
    REGIONS,
    EUR_TO_USD_RATE,
    Marketplace,
    Region,
)
from ..config.sku_categories import CATEGORIES, get_category_for_sku
from ..processing.models import (
    CategoryKPIs,
    KPIData,
    MarketplaceKPIs,
    WeeklyReport,
)
from ..sp_api.client import SPAPIClientFactory
from ..sp_api.data_kiosk import DataKioskService
from ..sp_api.queries import SALES_TRAFFIC_BY_ASIN, ECONOMICS_BY_MSKU, build_query
from ..sp_api.parsers import parse_sales_traffic, parse_economics

logger = structlog.get_logger(__name__)

CACHE_DIR = Path("/tmp/kpi_cache")


def _merge_kpi_data(sales: KPIData, econ: KPIData) -> KPIData:
    """Merge economics data into sales data, keeping sales for shared fields."""
    return KPIData(
        gross_sales=sales.gross_sales,
        units_sold=sales.units_sold,
        orders=sales.orders,
        refunds=sales.refunds,
        refund_rate=sales.refund_rate,
        promo_rebates=sales.promo_rebates,
        # From economics
        ad_spend=econ.ad_spend,
        ppc_sales=econ.ppc_sales,
        net_profit=econ.net_profit,
        amazon_costs=econ.amazon_costs,
        cogs=econ.cogs,
    )


def _merge_marketplace_kpis(
    sales: MarketplaceKPIs,
    econ: MarketplaceKPIs,
    marketplace: Marketplace,
) -> MarketplaceKPIs:
    """Merge economics MarketplaceKPIs into sales MarketplaceKPIs."""
    merged_categories: dict[str, KPIData] = {}

    # Merge matching categories
    all_cats = set(sales.categories.keys()) | set(econ.categories.keys())
    for cat in all_cats:
        s = sales.categories.get(cat, KPIData())
        e = econ.categories.get(cat, KPIData())
        merged_categories[cat] = _merge_kpi_data(s, e)

    # Merge totals
    merged_total = None
    if sales.total or econ.total:
        s_total = sales.total or KPIData()
        e_total = econ.total or KPIData()
        merged_total = _merge_kpi_data(s_total, e_total)

    return MarketplaceKPIs(
        marketplace=marketplace,
        categories=merged_categories,
        total=merged_total,
    )


def _cache_key(week_start: date, week_end: date) -> str:
    raw = f"{week_start.isoformat()}_{week_end.isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()


class DashboardDataService:
    """Fetches and caches SP-API data for the dashboard."""

    def __init__(self) -> None:
        self._factory = SPAPIClientFactory()
        self._data_kiosk = DataKioskService(self._factory)

    def clear_cache(self) -> None:
        """Delete all filesystem cache files."""
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*.json"):
                f.unlink()
            logger.info("Cleared filesystem cache")

    def has_cached_data(self, week_start: date, week_end: date) -> bool:
        """Check if cached data exists for the given week."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{_cache_key(week_start, week_end)}.json"
        return cache_file.exists()

    def fetch_weekly_data(
        self,
        week_start: date,
        week_end: date,
        progress_callback: Any = None,
    ) -> dict[Marketplace, MarketplaceKPIs]:
        """Fetch Sales & Traffic data for all marketplaces for a given week.

        Args:
            week_start: Monday of the target week.
            week_end: Sunday of the target week.
            progress_callback: Optional callable(marketplace_name, status) for UI updates.

        Returns:
            Dict mapping Marketplace to MarketplaceKPIs.
        """
        # Check file cache first
        cached = self._load_from_cache(week_start, week_end)
        if cached is not None:
            logger.info("Loaded data from cache", week_start=str(week_start))
            return cached

        results: dict[Marketplace, MarketplaceKPIs] = {}

        # Group marketplaces by seller account to avoid Data Kiosk rate limits.
        # Process one marketplace at a time per account (2 accounts in parallel).
        from ..config.constants import MARKETPLACE_ACCOUNT, SellerAccount
        account_groups: dict[SellerAccount, list[Marketplace]] = {}
        for mp in MARKETPLACES:
            acct = MARKETPLACE_ACCOUNT[mp]
            account_groups.setdefault(acct, []).append(mp)

        def _fetch_account_group(marketplaces: list[Marketplace]) -> dict[Marketplace, MarketplaceKPIs]:
            """Fetch marketplaces sequentially within one account."""
            group_results: dict[Marketplace, MarketplaceKPIs] = {}
            for mp in marketplaces:
                try:
                    mp_kpis = self._fetch_single_marketplace(mp, week_start, week_end)
                    group_results[mp] = mp_kpis
                    if progress_callback:
                        progress_callback(mp.value, "done")
                    logger.info("Fetched marketplace data", marketplace=mp.value)
                except Exception as e:
                    logger.error("Failed to fetch marketplace", marketplace=mp.value, error=str(e))
                    if progress_callback:
                        progress_callback(mp.value, f"error: {e}")
                    group_results[mp] = MarketplaceKPIs(marketplace=mp)
            return group_results

        # Run account groups in parallel (EU_UK and NA simultaneously)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(_fetch_account_group, mps): acct
                for acct, mps in account_groups.items()
            }
            for future in as_completed(futures):
                results.update(future.result())

        # Save to cache
        self._save_to_cache(week_start, week_end, results)

        return results

    def _fetch_single_marketplace(
        self,
        marketplace: Marketplace,
        week_start: date,
        week_end: date,
    ) -> MarketplaceKPIs:
        """Fetch Sales & Traffic + Economics data for a single marketplace."""
        marketplace_id = MARKETPLACE_SP_API_IDS[marketplace]

        # 1. Sales & Traffic (orders, revenue, refunds, traffic)
        sales_query = build_query(
            SALES_TRAFFIC_BY_ASIN,
            start_date=week_start.isoformat(),
            end_date=week_end.isoformat(),
            marketplace_id=marketplace_id,
        )
        sales_records = self._data_kiosk.execute_query(
            marketplace=marketplace,
            query=sales_query,
        )
        sales_kpis = parse_sales_traffic(sales_records, marketplace)

        # 2. Economics (ad spend, fees, net proceeds)
        try:
            econ_query = build_query(
                ECONOMICS_BY_MSKU,
                start_date=week_start.isoformat(),
                end_date=week_end.isoformat(),
                marketplace_id=marketplace_id,
            )
            econ_records = self._data_kiosk.execute_query(
                marketplace=marketplace,
                query=econ_query,
            )
            econ_kpis = parse_economics(econ_records, marketplace)

            # Merge economics into sales data
            return _merge_marketplace_kpis(sales_kpis, econ_kpis, marketplace)
        except Exception as e:
            logger.warning(
                "Economics query failed, using sales-only data",
                marketplace=marketplace.value,
                error=str(e),
            )
            return sales_kpis

    def build_weekly_report(
        self,
        current_data: dict[Marketplace, MarketplaceKPIs],
        previous_data: dict[Marketplace, MarketplaceKPIs],
        week_start: date,
        week_end: date,
        eur_usd_rate: float = EUR_TO_USD_RATE,
    ) -> tuple[WeeklyReport, WeeklyReport]:
        """Build two WeeklyReport objects (current + previous) with aggregation.

        Returns:
            Tuple of (current_report, previous_report).
        """
        prev_start = week_start - timedelta(days=7)
        prev_end = week_end - timedelta(days=7)

        current_report = self._build_report(
            current_data, week_start, week_end, prev_start, prev_end, eur_usd_rate
        )
        previous_report = self._build_report(
            previous_data, prev_start, prev_end,
            prev_start - timedelta(days=7), prev_start - timedelta(days=1),
            eur_usd_rate,
        )

        return current_report, previous_report

    def _build_report(
        self,
        data: dict[Marketplace, MarketplaceKPIs],
        week_start: date,
        week_end: date,
        prev_week_start: date,
        prev_week_end: date,
        eur_usd_rate: float,
    ) -> WeeklyReport:
        """Build a single WeeklyReport from marketplace data."""
        rate = Decimal(str(eur_usd_rate))

        # Build by_category from marketplace data
        category_data: dict[str, dict[Marketplace, KPIData]] = {}
        for mp, mp_kpis in data.items():
            for cat_name, kpi_data in mp_kpis.categories.items():
                if cat_name not in category_data:
                    category_data[cat_name] = {}
                category_data[cat_name][mp] = kpi_data

        by_category: dict[str, CategoryKPIs] = {}
        for cat_name, mp_data in category_data.items():
            # Get display name from CATEGORIES config
            display_name = cat_name.replace("_", " ").title()
            for cat in CATEGORIES:
                if cat.name == cat_name:
                    display_name = cat.display_name
                    break

            # Calculate regional aggregations
            regions: dict[Region, KPIData] = {}
            for region, region_mps in REGIONS.items():
                region_kpis = [mp_data[mp] for mp in region_mps if mp in mp_data]
                if region_kpis:
                    total = region_kpis[0]
                    for k in region_kpis[1:]:
                        total = total + k
                    regions[region] = total

            by_category[cat_name] = CategoryKPIs.model_construct(
                category_name=cat_name,
                category_display_name=display_name,
                marketplaces=mp_data,
                regions=regions,
            )

        # Overall region totals
        region_totals: dict[Region, KPIData] = {}
        for region, region_mps in REGIONS.items():
            region_kpis = []
            for mp in region_mps:
                if mp in data and data[mp].total:
                    region_kpis.append(data[mp].total)
            if region_kpis:
                total = region_kpis[0]
                for k in region_kpis[1:]:
                    total = total + k
                region_totals[region] = total

        # Grand total (EU converted to USD + NA)
        grand_total = None
        eu_total = region_totals.get(Region.EU_UK)
        na_total = region_totals.get(Region.US_CA)
        if eu_total and na_total:
            grand_total = eu_total.convert_currency(rate) + na_total
        elif na_total:
            grand_total = na_total
        elif eu_total:
            grand_total = eu_total.convert_currency(rate)

        return WeeklyReport.model_construct(
            week_start=week_start,
            week_end=week_end,
            previous_week_start=prev_week_start,
            previous_week_end=prev_week_end,
            by_marketplace=data,
            by_category=by_category,
            region_totals=region_totals,
            grand_total=grand_total,
        )

    def _load_from_cache(
        self, week_start: date, week_end: date
    ) -> dict[Marketplace, MarketplaceKPIs] | None:
        """Load cached data from filesystem."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{_cache_key(week_start, week_end)}.json"
        if not cache_file.exists():
            return None

        try:
            raw = json.loads(cache_file.read_text())
            result: dict[Marketplace, MarketplaceKPIs] = {}
            for mp_str, mp_data in raw.items():
                mp = Marketplace(mp_str)
                result[mp] = MarketplaceKPIs.model_validate(mp_data)
            return result
        except Exception as e:
            logger.warning("Cache load failed", error=str(e))
            return None

    def _save_to_cache(
        self,
        week_start: date,
        week_end: date,
        data: dict[Marketplace, MarketplaceKPIs],
    ) -> None:
        """Save data to filesystem cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{_cache_key(week_start, week_end)}.json"
        try:
            raw = {mp.value: mp_kpis.model_dump(mode="json") for mp, mp_kpis in data.items()}
            cache_file.write_text(json.dumps(raw))
            logger.info("Saved data to cache", week_start=str(week_start))
        except Exception as e:
            logger.warning("Cache save failed", error=str(e))
