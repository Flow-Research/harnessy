#!/usr/bin/env python3
"""
Replay-oriented validation workflow for descriptive attribution.

This script does not change evaluator behavior. It supports the Phase 1.5
validation gate by:

- listing attribution records that still need human review
- recording human usefulness review scores
- generating a validation_summary.json artifact per skill

Usage:
    attribute_validate.py queue --skill issue-flow [--json]
    attribute_validate.py packet --skill issue-flow [--limit 5]
    attribute_validate.py review --skill issue-flow --attribution-id attr_... \
        --legibility 4 --plausibility 4 --conservatism 5 \
        --usefulness 4 --trustworthiness 4 [--notes "..."]
    attribute_validate.py summary --skill issue-flow [--json]
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def traces_root() -> Path:
    return Path(os.environ.get("AGENTS_TRACES_ROOT", Path.home() / ".agents" / "traces"))


def skill_trace_dir(skill: str) -> Path:
    return traces_root() / skill


def attributions_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "attributions.ndjson"


def reviews_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "attribution_reviews.ndjson"


def validation_summary_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "validation_summary.json"


def review_packet_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "validation_review_packet.md"


def component_index_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "component_index.json"


def load_ndjson(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def append_ndjson(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def load_attributions(skill: str) -> List[Dict[str, Any]]:
    return load_ndjson(attributions_path(skill))


def load_reviews(skill: str) -> List[Dict[str, Any]]:
    return load_ndjson(reviews_path(skill))


def latest_review_by_attribution(skill: str) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for review in load_reviews(skill):
        attribution_id = review.get("attribution_id")
        if not attribution_id:
            continue
        current = latest.get(attribution_id)
        if current is None or review.get("timestamp", "") > current.get("timestamp", ""):
            latest[attribution_id] = review
    return latest


def review_average(review: Dict[str, Any]) -> float:
    keys = ["legibility", "plausibility", "conservatism", "usefulness", "trustworthiness"]
    values = [float(review.get(key, 0.0)) for key in keys]
    return round(sum(values) / len(values), 2)


def coverage_stats(attributions: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_components = 0
    mapped_components = 0
    medium_confidence = 0
    low_confidence = 0

    for attribution in attributions:
        for component in attribution.get("touched_components", []):
            total_components += 1
            if component.get("mapping_basis") != "unmapped":
                mapped_components += 1
            if component.get("confidence") == "descriptive_medium_confidence":
                medium_confidence += 1
            else:
                low_confidence += 1

    return {
        "total_components": total_components,
        "mapped_components": mapped_components,
        "mapped_ratio": round(mapped_components / total_components, 4) if total_components else 0.0,
        "medium_confidence_components": medium_confidence,
        "low_confidence_components": low_confidence,
    }


def derive_readiness(skill: str) -> Dict[str, Any]:
    attributions = load_attributions(skill)
    reviews = latest_review_by_attribution(skill)
    coverage = coverage_stats(attributions)

    reviewed = [
        reviews[attribution_id]
        for attribution in attributions
        for attribution_id in [attribution.get("attribution_id")]
        if isinstance(attribution_id, str) and attribution_id in reviews
    ]
    review_count = len(reviewed)
    avg_review_score = round(sum(review_average(r) for r in reviewed) / review_count, 2) if reviewed else None
    usefulness_scores = [float(r.get("usefulness", 0.0)) for r in reviewed]
    trust_scores = [float(r.get("trustworthiness", 0.0)) for r in reviewed]

    component_index_exists = component_index_path(skill).exists()

    mechanical_ready = bool(attributions) and component_index_exists
    mapping_stable = coverage["mapped_ratio"] >= 0.5 if coverage["total_components"] else False
    human_usefulness_ready = (
        review_count >= 3
        and avg_review_score is not None
        and avg_review_score >= 3.5
        and (sum(usefulness_scores) / review_count) >= 3.5
        and (sum(trust_scores) / review_count) >= 3.5
    )

    promotion_ready = mechanical_ready and mapping_stable and human_usefulness_ready

    return {
        "skill": skill,
        "last_updated": now_iso(),
        "inputs": {
            "attribution_count": len(attributions),
            "review_count": review_count,
            "component_index_exists": component_index_exists,
        },
        "coverage": coverage,
        "human_review": {
            "reviewed_attribution_ids": [r.get("attribution_id") for r in reviewed],
            "average_score": avg_review_score,
            "minimum_reviews_required": 3,
        },
        "gates": {
            "mechanical_readiness": {
                "passed": mechanical_ready,
                "reason": "Attribution records and component index exist" if mechanical_ready else "Need at least one attribution record and component index",
            },
            "mapping_stability": {
                "passed": mapping_stable,
                "reason": (
                    f"Mapped ratio {coverage['mapped_ratio']:.2f} meets minimum 0.50"
                    if mapping_stable else
                    f"Mapped ratio {coverage['mapped_ratio']:.2f} is below minimum 0.50"
                ),
            },
            "human_usefulness": {
                "passed": human_usefulness_ready,
                "reason": (
                    f"Average review score {avg_review_score:.2f} across {review_count} reviews"
                    if human_usefulness_ready and avg_review_score is not None else
                    "Need at least 3 reviewed attributions with average score >= 3.5"
                ),
            },
            "external_alignment": {
                "passed": False,
                "reason": "Not yet instrumented; external quality sampling remains future validation work",
            },
        },
        "promotion_ready": promotion_ready,
        "next_action": (
            "Phase 1 is ready for a guarded Phase 2 pilot"
            if promotion_ready else
            "Continue replay review and human scoring before advancing phases"
        ),
        "notes": [
            "This summary evaluates Phase 1 descriptive attribution readiness only.",
            "External alignment remains pending until downstream or external quality signals are instrumented.",
        ],
    }


def command_queue(args: argparse.Namespace) -> int:
    attributions = load_attributions(args.skill)
    reviewed = latest_review_by_attribution(args.skill)
    queue = [
        {
            "attribution_id": attribution.get("attribution_id"),
            "improvement_id": attribution.get("improvement_id"),
            "timestamp": attribution.get("timestamp"),
            "component_count": len(attribution.get("touched_components", [])),
        }
        for attribution in attributions
        if attribution.get("attribution_id") not in reviewed
    ]

    payload = {
        "skill": args.skill,
        "pending_review_count": len(queue),
        "pending_reviews": queue,
    }
    print(json.dumps(payload, indent=2))
    return 0


def command_review(args: argparse.Namespace) -> int:
    record = {
        "review_id": f"arv_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": now_iso(),
        "skill": args.skill,
        "attribution_id": args.attribution_id,
        "legibility": args.legibility,
        "plausibility": args.plausibility,
        "conservatism": args.conservatism,
        "usefulness": args.usefulness,
        "trustworthiness": args.trustworthiness,
        "notes": args.notes,
    }
    append_ndjson(reviews_path(args.skill), record)
    payload = {"ok": True, "review": record, "average_score": review_average(record)}
    print(json.dumps(payload, indent=2))
    return 0


def command_packet(args: argparse.Namespace) -> int:
    attributions = load_attributions(args.skill)
    reviewed = latest_review_by_attribution(args.skill)
    pending = [a for a in attributions if a.get("attribution_id") not in reviewed]
    if args.limit:
        pending = pending[:args.limit]

    lines = [
        f"# Attribution Replay Packet: {args.skill}",
        "",
        "Use this packet to manually review descriptive attribution outputs.",
        "",
        "Scoring rubric (1-5): legibility, plausibility, conservatism, usefulness, trustworthiness.",
        "",
    ]

    if not pending:
        lines.append("No pending attribution records require review.")
    else:
        for attribution in pending:
            attribution_id = attribution.get("attribution_id")
            lines.extend([
                f"## {attribution_id}",
                "",
                f"- Improvement ID: `{attribution.get('improvement_id')}`",
                f"- Timestamp: `{attribution.get('timestamp')}`",
                f"- Status: `{attribution.get('status')}`",
                f"- Residual notes: {attribution.get('residual_notes')}",
                "",
                "### Components",
                "",
            ])
            for component in attribution.get("touched_components", []):
                lines.append(f"- `{component.get('component_key')}`")
                lines.append(f"  mapping_basis: `{component.get('mapping_basis')}`")
                lines.append(f"  confidence: `{component.get('confidence')}`")
                associated_gates = component.get("associated_gates", [])
                lines.append(f"  associated_gates: {', '.join(associated_gates) if associated_gates else 'none'}")
                if associated_gates:
                    lines.append("  observed_deltas:")
                    for gate_name, gate_delta in component.get("observed_gate_deltas", {}).items():
                        delta = gate_delta.get("delta", {})
                        lines.append(
                            f"  - {gate_name}: first_pass_rate {delta.get('first_pass_rate'):+.4f}, avg_refinement_loops {delta.get('avg_refinement_loops'):+.4f}"
                        )
                lines.append(f"  notes: {component.get('notes')}")
            lines.extend([
                "",
                "### Review command template",
                "",
                "```bash",
                f"python3 \"tools/flow-install/skills/_shared/attribute_validate.py\" review \\",
                f"  --skill {args.skill} \\",
                f"  --attribution-id {attribution_id} \\",
                "  --legibility 4 \\",
                "  --plausibility 4 \\",
                "  --conservatism 4 \\",
                "  --usefulness 4 \\",
                "  --trustworthiness 4 \\",
                "  --notes \"<notes>\"",
                "```",
                "",
            ])

    packet = "\n".join(lines) + "\n"
    path = review_packet_path(args.skill)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(packet)

    payload = {
        "ok": True,
        "skill": args.skill,
        "pending_review_count": len(pending),
        "packet_file": str(path),
    }
    print(json.dumps(payload, indent=2))
    return 0


def command_summary(args: argparse.Namespace) -> int:
    summary = derive_readiness(args.skill)
    path = validation_summary_path(args.skill)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay-oriented validation for descriptive attribution")
    subparsers = parser.add_subparsers(dest="command", required=True)

    queue = subparsers.add_parser("queue", help="List attribution records still needing replay review")
    queue.add_argument("--skill", required=True)
    queue.add_argument("--json", action="store_true")

    packet = subparsers.add_parser("packet", help="Generate a markdown replay-review packet for pending attributions")
    packet.add_argument("--skill", required=True)
    packet.add_argument("--limit", type=int, default=0)
    packet.add_argument("--json", action="store_true")

    review = subparsers.add_parser("review", help="Record a human replay review for one attribution")
    review.add_argument("--skill", required=True)
    review.add_argument("--attribution-id", required=True)
    review.add_argument("--legibility", type=int, choices=range(1, 6), required=True)
    review.add_argument("--plausibility", type=int, choices=range(1, 6), required=True)
    review.add_argument("--conservatism", type=int, choices=range(1, 6), required=True)
    review.add_argument("--usefulness", type=int, choices=range(1, 6), required=True)
    review.add_argument("--trustworthiness", type=int, choices=range(1, 6), required=True)
    review.add_argument("--notes", default="")

    summary = subparsers.add_parser("summary", help="Generate validation summary for a skill")
    summary.add_argument("--skill", required=True)
    summary.add_argument("--json", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "queue":
        return command_queue(args)
    if args.command == "packet":
        return command_packet(args)
    if args.command == "review":
        return command_review(args)
    if args.command == "summary":
        return command_summary(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
