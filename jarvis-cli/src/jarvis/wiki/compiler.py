"""Compilation pipeline orchestrator for jarvis wiki domains.

Runs the 9-step pipeline: hash-check → parse → summarize → entity extraction →
concept pages → cross-reference → index rebuild → log → manifest update.
"""

from __future__ import annotations

import datetime
import re
import traceback
from pathlib import Path
from typing import Any

import yaml

from jarvis.wiki.backends import WikiBackend, create_backend
from jarvis.wiki.index_builder import IndexBuilder
from jarvis.wiki.log import LogAppender
from jarvis.wiki.manifest import ManifestStore
from jarvis.wiki.models import (
    ArticleType,
    LogEntry,
    LogEntryType,
    SourceType,
    WikiDomain,
)
from jarvis.wiki.parser import (
    SourceParser,
    normalize_for_comparison,
    slug_similarity,
)

# Token-set Jaccard threshold above which two slugs trigger an LLM
# is_same_entity check. Set inclusively at 0.5 so that:
#   - "react" vs "react-agent" (0.5)            → triggers, LLM decides yes
#   - "a2a" vs "a2a-protocol" (0.5)             → triggers, LLM decides yes
#   - "cosmos" vs "cosmos-blockchain" (0.5)     → triggers, LLM decides yes
#   - "react" vs "react-native" (0.5)           → triggers, LLM decides no
#   - "apple-pay" vs "apple-intelligence" (0.33)→ no trigger
# False positives at 0.5 are cheap (one classifier call); false negatives
# would silently re-create duplicates, which is what we are trying to fix.
_SIMILARITY_THRESHOLD = 0.5

# Frontmatter regex (mirror of lint.py — kept local to avoid cross-import).
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a markdown article into (frontmatter dict, body text).

    Returns ({}, text) if no frontmatter block is present or if YAML parsing
    fails. The body retains a leading newline so callers can rejoin without
    introducing blank lines.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(fm, dict):
        return {}, text
    return fm, text[m.end() :]


class _EntityIndex:
    """In-memory canonical-slug → aliases lookup, built from concept files.

    Each compile session rebuilds this from scratch so the source of truth
    stays in concept frontmatter on disk. Mutated as new aliases are discovered
    during a single compile run so subsequent entities see them.
    """

    def __init__(self) -> None:
        # canonical_slug → set of alias slugs
        self._aliases: dict[str, set[str]] = {}
        # any alias slug → canonical slug it resolves to
        self._reverse: dict[str, str] = {}
        # canonical_slug → display name (for is_same_entity prompts)
        self._names: dict[str, str] = {}
        # canonical_slug → short context blurb (first body line)
        self._summaries: dict[str, str] = {}

    def add_canonical(
        self,
        slug: str,
        name: str,
        aliases: list[str],
        summary: str = "",
    ) -> None:
        """Register a canonical concept and any aliases it already declares."""
        canonical = slug.lower()
        self._aliases.setdefault(canonical, set())
        self._reverse[canonical] = canonical
        self._names[canonical] = name
        self._summaries[canonical] = summary
        for alias in aliases:
            self.add_alias(alias, canonical)

    def add_alias(self, alias: str, canonical: str) -> None:
        """Map an alias slug to its canonical slug."""
        from jarvis.wiki.parser import slug_from_title

        # Allow either a slug or a display name as input
        alias_slug = alias.lower() if "-" in alias or alias.islower() else slug_from_title(alias)
        canonical = canonical.lower()
        if not alias_slug or alias_slug == canonical:
            return
        self._aliases.setdefault(canonical, set()).add(alias_slug)
        self._reverse[alias_slug] = canonical

    def lookup(self, slug: str) -> str | None:
        """Resolve a slug to its canonical form, or return None if unknown."""
        return self._reverse.get(slug.lower())

    def find_similar(self, slug: str) -> list[str]:
        """Return canonical slugs whose normalized form or token Jaccard
        suggests they might be the same as the input slug."""
        target = slug.lower()
        target_norm = normalize_for_comparison(target)
        results: list[str] = []
        seen: set[str] = set()
        for canonical in self._aliases:
            if canonical in seen or canonical == target:
                continue
            canonical_norm = normalize_for_comparison(canonical)
            if target_norm and target_norm == canonical_norm:
                results.append(canonical)
                seen.add(canonical)
                continue
            if slug_similarity(target, canonical) >= _SIMILARITY_THRESHOLD:
                results.append(canonical)
                seen.add(canonical)
        return results

    def name_for(self, canonical_slug: str) -> str:
        return self._names.get(canonical_slug.lower(), canonical_slug)

    def summary_for(self, canonical_slug: str) -> str:
        return self._summaries.get(canonical_slug.lower(), "")

    def aliases_for(self, canonical_slug: str) -> list[str]:
        return sorted(self._aliases.get(canonical_slug.lower(), set()))

    def canonical_slugs(self) -> list[str]:
        return sorted(self._aliases.keys())

    def canonical_count(self) -> int:
        return len(self._aliases)

    def alias_count(self) -> int:
        return sum(len(a) for a in self._aliases.values())


