"""Pydantic data models for the jarvis wiki subsystem."""

from __future__ import annotations

import os
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _default_owner() -> str:
    """Resolve the wiki owner from the environment, falling back to 'unknown'."""
    return os.environ.get("FLOW_USER", os.environ.get("USER", "unknown"))


class SourceType(str, Enum):
    ARTICLE = "article"
    PAPER = "paper"
    NOTE = "note"
    REPO = "repo"
    CLIP = "clip"
    IMAGE = "image"


class ArticleType(str, Enum):
    SUMMARY = "summary"
    CONCEPT = "concept"
    QUERY = "query"
    INDEX = "index"
    LOG = "log"


class LogEntryType(str, Enum):
    INGEST = "INGEST"
    COMPILE = "COMPILE"
    QUERY = "QUERY"
    LINT = "LINT"
    ENHANCE = "ENHANCE"
    EXPORT = "EXPORT"
    INIT = "INIT"


class LLMConfig(BaseModel):
    backend: str = "claude-cli"  # claude-cli | anthropic-sdk | ollama
    provider: str = "anthropic"
    model: str = "claude-opus-4-6"
    max_tokens_compile: int = 4096
    max_tokens_qa: int = 8192
    temperature: float = 0.3
    temperature_qa: float = 0.5


class CategoryDef(BaseModel):
    id: str
    label: str
    description: str = ""


class CompileConfig(BaseModel):
    auto_backlinks: bool = True
    min_article_words: int = 200
    stale_days: int = 180
    summary_length: str = "medium"
    extract_entities: bool = True
    cross_reference: bool = True


class WikiDomain(BaseModel):
    domain: str
    title: str
    description: str = ""
    version: str = "0.1.0"
    owner: str = Field(default_factory=_default_owner)
    language: str = "en"
    created: date = Field(default_factory=date.today)
    updated: date = Field(default_factory=date.today)
    categories: list[CategoryDef] = Field(default_factory=list)
    entity_types: list[str] = Field(
        default_factory=lambda: ["person", "organization", "concept", "location"]
    )
    llm: LLMConfig = Field(default_factory=LLMConfig)
    compile: CompileConfig = Field(default_factory=CompileConfig)
    source_paths: list[str] = Field(default_factory=list)

    @field_validator("domain")
    @classmethod
    def domain_is_slug(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("domain must be lowercase kebab-case")
        return v


class RawSource(BaseModel):
    slug: str
    path: Path
    source_type: SourceType
    title: str
    url: str | None = None
    source_date: date | None = None
    tags: list[str] = Field(default_factory=list)
    category: str | None = None
    body_text: str = ""
    word_count: int = 0
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def compute_word_count(self) -> RawSource:
        self.word_count = len(self.body_text.split())
        return self


class ArticleFrontmatter(BaseModel):
    title: str
    type: ArticleType
    source_slug: str | None = None
    source_type: SourceType | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    created: date = Field(default_factory=date.today)
    updated: date = Field(default_factory=date.today)
    health_score: int | None = None
    mentioned_in: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    entity_type: str | None = None


class WikiArticle(BaseModel):
    slug: str
    path: Path
    article_type: ArticleType
    frontmatter: ArticleFrontmatter
    body: str
    word_count: int = 0
    backlinks: list[str] = Field(default_factory=list)
    outlinks: list[str] = Field(default_factory=list)


class IndexEntry(BaseModel):
    slug: str
    title: str
    article_type: ArticleType
    category: str | None = None
    one_line: str = ""
    tags: list[str] = Field(default_factory=list)
    updated: date = Field(default_factory=date.today)


class LogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    entry_type: LogEntryType
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    def format(self) -> str:
        """Format the entry as a single log line."""
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"[{ts}] [{self.entry_type.value}] {self.description}"


class CompilationFileRecord(BaseModel):
    hash: str
    size_bytes: int
    last_compiled: datetime
    compiled_to: list[str] = Field(default_factory=list)
    token_cost: dict[str, int] = Field(default_factory=dict)


class CompilationManifest(BaseModel):
    version: str = "1.0"
    domain: str
    last_full_compile: datetime | None = None
    files: dict[str, CompilationFileRecord] = Field(default_factory=dict)


class LintSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LintIssue(BaseModel):
    article_slug: str
    check: str  # e.g. "broken_link", "orphan_page", "thin_article"
    severity: LintSeverity
    message: str
    detail: str = ""


class LintReport(BaseModel):
    domain: str
    total_articles: int
    issues: list[LintIssue] = Field(default_factory=list)
    health_scores: dict[str, int] = Field(default_factory=dict)
    domain_score: float = 100.0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
