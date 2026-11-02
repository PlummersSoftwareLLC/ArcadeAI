Coherent persisted-start snapshot proposal — UNAPPLIED, REVIEW ONLY

No production file, live process, control, model, replay, or GPU was changed by
this preparation. coherent-snapshot.patch is the proposed production change.
staged/ contains complete source copies for inspection, not installed modules.
The startup opt-in is DQN_COHERENT_SNAPSHOT=1. It must be deployed in a later
reviewed restart, after the current frozen quality campaign finishes.

Purpose and limits

This captures one coherent persisted model/target/Adam/scaler/clocks plus current
ring data, priority leaves, pointer/size/max-priority metadata and fresh selected
HOF/EpHOF generations. It supports equally fresh experiment branch starts.
It does not save Python/NumPy/Torch/MAME RNG, game/emulator states, actor histories,
pending n-step tails, replay adaptive histories, or exact asynchronous scheduling.
Both branches must use the same archive and fresh client/server resets. It does
not promise deterministic paired trajectories or exact continuation.

The gate parks Python frame/accept handlers and game-settings HTTP writers. It
does not SIGSTOP MAME or freeze game time. Copying/hashing 267GB can exceed MAME's
3.5-second action deadline: clients may time out/disconnect/retry while handlers
remain parked. The controller performs no fleet restart. A later operator-owned
branch launch must start fresh actors; uninterrupted live games are not claimed.
After successful cleanup the application gate reopens, and live sources may
change again. The independent archive and its certified boundary remain fixed.

Why the existing primitives alone are insufficient

* main.py:1258 saves before server.stop(): an ordinary shutdown save message does
  not establish a coherent ring/priority/client-clock boundary.
* AsyncReplayBuffer.stop() sets running=False, drains the public queue, then
  joins. A consumer may still own a fetched private batch. Queue.empty() and the
  shutdown path therefore do not prove its writes finished. The existing FIFO
  barrier after all producers park does provide the required ordering.
* ManagedMeasurement pauses the learner and gates measurement replay, but still
  runs game clients and has evaluation/timeout/restore lifecycle effects. This
  proposal uses a narrow frame boundary rather than repurposing a quality leg.
* Prefetch.invalidate() waits the old producer epoch and discards ready batches.
  A worker-owned lease can remain, but its invalid epoch and paused flags prevent
  a later update after it acquires the training lock.
* Bank persistence holds _bank_persist_lock through generation publication and
  garbage collection. Pinning CURRENT alone cannot stop later generation GC.

Protocol and lock order

1. A main-thread request is accepted only when explicit startup opt-in is active,
   keyboard-thread creation was disabled at startup, no measurement/ratchet is
   active, and expected trainer PID/start ticks plus ring path/device/inode match.
   The request tag/UUID are constrained and the destination is exclusive.
2. Close the registered-worker gate. Accept loop and existing handlers park at
   their next complete frame boundary; handlers flush pending local frame counts
   before acknowledging. Exiting handlers complete their cleanup/reset enqueue
   before unregistering. New handlers/settings writers cannot start mutations.
   A gate timeout/error cannot be certified as quiescent.
3. Disable learner flags, acquire the learner RLock, pause/invalidate prefetch,
   and explicitly synchronize the owned learner CUDA device (CPU is a no-op).
   No CUDA calls were made during proposal testing; the barrier is injectable.
4. Enqueue and wait for a bounded FIFO replay barrier. All previously accepted
   commands, including an already-fetched private batch, precede the barrier.
   The consumer must remain alive and no drain command failure may be newly
   observed. Nested historical helper errors/old data quality are not certified.
5. Wait for the bank writer. Call memory.save BEFORE acquiring replay.lock;
   replay.lock is plain, not reentrant. save refreshes live priority/meta and
   bank capture ages. It can swallow bank errors, so saved revisions, fresh
   CURRENT selection and bank capture/add/staleness metadata are verified later.
6. Acquire bank-persist lock, then replay lock. Hold both through archive copy
   and readback hashing. This pins generation lifetime and blocks source writes.
   Inspect current mmap backing, pointer/size/max priority and exact priority
   leaves. The nested agent.save(save_replay=False) only reacquires its RLock and
   metrics lock; its replay persistence branch is disabled.
7. Save the model, independently copy ring/selected banks/settings/control and
   source files, fsync and verify hashes. No live-data hardlinks or reflinks are
   used. CURRENT's selected generation is copied; its previous generation is not
   required by the loader and is intentionally not included as another fallback.
8. Compare before/after clocks, replay pointers/adds/bank revisions/epochs,
   natural and override policy controls, canonical config/control/game settings,
   manual LR/gear/anchor and actual optimizer-group learning rates. Verify source
   and settings/control signatures. Stale loaded control or RAM/disk settings
   mismatches are rejected, not silently reconciled.
9. Release replay/persistence locks, restore the prior prefetch/learner flags,
   reopen the gate, then atomically publish COMPLETE.json only after cleanup
   succeeded. A failed copy keeps a partial artifact with FAILED.json and no
   COMPLETE certificate. Failed cleanup keeps training/gate paused and main-loop
   mutation paths parked for coordinated recovery; no automatic unsafe fallback.

