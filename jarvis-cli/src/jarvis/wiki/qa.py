"""Q&A engine for jarvis wiki domains.

Provides WikiQA which orchestrates the full question-answering pipeline:
index lookup → relevant article selection → answer synthesis → optional file-back.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from jarvis.wiki.backends import create_backend
from jarvis.wiki.log import LogAppender
from jarvis.wiki.models import LogEntry, LogEntryType, WikiDomain


class WikiQA:
    """Orchestrates Q&A against a compiled wiki domain."""

    def __init__(self, domain_root: Path, schema: WikiDomain) -> None:
        self.domain_root = domain_root
        self.schema = schema
        self.backend = create_backend(schema)

    # ── public API ────────────────────────────────────────────────────────────

    def ask(self, question: str, file_back: bool = True) -> dict[str, Any]:
        """Ask a question against the wiki.

        Steps:
        1. Read index.md
        2. backend.identify_relevant → relevant slugs
        3. Read those wiki articles
        4. backend.answer_question → answer dict
        5. File back if synthesis_flag and confidence > 0.7 and file_back
        6. Append QUERY log entry
        7. Return answer dict

        Args:
            question: Natural language question.
            file_back: Write synthesized answers to wiki/queries/.

        Returns:
            Dict with keys: answer, synthesis_flag, confidence, sources_used,
            and optionally filed_to (path of saved file).
        """
        index_content = self._read_index()
        relevant_slugs = self.backend.identify_relevant(self.schema, question, index_content)

        article_texts = self._read_articles(relevant_slugs)
        answer_dict = self.backend.answer_question(self.schema, question, article_texts)

        filed_to: Path | None = None
        if (
            file_back
            and answer_dict.get("synthesis_flag")
            and answer_dict.get("confidence", 0) > 0.7
        ):
            filed_to = self._file_answer(question, answer_dict)
            answer_dict["filed_to"] = str(filed_to)

        LogAppender.append(
            self.domain_root,
            LogEntry(
                entry_type=LogEntryType.QUERY,
                description=f"Q: {question[:120]}",
                metadata={
                    "sources_used": answer_dict.get("sources_used", []),
                    "confidence": answer_dict.get("confidence"),
                    "filed_to": str(filed_to) if filed_to else None,
                },
            ),
        )

        return answer_dict

    # ── private helpers ───────────────────────────────────────────────────────

    def _read_index(self) -> str:
        """Read the wiki index.md, returning empty string if absent."""
        index_path = self.domain_root / "wiki" / "index.md"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return ""

    def _read_articles(self, slugs: list[str]) -> list[tuple[str, str]]:
        """Read article text for each slug.

        Searches wiki/summaries/ and wiki/concepts/ subdirectories.
        Returns list of (slug, text) tuples for articles that exist.
        """
        wiki_dir = self.domain_root / "wiki"
        search_dirs = [
            wiki_dir / "summaries",
            wiki_dir / "concepts",
            wiki_dir,
        ]
        results: list[tuple[str, str]] = []
        for slug in slugs:
            for search_dir in search_dirs:
                candidate = search_dir / f"{slug}.md"
                if candidate.exists():
                    results.append((slug, candidate.read_text(encoding="utf-8")))
                    break
        return results

    def _file_answer(self, question: str, answer_dict: dict[str, Any]) -> Path:
        """Write answer to wiki/queries/YYYY-MM-DD-<slug>.md with frontmatter.

        Args:
            question: Original question.
            answer_dict: Answer dict from backend.answer_question.

        Returns:
            Path of the written file.
        """
        queries_dir = self.domain_root / "wiki" / "queries"
        queries_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.date.today().isoformat()
        slug = _slugify(question)[:60]
        filename = f"{today}-{slug}.md"
        dest = queries_dir / filename

        # Avoid overwriting if file already exists
        counter = 1
        while dest.exists():
            dest = queries_dir / f"{today}-{slug}-{counter}.md"
            counter += 1

        sources = answer_dict.get("sources_used", [])
        confidence = answer_dict.get("confidence", 0.0)
        answer_body = answer_dict.get("answer", "")

        frontmatter_lines = [
            "---",
            f'title: "{question[:100]}"',
            "type: query",
            f"created: {today}",
            f"confidence: {confidence}",
            f"sources_used: {sources}",
            "---",
            "",
        ]
        content = "\n".join(frontmatter_lines) + f"# {question}\n\n{answer_body}\n"
        dest.write_text(content, encoding="utf-8")
        return dest


# ── helpers ───────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert text to lowercase kebab-case slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")
