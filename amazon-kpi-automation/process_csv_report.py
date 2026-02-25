"""Process CSV files from Sellerboard and generate KPI report."""
import os
import sys
from datetime import date, datetime
from decimal import Decimal
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.amazon_kpi.config.constants import Region, Marketplace
from src.amazon_kpi.processing.models import WeeklyReport, KPIData, CategoryKPIs, MarketplaceKPIs
from src.amazon_kpi.output.templates import KPISummaryTemplate, ByCountryTemplate

# SKU to Category mapping based on product prefixes
def get_category_from_sku(sku: str) -> str:
    """Map SKU to category based on prefix."""
    sku_upper = sku.upper()

    # AirCard / Trackers
    if sku_upper.startswith(('ACP', 'ANP', 'AIR')):
        return 'aircard'

    # inCharge cables
    if sku_upper.startswith(('X0', 'XS', 'XL', 'SIX')):
        return 'incharge'

    # Edge Pro
    if sku_upper.startswith(('EPC', 'EPK', 'EPP')):
        return 'edge_pro'

    # Adapters / Chargers
    if sku_upper.startswith(('ST', 'TRAV', 'ADP')):
        return 'adapters'

    # Power Banks
    if sku_upper.startswith(('TAU', 'PWB')):
        return 'power_banks'

    # Cables
    if sku_upper.startswith('CBL'):
        return 'cables'

    # Accessories
    if sku_upper.startswith('ACC'):
        return 'accessories'

    # Bundles
    if sku_upper.startswith('BDL'):
        return 'bundles'

    return 'other'


def marketplace_from_string(mp_str: str) -> Marketplace | None:
    """Convert marketplace string to Marketplace enum."""
    mp_map = {
        'Amazon.com': Marketplace.US,
        'Amazon.ca': Marketplace.CA,
        'Amazon.co.uk': Marketplace.UK,
        'Amazon.de': Marketplace.DE,
        'Amazon.fr': Marketplace.FR,
        'Amazon.it': Marketplace.IT,
        'Amazon.es': Marketplace.ES,
    }
    return mp_map.get(mp_str)


def get_region(mp: Marketplace) -> Region:
    """Get region for a marketplace."""
    if mp in (Marketplace.US, Marketplace.CA):
        return Region.US_CA
    return Region.EU_UK


def create_kpi_data(row_data: pd.Series) -> KPIData:
    """Create KPIData from aggregated row."""
    gross_sales = Decimal(str(row_data.get('SalesOrganic', 0) + row_data.get('SalesPPC', 0)))
    ad_spend = Decimal(str(abs(row_data.get('SponsoredProducts', 0)) +
                          abs(row_data.get('SponsoredDisplay', 0)) +
                          abs(row_data.get('SponsoredВrands', 0)) +
                          abs(row_data.get('SponsoredBrandsVideo', 0))))
    ppc_sales = Decimal(str(row_data.get('SalesPPC', 0)))
    net_profit = Decimal(str(row_data.get('NetProfit', 0)))
    refunds = Decimal(str(abs(row_data.get('Refund Principal', 0))))
    orders = int(row_data.get('Orders', row_data.get('UnitsOrganic', 0) + row_data.get('UnitsPPC', 0)))
    units = int(row_data.get('UnitsOrganic', 0) + row_data.get('UnitsPPC', 0))

    # Calculate derived metrics
    acos = (ad_spend / ppc_sales * 100) if ppc_sales > 0 else Decimal('0')
    tacos = (ad_spend / gross_sales * 100) if gross_sales > 0 else Decimal('0')
    roas = (ppc_sales / ad_spend) if ad_spend > 0 else Decimal('0')
    margin = (net_profit / gross_sales * 100) if gross_sales > 0 else Decimal('0')

    return KPIData(
        gross_sales=gross_sales,
        units_sold=units,
        orders=orders,
        refunds=refunds,
        ad_spend=ad_spend,
        ppc_sales=ppc_sales,
        net_profit=net_profit,
        acos=acos,
        tacos=tacos,
        roas=roas,
        margin=margin,
    )


