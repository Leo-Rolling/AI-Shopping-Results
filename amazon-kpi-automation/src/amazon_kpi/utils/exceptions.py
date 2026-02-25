"""Custom exceptions for Amazon KPI automation."""

from typing import Any


class AmazonKPIError(Exception):
    """Base exception for all Amazon KPI automation errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ScrapingError(AmazonKPIError):
    """Base exception for web scraping errors."""

    pass


class AuthenticationError(ScrapingError):
    """Raised when login to Sellerboard fails."""

    def __init__(
        self,
        message: str = "Failed to authenticate with Sellerboard",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)


class NavigationError(ScrapingError):
    """Raised when page navigation fails."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        selector: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if url:
            details["url"] = url
        if selector:
            details["selector"] = selector
        super().__init__(message, details)


class DataExtractionError(ScrapingError):
    """Raised when KPI data extraction fails."""

    def __init__(
        self,
        message: str,
        marketplace: str | None = None,
        category: str | None = None,
        kpi_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if marketplace:
            details["marketplace"] = marketplace
        if category:
            details["category"] = category
        if kpi_name:
            details["kpi_name"] = kpi_name
        super().__init__(message, details)


class ElementNotFoundError(ScrapingError):
    """Raised when an expected DOM element is not found."""

    def __init__(
        self,
        selector: str,
        timeout_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        details["selector"] = selector
        if timeout_ms:
            details["timeout_ms"] = timeout_ms
        message = f"Element not found: {selector}"
        super().__init__(message, details)


class SheetsError(AmazonKPIError):
    """Base exception for Google Sheets errors."""

    pass


class SheetCreationError(SheetsError):
    """Raised when creating a Google Sheet fails."""

    def __init__(
        self,
        message: str = "Failed to create Google Sheet",
        sheet_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if sheet_name:
            details["sheet_name"] = sheet_name
        super().__init__(message, details)


class SheetUpdateError(SheetsError):
    """Raised when updating a Google Sheet fails."""

    def __init__(
        self,
        message: str,
        sheet_id: str | None = None,
        range_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if sheet_id:
            details["sheet_id"] = sheet_id
        if range_name:
            details["range_name"] = range_name
        super().__init__(message, details)


class SecretManagerError(AmazonKPIError):
    """Raised when accessing GCP Secret Manager fails."""

    def __init__(
        self,
        message: str,
        secret_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if secret_name:
            details["secret_name"] = secret_name
        super().__init__(message, details)


class ConfigurationError(AmazonKPIError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, details)


class RateLimitError(ScrapingError):
    """Raised when rate limiting is detected."""

    def __init__(
        self,
        message: str = "Rate limit detected",
        retry_after_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if retry_after_seconds:
            details["retry_after_seconds"] = retry_after_seconds
        super().__init__(message, details)


# =============================================================================
# SP-API Exceptions
# =============================================================================


class SPAPIError(AmazonKPIError):
    """Base exception for SP-API errors."""

    def __init__(
        self,
        message: str,
        marketplace: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if marketplace:
            details["marketplace"] = marketplace
        super().__init__(message, details)


class DataKioskError(SPAPIError):
    """Raised when a Data Kiosk query fails."""

    def __init__(
        self,
        message: str,
        query_id: str | None = None,
        marketplace: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if query_id:
            details["query_id"] = query_id
        super().__init__(message, marketplace, details)


class DataKioskTimeoutError(DataKioskError):
    """Raised when a Data Kiosk query times out."""

    pass


class ReportError(SPAPIError):
    """Raised when an SP-API report request fails."""

    def __init__(
        self,
        message: str,
        report_id: str | None = None,
        marketplace: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if report_id:
            details["report_id"] = report_id
        super().__init__(message, marketplace, details)


class ReportTimeoutError(ReportError):
    """Raised when a report times out."""

    pass


class ThrottlingError(SPAPIError):
    """Raised when SP-API returns 429 (too many requests)."""

    def __init__(
        self,
        message: str = "SP-API rate limit exceeded",
        retry_after_seconds: int | None = None,
        marketplace: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if retry_after_seconds:
            details["retry_after_seconds"] = retry_after_seconds
        super().__init__(message, marketplace, details)
