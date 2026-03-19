"""Tests for adapter exception hierarchy."""

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
    """Test cases for base JarvisBackendError."""

    def test_create_with_message(self) -> None:
        """Test creating error with just message."""
        error = JarvisBackendError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.backend is None

    def test_create_with_backend(self) -> None:
        """Test creating error with backend context."""
        error = JarvisBackendError("Something went wrong", backend="notion")
        assert str(error) == "[notion] Something went wrong"
        assert error.backend == "notion"

    def test_is_exception(self) -> None:
        """Test that JarvisBackendError is an Exception."""
        assert issubclass(JarvisBackendError, Exception)

    def test_can_be_raised(self) -> None:
        """Test that error can be raised and caught."""
        with pytest.raises(JarvisBackendError) as exc_info:
            raise JarvisBackendError("Test error", backend="anytype")
        assert "anytype" in str(exc_info.value)


class TestConnectionError:
    """Test cases for ConnectionError."""

    def test_inherits_from_base(self) -> None:
        """Test ConnectionError inherits from JarvisBackendError."""
        assert issubclass(ConnectionError, JarvisBackendError)

    def test_create_connection_error(self) -> None:
        """Test creating a connection error."""
        error = ConnectionError("Cannot connect to localhost:31009", backend="anytype")
        assert "localhost" in str(error)
        assert error.backend == "anytype"

    def test_catch_as_base_error(self) -> None:
        """Test ConnectionError can be caught as JarvisBackendError."""
        with pytest.raises(JarvisBackendError):
            raise ConnectionError("Connection refused")


class TestAuthError:
    """Test cases for AuthError."""

    def test_inherits_from_base(self) -> None:
        """Test AuthError inherits from JarvisBackendError."""
        assert issubclass(AuthError, JarvisBackendError)

    def test_create_auth_error(self) -> None:
        """Test creating an auth error."""
        error = AuthError("Invalid token", backend="notion")
        assert "Invalid token" in str(error)
        assert error.backend == "notion"


class TestRateLimitError:
    """Test cases for RateLimitError."""

    def test_inherits_from_base(self) -> None:
        """Test RateLimitError inherits from JarvisBackendError."""
        assert issubclass(RateLimitError, JarvisBackendError)

    def test_create_with_retry_after(self) -> None:
        """Test creating error with retry_after."""
        error = RateLimitError(
            "Rate limit exceeded", backend="notion", retry_after=30.0
        )
        assert error.retry_after == 30.0
        assert "notion" in str(error)

    def test_create_without_retry_after(self) -> None:
        """Test creating error without retry_after."""
        error = RateLimitError("Rate limit exceeded", backend="notion")
        assert error.retry_after is None

    def test_retry_after_can_be_float(self) -> None:
        """Test retry_after accepts float values."""
        error = RateLimitError("Rate limited", retry_after=0.5)
        assert error.retry_after == 0.5


class TestNotFoundError:
    """Test cases for NotFoundError."""

    def test_inherits_from_base(self) -> None:
        """Test NotFoundError inherits from JarvisBackendError."""
        assert issubclass(NotFoundError, JarvisBackendError)

    def test_create_with_resource_info(self) -> None:
        """Test creating error with resource type and ID."""
        error = NotFoundError(
            "Task not found",
            backend="anytype",
            resource_type="task",
            resource_id="task-123",
        )
        assert error.resource_type == "task"
        assert error.resource_id == "task-123"

    def test_create_without_resource_info(self) -> None:
        """Test creating error without optional resource info."""
        error = NotFoundError("Resource not found")
        assert error.resource_type is None
        assert error.resource_id is None


class TestNotSupportedError:
    """Test cases for NotSupportedError."""

    def test_inherits_from_base(self) -> None:
        """Test NotSupportedError inherits from JarvisBackendError."""
        assert issubclass(NotSupportedError, JarvisBackendError)

    def test_create_with_capability(self) -> None:
        """Test creating error with capability info."""
        error = NotSupportedError(
            "Daily notes not supported",
            backend="notion",
            capability="daily_notes",
        )
        assert error.capability == "daily_notes"
        assert "notion" in str(error)

    def test_create_without_capability(self) -> None:
        """Test creating error without capability info."""
        error = NotSupportedError("Operation not supported")
        assert error.capability is None


class TestAdapterNotFoundError:
    """Test cases for AdapterNotFoundError."""

    def test_inherits_from_base(self) -> None:
        """Test AdapterNotFoundError inherits from JarvisBackendError."""
        assert issubclass(AdapterNotFoundError, JarvisBackendError)

    def test_create_adapter_not_found_error(self) -> None:
        """Test creating adapter not found error."""
        error = AdapterNotFoundError("Backend 'obsidian' not registered")
        assert "obsidian" in str(error)


class TestConfigError:
    """Test cases for ConfigError."""

    def test_inherits_from_base(self) -> None:
        """Test ConfigError inherits from JarvisBackendError."""
        assert issubclass(ConfigError, JarvisBackendError)

    def test_create_config_error(self) -> None:
        """Test creating config error."""
        error = ConfigError("Missing workspace_id", backend="notion")
        assert "workspace_id" in str(error)
        assert error.backend == "notion"


class TestValidationError:
    """Test cases for ValidationError."""

    def test_inherits_from_base(self) -> None:
        """Test ValidationError inherits from JarvisBackendError."""
        assert issubclass(ValidationError, JarvisBackendError)

    def test_create_validation_error(self) -> None:
        """Test creating validation error."""
        error = ValidationError("Title cannot be empty", backend="anytype")
        assert "Title" in str(error)
        assert error.backend == "anytype"


class TestExceptionHierarchy:
    """Test the overall exception hierarchy."""

    def test_all_exceptions_inherit_from_base(self) -> None:
        """Test all exceptions inherit from JarvisBackendError."""
        exceptions = [
            ConnectionError,
            AuthError,
            RateLimitError,
            NotFoundError,
            NotSupportedError,
            AdapterNotFoundError,
            ConfigError,
            ValidationError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, JarvisBackendError)

    def test_exception_can_be_caught_hierarchically(self) -> None:
        """Test exceptions can be caught at different levels."""
        # Specific catch
        with pytest.raises(NotFoundError):
            raise NotFoundError("Task not found")

        # Base catch
        with pytest.raises(JarvisBackendError):
            raise NotFoundError("Task not found")

        # Built-in Exception catch
        with pytest.raises(Exception):
            raise NotFoundError("Task not found")

    def test_multiple_exceptions_in_except_block(self) -> None:
        """Test catching multiple exception types."""
        retryable_errors = (RateLimitError, ConnectionError)

        def might_fail() -> None:
            raise RateLimitError("Too many requests")

        with pytest.raises(retryable_errors):
            might_fail()
