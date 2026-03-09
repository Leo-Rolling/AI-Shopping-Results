"""Sidebar component — week selector, category filters, EUR/USD rate, CSV upload."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import streamlit as st

from ...config.constants import EUR_TO_USD_RATE
from ...config.sku_categories import CATEGORIES


def _get_last_complete_monday() -> date:
    """Get the Monday of the most recent complete week (Mon-Sun)."""
    today = date.today()
    # If today is Monday, last complete week started 8 days ago
    # Otherwise, go back to the Monday before the most recent Sunday
    days_since_monday = today.weekday()  # 0=Mon, 6=Sun
    if days_since_monday == 0:
        # Today is Monday — last complete week started 8 days ago
        return today - timedelta(days=8)
    else:
        # Last complete week's Monday
        last_sunday = today - timedelta(days=days_since_monday)
        return last_sunday - timedelta(days=6)


def render_sidebar() -> dict[str, Any]:
    """Render sidebar controls and return selected values.

    Returns:
        Dict with keys: week_start, week_end, prev_week_start, prev_week_end,
        categories, eur_usd_rate, uploaded_csv, refresh.
    """
    st.sidebar.markdown(
        '<h2 style="color: #1a1a2e; margin-bottom: 0;">AMZ Meeting KPIs</h2>'
        '<p style="color: #666; font-size: 12px; margin-top: 4px;">Weekly Performance Dashboard</p>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")

    # Week selector
    last_monday = _get_last_complete_monday()
    week_options = [last_monday - timedelta(weeks=i) for i in range(12)]

    selected_monday = st.sidebar.selectbox(
        "Select Week",
        options=week_options,
        format_func=lambda d: f"{d.strftime('%b %d')} – {(d + timedelta(days=6)).strftime('%b %d, %Y')}",
        index=0,
    )

    week_start = selected_monday
    week_end = selected_monday + timedelta(days=6)
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_end - timedelta(days=7)

    st.sidebar.markdown("---")

    # Category filter
    category_names = [cat.display_name for cat in CATEGORIES]
    selected_categories = st.sidebar.multiselect(
        "Product Categories",
        options=category_names,
        default=[],  # Empty = show all
        help="Leave empty to show all categories",
    )

    st.sidebar.markdown("---")

    # EUR/USD rate — persist in session state so it survives reruns
    if "eur_usd_rate" not in st.session_state:
        st.session_state.eur_usd_rate = EUR_TO_USD_RATE

    eur_usd_rate = st.sidebar.number_input(
        "EUR/USD Rate",
        value=st.session_state.eur_usd_rate,
        min_value=0.50,
        max_value=2.00,
        step=0.01,
        format="%.2f",
        key="eur_usd_input",
    )
    st.session_state.eur_usd_rate = eur_usd_rate

    st.sidebar.markdown("---")

    # Sellerboard CSV upload (multiple files)
    st.sidebar.markdown("**Sellerboard Data** *(optional)*")
    uploaded_csvs = st.sidebar.file_uploader(
        "Upload CSVs to fill PPC/Profit metrics",
        type=["csv"],
        accept_multiple_files=True,
        help="Upload one or more Sellerboard exports to populate Net Profit, PPC, and other metrics not available from SP-API.",
    )

    st.sidebar.markdown("---")

    # Refresh button
    refresh = st.sidebar.button("Refresh Data", use_container_width=True)

    # Info
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<p style="color: #999; font-size: 11px;">'
        "Data source: Amazon SP-API<br>"
        "Sales & Traffic + Economics datasets<br>"
        "Data refreshed hourly via cron"
        "</p>",
        unsafe_allow_html=True,
    )

    return {
        "week_start": week_start,
        "week_end": week_end,
        "prev_week_start": prev_week_start,
        "prev_week_end": prev_week_end,
        "categories": selected_categories,
        "eur_usd_rate": eur_usd_rate,
        "uploaded_csvs": uploaded_csvs,
        "refresh": refresh,
    }
