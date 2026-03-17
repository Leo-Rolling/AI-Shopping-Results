"""SKU and ASIN to category mappings for Amazon products.

Uses prefix-based matching on seller SKUs and a direct ASIN→SKU lookup table.
"""

from typing import Final


class Category:
    """Product category with display name and SKU prefix patterns."""

    def __init__(self, name: str, display_name: str, sku_prefixes: list[str]):
        self.name = name
        self.display_name = display_name
        self.sku_prefixes = sku_prefixes

    def matches_sku(self, sku: str) -> bool:
        """Check if a SKU belongs to this category (prefix match, case-insensitive)."""
        sku_upper = sku.upper()
        return any(sku_upper.startswith(p) for p in self.sku_prefixes)

    def __repr__(self) -> str:
        return f"Category({self.name}, prefixes={self.sku_prefixes})"


# ---------------------------------------------------------------------------
# Category definitions with SKU prefix patterns
# ---------------------------------------------------------------------------

CATEGORIES: Final[list[Category]] = [
    Category("trackers", "Trackers", [
        "ACP", "ANP", "AIR", "ACD",  # AirCard Pro, AirNotch Pro, AirCard, AirCard Duo
    ]),
    Category("incharge", "inCharge", [
        "SIX",   # inCharge 6
        "X01", "X02", "X03",  # inCharge X
        "XLS", "XLM", "XLL", "XLXS",  # inCharge XL variants
        "XS0",   # inCharge XS
    ]),
    Category("edge_pro", "Edge Pro", [
        "EPC", "EPCC", "EPK", "EKIT", "1AU",
    ]),
    Category("adapters", "Adapters & Chargers", [
        "ST65", "ST14", "TRAV",  # SuperTiny 65W, Travel adapters
    ]),
    Category("power_banks", "Power Banks", [
        "TAU",  # TAU power banks
    ]),
]

# Quick lookup dictionary: category_name -> Category
CATEGORY_MAP: Final[dict[str, Category]] = {cat.name: cat for cat in CATEGORIES}

# ---------------------------------------------------------------------------
# ASIN → SKU mapping (all regions)
# ---------------------------------------------------------------------------

ASIN_TO_SKU: Final[dict[str, str]] = {
    # inCharge 6
    "B0866753FP": "SIX01",
    "B086WHBN3N": "SIX02",
    "B086WHFRJH": "SIX03",
    # inCharge X
    "B09CDWT1JL": "X01W",
    "B09XGJCXQ8": "X02W",
    "B09XGYX72P": "X03W",
    # inCharge XL-S
    "B0BKGMCJHX": "XLS01E",
    "B0BLD36VX6": "XLS02E",
    "B0BKGR5B76": "XLS03E",
    # inCharge XL-M
    "B0BKGXZB5J": "XLM01E",
    "B0BKH1R68F": "XLM02E",
    "B0BKH1S748": "XLM03E",
    # inCharge XL-L
    "B0BKGVZ6MY": "XLL01E",
    "B0BKGWN8FP": "XLL02E",
    "B0BKGZ41GK": "XLL03E",
    # inCharge XL-XS
    "B0CHYZMZFX": "XLXS04E",
    # inCharge XS
    "B0DQQ8SD9P": "XS01E",
    "B0DQQBRFFF": "XS02E",
    "B0DQQCMB6D": "XS03E",
    # Edge Pro
    "B0C541J8V4": "EPC01",
    "B0C53ZWWXT": "EPC02",
    "B0C654376B": "EPCC01",
    "B0C659SJH2": "EPCC02",
    "B0C53ZGTYP": "EPK01",
    "B0C5426D2Y": "EPK02",
    # Trackers — AirCard
    "B0C8NHVW7L": "AIR01",
    "B0D4VD7HVW": "AIR01X2",
    "B0D4V8KTTW": "AIR01X4",
    "B0C8NMF1K2": "AIRCARDE",
    # Trackers — AirCard Pro
    "B0F3DNV9XY": "ACP01E",
    "B0F3F7SRR7": "ACP02E",
    "B0F4XQYHPD": "ACP01EX2",
    "B0FV3RV1H7": "ACP03E",
    "B0G2T7S5QF": "ACP03EX2",
    # Trackers — AirNotch Pro
    "B0F3F5R1XR": "ANP01E",
    "B0F3FFS2JM": "ANP02E",
    "B0F4XPMZYQ": "ANP01EX2",
    "B0FV3VGN48": "ANP03E",
    "B0G2T2SJ6Z": "ANP03EX2",
    # Trackers — AirCard Duo
    "B0GBY33MMG": "ACD01E",
    # Power Banks — TAU
    "B0D1VKR1M4": "TAU201E",
    "B0D1VKRMGV": "TAU202E",
    # Adapters & Chargers — SuperTiny 65W
    "B0DYDVBJRM": "ST65UKE",
    "B0F9Q1RJ1N": "ST65USE",
    "B0DYDT5F77": "ST65EUE",
    # Adapters & Chargers — Travel
    "B0C8HVRLNB": "TRAVPKR",
    "B0DZD3SJJ3": "TRAV30R",
}

# Reverse lookup: SKU → ASIN (first match; some SKUs have same ASIN across regions)
SKU_TO_ASIN: Final[dict[str, str]] = {sku: asin for asin, sku in ASIN_TO_SKU.items()}

# All known ASINs
ALL_ASINS: Final[set[str]] = set(ASIN_TO_SKU.keys())

# All known SKUs
ALL_SKUS: Final[set[str]] = set(ASIN_TO_SKU.values())


def get_category_for_sku(sku: str) -> Category | None:
    """Find which category a SKU belongs to (prefix match)."""
    if not sku:
        return None
    for category in CATEGORIES:
        if category.matches_sku(sku):
            return category
    return None


def get_category_for_asin(asin: str) -> Category | None:
    """Find which category an ASIN belongs to via ASIN→SKU lookup."""
    sku = ASIN_TO_SKU.get(asin)
    if sku:
        return get_category_for_sku(sku)
    return None


def resolve_sku(sku: str | None = None, asin: str | None = None) -> str | None:
    """Resolve to a known SKU from either a SKU or ASIN.

    The SP-API sometimes returns empty SKU but has the ASIN.
    """
    if sku:
        return sku
    if asin:
        return ASIN_TO_SKU.get(asin)
    return None


def get_category_by_name(name: str) -> Category | None:
    """Get category by its internal name."""
    return CATEGORY_MAP.get(name)
