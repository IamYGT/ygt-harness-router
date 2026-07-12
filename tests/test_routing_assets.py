"""Contract checks for the ygt-harness-router routing assets."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1] / "plugins" / "ygt-harness-router"
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"
CONFIG = ROOT / "config"

EXPECTED_SKILLS = {
    "model-router": ("score", "route receipt", "Sol", "Terra", "Luna"),
    "context-handoff": ("done_when", "changed_paths", "blockers", "next_action"),
    "usage-audit": ("cached", "marginal", "comparable", "privacy"),
    "duplicate-diagnosis": ("fingerprint", "safe duplicate", "unsafe to suppress"),
}
EXPECTED_AGENTS = {
    "luna-explorer": ("gpt-5.6-luna", "xhigh", "read-only"),
    "luna-challenger": ("gpt-5.6-luna", "max", "read-only"),
    "terra-worker": ("gpt-5.6-terra", "high", "workspace-write"),
    "sol-specialist": ("gpt-5.6-sol", "high", "read-only"),
}


def _frontmatter_and_body(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"missing frontmatter: {path}"
    _, frontmatter, body = text.split("---\n", 2)
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values, body


class RoutingAssetsTest(unittest.TestCase):
    def test_all_skills_have_metadata_and_contract_guidance(self) -> None:
        self.assertEqual(
            {path.parent.name for path in SKILLS.glob("*/SKILL.md")},
            set(EXPECTED_SKILLS),
        )
        for name, markers in EXPECTED_SKILLS.items():
            metadata, body = _frontmatter_and_body(SKILLS / name / "SKILL.md")
            self.assertEqual(metadata["name"], name)
            self.assertGreaterEqual(len(metadata.get("description", "")), 40)
            lowered = body.lower()
            for marker in markers:
                self.assertIn(marker.lower(), lowered, f"{marker!r} missing from {name}")
            self.assertLess(len(body.splitlines()), 500)

    def test_custom_agents_have_explicit_model_effort_and_sandbox_contracts(self) -> None:
        self.assertEqual({path.stem for path in AGENTS.glob("*.toml")}, set(EXPECTED_AGENTS))
        for name, (model, effort, sandbox) in EXPECTED_AGENTS.items():
            data = tomllib.loads((AGENTS / f"{name}.toml").read_text(encoding="utf-8"))
            self.assertEqual(data["name"], name)
            self.assertEqual(data["model"], model)
            self.assertEqual(data["model_reasoning_effort"], effort)
            self.assertEqual(data["sandbox_mode"], sandbox)
            self.assertGreaterEqual(len(data["developer_instructions"].strip()), 120)
            self.assertIn("spawn another agent", data["developer_instructions"].lower())

    def test_config_templates_are_valid_and_opt_in(self) -> None:
        rollout = tomllib.loads((CONFIG / "rollout-budget.toml").read_text(encoding="utf-8"))
        otel = tomllib.loads((CONFIG / "otel.toml").read_text(encoding="utf-8"))
        tomllib.loads((CONFIG / "compaction.toml").read_text(encoding="utf-8"))

        self.assertFalse(rollout["features"]["rollout_budget"]["enabled"])
        self.assertFalse(otel["otel"]["log_user_prompt"])
        self.assertEqual(otel["otel"]["metrics_exporter"], "none")
        self.assertEqual(otel["otel"]["trace_exporter"], "none")
        for path in CONFIG.glob("*.toml"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("BEGIN PRIVATE KEY", text)
            self.assertIsNone(re.search(r"(?:sk-|ghp_|Bearer\s+)[A-Za-z0-9._-]{12,}", text))
            self.assertIn("not auto-loaded", text)
