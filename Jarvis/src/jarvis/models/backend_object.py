"""Generic backend object model.

Represents any object from a knowledge base backend (AnyType, Notion, etc.)
in a backend-agnostic way. Unlike Task or JournalEntry, this model preserves
all properties without assuming a specific schema.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PropertyFormat(StrEnum):
    """Known property value formats across backends."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHECKBOX = "checkbox"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    FILES = "files"
    OBJECTS = "objects"  # Relations/links to other objects
    UNKNOWN = "unknown"


class ObjectProperty(BaseModel):
    """A single property on a backend object.

    Stores the property key, display name, format, and value in a
    format-agnostic way so the CLI can display and edit any property.
    """

    key: str
    name: str = ""
    format: PropertyFormat = PropertyFormat.UNKNOWN
    value: Any = None
    raw: dict[str, Any] = Field(default_factory=dict)
    """The original property dict from the backend, preserved for updates."""

    is_system: bool = False
    """Whether this is a system/read-only property (e.g., created_date)."""

    @property
    def display_value(self) -> str:
        """Return a human-readable string of the value."""
        if self.value is None:
            return ""
        if self.format == PropertyFormat.CHECKBOX:
            return "Yes" if self.value else "No"
        if self.format == PropertyFormat.MULTI_SELECT:
            if isinstance(self.value, list):
                return ", ".join(str(v) for v in self.value)
            return str(self.value)
        if self.format == PropertyFormat.DATE:
            # Trim timezone suffix for readability
            val = str(self.value)
            if val.endswith("T00:00:00Z") or val.endswith("+00:00"):
                return val[:10]
            return val
        return str(self.value)


class BackendObject(BaseModel):
    """Generic representation of any backend object.

    This model captures the essential information about any object
    from any backend without prescribing a fixed schema. It preserves
    all properties so the user can inspect and update any field.
    """

    id: str
    space_id: str
    name: str = "Untitled"
    object_type: str = "Unknown"
    """Human-readable type name (e.g., 'Task', 'Page', 'Collection')."""

    type_key: str = ""
    """Backend-specific type identifier (e.g., 'ot-task' for AnyType)."""

    icon: str = ""
    """Emoji or icon identifier."""

    description: str = ""
    snippet: str = ""
    content: str = ""
    """Full body/markdown content if available."""

    properties: list[ObjectProperty] = Field(default_factory=list)
    """All properties on this object."""

    created_at: datetime | None = None
    updated_at: datetime | None = None

    backend: str = ""
    """Which backend this object came from (e.g., 'anytype', 'notion')."""

    raw: dict[str, Any] = Field(default_factory=dict)
    """Complete raw API response, preserved for reference."""

    def get_property(self, key: str) -> ObjectProperty | None:
        """Get a property by key.

        Args:
            key: Property key to look up.

        Returns:
            ObjectProperty if found, None otherwise.
        """
        for prop in self.properties:
            if prop.key == key:
                return prop
        return None

    def get_editable_properties(self) -> list[ObjectProperty]:
        """Return only the non-system, editable properties.

        Returns:
            List of properties that can be updated.
        """
        return [p for p in self.properties if not p.is_system]

    @property
    def type_display(self) -> str:
        """Human-readable type with icon."""
        type_icons = {
            "Task": "[ ]",
            "Page": "#",
            "Collection": "{}",
            "Note": "#",
        }
        icon = type_icons.get(self.object_type, "?")
        return f"{icon} {self.object_type}"
