"""One-shot stdlib artifact audit; no production imports or runtime queries."""
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
RUN = OUT.parent
TRIAL = RUN / 'inference-cpu71-reservation-post320M-quality-reviewed2-20261017'
ALL = list(range(72))
checks, artifacts = [], []


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)


def archive(source, name, expected=None):
    source = Path(source)
    data = source.read_bytes()
    if expected is not None:
        check('binding:' + str(source), digest(data) == expected)
    copy = OUT / name
    save(copy, data)
    artifacts.append(dict(source=str(source), copy=str(copy), sha256=digest(data), bytes=len(data)))
    return data


def check(name, passed):
    checks.append(dict(check=name, passed=bool(passed)))


def key(owner, row):
    identity = owner['identity']
    return [identity['pid'], identity['starttime_ticks'], row['tid'], row['starttime_ticks']]


original = {}
for name in ('precommit.json', 'originals.json', 'status.json', 'mutation-journal.jsonl', 'observations.jsonl'):
    original[name] = archive(TRIAL / name, 'original-' + name)
plan = json.loads(original['precommit.json'])
originals = json.loads(original['originals.json'])
status = json.loads(original['status.json'])
journal = [json.loads(line) for line in original['mutation-journal.jsonl'].splitlines()]
rows = [json.loads(line) for line in original['observations.jsonl'].splitlines()]
launch = json.loads(archive(RUN / 'cpu71-reservation-reviewed2-detached-launch-20261017.json', 'original-detached-launch.json'))
archive(RUN / 'cpu71-reservation-reviewed2-scheduler-gone-observation-20261017.json', 'original-scheduler-gone.json')
console = Path(str(TRIAL) + '.console.log')
if console.exists():
    archive(console, 'original-controller.console.log')
for index, (source, expected) in enumerate(plan['bindings']['source_hashes'].items()):
    archive(source, f'source-{index:02d}-{Path(source).name}', expected)
for index, (source, expected) in enumerate(plan['bindings']['control_hashes'].items()):
    archive(source, f'control-{index:02d}-{Path(source).name}', expected)

check('originals hash equals precommit', digest(original['originals.json']) == plan['originals_sha256'])
check('fixed A/B/Areturn protocol', plan['phases'] == ['A', 'B', 'Areturn'] and
      [plan[name] for name in ('settle_s', 'window_s', 'poll_s', 'scan_budget_s')] == [90, 300, 1, 1.0])
check('fixed qualification gates', plan['gates'] == dict(applied_rate_ratio=1.05,
      accepted_learner_rate_ratio=1.0, amp_skip_fraction_allowance=.001, SPF_min=7.6, SPF_max=8.4))
check('failed invalid no completed phase results', status['state'] == 'failed' and status['results'] == []
      and status['decision'] == dict(outcome='invalid', automatic_promotion=False))
check('journal contiguous and complete', original['mutation-journal.jsonl'].endswith(b'\n') and
      [row['sequence'] for row in journal] == list(range(1, len(journal) + 1)))
kinds = collections.Counter(row['kind'] for row in journal)
check('no treatment or restore mutation journal records', kinds == dict(thread_scan=37, new_thread=36, phase_start=1))
check('all 35 observations retained before primary', len(rows) == 35 and
      all(row['phase'] == 'A' and row['stage'] == 'settle' for row in rows))
starts = [row for row in journal if row['kind'] == 'phase_start']
check('only original A phase started', len(starts) == 1 and starts[0]['phase'] == 'A' and
      rows[-1]['observed_monotonic_s'] - starts[0]['phase_start'] < 90)
owners = originals['processes']
check('original exact trainer plus192slots', len(owners) == 193 and owners[0]['kind'] == 'trainer' and
      [owner['identity']['client_slot'] for owner in owners[1:]] == list(range(192)) and
      [owner['identity'] for owner in owners[1:]] == plan['bindings']['actors'] and
      owners[0]['identity'] == plan['bindings']['worker']['trainer'])
