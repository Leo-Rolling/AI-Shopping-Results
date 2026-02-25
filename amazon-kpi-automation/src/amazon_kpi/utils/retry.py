"""Retry decorators and utilities using tenacity."""

import asyncio
import random
from functools import wraps
from typing import Any, Callable, TypeVar

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    before_sleep_log,
)

from ..config.constants import (
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    MIN_ACTION_DELAY,
    MAX_ACTION_DELAY,
)
from .exceptions import (
    ScrapingError,
    AuthenticationError,
    RateLimitError,
    SheetsError,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def with_retry(
    max_attempts: int = MAX_RETRIES,
    min_wait: float = RETRY_DELAY_SECONDS,
    max_wait: float = RETRY_DELAY_SECONDS * 4,
    retry_on: tuple[type[Exception], ...] = (ScrapingError, SheetsError),
    exclude: tuple[type[Exception], ...] = (AuthenticationError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for synchronous functions with retry logic.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        retry_on: Exception types to retry on
        exclude: Exception types to NOT retry on (even if in retry_on)

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            def should_retry(exception: BaseException) -> bool:
                if isinstance(exception, exclude):
                    return False
                return isinstance(exception, retry_on)

            try:
                for attempt in Retrying(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                    retry=retry_if_exception_type(retry_on),
                    before_sleep=lambda retry_state: logger.warning(
                        "Retrying after error",
                        function=func.__name__,
                        attempt=retry_state.attempt_number,
                        error=str(retry_state.outcome.exception()) if retry_state.outcome else None,
                    ),
                ):
                    with attempt:
                        if attempt.retry_state.attempt_number > 1:
                            logger.info(
                                "Retry attempt",
                                function=func.__name__,
                                attempt=attempt.retry_state.attempt_number,
                            )
                        return func(*args, **kwargs)
            except RetryError as e:
                logger.error(
                    "All retry attempts failed",
                    function=func.__name__,
                    max_attempts=max_attempts,
                )
                raise e.last_attempt.exception() from e

            # Should never reach here, but satisfy type checker
            raise RuntimeError("Unexpected retry state")

        return wrapper

    return decorator


def async_with_retry(
    max_attempts: int = MAX_RETRIES,
    min_wait: float = RETRY_DELAY_SECONDS,
    max_wait: float = RETRY_DELAY_SECONDS * 4,
    retry_on: tuple[type[Exception], ...] = (ScrapingError, SheetsError),
    exclude: tuple[type[Exception], ...] = (AuthenticationError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for async functions with retry logic.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        retry_on: Exception types to retry on
        exclude: Exception types to NOT retry on

    Returns:
        Decorated async function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                    retry=retry_if_exception_type(retry_on),
                    before_sleep=lambda retry_state: logger.warning(
                        "Retrying after error",
                        function=func.__name__,
                        attempt=retry_state.attempt_number,
                        error=str(retry_state.outcome.exception()) if retry_state.outcome else None,
                    ),
                ):
                    with attempt:
                        if attempt.retry_state.attempt_number > 1:
                            logger.info(
                                "Retry attempt",
                                function=func.__name__,
                                attempt=attempt.retry_state.attempt_number,
                            )
                        return await func(*args, **kwargs)
            except RetryError as e:
                logger.error(
                    "All retry attempts failed",
                    function=func.__name__,
                    max_attempts=max_attempts,
                )
                raise e.last_attempt.exception() from e

            raise RuntimeError("Unexpected retry state")

        return wrapper

    return decorator


async def random_delay(
    min_seconds: float = MIN_ACTION_DELAY,
    max_seconds: float = MAX_ACTION_DELAY,
) -> None:
    """
    Add a random delay to simulate human-like behavior.

    Args:
        min_seconds: Minimum delay in seconds
        max_seconds: Maximum delay in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug("Adding random delay", delay_seconds=round(delay, 2))
    await asyncio.sleep(delay)


def sync_random_delay(
    min_seconds: float = MIN_ACTION_DELAY,
    max_seconds: float = MAX_ACTION_DELAY,
) -> None:
    """
    Synchronous version of random delay.

    Args:
        min_seconds: Minimum delay in seconds
        max_seconds: Maximum delay in seconds
    """
    import time

    delay = random.uniform(min_seconds, max_seconds)
    logger.debug("Adding random delay", delay_seconds=round(delay, 2))
    time.sleep(delay)
