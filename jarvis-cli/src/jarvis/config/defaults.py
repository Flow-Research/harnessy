"""Default configuration values for Jarvis."""

DEFAULT_CONFIG_YAML = """\
# Jarvis Configuration
# ====================
# This file configures the Jarvis CLI tool.
# Secrets (API tokens) should be set via environment variables, NOT in this file.

version: 1

# Which backend to use for all operations
# Options: anytype, notion
active_backend: anytype

# Backend-specific configuration
backends:
  anytype:
    # AnyType uses local gRPC connection (localhost:31009)
    # Optionally pre-select a space ID to skip interactive selection
    # default_space_id: "your-space-id"

  # Uncomment and configure to use Notion:
  # notion:
  #   workspace_id: "your-workspace-id"
  #   task_database_id: "your-tasks-db-id"
  #   journal_database_id: "your-journal-db-id"
  #   # Optional: Custom property name mappings
  #   property_mappings:
  #     priority: "Priority"
  #     due_date: "Due Date"
  #     tags: "Tags"
  #     done: "Done"

# Analytics (opt-in)
analytics:
  enabled: false
  metrics_file: "~/.jarvis/metrics.json"
"""

# Valid backend names
VALID_BACKENDS = {"anytype", "notion"}

# Environment variable names for tokens
ENV_NOTION_TOKEN = "JARVIS_NOTION_TOKEN"
ENV_NOTION_TOKEN_FALLBACK = "NOTION_TOKEN"
