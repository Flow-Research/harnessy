#!/usr/bin/env python3
"""Tests for ratchet.py score history + comprehensive help (issues #27, #28).

Pure stdlib (unittest) so it runs without the jarvis-cli dependency set:

    python3 tests/ratchet/test_ratchet_history.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RATCHET_PATH = REPO_ROOT / "tools" / "flow-install" / "skills" / "_shared" / "ratchet.py"


def _load_ratchet():
    spec = importlib.util.spec_from_file_location("ratchet", RATCHET_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ratchet = _load_ratchet()

REQUIRED_KEYS = ("timestamp", "skill", "score", "f", "p", "q", "r")


class ScoreHistoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._orig_state_dir = ratchet.autoflow_state_dir
        ratchet.autoflow_state_dir = lambda: self.tmp

    def tearDown(self):
        ratchet.autoflow_state_dir = self._orig_state_dir
        self._tmp.cleanup()

    def _read_history(self):
        return ratchet.score_history_path().read_text().splitlines()

    def test_two_scores_produce_two_entries(self):
        variables = {"f": 0.9, "p": 0.8, "q": 0.7, "r": 0.1}
        ratchet.append_score_history("issue-flow", 1, 0.5, variables)
        ratchet.append_score_history("issue-flow", 1, 0.6, variables)

        lines = self._read_history()
        self.assertGreaterEqual(len(lines), 2)

    def test_each_entry_is_valid_json_with_required_keys(self):
        variables = {"f": 0.9, "p": 0.8, "q": 0.7, "r": 0.1}
        ratchet.append_score_history("issue-flow", 1, 0.5, variables)

        entry = json.loads(self._read_history()[0])
        for key in REQUIRED_KEYS:
            self.assertIn(key, entry)
        self.assertEqual(entry["skill"], "issue-flow")
        self.assertEqual(entry["score"], 0.5)

    def test_history_is_append_only(self):
        variables = {"f": 0.9, "p": 0.8, "q": 0.7, "r": 0.1}
        ratchet.append_score_history("a", 1, 0.5, variables)
        first = self._read_history()[0]

        ratchet.append_score_history("b", 1, 0.6, variables)
        lines = self._read_history()

        # Original line is preserved verbatim; file only grows.
        self.assertEqual(lines[0], first)
        self.assertEqual(len(lines), 2)

    def test_layer_two_records_h_and_c(self):
        variables = {"f": 0.9, "p": 0.8, "q": 0.7, "r": 0.1, "h": 0.2, "c": 0.3}
        ratchet.append_score_history("issue-flow", 2, 0.5, variables)
        entry = json.loads(self._read_history()[0])
        self.assertEqual(entry["layer"], 2)
        self.assertEqual(entry["h"], 0.2)
        self.assertEqual(entry["c"], 0.3)

    def test_load_score_history_filters_by_skill(self):
        variables = {"f": 0.9, "p": 0.8, "q": 0.7, "r": 0.1}
        ratchet.append_score_history("a", 1, 0.5, variables)
        ratchet.append_score_history("b", 1, 0.6, variables)
        self.assertEqual(len(ratchet.load_score_history("a")), 1)
        self.assertEqual(len(ratchet.load_score_history()), 2)


class CostExtractionTest(unittest.TestCase):
    """Thrust B: real cost tracking feeds the `c` dimension."""

    def _cfg(self, **overrides):
        cfg = dict(ratchet.DEFAULT_CONFIG)
        cfg.update(overrides)
        return cfg

    def test_cost_usd_used_directly(self):
        cfg = self._cfg(target_cost=1.0)
        runs = [{"outcome": "completed", "cost_usd": 0.5},
                {"outcome": "completed", "cost_usd": 1.5}]
        v = ratchet.extract_variables(runs, [], cfg)
        self.assertEqual(v["raw"]["runs_with_cost"], 2)
        self.assertAlmostEqual(v["raw"]["avg_cost_usd"], 1.0)
        self.assertAlmostEqual(v["c"], 1.0)  # avg 1.0 / budget 1.0, capped

    def test_tokens_priced_when_no_cost_usd(self):
        cfg = self._cfg(price_per_1k_input=0.003, price_per_1k_output=0.015, target_cost=1.0)
        runs = [{"outcome": "completed", "tokens_in": 1000, "tokens_out": 1000}]
        cost = ratchet.run_cost_usd(runs[0], cfg)
        self.assertAlmostEqual(cost, 0.018)
        v = ratchet.extract_variables(runs, [], cfg)
        self.assertEqual(v["raw"]["total_tokens_in"], 1000)
        self.assertAlmostEqual(v["raw"]["avg_cost_usd"], 0.018)

    def test_legacy_cost_field_back_compat(self):
        self.assertAlmostEqual(ratchet.run_cost_usd({"cost": 0.3}, self._cfg()), 0.3)

    def test_no_cost_signal_is_excluded_not_free(self):
        cfg = self._cfg(target_cost=1.0)
        runs = [{"outcome": "completed"}, {"outcome": "completed"}]
        v = ratchet.extract_variables(runs, [], cfg)
        self.assertEqual(v["raw"]["runs_with_cost"], 0)
        self.assertEqual(v["c"], 0.0)


class RevertSafetyTest(unittest.TestCase):
    """Thrust C: safe, auditable auto-revert."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.repo)

        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        os.environ.update(env)
        subprocess.run(["git", "init", "-q"], check=True)

        self.skills = self.repo / "skills"
        self.skill_dir = self.skills / "demo"
        self.skill_dir.mkdir(parents=True)
        (self.skill_dir / "a.txt").write_text("baseline\n")
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "baseline"], check=True)
        self.tag = "ratchet/demo/snap"
        subprocess.run(["git", "tag", self.tag], check=True)

        # Improvement: modify a.txt, add a tracked orphan and an untracked orphan.
        (self.skill_dir / "a.txt").write_text("improved\n")
        (self.skill_dir / "c.txt").write_text("added-tracked\n")
        subprocess.run(["git", "add", str(self.skill_dir / "c.txt")], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "improve"], check=True)
        (self.skill_dir / "b.txt").write_text("added-untracked\n")

        os.environ["AGENTS_SKILLS_ROOT"] = str(self.skills)
        self._orig_state_dir = ratchet.autoflow_state_dir
        ratchet.autoflow_state_dir = lambda: self.repo / "state"

    def tearDown(self):
        ratchet.autoflow_state_dir = self._orig_state_dir
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_tag_exists(self):
        self.assertTrue(ratchet.tag_exists(self.tag))
        self.assertFalse(ratchet.tag_exists("ratchet/demo/missing"))

    def test_plan_identifies_orphans(self):
        plan = ratchet.build_revert_plan("demo", self.tag)
        self.assertIn("skills/demo/c.txt", plan["orphan_tracked"])
        self.assertIn("skills/demo/b.txt", plan["orphan_untracked"])
        self.assertTrue(any(f.endswith("a.txt") for f in plan["restore_files"]))

    def test_missing_tag_aborts_without_mutation(self):
        result = ratchet.perform_revert("demo", "ratchet/demo/missing")
        self.assertFalse(result["reverted"])
        self.assertIn("error", result)
        self.assertEqual((self.skill_dir / "a.txt").read_text(), "improved\n")

    def test_revert_restores_and_writes_evidence(self):
        result = ratchet.perform_revert("demo", self.tag)
        self.assertTrue(result["reverted"])
        self.assertEqual((self.skill_dir / "a.txt").read_text(), "baseline\n")
        # Orphans survive a plain revert.
        self.assertTrue((self.skill_dir / "c.txt").exists())
        self.assertTrue(Path(result["evidence"]).exists())

    def test_clean_removes_orphans(self):
        result = ratchet.perform_revert("demo", self.tag, clean=True)
        self.assertTrue(result["reverted"])
        self.assertFalse((self.skill_dir / "c.txt").exists())
        self.assertFalse((self.skill_dir / "b.txt").exists())


class HelpOutputTest(unittest.TestCase):
    """Issue #28: top-level and per-subcommand help must succeed and describe usage."""

    SUBCOMMANDS = ("score", "gates", "snapshot", "evaluate", "decide", "status", "history")

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(RATCHET_PATH), *args],
            capture_output=True, text=True,
        )

    def test_top_level_help_lists_all_subcommands(self):
        result = self._run("--help")
        self.assertEqual(result.returncode, 0)
        for cmd in self.SUBCOMMANDS:
            self.assertIn(cmd, result.stdout)

    def test_each_subcommand_help_has_example(self):
        for cmd in self.SUBCOMMANDS:
            result = self._run(cmd, "--help")
            self.assertEqual(result.returncode, 0, f"{cmd} --help failed")
            self.assertIn("examples:", result.stdout, f"{cmd} --help missing examples")
            self.assertIn(f"ratchet.py {cmd}", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
