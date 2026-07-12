# Direct Model Routing Benchmark

Date: 2026-07-12 UTC. Five matched fresh sessions per model implemented the same
small login-storage contract in isolated disposable repositories. Every run used
base context, no subagent, workspace-write, the same prompt and the model's
configured effort (`Sol medium`, `Terra high`, `Luna xhigh`). All 15 runs passed
the focused test and changed only the intended source file; Python generated an
untracked `__pycache__` during independent verification.

| Model | n | Success | Wall median | Wall mean | Mean uncached input | Mean output | Mean reasoning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Terra | 5 | 5 | **27.486 s** | **26.611 s** | **18,071** | 1,389 | 472 |
| Sol | 5 | 5 | 27.755 s | 28.483 s | 19,976 | **925** | **122** |
| Luna | 5 | 5 | 41.535 s | 46.005 s | 23,323 | 2,330 | 1,280 |

Luna xhigh was 51.1% slower than Terra at the median and used 29.1% more mean
uncached input. The evidence rejects automatic Luna for this task class. The
pre-session launcher therefore defaults small bounded writes to Terra medium;
`luna-worker` remains an explicit experimental route. Raw JSONL and machine data
remain local under `/root/.codex-lab/model-routing-benchmark/`.
