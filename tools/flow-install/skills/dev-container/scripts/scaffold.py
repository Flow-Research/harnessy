#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def copy_tree(src: Path, dst: Path, force: bool) -> list[Path]:
    written: list[Path] = []
    for path in sorted(src.rglob("*")):
        relative = path.relative_to(src)
        if "__pycache__" in relative.parts:
            continue
        target = dst / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            raise FileExistsError(f"Refusing to overwrite existing file: {target}")
        shutil.copy2(path, target)
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold the dev-container bundle into a repo")
    parser.add_argument("--output", help="Output directory for the generated bundle root")
    parser.add_argument("--target", help="Deprecated alias for --output")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files in the bundle root")
    args = parser.parse_args()

    if args.output and args.target:
        raise SystemExit("Use either --output or --target, not both")

    script_dir = Path(__file__).resolve().parent
    template_root = script_dir.parent / "templates" / "container"
    destination_arg = args.output or args.target or "."
    destination = Path(destination_arg).expanduser().resolve()

    if not template_root.exists():
        raise SystemExit(f"Missing template root: {template_root}")

    destination.mkdir(parents=True, exist_ok=True)
    written = copy_tree(template_root, destination, args.force)
    for item in written:
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
