"""Pre-fetch SP-API data on a schedule to warm the cache.

Run via Cloud Scheduler → Cloud Run job, or locally as:
    python -m amazon_kpi.dashboard.prefetch

Fetches current + previous week data for all marketplaces, so the
Streamlit dashboard loads instantly without waiting for Data Kiosk queries.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import structlog

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from dotenv import load_dotenv
load_dotenv()

from amazon_kpi.dashboard.data_service import DashboardDataService

logger = structlog.get_logger(__name__)


def _get_current_week() -> tuple[date, date]:
    """Get Monday-Sunday of the most recent complete week."""
    today = date.today()
    days_since_monday = today.weekday()
    if days_since_monday == 0:
        monday = today - timedelta(days=8)
    else:
        last_sunday = today - timedelta(days=days_since_monday)
        monday = last_sunday - timedelta(days=6)
    return monday, monday + timedelta(days=6)


def prefetch() -> None:
    """Fetch current and previous week data to warm the cache."""
    logger.info("Starting pre-fetch...")
    service = DashboardDataService()

    week_start, week_end = _get_current_week()
    prev_start = week_start - timedelta(days=7)
    prev_end = week_end - timedelta(days=7)

    # Fetch current week
    logger.info("Fetching current week", start=str(week_start), end=str(week_end))
    current = service.fetch_weekly_data(week_start, week_end)
    logger.info("Current week done", marketplaces=len(current))

    # Fetch previous week
    logger.info("Fetching previous week", start=str(prev_start), end=str(prev_end))
    previous = service.fetch_weekly_data(prev_start, prev_end)
    logger.info("Previous week done", marketplaces=len(previous))

    logger.info("Pre-fetch complete!")


if __name__ == "__main__":
    prefetch()
