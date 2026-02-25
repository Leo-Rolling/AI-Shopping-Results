"""SP-API Reports service — create, poll, and download standard reports."""

from __future__ import annotations

import gzip
import json
import time
from typing import Any

import requests
import structlog

from ..config.constants import (
    MARKETPLACE_SP_API_IDS,
    Marketplace,
)
from ..utils.exceptions import ReportError, ReportTimeoutError, SPAPIError
from ..utils.retry import with_retry
from .client import SPAPIClientFactory

logger = structlog.get_logger(__name__)

# Polling configuration for Reports API
_REPORT_POLL_INTERVAL = 30  # seconds
_REPORT_MAX_POLL_ATTEMPTS = 40  # ~20 minutes


class ReportsService:
    """Service for creating and downloading SP-API reports.

    This handles the standard Reports API workflow:
      1. Create report  (POST /reports/2021-06-30/reports)
      2. Poll status    (GET  /reports/2021-06-30/reports/{reportId})
      3. Download doc   (GET  /reports/2021-06-30/documents/{reportDocumentId})
    """

    def __init__(self, client_factory: SPAPIClientFactory) -> None:
        self._factory = client_factory

    def get_sales_and_traffic_report(
        self,
        marketplace: Marketplace,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Get the Sales and Traffic Business Report.

        Args:
            marketplace: Target marketplace.
            start_date: Start date in ISO format (YYYY-MM-DD).
            end_date: End date in ISO format (YYYY-MM-DD).

        Returns:
            Parsed report data as list of records.
        """
        marketplace_id = MARKETPLACE_SP_API_IDS[marketplace]

        return self._create_and_download_report(
            marketplace=marketplace,
            report_type="GET_SALES_AND_TRAFFIC_REPORT",
            start_date=f"{start_date}T00:00:00Z",
            end_date=f"{end_date}T23:59:59Z",
            marketplace_ids=[marketplace_id],
        )

    def get_search_terms_report(
        self,
        marketplace: Marketplace,
        start_date: str,
        end_date: str,
        report_period: str = "WEEK",
    ) -> list[dict[str, Any]]:
        """Get Brand Analytics Search Terms Report.

        Args:
            marketplace: Target marketplace.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            report_period: Aggregation period (DAY, WEEK, MONTH, QUARTER).

        Returns:
            Parsed report data.
        """
        marketplace_id = MARKETPLACE_SP_API_IDS[marketplace]

        return self._create_and_download_report(
            marketplace=marketplace,
            report_type="GET_BRAND_ANALYTICS_SEARCH_TERMS_REPORT",
            start_date=f"{start_date}T00:00:00Z",
            end_date=f"{end_date}T23:59:59Z",
            marketplace_ids=[marketplace_id],
            report_options={"reportPeriod": report_period},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_and_download_report(
        self,
        marketplace: Marketplace,
        report_type: str,
        start_date: str,
        end_date: str,
        marketplace_ids: list[str],
        report_options: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Full lifecycle: create → poll → download a report."""
        client = self._factory.create_reports(marketplace)

        # Step 1: Create
        report_id = self._create_report(
            client, report_type, start_date, end_date,
            marketplace_ids, report_options, marketplace,
        )

        # Step 2: Poll
        document_id = self._poll_report(client, report_id, marketplace)

        # Step 3: Download
        return self._download_report(client, document_id, marketplace)

    @with_retry(max_attempts=3, retry_on=(SPAPIError, Exception))
    def _create_report(
        self,
        client: Any,
        report_type: str,
        start_date: str,
        end_date: str,
        marketplace_ids: list[str],
        report_options: dict[str, str] | None,
        marketplace: Marketplace,
    ) -> str:
        """Create a report request."""
        logger.info(
            "Creating report",
            report_type=report_type,
            marketplace=marketplace.value,
            start_date=start_date,
            end_date=end_date,
        )

        kwargs: dict[str, Any] = {
            "reportType": report_type,
            "dataStartTime": start_date,
            "dataEndTime": end_date,
            "marketplaceIds": marketplace_ids,
        }
        if report_options:
            kwargs["reportOptions"] = report_options

        response = client.create_report(**kwargs)
        report_id = response.payload.get("reportId")

        if not report_id:
            raise ReportError(
                "No reportId returned from create_report",
                marketplace=marketplace.value,
            )

        logger.info(
            "Report created",
            report_id=report_id,
            marketplace=marketplace.value,
        )
        return report_id

    def _poll_report(
        self,
        client: Any,
        report_id: str,
        marketplace: Marketplace,
    ) -> str:
        """Poll until report is DONE."""
        for attempt in range(1, _REPORT_MAX_POLL_ATTEMPTS + 1):
            response = client.get_report(report_id=report_id)
            status = response.payload.get("processingStatus")

            logger.info(
                "Report status",
                report_id=report_id,
                status=status,
                attempt=attempt,
                marketplace=marketplace.value,
            )

            if status == "DONE":
                doc_id = response.payload.get("reportDocumentId")
                if not doc_id:
                    raise ReportError(
                        "Report DONE but no reportDocumentId",
                        report_id=report_id,
                        marketplace=marketplace.value,
                    )
                return doc_id

            if status in ("CANCELLED", "FATAL"):
                raise ReportError(
                    f"Report failed with status: {status}",
                    report_id=report_id,
                    marketplace=marketplace.value,
                )

            time.sleep(_REPORT_POLL_INTERVAL)

        raise ReportTimeoutError(
            f"Report timed out after {_REPORT_MAX_POLL_ATTEMPTS * _REPORT_POLL_INTERVAL}s",
            report_id=report_id,
            marketplace=marketplace.value,
        )

    @with_retry(max_attempts=3, retry_on=(SPAPIError, Exception))
    def _download_report(
        self,
        client: Any,
        document_id: str,
        marketplace: Marketplace,
    ) -> list[dict[str, Any]]:
        """Download and parse a report document."""
        logger.info(
            "Downloading report document",
            document_id=document_id,
            marketplace=marketplace.value,
        )

        response = client.get_report_document(document_id=document_id)
        document_url = response.payload.get("url")

        if not document_url:
            raise ReportError(
                "No url in get_report_document response",
                marketplace=marketplace.value,
                details={"document_id": document_id},
            )

        # Download
        doc_response = requests.get(document_url, timeout=120)
        doc_response.raise_for_status()
        content_bytes = doc_response.content

        # Handle compression
        compression = response.payload.get("compressionAlgorithm")
        if compression == "GZIP":
            content_bytes = gzip.decompress(content_bytes)

        content = content_bytes.decode("utf-8")

        # Reports can be JSON or TSV depending on type
        # Try JSON first, fall back to raw content
        try:
            data = json.loads(content)
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                # Some reports wrap data in a key
                for key in ("salesAndTrafficByAsin", "salesAndTrafficByDate", "reportData"):
                    if key in data:
                        records = data[key] if isinstance(data[key], list) else [data[key]]
                        break
                else:
                    records = [data]
        except json.JSONDecodeError:
            # TSV format — parse line by line
            lines = content.strip().split("\n")
            if len(lines) < 2:
                return []
            headers = lines[0].split("\t")
            records = []
            for line in lines[1:]:
                values = line.split("\t")
                records.append(dict(zip(headers, values)))

        logger.info(
            "Report downloaded and parsed",
            document_id=document_id,
            record_count=len(records),
            marketplace=marketplace.value,
        )
        return records
