from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "tools" / "flow-install" / "skills" / "goal-agent" / "scripts" / "goal-agent"
TRIVIAL_GOAL = REPO_ROOT / "tools" / "flow-install" / "skills" / "goal-agent" / "templates" / "test-trivial-goal.md"


def run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_stdout(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.stdout, result.stderr
    return json.loads(result.stdout)


def test_run_setup_creates_identity_runtime_policy_and_state(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "run", str(TRIVIAL_GOAL), "--setup-only")
    assert result.returncode == 0, result.stderr
    payload = parse_stdout(result)
    run_dir = Path(payload["state_dir"])

    assert (run_dir / "identity.json").exists()
    assert (run_dir / "runtime-policy.json").exists()
    assert (run_dir / "state.json").exists()
    assert (run_dir / "prepared-goal.md").exists()

    state = json.loads((run_dir / "state.json").read_text())
    assert state["orchestrator_state"] == "INIT"
    assert state["role_reinforcement_interval"] == 2
    assert state["goal_type"] == "general"


def test_guard_blocks_non_state_write_and_allows_prompt_file(tmp_path: Path) -> None:
    setup = parse_stdout(run_cli(tmp_path, "run", str(TRIVIAL_GOAL), "--setup-only"))
    run_id = setup["run_id"]

    blocked = run_cli(tmp_path, "guard", run_id, "--tool", "Write", "--target", "src/app.ts")
    assert blocked.returncode == 1
    blocked_payload = parse_stdout(blocked)
    assert blocked_payload["allowed"] is False

    allowed = run_cli(
        tmp_path,
        "guard",
        run_id,
        "--tool",
        "Write",
        "--target",
        f".goal-agent/{run_id}/current-prompt.md",
    )
    assert allowed.returncode == 0
    allowed_payload = parse_stdout(allowed)
    assert allowed_payload["allowed"] is True


def test_meta_goal_setup_creates_chain_state_and_artifact_registry(tmp_path: Path) -> None:
    yaml = pytest.importorskip("yaml")
    assert yaml is not None

    meta_goal = tmp_path / "auth.meta.yaml"
    meta_goal.write_text(
        """
title: Test Chain
objective: Chain two goals
sub_goals:
  - id: first
    goal_file: first.md
    depends_on: []
  - id: second
    goal_file: second.md
    depends_on:
      - goal: first
constraints:
  max_total_budget_usd: 12
  allow_parallel_goals: true
""".strip()
        + "\n"
    )

    result = run_cli(tmp_path, "run", str(meta_goal), "--setup-only")
    assert result.returncode == 0, result.stderr
    payload = parse_stdout(result)
    run_dir = Path(payload["state_dir"])

    state = json.loads((run_dir / "state.json").read_text())
    assert state["meta_run_id"] == payload["run_id"]
    assert "first" in state["sub_goals"]
    assert (run_dir / "artifact-registry.json").exists()
    assert (run_dir / "prepared-goals").exists()


def test_approve_updates_state_and_prepared_goal(tmp_path: Path) -> None:
    goal = tmp_path / "goal.md"
    goal.write_text(
        """
# Goal: Auto verify demo

## Objective

Create `demo.py` and mention JWT in the output.

## Constraints

- Auto verify: true

## Verification

### Commands

```bash
test -f demo.py
```
""".strip()
        + "\n"
    )

    setup = parse_stdout(run_cli(tmp_path, "run", str(goal), "--setup-only"))
    run_id = setup["run_id"]
    approve = run_cli(tmp_path, "approve", run_id, "--approve-all")
    assert approve.returncode == 0, approve.stderr

    run_dir = Path(setup["state_dir"])
    state = json.loads((run_dir / "state.json").read_text())
    assert state["auto_verification"]["status"] == "approved"
    assert state["auto_verification"]["approved"]
    prepared_goal = (run_dir / "prepared-goal.md").read_text()
    assert "## Approved Auto Verification" in prepared_goal


def test_record_outcome_and_learn_generate_registry(tmp_path: Path) -> None:
    run_ids = []
    for index in range(3):
        setup = parse_stdout(run_cli(tmp_path, "run", str(TRIVIAL_GOAL), "--setup-only"))
        run_id = setup["run_id"]
        run_ids.append(run_id)
        run_dir = Path(setup["state_dir"])
        state = json.loads((run_dir / "state.json").read_text())
        state["phases"] = [
            {"name": f"Phase {index+1}", "status": "completed", "iterations": 1, "prompt_pattern": "task-with-context"}
        ]
        state["cumulative_spend_usd"] = 1.25
        (run_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n")
        recorded = run_cli(tmp_path, "record-outcome", run_id, "--strategy", "default")
        assert recorded.returncode == 0, recorded.stderr

    learned = run_cli(tmp_path, "learn")
    assert learned.returncode == 0, learned.stderr
    payload = parse_stdout(learned)
    assert payload["sample_size"] == 3
    assert "general" in payload["recommendations"]
