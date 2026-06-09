"""Text hygiene checks for AI-generated human-readable content."""

from __future__ import annotations

import fnmatch
import getpass
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import click
import yaml
from rich.console import Console
from rich.table import Table

RuleKind = Literal["phrase", "regex"]
RuleAction = Literal["clean", "flag"]

DEFAULT_PATTERN_CONFIG: dict[str, Any] = {
    "version": 1,
    "defaults": {
        "file_globs": [
            "*.md",
            "**/*.md",
            "*.mdx",
            "**/*.mdx",
            "*.txt",
            "**/*.txt",
            "README",
            "README.*",
            "**/README",
            "**/README.*",
        ],
        "exclude_globs": [
            ".git/**",
            "**/.git/**",
            "node_modules/**",
            "**/node_modules/**",
            ".venv/**",
            "**/.venv/**",
            "__pycache__/**",
            "**/__pycache__/**",
        ],
    },
    "rules": [
        {
            "id": "excited-to-announce",
            "kind": "phrase",
            "pattern": "We are excited to announce",
            "flags": ["i"],
            "note": "Launch-post cliche.",
        },
        {
            "id": "revolutionary",
            "kind": "regex",
            "pattern": r"\brevolutionary\b",
            "flags": ["i"],
            "note": "Generic AI/product hype.",
        },
        {
            "id": "game-changing",
            "kind": "regex",
            "pattern": r"\bgame-changing\b",
            "flags": ["i"],
            "note": "Generic AI/product hype.",
        },
        {
            "id": "unlocking",
            "kind": "regex",
            "pattern": r"\bunlock(?:s|ed|ing)?\b",
            "flags": ["i"],
            "note": "Common AI/consulting phrasing.",
        },
        {
            "id": "at-scale",
            "kind": "phrase",
            "pattern": "at scale",
            "flags": ["i"],
            "note": "Often vague unless tied to a concrete scale target.",
        },
    ],
}

console = Console()


@dataclass(frozen=True)
class HygieneRule:
    """One phrase or regex pattern to flag and clean."""

    id: str
    kind: RuleKind
    pattern: str
    replacement: str = ""
    flags: tuple[str, ...] = ()
    note: str | None = None
    action: RuleAction = "clean"

    def compiled(self) -> re.Pattern[str]:
        """Compile this rule into a regex pattern."""
        pattern = re.escape(self.pattern) if self.kind == "phrase" else self.pattern
        return re.compile(pattern, _regex_flags(self.flags))


@dataclass(frozen=True)
class HygieneConfig:
    """Resolved text hygiene configuration."""

    rules: tuple[HygieneRule, ...]
    file_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    config_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class HygieneFinding:
    """One matched pattern in one file."""

    path: Path
    line: int
    rule_id: str
    match: str
    replacement: str
    note: str | None = None
    action: RuleAction = "clean"

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "path": self.path.as_posix(),
            "line": self.line,
            "rule_id": self.rule_id,
            "match": self.match,
            "replacement": self.replacement,
            "note": self.note,
            "action": self.action,
        }


@dataclass(frozen=True)
class HygieneRunResult:
    """Result of checking or cleaning one or more files."""

    files_checked: tuple[Path, ...]
    changed_files: tuple[Path, ...]
    findings: tuple[HygieneFinding, ...]
    config_paths: tuple[Path, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "files_checked": [path.as_posix() for path in self.files_checked],
            "changed_files": [path.as_posix() for path in self.changed_files],
            "findings": [finding.as_dict() for finding in self.findings],
            "config_paths": [path.as_posix() for path in self.config_paths],
            "summary": {
                "files_checked": len(self.files_checked),
                "files_changed": len(self.changed_files),
                "matches": len(self.findings),
            },
        }


