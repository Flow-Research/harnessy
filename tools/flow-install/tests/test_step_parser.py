"""Unit tests for the goal-agent step-result extractor.

These pin the behavior of extract_step_result against the response shapes
Claude has actually produced — including the fenced-JSON shape that stalled
the weekly content run on 2026-04-19.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
PARSER_PATH = (
    REPO_ROOT
    / "tools"
    / "flow-install"
    / "skills"
    / "goal-agent"
    / "scripts"
    / "_step_parser.py"
)


def _load_parser():
    spec = importlib.util.spec_from_file_location("_step_parser", PARSER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def parser():
    return _load_parser()


def test_structured_output_dict_is_returned_directly(parser) -> None:
    output = {"structured_output": {"action": "decompose", "phases": []}}
    result = parser.extract_step_result(output)
    assert result == {"action": "decompose", "phases": []}


def test_result_string_with_plain_json_parses(parser) -> None:
    payload = {"action": "advance", "summary": "phase 1 done"}
    output = {"result": json.dumps(payload)}
    assert parser.extract_step_result(output) == payload


def test_result_string_with_json_code_fence_parses(parser) -> None:
    """Regression for 2026-04-19 weekly-content failure."""
    payload = {"action": "decompose", "summary": "three phases", "phases": [1, 2, 3]}
    fenced = "```json\n" + json.dumps(payload, indent=2) + "\n```"
    output = {"result": fenced}
    assert parser.extract_step_result(output) == payload


def test_result_string_with_bare_fence_parses(parser) -> None:
    payload = {"action": "advance"}
    fenced = "```\n" + json.dumps(payload) + "\n```"
    output = {"result": fenced}
    assert parser.extract_step_result(output) == payload


def test_content_field_with_prose_and_embedded_object_parses(parser) -> None:
    payload = {"action": "retry", "summary": "worker needed more info"}
    prose = (
        "Here's my decision based on the worker output:\n\n"
        + json.dumps(payload)
        + "\n\nLet me know if you'd like to see a trace."
    )
    output = {"content": prose}
    assert parser.extract_step_result(output) == payload


def test_nested_braces_in_strings_do_not_confuse_walker(parser) -> None:
    payload = {"action": "advance", "summary": "found {weird} text in file"}
    output = {"result": f"noise {{not valid}}\n{json.dumps(payload)}\ntrailing"}
    assert parser.extract_step_result(output) == payload


def test_missing_action_key_returns_none(parser) -> None:
    output = {"result": json.dumps({"phase": "discovery"})}
    assert parser.extract_step_result(output) is None


def test_completely_empty_output_returns_none(parser) -> None:
    assert parser.extract_step_result({}) is None


def test_malformed_string_returns_none(parser) -> None:
    output = {"result": "this is not json and has no braces"}
    assert parser.extract_step_result(output) is None


def test_structured_output_without_action_falls_back_to_result(parser) -> None:
    payload = {"action": "advance", "summary": "ok"}
    output = {
        "structured_output": {"unrelated": True},
        "result": json.dumps(payload),
    }
    assert parser.extract_step_result(output) == payload
