"""Configuration loading from YAML files and environment variables."""

import os
from pathlib import Path

import yaml

from .defaults import (
    DEFAULT_CONFIG_YAML,
    ENV_NOTION_TOKEN,
    ENV_NOTION_TOKEN_FALLBACK,
)
from .schema import JarvisConfig, NotionConfig, get_config_path


class ConfigError(Exception):
    """Configuration error."""

    def __init__(self, message: str, backend: str | None = None):
        self.backend = backend
        super().__init__(message)

    def __str__(self) -> str:
        if self.backend:
            return f"[{self.backend}] {super().__str__()}"
        return super().__str__()


# Cached config instance
_config_instance: JarvisConfig | None = None


def load_config(config_path: Path | None = None, reload: bool = False) -> JarvisConfig:
    """Load Jarvis configuration from YAML file and environment.

    Configuration precedence (highest to lowest):
    1. Environment variables (JARVIS_* prefix)
    2. Config file values
    3. Default values

    Args:
        config_path: Optional path to config file. Uses default if None.
        reload: If True, reload config even if cached.

    Returns:
        JarvisConfig instance
    """
    global _config_instance

    if _config_instance is not None and not reload:
        return _config_instance

    path = config_path or get_config_path()

    # Load YAML if exists
    config_data: dict = {}
    if path.exists():
        with open(path) as f:
            loaded = yaml.safe_load(f)
            if loaded:
                config_data = loaded

    # Create config (Pydantic Settings will merge env vars)
    _config_instance = JarvisConfig(**config_data)
    return _config_instance


def get_config() -> JarvisConfig:
    """Get the current Jarvis configuration.

    Returns cached instance or loads if not yet loaded.

    Returns:
        JarvisConfig instance
    """
    return load_config()


def clear_config_cache() -> None:
    """Clear the cached configuration.

    Useful for testing or when config file has been modified.
    """
    global _config_instance
    _config_instance = None


def get_backend_token(backend: str) -> str:
    """Get API token for a backend from environment.

    Token resolution priority:
    1. JARVIS_{BACKEND}_TOKEN (e.g., JARVIS_NOTION_TOKEN)
    2. {BACKEND}_TOKEN (e.g., NOTION_TOKEN)

    Args:
        backend: Backend name (e.g., 'notion')

    Returns:
        API token string.

    Raises:
        ConfigError: If token not found.
    """
    # Try specific variable first
    specific_var = f"JARVIS_{backend.upper()}_TOKEN"
    token = os.environ.get(specific_var)

    if token:
        return token

    # Try generic variable (fallback)
    generic_var = f"{backend.upper()}_TOKEN"
    token = os.environ.get(generic_var)

    if token:
        return token

    raise ConfigError(
        f"No API token found for {backend}. "
        f"Set {specific_var} or {generic_var} environment variable.",
        backend=backend,
    )


def redact_token(token: str) -> str:
    """Redact a token for safe logging/display.

    Always shows exactly 4 characters to prevent information
    leakage about token length or structure.

    Args:
        token: Full token string

    Returns:
        Redacted string showing only first 4 chars.
    """
    if len(token) <= 4:
        return "****"
    return f"{token[:4]}****"


def init_config(config_path: Path | None = None, force: bool = False) -> Path:
    """Initialize a new configuration file with defaults.

    Args:
        config_path: Optional path for config file. Uses default if None.
        force: If True, overwrite existing config file.

    Returns:
        Path to the created config file.

    Raises:
        ConfigError: If file exists and force=False.
    """
    path = config_path or get_config_path()

    if path.exists() and not force:
        raise ConfigError(f"Configuration file already exists: {path}")

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write default config
    with open(path, "w") as f:
        f.write(DEFAULT_CONFIG_YAML)

    return path


def validate_config() -> list[str]:
    """Validate the current configuration.

    Checks:
    - Config file syntax
    - Required fields for active backend
    - Token availability for backends that need it

    Returns:
        List of validation warnings/errors. Empty list if valid.
    """
    issues: list[str] = []

    try:
        config = get_config()
    except Exception as e:
        return [f"Failed to load config: {e}"]

    # Check Notion configuration if active
    if config.active_backend == "notion":
        if config.backends.notion is None:
            issues.append(
                "Notion is the active backend but not configured. "
                "Add [backends.notion] section to config."
            )
        else:
            # Check for token
            try:
                get_backend_token("notion")
            except ConfigError:
                issues.append(
                    f"Notion token not found. Set {ENV_NOTION_TOKEN} or "
                    f"{ENV_NOTION_TOKEN_FALLBACK} environment variable."
                )

    return issues


def save_config(config: JarvisConfig, config_path: Path | None = None) -> Path:
    """Save configuration to YAML file.

    Args:
        config: JarvisConfig instance to save
        config_path: Optional path for config file. Uses default if None.

    Returns:
        Path to the saved config file.
    """
    path = config_path or get_config_path()

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict, excluding None values and env-only settings
    config_dict = config.model_dump(
        exclude_none=True,
        exclude_unset=False,
    )

    # Write YAML with nice formatting
    with open(path, "w") as f:
        f.write("# Jarvis Configuration\n")
        f.write("# ====================\n")
        f.write("# Secrets (API tokens) should be set via environment variables.\n\n")
        yaml.dump(
            config_dict,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    # Clear cache so next load picks up changes
    clear_config_cache()

    return path


def set_active_backend(backend: str, config_path: Path | None = None) -> JarvisConfig:
    """Set the active backend in configuration.

    Args:
        backend: Backend name (anytype, notion)
        config_path: Optional path for config file. Uses default if None.

    Returns:
        Updated JarvisConfig instance.

    Raises:
        ConfigError: If backend is invalid.
    """
    from .defaults import VALID_BACKENDS

    if backend not in VALID_BACKENDS:
        raise ConfigError(
            f"Invalid backend: {backend}. Valid options: {', '.join(sorted(VALID_BACKENDS))}"
        )

    # Load current config
    config = load_config(config_path, reload=True)

    # Create new config with updated backend
    config_dict = config.model_dump()
    config_dict["active_backend"] = backend

    new_config = JarvisConfig(**config_dict)

    # Save to file
    save_config(new_config, config_path)

    return new_config
