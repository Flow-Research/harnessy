"""Helpers for interactive WhatsApp channel setup."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from .fathom_setup import (
    default_env_var,
    ensure_shell_profile_sources_env,
    escape_shell_value,
    write_env_file,
)
from .schema import JarvisConfig, WhatsAppAccountConfig


@dataclass
class WhatsAppSetupAccount:
    """Resolved setup data for one WhatsApp account."""

    name: str
    phone_number_id: str
    business_account_id: str
    access_token_env_var: str
    app_secret_env_var: str
    verify_token_env_var: str
    access_token: str = ""
    app_secret: str = ""
    verify_token: str = ""


def normalize_whatsapp_accounts(config: JarvisConfig) -> list[WhatsAppSetupAccount]:
    """Fill missing env var names with safe defaults and return setup records."""

    accounts: list[WhatsAppSetupAccount] = []
    for name, account in config.whatsapp.accounts.items():
        access_var = account.access_token_env_var or default_env_var(
            "JARVIS_WHATSAPP_META_TOKEN",
            name,
        )
        app_secret_var = account.app_secret_env_var or default_env_var(
            "JARVIS_WHATSAPP_META_APP_SECRET",
            name,
        )
        verify_var = account.verify_token_env_var or default_env_var(
            "JARVIS_WHATSAPP_VERIFY_TOKEN",
            name,
        )
        account.access_token_env_var = access_var
        account.app_secret_env_var = app_secret_var
        account.verify_token_env_var = verify_var
        accounts.append(
            WhatsAppSetupAccount(
                name=name,
                phone_number_id=account.phone_number_id or "",
                business_account_id=account.business_account_id or "",
                access_token_env_var=access_var,
                app_secret_env_var=app_secret_var,
                verify_token_env_var=verify_var,
            )
        )
    return accounts


def ensure_default_whatsapp_accounts(config: JarvisConfig) -> list[WhatsAppSetupAccount]:
    """Seed a minimal personal WhatsApp account when no accounts exist."""

    if not config.whatsapp.accounts:
        config.whatsapp.accounts["personal"] = WhatsAppAccountConfig(
            access_token_env_var=default_env_var("JARVIS_WHATSAPP_META_TOKEN", "personal"),
            app_secret_env_var=default_env_var(
                "JARVIS_WHATSAPP_META_APP_SECRET",
                "personal",
            ),
            verify_token_env_var=default_env_var(
                "JARVIS_WHATSAPP_VERIFY_TOKEN",
                "personal",
            ),
        )
    if config.whatsapp.default_account is None:
        config.whatsapp.default_account = next(iter(config.whatsapp.accounts), "personal")
    return normalize_whatsapp_accounts(config)


def render_whatsapp_env_file(accounts: list[WhatsAppSetupAccount]) -> str:
    """Render the managed env file content for provided WhatsApp secrets."""

    lines = [
        "# Jarvis-managed WhatsApp environment",
        "# Source this file from your shell profile to activate WhatsApp accounts.",
        "",
    ]
    for account in accounts:
        if account.access_token:
            lines.append(
                f'export {account.access_token_env_var}="'
                f'{escape_shell_value(account.access_token)}"'
            )
        if account.app_secret:
            lines.append(
                f'export {account.app_secret_env_var}="{escape_shell_value(account.app_secret)}"'
            )
        if account.verify_token:
            lines.append(
                f'export {account.verify_token_env_var}="'
                f'{escape_shell_value(account.verify_token)}"'
            )
        if account.access_token or account.app_secret or account.verify_token:
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def default_whatsapp_env_file_path() -> Path:
    """Default managed env file path for WhatsApp secrets."""

    return Path.home() / ".jarvis" / "env" / "whatsapp.zsh"


def generate_whatsapp_verify_token() -> str:
    """Generate a local Meta webhook verification token."""

    return secrets.token_urlsafe(32)


__all__ = [
    "WhatsAppSetupAccount",
    "default_whatsapp_env_file_path",
    "ensure_default_whatsapp_accounts",
    "ensure_shell_profile_sources_env",
    "generate_whatsapp_verify_token",
    "normalize_whatsapp_accounts",
    "render_whatsapp_env_file",
    "write_env_file",
]
