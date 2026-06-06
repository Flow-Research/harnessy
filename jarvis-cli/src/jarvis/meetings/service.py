"""Meeting ingestion orchestration and destination writers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import yaml
from rich.console import Console

from jarvis.reading_list.source_loader import load_source_document
from jarvis.services.journal_service import JournalService
from jarvis.wiki.config import get_domain_root
from jarvis.wiki.parser import slug_from_title

from .fathom import FathomClient, parse_fathom_json_text, parse_fathom_payload
from .models import MeetingIngestResult, MeetingRecord
from .parser import meeting_filename, parse_meeting_document, render_meeting_markdown
from .webhook import list_inbox_files, load_archived_payload, move_inbox_file

console = Console()
_USERNAME = os.environ.get("FLOW_USER", os.environ.get("USER", "default"))
_AI_MODEL = "claude-sonnet-4-20250514"
_MEETING_ROUTE_CONFIG = "meeting-routes.yaml"
_ROUTE_EXCLUDED_DIRS = {"meeting-inbox", "meetings", "notes"}


def ingest_meeting(
    source: str,
    *,
    resolver: str | None = None,
    backend: str | None = None,
    title: str | None = None,
    project: str = "",
    tags: list[str] | None = None,
    auto_route: bool = False,
    destinations: list[str] | None = None,
    wiki_domain: str | None = None,
    journal_space_id: str | None = None,
    enrich_ai: bool = True,
) -> MeetingIngestResult:
    """Ingest a meeting transcript-like source into one or more destinations."""

    meeting = load_meeting_record_from_source(
        source,
        resolver=resolver,
        backend=backend,
        title=title,
        project=project,
        tags=tags,
    )
    if enrich_ai:
        meeting = enrich_meeting_record(meeting)
    meeting = apply_meeting_auto_route(meeting, auto_route=auto_route)

    return write_meeting_record(
        meeting,
        destinations=destinations,
        wiki_domain=wiki_domain,
        backend=backend,
        journal_space_id=journal_space_id,
    )


def ingest_fathom_meeting(
    recording_id: str,
    *,
    account: str | None = None,
    project: str = "",
    tags: list[str] | None = None,
    auto_route: bool = False,
    destinations: list[str] | None = None,
    wiki_domain: str | None = None,
    created_after: str | None = None,
    backend: str | None = None,
    journal_space_id: str | None = None,
) -> MeetingIngestResult:
    """Fetch a Fathom recording and ingest it into Jarvis destinations."""

    client = FathomClient(account=account)
    payload = client.get_meeting_by_recording_id(recording_id, created_after=created_after)
    meeting = parse_fathom_payload(
        payload,
        project=project,
        tags=tags or ["fathom"],
        source_ref=f"fathom:{recording_id}",
    )
    meeting = apply_meeting_auto_route(meeting, auto_route=auto_route)
    return write_meeting_record(
        meeting,
        destinations=destinations,
        wiki_domain=wiki_domain,
        backend=backend,
        journal_space_id=journal_space_id,
    )


def ingest_fathom_meetings_since(
    *,
    account: str | None = None,
    created_after: str | None = None,
    limit: int = 100,
    max_pages: int = 5,
    project: str = "",
    tags: list[str] | None = None,
    auto_route: bool = False,
    destinations: list[str] | None = None,
    wiki_domain: str | None = None,
    backend: str | None = None,
    journal_space_id: str | None = None,
    skip_existing: bool = True,
) -> list[MeetingIngestResult]:
    """Ingest Fathom recordings, optionally filtering by created-after timestamp."""

    client = FathomClient(account=account)
    results: list[MeetingIngestResult] = []
    cursor: str | None = None
    pages = 0

    while pages < max_pages:
        payload = client.list_meetings(
            limit=limit,
            created_after=created_after,
            include_transcript=True,
            include_summary=True,
            include_action_items=True,
            cursor=cursor,
        )
        items = payload.get("items", [])
        if not isinstance(items, list):
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            recording_id = str(item.get("recording_id") or "").strip()
            if not recording_id:
                continue
            if skip_existing and find_private_context_fathom_recording(recording_id):
                continue
            meeting = parse_fathom_payload(
                item,
                project=project,
                tags=tags or ["fathom"],
                source_ref=f"fathom:{recording_id}",
            )
            meeting = apply_meeting_auto_route(meeting, auto_route=auto_route)
            results.append(
                write_meeting_record(
                    meeting,
                    destinations=destinations,
                    wiki_domain=wiki_domain,
                    backend=backend,
                    journal_space_id=journal_space_id,
                )
            )

        cursor = payload.get("next_cursor")
        if not cursor:
            break
        pages += 1

    return results


def list_fathom_meetings(
    *,
    account: str | None = None,
    limit: int = 10,
    created_after: str | None = None,
) -> list[dict[str, object]]:
    """Return recent Fathom meetings for discovery and testing."""

    client = FathomClient(account=account)
    payload = client.list_meetings(limit=limit, created_after=created_after)
    items = payload.get("items", [])
    return [item for item in items if isinstance(item, dict)]


def ingest_fathom_inbox(
    *,
    account: str | None = None,
    project: str = "",
    tags: list[str] | None = None,
    auto_route: bool = False,
    destinations: list[str] | None = None,
    wiki_domain: str | None = None,
    backend: str | None = None,
    journal_space_id: str | None = None,
    limit: int | None = None,
    keep: bool = False,
) -> list[MeetingIngestResult]:
    """Ingest archived Fathom webhook payloads from the local inbox."""

    results: list[MeetingIngestResult] = []
    files = list_inbox_files(account, state="pending")
    if limit is not None:
        files = files[:limit]

    for path in files:
        result = ingest_archived_fathom_payload(
            path,
            account=account,
            project=project,
            tags=tags,
            auto_route=auto_route,
            destinations=destinations,
            wiki_domain=wiki_domain,
            backend=backend,
            journal_space_id=journal_space_id,
            keep=keep,
        )
        if result is not None:
            results.append(result)

    return results


def ingest_archived_fathom_payload(
    path: Path,
    *,
    account: str | None = None,
    project: str = "",
    tags: list[str] | None = None,
    auto_route: bool = False,
    destinations: list[str] | None = None,
    wiki_domain: str | None = None,
    backend: str | None = None,
    journal_space_id: str | None = None,
    keep: bool = False,
) -> MeetingIngestResult | None:
    """Ingest one archived Fathom webhook payload into Jarvis destinations."""

    wrapper = load_archived_payload(path)
    payload = wrapper.get("payload")
    if not isinstance(payload, dict):
        move_inbox_file(path, account, state="invalid")
        return None
    meeting = parse_fathom_payload(
        payload,
        project=project,
        tags=tags or ["fathom"],
        source_ref=f"fathom-webhook:{payload.get('recording_id', '')}",
    )
    meeting = apply_meeting_auto_route(meeting, auto_route=auto_route)
    result = write_meeting_record(
        meeting,
        destinations=destinations,
        wiki_domain=wiki_domain,
        backend=backend,
        journal_space_id=journal_space_id,
    )
    if not keep:
        move_inbox_file(path, account, state="processed")
    return result


def load_meeting_record_from_source(
    source: str,
    *,
    resolver: str | None = None,
    backend: str | None = None,
    title: str | None = None,
    project: str = "",
    tags: list[str] | None = None,
) -> MeetingRecord:
    """Load and normalize a meeting record from any supported source."""

    source_doc = load_source_document(source, resolver=resolver, backend=backend)
    fathom_record = parse_fathom_json_text(
        source_doc.markdown,
        project=project,
        tags=tags,
        source_ref=source_doc.source_ref,
    )
    if fathom_record is not None:
        if title:
            return fathom_record.model_copy(update={"title": title})
        return fathom_record
    return parse_meeting_document(source_doc, title_override=title, project=project, tags=tags)


def apply_meeting_auto_route(
    meeting: MeetingRecord,
    *,
    auto_route: bool = False,
) -> MeetingRecord:
    """Infer a project for a meeting when routing is explicitly enabled."""

    if not auto_route or meeting.project:
        return meeting
    project = infer_meeting_project(meeting)
    if not project:
        return meeting
    return meeting.model_copy(update={"project": project})


def infer_meeting_project(meeting: MeetingRecord) -> str:
    """Infer a private-context project slug from route rules and project folders."""

    root = _resolve_private_context_root()
    rules = _load_meeting_route_rules(root)
    if not rules:
        return ""

    text = _meeting_route_text(meeting)
    scores: dict[str, int] = {}
    for project, keywords in rules.items():
        project_slug = safe_project_slug(project)
        if not project_slug:
            continue
        score = _score_route_keywords(text, [project_slug, *keywords])
        if score > 0:
            scores[project_slug] = max(scores.get(project_slug, 0), score)

    if not scores:
        return ""
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return ""
    return ranked[0][0]


def write_meeting_record(
    meeting: MeetingRecord,
    *,
    destinations: list[str] | None = None,
    wiki_domain: str | None = None,
    backend: str | None = None,
    journal_space_id: str | None = None,
) -> MeetingIngestResult:
    """Write a normalized meeting record to one or more destinations."""

    resolved_destinations = destinations or ["private-context"]
    rendered = render_meeting_markdown(meeting)
    result = MeetingIngestResult(meeting=meeting, destinations=resolved_destinations)

    for destination in resolved_destinations:
        if destination == "private-context":
            path = write_private_context_meeting(meeting, rendered)
            result.written_paths.append(str(path))
        elif destination == "wiki":
            if not wiki_domain:
                raise ValueError("--wiki-domain is required when using the wiki destination")
            path = write_wiki_meeting(wiki_domain, meeting, rendered)
            result.written_paths.append(str(path))
        elif destination == "journal":
            entry = write_journal_entry(
                meeting,
                rendered,
                backend=backend,
                space_id=journal_space_id,
            )
            result.journal_entry_id = entry
        elif destination == "memory":
            paths = write_meeting_memory(meeting)
            result.written_paths.extend(str(path) for path in paths)
        else:
            raise ValueError(f"Unsupported destination: {destination}")

    return result


def enrich_meeting_record(meeting: MeetingRecord) -> MeetingRecord:
    """Fill obvious missing sections using AI when available."""

    if meeting.summary and meeting.action_items and meeting.decisions:
        return meeting

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return meeting

    try:
        from anthropic import Anthropic
    except ImportError:
        return meeting

    prompt = build_enrichment_prompt(meeting)
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_AI_MODEL,
            max_tokens=1200,
            temperature=0.2,
            system=(
                "Extract structured meeting notes from transcripts. Return valid JSON only with "
                "keys: summary, detailed_summary, decisions, action_items, "
                "open_questions, participants."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        text = getattr(response.content[0], "text", "")
        parsed = parse_json_object(text)
    except Exception as exc:
        console.print(f"[yellow]AI enrichment skipped: {exc}[/yellow]")
        return meeting

    return meeting.model_copy(
        update={
            "summary": meeting.summary or parsed.get("summary", ""),
            "detailed_summary": meeting.detailed_summary or parsed.get("detailed_summary", ""),
            "decisions": meeting.decisions or coerce_str_list(parsed.get("decisions")),
            "action_items": meeting.action_items or coerce_str_list(parsed.get("action_items")),
            "open_questions": (
                meeting.open_questions or coerce_str_list(parsed.get("open_questions"))
            ),
            "participants": meeting.participants or coerce_str_list(parsed.get("participants")),
        }
    )


def build_enrichment_prompt(meeting: MeetingRecord) -> str:
    """Build the AI enrichment prompt for a partially structured meeting record."""

    transcript = meeting.transcript or meeting.raw_markdown
    if len(transcript) > 18000:
        transcript = transcript[:18000] + "\n\n[truncated]"
    return (
        f"Title: {meeting.title}\n"
        f"Date: {meeting.meeting_date.isoformat()}\n"
        f"Project: {meeting.project}\n\n"
        "Existing extracted fields:\n"
        f"Summary: {meeting.summary or '[missing]'}\n"
        f"Detailed Summary: {meeting.detailed_summary or '[missing]'}\n"
        f"Participants: {', '.join(meeting.participants) or '[missing]'}\n"
        f"Decisions: {meeting.decisions or '[missing]'}\n"
        f"Action Items: {meeting.action_items or '[missing]'}\n"
        f"Open Questions: {meeting.open_questions or '[missing]'}\n\n"
        "Transcript / notes:\n"
        f"{transcript}\n"
    )


def parse_json_object(text: str) -> dict[str, object]:
    """Extract and parse the first JSON object found in an AI response."""

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def coerce_str_list(value: object) -> list[str]:
    """Coerce a scalar or array-like value into a clean string list."""

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = re.split(r"\n|;", value)
        return [part.strip(" -") for part in parts if part.strip(" -")]
    return []


def write_private_context_meeting(meeting: MeetingRecord, rendered: str) -> Path:
    """Write a meeting artifact into the user's private context folder."""

    root = _resolve_private_context_root()
    project_slug = safe_project_slug(meeting.project)
    meetings_dir = (root / project_slug / "meetings") if project_slug else root / "meetings"
    target = meetings_dir / str(meeting.meeting_date.year) / meeting.meeting_date.strftime("%b")
    target.mkdir(parents=True, exist_ok=True)
    desired_path = target / private_context_meeting_filename(meeting)
    if desired_path.exists() and _meeting_note_matches(desired_path, meeting):
        return desired_path
    path = unique_path(desired_path)
    path.write_text(rendered, encoding="utf-8")
    return path