Timeouts bound waiting at gates, locks, replay enqueue/barrier and an existing
bank writer. Copy/readback checks the deadline between chunks. Individual model
serialization, synchronous bank writes, fsync and filesystem calls cannot be
safely interrupted, so this is a cooperative deadline rather than a hard I/O SLA.
Disk free-space checks are advisory and concurrent disk use can still cause a
handled failure. Durability assumes functioning filesystem fsync semantics.

API and dashboard

The existing activity row says "Saving matched-start snapshot" and exposes phase,
elapsed time and copied/total source bytes. Cleanup failure says "Snapshot failed
· recovery required". /api/now uses a lock-only status overlay independent of
model/replay/telemetry reads, so it remains responsive even when its background
sampler is waiting for the archive's replay lock. Cached training-metric timestamp
is retained as snapshot_base_metrics_ts; training is explicitly paused/FPS0 in
the overlay. This status does not claim the cached training metrics are fresh.

Future request schema (example only — NOT a live request)

The future main thread consumes MODEL_DIR/coherent_snapshot.request.json after
the normal control refresh. No CLI or request file was installed or invoked.
All fields are required; use the actual PID/start identity and ring directory
identity from the intended newly deployed process:

  {"tag":"lr-paired-seed", "request_id":"0123456789abcdef0123456789abcdef",
   "expected_pid":12345, "expected_start_ticks":"123456789",
   "expected_ring_dir":"/dev/shm/robotron_dqn_latest_replay",
   "expected_ring_device":123, "expected_ring_inode":456, "timeout_s":7200}

Artifacts go to MODEL_DIR/coherent-snapshots/TAG-UUID/. COMPLETE.json is the
certificate; INCOMPLETE.json or an existing directory alone is never success.
Claimed request/results remain available for audit. Source/ring identities and
artifact hashes must be reviewed before any later branch restore. Changing model
directory alone does not isolate the current shared tmpfs replay basename.

Validation and review

  python Robotron/tools/coherent_snapshot_proposal/build_proposal.py
  git apply --check Robotron/tools/coherent_snapshot_proposal/coherent-snapshot.patch
  CUDA_VISIBLE_DEVICES='' .venv-gb300/bin/python -m unittest Robotron.tools.coherent_snapshot_proposal.test_coherent_snapshot -v
  CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-gb300/bin/python -Xgil=0 -B -m unittest Robotron.tools.coherent_snapshot_proposal.test_real_replay_roundtrip -v

The original 20 tests use tiny temporary memmaps, real threading/locks/FIFO consumer logic and
AST-executed proposed HTTP/keyboard/device/API paths. They test the persisted
payload, non-reentrant save ordering, in-flight private batches, frame-count
flush/new-handler races, generation lifetime after later GC, stale control/RAM
settings, identity/source replacement, LR drift, copy/deadline/prefetch/writer
failures, fail-closed cleanup and truthful responsive pause status. The actual
prefetch invalidate method is tested without constructing Torch or CUDA objects.

Two additional CPU round-trip tests exercise actual PrioritizedReplayBuffer
admission/save/load with a wrapped 32-row ring and both selected HOF/EpHOF bank
generations. AST-extracted production agent.save/load methods serialize and
restore toy Linear online/target models, actual Adam state and a CPU GradScaler.
Two fresh branches restore equal ring fields, priority leaves, metadata, bank
contents/ages and model/optimizer/scaler state. Deliberately different pre-load
sentinels verify the saved frame/learner/measurement/training/sample clocks,
epsilon/expert controls, target-update clock, LR gear/anchor and optimizer LR
are restored. One further CPU Adam step also matches using identical test inputs.
The sampler parity check explicitly sets
equal test RNG states; the archive does not restore RNG. Later synthetic live
ring writes and bank generation garbage collection leave archive hashes and a
subsequent reload intact. No CUDA context is initialized.

The independent reviewer passed the final strengthened tests in 1.280s; an
additional captured run passed in 1.278s. Read-only, hash-sealed evidence is under
Robotron/logs/managed-learning-20261015/run-26/coherent-snapshot-analysis/,
including the byte-identical original 20-test log, original source manifest and
validation, unchanged patch, new test source, captured CPU test log and hash
receipt. The earlier test version/run is retained with an -initial suffix.
The final new test source SHA256 is
51634208837d612219b68cf5ef9cecd7d954ce2b96097f3bf4c8186fe0d44e43.
The patch SHA256 remains
31dd8553f505f383c21b3df5631efb5a8064dab73c4503b30176940f15f70717.

These tests do not validate the actual Rainbow network, fused CUDA optimizer,
whole trainer restore, real device synchronization, or large storage I/O. Those
still require a separately reviewed isolated smoke before live snapshot rollout.
Applying runtime.json/manual LR scale and configuration consistently to each
branch remains the responsibility of the future reviewed branch launcher.
