#!/usr/bin/env python3
"""Safely preview or install bundled Codex custom agents."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "agents"


def install(target: Path, *, apply: bool, force: bool) -> list[str]:
    sources = sorted(SOURCE.glob("*.toml"))
    if not sources:
        raise RuntimeError(f"no agent definitions found under {SOURCE}")
    target = target.expanduser()
    collisions = [target / source.name for source in sources if (target / source.name).exists()]
    if collisions and not force:
        joined = ", ".join(str(path) for path in collisions)
        raise FileExistsError(
            f"refusing to overwrite existing agent files: {joined}; review them or pass --force"
        )
    actions: list[str] = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for source in sources:
        destination = target / source.name
        if destination.exists():
            backup = destination.with_suffix(destination.suffix + f".bak.{stamp}")
            actions.append(f"backup {destination} -> {backup}")
            if apply:
                shutil.copy2(destination, backup)
        actions.append(f"install {source} -> {destination}")
        if apply:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".codex" / "agents",
        help="personal or project Codex agents directory",
    )
    parser.add_argument("--apply", action="store_true", help="perform writes; default is preview")
    parser.add_argument("--force", action="store_true", help="back up and replace existing files")
    args = parser.parse_args()
    try:
        actions = install(args.target, apply=args.apply, force=args.force)
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    mode = "applied" if args.apply else "preview"
    print(f"mode={mode}")
    for action in actions:
        print(action)
    if not args.apply:
        print("no files changed; pass --apply to install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
