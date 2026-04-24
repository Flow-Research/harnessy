"""Configuration schema models using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotionConfig(BaseModel):
    """Notion-specific configuration.

    Requires API token via JARVIS_NOTION_TOKEN environment variable.
    """

    workspace_id: str = Field(description="Notion workspace ID")
    task_database_id: str = Field(description="Tasks database ID")
    journal_database_id: str = Field(description="Journal database ID")
    property_mappings: dict[str, str] = Field(
        default_factory=lambda: {
            "priority": "Priority",
            "due_date": "Due Date",
            "tags": "Tags",
            "done": "Done",
            "title": "Name",
            "date": "Date",
        },
        description="Mapping of Jarvis fields to Notion property names",
    )


class AnyTypeConfig(BaseModel):
    """AnyType-specific configuration.

    AnyType uses local gRPC connection (localhost:31009), so minimal config needed.
    """

    default_space_id: str | None = Field(
        default=None,
        description="Optional: Pre-select space ID to skip space selection",
    )


class BackendsConfig(BaseModel):
    """Container for all backend configurations."""

    anytype: AnyTypeConfig = Field(default_factory=AnyTypeConfig)
    notion: NotionConfig | None = Field(
        default=None,
        description="Notion configuration (required if using Notion backend)",
    )


class ContentConfig(BaseModel):
    """Configuration for the content publishing pipeline.

    Values here replace previously-hardcoded identifiers so the CLI is not
    tied to any particular workspace layout or AnyType space/collection name.
    """

    root_path: str | None = Field(
        default=None,
        description=(
            "Local path to the content root directory. May be absolute or "
            "relative to the current working directory / git root. When unset, "
            "the CLI searches `.jarvis/context/private/<user>/content` and "
            "then `<user>/flow-content` as a backwards-compat fallback."
        ),
    )
    anytype_space_name: str | None = Field(
        default=None,
        description=(
            "Case-insensitive name of the AnyType space to target for content "
            "publishing. When unset, the standard space-selection prompt runs."
        ),
    )
    anytype_root_collection: str = Field(
        default="Content",
        description=(
            "Name of the top-level AnyType collection under which the "
            "year/month/piece hierarchy is created."
        ),
    )


class AnalyticsConfig(BaseModel):
    """Analytics configuration (opt-in only)."""

    enabled: bool = Field(default=False)
    metrics_file: str = Field(default="~/.jarvis/metrics.json")


class JarvisConfig(BaseSettings):
    """Root configuration model for Jarvis.

    Configuration is loaded from:
    1. Config file: ~/.jarvis/config.yaml
    2. Environment variables: JARVIS_* prefix

    Environment variables take precedence over config file.
    """

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_nested_delimiter="__",
        extra="ignore",  # Ignore unknown fields
    )

    version: int = Field(default=1, description="Config file version")
    active_backend: Literal["anytype", "notion"] = Field(
        default="anytype",
        description="Which backend to use for all operations",
    )
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    content: ContentConfig = Field(default_factory=ContentConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)

    @field_validator("active_backend")
    @classmethod
    def validate_active_backend(cls, v: str) -> str:
        """Validate active_backend is a known backend type."""
        valid_backends = {"anytype", "notion"}
        if v not in valid_backends:
            raise ValueError(f"Invalid backend: {v}. Must be one of: {valid_backends}")
        return v

    def get_backend_config(self, backend: str | None = None) -> BaseModel:
        """Get the configuration for a specific backend.

        Args:
            backend: Backend name. Uses active_backend if None.

        Returns:
            Backend-specific configuration model.

        Raises:
            ValueError: If backend is not configured.
        """
        target = backend or self.active_backend
        if target == "anytype":
            return self.backends.anytype
        elif target == "notion":
            if self.backends.notion is None:
                raise ValueError(
                    "Notion backend is not configured. "
                    "Add a [backends.notion] section to ~/.jarvis/config.yaml"
                )
            return self.backends.notion
        else:
            raise ValueError(f"Unknown backend: {target}")


def get_config_dir() -> Path:
    """Get the Jarvis configuration directory, creating if needed.

    Returns:
        Path to ~/.jarvis/ directory
    """
    config_dir = Path.home() / ".jarvis"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the Jarvis config file.

    Returns:
        Path to ~/.jarvis/config.yaml
    """
    return get_config_dir() / "config.yaml"
