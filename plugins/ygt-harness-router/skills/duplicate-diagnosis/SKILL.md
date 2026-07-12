---
name: duplicate-diagnosis
description: Detect and explain repeated Codex reads, searches, tool calls, retries, and post-compaction rereads using stable fingerprints and current-state checks. Use when work appears to repeat, context grows unexpectedly, or a retry needs justification.
---

# Duplicate Diagnosis

The goal is to distinguish waste from a necessary revalidation. Never skip a
state-changing command, test, build, deployment readback, or security check merely
because its text matches an earlier command.

## Fingerprint

Normalize only noise that cannot change meaning:

- collapse whitespace and normalize harmless path spelling;
- preserve arguments, environment selectors, commit/ref, query predicates, and
  tool name;
- include repository identity, working directory, phase, and relevant file-state
  fingerprint;
- include parent/child session and sequence for cumulative usage events.

Classify each repeat:

- **safe duplicate:** read-only command, same target and unchanged state;
- **necessary revalidation:** state changed, time-sensitive external read, or a
  contract explicitly requires a fresh check;
- **suspect loop:** same read-only fingerprint repeated without new evidence;
- **required retry:** prior failure or transient error and the next attempt changes
  a bounded variable;
- **unsafe to suppress:** write, test, build, deploy, migration, or security check.

## Diagnostic procedure

1. Compare the normalized fingerprint and state hash.
2. Compare the prior result, exit status, and timestamp.
3. Check whether compaction or a handoff erased the evidence; if so, restore a
   context handoff rather than blindly rereading.
4. Ask what new evidence the next call is expected to produce.
5. Suppress only a safe duplicate with a receipt pointing to the prior result.
6. Escalate a suspect loop with the first and latest command, paths, and phase.

## Output

```text
classification: safe duplicate | necessary revalidation | suspect loop | required retry | unsafe to suppress
fingerprint: <stable redacted id>
prior_evidence: <command, exit, timestamp>
new_evidence_expected: <one sentence>
action: reuse receipt | rerun once | stop and hand off | never suppress
```

Do not print secrets while showing commands. A duplicate finding is a diagnosis,
not permission to weaken tests or delete logs.
