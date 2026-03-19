"""Entry capture modes for journal entries."""

import os
import subprocess
import tempfile
from enum import Enum

from rich.console import Console

console = Console()


class CaptureMode(str, Enum):
    """Mode for capturing journal entry content."""

    INLINE = "inline"
    EDITOR = "editor"
    INTERACTIVE = "interactive"
    FILE = "file"


def capture_entry(
    mode: CaptureMode,
    initial_text: str = "",
) -> str | None:
    """Capture journal entry content using the specified mode.

    Args:
        mode: Capture mode to use
        initial_text: Pre-filled text for inline mode

    Returns:
        Entry content or None if cancelled/empty
    """
    if mode == CaptureMode.INLINE:
        return _capture_inline(initial_text)

    elif mode == CaptureMode.EDITOR:
        return _capture_via_editor(initial_text)

    elif mode == CaptureMode.INTERACTIVE:
        return _capture_interactive()

    elif mode == CaptureMode.FILE:
        return _capture_from_file(initial_text)

    return None


def _capture_from_file(file_path: str) -> str | None:
    """Read content from a file path.

    Args:
        file_path: Path to the file to read

    Returns:
        File content or None if file doesn't exist or is empty
    """
    from pathlib import Path

    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return None

    if not path.is_file():
        console.print(f"[red]Not a file: {file_path}[/red]")
        return None

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            console.print(f"[yellow]File is empty: {file_path}[/yellow]")
            return None
        return content
    except (OSError, UnicodeDecodeError) as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        return None


def _capture_inline(text: str) -> str | None:
    """Capture inline text.

    Args:
        text: The text provided by the user

    Returns:
        Trimmed text or None if empty
    """
    stripped = text.strip()
    return stripped if stripped else None


def _capture_via_editor(initial_text: str = "") -> str | None:
    """Open $EDITOR for entry capture.

    Args:
        initial_text: Optional initial content for the file

    Returns:
        Entry content or None if empty/cancelled
    """
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))

    # Create temp file with .md extension for syntax highlighting
    fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="jarvis_journal_")

    try:
        # Write initial content if provided
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if initial_text:
                f.write(initial_text)
            else:
                # Add helpful comment header
                f.write("# Write your journal entry below\n")
                f.write("# Lines starting with # will be removed\n\n")

        # Open editor
        result = subprocess.run([editor, temp_path], check=False)

        if result.returncode != 0:
            console.print("[yellow]Editor closed with non-zero exit code.[/yellow]")
            return None

        # Read content
        with open(temp_path, encoding="utf-8") as f:
            content = f.read()

        # Remove comment lines (lines starting with #)
        lines = content.split("\n")
        lines = [line for line in lines if not line.strip().startswith("#")]
        content = "\n".join(lines).strip()

        return content if content else None

    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found. Set $EDITOR environment variable.[/red]")
        return None
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"[red]Error running editor: {e}[/red]")
        return None
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _capture_interactive() -> str | None:
    """Interactive multi-line capture.

    User types entry line by line. Two empty lines or Ctrl+D finishes.

    Returns:
        Entry content or None if empty/cancelled
    """
    console.print()
    console.print("[dim]Enter your journal entry below.[/dim]")
    console.print("[dim]Press Enter twice or Ctrl+D to finish.[/dim]")
    console.print()

    lines: list[str] = []
    empty_line_count = 0

    try:
        while True:
            try:
                line = input()

                if not line:
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        # Two empty lines = done
                        break
                    lines.append(line)
                else:
                    empty_line_count = 0
                    lines.append(line)

            except EOFError:
                # Ctrl+D pressed
                break

    except KeyboardInterrupt:
        # Ctrl+C pressed - cancel
        console.print()
        console.print("[yellow]Cancelled.[/yellow]")
        return None

    # Remove trailing empty lines
    while lines and not lines[-1]:
        lines.pop()

    content = "\n".join(lines).strip()
    return content if content else None


def determine_capture_mode(
    text: str | None,
    interactive: bool = False,
    force_editor: bool = False,
    file_path: str | None = None,
) -> tuple[CaptureMode, str]:
    """Determine which capture mode to use based on arguments.

    Args:
        text: Optional inline text provided
        interactive: Whether -i/--interactive flag was set
        force_editor: Whether -e/--editor flag was set
        file_path: Optional file path to read content from

    Returns:
        Tuple of (capture mode, initial text)
    """
    if file_path:
        return CaptureMode.FILE, file_path

    if force_editor:
        return CaptureMode.EDITOR, text or ""

    if interactive:
        return CaptureMode.INTERACTIVE, ""

    if text:
        return CaptureMode.INLINE, text

    # No text provided, default to editor
    return CaptureMode.EDITOR, ""
