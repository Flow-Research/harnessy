"""Deprecated: use jarvis.wiki.backends instead.

WikiLLM is preserved as a thin re-export for any external code that still
imports it directly. New code should use create_backend() from backends/.
"""

from __future__ import annotations

import warnings
from datetime import date
from typing import Any


def __getattr__(name: str) -> type:
    if name == "WikiLLM":
        warnings.warn(
            "WikiLLM is deprecated. Use jarvis.wiki.backends.create_backend() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from jarvis.wiki.backends.sdk import AnthropicSdkBackend as _Sdk

        class WikiLLM(_Sdk):
            """Backward-compat shim: wraps AnthropicSdkBackend with the old interface."""

            def __init__(self, domain: Any) -> None:
                super().__init__(model=domain.llm.model)
                self.domain = domain

            def summarize(  # type: ignore[override]
                self,
                source_slug: str,
                source_type: str,
                title: str,
                source_date: date | None,
                body_text: str,
            ) -> str:
                return super().summarize(
                    self.domain, source_slug, source_type, title, source_date, body_text
                )

            def extract_entities(  # type: ignore[override]
                self, article_text: str
            ) -> list[dict[str, Any]]:
                return super().extract_entities(self.domain, article_text)

            def cross_reference(  # type: ignore[override]
                self, article_text: str, concept_slugs: list[str]
            ) -> str:
                return super().cross_reference(self.domain, article_text, concept_slugs)

            def merge_entity(  # type: ignore[override]
                self, existing_page: str, new_info: str, source_slug: str
            ) -> str:
                return super().merge_entity(self.domain, existing_page, new_info, source_slug)

        return WikiLLM
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
