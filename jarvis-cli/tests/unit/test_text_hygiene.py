"""Tests for AI-speak text hygiene checks and cleanup."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from jarvis.cli import cli
from jarvis.text_hygiene import HygieneRule, check_paths, clean_paths, process_text


def _write_config(tmp_path: Path) -> Path:
    config = tmp_path / "ai-speak-patterns.yaml"
    config.write_text(
        """version: 1
rules:
  - id: ai-vibe
    kind: phrase
    pattern: "AI vibe"
    flags: ["i"]
  - id: vague-magic
    kind: regex
    pattern: '\\bmagic\\b'
    flags: ["i"]
""",
        encoding="utf-8",
    )
    return config


def test_process_text_skips_frontmatter_code_fences_and_inline_code() -> None:
    rules = (
        HygieneRule(
            id="game-changing",
            kind="regex",
            pattern=r"\bgame-changing\b",
            flags=("i",),
        ),
    )
    text = """---
title: game-changing
---

This is a game-changing idea.
This keeps `game-changing` as literal code.

```md
game-changing
```
"""

    cleaned, findings = process_text(text, rules, path=Path("doc.md"), write=True)

    assert len(findings) == 1
    assert findings[0].line == 5
    assert "This is a idea." in cleaned
    assert "title: game-changing" in cleaned
    assert "`game-changing`" in cleaned
    assert "```md\ngame-changing\n```" in cleaned


def test_check_and_clean_paths_use_phrase_and_regex_rules(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    doc = tmp_path / "README.md"
    doc.write_text("This has an AI vibe and magic wording.\n", encoding="utf-8")

    checked = check_paths([doc], config_path=config)

    assert len(checked.findings) == 2
    assert doc.read_text(encoding="utf-8") == "This has an AI vibe and magic wording.\n"

    cleaned = clean_paths([doc], config_path=config)

    assert len(cleaned.findings) == 2
    assert doc in cleaned.changed_files
    assert doc.read_text(encoding="utf-8") == "This has an and wording.\n"


def test_text_hygiene_cli_check_reports_json_and_fails_on_findings(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    doc = tmp_path / "notes.md"
    doc.write_text("AI vibe.\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["text-hygiene", "check", str(doc), "--config", str(config), "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["summary"]["matches"] == 1
    assert payload["findings"][0]["rule_id"] == "ai-vibe"
    assert doc.read_text(encoding="utf-8") == "AI vibe.\n"


def test_text_hygiene_cli_clean_writes_file(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    doc = tmp_path / "notes.md"
    doc.write_text("AI vibe.\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["text-hygiene", "clean", str(doc), "--config", str(config), "--report"],
    )

    assert result.exit_code == 0
    assert "Text hygiene found 1 match" in result.output
    assert doc.read_text(encoding="utf-8") == ".\n"
