from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "tools" / "flow-install" / "skills" / "tmux-agent-launcher" / "scripts" / "tmux-agent-launcher"


def run_launcher(tmp_path: Path, *args: str, extra_env: dict[str, str] | None = None) -> dict:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    env.pop("TMUX_AGENT_LAUNCHER_CONFIG", None)
    env.pop("TMUX_AGENT_LAUNCHER_PERMISSION_MODE", None)
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        [str(SCRIPT), *args, "--dry-run", "--json"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def runner_shell_command(plan: dict) -> str:
    return plan["command"][-1]


def test_codex_launch_defaults_to_bypass_when_user_config_is_missing(tmp_path: Path) -> None:
    plan = run_launcher(tmp_path, "--runner", "codex", "agent-test")

    command = runner_shell_command(plan)
    assert plan["permission_mode"] == "bypass"
    assert plan["permission_mode_source"] == "built-in"
    assert command.startswith("codex ")
    assert "--dangerously-bypass-approvals-and-sandbox" in command


def test_user_config_can_opt_out_by_default(tmp_path: Path) -> None:
    config_dir = tmp_path / ".config" / "harnessy"
    config_dir.mkdir(parents=True)
    (config_dir / "tmux-agent-launcher.json").write_text('{"permissionMode":"default"}\n')

    plan = run_launcher(tmp_path, "--runner", "codex", "agent-test")

    command = runner_shell_command(plan)
    assert plan["permission_mode"] == "default"
    assert plan["permission_mode_source"] == "config"
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_cli_permission_mode_wins_over_env_and_config(tmp_path: Path) -> None:
    config_dir = tmp_path / ".config" / "harnessy"
    config_dir.mkdir(parents=True)
    (config_dir / "tmux-agent-launcher.json").write_text('{"permissionMode":"bypass"}\n')

    plan = run_launcher(
        tmp_path,
        "--runner",
        "claude",
        "agent-test",
        "--permission-mode",
        "default",
        extra_env={"TMUX_AGENT_LAUNCHER_PERMISSION_MODE": "bypass"},
    )

    command = runner_shell_command(plan)
    assert plan["permission_mode"] == "default"
    assert plan["permission_mode_source"] == "cli"
    assert "--permission-mode bypassPermissions" not in command


def test_claude_bypass_uses_permission_mode_flag(tmp_path: Path) -> None:
    plan = run_launcher(tmp_path, "--runner", "claude", "agent-test")

    command = runner_shell_command(plan)
    assert plan["permission_mode"] == "bypass"
    assert command.startswith("claude ")
    assert "--permission-mode bypassPermissions" in command


def test_opencode_bypass_uses_interactive_run_permission_flag(tmp_path: Path) -> None:
    plan = run_launcher(tmp_path, "--runner", "opencode", "agent-test")

    command = runner_shell_command(plan)
    assert plan["permission_mode"] == "bypass"
    assert command.startswith("opencode run --interactive ")
    assert "--dangerously-skip-permissions" in command
    assert "--log-level WARN" in command
