"""Fetch reference file to see format."""

import os
import sys
import io

sys.path.insert(0, "/Users/leonardodol/Documents/VisualSTudioCode/AI Shopping/amazon-kpi-automation/src")
os.environ["GCP_PROJECT_ID"] = "sellerboard-amz-kpi"

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from amazon_kpi.secrets.secret_manager import get_google_service_account

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def fetch_reference():
    # Get credentials
    service_account = get_google_service_account()
    credentials = Credentials.from_service_account_info(
        service_account.credentials_json,
        scopes=SCOPES,
    )

    # Build Drive service
    drive_service = build("drive", "v3", credentials=credentials)

    # Reference file ID
    file_id = "1lITiRE1NaOWMUSKyOqJOrplCmyONy1mo"

    print(f"Getting file metadata: {file_id}")

    try:
        # Get file metadata
        file = drive_service.files().get(
            fileId=file_id,
            fields="id, name, mimeType",
            supportsAllDrives=True,
        ).execute()

        print(f"File name: {file.get('name')}")
        print(f"MIME type: {file.get('mimeType')}")

        # Download the file directly (it's an xlsx file)
        request = drive_service.files().get_media(fileId=file_id)
        content = io.BytesIO()
        downloader = MediaIoBaseDownload(content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")

        content.seek(0)

        # Read with pandas
        import pandas as pd
        excel_file = pd.ExcelFile(content)
        print(f"\nSheets: {excel_file.sheet_names}")

        for sheet_name in excel_file.sheet_names:
            print(f"\n{'='*60}")
            print(f"=== Sheet: {sheet_name} ===")
            print(f"{'='*60}")
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            print(f"Shape: {df.shape}")
            # Print all rows for reference
            pd.set_option('display.max_rows', None)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            print(df.to_string())

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fetch_reference()
