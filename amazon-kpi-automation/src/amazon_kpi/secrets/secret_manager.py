"""Google Cloud Secret Manager client for secure credential access."""

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import structlog

from ..utils.exceptions import SecretManagerError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SellerboardCredentials:
    """Sellerboard login credentials."""

    email: str
    password: str


@dataclass(frozen=True)
class GoogleServiceAccount:
    """Google service account credentials."""

    credentials_json: dict[str, Any]


@dataclass(frozen=True)
class SPAPICredentials:
    """Amazon SP-API credentials for a single seller account."""

    refresh_token: str
    lwa_app_id: str
    lwa_client_secret: str
    aws_access_key: str
    aws_secret_key: str
    role_arn: str | None = None


class SecretManagerClient:
    """Client for accessing secrets from GCP Secret Manager or environment."""

    def __init__(self, project_id: str | None = None):
        """
        Initialize Secret Manager client.

        Args:
            project_id: GCP project ID. If None, attempts to detect from environment.
        """
        self._project_id = project_id or os.environ.get("GCP_PROJECT_ID")
        self._client = None
        self._use_env_fallback = os.environ.get("USE_ENV_SECRETS", "false").lower() == "true"

        if not self._use_env_fallback:
            try:
                from google.cloud import secretmanager

                self._client = secretmanager.SecretManagerServiceClient()
                logger.info("Initialized GCP Secret Manager client")
            except ImportError:
                logger.warning(
                    "google-cloud-secret-manager not installed, using environment fallback"
                )
                self._use_env_fallback = True
            except Exception as e:
                logger.warning(
                    "Failed to initialize Secret Manager client, using environment fallback",
                    error=str(e),
                )
                self._use_env_fallback = True

    def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """
        Retrieve a secret value.

        Args:
            secret_name: Name of the secret in Secret Manager
            version: Version of the secret (default: "latest")

        Returns:
            The secret value as a string

        Raises:
            SecretManagerError: If secret retrieval fails
        """
        if self._use_env_fallback:
            return self._get_from_environment(secret_name)

        return self._get_from_secret_manager(secret_name, version)

    def _get_from_environment(self, secret_name: str) -> str:
        """Get secret from environment variable."""
        # Convert secret name to environment variable format
        # e.g., "sellerboard-credentials" -> "SELLERBOARD_CREDENTIALS"
        env_name = secret_name.upper().replace("-", "_")

        value = os.environ.get(env_name)
        if value is None:
            raise SecretManagerError(
                f"Secret not found in environment variable: {env_name}",
                secret_name=secret_name,
            )

        logger.debug("Retrieved secret from environment", secret_name=secret_name)
        return value

    def _get_from_secret_manager(self, secret_name: str, version: str) -> str:
        """Get secret from GCP Secret Manager."""
        if not self._project_id:
            raise SecretManagerError(
                "GCP project ID not configured",
                secret_name=secret_name,
                details={"hint": "Set GCP_PROJECT_ID environment variable"},
            )

        try:
            name = f"projects/{self._project_id}/secrets/{secret_name}/versions/{version}"
            response = self._client.access_secret_version(request={"name": name})
            value = response.payload.data.decode("UTF-8")

            logger.debug(
                "Retrieved secret from Secret Manager",
                secret_name=secret_name,
                version=version,
            )
            return value

        except Exception as e:
            raise SecretManagerError(
                f"Failed to retrieve secret: {secret_name}",
                secret_name=secret_name,
                details={"error": str(e)},
            ) from e

    def get_json_secret(self, secret_name: str, version: str = "latest") -> dict[str, Any]:
        """
        Retrieve and parse a JSON secret.

        Args:
            secret_name: Name of the secret
            version: Version of the secret

        Returns:
            Parsed JSON as dictionary

        Raises:
            SecretManagerError: If retrieval or parsing fails
        """
        value = self.get_secret(secret_name, version)

        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise SecretManagerError(
                f"Failed to parse secret as JSON: {secret_name}",
                secret_name=secret_name,
                details={"error": str(e)},
            ) from e

    def get_sellerboard_credentials(self) -> SellerboardCredentials:
        """
        Get Sellerboard login credentials.

        Returns:
            SellerboardCredentials with email and password

        Raises:
            SecretManagerError: If credentials are missing or invalid
        """
        data = self.get_json_secret("sellerboard-credentials")

        if "email" not in data or "password" not in data:
            raise SecretManagerError(
                "Invalid Sellerboard credentials format",
                secret_name="sellerboard-credentials",
                details={"hint": "Expected JSON with 'email' and 'password' keys"},
            )

        return SellerboardCredentials(email=data["email"], password=data["password"])

    def get_google_service_account(self) -> GoogleServiceAccount:
        """
        Get Google service account credentials.

        Returns:
            GoogleServiceAccount with credentials JSON

        Raises:
            SecretManagerError: If credentials are missing or invalid
        """
        data = self.get_json_secret("google-service-account")

        # Validate it looks like a service account
        if "type" not in data or data.get("type") != "service_account":
            raise SecretManagerError(
                "Invalid Google service account format",
                secret_name="google-service-account",
                details={"hint": "Expected service account JSON with type='service_account'"},
            )

        return GoogleServiceAccount(credentials_json=data)

    def get_sp_api_credentials(self, account: str) -> SPAPICredentials:
        """
        Get SP-API credentials for a seller account.

        Args:
            account: Account identifier ("eu-uk" or "na")

        Returns:
            SPAPICredentials with all required fields

        Raises:
            SecretManagerError: If credentials are missing or invalid
        """
        secret_name = f"sp-api-credentials-{account}"
        data = self.get_json_secret(secret_name)

        required_keys = {"refresh_token", "lwa_app_id", "lwa_client_secret", "aws_access_key", "aws_secret_key"}
        missing = required_keys - set(data.keys())
        if missing:
            raise SecretManagerError(
                f"Invalid SP-API credentials format: missing {missing}",
                secret_name=secret_name,
                details={"hint": f"Expected JSON with keys: {required_keys}"},
            )

        return SPAPICredentials(
            refresh_token=data["refresh_token"],
            lwa_app_id=data["lwa_app_id"],
            lwa_client_secret=data["lwa_client_secret"],
            aws_access_key=data["aws_access_key"],
            aws_secret_key=data["aws_secret_key"],
            role_arn=data.get("role_arn"),
        )

    def get_drive_folder_id(self) -> str:
        """
        Get Google Drive folder ID for output.

        Returns:
            Google Drive folder ID

        Raises:
            SecretManagerError: If folder ID is not configured
        """
        return self.get_secret("google-drive-folder-id")


# Module-level singleton instance
_client: SecretManagerClient | None = None


def get_client() -> SecretManagerClient:
    """Get or create the singleton Secret Manager client."""
    global _client
    if _client is None:
        _client = SecretManagerClient()
    return _client


def get_secret(secret_name: str, version: str = "latest") -> str:
    """Convenience function to get a secret using the singleton client."""
    return get_client().get_secret(secret_name, version)


def get_sellerboard_credentials() -> SellerboardCredentials:
    """Convenience function to get Sellerboard credentials."""
    return get_client().get_sellerboard_credentials()


def get_google_service_account() -> GoogleServiceAccount:
    """Convenience function to get Google service account credentials."""
    return get_client().get_google_service_account()


def get_drive_folder_id() -> str:
    """Convenience function to get Drive folder ID."""
    return get_client().get_drive_folder_id()


def get_sp_api_credentials(account: str) -> SPAPICredentials:
    """Convenience function to get SP-API credentials for a seller account."""
    return get_client().get_sp_api_credentials(account)
