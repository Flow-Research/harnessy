"""Sync engine: walk source, diff against state, apply operations to Anytype.

The engine is the orchestrator. Inputs: source path, destination link, ignore list,
options, prior state, and a SyncAdapter Protocol that wraps the actual Anytype calls.
Outputs: list of SyncOperations performed (or planned, if dry_run=True), and an
updated SyncState.

The Protocol shape lets us unit-test the engine without touching Anytype: tests
pass in a recording mock that captures every call.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    "create_file",
    "update_file",
    "skip_file_unchanged",
    "create_stub_page",
    "update_stub_page",
    "skip_stub_unchanged",
    "skip_unchanged",
    "skip_unsupported",
    "skip_blocked",
    "skip_orphan",
    "delete_orphan",
]
UnsupportedMode = Literal["upload", "warn", "stub", "error"]


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
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def created(self) -> int:
        return sum(
            1
            for o in self.operations
            if o.kind in ("create_collection", "create_page", "create_file", "create_stub_page")
        )

    @property
    def updated(self) -> int:
        return sum(
            1
            for o in self.operations
            if o.kind in ("update_page", "update_file", "update_stub_page")
        )

    @property
    def unchanged(self) -> int:
        return sum(
            1
            for o in self.operations
            if o.kind in ("skip_unchanged", "skip_file_unchanged", "skip_stub_unchanged")
        )

    @property
    def stubbed(self) -> int:
        return sum(
            1
            for o in self.operations
            if o.kind
            in (
                "create_stub_page",
                "update_stub_page",
                "skip_stub_unchanged",
            )
        )

    @property
    def skipped(self) -> int:
        return sum(1 for o in self.operations if o.kind in ("skip_unsupported", "skip_blocked"))

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

    def update_page_content(self, space_id: str, object_id: str, body_markdown: str) -> None: ...

    def upload_file_in(
        self, space_id: str, parent_collection_id: str | None, file_path: Path
    ) -> str: ...

    def delete_object(self, space_id: str, object_id: str) -> bool: ...

    def delete_file(self, space_id: str, file_id: str) -> bool: ...


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
    unsupported_mode: UnsupportedMode = "upload",
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
          exists locally is deleted on Anytype. Deeper paths are deleted before
          their parent collections, so a folder's children are removed before the
          folder itself.

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
        unsupported_mode: How to handle existing files that cannot be synced
            as text pages. "upload" creates native Anytype file objects,
            "warn" reports and skips, "stub" creates metadata pages, and
            "error" records a sync error.

    Returns:
        SyncResult with operations, updated state, and any non-fatal errors.
    """
    result = SyncResult()
    new_objects: dict[str, ObjectRecord] = {}
    seen_relpaths: set[str] = set()
    blocked_relpaths: set[str] = set()

    # Map of relpath → object_id for parent resolution. Seeded from prior state's
    # collections so we can reuse them when their directories still exist locally.
    relpath_to_id: dict[str, str] = {}
    if prior_state is not None:
        for rp, rec in prior_state.objects.items():
            if rec.kind == "collection":
                relpath_to_id[rp] = rec.object_id

    for item in walk(source, include_extensions, ignore, include_unsupported=True):
        seen_relpaths.add(item.relpath)
        blocked_parent = _blocked_parent_for(item.relpath, blocked_relpaths)
        if blocked_parent is not None:
            prior = prior_state.objects.get(item.relpath) if prior_state else None
            if prior is not None:
                new_objects[item.relpath] = prior
            result.operations.append(
                SyncOperation(
                    kind="skip_blocked",
                    relpath=item.relpath,
                    object_id=prior.object_id if prior is not None else None,
                )
            )
            result.warnings.append(
                f"skip_blocked {item.relpath}: parent collection {blocked_parent} was not created"
            )
            continue
        parent_id = _resolve_parent_id(item.relpath, relpath_to_id, destination.object_id)

        if item.kind == "directory":
            prior = prior_state.objects.get(item.relpath) if prior_state else None
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
            name = _name_for_relpath(item.relpath, strip_extension=False)
            try:
                if dry_run:
                    new_id = ""
                else:
                    new_id = adapter.create_collection_in(destination.space_id, parent_id, name)
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
                _cleanup_replaced_prior(
                    result=result,
                    adapter=adapter,
                    destination=destination,
                    relpath=item.relpath,
                    prior=prior,
                    dry_run=dry_run,
                )
            except Exception as e:
                blocked_relpaths.add(item.relpath)
                result.errors.append(f"create_collection {item.relpath}: {e}")
            continue

        if item.kind == "unsupported_file":
            prior = prior_state.objects.get(item.relpath) if prior_state else None
            reason = item.skip_reason or "unsupported file"
            if unsupported_mode == "upload":
                _sync_binary_file(
                    result=result,
                    new_objects=new_objects,
                    adapter=adapter,
                    destination=destination,
                    relpath=item.relpath,
                    parent_id=parent_id,
                    file_path=item.abspath,
                    prior=prior,
                    dry_run=dry_run,
                )
                continue
            if unsupported_mode == "stub":
                _sync_page_body(
                    result=result,
                    new_objects=new_objects,
                    adapter=adapter,
                    destination=destination,
                    relpath=item.relpath,
                    parent_id=parent_id,
                    page_name=_name_for_relpath(item.relpath, strip_extension=False),
                    body_markdown=_unsupported_stub_body(item, reason),
                    prior=prior,
                    dry_run=dry_run,
                    create_kind="create_stub_page",
                    update_kind="update_stub_page",
                    unchanged_kind="skip_stub_unchanged",
                )
                result.warnings.append(f"stub_unsupported {item.relpath}: {reason}")
                continue
            if prior is not None:
                # The path still exists locally, so preserve the remote mapping.
                # A future run can resync it if the extension list changes.
                new_objects[item.relpath] = prior
            result.operations.append(
                SyncOperation(
                    kind="skip_unsupported",
                    relpath=item.relpath,
                    object_id=prior.object_id if prior is not None else None,
                )
            )
            message = f"unsupported_file {item.relpath}: {reason}"
            if unsupported_mode == "error":
                result.errors.append(message)
            else:
                result.warnings.append(f"skip_unsupported {item.relpath}: {reason}")
            continue

        # File path
        assert item.content is not None
        prior = prior_state.objects.get(item.relpath) if prior_state else None
        _sync_page_body(
            result=result,
            new_objects=new_objects,
            adapter=adapter,
            destination=destination,
            relpath=item.relpath,
            parent_id=parent_id,
            page_name=_name_for_relpath(item.relpath),
            body_markdown=item.content,
            prior=prior,
            dry_run=dry_run,
            create_kind="create_page",
            update_kind="update_page",
            unchanged_kind="skip_unchanged",
        )

    # Orphans — paths in prior_state that didn't appear in the walk.
    if prior_state is not None:
        orphan_items = [
            (rp, rec) for rp, rec in prior_state.objects.items() if rp not in seen_relpaths
        ]
        # Delete children before parent collections.
        orphan_items.sort(key=lambda item: item[0].count("/"), reverse=True)
        for rp, rec in orphan_items:
            if rp in seen_relpaths:
                continue
            if prune:
                try:
                    if not dry_run:
                        if rec.kind == "file":
                            deleted = adapter.delete_file(destination.space_id, rec.object_id)
                        else:
                            deleted = adapter.delete_object(destination.space_id, rec.object_id)
                        if not deleted:
                            raise RuntimeError("backend returned false")
                    result.operations.append(
                        SyncOperation(kind="delete_orphan", relpath=rp, object_id=rec.object_id)
                    )
                except Exception as e:
                    # Keep failed deletes in state so a future prune can retry.
                    new_objects[rp] = rec
                    result.errors.append(f"delete_orphan {rp}: {e}")
            else:
                # Preserve the orphan in state so a future run with --prune can find it.
                new_objects[rp] = rec
                result.operations.append(
                    SyncOperation(kind="skip_orphan", relpath=rp, object_id=rec.object_id)
                )

    result.state = SyncState(
        preset=preset_name or "_adhoc",
        destination_object_id=destination.object_id,
        space_id=destination.space_id,
        last_synced_at=now_iso(),
        objects=new_objects,
    )
    return result


