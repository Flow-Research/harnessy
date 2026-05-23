"""Fathom meeting fetch and normalization helpers."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import httpx

from jarvis.config import get_fathom_api_key

from .models import MeetingRecord
from .parser import (
    extract_first_list,
    first_paragraph,
    first_section,
    normalize_heading,
    split_markdown_sections,
)

FATHOM_API_BASE = "https://api.fathom.ai/external/v1"
_FATHOM_SUMMARY_HEADINGS = (
    normalize_heading("Summary"),
    normalize_heading("Executive Summary"),
    normalize_heading("Overview"),
    normalize_heading("Key Takeaways"),
    normalize_heading("Meeting Purpose"),
)
_FATHOM_ACTION_HEADINGS = (
    normalize_heading("Action Items"),
    normalize_heading("Actions"),
    normalize_heading("Next Steps"),
    normalize_heading("Follow Ups"),
    normalize_heading("Follow-up"),
)


class FathomClient:
    """Minimal API client for pulling Fathom meetings."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        account: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or get_fathom_api_key(account)
        self.timeout = timeout

    def list_meetings(
        self,
        *,
        limit: int = 20,
        created_after: str | None = None,
        include_transcript: bool = False,
        include_summary: bool = False,
        include_action_items: bool = False,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List meetings from Fathom with optional inline enrichments."""

        params: dict[str, Any] = {
            "limit": limit,
            "include_transcript": str(include_transcript).lower(),
            "include_summary": str(include_summary).lower(),
            "include_action_items": str(include_action_items).lower(),
        }
        if created_after:
            params["created_after"] = created_after
        if cursor:
            params["cursor"] = cursor
        return self._get_json("/meetings", params=params)

    def create_webhook(
        self,
        *,
        destination_url: str,
        triggered_for: list[str],
        include_transcript: bool,
        include_summary: bool,
        include_action_items: bool,
        include_crm_matches: bool,
    ) -> dict[str, Any]:
        """Create a Fathom webhook and return the response payload."""

        body = {
            "destination_url": destination_url,
            "triggered_for": triggered_for,
            "include_transcript": include_transcript,
            "include_summary": include_summary,
            "include_action_items": include_action_items,
            "include_crm_matches": include_crm_matches,
        }
        return self._post_json("/webhooks", json_body=body)

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a Fathom webhook by ID."""

        with httpx.Client(base_url=FATHOM_API_BASE, timeout=self.timeout) as client:
            response = client.delete(
                f"/webhooks/{webhook_id}",
                headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
            )
            response.raise_for_status()

    def get_meeting_by_recording_id(
        self,
        recording_id: str,
        *,
        created_after: str | None = None,
        max_pages: int = 10,
    ) -> dict[str, Any]:
        """Find a meeting by recording ID by paging through the meetings list."""

        cursor: str | None = None
        pages = 0
        while pages < max_pages:
            payload = self.list_meetings(
                limit=100,
                created_after=created_after,
                include_transcript=True,
                include_summary=True,
                include_action_items=True,
                cursor=cursor,
            )
            items = payload.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and str(item.get("recording_id", "")) == str(
                        recording_id
                    ):
                        return item
            cursor = payload.get("next_cursor")
            if not cursor:
                break
            pages += 1
        raise RuntimeError(f"Fathom recording not found: {recording_id}")

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with httpx.Client(base_url=FATHOM_API_BASE, timeout=self.timeout) as client:
            response = client.get(
                path,
                params=params,
                headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}

    def _post_json(self, path: str, *, json_body: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(base_url=FATHOM_API_BASE, timeout=self.timeout) as client:
            response = client.post(
                path,
                json=json_body,
                headers={
                    "X-Api-Key": self.api_key,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}


def looks_like_fathom_payload(data: object) -> bool:
    """Return True when an object matches the public Fathom meeting schema."""

    if not isinstance(data, dict):
        return False
    if "recording_id" in data and ("default_summary" in data or "transcript" in data):
        return True
    items = data.get("items")
    return bool(
        isinstance(items, list)
        and len(items) == 1
        and isinstance(items[0], dict)
        and looks_like_fathom_payload(items[0])
    )


def parse_fathom_json_text(
    text: str,
    *,
    project: str = "",
    tags: list[str] | None = None,
    source_ref: str = "fathom-json",
) -> MeetingRecord | None:
    """Parse a Fathom JSON blob into a canonical meeting record when possible."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not looks_like_fathom_payload(payload):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
        if items and isinstance(items[0], dict):
            payload = items[0]
    if not isinstance(payload, dict):
        return None
    return parse_fathom_payload(payload, project=project, tags=tags, source_ref=source_ref)


def parse_fathom_payload(
    payload: dict[str, Any],
    *,
    project: str = "",
    tags: list[str] | None = None,
    source_ref: str | None = None,
) -> MeetingRecord:
    """Normalize a Fathom meeting payload into the canonical meeting model."""

    summary_markdown = fathom_summary_markdown(payload)
    summary_sections, summary_preamble, _ = split_markdown_sections(summary_markdown)
    title = (
        str(payload.get("meeting_title") or "").strip()
        or str(payload.get("title") or "").strip()
        or f"Fathom Meeting {payload.get('recording_id', '')}"
    )
    decisions = extract_first_list(
        summary_sections,
        {normalize_heading("Key Decisions"), normalize_heading("Decisions")},
    )
    open_questions = extract_first_list(
        summary_sections,
        {
            normalize_heading("Open Questions"),
            normalize_heading("Questions"),
            normalize_heading("Risks"),
        },
    )
    summary = first_section(summary_sections, _FATHOM_SUMMARY_HEADINGS) or first_paragraph(
        summary_preamble
    )
    action_items = fathom_action_items(payload) or extract_first_list(
        summary_sections, _FATHOM_ACTION_HEADINGS
    )
    transcript = fathom_transcript_markdown(payload)
    recording_id = payload.get("recording_id", "")
    ref = source_ref or f"fathom:{recording_id}"
    return MeetingRecord(
        title=title,
        meeting_date=fathom_meeting_date(payload),
        source_ref=ref,
        source_type="fathom",
        fingerprint=f"fathom:{recording_id}:{payload.get('created_at', '')}",
        project=project,
        tags=tags or ["fathom"],
        participants=fathom_participants(payload),
        summary=summary,
        detailed_summary=summary_markdown.strip(),
        decisions=decisions,
        action_items=action_items,
        open_questions=open_questions,
        transcript=transcript,
        raw_markdown=summary_markdown.strip(),
    )


def fathom_meeting_date(payload: dict[str, Any]) -> date:
    """Extract the best meeting date from a Fathom payload."""

    for key in ("recording_start_time", "scheduled_start_time", "created_at"):
        value = payload.get(key)
        if value:
            parsed = parse_iso_datetime(str(value))
            if parsed:
                return parsed.date()
    return date.today()


def parse_iso_datetime(value: str) -> datetime | None:
    """Parse an ISO-like datetime string into a datetime."""

    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def fathom_summary_markdown(payload: dict[str, Any]) -> str:
    """Extract summary markdown from a Fathom payload."""

    summary = payload.get("default_summary")
    if isinstance(summary, dict):
        return str(summary.get("markdown_formatted") or "").strip()
    return ""


def fathom_participants(payload: dict[str, Any]) -> list[str]:
    """Collect unique participant names from Fathom calendar invitees and owner."""

    names: list[str] = []
    recorded_by = payload.get("recorded_by")
    if isinstance(recorded_by, dict):
        owner = str(recorded_by.get("name") or "").strip()
        if owner:
            names.append(owner)
    invitees = payload.get("calendar_invitees")
    if isinstance(invitees, list):
        for invitee in invitees:
            if not isinstance(invitee, dict):
                continue
            name = str(
                invitee.get("name") or invitee.get("matched_speaker_display_name") or ""
            ).strip()
            if name and name not in names:
                names.append(name)
    return names


def fathom_action_items(payload: dict[str, Any]) -> list[str]:
    """Render structured Fathom action items into concise strings."""

    rendered: list[str] = []
    items = payload.get("action_items")
    if not isinstance(items, list):
        return rendered
    for item in items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "").strip()
        if not description:
            continue
        assignee = item.get("assignee")
        assignee_name = (
            str(assignee.get("name") or "").strip() if isinstance(assignee, dict) else ""
        )
        rendered.append(f"{assignee_name}: {description}" if assignee_name else description)
    return rendered


def fathom_transcript_markdown(payload: dict[str, Any]) -> str:
    """Render transcript segments into readable markdown lines."""

    lines: list[str] = []
    transcript = payload.get("transcript")
    if not isinstance(transcript, list):
        return ""
    for item in transcript:
        if not isinstance(item, dict):
            continue
        speaker = item.get("speaker")
        display_name = "Unknown Speaker"
        if isinstance(speaker, dict):
            display_name = str(speaker.get("display_name") or display_name).strip() or display_name
        timestamp = str(item.get("timestamp") or "").strip()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        prefix = f"[{timestamp}] " if timestamp else ""
        lines.append(f"{prefix}{display_name}: {text}")
    return "\n".join(lines)
