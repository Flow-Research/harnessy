"""Configuration system for Jarvis.

This package provides:
- Configuration loading from YAML and environment variables
- Pydantic models for type-safe configuration
- Token management for backend APIs
"""

from .defaults import DEFAULT_CONFIG_YAML, VALID_BACKENDS
from .fathom_setup import (
    FathomSetupAccount,
    default_env_file_path,
    default_env_var,
    default_shell_profile_path,
    ensure_default_accounts,
    ensure_shell_profile_sources_env,
    escape_shell_value,
    normalize_fathom_accounts,
    render_fathom_env_file,
    update_managed_env_var,
    write_env_file,
)
from .loader import (
    ConfigError,
    clear_config_cache,
    get_backend_token,
    get_config,
    get_fathom_api_key,
    get_fathom_webhook_secret,
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
    FathomAccountConfig,
    FathomConfig,
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
    "FathomAccountConfig",
    "FathomConfig",
    "get_config_dir",
    "get_config_path",
    # Loader
    "load_config",
    "get_config",
    "clear_config_cache",
    "get_backend_token",
    "get_fathom_api_key",
    "get_fathom_webhook_secret",
    "redact_token",
    "init_config",
    "validate_config",
    "save_config",
    "set_active_backend",
    "ConfigError",
    # Defaults
    "DEFAULT_CONFIG_YAML",
    "VALID_BACKENDS",
    # Fathom setup helpers
    "FathomSetupAccount",
    "default_env_var",
    "normalize_fathom_accounts",
    "ensure_default_accounts",
    "render_fathom_env_file",
    "escape_shell_value",
    "update_managed_env_var",
    "write_env_file",
    "default_env_file_path",
    "default_shell_profile_path",
    "ensure_shell_profile_sources_env",
]
