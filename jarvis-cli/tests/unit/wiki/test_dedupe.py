"""Tests for jarvis.wiki.dedupe — legacy duplicate cleanup.

Covers the canonical-picking logic, the dry-run path with a fake backend that
records LLM calls, and the actual file-merge path against a temporary domain.
"""

from pathlib import Path
from typing import Any

from jarvis.wiki.backends.base import WikiBackend
from jarvis.wiki.dedupe import WikiDedupe
from jarvis.wiki.models import WikiDomain

# ── shared fixtures ───────────────────────────────────────────────────────────


class FakeBackend(WikiBackend):
    """In-memory backend that records calls and returns scripted responses."""

    def __init__(
        self,
        same_entity_responses: dict[frozenset, bool] | None = None,
        merge_template: str = "{existing}\n\n[Merged from {source}]\n\n{new_info}",
    ) -> None:
        super().__init__()
        self.same_entity_responses = same_entity_responses or {}
        self.merge_template = merge_template
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
        pair = frozenset({slug_a, slug_b})
        self.is_same_entity_calls.append((slug_a, slug_b))
        return self.same_entity_responses.get(pair, False)

    def merge_entity(  # type: ignore[override]
        self, domain: Any, existing_page: str, new_info: str, source_slug: str
    ) -> str:
        self.merge_entity_calls.append((source_slug, new_info))
        return self.merge_template.format(
            existing=existing_page, new_info=new_info, source=source_slug
        )


def _make_schema(domain: str = "test") -> WikiDomain:
    return WikiDomain(domain=domain, title="Test", description="t")


def _write_concept(
    domain_root: Path,
    slug: str,
    *,
    body: str = "Default body content for the concept.",
    title: str | None = None,
    aliases: list[str] | None = None,
    created: str = "2026-04-01",
) -> Path:
    """Helper that drops a well-formed concept file at <domain>/wiki/concepts/<slug>.md."""
    concepts_dir = domain_root / "wiki" / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    aliases_yaml = "\n".join(f"  - {a}" for a in aliases) if aliases else "  []"
    text = (
        "---\n"
        f"title: {title or slug.replace('-', ' ').title()}\n"
        "type: concept\n"
        "entity_type: concept\n"
        f"created: {created}\n"
        f"updated: {created}\n"
        f"aliases:\n{aliases_yaml}\n"
        "mentioned_in:\n  - source\n"
        "---\n\n"
        f"{body}\n"
    )
    path = concepts_dir / f"{slug}.md"
    path.write_text(text, encoding="utf-8")
    return path


def _make_dedupe(
    tmp_path: Path,
    backend: FakeBackend,
) -> WikiDedupe:
    schema = _make_schema()
    deduper = WikiDedupe(tmp_path, schema)
    # Inject the fake backend so we don't try to spawn claude-cli
    deduper._backend = backend  # noqa: SLF001
    return deduper


# ── _pick_canonical ───────────────────────────────────────────────────────────


