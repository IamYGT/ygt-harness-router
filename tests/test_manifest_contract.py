#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/ygt-harness-router"


class ManifestContractTest(unittest.TestCase):
    def test_plugin_manifest_is_publishable(self) -> None:
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "ygt-harness-router")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["repository"], "https://github.com/IamYGT/ygt-harness-router")
        self.assertEqual(manifest["license"], "MIT")
        prompts = manifest["interface"]["defaultPrompt"]
        self.assertLessEqual(len(prompts), 3)
        self.assertTrue(all(0 < len(prompt) <= 128 for prompt in prompts))

    def test_repo_marketplace_points_to_the_plugin(self) -> None:
        market = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual(market["name"], "ygt-harness-router")
        self.assertEqual(len(market["plugins"]), 1)
        entry = market["plugins"][0]
        self.assertEqual(entry["name"], "ygt-harness-router")
        self.assertEqual(entry["source"]["path"], "./plugins/ygt-harness-router")
        self.assertEqual(entry["policy"], {"installation": "AVAILABLE", "authentication": "ON_INSTALL"})

    def test_rendered_config_is_valid_toml(self) -> None:
        import importlib.util
        path = PLUGIN / "scripts/render_config.py"
        spec = importlib.util.spec_from_file_location("render_config_contract", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        parsed = tomllib.loads(module.render(30_000_000, 24_000_000))
        self.assertEqual(parsed["model"], "gpt-5.6-sol")
        self.assertEqual(parsed["review_model"], "gpt-5.6-terra")
        self.assertTrue(parsed["features"]["rollout_budget"]["enabled"])
        self.assertFalse(parsed["otel"]["log_user_prompt"])

    def test_public_tree_has_no_placeholders_or_literal_secrets(self) -> None:
        corpus = ""
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                corpus += path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
        placeholder = "[" + "TODO:"
        self.assertNotIn(placeholder, corpus)
        self.assertIsNone(re.search(r"(?:sk-|ghp_|github_pat_)[A-Za-z0-9_\-]{16,}", corpus))
        self.assertNotRegex(corpus, r"/root/\.codex/(?:auth|sessions)")


if __name__ == "__main__":
    unittest.main()
