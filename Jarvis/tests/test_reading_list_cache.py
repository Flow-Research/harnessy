from jarvis.reading_list.cache import ResultCache, URLCache, clear_cache
from jarvis.reading_list.models import (
    FetchedContent,
    PrioritizationResult,
    PrioritizedItem,
    ReadingItem,
    SourceDocument,
    SourceType,
    Tier,
    Topic,
    classify_item_type,
    timestamp_now,
)


def test_url_cache_round_trip() -> None:
    clear_cache()
    cache = URLCache()
    item = ReadingItem(
        url="https://example.com",
        title="Example",
        description="desc",
        section="s",
        domain="example.com",
        item_type=classify_item_type("https://example.com"),
    )
    content = FetchedContent(
        item=item,
        fetched_title="Example",
        fetched_text="Body",
        authors=[],
        fetch_status="success",
        fetched_at=timestamp_now(),
    )
    cache.set(item.url, content)
    loaded = cache.get(item.url, ttl_days=7)
    assert loaded is not None
    assert loaded.fetched_title == "Example"


def test_result_cache_round_trip() -> None:
    clear_cache()
    cache = ResultCache()
    source = SourceDocument(
        source_type=SourceType.FILE,
        source_ref="/tmp/example.md",
        title="Read",
        markdown="",
        last_modified="1",
    )
    item = ReadingItem(
        url="https://example.com",
        title="Example",
        description="desc",
        section="s",
        domain="example.com",
        item_type=classify_item_type("https://example.com"),
    )
    fetched = FetchedContent(
        item=item,
        fetched_title="Example",
        fetched_text="Body",
        authors=[],
        fetch_status="success",
        fetched_at=timestamp_now(),
    )
    prioritized = PrioritizedItem(
        content=fetched,
        relevance=4,
        urgency=4,
        topic=Topic.DEVELOPER_TOOLING,
        tier="read_now",
        rationale="Useful now",
        rank=1,
    )
    result = PrioritizationResult(
        source=source,
        items=[prioritized],
        fetch_successes=1,
        fetch_failures=0,
        generated_at=timestamp_now(),
    )
    cache.set(source.fingerprint, result)
    loaded = cache.get(source.fingerprint)
    assert loaded is not None
    assert loaded.items[0].tier == "read_now"
