"""Formatting utilities for Google Sheets output."""

from decimal import Decimal
from typing import Any

import structlog

from ..config.constants import (
    Marketplace,
    CURRENCY_SYMBOLS,
    CURRENCY_KPIS,
    PERCENTAGE_KPIS,
    INTEGER_KPIS,
)

logger = structlog.get_logger(__name__)


# Color definitions (RGB values 0-1)
COLORS = {
    "green": {"red": 0.2, "green": 0.8, "blue": 0.2},
    "light_green": {"red": 0.85, "green": 0.95, "blue": 0.85},
    "red": {"red": 0.9, "green": 0.2, "blue": 0.2},
    "light_red": {"red": 0.95, "green": 0.85, "blue": 0.85},
    "yellow": {"red": 1.0, "green": 0.95, "blue": 0.6},
    "header_blue": {"red": 0.2, "green": 0.4, "blue": 0.8},
    "header_bg": {"red": 0.9, "green": 0.92, "blue": 0.96},
    "white": {"red": 1.0, "green": 1.0, "blue": 1.0},
    "gray": {"red": 0.9, "green": 0.9, "blue": 0.9},
}


def format_currency(
    value: Decimal | float | int,
    marketplace: Marketplace | None = None,
    include_symbol: bool = True,
) -> str:
    """
    Format a value as currency.

    Args:
        value: Numeric value to format
        marketplace: Marketplace for currency symbol
        include_symbol: Whether to include currency symbol

    Returns:
        Formatted currency string
    """
    if isinstance(value, Decimal):
        value = float(value)

    # Handle negative values
    is_negative = value < 0
    abs_value = abs(value)

    # Format with thousands separator and 2 decimal places
    formatted = f"{abs_value:,.2f}"

    # Add currency symbol
    if include_symbol:
        symbol = CURRENCY_SYMBOLS.get(marketplace, "$") if marketplace else "$"
        formatted = f"{symbol}{formatted}"

    # Add negative sign
    if is_negative:
        formatted = f"-{formatted}"

    return formatted


def format_percentage(
    value: Decimal | float | int,
    decimal_places: int = 1,
) -> str:
    """
    Format a value as percentage.

    Args:
        value: Percentage value (e.g., 15.5 for 15.5%)
        decimal_places: Number of decimal places

    Returns:
        Formatted percentage string
    """
    if isinstance(value, Decimal):
        value = float(value)

    return f"{value:.{decimal_places}f}%"


def format_integer(value: int | Decimal | float) -> str:
    """
    Format a value as integer with thousands separator.

    Args:
        value: Numeric value

    Returns:
        Formatted integer string
    """
    return f"{int(value):,}"


def format_kpi_value(
    kpi_name: str,
    value: Decimal | float | int,
    marketplace: Marketplace | None = None,
) -> str:
    """
    Format a KPI value based on its type.

    Args:
        kpi_name: Name of the KPI
        value: Value to format
        marketplace: Marketplace for currency formatting

    Returns:
        Formatted value string
    """
    if kpi_name in CURRENCY_KPIS:
        return format_currency(value, marketplace)
    elif kpi_name in PERCENTAGE_KPIS:
        return format_percentage(value)
    elif kpi_name in INTEGER_KPIS:
        return format_integer(value)
    else:
        # Default: format as number
        if isinstance(value, int):
            return format_integer(value)
        return f"{float(value):,.2f}"


def format_delta(
    delta_value: Decimal | float | int,
    kpi_name: str,
    include_sign: bool = True,
) -> str:
    """
    Format a delta (change) value.

    Args:
        delta_value: Change value
        kpi_name: Name of the KPI for type-appropriate formatting
        include_sign: Whether to include +/- sign

    Returns:
        Formatted delta string
    """
    if isinstance(delta_value, Decimal):
        delta_value = float(delta_value)

    is_positive = delta_value > 0
    sign = "+" if is_positive and include_sign else ""

    if kpi_name in CURRENCY_KPIS:
        formatted = format_currency(abs(delta_value), include_symbol=True)
        if delta_value < 0:
            return f"-{formatted}"
        return f"{sign}{formatted}"
    elif kpi_name in PERCENTAGE_KPIS:
        return f"{sign}{delta_value:.1f}pp"  # percentage points
    elif kpi_name in INTEGER_KPIS:
        return f"{sign}{int(delta_value):,}"
    else:
        return f"{sign}{delta_value:,.2f}"


def get_conditional_color(
    value: Decimal | float | int,
    kpi_name: str,
    threshold: float = 0,
) -> dict[str, float]:
    """
    Get color for conditional formatting based on value.

    Args:
        value: Value to evaluate
        kpi_name: Name of the KPI
        threshold: Threshold for positive/negative

    Returns:
        RGB color dictionary
    """
    if isinstance(value, Decimal):
        value = float(value)

    # Determine if higher is better for this KPI
    higher_is_better = kpi_name not in {
        "Refunds",
        "Refund Rate",
        "Amazon Costs",
        "COGS",
        "Ad Spend",
        "ACOS",
        "TACOS",
    }

    is_good = (value > threshold) if higher_is_better else (value < threshold)

    if value == threshold:
        return COLORS["white"]
    elif is_good:
        return COLORS["light_green"]
    else:
        return COLORS["light_red"]


