#!/usr/bin/env python3
"""
Autoresearch ratchet: multiplicative composite metric with hard constraint gates.

This is evaluation infrastructure — fixed and not modified by agents.
It implements the ratchet mechanics for Autoflow's autoresearch loop:
snapshot skill state, evaluate improvement impact, and make binary
keep/revert decisions.

The metric is a layered multiplicative composite:

  Layer 1: S = f^0.35 · p^0.25 · q^0.25 · (1-r)^0.15
  Layer 2: S = f^0.35 · p^0.20 · q^0.20 · (1-r)^0.10 · (1-h)^0.10 · (1-c)^0.05

Hard constraint gates (vetoes):
  - Catastrophic failure rate must be 0
  - Regression rate must be ≤ configured max
  - Human intervention rate must be ≤ configured max

Usage:
    ratchet.py score --skill issue-flow [--layer 1] [--json]
    ratchet.py gates --skill issue-flow [--json]
    ratchet.py snapshot --skill <name>
    ratchet.py evaluate --skill <name> --window <N> [--json]
    ratchet.py decide --skill <name> [--json]
    ratchet.py status --skill <name> [--json]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import from sibling evaluation scripts
sys.path.insert(0, str(Path(__file__).parent))
from run_metrics import compute_metrics
from trace_query import load_traces


# --- Default configuration (overridden by program.md parsing) ---

DEFAULT_CONFIG = {
    "layer": 1,
    "epsilon": 0.02,
    "max_loops": 5.0,
    "max_regression_rate": 0.1,
    "max_human_intervention": 0.5,
    # Cost normalization. target_cost is the per-run USD budget the cost
    # dimension (c) is normalized against: a run at target_cost maps to c=1.0.
    # When runs carry token counts instead of a direct cost_usd, they are
    # priced with these per-1K-token rates (0 = disabled).
    "target_cost": 1.0,
    "price_per_1k_input": 0.0,
    "price_per_1k_output": 0.0,
    "evaluation_window": 3,
    # Layer 1 exponents
    "layer_1": {"f": 0.35, "p": 0.25, "q": 0.25, "r": 0.15},
    # Layer 2 exponents
    "layer_2": {"f": 0.35, "p": 0.20, "q": 0.20, "r": 0.10, "h": 0.10, "c": 0.05},
}


# --- Paths ---

def traces_root() -> Path:
    return Path(os.environ.get("AGENTS_TRACES_ROOT", Path.home() / ".agents" / "traces"))


def skills_root() -> Path:
    return Path(os.environ.get("AGENTS_SKILLS_ROOT", Path.home() / ".agents" / "skills"))


def autoflow_state_dir() -> Path:
    """Per-project autoflow state directory.

    Prefers .jarvis/context/autoflow/ (per-project) if it exists or can be
    created. Falls back to ~/.agents/traces/autoflow/ (global) for backwards
    compatibility or when not inside a project with .jarvis/context/.
    """
    # Check for per-project path relative to git root or cwd
    for base in [_git_root(), Path.cwd()]:
        if base is None:
            continue
        project_dir = base / ".jarvis" / "context" / "autoflow"
        if project_dir.exists() or (base / ".jarvis" / "context").exists():
            project_dir.mkdir(parents=True, exist_ok=True)
            return project_dir

    # Fallback to global
    return traces_root() / "autoflow"


def _git_root() -> Optional[Path]:
    """Find git repository root, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def ratchet_state_path(skill: str) -> Path:
    return autoflow_state_dir() / f"ratchet_{skill}.json"


def runs_path() -> Path:
    return autoflow_state_dir() / "runs.ndjson"


def score_history_path() -> Path:
    return autoflow_state_dir() / "score_history.ndjson"


# --- Run record loading ---

