# Bank persistence

`PrioritizedReplayBuffer.save_banks_if_dirty()` now schedules one background
writer and returns immediately. A second request while it is active does not
create another writer or grow a queue. The periodic caller's returned strings
say `queued`; completion and failure are available from
`get_bank_persistence_stats()`.

The change addresses the demonstrated shared replay-lock pause during bank
disk writes. Other synchronized emulator stalls have also occurred outside
bank saves; this change does not establish their cause or resolve them.

## Coherent capture and dirty revisions

Every accepted admission advances a bank mutation revision, even when several
admissions share a ring-add clock. These revisions are independent of sampling,
RNG, quota, optimizer, model and schedule clocks.

Capture copies episode metadata and both staleness ages relative to the same
ring-add snapshot. It allocates compact RAM arrays outside the replay lock and
copies only valid episode prefixes, in chunks of at most 128 rows. State pairs
remain FP32. Each chunk checks the captured mutation revision and load epoch;
an admission during capture rejects the entire attempt. Ring additions alone
do not invalidate a bank snapshot. Two attempts are allowed; if both fail, the
bank stays dirty for the next request or explicit flush. There is no fuzzy
combination of versions and no unbounded capture loop.

One bank is captured and written at a time. Peak staging memory is the compact
valid data of that bank, rather than both padded banks. A capped CPU probe on
this host with 2,048 rows of width 11,128 captured 182 MB of FP32 state pairs in
18.6–19.5 ms, with the longest individual locked copy 1.32 ms. These are local
probe measurements, not a bound under every host load.

## Publication and recovery

Disk writes, sparse-array flushes and fsync run outside the replay lock.
Each save creates `generations/gen-<uuid>/` under the existing bank directory,
writes and fsyncs the arrays and metadata, fsyncs the generation directories,
then atomically replaces and fsyncs `CURRENT.json`. Current and previous
complete generations are retained. Failed unpublished work is removed. A
failure after selector replacement leaves a complete selected generation but
keeps the bank dirty; an explicit retry remains possible.

The files retain the original padded `.npy` geometry and scalar dtypes.
Unused padding is zero-filled sparse storage. Metadata retains `ep_score`,
`ep_len`, `ep_game`, `ep_level`, `stride`, `state_size`, `stale_age` and
`stale_age_normal`, with capture/revision provenance added. Only the captured
revision becomes saved after successful publication; admissions during disk
I/O remain dirty.

Loads and publication serialize on a separate persistence lock. Loads advance
an epoch, so requests queued before that load cannot later publish the prior
bank. A loader resolves `CURRENT.json` once and stages/validates all valid rows
before changing the live bank. Legacy flat directories load when CURRENT is
absent, including older metadata without game IDs. Malformed selectors,
missing selected generations or missing selected metadata fail explicitly;
they do not silently fall back to old legacy files.

The existing flat files are left untouched. Readers outside the buffer must
follow CURRENT to see new saves. Old software that only understands flat
files will still see the last legacy save, not the newer generations. The
live ring's mmap format and bank survival across ring clear are unchanged.

## Explicit save and flush contract

`flush_banks(timeout=None)` waits for the current writer, then synchronously
captures dirty banks. `timeout` bounds waiting for an already-running writer;
it does not interrupt a filesystem write. Capture still has bounded retries.
Disk errors or inability to obtain a coherent capture propagate to its caller.
It guarantees a coherent captured revision, not all future admissions:
admissions arriving after capture remain dirty. Quiesce actor producers first
when a complete shutdown tail is required.

The existing full `memory.save()` waits for any background writer before its
synchronous bank saves. It retains its historical behavior of warning on
individual bank failures and continuing the ring save. `agent.save()` also
downgrades replay save errors to warnings. This patch does not reorder main's
shutdown, where producers can still be active at the final save. Callers must
not interpret the old warning path as a guaranteed clean bank flush.

Telemetry includes capture attempts/deferrals, maximum chunk lock duration,
write count/failures/durations, last error, writer status, and per-bank live and
saved revisions/dirty flags. No telemetry/report/config code is changed here.

Focused CPU checks:

```sh
CUDA_VISIBLE_DEVICES='' .venv-gb300/bin/python -m unittest \
  Robotron.Scripts.dqn.test_bank_persistence \
  Robotron.Scripts.dqn.test_direct_replay \
  Robotron.Scripts.dqn.test_native_sumtree \
  Robotron.Scripts.dqn.test_replay_pressure
```
