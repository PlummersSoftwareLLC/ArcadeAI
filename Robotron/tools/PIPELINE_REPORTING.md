# Host pipeline reporting

The console/CSV reporter and dashboard share a bounded cache that reads one
agent's `pipeline_telemetry_snapshot(reset=False)` and replay's existing
`get_bank_persistence_stats()` at most once per second. Reads happen outside
`metrics.lock`, model locks, and CUDA stream contexts. Reporting never drains
producer counters and adds no CUDA events, synchronizations, or RNG operations.

The compact console columns are:

| Column | Meaning |
| --- | --- |
| `IBat` | Mean sampled greedy inference tensor rows, after epsilon filtering; not the outer server batch size |
| `IHost L/S/R` | Mean sync-lock wait / service / CPU readback host milliseconds |
| `RefHost A/T` | Mean actor-refresh total host milliseconds / target-refresh host milliseconds |
| `BankLk` | Cumulative maximum bank snapshot chunk lock hold in milliseconds |

Inference timing samples one in 20 eligible agent inference calls; refreshes are
recorded on every actual refresh. Missing/unsampled phases display `NA`. These are
host elapsed measurements, including scheduling and possible device waits. They
are not GPU kernel durations, cannot be added to unrelated training timers as
disjoint work, and do not establish the cause of a slow throughput phase.

The console reporter alone derives interval means from cumulative count/sum
deltas. First observations summarize since recorder initialization; generation
changes identify an explicit producer reset. The API cannot move the CSV's
baseline. Flattened CSV names end in `_mean` for interval means and
`_max_cumulative` for maxima since initialization/reset. Counts and sampling
interval, cache age, forced refresh counts, and errors accompany those values.
Inference error counts cover sampled model calls; they are not socket deadline
or batcher error counters. Actor/target refresh counts cover all actual refreshes.

`pipeline_snapshot_json` preserves the complete cumulative snapshot, including
bounded histograms and their bucket limits. `bank_persistence_json` preserves the
complete bank snapshot, with capture deferrals/lock maximum, write duration and
failures, writer activity, revisions, dirty flags, and last error. Selected bank
fields also have numeric CSV columns. `/api/now` exposes the same cached full
data as `host_pipeline` and `bank_persistence`, plus cache age and read errors.
Raw histogram dictionaries are excluded from retained dashboard history to avoid
copying them into up to 40,000 history entries.

All telemetry columns are present even before the new agent helper is available;
absent values stay blank. CSV field names are fixed by the first row/existing
header. A schema mismatch refuses the append before modifying the file. Reload
this reporting change into a new run directory, preserving old run CSVs.

Bounded CPU checks in `Scripts/dqn/test_run_telemetry.py` cover cache sharing,
counter/reset semantics, exact interval means, missing values, full JSON payloads,
actual dashboard API snapshots, and prevention of incompatible CSV appends.

## Learning exposure counters

Run23 enabled the separately reviewed `DQN_LEARNING_EXPOSURE_COUNTERS=1`
telemetry on 2026-10-16; the code default remains OFF. `/api/now` exposes
`host_pipeline.learning_exposure.{optimizer,replay}`. The same complete object
is retained in existing CSV `pipeline_snapshot_json`; no columns or checkpoint
keys were added. Snapshots do not drain these counters.

The existing `training_steps` and `optimized_samples` remain logical learner
clocks. A completed iteration still advances them when GradScaler skips the
optimizer update. LR, imitation, target/actor refresh and replay-pressure
schedules continue to use their existing clocks. The new counters neither
replace these clocks nor change training behavior.

Optimizer `total` and `since_epoch` contain `attempts_started`,
`outcomes_recorded`, `applied`, `amp_skipped` and `unavailable`. Outcomes partition
into the last three categories. `applied` means the optimizer call was admitted,
not that every parameter changed or every Adam state advanced. The supported
single-device fused-Adam/GradScaler path retains the existing `found_inf` tensor
and appends it after diagnostics to the existing packed CPU readback; it adds no
extra device readback, reduction, event or synchronization. Unsupported or
malformed private metadata is explicitly unavailable. An in-flight attempt can
make `available=false` with pending count one; it is not itself an AMP skip.

Replay `accepted_learner_total` counts only normally completed, post-nstep new
ring additions with explicit DQN or epsilon source tags. Expert, eval and
unattributed rows retain separate counts; their presence is permitted and they
are excluded from the learner count. Imported replay/bank rows and wire frames
do not count as new admissions. Run23's prefleet audit verified a restored
six-million-row ring with zero new accepted rows.

Compare deltas only within the same `process_id`, `instance_monotonic_ns` and
`epoch`. Replay clear/flush/load and optimizer restore/reset invalidate the
corresponding epoch before destructive mutation; totals remain process-local
and are not checkpoint-restored. A future fresh-data burn-in also needs a
verified actor/nstep/replay-queue policy boundary. Snapshot components and model
clocks are not atomic together: report AMP skip increments as observation
brackets, and retain nonfinite-gradient diagnostics without assigning a skip to
a particular row. Nonfinite loss remains a health failure. Earlier compiler B's
precommitted nonfinite-gradient failure is not retroactively reclassified.

Implementation/startup evidence is in
`logs/managed-learning-20261015/run-23/exposure-source-application-audit.json`,
`exposure-postapply-independent-audit.json` and
`startup-readonly-independent-audit.json` in the same directory. The bounded CPU
fixtures and tiny constructed-GPU0 parity probe do not establish live overhead
or cross-device equivalence.

The first fixed run23 health window (11:38:36.064–11:41:36.078 UTC on
2026-10-16) recorded 3,151 completed optimizer outcomes: 3,150 applied, one
AMP-skipped and zero unavailable. Fresh learner inserts were 813,040
(731,168 DQN + 81,872 epsilon); 90,536 expert and 227,847 eval inserts were
retained separately. The one Inf-gradient diagnostic and both observed skip
brackets from prefleet through the endpoint remain in the audit; only one skip
bracket falls in the primary window. They are not atomic row-level attribution.
The original observer's overstrict zero-eval alerts were preserved and every
row was rechecked against the correct exclusion/partition contract, without
moving the window or changing production policy.

The measured 71,833.77 samples/s versus run22's 69,261.72 is descriptive
(+3.714%), not a causal estimate of telemetry overhead or a learning-quality
result. The final evidence is `exposure-health-independent-summary.json` and
`exposure-health-final-independent-audit.json` in run23. These operational
observations do not themselves select or rebase a quality reference. The separately
confirmed 128M and 192M promotions and preserved 64M/96M/160M history are documented in
`../DELL_SETUP.md`; subsequent quality checks must name their fixed reference.

## Bank field output phases

`bank_persistence.output` in `/api/now` and the same nested `output` object in
CSV `bank_persistence_json` expose `robotron-bank-output-v1`. The CSV header is
unchanged. This is a cumulative, non-draining snapshot with seven fixed phases:
`create`, `write`, `mmap_flush`, `mmap_close`, `file_open`, `file_fsync`, and
`file_close`. Each phase reports `count`, `errors`, `host_total_ms`,
`host_max_ms`, `logical_bytes`, and `payload_bytes`. Counts include completed
phase attempts; errors identify failed attempts. `active` identifies the current
bank/field/phase and its elapsed host time, and `recent` retains only the last
32 completed phase events. A cached or sampled read can miss short active
phases and older events; cumulative totals retain completed work.

These are host elapsed times for field `.npy` files, including scheduling and
filesystem waits. They exclude capture, snapshot allocation/release, metadata,
directory synchronization, atomic `CURRENT` publication, and generation cleanup.
They are neither GPU timings nor physical disk service times. The difference
from whole-bank write time does not isolate any one excluded operation. Byte
counts describe the padded array body and compact valid-row payload on `write`;
they do not measure physical disk traffic.

`DQN_STREAM_BANK_OUTPUT` is read once when replay is constructed and defaults to
`0` (`backend=memmap`). The original route times array assignment, mmap flush,
mmap close, and file fsync separately. Opt-in `1` (`backend=stream`) writes the
same padded `.npy` geometry with bounded positional writes and file fsync; its
mmap phase counts stay zero because those operations are absent. Both routes
retain coherent capture, dirty/revision and load-epoch checks, atomic `CURRENT`
publication, retained complete generations, and the existing durability contract.
The flag changes field output only; it does not remove synchronization or
change what a successful save means.

The 2026-10-16 run19 natural **memmap** baseline completed both bank publications
with no bank/field write errors, but recorded 34 main inference-deadline errors
and reconnections while all 192 pinned MAME PIDs survived. Aggregate field write
time was 10.466 s, mmap flush 7.833 s, and mmap close 26.916 ms (9.964 ms maximum).
This does not establish a long unmap/close stall or a GC/snapshot cause. Timings
and deadline overlap are observational; the audit also records an overlapping
autosave and sampling gaps. See
`logs/managed-learning-20261015/run-19/natural-bank-memmap-independent-audit.json`.

Run20's first natural streaming event published both banks without write errors,
main inference deadlines or journal disconnects; all 192 pinned actors survived.
The memmap baseline retains its 34 deadline errors. Overall observed capture/write
brackets were 32.813 s versus 33.003 s, so this is not evidence of a faster whole
save. Policy, snapshot payload and uncontrolled host work changed; no causal
speedup or universal reliability fix is established. The default remains OFF and
the separate trial is ON. See
`logs/managed-learning-20261015/run-20/natural-bank-stream-vs-memmap-independent-comparison.json`.
The same trainer then completed two further natural stream cycles at 10:27 and
10:57 UTC on 2026-10-16. Across all three observed cycles, both banks published
on each cycle (six publications), with zero bank/field errors, main deadline
errors or journal disconnects, all 192 pinned actor identities preserved, and
at least 134 seconds of recovery observation after each pair. See
`logs/managed-learning-20261015/run-20/natural-bank-stream-independent-audit.json`,
`natural-bank-repeat-independent-audit.json` and
`natural-bank-third-independent-audit.json` in that directory. These are three
sequential natural observations under changing policy/payload and disclosed
coast-period auxiliary work, not controlled repetitions or a universal fix.
Header/geometry/size and sampled valid/padded-row checks are not exhaustive
payload equality or a filesystem durability proof. GC/snapshot/unmap causality
and a faster whole save remain unestablished.


