#!/usr/bin/env python3
"""Tests for ratchet.py score history + comprehensive help (issues #27, #28).

Pure stdlib (unittest) so it runs without the jarvis-cli dependency set:

    python3 tests/ratchet/test_ratchet_history.py
"""

import importlib.util
import json
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
