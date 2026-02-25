"""Sellerboard authentication and session management."""

import structlog
from playwright.async_api import Page, BrowserContext

from ..config.constants import (
    SELLERBOARD_LOGIN_URL,
    SELLERBOARD_DASHBOARD_URL,
    PAGE_LOAD_TIMEOUT_MS,
    ELEMENT_TIMEOUT_MS,
)
from ..secrets.secret_manager import SellerboardCredentials
from ..utils.exceptions import AuthenticationError
from ..utils.retry import random_delay

logger = structlog.get_logger(__name__)


class SellerboardAuth:
    """Handles Sellerboard login and session management."""

    # Selectors for cookie consent dialog
    COOKIE_SELECTORS = {
        "accept_all": '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, button:has-text("Allow all"), #CybotCookiebotDialogBodyButtonAccept',
        "deny": 'button:has-text("Deny"), #CybotCookiebotDialogBodyButtonDecline',
        "dialog": '#CybotCookiebotDialog, .cookie-consent, .cookie-banner',
    }

    # Selectors for login page elements
    SELECTORS = {
        "email_input": '#username, input[name="login"], input[placeholder*="mail"]',
        "password_input": '#password, input[name="password"], input[type="password"]',
        "login_button": 'button[type="submit"], input[type="submit"], button:has-text("Log in"), button:has-text("Sign in")',
        "dashboard_indicator": '.main-sidebar, .sidebar, .dashboard-content, nav.navbar, .app-content',
        "error_message": '.error, .alert-danger, .login-error, [role="alert"], .invalid-feedback, .text-danger',
    }

    def __init__(self, page: Page, credentials: SellerboardCredentials):
        """
        Initialize authentication handler.

        Args:
            page: Playwright page instance
            credentials: Sellerboard login credentials
        """
        self._page = page
        self._credentials = credentials

    async def login(self) -> bool:
        """
        Perform login to Sellerboard.

        Returns:
            True if login successful

        Raises:
            AuthenticationError: If login fails
        """
        logger.info("Starting Sellerboard login")

        try:
            # Navigate to login page
            await self._page.goto(
                SELLERBOARD_LOGIN_URL,
                wait_until="networkidle",
                timeout=60000,
            )

            await random_delay(1, 2)

            # Handle cookie consent dialog if present
            await self._handle_cookie_consent()

            # Check if already logged in (redirected to dashboard)
            if await self._is_logged_in():
                logger.info("Already logged in to Sellerboard")
                return True

            # Fill email
            email_input = await self._find_element(self.SELECTORS["email_input"])
            if not email_input:
                raise AuthenticationError(
                    "Could not find email input field",
                    details={"selector": self.SELECTORS["email_input"]},
                )

            await email_input.fill(self._credentials.email)
            await random_delay(0.5, 1)

            # Fill password
            password_input = await self._find_element(self.SELECTORS["password_input"])
            if not password_input:
                raise AuthenticationError(
                    "Could not find password input field",
                    details={"selector": self.SELECTORS["password_input"]},
                )

            await password_input.fill(self._credentials.password)
            await random_delay(0.5, 1)

            # Click login button
            login_button = await self._find_element(self.SELECTORS["login_button"])
            if not login_button:
                raise AuthenticationError(
                    "Could not find login button",
                    details={"selector": self.SELECTORS["login_button"]},
                )

            # Click and don't wait for navigation (handle separately)
            await login_button.click(no_wait_after=True)

            # Wait for URL to change to dashboard
            try:
                await self._page.wait_for_url("**/dashboard/**", timeout=30000)
                logger.info("Navigated to dashboard")
            except Exception as e:
                logger.warning("URL wait failed, continuing anyway", error=str(e))

            # Wait for page to stabilize
            await self._page.wait_for_load_state("networkidle", timeout=60000)
            await random_delay(3, 5)

            # Verify login success
            if await self._is_logged_in():
                logger.info("Successfully logged in to Sellerboard")
                return True

            # Check for error message
            error_msg = await self._get_error_message()

            # Log current state for debugging
            current_url = self._page.url
            page_title = await self._page.title()
            logger.error(
                "Login verification failed",
                url=current_url,
                title=page_title,
                error_msg=error_msg,
            )

            raise AuthenticationError(
                f"Login failed: {error_msg or 'Unknown error'}",
                details={"email": self._credentials.email, "url": current_url},
            )

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error("Login error", error=str(e))
            raise AuthenticationError(
                f"Login failed with unexpected error: {str(e)}",
                details={"error_type": type(e).__name__},
            ) from e

    async def _handle_cookie_consent(self) -> None:
        """Handle cookie consent dialog if present."""
        try:
            # Check if cookie dialog is present
            dialog = await self._page.query_selector(self.COOKIE_SELECTORS["dialog"])
            if not dialog:
                logger.debug("No cookie consent dialog found")
                return

            logger.info("Cookie consent dialog detected, accepting...")

            # Try to click accept/allow all button
            accept_button = await self._page.query_selector(self.COOKIE_SELECTORS["accept_all"])
            if accept_button:
                await accept_button.click()
                await random_delay(0.5, 1)
                logger.info("Accepted cookie consent")
                return

            # Try deny button as fallback
            deny_button = await self._page.query_selector(self.COOKIE_SELECTORS["deny"])
            if deny_button:
                await deny_button.click()
                await random_delay(0.5, 1)
                logger.info("Denied cookie consent")
                return

            logger.warning("Could not find cookie consent buttons")

        except Exception as e:
            logger.debug("Error handling cookie consent", error=str(e))

    async def _is_logged_in(self) -> bool:
        """Check if currently logged in by looking for dashboard elements."""
        import asyncio

        # Retry a few times in case of navigation
        for attempt in range(3):
            try:
                # Wait for page to be stable
                await self._page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(1)  # Extra stabilization time

                current_url = self._page.url
                logger.debug("Checking login status", url=current_url, attempt=attempt + 1)

                # Simple check: if URL contains /dashboard, we're logged in
                if "/dashboard" in current_url:
                    logger.info("URL contains /dashboard - logged in")
                    return True

                # Check page title
                try:
                    page_title = await self._page.title()
                    if "Dashboard" in page_title and "Sign in" not in page_title:
                        logger.info("Dashboard in title - logged in")
                        return True
                except Exception:
                    pass  # Title check failed, continue with other checks

                # Check for dashboard indicator elements
                indicator = await self._page.query_selector(self.SELECTORS["dashboard_indicator"])
                if indicator:
                    logger.info("Found dashboard indicator - logged in")
                    return True

                logger.info("Not logged in - no conditions matched")
                return False

            except Exception as e:
                logger.warning("Login check attempt failed", attempt=attempt + 1, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2)  # Wait before retry
                continue

        return False

    async def _find_element(self, selector: str):
        """
        Find element using multiple selector strategies.

        Args:
            selector: CSS selector (can include multiple comma-separated selectors)

        Returns:
            Element handle or None if not found
        """
        try:
            # Try each selector in the comma-separated list
            for single_selector in selector.split(","):
                single_selector = single_selector.strip()
                element = await self._page.query_selector(single_selector)
                if element:
                    return element

            # Wait and try again
            await self._page.wait_for_selector(
                selector,
                timeout=ELEMENT_TIMEOUT_MS,
                state="visible",
            )
            return await self._page.query_selector(selector)

        except Exception as e:
            logger.debug("Element not found", selector=selector, error=str(e))
            return None

    async def _get_error_message(self) -> str | None:
        """Extract error message from login page if present."""
        try:
            error_element = await self._page.query_selector(self.SELECTORS["error_message"])
            if error_element:
                return await error_element.inner_text()
        except Exception:
            pass
        return None

    async def logout(self) -> None:
        """Log out from Sellerboard."""
        try:
            # Look for logout button/link
            logout_selectors = [
                'a:has-text("Logout")',
                'a:has-text("Log out")',
                'button:has-text("Logout")',
                '.logout-button',
                '[data-testid="logout"]',
            ]

            for selector in logout_selectors:
                element = await self._page.query_selector(selector)
                if element:
                    await element.click()
                    await self._page.wait_for_load_state("networkidle")
                    logger.info("Logged out from Sellerboard")
                    return

            logger.warning("Could not find logout button")

        except Exception as e:
            logger.warning("Error during logout", error=str(e))


async def save_session_cookies(context: BrowserContext, file_path: str) -> None:
    """
    Save session cookies to file for reuse.

    Args:
        context: Browser context
        file_path: Path to save cookies
    """
    import json

    cookies = await context.cookies()
    with open(file_path, "w") as f:
        json.dump(cookies, f)
    logger.info("Saved session cookies", path=file_path)


async def load_session_cookies(context: BrowserContext, file_path: str) -> bool:
    """
    Load session cookies from file.

    Args:
        context: Browser context
        file_path: Path to load cookies from

    Returns:
        True if cookies loaded successfully
    """
    import json
    import os

    if not os.path.exists(file_path):
        return False

    try:
        with open(file_path, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        logger.info("Loaded session cookies", path=file_path)
        return True
    except Exception as e:
        logger.warning("Failed to load cookies", error=str(e))
        return False
