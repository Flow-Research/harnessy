"""Tests for jarvis content CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import jarvis.content.cli as content_cli
from jarvis.cli import cli


def _write_piece(root: Path) -> Path:
    piece = root / "drafts" / "2026" / "Jun" / "01-harnessy"
    piece.mkdir(parents=True)
    (piece / "index.md").write_text(
        """---
title: Harnessy
platform: linkedin
audience: builders
type: update
voice: direct
status: draft
scheduled: 2026-06-07
---

Harnessy is an agent capability harness for software projects and agent runtimes.
""",
        encoding="utf-8",
    )
    (piece / "twitter.md").write_text(
        "Harnessy coordinates agent capability work across runtimes.\n",
        encoding="utf-8",
    )
    return piece


def test_package_writes_journal_file(monkeypatch, tmp_path: Path) -> None:
    content_root = tmp_path / "content"
    piece = _write_piece(content_root)
    monkeypatch.setattr(content_cli, "resolve_content_root", lambda: content_root)

    result = CliRunner().invoke(
        content_cli.content_cli,
        ["package", "drafts/2026/Jun/01-harnessy"],
    )

    assert result.exit_code == 0
    journal = piece / "journal.md"
    assert journal.exists()
    text = journal.read_text(encoding="utf-8")
    assert "# Harnessy" in text
    assert "## Main Draft" in text
    assert "### twitter.md" in text


def test_verify_catches_required_and_forbidden_text(monkeypatch, tmp_path: Path) -> None:
    content_root = tmp_path / "content"
    _write_piece(content_root)
    monkeypatch.setattr(content_cli, "resolve_content_root", lambda: content_root)

    result = CliRunner().invoke(
        content_cli.content_cli,
        [
            "verify",
            "drafts/2026/Jun/01-harnessy",
            "--require",
            "agent capability harness",
            "--forbid",
            "repo install",
        ],
    )

    assert result.exit_code == 0
    assert "Content verification passed" in result.output


def test_verify_fails_when_forbidden_text_is_present(monkeypatch, tmp_path: Path) -> None:
    content_root = tmp_path / "content"
    _write_piece(content_root)
    monkeypatch.setattr(content_cli, "resolve_content_root", lambda: content_root)

    result = CliRunner().invoke(
        content_cli.content_cli,
        [
            "verify",
            "drafts/2026/Jun/01-harnessy",
            "--forbid",
            "software projects",
        ],
    )

    assert result.exit_code == 1
    assert "forbidden text found: software projects" in result.output


def test_verify_fails_when_text_hygiene_pattern_is_present(
    monkeypatch, tmp_path: Path
) -> None:
    content_root = tmp_path / "content"
    piece = _write_piece(content_root)
    index = piece / "index.md"
    index.write_text(
        index.read_text(encoding="utf-8") + "\nThis is a game-changing update.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(content_cli, "resolve_content_root", lambda: content_root)

    result = CliRunner().invoke(
        content_cli.content_cli,
        ["verify", "drafts/2026/Jun/01-harnessy"],
    )

    assert result.exit_code == 1
    assert "AI-speak pattern found" in result.output
    assert "[game-changing] game-changing" in result.output


def test_publish_draft_cleans_text_hygiene_patterns_before_packaging(
    monkeypatch, tmp_path: Path
) -> None:
    content_root = tmp_path / "content"
    piece = _write_piece(content_root)
    index = piece / "index.md"
    index.write_text(
        index.read_text(encoding="utf-8") + "\nThis is a game-changing update.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(content_cli, "resolve_content_root", lambda: content_root)

    result = CliRunner().invoke(
        content_cli.content_cli,
        ["publish-draft", "drafts/2026/Jun/01-harnessy", "--no-sync"],
    )

    assert result.exit_code == 0
    assert "Text hygiene found" in result.output
    assert "game-changing" not in index.read_text(encoding="utf-8")
    assert "game-changing" not in (piece / "journal.md").read_text(encoding="utf-8")


def test_docs_include_content_workflow_commands() -> None:
    result = CliRunner().invoke(cli, ["docs", "--json"])
    assert result.exit_code == 0
    docs = json.loads(result.output)
    content_docs = docs["commands"]["content"]
    assert content_docs["subcommands"]["package"]["description"]
    assert content_docs["subcommands"]["verify"]["options"]["--forbid"]
    assert content_docs["subcommands"]["verify"]["options"]["--hygiene / --no-hygiene"]
    assert content_docs["subcommands"]["publish-draft"]["options"]["--dedupe"]
    assert docs["commands"]["text-hygiene"]["subcommands"]["clean"]["options"]["--report"]
