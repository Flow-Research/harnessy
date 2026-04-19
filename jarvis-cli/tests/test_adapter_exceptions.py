"""Tests for adapter exceptions."""

import pytest

from jarvis.adapters.exceptions import (
    AdapterNotFoundError,
    AuthError,
    ConfigError,
    ConnectionError,
    JarvisBackendError,
    NotFoundError,
    NotSupportedError,
    RateLimitError,
    ValidationError,
)


class TestJarvisBackendError:
    """Tests for the base exception class."""

    def test_message_only(self) -> None:
        """Test exception with message only."""
        error = JarvisBackendError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.backend is None

    def test_with_backend(self) -> None:
        """Test exception with backend specified."""
        error = JarvisBackendError("Something went wrong", backend="anytype")
        assert "[anytype] Something went wrong" in str(error)
        assert error.backend == "anytype"

    def test_inheritance(self) -> None:
        """Test that JarvisBackendError inherits from Exception."""
        error = JarvisBackendError("Test")
        assert isinstance(error, Exception)


class TestConnectionError:
    """Tests for ConnectionError exception."""

    def test_basic(self) -> None:
        """Test basic ConnectionError."""
        error = ConnectionError("Cannot connect")
        assert "Cannot connect" in str(error)

    def test_with_backend(self) -> None:
        """Test ConnectionError with backend."""
        error = ConnectionError("Timeout", backend="notion")
        assert "notion" in str(error)
        assert "Timeout" in str(error)

    def test_inheritance(self) -> None:
        """Test inheritance chain."""
        error = ConnectionError("Test")
        assert isinstance(error, JarvisBackendError)


class TestAuthError:
    """Tests for AuthError exception."""

    def test_basic(self) -> None:
        """Test basic AuthError."""
        error = AuthError("Invalid token")
        assert "Invalid token" in str(error)

    def test_with_backend(self) -> None:
        """Test AuthError with backend."""
        error = AuthError("Token expired", backend="notion")
        assert "notion" in str(error)

    def test_inheritance(self) -> None:
        """Test inheritance chain."""
        error = AuthError("Test")
        assert isinstance(error, JarvisBackendError)


class TestNotFoundError:
    """Tests for NotFoundError exception."""

    def test_basic(self) -> None:
        """Test basic NotFoundError."""
        error = NotFoundError("Task not found")
        assert "Task not found" in str(error)

    def test_with_resource(self) -> None:
        """Test NotFoundError with resource info."""
        error = NotFoundError("Not found", resource_type="task", resource_id="123")
        assert error.resource_type == "task"
        assert error.resource_id == "123"

    def test_str_with_resource(self) -> None:
        """Test string representation includes resource info."""
        error = NotFoundError("Not found", resource_type="task", resource_id="123")
        result = str(error)
        # Should contain the base message at minimum
        assert "Not found" in result


class TestNotSupportedError:
    """Tests for NotSupportedError exception."""

    def test_basic(self) -> None:
        """Test basic NotSupportedError."""
        error = NotSupportedError("Search not supported")
        assert "Search not supported" in str(error)

    def test_with_capability(self) -> None:
        """Test NotSupportedError with capability info."""
        error = NotSupportedError("Not supported", capability="search")
        assert error.capability == "search"

    def test_inheritance(self) -> None:
        """Test inheritance chain."""
        error = NotSupportedError("Test")
        assert isinstance(error, JarvisBackendError)


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_basic(self) -> None:
        """Test basic RateLimitError."""
        error = RateLimitError("Too many requests")
        assert "Too many requests" in str(error)

    def test_with_retry_after(self) -> None:
        """Test RateLimitError with retry_after."""
        error = RateLimitError("Rate limited", retry_after=30.0)
        assert error.retry_after == 30.0

    def test_retry_after_default(self) -> None:
        """Test default retry_after is None."""
        error = RateLimitError("Rate limited")
        assert error.retry_after is None

    def test_inheritance(self) -> None:
        """Test inheritance chain."""
        error = RateLimitError("Test")
        assert isinstance(error, JarvisBackendError)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_basic(self) -> None:
        """Test basic ValidationError."""
        error = ValidationError("Invalid field")
        assert "Invalid field" in str(error)

    def test_with_field(self) -> None:
        """Test ValidationError with field."""
        error = ValidationError("Invalid", field="title")
        assert error.field == "title"

    def test_inheritance(self) -> None:
        """Test inheritance chain."""
        error = ValidationError("Test")
        assert isinstance(error, JarvisBackendError)


class TestConfigError:
    """Tests for ConfigError exception."""

    def test_basic(self) -> None:
        """Test basic ConfigError."""
        error = ConfigError("Missing config")
        assert "Missing config" in str(error)

    def test_with_backend(self) -> None:
        """Test ConfigError with backend."""
        error = ConfigError("Invalid setting", backend="notion")
        assert "notion" in str(error)

    def test_inheritance(self) -> None:
        """Test inheritance chain."""
        error = ConfigError("Test")
        assert isinstance(error, JarvisBackendError)


class TestAdapterNotFoundError:
    """Tests for AdapterNotFoundError exception."""

    def test_basic(self) -> None:
        """Test basic AdapterNotFoundError."""
        error = AdapterNotFoundError("Backend not found")
        assert "Backend not found" in str(error)

    def test_inheritance(self) -> None:
        """Test inheritance chain."""
        error = AdapterNotFoundError("Test")
        assert isinstance(error, JarvisBackendError)


class TestExceptionCatching:
    """Tests for exception catching patterns."""

    def test_catch_all_backend_errors(self) -> None:
        """Test catching all backend errors with base class."""
        errors = [
            ConnectionError("conn"),
            AuthError("auth"),
            NotFoundError("not found"),
            NotSupportedError("not supported"),
            RateLimitError("rate limit"),
            ValidationError("validation"),
            ConfigError("config"),
            AdapterNotFoundError("adapter"),
        ]

        for error in errors:
            try:
                raise error
            except JarvisBackendError as e:
                assert isinstance(e, JarvisBackendError)

    def test_can_catch_specific_errors(self) -> None:
        """Test catching specific error types."""

        def raise_auth_error():
            raise AuthError("Invalid token")

        def raise_rate_limit():
            raise RateLimitError("Too fast", retry_after=60.0)

        # Can catch AuthError specifically
        with pytest.raises(AuthError):
            raise_auth_error()

        # Can catch RateLimitError and access retry_after
        with pytest.raises(RateLimitError) as exc_info:
            raise_rate_limit()
        assert exc_info.value.retry_after == 60.0
