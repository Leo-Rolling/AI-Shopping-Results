"""Tests for SP-API GraphQL query templates."""

from amazon_kpi.sp_api.queries import (
    SALES_TRAFFIC_BY_ASIN,
    SALES_TRAFFIC_BY_DATE,
    SEARCH_QUERY_PERFORMANCE,
    BRAND_ANALYTICS_MARKET_BASKET,
    BRAND_ANALYTICS_REPEAT_PURCHASE,
    build_query,
)


class TestBuildQuery:
    """Tests for the build_query function."""

    def test_sales_traffic_by_asin_query(self):
        """Build a valid Sales & Traffic by ASIN query."""
        query = build_query(
            SALES_TRAFFIC_BY_ASIN,
            start_date="2024-02-01",
            end_date="2024-02-07",
            marketplace_id="ATVPDKIKX0DER",
        )
        assert "2024-02-01" in query
        assert "2024-02-07" in query
        assert "ATVPDKIKX0DER" in query
        assert "salesAndTrafficByAsin" in query
        assert "orderedProductSales" in query
        assert "unitSessionPercentage" in query

    def test_sales_traffic_by_date_query(self):
        """Build a valid Sales & Traffic by Date query."""
        query = build_query(
            SALES_TRAFFIC_BY_DATE,
            start_date="2024-01-01",
            end_date="2024-01-31",
            marketplace_id="A1F83G8C2ARO7P",
        )
        assert "salesAndTrafficByDate" in query
        assert "A1F83G8C2ARO7P" in query
        assert "DAY" in query

    def test_search_query_performance(self):
        """Build a valid SQP query."""
        query = build_query(
            SEARCH_QUERY_PERFORMANCE,
            start_date="2024-02-01",
            end_date="2024-02-07",
            marketplace_id="ATVPDKIKX0DER",
        )
        assert "searchQueryPerformanceByQueryASIN" in query
        assert "queryImpressions" in query
        assert "queryPurchaseRate" in query

    def test_market_basket_query(self):
        """Build a valid Market Basket query."""
        query = build_query(
            BRAND_ANALYTICS_MARKET_BASKET,
            start_date="2024-02-01",
            end_date="2024-02-07",
            marketplace_id="ATVPDKIKX0DER",
        )
        assert "marketBasketByAsin" in query
        assert "purchasedWithAsin" in query
        assert "combinationPercentage" in query

    def test_repeat_purchase_query(self):
        """Build a valid Repeat Purchase query."""
        query = build_query(
            BRAND_ANALYTICS_REPEAT_PURCHASE,
            start_date="2024-03-01",
            end_date="2024-03-31",
            marketplace_id="A1PA6795UKMFR9",
        )
        assert "repeatPurchaseByAsin" in query
        assert "A1PA6795UKMFR9" in query
        assert "repeatPurchaseRate" in query

    def test_query_has_no_unresolved_placeholders(self):
        """Ensure all placeholders are resolved after build."""
        query = build_query(
            SALES_TRAFFIC_BY_ASIN,
            start_date="2024-01-01",
            end_date="2024-01-07",
            marketplace_id="ATVPDKIKX0DER",
        )
        # No remaining {placeholder} patterns (escaped {{ }} become { })
        assert "{start_date}" not in query
        assert "{end_date}" not in query
        assert "{marketplace_id}" not in query
