"""Source parser for jarvis wiki ingestion.

Handles reading and normalizing raw sources from .md, .pdf, .txt files
and URLs into RawSource models with consistent slug and title extraction.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from jarvis.wiki.models import RawSource, SourceType


def slug_from_title(title: str) -> str:
    """Generate a kebab-case slug from a title string.

    Args:
        title: Human-readable title

    Returns:
        Lowercase kebab-case slug (e.g. "My Article" → "my-article")
    """
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:80]


# Suffixes stripped during comparison (longest first to avoid partial matches).
# Only used for similarity matching — actual slugs preserve their full form.
# This is heuristic: it catches the common "X" vs "X-protocol" / "X-framework"
# pattern but cannot resolve semantic equivalents like "a2a-protocol" vs
# "agent-to-agent-protocol" (those need the LLM is_same_entity classifier).
_COMPARE_SUFFIXES = (
    "-agent-framework",
    "-protocol-v2",
    "-protocol-v1",
    "-marketplace",
    "-blockchain",
    "-framework",
    "-protocol",
    "-standard",
    "-network",
    "-platform",
    "-library",
    "-system",
    "-agent",
    "-spec",
    "-model",
)


def normalize_for_comparison(slug: str) -> str:
    """Reduce a slug to a comparison key for similarity matching.

    Strips common qualifying suffixes ("-protocol", "-framework", etc.),
    drops trailing plural "s", and removes hyphens. Used ONLY for matching
    candidate concepts against existing ones — never written to disk.

    Examples:
        react-agent-framework → react
        a2a-protocol           → a2a
        ai-os-agents           → aiosagent
        agents                 → agent
    """
    s = slug.lower().strip()
    # Strip suffixes, repeatedly to catch e.g. "-agent-framework" then "-protocol"
    changed = True
    while changed:
        changed = False
        for suffix in _COMPARE_SUFFIXES:
            if s.endswith(suffix) and len(s) > len(suffix) + 2:
                s = s[: -len(suffix)]
                changed = True
                break
    # Singularize trailing plural (avoid "as", "is", "us")
    if s.endswith("s") and not s.endswith(("as", "is", "us", "ss")):
        s = s[:-1]
    return s.replace("-", "")


def slug_similarity(a: str, b: str) -> float:
    """Token-set Jaccard similarity between two kebab-case slugs.

    Splits on hyphens and computes |A ∩ B| / |A ∪ B|. Returns 0.0 if either
    is empty. Used as a fast pre-filter before invoking the LLM dedup
    classifier.

    Examples:
        react-agent-framework vs react-framework  → 2/3 = 0.667
        a2a vs a2a-protocol                        → 1/2 = 0.500
        cosmos vs cosmos-blockchain                → 1/2 = 0.500
        apple vs microsoft                         → 0/2 = 0.000
    """
    tokens_a = {t for t in a.split("-") if t}
    tokens_b = {t for t in b.split("-") if t}
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def ingest_to_raw(
    source: str,
    domain_root: Path,
    source_type: SourceType,
    title: str | None = None,
) -> Path:
    """Copy or fetch a source into the raw/ subdirectory with dated naming.

    Fetches URLs, copies local files, or passes through already-raw paths.
    The destination filename follows the YYYY-MM-DD-<slug>.md convention.

    Args:
        source: File path string or URL
        domain_root: Root directory of the wiki domain
        source_type: SourceType enum value
        title: Optional display title; inferred from content/filename if absent

    Returns:
        Path to the written raw file
    """
    today = date.today().strftime("%Y-%m-%d")
    raw_dir = domain_root / "raw" / f"{source_type.value}s"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if source.startswith(("http://", "https://")):
        text, inferred_title = _fetch_url(source)
        resolved_title = title or inferred_title or _title_from_url(source)
        slug = slug_from_title(resolved_title)
        dest = raw_dir / f"{today}-{slug}.md"
        # Prepend a YAML-ish title comment for downstream parsing
        dest.write_text(f"# {resolved_title}\n\n{text}", encoding="utf-8")
    else:
        src_path = Path(source)
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        if src_path.suffix.lower() == ".pdf":
            text, inferred_title = _extract_pdf(src_path)
        else:
            text = src_path.read_text(encoding="utf-8", errors="replace")
            inferred_title = None

        resolved_title = (
            title or inferred_title or src_path.stem.replace("-", " ").replace("_", " ")
        )
        slug = slug_from_title(resolved_title)
        dest = raw_dir / f"{today}-{slug}.md"

        if src_path.suffix.lower() in {".md", ".txt"}:
            # Copy as-is; ensure a title heading exists at top
            if not text.lstrip().startswith("#"):
                dest.write_text(f"# {resolved_title}\n\n{text}", encoding="utf-8")
            else:
                dest.write_text(text, encoding="utf-8")
        else:
            dest.write_text(f"# {resolved_title}\n\n{text}", encoding="utf-8")

    return dest


class SourceParser:
    """Parse raw source files into normalized RawSource models."""

    def parse(self, path: Path, source_type: SourceType) -> RawSource:
        """Read and normalize a raw source file.

        Dispatches to the appropriate reader based on file suffix, extracts
        title and body text, and returns a fully populated RawSource.

        Args:
            path: Path to the raw source file
            source_type: Type of source (article, paper, note, etc.)

        Returns:
            Populated RawSource model
        """
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            body_text, title = _extract_pdf(path)
        elif suffix in {".md", ".txt", ""}:
            body_text = path.read_text(encoding="utf-8", errors="replace")
            title = _extract_md_title(body_text) or _title_from_stem(path.stem)
        else:
            # Fallback: read as text
            body_text = path.read_text(encoding="utf-8", errors="replace")
            title = _title_from_stem(path.stem)

        if not title:
            title = _title_from_stem(path.stem)

        slug = _slug_from_stem(path.stem)
        source_date = _date_from_stem(path.stem)

        return RawSource(
            slug=slug,
            path=path,
            source_type=source_type,
            title=title,
            source_date=source_date,
            body_text=body_text,
        )


# ── Private helpers ────────────────────────────────────────────────────────────


def _extract_md_title(text: str) -> str | None:
    """Return the first # heading found in markdown text, or None."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _title_from_stem(stem: str) -> str:
    """Convert a filename stem to a display title.

    Strips the leading YYYY-MM-DD- date prefix if present, then converts
    dashes and underscores to spaces and title-cases the result.
    """
    # Remove leading date prefix like 2026-04-05-
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
    return name.replace("-", " ").replace("_", " ").title()


