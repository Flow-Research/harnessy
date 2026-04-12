"""Claude Code CLI backend — delegates to `claude -p` subprocess."""

from __future__ import annotations

import json
import subprocess
from typing import Any, cast

from jarvis.wiki.backends.base import WikiBackend


class ClaudeCliBackend(WikiBackend):
    """Shells out to `claude -p` for LLM operations.

    Pipes the combined system+user prompt to `claude -p --output-format json`
    and parses the JSON envelope for both the result text and token usage.
    """

    def __init__(self, model: str = "opus") -> None:
        super().__init__()
        self.model = model

    def run(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        combined = f"{system_prompt}\n\n---\n\n{user_prompt}"
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--model", self.model],
            input=combined,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude -p failed (operation={operation}): {result.stderr.strip()}")

        envelope = self._parse_json_envelope(result.stdout)
        text = envelope.get("result") or envelope.get("text") or ""

        usage = envelope.get("usage") or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0) + int(
            usage.get("cache_read_input_tokens", 0) or 0
        )
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        self.record_usage(operation, input_tokens, output_tokens)

        return text.strip()

    @staticmethod
    def _parse_json_envelope(stdout: str) -> dict[str, Any]:
        """Parse the JSON envelope returned by `claude -p --output-format json`.

        Tolerates leading/trailing whitespace and falls back to treating the
        entire stdout as the result text if JSON parsing fails (older claude
        versions or non-JSON output).
        """
        text = stdout.strip()
        if not text:
            return {}
        try:
            return cast("dict[str, Any]", json.loads(text))
        except json.JSONDecodeError:
            # Best-effort fallback: return the raw stdout as the result text.
            return {"result": text, "usage": {}}

    def research_session(
        self,
        prompt: str,
        allowed_dirs: list[str],
        max_turns: int = 25,
        timeout: int = 1800,
    ) -> str:
        """Spawn `claude -p` with web tools enabled for autonomous research.

        The agent is given WebSearch, WebFetch, Read, Write, Glob, and Grep
        and explicit `--add-dir` access to each path in `allowed_dirs`. Its
        final response is returned verbatim — the orchestrator parses the
        trailing JSON contract.
        """
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--allowed-tools",
            "WebSearch,WebFetch,Read,Write,Glob,Grep,LS",
            "--max-turns",
            str(max_turns),
            "--permission-mode",
            "acceptEdits",
        ]
        for d in allowed_dirs:
            cmd.extend(["--add-dir", d])

        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude -p research session failed: {result.stderr.strip()}")

        envelope = self._parse_json_envelope(result.stdout)
        text = envelope.get("result") or envelope.get("text") or ""

        usage = envelope.get("usage") or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0) + int(
            usage.get("cache_read_input_tokens", 0) or 0
        )
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        self.record_usage("research_session", input_tokens, output_tokens)

        return text
