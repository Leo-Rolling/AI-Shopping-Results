"""Unit tests for formatting utilities."""

from decimal import Decimal

import pytest

from amazon_kpi.config.constants import Marketplace
from amazon_kpi.output.formatters import (
    format_currency,
    format_percentage,
    format_integer,
    format_kpi_value,
    format_delta,
    get_conditional_color,
)


class TestFormatCurrency:
    """Tests for currency formatting."""

    def test_basic_format(self):
        """Test basic currency formatting."""
        assert format_currency(1234.56) == "$1,234.56"
        assert format_currency(1000) == "$1,000.00"

    def test_negative_value(self):
        """Test formatting negative values."""
        assert format_currency(-500.50) == "-$500.50"

    def test_marketplace_symbols(self):
        """Test marketplace-specific currency symbols."""
        assert format_currency(100, Marketplace.US) == "$100.00"
        assert format_currency(100, Marketplace.UK) == "£100.00"
        assert format_currency(100, Marketplace.DE) == "€100.00"
        assert format_currency(100, Marketplace.CA) == "C$100.00"

    def test_decimal_input(self):
        """Test with Decimal input."""
        value = Decimal("1234.56")
        assert format_currency(value) == "$1,234.56"

    def test_without_symbol(self):
        """Test formatting without currency symbol."""
        assert format_currency(1234.56, include_symbol=False) == "1,234.56"


class TestFormatPercentage:
    """Tests for percentage formatting."""

    def test_basic_format(self):
        """Test basic percentage formatting."""
        assert format_percentage(15.5) == "15.5%"
        assert format_percentage(100) == "100.0%"

    def test_decimal_places(self):
        """Test different decimal places."""
        assert format_percentage(15.567, decimal_places=2) == "15.57%"
        assert format_percentage(15.567, decimal_places=0) == "16%"

    def test_decimal_input(self):
        """Test with Decimal input."""
        value = Decimal("25.5")
        assert format_percentage(value) == "25.5%"


class TestFormatInteger:
    """Tests for integer formatting."""

    def test_basic_format(self):
        """Test basic integer formatting."""
        assert format_integer(1234) == "1,234"
        assert format_integer(1000000) == "1,000,000"

    def test_decimal_input(self):
        """Test with Decimal/float input."""
        assert format_integer(1234.56) == "1,234"
        assert format_integer(Decimal("5678.9")) == "5,678"


class TestFormatKPIValue:
    """Tests for KPI-aware formatting."""

    def test_currency_kpis(self):
        """Test formatting of currency KPIs."""
        assert "$" in format_kpi_value("Gross Sales", 1000)
        assert "$" in format_kpi_value("Net Profit", 500)
        assert "$" in format_kpi_value("Ad Spend", 200)

    def test_percentage_kpis(self):
        """Test formatting of percentage KPIs."""
        assert "%" in format_kpi_value("Margin", 25.5)
        assert "%" in format_kpi_value("ACOS", 15.0)
        assert "%" in format_kpi_value("Refund Rate", 2.5)

    def test_integer_kpis(self):
        """Test formatting of integer KPIs."""
        result = format_kpi_value("Units Sold", 1234)
        assert result == "1,234"

        result = format_kpi_value("Orders", 5678)
        assert result == "5,678"


class TestFormatDelta:
    """Tests for delta formatting."""

    def test_positive_delta(self):
        """Test formatting positive delta."""
        result = format_delta(100, "Units Sold")
        assert "+" in result

    def test_negative_delta(self):
        """Test formatting negative delta."""
        result = format_delta(-50.5, "Gross Sales")
        assert "-" in result

    def test_no_sign(self):
        """Test formatting without sign."""
        result = format_delta(100, "Units Sold", include_sign=False)
        assert "+" not in result


class TestConditionalColor:
    """Tests for conditional color formatting."""

    def test_positive_change_good(self):
        """Test positive change for good KPIs."""
        color = get_conditional_color(100, "Gross Sales")
        assert color["green"] > color["red"]  # Light green

    def test_negative_change_bad(self):
        """Test negative change for good KPIs."""
        color = get_conditional_color(-100, "Gross Sales")
        assert color["red"] > color["green"]  # Light red

    def test_cost_kpi_inverted(self):
        """Test that cost KPIs have inverted color logic."""
        # For costs, lower is better
        color_decrease = get_conditional_color(-100, "Amazon Costs")
        color_increase = get_conditional_color(100, "Amazon Costs")

        # Decrease in costs should be green
        assert color_decrease["green"] > color_decrease["red"]
        # Increase in costs should be red
        assert color_increase["red"] > color_increase["green"]
