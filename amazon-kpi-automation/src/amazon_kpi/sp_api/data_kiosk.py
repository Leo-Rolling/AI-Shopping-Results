"""Data Kiosk API service — submit query, poll for completion, download results."""

from __future__ import annotations

import gzip
import json
import time
from io import BytesIO
from typing import Any

import requests
import structlog

from ..config.constants import (
    DATA_KIOSK_MAX_POLL_ATTEMPTS,
    DATA_KIOSK_POLL_INTERVAL_SECONDS,
    Marketplace,
)
from ..utils.exceptions import DataKioskError, DataKioskTimeoutError, SPAPIError
from ..utils.retry import with_retry
from .client import SPAPIClientFactory

logger = structlog.get_logger(__name__)


class DataKioskService:
    """Service for submitting and retrieving Data Kiosk queries.

    The Data Kiosk workflow is:
      1. Submit a GraphQL query  (POST /dataKiosk/2023-11-15/queries)
      2. Poll until status is DONE (GET  /dataKiosk/2023-11-15/queries/{queryId})
      3. Download the JSONL document (GET  /dataKiosk/2023-11-15/documents/{documentId})
    """

    def __init__(self, client_factory: SPAPIClientFactory) -> None:
        self._factory = client_factory

    def execute_query(
        self,
        marketplace: Marketplace,
        query: str,
        *,
        poll_interval: int = DATA_KIOSK_POLL_INTERVAL_SECONDS,
        max_attempts: int = DATA_KIOSK_MAX_POLL_ATTEMPTS,
    ) -> list[dict[str, Any]]:
        """Execute a Data Kiosk query end-to-end.

        Args:
            marketplace: Target marketplace.
            query: GraphQL query string.
            poll_interval: Seconds between status polls.
            max_attempts: Maximum number of poll attempts before timeout.

        Returns:
            List of parsed JSONL records from the result document.

        Raises:
            DataKioskError: If the query fails.
            DataKioskTimeoutError: If the query doesn't complete in time.
        """
        client = self._factory.create_data_kiosk(marketplace)

        # Step 1: Submit
        query_id = self._submit_query(client, query, marketplace)

        # Step 2: Poll
        document_id = self._poll_until_done(
            client, query_id, marketplace, poll_interval, max_attempts
        )

        if document_id is None:
            logger.info(
                "Query completed with no data",
                query_id=query_id,
                marketplace=marketplace.value,
            )
            return []

        # Step 3: Download
        return self._download_document(client, document_id, marketplace)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @with_retry(
        max_attempts=3,
        retry_on=(SPAPIError, Exception),
    )
    def _submit_query(self, client: Any, query: str, marketplace: Marketplace) -> str:
        """Submit a GraphQL query to Data Kiosk."""
        logger.info("Submitting Data Kiosk query", marketplace=marketplace.value)

        response = client.create_query(query=query)
        query_id = response.payload.get("queryId")

        if not query_id:
            raise DataKioskError(
                "No queryId returned from create_query",
                marketplace=marketplace.value,
            )

        logger.info(
            "Query submitted successfully",
            query_id=query_id,
            marketplace=marketplace.value,
        )
        return query_id

    def _poll_until_done(
        self,
        client: Any,
        query_id: str,
        marketplace: Marketplace,
        poll_interval: int,
        max_attempts: int,
    ) -> str | None:
        """Poll query status until DONE, FATAL, or CANCELLED.

        Returns:
            The dataDocumentId if data is available, or None if the query
            completed successfully but produced no results.
        """
        for attempt in range(1, max_attempts + 1):
            response = client.get_query(query_id=query_id)
            status = response.payload.get("processingStatus")

            logger.info(
                "Query status",
                query_id=query_id,
                status=status,
                attempt=attempt,
                marketplace=marketplace.value,
            )

            if status == "DONE":
                return response.payload.get("dataDocumentId")

            if status == "FATAL":
                error_doc_id = response.payload.get("errorDocumentId")
                raise DataKioskError(
                    "Query failed with FATAL status",
                    query_id=query_id,
                    marketplace=marketplace.value,
                    details={"errorDocumentId": error_doc_id},
                )

            if status == "CANCELLED":
                raise DataKioskError(
                    "Query was cancelled",
                    query_id=query_id,
                    marketplace=marketplace.value,
                )

            # Still IN_QUEUE or IN_PROGRESS — wait and retry
            time.sleep(poll_interval)

        raise DataKioskTimeoutError(
            f"Query timed out after {max_attempts * poll_interval}s",
            query_id=query_id,
            marketplace=marketplace.value,
        )

    @with_retry(
        max_attempts=3,
        retry_on=(SPAPIError, Exception),
    )
    def _download_document(
        self,
        client: Any,
        document_id: str,
        marketplace: Marketplace,
    ) -> list[dict[str, Any]]:
        """Download and parse a Data Kiosk document (JSONL, possibly gzipped)."""
        logger.info(
            "Downloading document",
            document_id=document_id,
            marketplace=marketplace.value,
        )

        response = client.get_document(document_id=document_id)
        document_url = response.payload.get("documentUrl")

        if not document_url:
            raise DataKioskError(
                "No documentUrl in get_document response",
                marketplace=marketplace.value,
                details={"document_id": document_id},
            )

        # Download the actual document content
        doc_response = requests.get(document_url, timeout=120)
        doc_response.raise_for_status()
        content_bytes = doc_response.content

        # Check if gzipped
        compression = response.payload.get("compressionAlgorithm")
        if compression == "GZIP":
            content_bytes = gzip.decompress(content_bytes)

        content = content_bytes.decode("utf-8")

        # Parse JSONL (one JSON object per line)
        records: list[dict[str, Any]] = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if line:
                records.append(json.loads(line))

        logger.info(
            "Document downloaded and parsed",
            document_id=document_id,
            record_count=len(records),
            marketplace=marketplace.value,
        )
        return records
