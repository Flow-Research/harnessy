"""Index builder for jarvis wiki domains.

Scans all compiled wiki articles, reads their frontmatter, and
regenerates index.md organized by category with a separate concepts table.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jarvis.content.frontmatter import parse_frontmatter
from jarvis.wiki.models import ArticleType, IndexEntry, WikiDomain

_INDEX_PATH = "wiki/index.md"


class IndexBuilder:
    """Rebuild index.md from the current state of all wiki articles."""

    @classmethod
    def rebuild(cls, domain_root: Path, schema: WikiDomain) -> None:
        """Scan all wiki/*.md files and regenerate index.md.

        Reads frontmatter from every .md file under wiki/ (excluding index.md
        and log.md), groups articles by category, lists concepts separately,
        and writes the formatted index.

        Args:
            domain_root: Root directory of the wiki domain
            schema: WikiDomain containing category definitions and metadata
        """
        wiki_dir = domain_root / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)

        entries = cls._collect_entries(wiki_dir)
        content = cls._render(schema, entries)

        index_path = domain_root / _INDEX_PATH
        index_path.write_text(content, encoding="utf-8")

    @classmethod
    def _collect_entries(cls, wiki_dir: Path) -> list[IndexEntry]:
        """Walk wiki_dir and build IndexEntry for each article."""
        entries: list[IndexEntry] = []
        skip = {"index.md", "log.md"}

        for md_path in sorted(wiki_dir.rglob("*.md")):
            if md_path.name in skip:
                continue

            fm, body = parse_frontmatter(md_path)
            if not fm:
                continue

            title = fm.get("title", md_path.stem)
            try:
                article_type = ArticleType(fm.get("type", "summary"))
            except ValueError:
                article_type = ArticleType.SUMMARY

            # Extract first non-empty body line as one-liner fallback
            one_line = fm.get("one_line", "")
            if not one_line:
                for line in body.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        one_line = line[:120]
                        break

            slug = md_path.stem
            entries.append(
                IndexEntry(
                    slug=slug,
                    title=title,
                    article_type=article_type,
                    category=fm.get("category"),
                    one_line=one_line,
                    tags=fm.get("tags") or [],
                    updated=fm.get("updated", datetime.utcnow().date()),
                )
            )
        return entries

    @classmethod
    def _render(cls, schema: WikiDomain, entries: list[IndexEntry]) -> str:
        """Render the full index.md content string."""
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        total = len(entries)

        # Split concepts from regular articles
        concepts = [e for e in entries if e.article_type == ArticleType.CONCEPT]
        articles = [e for e in entries if e.article_type != ArticleType.CONCEPT]

        category_count = len({e.category for e in articles if e.category})

        lines: list[str] = [
            f"# {schema.title} Wiki — Index",
            f"*Last updated: {now}*",
            f"*{total} articles across {category_count} categories*",
            "",
            "---",
            "",
        ]

        # One section per defined category
        for cat in schema.categories:
            cat_articles = [a for a in articles if a.category == cat.id]
            if not cat_articles:
                continue

            lines.append(f"## {cat.label}")
            lines.append("")
            lines.append("| Article | Summary |")
            lines.append("|---------|---------|")
            for entry in sorted(cat_articles, key=lambda e: e.title.lower()):
                lines.append(f"| [[{entry.slug}\\|{entry.title}]] | {entry.one_line} |")
            lines.append("")

        # Uncategorized articles
        uncategorized = [a for a in articles if not a.category]
        if uncategorized:
            lines.append("## Uncategorized")
            lines.append("")
            lines.append("| Article | Summary |")
            lines.append("|---------|---------|")
            for entry in sorted(uncategorized, key=lambda e: e.title.lower()):
                lines.append(f"| [[{entry.slug}\\|{entry.title}]] | {entry.one_line} |")
            lines.append("")

        # Concepts section
        if concepts:
            lines.append("## Concepts")
            lines.append("")
            lines.append("| Concept | Type | Description |")
            lines.append("|---------|------|-------------|")
            for entry in sorted(concepts, key=lambda e: e.title.lower()):
                entity_type = entry.tags[0] if entry.tags else ""
                lines.append(
                    f"| [[{entry.slug}\\|{entry.title}]] | {entity_type} | {entry.one_line} |"
                )
            lines.append("")

        lines.append("---")
        lines.append("*Generated by `jarvis wiki compile`. Do not edit manually.*")
        lines.append("")

        return "\n".join(lines)
