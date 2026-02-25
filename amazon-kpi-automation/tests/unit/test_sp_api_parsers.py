"""Tests for SP-API data parsers."""

from decimal import Decimal

import pandas as pd

from amazon_kpi.config.constants import Marketplace
from amazon_kpi.sp_api.parsers import (
    parse_sales_traffic,
    parse_sales_traffic_by_date,
    parse_search_query_performance,
    parse_market_basket,
    parse_repeat_purchase,
)


class TestParseSalesTraffic:
    """Tests for sales & traffic JSONL parsing."""

    def test_empty_records(self):
        """Empty records produce empty MarketplaceKPIs."""
        result = parse_sales_traffic([], Marketplace.US)
        assert result.marketplace == Marketplace.US
        assert result.categories == {}
        assert result.total is None

    def test_single_record_with_known_sku(self):
        """A record with a known SKU is categorized correctly."""
        records = [
            {
                "salesAndTrafficByAsin": [
                    {
                        "sku": "TRK-001",
                        "sales": {
                            "orderedProductSales": {"amount": "150.00", "currencyCode": "USD"},
                            "unitsOrdered": 5,
                            "totalOrderItems": 3,
                            "unitsRefunded": 1,
                            "refundRate": 0.2,
                        },
                        "traffic": {
                            "browserPageViews": 100,
                            "mobileAppPageViews": 50,
                            "browserSessions": 80,
                            "mobileAppSessions": 40,
                            "buyBoxPercentage": 95.0,
                            "unitSessionPercentage": 4.17,
                        },
                    }
                ]
            }
        ]
        result = parse_sales_traffic(records, Marketplace.US)
        assert "trackers" in result.categories
        kpi = result.categories["trackers"]
        assert kpi.gross_sales == Decimal("150.00")
        assert kpi.units_sold == 5
        assert kpi.orders == 3

    def test_unknown_sku_goes_to_other(self):
        """A record with an unknown SKU is categorized as 'other'."""
        records = [
            {
                "salesAndTrafficByAsin": [
                    {
                        "sku": "UNKNOWN-SKU-999",
                        "sales": {
                            "orderedProductSales": {"amount": "50.00"},
                            "unitsOrdered": 2,
                            "totalOrderItems": 1,
                            "unitsRefunded": 0,
                            "refundRate": 0,
                        },
                        "traffic": {},
                    }
                ]
            }
        ]
        result = parse_sales_traffic(records, Marketplace.DE)
        assert "other" in result.categories
        assert result.categories["other"].units_sold == 2

    def test_multiple_records_aggregated(self):
        """Multiple records with the same category are summed."""
        records = [
            {
                "salesAndTrafficByAsin": [
                    {
                        "sku": "TRK-001",
                        "sales": {
                            "orderedProductSales": {"amount": "100"},
                            "unitsOrdered": 3,
                            "totalOrderItems": 2,
                            "unitsRefunded": 0,
                            "refundRate": 0,
                        },
                        "traffic": {},
                    },
                    {
                        "sku": "TRK-002",
                        "sales": {
                            "orderedProductSales": {"amount": "200"},
                            "unitsOrdered": 7,
                            "totalOrderItems": 5,
                            "unitsRefunded": 1,
                            "refundRate": 0,
                        },
                        "traffic": {},
                    },
                ]
            }
        ]
        result = parse_sales_traffic(records, Marketplace.US)
        kpi = result.categories["trackers"]
        assert kpi.gross_sales == Decimal("300")
        assert kpi.units_sold == 10
        assert kpi.orders == 7

    def test_total_aggregates_all_categories(self):
        """Total KPIs aggregate across all categories."""
        records = [
            {
                "salesAndTrafficByAsin": [
                    {
                        "sku": "TRK-001",
                        "sales": {
                            "orderedProductSales": {"amount": "100"},
                            "unitsOrdered": 2,
                            "totalOrderItems": 1,
                            "unitsRefunded": 0,
                            "refundRate": 0,
                        },
                        "traffic": {},
                    },
                    {
                        "sku": "ICH-X-001",
                        "sales": {
                            "orderedProductSales": {"amount": "50"},
                            "unitsOrdered": 3,
                            "totalOrderItems": 2,
                            "unitsRefunded": 0,
                            "refundRate": 0,
                        },
                        "traffic": {},
                    },
                ]
            }
        ]
        result = parse_sales_traffic(records, Marketplace.US)
        assert result.total is not None
        assert result.total.gross_sales == Decimal("150")
        assert result.total.units_sold == 5


