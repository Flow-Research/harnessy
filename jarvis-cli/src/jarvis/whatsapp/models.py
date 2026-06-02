"""Models for WhatsApp channel capture and local-first threads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WhatsAppDirection = Literal["inbound", "outbound", "status"]
WhatsAppThreadStatus = Literal["new", "triaged", "waiting", "done"]


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class WhatsAppMessage(BaseModel):
    """One normalized WhatsApp message or delivery-status event."""

    message_id: str
    account: str
    provider: str = "meta"
    direction: WhatsAppDirection
    sender: str = ""
    recipient: str = ""
    contact_name: str = ""
    timestamp: datetime = Field(default_factory=utc_now)
    message_type: str = "unknown"
    text: str = ""
    status: str = ""
    media: dict[str, Any] = Field(default_factory=dict)
    location: dict[str, Any] = Field(default_factory=dict)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def contact_phone(self) -> str:
        """Return the non-business participant phone number for thread grouping."""

        if self.direction == "inbound":
            return self.sender
        return self.recipient


class WhatsAppThread(BaseModel):
    """Local-first WhatsApp conversation thread."""

    thread_id: str
    account: str
    provider: str = "meta"
    contact: str
    contact_name: str = ""
    status: WhatsAppThreadStatus = "new"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    messages: list[WhatsAppMessage] = Field(default_factory=list)


class WhatsAppIngestResult(BaseModel):
    """Result payload for ingesting one or more WhatsApp webhook archives."""

    account: str
    destinations: list[str] = Field(default_factory=list)
    messages: list[WhatsAppMessage] = Field(default_factory=list)
    written_paths: list[str] = Field(default_factory=list)
    journal_entry_ids: list[str] = Field(default_factory=list)
    processed_paths: list[str] = Field(default_factory=list)
    invalid_paths: list[str] = Field(default_factory=list)
    skipped_duplicates: int = 0
    errors: list[str] = Field(default_factory=list)


class WhatsAppSendResult(BaseModel):
    """Result payload for outbound WhatsApp sends."""

    account: str
    to: str
    provider_response: dict[str, Any] = Field(default_factory=dict)
    message: WhatsAppMessage | None = None
    thread_id: str | None = None
    written_paths: list[str] = Field(default_factory=list)
