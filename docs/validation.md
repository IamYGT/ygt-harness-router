# Validation contract

Validation is layered and evidence-bound. A higher layer is not a substitute
for a failed lower layer.

## Local checks

Run from the repository root:

```bash
python -m pytest -q
python -m json.tool plugins/ygt-harness-router/.codex-plugin/plugin.json >/dev/null
python -m json.tool .agents/plugins/marketplace.json >/dev/null
git diff --check
```

When the repository includes the optional public validator:

```bash
python scripts/validate_plugin.py plugins/ygt-harness-router
```

The validator must run against the checkout, not a private absolute path. A
missing optional helper is reported as a skipped check, not silently imported
from a developer machine.

## Test layers

1. **Static/schema:** JSON, manifest shape, marketplace source path, and docs
   contract.
2. **Unit/contract:** routing score boundaries, forbidden outcomes, and receipt
   invariants.
3. **Integration:** hooks, agent lifecycle, and isolated temporary state.
4. **Smoke:** install/list/doctor against the Codex version under test.

The repository CI currently guarantees the first layer and Python contract tests.
Run Codex smoke checks on a machine with Codex installed; do not make CI depend
on a private account or secret.

## What counts as evidence

Every release note or completion claim should identify:

- exact command;
- exit status;
- test count or validation summary;
- plugin path and version checked; and
- any skipped check and why it was unavailable.

Never weaken a test to match an implementation. If a contract is intentionally
changed, update the contract test and release note together.
