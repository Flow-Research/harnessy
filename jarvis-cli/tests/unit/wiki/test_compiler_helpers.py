"""Tests for jarvis.wiki.compiler private helpers.

Covers `_split_frontmatter` (markdown frontmatter parser) and `_EntityIndex`
(canonical → aliases lookup) — the pure pieces of the compile pipeline that
don't need a backend.
"""

from jarvis.wiki.compiler import _EntityIndex, _split_frontmatter


class TestSplitFrontmatter:
    """_split_frontmatter splits a markdown article into (frontmatter, body)."""

    def test_well_formed_frontmatter(self) -> None:
        text = "---\ntitle: Test\ntags:\n  - a\n  - b\n---\n\nBody text here.\n"
        fm, body = _split_frontmatter(text)
        assert fm["title"] == "Test"
        assert fm["tags"] == ["a", "b"]
        assert "Body text here" in body

    def test_no_frontmatter_returns_empty_dict(self) -> None:
        text = "Just plain markdown.\n"
        fm, body = _split_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_empty_input(self) -> None:
        fm, body = _split_frontmatter("")
        assert fm == {}
        assert body == ""

    def test_malformed_yaml_returns_empty_dict(self) -> None:
        # Unclosed quote breaks YAML
        text = "---\ntitle: 'unclosed\n---\n\nbody\n"
        fm, body = _split_frontmatter(text)
        assert fm == {}
        # Body returned unchanged when parsing fails
        assert body == text

    def test_non_dict_yaml_returns_empty(self) -> None:
        # YAML that parses to a list, not a dict
        text = "---\n- one\n- two\n---\n\nbody\n"
        fm, body = _split_frontmatter(text)
        assert fm == {}

    def test_body_preserved_verbatim(self) -> None:
        body_content = "# Heading\n\nParagraph with **bold**.\n\n- list\n- items\n"
        text = f"---\ntitle: T\n---\n{body_content}"
        _, body = _split_frontmatter(text)
        assert body.strip() == body_content.strip()


class TestEntityIndex:
    """_EntityIndex maintains canonical → alias lookups during a compile session."""

    def test_empty_index(self) -> None:
        idx = _EntityIndex()
        assert idx.canonical_count() == 0
        assert idx.alias_count() == 0
        assert idx.lookup("anything") is None
        assert idx.find_similar("anything") == []
        assert idx.canonical_slugs() == []

    def test_add_canonical_no_aliases(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=[], summary="An agent framework.")
        assert idx.canonical_count() == 1
        assert idx.alias_count() == 0
        assert idx.lookup("react") == "react"
        assert idx.name_for("react") == "ReAct"
        assert idx.summary_for("react") == "An agent framework."

    def test_add_canonical_with_aliases(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=["react-agent", "react-framework"])
        assert idx.canonical_count() == 1
        assert idx.alias_count() == 2
        # All three resolve to the same canonical
        assert idx.lookup("react") == "react"
        assert idx.lookup("react-agent") == "react"
        assert idx.lookup("react-framework") == "react"

    def test_add_alias_after_canonical(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=[])
        idx.add_alias("react-agent-framework", "react")
        assert idx.lookup("react-agent-framework") == "react"
        assert "react-agent-framework" in idx.aliases_for("react")

    def test_add_alias_ignores_self_reference(self) -> None:
        """Adding the canonical as its own alias should be a no-op."""
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=[])
        idx.add_alias("react", "react")
        assert idx.alias_count() == 0  # not double-counted

    def test_lookup_is_case_insensitive(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=[])
        assert idx.lookup("REACT") == "react"
        assert idx.lookup("React") == "react"

    def test_unknown_slug_returns_none(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=[])
        assert idx.lookup("vue") is None
        assert idx.lookup("react-native") is None  # not registered

    def test_find_similar_exact_normalized_match(self) -> None:
        """react-agent-framework should find 'react' canonical."""
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=[])
        similar = idx.find_similar("react-agent-framework")
        assert "react" in similar

    def test_find_similar_jaccard_match(self) -> None:
        """High-Jaccard pairs should surface."""
        idx = _EntityIndex()
        idx.add_canonical("kill-switch-audit-trail", "Kill Switch Audit Trail", aliases=[])
        similar = idx.find_similar("kill-switch-and-audit-trail")
        assert "kill-switch-audit-trail" in similar

    def test_find_similar_excludes_self(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=[])
        # Looking for 'react' shouldn't return 'react' itself
        assert "react" not in idx.find_similar("react")

    def test_find_similar_no_matches(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("apple", "Apple", aliases=[])
        idx.add_canonical("microsoft", "Microsoft", aliases=[])
        # Slug with no token overlap should return empty
        assert idx.find_similar("zhipu-ai") == []

    def test_aliases_for_returns_sorted(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("react", "ReAct", aliases=["react-zoo", "react-bee"])
        aliases = idx.aliases_for("react")
        assert aliases == sorted(aliases)

    def test_canonical_slugs_returns_sorted(self) -> None:
        idx = _EntityIndex()
        idx.add_canonical("zoo", "Zoo", aliases=[])
        idx.add_canonical("apple", "Apple", aliases=[])
        idx.add_canonical("microsoft", "Microsoft", aliases=[])
        assert idx.canonical_slugs() == ["apple", "microsoft", "zoo"]

    def test_full_react_cluster_collapse(self) -> None:
        """End-to-end check: register react with all aliases, every variant resolves."""
        idx = _EntityIndex()
        idx.add_canonical(
            "react",
            "ReAct",
            aliases=["react-agent", "react-framework", "react-agent-framework"],
        )
        for slug in ("react", "react-agent", "react-framework", "react-agent-framework"):
            assert idx.lookup(slug) == "react"
