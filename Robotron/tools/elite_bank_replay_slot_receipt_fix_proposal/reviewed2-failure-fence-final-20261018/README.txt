REVIEWED2 COMPLETE FAILURE FENCE — UNAPPLIED / UNSELECTED / UNEXECUTED

This revision replaces the blocked b120 source draft for future review only.
Parent preparation-manifest0040, patchb120, fixturee467 and all original bytes
remain untouched. Intermediate1bfe/008f bytes also remain untouched in the sibling
reviewed2-failed-step-history-20261018 directory. Neither draft was executed or
applied. Their deficiency was found by independent source peer and root.

The entire _record_step transaction now has a BaseException fence: if a CID step,
receipt validation, or history creation/append fails, mark or create its episode
history incomplete before rethrowing. Preserve an existing guarded prefix and
its epoch. An unknown/legacy history becomes an empty incomplete marker. There
is no second insertion, fallback to bare indices, swallowed failure or automatic
retry. Next valid same-CID rows remain ineligible as a whole bank episode until
a genuine existing elite/reset boundary. The empty-history elite early return
also clears a guarded failure marker after the unchanged adaptive stats feed;
it never makes an empty episode a bank offer. Existing nonempty finally.clear,
reset/barrier acknowledgment, predeath and tail mutation ordering are unchanged.
Catastrophic allocator/runtime failures that prevent recording any marker are
not certified recoverable; this source proposal is not an OOM recovery system.

Only _record_step and the empty elite return differ from the blocked b120 socket
candidate. Replay and agent candidates are byte exact to that draft. Raw text
forward/reverse reconstruction is verified, without author AST/compile/imports.
The diff size reflects unchanged-body indentation for destructive mutation
fences in the original proposal, not additional scientific changes. Exact held
production sources are untouched. Adam, clocks, ReplayInsertExposure, _adds_total,
serialized replay/bank formats, loss, targets, controls and recipe remain intact.
No bank historical provenance or current occurrence/learning benefit is claimed.

The test contract additionally extracts the ACTUAL actor_kind_from_name static
method used by the real agent step; the first draft omitted that dependency.
Its eleven unexecuted methods now include first real add conversion failure,
same-epoch mid-episode pre-add failure, malformed receipt, episode append failure,
and history construction failure; each continues with >=33 resident valid rows,
checks both banks refuse the missing-prefix episode without retry, preserves
stats/offers and tests FIFO reset recovery. A separate empty-first-failure ->
empty elite -> fresh33-row life subcase verifies recovery at that boundary.
Original no-overwrite/wrap/epoch/overflow/destructive mutation/lock/stop cases
are unchanged. Synthetic fake worker/lock seams do not prove runtime concurrency
or producer quiescence. No project imports, model/replay contents, actual worker
threads, sockets, mmap writes or target tests have been run by the author.

Root may execute only AFTER the ENTIRE current quality campaign is terminal,
scientifically disposed, owned closures saved and source/workload freeze released.
Run original six characterization tests first, then selected eleven patch tests
once using manifest argv/caps. Incidence/cost and meaningful runtime concurrency
proof remain prerequisites before deployment. No instrumentation or benchmark
is added here.

IMPORTANT LIMITS PRESERVED FROM README.txt IN PARENT
Legacy bare-index API defaults remain unsafe for delayed residency; ordinary
sample -> GPU -> update_priorities remains unchanged and outside this patch.
Late queue.put publication after stop drain remains possible because callers
do not join all producers. stop-lock + join-before-drain only excludes dual
consumers; it is not a persistence/quiescence claim. External direct ndarray or
mmap mutation bypassing enumerated APIs cannot be detected by O(1) metadata.
No automatic cleanup/restart/old-weights fallback is introduced.

The immutable af24 invariant proof belongs to runtime_review and still binds
b120 as related context. It is NOT revised to approve these corrected bytes.
An independent full corrected-source/fixture review remains required. No existing
source62/E13/X4 quality family automatically admits these changed source hashes.
