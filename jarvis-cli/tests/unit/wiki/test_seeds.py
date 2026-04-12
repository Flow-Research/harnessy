"""Tests for jarvis.wiki.seeds — the per-domain research seed queue.

Covers parse → serialize round-trip, append_seed, mark_processed, and the
load/write file I/O wrappers.
"""

from datetime import date
from pathlib import Path

from jarvis.wiki.seeds import (
    Seed,
    SeedKind,
    SeedPriority,
    SeedsFile,
    append_seed,
    load_seeds,
    mark_processed,
    parse_seeds,
    seeds_path,
    serialize_seeds,
    write_seeds,
)

# ── parse_seeds ───────────────────────────────────────────────────────────────


class TestParseSeedsEmpty:
    def test_empty_string(self) -> None:
        sf = parse_seeds("", "d")
        assert sf.pending == []
        assert sf.processed == []
        assert sf.pending_count() == 0
        assert sf.processed_count() == 0

    def test_no_sections(self) -> None:
        sf = parse_seeds("# Just a header\n\nNo sections here.\n", "d")
        assert sf.pending == []
        assert sf.processed == []


class TestParseSeedsPending:
    def test_url_seed(self) -> None:
        text = (
            "## Pending\n\n"
            "### URL — https://example.com/foo\n"
            "id: abc123\n"
            "notes: check this\n"
            "priority: high\n"
            "added: 2026-04-12\n"
        )
        sf = parse_seeds(text, "d")
        assert len(sf.pending) == 1
        seed = sf.pending[0]
        assert seed.kind == SeedKind.URL
        assert seed.value == "https://example.com/foo"
        assert seed.id == "abc123"
        assert seed.notes == "check this"
        assert seed.priority == SeedPriority.HIGH
        assert seed.added == date(2026, 4, 12)

    def test_topic_seed(self) -> None:
        text = (
            "## Pending\n\n"
            "### Topic — agents and economics\n"
            "id: t1\n"
            "priority: medium\n"
            "added: 2026-04-11\n"
        )
        sf = parse_seeds(text, "d")
        assert sf.pending[0].kind == SeedKind.TOPIC
        assert sf.pending[0].value == "agents and economics"

    def test_note_seed(self) -> None:
        text = (
            "## Pending\n\n"
            "### Note — does Apple have an MCP equivalent?\n"
            "id: n1\n"
            "priority: low\n"
            "added: 2026-04-10\n"
        )
        sf = parse_seeds(text, "d")
        assert sf.pending[0].kind == SeedKind.NOTE
        assert sf.pending[0].priority == SeedPriority.LOW

    def test_multiple_seeds(self) -> None:
        text = (
            "## Pending\n\n"
            "### URL — https://a.example.com\n"
            "id: 1\n"
            "### URL — https://b.example.com\n"
            "id: 2\n"
            "### Topic — foo\n"
            "id: 3\n"
        )
        sf = parse_seeds(text, "d")
        assert len(sf.pending) == 3
        assert [s.id for s in sf.pending] == ["1", "2", "3"]

    def test_invalid_kind_skipped(self) -> None:
        text = "## Pending\n\n### NotARealKind — whatever\nid: x\n"
        sf = parse_seeds(text, "d")
        assert sf.pending == []

    def test_pending_seed_clears_processed_fields(self) -> None:
        """Even if a pending entry has 'processed:' metadata, it should be cleared."""
        text = (
            "## Pending\n\n"
            "### URL — https://example.com\n"
            "id: x\n"
            "processed: 2026-04-01\n"
            "session: stale\n"
        )
        sf = parse_seeds(text, "d")
        assert sf.pending[0].processed is None
        assert sf.pending[0].session is None


class TestParseSeedsProcessed:
    def test_processed_seed_with_session(self) -> None:
        text = (
            "## Processed\n\n"
            "### URL — https://example.com/done\n"
            "id: done1\n"
            "priority: high\n"
            "added: 2026-04-10\n"
            "processed: 2026-04-11\n"
            "session: 20260411-abc\n"
            "result: ingested as 2026-04-11-foo.md\n"
        )
        sf = parse_seeds(text, "d")
        assert len(sf.processed) == 1
        seed = sf.processed[0]
        assert seed.processed == date(2026, 4, 11)
        assert seed.session == "20260411-abc"
        assert seed.result == "ingested as 2026-04-11-foo.md"


# ── serialize + round-trip ────────────────────────────────────────────────────


