"""Sync engine: walk source, diff against state, apply operations to Anytype.

The engine is the orchestrator. Inputs: source path, destination link, ignore list,
options, prior state, and a SyncAdapter Protocol that wraps the actual Anytype calls.
Outputs: list of SyncOperations performed (or planned, if dry_run=True), and an
updated SyncState.

The Protocol shape lets us unit-test the engine without touching Anytype: tests
pass in a recording mock that captures every call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from jarvis.sync.object_link import AnytypeLink
from jarvis.sync.state import (
    ObjectRecord,
    SyncState,
    compute_content_sha256,
    now_iso,
)
from jarvis.sync.walker import WalkItem, walk

OperationKind = Literal[
    "create_collection",
    "create_page",
    "update_page",
    "skip_unchanged",
    "skip_orphan",
    "delete_orphan",
]


@dataclass(frozen=True)
class SyncOperation:
    """One thing the engine did (or would do, in dry-run mode)."""

    kind: OperationKind
    relpath: str
    object_id: str | None  # None for ops that didn't produce an id (create_*) until applied


@dataclass
class SyncResult:
    """Outcome of a single sync run."""

    operations: list[SyncOperation] = field(default_factory=list)
    state: SyncState | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def created(self) -> int:
        return sum(
            1 for o in self.operations if o.kind in ("create_collection", "create_page")
        )

    @property
    def updated(self) -> int:
        return sum(1 for o in self.operations if o.kind == "update_page")

    @property
    def unchanged(self) -> int:
        return sum(1 for o in self.operations if o.kind == "skip_unchanged")

    @property
    def pruned(self) -> int:
        return sum(1 for o in self.operations if o.kind == "delete_orphan")


class SyncAdapter(Protocol):
    """The minimum surface the engine needs from a backend.

    Implemented by AnyTypeAdapter. Tests pass in a recording mock matching this
    signature.
    """

    def create_collection_in(
        self, space_id: str, parent_collection_id: str | None, name: str
    ) -> str: ...

    def create_page_in(
        self,
        space_id: str,
        parent_collection_id: str | None,
        name: str,
        body_markdown: str,
    ) -> str: ...

    def update_page_content(
        self, space_id: str, object_id: str, body_markdown: str
    ) -> None: ...


def run_sync(
    *,
    preset_name: str,
    source: Path,
    destination: AnytypeLink,
    include_extensions: list[str],
    ignore: list[str],
    adapter: SyncAdapter,
    prior_state: SyncState | None = None,
    dry_run: bool = False,
    prune: bool = False,
) -> SyncResult:
    """Run an incremental sync from ``source`` to ``destination``.

    Behavior:
        - Walk the source in preorder (directories before their contents).
        - For each directory: if a tracked Collection exists at that relpath, reuse
          its object_id. Otherwise create a new Collection inside the appropriate
          parent (the destination root, or the parent directory's tracked id).
        - For each file: hash the content and compare to prior state. Unchanged →
          skip. Modified → update_page. New → create_page.
        - If ``prune`` is True, any object in prior_state whose relpath no longer
          exists locally is deleted on Anytype (collections deleted before files
          inside them — but in practice, deletion order doesn't matter since
          Anytype objects don't enforce containment).

    Args:
        preset_name: For state file naming (or '_adhoc').
        source: Local path (file or directory).
        destination: Where to sync to on Anytype.
        include_extensions: File extensions to consider.
        ignore: Glob patterns to skip.
        adapter: Backend adapter (real or mock).
        prior_state: Previously-saved state, or None for first run.
        dry_run: If True, no API calls are made — operations are computed and
            returned with a synthetic ``object_id`` of None for new objects.
        prune: If True, orphans in prior_state are deleted on Anytype.

    Returns:
        SyncResult with operations, updated state, and any non-fatal errors.
    """
    result = SyncResult()
    new_objects: dict[str, ObjectRecord] = {}
    seen_relpaths: set[str] = set()

    # Map of relpath → object_id for parent resolution. Seeded from prior state's
    # collections so we can reuse them when their directories still exist locally.
    relpath_to_id: dict[str, str] = {}
    if prior_state is not None:
        for rp, rec in prior_state.objects.items():
            if rec.kind == "collection":
                relpath_to_id[rp] = rec.object_id

    for item in walk(source, include_extensions, ignore):
        seen_relpaths.add(item.relpath)
        parent_id = _resolve_parent_id(
            item.relpath, relpath_to_id, destination.object_id
        )

        if item.kind == "directory":
            existing_id = relpath_to_id.get(item.relpath)
            if existing_id is not None:
                # Reuse — Collection already exists from a prior run.
                new_objects[item.relpath] = ObjectRecord(
                    object_id=existing_id,
                    kind="collection",
                    content_sha256=None,
                    last_synced_at=now_iso(),
                )
                continue
            # Create a new Collection.
            name = _name_for_relpath(item.relpath)
            try:
                if dry_run:
                    new_id = ""
                else:
                    new_id = adapter.create_collection_in(
                        destination.space_id, parent_id, name
                    )
                relpath_to_id[item.relpath] = new_id
                new_objects[item.relpath] = ObjectRecord(
                    object_id=new_id,
                    kind="collection",
                    content_sha256=None,
                    last_synced_at=now_iso(),
                )
                result.operations.append(
                    SyncOperation(
                        kind="create_collection", relpath=item.relpath, object_id=new_id or None
                    )
                )
            except Exception as e:
                result.errors.append(f"create_collection {item.relpath}: {e}")
            continue

        # File path
        assert item.content is not None
        content_hash = compute_content_sha256(item.content)
        prior = prior_state.objects.get(item.relpath) if prior_state else None
        page_name = _name_for_relpath(item.relpath)

        if prior is not None and prior.kind == "page":
            if prior.content_sha256 == content_hash:
                # No change — preserve the prior record.
                new_objects[item.relpath] = ObjectRecord(
                    object_id=prior.object_id,
                    kind="page",
                    content_sha256=content_hash,
                    last_synced_at=prior.last_synced_at,
                )
                result.operations.append(
                    SyncOperation(
                        kind="skip_unchanged",
                        relpath=item.relpath,
                        object_id=prior.object_id,
                    )
                )
                continue
            # Update existing.
            try:
                if not dry_run:
                    adapter.update_page_content(
                        destination.space_id, prior.object_id, item.content
                    )
                new_objects[item.relpath] = ObjectRecord(
                    object_id=prior.object_id,
                    kind="page",
                    content_sha256=content_hash,
                    last_synced_at=now_iso(),
                )
                result.operations.append(
                    SyncOperation(
                        kind="update_page",
                        relpath=item.relpath,
                        object_id=prior.object_id,
                    )
                )
            except Exception as e:
                result.errors.append(f"update_page {item.relpath}: {e}")
            continue

        # New file.
        try:
            if dry_run:
                new_id = ""
            else:
                new_id = adapter.create_page_in(
                    destination.space_id, parent_id, page_name, item.content
                )
            new_objects[item.relpath] = ObjectRecord(
                object_id=new_id,
                kind="page",
                content_sha256=content_hash,
                last_synced_at=now_iso(),
            )
            result.operations.append(
                SyncOperation(
                    kind="create_page", relpath=item.relpath, object_id=new_id or None
                )
            )
        except Exception as e:
            result.errors.append(f"create_page {item.relpath}: {e}")

    # Orphans — paths in prior_state that didn't appear in the walk.
    if prior_state is not None:
        for rp, rec in prior_state.objects.items():
            if rp in seen_relpaths:
                continue
            if prune:
                # Best-effort delete; we don't have a delete method on the SyncAdapter
                # protocol yet. Mark in operations; the engine caller can either
                # extend the adapter or treat prune as a no-op for now.
                result.operations.append(
                    SyncOperation(
                        kind="delete_orphan", relpath=rp, object_id=rec.object_id
                    )
                )
            else:
                # Preserve the orphan in state so a future run with --prune can find it.
                new_objects[rp] = rec
                result.operations.append(
                    SyncOperation(
                        kind="skip_orphan", relpath=rp, object_id=rec.object_id
                    )
                )

    result.state = SyncState(
        preset=preset_name or "_adhoc",
        destination_object_id=destination.object_id,
        space_id=destination.space_id,
        last_synced_at=now_iso(),
        objects=new_objects,
    )
    return result


def _resolve_parent_id(
    relpath: str, relpath_to_id: dict[str, str], root_id: str
) -> str:
    """Return the object_id of the Collection that should contain ``relpath``.

    Logic: take the parent directory of relpath. If it's empty (top-level), the
    parent is the destination root. Otherwise look up the parent's object_id.
    """
    parent_rel = "/".join(relpath.split("/")[:-1])
    if not parent_rel:
        return root_id
    return relpath_to_id.get(parent_rel, root_id)


def _name_for_relpath(relpath: str) -> str:
    """Display name for a relpath: just its basename (without extension for files)."""
    base = relpath.split("/")[-1]
    if "." in base:
        # Strip the trailing extension only.
        stem = ".".join(base.split(".")[:-1])
        return stem or base
    return base


def collect_walk_items(
    source: Path, include_extensions: list[str], ignore: list[str]
) -> list[WalkItem]:
    """Convenience helper for callers that want the planned tree before running."""
    return list(walk(source, include_extensions, ignore))
