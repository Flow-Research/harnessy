"""Backend factory for wiki LLM operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.wiki.backends.base import WikiBackend

if TYPE_CHECKING:
    from jarvis.wiki.models import WikiDomain


def create_backend(schema: WikiDomain) -> WikiBackend:
    """Instantiate the correct WikiBackend from schema.llm.backend.

    Args:
        schema: WikiDomain instance with llm.backend and llm.model fields.

    Returns:
        A WikiBackend instance ready for use.

    Raises:
        ValueError: If the backend name is not recognized.
    """
    backend_name = schema.llm.backend
    model = schema.llm.model

    if backend_name == "claude-cli":
        from jarvis.wiki.backends.claude_cli import ClaudeCliBackend

        return ClaudeCliBackend(model=model)
    elif backend_name == "anthropic-sdk":
        from jarvis.wiki.backends.sdk import AnthropicSdkBackend

        return AnthropicSdkBackend(model=model)
    elif backend_name == "ollama":
        from jarvis.wiki.backends.ollama import OllamaBackend

        ollama_model = getattr(schema.llm, "ollama_model", model)
        return OllamaBackend(model=ollama_model)
    else:
        raise ValueError(
            f"Unknown backend: {backend_name!r}. Supported: claude-cli, anthropic-sdk, ollama"
        )


__all__ = ["WikiBackend", "create_backend"]
