"""Tests for Fathom meeting normalization helpers."""

import json
from datetime import date

from jarvis.meetings.fathom import (
    fathom_action_items,
    fathom_participants,
    fathom_transcript_markdown,
    looks_like_fathom_payload,
    parse_fathom_json_text,
    parse_fathom_payload,
)


def _payload() -> dict:
    return {
        "title": "Quarterly Business Review",
        "meeting_title": "QBR 2025 Q1",
        "recording_id": 123456789,
        "created_at": "2025-03-01T17:01:30Z",
        "recording_start_time": "2025-03-01T16:01:12Z",
        "default_summary": {
            "template_name": "general",
            "markdown_formatted": (
                "## Summary\n\n"
                "Reviewed pipeline and budget allocation.\n\n"
                "## Key Decisions\n\n"
                "- Delay hiring until June\n"
            ),
        },
        "transcript": [
            {
                "speaker": {"display_name": "Alice Johnson"},
                "text": "Let's revisit the budget allocations.",
                "timestamp": "00:05:32",
            },
            {
                "speaker": {"display_name": "Bob Lee"},
                "text": "Agreed.",
                "timestamp": "00:06:01",
            },
        ],
        "action_items": [
            {
                "description": "Send revised proposal",
                "assignee": {"name": "Alice Johnson"},
            }
        ],
        "calendar_invitees": [{"name": "Alice Johnson"}, {"name": "Bob Lee"}],
        "recorded_by": {"name": "Alice Johnson"},
    }


class TestLooksLikeFathomPayload:
    """Fathom payload detection should be robust for direct and wrapped blobs."""

    def test_direct_payload(self) -> None:
        assert looks_like_fathom_payload(_payload()) is True

    def test_wrapped_payload(self) -> None:
        assert looks_like_fathom_payload({"items": [_payload()]}) is True

    def test_non_payload(self) -> None:
        assert looks_like_fathom_payload({"hello": "world"}) is False


class TestFathomNormalization:
    """Structured Fathom fields should map cleanly into the meeting model."""

    def test_extract_helpers(self) -> None:
        payload = _payload()
        assert fathom_participants(payload) == ["Alice Johnson", "Bob Lee"]
        assert fathom_action_items(payload) == ["Alice Johnson: Send revised proposal"]
        assert fathom_transcript_markdown(payload).startswith("[00:05:32] Alice Johnson:")

    def test_parse_payload(self) -> None:
        meeting = parse_fathom_payload(_payload(), project="aa")
        assert meeting.title == "QBR 2025 Q1"
        assert meeting.meeting_date == date(2025, 3, 1)
        assert meeting.project == "aa"
        assert meeting.source_type == "fathom"
        assert meeting.summary == "Reviewed pipeline and budget allocation."
        assert meeting.decisions == ["Delay hiring until June"]
        assert meeting.action_items == ["Alice Johnson: Send revised proposal"]
        assert "Alice Johnson: Let's revisit the budget allocations." in meeting.transcript
        assert "Let's revisit the budget allocations." not in meeting.raw_markdown

    def test_parse_payload_uses_summary_headings_and_action_fallbacks(self) -> None:
        payload = _payload()
        payload["default_summary"] = {
            "markdown_formatted": (
                "## Key Takeaways\n\n"
                "- The team aligned on a narrower launch scope.\n"
                "- Budget review should move before hiring.\n\n"
                "## Next Steps\n\n"
                "- Bob to update the launch budget\n"
            )
        }
        payload["action_items"] = []

        meeting = parse_fathom_payload(payload)

        assert "narrower launch scope" in meeting.summary
        assert meeting.action_items == ["Bob to update the launch budget"]

    def test_parse_json_text(self) -> None:
        meeting = parse_fathom_json_text(json.dumps({"items": [_payload()]}))
        assert meeting is not None
        assert meeting.title == "QBR 2025 Q1"
