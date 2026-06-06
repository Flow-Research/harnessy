from __future__ import annotations

import importlib.util
import os
import uuid
from importlib.machinery import SourceFileLoader
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
COLLECT_STATE_PATH = (
    REPO_ROOT / "tools" / "flow-install" / "skills" / "life-orchestrator" / "scripts" / "collect-state"
)
WEEKLY_PLAN_PATH = (
    REPO_ROOT / "tools" / "flow-install" / "skills" / "life-orchestrator" / "scripts" / "weekly-plan"
)


def load_collect_state(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FLOW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("FLOW_USER", "tester")
    monkeypatch.setenv("AGENTS_LIFE_DIR", str(tmp_path / ".agents" / "life"))
    monkeypatch.setenv("LIFE_ORCHESTRATOR_MEETING_LOOKBACK_DAYS", "9999")

    loader = SourceFileLoader(f"collect_state_{uuid.uuid4().hex}", str(COLLECT_STATE_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collects_nested_project_context_vault_meetings(tmp_path, monkeypatch) -> None:
    write(
        tmp_path / ".jarvis" / "context" / "private" / "tester" / "priorities.md",
        "# Priorities\n\n| Project | Priority | Status | Next Milestone |\n|---|---|---|---|\n",
    )
    vault_root = tmp_path / "projects" / "accelerate-africa" / "dev" / ".jarvis" / "context"
    write(
        vault_root / "status.md",
        "# Status\n\nAA latest context from May 27.\n",
    )
    write(
        vault_root / "roadmap.md",
        "# Roadmap\n\nCurrent cohort visibility now.\n",
    )
    write(
        vault_root / "decisions.md",
        "# Decisions\n\nShared investor-founder intro email.\n",
    )
    write(
        vault_root / "meetings" / "2026" / "May" / "27-aa-pdt-check-in.md",
        """# AA PDT Check In

## Metadata

- Date: 2026-05-27

## Key Takeaways

1. Current-cohort startups need clearer investor visibility.
2. Xero reset is required for the live demo.

## Concrete Follow-Ups

### Sayo

- Implement removal of specific emails/users from the startup list.
- Add cohort filter or current-cohort visibility controls.
""",
    )

    collect_state = load_collect_state(tmp_path, monkeypatch)

    vaults = collect_state.collect_project_context_vaults()
    assert "accelerate-africa" in vaults
    assert vaults["accelerate-africa"]["status_md"].startswith("# Status")
    assert vaults["accelerate-africa"]["recent_meetings"][0]["project"] == "accelerate-africa"
    assert "Current-cohort startups" in vaults["accelerate-africa"]["recent_meetings"][0]["summary"]

    recent = collect_state.collect_recent_meetings()
    aa_meeting = next(item for item in recent if item["project"] == "accelerate-africa")
    assert aa_meeting["title"] == "AA PDT Check In"
    assert "Xero reset" in aa_meeting["summary"]
    assert "Implement removal" in aa_meeting["action_items"][0]


def test_collect_priorities_reports_stale_external_priorities(tmp_path, monkeypatch) -> None:
    private_path = tmp_path / ".jarvis" / "context" / "private" / "tester" / "priorities.md"
    external_path = tmp_path / ".agents" / "life" / "priorities.md"
    write(private_path, "# Priorities\n\nFresh repo-private AA state.\n")
    write(external_path, "# Priorities\n\nStale external AA state.\n")

    old_time = 1_700_000_000
    new_time = 1_800_000_000
    os.utime(external_path, (old_time, old_time))
    os.utime(private_path, (new_time, new_time))

    collect_state = load_collect_state(tmp_path, monkeypatch)
    priorities = collect_state.collect_priorities()

    assert priorities["source_path"] == ".jarvis/context/private/tester/priorities.md"
    assert priorities["external_exists"] is True
    assert priorities["external_differs"] is True
    assert priorities["external_older"] is True


def test_collect_notes_defaults_to_five_day_lookback(tmp_path, monkeypatch) -> None:
    write(
        tmp_path / ".jarvis" / "context" / "private" / "tester" / "priorities.md",
        "# Priorities\n",
    )
    collect_state = load_collect_state(tmp_path, monkeypatch)
    today = collect_state.datetime.date.today()

    for offset in range(6):
        day = today - collect_state.datetime.timedelta(days=offset)
        write(
            tmp_path
            / ".jarvis"
            / "context"
            / "private"
            / "tester"
            / "notes"
            / day.strftime("%Y")
            / day.strftime("%b")
            / f"{day.strftime('%d')}.md",
            f"# Note {offset}\n",
        )

    notes = collect_state.collect_notes()

    assert set(notes) == {
        (today - collect_state.datetime.timedelta(days=offset)).isoformat()
        for offset in range(5)
    }
    assert (today - collect_state.datetime.timedelta(days=5)).isoformat() not in notes


def test_weekly_plan_prefers_repo_private_priorities_before_legacy_file() -> None:
    script = WEEKLY_PLAN_PATH.read_text(encoding="utf-8")

    private_index = script.index('elif [ -f "$PRIVATE_PRIORITIES_FILE" ]; then')
    legacy_index = script.index('PRIORITIES_FILE="$LEGACY_PRIORITIES_FILE"')

    assert "PRIVATE_PRIORITIES_FILE=" in script
    assert private_index < legacy_index
