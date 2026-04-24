"""Configuration system for Jarvis.

This package provides:
- Configuration loading from YAML and environment variables
- Pydantic models for type-safe configuration
- Token management for backend APIs
"""

from .defaults import DEFAULT_CONFIG_YAML, VALID_BACKENDS
from .loader import (
    ConfigError,
    clear_config_cache,
    get_backend_token,
    get_config,
    init_config,
    load_config,
    redact_token,
    save_config,
    set_active_backend,
    validate_config,
)
from .schema import (
    AnalyticsConfig,
    AnyTypeConfig,
    BackendsConfig,
    ContentConfig,
    JarvisConfig,
    NotionConfig,
    get_config_dir,
    get_config_path,
)

__all__ = [
    # Schema
    "JarvisConfig",
    "NotionConfig",
    "AnyTypeConfig",
    "BackendsConfig",
    "ContentConfig",
    "AnalyticsConfig",
    "get_config_dir",
    "get_config_path",
    # Loader
    "load_config",
    "get_config",
    "clear_config_cache",
    "get_backend_token",
    "redact_token",
    "init_config",
    "validate_config",
    "save_config",
    "set_active_backend",
    "ConfigError",
    # Defaults
    "DEFAULT_CONFIG_YAML",
    "VALID_BACKENDS",
]
