from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "plugins" / "opencode"


def _iter_text_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    files: list[Path] = []
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml"}:
            files.append(path)
    return files


def main() -> int:
    errors: list[str] = []

    skill_dirs = [p for p in SKILLS_ROOT.iterdir() if p.is_dir()] if SKILLS_ROOT.exists() else []
    if not skill_dirs:
        errors.append(f"No skill directories found under {SKILLS_ROOT}")

    files = _iter_text_files(SKILLS_ROOT)

    deprecated_pattern = re.compile(r"CLAUDE_PLUGIN_ROOT")
    unresolved_commands_pattern = re.compile(r"\./commands/[^\s)]+\.md")

    for file_path in files:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        if deprecated_pattern.search(content):
            errors.append(
                f"Deprecated variable CLAUDE_PLUGIN_ROOT found in {file_path.relative_to(ROOT)}"
            )

        if unresolved_commands_pattern.search(content):
            errors.append(
                "Relative command path './commands/*.md' found in "
                f"{file_path.relative_to(ROOT)}; use ${{AGENTS_SKILLS_ROOT}}/<skill>/commands/..."
            )

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"Missing SKILL.md in {skill_dir.relative_to(ROOT)}")
            continue

        skill_content = skill_md.read_text(encoding="utf-8", errors="ignore")
        if "Template paths are resolved from `${AGENTS_SKILLS_ROOT}/" not in skill_content:
            errors.append(
                f"Missing template-resolution declaration in {skill_md.relative_to(ROOT)}"
            )

    if errors:
        print("Skill path validation failed:\n")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Skill path validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
