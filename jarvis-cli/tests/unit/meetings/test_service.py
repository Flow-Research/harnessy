"""Tests for meeting ingestion destination writers."""

from datetime import date

import pytest

from jarvis.meetings.models import MeetingRecord
from jarvis.meetings.service import (
    MEETING_JOURNAL_TITLE_PREFIX,
    apply_meeting_auto_route,
    infer_meeting_project,
    meeting_journal_title,
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
        participants=["Project Lead", "Operations Lead", "Finance Lead"],
        summary="Aligned on a sustainable Enugu innovation hub structure.",
        detailed_summary="## Key Takeaways\n\n- Tenants should cover operating costs.",
        decisions=["Replace vague profit-sharing with a right of first refusal."],
        action_items=["Project Lead: Revise the proposal."],
        open_questions=["Will owners fund the vocational institute building?"],
        transcript="Project Lead: Let's revise the proposal.",
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
        assert "### Next Steps" in events_text
        assert "### Action Items" not in events_text
        assert "Project Lead: Revise the proposal." in events_text
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
        assert "## Next Steps" in note_text
        assert "## Action Items" not in note_text
        assert "Project Lead: Revise the proposal." in note_text
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


class TestMeetingJournalGuards:
    """Meeting journal writes should be scoped before backend sync."""

    def test_journal_destination_requires_explicit_space(self) -> None:
        with pytest.raises(ValueError, match="--journal-space"):
            write_meeting_record(_meeting_record(), destinations=["journal"])

    def test_journal_destination_skipped_when_project_missing(self) -> None:
        meeting = _meeting_record().model_copy(update={"project": ""})

        result = write_meeting_record(
            meeting,
            destinations=["journal"],
            journal_space_id="Flow",
        )

        assert result.journal_entry_id is None
        assert result.journal_skipped_reason is not None
        assert "routed project" in result.journal_skipped_reason
        assert "journal" not in result.destinations

    def test_guarded_journal_skips_disallowed_project_keeping_other_destinations(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        # A disallowed project must never attempt the journal write.
        monkeypatch.setattr(
            "jarvis.meetings.service.write_journal_entry",
            lambda *args, **kwargs: pytest.fail("journal should be skipped"),
        )
        root = tmp_path / ".jarvis" / "context" / "private" / "default"
        root.mkdir(parents=True)
        (root / "meeting-routes.yaml").write_text(
            "journal_guards:\n"
            "  - space_names:\n"
            "      - Flow\n"
            "    space_ids:\n"
            "      - flow-space-id\n"
            "    allowed_projects:\n"
            "      - flow\n"
            "      - garden\n",
            encoding="utf-8",
        )
        meeting = _meeting_record().model_copy(update={"project": "adtf"})

        result = write_meeting_record(
            meeting,
            destinations=["private-context", "journal"],
            journal_space_id="flow-space-id",
        )

        assert result.journal_entry_id is None
        assert result.journal_skipped_reason is not None
        assert "not allowed" in result.journal_skipped_reason
        assert "journal" not in result.destinations
        # The meeting is still captured by its other destination.
        assert result.written_paths

    def test_guarded_journal_allows_allowed_project(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        monkeypatch.setattr(
            "jarvis.meetings.service.write_journal_entry",
            lambda *args, **kwargs: "entry-123",
        )
        root = tmp_path / ".jarvis" / "context" / "private" / "default"
        root.mkdir(parents=True)
        (root / "meeting-routes.yaml").write_text(
            "journal_guards:\n"
            "  - space_names:\n"
            "      - Flow\n"
            "    space_ids:\n"
            "      - flow-space-id\n"
            "    allowed_projects:\n"
            "      - flow\n",
            encoding="utf-8",
        )
        meeting = _meeting_record().model_copy(update={"project": "flow"})

        result = write_meeting_record(
            meeting,
            destinations=["journal"],
            journal_space_id="Flow",
        )

        assert result.journal_entry_id == "entry-123"


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
            "      - hub financing model\n",
            encoding="utf-8",
        )
        meeting = _meeting_record().model_copy(
            update={
                "project": "",
                "summary": "Discussed the hub financing model and the innovation hub.",
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

    def test_considers_decisive_route_terms_deep_in_fathom_markdown(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("jarvis.meetings.service._USERNAME", "default")
        root = tmp_path / ".jarvis" / "context" / "private" / "default"
        root.mkdir(parents=True)
        (root / "meeting-routes.yaml").write_text(
            "routes:\n"
            "  - project: adtf\n"
            "    keywords:\n"
            "      - automated judging platform\n"
            "      - judging rubric\n"
            "  - project: flow\n"
            "    keywords:\n"
            "      - flow community\n",
            encoding="utf-8",
        )
        meeting = _meeting_record().model_copy(
            update={
                "project": "",
                "summary": "Discussed mentor recommendations.",
                "action_items": ["Review mentors from the Flow community."],
                "raw_markdown": (
                    ("filler " * 900)
                    + "Automated judging platform demo. Judging rubric finalized."
                ),
            }
        )

        assert infer_meeting_project(meeting) == "adtf"


class TestMeetingJournalTitle:
    """The journal title used when syncing meetings to backends (Anytype Flow Space, Notion).

    The JournalHierarchy already prepends the day number (``15 - <title>``),
    so the helper here only needs to add the ``Meeting - `` marker so the
    final rendered title in Flow Space reads ``dd - Meeting - <title>``.
    """

    def test_prepends_meeting_marker_to_plain_title(self) -> None:
        meeting = _meeting_record()
        title = meeting_journal_title(meeting)
        assert title == "Meeting - SEAS Partnership Sync"
        assert title.startswith(MEETING_JOURNAL_TITLE_PREFIX)

    def test_idempotent_when_title_already_has_marker(self) -> None:
        meeting = _meeting_record().model_copy(
            update={"title": "Meeting - SEAS Partnership Sync"},
        )
        assert meeting_journal_title(meeting) == "Meeting - SEAS Partnership Sync"

    def test_idempotent_marker_match_is_case_insensitive(self) -> None:
        meeting = _meeting_record().model_copy(
            update={"title": "meeting - already prefixed"},
        )
        # Preserve the user's casing rather than re-prefixing.
        assert meeting_journal_title(meeting) == "meeting - already prefixed"

    def test_handles_empty_title_with_fallback(self) -> None:
        meeting = _meeting_record().model_copy(update={"title": ""})
        assert meeting_journal_title(meeting) == "Meeting - Untitled Meeting"

    def test_strips_surrounding_whitespace_before_prefixing(self) -> None:
        meeting = _meeting_record().model_copy(
            update={"title": "  SEAS Partnership Sync  "},
        )
        assert meeting_journal_title(meeting) == "Meeting - SEAS Partnership Sync"
