"""Test the scraper without Google Sheets output."""

import asyncio
import os
import sys

sys.path.insert(0, "/Users/leonardodol/Documents/VisualSTudioCode/AI Shopping/amazon-kpi-automation/src")
os.environ["GCP_PROJECT_ID"] = "sellerboard-amz-kpi"

async def test_scraper():
    from amazon_kpi.scraper.sellerboard_client import run_scraper

    print("Running scraper (visible browser)...")
    report = await run_scraper(headless=False)

    print("\n=== Scraper Results ===")
    print(f"Week: {report.week_start} to {report.week_end}")
    print(f"\nGrand Total KPIs:")
    print(f"  Gross Sales: ${report.grand_total.gross_sales}")
    print(f"  Orders: {report.grand_total.orders}")
    print(f"  Units Sold: {report.grand_total.units_sold}")
    print(f"  Refunds: {report.grand_total.refunds}")
    print(f"  Ad Spend: ${report.grand_total.ad_spend}")
    print(f"  Net Profit: ${report.grand_total.net_profit}")
    print(f"  Margin: {report.grand_total.margin:.2f}%")
    print(f"  ACOS: {report.grand_total.acos:.2f}%")

    print("\nScraper test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_scraper())