## Confirmed 192M quality reporting

The 192M reference update is separate from host pipeline or exposure telemetry.
Two original full-tail cohorts (52 and 61 games) independently passed the fixed
5% mean-gain and median-floor gates against the original 128M 148-game reference.
The descriptive 113-row pool is mean 266,294.25, median 230,150 and SE 11,652.97
(+28.8839% mean); it is not a fabricated valid measurement receipt. Root promoted
the protected 192M policy at 16:52:44.318 UTC on 2026-10-16; 128M is preserved.
Both 160M guards and the single 96M guard remain unpromoted history, not baseline.
The official 50-whole-game floor, 16-slot/full-tail protocol and runtime failure
rules remain unchanged. Low N and bootstrap/SE precision limits are disclosed.

The final 192M campaign and root promotion audit are linked from `../DELL_SETUP.md`.
The confirmation's eight raw generic alerts and ten intentional batcher-stop
cleanup tracebacks are retained with explicit post-cutoff source-order evidence;
the two full cohorts have zero measured runtime errors. Host elapsed duration,
maximum observed level, playable frames and recorded deaths are supporting
diagnostics only. More deaths can accompany earned lives and longer games.
Logical updates/optimized samples, actual saved Adam steps and timestamped
process/epoch application counters stay separate; no whole-interval AMP claim,
new schedule, new telemetry column or causal batch/compiler conclusion follows.


## Protected 384M reporting and diagnostic evidence

The current figure identifies protected 384M separately from the historical
600-second quality curves through 192M. Its four fresh 1200-second cohorts had
boundary diagnostics enabled and all 377 games independently audited. Candidate
cohorts individually gained 9.81% and 9.06% over the fresh reference mean and
passed both median gates; the 172-game candidate pool is descriptive only.
`render_learning_progress.py` checks the current incumbent, protected metadata,
actual publication/adoption, CPU proof, original receipts and both separate gates.
The figure passed an actual private render, text bounds, PNG integrity and visual
review. Its data retains the successful isolated CPython 3.12 / Matplotlib 3.11.2
reproduction argv; no plotting dependency was installed into the training venv.
See `run-26/confirmed384M-reporting-root-adoption-20261017/` under the managed log
root and `../DELL_SETUP.md` for current evidence. The original failed render from
the venv without Matplotlib is retained separately.

The spare-GPU one-attempt original-four-output CE capture and fresh conditional
recompute completed; a separate CPU audit verified all 4,096 CE values at the
original tolerances. This is diagnostic evidence, not a learning treatment or
throughput claim. Its first AMP skip, full artifacts and original exits remain
preserved. The first live-eight acquisition passed 43 focused CPU contracts but
failed after shutdown and before installation/capture: the settings contents
were unchanged, but their normal atomic rewrite changed the inode/timestamps.
The automatic recovery lacked a retired-owner record at this early boundary.
The original failed exit is retained; all 192 actor resume attempts succeeded.
Root independently verified the newest 431,584,381-frame saved latest and booted
the original code from it. Recovery confirmed the same actors/masks/fleet,
both replay banks, the 6M ring, 128 graphs/640 validations and advancing counters;
the protected 384M bytes were rehashed unchanged. See
`run-26/live8-owned-manual-forward-recovery-reviewed1-20261017/`. That v3 attempt
produced zero captures and remains a failed original invocation.

The separate v4 maintenance revision passed 51 CPU guards and source review,
with fresh insurance bound to the recovered current owner. It allows the
precommitted exact same-byte settings replacement only after an owned stop and
records retirement before post-stop checks. Strict CPU verification covered
insurance and the actual stopped latest. The first consumed PRE clocks exactly
matched that latest: 2,090,214 logical steps, 7,113,928,704 optimized samples,
435,450,662 learner frames and 871,030,534 fleet frames. Both selected bank
generations, the 6M ring and post-load graph checks preceded actor resume.

V4 actually completed eight original-four-output captures, all with classified
optimizer admission and no AMP skips, and exited 0. All 192 actors resumed;
the installed observer is dormant after eight. No priority, optimizer/scaler
policy, learning recipe or architecture was changed. Ordinary restart tails
remain disclosed: this is not a coherent replay/RNG anchor or zero-loss restart.
Capture evidence is in `run-26/live8-owned-maintenance-reviewed4-20261017/`.

The actual-only CPU analysis passed ten stdlib guards and completed with its
original exit 0 retained before release. All eight batches had the same actual
901/737/1434/410/614 PER/interesting/recent/HOF/EpHOF counts. PER mean coefficients
ranged from 0.226 to 0.471; bank rows carried that batch mean, while both quota
slices carried one. Whole-batch mean coefficients ranged from 0.636 to 0.752.
These coefficient/contribution and concentration descriptions are not measured gradients,
an effective learning rate, sustained throughput or policy improvement. Copied
`draw.unknown` strings describe only the sampler metadata subsection; the outer
capture independently joins actual outcomes and full PRE inputs. Per-row
executed targets, entropy and KL remain unobserved.
See `run-26/live8-actual-CE-offline-analysis-reviewed1-20261017/` and
`run-26/live8-completion-and-448-rearm-root-20261017/`.

The separate replay-only conditional reconstruction passed 59 bounded guards
after two retained incomplete-mock failures, then completed all eight actual PRE
reconstructions. Original parent/child exits were 0; every original CE comparison
was false: 11,433/32,768 violations at unchanged rtol0.0002/atol0.00002, maximum
per-batch differences 0.00738–0.02519. Model/RNG fingerprints and forbidden update
counts remained unchanged. GB300 captures and RTX reconstruction differ in
physical hardware; no cause has been established. No parity, actual target/KL,
learning gain or tolerance rescue follows. See
`run-26/live8-conditional8-reconstruction-reviewed1-20261017/`.

The four-readout CPU analyser passed 12 checks and decoded all small retained
outputs, independently rechecking every original failed mask. Conditional CE/KL
PER ranks correlated 0.214–0.276; holding actual CE fixed, selected-row mean coefficients changed
0.702→0.564 and bank Bellman scalar share 12.56%→3.07%. These are conditional
sensitivities under separate bank recoupling, not future sampled distributions,
parameter gradients, effective LR or policy quality. All eight original CE
comparisons remain failed. Results are under
`run-26/live8-four-readout-analysis-reviewed1-20261017/`. The next same-GPU
original-four/conditional-five diagnostic subsequently completed as described below.

The 448M model-only waiter reached its original target and exited 0 at
09:19:42 UTC. PID 64907/invocation `7a0c4af840184de4bd8ffe479eb4c4bf`
was archived before release. The saved candidate has 452,630,871 learner frames,
2,156,883 logical updates, 7,387,004,928 optimized samples and 905,164,910 fleet
frames. Its byte identity and first actual strict CPU verification passed;
source/copy SHA256 is
`1e085a128e237c2bb0636b073e5053dd8bf5be932bcbd8249543b3af20e23021`.
All 81 initialized Adam states agree at 2,155,894; the observed gap of 989 from
logical updates is retained without attribution or a forced historical value.

The fixed attempt01 same-GPU diagnostic passed 62 guards, then completed exactly
two forwards with independent PRE/RNG restoration and original parent/child exits
0. Local conditional-five versus original-four CE passed all 4,096 comparisons
at the original tolerance; maximum absolute difference was 1.1920928955078125e-7.
Original-four versus captured actual CE failed 1,408/4,096 comparisons, maximum
0.02144545316696167. This leaves a shared capture/device/profile residual; two
calls do not establish its cause or exclude nondeterminism. The prior eight
failed comparisons remain failed, and actual per-row target/H/KL remain
unobserved. No update, parity qualification or efficacy claim follows.
See `run-26/live8-route1-sameGPU-diagnostic-reviewed1-20261017/` and
`run-26/live8-route1-completion-and-448-rearm-root-20261017/` for retained results,
independent ownership/cleanup evidence and the restored watcher bindings.

The generic immutable-candidate CPU verifier wrapper passed ten bounded stdlib
guards with original exit 0. Its strict model/Adam/scaler validation body remains
unchanged; an actual 448M job still requires authentic tag, four-clock trigger,
completed request, same trainer and original helper terminal evidence. Passing
wrapper guards is not saved-candidate verification or quality qualification.

The separate 448M capture preparer and original-row leg auditor each passed 11
bounded stdlib checks with original exits 0. The preparer preserves the retained
original helper terminal evidence and creates an independent readonly CPU copy;
it never modifies the tagged source or releases the helper. The leg auditor
retains the existing all-game, all-slot, full-tail validity checks and binds the
new candidate CPU proof. Two actual pre-output preparation metadata refusals
are preserved: exited systemd units clear/omit `ControlGroup`. Reviewed3 requests
`show --all`, retains exact original ownership/absence predicates, passed 14
guards and completed preparation with exit 0. The first numeric CPU verification
then passed with original exit 0; no numeric retry or quality rescue occurred.

