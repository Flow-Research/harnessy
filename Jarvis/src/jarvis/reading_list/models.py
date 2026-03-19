"""Models for reading list organization."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    ANYTYPE = "anytype"
    NOTION = "notion"
    FILE = "file"
    URL = "url"
    STDIN = "stdin"


class ItemType(StrEnum):
    PAPER = "paper"
    TWEET = "tweet"
    REPO = "repo"
    ARTICLE = "article"
    PDF = "pdf"
    VIDEO = "video"
    UNKNOWN = "unknown"


class Topic(StrEnum):
    AGENT_RUNTIME = "agent_runtime"
    MEMORY_CONTEXT = "memory_context"
    BITTENSOR_ECONOMICS = "bittensor_economics"
    TASK_DECOMPOSITION = "task_decomposition"
    DISTRIBUTED_SYSTEMS = "distributed_systems"
    KNOWLEDGE_GRAPHS = "knowledge_graphs"
    RAG_RETRIEVAL = "rag_retrieval"
    SECURITY_PRIVACY = "security_privacy"
    DEVELOPER_TOOLING = "developer_tooling"
    CONTENT_AUTOMATION = "content_automation"
    HARDWARE_INFRASTRUCTURE = "hardware_infrastructure"
    MARKET_MACRO = "market_macro"
    OTHER = "other"


Tier = Literal["read_now", "this_week", "this_month", "reference", "deferred"]
FetchStatus = Literal["success", "failed", "timeout", "rate_limited"]


class SourceDocument(BaseModel):
    source_type: SourceType
    source_ref: str
    title: str = "Untitled"
    markdown: str
    last_modified: str = ""
    object_id: str = ""
    space_id: str = ""

    @property
    def fingerprint(self) -> str:
        return f"{self.source_type}:{self.source_ref}:{self.last_modified}".strip(":")

    @property
    def supports_write_back(self) -> bool:
        return (
            self.source_type in {SourceType.ANYTYPE, SourceType.NOTION}
            and bool(self.object_id)
            and bool(self.space_id)
        )


class ReadingItem(BaseModel):
    url: str
    title: str = ""
    description: str = ""
    section: str = ""
    domain: str = ""
    item_type: ItemType = ItemType.UNKNOWN


class FetchedContent(BaseModel):
    item: ReadingItem
    fetched_title: str = ""
    fetched_text: str = ""
    authors: list[str] = Field(default_factory=list)
    fetch_status: FetchStatus = "failed"
    fetched_at: str = ""


class PrioritizedItem(BaseModel):
    content: FetchedContent
    relevance: int = Field(ge=1, le=5)
    urgency: int = Field(ge=1, le=5)
    topic: Topic = Topic.OTHER
    tier: Tier = "reference"
    rationale: str
    rank: int = Field(ge=1)


class PrioritizationResult(BaseModel):
    source: SourceDocument
    items: list[PrioritizedItem]
    fetch_successes: int = 0
    fetch_failures: int = 0
    generated_at: str


def classify_item_type(url: str) -> ItemType:
    lower = url.lower()
    if "arxiv.org" in lower:
        return ItemType.PAPER
    if "x.com/" in lower or "twitter.com/" in lower:
        return ItemType.TWEET
    if "github.com/" in lower:
        return ItemType.REPO
    if lower.endswith(".pdf") or "drive.google.com/file" in lower or "dropbox.com" in lower:
        return ItemType.PDF
    if "youtube.com/" in lower or "youtu.be/" in lower or "broadcasts/" in lower:
        return ItemType.VIDEO
    if lower.startswith("http://") or lower.startswith("https://"):
        return ItemType.ARTICLE
    return ItemType.UNKNOWN


def timestamp_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
