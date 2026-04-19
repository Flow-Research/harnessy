"""Editor integration for task descriptions."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


class EditorCancelledError(Exception):
    """Raised when user cancels editor."""

    pass


def open_editor_for_description(title: str) -> str | None:
    """Open editor for task description.

    Creates a temporary file with a template, opens the user's editor,
    and returns the content after stripping comment lines.

    Args:
        title: Task title (shown in template)

    Returns:
        Description text (stripped of comment lines) or None if empty

    Raises:
        EditorCancelledError: If user cancels (non-zero exit or file deleted)
    """
    editor_env = os.environ.get("EDITOR", "vim")
    # Handle editors with arguments (e.g., "code --wait")
    editor_parts = shlex.split(editor_env)

    # Create template
    template = f"""# Task: {title}
# Add your description below. Lines starting with # are ignored.
# Save and close to create the task. Exit without saving to cancel.

"""

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False,
        prefix="jarvis_task_",
    ) as f:
        f.write(template)
        temp_path = Path(f.name)

    try:
        # Open editor (handle editors with args like "code --wait")
        result = subprocess.run([*editor_parts, str(temp_path)])

        # Check for cancellation (non-zero exit)
        if result.returncode != 0:
            raise EditorCancelledError("Editor exited with non-zero status")

        # Check if file still exists
        if not temp_path.exists():
            raise EditorCancelledError("Temp file was deleted")

        # Read content
        content = temp_path.read_text()

        # Strip comment lines
        lines = [line for line in content.split("\n") if not line.strip().startswith("#")]
        description = "\n".join(lines).strip()

        return description if description else None

    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