def get_delta_color(
    delta: Decimal | float | int,
    kpi_name: str,
) -> dict[str, float]:
    """
    Get color for delta (change) value.

    Args:
        delta: Change value
        kpi_name: Name of the KPI

    Returns:
        RGB color dictionary
    """
    return get_conditional_color(delta, kpi_name, threshold=0)


def apply_sheet_formatting(
    sheets_service: Any,
    spreadsheet_id: str,
) -> None:
    """
    Apply formatting to the entire spreadsheet.

    Args:
        sheets_service: Google Sheets API service
        spreadsheet_id: ID of the spreadsheet
    """
    logger.info("Applying sheet formatting")

    requests = []

    # Set spreadsheet locale to Italian (displays numbers with comma as decimal separator: 100,22)
    requests.append({
        "updateSpreadsheetProperties": {
            "properties": {
                "locale": "it_IT",
            },
            "fields": "locale",
        }
    })

    # Get sheet IDs
    spreadsheet = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()

    for sheet in spreadsheet.get("sheets", []):
        sheet_id = sheet["properties"]["sheetId"]
        sheet_title = sheet["properties"]["title"]

        # Header row formatting
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": COLORS["header_bg"],
                        "textFormat": {
                            "bold": True,
                            "fontSize": 11,
                        },
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        })

        # Freeze header row
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 1,
                    },
                },
                "fields": "gridProperties.frozenRowCount",
            }
        })

        # Set number format with 2 decimal places for all cells
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": 1,
                    "endColumnIndex": 50,  # Increased for By Country sheet
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "NUMBER",
                            "pattern": "#,##0.00",  # 2 decimal places with thousands separator
                        }
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        })

        # Auto-resize columns
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 50,  # Increased for By Country sheet
                }
            }
        })

        # Apply percentage formatting to specific KPI rows
        # These are the row indices for percentage KPIs (0-indexed from data start)
        # Net Margin (row 2), PPC Sales/Revenue (row 6), ACOS (row 7), ROAS (row 8), TACOS (row 9)
        percentage_rows = [2, 6, 7, 8, 9]  # 0-indexed: Net Margin=2, PPC Sales/Rev=6, ACOS=7, ROAS=8, TACOS=9

        # Apply percentage format to KPIs sheet
        if sheet_title == "KPIs":
            # Overall section starts at row 4 (1-indexed), so row 3 (0-indexed)
            # Add formatting for overall section percentage rows
            for row_offset in percentage_rows:
                actual_row = 3 + row_offset  # 0-indexed
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": actual_row,
                            "endRowIndex": actual_row + 1,
                            "startColumnIndex": 1,
                            "endColumnIndex": 13,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "PERCENT",
                                    "pattern": "0.00%",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                })

            # Also apply percentage format to Delta columns (columns E, I, M = 4, 8, 12)
            # For all KPI rows (rows 4-15, 0-indexed: 3-14)
            delta_cols = [4, 8, 12]  # 0-indexed: E=4, I=8, M=12
            for delta_col in delta_cols:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 3,
                            "endRowIndex": 16,
                            "startColumnIndex": delta_col,
                            "endColumnIndex": delta_col + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "PERCENT",
                                    "pattern": "0.00%",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                })

        # Apply percentage formatting to By Country sheet
        if sheet_title == "By Country":
            # Apply percentage format to all Delta columns (every 3rd column starting from D)
            # and to percentage KPI rows
            # For By Country, columns are: A(metric), then B,C,D for each MP (Prev, This, Delta)
            # Delta columns are: D, G, J, M, P, S, V (indices 3, 6, 9, 12, 15, 18, 21) and total: Y (24)
            delta_col_indices = [3, 6, 9, 12, 15, 18, 21, 24]
            for delta_col in delta_col_indices:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 5,  # Start after headers
                            "endRowIndex": 500,  # Large enough for all rows
                            "startColumnIndex": delta_col,
                            "endColumnIndex": delta_col + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "PERCENT",
                                    "pattern": "0.00%",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                })

    # Execute batch update
    if requests:
        try:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            ).execute()
            logger.info("Formatting applied successfully")
        except Exception as e:
            logger.warning("Error applying formatting", error=str(e))


def create_number_format(
    kpi_name: str,
    marketplace: Marketplace | None = None,
) -> dict[str, Any]:
    """
    Create Google Sheets number format for a KPI.

    Args:
        kpi_name: Name of the KPI
        marketplace: Marketplace for currency format

    Returns:
        Number format dictionary for Sheets API
    """
    if kpi_name in CURRENCY_KPIS:
        symbol = CURRENCY_SYMBOLS.get(marketplace, "$") if marketplace else "$"
        return {
            "type": "CURRENCY",
            "pattern": f'"{symbol}"#,##0.00',
        }
    elif kpi_name in PERCENTAGE_KPIS:
        return {
            "type": "PERCENT",
            "pattern": "0.0%",
        }
    elif kpi_name in INTEGER_KPIS:
        return {
            "type": "NUMBER",
            "pattern": "#,##0",
        }
    else:
        return {
            "type": "NUMBER",
            "pattern": "#,##0.00",
        }
