"""Parse Anytype object links into structured Space + Object IDs.

Accepts the forms users typically paste:
    - anytype://object?objectId=<id>&spaceId=<sid>
    - https://<host>/<id>?spaceId=<sid>            (e.g. object.any.coop)
    - https://<host>/object/<id>?spaceId=<sid>     (e.g. anytype.io/object/...)
    - raw "object_id:space_id" pairs (from API output)

Extra query params (inviteId, etc.) and URL fragments are tolerated and
ignored — Anytype's web links carry an invite key in the fragment, but the
locally-running desktop API doesn't need it.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, Field


class AnytypeLink(BaseModel):
    """Resolved Anytype object reference."""

    object_id: str = Field(description="Anytype object ID")
    space_id: str = Field(description="Anytype space ID")


class InvalidLinkError(ValueError):
    """Raised when a link cannot be parsed into an AnytypeLink."""


def parse_link(text: str) -> AnytypeLink:
    """Parse an Anytype object link into (object_id, space_id).

    Raises:
        InvalidLinkError: when the input cannot be parsed into both ids.
    """
    if text is None or not str(text).strip():
        raise InvalidLinkError("empty link")
    raw = str(text).strip()

    if "://" not in raw and "/" not in raw and "?" not in raw and ":" in raw:
        parts = raw.split(":")
        if len(parts) != 2 or not all(p.strip() for p in parts):
            raise InvalidLinkError(
                f"raw form must be exactly 'object_id:space_id', got {raw!r}"
            )
        return AnytypeLink(object_id=parts[0].strip(), space_id=parts[1].strip())

    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)

    if parsed.scheme == "anytype":
        object_id = _first(qs.get("objectId"))
        space_id = _first(qs.get("spaceId"))
        if not object_id or not space_id:
            raise InvalidLinkError(
                f"anytype:// link missing objectId or spaceId: {raw!r}"
            )
        return AnytypeLink(object_id=object_id, space_id=space_id)

    if parsed.scheme in ("http", "https"):
        space_id = _first(qs.get("spaceId"))
        if not space_id:
            # An Anytype web link always carries spaceId. Without it, this isn't
            # an Anytype link — bail out before guessing.
            raise InvalidLinkError(
                f"https link missing spaceId query param: {raw!r}"
            )
        path_parts = [p for p in parsed.path.split("/") if p]
        object_id: str | None = None
        if len(path_parts) >= 2 and path_parts[0] == "object":
            object_id = path_parts[1]
        elif len(path_parts) == 1:
            object_id = path_parts[0]
        if not object_id:
            raise InvalidLinkError(
                f"https link missing object id in path: {raw!r}"
            )
        return AnytypeLink(object_id=object_id, space_id=space_id)

    raise InvalidLinkError(f"unrecognized link format: {raw!r}")


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0] or None
