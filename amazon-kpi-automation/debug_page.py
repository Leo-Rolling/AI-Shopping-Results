"""Debug script to see what text is on the Sellerboard dashboard."""

import asyncio
import os
import sys

sys.path.insert(0, "/Users/leonardodol/Documents/VisualSTudioCode/AI Shopping/amazon-kpi-automation/src")
os.environ["GCP_PROJECT_ID"] = "sellerboard-amz-kpi"

from playwright.async_api import async_playwright

async def debug_page():
    from amazon_kpi.secrets.secret_manager import get_sellerboard_credentials
    from amazon_kpi.config.constants import SELLERBOARD_LOGIN_URL
    from amazon_kpi.scraper.extractors import KPIExtractor

    creds = get_sellerboard_credentials()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        page.set_default_timeout(60000)  # 60 second timeout

        # Go to login
        print("Navigating to login page...")
        await page.goto(SELLERBOARD_LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # Handle cookie consent
        try:
            accept_btn = await page.query_selector('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll')
            if accept_btn:
                await accept_btn.click()
                await asyncio.sleep(1)
                print("Accepted cookies")
        except:
            pass

        # Login
        print("Logging in...")
        email_input = await page.query_selector('#username')
        if email_input:
            await email_input.fill(creds.email)

        password_input = await page.query_selector('#password')
        if password_input:
            await password_input.fill(creds.password)

        login_btn = await page.query_selector('button[type="submit"]')
        if login_btn:
            # Click and don't wait for navigation (handle separately)
            await login_btn.click(no_wait_after=True)

        # Wait for dashboard
        print("Waiting for dashboard...")
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(5)

        # Now run the actual extractor
        print("\n=== Running KPIExtractor ===")
        extractor = KPIExtractor(page)

        try:
            kpi_data = await extractor.extract_all_kpis()
            print("\n=== Extraction Results ===")
            print(f"Gross Sales: ${kpi_data.gross_sales}")
            print(f"Orders: {kpi_data.orders}")
            print(f"Units Sold: {kpi_data.units_sold}")
            print(f"Refunds: {kpi_data.refunds}")
            print(f"Ad Spend: ${kpi_data.ad_spend}")
            print(f"Net Profit: ${kpi_data.net_profit}")
            print(f"Margin: {kpi_data.margin}%")
            print(f"ACOS: {kpi_data.acos}%")
        except Exception as e:
            print(f"Extraction failed: {e}")
            import traceback
            traceback.print_exc()

        print("\n\nKeeping browser open for 30 seconds so you can inspect...")
        await asyncio.sleep(30)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_page())
