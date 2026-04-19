"""Extract the structured step result from Claude's JSON output envelope.

Pulled out of background-runner so it can be covered by unit tests. The
extractor has to be defensive because Claude may return the decomposition in
several shapes depending on whether --json-schema produced structured_output,
whether the model wrapped its JSON in a ```json``` fence, or whether only a
free-form text response is available.
"""

from __future__ import annotations

import json
import re
from typing import Any


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?```\s*$")


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    return _FENCE_RE.sub("", stripped).strip()


def _find_json_object(text: str, required_key: str = "action") -> dict | None:
    """Walk the string looking for a balanced JSON object that contains required_key."""
    for match in re.finditer(r"\{", text):
        start = match.start()
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict) and required_key in parsed:
                        return parsed
                    break
    return None


def extract_step_result(output: dict[str, Any]) -> dict | None:
    """Return the structured step result from Claude's JSON output, or None.

    Tries, in order:
      1. output['structured_output'] / ['result'] / ['content'] as a dict with 'action'
      2. the same values as strings, after stripping ```json``` fences, parsed with json.loads
      3. bracket-walking over each string value for a balanced {...} containing 'action'
    """
    for key in ("structured_output", "result", "content"):
        candidate = output.get(key)
        if candidate is None:
            continue
        if isinstance(candidate, dict) and "action" in candidate:
            return candidate
        if isinstance(candidate, str):
            cleaned = _strip_code_fences(candidate)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and "action" in parsed:
                return parsed
            found = _find_json_object(cleaned)
            if found is not None:
                return found

    return None
