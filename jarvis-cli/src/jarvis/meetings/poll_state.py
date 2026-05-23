"""Persistent state for Fathom polling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_poll_state_path() -> Path:
    """Return the default per-user Fathom poll state path."""

    return Path.home() / ".jarvis" / "state" / "fathom" / "poll-state.json"


def load_poll_state(path: Path | None = None) -> dict[str, Any]:
    """Load Fathom poll state, returning an empty state when absent."""

    state_path = path or default_poll_state_path()
    if not state_path.exists():
        return {"version": 1, "accounts": {}}
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "accounts": {}}
    if not isinstance(loaded, dict):
        return {"version": 1, "accounts": {}}
    accounts = loaded.get("accounts")
    if not isinstance(accounts, dict):
        loaded["accounts"] = {}
    loaded.setdefault("version", 1)
    return loaded


def save_poll_state(state: dict[str, Any], path: Path | None = None) -> Path:
    """Persist Fathom poll state atomically enough for local cron usage."""

    state_path = path or default_poll_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(state_path)
    return state_path


def poll_account_key(account: str | None) -> str:
    """Return the stable state key for an account label."""

    return account or "__default__"
