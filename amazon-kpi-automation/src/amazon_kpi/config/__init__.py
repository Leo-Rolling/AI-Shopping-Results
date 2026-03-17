"""Configuration module for Amazon KPI automation."""

from .constants import (
    KPI_NAMES,
    MARKETPLACES,
    REGIONS,
    EUR_TO_USD_RATE,
    CURRENCY_SYMBOLS,
)
from .sku_categories import CATEGORY_MAP, CATEGORIES

__all__ = [
    "KPI_NAMES",
    "MARKETPLACES",
    "REGIONS",
    "EUR_TO_USD_RATE",
    "CURRENCY_SYMBOLS",
    "CATEGORY_MAP",
    "CATEGORIES",
]
