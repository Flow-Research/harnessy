from jarvis.reading_list.parser import extract_reading_items


def test_extract_reading_items_handles_markdown_links_and_bare_urls() -> None:
    markdown = """## Details
Memory for Agents
[](https://x.com/example/status/123)

Useful paper
(https://arxiv.org/pdf/2601.01885)

[Agency Agents](https://github.com/example/repo)
"""
    items = extract_reading_items(markdown)
    assert len(items) == 3
    assert items[0].section == "Details"
    assert items[0].description == "Memory for Agents"
    assert items[1].item_type.value == "paper"
    assert items[2].item_type.value == "repo"