Fresh `quality-384M-vs-448M-20261017` confirmation completed, original controller
125723/start32032124/invocation `b16156a323ef4b8d94b0fb3758e43a38`.
The actual plan differs from the reviewed preview only in creation time.
First-reference startup confirms all 16 private slots and GPU0 evaluator126524,
while main PID4140916/GPU1 retains its 192 clients. The dashboard points to the
live campaign. Initial games with unknown starts are excluded. All original
four-cohort mean/median, minimum-count, full-tail and validity checks remain;
448M is now protected and adopted after every confirmation requirement passed. The optional
raw-KL source bundle initially passed source review before installation. Its first
21-method CPU suite did not complete: 17 subtest errors used `totals` where the
pinned exposure API returns `total`. The original failure is retained; correcting
that assertion fixture changes no candidate algorithm or confirmation result.
The additive corrected test companion then passed all 21 checks with original
exit 0, including tiny CPU optimizer/scaler outcomes and both readback layouts.
These are CPU contract tests; actual 4096-row CUDA/AMP/native/phase-load
validation remains required before any training adoption, after this campaign.

The corrected CPU21 result also passed independent saved-source/result review.
The isolated GPU loss validation passed all 58 focused CPU guards and completed
three same-input compiled forward/backward
routes, preserving the original tolerances and retaining unscaled gradients;
it does not exercise optimizer admission or the full agent. Before its first
execution, the worker/total budgets were set to 600/900 seconds because the
earlier two-forward diagnostic took 94.44 seconds. The selected test modules
and enforced budgets are bound by the reviewed3 handoff companion. Before any
execution, a copied storage fixture's two expected time limits were corrected
to match 600/900; its old source and the superseded reviewed2 selection remain
preserved. The numerical sources and all 58 test methods are unchanged. The
separate constructor, native-priority, optimizer and phase-save/load bundle is
now frozen with independent scientific and practical API source reviews. Its
82 CPU tests passed. Its first actual parent exited 1 before launching a GPU child:
the freshly published phase record was writable, while its validator requires
readonly metadata. The original failure and cleanup are preserved; a narrow
phase-record and role-input publication correction passed independent review and
all 84 CPU guards. Its actual GPU validation completed as
`robotron-snapshot-smoke-rawkl-stage-b-reviewed2-20261017.service`, original parent
386698/start32782950/invocation `381b9f5cf8584ad283a1fa3a8f6aad0c`.
It fixes 18 actual 4096-row
steps, including the natural diagnostic step, under the saved optimizer/scaler;
512 explicitly synthetic fleet-frame credits per step fund the unchanged cap8.
It uses a declared fixed-input/native-tree adapter and releases private serving
graphs after constructor/load verification, so it cannot prove full replay
restore or simultaneous serving and learning. At that preparation stage the raw-KL
change was uninstalled; the confirmation gates stayed unchanged. The actual
three-role parent and children exited 0 in 655.78 seconds. All 18 optimizer attempts
applied with native priority updates; fresh KL resume and new CE return each loaded
the newest post-step checkpoint and performed zero learner attempts. Independent
review is retained under
`run-26/optional-rawKL-StageB-all3-independent-saved-science-review-20261017/`.
This is functional readiness using the declared fixed-input/native-tree fixture,
not a policy-quality or learning-speed result. The original terminal was archived
before release; all 192 original actors, main owner, source and controls held, and
GPU0, the lease, port, tmpfs and owned cgroup were clear after cleanup.
The phase verifier's 12 metadata guards, horizon observer's 18 guards and selected
post-stop transition's 26 guards also passed. The later live integration and its
independent deadline supervisor passed 47 focused controller guards.

The first 448M-campaign reference evaluator subsequently exited 0 with all 89
admitted games complete (mean 369,931.74, median 406,450). The original row audit
requested review of interleaved cleanup traces and exited 2; its result remains
unchanged. A separate exact-log/source review joined every original game,
retained all nine completion tails, rechecked artifacts and proved the seven
stopped-batcher traces followed intentional shutdown. Root accepted this narrow
supplement with zero measured runtime failures. Candidate01 subsequently
completed all 81 games (mean 422,591.36, median 434,000), including 14 full tails,
and its original-row audit exited 0. Reference02 then completed all 88 games,
with original evaluator and auditor exits 0 (mean 339,464.77, median 367,512.50).
The fixed fresh reference pool contains all 177 reference games: mean
354,784.32, median 399,850, required candidate mean 372,523.54. Candidate01
individually passes both gates (+19.11% mean). Candidate02 completed all 78 games
and 12 tails, with mean 448,283.65 and median 437,937.50 (+26.35% mean). Its
original evaluator and row auditor both exited 0. Independent review joined all
336 games, and both candidates passed separately. Root preserved the original
controller exit, released evaluation resources, published an independent readonly
448M copy and adopted it as the next reference. The prior 384M descriptor and all
ten earlier history entries are preserved; no live learner reload occurred.
Evidence is under
`run-26/quality448M-reference01-interleaved-shutdown-manual-review-20261017/`
and `run-26/quality448M-reference01-manually-reviewed-candidate01-running-root-continuation-20261017/`.
Candidate01 audit evidence is under
`run-26/quality448M-candidate01-independent-original-row-audit-20261017/`.
Fixed-pool and separate Candidate01 gate evidence is under
`run-26/quality448M-R2-original-auditor-PASS-fixed-reference-C1-PASS-C2-running-root-20261017/`.
Final publication/adoption is under
`run-26/quality448M-managed-incumbent-adoption-root-20261017/`.
Stage A's actual 58-test exit 0 is retained under
`run-26/optional-rawKL-StageA58-guards-root-execution-reviewed1-20261017/`;
the subsequent fixed GPU attempt exited 0 in 135.63 seconds and passed independent
saved-source/result review under
`run-26/optional-rawKL-StageA-independent-saved-science-review-20261017/`.
Its internal comparisons pass the original tolerances; the historical
captured-versus-recomputed CE comparison still fails and is retained separately.
No optimizer or scaler updates occurred in Stage A. The original service terminal
was archived before release, and GPU0, the lease, tmpfs and owned cgroup were clear.
The actual 448M report was rendered with exit 0, checked visually and adopted under
`run-26/confirmed448M-reporting-root-adoption-20261017/`. All 13 historical curve
objects and three guards are unchanged; the 1200-second confirmation is a separate
annotation, with each candidate gate reported independently.

The actual first KL trial was invalidated before 192-client admission: the phase
verifier correctly rejected a writable legacy boot CPU report. Writable historical
provenance would also require independent readonly archives. Preserve the original
startup CPU exit 1 and trial FAILED result; do not rerun that attempt or classify
it as a quality loss. The deadline independently recorded exact KL-owner absence
121.25 seconds after the owned start request. No horizon or quality candidate
was produced. One actual startup KL priority update was saved and preserved.

A separate newest_stopped phase CPU job passed with genuine zero-client scope,
strict finite model/Adam/scaler and the saved KL lineage. Its source is newest
`b8ff9f5fbd68ff89d81890cc52c7cfd5e11b754892b3c1e898271533317421ad`,
with clocks 2,340,866 logical updates / 8,140,599,296 optimized samples /
499,579,931 learner frames / 999,363,750 fleet frames. Boot proof and context
archives are independent readonly files; original reports were not chmodded.

Explicit forward recovery then passed eight guards and started one NEW CE phase
from that newest state. Startup CPU passed before actor admission, and all 192
original actors reconnected with the held recipe, sources, controls and masks.
The five optional science files remain installed in CE mode; no source rollback
or older checkpoint restore occurred. The original recovery controller exited 0
and was archived before exact timer/service release. Root current-health receipt
is `run-26/rawKL-trial01-forward-CE-repair-root-terminal-and-health-20261017/`
`root-forward-repair-terminal-release-and-current-health-PASS.json`.
The confirmed 448M reference is unchanged; there is no KL quality or speed claim.

The separately precommitted trial02 used the installed-CE transition revision
after 57 guards passed. Independent readonly copies of phase metadata preserve
the original reports and receipts. Newest CE boot clocks are 2,357,661 logical
updates / 8,209,391,616 optimized samples / 503,951,038 learner frames /
1,007,962,406 fleet frames. Actual KL owner546648 passed zero-client startup
phase CPU before all192 admission; its separate genuine KL192 early insurance
also passed CPU with original verifier exit0 and archived unit release.
The original first latch reached +8,003,254 learner and +11,119,726 physical
accepted transitions, durable at 1,943.432 seconds. The single candidate saved
at 511,985,990 learner frames and passed phase CPU; actual newest-stopped CPU
preserved equal or newer clocks. Independent KL absence was 1,979.652 seconds.
New CE owner620749 passed startup0 phase CPU before all192 admission. Original
trial and deadline controllers exited0, were archived, then released timer-first.
Canonical state now records that returned CE owner and the completed KL trial.
Fresh protected448-versus-firstKL quality qualification remains outstanding.
Do not call the early insurance a horizon candidate. The first-trial failure and
forward recovery remain preserved. See
`run-26/goal-continuation-KL-trial02-running-root-20261017/` and
`run-26/rawKL-trial02-activation-early-insurance-independent-saved-review-20261017/`.
The completed source/metadata lineage review is
`run-26/rawKL-trial02-first-horizon-candidate-and-CE-return-independent-saved-review-20261017/`.
The new quality binding companion passed 13 focused guards; its evaluator and
16,072-byte original row/tail/scoring audit body are unchanged. Structural and
controller checks do not qualify a playing-quality improvement.

