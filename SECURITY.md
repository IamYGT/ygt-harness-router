# Security policy

## Supported versions

Security fixes target the latest release on the `main` branch. Pin a known-good
tag when consuming the plugin in an automated environment and upgrade after
reviewing the changelog and validation results.

## Report privately

Please report a suspected vulnerability through a **private GitHub Security
Advisory** for [IamYGT/ygt-harness-router](https://github.com/IamYGT/ygt-harness-router/security/advisories/new).
If that channel is unavailable, contact the repository owner through a private
GitHub message and request a security-report channel.

Do not open a public issue for an undisclosed vulnerability. Do not include live
API keys, bearer tokens, cookies, SSH keys, customer data, or a weaponized
exploit in the report.

Include only what is needed to reproduce the problem safely:

- affected commit or release;
- Codex version and operating system;
- plugin component and configuration surface;
- minimal reproduction with all secrets redacted; and
- impact and a suggested mitigation, if known.

We will acknowledge a report when practicable, investigate it, and coordinate a
fix or mitigation before public disclosure. Response and disclosure timing may
depend on severity and the reporter's preferred contact channel.

## Security boundaries

YGT Harness Router is local orchestration code. It does not provide an identity
provider, token vault, billing service, or tenant boundary. Users remain
responsible for:

- Codex account and model permissions;
- sandbox and filesystem permissions;
- marketplace source and Git ref trust;
- MCP servers, connectors, and custom hooks; and
- retention of Codex logs, CI artifacts, and telemetry.

The plugin must never print or commit secrets. See [docs/privacy.md](docs/privacy.md)
for the data-handling contract.
