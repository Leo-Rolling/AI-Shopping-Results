"""Pydantic data models for KPI data structures."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, ConfigDict

from ..config.constants import Marketplace, Region, KPI_NAMES


class KPIData(BaseModel):
    """Individual KPI metrics for a single marketplace/category/period."""

    model_config = ConfigDict(frozen=True)

    gross_sales: Decimal = Field(default=Decimal("0"), description="Total gross sales (Revenue)")
    units_sold: int = Field(default=0, description="Number of units sold")
    orders: int = Field(default=0, description="Number of orders")
    refunds: Decimal = Field(default=Decimal("0"), description="Total refund amount")
    refund_rate: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, description="Refund rate percentage"
    )
    promo_rebates: Decimal = Field(default=Decimal("0"), description="Promotional rebates")
    amazon_costs: Decimal = Field(default=Decimal("0"), description="Amazon fees and costs")
    cogs: Decimal = Field(default=Decimal("0"), description="Cost of goods sold")
    net_profit: Decimal = Field(default=Decimal("0"), description="Net profit after all costs")
    margin: Decimal = Field(default=Decimal("0"), description="Profit margin percentage")
    roi: Decimal = Field(default=Decimal("0"), description="Return on investment percentage")
    ad_spend: Decimal = Field(default=Decimal("0"), description="Advertising spend (PPC)")
    ppc_sales: Decimal = Field(default=Decimal("0"), description="Sales attributed to PPC")
    acos: Decimal = Field(default=Decimal("0"), ge=0, description="Advertising cost of sales %")
    tacos: Decimal = Field(default=Decimal("0"), ge=0, description="Total ACOS percentage")
    roas: Decimal = Field(default=Decimal("0"), ge=0, description="Return on Ad Spend")

    @property
    def ppc_sales_ratio(self) -> Decimal:
        """PPC Sales / Revenue ratio."""
        if self.gross_sales > 0:
            return self.ppc_sales / self.gross_sales
        return Decimal("0")

    @property
    def aov(self) -> Decimal:
        """Average Order Value (Revenue / Orders)."""
        if self.orders > 0:
            return self.gross_sales / Decimal(str(self.orders))
        return Decimal("0")

    def to_dict(self) -> dict[str, Decimal | int]:
        """Convert to dictionary with KPI names as keys."""
        return {
            "Gross Sales": self.gross_sales,
            "Units Sold": self.units_sold,
            "Orders": self.orders,
            "Refunds": self.refunds,
            "Refund Rate": self.refund_rate,
            "Promo Rebates": self.promo_rebates,
            "Amazon Costs": self.amazon_costs,
            "COGS": self.cogs,
            "Net Profit": self.net_profit,
            "Margin": self.margin,
            "ROI": self.roi,
            "Ad Spend": self.ad_spend,
            "ACOS": self.acos,
            "TACOS": self.tacos,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Decimal | int | float | str]) -> "KPIData":
        """Create KPIData from dictionary with KPI names as keys."""
        return cls(
            gross_sales=Decimal(str(data.get("Gross Sales", 0))),
            units_sold=int(data.get("Units Sold", 0)),
            orders=int(data.get("Orders", 0)),
            refunds=Decimal(str(data.get("Refunds", 0))),
            refund_rate=Decimal(str(data.get("Refund Rate", 0))),
            promo_rebates=Decimal(str(data.get("Promo Rebates", 0))),
            amazon_costs=Decimal(str(data.get("Amazon Costs", 0))),
            cogs=Decimal(str(data.get("COGS", 0))),
            net_profit=Decimal(str(data.get("Net Profit", 0))),
            margin=Decimal(str(data.get("Margin", 0))),
            roi=Decimal(str(data.get("ROI", 0))),
            ad_spend=Decimal(str(data.get("Ad Spend", 0))),
            acos=Decimal(str(data.get("ACOS", 0))),
            tacos=Decimal(str(data.get("TACOS", 0))),
        )

    def __add__(self, other: "KPIData") -> "KPIData":
        """Add two KPIData objects (for aggregation). Percentages are recalculated."""
        if not isinstance(other, KPIData):
            return NotImplemented

        # Sum additive metrics
        gross_sales = self.gross_sales + other.gross_sales
        units_sold = self.units_sold + other.units_sold
        orders = self.orders + other.orders
        refunds = self.refunds + other.refunds
        promo_rebates = self.promo_rebates + other.promo_rebates
        amazon_costs = self.amazon_costs + other.amazon_costs
        cogs = self.cogs + other.cogs
        net_profit = self.net_profit + other.net_profit
        ad_spend = self.ad_spend + other.ad_spend
        ppc_sales = self.ppc_sales + other.ppc_sales

        # Recalculate percentages based on aggregated values
        refund_rate = (
            (refunds / gross_sales * 100) if gross_sales > 0 else Decimal("0")
        )
        margin = (net_profit / gross_sales * 100) if gross_sales > 0 else Decimal("0")
        roi = (net_profit / cogs * 100) if cogs > 0 else Decimal("0")
        acos = (ad_spend / gross_sales * 100) if gross_sales > 0 else Decimal("0")
        tacos = acos  # TACOS calculation may need adjustment based on business logic
        roas = (ppc_sales / ad_spend) if ad_spend > 0 else Decimal("0")

        return KPIData(
            gross_sales=gross_sales,
            units_sold=units_sold,
            orders=orders,
            refunds=refunds,
            refund_rate=refund_rate,
            promo_rebates=promo_rebates,
            amazon_costs=amazon_costs,
            cogs=cogs,
            net_profit=net_profit,
            margin=margin,
            roi=roi,
            ad_spend=ad_spend,
            ppc_sales=ppc_sales,
            acos=acos,
            tacos=tacos,
            roas=roas,
        )

    def convert_currency(self, rate: Decimal) -> "KPIData":
        """Convert currency values by given rate. Used for EUR to USD conversion."""
        return KPIData(
            gross_sales=self.gross_sales * rate,
            units_sold=self.units_sold,
            orders=self.orders,
            refunds=self.refunds * rate,
            refund_rate=self.refund_rate,
            promo_rebates=self.promo_rebates * rate,
            amazon_costs=self.amazon_costs * rate,
            cogs=self.cogs * rate,
            net_profit=self.net_profit * rate,
            margin=self.margin,
            roi=self.roi,
            ad_spend=self.ad_spend * rate,
            ppc_sales=self.ppc_sales * rate,
            acos=self.acos,
            tacos=self.tacos,
            roas=self.roas,
        )


class MarketplaceKPIs(BaseModel):
    """KPI data for a single marketplace across all categories."""

    model_config = ConfigDict(frozen=True, revalidate_instances="never")

    marketplace: Marketplace
    categories: dict[str, KPIData] = Field(
        default_factory=dict, description="Category name -> KPI data"
    )
    total: KPIData | None = Field(
        default=None, description="Aggregated KPIs across all categories"
    )


class CategoryKPIs(BaseModel):
    """KPI data for a single category across all marketplaces."""

    model_config = ConfigDict(frozen=True, revalidate_instances="never")

    category_name: str
    category_display_name: str
    marketplaces: dict[Marketplace, KPIData] = Field(
        default_factory=dict, description="Marketplace -> KPI data"
    )
    regions: dict[Region, KPIData] = Field(
        default_factory=dict, description="Aggregated regional data"
    )


class WeeklyReport(BaseModel):
    """Complete weekly report containing all KPI data."""

    model_config = ConfigDict(frozen=True, revalidate_instances="never")

    week_start: date
    week_end: date
    previous_week_start: date
    previous_week_end: date

    # Per-marketplace data: marketplace -> category -> KPIs
    by_marketplace: dict[Marketplace, MarketplaceKPIs] = Field(default_factory=dict)

    # Per-category data: category -> marketplace/region -> KPIs
    by_category: dict[str, CategoryKPIs] = Field(default_factory=dict)

    # Overall totals by region
    region_totals: dict[Region, KPIData] = Field(default_factory=dict)

    # Grand total (all regions combined in USD)
    grand_total: KPIData | None = None


class KPIDelta(BaseModel):
    """Week-over-week change for a single KPI value."""

    model_config = ConfigDict(frozen=True)

    current_value: Decimal | int
    previous_value: Decimal | int
    absolute_change: Decimal | int
    percentage_change: Decimal | None = Field(
        default=None, description="Percentage change (None if previous was 0)"
    )

    @property
    def is_positive(self) -> bool:
        """Check if the change is positive."""
        if isinstance(self.absolute_change, Decimal):
            return self.absolute_change > Decimal("0")
        return self.absolute_change > 0

    @property
    def is_negative(self) -> bool:
        """Check if the change is negative."""
        if isinstance(self.absolute_change, Decimal):
            return self.absolute_change < Decimal("0")
        return self.absolute_change < 0


class KPIComparison(BaseModel):
    """Week-over-week comparison for all KPIs."""

    model_config = ConfigDict(frozen=True)

    current_week: KPIData
    previous_week: KPIData
    deltas: dict[str, KPIDelta] = Field(
        default_factory=dict, description="KPI name -> delta"
    )
