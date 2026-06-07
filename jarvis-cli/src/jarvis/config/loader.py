"""Configuration loading from YAML files and environment variables."""

import os
import shlex
from pathlib import Path

import yaml

from .defaults import (
    DEFAULT_CONFIG_YAML,
    ENV_NOTION_TOKEN,
    ENV_NOTION_TOKEN_FALLBACK,
)
from .fathom_setup import default_env_file_path
from .schema import JarvisConfig, WhatsAppAccountConfig, get_config_path
from .whatsapp_setup import default_whatsapp_env_file_path


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


def get_fathom_api_key(account: str | None = None) -> str:
    """Resolve a Fathom API key from named-account config or fallback env vars."""

    cfg = get_config()
    target_account = account or cfg.fathom.default_account

    if target_account:
        acct = cfg.fathom.accounts.get(target_account)
        if acct is None:
            raise ConfigError(
                f"Unknown Fathom account: {target_account}. "
                f"Add it under fathom.accounts in ~/.jarvis/config.yaml",
                backend="fathom",
            )
        token = os.environ.get(acct.api_key_env_var)
        if not token:
            token = _load_managed_env_var(acct.api_key_env_var)
        if token:
            return token
        raise ConfigError(
            f"Fathom API key not found for account '{target_account}'. "
            f"Set {acct.api_key_env_var} environment variable.",
            backend="fathom",
        )

    token = os.environ.get("FATHOM_API_KEY") or os.environ.get("JARVIS_FATHOM_API_KEY")
    if not token:
        token = _load_managed_env_var("FATHOM_API_KEY") or _load_managed_env_var(
            "JARVIS_FATHOM_API_KEY"
        )
    if token:
        return token
    raise ConfigError(
        "No Fathom API key found. Set FATHOM_API_KEY, JARVIS_FATHOM_API_KEY, "
        "or configure fathom.accounts in ~/.jarvis/config.yaml.",
        backend="fathom",
    )


def get_fathom_webhook_secret(account: str | None = None) -> str:
    """Resolve a Fathom webhook secret from named-account config or fallback env vars."""

    cfg = get_config()
    target_account = account or cfg.fathom.default_account

    if target_account:
        acct = cfg.fathom.accounts.get(target_account)
        if acct is None:
            raise ConfigError(
                f"Unknown Fathom account: {target_account}. "
                f"Add it under fathom.accounts in ~/.jarvis/config.yaml",
                backend="fathom",
            )
        secret = os.environ.get(acct.webhook_secret_env_var)
        if not secret:
            secret = _load_managed_env_var(acct.webhook_secret_env_var)
        if secret:
            return secret
        raise ConfigError(
            f"Fathom webhook secret not found for account '{target_account}'. "
            f"Set {acct.webhook_secret_env_var} environment variable.",
            backend="fathom",
        )

    secret = os.environ.get("FATHOM_WEBHOOK_SECRET") or os.environ.get(
        "JARVIS_FATHOM_WEBHOOK_SECRET"
    )
    if not secret:
        secret = _load_managed_env_var("FATHOM_WEBHOOK_SECRET") or _load_managed_env_var(
            "JARVIS_FATHOM_WEBHOOK_SECRET"
        )
    if secret:
        return secret
    raise ConfigError(
        "No Fathom webhook secret found. Set FATHOM_WEBHOOK_SECRET, "
        "JARVIS_FATHOM_WEBHOOK_SECRET, or configure fathom.accounts in ~/.jarvis/config.yaml.",
        backend="fathom",
    )


def get_whatsapp_account_config(account: str | None = None) -> WhatsAppAccountConfig:
    """Resolve a WhatsApp account configuration, using generic fallbacks when unnamed."""

    cfg = get_config()
    target_account = account or cfg.whatsapp.default_account
    if target_account:
        acct = cfg.whatsapp.accounts.get(target_account)
        if acct is None:
            raise ConfigError(
                f"Unknown WhatsApp account: {target_account}. "
                f"Add it under whatsapp.accounts in ~/.jarvis/config.yaml",
                backend="whatsapp",
            )
        return acct
    return WhatsAppAccountConfig()