def load_runs(skill: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load run records from runs.ndjson."""
    rp = runs_path()
    if not rp.exists():
        return []
    runs = []
    for line in rp.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            if skill and record.get("skill", "issue-flow") != skill:
                continue
            runs.append(record)
        except json.JSONDecodeError:
            continue
    return runs


# --- Cost extraction ---

def _run_tokens(run: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Extract input/output token counts from a run record, if present.

    Accepts either flat keys (tokens_in / tokens_out) or a nested
    `tokens: {"in": ..., "out": ...}` object.
    """
    tokens = run.get("tokens")
    if isinstance(tokens, dict):
        tin = tokens.get("in", tokens.get("input"))
        tout = tokens.get("out", tokens.get("output"))
    else:
        tin = run.get("tokens_in")
        tout = run.get("tokens_out")
    if tin is None and tout is None:
        return None
    return {"in": int(tin or 0), "out": int(tout or 0)}


def run_cost_usd(run: Dict[str, Any], config: Dict[str, Any]) -> Optional[float]:
    """Compute a single run's cost in USD, or None if the run has no cost data.

    Resolution order:
      1. explicit `cost_usd`
      2. token counts priced with configured per-1K rates
      3. legacy `cost` field (back-compat)
    A run with no cost signal returns None so it is excluded from the average
    rather than being counted as free.
    """
    if run.get("cost_usd") is not None:
        return float(run["cost_usd"])

    tokens = _run_tokens(run)
    if tokens is not None:
        price_in = config.get("price_per_1k_input", 0.0)
        price_out = config.get("price_per_1k_output", 0.0)
        return (tokens["in"] / 1000.0) * price_in + (tokens["out"] / 1000.0) * price_out

    if run.get("cost") is not None:
        return float(run["cost"])

    return None


# --- Variable extraction ---

def extract_variables(
    runs: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract normalized variables from run records and traces.

    Returns dict with keys: f, p, q, r, h, c plus raw values.
    """
    if not runs:
        return {"f": 0.0, "p": 0.0, "q": 0.0, "r": 1.0, "h": 1.0, "c": 1.0}

    # f = final success rate
    completed = sum(1 for r in runs if r.get("outcome") == "completed")
    f = completed / len(runs) if runs else 0.0

    # p = first-pass success rate (from traces)
    metrics = compute_metrics(
        [t for t in traces if t.get("gate", {}).get("type") not in ("retrospective",)]
    )
    p = metrics.get("first_pass_rate", 0.0)

    # q = output quality (from run records: tests_passed / tests_total)
    tests_passed_total = 0
    tests_total_total = 0
    for r in runs:
        tp = r.get("tests_passed")
        tt = r.get("tests_total")
        if tp is not None and tt is not None and tt > 0:
            tests_passed_total += tp
            tests_total_total += tt
    q = tests_passed_total / tests_total_total if tests_total_total > 0 else p  # fallback to first-pass rate

    # r = normalized refinement burden
    max_loops = config.get("max_loops", DEFAULT_CONFIG["max_loops"])
    avg_loops = metrics.get("avg_refinement_loops", 0.0)
    r = min(avg_loops / max_loops, 1.0)

    # h = human intervention rate (from run records)
    human_triggered_total = 0
    human_total_total = 0
    for run in runs:
        ht = run.get("human_gates_triggered")
        htotal = run.get("human_gates_total")
        if ht is not None and htotal is not None and htotal > 0:
            human_triggered_total += ht
            human_total_total += htotal
    h = human_triggered_total / human_total_total if human_total_total > 0 else 0.0

    # c = normalized cost. Averaged only over runs that carry a cost signal
    # (cost_usd, token counts, or legacy cost); runs without cost data are
    # excluded so missing instrumentation reads as c=0 rather than free.
    target_cost = config.get("target_cost", DEFAULT_CONFIG["target_cost"])
    run_costs = [rc for rc in (run_cost_usd(run, config) for run in runs) if rc is not None]
    avg_cost = sum(run_costs) / len(run_costs) if run_costs else 0.0
    c = min(avg_cost / target_cost, 1.0) if target_cost > 0 else 0.0

    token_totals = [_run_tokens(run) for run in runs]
    total_tokens_in = sum(t["in"] for t in token_totals if t)
    total_tokens_out = sum(t["out"] for t in token_totals if t)

    return {
        "f": round(f, 4),
        "p": round(p, 4),
        "q": round(q, 4),
        "r": round(r, 4),
        "h": round(h, 4),
        "c": round(c, 4),
        "raw": {
            "total_runs": len(runs),
            "completed_runs": completed,
            "avg_refinement_loops": round(avg_loops, 3),
            "tests_passed": tests_passed_total,
            "tests_total": tests_total_total,
            "human_gates_triggered": human_triggered_total,
            "human_gates_total": human_total_total,
            "runs_with_cost": len(run_costs),
            "avg_cost_usd": round(avg_cost, 6),
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
        },
    }


# --- Composite score ---

def compute_score(variables: Dict[str, float], layer: int = 1) -> float:
    """Compute the multiplicative composite score.

    Layer 1: S = f^0.35 · p^0.25 · q^0.25 · (1-r)^0.15
    Layer 2: S = f^0.35 · p^0.20 · q^0.20 · (1-r)^0.10 · (1-h)^0.10 · (1-c)^0.05

    All inputs must be in [0, 1]. Score range: [0, 1].
    """
    f = max(variables.get("f", 0.0), 1e-10)  # avoid log(0)
    p = max(variables.get("p", 0.0), 1e-10)
    q = max(variables.get("q", 0.0), 1e-10)
    r_inv = max(1.0 - variables.get("r", 0.0), 1e-10)

    if layer == 1:
        exp = DEFAULT_CONFIG["layer_1"]
        score = (f ** exp["f"]) * (p ** exp["p"]) * (q ** exp["q"]) * (r_inv ** exp["r"])
    else:
        exp = DEFAULT_CONFIG["layer_2"]
        h_inv = max(1.0 - variables.get("h", 0.0), 1e-10)
        c_inv = max(1.0 - variables.get("c", 0.0), 1e-10)
        score = (
            (f ** exp["f"])
            * (p ** exp["p"])
            * (q ** exp["q"])
            * (r_inv ** exp["r"])
            * (h_inv ** exp["h"])
            * (c_inv ** exp["c"])
        )

    return round(score, 6)


# --- Hard constraint gates ---

def check_gates(
    runs: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Check hard constraint gates. Returns pass/fail for each gate.

    Gates are vetoes — if any fails, the candidate is rejected regardless of score.
    """
    max_regression = config.get("max_regression_rate", DEFAULT_CONFIG["max_regression_rate"])
    max_human = config.get("max_human_intervention", DEFAULT_CONFIG["max_human_intervention"])

    # Catastrophic failure rate
    catastrophic = sum(1 for r in runs if r.get("catastrophic_failure", False))
    catastrophic_rate = catastrophic / len(runs) if runs else 0.0

    # Regression rate
    regressions = sum(1 for r in runs if r.get("regression_detected", False))
    regression_rate = regressions / len(runs) if runs else 0.0

    # Human intervention rate (fraction of runs needing human rescue)
    human_runs = 0
    for r in runs:
        ht = r.get("human_gates_triggered", 0)
        if ht > 0:
            human_runs += 1
    human_rate = human_runs / len(runs) if runs else 0.0

    gates = {
        "catastrophic_failure": {
            "value": round(catastrophic_rate, 4),
            "threshold": 0.0,
            "passed": catastrophic_rate == 0.0,
        },
        "regression": {
            "value": round(regression_rate, 4),
            "threshold": max_regression,
            "passed": regression_rate <= max_regression,
        },
        "human_intervention": {
            "value": round(human_rate, 4),
            "threshold": max_human,
            "passed": human_rate <= max_human,
        },
    }

    all_passed = all(g["passed"] for g in gates.values())

    return {
        "all_passed": all_passed,
        "gates": gates,
        "total_runs": len(runs),
    }


# --- Ratchet state management ---

def load_ratchet_state(skill: str) -> Optional[Dict[str, Any]]:
    path = ratchet_state_path(skill)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_ratchet_state(skill: str, state: Dict[str, Any]) -> None:
    path = ratchet_state_path(skill)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


# --- Score history (append-only) ---

def append_score_history(
    skill: str,
    layer: int,
    score: float,
    variables: Dict[str, Any],
) -> Path:
    """Append one score computation to the append-only history log.

    Each line is a self-contained JSON object with the timestamp, skill,
    layer, composite score, and the individual normalized variables. The file
    is opened in append mode and never truncated, so it forms a durable
    time-series of how a skill's ratchet score evolves across runs.
    """
    path = score_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "skill": skill,
        "layer": layer,
        "score": score,
        "f": variables.get("f"),
        "p": variables.get("p"),
        "q": variables.get("q"),
        "r": variables.get("r"),
    }
    # Layer-2 variables are only meaningful when present.
    if layer >= 2:
        entry["h"] = variables.get("h")
        entry["c"] = variables.get("c")

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return path


def load_score_history(skill: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load score history entries, optionally filtered by skill."""
    path = score_history_path()
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if skill and record.get("skill") != skill:
            continue
        entries.append(record)
    return entries


# --- CLI commands ---

def command_score(args: argparse.Namespace) -> int:
    """Compute and display the composite score."""
    skill = args.skill
    layer = args.layer

    traces = load_traces(skill)
    runs = load_runs()

    config = dict(DEFAULT_CONFIG)
    variables = extract_variables(runs, traces, config)
    score = compute_score(variables, layer=layer)

    if not args.no_history:
        append_score_history(skill, layer, score, variables)

    result = {
        "skill": skill,
        "layer": layer,
        "score": score,
        "variables": {k: v for k, v in variables.items() if k != "raw"},
        "raw": variables.get("raw", {}),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"=== {skill} Ratchet Score (Layer {layer}) ===")
        print(f"  Score: {score:.4f}")
        print(f"  f (final success):    {variables['f']:.2f}")
        print(f"  p (first-pass):       {variables['p']:.2f}")
        print(f"  q (output quality):   {variables['q']:.2f}")
        print(f"  r (refinement burden):{variables['r']:.2f}")
        if layer >= 2:
            print(f"  h (human intervention):{variables['h']:.2f}")
            print(f"  c (cost):             {variables['c']:.2f}")

        if args.verbose:
            print()
            print("  Breakdown (variable | raw | weight | weighted contribution):")
            exp = DEFAULT_CONFIG["layer_1" if layer == 1 else "layer_2"]
            # base values mirror compute_score: (1 - x) for r/h/c, floored at 1e-10
            inverted = {"r", "h", "c"}
            labels = {
                "f": "final success",
                "p": "first-pass",
                "q": "output quality",
                "r": "refinement burden",
                "h": "human intervention",
                "c": "cost",
            }
            for name in exp:
                raw = variables[name]
                base = max((1.0 - raw) if name in inverted else raw, 1e-10)
                weight = exp[name]
                contribution = base ** weight
                print(
                    f"    {name} ({labels[name]}): raw={raw:.4f}  "
                    f"weight={weight:.2f}  contribution={contribution:.4f}"
                )
            raw_block = variables.get("raw", {})
            if raw_block:
                print()
                print("  Raw aggregates:")
                for k, v in raw_block.items():
                    print(f"    {k}: {v}")

    return 0


def command_gates(args: argparse.Namespace) -> int:
    """Check hard constraint gates."""
    runs = load_runs()
    config = dict(DEFAULT_CONFIG)
    result = check_gates(runs, config)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASSED" if result["all_passed"] else "FAILED"
        print(f"=== Hard Constraint Gates: {status} ===")
        for name, gate in result["gates"].items():
            icon = "✓" if gate["passed"] else "✗"
            print(f"  {icon} {name}: {gate['value']:.2f} (threshold: {gate['threshold']})")

    return 0


def command_snapshot(args: argparse.Namespace) -> int:
    """Snapshot current skill state before improvement.

    Creates a git tag at ratchet/<skill>/<timestamp> and records
    baseline score in ratchet state.
    """
    skill = args.skill
    skill_path = skills_root() / skill

    if not skill_path.exists():
        print(json.dumps({"error": f"Skill not found: {skill_path}"}), file=sys.stderr)
        return 1

    # Compute baseline score
    traces = load_traces(skill)
    runs = load_runs()
    config = dict(DEFAULT_CONFIG)
    variables = extract_variables(runs, traces, config)
    baseline_score = compute_score(variables, layer=config.get("layer", 1))

    # Create git tag
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag_name = f"ratchet/{skill}/{timestamp}"

    try:
        subprocess.run(
            ["git", "tag", tag_name, "-m", f"Ratchet snapshot for {skill}"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(json.dumps({"error": f"Git tag failed: {e.stderr.strip()}"}), file=sys.stderr)
        return 1

    # Save ratchet state
    state = {
        "skill": skill,
        "status": "evaluating",
        "snapshot_tag": tag_name,
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "baseline_score": baseline_score,
        "baseline_variables": {k: v for k, v in variables.items() if k != "raw"},
        "baseline_runs_count": len(runs),
        "evaluation_window": config.get("evaluation_window", DEFAULT_CONFIG["evaluation_window"]),
        "runs_since_snapshot": 0,
    }
    save_ratchet_state(skill, state)

    result = {
        "ok": True,
        "tag": tag_name,
        "baseline_score": baseline_score,
        "evaluation_window": state["evaluation_window"],
    }
    print(json.dumps(result, indent=2))
    return 0


def command_evaluate(args: argparse.Namespace) -> int:
    """Evaluate improvement impact after N runs."""
    skill = args.skill
    window = args.window

    state = load_ratchet_state(skill)
    if not state:
        print(json.dumps({"error": f"No ratchet state for {skill}. Run 'snapshot' first."}), file=sys.stderr)
        return 1

    # Load runs since snapshot
    all_runs = load_runs()
    baseline_count = state.get("baseline_runs_count", 0)
    post_runs = all_runs[baseline_count:]

    if len(post_runs) < window:
        result = {
            "status": "waiting",
            "runs_completed": len(post_runs),
            "runs_needed": window,
            "baseline_score": state["baseline_score"],
        }
        print(json.dumps(result, indent=2))
        return 0

    # Use only the evaluation window runs
    eval_runs = post_runs[:window]

    # Compute candidate score
    traces = load_traces(skill)
    config = dict(DEFAULT_CONFIG)
    variables = extract_variables(eval_runs, traces, config)
    candidate_score = compute_score(variables, layer=config.get("layer", 1))

    # Check hard gates on evaluation window
    gate_result = check_gates(eval_runs, config)

    baseline_score = state["baseline_score"]
    delta = round(candidate_score - baseline_score, 6)
    epsilon = config.get("epsilon", DEFAULT_CONFIG["epsilon"])

    # Update state
    state["candidate_score"] = candidate_score
    state["candidate_variables"] = {k: v for k, v in variables.items() if k != "raw"}
    state["delta"] = delta
    state["gates_passed"] = gate_result["all_passed"]
    state["runs_since_snapshot"] = len(post_runs)
    save_ratchet_state(skill, state)

    result = {
        "status": "ready",
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "delta": delta,
        "epsilon": epsilon,
        "gates": gate_result,
        "variables": {k: v for k, v in variables.items() if k != "raw"},
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
        print(f"=== {skill} Ratchet Evaluation ===")
        print(f"  Baseline:  {baseline_score:.4f}")
        print(f"  Candidate: {candidate_score:.4f}")
        print(f"  Delta:     {delta:+.4f} {arrow}")
        print(f"  Epsilon:   {epsilon}")
        print(f"  Gates:     {'PASSED' if gate_result['all_passed'] else 'FAILED'}")

    return 0


# --- Git revert safety ---

def _git(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check)


def tag_exists(tag: str) -> bool:
    """Return True if the given ref resolves to a commit."""
    return _git(["rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}"], check=False).returncode == 0


def _files_at_ref(ref: str, path: str) -> set:
    result = _git(["ls-tree", "-r", "--name-only", ref, "--", path], check=False)
    if result.returncode != 0:
        return set()
    return {line for line in result.stdout.splitlines() if line.strip()}


def _tracked_files_now(path: str) -> set:
    result = _git(["ls-files", "--", path], check=False)
    return {line for line in result.stdout.splitlines() if line.strip()}


def _untracked_files_now(path: str) -> set:
    result = _git(["ls-files", "--others", "--exclude-standard", "--", path], check=False)
    return {line for line in result.stdout.splitlines() if line.strip()}


def reverts_dir() -> Path:
    return autoflow_state_dir() / "reverts"


def build_revert_plan(skill: str, tag: str) -> Dict[str, Any]:
    """Describe what a revert to `tag` would change, without touching anything.

    Orphan files exist in the working tree now but not in the snapshot tag,
    so a path-scoped `git checkout` would leave them behind. They are what
    makes a naive revert incomplete.
    """
    skill_path = str(skills_root() / skill)
    at_tag = _files_at_ref(tag, skill_path)
    tracked_now = _tracked_files_now(skill_path)

    diff = _git(["diff", "--stat", tag, "--", skill_path], check=False)
    return {
        "skill": skill,
        "tag": tag,
        "tag_exists": tag_exists(tag),
        "skill_path": skill_path,
        "restore_files": sorted(at_tag),
        "orphan_tracked": sorted(tracked_now - at_tag),
        "orphan_untracked": sorted(_untracked_files_now(skill_path)),
        "diffstat": diff.stdout.strip() if diff.returncode == 0 else "",
    }


def write_revert_evidence(skill: str, tag: str, plan: Dict[str, Any]) -> Path:
    """Persist an auditable record of what a revert discarded."""
    d = reverts_dir()
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    skill_path = plan["skill_path"]

    diff = _git(["diff", tag, "--", skill_path], check=False)
    (d / f"{skill}_{ts}.diff").write_text(diff.stdout if diff.returncode == 0 else "")

    manifest_path = d / f"{skill}_{ts}.json"
    manifest = {
        "skill": skill,
        "tag": tag,
        "reverted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "restore_files": plan["restore_files"],
        "orphan_tracked": plan["orphan_tracked"],
        "orphan_untracked": plan["orphan_untracked"],
        "diffstat": plan["diffstat"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def perform_revert(skill: str, tag: str, clean: bool = False) -> Dict[str, Any]:
    """Restore a skill's files to a snapshot tag, with evidence.

    Returns a result dict. On failure the returned dict contains an "error"
    key and no mutation beyond what git itself applied.
    """
    skill_path = str(skills_root() / skill)

    if not tag_exists(tag):
        return {"error": f"Snapshot tag not found: {tag}", "reverted": False}

    plan = build_revert_plan(skill, tag)
    evidence = write_revert_evidence(skill, tag, plan)

    try:
        _git(["checkout", tag, "--", skill_path])
    except subprocess.CalledProcessError as e:
        return {"error": f"Git revert failed: {e.stderr.strip()}", "reverted": False,
                "evidence": str(evidence)}

    removed: List[str] = []
    if clean:
        for f in plan["orphan_tracked"]:
            if _git(["rm", "-f", "--", f], check=False).returncode == 0:
                removed.append(f)
        for f in plan["orphan_untracked"]:
            try:
                Path(f).unlink()
                removed.append(f)
            except OSError:
                pass

    return {
        "reverted": True,
        "tag": tag,
        "restored": len(plan["restore_files"]),
        "orphan_tracked": plan["orphan_tracked"],
        "orphan_untracked": plan["orphan_untracked"],
        "removed_orphans": removed,
        "evidence": str(evidence),
    }


def _classify_decision(delta: float, epsilon: float, gates_passed: bool) -> tuple:
    if not gates_passed:
        return "revert", "hard constraint gate failed"
    if delta > epsilon:
        return "keep", f"delta {delta:+.4f} exceeds epsilon {epsilon}"
    if delta < -epsilon:
        return "revert", f"delta {delta:+.4f} below negative epsilon {-epsilon}"
    return "keep", f"delta {delta:+.4f} within noise band (no regression)"


def command_decide(args: argparse.Namespace) -> int:
    """Make binary keep/revert decision.

    Decision logic:
      1. If any hard constraint gate fails → REVERT
      2. If ΔS > ε → KEEP
      3. If ΔS < -ε → REVERT
      4. If |ΔS| ≤ ε → KEEP (no regression, within noise)

    A revert restores the skill to its snapshot tag. --dry-run reports the
    decision and the revert plan (files to restore, orphan files that would
    survive) without touching git or ratchet state.
    """
    skill = args.skill

    state = load_ratchet_state(skill)
    if not state:
        print(json.dumps({"error": f"No ratchet state for {skill}. Run 'snapshot' then 'evaluate' first."}), file=sys.stderr)
        return 1

    if "delta" not in state:
        print(json.dumps({"error": "Evaluation not complete. Run 'evaluate' first."}), file=sys.stderr)
        return 1

    delta = state["delta"]
    epsilon = DEFAULT_CONFIG["epsilon"]
    gates_passed = state.get("gates_passed", True)
    tag = state.get("snapshot_tag")

    decision, reason = _classify_decision(delta, epsilon, gates_passed)

    # Dry run: report the decision and, for a revert, the plan — mutate nothing.
    if args.dry_run:
        result: Dict[str, Any] = {
            "dry_run": True,
            "decision": decision,
            "reason": reason,
            "delta": delta,
            "tag": tag,
        }
        if decision == "revert" and tag:
            result["revert_plan"] = build_revert_plan(skill, tag)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"=== {skill} Ratchet Decision (dry-run): would {decision.upper()} ===")
            print(f"  Reason: {reason}")
            if decision == "revert" and tag:
                plan = result["revert_plan"]
                if not plan["tag_exists"]:
                    print(f"  ⚠ snapshot tag missing: {tag}")
                print(f"  Would restore {len(plan['restore_files'])} file(s) from {tag}")
                orphans = plan["orphan_tracked"] + plan["orphan_untracked"]
                if orphans:
                    print(f"  ⚠ {len(orphans)} orphan file(s) would remain (use --clean to remove):")
                    for f in orphans:
                        print(f"      {f}")
        return 0

    # Execute revert.
    revert_result: Optional[Dict[str, Any]] = None
    if decision == "revert" and tag:
        revert_result = perform_revert(skill, tag, clean=args.clean)
        if revert_result.get("error"):
            print(json.dumps({
                "error": revert_result["error"],
                "decision": decision,
                "reason": reason,
            }), file=sys.stderr)
            return 1

    # Update state
    state["status"] = "decided"
    state["decision"] = decision
    state["reason"] = reason
    state["decided_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if revert_result:
        state["revert_evidence"] = revert_result.get("evidence")
        state["orphan_files"] = revert_result.get("orphan_tracked", []) + revert_result.get("orphan_untracked", [])
    save_ratchet_state(skill, state)

    result = {
        "decision": decision,
        "reason": reason,
        "baseline_score": state.get("baseline_score"),
        "candidate_score": state.get("candidate_score"),
        "delta": delta,
        "tag": tag,
    }
    if revert_result:
        result["revert"] = revert_result

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        icon = "✓ KEEP" if decision == "keep" else "✗ REVERT"
        print(f"=== {skill} Ratchet Decision: {icon} ===")
        print(f"  Reason: {reason}")
        print(f"  Baseline:  {state.get('baseline_score', '?')}")
        print(f"  Candidate: {state.get('candidate_score', '?')}")
        print(f"  Delta:     {delta:+.4f}")
        if decision == "revert" and revert_result:
            print(f"  Reverted to: {tag}")
            print(f"  Restored:    {revert_result.get('restored', 0)} file(s)")
            print(f"  Evidence:    {revert_result.get('evidence')}")
            orphans = revert_result.get("orphan_tracked", []) + revert_result.get("orphan_untracked", [])
            if orphans and not args.clean:
                print(f"  ⚠ {len(orphans)} orphan file(s) left behind (use --clean to remove)")

    return 0


def command_status(args: argparse.Namespace) -> int:
    """Show current ratchet state."""
    skill = args.skill
    state = load_ratchet_state(skill)

    if not state:
        result = {"skill": skill, "status": "idle", "message": "No active ratchet cycle."}
    else:
        result = {
            "skill": skill,
            "status": state.get("status", "unknown"),
            "snapshot_tag": state.get("snapshot_tag"),
            "baseline_score": state.get("baseline_score"),
            "candidate_score": state.get("candidate_score"),
            "delta": state.get("delta"),
            "decision": state.get("decision"),
            "runs_since_snapshot": state.get("runs_since_snapshot", 0),
            "evaluation_window": state.get("evaluation_window"),
        }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"=== {skill} Ratchet Status ===")
        for k, v in result.items():
            if v is not None:
                print(f"  {k}: {v}")

    return 0


def command_history(args: argparse.Namespace) -> int:
    """Show the recorded score history as a time-series trend."""
    entries = load_score_history(args.skill)
    if args.last:
        entries = entries[-args.last:]

    if args.json:
        print(json.dumps({"skill": args.skill, "count": len(entries), "history": entries}, indent=2))
        return 0

    if not entries:
        print(f"=== {args.skill} Score History ===")
        print("  (no history yet — run 'ratchet.py score' first)")
        return 0

    print(f"=== {args.skill} Score History (last {len(entries)}) ===")
    prev: Optional[float] = None
    for entry in entries:
        score = entry.get("score", 0.0)
        ts = str(entry.get("timestamp", ""))[:19]
        # Sparkline-style bar over the [0, 1] score range.
        filled = int(round(score * 20))
        bar = "█" * filled + "░" * (20 - filled)
        if prev is None:
            arrow = " "
        elif score > prev:
            arrow = "↑"
        elif score < prev:
            arrow = "↓"
        else:
            arrow = "="
        print(f"  {ts}  {bar}  {score:.4f} {arrow}  (L{entry.get('layer', 1)})")
        prev = score

    return 0


# --- Argument parsing ---

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ratchet.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Autoresearch ratchet: multiplicative composite metric with hard "
            "constraint gates.\n\n"
            "Runs the keep/revert loop for a skill: snapshot a baseline, let new "
            "runs accumulate, evaluate the candidate against the baseline, and "
            "make a binary keep/revert decision. 'score' and 'gates' are "
            "read-only inspections; 'history' shows the recorded score trend."
        ),
        epilog=(
            "examples:\n"
            "  ratchet.py score --skill issue-flow\n"
            "  ratchet.py score --skill issue-flow --layer 2 --verbose\n"
            "  ratchet.py history --skill issue-flow --last 10\n"
            "  ratchet.py snapshot --skill issue-flow\n"
            "  ratchet.py evaluate --skill issue-flow --window 3\n"
            "  ratchet.py decide --skill issue-flow\n\n"
            "Run 'ratchet.py <command> --help' for command-specific options."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    def add(name: str, help_text: str, description: str, epilog: str):
        return subparsers.add_parser(
            name,
            help=help_text,
            description=description,
            epilog=epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

    # score
    sc = add(
        "score",
        "Compute composite score",
        "Compute the multiplicative composite ratchet score from recorded runs "
        "and traces. Each invocation is appended to the score history log "
        "(disable with --no-history).",
        "examples:\n"
        "  ratchet.py score --skill issue-flow\n"
        "  ratchet.py score --skill issue-flow --layer 2 --verbose\n"
        "  ratchet.py score --skill issue-flow --json --no-history",
    )
    sc.add_argument("--skill", required=True, help="Skill name to score (e.g. issue-flow)")
    sc.add_argument("--layer", type=int, default=1, choices=[1, 2],
                    help="Metric layer: 1 (f/p/q/r) or 2 (adds h/c). Default: 1")
    sc.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    sc.add_argument(
        "--verbose",
        action="store_true",
        help="Print a per-variable breakdown (raw value, weight, weighted contribution).",
    )
    sc.add_argument(
        "--no-history",
        action="store_true",
        help="Do not append this computation to score_history.ndjson.",
    )

    # gates
    gt = add(
        "gates",
        "Check hard constraint gates",
        "Check the hard constraint gates (catastrophic failure, regression rate, "
        "human intervention rate). Any failing gate is a veto that rejects a "
        "candidate regardless of its score.",
        "examples:\n"
        "  ratchet.py gates --skill issue-flow\n"
        "  ratchet.py gates --skill issue-flow --json",
    )
    gt.add_argument("--skill", required=True, help="Skill name to check")
    gt.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    # snapshot
    sn = add(
        "snapshot",
        "Snapshot skill state before improvement",
        "Snapshot the current skill state before an improvement: creates a git "
        "tag at ratchet/<skill>/<timestamp> and records the baseline score in "
        "ratchet state. Run this before editing a skill.",
        "examples:\n"
        "  ratchet.py snapshot --skill issue-flow",
    )
    sn.add_argument("--skill", required=True, help="Skill name to snapshot")

    # evaluate
    ev = add(
        "evaluate",
        "Evaluate improvement impact",
        "Evaluate the candidate against the baseline over a window of "
        "post-snapshot runs. Reports the score delta versus epsilon and whether "
        "the hard gates pass. Requires a prior 'snapshot'.",
        "examples:\n"
        "  ratchet.py evaluate --skill issue-flow --window 3\n"
        "  ratchet.py evaluate --skill issue-flow --window 5 --json",
    )
    ev.add_argument("--skill", required=True, help="Skill name to evaluate")
    ev.add_argument("--window", type=int, required=True,
                    help="Number of post-improvement runs to evaluate")
    ev.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    # decide
    dc = add(
        "decide",
        "Make keep/revert decision",
        "Make the binary keep/revert decision from the latest evaluation. A "
        "failed gate or a delta below -epsilon reverts the skill to its snapshot "
        "tag; otherwise the change is kept. A revert writes an evidence diff to "
        ".jarvis/context/autoflow/reverts/. Requires 'snapshot' then 'evaluate'.",
        "examples:\n"
        "  ratchet.py decide --skill issue-flow\n"
        "  ratchet.py decide --skill issue-flow --dry-run\n"
        "  ratchet.py decide --skill issue-flow --clean --json",
    )
    dc.add_argument("--skill", required=True, help="Skill name to decide on")
    dc.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    dc.add_argument("--dry-run", action="store_true",
                    help="Report the decision and revert plan without mutating git or state.")
    dc.add_argument("--clean", action="store_true",
                    help="On revert, also remove orphan files not present in the snapshot tag.")

    # status
    st = add(
        "status",
        "Show ratchet state",
        "Show the current ratchet cycle state for a skill: snapshot tag, "
        "baseline and candidate scores, delta, decision, and progress toward "
        "the evaluation window.",
        "examples:\n"
        "  ratchet.py status --skill issue-flow\n"
        "  ratchet.py status --skill issue-flow --json",
    )
    st.add_argument("--skill", required=True, help="Skill name to inspect")
    st.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    # history
    hi = add(
        "history",
        "Show recorded score history",
        "Show the append-only score history recorded by 'score' as a time-series "
        "trend, with a per-entry bar and an up/down/flat marker relative to the "
        "previous entry.",
        "examples:\n"
        "  ratchet.py history --skill issue-flow\n"
        "  ratchet.py history --skill issue-flow --last 10\n"
        "  ratchet.py history --skill issue-flow --json",
    )
    hi.add_argument("--skill", required=True, help="Skill name to show history for")
    hi.add_argument("--last", type=int, default=None,
                    help="Show only the most recent N entries")
    hi.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    commands = {
        "score": command_score,
        "gates": command_gates,
        "snapshot": command_snapshot,
        "evaluate": command_evaluate,
        "decide": command_decide,
        "status": command_status,
        "history": command_history,
    }
    handler = commands.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
