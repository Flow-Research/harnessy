"""Tests for jarvis.sync.walker."""

from __future__ import annotations

from pathlib import Path

from jarvis.sync.walker import WalkItem, walk

EXTS = [".md", ".txt", ".markdown", ".text"]
DEFAULT_IGNORE = [".git", ".DS_Store", "node_modules"]


def _build_tree(root: Path, layout: dict[str, str | None]) -> None:
    """Create a tree from a dict mapping relpath -> content (None means dir)."""
    for rel, content in layout.items():
        target = root / rel
        if content is None:
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")


class TestSingleFile:
    def test_yields_one_item(self, tmp_path: Path) -> None:
        f = tmp_path / "note.md"
        f.write_text("hello", encoding="utf-8")
        items = list(walk(f, EXTS, DEFAULT_IGNORE))
        assert len(items) == 1
        assert items[0].kind == "file"
        assert items[0].relpath == "note.md"
        assert items[0].content == "hello"

    def test_skips_excluded_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG")
        assert list(walk(f, EXTS, DEFAULT_IGNORE)) == []


class TestDirectoryWalk:
    def test_preorder_with_subdirs(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                "a.md": "a",
                "sub": None,
                "sub/b.md": "b",
                "sub/c.md": "c",
                "deep": None,
                "deep/inner": None,
                "deep/inner/d.md": "d",
            },
        )
        items = list(walk(tmp_path, EXTS, DEFAULT_IGNORE))

        kinds_and_paths = [(i.kind, i.relpath) for i in items]
        # Directories must precede their files.
        sub_dir_idx = kinds_and_paths.index(("directory", "sub"))
        assert sub_dir_idx < kinds_and_paths.index(("file", "sub/b.md"))
        deep_dir_idx = kinds_and_paths.index(("directory", "deep"))
        inner_dir_idx = kinds_and_paths.index(("directory", "deep/inner"))
        assert deep_dir_idx < inner_dir_idx
        assert inner_dir_idx < kinds_and_paths.index(("file", "deep/inner/d.md"))

    def test_skips_non_text_files(self, tmp_path: Path) -> None:
        _build_tree(tmp_path, {"keep.md": "ok", "skip.png": "binary"})
        items = list(walk(tmp_path, EXTS, DEFAULT_IGNORE))
        names = {i.relpath for i in items if i.kind == "file"}
        assert names == {"keep.md"}

    def test_respects_ignore_globs(self, tmp_path: Path) -> None:
        _build_tree(
            tmp_path,
            {
                ".git": None,
                ".git/config": "x",
                "node_modules": None,
                "node_modules/pkg.md": "x",
                "good.md": "y",
                "tmp.md.tmp": "z",
            },
        )
        items = list(walk(tmp_path, EXTS, [*DEFAULT_IGNORE, "*.tmp"]))
        names = {i.relpath for i in items if i.kind == "file"}
        assert names == {"good.md"}

    def test_empty_dir_yields_nothing(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert list(walk(empty, EXTS, DEFAULT_IGNORE)) == []

    def test_nonexistent_path_yields_nothing(self, tmp_path: Path) -> None:
        ghost = tmp_path / "nope"
        assert list(walk(ghost, EXTS, DEFAULT_IGNORE)) == []

    def test_walk_item_is_frozen(self, tmp_path: Path) -> None:
        f = tmp_path / "x.md"
        f.write_text("x", encoding="utf-8")
        item = next(walk(f, EXTS, DEFAULT_IGNORE))
        assert isinstance(item, WalkItem)
        # frozen dataclass: assigning attrs should fail
        try:
            item.relpath = "other"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("WalkItem should be frozen")
