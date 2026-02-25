"""Google Sheets API client for report generation."""

from datetime import date
from typing import Any

import structlog
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config.constants import Marketplace, Region
from ..config.sku_categories import CATEGORIES
from ..processing.models import WeeklyReport
from ..secrets.secret_manager import get_google_service_account, get_drive_folder_id
from ..utils.exceptions import SheetsError, SheetCreationError, SheetUpdateError
from ..utils.retry import with_retry

from .templates import KPISummaryTemplate, ByCountryTemplate
from .formatters import apply_sheet_formatting

logger = structlog.get_logger(__name__)

# Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsClient:
    """Client for creating and updating Google Sheets reports."""

    def __init__(self, credentials_json: dict[str, Any] | None = None):
        """
        Initialize Google Sheets client.

        Args:
            credentials_json: Service account credentials (fetched from Secret Manager if None)
        """
        self._credentials_json = credentials_json
        self._credentials: Credentials | None = None
        self._gspread_client: gspread.Client | None = None
        self._drive_service = None
        self._sheets_service = None

    def _initialize(self) -> None:
        """Initialize API clients."""
        if self._gspread_client is not None:
            return

        logger.info("Initializing Google API clients")

        # Get credentials
        if not self._credentials_json:
            service_account = get_google_service_account()
            self._credentials_json = service_account.credentials_json

        self._credentials = Credentials.from_service_account_info(
            self._credentials_json,
            scopes=SCOPES,
        )

        # Initialize gspread client
        self._gspread_client = gspread.authorize(self._credentials)

        # Initialize Drive and Sheets services for advanced operations
        self._drive_service = build("drive", "v3", credentials=self._credentials)
        self._sheets_service = build("sheets", "v4", credentials=self._credentials)

        logger.info("Google API clients initialized")

    @with_retry(max_attempts=3, retry_on=(SheetsError,))
    def create_report(
        self,
        report: WeeklyReport,
        folder_id: str | None = None,
    ) -> str:
        """
        Create a new Google Sheets report from KPI data.

        Args:
            report: WeeklyReport with KPI data
            folder_id: Google Drive folder ID (fetched from secrets if None)

        Returns:
            URL of the created spreadsheet

        Raises:
            SheetCreationError: If creation fails
        """
        self._initialize()

        if not folder_id:
            folder_id = get_drive_folder_id()

        # Generate filename: AMZ_Meeting_KPIs DD Month YYYY.xlsx
        filename = self._generate_filename(report.week_end)

        logger.info("Creating report", filename=filename, folder_id=folder_id)

        try:
            # Create spreadsheet directly in target folder using Drive API
            # Using supportsAllDrives=True for Shared Drive support
            file_metadata = {
                "name": filename,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [folder_id],
            }
            file = self._drive_service.files().create(
                body=file_metadata,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            spreadsheet_id = file.get("id")

            # Open with gspread for easier manipulation
            spreadsheet = self._gspread_client.open_by_key(spreadsheet_id)

            # Build and populate sheets
            self._build_kpi_summary_sheet(spreadsheet, report)
            self._build_by_country_sheet(spreadsheet, report)

            # Remove default "Sheet1" if it exists
            try:
                default_sheet = spreadsheet.worksheet("Sheet1")
                spreadsheet.del_worksheet(default_sheet)
            except gspread.exceptions.WorksheetNotFound:
                pass

            # Apply formatting
            apply_sheet_formatting(self._sheets_service, spreadsheet_id)

            logger.info(
                "Report created successfully",
                url=spreadsheet.url,
                spreadsheet_id=spreadsheet_id,
            )

            return spreadsheet.url

        except HttpError as e:
            raise SheetCreationError(
                f"Failed to create spreadsheet: {str(e)}",
                sheet_name=filename,
                details={"error": str(e)},
            ) from e
        except Exception as e:
            raise SheetCreationError(
                f"Unexpected error creating spreadsheet: {str(e)}",
                sheet_name=filename,
                details={"error_type": type(e).__name__},
            ) from e

    def _generate_filename(self, week_end: date) -> str:
        """Generate filename for the report."""
        return f"AMZ_Meeting_KPIs {week_end.strftime('%d %B %Y')}"

    def _move_to_folder(self, file_id: str, folder_id: str) -> None:
        """Move a file to a specific Drive folder."""
        try:
            # Get current parents
            file = self._drive_service.files().get(
                fileId=file_id,
                fields="parents",
            ).execute()

            previous_parents = ",".join(file.get("parents", []))

            # Move to new folder
            self._drive_service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            ).execute()

            logger.debug("Moved file to folder", file_id=file_id, folder_id=folder_id)

        except HttpError as e:
            logger.warning("Could not move file to folder", error=str(e))

    def _build_kpi_summary_sheet(
        self,
        spreadsheet: gspread.Spreadsheet,
        report: WeeklyReport,
    ) -> None:
        """Build the KPIs summary sheet."""
        logger.info("Building KPIs summary sheet")

        template = KPISummaryTemplate()
        data = template.build(report)

        # Create or get worksheet
        try:
            worksheet = spreadsheet.worksheet("KPIs")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title="KPIs",
                rows=len(data) + 10,
                cols=20,
            )

        # Write data
        if data:
            worksheet.update(
                range_name="A1",
                values=data,
                value_input_option="USER_ENTERED",
            )

        logger.info("KPIs summary sheet built", rows=len(data))

    def _build_by_country_sheet(
        self,
        spreadsheet: gspread.Spreadsheet,
        report: WeeklyReport,
    ) -> None:
        """Build the By Country breakdown sheet."""
        logger.info("Building By Country sheet")

        template = ByCountryTemplate()
        data = template.build(report)

        # Create worksheet (7 marketplaces * 3 columns + 3 total columns + 1 metric = 25 columns minimum)
        worksheet = spreadsheet.add_worksheet(
            title="By Country",
            rows=len(data) + 50,  # Extra rows for multiple category sections
            cols=30,
        )

        # Write data
        if data:
            worksheet.update(
                range_name="A1",
                values=data,
                value_input_option="USER_ENTERED",
            )

        logger.info("By Country sheet built", rows=len(data))

    @with_retry(max_attempts=3, retry_on=(SheetsError,))
    def update_sheet(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        """
        Update a range in an existing spreadsheet.

        Args:
            spreadsheet_id: ID of the spreadsheet
            range_name: A1 notation range (e.g., "Sheet1!A1:B10")
            values: 2D list of values to write

        Raises:
            SheetUpdateError: If update fails
        """
        self._initialize()

        try:
            spreadsheet = self._gspread_client.open_by_key(spreadsheet_id)
            worksheet_name = range_name.split("!")[0] if "!" in range_name else "Sheet1"
            cell_range = range_name.split("!")[-1]

            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.update(
                range_name=cell_range,
                values=values,
                value_input_option="USER_ENTERED",
            )

            logger.info(
                "Sheet updated",
                spreadsheet_id=spreadsheet_id,
                range=range_name,
                rows=len(values),
            )

        except Exception as e:
            raise SheetUpdateError(
                f"Failed to update sheet: {str(e)}",
                sheet_id=spreadsheet_id,
                range_name=range_name,
            ) from e


def create_kpi_report(
    report: WeeklyReport,
    folder_id: str | None = None,
) -> str:
    """
    Convenience function to create a KPI report.

    Args:
        report: WeeklyReport with KPI data
        folder_id: Google Drive folder ID

    Returns:
        URL of the created spreadsheet
    """
    client = GoogleSheetsClient()
    return client.create_report(report, folder_id)