def _resolve_parent_id(relpath: str, relpath_to_id: dict[str, str], root_id: str) -> str:
    """Return the object_id of the Collection that should contain ``relpath``.

    Logic: take the parent directory of relpath. If it's empty (top-level), the
    parent is the destination root. Otherwise look up the parent's object_id.
    """
    parent_rel = "/".join(relpath.split("/")[:-1])
    if not parent_rel:
        return root_id
    return relpath_to_id.get(parent_rel, root_id)


def _blocked_parent_for(relpath: str, blocked_relpaths: set[str]) -> str | None:
    """Return the nearest failed parent directory for ``relpath``, if any."""
    parts = relpath.split("/")[:-1]
    for i in range(len(parts), 0, -1):
        parent = "/".join(parts[:i])
        if parent in blocked_relpaths:
            return parent
    return None


def _sync_page_body(
    *,
    result: SyncResult,
    new_objects: dict[str, ObjectRecord],
    adapter: SyncAdapter,
    destination: AnytypeLink,
    relpath: str,
    parent_id: str,
    page_name: str,
    body_markdown: str,
    prior: ObjectRecord | None,
    dry_run: bool,
    create_kind: OperationKind,
    update_kind: OperationKind,
    unchanged_kind: OperationKind,
) -> None:
    """Create/update/skip a Page-like Anytype object for a source path."""
    content_hash = compute_content_sha256(body_markdown)
    if prior is not None and prior.kind == "page":
        if prior.content_sha256 == content_hash:
            new_objects[relpath] = ObjectRecord(
                object_id=prior.object_id,
                kind="page",
                content_sha256=content_hash,
                last_synced_at=prior.last_synced_at,
            )
            result.operations.append(
                SyncOperation(
                    kind=unchanged_kind,
                    relpath=relpath,
                    object_id=prior.object_id,
                )
            )
            return
        try:
            if not dry_run:
                adapter.update_page_content(destination.space_id, prior.object_id, body_markdown)
            new_objects[relpath] = ObjectRecord(
                object_id=prior.object_id,
                kind="page",
                content_sha256=content_hash,
                last_synced_at=now_iso(),
            )
            result.operations.append(
                SyncOperation(
                    kind=update_kind,
                    relpath=relpath,
                    object_id=prior.object_id,
                )
            )
        except Exception as e:
            # Preserve the old remote mapping. If the CLI chooses to persist
            # partial state, the next run should retry this update instead of
            # creating a duplicate page.
            new_objects[relpath] = prior
            result.errors.append(f"{update_kind} {relpath}: {e}")
        return

    try:
        if dry_run:
            new_id = ""
        else:
            new_id = adapter.create_page_in(
                destination.space_id, parent_id, page_name, body_markdown
            )
        new_objects[relpath] = ObjectRecord(
            object_id=new_id,
            kind="page",
            content_sha256=content_hash,
            last_synced_at=now_iso(),
        )
        result.operations.append(
            SyncOperation(kind=create_kind, relpath=relpath, object_id=new_id or None)
        )
        _cleanup_replaced_prior(
            result=result,
            adapter=adapter,
            destination=destination,
            relpath=relpath,
            prior=prior,
            dry_run=dry_run,
        )
    except Exception as e:
        result.errors.append(f"{create_kind} {relpath}: {e}")


