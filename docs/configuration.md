# Configuration

YGT Harness Router follows a **native-first** rule: use Codex configuration for
models, agents, sandbox, hooks, and telemetry; use the plugin for routing policy
and evidence. The plugin should not silently rewrite global settings.

## Capability preflight

Before enabling a setting, check the installed CLI:

```bash
codex --version
codex features
codex plugin --help
codex doctor
```

Preview keys can differ by release. Unknown settings should be removed or
disabled rather than ignored accidentally.

## Recommended baseline

In `~/.codex/config.toml` (or the equivalent managed Codex configuration):

```toml
[features]
multi_agent = true
hooks = true

[agents]
max_threads = 4
max_depth = 1
job_max_runtime_seconds = 900
```

Keep `max_depth = 1` unless a measured use case proves that another level is
worth the token and coordination cost. Recursive fan-out is a capacity risk.

## Lane profiles

A lane should be a normal Codex profile or custom agent, not a hidden model
switch in a shell script. Example profile files:

```toml
# ~/.codex/luna-xhigh.config.toml
model = "<model-id-for-explorer>"
model_reasoning_effort = "xhigh"
model_verbosity = "low"
```

```toml
# ~/.codex/terra-high.config.toml
model = "<model-id-for-worker>"
model_reasoning_effort = "high"
model_verbosity = "low"
```

```toml
# ~/.codex/sol-high.config.toml
model = "<model-id-for-specialist>"
model_reasoning_effort = "high"
model_verbosity = "medium"
```

Use identifiers available to your account. The placeholders above are
intentional; model names, limits, and prices are not universal.

## Rollout budget and compaction

If your Codex build exposes rollout accounting, configure it as a canary first:

```toml
[features.rollout_budget]
enabled = true
limit_tokens = 30000000
reminder_interval_tokens = 3000000

model_auto_compact_token_limit = 30000000
model_auto_compact_token_limit_scope = "body_after_prefix"
```

The exact placement of compaction keys is version-specific; use the current
Codex configuration reference for your build. A reminder may be advisory, and
compaction may trade context savings for rereads. Capture before/after evidence
before changing a global threshold.

## Custom agents

When supported, define bounded agents under `.codex/agents/` for a project or
`~/.codex/agents/` for a user. Keep each agent's contract explicit:

```toml
name = "explorer"
description = "Read-only inventory with structured evidence."
model = "<model-id-for-explorer>"
model_reasoning_effort = "high"
sandbox_mode = "read-only"

developer_instructions = """
Accept one bounded objective. Do not modify files. Return exact evidence,
unresolved blockers, and one next action. Stop when the objective is complete.
"""
```

The plugin does not require these names; map the router's explorer, worker, and
specialist lanes to the names used by your organization.

## Hooks

Hooks should be small, deterministic, and safe to disable. Useful event
boundaries include:

| Event | Example observation |
| --- | --- |
| `PreToolUse` | fingerprint a read-only command before execution |
| `PostToolUse` | record duration, exit status, and output size |
| `PreCompact` | write the objective, gates, files, and blockers into the handoff |
| `PostCompact` | detect rereads and missing receipt fields |
| `SubagentStart` | record parent, lane, scope, and budget |
| `SubagentStop` | require a structured child receipt |

Never print a full tool payload when it may contain a secret. Hash or classify
paths and commands instead.

## OpenTelemetry (optional)

Use native Codex telemetry only when an approved collector and retention policy
exist:

```toml
[otel]
environment = "development"
metrics_exporter = "otlp-http"
trace_exporter = "otlp-http"
log_user_prompt = false
```

Do not put collector tokens or authorization headers in this repository. Supply
them through the Codex-managed environment or credential store. Telemetry is
for operational comparison (latency, retries, compaction, gates); provider
billing remains the billing surface.

## Configuration checklist

Before enabling a new profile or hook:

- [ ] The CLI accepts every key (`codex doctor`).
- [ ] The sandbox matches the lane (read-only for inventory).
- [ ] Thread and depth limits are finite.
- [ ] The done contract and stop condition are visible to the lane.
- [ ] Tests and forbidden outcomes are named before implementation.
- [ ] Prompt logging is disabled unless explicitly approved.
- [ ] No token, cookie, `.env` value, or private endpoint is in the config file.
