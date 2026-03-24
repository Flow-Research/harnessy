#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def detect_features(repo_root: Path) -> dict[str, object]:
    recommendations: list[str] = []
    reasons: dict[str, str] = {}
    suggested_base = "debian"
    suggested_package_manager = "apt"

    if (repo_root / "Cargo.toml").exists() or any(repo_root.glob("**/Cargo.toml")):
        recommendations.append("rust")
        reasons["rust"] = "Detected Cargo.toml, so a Rust toolchain is likely useful in the dev container."

    docker_markers = [
        repo_root / "Dockerfile",
        repo_root / "docker-compose.yml",
        repo_root / "docker-compose.yaml",
        repo_root / "compose.yml",
        repo_root / "compose.yaml",
    ]
    if any(marker.exists() for marker in docker_markers):
        recommendations.append("docker")
        reasons["docker"] = "Detected Docker assets, so Docker CLI support is likely useful inside the container."

    if any(marker.exists() and "postgres" in marker.read_text("utf8", errors="ignore").lower() for marker in docker_markers):
        recommendations.append("postgres")
        reasons["postgres"] = "Detected postgres service references, so psql client support is likely useful."

    if (repo_root / "schema.sql").exists() or any(repo_root.glob("**/*.db")):
        recommendations.append("sqlite")
        reasons["sqlite"] = "Detected local SQLite artifacts or schema files."

    if (repo_root / "package.json").exists() and not any(repo_root.glob("**/requirements*.txt")):
        suggested_base = "alpine"
        suggested_package_manager = "apk"

    unique: list[str] = []
    seen: set[str] = set()
    for item in recommendations:
        if item not in seen:
            unique.append(item)
            seen.add(item)

    return {
        "recommended_features": unique,
        "reasons": reasons,
        "suggested_base_family": suggested_base,
        "suggested_package_manager": suggested_package_manager,
        "supported_package_managers": ["apk", "apt"],
    }


def main() -> int:
    repo_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(json.dumps(detect_features(repo_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
