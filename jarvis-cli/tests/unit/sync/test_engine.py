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

    def update_page_content(self, space_id: str, object_id: str, body_markdown: str) -> None:
        self.calls.append(("update_page_content", (space_id, object_id, body_markdown), {}))
        if self.raise_on == "update_page_content":
            raise RuntimeError("simulated")

    def upload_file_in(
        self, space_id: str, parent_collection_id: str | None, file_path: Path
    ) -> str:
        self.calls.append(("upload_file_in", (space_id, parent_collection_id, file_path), {}))
        if self.raise_on == "upload_file_in":
            raise RuntimeError("simulated")
        return self._id("file")

    def delete_object(self, space_id: str, object_id: str) -> bool:
        self.calls.append(("delete_object", (space_id, object_id), {}))
        if self.raise_on == "delete_object":
            raise RuntimeError("simulated")
        return True

    def delete_file(self, space_id: str, file_id: str) -> bool:
        self.calls.append(("delete_file", (space_id, file_id), {}))
        if self.raise_on == "delete_file":
            raise RuntimeError("simulated")
        return True


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

    def test_uploads_unsupported_files_by_default(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"keep.md": "ok"})
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")

        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
        )

        assert result.created == 2
        assert result.skipped == 0
        assert any(o.kind == "create_file" and o.relpath == "image.png" for o in result.operations)
        assert result.state.objects["image.png"].kind == "file"
        upload_calls = [c for c in adapter.calls if c[0] == "upload_file_in"]
        assert len(upload_calls) == 1
        assert upload_calls[0][1][2] == tmp_path / "image.png"

    def test_reports_unsupported_files_without_writes_in_warn_mode(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"keep.md": "ok"})
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")

        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            unsupported_mode="warn",
        )

        assert result.created == 1
        assert result.skipped == 1
        assert any(
            o.kind == "skip_unsupported" and o.relpath == "image.png" for o in result.operations
        )
        assert any("skip_unsupported image.png" in w for w in result.warnings)
        assert "image.png" not in result.state.objects
        assert not any("image.png" in str(call) for call in adapter.calls)

    def test_unchanged_uploaded_file_skips_by_hash(self, tmp_path: Path) -> None:
        image = tmp_path / "image.png"
        image.write_bytes(b"\x89PNG\r\n")
        ts = now_iso()
        prior_state = SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "image.png": ObjectRecord(
                    object_id="file_old",
                    kind="file",
                    content_sha256=_file_sha(image),
                    last_synced_at=ts,
                )
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
            prior_state=prior_state,
        )

        assert result.unchanged == 1
        assert result.operations[0].kind == "skip_file_unchanged"
        assert adapter.calls == []

    def test_modified_uploaded_file_reuploads_and_deletes_old(self, tmp_path: Path) -> None:
        image = tmp_path / "image.png"
        image.write_bytes(b"new bytes")
        ts = now_iso()
        prior_state = SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "image.png": ObjectRecord(
                    object_id="file_old",
                    kind="file",
                    content_sha256=_sha("old bytes"),
                    last_synced_at=ts,
                )
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
            prior_state=prior_state,
        )

        assert result.updated == 1
        assert result.operations[0].kind == "update_file"
        assert [c[0] for c in adapter.calls] == ["upload_file_in", "delete_file"]
        assert result.state.objects["image.png"].object_id == "file_1"

    def test_stub_page_replaced_by_uploaded_file_deletes_old_page(self, tmp_path: Path) -> None:
        image = tmp_path / "image.png"
        image.write_bytes(b"\x89PNG\r\n")
        ts = now_iso()
        prior_state = SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "image.png": ObjectRecord(
                    object_id="page_old_stub",
                    kind="page",
                    content_sha256=_sha("old stub"),
                    last_synced_at=ts,
                )
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
            prior_state=prior_state,
        )

        assert result.updated == 1
        assert result.operations[0].kind == "update_file"
        assert [c[0] for c in adapter.calls] == ["upload_file_in", "delete_object"]
        assert adapter.calls[1][1] == ("space_xyz", "page_old_stub")
        assert result.state.objects["image.png"].kind == "file"

    def test_file_object_replaced_by_text_page_deletes_old_file(self, tmp_path: Path) -> None:
        source = tmp_path / "data.bin"
        source.write_text("now readable as text", encoding="utf-8")
        ts = now_iso()
        prior_state = SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "data.bin": ObjectRecord(
                    object_id="file_old",
                    kind="file",
                    content_sha256=_sha("old binary"),
                    last_synced_at=ts,
                )
            },
        )

        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=[".bin"],
            ignore=IGNORE,
            adapter=adapter,
            prior_state=prior_state,
        )

        assert result.created == 1
        assert result.operations[0].kind == "create_page"
        assert [c[0] for c in adapter.calls] == ["create_page_in", "delete_file"]
        assert adapter.calls[1][1] == ("space_xyz", "file_old")
        assert result.state.objects["data.bin"].kind == "page"

    def test_file_object_replaced_by_collection_deletes_old_file(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"assets": None, "assets/readme.md": "ok"})
        ts = now_iso()
        prior_state = SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "assets": ObjectRecord(
                    object_id="file_old_assets",
                    kind="file",
                    content_sha256=_sha("old file"),
                    last_synced_at=ts,
                )
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
            prior_state=prior_state,
        )

        assert result.created == 2
        assert [c[0] for c in adapter.calls] == [
            "create_collection_in",
            "delete_file",
            "create_page_in",
        ]
        assert adapter.calls[1][1] == ("space_xyz", "file_old_assets")
        assert adapter.calls[2][1][1] == "col_1"
        assert result.state.objects["assets"].kind == "collection"

    def test_unsupported_mode_error_records_error(self, tmp_path: Path) -> None:
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")

        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            unsupported_mode="error",
        )

        assert result.created == 0
        assert result.skipped == 1
        assert any("unsupported_file image.png" in e for e in result.errors)
        assert "image.png" not in result.state.objects
        assert adapter.calls == []

    def test_unsupported_mode_stub_creates_metadata_page(self, tmp_path: Path) -> None:
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")

        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            unsupported_mode="stub",
        )

        assert result.created == 1
        assert result.stubbed == 1
        assert result.operations[0].kind == "create_stub_page"
        assert "image.png" in result.state.objects
        create_call = adapter.calls[0]
        assert create_call[0] == "create_page_in"
        assert create_call[1][2] == "image.png"
        assert "Relative path: `image.png`" in create_call[1][3]
        assert "SHA-256" in create_call[1][3]

    def test_directory_names_keep_dots(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"release.v1": None, "release.v1/notes.md": "ok"})

        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
        )

        assert result.created == 2
        collection_calls = [c for c in adapter.calls if c[0] == "create_collection_in"]
        assert collection_calls[0][1][2] == "release.v1"


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
        delete_calls = [c for c in adapter.calls if c[0] == "delete_object"]
        assert any(c[1][1] == "page_old_a" for c in delete_calls)

    def test_failed_prune_preserves_orphan_in_state(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                "subdir": None,
                "subdir/page-b.md": "inside",
            },
        )
        adapter = RecordingAdapter(raise_on="delete_object")
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
        assert any("delete_orphan page-a.md" in e for e in result.errors)
        assert "page-a.md" in result.state.objects

    def test_unsupported_existing_path_is_not_pruned(self, tmp_path: Path) -> None:
        (tmp_path / "page-a.md").write_text("hello", encoding="utf-8")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "page-b.md").write_text("inside", encoding="utf-8")
        (tmp_path / "archive.pdf").write_bytes(b"%PDF-1.4")

        state = self._initial_state()
        state.objects["archive.pdf"] = ObjectRecord(
            object_id="page_old_archive",
            kind="page",
            content_sha256=_sha("old archive stub"),
            last_synced_at=now_iso(),
        )

        adapter = RecordingAdapter()
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=state,
            prune=True,
            unsupported_mode="warn",
        )

        assert result.skipped == 1
        assert "archive.pdf" in result.state.objects
        assert result.state.objects["archive.pdf"].object_id == "page_old_archive"
        assert not any(
            call == ("delete_object", ("space_xyz", "page_old_archive"), {})
            for call in adapter.calls
        )


