"""Quick note capture for the life orchestrator.

Appends timestamped notes to daily markdown files at:
  .jarvis/context/private/julian/notes/YYYY/Mon/dd.md

These notes are read by the life orchestrator's collect-state script
and incorporated into daily briefs.
"""

from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

console = Console()

# Default notes directory (relative to project root)
NOTES_DIR = Path(".jarvis/context/private/julian/notes")


def _resolve_notes_dir() -> Path:
    """Find the project root by looking for priorities.md in the julian context."""
    # Walk up from cwd looking for the priorities.md file (only exists at the real project root)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        priorities = parent / ".jarvis" / "context" / "private" / "julian" / "priorities.md"
        if priorities.is_file():
            notes_dir = priorities.parent / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            return notes_dir
    # Fallback: walk up for any .jarvis/context/private/julian/
    for parent in [cwd, *cwd.parents]:
        julian_ctx = parent / ".jarvis" / "context" / "private" / "julian"
        if julian_ctx.is_dir():
            notes_dir = julian_ctx / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            return notes_dir
    # Last resort: use cwd-relative path
    notes_dir = cwd / NOTES_DIR
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _today_file(notes_dir: Path) -> Path:
    """Get today's notes file path: notes/YYYY/Mon/dd.md"""
    now = datetime.now()
    year = str(now.year)
    month = MONTH_NAMES[now.month - 1]
    day = now.strftime("%d")
    day_dir = notes_dir / year / month
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir / f"{day}.md"


def _timestamp() -> str:
    """Current time as HH:MM."""
    return datetime.now().strftime("%H:%M")


def append_note(text: str, category: str | None = None) -> Path:
    """Append a note to today's file. Returns the file path."""
    notes_dir = _resolve_notes_dir()
    filepath = _today_file(notes_dir)

    today_str = datetime.now().strftime("%A, %B %d, %Y")
    timestamp = _timestamp()

    # Create file with header if new
    if not filepath.exists():
        filepath.write_text(f"# Notes — {today_str}\n\n", encoding="utf-8")

    # Format the note
    prefix = f"[{category}] " if category else ""
    line = f"- {timestamp} — {prefix}{text}\n"

    # Append
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line)

    return filepath


@click.command("note")
@click.argument("text", nargs=-1, required=False)
@click.option("-c", "--category", type=click.Choice(
    ["decision", "meeting", "idea", "blocker", "followup", "priority"],
    case_sensitive=False,
), help="Categorize the note")
@click.option("-i", "--interactive", is_flag=True, help="Interactive multi-line input")
def note_command(text: tuple[str, ...], category: str | None, interactive: bool) -> None:
    """Capture a quick note for the daily brief.

    Notes are appended to .jarvis/context/private/julian/notes/YYYY/Mon/dd.md
    and automatically picked up by the life orchestrator's daily brief.

    Examples:
        jarvis note "Decided to deprioritize Sentinel"
        jarvis note -c decision "Parking Anchor until after AA hire"
        jarvis note -c blocker "TAO stake needed for miner registration"
        jarvis note -c meeting "Chizi confirmed OpenAI research for April 7"
        jarvis note -i
    """
    if interactive:
        console.print("[dim]Enter your note (Ctrl+D or empty line to finish):[/dim]")
        lines = []
        try:
            while True:
                line = input()
                if not line and lines:
                    break
                lines.append(line)
        except EOFError:
            pass
        note_text = "\n".join(lines).strip()
    elif text:
        note_text = " ".join(text)
    else:
        console.print("[red]Provide a note as an argument or use -i for interactive mode[/red]")
        raise SystemExit(1)

    if not note_text:
        console.print("[red]Empty note — nothing captured[/red]")
        raise SystemExit(1)

    filepath = append_note(note_text, category)
    cat_display = f" [{category}]" if category else ""
    # Show relative path from notes dir (YYYY/Mon/dd.md)
    notes_dir = _resolve_notes_dir()
    try:
        rel = filepath.relative_to(notes_dir)
    except ValueError:
        rel = filepath.name
    console.print(f"[green]✓[/green] Note captured{cat_display} → {rel}")
