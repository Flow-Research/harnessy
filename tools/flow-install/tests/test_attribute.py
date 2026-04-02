from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_ROOT = REPO_ROOT / "tools" / "flow-install" / "skills" / "_shared"

sys.path.insert(0, str(SHARED_ROOT))

import attribute  # type: ignore


@pytest.fixture()
def validation_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path | str]:
    project_root = tmp_path / "project"
    traces_root = tmp_path / "traces"
    skill = "issue-flow"

    (project_root / ".jarvis" / "context" / "autoflow").mkdir(parents=True)
    (traces_root / skill).mkdir(parents=True)

    monkeypatch.chdir(project_root)
    monkeypatch.setenv("AGENTS_TRACES_ROOT", str(traces_root))

    return {
        "project_root": project_root,
        "traces_root": traces_root,
        "skill": skill,
        "autoflow_dir": project_root / ".jarvis" / "context" / "autoflow",
        "skill_trace_dir": traces_root / skill,
    }


def write_ndjson(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


def write_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")


def make_trace(
    *,
    timestamp: str,
    gate: str,
    loops: int,
    phase_id: int | None = None,
    phase_name: str | None = None,
    gate_type: str = "quality",
) -> dict:
    trace = {
        "trace_id": f"tr_{timestamp}_{gate}",
        "timestamp": timestamp,
        "skill": "issue-flow",
        "gate": {
            "name": gate,
            "type": gate_type,
            "outcome": "passed" if loops == 0 else "failed",
            "refinement_loops": loops,
        },
        "feedback": {"structured": {}, "unstructured": []},
        "phase": {},
    }
    if phase_id is not None:
        trace["phase"]["id"] = phase_id
    if phase_name is not None:
        trace["phase"]["name"] = phase_name
    return trace


def make_run(outcome: str = "completed") -> dict:
    return {
        "skill": "issue-flow",
        "outcome": outcome,
        "tests_passed": 1,
        "tests_total": 1,
        "human_gates_triggered": 0,
        "human_gates_total": 1,
        "catastrophic_failure": False,
        "regression_detected": False,
        "cost": 0.0,
    }


def base_ratchet_state(decision: str = "keep") -> dict:
    return {
        "skill": "issue-flow",
        "status": "decided",
        "snapshot_tag": "ratchet/issue-flow/20260401T100000Z",
        "snapshot_timestamp": "2026-04-01T10:00:00Z",
        "baseline_score": 0.70,
        "candidate_score": 0.76,
        "delta": 0.06,
        "decision": decision,
        "decided_at": "2026-04-01T11:00:00Z",
        "gates_passed": True,
    }


def write_common_files(
    env: dict[str, Path | str],
    *,
    state: dict,
    traces: list[dict],
    improvements: list[dict],
    runs: list[dict] | None = None,
) -> None:
    autoflow_dir = env["autoflow_dir"]
    skill_trace_dir = env["skill_trace_dir"]
    skill = env["skill"]

    write_json(Path(autoflow_dir) / f"ratchet_{skill}.json", state)
    write_ndjson(Path(autoflow_dir) / "runs.ndjson", runs or [make_run(), make_run(), make_run()])
    write_ndjson(Path(skill_trace_dir) / "traces.ndjson", traces)
    write_ndjson(Path(skill_trace_dir) / "improvements.ndjson", improvements)


def test_compute_writes_descriptive_attribution_and_component_index(validation_env: dict[str, Path | str]) -> None:
    traces = [
        make_trace(timestamp="2026-04-01T09:10:00Z", gate="implementation-review", loops=2, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T09:20:00Z", gate="code-quality", loops=1, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:10:00Z", gate="implementation-review", loops=0, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:20:00Z", gate="code-quality", loops=0, phase_id=3, phase_name="Implementation"),
    ]
    improvements = [
        {
            "improvement_id": "imp_20260401_001",
            "timestamp": "2026-04-01T10:05:00Z",
            "changes": [
                {
                    "file": "SKILL.md",
                    "section": "Phase 3 - Implementation",
                    "type": "added_constraint",
                    "summary": "Add failure-mode checklist",
                }
            ],
        }
    ]
    write_common_files(validation_env, state=base_ratchet_state(), traces=traces, improvements=improvements)

    result = attribute.command_compute(type("Args", (), {"skill": validation_env["skill"], "improvement_id": None, "json": False})())
    assert result == 0

    attribution_records = attribute.load_attributions(str(validation_env["skill"]))
    assert len(attribution_records) == 1

    record = attribution_records[0]
    component = record["touched_components"][0]
    assert record["status"] == "descriptive"
    assert component["mapping_basis"] == "phase-id"
    assert component["confidence"] == "descriptive_medium_confidence"
    assert sorted(component["associated_gates"]) == ["code-quality", "implementation-review"]
    assert component["observed_gate_deltas"]["implementation-review"]["delta"]["avg_refinement_loops"] == -2.0

    index = json.loads(Path(validation_env["skill_trace_dir"]) .joinpath("component_index.json").read_text())
    component_key = "SKILL.md::Phase 3 - Implementation"
    assert component_key in index["components"]
    assert index["components"][component_key]["improvement_types"]["added_constraint"]["count"] == 1
    assert index["notes"][0].startswith("Component signals are descriptive")


def test_compute_marks_unmapped_changes_without_hallucinating_gate_associations(validation_env: dict[str, Path | str]) -> None:
    traces = [
        make_trace(timestamp="2026-04-01T09:10:00Z", gate="implementation-review", loops=1, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:10:00Z", gate="implementation-review", loops=0, phase_id=3, phase_name="Implementation"),
    ]
    improvements = [
        {
            "improvement_id": "imp_20260401_002",
            "timestamp": "2026-04-01T10:05:00Z",
            "changes": [
                {
                    "file": "SKILL.md",
                    "section": "Global style constraints",
                    "type": "modified_criteria",
                    "summary": "Clarify wording",
                }
            ],
        }
    ]
    write_common_files(validation_env, state=base_ratchet_state(), traces=traces, improvements=improvements)

    result = attribute.command_compute(type("Args", (), {"skill": validation_env["skill"], "improvement_id": "imp_20260401_002", "json": False})())
    assert result == 0

    record = attribute.load_attributions(str(validation_env["skill"]))[0]
    component = record["touched_components"][0]
    assert component["mapping_basis"] == "unmapped"
    assert component["associated_gates"] == []
    assert component["confidence"] == "descriptive_low_confidence"
    assert "No gate mapping" in component["notes"]


def test_compute_rejects_non_keep_ratchet_decisions(validation_env: dict[str, Path | str]) -> None:
    traces = [make_trace(timestamp="2026-04-01T09:10:00Z", gate="implementation-review", loops=1, phase_id=3, phase_name="Implementation")]
    improvements = [{"improvement_id": "imp_20260401_003", "timestamp": "2026-04-01T10:05:00Z", "changes": []}]
    write_common_files(validation_env, state=base_ratchet_state(decision="revert"), traces=traces, improvements=improvements)

    result = attribute.command_compute(type("Args", (), {"skill": validation_env["skill"], "improvement_id": None, "json": False})())
    assert result == 1
    assert not Path(validation_env["skill_trace_dir"]).joinpath("attributions.ndjson").exists()


def test_multiple_changes_downgrade_confidence(validation_env: dict[str, Path | str]) -> None:
    traces = [
        make_trace(timestamp="2026-04-01T09:10:00Z", gate="implementation-review", loops=2, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T09:20:00Z", gate="code-quality", loops=1, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:10:00Z", gate="implementation-review", loops=0, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:20:00Z", gate="code-quality", loops=0, phase_id=3, phase_name="Implementation"),
    ]
    improvements = [
        {
            "improvement_id": "imp_20260401_004",
            "timestamp": "2026-04-01T10:05:00Z",
            "changes": [
                {"file": "SKILL.md", "section": "Phase 3 - Implementation", "type": "added_constraint", "summary": "One"},
                {"file": "SKILL.md", "section": "Phase 4 - Validation", "type": "new_check", "summary": "Two"},
            ],
        }
    ]
    write_common_files(validation_env, state=base_ratchet_state(), traces=traces, improvements=improvements)

    result = attribute.command_compute(type("Args", (), {"skill": validation_env["skill"], "improvement_id": None, "json": False})())
    assert result == 0
    record = attribute.load_attributions(str(validation_env["skill"]))[0]
    assert len(record["touched_components"]) == 2
    assert all(component["confidence"] == "descriptive_low_confidence" for component in record["touched_components"])
    assert "Multiple concurrent changes" in record["residual_notes"]


def test_retrospective_traces_are_ignored_in_gate_stats(validation_env: dict[str, Path | str]) -> None:
    traces = [
        make_trace(timestamp="2026-04-01T09:10:00Z", gate="implementation-review", loops=1, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:10:00Z", gate="implementation-review", loops=0, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:15:00Z", gate="run_retrospective", loops=9, phase_name="Retrospective", gate_type="retrospective"),
    ]
    stats = attribute.build_gate_stats(traces)
    assert set(stats.keys()) == {"implementation-review"}


def test_index_regeneration_aggregates_multiple_attributions(validation_env: dict[str, Path | str]) -> None:
    attribution_records = [
        {
            "attribution_id": "attr_1",
            "touched_components": [
                {
                    "component_key": "SKILL.md::Phase 3 - Implementation",
                    "change": {"type": "added_constraint"},
                    "confidence": "descriptive_medium_confidence",
                    "observed_gate_deltas": {
                        "implementation-review": {"delta": {"first_pass_rate": 0.5, "avg_refinement_loops": -1.0}}
                    },
                    "notes": "Observed after an accepted change; causality is not established.",
                }
            ],
        },
        {
            "attribution_id": "attr_2",
            "touched_components": [
                {
                    "component_key": "SKILL.md::Phase 3 - Implementation",
                    "change": {"type": "added_constraint"},
                    "confidence": "descriptive_low_confidence",
                    "observed_gate_deltas": {
                        "implementation-review": {"delta": {"first_pass_rate": 0.1, "avg_refinement_loops": -0.2}}
                    },
                    "notes": "Observed after an accepted change; causality is not established.",
                }
            ],
        },
    ]
    write_ndjson(Path(validation_env["skill_trace_dir"]) / "attributions.ndjson", attribution_records)
    write_ndjson(
        Path(validation_env["skill_trace_dir"]) / "traces.ndjson",
        [
            make_trace(timestamp="2026-04-01T10:10:00Z", gate="implementation-review", loops=0, phase_id=3, phase_name="Implementation"),
        ],
    )

    index = attribute.update_component_index(str(validation_env["skill"]))
    component = index["components"]["SKILL.md::Phase 3 - Implementation"]
    assert component["attribution_count"] == 2
    assert component["confidence_counts"]["descriptive_medium_confidence"] == 1
    assert component["confidence_counts"]["descriptive_low_confidence"] == 1
    assert component["improvement_types"]["added_constraint"]["avg_first_pass_delta"] == pytest.approx(0.3)
    assert component["improvement_types"]["added_constraint"]["avg_refinement_loops_delta"] == pytest.approx(-0.6)


def test_cli_compute_runs_end_to_end(validation_env: dict[str, Path | str]) -> None:
    traces = [
        make_trace(timestamp="2026-04-01T09:10:00Z", gate="implementation-review", loops=2, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:10:00Z", gate="implementation-review", loops=0, phase_id=3, phase_name="Implementation"),
    ]
    improvements = [
        {
            "improvement_id": "imp_20260401_005",
            "timestamp": "2026-04-01T10:05:00Z",
            "changes": [
                {
                    "file": "SKILL.md",
                    "section": "Phase 3 - Implementation",
                    "type": "added_constraint",
                    "summary": "CLI smoke",
                }
            ],
        }
    ]
    write_common_files(validation_env, state=base_ratchet_state(), traces=traces, improvements=improvements)

    env = os.environ.copy()
    env["AGENTS_TRACES_ROOT"] = str(validation_env["traces_root"])
    result = subprocess.run(
        [
            sys.executable,
            str(SHARED_ROOT / "attribute.py"),
            "compute",
            "--skill",
            str(validation_env["skill"]),
            "--json",
        ],
        cwd=validation_env["project_root"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["component_count"] == 1
    assert Path(validation_env["skill_trace_dir"]).joinpath("attributions.ndjson").exists()


def test_backfill_creates_only_missing_attributions(validation_env: dict[str, Path | str], capsys: pytest.CaptureFixture[str]) -> None:
    traces = [
        make_trace(timestamp="2026-04-01T09:10:00Z", gate="implementation-review", loops=2, phase_id=3, phase_name="Implementation"),
        make_trace(timestamp="2026-04-01T10:10:00Z", gate="implementation-review", loops=0, phase_id=3, phase_name="Implementation"),
    ]
    improvements = [
        {
            "improvement_id": "imp_existing",
            "timestamp": "2026-04-01T10:05:00Z",
            "changes": [{"file": "SKILL.md", "section": "Phase 3 - Implementation", "type": "added_constraint", "summary": "Existing"}],
        },
        {
            "improvement_id": "imp_new",
            "timestamp": "2026-04-01T10:06:00Z",
            "changes": [{"file": "SKILL.md", "section": "Phase 3 - Implementation", "type": "added_constraint", "summary": "New"}],
        },
    ]
    write_common_files(validation_env, state=base_ratchet_state(), traces=traces, improvements=improvements)
    write_ndjson(
        Path(validation_env["skill_trace_dir"]) / "attributions.ndjson",
        [{"attribution_id": "attr_existing", "improvement_id": "imp_existing", "touched_components": []}],
    )

    result = attribute.command_backfill(type("Args", (), {"skill": validation_env["skill"], "limit": 0, "json": False})())
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["created"] == 1
    assert payload["created_records"][0]["improvement_id"] == "imp_new"
    records = attribute.load_attributions(str(validation_env["skill"]))
    assert len(records) == 2
