"""Preset registry for `jarvis sync`.

Presets live in ``~/.jarvis/sync/presets.yaml``. A preset has a name, an
optional source path (``None`` means prompt-at-run-time), an optional
destination Anytype link (same), an ignore list, and options.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from jarvis.sync.object_link import AnytypeLink, parse_link


def get_presets_path() -> Path:
    """Return the canonical presets file path."""
    return Path.home() / ".jarvis" / "sync" / "presets.yaml"


class PresetOptions(BaseModel):
    """Per-preset options that don't change the contract of the preset itself."""

    include_extensions: list[str] = Field(
        default_factory=lambda: [".md", ".txt", ".markdown", ".text"],
        description="File extensions to include during sync.",
    )


class Preset(BaseModel):
    """A named source→destination mapping. Either side may be None (prompt at run time)."""

    name: str = Field(description="Slug-safe unique identifier.")
    source: Path | None = Field(
        default=None,
        description="Source path; None means ask at run-time.",
    )
    destination: str | None = Field(
        default=None,
        description="Anytype object link; None means ask at run-time.",
    )
    ignore: list[str] = Field(
        default_factory=lambda: [".git", ".DS_Store", "node_modules"],
        description="Glob patterns to skip during walk.",
    )
    options: PresetOptions = Field(default_factory=PresetOptions)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("preset name cannot be empty")
        if any(c in v for c in (" ", "/", "\\", ":")):
            raise ValueError(
                f"preset name must be slug-safe (no spaces, slashes, colons): {v!r}"
            )
        return v

    @field_validator("destination")
    @classmethod
    def _validate_destination(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parse_link(v)  # raises if malformed
        return v

    def resolved_destination(self) -> AnytypeLink | None:
        if self.destination is None:
            return None
        return parse_link(self.destination)


class PresetRegistry(BaseModel):
    """The full set of saved presets, persisted to a single YAML file."""

    version: int = 1
    presets: list[Preset] = Field(default_factory=list)

    def get(self, name: str) -> Preset | None:
        for p in self.presets:
            if p.name == name:
                return p
        return None

    def upsert(self, preset: Preset) -> None:
        for i, p in enumerate(self.presets):
            if p.name == preset.name:
                self.presets[i] = preset
                return
        self.presets.append(preset)

    def remove(self, name: str) -> bool:
        for i, p in enumerate(self.presets):
            if p.name == name:
                del self.presets[i]
                return True
        return False


def load_registry(path: Path | None = None) -> PresetRegistry:
    """Load the registry from disk, returning an empty one if the file is absent."""
    path = path or get_presets_path()
    if not path.exists():
        return PresetRegistry()
    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}
    return PresetRegistry.model_validate(data)


def save_registry(registry: PresetRegistry, path: Path | None = None) -> None:
    """Persist the registry to disk, creating parent dirs as needed."""
    path = path or get_presets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = registry.model_dump(mode="json", exclude_none=False)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