def load_hygiene_config(
    config_path: Path | None = None,
    *,
    cwd: Path | None = None,
) -> HygieneConfig:
    """Load default, project, and optional user text hygiene rules."""
    raw_configs = [DEFAULT_PATTERN_CONFIG]
    config_paths: list[Path] = []

    for candidate in _candidate_config_paths(config_path=config_path, cwd=cwd):
        if not candidate.exists():
            continue
        loaded = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"text hygiene config must be a mapping: {candidate}")
        raw_configs.append(loaded)
        config_paths.append(candidate)

    file_globs = tuple(DEFAULT_PATTERN_CONFIG["defaults"]["file_globs"])
    exclude_globs = tuple(DEFAULT_PATTERN_CONFIG["defaults"]["exclude_globs"])
    rules_by_id: dict[str, HygieneRule] = {}

    for raw in raw_configs:
        defaults = raw.get("defaults", {})
        if isinstance(defaults, dict):
            raw_file_globs = defaults.get("file_globs")
            raw_exclude_globs = defaults.get("exclude_globs")
            if isinstance(raw_file_globs, list):
                file_globs = tuple(str(item) for item in raw_file_globs)
            if isinstance(raw_exclude_globs, list):
                exclude_globs = tuple(str(item) for item in raw_exclude_globs)

        raw_rules = raw.get("rules", [])
        if not isinstance(raw_rules, list):
            raise ValueError("text hygiene config `rules` must be a list")

        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict):
                raise ValueError("each text hygiene rule must be a mapping")
            rule_id = str(raw_rule.get("id", "")).strip()
            if not rule_id:
                raise ValueError("each text hygiene rule needs an id")
            if raw_rule.get("enabled", True) is False:
                rules_by_id.pop(rule_id, None)
                continue
            rules_by_id[rule_id] = _parse_rule(raw_rule)

    return HygieneConfig(
        rules=tuple(rules_by_id.values()),
        file_globs=file_globs,
        exclude_globs=exclude_globs,
        config_paths=tuple(config_paths),
    )


def check_paths(
    paths: list[Path],
    *,
    config_path: Path | None = None,
    cwd: Path | None = None,
) -> HygieneRunResult:
    """Check paths for configured AI-speak patterns without writing files."""
    config = load_hygiene_config(config_path=config_path, cwd=cwd)
    return _run_paths(paths, config=config, write=False)


def clean_paths(
    paths: list[Path],
    *,
    config_path: Path | None = None,
    cwd: Path | None = None,
) -> HygieneRunResult:
    """Clean configured AI-speak patterns from paths in place."""
    config = load_hygiene_config(config_path=config_path, cwd=cwd)
    return _run_paths(paths, config=config, write=True)


def process_text(
    text: str,
    rules: tuple[HygieneRule, ...],
    *,
    path: Path,
    write: bool,
) -> tuple[str, tuple[HygieneFinding, ...]]:
    """Check or clean text while skipping frontmatter and Markdown code spans."""
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    findings: list[HygieneFinding] = []
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    fence_marker: str | None = None

    for index, line in enumerate(lines):
        line_no = index + 1
        stripped = line.lstrip()

        if in_frontmatter:
            new_lines.append(line)
            if line_no > 1 and line.strip() in {"---", "..."}:
                in_frontmatter = False
            continue

        if fence_marker is not None:
            new_lines.append(line)
            if stripped.startswith(fence_marker):
                fence_marker = None
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence_marker = stripped[:3]
            new_lines.append(line)
            continue

        updated_line, line_findings = _process_line(
            line,
            rules,
            path=path,
            line_no=line_no,
            write=write,
        )
        new_lines.append(updated_line)
        findings.extend(line_findings)

    return "".join(new_lines), tuple(findings)


def format_report(result: HygieneRunResult) -> str:
    """Format a compact text report for command output."""
    if not result.findings:
        return f"Text hygiene passed: checked {len(result.files_checked)} file(s)."

    by_rule: dict[str, int] = {}
    for finding in result.findings:
        by_rule[finding.rule_id] = by_rule.get(finding.rule_id, 0) + 1
    rule_summary = ", ".join(f"{rule_id}={count}" for rule_id, count in sorted(by_rule.items()))
    changed = f", changed {len(result.changed_files)} file(s)" if result.changed_files else ""
    return (
        f"Text hygiene found {len(result.findings)} match(es) in "
        f"{len(result.files_checked)} file(s){changed}: {rule_summary}"
    )


@click.group(name="text-hygiene")
def text_hygiene_cli() -> None:
    """Check and clean AI-speak patterns from generated text."""


@text_hygiene_cli.command(name="check")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Pattern registry YAML to load after built-in defaults.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the report as JSON.")
def check_command(paths: tuple[str, ...], config_path: Path | None, as_json: bool) -> None:
    """Report configured AI-speak patterns without changing files."""
    result = _invoke_paths(paths, config_path=config_path, write=False)
    _emit_result(result, as_json=as_json)
    if result.findings:
        raise SystemExit(1)