# Raw subdirectory names → SourceType mapping
_SOURCE_TYPE_MAP: dict[str, SourceType] = {
    "articles": SourceType.ARTICLE,
    "papers": SourceType.PAPER,
    "notes": SourceType.NOTE,
    "repos": SourceType.REPO,
    "clips": SourceType.CLIP,
}


class WikiCompiler:
    """Orchestrates the 9-step wiki compilation pipeline."""

    def __init__(self, domain_root: Path, schema: WikiDomain) -> None:
        self.domain_root = domain_root
        self.schema = schema
        self._backend: WikiBackend | None = None
        self.manifest = ManifestStore()
        self.log = LogAppender()
        self.index_builder = IndexBuilder()
        self._parser = SourceParser()

    @property
    def backend(self) -> WikiBackend:
        """Lazy-init backend so dry-run skips API key validation."""
        if self._backend is None:
            self._backend = create_backend(self.schema)
        return self._backend

    def compile(
        self,
        force: bool = False,
        source: str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Run the compilation pipeline and return a stats dict.

        Args:
            force: Recompile all sources even if their hash is unchanged
            source: If given, compile only this specific raw file path
            dry_run: Show what would be compiled without calling the LLM
            verbose: Print per-step progress with rich

        Returns:
            Stats dict with keys: sources_compiled, concepts_created,
            concepts_updated, sources_skipped, errors
        """
        console = _get_console(verbose)

        stats: dict[str, Any] = {
            "sources_compiled": 0,
            "concepts_created": 0,
            "concepts_updated": 0,
            "concepts_aliased": 0,
            "sources_skipped": 0,
            "errors": [],
        }

        # Step 1: Collect raw source files to process
        raw_files = self._collect_sources(source)
        if not raw_files:
            console.print("[yellow]No raw source files found.[/yellow]")
            return stats

        console.print(f"Found [bold]{len(raw_files)}[/bold] raw source file(s).")

        # Build the in-memory entity index. Source of truth is each concept's
        # frontmatter (slug + aliases). Rebuilt every compile session — cheap
        # at current scale, deterministic from disk state.
        entity_index = self._build_entity_index()
        if entity_index.canonical_count():
            console.print(
                f"Loaded entity index: {entity_index.canonical_count()} canonical "
                f"concepts, {entity_index.alias_count()} aliases"
            )

        # Concept slugs seen so far — used for cross-referencing later sources.
        concept_slugs = list(entity_index.canonical_slugs())

        for raw_path, src_type in raw_files:
            label = raw_path.name
            try:
                # Step 2: Hash check — skip unchanged unless force
                if not force and not self.manifest.needs_compile(self.domain_root, raw_path):
                    console.print(f"  [dim]skip[/dim] {label} (unchanged)")
                    stats["sources_skipped"] += 1
                    continue

                console.print(f"  [cyan]compile[/cyan] {label}")

                if dry_run:
                    stats["sources_compiled"] += 1
                    continue

                compiled_to: list[str] = []
                self.backend.reset_usage()

                # Step 3: Parse source
                raw_source = self._parser.parse(raw_path, src_type)
                console.print(
                    f"    parsed: {raw_source.word_count} words, title={raw_source.title!r}"
                )

                # Step 4: Summarize → wiki/summaries/<slug>.md
                summary_text = self.backend.summarize(
                    self.schema,
                    source_slug=raw_source.slug,
                    source_type=raw_source.source_type.value,
                    title=raw_source.title,
                    source_date=raw_source.source_date,
                    body_text=raw_source.body_text,
                )
                summary_path = self._write_summary(raw_source.slug, summary_text)
                compiled_to.append(str(summary_path))
                console.print(f"    summary → {summary_path.name}")

                # Step 5: Extract entities
                entities: list[dict[str, Any]] = []
                if self.schema.compile.extract_entities:
                    entities = self.backend.extract_entities(
                        self.schema, summary_text, source_slug=raw_source.slug
                    )
                    console.print(f"    entities: {len(entities)} extracted")

                # Step 6: Create or merge concept pages (with dedup)
                for entity in entities:
                    entity_slug = entity.get("slug", "")
                    if not entity_slug:
                        continue
                    concept_path, outcome = self._upsert_concept(
                        entity,
                        raw_source.slug,
                        summary_text,
                        entity_index,
                    )
                    compiled_to.append(str(concept_path))
                    if outcome == "created":
                        stats["concepts_created"] += 1
                        concept_slugs.append(concept_path.stem)
                        console.print(f"    concept+ {concept_path.stem}")
                    elif outcome == "aliased":
                        stats["concepts_aliased"] += 1
                        console.print(f"    concept= {entity_slug} → {concept_path.stem} (alias)")
                    else:  # "updated"
                        stats["concepts_updated"] += 1
                        console.print(f"    concept~ {concept_path.stem}")

                # Step 7: Cross-reference summary with known concept slugs
                if self.schema.compile.cross_reference and concept_slugs:
                    linked_text = self.backend.cross_reference(
                        self.schema, summary_text, concept_slugs
                    )
                    summary_path.write_text(linked_text, encoding="utf-8")
                    console.print(f"    cross-referenced against {len(concept_slugs)} concepts")

                stats["sources_compiled"] += 1

                # Step 9 (per-source): Update manifest with token cost
                token_cost = self.backend.pop_usage()
                self.manifest.record(
                    self.domain_root,
                    raw_path,
                    compiled_to=compiled_to,
                    token_cost=token_cost,
                )

            except Exception as exc:  # noqa: BLE001
                msg = f"{label}: {exc}"
                stats["errors"].append(msg)
                console.print(f"  [red]error[/red] {msg}")
                if verbose:
                    console.print(traceback.format_exc())

        # Step 8: Rebuild index.md after all sources
        if stats["sources_compiled"] > 0:
            console.print("Rebuilding index.md…")
            self.index_builder.rebuild(self.domain_root, self.schema)

        # Stamp last_full_compile when this run was unfiltered
        # (i.e. evaluated every raw source, even if some were unchanged).
        if source is None and not dry_run and not stats["errors"]:
            self.manifest.mark_full_compile(self.domain_root)

        # Step 9 (full): Append compile log entry
        description = (
            f"Compiled {stats['sources_compiled']} sources. "
            f"Created {stats['concepts_created']} concepts, "
            f"updated {stats['concepts_updated']}, "
            f"aliased {stats['concepts_aliased']}. "
            f"Skipped {stats['sources_skipped']}. "
            f"Errors: {len(stats['errors'])}."
        )
        self.log.append(
            self.domain_root,
            LogEntry(
                entry_type=LogEntryType.COMPILE,
                description=description,
            ),
        )

        return stats

    # ── Private helpers ────────────────────────────────────────────────────────

    def _collect_sources(self, source_filter: str | None) -> list[tuple[Path, SourceType]]:
        """Return (path, SourceType) pairs for raw files to compile."""
        raw_root = self.domain_root / "raw"
        if not raw_root.exists():
            return []

        if source_filter:
            p = Path(source_filter)
            if not p.is_absolute():
                p = self.domain_root / source_filter
            src_type = _infer_source_type(p)
            return [(p, src_type)] if p.exists() else []

        results: list[tuple[Path, SourceType]] = []
        for subdir in sorted(raw_root.iterdir()):
            if not subdir.is_dir():
                continue
            src_type = _SOURCE_TYPE_MAP.get(subdir.name, SourceType.ARTICLE)
            for f in sorted(subdir.iterdir()):
                if f.suffix.lower() in {".md", ".txt", ".pdf"}:
                    results.append((f, src_type))
        return results

    def _existing_concept_slugs(self) -> list[str]:
        """Return slugs of all existing concept pages."""
        concepts_dir = self.domain_root / "wiki" / "concepts"
        if not concepts_dir.exists():
            return []
        return [p.stem for p in concepts_dir.glob("*.md")]

    def _write_summary(self, slug: str, content: str) -> Path:
        """Write summary text to wiki/summaries/<slug>.md."""
        summaries_dir = self.domain_root / "wiki" / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        path = summaries_dir / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def _build_entity_index(self) -> _EntityIndex:
        """Scan existing concept frontmatter and build the in-memory entity index.

        Source of truth: each concept file's `aliases:` frontmatter list.
        Rebuilt every compile session — fast at current scale, deterministic.
        """
        index = _EntityIndex()
        concepts_dir = self.domain_root / "wiki" / "concepts"
        if not concepts_dir.exists():
            return index

        for path in sorted(concepts_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, body = _split_frontmatter(text)
            slug = path.stem
            name = fm.get("title", slug.replace("-", " ").title())
            aliases_raw = fm.get("aliases") or []
            aliases = [a for a in aliases_raw if isinstance(a, str)]
            # First non-blank body line as a short context blurb
            summary = ""
            for line in body.splitlines():
                line = line.strip()
                if line:
                    summary = line[:300]
                    break
            index.add_canonical(slug, name, aliases, summary)
        return index

    def _upsert_concept(
        self,
        entity: dict[str, Any],
        source_slug: str,
        summary_text: str,
        entity_index: _EntityIndex,
    ) -> tuple[Path, str]:
        """Create new, merge into existing, or alias-merge a concept page.

        Resolution order:
            1. Exact slug match in the entity index (canonical OR known alias)
            2. Any extracted alias resolves to an existing canonical
            3. Slug similarity (token Jaccard ≥ threshold OR equal normalized
               form) → confirmed by `backend.is_same_entity()`
            4. No match → create a new canonical concept

        Args:
            entity: Entity dict from extract_entities (name, slug, type,
                description, aliases)
            source_slug: Source slug for attribution
            summary_text: Compiled summary text (unused here; kept in signature
                for future use cases that need fuller context for merging)
            entity_index: In-memory entity index, mutated as new aliases are
                discovered so subsequent entities in the same compile session
                see them.

        Returns:
            Tuple of (concept_path, outcome) where outcome is one of
            "created" | "updated" | "aliased".
        """
        del summary_text  # reserved for future merge-context use
        concepts_dir = self.domain_root / "wiki" / "concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)

        entity_slug = (entity.get("slug") or "").lower()
        if not entity_slug:
            raise ValueError("entity dict missing 'slug'")
        entity_name = entity.get("name") or entity_slug.replace("-", " ").title()
        entity_aliases: list[str] = list(entity.get("aliases") or [])
        entity_desc = entity.get("description") or ""

        # 1. Exact slug match (canonical OR known alias)
        canonical = entity_index.lookup(entity_slug)
        if canonical:
            return self._merge_into_canonical(
                concepts_dir,
                canonical,
                entity,
                source_slug,
                entity_index,
                aliased=(canonical != entity_slug),
            )

        # 2. Any extracted alias resolves to an existing canonical
        from jarvis.wiki.parser import slug_from_title

        for alias in entity_aliases:
            alias_slug = slug_from_title(alias)
            if not alias_slug:
                continue
            canonical = entity_index.lookup(alias_slug)
            if canonical:
                entity_index.add_alias(entity_slug, canonical)
                self._add_alias_to_concept_file(concepts_dir / f"{canonical}.md", entity_slug)
                return self._merge_into_canonical(
                    concepts_dir,
                    canonical,
                    entity,
                    source_slug,
                    entity_index,
                    aliased=True,
                )

        # 3. Slug similarity → LLM confirmation
        for similar in entity_index.find_similar(entity_slug):
            if similar == entity_slug:
                continue
            try:
                same = self.backend.is_same_entity(
                    name_a=entity_name,
                    slug_a=entity_slug,
                    name_b=entity_index.name_for(similar),
                    slug_b=similar,
                    aliases_a=entity_aliases,
                    aliases_b=entity_index.aliases_for(similar),
                    context_a=entity_desc[:200],
                    context_b=entity_index.summary_for(similar)[:200],
                )
            except Exception:  # noqa: BLE001
                # Classifier failure is non-fatal: fall through to create-new.
                same = False
            if same:
                entity_index.add_alias(entity_slug, similar)
                self._add_alias_to_concept_file(concepts_dir / f"{similar}.md", entity_slug)
                return self._merge_into_canonical(
                    concepts_dir,
                    similar,
                    entity,
                    source_slug,
                    entity_index,
                    aliased=True,
                )

        # 4. No match → create a new canonical concept
        return self._create_concept(concepts_dir, entity, source_slug, entity_index)

    def _create_concept(
        self,
        concepts_dir: Path,
        entity: dict[str, Any],
        source_slug: str,
        entity_index: _EntityIndex,
    ) -> tuple[Path, str]:
        """Write a brand-new concept page and register it in the index."""
        entity_slug = entity["slug"].lower()
        name = entity.get("name") or entity_slug.replace("-", " ").title()
        description = entity.get("description") or ""
        entity_type = entity.get("type") or "concept"
        aliases = list(entity.get("aliases") or [])
        aliases_yaml = "\n".join(f"  - {a}" for a in aliases) if aliases else "  []"
        today = datetime.date.today().isoformat()

        content = (
            f"---\n"
            f"title: {name}\n"
            f"type: {ArticleType.CONCEPT.value}\n"
            f"entity_type: {entity_type}\n"
            f"source_slug: {source_slug}\n"
            f"tags:\n  - {entity_type}\n"
            f"aliases:\n{aliases_yaml}\n"
            f"mentioned_in:\n  - {source_slug}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"---\n\n"
            f"{description}\n"
        )
        concept_path = concepts_dir / f"{entity_slug}.md"
        concept_path.write_text(content, encoding="utf-8")
        entity_index.add_canonical(entity_slug, name, aliases, description[:300])
        return concept_path, "created"

    def _merge_into_canonical(
        self,
        concepts_dir: Path,
        canonical_slug: str,
        entity: dict[str, Any],
        source_slug: str,
        entity_index: _EntityIndex,
        aliased: bool,
    ) -> tuple[Path, str]:
        """Merge an entity's information into an existing canonical concept page."""
        concept_path = concepts_dir / f"{canonical_slug}.md"
        if not concept_path.exists():
            # Index referenced a missing file — fall back to creating fresh.
            entity = {**entity, "slug": canonical_slug}
            return self._create_concept(concepts_dir, entity, source_slug, entity_index)

        existing = concept_path.read_text(encoding="utf-8")
        new_info = (
            f"Entity: {entity.get('name', '')}\n"
            f"Type: {entity.get('type', '')}\n"
            f"Description: {entity.get('description', '')}\n"
        )
        merged = self.backend.merge_entity(self.schema, existing, new_info, source_slug)
        concept_path.write_text(merged, encoding="utf-8")
        return concept_path, ("aliased" if aliased else "updated")

    def _add_alias_to_concept_file(self, concept_path: Path, alias_slug: str) -> None:
        """Append a new alias to a concept file's frontmatter `aliases:` list.

        No-op if the alias is already present. Performs an in-place rewrite,
        preserving body and other frontmatter keys.
        """
        if not concept_path.exists() or not alias_slug:
            return
        text = concept_path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        if not fm:
            return
        existing_aliases = fm.get("aliases") or []
        if not isinstance(existing_aliases, list):
            existing_aliases = []
        if alias_slug in existing_aliases:
            return
        fm["aliases"] = [*existing_aliases, alias_slug]
        new_fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
        concept_path.write_text(
            f"---\n{new_fm_text}\n---\n\n{body.lstrip()}",
            encoding="utf-8",
        )


# ── Module-level helpers ───────────────────────────────────────────────────────


def _infer_source_type(path: Path) -> SourceType:
    """Guess SourceType from the path's parent directory name."""
    parent = path.parent.name
    return _SOURCE_TYPE_MAP.get(parent, SourceType.ARTICLE)


def _get_console(verbose: bool) -> Any:
    """Return a rich Console if verbose, else a no-op stub."""
    if verbose:
        try:
            from rich.console import Console

            return Console()
        except ImportError:
            pass
    return _SilentConsole()


class _SilentConsole:
    """No-op console stub used when verbose=False."""

    def print(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        pass
