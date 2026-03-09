"""KPI summary table component — replicates Sheet 1 of the Excel report.

Layout per section (Overall, then each category):
  KPI | EU+UK (Avg/Day, Prev Week, Last Week, Delta) | US+CA (same) | Total (same)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from ...config.constants import EUR_TO_USD_RATE, Region
from ...processing.models import KPIData, WeeklyReport

# KPI row definitions matching Excel exactly
# (display_name, attr_name, format_type, is_formula)
KPI_ROWS = [
    ("Revenue", "gross_sales", "currency", False),
    ("Net Profit", "net_profit", "currency", False),
    ("Net Margin", None, "percent", True),
    ("Refunds", "refunds", "integer", False),
    ("PPC", "ad_spend", "currency", False),
    ("PPC Sales", "ppc_sales", "currency", False),
    ("PPC Sales/Revenue", None, "percent", True),
    ("ROAS", None, "ratio", True),
    ("TACOS", None, "percent", True),
    ("Orders", "orders", "integer", False),
    ("AOV", None, "currency", True),
]

# All KPIs are now available from SP-API (Sales & Traffic + Economics datasets)
SP_API_KPIS = {
    "Revenue", "Orders", "Refunds", "AOV",
    "Net Profit", "Net Margin", "PPC", "PPC Sales",
    "PPC Sales/Revenue", "ROAS", "TACOS",
}


def _get_value(data: KPIData | None, attr_name: str | None) -> float | None:
    """Extract a KPI value from KPIData."""
    if data is None or attr_name is None:
        return None
    val = getattr(data, attr_name, None)
    if val is None:
        return None
    return float(val)


def _compute_formula(kpi_name: str, data: KPIData | None) -> float | None:
    """Compute formula-based KPIs from raw data."""
    if data is None:
        return None

    revenue = float(data.gross_sales)
    net_profit = float(data.net_profit)
    ad_spend = float(data.ad_spend)
    ppc_sales = float(data.ppc_sales)
    orders = data.orders

    if kpi_name == "Net Margin":
        if not revenue or not net_profit:
            return None
        return net_profit / revenue
    elif kpi_name == "PPC Sales/Revenue":
        if not revenue or not ppc_sales:
            return None
        return ppc_sales / revenue
    elif kpi_name == "ROAS":
        if not ad_spend or not ppc_sales:
            return None
        return ppc_sales / ad_spend
    elif kpi_name == "TACOS":
        if not revenue or not ad_spend:
            return None
        return ad_spend / revenue
    elif kpi_name == "AOV":
        return revenue / orders if orders else None
    return None


def _get_kpi_value(kpi_name: str, attr_name: str | None, is_formula: bool, data: KPIData | None) -> float | None:
    """Get the value for a KPI row, either direct or computed."""
    if is_formula:
        return _compute_formula(kpi_name, data)
    return _get_value(data, attr_name)


def _is_available(kpi_name: str, has_sellerboard: bool) -> bool:
    """Check if a KPI can be displayed with current data sources."""
    return True  # All KPIs available via SP-API Economics + Sales datasets


def _format_val(value: float | None, fmt: str) -> str:
    """Format a value for display."""
    if value is None:
        return "—"
    if fmt == "currency":
        return f"${value:,.0f}" if abs(value) >= 1 else f"${value:,.2f}"
    elif fmt == "percent":
        return f"{value * 100:.1f}%" if abs(value) < 1 else f"{value:.1f}%"
    elif fmt == "ratio":
        return f"{value:.2f}"
    elif fmt == "integer":
        return f"{int(value):,}"
    return str(round(value, 2))


def _delta_pct(current: float | None, previous: float | None) -> float | None:
    """Calculate percentage change."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


def _delta_color(val: float | None, kpi_name: str) -> str:
    """Return CSS color for a delta value. Red for negative (except costs where red=positive)."""
    if val is None:
        return ""
    # For cost-type KPIs, lower is better
    inverted = kpi_name in {"PPC", "TACOS", "Refunds", "PPC Sales/Revenue"}
    if inverted:
        return "color: #28a745" if val < 0 else "color: #dc3545" if val > 0 else ""
    return "color: #28a745" if val > 0 else "color: #dc3545" if val < 0 else ""