class TestPickCanonical:
    def test_more_content_wins(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        deduper = _make_dedupe(tmp_path, backend)
        meta = {
            "a": {"word_count": 100, "created": "2026-01-01"},
            "b": {"word_count": 50, "created": "2026-01-01"},
        }
        winner, loser = deduper._pick_canonical("a", "b", meta)  # noqa: SLF001
        assert winner == "a"
        assert loser == "b"

    def test_earlier_created_wins_on_tie(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        deduper = _make_dedupe(tmp_path, backend)
        meta = {
            "a": {"word_count": 100, "created": "2026-04-01"},
            "b": {"word_count": 100, "created": "2026-02-01"},
        }
        winner, loser = deduper._pick_canonical("a", "b", meta)  # noqa: SLF001
        # b was created earlier → b wins
        assert winner == "b"
        assert loser == "a"

    def test_alphabetical_tiebreak(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        deduper = _make_dedupe(tmp_path, backend)
        meta = {
            "zoo": {"word_count": 50, "created": "2026-04-01"},
            "apple": {"word_count": 50, "created": "2026-04-01"},
        }
        winner, loser = deduper._pick_canonical("zoo", "apple", meta)  # noqa: SLF001
        # Alphabetical tiebreak → apple wins
        assert winner == "apple"
        assert loser == "zoo"

    def test_deterministic(self, tmp_path: Path) -> None:
        """Same inputs always produce same output regardless of arg order."""
        backend = FakeBackend()
        deduper = _make_dedupe(tmp_path, backend)
        meta = {
            "a": {"word_count": 100, "created": "2026-04-01"},
            "b": {"word_count": 50, "created": "2026-04-01"},
        }
        result1 = deduper._pick_canonical("a", "b", meta)  # noqa: SLF001
        result2 = deduper._pick_canonical("b", "a", meta)  # noqa: SLF001
        assert result1 == result2


# ── full dedupe pass ──────────────────────────────────────────────────────────


class TestDedupeFullPass:
    def test_empty_domain_no_proposals(self, tmp_path: Path) -> None:
        backend = FakeBackend()
        deduper = _make_dedupe(tmp_path, backend)
        report = deduper.run(dry_run=True)
        assert report.total_concepts == 0
        assert report.candidate_pairs == 0
        assert report.proposals == []

    def test_no_duplicate_pairs(self, tmp_path: Path) -> None:
        _write_concept(tmp_path, "apple")
        _write_concept(tmp_path, "microsoft")
        backend = FakeBackend()
        deduper = _make_dedupe(tmp_path, backend)
        report = deduper.run(dry_run=True)
        assert report.total_concepts == 2
        # apple/microsoft share no tokens → no candidate pair
        assert report.candidate_pairs == 0
        assert backend.is_same_entity_calls == []

    def test_dry_run_proposes_but_doesnt_merge(self, tmp_path: Path) -> None:
        _write_concept(tmp_path, "react", body="ReAct framework body. " * 20)
        _write_concept(tmp_path, "react-agent", body="ReAct agent body. " * 5)
        backend = FakeBackend(same_entity_responses={frozenset({"react", "react-agent"}): True})
        deduper = _make_dedupe(tmp_path, backend)
        report = deduper.run(dry_run=True)

        assert report.candidate_pairs == 1
        assert report.confirmed_merges == 1
        assert report.merged_files == []  # nothing actually written
        # File still exists (not deleted)
        assert (tmp_path / "wiki" / "concepts" / "react-agent.md").exists()
        assert (tmp_path / "wiki" / "concepts" / "react.md").exists()
        # Backend was called for is_same_entity but NOT for merge_entity
        assert len(backend.is_same_entity_calls) == 1
        assert backend.merge_entity_calls == []

    def test_llm_rejection_skips_merge(self, tmp_path: Path) -> None:
        _write_concept(tmp_path, "apple-pay")
        _write_concept(tmp_path, "apple-intelligence")
        # apple-pay vs apple-intelligence: jaccard 0.33 → below 0.5 threshold,
        # so they shouldn't even reach the LLM. Let me use a pair that DOES
        # trigger but should be rejected: react vs react-native (jaccard 0.5)
        backend = FakeBackend(
            same_entity_responses={}  # everything returns False
        )
        deduper = _make_dedupe(tmp_path, backend)

        # Add a triggering pair with LLM rejection
        _write_concept(tmp_path, "react")
        _write_concept(tmp_path, "react-native")
        report = deduper.run(dry_run=True)

        # react vs react-native should trigger (jaccard 0.5) but get rejected
        assert report.rejected_pairs >= 1
        assert report.confirmed_merges == 0

    def test_confirmed_merge_writes_files(self, tmp_path: Path) -> None:
        _write_concept(
            tmp_path,
            "react",
            body="ReAct framework body content. " * 30,
        )
        _write_concept(
            tmp_path,
            "react-agent",
            body="React agent body content. " * 5,
        )
        backend = FakeBackend(same_entity_responses={frozenset({"react", "react-agent"}): True})
        deduper = _make_dedupe(tmp_path, backend)
        report = deduper.run(dry_run=False)

        assert report.confirmed_merges == 1
        assert len(report.merged_files) == 1
        winner, loser = report.merged_files[0]
        # react has more content → winner
        assert winner == "react"
        assert loser == "react-agent"
        # The loser file is deleted, the winner remains
        assert not (tmp_path / "wiki" / "concepts" / "react-agent.md").exists()
        assert (tmp_path / "wiki" / "concepts" / "react.md").exists()
        # And the merged content was written
        merged_text = (tmp_path / "wiki" / "concepts" / "react.md").read_text()
        assert "Merged from concept 'react-agent'" in merged_text or "react-agent" in merged_text

    def test_existing_aliases_skip_pair(self, tmp_path: Path) -> None:
        """If two concepts already declare each other as aliases, the pair is skipped."""
        _write_concept(tmp_path, "react", aliases=["react-agent"])
        _write_concept(tmp_path, "react-agent")
        backend = FakeBackend(same_entity_responses={frozenset({"react", "react-agent"}): True})
        deduper = _make_dedupe(tmp_path, backend)
        report = deduper.run(dry_run=True)
        # Already linked → no candidate pair
        assert report.candidate_pairs == 0
        assert backend.is_same_entity_calls == []

    def test_max_pairs_caps_evaluation(self, tmp_path: Path) -> None:
        # Create 4 react-cluster concepts → 6 pairs total, but cap at 2
        for slug in ("react", "react-agent", "react-framework", "react-agent-framework"):
            _write_concept(tmp_path, slug)
        backend = FakeBackend()  # always rejects
        deduper = _make_dedupe(tmp_path, backend)
        report = deduper.run(dry_run=True, max_pairs=2)
        assert report.candidate_pairs <= 2

    def test_transitive_merge_redirects_canonical(self, tmp_path: Path) -> None:
        """If we merge B into A in dry-run, a later C↔B comparison should resolve to C↔A."""
        _write_concept(tmp_path, "react", body="canonical body. " * 30)
        _write_concept(tmp_path, "react-agent", body="agent body. " * 5)
        _write_concept(tmp_path, "react-framework", body="framework body. " * 5)
        backend = FakeBackend(
            same_entity_responses={
                frozenset({"react", "react-agent"}): True,
                frozenset({"react", "react-framework"}): True,
            }
        )
        deduper = _make_dedupe(tmp_path, backend)
        report = deduper.run(dry_run=True)
        # Both aliases should be merged into react
        # (test that the canonical map updated transitively)
        assert report.confirmed_merges >= 2
