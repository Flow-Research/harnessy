"""Automation helpers for launching the Fathom webhook workflow."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FathomAutomationPlan:
    """Resolved commands and metadata for a tmux-based Fathom workflow."""

    session_name: str
    cwd: Path
    layout: str
    webhook_command: str
    tunnel_command: str


def build_fathom_automation_plan(
    *,
    session_name: str,
    cwd: Path,
    layout: str,
    account: str,
    port: int,
    auto_ingest: bool,
    destinations: list[str],
    wiki_domain: str | None,
    backend: str | None,
    project: str,
    tags: list[str],
    auto_route: bool,
    verify_signatures: bool,
    tolerance_seconds: int,
    tunnel_name: str | None = None,
) -> FathomAutomationPlan:
    """Build the commands needed to run the webhook and tunnel stack."""

    webhook_args = [
        "uv",
        "run",
        "python",
        "-m",
        "jarvis",
        "meeting",
        "fathom",
        "webhook",
        "serve",
        "--account",
        account,
        "--port",
        str(port),
        "--tolerance-seconds",
        str(tolerance_seconds),
    ]
    if not verify_signatures:
        webhook_args.append("--no-verify-signatures")
    if auto_ingest:
        webhook_args.append("--auto-ingest")
    if project:
        webhook_args.extend(["--project", project])
    if auto_route:
        webhook_args.append("--auto-route")
    if wiki_domain:
        webhook_args.extend(["--wiki-domain", wiki_domain])
    if backend:
        webhook_args.extend(["--backend", backend])
    for tag in tags:
        webhook_args.extend(["--tag", tag])
    for destination in destinations:
        webhook_args.extend(["--dest", destination])

    if tunnel_name:
        tunnel_args = ["cloudflared", "tunnel", "run", tunnel_name]
    else:
        tunnel_args = ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"]

    return FathomAutomationPlan(
        session_name=session_name,
        cwd=cwd,
        layout=layout,
        webhook_command=shlex.join(webhook_args),
        tunnel_command=shlex.join(tunnel_args),
    )


def tmux_launch_commands(plan: FathomAutomationPlan) -> list[list[str]]:
    """Return the tmux commands needed to create the webhook workflow session."""

    cwd = str(plan.cwd)
    if plan.layout == "panes":
        return [
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                plan.session_name,
                "-n",
                "stack",
                "-c",
                cwd,
                "bash",
                "-lc",
                plan.webhook_command,
            ],
            [
                "tmux",
                "set-option",
                "-t",
                plan.session_name,
                "remain-on-exit",
                "on",
            ],
            [
                "tmux",
                "split-window",
                "-t",
                plan.session_name,
                "-h",
                "-c",
                cwd,
                "bash",
                "-lc",
                plan.tunnel_command,
            ],
            ["tmux", "select-layout", "-t", plan.session_name, "even-horizontal"],
        ]
    return [
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            plan.session_name,
            "-n",
            "webhook",
            "-c",
            cwd,
            "bash",
            "-lc",
            plan.webhook_command,
        ],
        [
            "tmux",
            "set-option",
            "-t",
            f"{plan.session_name}:webhook",
            "remain-on-exit",
            "on",
        ],
        [
            "tmux",
            "new-window",
            "-t",
            plan.session_name,
            "-n",
            "tunnel",
            "-c",
            cwd,
            "bash",
            "-lc",
            plan.tunnel_command,
        ],
        [
            "tmux",
            "set-option",
            "-t",
            f"{plan.session_name}:tunnel",
            "remain-on-exit",
            "on",
        ],
    ]


def start_fathom_tmux_stack(plan: FathomAutomationPlan, *, attach: bool = False) -> None:
    """Create the tmux session and optionally attach to it."""

    existing = subprocess.run(
        ["tmux", "has-session", "-t", plan.session_name],
        check=False,
    )
    if existing.returncode == 0:
        raise RuntimeError(f"tmux session already exists: {plan.session_name}")

    for command in tmux_launch_commands(plan):
        subprocess.run(command, check=True)

    if attach:
        subprocess.run(["tmux", "attach-session", "-t", plan.session_name], check=True)


def require_command(command_name: str) -> None:
    """Raise when a required executable is missing from PATH."""

    result = subprocess.run(["which", command_name], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Missing required command: {command_name}")
