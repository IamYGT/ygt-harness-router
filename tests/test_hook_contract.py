from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugins" / "ygt-harness-router" / "hooks" / "harness_hook.py"
HOOKS_JSON = ROOT / "plugins" / "ygt-harness-router" / "hooks" / "hooks.json"


def run_hook(event: str, payload: dict, tmp_path: Path, **env_overrides: str) -> tuple[dict, dict, str]:
    telemetry = tmp_path / "telemetry.jsonl"
    state = tmp_path / "state.json"
    env = os.environ.copy()
    env.update(
        {
            "YGT_HARNESS_TELEMETRY_FILE": str(telemetry),
            "YGT_HARNESS_STATE_FILE": str(state),
            "YGT_HARNESS_TELEMETRY": "1",
            **env_overrides,
        }
    )
    completed = subprocess.run(
        [sys.executable, str(HOOK), event],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    output = json.loads(completed.stdout)
    records = [json.loads(line) for line in telemetry.read_text().splitlines()] if telemetry.exists() else []
    state_value = json.loads(state.read_text()) if state.exists() else {}
    return output, {"records": records, "state": state_value}, completed.stderr


def context(output: dict) -> str:
    return output.get("hookSpecificOutput", {}).get("additionalContext", "") or output.get("systemMessage", "")


class HookContractTests(unittest.TestCase):
    def test_hooks_json_declares_all_codex_events_and_command_hooks(self) -> None:
        config = json.loads(HOOKS_JSON.read_text())
        self.assertEqual(
            set(config["hooks"]),
            {"PreToolUse", "PostToolUse", "PreCompact", "PostCompact", "SubagentStart", "SubagentStop", "Stop"},
        )
        for entries in config["hooks"].values():
            command = entries[0]["hooks"][0]
            self.assertEqual(command["type"], "command")
            self.assertIn("harness_hook.py", command["command"])
            self.assertIn("${PLUGIN_ROOT}", command["command"])

    def test_pretool_duplicate_read_fingerprint_is_hashed_and_nonblocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            payload = {"session_id": "test-session", "tool_name": "Bash", "command": "cat project/config.txt"}
            first, _, _ = run_hook("PreToolUse", payload, tmp_path)
            second, evidence, _ = run_hook("PreToolUse", payload, tmp_path)

            self.assertNotIn("permissionDecision", first["hookSpecificOutput"])
            self.assertNotIn("Duplicate read-only fingerprint", context(first))
            self.assertIn("Duplicate read-only fingerprint", context(second))
            record = evidence["records"][-1]
            self.assertTrue(record["read_only"])
            self.assertTrue(record["duplicate_read"])
            self.assertTrue(record["fingerprint"])
            self.assertEqual(len(record["fingerprint"]), 24)
            self.assertNotIn("project/config.txt", json.dumps(evidence))

    def test_budget_checkpoint_and_compaction_reminders_are_observational(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            output, evidence, _ = run_hook(
                "Stop",
                {"session_id": "budget-session", "final": "done", "usage": {"total_tokens": 900}},
                tmp_path,
                YGT_HARNESS_BUDGET_TOKENS="1000",
            )
            self.assertIn("900/1000 tokens", context(output))
            self.assertTrue(evidence["records"][-1]["finalization_ready"])

            compact, evidence, _ = run_hook("PreCompact", {"session_id": "budget-session"}, tmp_path)
            self.assertIn("Checkpoint before compaction", context(compact))
            self.assertTrue(evidence["records"][-1]["checkpoint"])

            pretool, _, _ = run_hook(
                "PreToolUse",
                {"session_id": "budget-session", "tool_name": "Bash", "command": "cat file", "usage": {"total_tokens": 900}},
                tmp_path,
                YGT_HARNESS_BUDGET_TOKENS="1000",
            )
            self.assertIn("900/1000 tokens", context(pretool))

    def test_subagent_stop_requires_receipt_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            run_hook("SubagentStart", {"session_id": "s", "agent_id": "child-1"}, tmp_path)
            stop, evidence, _ = run_hook("SubagentStop", {"session_id": "s", "agent_id": "child-1"}, tmp_path)
            self.assertNotIn("hookSpecificOutput", stop)
            self.assertIn("receipt is incomplete", context(stop))
            self.assertTrue(evidence["records"][-1]["was_active"])
            self.assertFalse(evidence["records"][-1]["receipt_present"])

            receipt = {"status": "completed", "summary": "done", "evidence": "tests passed"}
            complete, evidence, _ = run_hook(
                "SubagentStop", {"session_id": "s", "agent_id": "child-2", "receipt": receipt}, tmp_path
            )
            self.assertEqual(context(complete), "")
            self.assertTrue(evidence["records"][-1]["receipt_present"])

    def test_explicit_generic_policy_can_deny_but_destructive_commands_are_not_special_cased(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            output, evidence, _ = run_hook(
                "PreToolUse",
                {"session_id": "policy", "tool_name": "Bash", "command": "rm -rf ./scratch"},
                tmp_path,
                YGT_HARNESS_POLICY="deny",
            )
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertFalse(evidence["records"][-1]["read_only"])
            self.assertNotIn("rm -rf", json.dumps(evidence))

    def test_unsupported_ask_policy_fails_open_without_invalid_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output, _, _ = run_hook(
                "PreToolUse",
                {"session_id": "policy", "tool_name": "Bash", "command": "echo safe"},
                Path(directory),
                YGT_HARNESS_POLICY="ask",
            )
            self.assertNotIn("permissionDecision", output["hookSpecificOutput"])
            self.assertIn("unsupported", context(output))

    def test_untrusted_tool_label_is_hashed_in_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output, evidence, _ = run_hook(
                "PreToolUse",
                {"session_id": "privacy", "tool_name": "credential=not-a-secret", "command": "cat file"},
                Path(directory),
            )
            self.assertNotIn("credential=not-a-secret", json.dumps(evidence))
            self.assertTrue(evidence["records"][-1]["tool"].startswith("hash:"))

    def test_malformed_input_fails_open_with_valid_json(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(HOOK), "PostToolUse"], input="not-json", text=True, capture_output=True, check=True
        )
        output = json.loads(completed.stdout)
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")

    def test_event_can_be_read_from_official_snake_case_payload_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps({"hook_event_name": "PostCompact", "session_id": "event-field"}),
                text=True,
                capture_output=True,
                env={
                    **os.environ,
                    "YGT_HARNESS_TELEMETRY": "0",
                    "YGT_HARNESS_STATE_FILE": str(Path(directory) / "state.json"),
                },
                check=True,
            )
            output = json.loads(completed.stdout)
            self.assertIn("Compaction completed", output["systemMessage"])

    def test_stop_accepts_official_last_assistant_message_as_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output, _, _ = run_hook(
                "Stop", {"session_id": "official-stop", "last_assistant_message": "completed"}, Path(directory)
            )
            self.assertEqual(output, {})
            self.assertNotIn("Finalization checkpoint", context(output))

    def test_stop_and_compaction_use_common_output_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            stop, _, _ = run_hook("Stop", {"session_id": "s"}, tmp_path)
            compact, _, _ = run_hook("PreCompact", {"session_id": "s"}, tmp_path)
            self.assertIn("systemMessage", stop)
            self.assertIn("systemMessage", compact)
            self.assertNotIn("hookSpecificOutput", stop)
            self.assertNotIn("hookSpecificOutput", compact)

    def test_session_circuit_breakers_trigger_at_twelve_turns_and_two_compactions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            stop = {}
            for _ in range(12):
                stop, evidence, _ = run_hook(
                    "Stop", {"session_id": "long-session", "last_assistant_message": "done"}, tmp_path
                )
            self.assertIn("Twelve-turn circuit breaker", context(stop))
            self.assertEqual(evidence["records"][-1]["turns"], 12)

            first, _, _ = run_hook("PreCompact", {"session_id": "long-session"}, tmp_path)
            second, evidence, _ = run_hook("PreCompact", {"session_id": "long-session"}, tmp_path)
            self.assertNotIn("Second compaction reached", context(first))
            self.assertIn("Second compaction reached", context(second))
            self.assertEqual(evidence["records"][-1]["compactions"], 2)