@text_hygiene_cli.command(name="clean")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Pattern registry YAML to load after built-in defaults.",
)
@click.option("--report/--no-report", default=True, help="Print a cleanup report.")
@click.option("--json", "as_json", is_flag=True, help="Emit the report as JSON.")
def clean_command(
    paths: tuple[str, ...],
    config_path: Path | None,
    report: bool,
    as_json: bool,
) -> None:
    """Remove configured AI-speak patterns from files in place."""
    result = _invoke_paths(paths, config_path=config_path, write=True)
    if report or as_json:
        _emit_result(result, as_json=as_json)


def _invoke_paths(
    paths: tuple[str, ...],
    *,
    config_path: Path | None,
    write: bool,
) -> HygieneRunResult:
    try:
        resolved = [Path(path).expanduser() for path in paths]
        if write:
            return clean_paths(resolved, config_path=config_path)
        return check_paths(resolved, config_path=config_path)
    except (OSError, ValueError, re.error) as exc:
        raise click.ClickException(str(exc)) from exc


def _emit_result(result: HygieneRunResult, *, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(result.as_dict(), indent=2))
        return

    console.print(format_report(result))
    if not result.findings:
        return

    table = Table("File", "Line", "Rule", "Match", title="Text Hygiene Findings")
    for finding in result.findings[:50]:
        table.add_row(
            finding.path.as_posix(),
            str(finding.line),
            finding.rule_id,
            finding.match,
        )
    console.print(table)
    if len(result.findings) > 50:
        console.print(f"[dim]...and {len(result.findings) - 50} more finding(s).[/dim]")


def _run_paths(paths: list[Path], *, config: HygieneConfig, write: bool) -> HygieneRunResult:
    files = _discover_files(paths, config)
    findings: list[HygieneFinding] = []
    changed_files: list[Path] = []

    for path in files:
        original = path.read_text(encoding="utf-8")
        updated, file_findings = process_text(original, config.rules, path=path, write=write)
        findings.extend(file_findings)
        if write and updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files.append(path)

    return HygieneRunResult(
        files_checked=tuple(files),
        changed_files=tuple(changed_files),
        findings=tuple(findings),
        config_paths=config.config_paths,
    )


def _discover_files(paths: list[Path], config: HygieneConfig) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            if _included(path, path.name, config):
                files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            rel = child.relative_to(path).as_posix()
            if _included(child, rel, config):
                files.append(child)
    return tuple(dict.fromkeys(files))


def _included(path: Path, relpath: str, config: HygieneConfig) -> bool:
    rel = relpath.replace(os.sep, "/")
    name = path.name
    if any(
        fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern)
        for pattern in config.exclude_globs
    ):
        return False
    return any(
        fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern)
        for pattern in config.file_globs
    )


def _process_line(
    line: str,
    rules: tuple[HygieneRule, ...],
    *,
    path: Path,
    line_no: int,
    write: bool,
) -> tuple[str, list[HygieneFinding]]:
    spans = _editable_spans(line)
    if not spans:
        return line, []

    parts: list[str] = []
    findings: list[HygieneFinding] = []
    cursor = 0
    for start, end in spans:
        parts.append(line[cursor:start])
        segment, segment_findings = _process_segment(
            line[start:end],
            rules,
            path=path,
            line_no=line_no,
            write=write,
        )
        parts.append(segment)
        findings.extend(segment_findings)
        cursor = end
    parts.append(line[cursor:])
    return "".join(parts), findings


def _process_segment(
    segment: str,
    rules: tuple[HygieneRule, ...],
    *,
    path: Path,
    line_no: int,
    write: bool,
) -> tuple[str, list[HygieneFinding]]:
    updated = segment
    findings: list[HygieneFinding] = []
    changed = False
    for rule in rules:
        pattern = rule.compiled()
        if write and rule.action == "clean":

            def replace(match: re.Match[str]) -> str:
                findings.append(_finding(path, line_no, rule, match.group(0)))
                return rule.replacement

            updated, count = pattern.subn(replace, updated)
            changed = changed or count > 0
        else:
            findings.extend(
                _finding(path, line_no, rule, match.group(0))
                for match in pattern.finditer(updated)
            )

    if write and changed:
        updated = _normalize_spacing(updated)
    return updated, findings


def _finding(path: Path, line_no: int, rule: HygieneRule, match: str) -> HygieneFinding:
    return HygieneFinding(
        path=path,
        line=line_no,
        rule_id=rule.id,
        match=match,
        replacement=rule.replacement,
        note=rule.note,
        action=rule.action,
    )


