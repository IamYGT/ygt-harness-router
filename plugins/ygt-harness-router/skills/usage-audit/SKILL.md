---
name: usage-audit
description: Audit Codex rollout usage, model mix, context growth, compaction, retries, and child marginal cost from local exports without exposing prompts or secrets. Use for budget reviews, cost regressions, telemetry checks, or comparing routing runs.
---

# Usage Audit

Use local JSONL/OTel aggregates as evidence. This skill reports operational usage;
it does not claim provider billing unless a provider billing export is present.

## Audit sequence

1. Identify one UTC window and the exact session/workload set.
2. Read only aggregate fields needed for the audit: session/parent id, timestamp,
   model, reasoning effort, input/output token counts, cached-input counts,
   tool duration, compaction/retry events, and exit/gate status.
3. Establish a baseline per rollout. For a child, count the child's own post-fork
   usage; do not charge the parent's pre-fork cached prefix again. Report root,
   child, and aggregate totals separately.
4. Deduplicate cumulative snapshots by event id plus timestamp/sequence. A later
   cumulative snapshot is not a second turn.
5. Compare comparable workloads only. Include sample count, uncached input,
   output tokens, wall time, first-tool latency, compaction count, retries,
   gate success, and quality regressions.
6. Report observations, then clearly labelled inferences and actions.

## Minimum report

```text
window_utc: 2026-01-01T00:00:00Z/2026-01-01T23:59:59Z
workloads: 5 comparable runs
root: input=... cached=... output=... wall=...
children: count=... input=... output=... marginal_total=...
quality: gate_pass=... retries=... compactions=...
observation: ...
inference: ...
action: keep | investigate | change after five samples
```

A single run is exploratory evidence, not a global default change. Require five
comparable samples before changing routing thresholds or compaction defaults.
Never infer human attribution from a model/session id alone; identity requires
matching owner/UID, Git author, working directory, and time window.

## Privacy and integrity

Keep raw prompts, assistant text, tool output, file contents, credentials, and
API tokens out of reports. Prefer aggregate-only storage and local redaction. If
an input is malformed, report the field and record count as `invalid`; do not
silently coerce it. If cached and uncached accounting cannot be separated, mark
cost as `unknown` instead of inventing a number.
