#!/usr/bin/env python3
"""
Compute descriptive component attribution for a completed ratchet cycle.

This script is intentionally conservative. It does not claim causal attribution.
It summarizes which changed components were associated with observed per-gate
delta after an accepted improvement and writes two artifacts alongside traces:

- attributions.ndjson
- component_index.json

Usage:
    attribute.py compute --skill issue-flow [--improvement-id imp_...] [--json]
    attribute.py backfill --skill issue-flow [--limit 5] [--json]
    attribute.py index --skill issue-flow [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from ratchet import load_ratchet_state, load_runs  # type: ignore
from trace_query import load_traces  # type: ignore


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def traces_root() -> Path:
    return Path(os.environ.get("AGENTS_TRACES_ROOT", Path.home() / ".agents" / "traces"))


def skill_trace_dir(skill: str) -> Path:
    return traces_root() / skill


def improvements_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "improvements.ndjson"


def attributions_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "attributions.ndjson"


def component_index_path(skill: str) -> Path:
    return skill_trace_dir(skill) / "component_index.json"


def parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


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


def load_improvements(skill: str) -> List[Dict[str, Any]]:
    records = load_ndjson(improvements_path(skill))
    return [r for r in records if r.get("type") != "promotion"]


def load_attributions(skill: str) -> List[Dict[str, Any]]:
    return load_ndjson(attributions_path(skill))


def existing_improvement_ids(skill: str) -> set[str]:
    return {
        str(record.get("improvement_id"))
        for record in load_attributions(skill)
        if record.get("improvement_id")
    }


def gate_traces(traces: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [t for t in traces if t.get("gate", {}).get("type") != "retrospective"]


def build_gate_stats(traces: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "first_pass_count": 0,
        "total_loops": 0,
        "phase_names": Counter(),
        "phase_ids": Counter(),
    })

    for trace in gate_traces(traces):
        gate = trace.get("gate", {})
        gate_name = gate.get("name", "unknown")
        loops = int(gate.get("refinement_loops", 0) or 0)
        phase = trace.get("phase", {})
        entry = stats[gate_name]
        entry["count"] += 1
        entry["total_loops"] += loops
        if loops == 0:
            entry["first_pass_count"] += 1
        if phase.get("name"):
            entry["phase_names"][str(phase["name"])] += 1
        if phase.get("id") is not None:
            entry["phase_ids"][str(phase["id"])] += 1

    normalized: Dict[str, Dict[str, Any]] = {}
    for gate_name, entry in stats.items():
        count = entry["count"] or 1
        normalized[gate_name] = {
            "count": entry["count"],
            "first_pass_rate": round(entry["first_pass_count"] / count, 4),
            "avg_refinement_loops": round(entry["total_loops"] / count, 4),
            "top_phase_names": [name for name, _ in entry["phase_names"].most_common(3)],
            "top_phase_ids": [phase_id for phase_id, _ in entry["phase_ids"].most_common(3)],
        }
    return normalized


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def parse_phase_reference(section: str) -> Tuple[Optional[str], Optional[str]]:
    match = re.search(r"phase\s+(\d+)(?:\s*[\-—:]\s*(.+))?", section, flags=re.IGNORECASE)
    if not match:
        return None, None
    phase_id = match.group(1)
    phase_name = match.group(2).strip() if match.group(2) else None
    return phase_id, phase_name


def identify_gates(change: Dict[str, Any], candidate_traces: List[Dict[str, Any]]) -> Tuple[List[str], str]:
    section = str(change.get("section", "") or "")
    file_path = str(change.get("file", "") or "")
    lower_section = section.lower()
    lower_file = file_path.lower()

    gate_stats = build_gate_stats(candidate_traces)
    gate_names = list(gate_stats.keys())

    # Highest confidence: explicit phase reference in section name.
    phase_id, phase_name = parse_phase_reference(section)
    matched: List[str] = []
    if phase_id:
        for gate_name, stats in gate_stats.items():
            if phase_id in stats.get("top_phase_ids", []):
                matched.append(gate_name)
        if matched:
            return sorted(set(matched)), "phase-id"

    if phase_name:
        phase_slug = slugify(phase_name)
        for gate_name, stats in gate_stats.items():
            gate_slug = slugify(gate_name)
            if phase_slug and phase_slug in gate_slug:
                matched.append(gate_name)
                continue
            for candidate_name in stats.get("top_phase_names", []):
                if phase_slug and phase_slug in slugify(candidate_name):
                    matched.append(gate_name)
                    break
        if matched:
            return sorted(set(matched)), "phase-name"

    # Moderate confidence: command file stem overlaps with gate names.
    if "/commands/" in lower_file or lower_file.startswith("commands/"):
        stem = slugify(Path(lower_file).stem)
        if stem:
            for gate_name in gate_names:
                if stem in slugify(gate_name) or slugify(gate_name) in stem:
                    matched.append(gate_name)
            if matched:
                return sorted(set(matched)), "command-stem"

    # Lower confidence: textual overlap with well-known workflow words.
    keyword_map = {
        "spec": ["spec", "specification"],
        "implementation": ["implementation", "code"],
        "test": ["test", "validation", "qa"],
        "prd": ["prd", "product requirements"],
        "design": ["design", "architecture"],
        "pr": ["pr", "pull request"],
    }
    matched_keywords = []
    for keyword, aliases in keyword_map.items():
        if any(alias in lower_section for alias in aliases) or any(alias in lower_file for alias in aliases):
            matched_keywords.append(keyword)

    if matched_keywords:
        for gate_name in gate_names:
            gate_slug = slugify(gate_name)
            if any(keyword in gate_slug for keyword in matched_keywords):
                matched.append(gate_name)
        if matched:
            return sorted(set(matched)), "keyword-overlap"

    return [], "unmapped"


def confidence_label(mapping_basis: str, before_count: int, after_count: int, change_count: int) -> str:
    if mapping_basis in {"phase-id", "phase-name"} and before_count >= 2 and after_count >= 2 and change_count == 1:
        return "descriptive_medium_confidence"
    return "descriptive_low_confidence"


def component_key(change: Dict[str, Any]) -> str:
    file_part = str(change.get("file", "unknown"))
    section_part = str(change.get("section", "unknown"))
    return f"{file_part}::{section_part}"


def latest_nonpromotion_improvement(skill: str, improvement_id: Optional[str]) -> Optional[Dict[str, Any]]:
    improvements = load_improvements(skill)
    if improvement_id:
        for improvement in improvements:
            if improvement.get("improvement_id") == improvement_id:
                return improvement
        return None

    if not improvements:
        return None

    improvements.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return improvements[0]


def build_attribution(skill: str, improvement: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    snapshot_ts = parse_ts(state.get("snapshot_timestamp"))
    decided_at = parse_ts(state.get("decided_at"))
    all_traces = load_traces(skill)

    baseline_traces = []
    candidate_traces = []
    for trace in all_traces:
        ts = parse_ts(trace.get("timestamp"))
        if not ts or not snapshot_ts:
            continue
        if ts < snapshot_ts:
            baseline_traces.append(trace)
        elif decided_at is None or ts <= decided_at:
            candidate_traces.append(trace)

    baseline_stats = build_gate_stats(baseline_traces)
    candidate_stats = build_gate_stats(candidate_traces)
    runs = load_runs(skill)

    changes = improvement.get("changes", []) or []
    touched_components: List[Dict[str, Any]] = []
    total_delta = state.get("delta")

    for change in changes:
        associated_gates, mapping_basis = identify_gates(change, candidate_traces)
        observed_gate_deltas: Dict[str, Dict[str, Any]] = {}
        before_total = 0
        after_total = 0
        for gate_name in associated_gates:
            before = baseline_stats.get(gate_name, {})
            after = candidate_stats.get(gate_name, {})
            before_count = int(before.get("count", 0) or 0)
            after_count = int(after.get("count", 0) or 0)
            before_total += before_count
            after_total += after_count
            observed_gate_deltas[gate_name] = {
                "before": {
                    "count": before_count,
                    "first_pass_rate": before.get("first_pass_rate"),
                    "avg_refinement_loops": before.get("avg_refinement_loops"),
                },
                "after": {
                    "count": after_count,
                    "first_pass_rate": after.get("first_pass_rate"),
                    "avg_refinement_loops": after.get("avg_refinement_loops"),
                },
                "delta": {
                    "first_pass_rate": round((after.get("first_pass_rate") or 0.0) - (before.get("first_pass_rate") or 0.0), 4),
                    "avg_refinement_loops": round((after.get("avg_refinement_loops") or 0.0) - (before.get("avg_refinement_loops") or 0.0), 4),
                },
            }

        touched_components.append({
            "component_key": component_key(change),
            "change": {
                "file": change.get("file"),
                "section": change.get("section"),
                "type": change.get("type"),
                "summary": change.get("summary"),
            },
            "mapping_basis": mapping_basis,
            "associated_gates": associated_gates,
            "observed_gate_deltas": observed_gate_deltas,
            "confidence": confidence_label(mapping_basis, before_total, after_total, len(changes)),
            "notes": (
                "Observed after an accepted change; causality is not established."
                if associated_gates
                else "No gate mapping was established from available phase/file evidence."
            ),
        })

    return {
        "attribution_id": f"attr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": now_iso(),
        "skill": skill,
        "improvement_id": improvement.get("improvement_id"),
        "ratchet_cycle": {
            "snapshot_tag": state.get("snapshot_tag"),
            "snapshot_timestamp": state.get("snapshot_timestamp"),
            "baseline_score": state.get("baseline_score"),
            "candidate_score": state.get("candidate_score"),
            "delta": total_delta,
            "decision": state.get("decision"),
        },
        "evidence_window": {
            "runs_analyzed": len(runs),
            "baseline_traces": len(gate_traces(baseline_traces)),
            "candidate_traces": len(gate_traces(candidate_traces)),
        },
        "touched_components": touched_components,
        "residual_notes": (
            "Multiple concurrent changes were present; treat this as descriptive evidence only."
            if len(changes) > 1
            else "Descriptive attribution only. Other factors may have influenced outcomes."
        ),
        "status": "descriptive",
    }


def update_component_index(skill: str) -> Dict[str, Any]:
    attributions = load_attributions(skill)
    traces = load_traces(skill)
    gate_stats = build_gate_stats(traces)
    components: Dict[str, Dict[str, Any]] = {}

    for attribution in attributions:
        for component in attribution.get("touched_components", []):
            key = component.get("component_key", "unknown")
            entry = components.setdefault(key, {
                "component_key": key,
                "attribution_count": 0,
                "confidence_counts": Counter(),
                "improvement_types": defaultdict(lambda: {
                    "count": 0,
                    "total_first_pass_delta": 0.0,
                    "total_avg_loops_delta": 0.0,
                }),
                "associated_gates": Counter(),
                "notes": set(),
            })

            entry["attribution_count"] += 1
            confidence = component.get("confidence", "descriptive_low_confidence")
            entry["confidence_counts"][confidence] += 1
            change_type = component.get("change", {}).get("type", "unknown")

            type_entry = entry["improvement_types"][change_type]
            type_entry["count"] += 1
            for gate_name, gate_delta in component.get("observed_gate_deltas", {}).items():
                entry["associated_gates"][gate_name] += 1
                type_entry["total_first_pass_delta"] += gate_delta.get("delta", {}).get("first_pass_rate", 0.0) or 0.0
                type_entry["total_avg_loops_delta"] += gate_delta.get("delta", {}).get("avg_refinement_loops", 0.0) or 0.0
            note = component.get("notes")
            if note:
                entry["notes"].add(note)

    normalized_components: Dict[str, Any] = {}
    for key, entry in components.items():
        improvement_types = {}
        for change_type, type_entry in entry["improvement_types"].items():
            count = type_entry["count"] or 1
            improvement_types[change_type] = {
                "count": type_entry["count"],
                "avg_first_pass_delta": round(type_entry["total_first_pass_delta"] / count, 4),
                "avg_refinement_loops_delta": round(type_entry["total_avg_loops_delta"] / count, 4),
            }

        current_gate_signals = {}
        for gate_name, gate_count in entry["associated_gates"].most_common(5):
            current_gate_signals[gate_name] = {
                "association_count": gate_count,
                "current_first_pass_rate": gate_stats.get(gate_name, {}).get("first_pass_rate"),
                "current_avg_refinement_loops": gate_stats.get(gate_name, {}).get("avg_refinement_loops"),
            }

        normalized_components[key] = {
            "attribution_count": entry["attribution_count"],
            "confidence_counts": dict(entry["confidence_counts"]),
            "improvement_types": improvement_types,
            "current_gate_signals": current_gate_signals,
            "notes": sorted(entry["notes"]),
        }

    bottleneck_gates = sorted(
        [
            {
                "gate": gate_name,
                "avg_refinement_loops": stats.get("avg_refinement_loops"),
                "first_pass_rate": stats.get("first_pass_rate"),
                "count": stats.get("count"),
            }
            for gate_name, stats in gate_stats.items()
        ],
        key=lambda item: (item.get("avg_refinement_loops") or 0.0),
        reverse=True,
    )[:10]

    index = {
        "skill": skill,
        "last_updated": now_iso(),
        "components": normalized_components,
        "bottleneck_gates": bottleneck_gates,
        "status": "descriptive",
        "notes": [
            "Component signals are descriptive and may reflect correlation rather than causation.",
            "Use this index to support review and proposal ranking, not to justify automatic mutation.",
        ],
    }
    path = component_index_path(skill)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2) + "\n")
    return index


def command_compute(args: argparse.Namespace) -> int:
    skill = args.skill
    state = load_ratchet_state(skill)
    if not state:
        print(json.dumps({"error": f"No ratchet state found for {skill}"}), file=sys.stderr)
        return 1

    if state.get("decision") != "keep":
        print(json.dumps({
            "error": f"Ratchet decision for {skill} is not KEEP",
            "decision": state.get("decision"),
        }), file=sys.stderr)
        return 1

    improvement = latest_nonpromotion_improvement(skill, args.improvement_id)
    if not improvement:
        print(json.dumps({"error": f"No matching improvement record found for {skill}"}), file=sys.stderr)
        return 1

    attribution = build_attribution(skill, improvement, state)
    append_ndjson(attributions_path(skill), attribution)
    index = update_component_index(skill)

    result = {
        "ok": True,
        "attribution_id": attribution["attribution_id"],
        "improvement_id": improvement.get("improvement_id"),
        "attributions_file": str(attributions_path(skill)),
        "component_index_file": str(component_index_path(skill)),
        "status": attribution["status"],
        "component_count": len(attribution.get("touched_components", [])),
    }
    if args.json:
        result["attribution"] = attribution
        result["component_index"] = index
    print(json.dumps(result, indent=2))
    return 0


def command_index(args: argparse.Namespace) -> int:
    index = update_component_index(args.skill)
    print(json.dumps(index, indent=2))
    return 0


def command_backfill(args: argparse.Namespace) -> int:
    skill = args.skill
    state = load_ratchet_state(skill)
    if not state:
        print(json.dumps({"error": f"No ratchet state found for {skill}"}), file=sys.stderr)
        return 1

    if state.get("decision") != "keep":
        print(json.dumps({
            "error": f"Ratchet decision for {skill} is not KEEP",
            "decision": state.get("decision"),
        }), file=sys.stderr)
        return 1

    improvements = load_improvements(skill)
    if not improvements:
        print(json.dumps({"ok": True, "created": 0, "reason": "no improvements found"}, indent=2))
        return 0

    seen = existing_improvement_ids(skill)
    created = []
    skipped = []
    count = 0
    for improvement in sorted(improvements, key=lambda item: item.get("timestamp", ""), reverse=True):
        improvement_id = improvement.get("improvement_id")
        if improvement_id in seen:
            skipped.append(improvement_id)
            continue
        attribution = build_attribution(skill, improvement, state)
        append_ndjson(attributions_path(skill), attribution)
        created.append({
            "improvement_id": improvement_id,
            "attribution_id": attribution["attribution_id"],
        })
        seen.add(str(improvement_id))
        count += 1
        if args.limit and count >= args.limit:
            break

    index = update_component_index(skill)
    result = {
        "ok": True,
        "created": len(created),
        "created_records": created,
        "skipped_existing": skipped,
        "component_index_file": str(component_index_path(skill)),
        "component_count": len(index.get("components", {})),
    }
    print(json.dumps(result, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute descriptive component attribution for ratchet cycles")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compute = subparsers.add_parser("compute", help="Write a new attribution record for the latest kept ratchet cycle")
    compute.add_argument("--skill", required=True)
    compute.add_argument("--improvement-id", help="Specific improvement record to attribute")
    compute.add_argument("--json", action="store_true")

    backfill = subparsers.add_parser("backfill", help="Generate attribution records for improvements missing attribution history")
    backfill.add_argument("--skill", required=True)
    backfill.add_argument("--limit", type=int, default=0, help="Maximum number of new attribution records to create")
    backfill.add_argument("--json", action="store_true")

    index = subparsers.add_parser("index", help="Regenerate component index from attribution history")
    index.add_argument("--skill", required=True)
    index.add_argument("--json", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "compute":
        return command_compute(args)
    if args.command == "backfill":
        return command_backfill(args)
    if args.command == "index":
        return command_index(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
