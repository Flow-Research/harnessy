"""Priority enum for task priority levels."""

from enum import Enum


class Priority(str, Enum):
    """Task priority levels.

    Extends str for JSON serialization compatibility.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_string(cls, value: str | None) -> "Priority | None":
        """Parse priority from string, returning None for invalid values.

        Args:
            value: String representation of priority (case-insensitive)

        Returns:
            Priority enum value or None if invalid/None input
        """
        if value is None:
            return None
        try:
            return cls(value.lower())
        except ValueError:
            return None

    def __str__(self) -> str:
        """Return the string value for display."""
        return self.value
