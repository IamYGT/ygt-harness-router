#!/usr/bin/env python3
"""Privacy-bounded Codex lifecycle hooks for ygt-harness-router.

The command receives one Codex hook payload on stdin and emits one JSON
response on stdout.  It intentionally observes by default: a caller must set
``YGT_HARNESS_POLICY=deny`` to opt into a generic PreToolUse permission
decision.  No command is classified as destructive or blocked by default.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_BUDGET_THRESHOLD = 0.80
MAX_STATE_ENTRIES = 128
MAX_TELEMETRY_BYTES = 4 * 1024 * 1024
READ_ONLY_TOOLS = {
    "read",
    "read_file",
    "readfile",
    "glob",
    "grep",
    "search",
    "search_files",
    "list_files",
    "file_search",
}
READ_ONLY_COMMANDS = {
    "awk",
    "cat",
    "cmp",
    "cut",
    "diff",
    "du",
    "fd",
    "find",
    "git",
    "grep",
    "head",
    "jq",
    "ls",
    "more",
    "nl",
    "paste",
    "pwd",
    "rg",
    "sed",
    "sort",
    "stat",
    "tail",
    "tree",
    "uniq",
    "wc",
    "which",
}
READ_ONLY_GIT_SUBCOMMANDS = {"branch", "diff", "log", "ls-files", "remote", "show", "status"}
TOKEN_KEYS = {
    "context_tokens",
    "input_tokens",
    "output_tokens",
    "prompt_tokens",
    "sampling_tokens",
    "total_tokens",
    "used_tokens",
}
IDENTITY_KEYS = ("session_id", "sessionId", "thread_id", "threadId", "conversation_id", "conversationId")
TOOL_KEYS = ("tool_name", "toolName", "tool", "name")
COMMAND_KEYS = ("command", "cmd", "script")
SUBAGENT_KEYS = ("agent_id", "agentId", "subagent_id", "subagentId", "task_id", "taskId", "id")


def _text(value: Any, limit: int = 512) -> str:
    """Return bounded text without ever serialising arbitrary payload data."""

    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return str(value).strip()[:limit]


def _hash(value: Any) -> str | None:
    text = _text(value, 2048)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:24]


def _payload_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    for container_key in ("tool_input", "toolInput", "input", "data"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            for key in keys:
                if key in container and container[key] not in (None, ""):
                    return container[key]
    return None


def _tool_name(payload: dict[str, Any]) -> str:
    value = _payload_value(payload, TOOL_KEYS)
    if isinstance(value, dict):
        value = value.get("name") or value.get("type")
    return _text(value, 80).lower()


def _safe_tool_label(tool: str) -> str | None:
    """Keep conventional tool names readable without trusting arbitrary input."""

    if not tool:
        return None
    if re.fullmatch(r"[a-z0-9_.:/-]{1,80}", tool):
        return tool
    return f"hash:{_hash(tool)}"


def _command(payload: dict[str, Any]) -> str:
    value = _payload_value(payload, COMMAND_KEYS)
    if isinstance(value, dict):
        value = value.get("command") or value.get("cmd")
    return _text(value, 2048)


def _session_hash(payload: dict[str, Any]) -> str | None:
    value = _payload_value(payload, IDENTITY_KEYS)
    return _hash(value or os.environ.get("CODEX_SESSION_ID"))


def _cwd_hash(payload: dict[str, Any]) -> str | None:
    value = _payload_value(payload, ("cwd", "working_directory", "workingDirectory"))
    return _hash(value or os.getcwd())


def _normalise_command(command: str) -> str:
    # Fingerprints are for equality only.  Keep the exact argument semantics,
    # but collapse whitespace so harmless formatting does not create duplicates.
    return re.sub(r"\s+", " ", command.strip())


def _read_only(tool: str, command: str) -> bool:
    if tool in READ_ONLY_TOOLS:
        return True
    if not command:
        return False
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return False
    if not tokens:
        return False
    executable = Path(tokens[0]).name.lower()
    if executable in {"env", "command", "nohup", "timeout"} and len(tokens) > 1:
        tokens = tokens[1:]
        executable = Path(tokens[0]).name.lower()
    if executable == "git":
        return len(tokens) > 1 and tokens[1].lower() in READ_ONLY_GIT_SUBCOMMANDS
    # Shell composition is not considered read-only: a command such as
    # `cat file && rm file` must not be treated as a duplicate safe read.
    if any(token in {";", "&&", "||", "|", "|&", "&", ">", ">>"} for token in tokens):
        return False
    return executable in READ_ONLY_COMMANDS


def _fingerprint(tool: str, command: str) -> str | None:
    normalised = _normalise_command(command)
    if not normalised:
        return None
    return hashlib.sha256(f"{tool}\0{normalised}".encode("utf-8", "replace")).hexdigest()[:24]


def _int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _usage_tokens(payload: dict[str, Any]) -> int | None:
    """Read only documented usage-shaped fields; never inspect prompt text."""

    candidates: list[int] = []

    def visit(value: Any, depth: int = 0) -> None:
        if depth > 3 or not isinstance(value, dict):
            return
        for key, item in value.items():
            if key in TOKEN_KEYS:
                number = _int(item)
                if number is not None:
                    candidates.append(number)
            elif isinstance(item, dict):
                visit(item, depth + 1)

    for key in ("usage", "token_usage", "tokenUsage", "metrics", "context"):
        visit(payload.get(key))
    if candidates:
        # Prefer an explicit total/used value where one exists.  This avoids
        # summing nested input/output counters twice.
        for key in ("total_tokens", "used_tokens"):
            value = payload.get(key)
            number = _int(value)
            if number is not None:
                return number
        return max(candidates)
    return _int(os.environ.get("YGT_HARNESS_USED_TOKENS"))


def _budget_message(payload: dict[str, Any]) -> str | None:
    budget = _int(os.environ.get("YGT_HARNESS_BUDGET_TOKENS"))
    used = _usage_tokens(payload)
    if not budget or used is None:
        return None
    try:
        threshold = float(os.environ.get("YGT_HARNESS_BUDGET_THRESHOLD", DEFAULT_BUDGET_THRESHOLD))
    except ValueError:
        threshold = DEFAULT_BUDGET_THRESHOLD
    threshold = min(max(threshold, 0.0), 1.0)
    if used < budget * threshold:
        return None
    return f"Rollout budget checkpoint: {used}/{budget} tokens observed; preserve the done contract before continuing."


def _state_path() -> Path:
    configured = os.environ.get("YGT_HARNESS_STATE_FILE")
    if configured:
        return Path(configured).expanduser()
    telemetry = os.environ.get("YGT_HARNESS_TELEMETRY_FILE")
    if telemetry:
        return Path(telemetry).expanduser().with_suffix(".state.json")
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return root / "state" / "ygt-harness-router" / "hooks.state.json"


def _load_state() -> dict[str, Any]:
    try:
        path = _state_path()
        if not path.is_file() or path.stat().st_size > MAX_TELEMETRY_BYTES:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep state bounded and use an atomic replace so two hooks cannot leave a
    # half-written JSON document behind.
    fingerprints = state.get("fingerprints", {})
    if isinstance(fingerprints, dict):
        state["fingerprints"] = dict(list(fingerprints.items())[-MAX_STATE_ENTRIES:])
    active = state.get("active_subagents", {})
    if isinstance(active, dict):
        state["active_subagents"] = dict(list(active.items())[-MAX_STATE_ENTRIES:])
    handle = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
            handle = temporary.name
            json.dump(state, temporary, ensure_ascii=False, separators=(",", ":"))
            temporary.write("\n")
        os.chmod(handle, 0o600)
        os.replace(handle, path)
    except OSError:
        if handle:
            try:
                os.unlink(handle)
            except OSError:
                pass


def _telemetry_path() -> Path | None:
    if os.environ.get("YGT_HARNESS_TELEMETRY", "1").lower() in {"0", "false", "off", "no"}:
        return None
    configured = os.environ.get("YGT_HARNESS_TELEMETRY_FILE")
    if configured:
        return Path(configured).expanduser()
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return root / "state" / "ygt-harness-router" / "telemetry.jsonl"


def _write_telemetry(event: str, payload: dict[str, Any], details: dict[str, Any]) -> None:
    path = _telemetry_path()
    if path is None:
        return
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session": _session_hash(payload),
        "cwd": _cwd_hash(payload),
    }
    # details are built exclusively from bounded booleans, counters, names and
    # hashes.  Do not add arbitrary stdin fields here.
    for key, value in details.items():
        if key == "tool" and isinstance(value, str):
            record[key] = _safe_tool_label(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            record[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_TELEMETRY_BYTES:
            return
        with path.open("a", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        # Hooks must not turn an optional telemetry sink into a tool failure.
        return


def _response(event: str, messages: list[str], decision: str | None = None) -> dict[str, Any]:
    output: dict[str, Any] = {"hookEventName": event}
    if messages:
        output["additionalContext"] = " ".join(messages)[:2000]
    if event == "PreToolUse" and decision == "deny":
        output["permissionDecision"] = decision
        output["permissionDecisionReason"] = "Generic YGT_HARNESS_POLICY requested this PreToolUse decision."
    return {"hookSpecificOutput": output}


def _subagent_id(payload: dict[str, Any]) -> str | None:
    value = _payload_value(payload, SUBAGENT_KEYS)
    return _hash(value)


def _receipt(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    receipt = payload.get("receipt")
    if isinstance(receipt, dict):
        missing = [key for key in ("status", "summary", "evidence") if not _text(receipt.get(key))]
        return not missing, missing
    if _text(receipt):
        return True, []
    # Some Codex integrations flatten a receipt into result/summary/evidence.
    flattened = payload.get("result") or payload.get("output") or payload.get("message")
    if isinstance(flattened, dict):
        missing = [key for key in ("status", "summary", "evidence") if not _text(flattened.get(key))]
        return not missing, missing
    return False, ["receipt"]


def handle(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = event or _text(payload.get("hookEventName"), 40) or "Unknown"
    state = _load_state()
    messages: list[str] = []
    details: dict[str, Any] = {}
    tool = _tool_name(payload)
    command = _command(payload)
    read_only = _read_only(tool, command)
    fingerprint = _fingerprint(tool, command) if read_only else None
    session = _session_hash(payload)

    if event == "PreToolUse":
        details.update({"tool": tool or None, "read_only": read_only, "fingerprint": fingerprint})
        budget = _budget_message(payload)
        if budget:
            messages.append(budget)
        fingerprints = state.setdefault("fingerprints", {})
        duplicate = False
        count = 0
        if fingerprint and isinstance(fingerprints, dict):
            previous = fingerprints.get(fingerprint)
            if isinstance(previous, dict) and previous.get("session") == session:
                duplicate = True
                count = int(previous.get("count", 0)) + 1
            else:
                count = 1
            fingerprints[fingerprint] = {"session": session, "count": count}
        details.update({"duplicate_read": duplicate, "duplicate_count": count})
        if duplicate:
            messages.append(f"Duplicate read-only fingerprint observed ({count} repeats); reuse prior evidence if still valid.")
        configured_policy = os.environ.get("YGT_HARNESS_POLICY", "observe").lower()
        # Codex currently parses but does not support PreToolUse `ask`; emit a
        # reminder rather than invalid hook output when an operator selects it.
        if configured_policy == "ask":
            messages.append("YGT_HARNESS_POLICY=ask is unsupported by current Codex PreToolUse hooks; continuing in observe mode.")
        decision = "deny" if configured_policy == "deny" else None
        _write_telemetry(event, payload, details | {"decision": decision or "observe"})
        _save_state(state)
        if decision == "allow":
            decision = None
        return _response(event, messages, decision)

    if event == "PostToolUse":
        details.update({"tool": tool or None, "read_only": read_only, "fingerprint": fingerprint})
        budget = _budget_message(payload)
        if budget:
            messages.append(budget)
        _write_telemetry(event, payload, details)
        return _response(event, messages)

    if event == "PreCompact":
        messages.append("Checkpoint before compaction: preserve objective, done contract, changed files, tests, blockers, and exact next action.")
        _write_telemetry(event, payload, {"checkpoint": True, "used_tokens": _usage_tokens(payload)})
        return _response(event, messages)

    if event == "PostCompact":
        messages.append("Compaction completed; verify the handoff summary before rereading files or repeating tools.")
        _write_telemetry(event, payload, {"checkpoint": True, "used_tokens": _usage_tokens(payload)})
        return _response(event, messages)

    if event == "SubagentStart":
        subagent = _subagent_id(payload)
        if subagent:
            state.setdefault("active_subagents", {})[subagent] = {"session": session, "started": True}
        _write_telemetry(event, payload, {"subagent": subagent, "active": bool(subagent)})
        _save_state(state)
        return _response(event, messages)

    if event == "SubagentStop":
        subagent = _subagent_id(payload)
        active = state.setdefault("active_subagents", {})
        was_active = bool(subagent and isinstance(active, dict) and subagent in active)
        if subagent and isinstance(active, dict):
            active.pop(subagent, None)
        ready, missing = _receipt(payload)
        details.update({"subagent": subagent, "was_active": was_active, "receipt_present": ready, "receipt_missing": len(missing)})
        _write_telemetry(event, payload, details)
        _save_state(state)
        if not ready:
            messages.append("Subagent receipt is incomplete; return status, summary, evidence, and relevant tests before finalizing.")
        return _response(event, messages)

    if event == "Stop":
        final = (
            payload.get("final")
            or payload.get("final_message")
            or payload.get("response")
            or payload.get("message")
            or payload.get("last_assistant_message")
        )
        if not _text(final):
            messages.append("Finalization checkpoint: include the outcome, evidence, blockers, and next action before stopping.")
        budget = _budget_message(payload)
        if budget:
            messages.append(budget)
        _write_telemetry(event, payload, {"finalization_ready": bool(_text(final)), "used_tokens": _usage_tokens(payload)})
        return _response(event, messages)

    _write_telemetry(event, payload, {"unrecognised_event": True})
    return _response(event, messages)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    try:
        raw = sys.stdin.read()
        parsed = json.loads(raw) if raw.strip() else {}
        payload = parsed if isinstance(parsed, dict) else {}
        event = (
            _text(argv[0], 40)
            if argv
            else _text(payload.get("hook_event_name") or payload.get("hookEventName"), 40)
        )
        result = handle(event, payload)
    except Exception:
        # A telemetry/reminder hook is optional.  Fail open with valid JSON so
        # malformed third-party payloads cannot block the user's tool call.
        result = {
            "hookSpecificOutput": {
                "hookEventName": (
                    _text(argv[0], 40)
                    if argv
                    else "Unknown"
                )
            }
        }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