Fresh `quality-448M-vs-rawKL-trial02-first8M-20261017` confirmation finished `not_improved`:
original parent638119/invocation325ea02d8cde47869eb8340b3de73f69,
first reference evaluator 638126 exited 0 with all 76 admitted games completed and
all 16 slots contributing. Its original row auditor, PID 694456, also exited 0,
with all rows and admissions preserved, no measured timeouts, and 11 full-tail games
up to 254.58 seconds after admission closed. Original audit service/timer metadata
and invocation journals were archived before exact timer-first release; both
units are absent. R1 mean is 414,353.29 and median is 419,512.5. The fixed reference
threshold uses all games from R1 and R2. The first candidate evaluator, PID 687356,
finished with original exit 0 and all 65 admitted games completed. Its original
auditor, PID 737371, exited 0; independent saved review passed all 65 original
rows and admission contexts, 1,407 life records, and all 16 slots. Final mean is
481,136.15 and median is 456,075, with 12 tail games up to 234.19 seconds after
admission closed. Both exact audit units were archived before release. R2 is now
complete: original evaluator 736314 and original auditor 788425 exited 0 after all
65 games finished. Independent review passed exact rows, admissions, life records,
all slots and six tails up to 292.42 seconds. Its audit units were archived and
released. The fixed 141-game R1+R2 reference has mean 427,681.21 and median 441,875.
C1 independently passes mean (+12.50%) and median (456,075) against that pool.
C2 evaluator 787348 finished all 70 admitted games with original exit 0 and all
16 slots contributing. Original auditor 835388 also exited 0 and was archived
before exact unit release. Thirteen tail games finished up to 192.83 seconds
after admission closed; none were abandoned. Its mean 444,176.43 (+3.86%) misses
the fixed 449,065.2659574468 requirement; median 448,950 passes 441,875.
Original parent 638119 exited 0 with `not_improved`. No promotion is authorized;
protected448 remains the reference. Independent final saved review and original
parent archive/cleanup passed. Explicit source-freeze release followed checks of
the unchanged main192 owner, sources and available evaluation resources. Main CE training continues as620749 with
192 actors; the next candidate will use a fresh live save after closure.
Actual plan SHA is `b502625ed8e39f01fa57af1c9f9cc8283794aa14e351e2b9bc9ec1268b267ecf`;
it differs from the reviewed preview only in its creation timestamp. Original-row
audits must bind this actual plan. The legacy dashboard caption's "8M" means the
KL increment, while this candidate saved at511,985,990 total learner frames.
Source freeze was held through all four cohorts, reviews and original cleanup,
then explicitly released. The display-label correction remains optional. C1 passes its gates; C2 fails its mean gate, so the
candidate is not confirmed. No causal KL or learning-speed result follows.
Actual R1 audit/root execution and fresh C1/main192/source/GPU evidence are in
`run-26/rawKL-trial02-quality-R1-completion-C1-startup-root-20261017/`.
Actual C1 completion/audit/independent review and fresh R2/main192/source/GPU
evidence are in
`run-26/rawKL-trial02-quality-C1-completion-R2-startup-root-reviewed2-20261017/`.
The actual R2 audit, independent fixed-pool/C1 arithmetic, and fresh C2/main192
startup are in `run-26/rawKL-trial02-quality-R2-completion-C2-startup-root-20261017/`.
The final original-row fixed-gate calculation is in
`run-26/rawKL-trial02-quality-final-fixed-gates-root-reviewed2-20261017/`.
Final original cleanup and explicit freeze release are in
`run-26/rawKL-trial02-quality-root-freeze-release-20261017/`.

Fresh `quality-448M-vs-CE543M-20261017` completed all 274 original games
and qualified. Candidate543 was saved at 543,235,763 learner frames, SHA256
`8b86546355ade166937a8287a008c7854276ed773a103eb815287dde00d6fb7e`;
its original model-only live capture and strict phase CPU verification exited 0.
All 192 actors kept running during capture; no replay/RNG anchor was claimed.
Fresh reference counts are `[71, 78]`: the same fixed 149-game pool has mean
402,881.20805369125 and median 424,575. Candidate counts `[59, 66]` separately
score means 513,536.0169491525 (+27.465865%) and 488,850.3787878788
(+21.338590%), with medians 480,800 and 490,487.50. Each passes the unchanged
mean >= 1.05 * fixed reference mean and median >= 424,575 gates. The 125-game
candidate pool (mean 500,502, median 481,450) is descriptive, never the gate.
All 16 slots, minimum50, 1200-second admission windows, full tails and diagnostic
settings remain enforced; the historical KL campaign's reference pool is excluded.

Original auditor exits are `[0, 2, 0, 0]`. C1's failed report and exit 2 remain
unchanged; exact independent full-row/source review and explicit root acceptance
cover its six owned post-stop traces after all 59 games ended. The original
campaign parent894289 exited 0; full service/timer archives preceded exact owned
release, all 69 owned campaign processes were absent, and root explicitly
released the source freeze. Create-only publication at
`models_dqn/managed-incumbents/freshCE-543M-confirmed.pt` and actual canonical
adoption preserved the prior448M descriptor and all earlier history (12 entries).
Main620749 remains CE/batch4096 with192 actors and no promotion reload/restart.
The actual CPython3.12 private report render and visual review passed before the
renderer/data/PNG update; all 13 historical curves and three guards remain exact.
Evidence: `run-26/confirmedCE543M-reporting-root-adoption-20261017/`.
The goal remains active; no causal learning-speed or batch/KL efficacy claim follows.
See `run-26/CE543M-quality-final-fixed-gates-and-closure-preparation-root-20261017/`,
`run-26/CE543M-quality-C1-original-rows-narrow-shutdown-independent-saved-review-20261017/`,
`run-26/CE543M-quality-C1-original-audit-R2-running-root-20261017/`,
`run-26/CE543M-quality-root-freeze-release-20261017/` and
`run-26/CE543M-managed-incumbent-adoption-root-20261017/`.

The separate private CE2048 probe completed `ce18`, `resume` and `restart_ce`:
all three report readiness true, parent exit0, and all18 optimizer attempts
applied. Resume and new-CE restart load the newest saved state with zero further
attempts. The declared fixture uses verified448M weights and first2048 ordered
rows of the fully checked original4096-row attempt01, reused18 times. Actual
constructor/load, CE-four-output training, AMP/fused Adam, native priorities and
phase lifecycle were exercised. `qualification_pass=false`: no full live replay,
serving/learning concurrency, live trajectory, throughput or efficacy proof.
The subset contains ring rows only (one duplicate); bank-origin coverage and an
actual 2048-to-4096 profile return were not exercised.
The original parent and all three child exits0 were archived before exact
timer-first release (both stops0). Separate root cleanup confirmed main192,
source/control and resource ownership held. Result and original terminal/cleanup:
`run-26/CE2048-private-training-readiness-reviewed1-20261017/result.json` and
`run-26/CE2048-private-readiness-owned-cleanup-root-reviewed1-20261017/`.
The later live CE2048 trial01 failed at a shared environment guard that still
required 4096 before the profile-aware check. It completed one 2048 optimizer
update without advancing learner frames beyond 585,070,695, then its known owner
was stopped cleanly. No efficacy window or candidate qualified; preserve the
original failed result rather than retrying or relabeling it.

Forward recovery loaded the actual newest finite checkpoint into a fresh 4096 CE
phase, preserving that update and its ancestry. Startup CPU/Adam/scaler/phase
checks passed at zero clients, then all 192 original actors resumed. Main owner
1247463, start 35298775, invocation `3ed757b88b1f4ceda5f6947fb0832938`
advanced beyond 585.4M learner frames with zero pipeline errors. Original recovery
parent exit 0 was archived before owned timer/service release. Actual evidence:
`run-26/CE2048-trial01-activation-20261017/result.json`,
`run-26/CE2048-trial01-forward-CE4096-repair-20261017/result.json`,
`run-26/CE2048-trial01-forward-CE4096-repair-20261017/CE-startup-CPU-readonly.json`
and `run-26/CE2048-trial01-forward4096-recovery-root-preparation-20261017/repair-execution/root-PASS-and-owned-release.json`.
Next is a fresh model-only continuation capture versus protected 543M. Its mixed
startup ancestry remains explicit; quality selection does not prove batch-size
efficacy or faster learning. The continuous optimization Goal remains active.

The fresh continuation capture completed at 587,607,253 learner frames, model
SHA256 `47b7add9d55f0d815e0a863264f03988dfb24c1492de8578f2effff2ca6810ce`.
Its strict candidate CPU report passed and both original capture/verifier exits
0 were archived before owned release. New campaign
`quality-CE543M-vs-postRecoveryCE-candidate02-20261017` completed all four cohorts
with native outcome `not_improved` and original controller exit 0. Both candidates
missed their separate mean and median gates. Root
checked actual plan `e7419e89f607a95e091085b1afeda49064af3d6af038fff7a06201c17b9e2121`
against independently reviewed preview `82747cdf536fb6e1d93a8255afb19fbd28115a3dc2da705e413774112de02b89`:
only `created_unix_s` differs. Main GPU1 training retains 192 actors while GPU0
ran evaluation. The saved postcanonical startup dashboard readback was available,
running, four legs and not stale. The earlier startup API snapshot predates canonical
adoption and correctly has the campaign unavailable. Keep both snapshots under
`run-26/postRecoveryCE587M-quality-R1-startup-root-20261017/`; do not rewrite the
earlier snapshot. Actual bindings and source/plan reviews are under
`run-26/postRecoveryCE587M-quality-root-preparation-20261017/` and
`run-26/postRecoveryCE587M-quality-source-and-default-plan-independent-review-20261017/`.

R1 retained all 64 admitted full games, all 16 slots and 10 completion tails;
mean 485,384.375 and median 463,612.5. The original auditor exited 2 on a
missing provenance README before reading game inputs. Preserve that failed
report and exit. Only the README was added; the unchanged auditor passed in
a separate supplemental output, and independent review matched the original
rows. Root's narrow acceptance is recorded in
`run-26/postRecoveryCE587M-quality-leg01-followup-audit-root-execution-20261017/root-narrow-R1-acceptance-original-failure-preserved.json`.
This preserves R1 validity and its original failure. Scientific and evaluator
sources remain frozen through the original campaign, audits and owned cleanup.