def find_private_context_fathom_recording(recording_id: str) -> Path | None:
    """Return an existing private-context meeting note for a Fathom recording."""

    root = _resolve_private_context_root()
    if not root.exists():
        return None
    needles = (
        f"Source Ref: fathom:{recording_id}",
        f"Source Ref: fathom-webhook:{recording_id}",
        f"Fingerprint: fathom:{recording_id}:",
    )
    for path in sorted(root.glob("**/meetings/**/*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(needle in text for needle in needles):
            return path
    return None


def write_wiki_meeting(domain: str, meeting: MeetingRecord, rendered: str) -> Path:
    """Write a meeting artifact into a wiki domain's raw notes folder."""

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        raise FileNotFoundError(f"Wiki domain not found: {domain}")
    notes_dir = domain_root / "raw" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = unique_path(notes_dir / meeting_filename(meeting))
    path.write_text(rendered, encoding="utf-8")
    return path


def write_journal_entry(
    meeting: MeetingRecord,
    rendered: str,
    *,
    backend: str | None = None,
    space_id: str | None = None,
) -> str:
    """Persist a meeting artifact as a backend journal entry."""

    service = JournalService(backend=backend)
    service.connect()
    entry = service.create_entry(
        title=meeting_journal_title(meeting),
        content=rendered,
        space_id=space_id,
        entry_date=meeting.meeting_date,
        tags=meeting.tags,
    )
    return entry.id


def write_meeting_memory(meeting: MeetingRecord) -> list[Path]:
    """Absorb durable meeting takeaways into the user's private memory files."""

    root = _resolve_private_context_root()
    written: list[Path] = []
    memory_key = _meeting_memory_key(meeting)

    event_body = _render_meeting_event_memory(meeting)
    if event_body:
        path = root / "events.md"
        _append_memory_entry(
            path,
            memory_id=f"{memory_key}:event",
            title=meeting.title,
            source=meeting.source_ref,
            created_at=meeting.meeting_date.isoformat(),
            body=event_body,
        )
        written.append(path)

    for index, decision in enumerate(meeting.decisions, start=1):
        path = root / "decisions.md"
        _append_memory_entry(
            path,
            memory_id=f"{memory_key}:decision:{index}",
            title=_memory_title(decision, fallback=f"{meeting.title} decision"),
            source=meeting.source_ref,
            created_at=meeting.meeting_date.isoformat(),
            body=decision,
        )
        written.append(path)

    return sorted(set(written), key=str)


def _render_meeting_event_memory(meeting: MeetingRecord) -> str:
    """Build the compact event-memory body for one meeting."""

    sections: list[str] = []
    summary = _meeting_memory_summary(meeting)
    if summary:
        sections.extend(["### Summary", summary])
    if meeting.decisions:
        sections.extend(["### Decisions", _markdown_list(meeting.decisions)])
    if meeting.action_items:
        sections.extend(["### Next Steps", _markdown_list(meeting.action_items)])
    if meeting.open_questions:
        sections.extend(["### Open Questions", _markdown_list(meeting.open_questions)])
    source_lines = [f"- Source Ref: {meeting.source_ref}"]
    if meeting.project:
        source_lines.append(f"- Project: {meeting.project}")
    if meeting.tags:
        source_lines.append(f"- Tags: {', '.join(meeting.tags)}")
    sections.extend(["### Source", "\n".join(source_lines)])
    return "\n\n".join(section for section in sections if section).strip()


def _meeting_memory_summary(meeting: MeetingRecord) -> str:
    """Choose a useful summary for memory, even when Fathom uses custom headings."""

    candidates = [
        meeting.summary,
        _extract_heading_body(meeting.raw_markdown, "Key Takeaways"),
        _extract_heading_body(meeting.detailed_summary, "Key Takeaways"),
        _extract_heading_body(meeting.raw_markdown, "Meeting Purpose"),
        _extract_heading_body(meeting.detailed_summary, "Meeting Purpose"),
        meeting.detailed_summary,
    ]
    for candidate in candidates:
        cleaned = _compact_markdown(candidate)
        if cleaned:
            return cleaned
    return ""


def _extract_heading_body(markdown: str, heading: str) -> str:
    """Extract the body under a markdown heading, stopping at the next same-or-higher heading."""

    if not markdown:
        return ""
    target = heading.strip().lower()
    lines = markdown.splitlines()
    collecting = False
    heading_level = 0
    body: list[str] = []
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            current_level = len(match.group(1))
            current_heading = match.group(2).strip().lower().rstrip(":")
            if collecting and current_level <= heading_level:
                break
            if current_heading == target:
                collecting = True
                heading_level = current_level
                continue
        if collecting:
            body.append(line)
    return "\n".join(body).strip()


def _compact_markdown(markdown: str, *, max_chars: int = 1800) -> str:
    """Trim generated meeting markdown into a memory-friendly digest."""

    cleaned = markdown.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars].rsplit("\n", 1)[0].strip()
    return truncated + "\n\n[truncated]"


def _append_memory_entry(
    path: Path,
    *,
    memory_id: str,
    title: str,
    source: str,
    created_at: str,
    body: str,
) -> None:
    """Append one idempotent entry to a private memory file."""

    _ensure_memory_file(path)
    existing = path.read_text(encoding="utf-8", errors="ignore")
    if f'memory_id: "{memory_id}"' in existing:
        return
    block = (
        "\n---\n"
        f"created_at: {created_at}\n"
        "status: active\n"
        f"source: {json.dumps(source)}\n"
        f"title: {json.dumps(title)}\n"
        f"memory_id: {json.dumps(memory_id)}\n"
        "---\n\n"
        f"{body.strip()}\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write(block)


def _ensure_memory_file(path: Path) -> None:
    """Create a private memory file with the standard header when missing."""

    if path.exists():
        return
    memory_type = path.stem
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {memory_type.title()}\n\n"
        f"> Scoped to: user:{_USERNAME}\n"
        f"> Memory type: {memory_type}\n"
        "> One entry per `---` block with YAML frontmatter "
        "(created_at, status, source)\n",
        encoding="utf-8",
    )


def _meeting_memory_key(meeting: MeetingRecord) -> str:
    """Return a stable compact key for idempotent meeting memory entries."""

    base = meeting.fingerprint or meeting.source_ref or f"{meeting.title}:{meeting.meeting_date}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
    return f"meeting:{digest}"


def _memory_title(text: str, *, fallback: str) -> str:
    """Make a compact memory entry title from a decision/action string."""

    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return fallback
    return cleaned[:90].rstrip(" .") + ("..." if len(cleaned) > 90 else "")


def _markdown_list(items: list[str]) -> str:
    """Render a list of strings as markdown bullets."""

    return "\n".join(f"- {item}" for item in items if item.strip())


def private_context_meeting_filename(meeting: MeetingRecord) -> str:
    """Build the private-context meeting filename: dd-title.md."""

    slug = slug_from_title(meeting.title) or "meeting"
    return f"{meeting.meeting_date.strftime('%d')}-{slug}.md"


MEETING_JOURNAL_TITLE_PREFIX = "Meeting - "


def meeting_journal_title(meeting: MeetingRecord) -> str:
    """Title used when syncing a meeting to a backend journal (e.g. Anytype Flow Space).

    The JournalHierarchy prepends the day number (e.g. ``15 - <title>``).
    Meetings additionally carry a ``Meeting - `` marker so synced entries
    read as ``dd - Meeting - <title>`` and group cleanly alongside other
    journal entries from the same day.

    Idempotent: if ``meeting.title`` already starts with the marker
    (case-insensitive), it is returned unchanged so re-ingestion does
    not double-prefix.
    """

    title = (meeting.title or "Untitled Meeting").strip()
    if title.lower().startswith(MEETING_JOURNAL_TITLE_PREFIX.lower()):
        return title
    return f"{MEETING_JOURNAL_TITLE_PREFIX}{title}"


def _meeting_note_matches(path: Path, meeting: MeetingRecord) -> bool:
    """Return True when an existing note is the same meeting artifact."""

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    needles = []
    if meeting.fingerprint:
        needles.append(f"Fingerprint: {meeting.fingerprint}")
    if meeting.source_ref:
        needles.append(f"Source Ref: {meeting.source_ref}")
    return bool(needles) and any(needle in text for needle in needles)


def safe_project_slug(project: str) -> str:
    """Normalize a project label into a private-context folder name."""

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", project.strip()).strip(".-")
    return cleaned.lower()


def _load_meeting_route_rules(root: Path) -> dict[str, list[str]]:
    """Load route keywords from private config and project folder names."""

    rules = _discover_project_route_rules(root)
    config_path = root / _MEETING_ROUTE_CONFIG
    if config_path.exists():
        rules = _merge_route_rules(rules, _read_meeting_route_config(config_path))
    return rules


def _discover_project_route_rules(root: Path) -> dict[str, list[str]]:
    """Use existing private project folders as exact-match route hints."""

    if not root.exists():
        return {}
    rules: dict[str, list[str]] = {}
    for path in root.iterdir():
        if not path.is_dir() or path.name in _ROUTE_EXCLUDED_DIRS:
            continue
        has_project_context = (path / "status.md").exists() or (path / "meetings").is_dir()
        if not has_project_context:
            continue
        slug = safe_project_slug(path.name)
        if slug:
            rules[slug] = [slug.replace("-", " ")]
    return rules


def _read_meeting_route_config(path: Path) -> dict[str, list[str]]:
    """Read optional private meeting route rules."""

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}

    raw_routes = data.get("routes") if isinstance(data, dict) else data
    rules: dict[str, list[str]] = {}
    if isinstance(raw_routes, dict):
        for project, keywords in raw_routes.items():
            if isinstance(keywords, list):
                rules[str(project)] = [str(keyword) for keyword in keywords]
            elif isinstance(keywords, str):
                rules[str(project)] = [keywords]
        return rules

    if isinstance(raw_routes, list):
        for entry in raw_routes:
            if not isinstance(entry, dict):
                continue
            project = str(entry.get("project") or "").strip()
            keywords = entry.get("keywords", [])
            if not project:
                continue
            if isinstance(keywords, list):
                rules[project] = [str(keyword) for keyword in keywords]
            elif isinstance(keywords, str):
                rules[project] = [keywords]
    return rules


