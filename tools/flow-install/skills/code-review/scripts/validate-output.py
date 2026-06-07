#!/usr/bin/env python3
"""Validate Harnessy Code Review output JSON and verdict policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


VALID_VERDICTS = {"approve", "comment", "request_changes"}
VALID_SEVERITIES = {"critical", "major", "minor", "suggestion"}
BLOCKING_SEVERITIES = {"critical", "major"}
VALID_MODES = {"ai_review", "deterministic_only"}
VALID_REVIEW_STATUSES = {"completed", "skipped"}
REQUIRED_ROOT = {"schema_version", "verdict", "summary", "findings", "tests_reviewed", "missing_tests", "verification"}
REQUIRED_FINDING = {"id", "severity", "category", "file", "line", "title", "evidence", "risk", "recommended_fix"}


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["output must be a JSON object"]

    missing = sorted(REQUIRED_ROOT - set(data))
    for field in missing:
        errors.append(f"missing root field: {field}")

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    verdict = data.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append("verdict must be approve, comment, or request_changes")

    mode = data.get("mode")
    if mode is not None and mode not in VALID_MODES:
        errors.append("mode must be ai_review or deterministic_only")

    review_status = data.get("review_status")
    if review_status is not None and review_status not in VALID_REVIEW_STATUSES:
        errors.append("review_status must be completed or skipped")

    if review_status == "skipped" and not non_empty_string(data.get("skipped_reason")):
        errors.append("skipped_reason is required when review_status is skipped")

    if not non_empty_string(data.get("summary")):
        errors.append("summary must be a non-empty string")

    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []

    for index, finding in enumerate(findings):
        prefix = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing_finding = sorted(REQUIRED_FINDING - set(finding))
        for field in missing_finding:
            errors.append(f"{prefix} missing field: {field}")

        severity = finding.get("severity")
        if severity not in VALID_SEVERITIES:
            errors.append(f"{prefix}.severity must be one of {sorted(VALID_SEVERITIES)}")

        for field in ["id", "category", "title", "evidence", "risk", "recommended_fix"]:
            if not non_empty_string(finding.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")

        if severity in BLOCKING_SEVERITIES:
            if not non_empty_string(finding.get("file")):
                errors.append(f"{prefix}.file is required for blocking findings")
            line = finding.get("line")
            if isinstance(line, int):
                if line < 1:
                    errors.append(f"{prefix}.line must be positive")
            elif not non_empty_string(line):
                errors.append(f"{prefix}.line is required for blocking findings")

    for field in ["tests_reviewed", "missing_tests"]:
        value = data.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{field} must be an array of strings")

    verification = data.get("verification")
    if not isinstance(verification, dict):
        errors.append("verification must be an object")
    else:
        for field in ["schema_valid", "citations_valid", "blocking_findings_verified"]:
            if not isinstance(verification.get(field), bool):
                errors.append(f"verification.{field} must be a boolean")

    blocking_count = sum(1 for finding in findings if isinstance(finding, dict) and finding.get("severity") in BLOCKING_SEVERITIES)
    if blocking_count > 0 and verdict != "request_changes":
        errors.append("verdict must be request_changes when critical or major findings exist")
    if blocking_count == 0 and findings and verdict != "comment":
        errors.append("verdict must be comment when only non-blocking findings exist")
    if not findings and verdict != "approve":
        errors.append("verdict must be approve when there are no findings")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_json")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation result")
    args = parser.parse_args()

    try:
        data = json.loads(Path(args.review_json).read_text())
    except Exception as exc:
        errors = [f"could not read JSON: {exc}"]
    else:
        errors = validate(data)

    result = {"ok": not errors, "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        print("Code review output validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    else:
        print("Code review output validation passed.")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
