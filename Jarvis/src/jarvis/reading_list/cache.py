"""Caches for reading list URL fetches and prioritization results."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import FetchedContent, PrioritizationResult


def cache_dir() -> Path:
    path = Path.home() / ".jarvis" / "cache" / "reading-list"
    (path / "urls").mkdir(parents=True, exist_ok=True)
    (path / "results").mkdir(parents=True, exist_ok=True)
    return path


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class URLCache:
    def __init__(self) -> None:
        self._dir = cache_dir() / "urls"

    def get(self, key: str, ttl_days: int) -> FetchedContent | None:
        path = self._dir / f"{_hash(key)}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
            fetched_at = _parse_timestamp(payload.get("fetched_at", "1970-01-01T00:00:00+00:00"))
            if datetime.now(UTC) - fetched_at > timedelta(days=ttl_days):
                return None
            return FetchedContent.model_validate(payload)
        except Exception:
            return None

    def set(self, key: str, value: FetchedContent) -> None:
        path = self._dir / f"{_hash(key)}.json"
        path.write_text(value.model_dump_json(indent=2))


class ResultCache:
    def __init__(self) -> None:
        self._dir = cache_dir() / "results"

    def get(self, key: str) -> PrioritizationResult | None:
        path = self._dir / f"{_hash(key)}.json"
        if not path.exists():
            return None
        try:
            return PrioritizationResult.model_validate(json.loads(path.read_text()))
        except Exception:
            return None

    def set(self, key: str, value: PrioritizationResult) -> None:
        path = self._dir / f"{_hash(key)}.json"
        path.write_text(value.model_dump_json(indent=2))


def clear_cache() -> int:
    root = cache_dir()
    count = 0
    for path in root.rglob("*.json"):
        path.unlink(missing_ok=True)
        count += 1
    return count


def ttl_days_for_url(url: str) -> int:
    lower = url.lower()
    if "arxiv.org" in lower or "github.com" in lower or lower.endswith(".pdf"):
        return 30
    if "x.com/" in lower or "twitter.com/" in lower:
        return 30
    return 7
