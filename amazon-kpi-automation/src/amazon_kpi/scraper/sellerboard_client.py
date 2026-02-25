"""Main Sellerboard scraper orchestrator."""

import asyncio
from datetime import date, timedelta
from typing import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ..config.constants import (
    SELLERBOARD_DASHBOARD_URL,
    SELLERBOARD_LOGIN_URL,
    PAGE_LOAD_TIMEOUT_MS,
)
from ..processing.models import KPIData, WeeklyReport
from ..secrets.secret_manager import get_sellerboard_credentials, SellerboardCredentials
from ..utils.exceptions import ScrapingError
from ..utils.retry import random_delay

from .auth import SellerboardAuth
from .extractors import KPIExtractor

logger = structlog.get_logger(__name__)


class SellerboardClient:
    """
    Main client for scraping KPI data from Sellerboard.

    Orchestrates browser automation, authentication, and data extraction.
    """

    def __init__(
        self,
        credentials: SellerboardCredentials | None = None,
        headless: bool = True,
    ):
        """
        Initialize Sellerboard client.

        Args:
            credentials: Login credentials (fetched from Secret Manager if None)
            headless: Whether to run browser in headless mode
        """
        self._credentials = credentials
        self._headless = headless
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator["SellerboardClient", None]:
        """
        Context manager for browser session.

        Usage:
            async with SellerboardClient().session() as client:
                report = await client.scrape_all()
        """
        await self._start_browser()
        try:
            await self._login()
            yield self
        finally:
            await self._close_browser()

    async def _start_browser(self) -> None:
        """Start Playwright browser."""
        logger.info("Starting browser", headless=self._headless)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
        )

        self._page = await self._context.new_page()
        self._page.set_default_timeout(60000)  # 60 second timeout for all operations

        logger.info("Browser started successfully")

    async def _close_browser(self) -> None:
        """Close browser and cleanup."""
        logger.info("Closing browser")

        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    async def _login(self) -> None:
        """Authenticate with Sellerboard."""
        if not self._page:
            raise ScrapingError("Browser not started")

        if not self._credentials:
            self._credentials = get_sellerboard_credentials()

        auth = SellerboardAuth(self._page, self._credentials)
        await auth.login()

        # Wait for dashboard to fully load
        await self._page.wait_for_load_state("networkidle", timeout=60000)
        await random_delay(5, 7)  # Extra wait for dashboard data to load

    async def scrape_all(self) -> WeeklyReport:
        """
        Scrape KPI data from the current dashboard view.

        Returns:
            WeeklyReport with KPI data
        """
        if not self._page:
            raise ScrapingError("Browser session not active")

        logger.info("Starting KPI scrape")

        extractor = KPIExtractor(self._page)

        # Extract current view data (7 days by default)
        logger.info("Extracting KPI data from dashboard")
        kpi_data = await extractor.extract_all_kpis()

        logger.info(
            "KPI data extracted",
            sales=str(kpi_data.gross_sales),
            orders=kpi_data.orders,
            units=kpi_data.units_sold,
            net_profit=str(kpi_data.net_profit),
        )

        # Build report
        report = self._build_report(kpi_data)

        logger.info("KPI scrape complete")

        return report

    def _build_report(self, kpi_data: KPIData) -> WeeklyReport:
        """Build WeeklyReport from extracted data."""
        from ..config.constants import Region

        # Calculate week dates
        today = date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        week_end = today - timedelta(days=days_since_sunday)
        week_start = week_end - timedelta(days=6)

        previous_week_end = week_start - timedelta(days=1)
        previous_week_start = previous_week_end - timedelta(days=6)

        # For now, put all data in US+CA region (default view)
        region_totals = {Region.US_CA: kpi_data}

        return WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            previous_week_start=previous_week_start,
            previous_week_end=previous_week_end,
            by_marketplace={},
            by_category={},
            region_totals=region_totals,
            grand_total=kpi_data,
        )


async def run_scraper(headless: bool = True) -> WeeklyReport:
    """
    Convenience function to run the scraper.

    Args:
        headless: Whether to run browser in headless mode

    Returns:
        WeeklyReport with KPI data
    """
    client = SellerboardClient(headless=headless)
    async with client.session() as session:
        return await session.scrape_all()
