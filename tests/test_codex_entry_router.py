from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "plugins/ygt-harness-router/scripts/codex_entry_router.py"
SPEC = importlib.util.spec_from_file_location("codex_entry_router", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CodexEntryRouterTest(unittest.TestCase):
    def test_turn_start_injects_model_before_forwarding(self) -> None:
        request = {"id": 7, "method": "turn/start", "params": {"threadId": "t", "input": [{"type": "text", "text": "Bu alanı ekle"}]}}
        encoded, receipt = MODULE.route_turn_start_line((json.dumps(request) + "\n").encode())
        routed = json.loads(encoded)
        self.assertEqual(routed["params"]["model"], "gpt-5.6-luna")
        self.assertEqual(routed["params"]["effort"], "xhigh")
        self.assertEqual(receipt["agent"], "luna-worker")

    def test_complex_production_turn_escalates_to_sol(self) -> None:
        request = {"id": 8, "method": "turn/start", "params": {"threadId": "t", "input": [{"type": "text", "text": "Production ortamına deploy et"}]}}
        encoded, receipt = MODULE.route_turn_start_line((json.dumps(request) + "\n").encode())
        self.assertEqual(json.loads(encoded)["params"]["model"], "gpt-5.6-sol")
        self.assertEqual(receipt["agent"], "sol-owner")

    def test_non_turn_and_malformed_lines_are_byte_exact(self) -> None:
        for line in (b'{"id":1,"method":"thread/start","params":{}}\n', b'not-json\n'):
            with self.subTest(line=line):
                routed, receipt = MODULE.route_turn_start_line(line)
                self.assertEqual(routed, line)
                self.assertIsNone(receipt)

    def test_empty_or_non_text_turn_is_unchanged(self) -> None:
        for inputs in ([], [{"type": "image", "url": "x"}]):
            line = (json.dumps({"method": "turn/start", "params": {"threadId": "t", "input": inputs}}) + "\n").encode()
            routed, receipt = MODULE.route_turn_start_line(line)
            self.assertEqual(routed, line)
            self.assertIsNone(receipt)

    def test_cli_exec_routes_prompt_and_preserves_arguments(self) -> None:
        args, receipt = MODULE.routed_cli_args(["exec", "--ephemeral", "Bu alanı ekle"])
        self.assertEqual(args[0], "exec")
        self.assertIn("gpt-5.6-luna", args)
        self.assertIn("--ephemeral", args)
        self.assertEqual(receipt["agent"], "luna-worker")

    def test_cli_stdin_routes_without_putting_prompt_in_argv(self) -> None:
        prompt = "Bu alanı ekle; process listesinde görünmesin"
        args, receipt = MODULE.routed_cli_args(["exec", "-"], prompt)
        self.assertNotIn(prompt, args)
        self.assertEqual(receipt["model"], "gpt-5.6-luna")

    def test_cli_stdin_routes_after_global_options(self) -> None:
        prompt = "Bu alanı ekle"
        args, receipt = MODULE.routed_cli_args(["--strict-config", "exec", "-"], prompt)
        self.assertEqual(args[:2], ["--strict-config", "exec"])
        self.assertIn("gpt-5.6-luna", args)
        self.assertNotIn(prompt, args)
        self.assertEqual(receipt["agent"], "luna-worker")

    def test_management_and_explicit_model_are_passthrough(self) -> None:
        for args in (["plugin", "list"], ["doctor"], ["--strict-config", "doctor", "--summary"], ["exec", "-m", "gpt-5.6-sol", "task"], ["--version"]):
            with self.subTest(args=args):
                routed, receipt = MODULE.routed_cli_args(list(args))
                self.assertEqual(routed, list(args))
                self.assertIsNone(receipt)

    def test_bare_tui_defaults_to_priced_luna(self) -> None:
        args, receipt = MODULE.routed_cli_args([])
        self.assertEqual(args, ["-m", "gpt-5.6-luna", "-c", 'model_reasoning_effort="xhigh"'])
        self.assertEqual(receipt["model"], "gpt-5.6-luna")


if __name__ == "__main__":
    unittest.main()
