from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FLOW_CRON_PATH = REPO_ROOT / "tools" / "flow-install" / "scripts" / "flow-cron"

loader = SourceFileLoader("flow_cron", str(FLOW_CRON_PATH))
spec = importlib.util.spec_from_loader("flow_cron", loader)
assert spec and spec.loader
flow_cron = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow_cron)


def test_prompt_entries_default_to_codex(monkeypatch) -> None:
    monkeypatch.delenv("FLOW_CRON_PROMPT_RUNNER", raising=False)

    command = flow_cron.build_prompt_command(
        "cd jarvis-cli && uv run jarvis plan --days 7 --save",
        "/repo",
    )

    assert "codex exec" in command
    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert "claude -p" not in command


def test_launchd_environment_defaults_to_auto_with_codex_first(monkeypatch) -> None:
    monkeypatch.delenv("FLOW_CRON_AI_PROVIDER", raising=False)
    monkeypatch.delenv("FLOW_CRON_AI_PROVIDER_ORDER", raising=False)
    monkeypatch.delenv("FLOW_CRON_PROMPT_RUNNER", raising=False)

    plist = flow_cron.build_launchd_plist(
        {
            "skill": "project",
            "name": "weekly-plan",
            "cron": "0 18 * * 0",
            "type": "prompt",
            "command": "/life weekly",
            "description": "weekly plan",
        },
        "/repo",
    )

    env = plist["EnvironmentVariables"]
    assert env["FLOW_CRON_PROMPT_RUNNER"] == "codex"
    assert env["HARNESSY_AI_PROVIDER"] == "auto"
    assert env["FLOW_AI_PROVIDER"] == "auto"
    assert env["HARNESSY_AI_PROVIDER_ORDER"] == "codex,claude,opencode"
    assert env["FLOW_AI_PROVIDER_ORDER"] == "codex,claude,opencode"


def test_cron_environment_includes_fathom_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("FATHOM_API_KEY", "secret-default")
    monkeypatch.setenv("JARVIS_FATHOM_WORK_API_KEY", "secret-work")
    monkeypatch.setenv("UNRELATED_API_KEY", "ignored")

    env = flow_cron.build_cron_environment(path="/usr/bin")

    assert env["FATHOM_API_KEY"] == "secret-default"
    assert env["JARVIS_FATHOM_WORK_API_KEY"] == "secret-work"
    assert "UNRELATED_API_KEY" not in env


def test_collect_path_dirs_drops_codex_temp_path(monkeypatch) -> None:
    monkeypatch.setenv(
        "PATH",
        "/Users/me/.codex/tmp/arg0/codex-test:/usr/local/bin:/Users/me/.nvm/bin",
    )

    assert flow_cron.collect_path_dirs() == "/usr/local/bin:/Users/me/.nvm/bin"
