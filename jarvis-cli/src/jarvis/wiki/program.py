"""Per-domain research steering file (`program.md`).

`program.md` is the human control surface for autonomous research. It lives at
`<domain>/program.md` alongside `schema.yaml` and is read at the start of every
`jarvis wiki research` session. Agents never write to it.

Format is forgiving Markdown with H2 sections. Each section maps to a field on
the `Program` model. Unknown sections are tolerated and warned about.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

# Path of the steering file relative to a domain root
PROGRAM_FILENAME = "program.md"


class TopicDepth(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Topic(BaseModel):
    """One active research topic with priority and last-researched timestamp."""

    name: str
    depth: TopicDepth = TopicDepth.MEDIUM
    last_researched: date | None = None
    notes: str = ""


class SourcePreferences(BaseModel):
    """Preferred and deprioritized source domains for the research agent."""

    prefer: list[str] = Field(default_factory=list)
    deprioritize: list[str] = Field(default_factory=list)


class QualityThresholds(BaseModel):
    """Quality bars the research agent and lint should respect."""

    min_sources_per_concept: int = 3
    min_words_per_concept: int = 200
    max_duplicate_concepts: int = 0


class Cadence(BaseModel):
    """How often and how much the research agent runs."""

    autonomous_research: str = "manual"  # daily | weekly | manual
    schedule: str = ""  # e.g. "04:00" — interpreted by cron, not by Jarvis
    max_sources_per_session: int = 5
    include_in_morning_brief: bool = True


class Program(BaseModel):
    """Parsed `program.md` for a wiki domain."""

    domain: str
    active_topics: list[Topic] = Field(default_factory=list)
    avoid_topics: list[str] = Field(default_factory=list)
    source_preferences: SourcePreferences = Field(default_factory=SourcePreferences)
    quality_thresholds: QualityThresholds = Field(default_factory=QualityThresholds)
    cadence: Cadence = Field(default_factory=Cadence)
    raw_text: str = ""
    parse_warnings: list[str] = Field(default_factory=list)


# ── parser ────────────────────────────────────────────────────────────────────


_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")
_KV_RE = re.compile(r"^([a-z_][a-z0-9_]*)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_TOPIC_DEPTH_RE = re.compile(r"\bdepth\s*:\s*(high|medium|low)\b", re.IGNORECASE)
_TOPIC_LAST_RE = re.compile(r"\blast[_-]researched\s*:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
# HTML comments — stripped before parsing so example content inside <!-- -->
# blocks in the template doesn't get interpreted as live topics or fields.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def program_path(domain_root: Path) -> Path:
    """Return the canonical path to `program.md` for a domain."""
    return domain_root / PROGRAM_FILENAME


def parse_program(text: str, domain: str) -> Program:
    """Parse a `program.md` body into a `Program` model.

    Forgiving by design: unknown sections, missing sections, and malformed
    lines produce warnings stored on `Program.parse_warnings` rather than
    exceptions. Empty input returns a default `Program`.
    """
    program = Program(domain=domain, raw_text=text)
    if not text.strip():
        return program

    # Strip HTML comments so example content in templates is ignored.
    cleaned = _HTML_COMMENT_RE.sub("", text)
    sections = _split_sections(cleaned)
    known = {
        "active topics",
        "avoid topics",
        "source preferences",
        "quality thresholds",
        "cadence",
    }

    for header, body in sections.items():
        normalized = header.strip().lower()
        if normalized == "active topics":
            program.active_topics = _parse_active_topics(body, program)
        elif normalized == "avoid topics":
            program.avoid_topics = _parse_bullet_list(body)
        elif normalized == "source preferences":
            program.source_preferences = _parse_source_preferences(body)
        elif normalized == "quality thresholds":
            program.quality_thresholds = _parse_quality_thresholds(body, program)
        elif normalized == "cadence":
            program.cadence = _parse_cadence(body, program)
        elif normalized not in known:
            program.parse_warnings.append(f"Unknown section '## {header}' — ignored")

    return program


def load_program(domain_root: Path, domain: str) -> Program:
    """Read and parse `<domain_root>/program.md`. Returns default if absent."""
    path = program_path(domain_root)
    if not path.exists():
        return Program(domain=domain)
    return parse_program(path.read_text(encoding="utf-8"), domain)


# ── private parser helpers ────────────────────────────────────────────────────


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown text into {h2_header: body} pairs.

    Content before the first H2 is dropped. Headers are stored as-is so the
    parser can preserve original casing in warnings.
    """
    sections: dict[str, str] = {}
    matches = list(_H2_RE.finditer(text))
    for i, m in enumerate(matches):
        header = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[header] = text[start:end].strip("\n")
    return sections


