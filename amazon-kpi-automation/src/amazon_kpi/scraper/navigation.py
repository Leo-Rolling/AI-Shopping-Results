"""Page navigation and filter management for Sellerboard."""

import structlog
from playwright.async_api import Page

from ..config.constants import (
    Marketplace,
    DateRange,
    SELLERBOARD_DASHBOARD_URL,
    PAGE_LOAD_TIMEOUT_MS,
    ELEMENT_TIMEOUT_MS,
)
from ..config.sku_categories import Category
from ..utils.exceptions import NavigationError
from ..utils.retry import random_delay, async_with_retry

logger = structlog.get_logger(__name__)


# Account name mapping for Sellerboard accounts
ACCOUNT_NAMES = {
    "US": "AMZ_US",
    "EU+UK": "AMZ_EU+UK",
    "JP": "AMZ_JP",
}


class SellerboardNavigator:
    """Handles navigation and filter selection in Sellerboard."""

    # CSS selectors for navigation elements
    SELECTORS = {
        # Account/Marketplace selector (top right dropdown)
        "account_dropdown": 'a[data-accountfilter-opener], .accountFilter-selected',
        "account_option": '.accountFilter-dropdown a, .accountFilter-list a',
        "account_item_template": 'a:has-text("{name}")',

        # Period selector
        "period_button": 'button:has-text("Period"), .period-selector, [class*="period"]',
        "period_dropdown": '.dropdown-menu, .period-dropdown',
        "period_option_template": 'text="{text}"',

        # Preset period options
        "last_week": 'text="Last week"',
        "this_week": 'text="This week"',
        "two_weeks_ago": 'text="2 weeks ago"',
        "yesterday_7days": 'text="7 days"',

        # Filter button
        "filter_button": 'button:has-text("Filter")',

        # Search box for product filtering
        "search_box": 'input[placeholder*="Search"], .search-input',

        # Loading indicators
        "loading_spinner": '.loading, .spinner, [class*="loading"]',
        "tiles_loaded": '.dashboard-tile, .tile, [class*="tile"]',
    }

    def __init__(self, page: Page):
        """Initialize navigator."""
        self._page = page
        self._current_account: str | None = None
        self._current_period: str | None = None

    async def navigate_to_dashboard(self) -> None:
        """Navigate to the main dashboard page."""
        logger.info("Navigating to dashboard")

        try:
            # Check if already on dashboard
            if "dashboard" in self._page.url:
                logger.info("Already on dashboard")
                # Wait for dashboard to be fully loaded
                await self._page.wait_for_load_state("networkidle")
                await random_delay(2, 3)
                return

            await self._page.goto(
                SELLERBOARD_DASHBOARD_URL,
                wait_until="networkidle",
                timeout=PAGE_LOAD_TIMEOUT_MS,
            )
            await self._wait_for_data_load()
            await random_delay(2, 3)
            logger.info("Dashboard loaded successfully")

        except Exception as e:
            raise NavigationError(
                "Failed to navigate to dashboard",
                url=SELLERBOARD_DASHBOARD_URL,
                details={"error": str(e)},
            ) from e

    @async_with_retry(max_attempts=3)
    async def select_account(self, account_name: str) -> None:
        """
        Select an account from the dropdown.

        Args:
            account_name: Account name (e.g., "AMZ_US", "AMZ_EU+UK")
        """
        if self._current_account == account_name:
            logger.debug("Account already selected", account=account_name)
            return

        logger.info("Selecting account", account=account_name)

        try:
            # Try multiple selectors for the account dropdown
            dropdown = None
            dropdown_selectors = [
                'a[data-accountfilter-opener]',
                '.accountFilter-selected',
                'a[title*="AMZ"]',
                '.newLayout[data-accountfilter-opener]',
            ]

            for selector in dropdown_selectors:
                dropdown = await self._page.query_selector(selector)
                if dropdown:
                    logger.debug(f"Found dropdown with selector: {selector}")
                    break

            if not dropdown:
                # Wait with longer timeout
                dropdown = await self._page.wait_for_selector(
                    self.SELECTORS["account_dropdown"],
                    timeout=PAGE_LOAD_TIMEOUT_MS,
                    state="visible",
                )

            if not dropdown:
                raise NavigationError("Account dropdown not found")

            await dropdown.click()
            await random_delay(0.5, 1)

            # Find and click the account option
            option_selector = f'a:has-text("{account_name}")'
            option = await self._page.wait_for_selector(
                option_selector,
                timeout=ELEMENT_TIMEOUT_MS,
            )

            if not option:
                raise NavigationError(f"Account option not found: {account_name}")

            await option.click()
            await self._wait_for_data_load()

            self._current_account = account_name
            logger.info("Account selected", account=account_name)

        except NavigationError:
            raise
        except Exception as e:
            raise NavigationError(
                f"Failed to select account: {account_name}",
                details={"error": str(e)},
            ) from e

    @async_with_retry(max_attempts=3)
    async def select_period(self, period_text: str) -> None:
        """
        Select a period from the dropdown.

        Args:
            period_text: Period text (e.g., "Last week", "This week")
        """
        logger.info("Selecting period", period=period_text)

        try:
            # Click period button
            period_btn = await self._page.wait_for_selector(
                self.SELECTORS["period_button"],
                timeout=ELEMENT_TIMEOUT_MS,
            )

            if not period_btn:
                raise NavigationError("Period button not found")

            await period_btn.click()
            await random_delay(0.5, 1)

            # Click the period option
            option = await self._page.wait_for_selector(
                f'text="{period_text}"',
                timeout=ELEMENT_TIMEOUT_MS,
            )

            if not option:
                raise NavigationError(f"Period option not found: {period_text}")

            await option.click()
            await self._wait_for_data_load()

            self._current_period = period_text
            logger.info("Period selected", period=period_text)

        except NavigationError:
            raise
        except Exception as e:
            raise NavigationError(
                f"Failed to select period: {period_text}",
                details={"error": str(e)},
            ) from e

    async def select_last_week(self) -> None:
        """Select 'Last week' period."""
        await self.select_period("Last week")

    async def select_previous_week(self) -> None:
        """Select '2 weeks ago' period."""
        await self.select_period("2 weeks ago")

    async def search_products(self, search_term: str) -> None:
        """
        Search for products using the search box.

        Args:
            search_term: SKU or product name to search
        """
        logger.info("Searching for products", search_term=search_term)

        try:
            search_box = await self._page.query_selector(self.SELECTORS["search_box"])
            if search_box:
                await search_box.fill(search_term)
                await random_delay(0.5, 1)
                await search_box.press("Enter")
                await self._wait_for_data_load()
            else:
                logger.warning("Search box not found")

        except Exception as e:
            logger.warning("Error searching products", error=str(e))

    async def clear_search(self) -> None:
        """Clear the search box."""
        try:
            search_box = await self._page.query_selector(self.SELECTORS["search_box"])
            if search_box:
                await search_box.fill("")
                await search_box.press("Enter")
                await self._wait_for_data_load()
        except Exception as e:
            logger.warning("Error clearing search", error=str(e))

    async def _wait_for_data_load(self, timeout_ms: int = PAGE_LOAD_TIMEOUT_MS) -> None:
        """Wait for data to load after navigation/filter changes."""
        try:
            # Wait for any loading indicator to disappear
            spinner = await self._page.query_selector(self.SELECTORS["loading_spinner"])
            if spinner:
                await self._page.wait_for_selector(
                    self.SELECTORS["loading_spinner"],
                    state="hidden",
                    timeout=timeout_ms,
                )

            # Wait for network to be idle
            await self._page.wait_for_load_state("networkidle", timeout=timeout_ms)

            # Additional wait for dynamic content
            await random_delay(1, 2)

        except Exception as e:
            logger.debug("Wait for data load completed with warning", error=str(e))

    async def get_current_url_params(self) -> dict:
        """Extract current URL parameters."""
        from urllib.parse import urlparse, parse_qs

        url = self._page.url
        parsed = urlparse(url)
        return parse_qs(parsed.query)

    @property
    def current_account(self) -> str | None:
        """Get the currently selected account."""
        return self._current_account

    @property
    def current_period(self) -> str | None:
        """Get the currently selected period."""
        return self._current_period
