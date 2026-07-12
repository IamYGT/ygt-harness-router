#!/usr/bin/env python3
"""Route one initial prompt before starting a Codex exec session."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

ROUTER_PATH = Path(__file__).resolve().with_name("router.py")
_spec = importlib.util.spec_from_file_location("ygt_route_router", ROUTER_PATH)
assert _spec and _spec.loader
router = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = router
_spec.loader.exec_module(router)


WRITE_WORDS = re.compile(
    r"\b(ekle|uygula|değiştir|düzelt|oluştur|kur|tutulsun|sakla|güncelle|yap|yaz|geliştir|hazırla|üret|fix|add|build|create|implement|update|change|make|write|develop|prepare|generate|produce)\b",
    re.IGNORECASE,
)
PRODUCTION_WORDS = re.compile(r"\b(production|prod|deploy|canlıya|yayınla|release)\b", re.IGNORECASE)
READ_ONLY_WORDS = re.compile(r"\b(analiz|incele|araştır|raporla|audit|review|analyze|research)\b", re.IGNORECASE)
BROAD_WORDS = re.compile(r"\b(tüm repo(?:yu|nun|da)?|repo genelinde|repository|codebase|mimari|architecture|cross[- ]file|çok dosya|all files)\b", re.IGNORECASE)
PARALLEL_WORDS = re.compile(r"\b(multi[- ]?agent|çoklu agent|alt agent|subagents?|parallel|paralel|karşılaştır|compare)\b", re.IGNORECASE)
SESSION_PRESSURE_WORDS = re.compile(r"\b(uzun session|long session|büyük çıktı|large output|tüm log|all logs|son \d+ (?:gün|saat))\b", re.IGNORECASE)


def classify_prompt(prompt: str) -> dict[str, object]:
    text = prompt.strip()
    if not text:
        raise ValueError("prompt must not be empty")
    production = bool(PRODUCTION_WORDS.search(text))
    writes = bool(WRITE_WORDS.search(text)) or production
    broad = bool(BROAD_WORDS.search(text))
    parallel = bool(PARALLEL_WORDS.search(text))
    session_pressure = bool(SESSION_PRESSURE_WORDS.search(text))
    if READ_ONLY_WORDS.search(text) and not WRITE_WORDS.search(text) and not production:
        writes = False
    clear = writes and len(text) <= 500
    return {
        "ambiguity": 2 if clear else 8,
        "risk": 2,
        "integration": 3 if writes else 2,
        "judgment": 2,
        "failure_cost": 2,
        "clarity_gap": 2 if clear else 6,
        "repeatability_gap": 1,
        "clear_done": clear,
        "repeatable": False,
        "writes": writes,
        "production": production,
        "estimated_files": 6 if broad else (3 if writes else 1),
        "cross_file_search": broad,
        "symbol_navigation": broad,
        "large_tool_output": session_pressure,
        "long_session": session_pressure,
        "lane_clarity": 23 if broad and parallel else (12 if broad else 3),
        "parallel_gain": 20 if parallel else (8 if broad else 0),
        "verification_value": 20 if broad and parallel else (12 if broad else 3),
        "handoff_quality": 15 if broad else 2,
        "uncertainty": 8 if broad else 0,
        "reasoning_depth": 8 if broad else 0,
    }


def build_command(decision: router.RouteDecision, cwd: Path, prompt: str, extra: list[str]) -> list[str]:
    del prompt  # Prompt is intentionally passed through stdin, never argv/process listings.
    sandbox = "workspace-write" if decision.agent in {"luna-worker", "terra-worker", "sol-owner"} else "read-only"
    command = [
        os.environ.get("YGT_CODEX_REAL", "/usr/local/bin/codex.real"), "exec", "--strict-config", "-C", str(cwd), "-m", decision.model,
        "-c", f'model_reasoning_effort="{decision.reasoning_effort}"',
        "-c", 'model_verbosity="low"', "-c", 'approval_policy="never"',
        "-c", f'features.multi_agent={str(decision.max_parallel_children > 0).lower()}',
        "-s", sandbox,
    ]
    if decision.context_strategy == "serena":
        command += ["-p", "serena", "-c", "mcp_servers.serena.enabled=true"]
    elif decision.context_strategy == "context-mode":
        command += ["-p", "context-mode", "-c", "mcp_servers.serena.enabled=false"]
    elif decision.context_strategy == "context-lab":
        command += ["-p", "context-lab", "-c", "mcp_servers.serena.enabled=true"]
    else:
        command += ["-c", "mcp_servers.serena.enabled=false"]
    command += extra
    command.append("-")
    return command


def execute(command: list[str], prompt: str) -> int:
    return subprocess.run(command, input=prompt, text=True, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--task-json", help="explicit router task JSON merged over deterministic intake")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--codex-arg", action="append", default=[])
    args = parser.parse_args()
    try:
        cwd = args.cwd.expanduser().resolve()
        if not cwd.is_dir():
            raise ValueError(f"working directory does not exist: {cwd}")
        task = classify_prompt(args.prompt)
        if args.task_json:
            override = json.loads(args.task_json)
            if not isinstance(override, dict):
                raise ValueError("--task-json must be a JSON object")
            task.update(override)
        decision = router.route(task)
        command = build_command(decision, cwd, args.prompt, args.codex_arg)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(json.dumps({"task": task, "decision": asdict(decision), "command": command}, sort_keys=True))
        return 0
    return execute(command, args.prompt)


if __name__ == "__main__":
    raise SystemExit(main())
