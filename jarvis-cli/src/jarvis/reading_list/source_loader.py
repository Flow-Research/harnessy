"""Source resolution for reading list documents."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

from jarvis.adapters import get_adapter
from jarvis.adapters.exceptions import (
    AuthError,
    NotFoundError,
)
from jarvis.adapters.exceptions import (
    ConnectionError as AdapterConnectionError,
)
from jarvis.models import BackendObject
from jarvis.object.cli import parse_object_id

from .models import SourceDocument, SourceType


class SourceResolutionError(RuntimeError):
    pass


_ANYTYPE_OBJECT_URL_RE = re.compile(r"object\.any\.coop/([a-z0-9]+)", re.I)


def _extract_anytype_object_id(target: str) -> str:
    match = _ANYTYPE_OBJECT_URL_RE.search(target)
    if match:
        return match.group(1)
    return parse_object_id(target)


def autodetect_source(target: str) -> SourceType:
    if target == "-":
        return SourceType.STDIN
    path = Path(target).expanduser()
    if path.exists():
        return SourceType.FILE
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https"}:
        host = parsed.netloc.lower()
        if host == "object.any.coop":
            return SourceType.ANYTYPE
        if "notion.so" in host:
            return SourceType.NOTION
        return SourceType.URL
    raise SourceResolutionError(
        f"Could not determine source type for '{target}'. Use --resolver to specify explicitly."
    )


def _source_doc(
    source_type: SourceType,
    source_ref: str,
    title: str,
    markdown: str,
    last_modified: str = "",
) -> SourceDocument:
    return SourceDocument(
        source_type=source_type,
        source_ref=source_ref,
        title=title or "Untitled",
        markdown=markdown,
        last_modified=last_modified,
    )


def _space_from_object(obj: BackendObject) -> str:
    return obj.space_id


def load_anytype(target: str, backend: str | None = None) -> SourceDocument:
    object_id = _extract_anytype_object_id(target)
    adapter = get_adapter(backend or "anytype")
    adapter.connect()
    spaces = adapter.list_spaces()
    last_error: Exception | None = None
    for space in spaces:
        try:
            obj = adapter.get_object(space.id, object_id)
            last_modified = obj.updated_at.isoformat() if obj.updated_at else ""
            content = obj.content or obj.snippet or obj.description
            doc = _source_doc(
                SourceType.ANYTYPE,
                target,
                obj.name,
                content,
                last_modified,
            )
            doc.object_id = object_id
            doc.space_id = space.id
            return doc
        except NotFoundError as exc:
            last_error = exc
            continue
    raise SourceResolutionError(f"AnyType object not found: {target}") from last_error


def load_notion(target: str, backend: str | None = None) -> SourceDocument:
    object_id = parse_object_id(target)
    adapter = get_adapter(backend or "notion")
    adapter.connect()
    spaces = adapter.list_spaces()
    last_error: Exception | None = None
    for space in spaces:
        try:
            obj = adapter.get_object(space.id, object_id)
            last_modified = obj.updated_at.isoformat() if obj.updated_at else ""
            content = obj.content or obj.snippet or obj.description
            doc = _source_doc(
                SourceType.NOTION,
                target,
                obj.name,
                content,
                last_modified,
            )
            doc.object_id = object_id
            doc.space_id = space.id
            return doc
        except NotFoundError as exc:
            last_error = exc
            continue
    raise SourceResolutionError(f"Notion object not found: {target}") from last_error


def load_file(target: str) -> SourceDocument:
    path = Path(target).expanduser().resolve()
    markdown = path.read_text()
    stat = path.stat()
    return _source_doc(
        SourceType.FILE,
        str(path),
        path.stem,
        markdown,
        f"{int(stat.st_mtime)}:{stat.st_size}",
    )


def load_stdin() -> SourceDocument:
    markdown = sys.stdin.read()
    import hashlib

    fingerprint = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    return _source_doc(SourceType.STDIN, "stdin", "stdin", markdown, fingerprint)


def load_url(target: str) -> SourceDocument:
    response = httpx.get(target, follow_redirects=True, timeout=30.0)
    response.raise_for_status()
    title = urlparse(str(response.url)).path.rsplit("/", 1)[-1] or str(response.url)
    last_modified = response.headers.get("last-modified", "") or response.headers.get("etag", "")
    return _source_doc(SourceType.URL, str(response.url), title, response.text, last_modified)


def load_source_document(
    target: str,
    resolver: str | None = None,
    backend: str | None = None,
) -> SourceDocument:
    source_type = SourceType(resolver) if resolver else autodetect_source(target)
    try:
        if source_type == SourceType.ANYTYPE:
            return load_anytype(target, backend)
        if source_type == SourceType.NOTION:
            return load_notion(target, backend)
        if source_type == SourceType.FILE:
            return load_file(target)
        if source_type == SourceType.STDIN:
            return load_stdin()
        return load_url(target)
    except (AdapterConnectionError, AuthError, NotFoundError, httpx.HTTPError) as exc:
        raise SourceResolutionError(str(exc)) from exc
