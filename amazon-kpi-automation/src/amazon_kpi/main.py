"""Cloud Run entry point with Flask application."""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import structlog
from flask import Flask, jsonify, request

from .config.constants import MARKETPLACES, MARKETPLACE_SP_API_IDS, Marketplace
from .scraper.sellerboard_client import run_scraper
from .processing.aggregator import aggregate_regions, aggregate_total
from .output.sheets_client import create_kpi_report

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create Flask app
app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Cloud Run."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    })


@app.route("/run", methods=["POST"])
def run_kpi_extraction():
    """
    Main endpoint to trigger KPI extraction.

    Triggered by Cloud Scheduler or manual invocation.
    """
    logger.info("KPI extraction triggered")

    try:
        # Run the async scraper in the event loop
        report = asyncio.run(_run_extraction())

        return jsonify({
            "status": "success",
            "message": "KPI extraction completed",
            "report_url": report.get("url"),
            "week_start": report.get("week_start"),
            "week_end": report.get("week_end"),
        })

    except Exception as e:
        logger.error("KPI extraction failed", error=str(e), exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 500


async def _run_extraction() -> dict:
    """
    Run the full extraction pipeline.

    Returns:
        Dictionary with report URL and metadata
    """
    logger.info("Starting extraction pipeline")

    # Step 1: Scrape data from Sellerboard
    logger.info("Step 1: Scraping Sellerboard")
    report = await run_scraper(headless=True)

    # Step 2: Calculate regional aggregations
    logger.info("Step 2: Calculating regional aggregations")
    report = aggregate_regions(report)

    # Step 3: Calculate grand total
    logger.info("Step 3: Calculating grand total")
    report = aggregate_total(report)

    # Step 4: Generate Google Sheets report
    logger.info("Step 4: Generating Google Sheets report")
    report_url = create_kpi_report(report)

    logger.info("Extraction pipeline complete", report_url=report_url)

    return {
        "url": report_url,
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
    }


@app.route("/test", methods=["GET"])
def test_connection():
    """
    Test endpoint to verify connections.

    Tests:
    - Secret Manager access
    - Google Sheets API access
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "tests": {},
    }

    # Test Secret Manager
    try:
        from .secrets.secret_manager import get_client
        client = get_client()
        # Try to get folder ID (non-sensitive)
        folder_id = client.get_drive_folder_id()
        results["tests"]["secret_manager"] = {
            "status": "pass",
            "folder_id_length": len(folder_id),
        }
    except Exception as e:
        results["tests"]["secret_manager"] = {
            "status": "fail",
            "error": str(e),
        }

    # Test Google Sheets connection
    try:
        from .output.sheets_client import GoogleSheetsClient
        client = GoogleSheetsClient()
        client._initialize()
        results["tests"]["google_sheets"] = {
            "status": "pass",
        }
    except Exception as e:
        results["tests"]["google_sheets"] = {
            "status": "fail",
            "error": str(e),
        }

    # Test SP-API credentials
    try:
        from .secrets.secret_manager import get_sp_api_credentials
        creds_eu = get_sp_api_credentials("eu-uk")
        creds_na = get_sp_api_credentials("na")
        results["tests"]["sp_api_credentials"] = {
            "status": "pass",
            "eu_uk": "configured",
            "na": "configured",
        }
    except Exception as e:
        results["tests"]["sp_api_credentials"] = {
            "status": "fail",
            "error": str(e),
        }

    # Overall status
    all_passed = all(
        t.get("status") == "pass"
        for t in results["tests"].values()
    )
    results["overall_status"] = "pass" if all_passed else "fail"

    status_code = 200 if all_passed else 500
    return jsonify(results), status_code


@app.route("/run-sp-api", methods=["POST"])
def run_sp_api_extraction():
    """Trigger SP-API KPI extraction.

    Request body (JSON, all optional):
        report_types: list of report types to fetch
            ("sales_traffic", "search_query", "market_basket", "repeat_purchase")
        marketplaces: list of marketplace codes (e.g., ["US", "DE"]). Default: all.
        start_date: Start date YYYY-MM-DD. Default: last week Monday.
        end_date: End date YYYY-MM-DD. Default: last week Sunday.
        output: Output format ("sheets", "csv", "excel"). Default: "csv".
    """
    logger.info("SP-API extraction triggered")

    try:
        body = request.get_json(silent=True) or {}

        result = _run_sp_api_pipeline(
            report_types=body.get("report_types", ["sales_traffic"]),
            marketplaces=body.get("marketplaces"),
            start_date=body.get("start_date"),
            end_date=body.get("end_date"),
            output_format=body.get("output", "csv"),
        )

        return jsonify({
            "status": "success",
            "message": "SP-API extraction completed",
            **result,
        })

    except Exception as e:
        logger.error("SP-API extraction failed", error=str(e), exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


def _get_default_date_range() -> tuple[str, str]:
    """Get last complete week's date range (Monday to Sunday)."""
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()


def _run_sp_api_pipeline(
    report_types: list[str],
    marketplaces: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    output_format: str = "csv",
) -> dict:
    """Run the SP-API extraction pipeline."""
    from .sp_api.client import SPAPIClientFactory
    from .sp_api.data_kiosk import DataKioskService
    from .sp_api.queries import (
        SALES_TRAFFIC_BY_ASIN,
        SALES_TRAFFIC_BY_DATE,
        SEARCH_QUERY_PERFORMANCE,
        BRAND_ANALYTICS_MARKET_BASKET,
        BRAND_ANALYTICS_REPEAT_PURCHASE,
        build_query,
    )
    from .sp_api.parsers import (
        parse_sales_traffic,
        parse_sales_traffic_by_date,
        parse_search_query_performance,
        parse_market_basket,
        parse_repeat_purchase,
    )
    from .output.file_exporter import FileExporter

    # Resolve dates
    if not start_date or not end_date:
        start_date, end_date = _get_default_date_range()

    # Resolve marketplaces
    target_marketplaces = (
        [Marketplace(m) for m in marketplaces]
        if marketplaces
        else list(MARKETPLACES)
    )

    logger.info(
        "SP-API pipeline starting",
        report_types=report_types,
        marketplaces=[m.value for m in target_marketplaces],
        start_date=start_date,
        end_date=end_date,
        output_format=output_format,
    )

    factory = SPAPIClientFactory()
    data_kiosk = DataKioskService(factory)
    exporter = FileExporter()

    result: dict = {
        "start_date": start_date,
        "end_date": end_date,
        "files": [],
    }

    import pandas as pd

    # ---- Sales & Traffic by ASIN ----
    if "sales_traffic" in report_types:
        logger.info("Fetching Sales & Traffic by ASIN")
        all_marketplace_kpis = {}
        all_daily_dfs = []

        for mp in target_marketplaces:
            marketplace_id = MARKETPLACE_SP_API_IDS[mp]

            # By ASIN query
            query = build_query(
                SALES_TRAFFIC_BY_ASIN,
                start_date=start_date,
                end_date=end_date,
                marketplace_id=marketplace_id,
            )
            records = data_kiosk.execute_query(marketplace=mp, query=query)
            if records:
                all_marketplace_kpis[mp] = parse_sales_traffic(records, mp)

            # By Date query
            date_query = build_query(
                SALES_TRAFFIC_BY_DATE,
                start_date=start_date,
                end_date=end_date,
                marketplace_id=marketplace_id,
            )
            date_records = data_kiosk.execute_query(marketplace=mp, query=date_query)
            if date_records:
                df = parse_sales_traffic_by_date(date_records, mp)
                all_daily_dfs.append(df)

        # Export daily traffic data
        if all_daily_dfs:
            daily_df = pd.concat(all_daily_dfs, ignore_index=True)
            path = exporter.export_dataframe(
                daily_df,
                name=f"sales_traffic_{start_date}_{end_date}",
                output_format=output_format,
            )
            result["files"].append(str(path))

    # ---- Search Query Performance ----
    if "search_query" in report_types:
        logger.info("Fetching Search Query Performance")
        all_sqp_dfs = []

        for mp in target_marketplaces:
            marketplace_id = MARKETPLACE_SP_API_IDS[mp]
            query = build_query(
                SEARCH_QUERY_PERFORMANCE,
                start_date=start_date,
                end_date=end_date,
                marketplace_id=marketplace_id,
            )
            records = data_kiosk.execute_query(marketplace=mp, query=query)
            if records:
                df = parse_search_query_performance(records, mp)
                all_sqp_dfs.append(df)

        if all_sqp_dfs:
            sqp_df = pd.concat(all_sqp_dfs, ignore_index=True)
            path = exporter.export_dataframe(
                sqp_df,
                name=f"search_query_performance_{start_date}_{end_date}",
                output_format=output_format,
            )
            result["files"].append(str(path))

    # ---- Market Basket ----
    if "market_basket" in report_types:
        logger.info("Fetching Market Basket")
        all_mb_dfs = []

        for mp in target_marketplaces:
            marketplace_id = MARKETPLACE_SP_API_IDS[mp]
            query = build_query(
                BRAND_ANALYTICS_MARKET_BASKET,
                start_date=start_date,
                end_date=end_date,
                marketplace_id=marketplace_id,
            )
            records = data_kiosk.execute_query(marketplace=mp, query=query)
            if records:
                df = parse_market_basket(records, mp)
                all_mb_dfs.append(df)

        if all_mb_dfs:
            mb_df = pd.concat(all_mb_dfs, ignore_index=True)
            path = exporter.export_dataframe(
                mb_df,
                name=f"market_basket_{start_date}_{end_date}",
                output_format=output_format,
            )
            result["files"].append(str(path))

    # ---- Repeat Purchase ----
    if "repeat_purchase" in report_types:
        logger.info("Fetching Repeat Purchase")
        all_rp_dfs = []

        for mp in target_marketplaces:
            marketplace_id = MARKETPLACE_SP_API_IDS[mp]
            query = build_query(
                BRAND_ANALYTICS_REPEAT_PURCHASE,
                start_date=start_date,
                end_date=end_date,
                marketplace_id=marketplace_id,
            )
            records = data_kiosk.execute_query(marketplace=mp, query=query)
            if records:
                df = parse_repeat_purchase(records, mp)
                all_rp_dfs.append(df)

        if all_rp_dfs:
            rp_df = pd.concat(all_rp_dfs, ignore_index=True)
            path = exporter.export_dataframe(
                rp_df,
                name=f"repeat_purchase_{start_date}_{end_date}",
                output_format=output_format,
            )
            result["files"].append(str(path))

    logger.info("SP-API pipeline complete", files=result["files"])
    return result


def cli():
    """CLI entry point for local testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Amazon KPI Automation")
    subparsers = parser.add_subparsers(dest="command")

    # --- Sellerboard scraper (legacy) ---
    scrape_parser = subparsers.add_parser("scrape", help="Run Sellerboard scraper")
    scrape_parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with visible UI",
    )

    # --- SP-API ---
    sp_parser = subparsers.add_parser("sp-api", help="Run SP-API extraction")
    sp_parser.add_argument(
        "--report-type",
        nargs="+",
        choices=["sales_traffic", "search_query", "market_basket", "repeat_purchase", "all"],
        default=["all"],
        help="Report types to fetch (default: all)",
    )
    sp_parser.add_argument(
        "--marketplace",
        nargs="+",
        choices=["US", "CA", "UK", "DE", "IT", "FR", "ES"],
        default=None,
        help="Marketplaces to query (default: all)",
    )
    sp_parser.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START", "END"),
        default=None,
        help="Date range YYYY-MM-DD YYYY-MM-DD (default: last week)",
    )
    sp_parser.add_argument(
        "--output",
        choices=["csv", "excel"],
        default="csv",
        help="Output format (default: csv)",
    )

    # --- Other commands ---
    subparsers.add_parser("test", help="Test connections")
    server_parser = subparsers.add_parser("server", help="Start Flask server")
    server_parser.add_argument(
        "--port", type=int, default=8080, help="Server port (default: 8080)"
    )

    # Backward compatibility: support old --run / --test / --server flags
    parser.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--test-legacy", action="store_true", dest="test_legacy", help=argparse.SUPPRESS)
    parser.add_argument("--server-legacy", action="store_true", dest="server_legacy", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8080, help=argparse.SUPPRESS)
    parser.add_argument("--no-headless", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.command == "scrape" or args.run:
        headless = not args.no_headless
        print(f"Running Sellerboard extraction pipeline (headless={headless})...")
        result = asyncio.run(_run_extraction_cli(headless))
        print(f"Report URL: {result['url']}")
        print(f"Week: {result['week_start']} to {result['week_end']}")

    elif args.command == "sp-api":
        report_types = args.report_type
        if "all" in report_types:
            report_types = ["sales_traffic", "search_query", "market_basket", "repeat_purchase"]

        start_date = args.date_range[0] if args.date_range else None
        end_date = args.date_range[1] if args.date_range else None

        print(f"Running SP-API extraction...")
        print(f"  Reports: {', '.join(report_types)}")
        print(f"  Marketplaces: {', '.join(args.marketplace) if args.marketplace else 'all'}")
        if start_date:
            print(f"  Date range: {start_date} to {end_date}")
        else:
            print(f"  Date range: last complete week")
        print(f"  Output: {args.output}")
        print()

        result = _run_sp_api_pipeline(
            report_types=report_types,
            marketplaces=args.marketplace,
            start_date=start_date,
            end_date=end_date,
            output_format=args.output,
        )

        if result.get("files"):
            print("Generated files:")
            for f in result["files"]:
                print(f"  {f}")
        else:
            print("No data returned for the specified parameters.")

    elif args.command == "test" or args.test_legacy:
        with app.test_client() as client:
            response = client.get("/test")
            import json
            print(json.dumps(response.get_json(), indent=2))

    elif args.command == "server" or args.server_legacy:
        port = args.port
        print(f"Starting server on port {port}...")
        app.run(host="0.0.0.0", port=port, debug=True)

    else:
        parser.print_help()


async def _run_extraction_cli(headless: bool = True) -> dict:
    """CLI version of extraction with configurable headless mode."""
    logger.info("Starting CLI extraction", headless=headless)

    report = await run_scraper(headless=headless)
    report = aggregate_regions(report)
    report = aggregate_total(report)
    report_url = create_kpi_report(report)

    return {
        "url": report_url,
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
    }


# Gunicorn entry point
def create_app():
    """Create and configure the Flask application."""
    return app


if __name__ == "__main__":
    # Check if running as CLI or server
    if len(sys.argv) > 1:
        cli()
    else:
        # Default: start server
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)