def process_csv_files(folder_path: str) -> WeeklyReport:
    """Process CSV files and create WeeklyReport."""

    # Find the Dashboard Goods file (has detailed data by SKU and marketplace)
    goods_file = None
    totals_file = None

    for f in os.listdir(folder_path):
        if 'DashboardGoods' in f and f.endswith('.csv'):
            goods_file = os.path.join(folder_path, f)
        elif 'DashboardTotals' in f and f.endswith('.csv'):
            totals_file = os.path.join(folder_path, f)

    if not goods_file:
        raise FileNotFoundError("DashboardGoods CSV not found")

    print(f"Reading: {os.path.basename(goods_file)}")
    df = pd.read_csv(goods_file)

    # Parse dates to get week range
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y')
    week_start = df['Date'].min().date()
    week_end = df['Date'].max().date()

    # Previous week (assuming 7 days before)
    from datetime import timedelta
    prev_week_end = week_start - timedelta(days=1)
    prev_week_start = prev_week_end - timedelta(days=6)

    print(f"Week: {week_start} to {week_end}")

    # Add category column
    df['Category'] = df['SKU'].apply(get_category_from_sku)

    # Convert marketplace string to enum
    df['MP'] = df['Marketplace'].apply(marketplace_from_string)
    df = df[df['MP'].notna()]  # Filter out unknown marketplaces

    # Numeric columns to aggregate
    numeric_cols = ['SalesOrganic', 'SalesPPC', 'SalesSponsoredProducts', 'SalesSponsoredDisplay',
                   'UnitsOrganic', 'UnitsPPC', 'Refunds', 'SponsoredProducts', 'SponsoredDisplay',
                   'SponsoredВrands', 'SponsoredBrandsVideo', 'Refund Principal', 'NetProfit',
                   'GrossProfit', 'Commission', 'FBAPerUnitFulfillmentFee']

    # Ensure numeric columns are numeric
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Add Orders column if not present (use units as proxy)
    if 'Orders' not in df.columns:
        df['Orders'] = df['UnitsOrganic'] + df['UnitsPPC']

    # Aggregate by marketplace
    mp_agg = df.groupby('MP')[numeric_cols + ['Orders']].sum()

    by_marketplace = {}
    for mp in mp_agg.index:
        mp_data = mp_agg.loc[mp]
        kpi = create_kpi_data(mp_data)
        by_marketplace[mp] = MarketplaceKPIs(
            marketplace=mp,
            total=kpi
        )

    # Aggregate by category
    by_category = {}
    for cat_name in df['Category'].unique():
        cat_df = df[df['Category'] == cat_name]

        # By marketplace within category
        cat_mp_agg = cat_df.groupby('MP')[numeric_cols + ['Orders']].sum()
        mp_kpis = {}
        for mp in cat_mp_agg.index:
            mp_data = cat_mp_agg.loc[mp]
            mp_kpis[mp] = create_kpi_data(mp_data)

        # By region within category
        region_kpis = {}
        for region in Region:
            region_mps = [mp for mp in cat_mp_agg.index if get_region(mp) == region]
            if region_mps:
                region_data = cat_df[cat_df['MP'].isin(region_mps)][numeric_cols + ['Orders']].sum()
                region_kpis[region] = create_kpi_data(region_data)

        display_names = {
            'aircard': 'AirCard',
            'incharge': 'inCharge',
            'edge_pro': 'Edge Pro',
            'adapters': 'Adapters',
            'power_banks': 'Power Banks',
            'cables': 'Cables',
            'accessories': 'Accessories',
            'bundles': 'Bundles',
            'other': 'Other',
        }

        by_category[cat_name] = CategoryKPIs(
            category_name=cat_name,
            category_display_name=display_names.get(cat_name, cat_name.title()),
            marketplaces=mp_kpis,
            regions=region_kpis,
        )

    # Calculate region totals
    region_totals = {}
    for region in Region:
        region_mps = [mp for mp in by_marketplace.keys() if get_region(mp) == region]
        if region_mps:
            region_data = df[df['MP'].isin(region_mps)][numeric_cols + ['Orders']].sum()
            region_totals[region] = create_kpi_data(region_data)

    # Grand total
    total_data = df[numeric_cols + ['Orders']].sum()
    grand_total = create_kpi_data(total_data)

    return WeeklyReport(
        week_start=week_start,
        week_end=week_end,
        previous_week_start=prev_week_start,
        previous_week_end=prev_week_end,
        by_marketplace=by_marketplace,
        by_category=by_category,
        region_totals=region_totals,
        grand_total=grand_total,
    )


def main():
    folder_path = "/Users/leonardodol/Downloads/10feb26"

    print("=" * 60)
    print("Processing CSV files from Sellerboard")
    print("=" * 60)

    # Process CSV files
    report = process_csv_files(folder_path)

    print(f"\nMarketplaces found: {list(report.by_marketplace.keys())}")
    print(f"Categories found: {list(report.by_category.keys())}")
    print(f"Region totals: {list(report.region_totals.keys())}")

    # Build templates
    print("\nBuilding KPI templates...")
    kpi_template = KPISummaryTemplate()
    kpi_data = kpi_template.build(report)

    country_template = ByCountryTemplate()
    country_data = country_template.build(report)

    print(f"KPIs sheet: {len(kpi_data)} rows")
    print(f"By Country sheet: {len(country_data)} rows")

    # Save to Excel
    output_path = os.path.expanduser("~/Desktop/AMZ_KPI_Report_10Feb.xlsx")

    print(f"\nSaving to: {output_path}")
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_kpi = pd.DataFrame(kpi_data)
        df_kpi.to_excel(writer, sheet_name='KPIs', index=False, header=False)

        df_country = pd.DataFrame(country_data)
        df_country.to_excel(writer, sheet_name='By Country', index=False, header=False)

    print("\n" + "=" * 60)
    print("REPORT GENERATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\nFile: {output_path}")
    print(f"Week: {report.week_start} to {report.week_end}")

    # Print summary
    if report.grand_total:
        print(f"\nOverall Summary:")
        print(f"  Revenue: ${float(report.grand_total.gross_sales):,.2f}")
        print(f"  Net Profit: ${float(report.grand_total.net_profit):,.2f}")
        print(f"  Orders: {report.grand_total.orders}")
        print(f"  Ad Spend: ${float(report.grand_total.ad_spend):,.2f}")
        print(f"  ACOS: {float(report.grand_total.acos):.1f}%")


if __name__ == "__main__":
    main()
