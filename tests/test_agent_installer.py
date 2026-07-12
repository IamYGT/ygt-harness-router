#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/ygt-harness-router/scripts/install_agents.py"
SPEC = importlib.util.spec_from_file_location("install_agents", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AgentInstallerTest(unittest.TestCase):
    def test_preview_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "agents"
            actions = MODULE.install(target, apply=False, force=False)
            self.assertEqual(len(actions), 4)
            self.assertFalse(target.exists())

    def test_apply_installs_all_bundled_agents(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "agents"
            MODULE.install(target, apply=True, force=False)
            self.assertEqual(
                sorted(path.name for path in target.glob("*.toml")),
                [
                    "luna-challenger.toml",
                    "luna-explorer.toml",
                    "sol-specialist.toml",
                    "terra-worker.toml",
                ],
            )

    def test_existing_file_is_refused_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "agents"
            target.mkdir()
            (target / "luna-explorer.toml").write_text("user-owned\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                MODULE.install(target, apply=True, force=False)
            self.assertEqual(sorted(path.name for path in target.iterdir()), ["luna-explorer.toml"])
            self.assertEqual(
                (target / "luna-explorer.toml").read_text(encoding="utf-8"),
                "user-owned\n",
            )

    def test_force_creates_backup_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "agents"
            target.mkdir()
            existing = target / "luna-explorer.toml"
            existing.write_text("user-owned\n", encoding="utf-8")
            MODULE.install(target, apply=True, force=True)
            backups = list(target.glob("luna-explorer.toml.bak.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "user-owned\n")
            self.assertIn('name = "luna-explorer"', existing.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
