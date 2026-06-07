#!/usr/bin/env python3
"""Emit deterministic changed-file inventory for a local Code Review run."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def parse_shortstat(text: str) -> dict[str, int]:
    summary = {"files_changed": 0, "additions": 0, "deletions": 0}
    match = re.search(r"(\d+) files? changed", text)
    if match:
        summary["files_changed"] = int(match.group(1))
    match = re.search(r"(\d+) insertions?\(\+\)", text)
    if match:
        summary["additions"] = int(match.group(1))
    match = re.search(r"(\d+) deletions?\(-\)", text)
    if match:
        summary["deletions"] = int(match.group(1))
    return summary


def parse_numstat(text: str) -> dict[str, dict[str, int | None]]:
    stats: dict[str, dict[str, int | None]] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        additions_raw, deletions_raw, file_path = parts[0], parts[1], parts[-1]
        additions = None if additions_raw == "-" else int(additions_raw)
        deletions = None if deletions_raw == "-" else int(deletions_raw)
        stats[file_path] = {"additions": additions, "deletions": deletions}
    return stats


def cluster_for_path(file_path: str) -> str:
    p = file_path.lower()
    name = Path(file_path).name.lower()
    if p.startswith(".github/workflows/") or "deploy" in p or "hostinger" in p or "systemd" in p or name in {"dockerfile", "docker-compose.yml", "compose.yml"}:
        return "runtime-deploy"
    if "/tests/" in p or p.startswith("tests/") or p.startswith("qa/") or "playwright" in p or re.search(r"(^|[._-])test(s)?[._-]", name):
        return "qa-tests"
    if p.startswith("tools/flow-install/skills/") or p.startswith(".agents/skills/") or name in {"skill.md", "manifest.yaml"}:
        return "skills"
    if p.startswith("scripts/") or p.endswith(".sh") or "/scripts/" in p:
        return "cli-scripts"
    if p.startswith(".jarvis/context/profiles/") or name in {"package.json", "pnpm-lock.yaml", "package-lock.json", "pyproject.toml", "requirements.txt"}:
        return "config-profiles"
    if p.endswith(".md") or p.startswith(".jarvis/context/") or name == "agents.md":
        return "docs-context"
    return "source-code"


def risk_surfaces(files: list[dict[str, Any]]) -> list[str]:
    risks: set[str] = set()
    for item in files:
        p = item["path"].lower()
        cluster = item["cluster"]
        if cluster == "runtime-deploy":
            risks.add("deployment")
        if cluster == "qa-tests":
            risks.add("qa")
        if cluster == "skills":
            risks.add("skill-packaging")
        if cluster == "cli-scripts" or p.endswith(".sh"):
            risks.add("shell-execution")
        if ".github/workflows/" in p or "ci" in p:
            risks.add("ci")
        if any(token in p for token in ["auth", "secret", "token", "permission", "sandbox", "policy"]):
            risks.add("security-policy")
        if any(Path(p).name == name for name in ["package.json", "pnpm-lock.yaml", "package-lock.json", "pyproject.toml", "requirements.txt"]):
            risks.add("dependency")
    return sorted(risks)


def discover(base: str, head: str) -> dict[str, Any]:
    rev_range = f"{base}...{head}"
    commands = [
        f"git diff --name-status -M {rev_range}",
        f"git diff --numstat -M {rev_range}",
        f"git diff --shortstat {rev_range}",
    ]
    name_status = run_git(["diff", "--name-status", "-M", rev_range])
    numstat = parse_numstat(run_git(["diff", "--numstat", "-M", rev_range]))
    shortstat_text = run_git(["diff", "--shortstat", rev_range])

    files: list[dict[str, Any]] = []
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        old_path = None
        file_path = parts[-1]
        if status.startswith("R") and len(parts) >= 3:
            old_path = parts[1]
        file_stats = numstat.get(file_path, {"additions": None, "deletions": None})
        files.append(
            {
                "path": file_path,
                "old_path": old_path,
                "status": status,
                "additions": file_stats["additions"],
                "deletions": file_stats["deletions"],
                "cluster": cluster_for_path(file_path),
            }
        )

    summary = parse_shortstat(shortstat_text)
    if not summary["files_changed"]:
        summary["files_changed"] = len(files)

    return {
        "schema_version": 1,
        "source_type": "local_diff",
        "base_ref": base,
        "head_ref": head,
        "range": rev_range,
        "generated_at": now_iso(),
        "summary": summary,
        "files": files,
        "risk_surfaces": risk_surfaces(files),
        "commands": commands,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        data = discover(args.base, args.head)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    text = json.dumps(data, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