C1 completed all 66 admitted full games, including 10 completion tails with
maximum 137.94 seconds after admission closed. Original audit exited 0;
mean 455,994.70 and median 460,900. Independent raw-row review passed and
matched all 66 games, admissions and 1,361 admitted life records in
`run-26/postRecoveryCE587M-quality-C1-original-rows-independent-saved-review-20261017/`.
The original auditor exit history is `[2, 0, 2, 0]`; preserve the R1 packaging
failure separately from its supplemental success. C1 audit and execution
evidence are under `run-26/postRecoveryCE587M-quality-original-row-leg02-audit/`
and `run-26/postRecoveryCE587M-quality-leg02-audit-root-execution-20261017/`.
R2 completed 72 full games, including 12 completion tails with maximum
143.31 seconds after admission closed. Mean 513,195.49; median 517,900.
Its original auditor exited 2 on two interleaved stopped-batcher traces.
Independent review matched every game, admission and admitted life record;
a separate pinned-source review reconstructed exactly two owned shutdown
cancellations after the last admitted game. Runtime timeouts were zero.
Root accepted only this cleanup case and preserved the original failure,
without rerunning a cohort or auditor. Evidence:
`run-26/postRecoveryCE587M-quality-R2-original-rows-independent-saved-review-20261017/`,
`run-26/postRecoveryCE587M-quality-R2-interleaved-shutdown-independent-source-review-20261017/`
and `run-26/postRecoveryCE587M-quality-leg03-audit-root-execution-20261017/root-narrow-R2-acceptance-original-audit2-preserved.json`.

The immutable fresh reference pool contains all 136 R1+R2 games and all 22
reference completion tails: mean 500,107.90; median 479,550. C1 misses both
precommitted gates: mean 455,994.70 versus required 525,113.30 and median
460,900 versus 479,550. An exact integer mean cross-check agrees. Pool and
interim C1 evidence are under
`run-26/postRecoveryCE587M-fixed-reference-and-C1-root-20261017/`.
Independent verification of all reference rows, signatures, tails and C1
arithmetic passed under
`run-26/postRecoveryCE587M-fixed-reference-C1-independent-saved-review-20261017/`.
C2 completed all 65 games and 12 completion tails, with maximum 185.65 seconds
after admission closed. Mean 434,207.69 and median 421,925 both miss the same
fixed gates. Its original audit exited 0 and independent full-row review passed
under `run-26/postRecoveryCE587M-quality-C2-original-rows-and-final-gates-independent-saved-review-20261017/`.
All 267 games and 44 completion tails are retained. Final all-four acceptance,
individual candidate gates and original controller exit 0 are preserved under
`run-26/postRecoveryCE587M-quality-final-gates-and-owned-closure-root-20261017/`.
Protected 543M remains the incumbent. Both direct resource observations passed
around the exact original parent/timer release; all 69 private process identities
are absent, GPU0 is free and the original main trainer retains all 192 actors.
Root explicitly released the source freeze in
`run-26/postRecoveryCE587M-quality-final-gates-and-owned-closure-root-20261017/root-explicit-current-quality-source-freeze-release.json`.
The 11 deferred shared-batch metadata guards then passed with original exits
0/0 and their units were released. These boundary guards do not establish full
trial readiness. Actual executions are in
`run-26/batch2048-shared-recipe-eleven-metadata-guards-root-20261017/`.
A fresh current-owner insurance snapshot at 617,170,788 learner frames passed
strict CPU verification with original exit 0 before owned release, under
`run-26/preCE2048trial02-insurance-20261017T204218Z-root-acquisition/`.
New trial02 subsequently passed the strict current-quality preparation gate,
its eight metadata guards and the full selected runtime constructor/before
inspection. Actual owner 1525103 resumed batch2048 from the newest 619,563,192-frame model;
strict client0 startup CPU verification passed before all original 192 actors
resumed. Typed early phase insurance also passed with its original CPU exit 0
archived before owned release. Original first LATCH reached +8,005,729 learner
frames and +11,116,964 all-five-source physical insertions, durable at
2038.0115 seconds. Subtracting the actual pre-resume startup admission gives
62,315 admitted optimizer calls and 29 AMP skips over 62,344 completed outcomes;
the same original snapshot has no in-flight or unavailable outcome. These are
process-local admissions, not proof every parameter moved. The first candidate
saved at 627,599,867 learner frames and its original strict CPU verification
passed. Precommit, actual startup and saved independent reviews are under
`run-26/CE2048-trial02-final-root-preparation-20261017/`,
`run-26/CE2048-trial02-startup-root-acceptance-20261017/` and
`run-26/CE2048-trial02-first-LATCH-candidate-and-newest-independent-saved-review-20261017/`.

The original return to4096 failed `CSV_recipe` after strict startup verification
and actor admission. Its controller exit1 and FAILED result remain preserved;
the independent deadline exited0 after proving treatment-owner absence at
2074.52 seconds. No trial was rerun. Source inspection found no CSV publication
wait before the post-resume guard; the actual failing row was not archived, so
its contents are unknown. Original archives and exact owned cleanup are under
`run-26/CE2048-trial02-original-failure-archives-and-owned-closure-root-20261017/`.

Separate forward maintenance used a new strict CPU proof of actual latest
627,648,989-frame CE4096 state, retaining its genuine failed-return founder.
Seven focused metadata guards passed. One new CE phase then waited for genuine
post-start4096/cap8 CSV within the original600-second readiness budget, keeping
all other guards and log offsets. Its original controller exited0 with
`READY_CE_FORWARD_REPAIR`, all192 actors healthy, zero pipeline errors, and
graphs128/validation640. Original service/timer archives preceded exact owned
release. Evidence is under
`run-26/CE2048-trial02-failed-return-forward-CE4096-repair-20261017/` and
`run-26/CE2048-trial02-failed-return-forward4096-recovery-root-execution-20261017/`.

Root precommitted a distinct first frozen-policy follow-up for the retained
original candidate before any new quality score. The COMPLETE-only binder is
unselected; the selected binding preserves the failed trial and separate genuine
maintenance evidence. Fresh R/C/R/C, full tails, all16 slots, minimum50 per leg,
and separate +5% mean/preserved-median gates remain unchanged. One follow-up
campaign has finished. The first reference completed65 whole games across
all16 slots, including11 tails (last275.61s after admissionclose), with no
abandonments. Original auditor exit0 reported `valid_completed_leg`; its full
service/timer archives preceded exact owned release. Reference01 mean is
485,636.15 and median467,650.
Candidate01 completed all 74 admitted games with no abandonments and all 16 slots.
Its nine full tails ended up to 173.17s after admission close; mean 403,329.39 and
median 405,162.5. Original auditor exit0 and independent original-row review passed;
its full service/timer archives preceded timer-first owned release. Reference02
completed all 65 games and 10 full tails (last 208.13s after admission close).
Original auditor exit0 and independent saved-row review passed; its original
archives preceded timer-first owned release. All 130 fresh reference games give
mean 465,593.27 and median 462,725, requiring candidate mean 488,872.93.
Candidate01 fails both gates, with mean 13.37% below the reference. Candidate02
completed all 78 games across all 16 slots, including 15 full tails ending up to
214.03s after admission close. Its mean 401,727.88 is 13.72% below the same fixed
reference, and its median 418,387.5 also fails. The original auditor exited 0;
full archives preceded timer-first owned release. Independent saved-row review
accepts all 282 games and 45 full tails and agrees with native `not_improved`.
Main192 continues on GPU1.
Twenty metadata guards
passed after retaining two original setup/fixture failures. Exact default-plan,
fresh readiness and actual-launch reviews passed. Native plan `fdb13f96…`
differs from reviewed preview only in creation time. Protected543 remains
unchanged; original parent0/full archives, timer-first owned release, all69
absence and post-release resource checks passed independent closure review.
Both candidate cohorts failed independently. This comparison cannot
qualify the original trial, isolate a causal batch effect or establish faster
learning. See
`run-26/CE2048-trial02-retained-first-candidate-frozen-quality-followup-root-precommit-20261017/precommit-FINAL.json` and
`run-26/CE2048-trial02-first-LATCH-followup-quality-actual-launch-root-20261017/`,
`run-26/CE2048-trial02-first-LATCH-followup-quality-original-row-leg01-audit/` and
`run-26/CE2048-trial02-first-LATCH-followup-quality-C1-original-rows-independent-saved-review-20261017/` and
`run-26/CE2048-trial02-first-LATCH-followup-quality-R2-original-rows-fixed-reference-C1-independent-saved-review-20261017/` and
`run-26/CE2048-trial02-first-LATCH-followup-quality-C2-startup-root-20261017/`.

The subsequent same-owner LR25 window completed with CE4096, unchanged phase,
Adam/replay and all192 actors. All31 focused metadata safeguards passed; the
genuine candidate192 entry at661593752 learner frames passed b2e/9ef strict CPU.
Effective LR was1.25e-5 (scale.25), from2.5e-5 (scale.5). All deltas use the same
post-barrier nonzero B at662701467 learner frames. Original observation1498 was
the first BOTH-horizon LATCH: +8004666 learner frames, +8001691 accepted
DQN+epsilon transitions in1859.828500s. Its original durability completed
at1859.847569s within3600s. From B, applied outcomes=31004, AMP skips=13,
unavailable=0, pending=0; logical steps=31028 and logical samples=127094784
remain separate counters. Expert/evaluation insertions remain separately reported.
The sole endpoint saved at670708732 learner frames, SHA`cd614b84…`, passed
original d73/0854 strict CPU verification and independent saved review. Both
original driver and CPU exited0; six full CPU archives preceded exact
timer-first owned release. Exact original .5 control bytes and live LR2.5e-5
were restored without restarting the owner or clearing replay/Adam.

