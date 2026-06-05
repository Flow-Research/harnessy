"""Helpers for storing markdown bodies in knowledge-base tools."""

from __future__ import annotations

import re

_H1_RE = re.compile(r"^(?P<indent>[ \t]*)#(?!#)\s+(?P<title>.+?)\s*#*\s*$")
_JOURNAL_DAY_PREFIX_RE = re.compile(r"^\d{1,2}\s*[-.\u2013\u2014]\s*")
_SPACE_RE = re.compile(r"\s+")


def strip_duplicate_title_heading(markdown: str, title: str | None) -> str:
    """Remove a leading H1 when it duplicates the object title.

    Knowledge tools already display the page title outside the body. When a
    markdown file also starts with the same ``# Title`` heading, storing both
    creates duplicate visible titles in Anytype/Notion pages.
    """
    if not markdown or not title:
        return markdown

    frontmatter, body = _split_leading_frontmatter(markdown)
    leading_ws_len = len(body) - len(body.lstrip())
    leading_ws = body[:leading_ws_len]
    stripped_body = body[leading_ws_len:]

    if not stripped_body:
        return markdown

    first_line_end = stripped_body.find("\n")
    if first_line_end == -1:
        first_line = stripped_body
        remainder = ""
    else:
        first_line = stripped_body[:first_line_end]
        remainder = stripped_body[first_line_end + 1 :]

    match = _H1_RE.match(first_line)
    if not match:
        return markdown

    heading_title = match.group("title").strip()
    if _normalize_title(heading_title) != _normalize_title(title):
        return markdown

    return frontmatter + leading_ws + remainder.lstrip("\n")


def _split_leading_frontmatter(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", markdown

    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() in {"---", "..."}:
            split_at = idx + 1
            return "".join(lines[:split_at]), "".join(lines[split_at:])

    return "", markdown


def _normalize_title(title: str) -> str:
    normalized = title.strip().strip("\"'`*_")
    normalized = re.sub(r"^#(?!#)\s+", "", normalized)
    normalized = _JOURNAL_DAY_PREFIX_RE.sub("", normalized)
    normalized = normalized.rstrip("#").strip()
    normalized = normalized.strip().strip("\"'`*_")
    return _SPACE_RE.sub(" ", normalized).casefold()
