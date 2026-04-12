"""Compilation manifest store for tracking source file hashes and compile state.

Reads and writes .state/manifest.json inside a domain root, allowing the
compiler to skip unchanged source files on subsequent runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from jarvis.wiki.models import CompilationFileRecord, CompilationManifest

_MANIFEST_PATH = ".state/manifest.json"


class ManifestStore:
    """Persist and query the compilation manifest for a wiki domain."""

    @staticmethod
    def _path(domain_root: Path) -> Path:
        return domain_root / _MANIFEST_PATH

    @classmethod
    def load(cls, domain_root: Path) -> CompilationManifest:
        """Load the manifest from disk, or return an empty one if absent.

        Args:
            domain_root: Root directory of the wiki domain

        Returns:
            Parsed CompilationManifest (empty if file does not exist)
        """
        manifest_path = cls._path(domain_root)
        if not manifest_path.exists():
            # Infer domain name from directory
            return CompilationManifest(domain=domain_root.name)

        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        return CompilationManifest.model_validate(raw)

    @classmethod
    def save(cls, domain_root: Path, manifest: CompilationManifest) -> None:
        """Persist the manifest to disk.

        Args:
            domain_root: Root directory of the wiki domain
            manifest: CompilationManifest to write
        """
        manifest_path = cls._path(domain_root)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )

    @classmethod
    def needs_compile(cls, domain_root: Path, raw_path: Path) -> bool:
        """Check whether a source file needs recompilation.

        Computes the SHA-256 of the file and compares it against the stored
        hash. Returns True if the file is new or has changed.

        Args:
            domain_root: Root directory of the wiki domain
            raw_path: Absolute path to the raw source file

        Returns:
            True if the file should be compiled; False if unchanged
        """
        manifest = cls.load(domain_root)
        key = str(raw_path)

        if key not in manifest.files:
            return True

        current_hash = _sha256(raw_path)
        return current_hash != manifest.files[key].hash

    @classmethod
    def record(
        cls,
        domain_root: Path,
        raw_path: Path,
        compiled_to: list[str],
        token_cost: dict[str, int],
    ) -> None:
        """Update the manifest entry for a compiled source file.

        Args:
            domain_root: Root directory of the wiki domain
            raw_path: Absolute path to the raw source file
            compiled_to: List of output file paths generated from this source
            token_cost: Dict of token usage by stage (e.g. {"summarize_input": 1200})
        """
        manifest = cls.load(domain_root)
        key = str(raw_path)

        manifest.files[key] = CompilationFileRecord(
            hash=_sha256(raw_path),
            size_bytes=raw_path.stat().st_size,
            last_compiled=datetime.utcnow(),
            compiled_to=compiled_to,
            token_cost=token_cost,
        )
        cls.save(domain_root, manifest)

    @classmethod
    def mark_full_compile(cls, domain_root: Path) -> None:
        """Stamp the manifest's `last_full_compile` to now.

        Called by the compiler at the end of a successful compile run that
        processed (or evaluated) every raw source — i.e. when no `source`
        filter was passed.
        """
        manifest = cls.load(domain_root)
        manifest.last_full_compile = datetime.utcnow()
        cls.save(domain_root, manifest)


def _sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()