class TestErrorRecovery:
    def test_collection_failure_blocks_descendants(self, tmp_path: Path) -> None:
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
        # Do not create children at the wrong parent when their directory failed.
        page_calls = [c for c in adapter.calls if c[0] == "create_page_in"]
        assert page_calls == []
        assert any(o.kind == "skip_blocked" and o.relpath == "sub/x.md" for o in result.operations)
        assert any("skip_blocked sub/x.md" in w for w in result.warnings)
        assert "sub/x.md" not in result.state.objects

    def test_failed_page_update_preserves_prior_mapping(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"note.md": "new"})
        ts = now_iso()
        prior_state = SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "note.md": ObjectRecord(
                    object_id="page_old",
                    kind="page",
                    content_sha256=_sha("old"),
                    last_synced_at=ts,
                )
            },
        )

        adapter = RecordingAdapter(raise_on="update_page_content")
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=prior_state,
        )

        assert any("update_page note.md" in e for e in result.errors)
        assert result.state.objects["note.md"].object_id == "page_old"
        assert result.state.objects["note.md"].content_sha256 == _sha("old")

    def test_failed_file_update_preserves_prior_mapping(self, tmp_path: Path) -> None:
        image = tmp_path / "image.png"
        image.write_bytes(b"new")
        ts = now_iso()
        prior_state = SyncState(
            preset="t",
            destination_object_id="root_obj",
            space_id="space_xyz",
            last_synced_at=ts,
            objects={
                "image.png": ObjectRecord(
                    object_id="file_old",
                    kind="file",
                    content_sha256=_sha("old"),
                    last_synced_at=ts,
                )
            },
        )

        adapter = RecordingAdapter(raise_on="upload_file_in")
        result = run_sync(
            preset_name="t",
            source=tmp_path,
            destination=_link(),
            include_extensions=EXTS,
            ignore=IGNORE,
            adapter=adapter,
            prior_state=prior_state,
        )

        assert any("update_file image.png" in e for e in result.errors)
        assert result.state.objects["image.png"].object_id == "file_old"
        assert result.state.objects["image.png"].content_sha256 == _sha("old")


def _sha(s: str) -> str:
    from jarvis.sync.state import compute_content_sha256

    return compute_content_sha256(s)


def _file_sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
