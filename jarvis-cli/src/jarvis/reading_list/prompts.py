"""Prompt templates for reading list prioritization."""

from __future__ import annotations

from collections.abc import Sequence

from jarvis.models import UserContext

from .models import FetchedContent

READING_LIST_SYSTEM_PROMPT = """You are Jarvis, a research prioritization assistant.

Your job is to help a technical founder decide what to read next.
You will receive:
1. Current project context (priorities, goals, focus, blockers, decisions)
2. A roadmap summary
3. Reading items with researched content

Classify each item into one of these topics exactly:
- agent_runtime
- memory_context
- bittensor_economics
- task_decomposition
- distributed_systems
- knowledge_graphs
- rag_retrieval
- security_privacy
- developer_tooling
- content_automation
- hardware_infrastructure
- market_macro
- other

Score each item:
- relevance: 1-5
- urgency: 1-5

Relevance rubric:
5 = directly affects current sprint deliverables
4 = strongly informs next active phase
3 = useful supporting context
2 = peripheral but related
1 = broad background only

Urgency rubric:
5 = needed this week to unblock work
4 = needed before next sprint
3 = useful this month
2 = useful later
1 = no time pressure

Return strict JSON with this format:
{
  "items": [
    {
      "url": "...",
      "topic": "agent_runtime",
      "relevance": 5,
      "urgency": 4,
      "rationale": "One sentence rationale."
    }
  ]
}
"""


def _truncate(text: str, limit: int) -> str:
    stripped = " ".join(text.split())
    return stripped[:limit]


def build_reading_list_prompt(
    items: Sequence[FetchedContent],
    context: UserContext,
    roadmap: str,
) -> str:
    parts = [
        "## Current Project Context",
        context.to_prompt_context(),
        "\n## Current Roadmap",
        roadmap,
        "\n## Reading Items",
    ]
    for index, item in enumerate(items, start=1):
        authors = ", ".join(item.authors[:5])
        parts.append(
            f"\n### Item {index}\n"
            f"URL: {item.item.url}\n"
            f"Section: {item.item.section or 'Uncategorized'}\n"
            f"Source Title: {item.item.title or 'Unknown'}\n"
            f"Fetched Title: {item.fetched_title or 'Unknown'}\n"
            f"Item Type: {item.item.item_type.value}\n"
            f"Fetch Status: {item.fetch_status}\n"
            f"Authors: {authors}\n"
            f"Source Description: {_truncate(item.item.description, 240)}\n"
            f"Fetched Content: {_truncate(item.fetched_text, 1400)}\n"
        )
    parts.append(
        "\n## Instructions\n"
        "Return JSON only. Score each item independently. "
        "Do not assign tiers. The application will map scores to tiers."
    )
    return "\n".join(parts)