def _merge_route_rules(
    base: dict[str, list[str]],
    overrides: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Merge route rules keyed by normalized project slug."""

    merged = {safe_project_slug(project): list(keywords) for project, keywords in base.items()}
    for project, keywords in overrides.items():
        slug = safe_project_slug(project)
        if not slug:
            continue
        existing = merged.setdefault(slug, [])
        for keyword in keywords:
            cleaned = keyword.strip()
            if cleaned and cleaned not in existing:
                existing.append(cleaned)
    return merged


def _meeting_route_text(meeting: MeetingRecord) -> str:
    """Build the searchable text used by the route scorer."""

    parts = [
        meeting.title,
        " ".join(meeting.participants),
        meeting.summary,
        meeting.detailed_summary,
        " ".join(meeting.decisions),
        " ".join(meeting.action_items),
        " ".join(meeting.open_questions),
        meeting.raw_markdown[:4000],
        meeting.transcript[:4000],
    ]
    return _normalize_route_text("\n".join(part for part in parts if part))


def _score_route_keywords(text: str, keywords: list[str]) -> int:
    """Score exact normalized keyword matches in meeting text."""

    padded_text = f" {text} "
    score = 0
    seen: set[str] = set()
    for keyword in keywords:
        normalized = _normalize_route_text(keyword)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if f" {normalized} " not in padded_text:
            continue
        score += max(1, len(normalized.split()))
    return score


def _normalize_route_text(value: str) -> str:
    """Normalize route matching text without allowing substring matches."""

    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _resolve_private_context_root() -> Path:
    """Locate .jarvis/context/private/<user>, following the note command convention."""

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        user_ctx = parent / ".jarvis" / "context" / "private" / _USERNAME
        if user_ctx.is_dir():
            user_ctx.mkdir(parents=True, exist_ok=True)
            return user_ctx
    fallback = cwd / ".jarvis" / "context" / "private" / _USERNAME
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def unique_path(path: Path) -> Path:
    """Return a non-colliding path by appending a numeric suffix when needed."""

    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