All13 subsequent quality-binding guards passed once, and the new actual
binding/current baseline, independent prepared-plan review and fresh exclusive
readiness passed. Native plan`3a9dc2b0…` differs from preview`f65a61e4…` only in
creation time. Fresh Reference01 completed all62 games across all16 slots,
including eight tails ending up to196.904454s after admission close. Its
original evaluator and original auditor exited0, with all source pins held and
full archives before timer-first owned release. Sum31441250, mean507116.935484
and median497475 describe this first reference only. Independent saved review
accepted all62 games, 1408 admitted life records, original audit0 and owned release.
Candidate01 completed all49 admitted games with all16 slots, zero pending and
zero abandoned games. Mean624664.285714 and median636725 are descriptive only;
the original receipt is invalid because49 is below the precommitted minimum50.
The evaluator and parent exited1, and the unchanged original auditor exited2
before reading game rows. Reference02 and Candidate02 did not run, so no fixed
two-reference pool or confirmation gate exists. No admission extension, retry
or pooled rescue was attempted. All35 original evaluation processes are absent;
owned failed services were archived before release and fresh resource checks
passed with main192 continuing on GPU1. The one-shot timers had naturally been
collected: original launch-time shows and invocation journals, plus actual
not-found show/cat outcomes, are retained without synthesizing timer definitions.
Independent descriptive original49/closure review passed, and root explicitly
released this partial campaign's source freeze. Two root read-only startup assertions were
corrected with both failures retained: private actors use their private cwd,
and this evaluator does not claim the snapshot-smoke lease. No native attempt
was retried and no scientific gate changed. Protected543 remains unchanged;
confirmation and causal learning-speed gains remain unproven. See
`run-26/lr25-first8M-frozen-quality-root-preparation-20261017/`,
`run-26/lr25-first8M-quality-R1-startup-root-20261017/` and
`quality-CE543M-vs-CE4096-lr25-first8M-trial01-20261017/`.

Subsequent source review identified two conditional replay discontinuities:
an accepted game reset can reach replay before old transition state is cleared,
and a rejected frame can introduce a neutral action while the next accepted
frame still attributes its transition to the previous action. Neither live
occurrence nor learning impact is established; a bounded final2MiB console
sample contained no matching throttled rejection warnings. A narrow accepted
new-game patch is sealed and independently source-reviewed. After
honest partial campaign closure and explicit freeze release, all seven actual
whole-handler guards passed once in a retained CPU unit (exit0, no skips,
1.888s); full archives preceded owned release. The original branch reproduces
the crossing row; the patched handler guards use isolated memory. Rejection-only
handling remains separate and unpatched. Newest-state maintenance source passed
independent review and all four original metadata/order guards (exit0, no skips,
0.232s), with archives before owned release. It preserves the newest saved
model/Adam/scaler/clocks and checks replay/bank retention; no coherent RAM/FIFO
anchor is claimed. The original maintenance installed socket4a and both inline
CPU checks exited0, then failed reconnect guards (`client_count` and
`new_runtime_log_error`) and retired its new owner2216495. Original parent exit1
and all evidence remain preserved. Its192 original actors resumed. The actual
newest saved checkpoint ce9e at692277875 learner
frames passed one separate strict b2e check with honest stopped/client0 scope.
A distinct newest-only recovery fixes the overlapping restart/runtime log
handover and passed six focused guards once. Its distinct original parent exited0,
with genuine startup0 CPU verification, all192 clients and60.286 clean seconds
within the original600s deadline. Full archives preceded timer-first owned
release. Fresh post-release checks passed for owner2257565/38102590/2cd616ad,
new phase cb904195, source61/control2/unit3, original actor masks, graphs128+640,
native replay and zero runtime errors. Training resumed from ce9e and progressed
beyond692.8M learner frames; the protected reference remains543M. The next fresh
post-READY window prospectively requires8M learner and8M accepted DQN/epsilon
transitions; this does not relabel the previous LR window's6M accepted threshold.
Future frozen confirmation precommits2400s admission and3600s timeout per leg,
retaining all existing individual gates and full tails. No retry, rollback,
confirmed quality improvement or causal learning-speed gain is claimed. See
`run-26/terminal-replay-segment-discontinuity-source-review-20261017/` and
`run-26/accepted-newgame-replay-boundary-unapplied-source-preparation-20261017/`.
Recovery evidence is in
`run-26/accepted-newgame-failed-maintenance-forward-recovery-20261017/`,
`run-26/accepted-newgame-forward-recovery-parent-root-execution-20261017/` and
`run-26/accepted-newgame-forward-recovery-postrelease-health-root-20261017/`.
The passive continuation window completed under original parent2294269.
Fresh B is696401265 learner frames /4121568 accepted DQN+epsilon transitions;
the corresponding targets are704401265 /12121568, both required. The3600s
cutoff starts at the actual nonzero pending0 B, after genuine READY and fresh
current-resource review. All six observer guards and four capture guards passed
once. The capture-test process ended before root's live PID observation; its
actual retained PID/invocation, original exit0 and outputs are preserved, with
unknown kernel start ticks left null and the observer assertion retained.
No test was rerun. One durable eligible observation permits one managed model
snapshot and candidate192 CPU-job preparation; the monitor does not run CPU
verification, change LR, stop the owner or establish a quality win. Evidence:
`run-26/postaccepted-newgame-live8M-candidate-root-preparation-20261017/`,
`run-26/postaccepted-newgame-live8M-candidate-parent-root-execution-20261017/` and
`run-26/postaccepted-newgame-live8M-candidate-trial01-20261017/`.

The first durable observation1674 reached+8001951 learner frames and+8002396
accepted DQN/epsilon transitions after1902.9726s. Its optimizer deltas were31130
applied,14 AMP skips,0 unavailable and1 pending; physical accepted insertions
remain a separate11119104. One request captured candidate `eba19578…` at704405115
learner frames/3170349 steps/11409954816 samples/1408030630 fleet frames.
The original capture exited0. Its sole separate b2e CPU process2380324 also
exited0, with443 finite tensors,81 Adam states/one group, strict online+target
loads, valid scaler and matching CE phase. CUDA remained uninitialized. Full six
service/timer archives preceded each timer-first owned release. Eight production
metadata guards passed once in2.416s with no skips; a preceding launcher config
error executed zero tests and remains separate. Original verifier output retains
its actual mode; an independent readonly report supplies the bound CPU proof.
Fresh readiness passed and the single RCRC campaign launched at03:20 UTC on
2026-10-18 under original2401897/38461310/6cf11da7. Actual native plan4093225c
differs from the independently reviewed preview only in its creation timestamp.
R1 completed134 whole games with sum63605275, mean474666.2313 and median461400.
All16 slots contributed; pending and abandoned were0. Ten admitted tails ended
after close, the last199.55s later. Original evaluator2401917 exited0, and the
sole original metadata auditor2501739 also exited0; six original service/timer
archives preceded its timer-first owned release. C1 completed123 whole games
with sum68569500, mean557475.6098 and median519200. All16 slots contributed,
pending/abandoned were0, and15 full tails ended as late as302.88s after close.
Its original evaluator2501433 exited0. Original metadata auditor2598263 exited2
because concurrent shutdown output interleaved eight otherwise exact traces;
the waiter then exited1 after an already-collected timer returned cat1/stop5.
Those original failures and incomplete terminal timer evidence are preserved.
Independent row/source reviews plus root acceptance `ffb60de2…` established the
same cohort's integrity: all admitted games finished before logical owned
shutdown, every flagged byte reconstructs the exact known shutdown traces, and
no earlier fatal or unknown remainder exists. Console lines lack individual
timestamps; the review relies on source order, not invented line times. Root
closure `1d0f999d…` retained the failures and released only the stopped audit
service after confirming its timer was already absent. No audit was rerun.
R2 evaluator2597979 completed136 whole games with sum67347475,
mean495202.0221 and median471837.5. All16 slots contributed; pending and
abandoned were0. Twelve full tails ended up to252.2441s after close. Original
auditor2689421 and waiter session13896 exited0. All six archive commands
succeeded before timer-first owned release; independent row and lifecycle
reviews passed. The final270-game R1+R2 reference pool has sum130952750,
mean485010.1852 and median464475. C1 clears both individual gates: mean is
14.9410% higher and median is519200. Its original audit2/waiter1 and separate
narrow integrity acceptance remain unchanged. C2 evaluator2689023 completed128
whole games with sum67926650, mean530676.9531 and median484650. All16 slots
contributed; pending and abandoned were0, and11 full tails ended up to255.0137s
after close. Its original auditor2780390 and waiter session16764 exited0.
All six archive commands succeeded before timer-first owned release. Independent
closed-row and lifecycle reviews passed. C2's mean is9.4156% above the same
fixed270 reference and its median passes; C1 and C2 qualify independently.
The native parent2401897 exited0; its six original archives and timer-first
release also passed review. The protection tool revalidated the original rows,
precommit, source and checkpoint hashes, then published
`models_dqn/managed-incumbents/freshCE-accepted-newgame-704M-confirmed-20261018.pt`
as a new immutable policy. Root adoption and source-freeze release are recorded
in `run-26/accepted-newgame-forward-recovery-root-control-20261017/`
`root-confirmed704-protected-canonical-adoption-and-source-freeze-release-20261018.json`.
The protected543M policy and all original failures remain preserved. Training
continues with192 actors on GPU1; it was not rolled back to the frozen winner.
The dashboard reports four fresh legs and no stale/read error. Its headline now
uses saved checkpoint clocks and correctly shows543.2M vs704.4M, rather than
interpreting the candidate's additional8M window as its total training age.
Frozen-policy quality is confirmed; a causal learning-speed gain is not
established. CPU evidence is in
`run-26/postaccepted-newgame-live8M-candidate-CPU-original01-root-execution-20261017/`.
The completed campaign is
`quality-CE543M-vs-postaccepted-newgame-first8M-trial01-20261017/`.
Its first reference leg's root-owned passive audit waiter completed0. The same
reviewed waiter accepts an explicitly bound leg1..4 and the observed evaluator
PID/start; it does not choose future evaluators. After the native finished
record it launches the selected metadata auditor once. Original evaluator and
auditor exits remain separate. Successful audits retain service/timer archives
and release their own units. C1 exposed an inherited absent-timer edge on the
nonzero path: preserve the original terminal archive and waiter failure, then
complete an exact root-owned closure without rerunning either payload or
observer. Archive attempts are not proof every archive command succeeded.
Polls retain compact start/end evidence
without creating a new file every15s. It does not alter training, admission or
confirmation criteria. R2 session13896 completed0 and its process2606645 is
gone. C2's observed passive waiter session16764/process2692498 completed0;
evaluator2689023/start39272048 is gone. Leg1 session38110 completed0 and C1
session16985 completed1. These completed handles must not be resumed or rerun.
The fixed fresh reference and both individual candidate gates are final.
Historical audit/gate aliases were preserved before this campaign, and prior
incumbent aliases were archived before adopting704M. Future comparisons use
the new protected policy with new fresh reference cohorts, not the pooled
candidate scores from this campaign.

