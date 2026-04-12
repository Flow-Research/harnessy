"""Tests for jarvis.wiki.parser pure helper functions.

Covers `slug_from_title`, `normalize_for_comparison`, and `slug_similarity` —
the three functions the dedup pipeline relies on.
"""

import pytest

from jarvis.wiki.parser import (
    normalize_for_comparison,
    slug_from_title,
    slug_similarity,
)


class TestSlugFromTitle:
    """slug_from_title turns a human-readable title into a kebab-case slug."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("My Article", "my-article"),
            ("Apple Intelligence", "apple-intelligence"),
            ("ReAct Framework", "react-framework"),
            ("ERC-8004", "erc-8004"),
            # Special characters dropped
            ("What's Next?", "whats-next"),
            ("Hello, World!", "hello-world"),
            # Underscores and multiple spaces collapse
            ("foo_bar  baz", "foo-bar-baz"),
            # Leading/trailing whitespace and dashes stripped
            ("  spaced  ", "spaced"),
            ("---dashes---", "dashes"),
        ],
    )
    def test_basic_cases(self, title: str, expected: str) -> None:
        assert slug_from_title(title) == expected

    def test_empty_string_returns_empty(self) -> None:
        assert slug_from_title("") == ""

    def test_truncates_to_80_characters(self) -> None:
        long_title = "a" * 200
        result = slug_from_title(long_title)
        assert len(result) == 80


class TestNormalizeForComparison:
    """normalize_for_comparison strips qualifying suffixes for similarity matching."""

    @pytest.mark.parametrize(
        "slug,expected",
        [
            # ReAct cluster from os-agents — every variant collapses to "react"
            ("react", "react"),
            ("react-agent", "react"),
            ("react-framework", "react"),
            ("react-agent-framework", "react"),
            # a2a cluster
            ("a2a", "a2a"),
            ("a2a-protocol", "a2a"),
            # cosmos cluster — also strips trailing 's' plural
            ("cosmos", "cosmo"),
            ("cosmos-blockchain", "cosmo"),
            # Pearl cluster
            ("pearl", "pearl"),
            ("pearl-marketplace", "pearl"),
            # Simple cases — nothing to strip
            ("apple-pay", "applepay"),
            ("microsoft", "microsoft"),
        ],
    )
    def test_collapses_known_clusters(self, slug: str, expected: str) -> None:
        assert normalize_for_comparison(slug) == expected

    def test_empty_string_returns_empty(self) -> None:
        assert normalize_for_comparison("") == ""

    def test_only_strips_suffix_when_base_remains(self) -> None:
        """A slug that IS a suffix shouldn't be reduced to nothing."""
        # "agent" is in the suffix list, but normalizing "agent" alone should
        # not strip itself away — there must be more than 2 chars left.
        result = normalize_for_comparison("agent")
        assert result == "agent"

    def test_double_plural_not_stripped(self) -> None:
        """Words ending in 'ss', 'as', 'is', 'us' should NOT be singularized."""
        # 'class' ends with 'ss' — should stay as-is
        assert normalize_for_comparison("class") == "class"
        # 'analysis' ends with 'is' — should stay as-is
        assert normalize_for_comparison("analysis") == "analysis"

    def test_lowercases_input(self) -> None:
        assert normalize_for_comparison("React-Agent") == "react"


class TestSlugSimilarity:
    """slug_similarity is token-set Jaccard over hyphen-split tokens."""

    @pytest.mark.parametrize(
        "a,b,expected",
        [
            # Same slug → 1.0
            ("react", "react", 1.0),
            # Common Track 1 cases
            ("react-agent-framework", "react-framework", 2 / 3),
            ("a2a", "a2a-protocol", 0.5),
            ("cosmos", "cosmos-blockchain", 0.5),
            ("pearl", "pearl-marketplace", 0.5),
            # No overlap → 0.0
            ("apple", "microsoft", 0.0),
            ("a2a", "ap2", 0.0),
            # High Jaccard — kill switch case
            ("kill-switch-audit-trail", "kill-switch-and-audit-trail", 4 / 5),
        ],
    )
    def test_known_pairs(self, a: str, b: str, expected: float) -> None:
        assert slug_similarity(a, b) == pytest.approx(expected, abs=0.001)

    def test_empty_input_returns_zero(self) -> None:
        assert slug_similarity("", "") == 0.0
        assert slug_similarity("react", "") == 0.0
        assert slug_similarity("", "react") == 0.0

    def test_symmetric(self) -> None:
        """Jaccard is symmetric: sim(a,b) == sim(b,a)."""
        assert slug_similarity("react-agent", "react-framework") == slug_similarity(
            "react-framework", "react-agent"
        )
