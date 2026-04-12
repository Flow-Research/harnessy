"""Legacy duplicate-concept cleanup for jarvis wiki domains.

`WikiDedupe` finds existing concept pages that look like duplicates of each
other (same logic as `lint._check_duplicate_concepts`), confirms each pair
with the LLM `is_same_entity` classifier, picks a canonical, merges bodies
via `backend.merge_entity`, updates the canonical's frontmatter to record
the alias, and deletes the secondary file.

This is the cleanup counterpart to Track 1's prevention path. Track 1's
compiler dedup prevents NEW duplicates from being created; this command
collapses the ones already on disk.

Defaults to dry-run because the operations are destructive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from jarvis.wiki.backends import WikiBackend, create_backend
from jarvis.wiki.compiler import _split_frontmatter
from jarvis.wiki.log import LogAppender
from jarvis.wiki.models import LogEntry, LogEntryType, WikiDomain
from jarvis.wiki.parser import normalize_for_comparison, slug_similarity

# Mirrors the threshold used by the compiler's _SIMILARITY_THRESHOLD.
_SIMILARITY_THRESHOLD = 0.5


@dataclass
class MergeProposal:
    """A pair of concepts the dedupe pass thinks should be merged."""

    canonical: str
    secondary: str
    reason: str  # "normalized_form_match" | "jaccard_<n>" | "alias_lookup"
    confirmed: bool = False  # True after LLM is_same_entity returns true
    skipped: bool = False  # True if already linked or out of scope
    note: str = ""


@dataclass
class DedupeReport:
    """Summary of one dedupe pass."""

    domain: str
    total_concepts: int = 0
    candidate_pairs: int = 0
    confirmed_merges: int = 0
    rejected_pairs: int = 0
    proposals: list[MergeProposal] = field(default_factory=list)
    merged_files: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class WikiDedupe:
    """Find and merge legacy duplicate concept pages in a wiki domain."""

    def __init__(self, domain_root: Path, schema: WikiDomain) -> None:
        self.domain_root = domain_root
        self.schema = schema
        self._backend: WikiBackend | None = None

    @property
    def backend(self) -> WikiBackend:
        if self._backend is None:
            self._backend = create_backend(self.schema)
        return self._backend

    def run(
        self,
        dry_run: bool = True,
        confidence: float = 0.75,
        max_pairs: int | None = None,
    ) -> DedupeReport:
        """Find duplicate pairs, confirm with LLM, optionally merge.

        Args:
            dry_run: If True (default), print proposals but make no changes.
            confidence: Minimum LLM confidence required to confirm a merge.
            max_pairs: Stop after considering this many pairs (None = all).
        """
        concepts_dir = self.domain_root / "wiki" / "concepts"
        report = DedupeReport(domain=self.schema.domain)
        if not concepts_dir.exists():
            return report

        concept_files = sorted(concepts_dir.glob("*.md"))
        report.total_concepts = len(concept_files)
        if len(concept_files) < 2:
            return report

        # Load every concept's frontmatter + first body line for is_same_entity context
        meta = self._load_concept_meta(concept_files)

        # Maintain a mutable canonical map: slug → current canonical (transitively closed)
        canonical_of: dict[str, str] = {slug: slug for slug in meta}

        slugs = sorted(meta.keys())
        seen_pairs: set[frozenset[str]] = set()

        for i, a in enumerate(slugs):
            a_norm = normalize_for_comparison(a)
            for b in slugs[i + 1 :]:
                if max_pairs is not None and report.candidate_pairs >= max_pairs:
                    break
                pair = frozenset({a, b})
                if pair in seen_pairs:
                    continue
                # Already collapsed in this run?
                ca = canonical_of[a]
                cb = canonical_of[b]
                if ca == cb:
                    continue

                # Already linked via existing aliases?
                if (
                    b in meta[a]["aliases"]
                    or a in meta[b]["aliases"]
                    or ca in meta[cb]["aliases"]
                    or cb in meta[ca]["aliases"]
                ):
                    continue

                b_norm = normalize_for_comparison(b)
                normalized_match = bool(a_norm) and a_norm == b_norm
                jaccard = slug_similarity(a, b)
                if not normalized_match and jaccard < _SIMILARITY_THRESHOLD:
                    continue

                seen_pairs.add(pair)
                report.candidate_pairs += 1

                reason = "normalized_form_match" if normalized_match else f"jaccard_{jaccard:.2f}"
                proposal = MergeProposal(
                    canonical=ca,
                    secondary=cb,
                    reason=reason,
                )

                # LLM confirmation
                try:
                    same = self.backend.is_same_entity(
                        name_a=meta[ca]["title"],
                        slug_a=ca,
                        name_b=meta[cb]["title"],
                        slug_b=cb,
                        aliases_a=meta[ca]["aliases"],
                        aliases_b=meta[cb]["aliases"],
                        context_a=meta[ca]["context"],
                        context_b=meta[cb]["context"],
                        confidence_threshold=confidence,
                    )
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"is_same_entity failed for {ca} vs {cb}: {exc}")
                    same = False

                if not same:
                    proposal.note = "LLM rejected"
                    report.rejected_pairs += 1
                    report.proposals.append(proposal)
                    continue

                proposal.confirmed = True
                # Pick canonical: more content wins, tiebreak by earlier created date
                winner, loser = self._pick_canonical(ca, cb, meta)
                proposal.canonical = winner
                proposal.secondary = loser

                if dry_run:
                    proposal.note = "would merge (dry-run)"
                    report.proposals.append(proposal)
                    report.confirmed_merges += 1
                    # Update canonical_of so transitively-related pairs in this
                    # run reflect the proposed direction
                    canonical_of[loser] = winner
                    for k, v in list(canonical_of.items()):
                        if v == loser:
                            canonical_of[k] = winner
                    continue

                # Perform the merge
                try:
                    self._do_merge(winner, loser, meta, concepts_dir)
                    report.merged_files.append((winner, loser))
                    proposal.note = f"merged {loser} into {winner}"
                    report.confirmed_merges += 1
                    # Reflect the merge in metadata + canonical_of for the rest
                    # of this run.
                    meta[winner]["aliases"] = sorted(
                        set(meta[winner]["aliases"]) | {loser} | set(meta[loser]["aliases"])
                    )
                    meta.pop(loser, None)
                    canonical_of[loser] = winner
                    for k, v in list(canonical_of.items()):
                        if v == loser:
                            canonical_of[k] = winner
                except Exception as exc:  # noqa: BLE001
                    proposal.note = f"merge failed: {exc}"
                    report.errors.append(f"{loser} → {winner}: {exc}")
                report.proposals.append(proposal)

            if max_pairs is not None and report.candidate_pairs >= max_pairs:
                break

        # Append a log entry summarizing the pass
        if not dry_run and report.merged_files:
            LogAppender.append(
                self.domain_root,
                LogEntry(
                    entry_type=LogEntryType.LINT,  # closest existing type
                    description=(
                        f"Dedupe pass — {len(report.merged_files)} merges, "
                        f"{report.rejected_pairs} rejected"
                    ),
                    metadata={
                        "merged": [
                            {"canonical": canonical, "secondary": secondary}
                            for canonical, secondary in report.merged_files
                        ],
                        "errors": report.errors,
                    },
                ),
            )

        return report

    # ── helpers ─────────────────────────────────────────────────────────────

    def _load_concept_meta(self, files: list[Path]) -> dict[str, dict[str, Any]]:
        """Build {slug: {title, aliases, context, word_count, created}}."""
        out: dict[str, dict[str, Any]] = {}
        for f in files:
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, body = _split_frontmatter(text)
            slug = f.stem
            aliases_raw = fm.get("aliases") or []
            aliases = [str(a).lower() for a in aliases_raw if isinstance(a, (str, int))]
            # First non-blank body line as context
            context = ""
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    context = line[:300]
                    break
            out[slug] = {
                "title": fm.get("title", slug.replace("-", " ").title()),
                "aliases": aliases,
                "context": context,
                "word_count": len(body.split()),
                "created": str(fm.get("created") or ""),
                "path": f,
            }
        return out

    def _pick_canonical(self, a: str, b: str, meta: dict[str, dict[str, Any]]) -> tuple[str, str]:
        """Choose which slug stays (winner) and which gets merged (loser).

        Strategy: more content wins; tiebreak by earlier `created` date;
        final tiebreak alphabetical (so the result is deterministic).
        """
        wa = meta[a]["word_count"]
        wb = meta[b]["word_count"]
        if wa != wb:
            return (a, b) if wa > wb else (b, a)
        ca = meta[a]["created"]
        cb = meta[b]["created"]
        if ca and cb and ca != cb:
            return (a, b) if ca < cb else (b, a)
        return (a, b) if a < b else (b, a)

    def _do_merge(
        self,
        winner: str,
        loser: str,
        meta: dict[str, dict[str, Any]],
        concepts_dir: Path,
    ) -> None:
        """Merge `loser` into `winner` and delete the loser file."""
        winner_path = concepts_dir / f"{winner}.md"
        loser_path = concepts_dir / f"{loser}.md"
        if not winner_path.exists() or not loser_path.exists():
            raise FileNotFoundError(
                f"missing concept file: winner={winner_path.exists()}, loser={loser_path.exists()}"
            )

        existing = winner_path.read_text(encoding="utf-8")
        loser_text = loser_path.read_text(encoding="utf-8")
        loser_fm, loser_body = _split_frontmatter(loser_text)

        new_info = (
            f"Merged from concept '{loser}' "
            f"(title: {loser_fm.get('title', loser)}):\n"
            f"{loser_body.strip()}"
        )
        merged = self.backend.merge_entity(self.schema, existing, new_info, source_slug=loser)

        # Update frontmatter to add the loser slug + its aliases as aliases
        merged_fm, merged_body = _split_frontmatter(merged)
        if merged_fm:
            existing_aliases = merged_fm.get("aliases") or []
            if not isinstance(existing_aliases, list):
                existing_aliases = []
            new_aliases = sorted(
                {*[str(a) for a in existing_aliases], loser, *meta[loser]["aliases"]}
            )
            merged_fm["aliases"] = new_aliases
            new_fm_text = yaml.safe_dump(merged_fm, sort_keys=False, allow_unicode=True).strip()
            merged = f"---\n{new_fm_text}\n---\n\n{merged_body.lstrip()}"

        winner_path.write_text(merged, encoding="utf-8")
        loser_path.unlink()
