"""Week-over-week comparison calculations for KPI data."""

from decimal import Decimal
from dataclasses import dataclass
from typing import Any

import structlog

from ..config.constants import KPI_NAMES
from .models import KPIData, KPIDelta, KPIComparison

logger = structlog.get_logger(__name__)


@dataclass
class WeekOverWeekComparison:
    """Container for week-over-week comparison results."""

    current_week: KPIData
    previous_week: KPIData
    deltas: dict[str, KPIDelta]

    def get_delta(self, kpi_name: str) -> KPIDelta | None:
        """Get delta for a specific KPI."""
        return self.deltas.get(kpi_name)

    def get_percentage_change(self, kpi_name: str) -> Decimal | None:
        """Get percentage change for a specific KPI."""
        delta = self.deltas.get(kpi_name)
        return delta.percentage_change if delta else None

    def is_positive_change(self, kpi_name: str) -> bool:
        """Check if KPI change is positive."""
        delta = self.deltas.get(kpi_name)
        return delta.is_positive if delta else False

    def is_negative_change(self, kpi_name: str) -> bool:
        """Check if KPI change is negative."""
        delta = self.deltas.get(kpi_name)
        return delta.is_negative if delta else False


def calculate_deltas(
    current: KPIData,
    previous: KPIData,
) -> WeekOverWeekComparison:
    """
    Calculate week-over-week changes between two KPI data sets.

    Args:
        current: Current week's KPI data
        previous: Previous week's KPI data

    Returns:
        WeekOverWeekComparison with all delta calculations
    """
    logger.debug("Calculating week-over-week deltas")

    current_dict = current.to_dict()
    previous_dict = previous.to_dict()
    deltas: dict[str, KPIDelta] = {}

    for kpi_name in KPI_NAMES:
        current_value = current_dict.get(kpi_name, Decimal("0"))
        previous_value = previous_dict.get(kpi_name, Decimal("0"))

        delta = _calculate_single_delta(current_value, previous_value)
        deltas[kpi_name] = delta

        logger.debug(
            "Delta calculated",
            kpi=kpi_name,
            current=str(current_value),
            previous=str(previous_value),
            change=str(delta.absolute_change),
            pct_change=str(delta.percentage_change) if delta.percentage_change else "N/A",
        )

    return WeekOverWeekComparison(
        current_week=current,
        previous_week=previous,
        deltas=deltas,
    )


def _calculate_single_delta(
    current: Decimal | int,
    previous: Decimal | int,
) -> KPIDelta:
    """
    Calculate delta for a single KPI value.

    Args:
        current: Current value
        previous: Previous value

    Returns:
        KPIDelta with absolute and percentage changes
    """
    # Convert to Decimal for consistent calculation
    current_dec = Decimal(str(current))
    previous_dec = Decimal(str(previous))

    # Absolute change
    absolute_change = current_dec - previous_dec

    # Percentage change
    percentage_change: Decimal | None = None
    if previous_dec != Decimal("0"):
        percentage_change = (absolute_change / previous_dec) * Decimal("100")
        # Round to 2 decimal places
        percentage_change = percentage_change.quantize(Decimal("0.01"))

    # Preserve original type for absolute change
    if isinstance(current, int) and isinstance(previous, int):
        return KPIDelta(
            current_value=current,
            previous_value=previous,
            absolute_change=int(absolute_change),
            percentage_change=percentage_change,
        )

    return KPIDelta(
        current_value=current_dec,
        previous_value=previous_dec,
        absolute_change=absolute_change,
        percentage_change=percentage_change,
    )


def calculate_comparison_matrix(
    current_data: dict[str, dict[str, KPIData]],
    previous_data: dict[str, dict[str, KPIData]],
) -> dict[str, dict[str, WeekOverWeekComparison]]:
    """
    Calculate comparisons for a matrix of data (e.g., marketplace x category).

    Args:
        current_data: Current week data (outer_key -> inner_key -> KPIData)
        previous_data: Previous week data (same structure)

    Returns:
        Nested dict with WeekOverWeekComparison for each cell
    """
    result: dict[str, dict[str, WeekOverWeekComparison]] = {}

    for outer_key, inner_data in current_data.items():
        result[outer_key] = {}

        for inner_key, current_kpis in inner_data.items():
            previous_kpis = previous_data.get(outer_key, {}).get(inner_key)

            if previous_kpis:
                result[outer_key][inner_key] = calculate_deltas(current_kpis, previous_kpis)
            else:
                # No previous data - create comparison with zero previous
                result[outer_key][inner_key] = calculate_deltas(current_kpis, KPIData())

    return result


def format_delta_for_display(
    delta: KPIDelta,
    include_percentage: bool = True,
    include_sign: bool = True,
) -> str:
    """
    Format a delta for display in reports.

    Args:
        delta: KPIDelta to format
        include_percentage: Whether to include percentage change
        include_sign: Whether to include +/- sign

    Returns:
        Formatted string like "+$1,234 (+15.2%)"
    """
    absolute = delta.absolute_change
    percentage = delta.percentage_change

    # Format absolute change
    if isinstance(absolute, int):
        abs_str = f"{absolute:,}"
    else:
        abs_str = f"{float(absolute):,.2f}"

    # Add sign
    if include_sign:
        if isinstance(absolute, Decimal):
            is_positive = absolute > Decimal("0")
        else:
            is_positive = absolute > 0

        if is_positive:
            abs_str = f"+{abs_str}"

    # Add percentage
    if include_percentage and percentage is not None:
        pct_str = f"{float(percentage):+.1f}%"
        return f"{abs_str} ({pct_str})"

    return abs_str


def get_trend_indicator(delta: KPIDelta) -> str:
    """
    Get a trend indicator emoji/symbol for a delta.

    Args:
        delta: KPIDelta to evaluate

    Returns:
        Trend indicator string
    """
    if delta.is_positive:
        return "↑"
    elif delta.is_negative:
        return "↓"
    return "→"


def is_significant_change(
    delta: KPIDelta,
    threshold_percent: Decimal = Decimal("5"),
) -> bool:
    """
    Determine if a change is significant based on percentage threshold.

    Args:
        delta: KPIDelta to evaluate
        threshold_percent: Minimum percentage for significance

    Returns:
        True if change exceeds threshold
    """
    if delta.percentage_change is None:
        return False

    return abs(delta.percentage_change) >= threshold_percent
