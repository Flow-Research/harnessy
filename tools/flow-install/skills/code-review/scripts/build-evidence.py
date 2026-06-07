#!/usr/bin/env python3
"""Build a Harnessy Code Review evidence bundle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id() -> str:
    return "cr_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--validation-result", choices=["pass", "fail"], default="pass")
    parser.add_argument("--provider", default="codex")
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--capability-version", default="0.3.0")
    parser.add_argument("--ci-provider", default="local")
    parser.add_argument("--ci-run-id", default="")
    parser.add_argument("--gate-result", choices=["pass", "fail"], default="pass")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-root", default=".jarvis/context/evidence/code-review")
    parser.add_argument("--markdown-report", default=None)
    parser.add_argument("--sarif-report", default=None)
    parser.add_argument("--print-path", action="store_true")
    args = parser.parse_args()

    discovery = read_json(args.discovery)
    review = read_json(args.review)
    run_id = args.run_id or default_run_id()
    verifier = review.get("verification", {})
    verifier_result = "pass" if verifier.get("blocking_findings_verified") and verifier.get("citations_valid") else "fail"

    evidence = {
        "schema_version": 1,
        "run_id": run_id,
        "capability_id": "harnessy.code_review",
        "capability_version": args.capability_version,
        "provider": args.provider,
        "adapter": args.adapter,
        "mode": review.get("mode", "ai_review"),
        "review_status": review.get("review_status", "completed"),
        "skipped_reason": review.get("skipped_reason"),
        "ci_provider": args.ci_provider,
        "ci_run_id": args.ci_run_id,
        "base_ref": discovery.get("base_ref", ""),
        "head_ref": discovery.get("head_ref", ""),
        "changed_file_count": len(discovery.get("files", [])),
        "risk_surfaces": discovery.get("risk_surfaces", []),
        "commands_run": discovery.get("commands", []),
        "output_schema_result": args.validation_result,
        "verifier_result": verifier_result,
        "gate_result": args.gate_result,
        "verdict": review.get("verdict", ""),
        "artifacts": {
            "discovery": args.discovery,
            "review_json": args.review,
            "markdown_report": args.markdown_report or str(Path(args.review).with_name("REVIEW_REPORT.md")),
            "sarif_report": args.sarif_report or "",
        },
        "generated_at": now_iso(),
    }

    output_dir = Path(args.output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "evidence.json"
    output_path.write_text(json.dumps(evidence, indent=2) + "\n")

    if args.print_path:
        print(output_path)
    else:
        print(json.dumps({"ok": True, "path": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
