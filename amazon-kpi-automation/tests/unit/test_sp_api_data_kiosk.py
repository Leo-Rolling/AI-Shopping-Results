"""Tests for DataKioskService."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from amazon_kpi.config.constants import Marketplace
from amazon_kpi.sp_api.data_kiosk import DataKioskService
from amazon_kpi.utils.exceptions import DataKioskError, DataKioskTimeoutError


class MockPayload:
    """Mock SP-API response with payload dict."""

    def __init__(self, payload: dict):
        self.payload = payload


@pytest.fixture
def mock_factory():
    """Mock SPAPIClientFactory."""
    factory = MagicMock()
    return factory


@pytest.fixture
def service(mock_factory):
    """DataKioskService with mocked factory."""
    return DataKioskService(mock_factory)


class TestSubmitQuery:
    """Tests for query submission."""

    def test_submit_returns_query_id(self, service, mock_factory):
        """Successful submission returns query ID."""
        mock_client = MagicMock()
        mock_client.create_query.return_value = MockPayload({"queryId": "q-123"})
        mock_factory.create_data_kiosk.return_value = mock_client

        query_id = service._submit_query(mock_client, "query {}", Marketplace.US)
        assert query_id == "q-123"

    def test_submit_raises_on_missing_query_id(self, service, mock_factory):
        """Missing queryId raises DataKioskError."""
        mock_client = MagicMock()
        mock_client.create_query.return_value = MockPayload({})

        with pytest.raises(DataKioskError, match="No queryId"):
            service._submit_query(mock_client, "query {}", Marketplace.US)


class TestPollUntilDone:
    """Tests for status polling."""

    def test_returns_document_id_on_done(self, service):
        """DONE status returns the dataDocumentId."""
        mock_client = MagicMock()
        mock_client.get_query.return_value = MockPayload({
            "processingStatus": "DONE",
            "dataDocumentId": "doc-456",
        })

        doc_id = service._poll_until_done(
            mock_client, "q-123", Marketplace.US, poll_interval=0, max_attempts=1,
        )
        assert doc_id == "doc-456"

    def test_returns_none_when_done_without_data(self, service):
        """DONE status without dataDocumentId returns None."""
        mock_client = MagicMock()
        mock_client.get_query.return_value = MockPayload({
            "processingStatus": "DONE",
        })

        doc_id = service._poll_until_done(
            mock_client, "q-123", Marketplace.US, poll_interval=0, max_attempts=1,
        )
        assert doc_id is None

    def test_raises_on_fatal(self, service):
        """FATAL status raises DataKioskError."""
        mock_client = MagicMock()
        mock_client.get_query.return_value = MockPayload({
            "processingStatus": "FATAL",
            "errorDocumentId": "err-789",
        })

        with pytest.raises(DataKioskError, match="FATAL"):
            service._poll_until_done(
                mock_client, "q-123", Marketplace.US, poll_interval=0, max_attempts=1,
            )

    def test_raises_on_cancelled(self, service):
        """CANCELLED status raises DataKioskError."""
        mock_client = MagicMock()
        mock_client.get_query.return_value = MockPayload({
            "processingStatus": "CANCELLED",
        })

        with pytest.raises(DataKioskError, match="cancelled"):
            service._poll_until_done(
                mock_client, "q-123", Marketplace.US, poll_interval=0, max_attempts=1,
            )

    def test_timeout_after_max_attempts(self, service):
        """Exceeding max attempts raises DataKioskTimeoutError."""
        mock_client = MagicMock()
        mock_client.get_query.return_value = MockPayload({
            "processingStatus": "IN_PROGRESS",
        })

        with pytest.raises(DataKioskTimeoutError, match="timed out"):
            service._poll_until_done(
                mock_client, "q-123", Marketplace.US, poll_interval=0, max_attempts=2,
            )

        # Should have polled exactly max_attempts times
        assert mock_client.get_query.call_count == 2

    def test_polls_until_done(self, service):
        """Polls through IN_PROGRESS states until DONE."""
        mock_client = MagicMock()
        mock_client.get_query.side_effect = [
            MockPayload({"processingStatus": "IN_QUEUE"}),
            MockPayload({"processingStatus": "IN_PROGRESS"}),
            MockPayload({"processingStatus": "DONE", "dataDocumentId": "doc-999"}),
        ]

        doc_id = service._poll_until_done(
            mock_client, "q-123", Marketplace.US, poll_interval=0, max_attempts=5,
        )
        assert doc_id == "doc-999"
        assert mock_client.get_query.call_count == 3


class TestExecuteQuery:
    """Tests for the full execute_query flow."""

    @patch("amazon_kpi.sp_api.data_kiosk.requests")
    def test_full_flow(self, mock_requests, service, mock_factory):
        """Full flow: submit → poll → download."""
        mock_client = MagicMock()
        mock_factory.create_data_kiosk.return_value = mock_client

        # Submit returns query ID
        mock_client.create_query.return_value = MockPayload({"queryId": "q-100"})

        # Poll returns DONE with document ID
        mock_client.get_query.return_value = MockPayload({
            "processingStatus": "DONE",
            "dataDocumentId": "doc-200",
        })

        # Get document returns URL
        mock_client.get_document.return_value = MockPayload({
            "documentUrl": "https://example.com/doc",
        })

        # HTTP download returns JSONL content
        mock_response = MagicMock()
        mock_response.content = b'{"sku": "TRK-001", "sales": {"unitsOrdered": 5}}\n'
        mock_response.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_response

        records = service.execute_query(
            marketplace=Marketplace.US,
            query="query {}",
            poll_interval=0,
            max_attempts=1,
        )

        assert len(records) == 1
        assert records[0]["sku"] == "TRK-001"

    def test_returns_empty_when_no_document(self, service, mock_factory):
        """Returns empty list when query completes with no data."""
        mock_client = MagicMock()
        mock_factory.create_data_kiosk.return_value = mock_client

        mock_client.create_query.return_value = MockPayload({"queryId": "q-100"})
        mock_client.get_query.return_value = MockPayload({
            "processingStatus": "DONE",
            # No dataDocumentId
        })

        records = service.execute_query(
            marketplace=Marketplace.US,
            query="query {}",
            poll_interval=0,
            max_attempts=1,
        )

        assert records == []
