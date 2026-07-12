#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "plugins/ygt-harness-router/scripts/router.py"
RENDER = ROOT / "plugins/ygt-harness-router/scripts/render_config.py"
spec = importlib.util.spec_from_file_location("router", ROUTER)
assert spec and spec.loader
router = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = router
spec.loader.exec_module(router)


class RouterContractTest(unittest.TestCase):
    def test_unassessed_work_defaults_to_sol(self) -> None:
        result = router.route({})
        self.assertEqual(result.model, "gpt-5.6-sol")
        self.assertIn("insufficient assessment", " ".join(result.reasons))

    def test_clear_repeatable_work_routes_to_luna(self) -> None:
        result = router.route({"clear_done": True, "repeatable": True, "parallel_lanes": 2,
                               "lane_clarity": 20, "parallel_gain": 18, "verification_value": 16,
                               "handoff_quality": 12, "uncertainty": 4, "reasoning_depth": 4})
        self.assertEqual(result.model, "gpt-5.6-luna")
        self.assertEqual(result.delegation, "two_parallel_lanes")
        self.assertEqual(result.max_parallel_children, 2)

    def test_everyday_implementation_routes_to_terra(self) -> None:
        result = router.route({"ambiguity": 8, "risk": 5, "integration": 7, "judgment": 6,
                               "failure_cost": 4, "clarity_gap": 4, "repeatability_gap": 3,
                               "writes": True})
        self.assertEqual(result.model, "gpt-5.6-terra")
        self.assertEqual(result.agent, "terra-worker")

    def test_unknown_write_scope_routes_to_terra_not_read_only_luna(self) -> None:
        result = router.route({"clear_done": True, "repeatable": True, "writes": True,
                               "ambiguity": 1, "risk": 1, "estimated_files": 0})
        self.assertEqual(result.model, "gpt-5.6-terra")
        self.assertEqual(result.agent, "terra-worker")
        self.assertIn("write-capable lane", " ".join(result.reasons))

    def test_small_clear_write_defaults_to_price_winning_luna(self) -> None:
        result = router.route({"clear_done": True, "writes": True, "estimated_files": 3,
                               "ambiguity": 2, "risk": 2, "integration": 3, "judgment": 2,
                               "failure_cost": 2, "clarity_gap": 2, "repeatability_gap": 1})
        self.assertEqual(result.model, "gpt-5.6-luna")
        self.assertEqual(result.agent, "luna-worker")
        self.assertEqual(result.reasoning_effort, "xhigh")
        self.assertEqual(result.context_strategy, "base")

    def test_explicit_luna_write_route_remains_write_capable_luna(self) -> None:
        result = router.route({"clear_done": True, "writes": True, "estimated_files": 3,
                               "ambiguity": 2, "risk": 2, "integration": 3, "judgment": 2,
                               "failure_cost": 2, "clarity_gap": 2, "repeatability_gap": 1,
                               "task_type": "luna_write"})
        self.assertEqual(result.model, "gpt-5.6-luna")
        self.assertEqual(result.agent, "luna-worker")
        self.assertEqual(result.reasoning_effort, "xhigh")

    def test_write_scope_over_three_files_routes_to_terra(self) -> None:
        result = router.route({"clear_done": True, "writes": True, "estimated_files": 4,
                               "ambiguity": 2, "risk": 2})
        self.assertEqual(result.model, "gpt-5.6-terra")
        self.assertEqual(result.agent, "terra-worker")

    def test_failed_gate_never_routes_to_luna_worker(self) -> None:
        result = router.route({"clear_done": True, "writes": True, "estimated_files": 1,
                               "failed_gate": True, "task_type": "luna_write"})
        self.assertEqual(result.model, "gpt-5.6-sol")
        self.assertNotEqual(result.agent, "luna-worker")

    def test_security_and_production_force_sol(self) -> None:
        for key in ("security_sensitive", "production", "evidence_conflict"):
            with self.subTest(key=key):
                result = router.route({key: True, "clear_done": True, "repeatable": True})
                self.assertEqual(result.model, "gpt-5.6-sol")
                self.assertGreaterEqual(result.capability_score, 70)

    def test_failed_gate_changes_escalation_contract(self) -> None:
        result = router.route({"failed_gate": True})
        self.assertEqual(result.model, "gpt-5.6-sol")
        self.assertIn("change approach", result.escalation)

    def test_large_fanout_uses_bounded_waves(self) -> None:
        result = router.route({"parallel_lanes": 6, "lane_clarity": 25, "parallel_gain": 20,
                               "verification_value": 20, "handoff_quality": 15,
                               "uncertainty": 10, "reasoning_depth": 10})
        self.assertEqual(result.delegation, "two_wave_council")
        self.assertEqual(result.max_parallel_children, 3)

    def test_delegation_score_bands_are_deterministic(self) -> None:
        cases = [
            ({}, "local", 0),
            ({"lane_clarity": 10}, "one_bounded_probe", 1),
            ({"lane_clarity": 20, "parallel_gain": 10}, "one_deep_lane", 1),
            ({"lane_clarity": 25, "parallel_gain": 20, "verification_value": 15}, "two_parallel_lanes", 2),
        ]
        for payload, route_name, children in cases:
            with self.subTest(payload=payload):
                result = router.route(payload)
                self.assertEqual(result.delegation, route_name)
                self.assertEqual(result.max_parallel_children, children)

    def test_unknown_and_out_of_range_fields_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            router.route({"price": 1})
        with self.assertRaisesRegex(ValueError, "between"):
            router.route({"risk": 21})
        with self.assertRaisesRegex(ValueError, "between"):
            router.route({"estimated_files": 1001})

    def test_small_single_file_task_bypasses_context_layers(self) -> None:
        result = router.route({"clear_done": True, "repeatable": True, "estimated_files": 1})
        self.assertEqual(result.context_strategy, "base")
        self.assertIn("small bounded task", result.context_reason)

    def test_symbol_or_cross_file_work_routes_to_serena(self) -> None:
        for payload in ({"symbol_navigation": True}, {"cross_file_search": True}, {"estimated_files": 4}):
            with self.subTest(payload=payload):
                self.assertEqual(router.route(payload).context_strategy, "serena")

    def test_large_output_or_long_session_routes_to_context_mode(self) -> None:
        for payload in ({"large_tool_output": True}, {"long_session": True}):
            with self.subTest(payload=payload):
                self.assertEqual(router.route(payload).context_strategy, "context-mode")

    def test_symbol_and_session_pressure_use_combined_context(self) -> None:
        result = router.route({"symbol_navigation": True, "large_tool_output": True})
        self.assertEqual(result.context_strategy, "context-lab")

    def test_unassessed_context_need_defaults_to_combined_quality_route(self) -> None:
        result = router.route({})
        self.assertEqual(result.context_strategy, "context-lab")
        self.assertIn("unassessed", result.context_reason)

    def test_context_strategy_does_not_weaken_security_model_gate(self) -> None:
        result = router.route({"security_sensitive": True, "estimated_files": 1,
                               "clear_done": True, "repeatable": True})
        self.assertEqual(result.model, "gpt-5.6-sol")
        self.assertEqual(result.context_strategy, "base")

    def test_cli_is_json_only_and_reports_invalid_input(self) -> None:
        good = subprocess.run([sys.executable, str(ROUTER)], input='{"clear_done":true}', text=True,
                              capture_output=True, check=False)
        self.assertEqual(good.returncode, 0)
        self.assertEqual(json.loads(good.stdout)["model"], "gpt-5.6-luna")
        self.assertEqual(json.loads(good.stdout)["context_strategy"], "base")
        bad = subprocess.run([sys.executable, str(ROUTER)], input='[]', text=True,
                             capture_output=True, check=False)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(json.loads(bad.stderr)["error"], "task input must be a JSON object")

    def test_config_renderer_is_opt_in_and_prompt_private(self) -> None:
        spec = importlib.util.spec_from_file_location("render_config", RENDER)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        value = module.render(30_000_000, 24_000_000)
        self.assertIn("[features.rollout_budget]", value)
        self.assertIn('model_auto_compact_token_limit_scope = "body_after_prefix"', value)
        self.assertIn("log_user_prompt = false", value)
        self.assertNotIn("endpoint =", value)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "canary.toml"
            run = subprocess.run([sys.executable, str(RENDER), "--output", str(output)], check=False)
            self.assertEqual(run.returncode, 0)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
