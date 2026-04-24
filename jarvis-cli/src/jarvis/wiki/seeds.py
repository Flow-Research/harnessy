"""Per-domain research seed queue (`seeds.md`).

`seeds.md` is the user-supplied input queue for autonomous research. The user
adds URLs, topics, and notes via `jarvis wiki seed`; the research agent reads
the Pending section, processes entries, and moves them to Processed.

Format is markdown with two H2 sections (`## Pending`, `## Processed`) and one
H3 per seed: `### <kind> — <value>`. Each seed has free-form `key: value`
metadata lines on subsequent lines until the next H3 or H2.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

SEEDS_FILENAME = "seeds.md"


class SeedKind(str, Enum):
    URL = "URL"
    TOPIC = "Topic"
    NOTE = "Note"


class SeedPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Seed(BaseModel):
    """One entry in `seeds.md`.

    Fields are loose by design — the research agent reads `value` and the
    optional `notes` field; everything else is metadata for humans.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    kind: SeedKind
    value: str
    notes: str = ""
    priority: SeedPriority = SeedPriority.MEDIUM
    added: date = Field(default_factory=date.today)
    # Populated only when the seed is in the Processed section
    processed: date | None = None
    session: str | None = None
    result: str | None = None


class SeedsFile(BaseModel):
    """In-memory representation of one `seeds.md` file."""

    domain: str
    pending: list[Seed] = Field(default_factory=list)
    processed: list[Seed] = Field(default_factory=list)

    def pending_count(self) -> int:
        return len(self.pending)

    def processed_count(self) -> int:
        return len(self.processed)


# ── parser ────────────────────────────────────────────────────────────────────


_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_KV_RE = re.compile(r"^([a-z_][a-z0-9_]*)\s*:\s*(.+?)\s*$", re.IGNORECASE)


def seeds_path(domain_root: Path) -> Path:
    """Return the canonical path to `seeds.md` for a domain."""
    return domain_root / SEEDS_FILENAME


def parse_seeds(text: str, domain: str) -> SeedsFile:
    """Parse a `seeds.md` body into a `SeedsFile`. Empty input → empty file."""
    sf = SeedsFile(domain=domain)
    if not text.strip():
        return sf

    sections = _split_h2_sections(text)
    for header, body in sections.items():
        normalized = header.strip().lower()
        if normalized == "pending":
            sf.pending = _parse_seed_block(body, processed=False)
        elif normalized == "processed":
            sf.processed = _parse_seed_block(body, processed=True)
    return sf


def load_seeds(domain_root: Path, domain: str) -> SeedsFile:
    """Read and parse `<domain_root>/seeds.md`. Returns empty if absent."""
    path = seeds_path(domain_root)
    if not path.exists():
        return SeedsFile(domain=domain)
    return parse_seeds(path.read_text(encoding="utf-8"), domain)


def serialize_seeds(sf: SeedsFile) -> str:
    """Render a `SeedsFile` back to markdown.

    Output format matches what `parse_seeds` accepts. Sections always appear
    in the order Pending → Processed even if one is empty.
    """
    lines: list[str] = [f"# {sf.domain} Research Seeds", ""]
    lines.append("## Pending")
    lines.append("")
    if not sf.pending:
        lines.append("_(none)_")
        lines.append("")
    else:
        for seed in sf.pending:
            lines.extend(_render_seed(seed))
    lines.append("## Processed")
    lines.append("")
    if not sf.processed:
        lines.append("_(none)_")
        lines.append("")
    else:
        for seed in sf.processed:
            lines.extend(_render_seed(seed))
    return "\n".join(lines).rstrip() + "\n"


def write_seeds(domain_root: Path, sf: SeedsFile) -> None:
    """Write a `SeedsFile` to `<domain_root>/seeds.md`."""
    path = seeds_path(domain_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_seeds(sf), encoding="utf-8")


def append_seed(domain_root: Path, domain: str, seed: Seed) -> SeedsFile:
    """Load, append a new pending seed, and write back. Returns the updated file."""
    sf = load_seeds(domain_root, domain)
    sf.pending.append(seed)
    write_seeds(domain_root, sf)
    return sf


def mark_processed(
    domain_root: Path,
    domain: str,
    seed_id: str,
    session: str,
    result: str,
) -> SeedsFile | None:
    """Move a pending seed to the Processed section.

    Returns the updated `SeedsFile`, or None if the seed id was not found.
    """
    sf = load_seeds(domain_root, domain)
    for i, seed in enumerate(sf.pending):
        if seed.id == seed_id:
            seed.processed = date.today()
            seed.session = session
            seed.result = result
            sf.processed.append(seed)
            sf.pending.pop(i)
            write_seeds(domain_root, sf)
            return sf
    return None


# ── private parser helpers ────────────────────────────────────────────────────


def _split_h2_sections(text: str) -> dict[str, str]:
    """Split text into {h2_header: body} pairs."""
    sections: dict[str, str] = {}
    matches = list(_H2_RE.finditer(text))
    for i, m in enumerate(matches):
        header = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[header] = text[start:end].strip("\n")
    return sections


def _parse_seed_block(body: str, processed: bool) -> list[Seed]:
    """Parse a section body into a list of Seeds, one per H3."""
    seeds: list[Seed] = []
    matches = list(_H3_RE.finditer(body))
    for i, m in enumerate(matches):
        header = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        seed_body = body[start:end].strip("\n")
        seed = _parse_one_seed(header, seed_body, processed)
        if seed is not None:
            seeds.append(seed)
    return seeds


def _parse_one_seed(header: str, body: str, processed: bool) -> Seed | None:
    """Parse a single H3 + body block into a Seed.

    Header format: `<Kind> — <value>` or `<Kind> - <value>`.
    """
    parts = re.split(r"\s+[—-]\s+", header.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    kind_raw, value = parts[0].strip(), parts[1].strip()
    try:
        kind = SeedKind(kind_raw)
    except ValueError:
        # Tolerate lowercase / mismatched casing
        try:
            kind = SeedKind(kind_raw.title())
        except ValueError:
            return None

    seed = Seed(kind=kind, value=value)
    for line in body.splitlines():
        kv = _KV_RE.match(line.strip())
        if not kv:
            continue
        key = kv.group(1).lower()
        val = kv.group(2).strip()
        if key == "id":
            seed.id = val
        elif key == "notes":
            seed.notes = val
        elif key == "priority":
            try:
                seed.priority = SeedPriority(val.lower())
            except ValueError:
                pass
        elif key == "added":
            try:
                seed.added = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                pass
        elif key == "processed":
            try:
                seed.processed = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                pass
        elif key == "session":
            seed.session = val
        elif key == "result":
            seed.result = val
    if not processed:
        seed.processed = None
        seed.session = None
        seed.result = None
    return seed


def _render_seed(seed: Seed) -> list[str]:
    """Render a single seed back to markdown lines."""
    lines = [f"### {seed.kind.value} — {seed.value}"]
    lines.append(f"id: {seed.id}")
    if seed.notes:
        lines.append(f"notes: {seed.notes}")
    lines.append(f"priority: {seed.priority.value}")
    lines.append(f"added: {seed.added.isoformat()}")
    if seed.processed:
        lines.append(f"processed: {seed.processed.isoformat()}")
    if seed.session:
        lines.append(f"session: {seed.session}")
    if seed.result:
        lines.append(f"result: {seed.result}")
    lines.append("")
    return lines
