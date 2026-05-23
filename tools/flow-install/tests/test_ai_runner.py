from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_ROOT = REPO_ROOT / "tools" / "flow-install" / "skills" / "_shared"

sys.path.insert(0, str(SHARED_ROOT))

import ai_runner  # type: ignore


def test_provider_order_uses_explicit_provider(monkeypatch) -> None:
    monkeypatch.setenv("HARNESSY_AI_PROVIDER", "opencode")
    assert ai_runner.provider_order() == ["opencode"]


def test_provider_order_auto_uses_configured_order(monkeypatch) -> None:
    monkeypatch.setenv("HARNESSY_AI_PROVIDER", "auto")
    monkeypatch.setenv("HARNESSY_AI_PROVIDER_ORDER", "codex,claude")
    assert ai_runner.provider_order() == ["codex", "claude"]


def test_classify_auth_failure_from_claude_login_message() -> None:
    error_type, summary = ai_runner.classify_failure(
        "Not logged in · Please run /login",
        "SessionEnd hook failed: Hook cancelled",
        1,
    )
    assert error_type == "auth_required"
    assert "not logged in" in summary.lower()


def test_classify_hook_failure_separately_from_auth() -> None:
    error_type, _ = ai_runner.classify_failure(
        "",
        "SessionEnd hook [worker-service] failed: Hook cancelled",
        1,
    )
    assert error_type == "hook_failed"


def test_markdown_document_detection_accepts_daily_brief_shape() -> None:
    text = "## What Moved\nA\n\n## What Needs You\nB\n\n## Strategic Picture\nC\n"
    assert ai_runner.looks_like_markdown_document(text)


def test_provider_model_translates_claude_alias_for_codex(monkeypatch) -> None:
    monkeypatch.delenv("HARNESSY_AI_CODEX_MODEL", raising=False)
    monkeypatch.delenv("HARNESSY_AI_CODEX_DEFAULT_MODEL", raising=False)

    assert ai_runner.provider_model("codex", "sonnet") == "gpt-5.4-mini"
    assert ai_runner.provider_model("codex", "haiku") == "gpt-5.4-mini"
    assert ai_runner.provider_model("codex", "gpt-5.2") == "gpt-5.2"


def test_provider_model_omits_claude_alias_for_opencode(monkeypatch) -> None:
    monkeypatch.delenv("HARNESSY_AI_OPENCODE_MODEL", raising=False)

    assert ai_runner.provider_model("opencode", "sonnet") is None
    assert ai_runner.provider_model("opencode", "openai/gpt-5") == "openai/gpt-5"


def test_provider_model_provider_specific_env_wins(monkeypatch) -> None:
    monkeypatch.setenv("HARNESSY_AI_CODEX_MODEL", "gpt-custom")
    monkeypatch.setenv("HARNESSY_AI_OPENCODE_MODEL", "openrouter/test")

    assert ai_runner.provider_model("codex", "sonnet") == "gpt-custom"
    assert ai_runner.provider_model("opencode", "sonnet") == "openrouter/test"


def test_run_ai_prompt_falls_back_after_provider_failure(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_provider(provider, prompt, **kwargs):
        calls.append(provider)
        if provider == "claude":
            return ai_runner.AIResult(
                ok=False,
                provider="claude",
                error_type="auth_required",
                error="Provider is not logged in.",
            )
        return ai_runner.AIResult(ok=True, provider=provider, text="ok")

    monkeypatch.setenv("HARNESSY_AI_PROVIDER", "auto")
    monkeypatch.setenv("HARNESSY_AI_PROVIDER_ORDER", "claude,codex")
    monkeypatch.setattr(ai_runner, "run_provider", fake_run_provider)

    result = ai_runner.run_ai_prompt("prompt")

    assert result.ok
    assert result.provider == "codex"
    assert calls == ["claude", "codex"]
    assert result.warning