A later descriptive review authenticated all531 admitted games from the same
closed campaign. Mean recorded playable frames rose10.57% and4.27% in C1/C2;
aggregate score per recorded playable frame rose3.95% and4.94%. Both candidates
also scored more in comparable recorded-frame bins and reached level29+ more
often. Gains were strongest in the upper-middle scores; C2's lower10th percentile
remained slightly below the fixed reference pool. These are associations within
the original games, not evidence of a causal learning-speed mechanism. They do
not replace or rescue either independent qualification gate. The receipt is
`run-26/protected704-score-survival-association-independent-saved-analysis-20261018/analysis-receipt.json`.
The best-supported next decision remains completion of the current unchanged
continuation and its fresh confirmation. No new recipe is selected by this
retrospective analysis.

The diagnostic changes cover serialized client error/traceback output, bounded
rejected-frame gap telemetry, a readonly diagnostic API, and SHA-bound saved-clock
headline labels. Three bounded original regression
suites passed once after freeze release:19+12+12 tests,43 passed with no skips.
Every payload exited0; all six archives per suite preceded timer-first owned
release. These tests exercised the proposed controller/helper and extracted
candidate API/reader/exception paths; they do not establish live throughput or
model efficacy. A separate corrected activation fixture passed7 native checks;
its original6-pass/1-fail fixture and subsequent launcher timer-format failure
remain preserved. The timer controller repair then passed20 checks.

Root applied the reviewed four-file diagnostic transaction once on2026-10-18.
Both newest-stopped and zero-actor startup CPU verifications passed at761680518
learner frames. Startup legitimately advanced one optimizer step on retained
replay; the proofs establish nondecreasing clocks, not bit-identical weights.
The same192 actors and masks, replay banks and nine ring mappings were retained.
Trainer2863379/start39797375/invocation5a8bfc5e10674a8e9169978804378393
passed a60.376s health window. The original activation parent exited0, all six
archives succeeded, and timer-first owned release passed. Actual evidence is in
`run-26/rejected-gap-healthy-activation-original01-20261018/` and its sibling
`rejected-gap-healthy-activation-original01-root-execution-20261018/`.
The real `/api/rejected_gaps` reports enabled, available counters for this owner;
its initial sample contained no rejected gaps or observer errors. The first
postactivation sampler failed a composite availability assertion and retained
no raw response; its exact cause remains unknown. The revised observer retained
all seven raw samples over120s, with zero classified issues or rejected gaps.
One sample showed the normal single in-flight optimizer attempt: availability
was false until its outcome was recorded. Logical learner throughput was3944.1/s
versus4205.4/s in the earlier window (6.21% lower). The windows were about41 minutes
apart with an evolving learner and host workload; this is not a causal telemetry
cost estimate or an efficiency gain. Two subsequent bounded192-thread synthetic
cost experiments each completed12 fixed-order runs. The first exposed a shared
bound-method artifact. The second compared per-worker cached methods with the
per-hook lookup used by the socket handler; the disabled lookup path was much
cheaper than the cached path, while enabled saturated paths were similar. These
probes establish call-style sensitivity, not real actor duty-cycle cost or the
cause of the live6.21% difference. All24 runs passed their counter checks, and
both original units and their archives/releases passed independent review.
A small None-ticket guard proposal has passed source review but remains
unapplied. A deferred differential fixture now
compares the complete held handler with real n-step/reset/telemetry code under
explicit fakes. After source review and the current confirmation's final closure,
its single original bounded run passed all six methods in4.032s. The original
unit exited0; all six archives preceded timer-first owned release.
The selected notes accurately limit journal comparison to recorded scalars,
boundary arguments and ordering. Numerical kernels, physical replay processing,
actual journal rows, concurrency and production cost remain outside its scope.
This execution followed final disposition and explicit source/control/workload
freeze release. One subsequent paced192-thread trial completed all eight
precommitted ABBA/BAAB arms at40.59 accepted frames/s per connection. Each arm
completed62400 measured frames with exact side-effect/state/exposure equality
and valid timing/counters. Median paired B/A process CPU was0.980517, about1.9%
less CPU in this synthetic complete-handler harness. Fakes, hashing, pacing,
shared locks and coordinator costs are included; this establishes neither a
production throughput gain nor faster learning. The patch remains unapplied.
A same-instance cumulative sample recorded70875892 counted accepted events
with zero rejected-gap, observer-fault, saturation or overflow counters. Held
source review confirms those counted events returned None tickets, supporting
the proposed fast path's relevance. Measure its actual cost benefit separately
after equivalence verification; the snapshot does not supply a hook-call count.

Five new metadata compatibility guards passed once. The evaluator inventory now
includes the diagnostic helper as its thirteenth source; its numerical body is
unchanged. Fresh E13+X4/62-source bindings are selected. The original next window
started at07:45:20 UTC from771606316 learner frames and9923785 accepted
DQN/epsilon transitions. It requires779606316 learner frames and17923785 accepted
transitions before one candidate request. The same trainer2863379 and192 actors
remain in use. Its original unit is
`robotron-postdiagnostic-live8M-candidate-original01-20261018.service`;
evidence is under `run-26/postdiagnostic-live8M-candidate-trial01-20261018/`.
The first eligible event added8002816 learner frames and8003515 accepted
DQN/epsilon transitions; file and directory durability completed in2025.044s,
within the original3600s cutoff. Exactly one model-only candidate was published.
The original capture exited0; all six archives preceded timer-first owned
release. Independent closed-metadata review passed.

Root's first CPU launcher refused before scheduling or loading a model: its
capture configuration had requested an extra `payload_result` receipt field
that the inherited checker forbade. The original successful release and this
preparation failure remain intact. Additive metadata siblings now accept that
field only when it exactly matches the actual result's minimal identity PIN,
including types; all original identity/source/archive/release checks remain.
Six targeted guards passed once. The original audit-waiter fixtures also passed
six checks separately; they are not evidence for a different waiter variant.
The original numerical CPU verification then ran once and exited0. Both
networks loaded strictly;443 tensors,81 Adam states and scaler data were finite.
Saved learner frames are779610569, and checkpoint SHA is `57a53937…`.
Its six archives and timer-first release passed independent review.

Fresh readiness and the fixed-profile root plan review preceded one native
RCRC launch at08:34 UTC. The closed default-plan independent review completed
after launch and is recorded separately. The actual native plan matches the
default except its creation timestamp. First reference evaluation3060892
finished0 at09:18 UTC with all128 admitted games, all16 slots, no abandonment
and13 full completion tails (maximum189.160s after admissions closed). The
original completed-leg audit ran once and exited0; all six archives preceded
successful timer-first owned release. Independent saved-row and lifecycle
reviews passed;3163 admitted life records reconcile with those128 games.
Its mean is559118.1641 and median565550.
The first candidate evaluation3149466 finished0 with all123 admitted games,
all16 slots and no abandonment. Its mean is561143.0894 and median522925;
12 full completion tails were retained, with a maximum306.534s after close.
Its original completed-leg audit ran once and exited0, with all six archives
and timer-first owned release complete. Separate saved-row and lifecycle reviews
passed, including reconciliation of3058 admitted life records. Second reference
evaluation3242236 finished0 at10:47 UTC with all120 admitted games, all16 slots,
no abandonment and8 full tails (maximum147.263s after admission closed).
Its mean is554589.375 and median529875. The original completed-leg audit
exited0; all six archives and timer-first owned release passed separate closed
row and lifecycle reviews. All2948 admitted life records reconcile.
The fixed fresh R1+R2 pool contains248 games, mean556926.8145 and median542000.
C1 misses both gates: its mean gain is0.7571%, below5%, and median522925 is
below542000. Final candidate evaluation3330038 finished0 with all122 admitted
games, all16 slots and no abandonment. Its mean558727.8689 (+0.3234%) and
median495625 also miss both gates. All10 completion tails were retained
(maximum272.516s), and3016 admitted life records reconcile. Its original audit
exited0 with six archives and timer-first release; separate saved-row and
lifecycle reviews passed. Independent final arithmetic matches the native
not-improved outcome across493 games and43 full tails, without candidate pooling.
The protected704 policy remains the incumbent. Main training remains on2863379
with192 actors. Passive filesystem metadata also confirms recent periodic
latest-policy replacements approximately300s apart; this does not validate
their numerical contents or a coherent replay/bank resume state.
The original parent exited0. All69 original campaign processes were absent,
GPU0 was idle and the unchanged trainer remained onGPU1. Both parent service
and timer had all six raw archives before timer-first owned release; independent
closure review passed. Root recorded the failed disposition and explicitly
released the experiment freeze, preserving every result and protected policy.
The campaign is `quality-CE704M-vs-postdiagnostic-first8M-trial01-20261018/`.
Both candidate cohorts must independently pass against the new fresh R1+R2
pool. Previous campaign scores were not reused, and779M did not qualify.
No causal speed improvement is claimed.

