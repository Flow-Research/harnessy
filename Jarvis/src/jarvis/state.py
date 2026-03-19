"""State management for pending suggestions."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.models import Suggestion

# Default data directory
DATA_DIR = Path.home() / ".jarvis"
PENDING_FILE = DATA_DIR / "pending.json"
CONFIG_FILE = DATA_DIR / "config.json"


def save_selected_space(space_id: str) -> None:
    """Save the selected space ID to config.

    Args:
        space_id: AnyType space ID to save
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    config = _load_config()
    config["selected_space_id"] = space_id
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_selected_space() -> str | None:
    """Get the saved space ID from config.

    Returns:
        Space ID or None if not set
    """
    config = _load_config()
    return config.get("selected_space_id")


def clear_selected_space() -> None:
    """Clear the saved space selection."""
    config = _load_config()
    config.pop("selected_space_id", None)
    if config:
        CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    elif CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


def _load_config() -> dict[str, Any]:
    """Load config from disk.

    Returns:
        Config dictionary
    """
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_suggestions(suggestions: list[Suggestion], space_id: str) -> None:
    """Save suggestions to pending.json.

    Args:
        suggestions: List of suggestions to save
        space_id: AnyType space ID these suggestions belong to
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "generated_at": datetime.now().isoformat(),
        "space_id": space_id,
        "suggestions": [_suggestion_to_dict(s) for s in suggestions],
    }

    PENDING_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_suggestions() -> tuple[list[Suggestion], str]:
    """Load pending suggestions from disk.

    Returns:
        Tuple of (suggestions list, space_id)
        Returns empty list and empty string if no pending file
    """
    if not PENDING_FILE.exists():
        return [], ""

    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        suggestions = [_dict_to_suggestion(s) for s in data.get("suggestions", [])]
        space_id = data.get("space_id", "")
        return suggestions, space_id
    except (json.JSONDecodeError, KeyError, ValueError):
        return [], ""


def clear_suggestions() -> None:
    """Remove the pending suggestions file."""
    if PENDING_FILE.exists():
        PENDING_FILE.unlink()


def has_pending_suggestions() -> bool:
    """Check if there are pending suggestions.

    Returns:
        True if pending.json exists and has suggestions
    """
    if not PENDING_FILE.exists():
        return False

    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        suggestions = data.get("suggestions", [])
        return any(s.get("status") == "pending" for s in suggestions)
    except (json.JSONDecodeError, KeyError):
        return False


def _suggestion_to_dict(s: Suggestion) -> dict[str, Any]:
    """Convert Suggestion to JSON-serializable dict.

    Args:
        s: Suggestion to convert

    Returns:
        Dictionary representation
    """
    return {
        "id": s.id,
        "task_id": s.task_id,
        "task_name": s.task_name,
        "current_date": s.current_date.isoformat(),
        "proposed_date": s.proposed_date.isoformat(),
        "reasoning": s.reasoning,
        "confidence": s.confidence,
        "status": s.status,
        "created_at": s.created_at.isoformat(),
    }


def _dict_to_suggestion(d: dict[str, Any]) -> Suggestion:
    """Convert dictionary to Suggestion.

    Args:
        d: Dictionary from JSON

    Returns:
        Suggestion object
    """
    from datetime import date as date_type

    return Suggestion(
        id=d["id"],
        task_id=d["task_id"],
        task_name=d["task_name"],
        current_date=date_type.fromisoformat(d["current_date"]),
        proposed_date=date_type.fromisoformat(d["proposed_date"]),
        reasoning=d["reasoning"],
        confidence=d["confidence"],
        status=d["status"],
        created_at=datetime.fromisoformat(d["created_at"]),
    )