def _sync_binary_file(
    *,
    result: SyncResult,
    new_objects: dict[str, ObjectRecord],
    adapter: SyncAdapter,
    destination: AnytypeLink,
    relpath: str,
    parent_id: str,
    file_path: Path,
    prior: ObjectRecord | None,
    dry_run: bool,
) -> None:
    """Create/update/skip a native Anytype file object for a source path."""
    content_hash = _file_sha256(file_path)
    if prior is not None and prior.kind == "file" and prior.content_sha256 == content_hash:
        new_objects[relpath] = ObjectRecord(
            object_id=prior.object_id,
            kind="file",
            content_sha256=content_hash,
            last_synced_at=prior.last_synced_at,
        )
        result.operations.append(
            SyncOperation(
                kind="skip_file_unchanged",
                relpath=relpath,
                object_id=prior.object_id,
            )
        )
        return

    try:
        if dry_run:
            new_id = ""
        else:
            new_id = adapter.upload_file_in(destination.space_id, parent_id, file_path)
    except Exception as e:
        op = "update_file" if prior and prior.kind == "file" else "create_file"
        if prior is not None:
            new_objects[relpath] = prior
        result.errors.append(f"{op} {relpath}: {e}")
        return

    new_objects[relpath] = ObjectRecord(
        object_id=new_id,
        kind="file",
        content_sha256=content_hash,
        last_synced_at=now_iso(),
    )
    result.operations.append(
        SyncOperation(
            kind="update_file" if prior is not None else "create_file",
            relpath=relpath,
            object_id=new_id or None,
        )
    )

    _cleanup_replaced_prior(
        result=result,
        adapter=adapter,
        destination=destination,
        relpath=relpath,
        prior=prior,
        dry_run=dry_run,
    )


def _cleanup_replaced_prior(
    *,
    result: SyncResult,
    adapter: SyncAdapter,
    destination: AnytypeLink,
    relpath: str,
    prior: ObjectRecord | None,
    dry_run: bool,
) -> None:
    """Delete the old remote object after the same relpath changes object kind/id."""
    if prior is None or not prior.object_id or dry_run:
        return
    try:
        if prior.kind == "file":
            deleted = adapter.delete_file(destination.space_id, prior.object_id)
        else:
            deleted = adapter.delete_object(destination.space_id, prior.object_id)
        if not deleted:
            raise RuntimeError("backend returned false")
    except Exception as e:
        result.warnings.append(f"cleanup_replaced_{prior.kind} {relpath}: {e}")


def _name_for_relpath(relpath: str, *, strip_extension: bool = True) -> str:
    """Display name for a relpath: basename, optionally without file extension."""
    base = relpath.split("/")[-1]
    if strip_extension and "." in base:
        # Strip the trailing extension only.
        stem = ".".join(base.split(".")[:-1])
        return stem or base
    return base


def _unsupported_stub_body(item: WalkItem, reason: str) -> str:
    """Markdown placeholder for a file the run is configured not to upload."""
    stat = item.abspath.stat()
    digest = _file_sha256(item.abspath)
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()
    return "\n".join(
        [
            f"# {item.abspath.name}",
            "",
            "Jarvis saw this local file during folder sync and created a "
            "metadata placeholder instead of uploading the file content.",
            "",
            f"- Relative path: `{item.relpath}`",
            f"- Size: {stat.st_size} bytes",
            f"- SHA-256: `{digest}`",
            f"- Last modified: {modified_at}",
            f"- Reason: {reason}",
            "",
            "Keep the original file in the local source folder. This page is a "
            "placeholder so the Anytype tree still shows that the file exists.",
            "",
        ]
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_walk_items(
    source: Path, include_extensions: list[str], ignore: list[str]
) -> list[WalkItem]:
    """Convenience helper for callers that want the planned tree before running."""
    return list(walk(source, include_extensions, ignore))
