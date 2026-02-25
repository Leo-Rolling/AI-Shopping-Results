"""Test Google Drive access."""

import os
import sys

sys.path.insert(0, "/Users/leonardodol/Documents/VisualSTudioCode/AI Shopping/amazon-kpi-automation/src")
os.environ["GCP_PROJECT_ID"] = "sellerboard-amz-kpi"

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from amazon_kpi.secrets.secret_manager import get_google_service_account, get_drive_folder_id

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def test_drive():
    # Get credentials
    service_account = get_google_service_account()
    credentials = Credentials.from_service_account_info(
        service_account.credentials_json,
        scopes=SCOPES,
    )

    # Build Drive service
    drive_service = build("drive", "v3", credentials=credentials)

    # Get folder ID
    folder_id = get_drive_folder_id()
    print(f"Target folder ID: {folder_id}")

    # Try to create a simple Google Sheet directly in the folder
    print("\nTrying to create a spreadsheet in the folder...")
    try:
        file_metadata = {
            "name": "Test_Sheet_Delete_Me",
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [folder_id],
        }
        file = drive_service.files().create(
            body=file_metadata,
            fields="id, name, webViewLink",
            supportsAllDrives=True,  # Support shared drives
        ).execute()
        print(f"SUCCESS! Created: {file.get('name')}")
        print(f"ID: {file.get('id')}")
        print(f"Link: {file.get('webViewLink')}")

        # Delete the test file
        print("\nDeleting test file...")
        drive_service.files().delete(
            fileId=file.get('id'),
            supportsAllDrives=True,
        ).execute()
        print("Test file deleted")

    except Exception as e:
        print(f"Error creating file: {e}")
        print(f"\nError type: {type(e).__name__}")

if __name__ == "__main__":
    test_drive()
