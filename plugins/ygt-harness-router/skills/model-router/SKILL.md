---
name: model-router
description: Route Codex work to Sol, Terra, or Luna using a transparent task score, bounded parallelism, and evidence-based escalation. Use when choosing a model, reasoning effort, agent, lane count, or whether a retry/hand-off is justified.
---

# Model Router

Use this skill before starting non-trivial work or adding a delegated lane. The root
agent remains the owner of the contract, exact target, integration, and final
verification; routed agents return evidence, not authority.

## 1. Establish the contract

Write down the objective, observable done condition, prohibited outcomes, exact
mutation target, and stop condition. If the repository, branch, tenant, account,
or deployment target is ambiguous, resolve it read-only before routing; do not
route around an unresolved identity.

## 2. Score delegation value

Score each dimension from 0 to its weight, then round the total to 0-100:

| Dimension | Weight | High score means |
| --- | ---: | --- |
| Clarity | 25 | The request and acceptance criteria are explicit |
| Parallel gain | 20 | Independent lanes can finish useful work |
| Verification value | 20 | A separate check materially reduces risk |
| Handoff quality | 15 | Inputs/outputs can be bounded and structured |
| Uncertainty | 10 | Domain or current-state uncertainty is material |
| Reasoning depth | 10 | The decision needs more than routine execution |

Do not inflate a dimension to justify delegation. A score below 10 stays local.

This is the `delegation_score`; it selects lane count, not model capability. Keep
model choice independent so a high-risk task does not create a swarm merely
because it needs Sol, and a highly parallel extraction task can still use Luna.

## 3. Score model capability

Use the bundled `scripts/router.py` from the plugin root. Pass a JSON object with
capability dimensions (`ambiguity`, `risk`, `integration`, `judgment`,
`failure_cost`, `clarity_gap`, `repeatability_gap`) and the delegation dimensions
(`lane_clarity`, `parallel_gain`, `verification_value`, `handoff_quality`,
`uncertainty`, `reasoning_depth`). Each value is bounded by the router schema.

```bash
printf '%s' '{
  "ambiguity": 8,
  "risk": 5,
  "integration": 7,
  "judgment": 6,
  "failure_cost": 4,
  "clarity_gap": 4,
  "repeatability_gap": 3,
  "lane_clarity": 20,
  "parallel_gain": 10
}' | python3 scripts/router.py --pretty
```

The capability bands are quality-first: `0-29` Luna, `30-64` Terra, and
`65-100` Sol. Production, security-sensitive work, evidence conflict, and failed
mandatory gates raise the minimum tier. An unassessed task defaults to Sol rather
than guessing a cheaper lane.

Also provide privacy-safe context signals before the session starts:

- `estimated_files` (`0..1000`)
- `symbol_navigation`
- `cross_file_search`
- `large_tool_output`
- `long_session`

The returned `context_strategy` is a separate latency decision:

- `base`: small bounded task; avoid MCP/plugin startup.
- `serena`: symbol navigation, cross-file search, or at least four estimated files.
- `context-mode`: large tool output or a long session.
- `context-lab`: both needs are present, or the need has not yet been assessed.

Select this strategy before opening the Codex session. A tool hook is too late to
save `SessionStart` and MCP initialization time.

## 4. Select the route

- **0-9 — local:** root handles it without a child.
- **10-29 — probe:** one read-only Luna explorer for bounded inventory/evidence.
- **30-59 — deep:** one Luna xhigh lane, or Terra for a clearly scoped implementation.
- **60-84 — two lanes:** one primary lane plus one independent verifier; keep paths disjoint.
- **85-100 — three specialists + challenger:** Luna explorer, Terra worker or Sol specialist,
  and Luna challenger; use only when the parallel gain and verification are real.

Model policy:

- **Sol (`gpt-5.6-sol`)**: root orchestration and owner-grade ambiguity, architecture,
  or a failed gate. Prefer `high`; use `xhigh` only when the contract warrants it.
- **Terra (`gpt-5.6-terra`)**: ordinary implementation when Luna's bounded
  one-to-three-file contract is exceeded. Prefer `medium` for bounded work and
  `high` for broader integration.
- **Luna (`gpt-5.6-luna`)**: bounded exploration, extraction, verification, and
  low-risk writes across at most three files. Use `xhigh` for normal lanes
  and `max` for a failed gate, conflict, or adversarial challenge. `luna-explorer`
  stays read-only while `luna-worker` is explicitly write-capable.

Keep `max_threads` at four and `max_depth` at one unless the operator explicitly
changes the contract. Never fan out overlapping writers. A retry must explain what
new evidence it expects; otherwise stop and hand off.

## 5. Return a route receipt

Before launching, record a compact receipt:

```text
route: terra-worker
model: gpt-5.6-terra
reasoning: high
score: 47
context_strategy: serena
owned_paths: [src/example.py, tests/test_example.py]
stop_when: focused test passes or first blocking failure is captured
forbidden: no unrelated edits, no database reset, no secret output
```

The child must return changed paths, exact commands, exit status, evidence, and
remaining blockers. The root consumes the receipt and reruns the smallest relevant
validation after integration.

## Cost and quality guardrails

Prefer a small complete route over broad speculative exploration. Count root and
child marginal usage separately; do not claim cached context as new work. A
compaction, retry, or additional lane is justified only when it improves the done
contract, not merely because context is large. Never place credentials, raw tokens,
or unredacted prompts in receipts or telemetry.
