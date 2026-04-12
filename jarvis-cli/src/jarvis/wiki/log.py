"""Append-only log writer and reader for wiki domain activity.

Writes human-readable log entries to wiki/log.md and can parse
them back into LogEntry models for programmatic inspection.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from jarvis.wiki.models import LogEntry, LogEntryType

_LOG_RELATIVE = "wiki/log.md"
_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] \[([A-Z]+)\] (.+)$")


class LogAppender:
    """Read and write the wiki activity log."""

    @staticmethod
    def _log_path(domain_root: Path) -> Path:
        return domain_root / _LOG_RELATIVE

    @classmethod
    def append(cls, domain_root: Path, entry: LogEntry) -> None:
        """Append a formatted log entry to wiki/log.md.

        Creates the file with a header if it does not yet exist.

        Args:
            domain_root: Root directory of the wiki domain
            entry: LogEntry to append
        """
        log_path = cls._log_path(domain_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if not log_path.exists():
            # Infer a display name from the directory name
            domain_label = domain_root.name.replace("-", " ").title()
            log_path.write_text(
                f"# {domain_label} Wiki — Compilation Log\n\n---\n\n",
                encoding="utf-8",
            )

        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(entry.format() + "\n")

    @classmethod
    def read(cls, domain_root: Path) -> list[LogEntry]:
        """Parse wiki/log.md back into a list of LogEntry models.

        Lines that do not match the expected format are silently skipped.

        Args:
            domain_root: Root directory of the wiki domain

        Returns:
            Ordered list of LogEntry objects (oldest first)
        """
        log_path = cls._log_path(domain_root)
        if not log_path.exists():
            return []

        entries: list[LogEntry] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            m = _LINE_RE.match(line.strip())
            if not m:
                continue
            ts_str, type_str, description = m.groups()
            try:
                timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
                entry_type = LogEntryType(type_str)
            except (ValueError, KeyError):
                continue
            entries.append(
                LogEntry(
                    timestamp=timestamp,
                    entry_type=entry_type,
                    description=description,
                )
            )
        return entries
