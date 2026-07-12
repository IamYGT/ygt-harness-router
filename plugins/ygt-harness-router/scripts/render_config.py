#!/usr/bin/env python3
"""Render an opt-in Codex configuration fragment without mutating user config."""

from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = '''# YGT Harness Router — opt-in canary configuration
# Merge deliberately into user-level ~/.codex/config.toml after validation.
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
model_verbosity = "low"
review_model = "gpt-5.6-terra"
model_auto_compact_token_limit = {compact_limit}
model_auto_compact_token_limit_scope = "body_after_prefix"

[agents]
max_threads = 4
max_depth = 1
job_max_runtime_seconds = 900
interrupt_message = true

[features]
multi_agent = true
hooks = true

[features.rollout_budget]
enabled = true
limit_tokens = {budget_limit}
reminder_interval_tokens = {reminder_interval}
prefill_token_weight = 1.0
sampling_token_weight = 1.0

[otel]
environment = "canary"
log_user_prompt = false
metrics_exporter = "none"
trace_exporter = "none"
'''


def render(budget_limit: int, compact_limit: int) -> str:
    if budget_limit <= 0 or compact_limit <= 0:
        raise ValueError("limits must be positive")
    reminder = max(1, budget_limit // 10)
    return TEMPLATE.format(
        budget_limit=budget_limit,
        compact_limit=compact_limit,
        reminder_interval=reminder,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-limit", type=int, default=30_000_000)
    parser.add_argument("--compact-limit", type=int, default=24_000_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        content = render(args.budget_limit, args.compact_limit)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
