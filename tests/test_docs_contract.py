"""Public-release contract tests for documentation and package metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "ygt-harness-router"


class PublicDocsContractTests(unittest.TestCase):
    def test_required_public_files_exist(self) -> None:
        required = (
            "README.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "docs/architecture.md",
            "docs/configuration.md",
            "docs/privacy.md",
            "docs/validation.md",
            ".github/workflows/ci.yml",
        )
        missing = [path for path in required if not (ROOT / path).is_file()]
        self.assertEqual(missing, [], f"missing release files: {missing}")

    def test_readme_explains_the_quality_first_contract(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        for phrase in (
            "quality-first",
            "capacity-first",
            "install from github",
            "native codex configuration",
            "architecture",
            "privacy and security",
            "limitations and trade-offs",
            "validate a checkout",
        ):
            self.assertIn(phrase, readme)
        self.assertIn("not a blind cost minimizer", readme)
        self.assertIn("does not create an account", readme)

    def test_installation_has_marketplace_and_plugin_commands(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("codex plugin marketplace add IamYGT/ygt-harness-router", readme)
        self.assertIn("codex plugin add ygt-harness-router", readme)
        self.assertIn("codex doctor", readme)
        self.assertNotIn("/root/", readme)
        self.assertNotIn("/opt/codex-harness", readme)
        releasing = (ROOT / "docs/releasing.md").read_text(encoding="utf-8")
        self.assertNotIn("--sparse plugins/ygt-harness-router", readme + releasing)

    def test_manifest_and_marketplace_point_to_the_public_plugin(self) -> None:
        manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], PLUGIN_ROOT.name)
        self.assertRegex(manifest.get("version", ""), r"^\d+\.\d+\.\d+$")
        self.assertIsInstance(manifest.get("interface"), dict)
        entry = next(
            (item for item in marketplace.get("plugins", []) if item.get("name") == PLUGIN_ROOT.name),
            None,
        )
        self.assertIsNotNone(entry, "marketplace must expose the plugin")
        assert entry is not None
        self.assertEqual(entry["source"]["path"], "./plugins/ygt-harness-router")
        self.assertIn(entry["policy"]["installation"], {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"})
        self.assertIn(entry["policy"]["authentication"], {"ON_INSTALL", "ON_USE"})

    def test_public_docs_do_not_include_common_secret_literals(self) -> None:
        paths = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md"]
        paths.extend((ROOT / "docs").glob("*.md"))
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for pattern in (r"sk-[A-Za-z0-9]{20,}", r"ghp_[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}"):
            self.assertIsNone(re.search(pattern, text), pattern)

    def test_ci_is_public_path_independent(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertNotIn("pip install", workflow)
        self.assertIn("plugins/ygt-harness-router", workflow)
        self.assertNotIn("/root/", workflow)
        self.assertNotIn("/opt/codex-harness", workflow)


if __name__ == "__main__":
    unittest.main()