def _parse_bullet_list(body: str) -> list[str]:
    """Extract the text after each `-` or `*` bullet, ignoring empty entries."""
    items: list[str] = []
    for line in body.splitlines():
        m = _BULLET_RE.match(line.strip())
        if m:
            items.append(m.group(1).strip())
    return items


def _parse_active_topics(body: str, program: Program) -> list[Topic]:
    """Parse bullet lines like `- Decentralized identity — depth: high`.

    Format (whitespace-flexible):
        - <topic name> [— depth: high|medium|low] [— last_researched: YYYY-MM-DD]
    """
    topics: list[Topic] = []
    for line in body.splitlines():
        bullet = _BULLET_RE.match(line.strip())
        if not bullet:
            continue
        raw = bullet.group(1).strip()

        depth = TopicDepth.MEDIUM
        depth_match = _TOPIC_DEPTH_RE.search(raw)
        if depth_match:
            try:
                depth = TopicDepth(depth_match.group(1).lower())
            except ValueError:
                program.parse_warnings.append(f"Invalid depth in topic '{raw}'")

        last_researched: date | None = None
        last_match = _TOPIC_LAST_RE.search(raw)
        if last_match:
            try:
                last_researched = datetime.strptime(last_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                program.parse_warnings.append(f"Invalid last_researched date in topic '{raw}'")

        # The topic name is everything before the first " —" or " -" qualifier
        name = re.split(r"\s+[—-]\s+", raw, maxsplit=1)[0].strip()
        if not name:
            continue
        topics.append(Topic(name=name, depth=depth, last_researched=last_researched))
    return topics


def _parse_source_preferences(body: str) -> SourcePreferences:
    """Parse `prefer: a, b, c` and `deprioritize: x, y` lines."""
    prefs = SourcePreferences()
    for line in body.splitlines():
        m = _KV_RE.match(line.strip())
        if not m:
            continue
        key = m.group(1).lower()
        value = m.group(2)
        items = [item.strip() for item in value.split(",") if item.strip()]
        if key == "prefer":
            prefs.prefer = items
        elif key == "deprioritize":
            prefs.deprioritize = items
    return prefs


def _parse_quality_thresholds(body: str, program: Program) -> QualityThresholds:
    """Parse `key: int` lines into a QualityThresholds model."""
    fields = {
        "min_sources_per_concept",
        "min_words_per_concept",
        "max_duplicate_concepts",
    }
    values: dict[str, int] = {}
    for line in body.splitlines():
        m = _KV_RE.match(line.strip())
        if not m:
            continue
        key = m.group(1).lower()
        if key not in fields:
            continue
        try:
            values[key] = int(m.group(2).strip())
        except ValueError:
            program.parse_warnings.append(
                f"Quality threshold '{key}' is not an integer: {m.group(2)!r}"
            )
    return QualityThresholds(**values) if values else QualityThresholds()


def _parse_cadence(body: str, program: Program) -> Cadence:
    """Parse cadence key: value lines."""
    cad = Cadence()
    for line in body.splitlines():
        m = _KV_RE.match(line.strip())
        if not m:
            continue
        key = m.group(1).lower()
        value = m.group(2).strip()
        if key == "autonomous_research":
            if value not in ("daily", "weekly", "manual"):
                program.parse_warnings.append(
                    f"autonomous_research must be daily|weekly|manual, got {value!r}"
                )
            else:
                cad.autonomous_research = value
        elif key == "schedule":
            cad.schedule = value
        elif key == "max_sources_per_session":
            try:
                cad.max_sources_per_session = int(value)
            except ValueError:
                program.parse_warnings.append(
                    f"max_sources_per_session must be an integer, got {value!r}"
                )
        elif key == "include_in_morning_brief":
            cad.include_in_morning_brief = value.lower() in (
                "true",
                "yes",
                "on",
                "1",
            )
    return cad