class TestParseSalesTrafficByDate:
    """Tests for daily sales & traffic parsing."""

    def test_produces_dataframe(self):
        """Records are converted to a DataFrame with expected columns."""
        records = [
            {
                "salesAndTrafficByDate": [
                    {
                        "startDate": "2024-02-01",
                        "endDate": "2024-02-01",
                        "sales": {
                            "orderedProductSales": {"amount": "500.00", "currencyCode": "USD"},
                            "unitsOrdered": 20,
                            "unitsRefunded": 2,
                            "refundRate": 0.1,
                            "totalOrderItems": 15,
                        },
                        "traffic": {
                            "browserPageViews": 1000,
                            "mobileAppPageViews": 500,
                            "browserSessions": 800,
                            "mobileAppSessions": 400,
                            "buyBoxPercentage": 92.5,
                            "unitSessionPercentage": 1.67,
                        },
                    }
                ]
            }
        ]
        df = parse_sales_traffic_by_date(records, Marketplace.US)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["ordered_sales"] == 500.0
        assert df.iloc[0]["units_ordered"] == 20
        assert df.iloc[0]["marketplace"] == "US"


class TestParseSearchQueryPerformance:
    """Tests for SQP data parsing."""

    def test_produces_dataframe(self):
        """SQP records are parsed into a DataFrame."""
        records = [
            {
                "searchQueryPerformanceByQueryASIN": [
                    {
                        "startDate": "2024-02-01",
                        "endDate": "2024-02-07",
                        "searchQuery": "bluetooth tracker",
                        "asin": "B0ABCDEF12",
                        "queryImpressions": 5000,
                        "queryClicks": 250,
                        "queryClickRate": 0.05,
                        "queryCartAdds": 50,
                        "queryPurchases": 20,
                        "queryPurchaseRate": 0.004,
                    }
                ]
            }
        ]
        df = parse_search_query_performance(records, Marketplace.US)
        assert len(df) == 1
        assert df.iloc[0]["search_query"] == "bluetooth tracker"
        assert df.iloc[0]["impressions"] == 5000
        assert df.iloc[0]["clicks"] == 250
        assert df.iloc[0]["purchase_rate"] == 0.004

    def test_empty_records(self):
        """Empty records produce empty DataFrame."""
        df = parse_search_query_performance([], Marketplace.UK)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestParseMarketBasket:
    """Tests for Market Basket parsing."""

    def test_produces_dataframe(self):
        """Market Basket records are parsed correctly."""
        records = [
            {
                "marketBasketByAsin": [
                    {
                        "startDate": "2024-02-01",
                        "endDate": "2024-02-07",
                        "asin": "B0ABCDEF12",
                        "purchasedWithAsin": "B0XYZ98765",
                        "purchasedWithTitle": "Phone Case",
                        "combinationPercentage": 15.5,
                    }
                ]
            }
        ]
        df = parse_market_basket(records, Marketplace.DE)
        assert len(df) == 1
        assert df.iloc[0]["combination_pct"] == 15.5


class TestParseRepeatPurchase:
    """Tests for Repeat Purchase parsing."""

    def test_produces_dataframe(self):
        """Repeat Purchase records are parsed correctly."""
        records = [
            {
                "repeatPurchaseByAsin": [
                    {
                        "startDate": "2024-02-01",
                        "endDate": "2024-02-07",
                        "asin": "B0ABCDEF12",
                        "ordersTotal": 100,
                        "ordersRepeat": 25,
                        "repeatPurchaseRate": 0.25,
                    }
                ]
            }
        ]
        df = parse_repeat_purchase(records, Marketplace.US)
        assert len(df) == 1
        assert df.iloc[0]["orders_total"] == 100
        assert df.iloc[0]["repeat_purchase_rate"] == 0.25
