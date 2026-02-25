"""Test script to export KPI report to local Excel file."""
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.amazon_kpi.scraper.sellerboard_client import run_scraper
from src.amazon_kpi.processing.aggregator import aggregate_regions, aggregate_total
from src.amazon_kpi.output.templates import KPISummaryTemplate, ByCountryTemplate
import pandas as pd


async def main():
    print("Step 1: Scraping Sellerboard...")
    report = await run_scraper(headless=False)

    print("Step 2: Aggregating regions...")
    report = aggregate_regions(report)

    print("Step 3: Aggregating total...")
    report = aggregate_total(report)

    print("Step 4: Building templates...")
    kpi_template = KPISummaryTemplate()
    kpi_data = kpi_template.build(report)

    country_template = ByCountryTemplate()
    country_data = country_template.build(report)

    print("Step 5: Saving to Excel...")
    output_path = os.path.expanduser("~/Desktop/AMZ_KPI_Report.xlsx")

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # KPIs sheet
        df_kpi = pd.DataFrame(kpi_data)
        df_kpi.to_excel(writer, sheet_name='KPIs', index=False, header=False)

        # By Country sheet
        df_country = pd.DataFrame(country_data)
        df_country.to_excel(writer, sheet_name='By Country', index=False, header=False)

    print(f"\nReport saved to: {output_path}")
    print(f"Week: {report.week_start} to {report.week_end}")
    print(f"KPIs rows: {len(kpi_data)}")
    print(f"By Country rows: {len(country_data)}")


if __name__ == "__main__":
    asyncio.run(main())
