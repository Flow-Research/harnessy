"""AI-powered prioritization for reading list items."""

from __future__ import annotations

import json
import os
from pathlib import Path

from anthropic import Anthropic

from jarvis.context_reader import load_context

from .models import FetchedContent, PrioritizedItem, Tier, Topic
from .prompts import READING_LIST_SYSTEM_PROMPT, build_reading_list_prompt


def _load_roadmap_summary() -> str:
    plans_dir = Path.cwd() / ".jarvis" / "context" / "plans"
    if not plans_dir.exists():
        return "No roadmap file found."
    candidates = sorted(plans_dir.rglob("*roadmap*.md"), reverse=True)
    if not candidates:
        return "No roadmap file found."
    text = candidates[0].read_text()
    return text[:12000]


def _tier_for_scores(relevance: int, urgency: int) -> Tier:
    if relevance >= 4 and urgency >= 4:
        return "read_now"
    if relevance >= 3 and urgency >= 3:
        return "this_week"
    if relevance >= 3:
        return "this_month"
    if relevance == 2:
        return "reference"
    return "deferred"


def _extract_json(text: str) -> dict[str, object]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in AI response")
    return json.loads(text[start : end + 1])


def _infer_topic(text: str) -> Topic:
    lower = text.lower()
    mapping = [
        (Topic.BITTENSOR_ECONOMICS, ["bittensor", "subnet", "tao", "alpha token", "miner"]),
        (Topic.AGENT_RUNTIME, ["agent", "claude", "opencode", "openclaw", "jarvis", "multi-agent"]),
        (Topic.MEMORY_CONTEXT, ["memory", "context", "context engineering"]),
        (Topic.TASK_DECOMPOSITION, ["decomposition", "workflow", "orchestr", "task graph"]),
        (Topic.DISTRIBUTED_SYSTEMS, ["distributed", "consensus", "kernel", "network", "packet"]),
        (Topic.KNOWLEDGE_GRAPHS, ["knowledge graph", "graph", "provenance"]),
        (Topic.RAG_RETRIEVAL, ["rag", "retrieval", "vector", "embedding"]),
        (Topic.SECURITY_PRIVACY, ["security", "privacy", "secure aggregation", "trust"]),
        (Topic.DEVELOPER_TOOLING, ["github", "cli", "testing", "code review", "tmux"]),
        (Topic.CONTENT_AUTOMATION, ["content", "podcast", "youtube", "instagram", "video"]),
        (Topic.HARDWARE_INFRASTRUCTURE, ["hardware", "gpu", "pcb", "energy", "robotics"]),
        (Topic.MARKET_MACRO, ["market", "economy", "nigeria", "stablecoin", "trade surplus"]),
    ]
    for topic, keywords in mapping:
        if any(keyword in lower for keyword in keywords):
            return topic
    return Topic.OTHER


