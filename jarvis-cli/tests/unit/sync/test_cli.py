"""CLI tests for jarvis sync."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import jarvis.sync.cli as sync_cli
from jarvis.cli import cli
from jarvis.sync.cli import sync_group
from jarvis.sync.object_link import AnytypeLink


class RecordingSyncAdapter:
    """Small real-run adapter for CLI tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.next_id = 0

    def _id(self, prefix: str) -> str:
        self.next_id += 1
        return f"{prefix}_{self.next_id}"

    def validate_collection(self, space_id: str, object_id: str) -> None:
        self.calls.append(("validate_collection", (space_id, object_id)))

    def create_collection_in(
        self, space_id: str, parent_collection_id: str | None, name: str
    ) -> str:
        self.calls.append(("create_collection_in", (space_id, parent_collection_id, name)))
        return self._id("col")

    def create_page_in(
        self,
        space_id: str,
        parent_collection_id: str | None,
        name: str,
        body_markdown: str,
    ) -> str:
        self.calls.append(("create_page_in", (space_id, parent_collection_id, name)))
        return self._id("page")

    def update_page_content(self, space_id: str, object_id: str, body_markdown: str) -> None:
        self.calls.append(("update_page_content", (space_id, object_id)))

    def upload_file_in(
        self, space_id: str, parent_collection_id: str | None, file_path: Path
    ) -> str:
        self.calls.append(("upload_file_in", (space_id, parent_collection_id, file_path)))
        return self._id("file")

    def delete_object(self, space_id: str, object_id: str) -> bool:
        self.calls.append(("delete_object", (space_id, object_id)))
        return True

    def delete_file(self, space_id: str, file_id: str) -> bool:
        self.calls.append(("delete_file", (space_id, file_id)))
        return True


def _write_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "note.md").write_text("hello", encoding="utf-8")
    return source


