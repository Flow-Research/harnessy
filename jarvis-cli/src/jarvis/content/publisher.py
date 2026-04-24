"""Content publisher — approve drafts and push to AnyType.

Manages the lifecycle: draft → approved → pushed-to-AnyType (with anytype_id).
"""

from pathlib import Path

from rich.console import Console

from jarvis.anytype_client import AnyTypeClient
from jarvis.content.frontmatter import find_drafts, parse_frontmatter, update_frontmatter
from jarvis.content.hierarchy import ContentHierarchy

console = Console()


class ContentPublisher:
    """Approves content and pushes to AnyType.

    Attributes:
        hierarchy: ContentHierarchy instance for AnyType structure
        content_root: Local root directory for content files
    """

    def __init__(
        self,
        client: AnyTypeClient,
        space_id: str,
        content_root: Path,
        root_collection_name: str | None = None,
    ) -> None:
        self.client = client
        self.space_id = space_id
        self.content_root = content_root
        if root_collection_name is None:
            self.hierarchy = ContentHierarchy(client, space_id)
        else:
            self.hierarchy = ContentHierarchy(client, space_id, root_collection_name)

    def approve_and_push(self, piece_dir: Path) -> str:
        """Approve a content piece and push to AnyType.

        Sets status to 'approved' and writes the anytype_id back to frontmatter.

        Args:
            piece_dir: Path to the piece directory (contains index.md)

        Returns:
            AnyType object ID of the created piece collection
        """
        index_path = piece_dir / "index.md"
        fm, _ = parse_frontmatter(index_path)

        if fm.get("anytype_id"):
            console.print(f"[yellow]Already pushed: {piece_dir.name} (id: {fm['anytype_id']})[/yellow]")
            return fm["anytype_id"]

        console.print(f"[blue]Pushing: {piece_dir.name}[/blue]")
        anytype_id = self.hierarchy.push_piece(piece_dir)

        update_frontmatter(index_path, {
            "status": "approved",
            "anytype_id": anytype_id,
        })

        console.print(f"[green]Approved and pushed: {piece_dir.name} → {anytype_id}[/green]")
        return anytype_id

    def push_pending(self, force: bool = False) -> list[tuple[str, str]]:
        """Push all approved pieces that haven't been pushed yet.

        Args:
            force: If True, re-push even if anytype_id is already set

        Returns:
            List of (piece_name, anytype_id) tuples for pushed pieces
        """
        drafts_dir = self.content_root / "drafts"
        if not drafts_dir.exists():
            console.print("[yellow]No drafts directory found.[/yellow]")
            return []

        results = []
        for piece_dir in find_drafts(drafts_dir, status="approved"):
            index_path = piece_dir / "index.md"
            fm, _ = parse_frontmatter(index_path)

            if fm.get("anytype_id") and not force:
                continue

            anytype_id = self.hierarchy.push_piece(piece_dir)
            update_frontmatter(index_path, {"anytype_id": anytype_id})
            results.append((piece_dir.name, anytype_id))
            console.print(f"[green]Pushed: {piece_dir.name} → {anytype_id}[/green]")

        return results

    def push_strategy(self) -> str:
        """Push the content strategy document to AnyType.

        Returns:
            AnyType object ID of the strategy page
        """
        strategy_path = self.content_root / "content-strategy.md"
        if not strategy_path.exists():
            raise FileNotFoundError(f"No content-strategy.md at {strategy_path}")

        anytype_id = self.hierarchy.push_strategy(strategy_path)
        console.print(f"[green]Strategy pushed → {anytype_id}[/green]")
        return anytype_id

    def list_pieces(self, status: str | None = None) -> list[dict]:
        """List all content pieces with their status.

        Args:
            status: Filter by status (draft, review, approved, published)

        Returns:
            List of dicts with piece info: name, title, status, platform, audience, anytype_id
        """
        drafts_dir = self.content_root / "drafts"
        if not drafts_dir.exists():
            return []

        pieces = []
        for piece_dir in find_drafts(drafts_dir, status=status):
            index_path = piece_dir / "index.md"
            fm, _ = parse_frontmatter(index_path)
            platform_files = [f.stem for f in piece_dir.glob("*.md") if f.name != "index.md"]
            pieces.append({
                "path": piece_dir,
                "name": piece_dir.name,
                "title": fm.get("title", "Untitled"),
                "status": fm.get("status", "unknown"),
                "platform": fm.get("platform", ""),
                "audience": fm.get("audience", ""),
                "scheduled": fm.get("scheduled", ""),
                "anytype_id": fm.get("anytype_id"),
                "platforms": platform_files,
            })

        return pieces

    def status_summary(self) -> dict[str, int]:
        """Get count of pieces by status.

        Returns:
            Dict mapping status to count (e.g., {"draft": 8, "approved": 4})
        """
        all_pieces = self.list_pieces()
        summary: dict[str, int] = {}
        for piece in all_pieces:
            s = piece["status"]
            summary[s] = summary.get(s, 0) + 1
        return summary
