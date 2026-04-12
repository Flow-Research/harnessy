"""jarvis.wiki — Personal knowledge wiki subsystem.

Provides domain-scoped wikis backed by compiled Markdown articles,
entity extraction, and cross-referencing.
"""

from jarvis.wiki.models import (
    ArticleFrontmatter,
    ArticleType,
    CategoryDef,
    CompilationFileRecord,
    CompilationManifest,
    CompileConfig,
    IndexEntry,
    LLMConfig,
    LogEntry,
    LogEntryType,
    RawSource,
    SourceType,
    WikiArticle,
    WikiDomain,
)

__all__ = [
    "ArticleFrontmatter",
    "ArticleType",
    "CategoryDef",
    "CompilationFileRecord",
    "CompilationManifest",
    "CompileConfig",
    "IndexEntry",
    "LLMConfig",
    "LogEntry",
    "LogEntryType",
    "RawSource",
    "SourceType",
    "WikiArticle",
    "WikiDomain",
]
