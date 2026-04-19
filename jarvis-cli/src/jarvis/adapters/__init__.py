"""Backend adapters package.

This package provides a unified interface for knowledge base backends
like AnyType and Notion through the adapter pattern.

Usage:
    from jarvis.adapters import get_adapter

    adapter = get_adapter()  # Uses active_backend from config
    adapter.connect()
    tasks = adapter.get_tasks(space_id)

    # Or specify a backend explicitly
    notion_adapter = get_adapter("notion")
"""

from typing import Callable, TypeVar

from .base import AdapterClass, KnowledgeBaseAdapter
from .exceptions import (
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
from .retry import RetryContext, with_retry

T = TypeVar("T", bound=KnowledgeBaseAdapter)


class AdapterRegistry:
    """Registry for adapter classes and instances.

    Manages adapter lifecycle and provides configured adapters
    to the rest of the application. Implements singleton pattern
    for adapter instances to ensure consistent state.

    Usage:
        # Register a custom adapter
        AdapterRegistry.register("custom", MyCustomAdapter)

        # Get an adapter instance
        adapter = AdapterRegistry.get_adapter()  # Uses config
        adapter = AdapterRegistry.get_adapter("notion")  # Explicit

        # List available adapters
        names = AdapterRegistry.list_adapters()
    """

    _adapters: dict[str, AdapterClass] = {}
    _instances: dict[str, KnowledgeBaseAdapter] = {}
    _factory_funcs: dict[str, Callable[..., KnowledgeBaseAdapter]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        adapter_class: AdapterClass,
        factory: Callable[..., KnowledgeBaseAdapter] | None = None,
    ) -> None:
        """Register an adapter class.

        Args:
            name: Backend name (e.g., 'anytype', 'notion')
            adapter_class: Adapter class to register
            factory: Optional factory function for custom instantiation.
                     If provided, called instead of adapter_class(config).
        """
        cls._adapters[name] = adapter_class
        if factory is not None:
            cls._factory_funcs[name] = factory

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister an adapter.

        Args:
            name: Backend name to remove

        Note:
            Also removes any cached instance for this adapter.
        """
        cls._adapters.pop(name, None)
        cls._factory_funcs.pop(name, None)
        if name in cls._instances:
            instance = cls._instances.pop(name)
            if instance.is_connected():
                instance.disconnect()

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List registered adapter names.

        Returns:
            List of backend names.
        """
        return list(cls._adapters.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an adapter is registered.

        Args:
            name: Backend name to check

        Returns:
            True if registered, False otherwise.
        """
        return name in cls._adapters

    @classmethod
    def get_adapter(cls, name: str | None = None) -> KnowledgeBaseAdapter:
        """Get a configured adapter instance.

        Args:
            name: Backend name. If None, uses active_backend from config.

        Returns:
            Configured adapter instance (singleton per backend).

        Raises:
            AdapterNotFoundError: If backend not registered
            ConfigError: If config loading fails
        """
        if name is None:
            from ..config import get_config

            config = get_config()
            name = config.active_backend

        if name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise AdapterNotFoundError(
                f"Backend '{name}' not found. Available: {available}"
            )

        # Return existing instance or create new one
        if name not in cls._instances:
            cls._instances[name] = cls._create_instance(name)

        return cls._instances[name]

    @classmethod
    def _create_instance(cls, name: str) -> KnowledgeBaseAdapter:
        """Create a new adapter instance.

        Args:
            name: Backend name

        Returns:
            New adapter instance.
        """
        from ..config import get_config

        config = get_config()

        # Use factory function if provided
        if name in cls._factory_funcs:
            return cls._factory_funcs[name](config)

        # Otherwise use default constructor
        adapter_class = cls._adapters[name]
        return adapter_class(config)  # type: ignore[call-arg]

    @classmethod
    def clear_instances(cls) -> None:
        """Clear all adapter instances (for testing).

        Disconnects any connected adapters before clearing.
        """
        for adapter in cls._instances.values():
            if adapter.is_connected():
                adapter.disconnect()
        cls._instances.clear()

    @classmethod
    def clear_all(cls) -> None:
        """Clear all registrations and instances (for testing).

        This resets the registry to its initial empty state.
        """
        cls.clear_instances()
        cls._adapters.clear()
        cls._factory_funcs.clear()


def get_adapter(name: str | None = None) -> KnowledgeBaseAdapter:
    """Get the configured adapter instance.

    This is a convenience function that wraps AdapterRegistry.get_adapter().

    Args:
        name: Backend name. If None, uses active_backend from config.

    Returns:
        Configured adapter instance.

    Raises:
        AdapterNotFoundError: If backend not registered
    """
    return AdapterRegistry.get_adapter(name)


# Auto-register built-in adapters
def _register_builtin_adapters() -> None:
    """Register the built-in adapters.

    Called automatically on module import. Silently skips adapters
    whose dependencies aren't installed.
    """
    # AnyType adapter (local gRPC, requires anytype-client)
    try:
        from .anytype import AnyTypeAdapter
        AdapterRegistry.register("anytype", AnyTypeAdapter)
    except ImportError:
        pass  # anytype-client not installed

    # Notion adapter (API-based, requires notion-client)
    try:
        from .notion import NotionAdapter
        AdapterRegistry.register("notion", NotionAdapter)
    except ImportError:
        pass  # notion-client not installed


_register_builtin_adapters()


# Public API
__all__ = [
    # Core types
    "KnowledgeBaseAdapter",
    "AdapterClass",
    # Registry
    "AdapterRegistry",
    "get_adapter",
    # Exceptions
    "JarvisBackendError",
    "ConnectionError",
    "AuthError",
    "RateLimitError",
    "NotFoundError",
    "NotSupportedError",
    "AdapterNotFoundError",
    "ConfigError",
    "ValidationError",
    # Retry utilities
    "with_retry",
    "RetryContext",
]
