# Parallel replay state filling proposal

The corrected owned-thread proposal supports a live efficiency trial after the
current frozen-policy campaign completes. Production is untouched;
`production.patch` is a review artifact, and its environment gate defaults off.

Eight alternating measured rounds, after one warmup pair per batch size:

| Batch | Sequential median | Two-worker median | Host-fill reduction |
| --- | ---: | ---: | ---: |
| 2048 | 13.134 ms | 6.925 ms | 47.28% |
| 4096 | 25.987 ms | 13.920 ms | 46.43% |

Both methods called the actual production `_fill_state_rows` on the same
fixed-seed indices, ring fp16 and bank fp32 sources, with disjoint fp32 outputs.
Every result matched its NumPy row oracle exactly, including bank precision.
All copied source hashes were unchanged. The corrected-owner observation peaked
at 767,229,952 bytes RSS with two persistent owned workers and nested math
threads limited to one. This was one observation, fixed at eight rounds before
collecting results, saved as `copied-pool-owned-workers-v2-20261016.json`; it was
not repeated or extended. Its exact source is preserved under
`owned-workers-v2-before-exit-policy/`. The final proposal changes its worker
daemon policy for early process exit; normal ticket/drain/join behavior is
unchanged. No timing rerun was made for that lifecycle-only change.

The earlier ThreadPoolExecutor observation remains separately preserved in
`copied-pool-20261016.json` (4096: 25.512 to 13.777 ms). These observations use
different copied sources and runtime intervals, so they do not establish whether
the corrected owner is faster than ThreadPoolExecutor.

The source pool contains 4096 ring rows and 512 rows from each bank. Each bank's
`CURRENT.json` was resolved once; both fields and metadata came from that
immutable generation, with stride padding excluded. Read-only mappings pin
opened files; cleanup before all files open fails the observation instead of
silently changing generations. Ring reads do not acquire the trainer's lock and
can mix concurrently overwritten fields. This measures copying, not behavior or
Bellman targets.

The initial observation failed a combined RSS/source-immutability guard before
results were saved. Exact failing values and timing arrays are unavailable.
`attempt-1-failed-guard.json` preserves that failure; no accepted estimate comes
from it. Bounded copy chunks and per-process mmap advice were then added to
limit residency from random mmap fault-around. Each later observation is saved
separately, including all timings, source and code hashes.

## Superseded integration

The first production proposal is withdrawn: CPython can enqueue work in
`ThreadPoolExecutor.submit()` and then fail to start a new thread before
returning its Future. Draining returned Futures alone allowed an unreturned
destination writer to outlive the replay lock. Independent review reproduced
this in the actual patched replay. Original code, patch, manifest and readiness
receipt are retained under `superseded-proposal-v1/` in the analysis directory.
The revised standalone prototype also uses the corrected owner.

## Corrected unapplied integration

`build_proposal.py` generates `production.patch` and a manifest binding original
and proposed hashes. Only `replay_buffer.py` and `agent.py` change:

1. One lazy two-thread owner belongs to each replay buffer.
   `DQN_PARALLEL_STATE_FILL=1` enables it for direct `sample_into` with the existing
   native backend. Default-off, allocating and native-missing paths remain
   sequential. Treat the gate as restart-only for the initial live trial.
2. Sampling, quotas, RNG and alias validation remain in the parent under its
   replay lock. Workers receive stable source/index references and disjoint
   outputs. They acquire no replay or model lock and draw no RNG.
3. All Thread objects are recorded before starting any thread; both startup calls
   return before output work is published. Every job ticket exists before queue
   insertion. Atomic pending-to-running or pending-to-cancelled transitions
   serialize destination access. On publication failure, including after queue
   insertion, pending tickets cancel and running tickets drain before the parent
   releases outputs or the replay lock. Worker failures retire the owner too.
   Failed output pairs are discarded; allocating sampling stays available.
4. `agent.stop()` stops prefetch, then closes the replay owner. Normal shutdown
   drains and joins owned workers. Exercised wait/join interruptions are delayed
   until claimed writers and observed live threads finish. Interrupted shutdown
   retains its owner for retry; failed-start owners and all Thread references
   remain conservatively retained for inspection and later shutdown. Uncertain
   late startup has no output job and sees the stop event. No replacement owner
   starts after failure.
5. Workers are daemon threads so an outer setup failure before `agent.stop()`
   cannot hang interpreter exit and defeat process supervision. They only write
   disposable batch outputs, never the replay ring or persisted files. Normal
   operation still requires explicit drain/join; daemon policy concerns terminal
   process exit, not buffer reuse.
6. Cumulative status uses an independent scalar cache lock, avoiding replay-lock
   waits in metrics polling. Telemetry retains no ndarray. Pipeline snapshots
   expose gate, backend, owner existence, closure and completed-batch counts.

The 32 tests apply the actual patch to a temporary copied package and import its
real replay buffer. They cover all tuple fields/RNG parity, bank/no-bank paths,
source immutability, aliases, insert/flush exclusion, publication errors before
and after queue insertion, pending cancellation, Thread.start failure before and
after real startup for both worker indices, wait and real join interruption,
owner reuse and shutdown recovery, sequential fallback, and status while replay
is locked. The exact agent stop method is compiled from copied source without
constructing a CUDA agent. Bounded subprocess tests verify successful fill then
normal main exit or uncaught main failure without an explicit close. Standalone
tests cover duplicates, vector tails, empty ring/banks/batch, fp32 precision,
nonfinite values, signed zero, subnormals, fallback sources and generation pinning.

Failure handling covers ordinary startup/publication errors and the exercised
wait/join interruptions. It does not promise recovery from arbitrary repeated
asynchronous exceptions at any instruction, process termination or a permanently
hung native call.

## Scope and next trial

This is host-copy evidence. The small copied pool differs from a 6M-row ring in
cache and NUMA behavior. Pageable outputs exclude pinned placement and H2D.
Two workers can compete with actors, persistence and model service. A shorter
host fill does not establish faster useful training FPS, learning, or game play.

After the frozen-policy campaign, review the manifest and precommit a live A/B/A
trial with fixed settings, identical durable restart/recovery treatment, a
protected recovery checkpoint and valid runtime receipts. Compare optimized
samples/second and update rate, replay insert/actor throughput, host sample and
priority timing, collector wait, inference latency, CPU/RSS, bank writer health
and errors. Retain only a useful throughput improvement without actor/runtime
regressions. Frozen complete-game confirmation gates remain unchanged for any
playing-strength claim.

```bash
.venv-gb300/bin/python -m unittest \
  Robotron.tools.parallel_replay_proposal.test_parallel_replay \
  Robotron.tools.parallel_replay_proposal.test_production_proposal -v

git apply --check Robotron/tools/parallel_replay_proposal/production.patch
```

Receipts: `Robotron/logs/managed-learning-20261015/run-26/parallel-replay-analysis/`.
