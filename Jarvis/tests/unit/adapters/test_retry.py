"""Tests for retry decorator and utilities."""

from unittest.mock import patch

import pytest

from jarvis.adapters.exceptions import AuthError, ConnectionError, RateLimitError
from jarvis.adapters.retry import RetryContext, _calculate_delay, with_retry


class TestWithRetry:
    """Test cases for with_retry decorator."""

    def test_success_on_first_attempt(self) -> None:
        """Test function succeeds without retry."""
        call_count = 0

        @with_retry(max_attempts=3)
        def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeed()
        assert result == "success"
        assert call_count == 1

    def test_success_after_retry(self) -> None:
        """Test function succeeds after retry."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "success"

        result = fail_then_succeed()
        assert result == "success"
        assert call_count == 2

    def test_all_attempts_fail(self) -> None:
        """Test all retry attempts fail."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection refused")

        with pytest.raises(ConnectionError):
            always_fail()
        assert call_count == 3

    def test_auth_error_not_retried(self) -> None:
        """Test AuthError is not retried."""
        call_count = 0

        @with_retry(max_attempts=3)
        def auth_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise AuthError("Invalid token")

        with pytest.raises(AuthError):
            auth_fails()
        assert call_count == 1  # No retries

    def test_rate_limit_error_retried(self) -> None:
        """Test RateLimitError is retried."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def rate_limited() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Too many requests")
            return "success"

        result = rate_limited()
        assert result == "success"
        assert call_count == 3

    def test_rate_limit_uses_retry_after(self) -> None:
        """Test retry_after from RateLimitError is used."""
        call_count = 0

        @with_retry(max_attempts=2, base_delay=10.0)
        def rate_limited() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("Too many requests", retry_after=0.01)
            return "success"

        with patch("jarvis.adapters.retry.time.sleep") as mock_sleep:
            result = rate_limited()
            # Should use 0.01 from retry_after, not 10.0 from base_delay
            mock_sleep.assert_called_once()
            assert mock_sleep.call_args[0][0] == pytest.approx(0.01, rel=0.1)

        assert result == "success"

    def test_exponential_backoff(self) -> None:
        """Test exponential backoff is applied."""
        call_count = 0

        @with_retry(max_attempts=4, base_delay=1.0, exponential_base=2.0)
        def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection refused")

        with patch("jarvis.adapters.retry.time.sleep") as mock_sleep:
            with pytest.raises(ConnectionError):
                always_fail()

            # Delays should be: 1.0, 2.0, 4.0 (no sleep after last attempt)
            assert mock_sleep.call_count == 3
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls[0] == pytest.approx(1.0)
            assert calls[1] == pytest.approx(2.0)
            assert calls[2] == pytest.approx(4.0)

    def test_max_delay_caps_backoff(self) -> None:
        """Test max_delay caps the exponential backoff."""
        @with_retry(max_attempts=4, base_delay=1.0, max_delay=2.5, exponential_base=2.0)
        def always_fail() -> str:
            raise ConnectionError("Connection refused")

        with patch("jarvis.adapters.retry.time.sleep") as mock_sleep:
            with pytest.raises(ConnectionError):
                always_fail()

            # Delays should be: 1.0, 2.0, 2.5 (capped)
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls[0] == pytest.approx(1.0)
            assert calls[1] == pytest.approx(2.0)
            assert calls[2] == pytest.approx(2.5)  # Capped

    def test_custom_retryable_exceptions(self) -> None:
        """Test custom retryable exception types."""

        class CustomError(Exception):
            pass

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, retryable_exceptions=(CustomError,))
        def custom_fails() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise CustomError("Custom error")
            return "success"

        result = custom_fails()
        assert result == "success"
        assert call_count == 2

    def test_non_retryable_exception_not_retried(self) -> None:
        """Test non-retryable exceptions are not retried."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid value")

        with pytest.raises(ValueError):
            value_error()
        assert call_count == 1  # No retries

    def test_preserves_function_metadata(self) -> None:
        """Test decorator preserves function metadata."""

        @with_retry()
        def documented_function() -> str:
            """This is the docstring."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."


class TestCalculateDelay:
    """Test cases for _calculate_delay function."""

    def test_rate_limit_with_retry_after(self) -> None:
        """Test delay calculation with retry_after."""
        exc = RateLimitError("Rate limited", retry_after=5.0)
        delay = _calculate_delay(exc, attempt=0, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay == 5.0

    def test_rate_limit_retry_after_capped(self) -> None:
        """Test retry_after is capped by max_delay."""
        exc = RateLimitError("Rate limited", retry_after=60.0)
        delay = _calculate_delay(exc, attempt=0, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay == 30.0

    def test_exponential_backoff_calculation(self) -> None:
        """Test exponential backoff for non-rate-limit errors."""
        exc = ConnectionError("Connection refused")

        # attempt 0: 1.0 * 2^0 = 1.0
        assert _calculate_delay(exc, 0, 1.0, 30.0, 2.0) == 1.0
        # attempt 1: 1.0 * 2^1 = 2.0
        assert _calculate_delay(exc, 1, 1.0, 30.0, 2.0) == 2.0
        # attempt 2: 1.0 * 2^2 = 4.0
        assert _calculate_delay(exc, 2, 1.0, 30.0, 2.0) == 4.0
        # attempt 3: 1.0 * 2^3 = 8.0
        assert _calculate_delay(exc, 3, 1.0, 30.0, 2.0) == 8.0

    def test_max_delay_applied(self) -> None:
        """Test max_delay caps exponential backoff."""
        exc = ConnectionError("Connection refused")
        # attempt 10: 1.0 * 2^10 = 1024, should be capped to 30
        delay = _calculate_delay(exc, 10, 1.0, 30.0, 2.0)
        assert delay == 30.0


class TestRetryContext:
    """Test cases for RetryContext class."""

    def test_should_retry_returns_true_initially(self) -> None:
        """Test should_retry returns True when attempts remain."""
        ctx = RetryContext(max_attempts=3)
        assert ctx.should_retry() is True

    def test_should_retry_returns_false_after_max_attempts(self) -> None:
        """Test should_retry returns False after max attempts."""
        ctx = RetryContext(max_attempts=2)
        ctx.attempt = 2
        assert ctx.should_retry() is False

    def test_record_failure_increments_attempt(self) -> None:
        """Test record_failure increments attempt counter."""
        ctx = RetryContext(max_attempts=3)
        ctx.record_failure(ConnectionError("test"), sleep=False)
        assert ctx.attempt == 1

    def test_record_failure_stores_exception(self) -> None:
        """Test record_failure stores the exception."""
        ctx = RetryContext(max_attempts=3)
        exc = ConnectionError("test error")
        ctx.record_failure(exc, sleep=False)
        assert ctx.last_exception is exc

    def test_record_failure_sleeps_by_default(self) -> None:
        """Test record_failure sleeps between attempts."""
        ctx = RetryContext(max_attempts=3, base_delay=1.0)

        with patch("jarvis.adapters.retry.time.sleep") as mock_sleep:
            ctx.record_failure(ConnectionError("test"))
            mock_sleep.assert_called_once()

    def test_record_failure_no_sleep_on_last_attempt(self) -> None:
        """Test record_failure doesn't sleep on last attempt."""
        ctx = RetryContext(max_attempts=2)
        ctx.attempt = 1  # Last attempt

        with patch("jarvis.adapters.retry.time.sleep") as mock_sleep:
            ctx.record_failure(ConnectionError("test"))
            mock_sleep.assert_not_called()

    def test_record_failure_no_sleep_when_disabled(self) -> None:
        """Test record_failure respects sleep=False."""
        ctx = RetryContext(max_attempts=3)

        with patch("jarvis.adapters.retry.time.sleep") as mock_sleep:
            ctx.record_failure(ConnectionError("test"), sleep=False)
            mock_sleep.assert_not_called()

    def test_manual_retry_loop(self) -> None:
        """Test using RetryContext in a manual loop."""
        attempt_count = 0

        ctx = RetryContext(max_attempts=3, base_delay=0.01)
        while ctx.should_retry():
            try:
                attempt_count += 1
                if attempt_count < 3:
                    raise ConnectionError("Temporary failure")
                break
            except ConnectionError as e:
                ctx.record_failure(e)
        else:
            raise ctx.last_exception  # type: ignore[misc]

        assert attempt_count == 3
