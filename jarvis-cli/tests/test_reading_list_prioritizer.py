from jarvis.reading_list.models import FetchedContent, ReadingItem, classify_item_type, Topic
from jarvis.reading_list.prioritizer import prioritize_items


def test_prioritize_items_falls_back_without_ai(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    class BrokenAnthropic:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = self

        def create(self, **kwargs):
            raise RuntimeError("no credits")

    monkeypatch.setattr("jarvis.reading_list.prioritizer.Anthropic", BrokenAnthropic)

    items = [
        FetchedContent(
            item=ReadingItem(
                url="https://example.com/bittensor",
                title="Bittensor economics",
                description="subnet miner rewards and tao alpha tokens",
                section="Details",
                domain="example.com",
                item_type=classify_item_type("https://example.com/bittensor"),
            ),
            fetched_title="Bittensor economics",
            fetched_text="Bittensor subnet miner rewards and tao alpha token economics",
            authors=[],
            fetch_status="success",
            fetched_at="2026-03-17T00:00:00Z",
        )
    ]

    ranked = prioritize_items(items)
    assert len(ranked) == 1
    assert ranked[0].topic in {Topic.BITTENSOR_ECONOMICS, Topic.OTHER}
    assert ranked[0].tier in {"read_now", "this_week", "this_month", "reference", "deferred"}
