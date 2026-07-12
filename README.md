# YGT Harness Router

YGT Harness Router is a Codex plugin for routing work to the smallest capable
execution lane while protecting quality, evidence, and context capacity.

[![CI](https://github.com/IamYGT/ygt-harness-router/actions/workflows/ci.yml/badge.svg)](https://github.com/IamYGT/ygt-harness-router/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Quality-first, capacity-first.** The router is not a blind cost minimizer.
> A cheaper lane that creates a failed gate, a lost handoff, or a second
> exploration is more expensive in practice than the right lane on the first
> attempt.

## What it does

The plugin provides a repeatable operating contract around Codex work:

- score a task before delegation using clarity, parallel gain, verification,
  handoff, uncertainty, and reasoning needs;
- route the initial prompt before Codex starts so a bounded write can run
  directly on Luna instead of paying for a Sol root and child handoff;
- route bounded work to a focused lane (for example, an explorer, workhorse,
  or specialist) instead of recursively fanning out by default;
- carry a compact receipt between parent and child work so the next step can be
  resumed without rereading an entire rollout;
- treat tests, smoke checks, and readback as completion evidence;
- make context growth, compaction, retries, duplicate reads, and child output
  visible when the corresponding Codex hooks or telemetry are enabled.

It is an orchestration layer, not a replacement for Codex, a model provider, a
billing meter, or a guarantee that every task can be parallelized.

## Prerequisites

- Codex CLI with plugin and marketplace support (`codex --help` should list
  `plugin` and `codex plugin marketplace --help` should succeed).
- A Codex account and model access appropriate to the lanes you configure.
- Git, if installing from the public marketplace snapshot.
- Python 3.10+ for the repository validation helpers.

The plugin does not create an account, request an API key, or collect a secret.
Authentication and model availability remain the responsibility of Codex.

## Install from GitHub

The public repository contains a marketplace manifest under
`.agents/plugins/marketplace.json` and the installable plugin under
`plugins/ygt-harness-router/`.

1. Add the GitHub marketplace snapshot:

   ```bash
   codex plugin marketplace add IamYGT/ygt-harness-router --ref main
   ```

2. Confirm the marketplace and plugin names visible to your Codex build:

   ```bash
   codex plugin marketplace list
   codex plugin list --available --json
   ```

3. Install the entry from the marketplace name printed by the previous command
   (the repository snapshot currently uses `ygt-harness-router`):

   ```bash
   codex plugin add ygt-harness-router --marketplace <marketplace-name>
   ```

   If your Codex installation has no marketplace-name collision, the concrete
   command is:

   ```bash
   codex plugin add ygt-harness-router@ygt-harness-router
   ```

4. Restart Codex, then verify the installation:

   ```bash
   codex plugin list
   codex doctor
   ```

5. Plugin hooks are executable code and are not trusted automatically. In a
   new interactive Codex session, open `/hooks`, inspect the source and exact
   command definitions, then trust the YGT Harness Router hooks if they match
   this checkout.

If the marketplace command succeeds but plugin lists remain empty, verify the
stable feature state:

```bash
codex features list
codex features enable plugins
```

A system or workspace-managed `plugins = false` setting can override personal
configuration. In that case, ask the administrator to enable the feature; use
`--enable plugins` only as a command-scoped diagnostic, not as a hidden global
configuration change.

To refresh a GitHub snapshot later, run `codex plugin marketplace upgrade` and
then restart Codex. The exact upgrade selector is shown by
`codex plugin marketplace --help` for the installed CLI version.

### Install from a local checkout

This is useful when developing or reviewing a change before publishing it:

```bash
git clone https://github.com/IamYGT/ygt-harness-router.git
cd ygt-harness-router
codex plugin marketplace add "$PWD"
codex plugin list --available --json
codex plugin add ygt-harness-router --marketplace <marketplace-name>
```

The local path must contain both `.agents/plugins/marketplace.json` and
`plugins/ygt-harness-router/.codex-plugin/plugin.json`.

### Install the optional custom agents

Codex discovers personal custom agents from `~/.codex/agents/`. The plugin keeps
its six role definitions inside the package so installation never overwrites
personal configuration implicitly. Preview the operation first, then apply it:

```bash
python3 plugins/ygt-harness-router/scripts/install_agents.py
python3 plugins/ygt-harness-router/scripts/install_agents.py --apply
```

Existing files are refused by default. Use `--force` only after review; the
installer creates a timestamped backup before replacement. Restart Codex after
installing or updating agent files.

### Pre-session launcher

Model routing only saves time when it happens before the session starts. The
launcher performs a local deterministic intake, selects model/context/sandbox,
and passes the prompt to Codex over stdin:

```bash
python3 plugins/ygt-harness-router/scripts/route_exec.py \
  --cwd /path/to/project \
  "Update this single login field and its focused test"
```

Preview without starting Codex:

```bash
python3 plugins/ygt-harness-router/scripts/route_exec.py \
  --cwd /path/to/project --dry-run "Update this single login field"
```

Clear low-risk writes across one to three estimated files route to
`gpt-5.6-terra` medium with `workspace-write`, no subagent, and no context MCP
startup. A five-sample matched benchmark found Terra faster and lower-token than
Luna xhigh for this contract. Luna write remains available explicitly with
`--task-json '{"task_type":"luna_write"}'`.

## First run

Start with a bounded, observable task rather than a repository-wide rewrite:

```text
Use YGT Harness Router to inspect the failing API test, keep the task read-only,
return the evidence and the smallest next action, and stop after the test result.
```

The router should return a lane decision and a receipt containing the objective,
scope, evidence, changed files (if any), unresolved blockers, and the next
action. Treat a missing receipt or a failed lower-level test as a failed gate,
not as a reason to widen the task.

## Native Codex configuration

The plugin is deliberately additive: it does not overwrite your global Codex
configuration. Enable only the native capabilities that your installed Codex
version supports.

Example `~/.codex/config.toml` baseline:

```toml
[features]
multi_agent = true
hooks = true

[agents]
max_threads = 4
max_depth = 1
job_max_runtime_seconds = 900
```

Optional native rollout accounting (experimental in some Codex releases):

```toml
[features.rollout_budget]
enabled = true
limit_tokens = 30000000
reminder_interval_tokens = 3000000
```

Use the exact keys accepted by your installed CLI; check `codex --help`,
`codex features`, and the [Codex configuration reference](https://developers.openai.com/codex/config-reference/)
before enabling a preview option. A reminder is not a hard budget stop unless
your Codex build explicitly documents that behavior.

For lane-specific profiles, keep model and reasoning choices in normal Codex
profiles, for example `~/.codex/luna-xhigh.config.toml`:

```toml
model = "<model-id-for-luna>"
model_reasoning_effort = "xhigh"
model_verbosity = "low"
```

Do not copy a model identifier from this example verbatim; availability and
pricing are account- and release-dependent.

## Architecture

The router has five deliberately separate responsibilities:

1. **Intake** — normalize the objective, done contract, scope, and stop
   condition before any expensive exploration.
2. **Scoring** — decide whether delegation has enough clarity, parallel gain,
   verification value, handoff value, uncertainty, and reasoning demand to
   justify its overhead.
3. **Execution** — run one bounded lane with explicit sandbox, depth, runtime,
   and model/reasoning settings.
4. **Evidence** — collect receipts, test results, tool outcomes, and current
   state. A completion claim without a matching current-run observation is not
   accepted as done.
5. **Capacity control** — detect duplicate read-only work, context growth,
   compaction boundaries, retries, and marginal child cost so the harness can
   choose a handoff, a compact summary, or a new session deliberately.

The plugin is compatible with native Codex hooks and agents. Hook handlers are
optional integration points; they must fail closed for secrets and must not turn
telemetry into a second source of truth for billing.

## Routing example

For a clear, isolated inventory request:

```text
Objective: list the routes under api/v1 and report auth middleware.
Scope: read-only route files and route listing.
Done: route names, middleware, and exact command output.
Forbidden: edits, migrations, database writes, and secrets in output.
```

The expected decision is a focused explorer lane with read-only access. A
cross-tenant mutation or a failed security gate should move to a specialist
lane and add negative tests instead of being sent to the cheapest model.

## Privacy and security

- The plugin does not ask for, upload, or persist API keys, bearer tokens,
  cookies, SSH keys, or environment-file contents.
- Prompt and tool output remain under Codex's normal local/session controls.
- Optional OpenTelemetry is opt-in and should be configured with prompt logging
  disabled (`log_user_prompt = false`) unless your organization has an explicit
  approved retention policy.
- Do not install an unreviewed MCP server merely to obtain usage metrics; an MCP
  server can expand the data and network boundary of a Codex session.
- Hook and script changes are code execution. Review them, pin marketplace
  sources where practical, and use a read-only sandbox for inventory work.

See [SECURITY.md](SECURITY.md) and [docs/privacy.md](docs/privacy.md) for the
full boundary and reporting process.

## Limitations and trade-offs

- Native Codex plugin, hook, model, and budget APIs can change between CLI
  releases; preview settings are intentionally documented as optional.
- A delegation score is a decision aid, not a proof of lower cost or higher
  quality. Repeated small tasks may be cheaper locally; ambiguous tasks need
  more reasoning and verification.
- Compaction can save context capacity or cause a reread if the handoff is poor.
  Measure both the compact event and the post-compact reread before changing a
  global threshold.
- Usage estimates are operational signals, not provider invoices. Use the
  provider's billing surface for billing truth.
- The plugin cannot infer an unresolved identity-bearing target safely. It must
  stop and ask instead of mutating a nearby repository, tenant, database, or
  deployment.

## Validate a checkout

From the repository root:

```bash
python -m unittest discover -s tests -v
python -m json.tool plugins/ygt-harness-router/.codex-plugin/plugin.json >/dev/null
python -m json.tool .agents/plugins/marketplace.json >/dev/null
git diff --check
```

If this checkout contains the optional public plugin validator, run it as well:

```bash
python scripts/validate_plugin.py plugins/ygt-harness-router
```

The CI workflow runs the same contract checks. It never depends on a private machine path.

## Contributing and support

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. For a
security issue, use the private process in [SECURITY.md](SECURITY.md); do not
publish credentials, tokens, or a weaponized proof of concept in an issue.

## License

YGT Harness Router is released under the [MIT License](LICENSE).