def test_dry_run_does_not_connect_to_anytype(monkeypatch, tmp_path: Path) -> None:
    """Dry-run should plan locally without requiring Anytype to be running."""
    source = _write_source(tmp_path)

    def fail_get_adapter():  # type: ignore[no-untyped-def]
        raise AssertionError("dry-run should not connect to Anytype")

    monkeypatch.setattr(sync_cli, "_get_anytype_adapter", fail_get_adapter)
    monkeypatch.setattr(sync_cli, "load_state", lambda _name: None)

    result = CliRunner().invoke(
        sync_group,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            "root_obj:space_1",
            "--unsupported-mode",
            "warn",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Dry run summary" in result.output
    assert "Created:" in result.output


def test_include_extension_expands_text_file_set(monkeypatch, tmp_path: Path) -> None:
    """A one-off sync adds text extensions without dropping default markdown."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "note.md").write_text("hello", encoding="utf-8")
    (source / "script.py").write_text("print('hello')", encoding="utf-8")

    monkeypatch.setattr(sync_cli, "load_state", lambda _name: None)

    result = CliRunner().invoke(
        sync_group,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            "root_obj:space_1",
            "--include-extension",
            "py",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Created:" in result.output
    assert "2" in result.output


def test_dry_run_reports_unsupported_files(monkeypatch, tmp_path: Path) -> None:
    """Folder sync should say which files it cannot sync as Anytype pages."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "note.md").write_text("hello", encoding="utf-8")
    (source / "image.png").write_bytes(b"\x89PNG\r\n")

    monkeypatch.setattr(sync_cli, "load_state", lambda _name: None)

    result = CliRunner().invoke(
        sync_group,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            "root_obj:space_1",
            "--unsupported-mode",
            "warn",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Skipped:" in result.output
    assert "Warnings:" in result.output
    assert "skip_unsupported image.png" in result.output


def test_unsupported_mode_stub_reports_stubbed(monkeypatch, tmp_path: Path) -> None:
    """Stub mode should represent unsupported files as metadata pages."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "image.png").write_bytes(b"\x89PNG\r\n")

    monkeypatch.setattr(sync_cli, "load_state", lambda _name: None)

    result = CliRunner().invoke(
        sync_group,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            "root_obj:space_1",
            "--unsupported-mode",
            "stub",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Unsupported files:" in result.output
    assert "stub" in result.output
    assert "Stubbed:" in result.output
    assert "stub_unsupported image.png" in result.output


def test_unsupported_mode_error_fails_run(monkeypatch, tmp_path: Path) -> None:
    """Strict mode should make unsupported files fail automation."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "image.png").write_bytes(b"\x89PNG\r\n")

    monkeypatch.setattr(sync_cli, "load_state", lambda _name: None)

    result = CliRunner().invoke(
        sync_group,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            "root_obj:space_1",
            "--unsupported-mode",
            "error",
            "--dry-run",
        ],
    )

    assert result.exit_code == 1
    assert "unsupported_file image.png" in result.output


def test_yes_runs_without_confirmation_and_validates_destination(
    monkeypatch, tmp_path: Path
) -> None:
    """--yes should skip the write confirmation but still validate the target."""
    source = _write_source(tmp_path)
    adapter = RecordingSyncAdapter()
    saved: dict[str, object] = {}

    monkeypatch.setattr(sync_cli, "_get_anytype_adapter", lambda: adapter)
    monkeypatch.setattr(sync_cli, "load_state", lambda _name: None)
    monkeypatch.setattr(sync_cli, "save_state", lambda state: saved.update(state=state))

    result = CliRunner().invoke(
        sync_group,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            "root_obj:space_1",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert "Proceed?" not in result.output
    assert ("validate_collection", ("space_1", "root_obj")) in adapter.calls
    assert any(call[0] == "create_page_in" for call in adapter.calls)
    assert "state" in saved


def test_destination_validation_failure_stops_before_write(monkeypatch, tmp_path: Path) -> None:
    """A non-collection target should fail before creating pages."""
    source = _write_source(tmp_path)
    adapter = RecordingSyncAdapter()

    def reject_collection(space_id: str, object_id: str) -> None:
        raise RuntimeError("not a Collection")

    adapter.validate_collection = reject_collection  # type: ignore[method-assign]

    monkeypatch.setattr(sync_cli, "_get_anytype_adapter", lambda: adapter)
    monkeypatch.setattr(sync_cli, "load_state", lambda _name: None)

    result = CliRunner().invoke(
        sync_group,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            "root_obj:space_1",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert "Invalid sync destination" in result.output
    assert not any(call[0] == "create_page_in" for call in adapter.calls)


def test_adhoc_state_names_are_stable_and_scoped(tmp_path: Path) -> None:
    """Different ad-hoc source/destination pairs should not share one state file."""
    source_a = tmp_path / "a"
    source_b = tmp_path / "b"
    source_a.mkdir()
    source_b.mkdir()
    destination = AnytypeLink(object_id="root_obj", space_id="space_1")

    first = sync_cli._state_name(None, source_a, destination)
    second = sync_cli._state_name(None, source_a, destination)
    other_source = sync_cli._state_name(None, source_b, destination)
    other_destination = sync_cli._state_name(
        None, source_a, AnytypeLink(object_id="other_root", space_id="space_1")
    )

    assert first == second
    assert first.startswith("_adhoc_")
    assert first != other_source
    assert first != other_destination
    assert sync_cli._state_name("flow-context", source_a, destination) == "flow-context"


def test_docs_include_sync_command() -> None:
    """The generated agent docs should make jarvis sync discoverable."""
    result = CliRunner().invoke(cli, ["docs", "--json"])
    assert result.exit_code == 0
    docs = json.loads(result.output)
    sync_docs = docs["commands"]["sync"]
    assert sync_docs["subcommands"]["run"]["options"]["--yes"]
    assert sync_docs["subcommands"]["run"]["options"]["--include-extension"]
    assert "upload" in sync_docs["subcommands"]["run"]["options"]["--unsupported-mode"]
    assert sync_docs["subcommands"]["preset add"]["description"]
