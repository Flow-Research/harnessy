"""Pure parsing and formatting helpers for meeting ingestion."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime

from jarvis.reading_list.models import SourceDocument
from jarvis.wiki.parser import slug_from_title

from .models import MeetingRecord

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_DATE_PATTERNS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
)
_TRANSCRIPT_LINE_RE = re.compile(r"^(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s+)?[A-Z][^:]{0,80}:\s+.+$")

_SUMMARY_HEADINGS = {"summary", "executive summary", "overview", "key takeaways"}
_DETAILED_SUMMARY_HEADINGS = {"detailed summary", "full summary"}
_PARTICIPANT_HEADINGS = {"participants", "attendees", "people", "guests"}
_DECISION_HEADINGS = {"decisions", "key decisions"}
_ACTION_HEADINGS = {"action items", "actions", "next steps", "follow ups", "follow-up"}
_VISIBLE_ACTION_HEADINGS = _ACTION_HEADINGS
_QUESTION_HEADINGS = {"open questions", "questions", "risks", "parking lot"}
_TRANSCRIPT_HEADINGS = {"transcript", "conversation transcript", "notes transcript"}


def parse_meeting_document(
    source: SourceDocument,
    *,
    title_override: str | None = None,
    project: str = "",
    tags: list[str] | None = None,
) -> MeetingRecord:
    """Parse a source document into a canonical meeting record."""

    sections, preamble, title = split_markdown_sections(source.markdown)
    metadata = extract_metadata(sections.get("metadata", ""))
    resolved_title = title_override or title or source.title or "Untitled Meeting"
    meeting_date = (
        infer_meeting_date(metadata.get("date", ""), source.markdown, source.title)
        or date.today()
    )
    inline_fields = extract_inline_fields(preamble)
    participants = []
    for heading in _PARTICIPANT_HEADINGS:
        body = sections.get(heading)
        if body:
            participants = extract_people(body)
            break
    if not participants and metadata.get("participants"):
        participants = extract_people(metadata["participants"])
    if not participants:
        for field in _PARTICIPANT_HEADINGS:
            if inline_fields.get(field):
                participants = extract_people(inline_fields[field])
                break

    summary = first_section(sections, _SUMMARY_HEADINGS)
    detailed_summary = first_section(sections, _DETAILED_SUMMARY_HEADINGS)
    decisions = extract_first_list(sections, _DECISION_HEADINGS)
    action_items = extract_first_list(sections, _ACTION_HEADINGS)
    open_questions = extract_first_list(sections, _QUESTION_HEADINGS)
    transcript = first_section(sections, _TRANSCRIPT_HEADINGS)

    if not transcript:
        transcript = extract_transcript_block(source.markdown)
    if not summary and preamble:
        summary = first_paragraph(preamble)

    resolved_tags = tags if tags is not None else extract_people(metadata.get("tags", ""))

    return MeetingRecord(
        title=resolved_title.strip(),
        meeting_date=meeting_date,
        source_ref=metadata.get("source ref") or source.source_ref,
        source_type=metadata.get("source type") or str(source.source_type),
        fingerprint=metadata.get("fingerprint") or source.fingerprint,
        project=project or metadata.get("project", ""),
        tags=resolved_tags,
        participants=participants,
        summary=summary,
        detailed_summary=detailed_summary,
        decisions=decisions,
        action_items=action_items,
        open_questions=open_questions,
        transcript=transcript.strip(),
        raw_markdown=source.markdown,
    )


def split_markdown_sections(markdown: str) -> tuple[dict[str, str], str, str | None]:
    """Split markdown into normalized sections keyed by heading."""

    sections: dict[str, list[str]] = {}
    preamble: list[str] = []
    current_key: str | None = None
    title: str | None = None

    for line in markdown.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            heading_level = len(match.group(1))
            heading_text = match.group(2).strip()
            if heading_level == 1 and title is None:
                title = heading_text
                current_key = None
                continue
            current_key = normalize_heading(heading_text)
            sections.setdefault(current_key, [])
            continue

        if current_key is None:
            preamble.append(line)
        else:
            sections[current_key].append(line)

    collapsed = {key: "\n".join(lines).strip() for key, lines in sections.items()}
    return collapsed, "\n".join(preamble).strip(), title


def normalize_heading(heading: str) -> str:
    """Normalize a markdown heading for section matching."""

    return re.sub(r"\s+", " ", heading.strip().lower().rstrip(":"))


def extract_list_items(body: str) -> list[str]:
    """Extract markdown bullet or numbered list items from a section body."""

    items: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        bullet_match = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)$", line)
        if bullet_match:
            items.append(bullet_match.group(1).strip())
            continue
        if len(body.splitlines()) == 1:
            items.extend([part.strip() for part in line.split(";") if part.strip()])
    return items


def extract_people(body: str) -> list[str]:
    """Extract participant names from a participants section."""

    listed = extract_list_items(body)
    if listed:
        if len(listed) == 1 and "," in listed[0]:
            return [part.strip() for part in listed[0].split(",") if part.strip()]
        return listed
    flattened = " ".join(line.strip() for line in body.splitlines() if line.strip())
    return [part.strip() for part in flattened.split(",") if part.strip()]


def extract_metadata(body: str) -> dict[str, str]:
    """Extract simple `- Key: Value` metadata from a rendered meeting note."""

    metadata: dict[str, str] = {}
    for item in extract_list_items(body):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        metadata[normalize_heading(key)] = value.strip()
    return metadata


def extract_inline_fields(text: str) -> dict[str, str]:
    """Extract bare `Key: Value` lines (no bullet) from a preamble block.

    Plain-text and manual meeting notes often place fields like
    ``Participants: A, B`` directly under the title rather than inside a
    ``## Metadata`` section. Those would otherwise be dropped.
    """

    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("-", "*", "+", "#", ">")):
            continue
        match = re.match(r"^([A-Za-z][\w ]{0,40}):\s+(.+)$", line)
        if match:
            fields.setdefault(normalize_heading(match.group(1)), match.group(2).strip())
    return fields


def extract_transcript_block(markdown: str) -> str:
    """Extract likely transcript lines from markdown when no section exists."""

    transcript_lines = [
        line.rstrip() for line in markdown.splitlines() if _TRANSCRIPT_LINE_RE.match(line)
    ]
    if transcript_lines:
        return "\n".join(transcript_lines)
    return markdown.strip()


def first_section(sections: dict[str, str], names: Iterable[str]) -> str:
    """Return the first present section body from a candidate heading set."""

    for name in names:
        body = sections.get(name, "").strip()
        if body:
            return body
    return ""


def extract_first_list(sections: dict[str, str], names: set[str]) -> list[str]:
    """Return the first non-empty list extracted from candidate sections."""

    for name in names:
        body = sections.get(name, "").strip()
        if not body:
            continue
        items = extract_list_items(body)
        if items:
            return items
    return []


def infer_meeting_date(*texts: str) -> date | None:
    """Infer a meeting date from source text snippets."""

    for text in texts:
        if not text:
            continue
        for pattern in _DATE_PATTERNS:
            match = re.search(_date_regex_for_pattern(pattern), text)
            if not match:
                continue
            try:
                return datetime.strptime(match.group(0), pattern).date()
            except ValueError:
                continue
    return None


def _date_regex_for_pattern(pattern: str) -> str:
    mapping = {
        "%Y-%m-%d": r"\b\d{4}-\d{2}-\d{2}\b",
        "%Y/%m/%d": r"\b\d{4}/\d{2}/\d{2}\b",
        "%B %d, %Y": r"\b[A-Z][a-z]+ \d{1,2}, \d{4}\b",
        "%b %d, %Y": r"\b[A-Z][a-z]{2} \d{1,2}, \d{4}\b",
        "%B %d %Y": r"\b[A-Z][a-z]+ \d{1,2} \d{4}\b",
        "%b %d %Y": r"\b[A-Z][a-z]{2} \d{1,2} \d{4}\b",
    }
    return mapping[pattern]


def first_paragraph(text: str) -> str:
    """Return the first non-empty paragraph from a text blob."""

    paragraphs = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    return paragraphs[0] if paragraphs else ""


def meeting_filename(meeting: MeetingRecord) -> str:
    """Build the canonical markdown filename for a meeting record."""

    slug = slug_from_title(meeting.title) or "meeting"
    return f"{meeting.meeting_date.isoformat()}-{slug}.md"


def render_meeting_markdown(meeting: MeetingRecord) -> str:
    """Render a concise meeting artifact for context and memory destinations."""

    lines = [f"# {meeting.title}", "", "## Metadata", ""]
    lines.append(f"- Date: {meeting.meeting_date.isoformat()}")
    lines.append(f"- Source Type: {meeting.source_type}")
    lines.append(f"- Source Ref: {meeting.source_ref}")
    if meeting.project:
        lines.append(f"- Project: {meeting.project}")
    if meeting.participants:
        lines.append(f"- Participants: {', '.join(meeting.participants)}")
    if meeting.tags:
        lines.append(f"- Tags: {', '.join(meeting.tags)}")
    if meeting.fingerprint:
        lines.append(f"- Fingerprint: {meeting.fingerprint}")

    def add_section(title: str, body: str | list[str]) -> None:
        if not body:
            return
        lines.extend(["", f"## {title}", ""])
        if isinstance(body, list):
            lines.extend([f"- {item}" for item in body])
        else:
            lines.append(body.strip())

    add_section("Executive Summary", meeting.summary)
    add_section("Detailed Summary", demote_markdown_headings(meeting.detailed_summary))
    add_section("Key Decisions", meeting.decisions)
    if not has_visible_action_heading(meeting.detailed_summary):
        add_section("Next Steps", meeting.action_items)
    add_section("Open Questions", meeting.open_questions)
    return "\n".join(lines).strip() + "\n"


def _yaml_str(value: str) -> str:
    """Quote a scalar for YAML frontmatter only when required."""

    value = value.replace("\n", " ").strip()
    if value and value[0] not in "-?:" and not re.search(r'[:#\[\]{}",&*!|>%@`]', value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _obsidian_tag(value: str) -> str:
    """Normalize a label into an Obsidian-safe tag (no spaces)."""

    return re.sub(r"[^A-Za-z0-9/_-]+", "-", value.strip().lower()).strip("-")


def render_obsidian_meeting_markdown(meeting: MeetingRecord) -> str:
    """Render a meeting as a first-class Obsidian note.

    Emits YAML frontmatter (so Obsidian shows Properties), a ``#meeting`` tag,
    action items as ``- [ ]`` checkboxes, and ``[[wikilinks]]`` for participants
    so the note participates in graph view, backlinks, and the tasks view.
    """

    tags = ["meeting"]
    for label in ([meeting.project] if meeting.project else []) + list(meeting.tags):
        slug = _obsidian_tag(label)
        if slug and slug not in tags:
            tags.append(slug)

    lines = [
        "---",
        f"title: {_yaml_str(meeting.title)}",
        f"date: {meeting.meeting_date.isoformat()}",
        "type: meeting",
    ]
    if meeting.participants:
        lines.append("participants:")
        lines.extend(f"  - {_yaml_str(person)}" for person in meeting.participants)
    lines.append("tags:")
    lines.extend(f"  - {tag}" for tag in tags)
    if meeting.source_ref:
        lines.append(f"source: {_yaml_str(meeting.source_ref)}")
    lines.extend(["---", "", f"# {meeting.title}", ""])

    callout = f"> [!info] Meeting\n> **Date:** {meeting.meeting_date.isoformat()}"
    if meeting.participants:
        people = ", ".join(f"[[{person}]]" for person in meeting.participants)
        callout += f" · **People:** {people}"
    lines.append(callout)

    def add_section(title: str, body: str | list[str], *, checkbox: bool = False) -> None:
        if not body:
            return
        lines.extend(["", f"## {title}", ""])
        if isinstance(body, list):
            if checkbox:
                for item in body:
                    cleaned = re.sub(r"^\[[ xX]\]\s*", "", item)
                    lines.append(f"- [ ] {cleaned}")
            else:
                lines.extend(f"- {item}" for item in body)
        else:
            lines.append(body.strip())

    add_section("Executive Summary", meeting.summary)
    add_section("Detailed Summary", demote_markdown_headings(meeting.detailed_summary))
    add_section("Key Decisions", meeting.decisions)
    if not has_visible_action_heading(meeting.detailed_summary):
        add_section("Action Items", meeting.action_items, checkbox=True)
    add_section("Open Questions", meeting.open_questions)
    return "\n".join(lines).strip() + "\n"


def has_visible_action_heading(markdown: str) -> bool:
    """Return True when rendered markdown already includes an action-style section."""

    if not markdown:
        return False
    sections, _, _ = split_markdown_sections(markdown)
    return any(heading in sections for heading in _VISIBLE_ACTION_HEADINGS)


def demote_markdown_headings(markdown: str) -> str:
    """Nest source summary headings under the rendered meeting section."""

    if not markdown:
        return ""
    return re.sub(r"^(#{1,5})\s+", r"#\1 ", markdown.strip(), flags=re.MULTILINE)