def render_kpi_section(
    section_name: str,
    eu_current: KPIData | None,
    eu_previous: KPIData | None,
    us_current: KPIData | None,
    us_previous: KPIData | None,
    eur_usd_rate: float,
    has_sellerboard: bool = False,
    prev_week_label: str = "",
    last_week_label: str = "",
) -> None:
    """Render a KPI section (Overall or category) as an HTML table."""

    # Compute Total (EU converted to USD + NA)
    rate = Decimal(str(eur_usd_rate))
    total_current = None
    total_previous = None

    if eu_current and us_current:
        total_current = eu_current.convert_currency(rate) + us_current
    elif us_current:
        total_current = us_current
    elif eu_current:
        total_current = eu_current.convert_currency(rate)

    if eu_previous and us_previous:
        total_previous = eu_previous.convert_currency(rate) + us_previous
    elif us_previous:
        total_previous = us_previous
    elif eu_previous:
        total_previous = eu_previous.convert_currency(rate)

    # Build HTML table (dark theme — works in Streamlit dark mode)
    html = f"""
    <div style="margin-bottom: 24px;">
    <h4 style="margin-bottom: 8px; color: #e0e0e0;">{section_name}</h4>
    <table style="width:100%; border-collapse: collapse; font-size: 13px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; color: #e0e0e0;">
    <thead>
        <tr style="background: #1a1a2e; color: white;">
            <th style="padding: 8px; text-align: left; width: 140px;" rowspan="2">KPI</th>
            <th style="padding: 8px; text-align: center; border-left: 2px solid #444;" colspan="4">EU+UK (EUR)</th>
            <th style="padding: 8px; text-align: center; border-left: 2px solid #444;" colspan="4">US+CA (USD)</th>
            <th style="padding: 8px; text-align: center; border-left: 2px solid #444;" colspan="4">Total (USD)</th>
        </tr>
        <tr style="background: #2d2d44; color: #aaa; font-size: 11px;">
            <th style="padding: 4px; border-left: 2px solid #444;">Avg/Day</th>
            <th style="padding: 4px;">{prev_week_label or 'Prev Week'}</th>
            <th style="padding: 4px;">{last_week_label or 'Last Week'}</th>
            <th style="padding: 4px;">Delta</th>
            <th style="padding: 4px; border-left: 2px solid #444;">Avg/Day</th>
            <th style="padding: 4px;">{prev_week_label or 'Prev Week'}</th>
            <th style="padding: 4px;">{last_week_label or 'Last Week'}</th>
            <th style="padding: 4px;">Delta</th>
            <th style="padding: 4px; border-left: 2px solid #444;">Avg/Day</th>
            <th style="padding: 4px;">{prev_week_label or 'Prev Week'}</th>
            <th style="padding: 4px;">{last_week_label or 'Last Week'}</th>
            <th style="padding: 4px;">Delta</th>
        </tr>
    </thead>
    <tbody>
    """

    for i, (kpi_name, attr_name, fmt, is_formula) in enumerate(KPI_ROWS):
        available = _is_available(kpi_name, has_sellerboard)
        row_bg = "#1e1e2e" if i % 2 == 0 else "#262638"

        if not available:
            row_bg = "#333"
            html += f'<tr style="background: {row_bg}; color: #666;">'
            html += f'<td style="padding: 6px 8px; font-weight: 500;">{kpi_name}</td>'
            html += '<td style="padding: 6px; text-align: right; border-left: 2px solid #444;" colspan="4">—</td>'
            html += '<td style="padding: 6px; text-align: right; border-left: 2px solid #444;" colspan="4">—</td>'
            html += '<td style="padding: 6px; text-align: right; border-left: 2px solid #444;" colspan="4">—</td>'
            html += '</tr>'
            continue

        # Get values
        eu_curr_val = _get_kpi_value(kpi_name, attr_name, is_formula, eu_current)
        eu_prev_val = _get_kpi_value(kpi_name, attr_name, is_formula, eu_previous)
        us_curr_val = _get_kpi_value(kpi_name, attr_name, is_formula, us_current)
        us_prev_val = _get_kpi_value(kpi_name, attr_name, is_formula, us_previous)
        tot_curr_val = _get_kpi_value(kpi_name, attr_name, is_formula, total_current)
        tot_prev_val = _get_kpi_value(kpi_name, attr_name, is_formula, total_previous)

        # Compute deltas
        eu_delta = _delta_pct(eu_curr_val, eu_prev_val)
        us_delta = _delta_pct(us_curr_val, us_prev_val)
        tot_delta = _delta_pct(tot_curr_val, tot_prev_val)

        # Avg per day (last week / 7) — skip for ratio/percent KPIs
        is_ratio_kpi = is_formula and kpi_name not in {"AOV"}
        if is_ratio_kpi:
            eu_avg = eu_curr_val
            us_avg = us_curr_val
            tot_avg = tot_curr_val
        else:
            eu_avg = eu_curr_val / 7 if eu_curr_val is not None else None
            us_avg = us_curr_val / 7 if us_curr_val is not None else None
            tot_avg = tot_curr_val / 7 if tot_curr_val is not None else None

        html += f'<tr style="background: {row_bg}; color: #e0e0e0;">'
        html += f'<td style="padding: 6px 8px; font-weight: 500; color: #fff;">{kpi_name}</td>'

        # EU columns
        html += f'<td style="padding: 6px; text-align: right; border-left: 2px solid #444; color: #aaa;">{_format_val(eu_avg, fmt)}</td>'
        html += f'<td style="padding: 6px; text-align: right; color: #ccc;">{_format_val(eu_prev_val, fmt)}</td>'
        html += f'<td style="padding: 6px; text-align: right; font-weight: 600; color: #fff;">{_format_val(eu_curr_val, fmt)}</td>'
        eu_delta_str = f"{eu_delta*100:+.1f}%" if eu_delta is not None else "—"
        eu_color = _delta_color(eu_delta, kpi_name)
        html += f'<td style="padding: 6px; text-align: right; {eu_color}">{eu_delta_str}</td>'

        # US columns
        html += f'<td style="padding: 6px; text-align: right; border-left: 2px solid #444; color: #aaa;">{_format_val(us_avg, fmt)}</td>'
        html += f'<td style="padding: 6px; text-align: right; color: #ccc;">{_format_val(us_prev_val, fmt)}</td>'
        html += f'<td style="padding: 6px; text-align: right; font-weight: 600; color: #fff;">{_format_val(us_curr_val, fmt)}</td>'
        us_delta_str = f"{us_delta*100:+.1f}%" if us_delta is not None else "—"
        us_color = _delta_color(us_delta, kpi_name)
        html += f'<td style="padding: 6px; text-align: right; {us_color}">{us_delta_str}</td>'

        # Total columns
        html += f'<td style="padding: 6px; text-align: right; border-left: 2px solid #444; color: #aaa;">{_format_val(tot_avg, fmt)}</td>'
        html += f'<td style="padding: 6px; text-align: right; color: #ccc;">{_format_val(tot_prev_val, fmt)}</td>'
        html += f'<td style="padding: 6px; text-align: right; font-weight: 600; color: #fff;">{_format_val(tot_curr_val, fmt)}</td>'
        tot_delta_str = f"{tot_delta*100:+.1f}%" if tot_delta is not None else "—"
        tot_color = _delta_color(tot_delta, kpi_name)
        html += f'<td style="padding: 6px; text-align: right; {tot_color}">{tot_delta_str}</td>'

        html += '</tr>'

    html += '</tbody></table></div>'

    st.markdown(html, unsafe_allow_html=True)


