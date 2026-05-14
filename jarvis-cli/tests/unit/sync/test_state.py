"""Tests for jarvis.sync.state."""

from __future__ import annotations

from pathlib import Path

from jarvis.sync.state import (
    ObjectRecord,
    SyncState,
    compute_content_sha256,
    get_state_path,
    load_state,
    now_iso,
    save_state,
)


class TestSha256:
    def test_stable_for_same_content(self) -> None:
        assert compute_content_sha256("hello") == compute_content_sha256("hello")

    def test_differs_for_different_content(self) -> None:
        assert compute_content_sha256("a") != compute_content_sha256("b")

    def test_handles_unicode(self) -> None:
        digest = compute_content_sha256("héllo 🌊")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


class TestStatePath:
    def test_default_uses_underscore_adhoc(self) -> None:
        assert get_state_path("").name == "_adhoc.json"
        assert get_state_path("   ").name == "_adhoc.json"

    def test_named_preset(self) -> None:
        assert get_state_path("blog-publish").name == "blog-publish.json"


class TestRoundTrip:
    def _make_state(self) -> SyncState:
        return SyncState(
            preset="blog",
            destination_object_id="root_id",
            space_id="space_id",
            last_synced_at=now_iso(),
            objects={
                "page-1.md": ObjectRecord(
                    object_id="obj_a",
                    kind="page",
                    content_sha256="abc123",
                    last_synced_at=now_iso(),
                ),
                "subdir": ObjectRecord(
                    object_id="col_b",
                    kind="collection",
                    content_sha256=None,
                    last_synced_at=now_iso(),
                ),
            },
        )

    def test_save_then_load(self, tmp_path: Path) -> None:
        path = tmp_path / "blog.json"
        original = self._make_state()
        save_state(original, path)
        loaded = load_state("blog", path)
        assert loaded is not None
        assert loaded.preset == "blog"
        assert loaded.objects["page-1.md"].content_sha256 == "abc123"
        assert loaded.objects["subdir"].kind == "collection"
        assert loaded.objects["subdir"].content_sha256 is None

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        assert load_state("never-saved", tmp_path / "never-saved.json") is None

    def test_save_creates_parent_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "deeply" / "nested" / "blog.json"
        save_state(self._make_state(), nested)
        assert nested.exists()
