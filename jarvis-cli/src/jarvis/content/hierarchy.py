"""Content hierarchy manager for AnyType integration.

Manages the Flow Content → Year → Month → Piece structure in AnyType.
Each content piece is a collection containing index + platform-specific pages.
"""

from pathlib import Path

from jarvis.anytype_client import AnyTypeClient
from jarvis.content.frontmatter import parse_frontmatter


MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class ContentHierarchy:
    """Manages Flow Content → Year → Month → Piece hierarchy in AnyType.

    Mirrors the local folder structure:
        drafts/2026/Apr/02-flow-thesis-thread/
    As AnyType collections:
        Flow Content → 2026 → April → 02 - Your AI Agent Should Have a Job

    Attributes:
        client: AnyType client instance
        space_id: AnyType space ID to work in
    """

    def __init__(self, client: AnyTypeClient, space_id: str) -> None:
        self.client = client
        self.space_id = space_id
        self._root_id: str | None = None
        self._year_cache: dict[int, str] = {}
        self._month_cache: dict[tuple[int, int], str] = {}

    def get_content_root(self) -> str:
        """Get or create the Flow Content top-level collection."""
        if self._root_id:
            return self._root_id
        self._root_id = self.client.get_or_create_collection(
            self.space_id, "Flow Content"
        )
        return self._root_id

    def get_year_container(self, year: int) -> str:
        """Get or create a year container under Flow Content."""
        if year in self._year_cache:
            return self._year_cache[year]
        root_id = self.get_content_root()
        year_id = self.client.get_or_create_container(
            self.space_id, root_id, str(year)
        )
        self._year_cache[year] = year_id
        return year_id

    def get_month_container(self, year: int, month: int) -> str:
        """Get or create a month container under a year."""
        if not 1 <= month <= 12:
            raise ValueError(f"Month must be 1-12, got {month}")
        cache_key = (year, month)
        if cache_key in self._month_cache:
            return self._month_cache[cache_key]
        year_id = self.get_year_container(year)
        month_id = self.client.get_or_create_container(
            self.space_id, year_id, MONTHS[month - 1]
        )
        self._month_cache[cache_key] = month_id
        return month_id

    def push_piece(self, piece_dir: Path) -> str:
        """Push a content piece folder to AnyType.

        Creates a collection for the piece, then adds pages for each .md file.

        Args:
            piece_dir: Local directory containing index.md + platform files

        Returns:
            AnyType object ID of the piece collection

        Raises:
            FileNotFoundError: If index.md doesn't exist in piece_dir
            ValueError: If frontmatter is missing required fields
        """
        index_path = piece_dir / "index.md"
        if not index_path.exists():
            raise FileNotFoundError(f"No index.md in {piece_dir}")

        fm, _ = parse_frontmatter(index_path)
        title = fm.get("title", piece_dir.name)
        scheduled = fm.get("scheduled", "")

        # Parse date from scheduled field or folder path
        year, month = self._extract_date(piece_dir, scheduled)

        # Ensure hierarchy
        month_id = self.get_month_container(year, month)

        # Create piece collection: "02 - Your AI Agent Should Have a Job"
        day_prefix = piece_dir.name[:2]
        piece_name = f"{day_prefix} - {title}"
        piece_id = self.client.get_or_create_container(
            self.space_id, month_id, piece_name
        )

        # Push each .md file as a page in the piece collection
        for md_file in sorted(piece_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            page_name = md_file.stem  # "index", "twitter", "blog", etc.
            self.client.create_page(
                self.space_id,
                name=page_name,
                content=content,
                parent_id=piece_id,
            )

        return piece_id

    def push_strategy(self, strategy_path: Path) -> str:
        """Push the content strategy document as a page under Flow Content root.

        Args:
            strategy_path: Path to content-strategy.md

        Returns:
            AnyType object ID of the strategy page
        """
        root_id = self.get_content_root()
        content = strategy_path.read_text(encoding="utf-8")
        return self.client.create_page(
            self.space_id,
            name="Content Strategy",
            content=content,
            parent_id=root_id,
        )

    def _extract_date(self, piece_dir: Path, scheduled: str) -> tuple[int, int]:
        """Extract year and month from scheduled field or folder path.

        Tries scheduled field first (e.g., "2026-04-02"), falls back to
        folder path (e.g., .../drafts/2026/Apr/...).
        """
        # Try scheduled field
        if scheduled:
            parts = str(scheduled).split("-")
            if len(parts) >= 2:
                try:
                    return int(parts[0]), int(parts[1])
                except ValueError:
                    pass

        # Fall back to folder path: .../2026/Apr/...
        parts = piece_dir.parts
        for i, part in enumerate(parts):
            if part.isdigit() and len(part) == 4 and i + 1 < len(parts):
                year = int(part)
                month_str = parts[i + 1]
                # Try abbreviated month name
                month_map = {
                    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
                    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
                    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
                }
                if month_str in month_map:
                    return year, month_map[month_str]
                # Try full month name
                for idx, name in enumerate(MONTHS):
                    if month_str == name:
                        return year, idx + 1

        raise ValueError(
            f"Cannot determine date for {piece_dir}. "
            "Set 'scheduled' in frontmatter or use YYYY/Mon folder structure."
        )

    def clear_cache(self) -> None:
        """Clear all cached collection IDs."""
        self._root_id = None
        self._year_cache.clear()
        self._month_cache.clear()
