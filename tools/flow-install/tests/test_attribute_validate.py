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

import attribute_validate  # type: ignore


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
        "skill_trace_dir": traces_root / skill,
    }


def write_ndjson(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


def write_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")


def sample_attribution(attribution_id: str, mapped: bool = True) -> dict:
    return {
        "attribution_id": attribution_id,
        "timestamp": "2026-04-01T12:00:00Z",
        "skill": "issue-flow",
        "improvement_id": f"imp_for_{attribution_id}",
        "touched_components": [
            {
                "component_key": f"SKILL.md::{attribution_id}",
                "mapping_basis": "phase-id" if mapped else "unmapped",
                "confidence": "descriptive_medium_confidence" if mapped else "descriptive_low_confidence",
                "change": {"type": "added_constraint"},
                "observed_gate_deltas": {
                    "implementation-review": {
                        "delta": {"first_pass_rate": 0.2, "avg_refinement_loops": -0.5}
                    }
                } if mapped else {},
                "notes": "Observed after an accepted change; causality is not established." if mapped else "No gate mapping was established from available phase/file evidence.",
            }
        ],
    }


def sample_review(attribution_id: str, score: int = 4) -> dict:
    return {
        "review_id": f"review_{attribution_id}",
        "timestamp": "2026-04-01T12:30:00Z",
        "skill": "issue-flow",
        "attribution_id": attribution_id,
        "legibility": score,
        "plausibility": score,
        "conservatism": score,
        "usefulness": score,
        "trustworthiness": score,
        "notes": "Looks good",
    }


def test_queue_lists_unreviewed_attributions(validation_env: dict[str, Path | str], capsys: pytest.CaptureFixture[str]) -> None:
    write_ndjson(
        Path(validation_env["skill_trace_dir"]) / "attributions.ndjson",
        [sample_attribution("attr_1"), sample_attribution("attr_2")],
    )
    write_ndjson(Path(validation_env["skill_trace_dir"]) / "attribution_reviews.ndjson", [sample_review("attr_1")])

    result = attribute_validate.command_queue(type("Args", (), {"skill": validation_env["skill"], "json": False})())
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pending_review_count"] == 1
    assert payload["pending_reviews"][0]["attribution_id"] == "attr_2"


def test_review_appends_human_scores(validation_env: dict[str, Path | str], capsys: pytest.CaptureFixture[str]) -> None:
    result = attribute_validate.command_review(
        type(
            "Args",
            (),
            {
                "skill": validation_env["skill"],
                "attribution_id": "attr_3",
                "legibility": 4,
                "plausibility": 5,
                "conservatism": 5,
                "usefulness": 4,
                "trustworthiness": 4,
                "notes": "Good replay result",
            },
        )()
    )
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    reviews = attribute_validate.load_reviews(str(validation_env["skill"]))
    assert len(reviews) == 1
    assert reviews[0]["attribution_id"] == "attr_3"
    assert payload["average_score"] == pytest.approx(4.4)


def test_summary_marks_promotion_ready_when_review_thresholds_are_met(validation_env: dict[str, Path | str], capsys: pytest.CaptureFixture[str]) -> None:
    attributions = [sample_attribution("attr_1"), sample_attribution("attr_2"), sample_attribution("attr_3")]
    reviews = [sample_review("attr_1", 4), sample_review("attr_2", 4), sample_review("attr_3", 5)]
    write_ndjson(Path(validation_env["skill_trace_dir"]) / "attributions.ndjson", attributions)
    write_ndjson(Path(validation_env["skill_trace_dir"]) / "attribution_reviews.ndjson", reviews)
    write_json(Path(validation_env["skill_trace_dir"]) / "component_index.json", {"skill": validation_env["skill"]})

    result = attribute_validate.command_summary(type("Args", (), {"skill": validation_env["skill"], "json": False})())
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["promotion_ready"] is True
    assert payload["gates"]["mechanical_readiness"]["passed"] is True
    assert payload["gates"]["mapping_stability"]["passed"] is True
    assert payload["gates"]["human_usefulness"]["passed"] is True
    assert Path(validation_env["skill_trace_dir"]).joinpath("validation_summary.json").exists()


def test_summary_blocks_promotion_when_reviews_are_missing(validation_env: dict[str, Path | str], capsys: pytest.CaptureFixture[str]) -> None:
    write_ndjson(Path(validation_env["skill_trace_dir"]) / "attributions.ndjson", [sample_attribution("attr_1")])
    write_json(Path(validation_env["skill_trace_dir"]) / "component_index.json", {"skill": validation_env["skill"]})

    result = attribute_validate.command_summary(type("Args", (), {"skill": validation_env["skill"], "json": False})())
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["promotion_ready"] is False
    assert payload["gates"]["mechanical_readiness"]["passed"] is True
    assert payload["gates"]["human_usefulness"]["passed"] is False


def test_cli_summary_runs_end_to_end(validation_env: dict[str, Path | str]) -> None:
    write_ndjson(Path(validation_env["skill_trace_dir"]) / "attributions.ndjson", [sample_attribution("attr_cli")])
    write_json(Path(validation_env["skill_trace_dir"]) / "component_index.json", {"skill": validation_env["skill"]})

    env = os.environ.copy()
    env["AGENTS_TRACES_ROOT"] = str(validation_env["traces_root"])
    result = subprocess.run(
        [
            sys.executable,
            str(SHARED_ROOT / "attribute_validate.py"),
            "summary",
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
    assert payload["skill"] == validation_env["skill"]
    assert payload["inputs"]["attribution_count"] == 1


def test_packet_generates_markdown_for_pending_reviews(validation_env: dict[str, Path | str], capsys: pytest.CaptureFixture[str]) -> None:
    write_ndjson(
        Path(validation_env["skill_trace_dir"]) / "attributions.ndjson",
        [sample_attribution("attr_1"), sample_attribution("attr_2")],
    )
    write_ndjson(Path(validation_env["skill_trace_dir"]) / "attribution_reviews.ndjson", [sample_review("attr_1")])

    result = attribute_validate.command_packet(type("Args", (), {"skill": validation_env["skill"], "limit": 0, "json": False})())
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pending_review_count"] == 1
    packet_path = Path(payload["packet_file"])
    assert packet_path.exists()
    packet = packet_path.read_text()
    assert "## attr_2" in packet
    assert "attribute_validate.py\" review" in packet
