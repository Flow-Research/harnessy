"""Helpers for interactive Fathom multi-account setup."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .schema import FathomAccountConfig, JarvisConfig


@dataclass
class FathomSetupAccount:
    """Resolved setup data for a single Fathom account."""

    name: str
    email: str
    api_key_env_var: str
    webhook_secret_env_var: str
    api_key: str = ""
    webhook_secret: str = ""


def default_env_var(prefix: str, account_name: str) -> str:
    """Build a conventional env var name from an account slug."""

    slug = "_".join(part for part in account_name.upper().replace("-", "_").split("_") if part)
    return f"{prefix}_{slug}" if slug else prefix


def normalize_fathom_accounts(config: JarvisConfig) -> list[FathomSetupAccount]:
    """Fill missing env var names with safe defaults and return setup records."""

    accounts: list[FathomSetupAccount] = []
    for name, account in config.fathom.accounts.items():
        api_var = account.api_key_env_var or default_env_var("FATHOM_API_KEY", name)
        webhook_var = account.webhook_secret_env_var or default_env_var(
            "FATHOM_WEBHOOK_SECRET", name
        )
        account.api_key_env_var = api_var
        account.webhook_secret_env_var = webhook_var
        accounts.append(
            FathomSetupAccount(
                name=name,
                email=account.email or "",
                api_key_env_var=api_var,
                webhook_secret_env_var=webhook_var,
            )
        )
    return accounts


def ensure_default_accounts(config: JarvisConfig) -> list[FathomSetupAccount]:
    """Seed a minimal personal/work config when no accounts exist."""

    if config.fathom.accounts:
        return normalize_fathom_accounts(config)

    defaults = {
        "personal": FathomAccountConfig(
            email="",
            api_key_env_var=default_env_var("FATHOM_API_KEY", "personal"),
            webhook_secret_env_var=default_env_var("FATHOM_WEBHOOK_SECRET", "personal"),
        ),
        "work": FathomAccountConfig(
            email="",
            api_key_env_var=default_env_var("FATHOM_API_KEY", "work"),
            webhook_secret_env_var=default_env_var("FATHOM_WEBHOOK_SECRET", "work"),
        ),
    }
    config.fathom.accounts.update(defaults)
    if config.fathom.default_account is None:
        config.fathom.default_account = "personal"
    return normalize_fathom_accounts(config)


def render_fathom_env_file(accounts: list[FathomSetupAccount]) -> str:
    """Render the managed env file content for provided account secrets."""

    lines = [
        "# Jarvis-managed Fathom environment",
        "# Source this file from your shell profile to activate Fathom accounts.",
        "",
    ]
    for account in accounts:
        if account.api_key:
            lines.append(
                f'export {account.api_key_env_var}="{escape_shell_value(account.api_key)}"'
            )
        if account.webhook_secret:
            lines.append(
                f'export {account.webhook_secret_env_var}="'
                f'{escape_shell_value(account.webhook_secret)}"'
            )
        if account.api_key or account.webhook_secret:
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def escape_shell_value(value: str) -> str:
    """Escape a value for inclusion inside double-quoted shell exports."""

    return value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")


def write_env_file(path: Path, content: str) -> Path:
    """Write a managed env file with restrictive permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def update_managed_env_var(path: Path, name: str, value: str) -> Path:
    """Upsert one exported variable in the managed Fathom env file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    export_line = f'export {name}="{escape_shell_value(value)}"'
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"export {name}="):
            next_lines.append(export_line)
            updated = True
        else:
            next_lines.append(line)

    if not updated:
        if next_lines and next_lines[-1].strip():
            next_lines.append("")
        if not next_lines:
            next_lines.extend(
                [
                    "# Jarvis-managed Fathom environment",
                    "# Source this file from your shell profile to activate Fathom accounts.",
                    "",
                ]
            )
        next_lines.append(export_line)

    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def ensure_shell_profile_sources_env(profile_path: Path, env_file_path: Path) -> bool:
    """Ensure a shell profile sources the managed env file exactly once."""

    source_line = f'[[ -f "{env_file_path}" ]] && source "{env_file_path}"'
    existing = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
    if source_line in existing:
        return False
    prefix = existing.rstrip() + ("\n\n" if existing.strip() else "")
    profile_path.write_text(prefix + source_line + "\n", encoding="utf-8")
    return True


def default_env_file_path() -> Path:
    """Default managed env file path for Fathom secrets."""

    return Path.home() / ".jarvis" / "env" / "fathom.zsh"


def default_shell_profile_path() -> Path:
    """Choose a default shell profile path based on the active shell."""

    shell = os.environ.get("SHELL", "")
    if shell.endswith("zsh"):
        return Path.home() / ".zshrc"
    if shell.endswith("bash"):
        return Path.home() / ".bashrc"
    return Path.home() / ".profile"
