"""Migrate flat content files (dd-slug.md) to folder model (dd-slug/index.md + platform files).

This is a one-time migration for the initial batch of content generated as flat files.
"""

from pathlib import Path

from rich.console import Console

from jarvis.content.frontmatter import parse_frontmatter, render_frontmatter

console = Console()


def migrate_flat_to_folders(drafts_dir: Path) -> int:
    """Convert flat dd-slug.md files to dd-slug/index.md + platform files.

    For each flat .md file directly under a month directory:
    1. Create dd-slug/ folder
    2. Move the file to dd-slug/index.md
    3. Add anytype_id: null to frontmatter if missing
    4. Create a platform-specific copy (e.g., twitter.md) based on the platform frontmatter field

    Already-migrated folders (containing index.md) are skipped.

    Args:
        drafts_dir: Root drafts directory (e.g., .../flow-content/drafts)

    Returns:
        Number of files migrated
    """
    if not drafts_dir.exists():
        console.print(f"[red]Drafts directory not found: {drafts_dir}[/red]")
        return 0

    migrated = 0

    # Find all .md files that are NOT inside a piece folder (i.e., flat files)
    for md_file in sorted(drafts_dir.rglob("*.md")):
        # Skip if this file is already inside a piece folder (has index.md sibling or IS index.md)
        if md_file.name == "index.md":
            continue
        if (md_file.parent / "index.md").exists():
            continue

        # This is a flat file like 02-flow-thesis-thread.md
        slug = md_file.stem  # "02-flow-thesis-thread"
        piece_dir = md_file.parent / slug

        console.print(f"[blue]Migrating: {md_file.name} → {slug}/[/blue]")

        # Create the folder
        piece_dir.mkdir(exist_ok=True)

        # Read and update frontmatter
        fm, body = parse_frontmatter(md_file)
        if "anytype_id" not in fm:
            fm["anytype_id"] = None

        # Write index.md
        index_path = piece_dir / "index.md"
        index_path.write_text(render_frontmatter(fm, body), encoding="utf-8")

        # Create platform-specific file
        platform = fm.get("platform", "blog")
        platform_path = piece_dir / f"{platform}.md"
        # Platform file gets the content without the full frontmatter — just a header
        platform_header = f"# {fm.get('title', slug)}\n\n"
        platform_path.write_text(platform_header + body, encoding="utf-8")

        # Remove the original flat file
        md_file.unlink()

        migrated += 1
        console.print(f"  [green]→ {slug}/index.md + {platform}.md[/green]")

    return migrated
