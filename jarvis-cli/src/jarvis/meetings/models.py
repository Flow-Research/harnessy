"""Models for meeting transcript ingestion."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MeetingRecord(BaseModel):
    """Canonical meeting document assembled from an input source."""

    title: str
    meeting_date: date
    source_ref: str
    source_type: str
    fingerprint: str = ""
    project: str = ""
    tags: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    summary: str = ""
    detailed_summary: str = ""
    decisions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    transcript: str = ""
    raw_markdown: str


class MeetingIngestResult(BaseModel):
    """Result payload for a meeting ingestion run."""

    meeting: MeetingRecord
    destinations: list[str] = Field(default_factory=list)
    written_paths: list[str] = Field(default_factory=list)
    journal_entry_id: str | None = None
    journal_skipped_reason: str | None = None
