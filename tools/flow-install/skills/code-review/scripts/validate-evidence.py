#!/usr/bin/env python3
"""Validate a Harnessy Code Review evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_VERDICTS = {"approve", "comment", "request_changes"}
VALID_SEVERITIES = {"critical", "major", "minor", "suggestion"}
BLOCKING_SEVERITIES = {"critical", "major"}
VALID_MODES = {"ai_review", "deterministic_only"}
VALID_REVIEW_STATUSES = {"completed", "skipped"}
VALID_RESULTS = {"pass", "fail"}
VALID_VERIFIER_RESULTS = {"pass", "fail", "not_run"}
REQUIRED_ROOT = {
    "schema_version",
    "run_id",
    "capability_id",
    "capability_version",
    "provider",
    "mode",
    "review_status",
    "ci_provider",
    "base_ref",
    "head_ref",
    "changed_file_count",
    "risk_surfaces",
    "commands_run",
    "output_schema_result",
    "verifier_result",
    "gate_result",
    "verdict",
    "artifacts",
    "generated_at",
}
ALLOWED_ROOT = REQUIRED_ROOT | {"adapter", "skipped_reason", "ci_run_id"}
REQUIRED_ARTIFACTS = {"discovery", "review_json"}


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "JSON must be an object"
    return payload, None


def resolve_artifact_path(raw: str, evidence_path: Path, repo_root: Path) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    cwd_candidate = repo_root / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    sibling_candidate = evidence_path.parent / candidate
    if sibling_candidate.exists():
        return sibling_candidate
    return cwd_candidate


def parse_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def blocking_count(review: dict[str, Any]) -> int:
    findings = review.get("findings", [])
    if not isinstance(findings, list):
        return 0
    return sum(1 for finding in findings if isinstance(finding, dict) and finding.get("severity") in BLOCKING_SEVERITIES)


def validate_review_cross_checks(review: dict[str, Any], errors: list[str]) -> None:
    verdict = review.get("verdict")
    findings = review.get("findings", [])
    if verdict not in VALID_VERDICTS:
        errors.append("review.verdict must be approve, comment, or request_changes")
    if not isinstance(findings, list):
        errors.append("review.findings must be an array")
        findings = []

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"review.findings[{index}] must be an object")
            continue
        severity = finding.get("severity")
        if severity not in VALID_SEVERITIES:
            errors.append(f"review.findings[{index}].severity is invalid")
        if severity in BLOCKING_SEVERITIES:
            if not non_empty_string(finding.get("file")):
                errors.append(f"review.findings[{index}].file is required for blocking findings")
            line = finding.get("line")
            if not (isinstance(line, int) and line > 0) and not non_empty_string(line):
                errors.append(f"review.findings[{index}].line is required for blocking findings")

    blockers = blocking_count(review)
    if blockers > 0 and verdict != "request_changes":
        errors.append("review.verdict must be request_changes when critical or major findings exist")
    if blockers == 0 and findings and verdict != "comment":
        errors.append("review.verdict must be comment when only non-blocking findings exist")
    if not findings and verdict != "approve":
        errors.append("review.verdict must be approve when there are no findings")


def validate_evidence(evidence_path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    evidence, read_error = read_json(evidence_path)
    if read_error:
        return [f"could not read evidence JSON: {read_error}"]
    assert evidence is not None

    missing = sorted(REQUIRED_ROOT - set(evidence))
    for field in missing:
        errors.append(f"missing root field: {field}")
    unknown = sorted(set(evidence) - ALLOWED_ROOT)
    for field in unknown:
        errors.append(f"unknown root field: {field}")

    if evidence.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if evidence.get("capability_id") != "harnessy.code_review":
        errors.append("capability_id must be harnessy.code_review")

    for field in ["run_id", "capability_version", "provider", "ci_provider", "base_ref", "head_ref"]:
        if not non_empty_string(evidence.get(field)):
            errors.append(f"{field} must be a non-empty string")

    if evidence.get("mode") not in VALID_MODES:
        errors.append("mode must be ai_review or deterministic_only")
    if evidence.get("review_status") not in VALID_REVIEW_STATUSES:
        errors.append("review_status must be completed or skipped")
    if evidence.get("review_status") == "skipped":
        if not non_empty_string(evidence.get("skipped_reason")):
            errors.append("skipped_reason is required when review_status is skipped")
        if evidence.get("mode") != "deterministic_only":
            errors.append("skipped reviews must use mode deterministic_only")

    if not isinstance(evidence.get("changed_file_count"), int) or evidence.get("changed_file_count") < 0:
        errors.append("changed_file_count must be a non-negative integer")
    if not string_list(evidence.get("risk_surfaces")):
        errors.append("risk_surfaces must be an array of strings")
    if not string_list(evidence.get("commands_run")):
        errors.append("commands_run must be an array of strings")
    if evidence.get("output_schema_result") not in VALID_RESULTS:
        errors.append("output_schema_result must be pass or fail")
    if evidence.get("verifier_result") not in VALID_VERIFIER_RESULTS:
        errors.append("verifier_result must be pass, fail, or not_run")
    if evidence.get("gate_result") not in VALID_RESULTS:
        errors.append("gate_result must be pass or fail")
    if evidence.get("verdict") not in VALID_VERDICTS:
        errors.append("verdict must be approve, comment, or request_changes")
    if not parse_iso_datetime(evidence.get("generated_at")):
        errors.append("generated_at must be an ISO datetime")

    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
        artifacts = {}
    else:
        for key in sorted(REQUIRED_ARTIFACTS - set(artifacts)):
            errors.append(f"artifacts.{key} is required")
        for key, raw in artifacts.items():
            if not isinstance(raw, str):
                errors.append(f"artifacts.{key} must be a string")
                continue
            if not raw:
                continue
            resolved = resolve_artifact_path(raw, evidence_path, repo_root)
            if not resolved.exists():
                errors.append(f"artifacts.{key} does not exist: {raw}")

    discovery_path_raw = artifacts.get("discovery") if isinstance(artifacts.get("discovery"), str) else ""
    review_path_raw = artifacts.get("review_json") if isinstance(artifacts.get("review_json"), str) else ""
    discovery: dict[str, Any] | None = None
    review: dict[str, Any] | None = None

    if discovery_path_raw:
        discovery_path = resolve_artifact_path(discovery_path_raw, evidence_path, repo_root)
        if discovery_path.exists():
            discovery, discovery_error = read_json(discovery_path)
            if discovery_error:
                errors.append(f"could not read artifacts.discovery JSON: {discovery_error}")

    if review_path_raw:
        review_path = resolve_artifact_path(review_path_raw, evidence_path, repo_root)
        if review_path.exists():
            review, review_error = read_json(review_path)
            if review_error:
                errors.append(f"could not read artifacts.review_json JSON: {review_error}")

    if discovery:
        files = discovery.get("files", [])
        if not isinstance(files, list):
            errors.append("discovery.files must be an array")
            files = []
        if evidence.get("base_ref") != discovery.get("base_ref"):
            errors.append("base_ref does not match discovery.base_ref")
        if evidence.get("head_ref") != discovery.get("head_ref"):
            errors.append("head_ref does not match discovery.head_ref")
        if evidence.get("changed_file_count") != len(files):
            errors.append("changed_file_count does not match discovery.files length")
        if evidence.get("risk_surfaces") != discovery.get("risk_surfaces", []):
            errors.append("risk_surfaces does not match discovery.risk_surfaces")
        if evidence.get("commands_run") != discovery.get("commands", []):
            errors.append("commands_run does not match discovery.commands")

    if review:
        validate_review_cross_checks(review, errors)
        verification = review.get("verification", {})
        if not isinstance(verification, dict):
            errors.append("review.verification must be an object")
            verification = {}
        computed_verifier_result = "pass" if verification.get("blocking_findings_verified") and verification.get("citations_valid") else "fail"
        if evidence.get("verifier_result") != computed_verifier_result:
            errors.append("verifier_result does not match review.verification")
        for field in ["mode", "review_status", "skipped_reason", "verdict"]:
            if evidence.get(field) != review.get(field):
                if field == "skipped_reason" and evidence.get(field) is None and review.get(field) is None:
                    continue
                errors.append(f"{field} does not match review.{field}")
        if blocking_count(review) > 0 and evidence.get("gate_result") != "fail":
            errors.append("gate_result must be fail when review has critical or major findings")
        if evidence.get("gate_result") == "pass":
            if evidence.get("output_schema_result") != "pass":
                errors.append("passing gate requires output_schema_result pass")
            if evidence.get("verifier_result") != "pass":
                errors.append("passing gate requires verifier_result pass")
            if blocking_count(review) > 0:
                errors.append("passing gate cannot include critical or major findings")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation result")
    args = parser.parse_args()

    errors = validate_evidence(Path(args.evidence_json), Path(args.repo_root).resolve())
    result = {"ok": not errors, "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        print("Code review evidence validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    else:
        print("Code review evidence validation passed.")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
