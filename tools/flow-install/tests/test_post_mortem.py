"""Tests for the post-mortem classifier and report generator.

The classifier is intentionally rule-based and conservative — these tests pin
the behavior on concrete failure logs from real runs, including 2026-04-19's
fenced-JSON stall and the Apr 12 green run for contrast.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
POST_MORTEM_PATH = (
    REPO_ROOT
    / "tools"
    / "flow-install"
    / "skills"
    / "goal-agent"
    / "scripts"
    / "post-mortem"
)


def _load_module():
    loader = importlib.machinery.SourceFileLoader("post_mortem", str(POST_MORTEM_PATH))
    spec = importlib.util.spec_from_loader("post_mortem", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules so @dataclass can resolve string annotations.
    sys.modules["post_mortem"] = module
    loader.exec_module(module)
    return module


@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOW_AUTO_FIX_LOG", str(tmp_path / "auto-fix.log"))
    return _load_module()


def _run_state(**overrides) -> dict:
    base = {
        "status": "failed",
        "iteration": 3,
        "current_phase": 0,
        "total_phases": 2,
        "started_at": "2026-04-19T19:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_parser_infra_classification_from_extractor_failure(pm) -> None:
    log = (
        "[2026-04-19 20:00:05] Starting run\n"
        "[2026-04-19 20:01:19] Step 1: action=fail, phase=-\n"
        "[2026-04-19 20:01:19] Retryable failure: Could not extract structured step result from Claude response\n"
    )
    c = pm.classify(log, _run_state())
    assert c.klass == "parser-infra"
    assert c.confidence >= 0.8
    assert any("Could not extract" in line for line in c.evidence)


def test_parser_infra_classification_from_keyerror_trace(pm) -> None:
    log = (
        'File "background-runner", line 449, in <listcomp>\n'
        '    "id": p["id"],\n'
        "KeyError: 'id'\n"
    )
    c = pm.classify(log, _run_state())
    assert c.klass == "parser-infra"


def test_budget_exhausted_classification(pm) -> None:
    log = (
        "[2026-04-19 21:05:00] Calling claude (budget_cap=2.00)\n"
        "[2026-04-19 21:05:30] Budget exhausted\n"
    )
    c = pm.classify(log, _run_state(error="Budget limit reached"))
    assert c.klass == "budget-exhausted"
    assert c.confidence >= 0.9


def test_transient_failure_classification(pm) -> None:
    log = (
        "[2026-04-19 21:05:00] Calling claude\n"
        "[2026-04-19 21:07:00] Claude call timed out after 120s\n"
    )
    c = pm.classify(log, _run_state())
    assert c.klass == "transient"


def test_goal_impossible_classification(pm) -> None:
    log = (
        "[2026-04-19 21:05:00] Calling claude\n"
        "[2026-04-19 21:05:15] Error: source_material path missing: drafts/2026/Apr\n"
    )
    c = pm.classify(log, _run_state())
    assert c.klass == "goal-impossible"


def test_worker_wrong_classification(pm) -> None:
    log = "[2026-04-19 21:10:00] Verification FAILED for phase 'generation' attempts=3\n"
    c = pm.classify(log, _run_state())
    assert c.klass == "worker-wrong"


def test_unknown_when_nothing_matches(pm) -> None:
    log = "[2026-04-19 21:00:00] Some unrelated informational message\n"
    c = pm.classify(log, _run_state())
    assert c.klass == "unknown"
    assert c.confidence == 0.0


def test_non_failed_state_returns_unknown(pm) -> None:
    log = "[2026-04-19 21:00:00] All good\n"
    c = pm.classify(log, _run_state(status="completed"))
    assert c.klass == "unknown"
    assert "completed" in c.summary


def test_first_matching_rule_wins(pm) -> None:
    log = (
        "[2026-04-19 21:00:00] Budget exhausted\n"
        "[2026-04-19 21:00:01] Could not extract structured step result\n"
    )
    c = pm.classify(log, _run_state())
    # Budget rule appears first in the rules table, so it should match.
    assert c.klass == "budget-exhausted"


def test_end_to_end_writes_artifacts(pm, tmp_path: Path) -> None:
    run_dir = tmp_path / "20260419-test-abc"
    run_dir.mkdir()
    (run_dir / "session.log").write_text(
        "[2026-04-19 20:00:00] starting\n"
        "[2026-04-19 20:01:00] Retryable failure: Could not extract structured step result\n"
    )
    (run_dir / "state.json").write_text(json.dumps(_run_state()))

    rc = pm.main([str(run_dir), "--json"])
    assert rc == 0

    post_mortem = (run_dir / "post-mortem.md").read_text()
    assert "class**: `parser-infra`" in post_mortem
    assert "Could not extract" in post_mortem

    # Parser-infra should have the placeholder diff.
    assert (run_dir / "proposed-patch.diff").exists()


def test_end_to_end_non_parser_infra_has_no_diff(pm, tmp_path: Path) -> None:
    run_dir = tmp_path / "20260419-test-xyz"
    run_dir.mkdir()
    (run_dir / "session.log").write_text("[2026-04-19 20:05:00] Budget exhausted\n")
    (run_dir / "state.json").write_text(json.dumps(_run_state()))

    rc = pm.main([str(run_dir)])
    assert rc == 0
    assert (run_dir / "post-mortem.md").exists()
    assert not (run_dir / "proposed-patch.diff").exists()
