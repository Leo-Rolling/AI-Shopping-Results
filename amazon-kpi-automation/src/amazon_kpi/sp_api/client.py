"""Factory for creating configured SP-API client instances."""

from __future__ import annotations

import structlog
from sp_api.api import DataKiosk, Reports
from sp_api.base import Marketplaces as SPMarketplaces

from ..config.constants import (
    Marketplace,
    SellerAccount,
    MARKETPLACE_ACCOUNT,
)
from ..secrets.secret_manager import SPAPICredentials, get_sp_api_credentials

logger = structlog.get_logger(__name__)

# Mapping from our Marketplace enum to sp-api library Marketplaces enum
_MARKETPLACE_TO_SP: dict[Marketplace, SPMarketplaces] = {
    Marketplace.US: SPMarketplaces.US,
    Marketplace.CA: SPMarketplaces.CA,
    Marketplace.UK: SPMarketplaces.GB,
    Marketplace.DE: SPMarketplaces.DE,
    Marketplace.IT: SPMarketplaces.IT,
    Marketplace.FR: SPMarketplaces.FR,
    Marketplace.ES: SPMarketplaces.ES,
}


class SPAPIClientFactory:
    """Creates SP-API client instances with correct credentials per account.

    Credentials are cached per SellerAccount (EU_UK shares one refresh token,
    NA shares another). Client instances are created fresh per marketplace.
    """

    def __init__(self) -> None:
        self._credentials_cache: dict[SellerAccount, SPAPICredentials] = {}

    def _get_credentials(self, account: SellerAccount) -> SPAPICredentials:
        """Get cached credentials for an account."""
        if account not in self._credentials_cache:
            secret_name = account.value.lower().replace("_", "-")
            self._credentials_cache[account] = get_sp_api_credentials(secret_name)
            logger.info("Loaded SP-API credentials", account=account.value)
        return self._credentials_cache[account]

    def _build_credentials_dict(self, creds: SPAPICredentials) -> dict[str, str]:
        """Convert SPAPICredentials to sp-api library format."""
        d: dict[str, str] = {
            "refresh_token": creds.refresh_token,
            "lwa_app_id": creds.lwa_app_id,
            "lwa_client_secret": creds.lwa_client_secret,
            "aws_access_key": creds.aws_access_key,
            "aws_secret_key": creds.aws_secret_key,
        }
        if creds.role_arn:
            d["role_arn"] = creds.role_arn
        return d

    def _get_sp_marketplace(self, marketplace: Marketplace) -> SPMarketplaces:
        """Get the sp-api library marketplace enum value."""
        sp_mp = _MARKETPLACE_TO_SP.get(marketplace)
        if sp_mp is None:
            raise ValueError(f"Unsupported marketplace for SP-API: {marketplace.value}")
        return sp_mp

    def create_data_kiosk(self, marketplace: Marketplace) -> DataKiosk:
        """Create a DataKiosk client for a specific marketplace."""
        account = MARKETPLACE_ACCOUNT[marketplace]
        creds = self._get_credentials(account)
        sp_marketplace = self._get_sp_marketplace(marketplace)

        logger.info(
            "Creating DataKiosk client",
            marketplace=marketplace.value,
            account=account.value,
        )

        return DataKiosk(
            marketplace=sp_marketplace,
            credentials=self._build_credentials_dict(creds),
        )

    def create_reports(self, marketplace: Marketplace) -> Reports:
        """Create a Reports client for a specific marketplace."""
        account = MARKETPLACE_ACCOUNT[marketplace]
        creds = self._get_credentials(account)
        sp_marketplace = self._get_sp_marketplace(marketplace)

        logger.info(
            "Creating Reports client",
            marketplace=marketplace.value,
            account=account.value,
        )

        return Reports(
            marketplace=sp_marketplace,
            credentials=self._build_credentials_dict(creds),
        )
