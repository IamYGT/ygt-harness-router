# Privacy boundary

YGT Harness Router is designed to keep routing decisions local to the Codex
installation. It does not create a second account, scrape credentials, or send
prompt content to a YGT service.

## Data the plugin needs

For a routing decision, the plugin may need local metadata such as:

- task scope and the requested done contract;
- lane/model/reasoning configuration;
- tool and test status (success/failure, duration, and a short classification);
- changed paths and receipt fields; and
- context, compaction, retry, and child-lifecycle counters.

These are operational signals. They are not a provider invoice and should not be
treated as a complete record of a model's internal reasoning.

## Data the plugin must not collect

Do not store or print:

- API keys, bearer tokens, cookies, SSH keys, passwords, or `.env` values;
- full request/response bodies when they can contain credentials or customer data;
- private repository contents in telemetry by default; or
- a raw prompt transcript merely to calculate a routing score.

If a command output is needed for evidence, retain the smallest redacted excerpt
that proves the contract. Prefer hashes, counts, categories, and paths over raw
payloads.

## Telemetry

OpenTelemetry is optional and controlled by native Codex configuration. If an
organization enables it:

1. use an approved collector and retention policy;
2. set prompt logging to false (`log_user_prompt = false`);
3. avoid putting collector credentials in Git, plugin manifests, or hook output;
4. document the data owner and deletion path; and
5. validate that path and command attributes are not exposing tenant data.

Telemetry should answer questions such as “did compaction reduce rereads?” and
“which gate failed?” It should not become a hidden content export.

## Third-party extensions

MCP servers, browser connectors, and custom hooks expand the trust boundary.
Review their source and permissions before installation. The plugin does not
install a usage-tracking MCP server automatically. If a connector is enabled,
its data handling is governed by that connector's policy as well as your Codex
configuration.

## Local retention

Codex session logs, shell history, CI artifacts, and marketplace caches may
retain information outside the plugin directory. Set retention and file
permissions at the host/organization level, and scrub artifacts before sharing
them publicly.

## Reporting a privacy issue

Do not open a public issue containing a credential or private transcript. Follow
the private process in [SECURITY.md](../SECURITY.md), include the minimum
reproduction, and redact all sensitive values.
