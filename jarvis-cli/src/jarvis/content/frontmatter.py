"""YAML frontmatter parser and writer for content markdown files.

Handles the --- delimited YAML frontmatter block at the top of content files.
Supports reading, updating individual fields, and scanning directories for drafts.
"""

from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and body from a markdown file.

    Args:
        path: Path to the markdown file

    Returns:
        Tuple of (frontmatter dict, body string).
        If no frontmatter found, returns ({}, full content).
    """
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return {}, text

    # Find the closing ---
    end = text.find("---", 3)
    if end == -1:
        return {}, text

    yaml_block = text[3:end].strip()
    body = text[end + 3:].lstrip("\n")

    try:
        fm = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return {}, text

    return fm, body


def render_frontmatter(fm: dict[str, Any], body: str) -> str:
    """Render frontmatter dict and body back to markdown string.

    Args:
        fm: Frontmatter dictionary
        body: Markdown body content

    Returns:
        Complete markdown string with --- delimited frontmatter
    """
    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"---\n{yaml_str}---\n\n{body}"


def update_frontmatter(path: Path, updates: dict[str, Any]) -> None:
    """Update specific frontmatter fields without touching the body.

    Args:
        path: Path to the markdown file
        updates: Dict of fields to update (merged into existing frontmatter)
    """
    fm, body = parse_frontmatter(path)
    fm.update(updates)
    path.write_text(render_frontmatter(fm, body), encoding="utf-8")


def find_drafts(
    base_dir: Path,
    status: str | None = None,
) -> list[Path]:
    """Find all content piece directories containing index.md.

    Args:
        base_dir: Root directory to scan (e.g., .jarvis/.../flow-content/drafts)
        status: If provided, only return pieces with this status in frontmatter

    Returns:
        List of paths to piece directories (parent of index.md), sorted by name
    """
    pieces = []
    for index_file in sorted(base_dir.rglob("index.md")):
        if status is not None:
            fm, _ = parse_frontmatter(index_file)
            if fm.get("status") != status:
                continue
        pieces.append(index_file.parent)
    return pieces
