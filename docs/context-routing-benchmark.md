# Context Routing Discovery Benchmark

Date: 2026-07-12 UTC. Repository: `IamYGT/ygt-harness-router`.

## Contract

Twenty fresh Codex sessions compared four isolated routes across five read-only
repository tasks. Model, reasoning effort, repository and prompts were held
constant. Route order used a Latin-square rotation. Raw JSONL, stderr and the
machine-readable result set are stored locally under
`/root/.codex-lab/context-benchmark/` and are intentionally not committed.

This is a discovery sample (`n=5` per route), not a global performance claim.
Five comparable matrices (`n=25` per route) are required before changing broad
defaults based only on performance.

## Result

| Route | n | Wall median | Wall mean | Total wall | Mean uncached input | Quality proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | 5 | 33.531 s | 34.657 s | 173.283 s | 19,848 | 100.0 |
| Serena | 5 | 36.649 s | 38.063 s | 190.315 s | 28,584 | 93.3 |
| Context Mode | 5 | 64.826 s | 56.211 s | 281.054 s | 24,646 | 93.3 |
| Combined | 5 | 34.702 s | 39.065 s | 195.327 s | 31,938 | 93.3 |

On these small/medium tasks, base had the lowest median, mean and total waiting
time. Combined was 3.5% slower at the median and 12.7% slower by total wall time.
Serena was 9.3% slower at the median. Context Mode was 93.3% slower at the
median. All twenty processes exited successfully.

The quality proxy checked required repository evidence strings; it is not a
blind human review. Three non-base outputs omitted one requested evidence token,
so the benchmark does not justify a quality advantage for extra context layers.

## Decision

Do not force Serena or Context Mode on every message. Route before session start:

```text
small bounded task           -> base
symbol/cross-file task       -> serena
large output/long session    -> context-mode
both pressures               -> context-lab
unassessed task              -> context-lab (quality-first fallback)
```

The expected user wait is:

```text
startup + reasoning + tools + output processing + synthesis + retries
```

Serena and Context Mode reduce time only when saved retrieval/output-processing
work exceeds their startup and instruction overhead. The next benchmark matrix
should use larger symbol graphs, large build logs and multi-compaction sessions;
the current sample proves the small-task bypass, not that the tools lack value.
