"""Adapter service for managing backend adapter lifecycle.

This module provides helper functions for getting and managing the
active adapter instance, handling connection state, and providing
a clean interface for CLI commands.
"""

from contextlib import contextmanager
from typing import Generator

from ..adapters import AdapterRegistry
from ..adapters.base import KnowledgeBaseAdapter
from ..adapters.exceptions import ConnectionError, AdapterNotFoundError
from ..config import load_config


def get_adapter(backend: str | None = None) -> KnowledgeBaseAdapter:
    """Get the configured adapter instance.

    If no backend is specified, uses the active_backend from config.

    Args:
        backend: Optional backend name override ('anytype', 'notion')

    Returns:
        Configured adapter instance (may not be connected yet)

    Raises:
        AdapterNotFoundError: If the requested backend is not available
        ConfigError: If configuration is invalid
    """
    if backend is None:
        config = load_config()
        backend = config.active_backend

    return AdapterRegistry.get_adapter(backend)


def ensure_connected(adapter: KnowledgeBaseAdapter) -> None:
    """Ensure adapter is connected, connecting if needed.

    Args:
        adapter: Adapter instance to connect

    Raises:
        ConnectionError: If connection fails
        AuthError: If authentication fails
    """
    if not adapter.is_connected():
        adapter.connect()


@contextmanager
def connected_adapter(
    backend: str | None = None,
) -> Generator[KnowledgeBaseAdapter, None, None]:
    """Context manager that provides a connected adapter.

    Automatically connects the adapter and disconnects when done.

    Args:
        backend: Optional backend name override

    Yields:
        Connected adapter instance

    Example:
        with connected_adapter() as adapter:
            tasks = adapter.get_tasks(space_id)
    """
    adapter = get_adapter(backend)
    try:
        ensure_connected(adapter)
        yield adapter
    finally:
        if adapter.is_connected():
            adapter.disconnect()


def get_default_space(adapter: KnowledgeBaseAdapter) -> str:
    """Get the default space ID for the adapter.

    This checks:
    1. Saved selection from state
    2. Config default_space
    3. First available space

    Args:
        adapter: Connected adapter instance

    Returns:
        Space ID string

    Raises:
        NotFoundError: If no spaces exist
    """
    from ..state import get_selected_space

    # Try saved selection first
    saved_space_id = get_selected_space()
    if saved_space_id:
        # Verify it still exists
        spaces = adapter.list_spaces()
        for space in spaces:
            if space.id == saved_space_id:
                return saved_space_id

    # Fall back to adapter's default
    return adapter.get_default_space()


def check_capability(adapter: KnowledgeBaseAdapter, capability: str) -> bool:
    """Check if the adapter supports a capability.

    Args:
        adapter: Adapter instance
        capability: Capability name (e.g., 'tasks', 'journal', 'search')

    Returns:
        True if capability is supported
    """
    return adapter.capabilities.get(capability, False)
