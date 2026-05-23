"""Tests for pure meeting parsing helpers."""

from datetime import date

import pytest

from jarvis.meetings.parser import (
    extract_list_items,
    infer_meeting_date,
    parse_meeting_document,
    render_meeting_markdown,
    split_markdown_sections,
)
from jarvis.reading_list.models import SourceDocument, SourceType


class TestSplitMarkdownSections:
    """Markdown section splitting should preserve canonical headings."""

    def test_extracts_title_sections_and_preamble(self) -> None:
        markdown = (
            "# Team Sync\n\nOpening note.\n\n## Summary\n\n"
            "Short summary.\n\n## Action Items\n\n- Ship it\n"
        )
        sections, preamble, title = split_markdown_sections(markdown)
        assert title == "Team Sync"
        assert preamble == "Opening note."
        assert sections["summary"] == "Short summary."
        assert sections["action items"] == "- Ship it"


class TestExtractListItems:
    """List extraction should support bullets and single-line fallbacks."""

    @pytest.mark.parametrize(
        "body,expected",
        [
            ("- One\n- Two", ["One", "Two"]),
            ("1. First\n2. Second", ["First", "Second"]),
            ("One; Two", ["One", "Two"]),
        ],
    )
    def test_known_list_forms(self, body: str, expected: list[str]) -> None:
        assert extract_list_items(body) == expected


class TestInferMeetingDate:
    """Date inference should handle common meeting-export date forms."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Meeting on 2026-05-15", date(2026, 5, 15)),
            ("Held May 15, 2026 over Zoom", date(2026, 5, 15)),
            ("Captured 2026/05/15 from Fathom", date(2026, 5, 15)),
        ],
    )
    def test_common_date_formats(self, text: str, expected: date) -> None:
        assert infer_meeting_date(text) == expected


class TestParseMeetingDocument:
    """Meeting parsing should extract structured sections from markdown notes."""

    def test_extracts_structured_sections(self) -> None:
        source = SourceDocument(
            source_type=SourceType.FILE,
            source_ref="/tmp/meeting.md",
            title="Fallback Title",
            markdown=(
                "# Founder Sync\n\n"
                "## Participants\n\n"
                "- Alice\n- Bob\n\n"
                "## Summary\n\n"
                "We aligned on roadmap and fundraising.\n\n"
                "## Key Decisions\n\n"
                "- Delay hiring until June\n\n"
                "## Action Items\n\n"
                "- Alice to send deck\n- Bob to update model\n\n"
                "## Transcript\n\n"
                "Alice: Let's tighten scope.\n"
            ),
            last_modified="1:2",
        )
        meeting = parse_meeting_document(source, project="aa", tags=["fathom"])
        assert meeting.title == "Founder Sync"
        assert meeting.project == "aa"
        assert meeting.tags == ["fathom"]
        assert meeting.participants == ["Alice", "Bob"]
        assert meeting.summary == "We aligned on roadmap and fundraising."
        assert meeting.decisions == ["Delay hiring until June"]
        assert meeting.action_items == ["Alice to send deck", "Bob to update model"]
        assert meeting.transcript == "Alice: Let's tighten scope."

    def test_falls_back_to_raw_transcript_when_no_sections_exist(self) -> None:
        source = SourceDocument(
            source_type=SourceType.STDIN,
            source_ref="stdin",
            title="Raw transcript",
            markdown="[00:01] Alice: Hello\n[00:02] Bob: Hi",
            last_modified="abc",
        )
        meeting = parse_meeting_document(source)
        assert meeting.transcript == "[00:01] Alice: Hello\n[00:02] Bob: Hi"

    def test_uses_key_takeaways_as_summary_for_fathom_markdown_exports(self) -> None:
        source = SourceDocument(
            source_type=SourceType.FILE,
            source_ref="/tmp/fathom.md",
            title="Fathom Export",
            markdown=(
                "# Fathom Export\n\n"
                "## Detailed Summary\n\n"
                "## Key Takeaways\n\n"
                "- Tenants cover operating costs.\n"
                "- Replace vague profit-sharing with right of first refusal.\n\n"
                "## Next Steps\n\n"
                "- Julian to revise proposal\n"
            ),
            last_modified="1",
        )

        meeting = parse_meeting_document(source)

        assert "Tenants cover operating costs" in meeting.summary
        assert meeting.action_items == ["Julian to revise proposal"]

    def test_preserves_rendered_meeting_metadata_when_file_moves(self) -> None:
        source = SourceDocument(
            source_type=SourceType.FILE,
            source_ref="/tmp/moved.md",
            title="Moved Export",
            markdown=(
                "# SEAS Sync\n\n"
                "## Metadata\n\n"
                "- Date: 2026-05-23\n"
                "- Source Type: fathom\n"
                "- Source Ref: fathom:149059728\n"
                "- Project: seas\n"
                "- Participants: Julian Duru, Eke Urum\n"
                "- Tags: fathom, seas\n"
                "- Fingerprint: fathom:149059728:2026-05-23T19:25:04Z\n\n"
                "## Key Takeaways\n\n"
                "- Preserve stable meeting identity.\n"
            ),
            last_modified="file:/tmp/moved.md:1",
        )

        meeting = parse_meeting_document(source)

        assert meeting.source_type == "fathom"
        assert meeting.source_ref == "fathom:149059728"
        assert meeting.project == "seas"
        assert meeting.participants == ["Julian Duru", "Eke Urum"]
        assert meeting.tags == ["fathom", "seas"]
        assert meeting.fingerprint == "fathom:149059728:2026-05-23T19:25:04Z"


class TestRenderMeetingMarkdown:
    """Rendered meeting markdown should include canonical sections."""

    def test_renders_key_sections(self) -> None:
        source = SourceDocument(
            source_type=SourceType.FILE,
            source_ref="/tmp/meeting.md",
            title="Board Sync",
            markdown="# Board Sync\n\n## Summary\n\nShort summary.\n",
            last_modified="1",
        )
        meeting = parse_meeting_document(source)
        rendered = render_meeting_markdown(meeting)
        assert "# Board Sync" in rendered
        assert "## Metadata" in rendered
        assert "## Executive Summary" in rendered
        assert "## Transcript" not in rendered

    def test_render_omits_transcript_discussion(self) -> None:
        source = SourceDocument(
            source_type=SourceType.FILE,
            source_ref="/tmp/meeting.md",
            title="Founder Sync",
            markdown=(
                "# Founder Sync\n\n"
                "## Summary\n\nWe agreed on the next fundraising steps.\n\n"
                "## Transcript\n\n"
                "Alice: This is the full line-by-line discussion.\n"
            ),
            last_modified="1",
        )
        meeting = parse_meeting_document(source)

        rendered = render_meeting_markdown(meeting)

        assert "We agreed on the next fundraising steps." in rendered
        assert "## Transcript" not in rendered
        assert "full line-by-line discussion" not in rendered