class TestSerializeAndRoundTrip:
    def test_serialize_empty_file(self) -> None:
        sf = SeedsFile(domain="d")
        text = serialize_seeds(sf)
        assert "# d Research Seeds" in text
        assert "## Pending" in text
        assert "## Processed" in text

    def test_round_trip_stable(self) -> None:
        original = SeedsFile(
            domain="test",
            pending=[
                Seed(
                    id="seed1",
                    kind=SeedKind.URL,
                    value="https://example.com/a",
                    notes="hello",
                    priority=SeedPriority.HIGH,
                    added=date(2026, 4, 12),
                ),
                Seed(
                    id="seed2",
                    kind=SeedKind.TOPIC,
                    value="agents",
                    priority=SeedPriority.MEDIUM,
                    added=date(2026, 4, 11),
                ),
            ],
            processed=[
                Seed(
                    id="seed3",
                    kind=SeedKind.URL,
                    value="https://example.com/done",
                    priority=SeedPriority.LOW,
                    added=date(2026, 4, 9),
                    processed=date(2026, 4, 10),
                    session="abc",
                    result="ingested",
                ),
            ],
        )
        text1 = serialize_seeds(original)
        parsed = parse_seeds(text1, "test")
        text2 = serialize_seeds(parsed)
        assert text1 == text2

    def test_round_trip_preserves_all_fields(self) -> None:
        seed = Seed(
            id="abc",
            kind=SeedKind.NOTE,
            value="a note",
            notes="extra context",
            priority=SeedPriority.HIGH,
            added=date(2026, 4, 1),
        )
        sf = SeedsFile(domain="t", pending=[seed])
        roundtripped = parse_seeds(serialize_seeds(sf), "t")
        recovered = roundtripped.pending[0]
        assert recovered.id == seed.id
        assert recovered.kind == seed.kind
        assert recovered.value == seed.value
        assert recovered.notes == seed.notes
        assert recovered.priority == seed.priority
        assert recovered.added == seed.added


# ── file I/O ──────────────────────────────────────────────────────────────────


class TestFileIO:
    def test_seeds_path_helper(self, tmp_path: Path) -> None:
        assert seeds_path(tmp_path) == tmp_path / "seeds.md"

    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        sf = load_seeds(tmp_path, "d")
        assert sf.domain == "d"
        assert sf.pending_count() == 0

    def test_write_then_load(self, tmp_path: Path) -> None:
        seed = Seed(
            id="x", kind=SeedKind.URL, value="https://example.com", priority=SeedPriority.HIGH
        )
        sf = SeedsFile(domain="d", pending=[seed])
        write_seeds(tmp_path, sf)
        assert (tmp_path / "seeds.md").exists()
        loaded = load_seeds(tmp_path, "d")
        assert loaded.pending_count() == 1
        assert loaded.pending[0].value == "https://example.com"

    def test_append_seed(self, tmp_path: Path) -> None:
        seed1 = Seed(id="1", kind=SeedKind.URL, value="https://a.example.com")
        sf = append_seed(tmp_path, "d", seed1)
        assert sf.pending_count() == 1

        seed2 = Seed(id="2", kind=SeedKind.TOPIC, value="topic A")
        sf = append_seed(tmp_path, "d", seed2)
        assert sf.pending_count() == 2

        # Reload from disk and verify both are there
        loaded = load_seeds(tmp_path, "d")
        assert [s.id for s in loaded.pending] == ["1", "2"]


# ── mark_processed ────────────────────────────────────────────────────────────


class TestMarkProcessed:
    def test_moves_pending_to_processed(self, tmp_path: Path) -> None:
        seed = Seed(id="x", kind=SeedKind.URL, value="https://example.com")
        append_seed(tmp_path, "d", seed)

        result = mark_processed(tmp_path, "d", "x", session="sess1", result="ingested as foo.md")
        assert result is not None
        assert result.pending_count() == 0
        assert result.processed_count() == 1
        moved = result.processed[0]
        assert moved.id == "x"
        assert moved.session == "sess1"
        assert moved.result == "ingested as foo.md"
        assert moved.processed == date.today()

    def test_unknown_id_returns_none(self, tmp_path: Path) -> None:
        seed = Seed(id="x", kind=SeedKind.URL, value="https://example.com")
        append_seed(tmp_path, "d", seed)
        result = mark_processed(tmp_path, "d", "nope", session="s", result="r")
        assert result is None

    def test_persisted_after_mark_processed(self, tmp_path: Path) -> None:
        seed = Seed(id="x", kind=SeedKind.URL, value="https://example.com")
        append_seed(tmp_path, "d", seed)
        mark_processed(tmp_path, "d", "x", session="s", result="r")

        # Re-read from disk
        loaded = load_seeds(tmp_path, "d")
        assert loaded.pending_count() == 0
        assert loaded.processed_count() == 1
        assert loaded.processed[0].id == "x"

    def test_only_one_of_many_moves(self, tmp_path: Path) -> None:
        for sid in ("a", "b", "c"):
            append_seed(tmp_path, "d", Seed(id=sid, kind=SeedKind.URL, value=f"https://{sid}.com"))
        mark_processed(tmp_path, "d", "b", session="s", result="r")
        loaded = load_seeds(tmp_path, "d")
        assert [s.id for s in loaded.pending] == ["a", "c"]
        assert [s.id for s in loaded.processed] == ["b"]
