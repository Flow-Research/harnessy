"""Tests for meeting ingestion destination writers."""

from datetime import date

from jarvis.meetings.models import MeetingRecord
from jarvis.meetings.service import (
    apply_meeting_auto_route,
    infer_meeting_project,
    write_meeting_record,
)


def _meeting_record() -> MeetingRecord:
    return MeetingRecord(
        title="SEAS Partnership Sync",
        meeting_date=date(2026, 5, 23),
        source_ref="fathom:149059728",
        source_type="fathom",
        fingerprint="fathom:149059728:2026-05-23T19:25:04Z",
        project="seas",
        tags=["fathom"],
        participants=["Julian Duru", "Eke Urum", "Alex Onyia"],
        summary="Aligned on a sustainable Enugu innovation hub structure.",
        detailed_summary="## Key Takeaways\n\n- Tenants should cover operating costs.",
        decisions=["Replace vague profit-sharing with a right of first refusal."],
        action_items=["Julian: Revise the proposal."],
        open_questions=["Will owners fund the vocational institute building?"],
        transcript="Julian Duru: Let's revise the proposal.",
        raw_markdown="## Key Takeaways\n\n- Tenants should cover operating costs.",
    )


class TestWriteMeetingMemory:
    """Meeting memory absorption should be useful and idempotent."""

    def test_writes_event_and_decision_memory(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        meeting = _meeting_record()

        first = write_meeting_record(meeting, destinations=["memory"])
        second = write_meeting_record(meeting, destinations=["memory"])

        assert first.destinations == ["memory"]
        assert second.destinations == ["memory"]
        events = tmp_path / ".jarvis" / "context" / "private" / "default" / "events.md"
        decisions = (
            tmp_path / ".jarvis" / "context" / "private" / "default" / "decisions.md"
        )
        assert events.exists()
        assert decisions.exists()
        events_text = events.read_text(encoding="utf-8")
        decisions_text = decisions.read_text(encoding="utf-8")
        assert "SEAS Partnership Sync" in events_text
        assert "Julian: Revise the proposal." in events_text
        assert "right of first refusal" in decisions_text
        assert events_text.count("memory_id:") == 1
        assert decisions_text.count("memory_id:") == 1

    def test_writes_private_context_meeting_under_project_path(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        meeting = _meeting_record()

        first = write_meeting_record(meeting, destinations=["private-context"])
        second = write_meeting_record(meeting, destinations=["private-context"])

        note = (
            tmp_path
            / ".jarvis"
            / "context"
            / "private"
            / "default"
            / "seas"
            / "meetings"
            / "2026"
            / "May"
            / "23-seas-partnership-sync.md"
        )
        assert first.written_paths == [str(note)]
        assert second.written_paths == [str(note)]
        assert note.exists()
        assert list(note.parent.glob("23-seas-partnership-sync*.md")) == [note]
        note_text = note.read_text(encoding="utf-8")
        assert "Aligned on a sustainable Enugu innovation hub structure." in note_text
        assert "Julian: Revise the proposal." in note_text
        assert "## Transcript" not in note_text
        assert "Let's revise the proposal" not in note_text

    def test_writes_private_context_meeting_without_project_to_general_path(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        meeting = _meeting_record().model_copy(update={"project": ""})

        result = write_meeting_record(meeting, destinations=["private-context"])

        note = (
            tmp_path
            / ".jarvis"
            / "context"
            / "private"
            / "default"
            / "meetings"
            / "2026"
            / "May"
            / "23-seas-partnership-sync.md"
        )
        assert result.written_paths == [str(note)]
        assert note.exists()


class TestMeetingAutoRoute:
    """Meeting auto-routing should only infer clear private project matches."""

    def test_uses_private_route_rules_when_project_is_missing(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        root = tmp_path / ".jarvis" / "context" / "private" / "default"
        root.mkdir(parents=True)
        (root / "meeting-routes.yaml").write_text(
            "routes:\n"
            "  - project: seas\n"
            "    keywords:\n"
            "      - enugu innovation hub\n"
            "      - alex onyia\n",
            encoding="utf-8",
        )
        meeting = _meeting_record().model_copy(
            update={
                "project": "",
                "summary": "Discussed Alex Onyia and the Enugu innovation hub model.",
            }
        )

        routed = apply_meeting_auto_route(meeting, auto_route=True)

        assert routed.project == "seas"

    def test_explicit_project_wins_over_auto_route(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        root = tmp_path / ".jarvis" / "context" / "private" / "default"
        root.mkdir(parents=True)
        (root / "meeting-routes.yaml").write_text(
            "routes:\n"
            "  - project: flow\n"
            "    keywords:\n"
            "      - seas partnership sync\n",
            encoding="utf-8",
        )
        meeting = _meeting_record()

        routed = apply_meeting_auto_route(meeting, auto_route=True)

        assert routed.project == "seas"

    def test_tie_returns_no_project(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        root = tmp_path / ".jarvis" / "context" / "private" / "default"
        root.mkdir(parents=True)
        (root / "meeting-routes.yaml").write_text(
            "routes:\n"
            "  - project: seas\n"
            "    keywords:\n"
            "      - shared keyword\n"
            "  - project: flow\n"
            "    keywords:\n"
            "      - shared keyword\n",
            encoding="utf-8",
        )
        meeting = _meeting_record().model_copy(
            update={
                "title": "Neutral Partnership Sync",
                "project": "",
                "summary": "This mentions a shared keyword.",
            }
        )

        assert infer_meeting_project(meeting) == ""
