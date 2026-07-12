#!/usr/bin/env python3
"""Transparent Codex CLI and app-server entry router."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import route_exec  # noqa: E402


PASSTHROUGH = {
    "login", "logout", "mcp", "plugin", "mcp-server", "remote-control",
    "completion", "update", "doctor", "sandbox", "debug", "apply", "resume",
    "archive", "delete", "unarchive", "fork", "cloud", "exec-server", "features",
    "review", "help",
}
VALUE_OPTIONS = {"-c", "--config", "-C", "--cd", "-p", "--profile", "-s", "--sandbox", "-m", "--model"}


def decision(prompt: str):
    return route_exec.router.route(route_exec.classify_prompt(prompt))


def route_receipt(routed) -> dict[str, Any]:
    return {
        "model": routed.model,
        "effort": routed.reasoning_effort,
        "agent": routed.agent,
        "context": routed.context_strategy,
        "children": routed.max_parallel_children,
    }


def route_turn_start_line(line: bytes) -> tuple[bytes, dict[str, Any] | None]:
    try:
        payload = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return line, None
    if not isinstance(payload, dict) or payload.get("method") != "turn/start":
        return line, None
    params = payload.get("params")
    if not isinstance(params, dict) or not isinstance(params.get("input"), list):
        return line, None
    prompt = "\n".join(
        item.get("text", "") for item in params["input"]
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
    ).strip()
    if not prompt:
        return line, None
    routed = decision(prompt)
    params["model"] = routed.model
    params["effort"] = routed.reasoning_effort
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(), route_receipt(routed)


def _copy(source, target) -> None:
    for chunk in iter(source.readline, b""):
        target.write(chunk)
        target.flush()


def proxy_app_server(real: str, args: list[str]) -> int:
    child = subprocess.Popen([real, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert child.stdin and child.stdout and child.stderr
    previous_handlers = {}

    def forward_signal(signum, _frame) -> None:
        if child.poll() is None:
            child.send_signal(signum)
        raise SystemExit(128 + signum)

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        previous_handlers[signum] = signal.signal(signum, forward_signal)
    stdout_thread = threading.Thread(target=_copy, args=(child.stdout, sys.stdout.buffer), daemon=True)
    stderr_thread = threading.Thread(target=_copy, args=(child.stderr, sys.stderr.buffer), daemon=True)
    try:
        stdout_thread.start(); stderr_thread.start()
        for line in sys.stdin.buffer:
            routed, receipt = route_turn_start_line(line)
            if receipt:
                print(f"ygt-route model={receipt['model']} effort={receipt['effort']} agent={receipt['agent']}", file=sys.stderr, flush=True)
            child.stdin.write(routed); child.stdin.flush()
        child.stdin.close()
        code = child.wait()
        stdout_thread.join(timeout=2); stderr_thread.join(timeout=2)
        return code
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        if child.poll() is None:
            child.terminate()


def _explicit_model(args: list[str]) -> bool:
    return any(arg in {"-m", "--model"} or arg.startswith("--model=") for arg in args)


def _last_prompt(args: list[str]) -> str | None:
    skip = False
    candidates: list[str] = []
    for arg in args:
        if skip:
            skip = False; continue
        if arg in VALUE_OPTIONS:
            skip = True; continue
        if arg.startswith("-"):
            continue
        candidates.append(arg)
    return candidates[-1] if candidates else None


def _command_index(args: list[str]) -> int | None:
    skip = False
    for index, arg in enumerate(args):
        if skip:
            skip = False
            continue
        if arg in VALUE_OPTIONS:
            skip = True
            continue
        if not arg.startswith("-"):
            return index
    return None


def app_server_args(args: list[str]) -> list[str]:
    if any(arg == "features.multi_agent=true" for arg in args):
        return args
    index = args.index("app-server")
    return [*args[:index], "-c", "features.multi_agent=true", *args[index:]]


def policy_overrides(routed) -> list[str]:
    sandbox = "workspace-write" if routed.agent in {"luna-worker", "terra-worker", "sol-owner"} else "read-only"
    overrides = [
        "-m", routed.model,
        "-c", f'model_reasoning_effort="{routed.reasoning_effort}"',
        "-c", 'model_verbosity="low"',
        "-c", 'approval_policy="never"',
        "-c", f'features.multi_agent={str(routed.max_parallel_children > 0).lower()}',
        "-s", sandbox,
    ]
    if routed.context_strategy == "serena":
        overrides += ["-p", "serena", "-c", "mcp_servers.serena.enabled=true"]
    elif routed.context_strategy == "context-mode":
        overrides += ["-p", "context-mode", "-c", "mcp_servers.serena.enabled=false"]
    elif routed.context_strategy == "context-lab":
        overrides += ["-p", "context-lab", "-c", "mcp_servers.serena.enabled=true"]
    else:
        overrides += ["-c", "mcp_servers.serena.enabled=false"]
    return overrides


def routed_cli_args(args: list[str], stdin_prompt: str | None = None) -> tuple[list[str], dict[str, Any] | None]:
    if not args:
        return ["-m", "gpt-5.6-luna", "-c", 'model_reasoning_effort="xhigh"'], {"model": "gpt-5.6-luna", "effort": "xhigh", "agent": "luna-worker"}
    command_index = _command_index(args)
    command = args[command_index] if command_index is not None else None
    if command in PASSTHROUGH or args[0] in {"-h", "--help", "-V", "--version"}:
        return args, None
    if command == "exec" and command_index is not None and len(args) > command_index + 1 and args[command_index + 1] in {"resume", "review", "help"}:
        return args, None
    if _explicit_model(args):
        return args, None
    prompt = stdin_prompt if command == "exec" and (len(args) == command_index + 1 or args[-1] == "-") else _last_prompt(args[command_index + 1:] if command == "exec" and command_index is not None else args)
    if not prompt:
        return args, None
    routed = decision(prompt)
    overrides = policy_overrides(routed)
    if command == "exec" and command_index is not None:
        result = [*args[:command_index + 1], *overrides, *args[command_index + 1:]]
    else:
        result = [*overrides, *args]
    return result, route_receipt(routed)


def main() -> int:
    real = os.environ.get("YGT_CODEX_REAL", "/usr/local/bin/codex.real")
    args = sys.argv[1:]
    if "app-server" in args:
        return proxy_app_server(real, app_server_args(args))
    stdin_prompt = None
    command_index = _command_index(args)
    if command_index is not None and args[command_index] == "exec" and (len(args) == command_index + 1 or args[-1] == "-") and not sys.stdin.isatty():
        stdin_prompt = sys.stdin.read()
    routed_args, receipt = routed_cli_args(args, stdin_prompt)
    if receipt:
        print(f"ygt-route model={receipt['model']} effort={receipt['effort']} agent={receipt['agent']}", file=sys.stderr)
    return subprocess.run([real, *routed_args], input=stdin_prompt, text=True, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
