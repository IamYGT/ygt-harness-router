from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "plugins/ygt-harness-router/scripts/route_exec.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("route_exec", LAUNCHER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RouteExecContractTest(unittest.TestCase):
    def test_creation_intents_are_write_capable_luna_tasks(self) -> None:
        module = load_launcher()
        cases = (
            ("Bir hesap makinesi yap", "yap"),
            ("Bir hesap makinesi yaz", "yaz"),
            ("Bu bileşeni geliştir", "geliştir"),
            ("Bu ekranı hazırla", "hazırla"),
            ("Bir hesap makinesi üret", "üret"),
            ("Build a calculator", "build"),
            ("Create a calculator", "create"),
            ("Implement a calculator", "implement"),
            ("Generate a calculator", "generate"),
        )
        for prompt, intent in cases:
            with self.subTest(intent=intent):
                task = module.classify_prompt(prompt)
                decision = module.router.route(task)
                self.assertTrue(task["writes"])
                self.assertTrue(task["clear_done"])
                self.assertEqual(decision.model, "gpt-5.6-luna")
                self.assertEqual(decision.agent, "luna-worker")
                self.assertEqual(decision.reasoning_effort, "xhigh")

    def test_broad_research_prompt_populates_delegation_and_context_signals(self) -> None:
        module = load_launcher()
        task = module.classify_prompt("Tüm repoyu çoklu agent ile araştır, mimariyi karşılaştır ve raporla")
        decision = module.router.route(task)
        self.assertGreaterEqual(decision.delegation_score, 60)
        self.assertEqual(decision.max_parallel_children, 3)
        self.assertTrue(task["cross_file_search"])
        self.assertEqual(decision.context_strategy, "serena")

    def test_small_creation_keeps_base_context_without_child_overhead(self) -> None:
        module = load_launcher()
        decision = module.router.route(module.classify_prompt("Bir hesap makinesi yap"))
        self.assertLess(decision.delegation_score, 10)
        self.assertEqual(decision.max_parallel_children, 0)
        self.assertEqual(decision.context_strategy, "base")

    def test_explicit_small_mutation_intake_is_luna_sized(self) -> None:
        module = load_launcher()
        for prompt in (
            "Login alanını local storage içinde tutulsun.",
            "Bu butonu ekle ve test et.",
            "Fix the copy in this component.",
            "Update this single config value.",
        ):
            with self.subTest(prompt=prompt):
                task = module.classify_prompt(prompt)
                self.assertTrue(task["writes"])
                self.assertTrue(task["clear_done"])
                self.assertEqual(task["estimated_files"], 3)

    def test_read_only_and_high_impact_prompts_are_not_small_writes(self) -> None:
        module = load_launcher()
        cases = (
            ("Bu kodu analiz et ve raporla", False, False),
            ("Production ortamına deploy et", True, True),
            ("Canlıya yayınla ve smoke yap", True, True),
        )
        for prompt, writes, production in cases:
            with self.subTest(prompt=prompt):
                task = module.classify_prompt(prompt)
                self.assertEqual(task["writes"], writes)
                self.assertEqual(task["production"], production)

    def test_build_command_uses_price_winning_luna_for_small_write(self) -> None:
        module = load_launcher()
        decision = module.router.route(module.classify_prompt("Bu alanı ekle ve test et"))
        command = module.build_command(decision, Path("/tmp/project"), "Bu alanı ekle ve test et", [])
        self.assertEqual(command[0:2], ["/usr/local/bin/codex.real", "exec"])
        self.assertIn("gpt-5.6-luna", command)
        self.assertIn("workspace-write", command)
        self.assertIn('model_reasoning_effort="xhigh"', command)
        self.assertIn("mcp_servers.serena.enabled=false", command)
        self.assertNotIn("context-mode", command)

    def test_context_strategy_maps_to_serena_and_context_profiles(self) -> None:
        module = load_launcher()
        fixtures = (
            ({"clear_done": True, "cross_file_search": True}, "serena", "mcp_servers.serena.enabled=true"),
            ({"clear_done": True, "large_tool_output": True}, "context-mode", "context-mode"),
            ({"clear_done": True, "cross_file_search": True, "long_session": True}, "context-lab", "context-lab"),
        )
        for task, strategy, marker in fixtures:
            with self.subTest(strategy=strategy):
                decision = module.router.route(task)
                command = module.build_command(decision, Path("/tmp/project"), "inspect", [])
                self.assertEqual(decision.context_strategy, strategy)
                self.assertIn(marker, command)

    def test_cli_dry_run_is_json_and_never_spawns_codex(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(LAUNCHER), "--cwd", directory, "--dry-run", "Bu alanı ekle"],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"]["agent"], "luna-worker")
        self.assertEqual(payload["command"][0:2], ["/usr/local/bin/codex.real", "exec"])

    def test_cli_explicit_luna_write_override_uses_luna_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(LAUNCHER), "--cwd", directory, "--dry-run",
                 "--task-json", '{"task_type":"luna_write"}', "Bu alanı ekle"],
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["decision"]["agent"], "luna-worker")
        self.assertIn("gpt-5.6-luna", payload["command"])

    def test_execute_returns_child_exit_code_without_shell_interpolation(self) -> None:
        module = load_launcher()
        with patch.object(module.subprocess, "run") as run:
            run.return_value.returncode = 7
            result = module.execute(["codex", "exec", "-"], "literal;not-shell")
        self.assertEqual(result, 7)
        run.assert_called_once_with(
            ["codex", "exec", "-"], input="literal;not-shell", text=True, check=False
        )

    def test_empty_prompt_and_missing_cwd_fail_before_execution(self) -> None:
        module = load_launcher()
        with self.assertRaisesRegex(ValueError, "prompt"):
            module.classify_prompt("   ")
        completed = subprocess.run(
            [sys.executable, str(LAUNCHER), "--cwd", "/definitely/missing", "--dry-run", "fix it"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("working directory", completed.stderr)


if __name__ == "__main__":
    unittest.main()