def render_kpis_tab(
    current_report: WeeklyReport,
    previous_report: WeeklyReport,
    selected_categories: list[str],
    eur_usd_rate: float,
    has_sellerboard: bool = False,
) -> None:
    """Render the full KPIs tab with overall + category sections."""
    prev_label = f"{current_report.previous_week_start.strftime('%d %b')} - {current_report.previous_week_end.strftime('%d %b %Y')}"
    curr_label = f"{current_report.week_start.strftime('%d %b')} - {current_report.week_end.strftime('%d %b %Y')}"

    # EUR/USD badge
    st.markdown(
        f'<div style="text-align: right; color: #aaa; font-size: 12px; margin-bottom: 8px;">'
        f'EUR/USD: {eur_usd_rate:.2f}</div>',
        unsafe_allow_html=True,
    )

    # Overall section
    render_kpi_section(
        section_name="Overall",
        eu_current=current_report.region_totals.get(Region.EU_UK),
        eu_previous=previous_report.region_totals.get(Region.EU_UK),
        us_current=current_report.region_totals.get(Region.US_CA),
        us_previous=previous_report.region_totals.get(Region.US_CA),
        eur_usd_rate=eur_usd_rate,
        has_sellerboard=has_sellerboard,
        prev_week_label=prev_label,
        last_week_label=curr_label,
    )

    # Category sections
    for cat_name, cat_kpis in current_report.by_category.items():
        if cat_name.startswith("_"):
            continue
        if selected_categories and cat_kpis.category_display_name not in selected_categories:
            continue

        prev_cat = previous_report.by_category.get(cat_name)

        render_kpi_section(
            section_name=cat_kpis.category_display_name,
            eu_current=cat_kpis.regions.get(Region.EU_UK),
            eu_previous=prev_cat.regions.get(Region.EU_UK) if prev_cat else None,
            us_current=cat_kpis.regions.get(Region.US_CA),
            us_previous=prev_cat.regions.get(Region.US_CA) if prev_cat else None,
            eur_usd_rate=eur_usd_rate,
            has_sellerboard=has_sellerboard,
            prev_week_label=prev_label,
            last_week_label=curr_label,
        )
