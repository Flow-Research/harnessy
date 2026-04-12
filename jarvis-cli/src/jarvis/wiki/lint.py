"""Wiki quality linter — structural and optional LLM-based checks."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jarvis.wiki.models import LintReport, WikiDomain

# Regex for [[wikilink]] and [[wikilink|display]] syntax
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

# Frontmatter block
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter as a dict (best-effort, no heavy dep)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        import yaml

        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def _body_text(text: str) -> str:
    """Return article body with frontmatter stripped."""
    m = _FRONTMATTER_RE.match(text)
    if m:
        return text[m.end() :]
    return text


def _word_count(text: str) -> int:
    return len(text.split())


class WikiLinter:
    """Run structural (and optional LLM) quality checks across a wiki domain."""

    def __init__(self, domain_root: Path, schema: WikiDomain) -> None:
        self.domain_root = domain_root
        self.schema = schema
        self.wiki_root = domain_root / "wiki"

    # ── public API ────────────────────────────────────────────────────────────

    def lint(self, fix: bool = False) -> LintReport:
        """Run all lint checks and return a LintReport.

        Structural checks run without any LLM. LLM contradiction check is
        skipped if the backend is unavailable.
        """
        from jarvis.wiki.models import LintReport

        issues: list[Any] = []

        # Collect all wiki articles (summaries + concepts)
        articles = self._collect_articles()
        article_slugs = set(articles.keys())

        # Build outlink map: slug → [linked slugs]
        outlink_map: dict[str, list[str]] = {}
        for slug, (path, text) in articles.items():
            body = _body_text(text)
            outlink_map[slug] = _WIKILINK_RE.findall(body)

        # Build inlink map (backlinks): slug → [slugs that link to it]
        inlink_map: dict[str, list[str]] = {s: [] for s in article_slugs}
        for src_slug, targets in outlink_map.items():
            for t in targets:
                if t in inlink_map:
                    inlink_map[t].append(src_slug)

        issues += self._check_orphans(article_slugs, inlink_map, articles)
        issues += self._check_broken_links(outlink_map, article_slugs)
        issues += self._check_stale(articles)
        issues += self._check_thin(articles)
        issues += self._check_uncategorized(articles)
        issues += self._check_missing_summaries()
        issues += self._check_duplicate_concepts(article_slugs)

        health_scores = self._calculate_health_scores(article_slugs, issues)
        domain_score = sum(health_scores.values()) / len(health_scores) if health_scores else 100.0

        return LintReport(
            domain=self.schema.domain,
            total_articles=len(articles),
            issues=issues,
            health_scores=health_scores,
            domain_score=round(domain_score, 1),
        )

    # ── article collection ────────────────────────────────────────────────────

    def _collect_articles(self) -> dict[str, tuple[Path, str]]:
        """Return {slug: (path, text)} for all compiled wiki articles."""
        result: dict[str, tuple[Path, str]] = {}
        for subdir in ("summaries", "concepts", "queries"):
            d = self.wiki_root / subdir
            if not d.exists():
                continue
            for f in d.glob("*.md"):
                slug = f.stem
                try:
                    text = f.read_text(encoding="utf-8")
                    result[slug] = (f, text)
                except Exception:
                    pass
        return result

    # ── structural checks ─────────────────────────────────────────────────────

    def _check_orphans(
        self,
        article_slugs: set[str],
        inlink_map: dict[str, list[str]],
        articles: dict[str, tuple[Path, str]],
    ) -> list[Any]:
        from jarvis.wiki.models import LintIssue, LintSeverity

        issues = []
        for slug in article_slugs:
            fm = _parse_frontmatter(articles[slug][1])
            article_type = fm.get("type", "")
            # index and log pages are intentionally standalone
            if article_type in ("index", "log"):
                continue
            if not inlink_map.get(slug):
                issues.append(
                    LintIssue(
                        article_slug=slug,
                        check="orphan_page",
                        severity=LintSeverity.WARNING,
                        message=f"'{slug}' has no incoming wiki-links",
                    )
                )
        return issues

    def _check_broken_links(
        self,
        outlink_map: dict[str, list[str]],
        article_slugs: set[str],
    ) -> list[Any]:
        from jarvis.wiki.models import LintIssue, LintSeverity

        issues = []
        for src_slug, targets in outlink_map.items():
            for target in targets:
                if target not in article_slugs:
                    issues.append(
                        LintIssue(
                            article_slug=src_slug,
                            check="broken_link",
                            severity=LintSeverity.ERROR,
                            message=f"Broken link [[{target}]] in '{src_slug}'",
                            detail=target,
                        )
                    )
        return issues

    def _check_stale(self, articles: dict[str, tuple[Path, str]]) -> list[Any]:
        from jarvis.wiki.models import LintIssue, LintSeverity

        stale_days = self.schema.compile.stale_days
        cutoff = date.today() - timedelta(days=stale_days)
        issues = []
        for slug, (_, text) in articles.items():
            fm = _parse_frontmatter(text)
            updated = fm.get("updated")
            if updated and isinstance(updated, date) and updated < cutoff:
                age = (date.today() - updated).days
                issues.append(
                    LintIssue(
                        article_slug=slug,
                        check="stale_claim",
                        severity=LintSeverity.WARNING,
                        message=f"'{slug}' not updated in {age} days (threshold: {stale_days})",
                        detail=str(updated),
                    )
                )
        return issues

    def _check_thin(self, articles: dict[str, tuple[Path, str]]) -> list[Any]:
        from jarvis.wiki.models import LintIssue, LintSeverity

        min_words = self.schema.compile.min_article_words
        issues = []
        for slug, (_, text) in articles.items():
            fm = _parse_frontmatter(text)
            if fm.get("type") in ("index", "log", "query"):
                continue
            body = _body_text(text)
            wc = _word_count(body)
            if wc < min_words:
                issues.append(
                    LintIssue(
                        article_slug=slug,
                        check="thin_article",
                        severity=LintSeverity.INFO,
                        message=f"'{slug}' is thin: {wc} words (min: {min_words})",
                        detail=str(wc),
                    )
                )
        return issues

    def _check_uncategorized(self, articles: dict[str, tuple[Path, str]]) -> list[Any]:
        from jarvis.wiki.models import LintIssue, LintSeverity

        issues = []
        for slug, (_, text) in articles.items():
            fm = _parse_frontmatter(text)
            if fm.get("type") in ("index", "log"):
                continue
            if not fm.get("category"):
                issues.append(
                    LintIssue(
                        article_slug=slug,
                        check="uncategorized",
                        severity=LintSeverity.INFO,
                        message=f"'{slug}' has no category assigned",
                    )
                )
        return issues

    def _check_missing_summaries(self) -> list[Any]:
        """Flag raw sources that have no compiled summary in wiki/summaries/."""
        from jarvis.wiki.models import LintIssue, LintSeverity

        raw_root = self.domain_root / "raw"
        summaries_dir = self.wiki_root / "summaries"
        if not raw_root.exists():
            return []

        compiled_slugs: set[str] = set()
        if summaries_dir.exists():
            compiled_slugs = {f.stem for f in summaries_dir.glob("*.md")}

        issues = []
        for subdir in raw_root.iterdir():
            if not subdir.is_dir():
                continue
            for f in subdir.iterdir():
                if f.suffix.lower() in {".md", ".pdf", ".txt"}:
                    slug = f.stem
                    if slug not in compiled_slugs:
                        issues.append(
                            LintIssue(
                                article_slug=slug,
                                check="missing_summary",
                                severity=LintSeverity.INFO,
                                message=f"Raw source '{slug}' has no compiled summary",
                                detail=str(f.relative_to(self.domain_root)),
                            )
                        )
        return issues

    def _check_duplicate_concepts(self, article_slugs: set[str]) -> list[Any]:
        """Flag concept pages that look like duplicates of each other.

        Detection strategy (any of):
            - Same normalized form (suffixes stripped, e.g. ``a2a-protocol``
              and ``a2a`` both normalize to ``a2a``)
            - Token-set Jaccard ≥ 0.6 over hyphen-split tokens

        Concepts that already declare each other as aliases (in frontmatter)
        are skipped — those are *resolved* duplicates, not pending ones.
        """
        from jarvis.wiki.models import LintIssue, LintSeverity
        from jarvis.wiki.parser import normalize_for_comparison, slug_similarity

        concepts_dir = self.wiki_root / "concepts"
        if not concepts_dir.exists():
            return []

        # Build alias adjacency: slug → set of aliases declared in its frontmatter
        alias_map: dict[str, set[str]] = {}
        slugs: list[str] = []
        for f in sorted(concepts_dir.glob("*.md")):
            slug = f.stem
            slugs.append(slug)
            try:
                fm = _parse_frontmatter(f.read_text(encoding="utf-8"))
            except OSError:
                fm = {}
            raw_aliases = fm.get("aliases") or []
            if isinstance(raw_aliases, list):
                alias_map[slug] = {str(a).lower() for a in raw_aliases if a}
            else:
                alias_map[slug] = set()

        def linked(a: str, b: str) -> bool:
            """True iff a and b are already mutually or one-way linked as aliases."""
            return b in alias_map.get(a, set()) or a in alias_map.get(b, set())

        issues: list[Any] = []
        seen: set[frozenset[str]] = set()
        threshold = 0.6

        for i, a in enumerate(slugs):
            a_norm = normalize_for_comparison(a)
            for b in slugs[i + 1 :]:
                pair = frozenset({a, b})
                if pair in seen or linked(a, b):
                    continue
                b_norm = normalize_for_comparison(b)
                normalized_match = bool(a_norm) and a_norm == b_norm
                jaccard = slug_similarity(a, b)
                if not normalized_match and jaccard < threshold:
                    continue
                seen.add(pair)
                reason = (
                    f"normalized form '{a_norm}' matches"
                    if normalized_match
                    else f"token Jaccard {jaccard:.2f}"
                )
                issues.append(
                    LintIssue(
                        article_slug=a,
                        check="duplicate_concept",
                        severity=LintSeverity.WARNING,
                        message=(f"Possible duplicate concepts: '{a}' and '{b}' ({reason})"),
                        detail=b,
                    )
                )
        return issues

    # ── health scoring ────────────────────────────────────────────────────────

    def _calculate_health_scores(
        self, article_slugs: set[str], issues: list[Any]
    ) -> dict[str, int]:
        """Compute a 0-100 health score per article slug."""
        deductions = {
            "broken_link": 15,
            "orphan_page": 10,
            "stale_claim": 10,
            "thin_article": 5,
            "uncategorized": 5,
            "contradiction": 20,
            "duplicate_concept": 5,
            "missing_summary": 0,  # raw-level, not per compiled article
        }
        scores: dict[str, int] = {slug: 100 for slug in article_slugs}
        for issue in issues:
            slug = issue.article_slug
            if slug not in scores:
                continue
            scores[slug] = max(0, scores[slug] - deductions.get(issue.check, 5))
        return scores
