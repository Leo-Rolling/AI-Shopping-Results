"""GraphQL query templates for the Data Kiosk API.

Each template uses Python string formatting with named placeholders.
Use build_query() to fill in parameters like dates and marketplace IDs.
"""

from typing import Final


# ---------------------------------------------------------------------------
# Sales & Traffic by ASIN (child-level, weekly)
# ---------------------------------------------------------------------------
SALES_TRAFFIC_BY_ASIN: Final[str] = """\
{{
  analytics_salesAndTraffic_2024_04_24 {{
    salesAndTrafficByAsin(
      aggregateBy: CHILD
      startDate: "{start_date}"
      endDate: "{end_date}"
      marketplaceIds: ["{marketplace_id}"]
    ) {{
      startDate
      endDate
      marketplaceId
      childAsin
      parentAsin
      sku
      sales {{
        orderedProductSales {{ amount currencyCode }}
        unitsOrdered
        unitsRefunded
        refundRate
        totalOrderItems
      }}
      traffic {{
        browserPageViews
        mobileAppPageViews
        browserSessions
        mobileAppSessions
        buyBoxPercentage
        unitSessionPercentage
        sessionPercentage
      }}
    }}
  }}
}}
"""

# ---------------------------------------------------------------------------
# Sales & Traffic by Date (daily aggregation)
# ---------------------------------------------------------------------------
SALES_TRAFFIC_BY_DATE: Final[str] = """\
{{
  analytics_salesAndTraffic_2024_04_24 {{
    salesAndTrafficByDate(
      aggregateBy: DAY
      startDate: "{start_date}"
      endDate: "{end_date}"
      marketplaceIds: ["{marketplace_id}"]
    ) {{
      startDate
      endDate
      marketplaceId
      sales {{
        orderedProductSales {{ amount currencyCode }}
        unitsOrdered
        unitsRefunded
        refundRate
        totalOrderItems
      }}
      traffic {{
        browserPageViews
        mobileAppPageViews
        browserSessions
        mobileAppSessions
        buyBoxPercentage
        unitSessionPercentage
      }}
    }}
  }}
}}
"""

# ---------------------------------------------------------------------------
# Search Query Performance (requires Brand Analytics access)
# ---------------------------------------------------------------------------
SEARCH_QUERY_PERFORMANCE: Final[str] = """\
{{
  analytics_searchQueryPerformance_2024_04_24 {{
    searchQueryPerformanceByQueryASIN(
      startDate: "{start_date}"
      endDate: "{end_date}"
      marketplaceIds: ["{marketplace_id}"]
    ) {{
      startDate
      endDate
      marketplaceId
      searchQuery
      asin
      queryImpressions
      queryClicks
      queryClickRate
      queryCartAdds
      queryPurchases
      queryPurchaseRate
    }}
  }}
}}
"""

# ---------------------------------------------------------------------------
# Brand Analytics - Market Basket (requires Brand Analytics access)
# ---------------------------------------------------------------------------
BRAND_ANALYTICS_MARKET_BASKET: Final[str] = """\
{{
  analytics_marketBasket_2024_04_24 {{
    marketBasketByAsin(
      startDate: "{start_date}"
      endDate: "{end_date}"
      marketplaceIds: ["{marketplace_id}"]
    ) {{
      startDate
      endDate
      marketplaceId
      asin
      purchasedWithAsin
      purchasedWithTitle
      combinationPercentage
    }}
  }}
}}
"""

# ---------------------------------------------------------------------------
# Brand Analytics - Repeat Purchase (requires Brand Analytics access)
# ---------------------------------------------------------------------------
BRAND_ANALYTICS_REPEAT_PURCHASE: Final[str] = """\
{{
  analytics_repeatPurchase_2024_04_24 {{
    repeatPurchaseByAsin(
      startDate: "{start_date}"
      endDate: "{end_date}"
      marketplaceIds: ["{marketplace_id}"]
    ) {{
      startDate
      endDate
      marketplaceId
      asin
      ordersTotal
      ordersRepeat
      repeatPurchaseRate
    }}
  }}
}}
"""


# ---------------------------------------------------------------------------
# Economics (ads, fees, net proceeds, COGS) — by MSKU, weekly range
# ---------------------------------------------------------------------------
ECONOMICS_BY_MSKU: Final[str] = """\
{{
  analytics_economics_2024_03_15 {{
    economics(
      startDate: "{start_date}"
      endDate: "{end_date}"
      marketplaceIds: ["{marketplace_id}"]
      aggregateBy: {{ date: RANGE, productId: MSKU }}
    ) {{
      msku
      childAsin
      parentAsin
      startDate
      endDate
      marketplaceId
      sales {{
        orderedProductSales {{ amount currencyCode }}
        netProductSales {{ amount currencyCode }}
        unitsOrdered
        unitsRefunded
        netUnitsSold
      }}
      ads {{
        adTypeName
        charge {{
          totalAmount {{ amount currencyCode }}
        }}
      }}
      cost {{
        costOfGoodsSold {{ amount currencyCode }}
      }}
      netProceeds {{
        total {{ amount currencyCode }}
      }}
    }}
  }}
}}
"""


def build_query(template: str, **kwargs: str) -> str:
    """Build a GraphQL query from a template with parameters.

    Args:
        template: Query template with {placeholder} markers.
        **kwargs: Values to substitute (e.g., start_date, end_date, marketplace_id).

    Returns:
        Formatted GraphQL query string.
    """
    return template.format(**kwargs)
