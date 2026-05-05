"""Tests for jarvis.sync.engine.

The engine is unit-tested against a RecordingAdapter that implements the
SyncAdapter Protocol and captures every call. No real Anytype required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from jarvis.sync.engine import run_sync
from jarvis.sync.object_link import AnytypeLink
from jarvis.sync.state import ObjectRecord, SyncState, now_iso

EXTS = [".md", ".txt"]
IGNORE = [".git", ".DS_Store"]


@dataclass
class RecordingAdapter:
    """Captures every adapter call. Returns deterministic synthetic ids."""

    calls: list[tuple[str, tuple, dict]] = field(default_factory=list)
    next_id: int = 0
    raise_on: str | None = None  # operation name to raise on

    def _id(self, prefix: str) -> str:
        self.next_id += 1
        return f"{prefix}_{self.next_id}"

    def create_collection_in(
        self, space_id: str, parent_collection_id: str | None, name: str
    ) -> str:
        self.calls.append(("create_collection_in", (space_id, parent_collection_id, name), {}))
        if self.raise_on == "create_collection_in":
            raise RuntimeError("simulated")
        return self._id("col")

    def create_page_in(
        self,
        space_id: str,
        parent_collection_id: str | None,
        name: str,
        body_markdown: str,
    ) -> str:
        self.calls.append(
            ("create_page_in", (space_id, parent_collection_id, name, body_markdown), {})
        )
        if self.raise_on == "create_page_in":
            raise RuntimeError("simulated")
        return self._id("page")

    def update_page_content(
        self, space_id: str, object_id: str, body_markdown: str
    ) -> None:
        self.calls.append(("update_page_content", (space_id, object_id, body_markdown), {}))
        if self.raise_on == "update_page_content":
            raise RuntimeError("simulated")


def _build_tree(root: Path, layout: dict[str, str | None]) -> None:
    for rel, content in layout.items():
        target = root / rel
        if content is None:
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")


def _link() -> AnytypeLink:
    return AnytypeLink(object_id="root_obj", space_id="space_xyz")


class TestFirstRun:
    def test_creates_collections_and_pages_in_order(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                "top.md": "top content",
                "sub": None,
                "sub/inner.md": "inner content",
            },
        )
        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
        )
        assert result.created == 3  # one collection + two pages
        assert result.updated == 0
        assert result.unchanged == 0

        # Order: top.md is at top-level; sub directory before sub/inner.md.
        names = [c[1][2] for c in adapter.calls]
        assert "top" in names and "sub" in names and "inner" in names

        # The collection must be created before the inner page.
        col_idx = next(i for i, c in enumerate(adapter.calls) if c[0] == "create_collection_in")
        inner_idx = next(
            i
            for i, c in enumerate(adapter.calls)
            if c[0] == "create_page_in" and c[1][2] == "inner"
        )
        assert col_idx < inner_idx

        # The inner page's parent_collection_id must be the new collection's id.
        inner_call = adapter.calls[inner_idx]
        # Returned id from create_collection_in is in result.state.objects
        sub_record = result.state.objects["sub"]
        assert inner_call[1][1] == sub_record.object_id

    def test_dry_run_makes_no_api_calls(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"a.md": "x"})
        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            dry_run=True,
        )
        assert adapter.calls == []
        assert result.created == 1
        # The state still records the operation; new ids are empty strings in dry-run.
        assert result.state.objects["a.md"].object_id == ""


class TestIncrementalRun:
    def _initial_state(self) -> SyncState:
        ts = now_iso()
        return SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "page-a.md": ObjectRecord(
                    object_id="page_old_a",
                    kind="page",
                    content_sha256=_sha("hello"),
                    last_synced_at=ts,
                ),
                "subdir": ObjectRecord(
                    object_id="col_old_sub",
                    kind="collection",
                    content_sha256=None,
                    last_synced_at=ts,
                ),
                "subdir/page-b.md": ObjectRecord(
                    object_id="page_old_b",
                    kind="page",
                    content_sha256=_sha("inside"),
                    last_synced_at=ts,
                ),
            },
        )

    def test_unchanged_files_skip(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                "page-a.md": "hello",
                "subdir": None,
                "subdir/page-b.md": "inside",
            },
        )
        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=self._initial_state(),
        )
        assert result.unchanged == 2  # both files unchanged
        assert result.updated == 0
        assert result.created == 0
        assert adapter.calls == []  # short-circuit by hash

    def test_modified_file_updates(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                "page-a.md": "hello changed",
                "subdir": None,
                "subdir/page-b.md": "inside",
            },
        )
        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=self._initial_state(),
        )
        assert result.updated == 1
        assert result.unchanged == 1
        # The update call must target the prior object_id.
        update_calls = [c for c in adapter.calls if c[0] == "update_page_content"]
        assert len(update_calls) == 1
        assert update_calls[0][1][1] == "page_old_a"

    def test_new_file_creates(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                "page-a.md": "hello",
                "page-c.md": "brand new",  # new
                "subdir": None,
                "subdir/page-b.md": "inside",
            },
        )
        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=self._initial_state(),
        )
        assert result.created == 1
        create_calls = [c for c in adapter.calls if c[0] == "create_page_in"]
        assert len(create_calls) == 1
        assert create_calls[0][1][2] == "page-c"  # name without extension

    def test_orphan_preserved_without_prune(self, tmp_path: Path) -> None:
        # Local tree drops page-a.md
        _build_tree(
            tmp_path,
            {
                "subdir": None,
                "subdir/page-b.md": "inside",
            },
        )
        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=self._initial_state(),
        )
        # Orphan stays in state under skip_orphan, no destructive call.
        orphan_ops = [o for o in result.operations if o.kind == "skip_orphan"]
        assert any(o.relpath == "page-a.md" for o in orphan_ops)
        assert "page-a.md" in result.state.objects

    def test_orphan_marked_for_deletion_with_prune(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                "subdir": None,
                "subdir/page-b.md": "inside",
            },
        )
        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=self._initial_state(),
            prune=True,
        )
        delete_ops = [o for o in result.operations if o.kind == "delete_orphan"]
        assert any(o.relpath == "page-a.md" for o in delete_ops)
        # Orphan should NOT be in the resulting state.
        assert "page-a.md" not in result.state.objects


class TestErrorRecovery:
    def test_collection_failure_logged_not_fatal(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"sub": None, "sub/x.md": "x"})
        adapter = RecordingAdapter(raise_on="create_collection_in")
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
        )
        assert any("create_collection sub" in e for e in result.errors)
        # The page should still attempt to create, parented to the root since
        # the collection's id was never recorded.
        page_calls = [c for c in adapter.calls if c[0] == "create_page_in"]
        assert page_calls, "page creation should have been attempted"
        assert page_calls[0][1][1] == "root_obj"  # fell back to root


def _sha(s: str) -> str:
    from jarvis.sync.state import compute_content_sha256

    return compute_content_sha256(s)
