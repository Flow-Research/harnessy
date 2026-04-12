"""Schema loader and domain root resolver for jarvis wiki domains.

Handles reading and writing schema.yaml files that define a WikiDomain's
configuration: categories, entity types, LLM settings, and compile options.
"""

from pathlib import Path

import yaml

from jarvis.wiki.models import WikiDomain

WIKIS_ROOT = Path.home() / ".jarvis" / "wikis"


def get_domain_root(domain: str) -> Path:
    """Return the root directory for a wiki domain.

    Args:
        domain: Kebab-case domain identifier (e.g. "seas")

    Returns:
        Path to ~/.jarvis/wikis/<domain>/
    """
    return WIKIS_ROOT / domain


def load_schema(domain: str) -> WikiDomain:
    """Read and parse schema.yaml for the given domain.

    Args:
        domain: Kebab-case domain identifier

    Returns:
        Parsed WikiDomain model

    Raises:
        FileNotFoundError: If schema.yaml does not exist for the domain
    """
    schema_path = get_domain_root(domain) / "schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"No schema.yaml found at {schema_path}")

    raw = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    return WikiDomain.model_validate(raw)


def save_schema(domain: WikiDomain) -> None:
    """Serialize a WikiDomain and write it to schema.yaml.

    Creates the domain root directory if it does not exist.

    Args:
        domain: WikiDomain instance to persist
    """
    domain_root = get_domain_root(domain.domain)
    domain_root.mkdir(parents=True, exist_ok=True)

    schema_path = domain_root / "schema.yaml"
    data = domain.model_dump(mode="json")
    schema_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
