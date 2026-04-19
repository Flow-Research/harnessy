"""Notion adapter package.

Provides the NotionAdapter for interacting with Notion as a knowledge base.
"""

from .adapter import NotionAdapter
from .mappings import (
    journal_to_notion_properties,
    notion_to_journal_entry,
    notion_to_task,
    task_to_notion_properties,
)

__all__ = [
    "NotionAdapter",
    "notion_to_task",
    "task_to_notion_properties",
    "notion_to_journal_entry",
    "journal_to_notion_properties",
]
