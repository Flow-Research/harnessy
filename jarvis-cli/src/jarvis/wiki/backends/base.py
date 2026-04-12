"""Abstract base class for wiki LLM backends."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, cast


class WikiBackend(ABC):
    """Provider-agnostic interface for wiki LLM operations.

    Subclasses implement only `run()`. The high-level methods (summarize,
    extract_entities, cross_reference, merge_entity) live here so prompt
    formatting logic is shared across all backends.

    Token usage is accumulated per session via `record_usage()` and consumed
    by callers via `pop_usage()`. Subclasses should call `record_usage()`
    inside their `run()` implementation when usage information is available;
    backends without per-call usage data can simply omit the call.
    """

    def __init__(self) -> None:
        self._usage: dict[str, int] = {}

    def record_usage(self, operation: str, input_tokens: int, output_tokens: int) -> None:
        """Add token usage for one LLM call to the running accumulator.

        Counts are stored as `<operation>_input` and `<operation>_output`
        keys so a single source's compile cost can be broken down by step.
        """
        if input_tokens:
            key_in = f"{operation}_input"
            self._usage[key_in] = self._usage.get(key_in, 0) + input_tokens
        if output_tokens:
            key_out = f"{operation}_output"
            self._usage[key_out] = self._usage.get(key_out, 0) + output_tokens

    def pop_usage(self) -> dict[str, int]:
        """Return accumulated usage and clear the accumulator.

        Compilers call this between sources so each manifest record contains
        only the cost of compiling that source.
        """
        usage = self._usage
        self._usage = {}
        return usage

    def reset_usage(self) -> None:
        """Discard accumulated usage without returning it."""
        self._usage = {}

    @abstractmethod
    def run(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Execute a single LLM call and return the text response.

        Implementations should call `self.record_usage(operation, ...)` after
        a successful call when token counts are available.

        Args:
            operation: Human-readable label for the operation (e.g. "summarize").
            system_prompt: System prompt string.
            user_prompt: User message string.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Text response from the model.
        """
        ...

    def research_session(
        self,
        prompt: str,
        allowed_dirs: list[str],
        max_turns: int = 25,
        timeout: int = 1800,
    ) -> str:
        """Run a multi-turn research agent session and return its raw output.

        Unlike `run()`, this spawns an interactive agent with file and web
        tools enabled and lets it act over many turns. The agent is expected
        to read context files, search the web, fetch sources, and write new
        markdown files into one of the allowed directories. Its final
        response should contain a JSON summary that the caller parses.

        Default implementation raises NotImplementedError; only backends that
        can host a tool-using agent loop need to override this. The
        `claude_cli` backend implements it via `claude -p` with explicit
        `--allowed-tools` and `--add-dir` flags.

        Args:
            prompt: The full agent prompt (system + user content combined).
            allowed_dirs: Filesystem paths the agent is allowed to read/write.
            max_turns: Maximum number of agent turns before termination.
            timeout: Wall-clock timeout in seconds.

        Returns:
            The agent's final text output (expected to end with a JSON block).
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support research_session(). "
            "Use the claude-cli backend for autonomous research."
        )

    def summarize(
        self,
        domain: Any,
        source_slug: str,
        source_type: str,
        title: str,
        source_date: Any,
        body_text: str,
    ) -> str:
        """Compile a raw source into a wiki article with YAML frontmatter."""
        import datetime

        from jarvis.wiki.prompts import SUMMARIZE_SYSTEM, SUMMARIZE_USER

        categories_str = ", ".join(f"{c.id}: {c.label}" for c in domain.categories)
        system = SUMMARIZE_SYSTEM.format(
            domain_title=domain.title,
            summary_length=domain.compile.summary_length,
            categories=categories_str,
            source_slug=source_slug,
            source_type=source_type,
            today=datetime.date.today().isoformat(),
        )
        user = SUMMARIZE_USER.format(
            title=title,
            source_type=source_type,
            source_date=source_date,
            body_text=body_text[:12000],
        )
        return self.run(
            "summarize",
            system,
            user,
            max_tokens=domain.llm.max_tokens_compile,
            temperature=domain.llm.temperature,
        )

    def extract_entities(
        self, domain: Any, article_text: str, source_slug: str = ""
    ) -> list[dict[str, Any]]:
        """Extract named entities from a compiled wiki article.

        Returns a list of entity dicts with keys: name, slug, type,
        description, aliases, mentioned_in.
        """
        from jarvis.wiki.prompts import EXTRACT_ENTITIES_SYSTEM, EXTRACT_ENTITIES_USER

        entity_types_str = json.dumps(domain.entity_types)
        system = EXTRACT_ENTITIES_SYSTEM.format(
            entity_types=entity_types_str, source_slug=source_slug
        )
        user = EXTRACT_ENTITIES_USER.format(
            article_text=article_text,
            entity_types=entity_types_str,
        )
        raw = self.run("extract_entities", system, user, max_tokens=2048, temperature=0.1)
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start != -1 and end > start:
                return cast("list[dict[str, Any]]", json.loads(raw[start:end]))
        except json.JSONDecodeError:
            pass
        return []

    def cross_reference(self, domain: Any, article_text: str, concept_slugs: list[str]) -> str:
        """Insert [[wiki-links]] into an article for known concept slugs."""
        from jarvis.wiki.prompts import CROSS_REFERENCE_SYSTEM, CROSS_REFERENCE_USER

        user = CROSS_REFERENCE_USER.format(
            concept_slugs_json=json.dumps(concept_slugs),
            article_text=article_text,
        )
        return self.run(
            "cross_reference",
            CROSS_REFERENCE_SYSTEM,
            user,
            max_tokens=domain.llm.max_tokens_compile,
            temperature=0.1,
        )

    def identify_relevant(self, domain: Any, question: str, index_content: str) -> list[str]:
        """Given a question and index.md content, return list of relevant slugs."""
        from jarvis.wiki.prompts import IDENTIFY_RELEVANT_SYSTEM, IDENTIFY_RELEVANT_USER

        system = IDENTIFY_RELEVANT_SYSTEM
        user = IDENTIFY_RELEVANT_USER.format(
            question=question,
            index_content=index_content[:8000],
        )
        raw = self.run("identify_relevant", system, user, max_tokens=512, temperature=0.1)
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start != -1 and end > start:
                return cast("list[str]", json.loads(raw[start:end]))
        except json.JSONDecodeError:
            pass
        return []

    def answer_question(
        self,
        domain: Any,
        question: str,
        article_texts: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """Answer question using wiki articles.

        Returns dict with keys: answer, synthesis_flag, confidence, sources_used.
        """
        from jarvis.wiki.prompts import QA_SYSTEM, QA_USER

        articles_block = "\n\n".join(f"### {slug}\n{text[:4000]}" for slug, text in article_texts)
        system = QA_SYSTEM.format(domain_title=domain.title)
        user = QA_USER.format(question=question, articles=articles_block)
        raw = self.run(
            "answer_question",
            system,
            user,
            max_tokens=domain.llm.max_tokens_qa,
            temperature=domain.llm.temperature_qa,
        )
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return cast("dict[str, Any]", json.loads(raw[start:end]))
        except json.JSONDecodeError:
            pass
        # Fallback: treat raw response as the answer
        return {
            "answer": raw,
            "synthesis_flag": False,
            "confidence": 0.5,
            "sources_used": [slug for slug, _ in article_texts],
        }

    def is_same_entity(
        self,
        name_a: str,
        slug_a: str,
        name_b: str,
        slug_b: str,
        aliases_a: list[str] | None = None,
        aliases_b: list[str] | None = None,
        context_a: str = "",
        context_b: str = "",
        confidence_threshold: float = 0.75,
    ) -> bool:
        """Classify whether two entity candidates refer to the same thing.

        Calls the LLM with a strict deduplication prompt and returns True
        only if the model answers "same" with confidence above the threshold.
        Used by the compiler when slug similarity suggests a possible duplicate
        but exact match fails.

        Args:
            name_a, slug_a: First candidate's display name and slug
            name_b, slug_b: Second candidate's display name and slug
            aliases_a, aliases_b: Optional alias lists for each
            context_a, context_b: Optional one-line descriptions for each
            confidence_threshold: Minimum confidence required for True

        Returns:
            True only when the LLM is confident both refer to the same entity.
        """
        from jarvis.wiki.prompts import IS_SAME_ENTITY_SYSTEM, IS_SAME_ENTITY_USER

        user = IS_SAME_ENTITY_USER.format(
            name_a=name_a,
            slug_a=slug_a,
            aliases_a=json.dumps(aliases_a or []),
            context_a=context_a or "(none)",
            name_b=name_b,
            slug_b=slug_b,
            aliases_b=json.dumps(aliases_b or []),
            context_b=context_b or "(none)",
        )
        raw = self.run(
            "is_same_entity",
            IS_SAME_ENTITY_SYSTEM,
            user,
            max_tokens=256,
            temperature=0.0,
        )
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                result = json.loads(raw[start:end])
                return (
                    bool(result.get("same"))
                    and float(result.get("confidence", 0.0)) >= confidence_threshold
                )
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return False

    def merge_entity(self, domain: Any, existing_page: str, new_info: str, source_slug: str) -> str:
        """Merge new information into an existing concept page."""
        from jarvis.wiki.prompts import ENTITY_MERGE_SYSTEM

        user = (
            f"Existing concept page:\n---\n{existing_page}\n---\n\n"
            f"New information from source '{source_slug}':\n---\n{new_info}\n---\n\n"
            "Return the updated concept page."
        )
        return self.run(
            "merge_entity",
            ENTITY_MERGE_SYSTEM,
            user,
            max_tokens=domain.llm.max_tokens_compile,
            temperature=domain.llm.temperature,
        )

    def lint_article(self, domain: Any, article_text: str, all_slugs: list[str]) -> dict[str, Any]:
        """Check article for contradictions, stale claims, suggestions.

        Returns dict with keys: contradictions, stale_claims, suggestions.
        """
        from jarvis.wiki.prompts import LINT_SYSTEM, LINT_USER

        user = LINT_USER.format(
            article_text=article_text[:8000],
            known_slugs=", ".join(all_slugs),
        )
        raw = self.run("lint_article", LINT_SYSTEM, user, max_tokens=1024, temperature=0.1)
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return cast("dict[str, Any]", json.loads(raw[start:end]))
        except json.JSONDecodeError:
            pass
        return {"contradictions": [], "stale_claims": [], "suggestions": []}
