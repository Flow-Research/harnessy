from __future__ import annotations

import json
import os
import pty
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "tools" / "flow-install" / "skills" / "tmux-agent-launcher" / "scripts" / "tmux-agent-launcher"


def launcher_env(tmp_path: Path, extra_env: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    env.pop("TMUX_AGENT_LAUNCHER_CONFIG", None)
    env.pop("TMUX_AGENT_LAUNCHER_PERMISSION_MODE", None)
    if extra_env:
        env.update(extra_env)
    return env


def run_launcher(
    tmp_path: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    cwd: Path = REPO_ROOT,
) -> dict:
    env = launcher_env(tmp_path, extra_env)

    result = subprocess.run(
        [str(SCRIPT), *args, "--dry-run", "--json"],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def run_launcher_interactive(
    tmp_path: Path,
    input_text: str,
    *args: str,
    extra_env: dict[str, str] | None = None,
    cwd: Path = REPO_ROOT,
) -> dict:
    env = launcher_env(tmp_path, extra_env)
    master_fd, slave_fd = pty.openpty()
    try:
        process = subprocess.Popen(
            [str(SCRIPT), *args, "--dry-run", "--json"],
            cwd=cwd,
            env=env,
            stdin=slave_fd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        os.close(slave_fd)
        os.write(master_fd, input_text.encode())
        stdout, stderr = process.communicate(timeout=10)
        if process.returncode != 0:
            raise AssertionError(f"launcher failed with {process.returncode}: {stderr}")
        return json.loads(stdout)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass


def runner_shell_command(plan: dict) -> str:
    return plan["command"][-1]


def tmux_path_with_sessions(tmp_path: Path, sessions: list[str]) -> str:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux = bin_dir / "tmux"
    tmux.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'if [[ "${1:-}" == "list-sessions" ]]; then',
                "cat <<'EOF'",
                *sessions,
                "EOF",
                "exit 0",
                "fi",
                "exit 0",
                "",
            ]
        )
    )
    tmux.chmod(0o755)
    return f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


def test_codex_launch_defaults_to_bypass_when_user_config_is_missing(tmp_path: Path) -> None:
    plan = run_launcher(tmp_path, "--runner", "codex", "agent-test")

    command = runner_shell_command(plan)
    assert plan["attach"] is True
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


def test_no_attach_leaves_created_session_detached(tmp_path: Path) -> None:
    plan = run_launcher(tmp_path, "--runner", "codex", "agent-test", "--no-attach")

    assert plan["attach"] is False


def test_explicit_session_name_is_not_rewritten(tmp_path: Path) -> None:
    plan = run_launcher(
        tmp_path,
        "--runner",
        "codex",
        "agent-test",
        extra_env={"PATH": tmux_path_with_sessions(tmp_path, ["agent-test-codex-4"])},
    )

    assert plan["session"] == "agent-test"


def test_omitted_session_name_uses_folder_default_non_interactively(tmp_path: Path) -> None:
    plan = run_launcher(
        tmp_path,
        "--runner",
        "codex",
        extra_env={"PATH": tmux_path_with_sessions(tmp_path, [])},
    )

    assert plan["session"] == "harnessy-codex-1"


def test_omitted_session_name_uses_typed_interactive_name(tmp_path: Path) -> None:
    project_dir = tmp_path / "Project Space"
    project_dir.mkdir()

    plan = run_launcher_interactive(
        tmp_path,
        "flow\n",
        "--runner",
        "claude",
        "--cwd",
        str(project_dir),
        extra_env={"PATH": tmux_path_with_sessions(tmp_path, [])},
    )

    assert plan["session"] == "flow-claude-1"


def test_blank_interactive_name_uses_folder_default(tmp_path: Path) -> None:
    project_dir = tmp_path / "My Project"
    project_dir.mkdir()

    plan = run_launcher_interactive(
        tmp_path,
        "\n",
        "--runner",
        "opencode",
        "--cwd",
        str(project_dir),
        extra_env={"PATH": tmux_path_with_sessions(tmp_path, [])},
    )

    assert plan["session"] == "My-Project-opencode-1"


def test_omitted_session_name_uses_next_matching_tmux_index(tmp_path: Path) -> None:
    plan = run_launcher(
        tmp_path,
        "--runner",
        "codex",
        extra_env={
            "PATH": tmux_path_with_sessions(
                tmp_path,
                [
                    "harnessy-codex-1",
                    "harnessy-codex-3",
                    "harnessy-claude-9",
                    "other-codex-20",
                ],
            )
        },
    )

    assert plan["session"] == "harnessy-codex-4"


def test_auto_index_is_scoped_by_runner(tmp_path: Path) -> None:
    plan = run_launcher(
        tmp_path,
        "--runner",
        "codex",
        extra_env={"PATH": tmux_path_with_sessions(tmp_path, ["harnessy-claude-1"])},
    )

    assert plan["session"] == "harnessy-codex-1"
