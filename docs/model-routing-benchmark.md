# Direct Model Routing Benchmark

Date: 2026-07-12 UTC. Five matched fresh sessions per model implemented the same
small login-storage contract in isolated disposable repositories. Every run used
base context, no subagent, workspace-write, the same prompt and the model's
configured effort (`Sol medium`, `Terra high`, `Luna xhigh`). All 15 runs passed
the focused test and changed only the intended source file; Python generated an
untracked `__pycache__` during independent verification.

| Model | n | Success | Wall median | Mean uncached | Mean credits | Mean API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Luna | 5 | 5 | 41.535 s | 23,323 | **1.266** | **$0.0506** |
| Terra | 5 | 5 | **27.486 s** | **18,071** | 2.521 | $0.1008 |
| Sol | 5 | 5 | 27.755 s | 19,976 | 4.712 | $0.1885 |

Luna xhigh was 51.1% slower than Terra at the median, but its official rate made
the measured task 49.8% cheaper in credits. The operator's primary objective is
priced consumption, not raw token count or minimum latency, so the pre-session
launcher defaults this bounded class to Luna. Raw JSONL and machine data remain
local under `/root/.codex-lab/model-routing-benchmark/`.

Pricing formula uses official credits per one million input/cached/output tokens:
Sol `125/12.5/750`, Terra `62.5/6.25/375`, Luna `25/2.5/150`. API-equivalent
rates are Sol `$5/$0.50/$30`, Terra `$2.50/$0.25/$15`, Luna `$1/$0.10/$6`.
