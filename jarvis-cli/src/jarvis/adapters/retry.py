"""Retry decorator with exponential backoff for transient failures.

This module provides a decorator for retrying operations that may fail
due to transient issues like rate limits or temporary connectivity problems.
"""

import functools
import logging
import time
from typing import Callable, ParamSpec, TypeVar

from .exceptions import AuthError, ConnectionError, RateLimitError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retrying operations with exponential backoff.

    Automatically retries on RateLimitError and ConnectionError.
    Fails immediately on AuthError (no point retrying bad credentials).

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 30.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        retryable_exceptions: Tuple of exception types to retry on.
            If None, defaults to (RateLimitError, ConnectionError).

    Returns:
        Decorated function with retry logic.

    Example:
        @with_retry(max_attempts=5, base_delay=0.5)
        def fetch_data():
            # May raise RateLimitError or ConnectionError
            return api.get_data()
    """
    if retryable_exceptions is None:
        retryable_exceptions = (RateLimitError, ConnectionError)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except AuthError:
                    # Don't retry auth errors - they won't succeed
                    raise
                except retryable_exceptions as e:
                    last_exception = e
                    delay = _calculate_delay(e, attempt, base_delay, max_delay, exponential_base)

                    if attempt < max_attempts - 1:
                        logger.warning(
                            "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                            attempt + 1,
                            max_attempts,
                            str(e),
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "All %d attempts failed. Last error: %s",
                            max_attempts,
                            str(e),
                        )

            # All attempts failed
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry failed unexpectedly")

        return wrapper

    return decorator


def _calculate_delay(
    exception: Exception,
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
) -> float:
    """Calculate delay before next retry attempt.

    If the exception is a RateLimitError with retry_after set,
    uses that value. Otherwise calculates exponential backoff.

    Args:
        exception: The exception that was raised
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation

    Returns:
        Delay in seconds before next attempt
    """
    # Use Retry-After header if available
    if isinstance(exception, RateLimitError) and exception.retry_after is not None:
        return min(exception.retry_after, max_delay)

    # Calculate exponential backoff
    delay = base_delay * (exponential_base**attempt)
    return min(delay, max_delay)


class RetryContext:
    """Context manager for manual retry control.

    Useful when you need more control over the retry process
    than the decorator provides.

    Example:
        ctx = RetryContext(max_attempts=3)
        while ctx.should_retry():
            try:
                result = do_something()
                break
            except RateLimitError as e:
                ctx.record_failure(e)
        else:
            raise ctx.last_exception
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.attempt = 0
        self.last_exception: Exception | None = None

    def should_retry(self) -> bool:
        """Check if another retry attempt should be made.

        Returns:
            True if more attempts are available, False otherwise.
        """
        return self.attempt < self.max_attempts

    def record_failure(self, exception: Exception, sleep: bool = True) -> None:
        """Record a failed attempt and optionally sleep.

        Args:
            exception: The exception that occurred
            sleep: Whether to sleep before the next attempt
        """
        self.last_exception = exception
        if sleep and self.attempt < self.max_attempts - 1:
            delay = _calculate_delay(
                exception,
                self.attempt,
                self.base_delay,
                self.max_delay,
                self.exponential_base,
            )
            time.sleep(delay)
        self.attempt += 1
