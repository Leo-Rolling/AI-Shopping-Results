"""Constants for marketplaces, KPIs, and regional configurations."""

from enum import Enum
from typing import Final


class Marketplace(str, Enum):
    """Amazon marketplace identifiers."""

    US = "US"
    CA = "CA"
    UK = "UK"
    DE = "DE"
    IT = "IT"
    FR = "FR"
    ES = "ES"


class Region(str, Enum):
    """Aggregated regional groupings."""

    EU_UK = "EU+UK"
    US_CA = "US+CA"
    TOTAL = "Total"


# All marketplaces in processing order
MARKETPLACES: Final[list[Marketplace]] = [
    Marketplace.US,
    Marketplace.CA,
    Marketplace.UK,
    Marketplace.DE,
    Marketplace.IT,
    Marketplace.FR,
    Marketplace.ES,
]

# Regional groupings for aggregation
REGIONS: Final[dict[Region, list[Marketplace]]] = {
    Region.EU_UK: [
        Marketplace.UK,
        Marketplace.DE,
        Marketplace.IT,
        Marketplace.FR,
        Marketplace.ES,
    ],
    Region.US_CA: [
        Marketplace.US,
        Marketplace.CA,
    ],
}

# KPI names as displayed in Sellerboard and sheets
KPI_NAMES: Final[list[str]] = [
    "Gross Sales",
    "Units Sold",
    "Orders",
    "Refunds",
    "Refund Rate",
    "Promo Rebates",
    "Amazon Costs",
    "COGS",
    "Net Profit",
    "Margin",
    "ROI",
    "Ad Spend",
    "ACOS",
    "TACOS",
]

# KPIs that should be displayed as currency
CURRENCY_KPIS: Final[set[str]] = {
    "Gross Sales",
    "Refunds",
    "Promo Rebates",
    "Amazon Costs",
    "COGS",
    "Net Profit",
    "Ad Spend",
}

# KPIs that should be displayed as percentages
PERCENTAGE_KPIS: Final[set[str]] = {
    "Refund Rate",
    "Margin",
    "ROI",
    "ACOS",
    "TACOS",
    "ROAS",
    "Net Margin",
    "PPC Sales/Revenue",
}

# KPIs that should be displayed as integers
INTEGER_KPIS: Final[set[str]] = {
    "Units Sold",
    "Orders",
}

# Currency conversion rate (EUR to USD)
EUR_TO_USD_RATE: Final[float] = 1.08

# Currency symbols per marketplace
CURRENCY_SYMBOLS: Final[dict[Marketplace, str]] = {
    Marketplace.US: "$",
    Marketplace.CA: "C$",
    Marketplace.UK: "£",
    Marketplace.DE: "€",
    Marketplace.IT: "€",
    Marketplace.FR: "€",
    Marketplace.ES: "€",
}

# Marketplace to Sellerboard filter value mapping
MARKETPLACE_SELLERBOARD_IDS: Final[dict[Marketplace, str]] = {
    Marketplace.US: "amazon.com",
    Marketplace.CA: "amazon.ca",
    Marketplace.UK: "amazon.co.uk",
    Marketplace.DE: "amazon.de",
    Marketplace.IT: "amazon.it",
    Marketplace.FR: "amazon.fr",
    Marketplace.ES: "amazon.es",
}

# Date range options in Sellerboard
class DateRange(str, Enum):
    """Sellerboard date range filter options."""

    PREVIOUS_WEEK = "Previous Week"  # Week before last
    LAST_WEEK = "Last Week"  # Most recent complete week


# Sellerboard base URL
SELLERBOARD_BASE_URL: Final[str] = "https://app.sellerboard.com"
SELLERBOARD_DASHBOARD_URL: Final[str] = f"{SELLERBOARD_BASE_URL}/en/dashboard"
SELLERBOARD_LOGIN_URL: Final[str] = f"{SELLERBOARD_BASE_URL}/en/auth/login/"

# Retry configuration
MAX_RETRIES: Final[int] = 3
RETRY_DELAY_SECONDS: Final[float] = 2.0
PAGE_LOAD_TIMEOUT_MS: Final[int] = 30000
ELEMENT_TIMEOUT_MS: Final[int] = 10000

# Random delay range for human-like behavior (seconds)
MIN_ACTION_DELAY: Final[float] = 1.0
MAX_ACTION_DELAY: Final[float] = 3.0


# =============================================================================
# SP-API Configuration
# =============================================================================


class SellerAccount(str, Enum):
    """SP-API seller account identifiers."""

    EU_UK = "EU_UK"  # Covers: UK, DE, IT, FR, ES
    NA = "NA"  # Covers: US, CA


# Mapping from our Marketplace enum to Amazon SP-API marketplace IDs
MARKETPLACE_SP_API_IDS: Final[dict[Marketplace, str]] = {
    Marketplace.US: "ATVPDKIKX0DER",
    Marketplace.CA: "A2EUQ1WTGCTBG2",
    Marketplace.UK: "A1F83G8C2ARO7P",
    Marketplace.DE: "A1PA6795UKMFR9",
    Marketplace.IT: "APJ6JRA9NG5V4",
    Marketplace.FR: "A13V1IB3VIYZZH",
    Marketplace.ES: "A1RKKUPIHCS9HS",
}

# Mapping from Marketplace to SellerAccount
MARKETPLACE_ACCOUNT: Final[dict[Marketplace, SellerAccount]] = {
    Marketplace.US: SellerAccount.NA,
    Marketplace.CA: SellerAccount.NA,
    Marketplace.UK: SellerAccount.EU_UK,
    Marketplace.DE: SellerAccount.EU_UK,
    Marketplace.IT: SellerAccount.EU_UK,
    Marketplace.FR: SellerAccount.EU_UK,
    Marketplace.ES: SellerAccount.EU_UK,
}

# SP-API endpoint regions
SP_API_ENDPOINTS: Final[dict[SellerAccount, str]] = {
    SellerAccount.NA: "https://sellingpartnerapi-na.amazon.com",
    SellerAccount.EU_UK: "https://sellingpartnerapi-eu.amazon.com",
}

# SP-API Data Kiosk polling configuration
DATA_KIOSK_POLL_INTERVAL_SECONDS: Final[int] = 30
DATA_KIOSK_MAX_POLL_ATTEMPTS: Final[int] = 60  # 30 minutes max wait

# SP-API retry configuration
SP_API_MAX_RETRIES: Final[int] = 5
SP_API_RETRY_BASE_DELAY: Final[float] = 2.0
SP_API_RETRY_MAX_DELAY: Final[float] = 60.0