def get_whatsapp_access_token(account: str | None = None) -> str:
    """Resolve a Meta WhatsApp Cloud API access token."""

    acct = get_whatsapp_account_config(account)
    token = os.environ.get(acct.access_token_env_var)
    if not token:
        token = _load_managed_whatsapp_env_var(acct.access_token_env_var)
    if token:
        return token
    target_account = account or get_config().whatsapp.default_account
    if target_account:
        raise ConfigError(
            f"WhatsApp access token not found for account '{target_account}'. "
            f"Set {acct.access_token_env_var} environment variable.",
            backend="whatsapp",
        )

    token = (
        os.environ.get("JARVIS_WHATSAPP_META_TOKEN")
        or os.environ.get("WHATSAPP_META_TOKEN")
        or os.environ.get("WHATSAPP_ACCESS_TOKEN")
    )
    if token:
        return token
    raise ConfigError(
        "No WhatsApp access token found. Set JARVIS_WHATSAPP_META_TOKEN "
        "or configure whatsapp.accounts in ~/.jarvis/config.yaml.",
        backend="whatsapp",
    )


def get_whatsapp_app_secret(account: str | None = None) -> str:
    """Resolve a Meta app secret for WhatsApp webhook signature checks."""

    acct = get_whatsapp_account_config(account)
    secret = os.environ.get(acct.app_secret_env_var)
    if not secret:
        secret = _load_managed_whatsapp_env_var(acct.app_secret_env_var)
    if secret:
        return secret
    target_account = account or get_config().whatsapp.default_account
    if target_account:
        raise ConfigError(
            f"WhatsApp app secret not found for account '{target_account}'. "
            f"Set {acct.app_secret_env_var} environment variable.",
            backend="whatsapp",
        )

    secret = os.environ.get("JARVIS_WHATSAPP_META_APP_SECRET") or os.environ.get(
        "WHATSAPP_META_APP_SECRET"
    )
    if secret:
        return secret
    raise ConfigError(
        "No WhatsApp app secret found. Set JARVIS_WHATSAPP_META_APP_SECRET "
        "or configure whatsapp.accounts in ~/.jarvis/config.yaml.",
        backend="whatsapp",
    )


def get_whatsapp_verify_token(account: str | None = None) -> str:
    """Resolve the local webhook verification token expected from Meta."""

    acct = get_whatsapp_account_config(account)
    token = os.environ.get(acct.verify_token_env_var)
    if not token:
        token = _load_managed_whatsapp_env_var(acct.verify_token_env_var)
    if token:
        return token
    target_account = account or get_config().whatsapp.default_account
    if target_account:
        raise ConfigError(
            f"WhatsApp verify token not found for account '{target_account}'. "
            f"Set {acct.verify_token_env_var} environment variable.",
            backend="whatsapp",
        )

    token = os.environ.get("JARVIS_WHATSAPP_VERIFY_TOKEN") or os.environ.get(
        "WHATSAPP_VERIFY_TOKEN"
    )
    if token:
        return token
    raise ConfigError(
        "No WhatsApp webhook verify token found. Set JARVIS_WHATSAPP_VERIFY_TOKEN "
        "or configure whatsapp.accounts in ~/.jarvis/config.yaml.",
        backend="whatsapp",
    )


def get_whatsapp_phone_number_id(account: str | None = None) -> str:
    """Resolve the Meta WhatsApp phone number ID for outbound sends."""

    acct = get_whatsapp_account_config(account)
    if acct.phone_number_id:
        return acct.phone_number_id
    fallback = os.environ.get("JARVIS_WHATSAPP_PHONE_NUMBER_ID") or os.environ.get(
        "WHATSAPP_PHONE_NUMBER_ID"
    )
    if fallback:
        return fallback
    target_account = account or get_config().whatsapp.default_account
    suffix = f" for account '{target_account}'" if target_account else ""
    raise ConfigError(
        f"WhatsApp phone number ID not configured{suffix}. "
        "Set phone_number_id under whatsapp.accounts or JARVIS_WHATSAPP_PHONE_NUMBER_ID.",
        backend="whatsapp",
    )


def _load_managed_env_var(name: str) -> str | None:
    """Read a single exported variable from the managed Fathom env file."""

    return _load_managed_env_var_from_file(name, default_env_file_path())


def _load_managed_whatsapp_env_var(name: str) -> str | None:
    """Read a single exported variable from the managed WhatsApp env file."""

    return _load_managed_env_var_from_file(name, default_whatsapp_env_file_path())


def _load_managed_env_var_from_file(name: str, env_file: Path) -> str | None:
    """Read a single exported variable from a managed shell env file."""

    if not name:
        return None
    if not env_file.exists():
        return None
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("export "):
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue
        if len(tokens) < 2:
            continue
        assignment = tokens[1]
        if "=" not in assignment:
            continue
        key, value = assignment.split("=", 1)
        if key == name:
            return value
    return None


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
