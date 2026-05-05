"""Per-preset sync state, stored as JSON sidecar files.

State is keyed by POSIX-style relative path (not absolute) so a preset survives
the source folder being moved or shared across machines.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ObjectKind = Literal["page", "collection"]


def get_state_dir() -> Path:
    return Path.home() / ".jarvis" / "sync" / "state"


def get_state_path(preset_name: str) -> Path:
    safe = preset_name.strip() if preset_name and preset_name.strip() else "_adhoc"
    return get_state_dir() / f"{safe}.json"


class ObjectRecord(BaseModel):
    """One synced source path's mapping to an Anytype object."""

    object_id: str = Field(description="Anytype object ID for this path.")
    kind: ObjectKind = Field(description="page or collection.")
    content_sha256: str | None = Field(
        default=None,
        description="Hex sha256 of last-synced body. None for collections.",
    )
    last_synced_at: str = Field(description="ISO-8601 UTC timestamp.")


class SyncState(BaseModel):
    """The state file for a single preset (or _adhoc run)."""

    preset: str = Field(description="Preset name, or '_adhoc' for ad-hoc runs.")
    destination_object_id: str = Field(description="Root container's Anytype id.")
    space_id: str = Field(description="Anytype Space id the destination lives in.")
    last_synced_at: str = Field(description="ISO-8601 UTC timestamp of the most recent sync.")
    objects: dict[str, ObjectRecord] = Field(
        default_factory=dict,
        description="POSIX-style relpath -> ObjectRecord.",
    )


def load_state(preset_name: str, path: Path | None = None) -> SyncState | None:
    """Load state for a preset, or None if no state file exists yet."""
    path = path or get_state_path(preset_name)
    if not path.exists():
        return None
    return SyncState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(state: SyncState, path: Path | None = None) -> None:
    """Persist state to its sidecar JSON file."""
    path = path or get_state_path(state.preset)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def compute_content_sha256(content: str) -> str:
    """Stable hex digest of UTF-8-encoded content. Used to short-circuit no-op updates."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def now_iso() -> str:
    """ISO-8601 UTC timestamp (e.g. '2026-04-28T01:23:45.678901+00:00')."""
    return datetime.now(UTC).isoformat()
