# Transport recovery fix

`preview_socket_recovery.py` only prints a patch against the reviewed old
Lua/server sources, or nothing when the exact reviewed patch is already applied.
`test_socket_recovery_proposal.py` extracts and executes the actual production
methods in memory. Static pre-fix fixtures under `fixtures/socket_recovery_before.*`
reproduce the old defects independently of current source or log artifacts. The
suite imports no production agent, replay, or Torch module and launches no MAME:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s Robotron/tools -p test_socket_recovery_proposal.py -v
python3 Robotron/tools/preview_socket_recovery.py
```

The preview requires exact old anchors or the exact reviewed final source hashes;
it fails on unexpected drift. The actual-source tests also compare transformed
fixture bodies with deployed file bodies. `test_socket_wait.py` now requires a
closed connection and `socket_ok=false` on timeout. Applying source files does not
reload an already running trainer or fleet; process changes remain a separate
coordinated step.

## Confirmed defects

1. `main.lua:3646` discarded partial bytes after a 3.5-second timeout while leaving
   the TCP stream open and returning `socket_ok=true`. Actions have no request ID.
   The actual Lua CPU harness demonstrates late action N applied to state N+1,
   then action N+1 applied to N+2. A partial timeout can also shift byte alignment.
2. `SocketServer._recv_exact` lost partially consumed header bytes at its timeout;
   the handler interpreted the remaining header plus payload as another length.
   The actual method/socketpair test reproduces this loss. Zero-byte idle polls
   are safe and remain allowed; a partial timeout now raises and closes the client.
3. `AsyncInferenceBatcher.infer` cancelled only queued work. If the 250ms deadline
   expired after dispatch, it launched solo work while the same state remained in
   an active batch. The original-code CPU test records one batch plus one solo
   call. Batch errors/missing results could also become apparently valid neutral
   actions through fallback exception handling.

## Patch contract

Lua closes the connection on timeout, clears its receive/preview state through the
existing close function, and returns `socket_ok=false`. Its existing reconnect
path creates a separate stream. Healthy 3/5/6-byte parsing, actions, frame timing,
and inference numerics remain unchanged.

The server uses a monotonic receive deadline. Only a timeout with zero bytes read
returns idle `None`; partial headers/payloads raise `ConnectionError`. The existing
handler exception path closes the connection and latches a frozen-leg failure.

The batcher has one absolute deadline across queue admission and completion. It
never calls solo inference. Timeout, stop, malformed/incomplete output, and model
failure raise to the handler instead of fabricating an action. A lock-protected
pending registry wakes all waiters on stop; late in-flight work cannot overwrite
the failure. CUDA work already dispatched may finish once, then is discarded.
Whole-batch validation runs before publishing any successful result. Current
agent/sidecar methods return Python int/int/bool and indices 0..8 as required.

The initial strict 250ms setting produced frequent disconnects in the 128-actor
run07 fleet (roughly two disconnects per second during the observed window).
The configured server default is now 3000ms for queue admission plus completion,
retaining nominal 500ms headroom below Lua's 3500ms whole-roundtrip timeout. Replay
enqueue, frame parsing, and transport also consume wall time, so this is not a
guarantee that every server timeout precedes Lua's deadline. Explicit shorter
batcher deadlines remain supported and tested. Expiry still raises and closes;
there is no duplicate inference or silent neutral success. The longer deadline
changes overload tolerance, not healthy actions, batching wait, policy, or
learning settings. Validate reconnect/error rates after the coordinated reload.
Main Lua's 3ms compatibility heuristic for distinguishing legacy packet lengths is
unchanged; it is still not a general solution to arbitrarily delayed TCP fragments.

Any protocol source change requires a fresh same-backend 16M reference before
comparison with a future 32M candidate. Runtime failures must still invalidate
quality legs, with all started games/tails counted.

## What remains unproven

The old bank disk-write lock pause was directly measured and separately fixed.
Later fleet-wide timeout bursts and persistent 5.5k versus 8k FPS phases have not
been attributed. This patch corrects three demonstrated failure paths; it does
not establish the cause or promise a throughput gain.

The serving system is closed loop: each actor waits for a reply, a single worker
collects for up to 1ms (maximum 128), then releases a group. Grouped arrivals can
split into different batch sizes and service cycles. `_run_inference` serializes
under `_sync_lock` through the CPU result readback; solo fallback could create a
convoy behind this lock. Training periodically copies weights on the inference
stream. These mechanisms justify measurement, not a causal claim. Existing
`inference_ms` measures handler wait including queue/fallback/lock time, not GPU
kernel duration. Low host-wide CPU usage does not distinguish these mechanisms.

## Next bounded diagnostics (separate from this correctness patch)

Expose cumulative counters plus interval deltas in API/CSV, using bounded fixed
latency buckets rather than retained request histories:

- Requests queued/dispatched/completed; current/high-water queue and in-flight
  size; batch count, size sum/max, and size buckets (1, 2-8, 9-32, 33-64, 65-128).
- Queue age, batch collection time, `act_batch` wall time, and request total time
  (total/max and fixed p50/p95/p99 buckets); queued/in-flight/admission timeout
  counts; model/malformed-result errors and stopped requests. Solo fallback
  counter remains zero by contract after this patch.
- Separate `_sync_lock` wait, inference-stream/readback time, and inference
  weight-copy duration/count. A host timer alone cannot measure pure GPU compute.
- Handler phase and elapsed maximum around header/payload receive, replay enqueue,
  inference, and send. Replay queue occupancy/high-water and enqueue blocked
  total/max distinguish replay backpressure from inference serving delays.
- Publish `memory.get_bank_persistence_stats()` through existing telemetry so
  capture chunk lock maximum, deferrals, write failures/duration, active writer,
  dirty revisions, and last error are visible without reading private fields.

Collect matching stable fast/slow windows with the same actor count/policy. Only
then try one bounded batching-wait or maximum-size change, with no quality cohort
active. Compare actual interval frames/s and samples/s, latency tails, batch-size
distribution, errors/reconnects, and GPU utilization. Do not add artificial actor
phase jitter or change policy/sticky-fire behavior before these measurements.
