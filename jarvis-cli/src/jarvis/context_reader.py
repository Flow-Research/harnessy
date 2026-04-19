"""Context file reader for user preferences.

Supports two-tier context loading:
- Global context: ~/.jarvis/context/ (user-wide preferences)
- Folder context: ./.jarvis/context/ (project-specific overrides)

Folder context extends and overrides global context.
"""

from pathlib import Path

from jarvis.models import UserContext

# Global context directory (user-wide)
GLOBAL_CONTEXT_DIR = Path.home() / ".jarvis" / "context"

# Folder context directory (project-specific)
FOLDER_CONTEXT_DIR = Path(".jarvis") / "context"

# Legacy context path for backwards compatibility
LEGACY_CONTEXT_DIR = Path("context")

# All context file names
CONTEXT_FILES = [
    "preferences.md",
    "patterns.md",
    "constraints.md",
    "priorities.md",
    "goals.md",
    "projects.md",
    "recurring.md",
    "focus.md",
    "blockers.md",
    "calendar.md",
    "delegation.md",
    "decisions.md",
]


def load_context(context_path: Path | None = None) -> UserContext:
    """Load user context from markdown files.

    Loads context from both global and folder levels, merging them.
    Folder-level context overrides global context for each file.

    Args:
        context_path: Optional explicit path. If provided, only loads from there.

    Returns:
        UserContext with merged content from global and folder levels
    """
    if context_path is not None:
        # Explicit path provided - use only that
        return _load_from_path(context_path)

    # Two-tier loading: global + folder (folder overrides global)
    global_ctx = _load_from_path(GLOBAL_CONTEXT_DIR)
    folder_ctx = _load_folder_context()

    return _merge_contexts(global_ctx, folder_ctx)


def load_global_context() -> UserContext:
    """Load only global context from ~/.jarvis/context/.

    Returns:
        UserContext with global preferences
    """
    return _load_from_path(GLOBAL_CONTEXT_DIR)


def load_folder_context() -> UserContext:
    """Load only folder context from ./.jarvis/context/.

    Falls back to legacy ./context/ for backwards compatibility.

    Returns:
        UserContext with folder-specific preferences
    """
    return _load_folder_context()


def _load_folder_context() -> UserContext:
    """Load folder context, checking both new and legacy paths.

    Returns:
        UserContext from folder-level context
    """
    # Try new path first: ./.jarvis/context/
    if FOLDER_CONTEXT_DIR.exists():
        return _load_from_path(FOLDER_CONTEXT_DIR)

    # Fall back to legacy path: ./context/
    if LEGACY_CONTEXT_DIR.exists():
        return _load_from_path(LEGACY_CONTEXT_DIR)

    # No folder context found
    return UserContext()


def _load_from_path(path: Path) -> UserContext:
    """Load context from a specific directory.

    Args:
        path: Directory containing context markdown files

    Returns:
        UserContext with content from that directory
    """
    return UserContext(
        # Core context
        preferences_raw=_read_if_exists(path / "preferences.md"),
        patterns_raw=_read_if_exists(path / "patterns.md"),
        constraints_raw=_read_if_exists(path / "constraints.md"),
        priorities_raw=_read_if_exists(path / "priorities.md"),
        # Extended context
        goals_raw=_read_if_exists(path / "goals.md"),
        projects_raw=_read_if_exists(path / "projects.md"),
        recurring_raw=_read_if_exists(path / "recurring.md"),
        focus_raw=_read_if_exists(path / "focus.md"),
        blockers_raw=_read_if_exists(path / "blockers.md"),
        calendar_raw=_read_if_exists(path / "calendar.md"),
        delegation_raw=_read_if_exists(path / "delegation.md"),
        decisions_raw=_read_if_exists(path / "decisions.md"),
    )