check('original421tasks broad masks', sum(len(owner['threads']) for owner in owners) == 421 and
      all(task['affinity'] == ALL for owner in owners for task in owner['threads']))
scans = [row for row in journal if row['kind'] == 'thread_scan']
worker = plan['bindings']['worker']
worker_key = [worker['trainer']['pid'], worker['trainer']['starttime_ticks'],
              worker['thread']['tid'], worker['thread']['starttime_ticks']]
scan_results = []
for scan in scans:
    processes = scan['processes']
    matches = [key(owner, task) for owner in processes for task in owner['threads']
               if owner['kind'] == 'trainer' and task['comm'] == 'InferBatchWorke']
    scan_results.append(dict(sequence=scan['sequence'], phase=scan['phase'], scan_start=scan['scan_start'],
        duration_s=scan['scan_duration_s'], owners=len(processes),
        tasks=sum(len(owner['threads']) for owner in processes),
        exact_owners=[owner['identity'] for owner in processes] == [owner['identity'] for owner in owners],
        all_original_masks=all(task['affinity'] == ALL for owner in processes for task in owner['threads']),
        exact_inference=matches == [worker_key]))
check('every scan exact193owners421tasks broad masks and inference', all(
      row['phase'] == 'A' and row['owners'] == 193 and row['tasks'] == 421 and
      row['exact_owners'] and row['all_original_masks'] and row['exact_inference'] for row in scan_results))
check('exact final scan solely exceeds fixed budget', scans[-1]['scan_duration_s'] > 1 and
      all(row['scan_duration_s'] <= 1 for row in scans[:-1]))
expected_issue = "all_thread_guard:RuntimeError('Complete all-thread guard exceeded fixed1s scan budget')"
check('last original row alone retains failure', rows[-1]['issues'] == [expected_issue] and
      all(not row['issues'] for row in rows[:-1]))
previous = plan['initial_snapshot']
observation_checks = []
for number, row in enumerate(rows, 1):
    valid = row['client_count'] == 192 and row['training_enabled'] and not row['measurement_active']
    valid &= math.isclose(row['epsilon'], .1) and math.isclose(row['expert_ratio'], .1) and math.isclose(row['lr'], 2.5e-5)
    valid &= all(math.isfinite(row[name]) for name in ('loss', 'grad_norm')) and not row['grad_norm_nonfinite']
    valid &= not row['log_errors'] and not row['pipeline_read_error'] and not row['bank_persistence_read_error']
    valid &= all(value == 0 for value in row['pipeline_errors'].values())
    valid &= row['csv']['replay_dropped'] == 0 and row['csv']['batch_size'] == 4096 and row['csv']['replay_sample_cap'] == 8
    valid &= row['graphs']['ready'] and row['graphs']['runtime_capture_count'] == 0 and row['graphs']['fallback_count'] == 0 and not row['graphs']['fatal_error']
    valid &= row['native']['enabled'] and row['native']['available'] and row['native']['fallback_count'] == 0 and row['native']['error_count'] == 0
    valid &= row['bank']['backend'] == 'stream' and row['bank']['stream_enabled'] and row['bank']['write_failures'] == 0 and row['bank']['output_errors'] == 0 and not row['bank']['last_error']
    for kind in ('optimizer', 'replay'):
        exposure = row['exposure'][kind]
        valid &= {name: exposure[name] for name in plan['exposure_identity'][kind]} == plan['exposure_identity'][kind]
    optimizer = row['exposure']['optimizer']
    total = optimizer['total']
    pending = total['attempts_started'] - total['outcomes_recorded']
    valid &= total['unavailable'] == 0 and pending in (0, 1) and row['optimizer_pending'] == pending
    valid &= optimizer['available'] or pending == 1
    valid &= total['outcomes_recorded'] == total['applied'] + total['amp_skipped'] + total['unavailable']
    valid &= all(row[name] >= previous[name] for name in ('frame_count', 'learner_frame_count', 'optimized_samples', 'training_steps'))
    valid &= row['observed_monotonic_s'] >= previous['observed_monotonic_s']
    observation_checks.append(dict(row=number, recorded_recipe_exposure_and_health_consistent=bool(valid), optimizer_pending=pending))
    previous = row