def _fallback_prioritize(items: list[FetchedContent], context_text: str) -> list[PrioritizedItem]:
    active_keywords = [
        "jarvis",
        "agent",
        "runtime",
        "bittensor",
        "subnet",
        "operator",
        "orchestrator",
        "task",
        "flow",
        "workstream",
        "economics",
        "reward",
        "gateway",
        "memory",
    ]
    roadmap_keywords = [
        "phase 2",
        "phase 3",
        "registration",
        "heartbeat",
        "execution loop",
        "task decomposition",
        "miner",
    ]
    lowered_context = context_text.lower()
    ranked: list[PrioritizedItem] = []
    tier_counts: dict[Tier, int] = {
        "read_now": 0,
        "this_week": 0,
        "this_month": 0,
        "reference": 0,
        "deferred": 0,
    }

    for fetched in items:
        combined = " ".join(
            [
                fetched.item.title,
                fetched.item.description,
                fetched.fetched_title,
                fetched.fetched_text,
                fetched.item.section,
            ]
        ).lower()
        active_hits = sum(
            1 for keyword in active_keywords if keyword in combined and keyword in lowered_context
        )
        roadmap_hits = sum(1 for keyword in roadmap_keywords if keyword in combined)
        topic = _infer_topic(combined)
        base_relevance = 1
        if active_hits >= 3 or roadmap_hits >= 2:
            base_relevance = 5
        elif active_hits >= 2 or roadmap_hits >= 1:
            base_relevance = 4
        elif active_hits >= 1:
            base_relevance = 3
        elif topic in {Topic.AGENT_RUNTIME, Topic.BITTENSOR_ECONOMICS, Topic.MEMORY_CONTEXT}:
            base_relevance = 3
        elif topic in {
            Topic.DISTRIBUTED_SYSTEMS,
            Topic.DEVELOPER_TOOLING,
            Topic.TASK_DECOMPOSITION,
        }:
            base_relevance = 2

        urgency = min(
            5,
            max(
                1,
                roadmap_hits
                + (1 if base_relevance >= 4 else 0)
                + (1 if topic in {Topic.AGENT_RUNTIME, Topic.BITTENSOR_ECONOMICS} else 0),
            ),
        )
        tier = _tier_for_scores(base_relevance, urgency)
        tier_counts[tier] += 1
        rationale = (
            "Fallback heuristic ranking based on current roadmap and context keywords. "
            f"Matched topic: {topic.value.replace('_', ' ')}."
        )
        ranked.append(
            PrioritizedItem(
                content=fetched,
                relevance=base_relevance,
                urgency=urgency,
                topic=topic,
                tier=tier,
                rationale=rationale,
                rank=tier_counts[tier],
            )
        )

    ranked.sort(
        key=lambda item: (
            ["read_now", "this_week", "this_month", "reference", "deferred"].index(item.tier),
            -(item.relevance * item.urgency),
            item.content.item.url,
        )
    )
    return ranked


def prioritize_items(items: list[FetchedContent]) -> list[PrioritizedItem]:
    context = load_context()
    roadmap = _load_roadmap_summary()
    prompt = build_reading_list_prompt(items, context, roadmap)
    fallback_context = "\n\n".join([context.to_prompt_context(), roadmap])

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            temperature=0.2,
            system=READING_LIST_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", "") == "text"
        ]
        text = "\n".join(part for part in text_blocks if part) or "{}"
        payload = _extract_json(text)
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("AI response missing items list")
    except Exception as exc:
        import sys

        print(
            f"[warning] AI prioritization failed ({type(exc).__name__}: {exc}). "
            "Using fallback heuristic.",
            file=sys.stderr,
        )
        return _fallback_prioritize(items, fallback_context)

    by_url = {item.item.url: item for item in items}
    ranked: list[PrioritizedItem] = []
    tier_counts: dict[Tier, int] = {
        "read_now": 0,
        "this_week": 0,
        "this_month": 0,
        "reference": 0,
        "deferred": 0,
    }

    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url", ""))
        fetched = by_url.get(url)
        if fetched is None:
            continue
        relevance = int(entry.get("relevance", 1))
        urgency = int(entry.get("urgency", 1))
        topic_raw = str(entry.get("topic", "other"))
        try:
            topic = Topic(topic_raw)
        except ValueError:
            topic = Topic.OTHER
        tier = _tier_for_scores(relevance, urgency)
        tier_counts[tier] += 1
        ranked.append(
            PrioritizedItem(
                content=fetched,
                relevance=relevance,
                urgency=urgency,
                topic=topic,
                tier=tier,
                rationale=str(entry.get("rationale", "")),
                rank=tier_counts[tier],
            )
        )

    ranked.sort(
        key=lambda item: (
            ["read_now", "this_week", "this_month", "reference", "deferred"].index(item.tier),
            -(item.relevance * item.urgency),
            item.content.item.url,
        )
    )

    return ranked
