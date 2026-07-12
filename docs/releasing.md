# Release checklist

This project publishes the plugin and its repository marketplace snapshot
together. Keep the release small, reproducible, and easy to roll back by pinning
the Git ref in downstream installs.

## Before tagging

- [ ] Update the plugin version in
      `plugins/ygt-harness-router/.codex-plugin/plugin.json`.
- [ ] Update user-facing behavior and limitations in `README.md` and `docs/`.
- [ ] Confirm `.agents/plugins/marketplace.json` still points to the intended
      plugin path and policy.
- [ ] Run Python contract tests and JSON/schema checks.
- [ ] Run the public plugin validator if it exists in the checkout.
- [ ] Review `git diff --check` and the final owned diff.
- [ ] Search the release diff for credentials, bearer tokens, private paths, and
      environment-file content.

## Tag and publish

Use a normal annotated tag after the checks pass:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main --tags
```

Do not force-push the primary branch. If the tag or marketplace snapshot is
wrong, publish a corrective release rather than rewriting a public history.

## Post-release smoke

From a clean temporary checkout or an isolated Codex profile:

```bash
codex plugin marketplace add IamYGT/ygt-harness-router --ref vX.Y.Z \
  --sparse plugins/ygt-harness-router
codex plugin list --available --json
codex plugin add ygt-harness-router --marketplace <marketplace-name>
codex plugin list
codex doctor
```

Record the exact Codex version, plugin version, marketplace ref, and command
result. Do not include authentication output, tokens, or private prompt text in
the release record.

## Rollback

Prefer installing the last known-good tag in a fresh profile or pinning the
marketplace ref back to that tag. Do not reset a user's existing checkout or
delete shared Codex state as a rollback shortcut.
