"""Tests for AdapterRegistry."""

import pytest

from jarvis.adapters import AdapterRegistry, get_adapter
from jarvis.adapters.base import KnowledgeBaseAdapter
from jarvis.adapters.exceptions import AdapterNotFoundError


class MockAdapter:
    """Mock adapter for testing."""

    def __init__(self, config=None):
        self._connected = False
        self._config = config

    @property
    def capabilities(self) -> dict[str, bool]:
        return {
            "tasks": True,
            "journal": True,
            "tags": True,
            "search": False,
            "priorities": True,
            "due_dates": True,
            "daily_notes": False,
            "relations": False,
            "custom_properties": False,
        }

    @property
    def backend_name(self) -> str:
        return "mock"

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected


@pytest.fixture(autouse=True)
def clean_registry():
    """Clean registry state before and after each test."""
    # Store original state
    original_adapters = AdapterRegistry._adapters.copy()
    original_instances = AdapterRegistry._instances.copy()
    original_factories = AdapterRegistry._factory_funcs.copy()

    yield

    # Restore original state
    AdapterRegistry.clear_all()
    AdapterRegistry._adapters = original_adapters
    AdapterRegistry._instances = original_instances
    AdapterRegistry._factory_funcs = original_factories


class TestAdapterRegistry:
    """Tests for AdapterRegistry class."""

    def test_register_adapter(self) -> None:
        """Test registering an adapter."""
        AdapterRegistry.register("test", MockAdapter)
        assert AdapterRegistry.is_registered("test")
        assert "test" in AdapterRegistry.list_adapters()

    def test_unregister_adapter(self) -> None:
        """Test unregistering an adapter."""
        AdapterRegistry.register("test", MockAdapter)
        AdapterRegistry.unregister("test")
        assert not AdapterRegistry.is_registered("test")
        assert "test" not in AdapterRegistry.list_adapters()

    def test_unregister_disconnects_instance(self) -> None:
        """Test that unregistering disconnects any cached instance."""
        AdapterRegistry.register("test", MockAdapter)

        # Create and connect an instance
        instance = MockAdapter()
        instance.connect()
        AdapterRegistry._instances["test"] = instance

        assert instance.is_connected()
        AdapterRegistry.unregister("test")
        assert not instance.is_connected()

    def test_list_adapters(self) -> None:
        """Test listing registered adapters."""
        AdapterRegistry.register("alpha", MockAdapter)
        AdapterRegistry.register("beta", MockAdapter)

        adapters = AdapterRegistry.list_adapters()
        assert "alpha" in adapters
        assert "beta" in adapters

    def test_is_registered(self) -> None:
        """Test checking if adapter is registered."""
        AdapterRegistry.register("test", MockAdapter)
        assert AdapterRegistry.is_registered("test")
        assert not AdapterRegistry.is_registered("nonexistent")

    def test_get_adapter_not_found(self) -> None:
        """Test getting a non-existent adapter raises error."""
        with pytest.raises(AdapterNotFoundError) as exc_info:
            AdapterRegistry.get_adapter("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_get_adapter_returns_singleton(self) -> None:
        """Test that get_adapter returns the same instance."""
        AdapterRegistry.register("test", MockAdapter)

        adapter1 = AdapterRegistry.get_adapter("test")
        adapter2 = AdapterRegistry.get_adapter("test")

        assert adapter1 is adapter2

    def test_clear_instances(self) -> None:
        """Test clearing adapter instances."""
        AdapterRegistry.register("test", MockAdapter)
        instance = AdapterRegistry.get_adapter("test")
        instance.connect()

        AdapterRegistry.clear_instances()

        assert "test" not in AdapterRegistry._instances
        assert not instance.is_connected()

    def test_clear_all(self) -> None:
        """Test clearing all registrations and instances."""
        AdapterRegistry.register("test", MockAdapter)
        AdapterRegistry.get_adapter("test")

        AdapterRegistry.clear_all()

        assert not AdapterRegistry._adapters
        assert not AdapterRegistry._instances
        assert not AdapterRegistry._factory_funcs

    def test_register_with_factory(self) -> None:
        """Test registering adapter with custom factory."""
        factory_called = {"value": False}

        def custom_factory(config):
            factory_called["value"] = True
            return MockAdapter(config)

        AdapterRegistry.register("test", MockAdapter, factory=custom_factory)
        AdapterRegistry.get_adapter("test")

        assert factory_called["value"]

    def test_unregister_nonexistent_is_safe(self) -> None:
        """Test that unregistering nonexistent adapter doesn't raise."""
        AdapterRegistry.unregister("nonexistent")  # Should not raise


class TestGetAdapterFunction:
    """Tests for the get_adapter convenience function."""

    def test_get_adapter_delegates_to_registry(self) -> None:
        """Test that get_adapter() delegates to AdapterRegistry."""
        AdapterRegistry.register("test", MockAdapter)

        adapter = get_adapter("test")

        assert isinstance(adapter, MockAdapter)

    def test_get_adapter_raises_not_found(self) -> None:
        """Test that get_adapter raises for unknown backends."""
        with pytest.raises(AdapterNotFoundError):
            get_adapter("nonexistent")


class TestBuiltinAdapters:
    """Tests for built-in adapter registration."""

    def test_anytype_adapter_registered(self) -> None:
        """Test that AnyType adapter is registered by default."""
        # The fixture clears the registry, but builtins are registered on import
        # We need to check the original state was preserved or re-register
        from jarvis.adapters import _register_builtin_adapters

        _register_builtin_adapters()
        assert AdapterRegistry.is_registered("anytype")

    def test_notion_adapter_registered(self) -> None:
        """Test that Notion adapter is registered by default."""
        from jarvis.adapters import _register_builtin_adapters

        _register_builtin_adapters()
        assert AdapterRegistry.is_registered("notion")
