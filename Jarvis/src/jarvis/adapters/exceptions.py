"""Typed exception hierarchy for backend adapters.

This module defines a hierarchy of exceptions that adapters use to
communicate errors in a consistent, type-safe way. This allows the
CLI and service layers to handle errors appropriately without needing
to know backend-specific error types.
"""


class JarvisBackendError(Exception):
    """Base exception for all backend errors.

    All adapter exceptions inherit from this class, allowing for
    broad exception handling when needed.

    Attributes:
        backend: The backend that raised the error (e.g., 'anytype', 'notion')
    """

    def __init__(self, message: str, backend: str | None = None):
        self.backend = backend
        super().__init__(message)

    def __str__(self) -> str:
        if self.backend:
            return f"[{self.backend}] {super().__str__()}"
        return super().__str__()


class ConnectionError(JarvisBackendError):  # noqa: A001 - Intentional shadow of builtin
    """Cannot connect to backend.

    Raised when:
    - Backend service is not running
    - Network connectivity issues
    - Timeout during connection
    """

    pass


class AuthError(JarvisBackendError):
    """Authentication failed.

    Raised when:
    - API token is invalid or expired
    - Missing required credentials
    - Insufficient permissions
    """

    pass


class RateLimitError(JarvisBackendError):
    """Too many requests to backend.

    Raised when the backend returns a rate limit response (e.g., HTTP 429).

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header)
    """

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message, backend)
        self.retry_after = retry_after


class NotFoundError(JarvisBackendError):
    """Resource not found.

    Raised when:
    - Requested task, journal entry, or space doesn't exist
    - Resource was deleted

    Attributes:
        resource_type: Type of resource (e.g., 'task', 'journal_entry', 'space')
        resource_id: ID of the resource that wasn't found
    """

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ):
        super().__init__(message, backend)
        self.resource_type = resource_type
        self.resource_id = resource_id


class NotSupportedError(JarvisBackendError):
    """Operation not supported by this backend.

    Raised when:
    - Attempting an operation the backend doesn't support
    - Using a feature that requires a specific capability

    Attributes:
        capability: The capability that's not supported
    """

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        capability: str | None = None,
    ):
        super().__init__(message, backend)
        self.capability = capability


class AdapterNotFoundError(JarvisBackendError):
    """Requested adapter not registered.

    Raised when:
    - Attempting to use a backend that isn't installed
    - Typo in backend name
    """

    pass


class ConfigError(JarvisBackendError):
    """Configuration error.

    Raised when:
    - Required configuration is missing
    - Configuration values are invalid
    - Environment variables not set
    """

    pass


class ValidationError(JarvisBackendError):
    """Data validation error.

    Raised when:
    - Input data fails validation
    - Data from backend doesn't match expected schema

    Attributes:
        field: The field that failed validation
    """

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        field: str | None = None,
    ):
        super().__init__(message, backend)
        self.field = field
