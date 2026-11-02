UNAPPLIED RING-RECEIPT CORRECTION — SOURCE ONLY, UNSELECTED, UNEXECUTED

The original source-only counterexample/design remains in ../elite_bank_replay_
slot_freshness_proposal (selected manifest1e487, finding100969, DESIGN719a).
The held three production sources have NOT been modified. The52,007-byte
unified diff mostly reflects unchanged-body indentation for six destructive-
mutation try/finally fences. No giant candidate copies are installed or saved.
Text-only reconstruction/reversal produces candidate hashes in preservation;
no author AST/compile/import/test/numerical/runtime/model/replay work occurred.

MINIMUM PRODUCTION CHANGE
replay_buffer.py: process-local opaque epoch OBJECT, successful-write serial and
pointer anchor; no per-slot generation array. All successful inserts (including
legacy callers) advance serial. add_with_receipt returns(idx,epoch,serial) only
inside the existing lock after all original fields/exposure publication succeed.
A partial insertion rethrows the original error, emits no receipt and invalidates/
reanchors before unlock. clear/flush/array restore/mmap adoption/ensure/promotion
invalidate before mutation and reanchor actual final pointer in finally, including
failure. A token must be same-epoch and age0..capacity-1; current pointer, tree/
capacity/size/livebounds must agree. No loaded row is certified from its index.

agent.py: one common ingestion implementation; default step still returns its
legacy integer, memory.add still returnsNone. Opt-in step_with_receipt passes the
actual atomic insertion tuple through; it never reconstructs it from currentptr.
Existing action conversion, reward, priorities, actor labels and exposure calls
remain the original operations. Adam/model/loss/target/prefetch are untouched.

socket_server.py: the real async consumer requires the receipt-capable agent
before starting its thread. Each existing bounded history retains serial INTS,
with one epoch/completeness marker per deque; no per-entry triple is retained.
The tuple returned by ingestion is transient. Epoch change with pending prefix
or episode-deque eviction marks the episode incomplete. clear resets the local
history epochNone/completeTrue at existing callback boundaries; next new receipt
binds it to the actual current epoch. Dictionary-wide clear/removal also removes
all associated receipt state, without changing frozen_evaluation.py.

Both banks receive the same offers and adaptive episode stats even when their
whole incomplete/stale/unknown episode is refused. No surviving tail is silently
called complete. Learner-kind inspection, bank copy, predeath reward/priority,
elite priority and interesting-label writes each resolve receipts INSIDE their
existing plain replay lock and keep that lock through read/write; no validate-
unlock-use pattern or nested replay lock. Callbacks clear/FIFO-reset histories
as before. The current disabled predeath reward repaint stays disabled.

PUBLIC/PRIVATE COMPATIBILITY LIMITS
Legacy integer-index bank/mutation APIs keep their defaults and remain incapable
of proving delayed residency without opt-in receipt_context. New production
async calls always supply context, including unknown/incomplete refusal; it does
not silently fall back to legacy. Internal _client_indices/_episode_indices now
hold serials, so private tests/debug consumers must not treat them as slot IDs.
Old fake agents lacking step_with_receipt are intentionally rejected before
worker startup; update mocks, do not weaken the production capability guard.
No public replay serialization fields, bank arrays/schemas/generations, existing
_adds_total, ReplayInsertExposure epochs, schedules, controls or model geometry
are changed. Existing stored banks are neither altered nor retrocertified.
Ordinary sample->GPU->update_priorities still uses legacy indices: this separate
possible staleness path is explicitly NOT fixed or claimed safe by this patch.
External ndarray/mmap writers that bypass enumerated APIs cannot be detected by
O(1) metadata; exclusive in-process ownership is a prerequisite, not new evidence.

EXPLICIT SHUTDOWN CHANGE
Normal consume and stop-drain share one receipt-recording step helper. A stop-
only lock serializes callers without adding a hot-path lock. stop setsrunningFalse,
joins the existing consumer BEFORE caller drain, and raises TimeoutError without
second consumption if the worker remains alive after5s. Already-prefetched work
therefore finishes before queued drain; reset/barrier acknowledgments retain
order among commands actually consumed. This is a new fail-closed shutdown
behavior. A late producer already in queue.put can still publish after drain:
SocketServer.stop does not join client handlers. No claim of producer quiescence,
all in-flight command persistence, completed save tail or atomic shutdown is made.
No Queue.shutdown dependency or producer hot-path lock is added. A stop failure
retains pending commands; there is no second consumer/retry/adoption/cleanup
hidden in this proposal. Callers may currently catch stop errors; root must keep
honest failure evidence and verify actual owned closure for any future deployment.

DEFERRED VALIDATION — ROOT ONLY AFTER ENTIRE QUALITY FREEZE RELEASE
First run the original six characterization tests against pinned held bases.
Then run the eleven new correctness tests once under bounded CPU resources;
they reconstruct the patch IN MEMORY, authenticate/reverse every source delta,
and execute exact selected method ASTs with explicit small NumPy/fake dependencies.
No project modules, torch, sockets, mmap/file writes or actual project worker
threads are imported/started. Virtual mmap tests refuse unexpected host calls.
Tests cover legacy/receipt outputs and alladd clocks; freshbothbanks/FIFO reset;
foreign-wrap wholebank refusal with offers/stats; overflow/epoch-boundary flags;
all selected delayed-write refusal under same nonnested plain lock; pre/posttree
insert failures; clear/flush/nonzero restore; ensure/promote failure/adoption
using virtual arrays; ageC-1/C/crossbuffer/livebounds; stop join/drain/reset/barrier/
stop-lock ordering and alive-worker timeout refusal. Stop tests use strict fake
worker/lock seams, not a live concurrency or producer-quiescence stress proof.
All eleven remain UNEXECUTED. Preliminary draft fixture issues were caught by
source-only author review (unittest.run name and class lexical RHS); old bytes
are preserved in the single draft-history subtree, not reported as executed runs.

independent-ring-residency-source-proof.json is runtime_review's invariant/
mutation-path audit bound to held sources and this fixed unapplied patch; it is
NOT complete candidate approval or test execution. Final independent full patch/
fixture review is a separate root-assigned step.

BEFORE ROLLOUT
Obtain actual baseline6 +patch11 results, meaningful fault/concurrency coverage,
then bounded incidence/cost evidence after freeze. O(1) global counters do not
imply zero overhead: serial/history bookkeeping, per-callback validation and
Python object costs are unmeasured; there is no speed/learning-benefit claim.
Do not add instrumentation or benchmark during current frozen comparison.
Any selected deployment requires truthful newest-state/source continuation,
updated three source hashes in the future E13/X4/source62 family and exact
runtime ownership/resource checks. No existing family auto-accepts these new
hashes. No old-model rollback, replay/bank flush or speculative scientific knob
change is authorized by this source proposal. Occurrence and plateau causality
remain unestablished.
