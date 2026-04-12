"""Anthropic SDK backend — extracted from the original WikiLLM class."""

from __future__ import annotations

import os
from typing import cast

from jarvis.wiki.backends.base import WikiBackend


class AnthropicSdkBackend(WikiBackend):
    """Direct Anthropic API calls via the anthropic SDK."""

    def __init__(self, model: str = "claude-opus-4-6") -> None:
        super().__init__()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise OSError(
                "ANTHROPIC_API_KEY is not set. Export it before using the anthropic-sdk backend."
            )
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model

    def run(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        usage = getattr(message, "usage", None)
        if usage is not None:
            self.record_usage(
                operation,
                int(getattr(usage, "input_tokens", 0) or 0),
                int(getattr(usage, "output_tokens", 0) or 0),
            )
        block = message.content[0]
        if not hasattr(block, "text"):
            raise RuntimeError(
                f"Unexpected response block type (operation={operation}): {type(block)}"
            )
        # The SDK union covers many block types; only TextBlock has `text`.
        # hasattr() guards at runtime; use getattr() to satisfy both checkers.
        return cast(str, getattr(block, "text"))
