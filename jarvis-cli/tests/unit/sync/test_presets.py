"""Tests for jarvis.sync.presets."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.sync.presets import (
    Preset,
    PresetOptions,
    PresetRegistry,
    load_registry,
    save_registry,
)


class TestPresetValidation:
    def test_valid_minimal(self) -> None:
        p = Preset(name="my-preset")
        assert p.source is None
        assert p.destination is None
        assert ".md" in p.options.include_extensions

    def test_valid_full(self) -> None:
        p = Preset(
            name="blog",
            source=Path("/tmp/source"),
            destination="anytype://object?objectId=a&spaceId=b",
            ignore=[".git", "*.tmp"],
        )
        rd = p.resolved_destination()
        assert rd is not None
        assert rd.object_id == "a"
        assert rd.space_id == "b"

    @pytest.mark.parametrize(
        "bad_name",
        ["", "   ", "name with space", "name/slash", "name:colon", "name\\back"],
    )
    def test_invalid_names_raise(self, bad_name: str) -> None:
        with pytest.raises(ValueError):
            Preset(name=bad_name)

    def test_malformed_destination_raises(self) -> None:
        with pytest.raises(ValueError):
            Preset(name="x", destination="not-a-link")

    def test_empty_destination_normalized_to_none(self) -> None:
        p = Preset(name="x", destination="   ")
        assert p.destination is None


class TestRegistryOps:
    def test_get_existing(self) -> None:
        reg = PresetRegistry(presets=[Preset(name="a"), Preset(name="b")])
        assert reg.get("a") is not None
        assert reg.get("missing") is None

    def test_upsert_inserts_new(self) -> None:
        reg = PresetRegistry()
        reg.upsert(Preset(name="a"))
        assert len(reg.presets) == 1
        assert reg.presets[0].name == "a"

    def test_upsert_replaces_existing(self) -> None:
        reg = PresetRegistry(presets=[Preset(name="a", source=Path("/old"))])
        reg.upsert(Preset(name="a", source=Path("/new")))
        assert len(reg.presets) == 1
        assert reg.presets[0].source == Path("/new")

    def test_remove_existing(self) -> None:
        reg = PresetRegistry(presets=[Preset(name="a"), Preset(name="b")])
        assert reg.remove("a") is True
        assert reg.get("a") is None
        assert reg.get("b") is not None

    def test_remove_missing_returns_false(self) -> None:
        reg = PresetRegistry()
        assert reg.remove("missing") is False


class TestRoundTrip:
    def test_save_load_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "presets.yaml"
        save_registry(PresetRegistry(), path)
        loaded = load_registry(path)
        assert loaded.presets == []
        assert loaded.version == 1

    def test_save_load_full(self, tmp_path: Path) -> None:
        path = tmp_path / "presets.yaml"
        original = PresetRegistry(
            presets=[
                Preset(
                    name="blog",
                    source=Path("/tmp/blog"),
                    destination="anytype://object?objectId=a&spaceId=b",
                    ignore=[".git", "drafts/*"],
                    options=PresetOptions(include_extensions=[".md"]),
                ),
                Preset(name="research"),  # all optional fields None
            ]
        )
        save_registry(original, path)
        loaded = load_registry(path)
        assert len(loaded.presets) == 2
        blog = loaded.get("blog")
        assert blog is not None
        assert blog.source == Path("/tmp/blog")
        assert blog.options.include_extensions == [".md"]
        research = loaded.get("research")
        assert research is not None
        assert research.source is None
        assert research.destination is None

    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        loaded = load_registry(tmp_path / "does-not-exist.yaml")
        assert loaded.presets == []
