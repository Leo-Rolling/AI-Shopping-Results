"""SKU to category mappings for Amazon products."""

from typing import Final


class Category:
    """Product category with display name and SKU list."""

    def __init__(self, name: str, display_name: str, skus: list[str]):
        self.name = name
        self.display_name = display_name
        self.skus = skus

    def __repr__(self) -> str:
        return f"Category({self.name}, {len(self.skus)} SKUs)"


# Category SKU mappings - 8 product categories
# Each category maps to a list of SKU codes used in Sellerboard filtering

TRACKERS_SKUS: Final[list[str]] = [
    "TRK-001",
    "TRK-002",
    "TRK-003",
    "TRK-PRO-001",
    "TRK-PRO-002",
    "TRK-MINI-001",
    "TRK-MINI-002",
]

AIRCARD_LIGHT_SKUS: Final[list[str]] = [
    "ACL-001",
    "ACL-002",
    "ACL-003",
    "ACL-BLK-001",
    "ACL-WHT-001",
]

INCHARGE_SKUS: Final[list[str]] = [
    "ICH-X-001",
    "ICH-X-002",
    "ICH-X-003",
    "ICH-6-001",
    "ICH-6-002",
    "ICH-XL-001",
    "ICH-XL-002",
]

CABLES_SKUS: Final[list[str]] = [
    "CBL-USB-C-001",
    "CBL-USB-C-002",
    "CBL-USB-A-001",
    "CBL-LTG-001",
    "CBL-LTG-002",
    "CBL-MULTI-001",
]

ADAPTERS_SKUS: Final[list[str]] = [
    "ADP-001",
    "ADP-002",
    "ADP-PRO-001",
    "ADP-WALL-001",
    "ADP-CAR-001",
]

POWER_BANKS_SKUS: Final[list[str]] = [
    "PWB-5K-001",
    "PWB-10K-001",
    "PWB-10K-002",
    "PWB-20K-001",
    "PWB-SLIM-001",
]

ACCESSORIES_SKUS: Final[list[str]] = [
    "ACC-CASE-001",
    "ACC-CASE-002",
    "ACC-STRAP-001",
    "ACC-CLIP-001",
    "ACC-HOLDER-001",
]

BUNDLES_SKUS: Final[list[str]] = [
    "BDL-TRK-ACL-001",
    "BDL-ICH-CBL-001",
    "BDL-PWB-ADP-001",
    "BDL-COMPLETE-001",
]

# Category definitions with display names
CATEGORIES: Final[list[Category]] = [
    Category("trackers", "Trackers", TRACKERS_SKUS),
    Category("aircard_light", "AirCard Light", AIRCARD_LIGHT_SKUS),
    Category("incharge", "inCharge", INCHARGE_SKUS),
    Category("cables", "Cables", CABLES_SKUS),
    Category("adapters", "Adapters", ADAPTERS_SKUS),
    Category("power_banks", "Power Banks", POWER_BANKS_SKUS),
    Category("accessories", "Accessories", ACCESSORIES_SKUS),
    Category("bundles", "Bundles", BUNDLES_SKUS),
]

# Quick lookup dictionary: category_name -> Category
CATEGORY_SKUS: Final[dict[str, Category]] = {cat.name: cat for cat in CATEGORIES}

# All SKUs across all categories (for validation)
ALL_SKUS: Final[set[str]] = {sku for cat in CATEGORIES for sku in cat.skus}


def get_category_by_name(name: str) -> Category | None:
    """Get category by its internal name."""
    return CATEGORY_SKUS.get(name)


def get_category_for_sku(sku: str) -> Category | None:
    """Find which category a SKU belongs to."""
    for category in CATEGORIES:
        if sku in category.skus:
            return category
    return None
