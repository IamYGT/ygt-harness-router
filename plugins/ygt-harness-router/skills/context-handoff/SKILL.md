---
name: context-handoff
description: Produce compact, durable Codex handoffs across agents, compaction, and resumed sessions without losing the done contract, evidence, or blockers. Use before compaction, at a child boundary, or when a task must continue in a fresh session.
---

# Context Handoff

Treat a handoff as a lossless engineering checkpoint, not a transcript summary.
Keep it short enough to reload and precise enough that the next agent does not
repeat discovery.

## Required handoff record

Use this order and omit empty sections only when they are genuinely irrelevant:

```yaml
objective: "One sentence"
done_when:
  - "Observable acceptance criterion"
forbidden:
  - "Prohibited outcome or mutation"
exact_target: "Repository/path/account resolved by read-only discovery"
state: "What is true now"
changed_paths:
  - "path/to/file"
decisions:
  - decision: "Selected approach"
    reason: "Evidence or contract reason"
    rejected: "Strongest rejected alternative, if material"
evidence:
  - command: "exact command"
    result: "PASS|FAIL|BLOCKED"
    detail: "Smallest useful excerpt"
blockers: []
next_action: "One concrete next action"
route:
  owner: "root|child name"
  model: "model id"
  remaining_budget: "known value or unknown"
```

## Boundaries

- Preserve exact paths, test names, error text, and unresolved target identity.
- Summarize large logs; retain the command, exit status, and one diagnostic excerpt.
- Record decisions and rejected alternatives so a resumed agent does not reopen them.
- List files actually changed, not files merely inspected.
- Separate observation from inference; label an inference explicitly.
- Redact secrets, bearer tokens, cookies, private keys, and sensitive prompt content.
- Never use a handoff to authorize a destructive operation or an unresolved target.

## Child receipt

A child handoff is complete only when it states its owned paths, tests run, exact
results, remaining blockers, and whether the parent must inspect a diff. The parent
must acknowledge the receipt and integrate it before claiming completion. A child
that exits without a receipt is `incomplete`, not `passed`.

## Compaction checklist

Before compaction, update `state`, `changed_paths`, `evidence`, `blockers`, and
`next_action`; include the current phase and route. After compaction, check that the
next tool call advances `next_action`. If the agent starts rereading unchanged
files or repeating a fingerprinted command, stop and use duplicate diagnosis.
