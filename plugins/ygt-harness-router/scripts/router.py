#!/usr/bin/env python3
"""Deterministic quality-first model and delegation router for Codex tasks."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DIMENSIONS = {
    "ambiguity": 20,
    "risk": 20,
    "integration": 15,
    "judgment": 15,
    "failure_cost": 10,
    "clarity_gap": 10,
    "repeatability_gap": 10,
}
DELEGATION_DIMENSIONS = {
    "lane_clarity": 25,
    "parallel_gain": 20,
    "verification_value": 20,
    "handoff_quality": 15,
    "uncertainty": 10,
    "reasoning_depth": 10,
}


@dataclass(frozen=True)
class RouteDecision:
    capability_score: int
    delegation_score: int
    model: str
    reasoning_effort: str
    agent: str
    delegation: str
    max_parallel_children: int
    budget_class: str
    reasons: list[str]
    quality_gate: str
    escalation: str


def bounded(value: Any, maximum: int, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer from 0 to {maximum}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer from 0 to {maximum}") from exc
    if not 0 <= parsed <= maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return parsed


def normalize_task(payload: dict[str, Any]) -> dict[str, Any]:
    known = set(DIMENSIONS) | set(DELEGATION_DIMENSIONS) | {
        "clear_done", "repeatable", "parallel_lanes", "writes", "production",
        "security_sensitive", "failed_gate", "evidence_conflict", "task_type",
    }
    unknown = sorted(set(payload) - known)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")
    task = {key: bounded(payload.get(key, 0), limit, key) for key, limit in DIMENSIONS.items()}
    task.update({key: bounded(payload.get(key, 0), limit, key) for key, limit in DELEGATION_DIMENSIONS.items()})
    task["clear_done"] = bool(payload.get("clear_done", False))
    task["repeatable"] = bool(payload.get("repeatable", False))
    task["parallel_lanes"] = bounded(payload.get("parallel_lanes", 0), 6, "parallel_lanes")
    for key in ("writes", "production", "security_sensitive", "failed_gate", "evidence_conflict"):
        task[key] = bool(payload.get(key, False))
    task["task_type"] = str(payload.get("task_type", "general")).strip().lower() or "general"
    return task


def route(payload: dict[str, Any]) -> RouteDecision:
    task = normalize_task(payload)
    score = sum(task[key] for key in DIMENSIONS)
    delegation_score = sum(task[key] for key in DELEGATION_DIMENSIONS)
    reasons: list[str] = []

    assessed = any(key in payload for key in DIMENSIONS) or task["clear_done"] or task["repeatable"]
    if not assessed:
        score = 65
        reasons.append("insufficient assessment defaults to Sol rather than guessing a cheaper lane")

    forced_sol = task["production"] or task["security_sensitive"] or task["evidence_conflict"]
    if forced_sol:
        score = max(score, 70)
        reasons.append("high-impact or conflict-sensitive work requires frontier judgment")
    if task["failed_gate"]:
        score = max(score, 65)
        reasons.append("a failed mandatory gate requires focused diagnosis before retry")
    if task["writes"] and not forced_sol:
        score = max(score, 30)
        reasons.append("workspace mutation requires a write-capable lane")

    if score >= 65:
        model, agent = "gpt-5.6-sol", "sol-specialist"
        effort = "xhigh" if score >= 85 else "high"
        budget_class = "large"
    elif score >= 30:
        model, agent = "gpt-5.6-terra", "terra-worker"
        effort = "high" if score >= 50 else "medium"
        budget_class = "medium"
    else:
        model, agent = "gpt-5.6-luna", "luna-explorer"
        effort = "xhigh"
        budget_class = "small"

    if task["clear_done"] and task["repeatable"] and not forced_sol and not task["writes"] and score < 40:
        model, agent, effort, budget_class = "gpt-5.6-luna", "luna-explorer", "xhigh", "small"
        reasons.append("clear repeatable contract fits the efficient lane")
    elif model == "gpt-5.6-terra":
        reasons.append("bounded implementation needs stronger everyday reasoning and tool use")
    elif model == "gpt-5.6-sol":
        reasons.append("ambiguity, integration, or failure cost justifies the flagship lane")

    requested_lanes = task["parallel_lanes"]
    if delegation_score < 10:
        delegation, max_children = "local", 0
    elif delegation_score < 30:
        delegation, max_children = "one_bounded_probe", 1
    elif delegation_score < 60:
        delegation, max_children = "one_deep_lane", 1
    elif delegation_score < 85:
        delegation, max_children = "two_parallel_lanes", 2
    else:
        delegation, max_children = "two_wave_council", 3
        reasons.append("high delegation value uses three specialists then a challenger, not a blind swarm")
    if requested_lanes and requested_lanes != max_children:
        reasons.append(f"requested {requested_lanes} child lanes; score policy selected {max_children}")

    if task["evidence_conflict"]:
        escalation = "sol-specialist xhigh adjudication"
    elif task["failed_gate"]:
        escalation = "change approach; escalate one capability tier only after diagnosis"
    else:
        escalation = "escalate only when the quality gate fails on representative evidence"

    gate = "observable done contract, nearest tests, forbidden outcome, final evidence receipt"
    if not reasons:
        reasons.append("low-complexity bounded work does not need frontier capacity")
    return RouteDecision(score, delegation_score, model, effort, agent, delegation, max_children, budget_class, reasons, gate, escalation)


def load_payload(path: str | None) -> dict[str, Any]:
    if path:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        value = json.load(sys.stdin)
    if not isinstance(value, dict):
        raise ValueError("task input must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="JSON task file; stdin when omitted")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        decision = route(load_payload(args.input))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(asdict(decision), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
