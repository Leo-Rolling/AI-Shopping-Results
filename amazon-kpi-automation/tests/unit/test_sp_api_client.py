"""Tests for SPAPIClientFactory."""

from unittest.mock import MagicMock, patch

import pytest

from amazon_kpi.config.constants import Marketplace, SellerAccount
from amazon_kpi.secrets.secret_manager import SPAPICredentials
from amazon_kpi.sp_api.client import SPAPIClientFactory


@pytest.fixture
def mock_credentials():
    """Sample SP-API credentials."""
    return SPAPICredentials(
        refresh_token="Atzr|test_token",
        lwa_app_id="amzn1.application-oa2-client.test",
        lwa_client_secret="amzn1.oa2-cs.v1.test",
        aws_access_key="AKIATEST123",
        aws_secret_key="test_secret_key",
        role_arn="arn:aws:iam::123456789:role/test-role",
    )


class TestSPAPIClientFactory:
    """Tests for the client factory."""

    @patch("amazon_kpi.sp_api.client.get_sp_api_credentials")
    @patch("amazon_kpi.sp_api.client.DataKiosk")
    def test_create_data_kiosk_us(self, mock_dk_class, mock_get_creds, mock_credentials):
        """Creating a DataKiosk client for US uses NA credentials."""
        mock_get_creds.return_value = mock_credentials

        factory = SPAPIClientFactory()
        client = factory.create_data_kiosk(Marketplace.US)

        mock_get_creds.assert_called_once_with("na")
        mock_dk_class.assert_called_once()

        call_kwargs = mock_dk_class.call_args
        creds_dict = call_kwargs.kwargs["credentials"]
        assert creds_dict["refresh_token"] == "Atzr|test_token"
        assert creds_dict["lwa_app_id"] == "amzn1.application-oa2-client.test"

    @patch("amazon_kpi.sp_api.client.get_sp_api_credentials")
    @patch("amazon_kpi.sp_api.client.DataKiosk")
    def test_create_data_kiosk_de(self, mock_dk_class, mock_get_creds, mock_credentials):
        """Creating a DataKiosk client for DE uses EU-UK credentials."""
        mock_get_creds.return_value = mock_credentials

        factory = SPAPIClientFactory()
        factory.create_data_kiosk(Marketplace.DE)

        mock_get_creds.assert_called_once_with("eu-uk")

    @patch("amazon_kpi.sp_api.client.get_sp_api_credentials")
    @patch("amazon_kpi.sp_api.client.DataKiosk")
    def test_credentials_are_cached(self, mock_dk_class, mock_get_creds, mock_credentials):
        """Credentials are fetched once per account and cached."""
        mock_get_creds.return_value = mock_credentials

        factory = SPAPIClientFactory()
        factory.create_data_kiosk(Marketplace.US)
        factory.create_data_kiosk(Marketplace.CA)

        # Both US and CA use NA account — credentials fetched only once
        assert mock_get_creds.call_count == 1

    @patch("amazon_kpi.sp_api.client.get_sp_api_credentials")
    @patch("amazon_kpi.sp_api.client.DataKiosk")
    def test_different_accounts_fetch_separately(self, mock_dk_class, mock_get_creds, mock_credentials):
        """EU and NA accounts fetch credentials separately."""
        mock_get_creds.return_value = mock_credentials

        factory = SPAPIClientFactory()
        factory.create_data_kiosk(Marketplace.US)
        factory.create_data_kiosk(Marketplace.UK)

        assert mock_get_creds.call_count == 2
        mock_get_creds.assert_any_call("na")
        mock_get_creds.assert_any_call("eu-uk")

    @patch("amazon_kpi.sp_api.client.get_sp_api_credentials")
    @patch("amazon_kpi.sp_api.client.Reports")
    def test_create_reports(self, mock_reports_class, mock_get_creds, mock_credentials):
        """Creating a Reports client works correctly."""
        mock_get_creds.return_value = mock_credentials

        factory = SPAPIClientFactory()
        factory.create_reports(Marketplace.UK)

        mock_get_creds.assert_called_once_with("eu-uk")
        mock_reports_class.assert_called_once()

    @patch("amazon_kpi.sp_api.client.get_sp_api_credentials")
    @patch("amazon_kpi.sp_api.client.DataKiosk")
    def test_credentials_without_role_arn(self, mock_dk_class, mock_get_creds):
        """Credentials without role_arn omit it from the dict."""
        creds = SPAPICredentials(
            refresh_token="Atzr|test",
            lwa_app_id="amzn1.test",
            lwa_client_secret="amzn1.secret",
            aws_access_key="AKIA",
            aws_secret_key="secret",
            role_arn=None,
        )
        mock_get_creds.return_value = creds

        factory = SPAPIClientFactory()
        factory.create_data_kiosk(Marketplace.US)

        creds_dict = mock_dk_class.call_args.kwargs["credentials"]
        assert "role_arn" not in creds_dict
