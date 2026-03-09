"""Main Streamlit dashboard application."""

from __future__ import annotations

import traceback

import streamlit as st

from ..config.constants import Marketplace
from .components.country_split import render_country_split
from .components.kpi_table import render_kpis_tab
from .components.sidebar import render_sidebar
from .data_service import DashboardDataService

EU5_MARKETPLACES = [
    Marketplace.UK,
    Marketplace.DE,
    Marketplace.IT,
    Marketplace.FR,
    Marketplace.ES,
]

NA_MARKETPLACES = [
    Marketplace.US,
    Marketplace.CA,
]


@st.cache_resource
def get_data_service() -> DashboardDataService:
    """Create a singleton DashboardDataService."""
    return DashboardDataService()


def main() -> None:
    """Entry point for the Streamlit dashboard."""
    try:
        _run_dashboard()
    except Exception as e:
        st.error(f"Application error: {e}")
        st.code(traceback.format_exc())


def _run_dashboard() -> None:
    st.set_page_config(
        page_title="AMZ Meeting KPIs",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS — force light text colors for tables regardless of Streamlit theme
    st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        h4 { margin-top: 0.5rem; color: #e0e0e0 !important; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 8px; }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            padding: 8px 24px;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)

    # Title
    st.title("📊 AMZ Meeting KPIs")

    # Sidebar
    sidebar = render_sidebar()

    # Clear ALL caches on refresh (memory + filesystem + session state)
    if sidebar["refresh"]:
        st.cache_resource.clear()
        service = get_data_service()
        service.clear_cache()
        st.session_state.fetch_data = False
        st.rerun()

    # Use session state to track if data should be fetched
    if "fetch_data" not in st.session_state:
        st.session_state.fetch_data = False

    # Check if cache exists for selected week (pre-fetched by cron)
    service = get_data_service()
    has_cache = service.has_cached_data(
        sidebar["week_start"], sidebar["week_end"]
    ) and service.has_cached_data(
        sidebar["prev_week_start"], sidebar["prev_week_end"]
    )

    # Auto-load if cache exists, otherwise show fetch button
    if has_cache and not st.session_state.fetch_data:
        st.session_state.fetch_data = True

    # Fetch button
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("🔄 Fetch KPI Data", use_container_width=True, type="primary"):
            st.session_state.fetch_data = True

    if not st.session_state.fetch_data:
        st.info(
            f"Select a week in the sidebar and click **Fetch KPI Data** to load data from Amazon SP-API.\n\n"
            f"**Selected week:** {sidebar['week_start'].strftime('%b %d')} – {sidebar['week_end'].strftime('%b %d, %Y')}"
        )
        return

    # Fetch data
    try:
        with st.status("Fetching data from Amazon SP-API (Sales + Economics)...", expanded=True) as status:
            # Fetch current week
            st.write(f"📥 Current week: {sidebar['week_start']} → {sidebar['week_end']}")
            st.write("  Querying Sales & Traffic + Economics for 7 marketplaces...")
            current_data = _fetch_cached(
                service, sidebar["week_start"], sidebar["week_end"],
            )
            # Show economics data status
            econ_ok = sum(1 for mp_kpis in current_data.values() if mp_kpis.total and float(mp_kpis.total.ad_spend) > 0)
            st.write(f"✅ Current week: {len(current_data)} marketplaces ({econ_ok} with Economics data)")

            # Fetch previous week
            st.write(f"📥 Previous week: {sidebar['prev_week_start']} → {sidebar['prev_week_end']}")
            previous_data = _fetch_cached(
                service, sidebar["prev_week_start"], sidebar["prev_week_end"],
            )
            econ_ok_prev = sum(1 for mp_kpis in previous_data.values() if mp_kpis.total and float(mp_kpis.total.ad_spend) > 0)
            st.write(f"✅ Previous week: {len(previous_data)} marketplaces ({econ_ok_prev} with Economics data)")

            status.update(label="Data loaded!", state="complete")

    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        st.code(traceback.format_exc())
        st.info("Make sure your SP-API credentials are configured in .env")
        return

    # Build reports
    current_report, previous_report = service.build_weekly_report(
        current_data=current_data,
        previous_data=previous_data,
        week_start=sidebar["week_start"],
        week_end=sidebar["week_end"],
        eur_usd_rate=sidebar["eur_usd_rate"],
    )

    # Check if we have any data
    has_data = any(
        mp_kpis.total is not None
        for mp_kpis in current_data.values()
    )

    if not has_data:
        st.warning(
            "No data returned from SP-API for the selected week. "
            "The Data Kiosk query may still be processing — try again in a few minutes."
        )
        return

    # Tabs
    tab_kpis, tab_eu5, tab_na = st.tabs(["📊 KPIs", "🇪🇺 EU5 Country Split", "🇺🇸 NA Country Split"])

    with tab_kpis:
        render_kpis_tab(
            current_report=current_report,
            previous_report=previous_report,
            selected_categories=sidebar["categories"],
            eur_usd_rate=sidebar["eur_usd_rate"],
            has_sellerboard=bool(sidebar["uploaded_csvs"]),
        )

    with tab_eu5:
        render_country_split(
            current_report=current_report,
            previous_report=previous_report,
            marketplaces=EU5_MARKETPLACES,
            selected_categories=sidebar["categories"],
            has_sellerboard=bool(sidebar["uploaded_csvs"]),
        )

    with tab_na:
        render_country_split(
            current_report=current_report,
            previous_report=previous_report,
            marketplaces=NA_MARKETPLACES,
            selected_categories=sidebar["categories"],
            has_sellerboard=bool(sidebar["uploaded_csvs"]),
        )


@st.cache_resource(ttl=3600, show_spinner=False)
def _fetch_cached(_service, week_start, week_end):
    """Cache wrapper for data fetching (TTL=1 hour)."""
    return _service.fetch_weekly_data(week_start, week_end)