The next prospective efficacy screen uses the existing live LR scale control
(.5 to.25), preserving Adam, replay, actors and schedule clocks. Its benefit is
uncertain. The recipe-aware capture/CPU/quality family has passed source review
and22 metadata/controller guards. The first guard run's20 passes and2 fixture
errors remain preserved; a fixture-only correction passed22/22 in0.501s with
owned archives/release and independent review. Historical successful startup
authority and the current failed campaign release remain distinct. Fresh live
preflight passed and the original continuation started at12:29 UTC on October18.
The live control now holds.25 (effective LR1.25e-5) on the same trainer, Adam,
replay epochs,192 actors and CE phase; no source or model structure changed.
After a post-refresh managed barrier, fresh B was837078391 learner frames and
75395269 accepted DQN+epsilon insertions. Both must advance by8000000 within
the fixed3600s window before its first durable endpoint grants one candidate
capture. That original window completed in2032.945s: +8003540 learner frames
and +8001940 accepted DQN+epsilon insertions. The original capture exited0;
all six archives and timer-first owned release passed closed review. Candidate
`CE4096-LR25-first8M-trial01-20261018.pt` saved at845082817 learner frames.
Its single original numerical child exited0 and reported PASS,443 finite tensors,
81 Adam states and actual saved Adam LR1.25e-5. The CPU launcher's overall exit1
and FAIL receipt are preserved: it compared a flattened report fingerprint with
the equivalent nested job fingerprint. Closed metadata rechecks pass; no model
rerun occurred. A separate, independently reviewed metadata companion admits
only that exact known failure while retaining every existing numerical,
archive and release gate. Its six guards passed once in0.145s with all six
archives and timer-first owned release. Root published an explicit review and
an exact copy of the original CPU execution plus that review PIN; raw FAIL
and all original artifacts remain unchanged. Fresh runtime collection and the
actual default plan passed review. The original full R/C/R/C campaign launched
at13:35 UTC on October18: parent3673741, first reference evaluator3673748 onGPU0,
unchanged main2863379 and192 actors onGPU1. R1 completed125 valid games, with
mean547589.8 and median511425. All16 slots contributed;12 full tails were
included, maximum285.957s after admission closed. The original bound audit
exited0; all six archives preceded timer-first owned release. Independent data
and lifecycle reviews passed, including all3039 admitted life records. C1
ran from14:21 to15:07 UTC and completed92 valid games, with mean731029.6195652174,
median757762.5 and score sum67254725. All16 slots contributed;12 full tails
were retained, maximum357.51784896850586s after admission closed. The original
bound audit exited0 with all six archives and timer-first owned release;
independent row/life and lifecycle reviews passed. All2912 admitted life records
reconcile. R2 ran from15:08 to15:52 UTC and completed122 valid games, with
mean531942.6229508197, median477125 and score sum64897000. All16 slots
contributed;10 full tails were retained, maximum248.7404763698578s. Its
original bound audit exited0 with all six archives and timer-first owned
release; independent row/life and lifecycle reviews passed, including2885
admitted life records. The fixed fresh R1+R2 pool contains247 games, with
mean539861.2348178137 and median489675. Each candidate must independently
reach mean566854.2965587045 and median489675. Root and independent review
confirm C1 passes both gates: mean+35.4106523%. C2 ran from15:52:58 to16:38:48
UTC and completed91 valid full games: score sum65126250, mean715673.0769230769,
median767500, all16 slots and13 full tails (maximum300.43672251701355s).
Its original bound audit exited0; independent row/life and lifecycle reviews
passed, including2821 admitted life records. Root and independent final math
confirm C2 separately passes both gates: mean+32.5661171%. All430 original
rows have unique game IDs; all47 completion tails are included. No historical
reference or candidate-pooling rescue was used.
Actual native plan8ac7c572 equals the reviewed preview
except its creation timestamp. All four2400/3600 legs held.25, min50,
all16 slots and full tails. Both candidate cohorts independently pass the
fresh R1+R2 mean+5% and median gates. The original native parent exited0;
four actual closure guards passed, and its six archives and timer-first owned
release passed independent review. One original protection command exited0
and published immutable model/metadata. Root verified the model hash, adopted
`models_dqn/managed-incumbents/freshCE-LR25-845M-confirmed-20261018.pt` as the
next reference and explicitly released the experiment freeze. Its SHA256 is
`fda8dcdf80a794b2715843dc892890296363c7586c60bae435a0925e32997ecd`;
metadata SHA256 is
`cbae40714a55aa3ce902bb9804f5ee5545c8e995eec94210fe518946d699a2cb`.
Protected704M and543M remain; the original live trainer/replay/192 actors
continue at.25 without a restore or model-structure change. This establishes
frozen-policy quality, not causal LR effects, learning speed, throughput or
statistical confidence. The ongoing goal continues with fresh prospective
capture and fresh reference cohorts for the next comparison. The campaign is
`quality-CE704M-vs-LR25-845M-trial01-20261018/`.

A separate source review identified a conditional replay-slot freshness defect.
The async consumer retains bare episode indices; elite-bank admission checks
their range before copying the rows currently at those positions. Other actors
can overwrite a long-lived episode's slots before admission. For a64-slot ring,
A's32 rows followed by B's64 rows and A's terminal can admit32 B rows under
A's score/game ID. Current incidence and learning impact remain unmeasured.
`tools/elite_bank_replay_slot_freshness_proposal/` contains the source finding,
six isolated characterization tests and an insertion-token design.
A separate corrected patch in
`tools/elite_bank_replay_slot_receipt_fix_proposal/reviewed2-failure-fence-final-20261018/`
has passed independent source review. It adds atomic insertion receipts,
same-lock validation for bank/death/elite callbacks, failure incompleteness and
episode-boundary recovery. The blocked first draft remains preserved. After
the entire845M confirmation, owned closure, protection, adoption and explicit
freeze release, root ran the original six characterizations first:6/6 passed
in0.121s. The corrected patch's eleven isolated tests then passed11/11 in1.707s.
Both original commands exited0, with six archives and timer-first owned release.
The fixtures use small NumPy/source-extracted/virtual cases; they establish
the scoped failure and rejection/recovery contracts. The production patch
remains unapplied. Actual replay incidence, production cost and learning benefit
remain unmeasured.
Existing bank contents cannot be certified retrospectively from indices;
ordinary delayed sample-to-PER updates and late shutdown producer publication
remain separate, explicitly excluded issues.

Keep mutable `state.json` in compact JSON form below the dashboard's existing
1 MiB reader limit. Compacting retained all parsed values; no reader limit or
scientific source changed. Current status updates use this format. The inactive
historical KL research field is now archived intact in
`run-26/root-archived-historical-kl-calibration-before-state-compaction-20261018.json`;
the current field links that immutable history. The preservation receipt proves
that its parsed contents and all other state values were retained. This reduced
the live state from973234 to858136 bytes before subsequent status updates.

The proposed 2048-batch experiment changes optimizer cadence as well as batch
size. At unchanged LR and replay-pressure credit it permits twice as many
optimizer attempts per logical sample count. Cap8 uses nonmeasurement fleet
frames, so the 8M learner-frame and 6M accepted-insertion horizon does not
equalize sample exposure. Compare actual fleet/learner frames, per-source
accepted insertions, logical samples, admitted optimizer calls times batch
size, AMP skips and elapsed time. An admitted call does not prove every Adam
state advanced. LR and target schedules remain sample-based; actor refresh
rounding and the per-batch diagnostic cadence also change. Higher steps/s or
passing a frozen-policy quality comparison alone cannot establish faster
learning; that claim needs matched 4096 control evidence. The failed trial01
startup and recovery remain ancestry, with no trial01 efficacy result.

Existing observer records already retain the necessary exposure endpoints.
Derive every delta from `observer-job.before_resume_api` to the original
LATCH's `first_eligible_observation`; boot-origin logical-sample progress has
a different starting point. Use complete, matching process/epoch counters
for exact admitted-row and AMP-skip calculations. If the first LATCH has an
unfinished outcome, keep that LATCH and report exposure as incomplete or
bounded by one outcome. Ending API snapshots and saved CPU clocks describe
different instants and cannot establish an exact applied/skipped split
through shutdown. No observer or gate change is required.

The proposed bank-weight floor remains unselected: historical coefficient mass
and scalar loss shares do not establish a gradient or retention defect. No
reviewed retained consumed batch proves the current CE phase; any future
coefficient observation and PRE-based gradient diagnostic require separate
bounded preparation after this campaign's full audits, cleanup and freeze release.
Three passive readings of existing main-learner C51 metrics showed low sampled
target mass outside the support. Those fields are unweighted, decimated batch
means without individual batch IDs or population coverage; they justify no
support or architecture change. The source interpretation and original readings
are pinned under
`run-26/rawKL-trial02-quality-C1-running-passive-main-diagnostics-root-20261017/`.
An unapplied coefficient-only observation proposal has a source review and 15
authored guards, all unexecuted. It requires full freeze release, actual guard
execution and a separately bound future CE resume before activation; it supplies
no PRE model, target distribution or gradient identity.
The nonratchet learner still autosaves the latest model every 300 seconds;
dirty banks have a separate 1800-second schedule. A passive check observed a
15-second-old latest model file and four successful bank writes, while dirty
admissions remained. This is persistence metadata, not a finite-model or coherent
replay/RNG/actor proof. After final decision, owned closure and freeze release,
prefer one unique live managed model-only capture plus independent readonly copy
and candidate phase CPU verification for the next quality test. That capture
does not require restarting the 192 actors; optional reporting or observer
maintenance may wait if it would delay the next useful test.