def _merge_contexts(global_ctx: UserContext, folder_ctx: UserContext) -> UserContext:
    """Merge global and folder contexts.

    For each field, folder context overrides global if it has content.
    If folder has no content for a field, global content is used.

    Args:
        global_ctx: Global user context
        folder_ctx: Folder-specific context

    Returns:
        Merged UserContext
    """
    return UserContext(
        # Core context
        preferences_raw=_merge_field(
            global_ctx.preferences_raw, folder_ctx.preferences_raw
        ),
        patterns_raw=_merge_field(global_ctx.patterns_raw, folder_ctx.patterns_raw),
        constraints_raw=_merge_field(
            global_ctx.constraints_raw, folder_ctx.constraints_raw
        ),
        priorities_raw=_merge_field(
            global_ctx.priorities_raw, folder_ctx.priorities_raw
        ),
        # Extended context
        goals_raw=_merge_field(global_ctx.goals_raw, folder_ctx.goals_raw),
        projects_raw=_merge_field(global_ctx.projects_raw, folder_ctx.projects_raw),
        recurring_raw=_merge_field(global_ctx.recurring_raw, folder_ctx.recurring_raw),
        focus_raw=_merge_field(global_ctx.focus_raw, folder_ctx.focus_raw),
        blockers_raw=_merge_field(global_ctx.blockers_raw, folder_ctx.blockers_raw),
        calendar_raw=_merge_field(global_ctx.calendar_raw, folder_ctx.calendar_raw),
        delegation_raw=_merge_field(
            global_ctx.delegation_raw, folder_ctx.delegation_raw
        ),
        decisions_raw=_merge_field(global_ctx.decisions_raw, folder_ctx.decisions_raw),
    )


def _merge_field(global_val: str, folder_val: str) -> str:
    """Merge a single context field.

    Strategy: If folder has content, use it. Otherwise use global.
    For additive merging, folder content can reference global with {{global}}.

    Args:
        global_val: Value from global context
        folder_val: Value from folder context

    Returns:
        Merged value
    """
    folder_stripped = folder_val.strip()

    if not folder_stripped:
        # No folder content, use global
        return global_val

    # Check for {{global}} placeholder for additive merging
    if "{{global}}" in folder_val:
        return folder_val.replace("{{global}}", global_val)

    # Folder content overrides global
    return folder_val


def _read_if_exists(file_path: Path) -> str:
    """Read file content if it exists, otherwise return empty string.

    Args:
        file_path: Path to the file

    Returns:
        File content or empty string
    """
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return ""


def get_context_summary(context: UserContext) -> dict[str, bool]:
    """Get a summary of which context files are loaded.

    Args:
        context: UserContext to summarize

    Returns:
        Dict mapping file name to whether it has content
    """
    return {
        # Core context
        "preferences.md": bool(context.preferences_raw.strip()),
        "patterns.md": bool(context.patterns_raw.strip()),
        "constraints.md": bool(context.constraints_raw.strip()),
        "priorities.md": bool(context.priorities_raw.strip()),
        # Extended context
        "goals.md": bool(context.goals_raw.strip()),
        "projects.md": bool(context.projects_raw.strip()),
        "recurring.md": bool(context.recurring_raw.strip()),
        "focus.md": bool(context.focus_raw.strip()),
        "blockers.md": bool(context.blockers_raw.strip()),
        "calendar.md": bool(context.calendar_raw.strip()),
        "delegation.md": bool(context.delegation_raw.strip()),
        "decisions.md": bool(context.decisions_raw.strip()),
    }


def get_context_locations() -> dict[str, Path | None]:
    """Get the paths where context is loaded from.

    Returns:
        Dict with 'global' and 'folder' paths (None if not exists)
    """
    global_path = GLOBAL_CONTEXT_DIR if GLOBAL_CONTEXT_DIR.exists() else None

    folder_path = None
    if FOLDER_CONTEXT_DIR.exists():
        folder_path = FOLDER_CONTEXT_DIR.resolve()
    elif LEGACY_CONTEXT_DIR.exists():
        folder_path = LEGACY_CONTEXT_DIR.resolve()

    return {
        "global": global_path,
        "folder": folder_path,
    }


def ensure_global_context_dir() -> Path:
    """Ensure global context directory exists.

    Returns:
        Path to global context directory
    """
    GLOBAL_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_CONTEXT_DIR


def ensure_folder_context_dir() -> Path:
    """Ensure folder context directory exists in current directory.

    Returns:
        Path to folder context directory
    """
    FOLDER_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    return FOLDER_CONTEXT_DIR
