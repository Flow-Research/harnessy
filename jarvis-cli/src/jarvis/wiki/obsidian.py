"""Obsidian vault configuration writer for jarvis wiki domains.

Creates a minimal .obsidian/ directory inside the wiki/ folder so the domain
can be opened directly as an Obsidian vault with useful defaults pre-applied.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from jarvis.wiki.models import WikiDomain


def setup_obsidian_vault(domain_root: Path, schema: WikiDomain) -> None:  # noqa: ARG001
    """Write .obsidian/ config files to the wiki/ directory.

    Creates:
    - wiki/.obsidian/community-plugins.json — recommended plugins list
    - wiki/.obsidian/graph.json — color groups for concepts, queries, summaries
    - wiki/.obsidian/app.json — basic editor/display settings
    """
    obsidian_dir = domain_root / "wiki" / ".obsidian"
    obsidian_dir.mkdir(parents=True, exist_ok=True)

    # Community plugins list (not installed, just noted as recommended)
    community_plugins = ["obsidian-marp", "dataview", "graph-analysis"]
    _write_json(obsidian_dir / "community-plugins.json", community_plugins)

    # Graph view color groups
    graph_config = {
        "colorGroups": [
            {
                "query": "path:concepts",
                "color": {"a": 1, "rgb": 9109759},  # purple
            },
            {
                "query": "path:queries",
                "color": {"a": 1, "rgb": 16744272},  # orange
            },
            {
                "query": "path:summaries",
                "color": {"a": 1, "rgb": 3899154},  # green
            },
        ],
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "showOrphans": True,
        "collapse-filter": False,
        "collapse-color-groups": False,
        "collapse-display": False,
        "collapse-forces": True,
        "collapse-arrows": True,
    }
    _write_json(obsidian_dir / "graph.json", graph_config)

    # Basic app settings
    app_config = {
        "showLineNumber": True,
        "strictLineBreaks": False,
        "defaultViewMode": "source",
        "livePreview": True,
        "readableLineLength": True,
        "tabSize": 2,
        "useTab": False,
        "showInlineTitle": True,
        "showRibbonCommands": True,
        "alwaysUpdateLinks": True,
        "newLinkFormat": "shortest",
        "useMarkdownLinks": False,
    }
    _write_json(obsidian_dir / "app.json", app_config)


def get_obsidian_url(domain_root: Path) -> str:
    """Return an obsidian:// URL that opens the wiki/ folder as a vault.

    Args:
        domain_root: Path to the domain root (e.g. ~/.jarvis/wikis/seas)

    Returns:
        obsidian://open?vault=<absolute-encoded-path-to-wiki>
    """
    wiki_path = (domain_root / "wiki").resolve()
    encoded = quote(str(wiki_path), safe="")
    return f"obsidian://open?vault={encoded}"


def _write_json(path: Path, data: object) -> None:
    """Write JSON to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
