"""File-tree walker for `jarvis sync`.

Yields items in preorder so collections can be created before their children.
Filters by include_extensions; skips paths matching any ignore glob.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

WalkKind = Literal["file", "directory"]


@dataclass(frozen=True)
class WalkItem:
    """One entry in a sync walk."""

    relpath: str  # POSIX-style, relative to the walk root
    kind: WalkKind
    content: str | None  # None for directories
    abspath: Path


def walk(
    source: Path,
    include_extensions: list[str],
    ignore: list[str],
) -> Iterator[WalkItem]:
    """Yield items under ``source`` in preorder.

    - If ``source`` is a single file with a matching extension, yield one file item.
    - If ``source`` is a directory, walk it preorder: each directory is yielded
      before its contents. Files whose extension isn't in ``include_extensions``
      are skipped silently. Any path matching an ignore glob is skipped.
    """
    source = source.resolve()
    if source.is_file():
        if _has_extension(source, include_extensions) and not _matches_any(
            source.name, ignore
        ):
            yield WalkItem(
                relpath=source.name,
                kind="file",
                content=_read_text(source),
                abspath=source,
            )
        return

    if not source.is_dir():
        return

    yield from _walk_dir(source, source, include_extensions, ignore)


def _walk_dir(
    root: Path,
    current: Path,
    include_extensions: list[str],
    ignore: list[str],
) -> Iterator[WalkItem]:
    # Sort directories first, then files, by lowercase name. Stable across runs.
    entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        rel = entry.relative_to(root).as_posix()
        if _matches_any(entry.name, ignore) or _matches_any(rel, ignore):
            continue
        if entry.is_dir():
            yield WalkItem(relpath=rel, kind="directory", content=None, abspath=entry)
            yield from _walk_dir(root, entry, include_extensions, ignore)
        elif entry.is_file() and _has_extension(entry, include_extensions):
            yield WalkItem(
                relpath=rel,
                kind="file",
                content=_read_text(entry),
                abspath=entry,
            )


def _has_extension(path: Path, exts: list[str]) -> bool:
    name = path.name.lower()
    return any(name.endswith(ext.lower()) for ext in exts)


def _matches_any(name_or_path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name_or_path, pat) for pat in patterns)


def _read_text(path: Path) -> str:
    # We promised markdown/text only — utf-8 decode is the right default.
    # Surrogateescape lets us not crash on stray bytes; the engine logs and skips.
    return path.read_text(encoding="utf-8", errors="replace")
