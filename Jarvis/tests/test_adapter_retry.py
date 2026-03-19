"""Tests for retry decorator and context."""

from unittest.mock import patch

import pytest

from jarvis.adapters.exceptions import AuthError, ConnectionError, RateLimitError
from jarvis.adapters.retry import RetryContext, _calculate_delay, with_retry


class TestWithRetryDecorator:
    """Tests for the with_retry decorator."""

    def test_successful_call_no_retry(self) -> None:
        """Test that successful calls don't retry."""
        call_count = {"value": 0}

        @with_retry(max_attempts=3)
        def success():
            call_count["value"] += 1
            return "success"

        result = success()
        assert result == "success"
        assert call_count["value"] == 1

    def test_retries_on_connection_error(self) -> None:
        """Test that ConnectionError triggers retry."""
        call_count = {"value": 0}

        @with_retry(max_attempts=3, base_delay=0.01)
        def fails_twice():
            call_count["value"] += 1
            if call_count["value"] < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = fails_twice()
        assert result == "success"
        assert call_count["value"] == 3

    def test_retries_on_rate_limit_error(self) -> None:
        """Test that RateLimitError triggers retry."""
        call_count = {"value": 0}

        @with_retry(max_attempts=3, base_delay=0.01)
        def rate_limited():
            call_count["value"] += 1
            if call_count["value"] < 2:
                raise RateLimitError("Too fast")
            return "success"

        result = rate_limited()
        assert result == "success"
        assert call_count["value"] == 2

    def test_does_not_retry_auth_error(self) -> None:
        """Test that AuthError is not retried."""
        call_count = {"value": 0}

        @with_retry(max_attempts=3, base_delay=0.01)
        def auth_fails():
            call_count["value"] += 1
            raise AuthError("Invalid token")

        with pytest.raises(AuthError):
            auth_fails()

        # Should only have been called once
        assert call_count["value"] == 1

    def test_raises_after_max_attempts(self) -> None:
        """Test that exception is raised after max attempts."""
        call_count = {"value": 0}

        @with_retry(max_attempts=3, base_delay=0.01)
        def always_fails():
            call_count["value"] += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            always_fails()

        assert call_count["value"] == 3

    def test_custom_retryable_exceptions(self) -> None:
        """Test custom retryable exceptions."""

        class CustomError(Exception):
            pass

        call_count = {"value": 0}

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(CustomError,),
        )
        def custom_retry():
            call_count["value"] += 1
            if call_count["value"] < 2:
                raise CustomError("Custom error")
            return "success"

        result = custom_retry()
        assert result == "success"
        assert call_count["value"] == 2

    def test_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function metadata."""

        @with_retry(max_attempts=3)
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestCalculateDelay:
    """Tests for delay calculation."""

    def test_exponential_backoff(self) -> None:
        """Test exponential backoff calculation."""
        error = ConnectionError("Test")

        # Attempt 0: base_delay * 2^0 = 1.0
        delay0 = _calculate_delay(error, 0, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay0 == 1.0

        # Attempt 1: base_delay * 2^1 = 2.0
        delay1 = _calculate_delay(error, 1, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay1 == 2.0

        # Attempt 2: base_delay * 2^2 = 4.0
        delay2 = _calculate_delay(error, 2, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay2 == 4.0

    def test_respects_max_delay(self) -> None:
        """Test that delay is capped at max_delay."""
        error = ConnectionError("Test")

        # Very high attempt would give huge delay without cap
        delay = _calculate_delay(error, 10, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay == 30.0

    def test_uses_retry_after_from_rate_limit(self) -> None:
        """Test that retry_after from RateLimitError is used."""
        error = RateLimitError("Rate limited", retry_after=5.0)

        delay = _calculate_delay(error, 0, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay == 5.0

    def test_retry_after_respects_max_delay(self) -> None:
        """Test that retry_after is capped at max_delay."""
        error = RateLimitError("Rate limited", retry_after=60.0)

        delay = _calculate_delay(error, 0, base_delay=1.0, max_delay=30.0, exponential_base=2.0)
        assert delay == 30.0

    def test_custom_exponential_base(self) -> None:
        """Test custom exponential base."""
        error = ConnectionError("Test")

        # With base 3: base_delay * 3^1 = 3.0
        delay = _calculate_delay(error, 1, base_delay=1.0, max_delay=30.0, exponential_base=3.0)
        assert delay == 3.0


class TestRetryContext:
    """Tests for RetryContext class."""

    def test_should_retry_limits_attempts(self) -> None:
        """Test that should_retry respects max_attempts."""
        ctx = RetryContext(max_attempts=3)

        assert ctx.should_retry()
        ctx.attempt = 1
        assert ctx.should_retry()
        ctx.attempt = 2
        assert ctx.should_retry()
        ctx.attempt = 3
        assert not ctx.should_retry()

    def test_record_failure_increments_attempt(self) -> None:
        """Test that record_failure increments attempt counter."""
        ctx = RetryContext(max_attempts=3, base_delay=0.01)

        assert ctx.attempt == 0
        ctx.record_failure(ConnectionError("Test"), sleep=False)
        assert ctx.attempt == 1

    def test_record_failure_stores_exception(self) -> None:
        """Test that record_failure stores the exception."""
        ctx = RetryContext(max_attempts=3)
        error = ConnectionError("Test error")

        ctx.record_failure(error, sleep=False)
        assert ctx.last_exception is error

    def test_manual_retry_pattern(self) -> None:
        """Test the manual retry pattern works correctly."""
        ctx = RetryContext(max_attempts=3, base_delay=0.01)
        call_count = 0
        result = None

        while ctx.should_retry():
            try:
                call_count += 1
                if call_count < 3:
                    raise ConnectionError("Temporary")
                result = "success"
                break
            except ConnectionError as e:
                ctx.record_failure(e)
        else:
            raise ctx.last_exception

        assert result == "success"
        assert call_count == 3

    @patch("jarvis.adapters.retry.time.sleep")
    def test_record_failure_sleeps_by_default(self, mock_sleep) -> None:
        """Test that record_failure sleeps by default."""
        ctx = RetryContext(max_attempts=3, base_delay=1.0)

        ctx.record_failure(ConnectionError("Test"))

        mock_sleep.assert_called_once()

    def test_record_failure_no_sleep_on_last_attempt(self) -> None:
        """Test that no sleep occurs on last attempt."""
        ctx = RetryContext(max_attempts=2, base_delay=0.5)
        ctx.attempt = 1  # Last attempt

        # Should not sleep even with sleep=True
        with patch("jarvis.adapters.retry.time.sleep") as mock_sleep:
            ctx.record_failure(ConnectionError("Test"), sleep=True)
            mock_sleep.assert_not_called()