check('all recorded API recipe health and exposure guards consistent', all(row['recorded_recipe_exposure_and_health_consistent'] for row in observation_checks))
restoration = status['restoration']
check('reported restoration clean and no changed tasks', restoration['masks_restored'] and
      not restoration['manual_recovery_required'] and not restoration['journal_failed'] and
      not restoration['errors'] and not restoration['journal_errors'] and not restoration['changed_tasks'])
check('all observed new threads already original masks', all(row['observed'] == ALL for row in journal if row['kind'] == 'new_thread'))
check('all original artifact and source bytes unchanged through audit', all(
      digest(Path(row['source']).read_bytes()) == row['sha256'] for row in artifacts))
durations = [row['scan_duration_s'] for row in scans]
report = dict(status='CONSISTENT_INVALID_PRETREATMENT' if all(row['passed'] for row in checks) else 'AUDIT_NEEDS_REVIEW',
    created_unix_s=time.time(), script_sha256=digest(Path(__file__).read_bytes()), checks=checks,
    trial=str(TRIAL), journal_counts=dict(kinds), observations=len(rows), phase_results=[],
    no_comparative_gain_claim=True, no_treatment_evidence=dict(intent_records=0, applied_records=0,
        B_transition_records=0, broad_masks_in_every_scan=True,
        interpretation='Under the bound controller, treatment syscalls require durable intent before mutation; no such intent exists and journal has no failure. No independent kernel syscall trace was collected.'),
    scan_summary=dict(count=len(scans), min_s=min(durations), median_s=statistics.median(durations),
        mean_s=statistics.mean(durations), preceding_max_s=max(durations[:-1]), final_s=durations[-1],
        sum_s=sum(durations), scope='Serial controller scan wall times include scheduling/I/O; they do not establish CPU cost or cause of the final delay.'),
    scan_rows=scan_results, observation_checks=observation_checks,
    observed_interval_s=rows[-1]['observed_monotonic_s'] - rows[0]['observed_monotonic_s'],
    final_guard_cycle_s=rows[-1]['guard_cycle_s'], restoration=restoration,
    root_provided_original_terminal=dict(unit=launch['unit'], invocation='2b9ffafe4bd64336b02f866baaf360fc',
        ExecMainPID=3392678, ExecMainCode=1, ExecMainStatus=1, Result='exit-code',
        exit_utc='2026-10-17T02:39:31.024338Z', provenance='Root observation; root archives original unit/journal and independently verifies live restoration/rearm.'),
    limitations=['No primary window or treatment began; no throughput or quality conclusion follows.',
        'Saved scan durations prove the guard breach, not why scheduling/I/O took longer.',
        'Controller restoration is corroborated by broad masks in all recorded scans; fresh runtime restoration and original service exit are independently owned by root.',
        'This audit does not rescan historical trainer/actor log bytes; recorded log_errors remain preserved.'],
    artifacts=artifacts)
target = OUT / 'review-receipt.json'
save(target, (json.dumps(report, indent=2) + '\n').encode())
fd = os.open(OUT, os.O_DIRECTORY)
try:
    os.fsync(fd)
finally:
    os.close(fd)
print(json.dumps(dict(path=str(target), sha256=digest(target.read_bytes()), status=report['status'],
                      passed=sum(row['passed'] for row in checks), checks=len(checks), scan_summary=report['scan_summary']), indent=2))
raise SystemExit(report['status'] != 'CONSISTENT_INVALID_PRETREATMENT')