def _editable_spans(line: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    start = 0
    in_code = False
    index = 0
    while index < len(line):
        if line[index] != "`":
            index += 1
            continue
        marker_end = index + 1
        while marker_end < len(line) and line[marker_end] == "`":
            marker_end += 1
        if in_code:
            start = marker_end
            in_code = False
        else:
            if start < index:
                spans.append((start, index))
            in_code = True
        index = marker_end
    if not in_code and start < len(line):
        spans.append((start, len(line)))
    return tuple(spans)


def _normalize_spacing(segment: str) -> str:
    newline = ""
    if segment.endswith("\r\n"):
        segment = segment[:-2]
        newline = "\r\n"
    elif segment.endswith("\n"):
        segment = segment[:-1]
        newline = "\n"

    leading_match = re.match(r"^\s*", segment)
    trailing_match = re.search(r"\s*$", segment)
    leading = leading_match.group(0) if leading_match else ""
    trailing = trailing_match.group(0) if trailing_match else ""
    body = segment[len(leading) : len(segment) - len(trailing) if trailing else len(segment)]

    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\s+([,.;:!?])", r"\1", body)
    body = re.sub(r"([([{])\s+", r"\1", body)
    body = re.sub(r"\s+([])}])", r"\1", body)
    return f"{leading}{body}{trailing}{newline}"


def _parse_rule(raw_rule: dict[str, Any]) -> HygieneRule:
    kind_text = str(raw_rule.get("kind", "")).strip()
    if kind_text == "phrase":
        kind: RuleKind = "phrase"
    elif kind_text == "regex":
        kind = "regex"
    else:
        raise ValueError(f"text hygiene rule `{raw_rule.get('id')}` kind must be phrase or regex")
    pattern = str(raw_rule.get("pattern", ""))
    if not pattern:
        raise ValueError(f"text hygiene rule `{raw_rule.get('id')}` needs a pattern")
    raw_flags = raw_rule.get("flags", [])
    flags: tuple[str, ...]
    if isinstance(raw_flags, str):
        flags = (raw_flags,)
    elif isinstance(raw_flags, list):
        flags = tuple(str(flag) for flag in raw_flags)
    else:
        raise ValueError(f"text hygiene rule `{raw_rule.get('id')}` flags must be a list")
    action_text = str(raw_rule.get("action", "clean")).strip().lower()
    if action_text == "clean":
        action: RuleAction = "clean"
    elif action_text == "flag":
        action = "flag"
    else:
        raise ValueError(
            f"text hygiene rule `{raw_rule.get('id')}` action must be clean or flag"
        )
    return HygieneRule(
        id=str(raw_rule["id"]),
        kind=kind,
        pattern=pattern,
        replacement=str(raw_rule.get("replacement", "")),
        flags=flags,
        note=str(raw_rule["note"]) if raw_rule.get("note") is not None else None,
        action=action,
    )


def _regex_flags(flags: tuple[str, ...]) -> int:
    value = 0
    for flag in flags:
        normalized = flag.lower()
        if normalized in {"i", "ignorecase"}:
            value |= re.IGNORECASE
        elif normalized in {"m", "multiline"}:
            value |= re.MULTILINE
        elif normalized in {"s", "dotall"}:
            value |= re.DOTALL
        else:
            raise ValueError(f"unsupported regex flag: {flag}")
    return value


def _candidate_config_paths(config_path: Path | None, *, cwd: Path | None) -> tuple[Path, ...]:
    if config_path is not None:
        return (config_path.expanduser(),)

    candidates: list[Path] = []
    env_config = os.environ.get("JARVIS_TEXT_HYGIENE_CONFIG")
    if env_config:
        candidates.append(Path(env_config).expanduser())

    root = _find_project_root(cwd or Path.cwd())
    if root is not None:
        candidates.append(root / ".jarvis" / "context" / "style" / "ai-speak-patterns.yaml")
        user = os.environ.get("FLOW_USER") or os.environ.get("USER") or getpass.getuser()
        candidates.append(
            root
            / ".jarvis"
            / "context"
            / "private"
            / user
            / "style"
            / "ai-speak-patterns.yaml"
        )

    return tuple(dict.fromkeys(candidates))


def _find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".jarvis" / "context").exists() or (candidate / ".git").exists():
            return candidate
    return None
