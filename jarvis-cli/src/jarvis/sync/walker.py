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

WalkKind = Literal["file", "directory", "unsupported_file"]


@dataclass(frozen=True)
class WalkItem:
    """One entry in a sync walk."""

    relpath: str  # POSIX-style, relative to the walk root
    kind: WalkKind
    content: str | None  # None for directories and unsupported files
    abspath: Path
    skip_reason: str | None = None


def walk(
    source: Path,
    include_extensions: list[str],
    ignore: list[str],
    include_unsupported: bool = False,
) -> Iterator[WalkItem]:
    """Yield items under ``source`` in preorder.

    - If ``source`` is a single file with a matching extension, yield one file item.
    - If ``source`` is a directory, walk it preorder: each directory is yielded
      before its contents. Files whose extension isn't in ``include_extensions``
      are skipped silently. Any path matching an ignore glob is skipped.
    - If ``include_unsupported`` is True, unsupported files are yielded as
      ``unsupported_file`` items so callers can report them instead of silently
      skipping them.
    """
    source = source.resolve()
    if source.is_file():
        if _matches_any(source.name, ignore):
            return
        if not _has_extension(source, include_extensions):
            if include_unsupported:
                yield _unsupported(source.name, source, "extension is not included")
            return
        content, reason = _try_read_text(source, strict=include_unsupported)
        if reason is not None:
            if include_unsupported:
                yield _unsupported(source.name, source, reason)
            return
        if content is not None:
            yield WalkItem(
                relpath=source.name,
                kind="file",
                content=content,
                abspath=source,
            )
        return

    if not source.is_dir():
        return

    yield from _walk_dir(source, source, include_extensions, ignore, include_unsupported)


def _walk_dir(
    root: Path,
    current: Path,
    include_extensions: list[str],
    ignore: list[str],
    include_unsupported: bool,
) -> Iterator[WalkItem]:
    # Sort directories first, then files, by lowercase name. Stable across runs.
    entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        rel = entry.relative_to(root).as_posix()
        if _matches_any(entry.name, ignore) or _matches_any(rel, ignore):
            continue
        if entry.is_dir():
            yield WalkItem(relpath=rel, kind="directory", content=None, abspath=entry)
            yield from _walk_dir(root, entry, include_extensions, ignore, include_unsupported)
        elif entry.is_file():
            if not _has_extension(entry, include_extensions):
                if include_unsupported:
                    yield _unsupported(rel, entry, "extension is not included")
                continue
            content, reason = _try_read_text(entry, strict=include_unsupported)
            if reason is not None:
                if include_unsupported:
                    yield _unsupported(rel, entry, reason)
                continue
            yield WalkItem(
                relpath=rel,
                kind="file",
                content=content,
                abspath=entry,
            )


def _has_extension(path: Path, exts: list[str]) -> bool:
    name = path.name.lower()
    return any(name.endswith(ext.lower()) for ext in exts)


def _matches_any(name_or_path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name_or_path, pat) for pat in patterns)


def _read_text(path: Path) -> str:
    # We promised markdown/text only — utf-8 decode is the right default.
    # The legacy non-reporting mode preserves old behavior by replacing stray bytes.
    return path.read_text(encoding="utf-8", errors="replace")


def _try_read_text(path: Path, *, strict: bool) -> tuple[str | None, str | None]:
    """Return text content or a reason the file cannot be safely synced as text."""
    if not strict:
        return _read_text(path), None
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, "not valid UTF-8 text"
    except OSError as e:
        return None, str(e)


def _unsupported(relpath: str, abspath: Path, reason: str) -> WalkItem:
    return WalkItem(
        relpath=relpath,
        kind="unsupported_file",
        content=None,
        abspath=abspath,
        skip_reason=reason,
    )
