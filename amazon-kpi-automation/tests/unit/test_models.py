"""Unit tests for Pydantic data models."""

from decimal import Decimal

import pytest

from amazon_kpi.processing.models import KPIData, KPIDelta


class TestKPIData:
    """Tests for KPIData model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        data = KPIData()
        assert data.gross_sales == Decimal("0")
        assert data.units_sold == 0
        assert data.orders == 0
        assert data.net_profit == Decimal("0")

    def test_from_dict(self):
        """Test creating KPIData from dictionary."""
        input_data = {
            "Gross Sales": 1000.50,
            "Units Sold": 100,
            "Orders": 80,
            "Net Profit": 250.25,
            "Margin": 25.0,
        }
        data = KPIData.from_dict(input_data)

        assert data.gross_sales == Decimal("1000.5")
        assert data.units_sold == 100
        assert data.orders == 80
        assert data.net_profit == Decimal("250.25")
        assert data.margin == Decimal("25.0")

    def test_to_dict(self):
        """Test converting KPIData to dictionary."""
        data = KPIData(
            gross_sales=Decimal("500"),
            units_sold=50,
            orders=40,
        )
        result = data.to_dict()

        assert result["Gross Sales"] == Decimal("500")
        assert result["Units Sold"] == 50
        assert result["Orders"] == 40
        assert "Net Profit" in result

    def test_addition(self):
        """Test adding two KPIData objects."""
        data1 = KPIData(
            gross_sales=Decimal("1000"),
            units_sold=100,
            orders=80,
            net_profit=Decimal("200"),
            cogs=Decimal("500"),
        )
        data2 = KPIData(
            gross_sales=Decimal("500"),
            units_sold=50,
            orders=40,
            net_profit=Decimal("100"),
            cogs=Decimal("250"),
        )

        result = data1 + data2

        assert result.gross_sales == Decimal("1500")
        assert result.units_sold == 150
        assert result.orders == 120
        assert result.net_profit == Decimal("300")

    def test_currency_conversion(self):
        """Test currency conversion."""
        data = KPIData(
            gross_sales=Decimal("1000"),
            net_profit=Decimal("200"),
            ad_spend=Decimal("100"),
        )

        converted = data.convert_currency(Decimal("1.08"))

        assert converted.gross_sales == Decimal("1080")
        assert converted.net_profit == Decimal("216")
        assert converted.ad_spend == Decimal("108")
        # Units should not change
        assert converted.units_sold == data.units_sold


class TestKPIDelta:
    """Tests for KPIDelta model."""

    def test_positive_change(self):
        """Test delta with positive change."""
        delta = KPIDelta(
            current_value=Decimal("150"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("50"),
            percentage_change=Decimal("50.00"),
        )

        assert delta.is_positive is True
        assert delta.is_negative is False

    def test_negative_change(self):
        """Test delta with negative change."""
        delta = KPIDelta(
            current_value=Decimal("80"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("-20"),
            percentage_change=Decimal("-20.00"),
        )

        assert delta.is_positive is False
        assert delta.is_negative is True

    def test_no_change(self):
        """Test delta with no change."""
        delta = KPIDelta(
            current_value=Decimal("100"),
            previous_value=Decimal("100"),
            absolute_change=Decimal("0"),
            percentage_change=Decimal("0"),
        )

        assert delta.is_positive is False
        assert delta.is_negative is False

    def test_integer_values(self):
        """Test delta with integer values."""
        delta = KPIDelta(
            current_value=150,
            previous_value=100,
            absolute_change=50,
            percentage_change=Decimal("50.00"),
        )

        assert delta.is_positive is True
        assert isinstance(delta.absolute_change, int)
