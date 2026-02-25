"""Unit tests for week-over-week comparison calculations."""

from decimal import Decimal

import pytest

from amazon_kpi.processing.models import KPIData
from amazon_kpi.processing.comparator import (
    calculate_deltas,
    format_delta_for_display,
    get_trend_indicator,
    is_significant_change,
)


class TestCalculateDeltas:
    """Tests for calculate_deltas function."""

    def test_basic_comparison(self):
        """Test basic week-over-week comparison."""
        current = KPIData(
            gross_sales=Decimal("1500"),
            units_sold=150,
            orders=120,
            net_profit=Decimal("300"),
        )
        previous = KPIData(
            gross_sales=Decimal("1000"),
            units_sold=100,
            orders=80,
            net_profit=Decimal("200"),
        )

        comparison = calculate_deltas(current, previous)

        assert comparison.deltas["Gross Sales"].absolute_change == Decimal("500")
        assert comparison.deltas["Gross Sales"].percentage_change == Decimal("50.00")
        assert comparison.deltas["Units Sold"].absolute_change == 50
        assert comparison.deltas["Orders"].absolute_change == 40

    def test_negative_change(self):
        """Test comparison with decrease."""
        current = KPIData(gross_sales=Decimal("800"))
        previous = KPIData(gross_sales=Decimal("1000"))

        comparison = calculate_deltas(current, previous)

        delta = comparison.deltas["Gross Sales"]
        assert delta.absolute_change == Decimal("-200")
        assert delta.percentage_change == Decimal("-20.00")
        assert delta.is_negative is True

    def test_zero_previous(self):
        """Test comparison when previous value is zero."""
        current = KPIData(gross_sales=Decimal("1000"))
        previous = KPIData(gross_sales=Decimal("0"))

        comparison = calculate_deltas(current, previous)

        delta = comparison.deltas["Gross Sales"]
        assert delta.absolute_change == Decimal("1000")
        assert delta.percentage_change is None  # Cannot calculate % from zero

    def test_no_change(self):
        """Test comparison with no change."""
        current = KPIData(gross_sales=Decimal("1000"), units_sold=100)
        previous = KPIData(gross_sales=Decimal("1000"), units_sold=100)

        comparison = calculate_deltas(current, previous)

        assert comparison.deltas["Gross Sales"].absolute_change == Decimal("0")
        assert comparison.deltas["Gross Sales"].percentage_change == Decimal("0.00")
        assert comparison.deltas["Units Sold"].absolute_change == 0

    def test_helper_methods(self):
        """Test WeekOverWeekComparison helper methods."""
        current = KPIData(gross_sales=Decimal("1500"))
        previous = KPIData(gross_sales=Decimal("1000"))

        comparison = calculate_deltas(current, previous)

        assert comparison.get_percentage_change("Gross Sales") == Decimal("50.00")
        assert comparison.is_positive_change("Gross Sales") is True
        assert comparison.is_negative_change("Gross Sales") is False


class TestFormatDeltaForDisplay:
    """Tests for format_delta_for_display function."""

    def test_positive_with_percentage(self):
        """Test formatting positive delta with percentage."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("150"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("50"),
            percentage_change=Decimal("50.00"),
        )

        result = format_delta_for_display(delta)
        assert "+" in result
        assert "50.0%" in result

    def test_negative_delta(self):
        """Test formatting negative delta."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("80"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("-20"),
            percentage_change=Decimal("-20.00"),
        )

        result = format_delta_for_display(delta)
        assert "-" in result

    def test_integer_delta(self):
        """Test formatting integer delta."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=150,
            previous_value=100,
            absolute_change=50,
            percentage_change=Decimal("50.00"),
        )

        result = format_delta_for_display(delta)
        assert "50" in result


class TestTrendIndicator:
    """Tests for get_trend_indicator function."""

    def test_positive_trend(self):
        """Test trend indicator for positive change."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("150"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("50"),
            percentage_change=Decimal("50.00"),
        )

        assert get_trend_indicator(delta) == "↑"

    def test_negative_trend(self):
        """Test trend indicator for negative change."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("80"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("-20"),
            percentage_change=Decimal("-20.00"),
        )

        assert get_trend_indicator(delta) == "↓"

    def test_no_change_trend(self):
        """Test trend indicator for no change."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("100"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("0"),
            percentage_change=Decimal("0"),
        )

        assert get_trend_indicator(delta) == "→"


class TestSignificantChange:
    """Tests for is_significant_change function."""

    def test_significant_positive(self):
        """Test detection of significant positive change."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("120"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("20"),
            percentage_change=Decimal("20.00"),
        )

        assert is_significant_change(delta, Decimal("5")) is True

    def test_insignificant_change(self):
        """Test detection of insignificant change."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("102"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("2"),
            percentage_change=Decimal("2.00"),
        )

        assert is_significant_change(delta, Decimal("5")) is False

    def test_no_percentage(self):
        """Test when percentage change is None."""
        from amazon_kpi.processing.models import KPIDelta

        delta = KPIDelta(
            current_value=Decimal("100"),
            previous_value=Decimal("0"),
            absolute_change=Decimal("100"),
            percentage_change=None,
        )

        assert is_significant_change(delta) is False
