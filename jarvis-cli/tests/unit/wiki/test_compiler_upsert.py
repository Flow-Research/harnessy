"""Tests for compiler._upsert_concept dedup resolution.

This is the Track 1 entity-resolution algorithm — the most important behavior
to lock in. Uses a fake backend so we don't spawn claude-cli; the LLM
is_same_entity classifier is mocked via FakeBackend.same_entity_responses.
"""

from pathlib import Path
from typing import Any

from jarvis.wiki.backends.base import WikiBackend
from jarvis.wiki.compiler import WikiCompiler, _EntityIndex
from jarvis.wiki.models import WikiDomain


class FakeBackend(WikiBackend):
    """Fake backend that records is_same_entity calls and returns scripted answers."""

    def __init__(self, same_entity_responses: dict[frozenset, bool] | None = None) -> None:
        super().__init__()
        self.same_entity_responses = same_entity_responses or {}
        self.is_same_entity_calls: list[tuple[str, str]] = []
        self.merge_entity_calls: list[tuple[str, str]] = []

    def run(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        return ""

    def is_same_entity(  # type: ignore[override]
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
        self.is_same_entity_calls.append((slug_a, slug_b))
        return self.same_entity_responses.get(frozenset({slug_a, slug_b}), False)

    def merge_entity(  # type: ignore[override]
        self, domain: Any, existing_page: str, new_info: str, source_slug: str
    ) -> str:
        self.merge_entity_calls.append((source_slug, new_info))
        # Return existing unchanged so the test can inspect frontmatter changes
        return existing_page


def _make_compiler(tmp_path: Path, backend: FakeBackend) -> WikiCompiler:
    schema = WikiDomain(domain="test", title="Test", description="t")
    compiler = WikiCompiler(tmp_path, schema)
    compiler._backend = backend  # noqa: SLF001
    return compiler


def _entity(slug: str, name: str | None = None, aliases: list[str] | None = None) -> dict:
    return {
        "slug": slug,
        "name": name or slug.replace("-", " ").title(),
        "type": "concept",
        "description": f"Description of {slug}.",
        "aliases": aliases or [],
    }


class TestUpsertConceptCreate:
    """First-time entities get a new concept file."""

    def test_creates_new_concept(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()

        entity = _entity("react", "ReAct")
        path, outcome = compiler._upsert_concept(  # noqa: SLF001
            entity, source_slug="src1", summary_text="ignored", entity_index=index
        )
        assert outcome == "created"
        assert path.exists()
        assert path.name == "react.md"
        assert "ReAct" in path.read_text()
        # Index updated
        assert index.lookup("react") == "react"

    def test_no_llm_call_when_creating_first_entity(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()
        compiler._upsert_concept(  # noqa: SLF001
            _entity("react"), "src1", "ignored", index
        )
        assert backend.is_same_entity_calls == []

    def test_creates_with_aliases(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()
        compiler._upsert_concept(  # noqa: SLF001
            _entity("react", aliases=["react-agent", "react-framework"]),
            "src1",
            "ignored",
            index,
        )
        # All aliases resolve to react via the in-memory index
        assert index.lookup("react-agent") == "react"
        assert index.lookup("react-framework") == "react"


class TestUpsertConceptExactMatch:
    """Re-encountering an entity by exact slug merges into the existing file."""

    def test_exact_slug_match_merges(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()

        compiler._upsert_concept(  # noqa: SLF001
            _entity("react"), "src1", "ignored", index
        )
        path, outcome = compiler._upsert_concept(  # noqa: SLF001
            _entity("react"), "src2", "ignored", index
        )
        assert outcome == "updated"
        assert len(backend.merge_entity_calls) == 1
        # No is_same_entity needed for exact slug match
        assert backend.is_same_entity_calls == []


class TestUpsertConceptAliasLookup:
    """An entity whose extracted alias matches an existing canonical merges into it."""

    def test_alias_lookup_via_extracted_aliases(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()

        # First: create canonical 'react' with aliases registered
        compiler._upsert_concept(  # noqa: SLF001
            _entity("react", aliases=["react-agent"]),
            "src1",
            "ignored",
            index,
        )
        # Second: a NEW slug 'react-agent-framework' that has 'react-agent' in aliases
        path, outcome = compiler._upsert_concept(  # noqa: SLF001
            _entity("react-agent-framework", aliases=["react-agent"]),
            "src2",
            "ignored",
            index,
        )
        # Should resolve via alias lookup, not LLM
        assert outcome == "aliased"
        assert path.name == "react.md"
        assert backend.is_same_entity_calls == []
        # New slug now indexed as alias
        assert index.lookup("react-agent-framework") == "react"


class TestUpsertConceptLLMConfirmation:
    """When slugs are similar but no alias match, the LLM is consulted."""

    def test_similar_slug_consults_llm_yes(self, tmp_path: Path) -> None:
        backend = FakeBackend(same_entity_responses={frozenset({"react", "react-agent"}): True})
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()

        compiler._upsert_concept(  # noqa: SLF001
            _entity("react"), "src1", "ignored", index
        )
        path, outcome = compiler._upsert_concept(  # noqa: SLF001
            _entity("react-agent"),
            "src2",
            "ignored",
            index,
        )
        # LLM confirms → merge into react
        assert outcome == "aliased"
        assert path.name == "react.md"
        assert len(backend.is_same_entity_calls) == 1
        # The new slug is now an alias of react
        assert index.lookup("react-agent") == "react"

    def test_similar_slug_consults_llm_no(self, tmp_path: Path) -> None:
        # LLM rejects → create new canonical
        backend = FakeBackend(same_entity_responses={frozenset({"react", "react-native"}): False})
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()

        compiler._upsert_concept(  # noqa: SLF001
            _entity("react"), "src1", "ignored", index
        )
        path, outcome = compiler._upsert_concept(  # noqa: SLF001
            _entity("react-native"),
            "src2",
            "ignored",
            index,
        )
        # LLM said no → new canonical
        assert outcome == "created"
        assert path.name == "react-native.md"
        assert len(backend.is_same_entity_calls) == 1
        # Both now exist independently
        assert index.lookup("react") == "react"
        assert index.lookup("react-native") == "react-native"

    def test_dissimilar_slug_skips_llm(self, tmp_path: Path) -> None:
        """Slugs with no token overlap shouldn't trigger an LLM call."""
        backend = FakeBackend()
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()

        compiler._upsert_concept(  # noqa: SLF001
            _entity("apple"), "src1", "ignored", index
        )
        compiler._upsert_concept(  # noqa: SLF001
            _entity("microsoft"), "src2", "ignored", index
        )
        # Different tokens, no LLM consultation
        assert backend.is_same_entity_calls == []
        assert index.canonical_count() == 2


class TestUpsertConceptEntireCluster:
    """End-to-end: process the full ReAct cluster and verify it collapses to one canonical."""

    def test_react_cluster_collapses(self, tmp_path: Path) -> None:
        # LLM says yes for every react variant pair
        backend = FakeBackend(
            same_entity_responses={
                frozenset({"react", "react-agent"}): True,
                frozenset({"react", "react-framework"}): True,
                frozenset({"react", "react-agent-framework"}): True,
            }
        )
        compiler = _make_compiler(tmp_path, backend)
        index = _EntityIndex()

        for slug in ("react", "react-agent", "react-framework", "react-agent-framework"):
            compiler._upsert_concept(  # noqa: SLF001
                _entity(slug), "src", "ignored", index
            )

        # Only one concept file exists on disk
        concepts = list((tmp_path / "wiki" / "concepts").glob("*.md"))
        assert len(concepts) == 1
        assert concepts[0].name == "react.md"

        # All four slugs resolve to react via the index
        for slug in ("react", "react-agent", "react-framework", "react-agent-framework"):
            assert index.lookup(slug) == "react"
