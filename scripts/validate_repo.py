#!/usr/bin/env python3
"""Run the repository's deterministic local validation layers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/ygt-harness-router"
PLUGIN_TOOLS = Path("/opt/codex-harness/codex/skills/.system/plugin-creator/scripts")
SKILL_TOOLS = Path("/opt/codex-harness/codex/skills/.system/skill-creator/scripts")


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    run([sys.executable, "-m", "compileall", "-q", "plugins", "scripts", "tests"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    if PLUGIN_TOOLS.is_dir():
        run([sys.executable, str(PLUGIN_TOOLS / "validate_plugin.py"), str(PLUGIN)])
    for skill in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        if SKILL_TOOLS.is_dir():
            run([sys.executable, str(SKILL_TOOLS / "quick_validate.py"), str(skill.parent)])
    print("OK ygt-harness-router repository validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
