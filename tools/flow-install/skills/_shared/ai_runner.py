#!/usr/bin/env python3
"""Provider-agnostic text generation runner for Harnessy skills.

The runner keeps model CLI details out of individual skills. It normalizes
common failure modes so cron jobs can report "Claude auth missing" or "provider
timed out" instead of opaque subprocess errors.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_PROVIDER_ORDER = ("claude", "codex", "opencode")
DEFAULT_CLAUDE_MODEL = "sonnet"
DEFAULT_CODEX_MODEL = "gpt-5.4-mini"
CLAUDE_MODEL_ALIASES = {"sonnet", "haiku", "opus"}
TRANSIENT_FAILURES = {"timeout", "rate_limited", "quota", "hook_failed", "cli_error"}
PERMANENT_FAILURES = {"auth_required", "unavailable", "invalid_provider"}


@dataclass
class AIResult:
    ok: bool
    text: str = ""
    provider: str | None = None
    error_type: str | None = None
    error: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    warning: str | None = None


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def provider_order(provider: str | None = None) -> list[str]:
    selected = (provider or _env("HARNESSY_AI_PROVIDER") or _env("FLOW_AI_PROVIDER") or "auto").lower()
    if selected != "auto":
        return [selected]
    configured = _split_csv(_env("HARNESSY_AI_PROVIDER_ORDER") or _env("FLOW_AI_PROVIDER_ORDER"))
    return configured or list(DEFAULT_PROVIDER_ORDER)


def _is_claude_model_alias(model: str | None) -> bool:
    if not model:
        return False
    lowered = model.strip().lower()
    return lowered in CLAUDE_MODEL_ALIASES or lowered.startswith("claude")


def provider_model(provider: str, model: str | None = None) -> str | None:
    """Resolve the model for a provider without leaking another provider's defaults.

    Life-orchestrator historically used Claude's short model aliases (`sonnet`,
    `haiku`) as global defaults. When the runner falls back to Codex or
    OpenCode, those aliases are not portable. Provider-specific environment
    variables always win; otherwise known Claude aliases are translated or
    omitted so fallback can succeed.
    """
    provider = provider.lower()
    if provider == "claude":
        return _env("HARNESSY_AI_CLAUDE_MODEL", model or DEFAULT_CLAUDE_MODEL)
    if provider == "codex":
        configured = _env("HARNESSY_AI_CODEX_MODEL")
        if configured:
            return configured
        if not model or _is_claude_model_alias(model):
            return _env("HARNESSY_AI_CODEX_DEFAULT_MODEL", DEFAULT_CODEX_MODEL)
        return model
    if provider == "opencode":
        configured = _env("HARNESSY_AI_OPENCODE_MODEL")
        if configured:
            return configured
        if not model or _is_claude_model_alias(model):
            return None
        return model
    return model


def classify_failure(stdout: str, stderr: str, exit_code: int | None = None) -> tuple[str, str]:
    combined = f"{stdout or ''}\n{stderr or ''}".strip()
    lower = combined.lower()
    if "not logged in" in lower or "please run /login" in lower or "login required" in lower:
        return "auth_required", "Provider is not logged in."
    if "authentication" in lower or "unauthorized" in lower or "invalid api key" in lower:
        return "auth_required", "Provider authentication failed."
    if "rate limit" in lower or "429" in lower:
        return "rate_limited", "Provider rate limit was hit."
    if "quota" in lower or "credit balance" in lower or "billing" in lower:
        return "quota", "Provider quota or billing limit was hit."
    if "sessionend hook" in lower and "hook cancelled" in lower:
        return "hook_failed", "Provider generated a hook failure after execution."
    if exit_code == 124 or "timed out" in lower or "timeout" in lower:
        return "timeout", "Provider call timed out."
    return "cli_error", "Provider CLI exited unsuccessfully."


def looks_like_markdown_document(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    signals = (
        "## What Moved",
        "## What Needs",
        "## Strategic Picture",
        "## Background Work",
        "# ",
        "## ",
    )
    return sum(1 for signal in signals if signal in stripped) >= 2 or len(stripped) > 500


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


def _run_subprocess(
    cmd: list[str],
    *,
    prompt: str,
    cwd: str | None,
    timeout_s: int,
) -> subprocess.CompletedProcess[str] | TimeoutError | FileNotFoundError:
    try:
        return subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=cwd or os.getcwd(),
        )
    except subprocess.TimeoutExpired as exc:
        return TimeoutError(f"timed out after {exc.timeout}s")
    except FileNotFoundError as exc:
        return exc


def _claude_command(model: str | None, fallback_model: str | None, budget_usd: str | None) -> list[str]:
    cmd = [
        _env("HARNESSY_AI_CLAUDE_CMD", "claude") or "claude",
        "-p",
        "--output-format",
        "text",
        "--strict-mcp-config",
        "--mcp-config",
        _env("HARNESSY_AI_EMPTY_MCP", str(Path.home() / ".agents" / "cron" / "empty-mcp.json"))
        or str(Path.home() / ".agents" / "cron" / "empty-mcp.json"),
    ]
    if model:
        cmd.extend(["--model", model])
    if fallback_model:
        cmd.extend(["--fallback-model", fallback_model])
    if budget_usd:
        cmd.extend(["--max-budget-usd", budget_usd])
    return cmd


def _run_claude(prompt: str, *, cwd: str | None, model: str | None, fallback_model: str | None, timeout_s: int, budget_usd: str | None) -> AIResult:
    if not shutil.which(_claude_command(None, None, None)[0]):
        return AIResult(ok=False, provider="claude", error_type="unavailable", error="`claude` CLI not found.")
    result = _run_subprocess(_claude_command(model, fallback_model, budget_usd), prompt=prompt, cwd=cwd, timeout_s=timeout_s)
    if isinstance(result, TimeoutError):
        return AIResult(ok=False, provider="claude", error_type="timeout", error=str(result))
    if isinstance(result, FileNotFoundError):
        return AIResult(ok=False, provider="claude", error_type="unavailable", error=str(result))
    stdout = _strip_ansi(result.stdout)
    stderr = _strip_ansi(result.stderr)
    if result.returncode == 0:
        return AIResult(ok=True, provider="claude", text=stdout, stdout=stdout, stderr=stderr, exit_code=0)
    error_type, error = classify_failure(stdout, stderr, result.returncode)
    if error_type == "hook_failed" and looks_like_markdown_document(stdout):
        return AIResult(
            ok=True,
            provider="claude",
            text=stdout,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            warning="Claude SessionEnd hook failed after usable output was generated.",
        )
    return AIResult(
        ok=False,
        provider="claude",
        error_type=error_type,
        error=error,
        stdout=stdout,
        stderr=stderr,
        exit_code=result.returncode,
    )


def _run_codex(prompt: str, *, cwd: str | None, model: str | None, timeout_s: int) -> AIResult:
    codex_cmd = _env("HARNESSY_AI_CODEX_CMD", "codex") or "codex"
    if not shutil.which(codex_cmd):
        return AIResult(ok=False, provider="codex", error_type="unavailable", error="`codex` CLI not found.")
    with tempfile.NamedTemporaryFile(prefix="harnessy-codex-output-", suffix=".md", delete=False) as tmp:
        output_path = tmp.name
    try:
        cmd = [
            codex_cmd,
            "exec",
            "-C",
            cwd or os.getcwd(),
            "-s",
            _env("HARNESSY_AI_CODEX_SANDBOX", "read-only") or "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            "--output-last-message",
            output_path,
        ]
        if model:
            cmd.extend(["--model", model])
        cmd.append("-")
        result = _run_subprocess(cmd, prompt=prompt, cwd=cwd, timeout_s=timeout_s)
        final_text = ""
        try:
            final_text = Path(output_path).read_text(encoding="utf-8")
        except OSError:
            final_text = ""
    finally:
        Path(output_path).unlink(missing_ok=True)
    if isinstance(result, TimeoutError):
        return AIResult(ok=False, provider="codex", error_type="timeout", error=str(result))
    if isinstance(result, FileNotFoundError):
        return AIResult(ok=False, provider="codex", error_type="unavailable", error=str(result))
    stdout = _strip_ansi(result.stdout)
    stderr = _strip_ansi(result.stderr)
    text = final_text.strip() or stdout.strip()
    if result.returncode == 0 and text:
        return AIResult(ok=True, provider="codex", text=text + ("\n" if not text.endswith("\n") else ""), stdout=stdout, stderr=stderr, exit_code=0)
    error_type, error = classify_failure(stdout, stderr, result.returncode)
    return AIResult(ok=False, provider="codex", error_type=error_type, error=error, stdout=stdout, stderr=stderr, exit_code=result.returncode)


def _run_opencode(prompt: str, *, cwd: str | None, model: str | None, timeout_s: int) -> AIResult:
    opencode_cmd = _env("HARNESSY_AI_OPENCODE_CMD", "opencode") or "opencode"
    if not shutil.which(opencode_cmd):
        return AIResult(ok=False, provider="opencode", error_type="unavailable", error="`opencode` CLI not found.")
    cmd = [
        opencode_cmd,
        "run",
        "--pure",
        "--log-level",
        _env("HARNESSY_AI_OPENCODE_LOG_LEVEL", "WARN") or "WARN",
        "--dir",
        cwd or os.getcwd(),
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    result = _run_subprocess(cmd, prompt="", cwd=cwd, timeout_s=timeout_s)
    if isinstance(result, TimeoutError):
        return AIResult(ok=False, provider="opencode", error_type="timeout", error=str(result))
    if isinstance(result, FileNotFoundError):
        return AIResult(ok=False, provider="opencode", error_type="unavailable", error=str(result))
    stdout = _strip_ansi(result.stdout)
    stderr = _strip_ansi(result.stderr)
    if result.returncode == 0 and stdout.strip():
        return AIResult(ok=True, provider="opencode", text=stdout, stdout=stdout, stderr=stderr, exit_code=0)
    error_type, error = classify_failure(stdout, stderr, result.returncode)
    return AIResult(ok=False, provider="opencode", error_type=error_type, error=error, stdout=stdout, stderr=stderr, exit_code=result.returncode)


def run_provider(
    provider: str,
    prompt: str,
    *,
    cwd: str | None = None,
    model: str | None = None,
    fallback_model: str | None = None,
    timeout_s: int = 540,
    budget_usd: str | None = None,
) -> AIResult:
    provider = provider.lower()
    if provider == "claude":
        return _run_claude(prompt, cwd=cwd, model=provider_model(provider, model), fallback_model=fallback_model, timeout_s=timeout_s, budget_usd=budget_usd)
    if provider == "codex":
        return _run_codex(prompt, cwd=cwd, model=provider_model(provider, model), timeout_s=timeout_s)
    if provider == "opencode":
        return _run_opencode(prompt, cwd=cwd, model=provider_model(provider, model), timeout_s=timeout_s)
    return AIResult(ok=False, provider=provider, error_type="invalid_provider", error=f"Unknown provider: {provider}")


def run_ai_prompt(
    prompt: str,
    *,
    provider: str | None = None,
    cwd: str | None = None,
    model: str | None = None,
    fallback_model: str | None = None,
    timeout_s: int = 540,
    budget_usd: str | None = None,
) -> AIResult:
    attempts: list[AIResult] = []
    selected_provider = provider or _env("HARNESSY_AI_PROVIDER") or _env("FLOW_AI_PROVIDER") or "auto"
    single_provider = selected_provider.lower() != "auto"
    for candidate in provider_order(selected_provider):
        result = run_provider(
            candidate,
            prompt,
            cwd=cwd,
            model=model,
            fallback_model=fallback_model,
            timeout_s=timeout_s,
            budget_usd=budget_usd,
        )
        attempts.append(result)
        if result.ok:
            if attempts[:-1]:
                prior = ", ".join(f"{item.provider}:{item.error_type}" for item in attempts[:-1])
                result.warning = f"Fell back to {result.provider} after {prior}."
            return result
        if single_provider:
            return result
    details = "; ".join(f"{item.provider}:{item.error_type or 'unknown'}" for item in attempts)
    return AIResult(ok=False, provider="auto", error_type="all_failed", error=f"All providers failed: {details}", stderr="\n".join(format_failure(item) for item in attempts))


def format_failure(result: AIResult) -> str:
    lines = [f"{result.provider or 'provider'} failed: {result.error_type or 'unknown'} - {result.error}"]
    if result.exit_code is not None:
        lines.append(f"exit_code={result.exit_code}")
    if result.stdout.strip():
        lines.append("stdout:\n" + result.stdout.strip())
    if result.stderr.strip():
        lines.append("stderr:\n" + result.stderr.strip())
    return "\n".join(lines)


def cli(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a prompt through the configured Harnessy AI provider.")
    parser.add_argument("--provider", default=None, help="auto, claude, codex, or opencode. Defaults to HARNESSY_AI_PROVIDER or auto.")
    parser.add_argument("--model", default=_env("HARNESSY_AI_MODEL", "sonnet"))
    parser.add_argument("--fallback-model", default=_env("HARNESSY_AI_FALLBACK_MODEL", "haiku"))
    parser.add_argument("--timeout", type=int, default=int(_env("HARNESSY_AI_TIMEOUT", "540") or "540"))
    parser.add_argument("--budget-usd", default=_env("HARNESSY_AI_BUDGET_USD", "0.50"))
    parser.add_argument("--cwd", default=os.getcwd())
    args = parser.parse_args(list(argv) if argv is not None else None)

    prompt = sys.stdin.read()
    if not prompt.strip():
        print("Error: prompt is empty", file=sys.stderr)
        return 2

    result = run_ai_prompt(
        prompt,
        provider=args.provider,
        cwd=args.cwd,
        model=args.model,
        fallback_model=args.fallback_model,
        timeout_s=args.timeout,
        budget_usd=args.budget_usd,
    )
    if result.ok:
        if result.warning:
            print(f"Warning: {result.warning}", file=sys.stderr)
        sys.stdout.write(result.text)
        if not result.text.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    print(format_failure(result), file=sys.stderr)
    return 2 if result.error_type in PERMANENT_FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(cli())
