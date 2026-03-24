#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
from pathlib import Path


def as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"Expected dict, got {type(value).__name__}")
    return value


def as_list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def as_list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def run_command(command: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        command,
        shell=True,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def check_system_package(name: str, package_manager: str) -> tuple[bool, str]:
    if package_manager == "apk":
        code, _, stderr = run_command(f"apk info -e {name}")
    elif package_manager == "apt":
        code, _, stderr = run_command(f"dpkg -s {name}")
    else:
        return False, f"unsupported package manager in validator: {package_manager}"
    if code == 0:
        return True, f"package installed: {name}"
    return False, stderr or f"missing package: {name}"


def check_binary(entry: dict[str, object]) -> tuple[bool, str]:
    name = str(entry["name"])
    binary_path = shutil.which(name)
    if not binary_path:
        return False, f"binary not found in PATH: {name}"
    version_command = entry.get("version_command")
    expect_regex = entry.get("expect_regex")
    if version_command:
        code, stdout, stderr = run_command(str(version_command))
        output = stdout or stderr
        if code != 0:
            return False, f"version command failed for {name}: {output}"
        if expect_regex and not re.search(str(expect_regex), output):
            return False, f"version output mismatch for {name}: {output}"
    return True, f"binary available: {name} -> {binary_path}"


def check_env(entry: dict[str, object]) -> tuple[bool, str]:
    name = str(entry["name"])
    value = os.environ.get(name)
    required = bool(entry.get("required", True))
    if value is None:
        if required:
            return False, f"missing env var: {name}"
        return True, f"optional env var absent: {name}"
    if "equals" in entry and value != str(entry["equals"]):
        return False, f"env var mismatch for {name}: expected {entry['equals']!r}, got {value!r}"
    if "regex" in entry and not re.search(str(entry["regex"]), value):
        return False, f"env var regex mismatch for {name}: {value!r}"
    return True, f"env var ok: {name}"


def check_path(entry: dict[str, object]) -> tuple[bool, str]:
    raw_path = Path(str(entry["path"]))
    required = bool(entry.get("required", True))
    path_type = str(entry.get("type", "exists"))
    exists = raw_path.exists()
    if not exists and not required:
        return True, f"optional path absent: {raw_path}"
    if not exists:
        return False, f"missing path: {raw_path}"
    if path_type == "dir" and not raw_path.is_dir():
        return False, f"expected directory: {raw_path}"
    if path_type == "file" and not raw_path.is_file():
        return False, f"expected file: {raw_path}"
    return True, f"path ok: {raw_path}"


def check_command(entry: dict[str, object]) -> tuple[bool, str]:
    name = str(entry.get("name", entry["run"]))
    command = str(entry["run"])
    expected_exit = int(str(entry.get("expect_exit_code", 0)))
    code, stdout, stderr = run_command(command)
    output = stdout or stderr
    if code != expected_exit:
        return False, f"command failed [{name}]: exit={code}, output={output}"
    expect_regex = entry.get("expect_regex")
    if expect_regex and not re.search(str(expect_regex), output):
        return False, f"command output mismatch [{name}]: {output}"
    return True, f"command ok [{name}]"


def check_user(entry: dict[str, object]) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    user_info = pwd.getpwuid(os.getuid())
    if "name" in entry:
        expected_name = str(entry["name"])
        results.append((user_info.pw_name == expected_name, f"current user is {user_info.pw_name}" if user_info.pw_name == expected_name else f"user mismatch: expected {expected_name}, got {user_info.pw_name}"))
    if "uid" in entry:
        expected_uid = int(str(entry["uid"]))
        results.append((os.getuid() == expected_uid, f"uid is {os.getuid()}" if os.getuid() == expected_uid else f"uid mismatch: expected {expected_uid}, got {os.getuid()}"))
    if "gid" in entry:
        expected_gid = int(str(entry["gid"]))
        results.append((os.getgid() == expected_gid, f"gid is {os.getgid()}" if os.getgid() == expected_gid else f"gid mismatch: expected {expected_gid}, got {os.getgid()}"))
    for group in as_list_of_strings(entry.get("groups_contains", [])):
        _, stdout, stderr = run_command("id -nG")
        groups = set((stdout or stderr).split())
        results.append((group in groups, f"group present: {group}" if group in groups else f"missing group: {group}"))
    return results


def evaluate(spec: dict[str, object]) -> dict[str, object]:
    build = as_dict(spec.get("build", {}))
    checks = as_dict(spec.get("checks", {}))
    package_manager = str(build.get("package_manager", "apt"))
    results: list[dict[str, object]] = []

    for package in as_list_of_strings(checks.get("system_packages", [])):
        ok, message = check_system_package(package, package_manager)
        results.append({"ok": ok, "message": message, "kind": "system_package"})

    for entry in as_list_of_dicts(checks.get("binaries", [])):
        ok, message = check_binary(entry)
        results.append({"ok": ok, "message": message, "kind": "binary"})

    for entry in as_list_of_dicts(checks.get("env", [])):
        ok, message = check_env(entry)
        results.append({"ok": ok, "message": message, "kind": "env"})

    for entry in as_list_of_dicts(checks.get("paths", [])):
        ok, message = check_path(entry)
        results.append({"ok": ok, "message": message, "kind": "path"})

    for entry in as_list_of_dicts(checks.get("commands", [])):
        ok, message = check_command(entry)
        results.append({"ok": ok, "message": message, "kind": "command"})

    user_spec = spec.get("user")
    if isinstance(user_spec, dict):
        for ok, message in check_user(user_spec):
            results.append({"ok": ok, "message": message, "kind": "user"})

    failures = [result for result in results if not result["ok"]]
    return {
        "name": spec.get("name", "dev-baseline"),
        "passed": not failures,
        "results": results,
        "failure_count": len(failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate container state against a JSON spec")
    parser.add_argument("--spec", required=True, help="Path to the validation spec JSON")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"Missing spec file: {spec_path}", file=sys.stderr)
        return 1

    with spec_path.open("r", encoding="utf8") as handle:
        spec = as_dict(json.load(handle))

    summary = evaluate(spec)
    summary_results = as_list_of_dicts(summary.get("results", []))
    passed = bool(summary.get("passed", False))
    failure_count = int(str(summary.get("failure_count", 0)))

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for result in summary_results:
            prefix = "PASS" if bool(result.get("ok", False)) else "FAIL"
            print(f"{prefix} {result.get('kind', 'check')}: {result.get('message', '')}")
        if passed:
            print("\nContainer validation passed.")
        else:
            print(f"\nContainer validation failed with {failure_count} issue(s).", file=sys.stderr)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
