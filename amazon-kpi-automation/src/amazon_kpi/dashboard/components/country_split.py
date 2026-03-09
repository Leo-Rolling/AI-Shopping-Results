"""Country split table component — replicates EU5 and NA Country Split sheets.

Shows KPI rows broken down by individual marketplace columns.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from ...config.constants import CURRENCY_SYMBOLS, Marketplace, Region
from ...processing.models import KPIData, WeeklyReport
from .kpi_table import (
    KPI_ROWS,
    SP_API_KPIS,
    _compute_formula,
    _delta_color,
    _delta_pct,
    _format_val,
    _get_kpi_value,
    _is_available,
)


def render_country_split(
    current_report: WeeklyReport,
    previous_report: WeeklyReport,
    marketplaces: list[Marketplace],
    selected_categories: list[str],
    has_sellerboard: bool = False,
) -> None:
    """Render country split tab for a set of marketplaces."""
    prev_label = f"{current_report.previous_week_start.strftime('%d %b')} - {current_report.previous_week_end.strftime('%d %b %Y')}"
    curr_label = f"{current_report.week_start.strftime('%d %b')} - {current_report.week_end.strftime('%d %b %Y')}"

    # Overall section
    _render_split_section(
        section_name="Overall",
        marketplaces=marketplaces,
        current_report=current_report,
        previous_report=previous_report,
        category_name=None,
        has_sellerboard=has_sellerboard,
        prev_label=prev_label,
        curr_label=curr_label,
    )

    # Category sections
    for cat_name, cat_kpis in current_report.by_category.items():
        if cat_name.startswith("_"):
            continue
        if selected_categories and cat_kpis.category_display_name not in selected_categories:
            continue

        _render_split_section(
            section_name=cat_kpis.category_display_name,
            marketplaces=marketplaces,
            current_report=current_report,
            previous_report=previous_report,
            category_name=cat_name,
            has_sellerboard=has_sellerboard,
            prev_label=prev_label,
            curr_label=curr_label,
        )


def _get_marketplace_data(
    report: WeeklyReport,
    marketplace: Marketplace,
    category_name: str | None,
) -> KPIData | None:
    """Get KPIData for a marketplace, optionally filtered by category."""
    mp_kpis = report.by_marketplace.get(marketplace)
    if mp_kpis is None:
        return None

    if category_name is None:
        return mp_kpis.total
    return mp_kpis.categories.get(category_name)


def _render_split_section(
    section_name: str,
    marketplaces: list[Marketplace],
    current_report: WeeklyReport,
    previous_report: WeeklyReport,
    category_name: str | None,
    has_sellerboard: bool,
    prev_label: str,
    curr_label: str,
) -> None:
    """Render a single section of the country split table."""
    n_mp = len(marketplaces)

    # Build header (dark theme)
    html = f"""
    <div style="margin-bottom: 24px;">
    <h4 style="margin-bottom: 8px; color: #e0e0e0;">{section_name}</h4>
    <table style="width:100%; border-collapse: collapse; font-size: 12px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; color: #e0e0e0;">
    <thead>
        <tr style="background: #1a1a2e; color: white;">
            <th style="padding: 6px; text-align: left; width: 120px;" rowspan="2">KPI</th>
    """

    for mp in marketplaces:
        currency = CURRENCY_SYMBOLS.get(mp, "")
        html += f'<th style="padding: 6px; text-align: center; border-left: 2px solid #444;" colspan="4">{mp.value} ({currency})</th>'

    html += '</tr><tr style="background: #2d2d44; color: #aaa; font-size: 10px;">'

    for mp in marketplaces:
        html += f'<th style="padding: 3px; border-left: 2px solid #444;">Avg/Day</th>'
        html += f'<th style="padding: 3px;">{prev_label}</th>'
        html += f'<th style="padding: 3px;">{curr_label}</th>'
        html += f'<th style="padding: 3px;">Delta</th>'

    html += '</tr></thead><tbody>'

    for i, (kpi_name, attr_name, fmt, is_formula) in enumerate(KPI_ROWS):
        available = _is_available(kpi_name, has_sellerboard)
        row_bg = "#1e1e2e" if i % 2 == 0 else "#262638"

        if not available:
            html += f'<tr style="background: #333; color: #666;">'
            html += f'<td style="padding: 5px 6px; font-weight: 500;">{kpi_name}</td>'
            for _ in marketplaces:
                html += '<td style="padding: 5px; text-align: right; border-left: 2px solid #444;" colspan="4">—</td>'
            html += '</tr>'
            continue

        html += f'<tr style="background: {row_bg}; color: #e0e0e0;">'
        html += f'<td style="padding: 5px 6px; font-weight: 500; color: #fff;">{kpi_name}</td>'

        for mp in marketplaces:
            curr_data = _get_marketplace_data(current_report, mp, category_name)
            prev_data = _get_marketplace_data(previous_report, mp, category_name)

            curr_val = _get_kpi_value(kpi_name, attr_name, is_formula, curr_data)
            prev_val = _get_kpi_value(kpi_name, attr_name, is_formula, prev_data)

            is_ratio_kpi = is_formula and kpi_name not in {"AOV"}
            avg_val = curr_val if is_ratio_kpi else (curr_val / 7 if curr_val is not None else None)
            delta = _delta_pct(curr_val, prev_val)
            delta_str = f"{delta*100:+.1f}%" if delta is not None else "—"
            color = _delta_color(delta, kpi_name)

            html += f'<td style="padding: 5px; text-align: right; border-left: 2px solid #444; color: #aaa;">{_format_val(avg_val, fmt)}</td>'
            html += f'<td style="padding: 5px; text-align: right; color: #ccc;">{_format_val(prev_val, fmt)}</td>'
            html += f'<td style="padding: 5px; text-align: right; font-weight: 600; color: #fff;">{_format_val(curr_val, fmt)}</td>'
            html += f'<td style="padding: 5px; text-align: right; {color}">{delta_str}</td>'

        html += '</tr>'

    html += '</tbody></table></div>'

    st.markdown(html, unsafe_allow_html=True)
