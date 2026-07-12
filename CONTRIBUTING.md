# Contributing

Thanks for improving YGT Harness Router. The project values a small complete
patch, explicit evidence, and predictable capacity over clever orchestration.

## Before you start

1. Read the [README](README.md), [architecture](docs/architecture.md), and
   [validation contract](docs/validation.md).
2. Search existing issues and pull requests before opening a duplicate.
3. For a behavior change, write the observable contract first: objective, done
   evidence, scope, and prohibited outcomes.
4. Do not include secrets, private paths, customer data, or raw session logs in
   an issue, branch, commit, or pull request.

## Development setup

```bash
git clone https://github.com/IamYGT/ygt-harness-router.git
cd ygt-harness-router
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip pytest
```

The plugin itself runs inside Codex; the Python environment is for repository
contract tests and validation helpers.

## Change guidelines

- Keep plugin manifest paths and marketplace entries valid.
- Prefer native Codex configuration over hidden shell-side behavior.
- Keep read-only inventory lanes read-only.
- Preserve finite thread/depth/runtime limits.
- Emit structured receipts and exact evidence for child work.
- Do not claim cost savings without measuring quality, rereads, retries, and
  wall-clock impact as well.
- Add boundary and failure-path tests for routing or hook behavior.
- Keep documentation honest about preview APIs and version-specific keys.

## Checks before a pull request

```bash
python -m pytest -q
python -m json.tool plugins/ygt-harness-router/.codex-plugin/plugin.json >/dev/null
python -m json.tool .agents/plugins/marketplace.json >/dev/null
git diff --check
```

If present, also run:

```bash
python scripts/validate_plugin.py plugins/ygt-harness-router
```

Describe the exact commands and results in the pull request. If a check is
unavailable because it requires Codex credentials or a local-only integration,
say so explicitly rather than substituting a weaker claim.

## Pull requests

Use a focused title and explain:

- the user-visible contract;
- why the chosen lane/configuration is appropriate;
- tests and smoke checks run;
- privacy or compatibility impact; and
- any follow-up or known limitation.

Keep unrelated formatting or generated changes out of the same pull request.
Maintainers may ask for a smaller patch when review and rollback would otherwise
become difficult.

## Code of conduct

Be direct, respectful, and evidence-oriented. Security reports follow
[SECURITY.md](SECURITY.md), not the public issue tracker.
