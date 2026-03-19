"""Space model representing a workspace/container in any backend."""

from pydantic import BaseModel, Field


class Space(BaseModel):
    """Represents a workspace/container in any backend.

    Maps to:
    - AnyType Space
    - Notion Workspace
    - Obsidian Vault
    - Logseq Graph
    """

    id: str = Field(description="Backend-specific space identifier")
    name: str = Field(description="Human-readable space name")
    backend: str = Field(description="Backend type (anytype, notion, etc.)")

    model_config = {"frozen": True}  # Immutable
