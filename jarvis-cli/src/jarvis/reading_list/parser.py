"""Markdown parser for reading list documents."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import ReadingItem, classify_item_type

_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r"(?<!\()(?<!\[)(https?://[^\s)]+)")
_PAREN_URL_RE = re.compile(r"\((https?://[^)\s]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def extract_reading_items(markdown: str) -> list[ReadingItem]:
    items: list[ReadingItem] = []
    seen: set[str] = set()
    current_section = ""
    previous_non_empty = ""

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            current_section = _clean(heading_match.group(1))
            previous_non_empty = current_section
            continue

        consumed: set[str] = set()

        for match in _MARKDOWN_LINK_RE.finditer(line):
            title = _clean(match.group(1))
            url = match.group(2).strip()
            consumed.add(url)
            if url in seen:
                continue
            seen.add(url)
            items.append(
                ReadingItem(
                    url=url,
                    title=title,
                    description=_clean(
                        previous_non_empty if previous_non_empty != current_section else ""
                    ),
                    section=current_section,
                    domain=_domain(url),
                    item_type=classify_item_type(url),
                )
            )

        for pattern in (_PAREN_URL_RE, _BARE_URL_RE):
            for match in pattern.finditer(line):
                url = match.group(1).strip()
                if url in consumed or url in seen:
                    continue
                seen.add(url)
                context = line.replace(url, "").replace("()", "").strip("-• ")
                items.append(
                    ReadingItem(
                        url=url,
                        title="",
                        description=_clean(
                            context
                            or (previous_non_empty if previous_non_empty != current_section else "")
                        ),
                        section=current_section,
                        domain=_domain(url),
                        item_type=classify_item_type(url),
                    )
                )

        previous_non_empty = line

    return items