def _slug_from_stem(stem: str) -> str:
    """Derive a clean slug from a filename stem, removing date prefixes."""
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
    return slug_from_title(slug) or stem


def _date_from_stem(stem: str) -> date | None:
    """Extract a date from a YYYY-MM-DD-prefixed filename stem."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", stem)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _title_from_url(url: str) -> str:
    """Derive a rough title from a URL path."""
    path = url.rstrip("/").split("/")[-1]
    path = re.sub(r"\.\w+$", "", path)  # remove extension
    return path.replace("-", " ").replace("_", " ").title() or "Untitled"


def _fetch_url(url: str) -> tuple[str, str | None]:
    """Fetch a URL and extract main content with trafilatura.

    Args:
        url: The URL to fetch

    Returns:
        Tuple of (extracted_text, title_or_None)
    """
    try:
        import httpx
        import trafilatura

        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        html = response.text

        # trafilatura for clean article extraction
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="markdown",
        )
        title = trafilatura.extract_metadata(html)
        title_str = title.title if title and title.title else None

        return extracted or html, title_str
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch URL {url}: {exc}") from exc


def _extract_pdf(path: Path) -> tuple[str, str | None]:
    """Extract text and title from a PDF file using pypdf.

    Args:
        path: Path to the PDF file

    Returns:
        Tuple of (extracted_text, title_or_None)
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))

        # Try metadata title first
        title: str | None = None
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title).strip()

        pages_text: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

        body = "\n\n".join(pages_text)

        # Fall back to first non-empty line as title
        if not title:
            for line in body.splitlines():
                line = line.strip()
                if len(line) > 5:
                    title = line[:120]
                    break

        return body, title
    except Exception as exc:
        raise RuntimeError(f"Failed to extract PDF {path}: {exc}") from exc
