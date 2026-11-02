#!/usr/bin/env python3
"""Read-only completed first96M receipt/owned-cleanup audit; no launch or promotion."""
from datetime import datetime, timezone
import hashlib
import json
import re
import statistics
from pathlib import Path
import subprocess
import sys
import time

RUN = Path(__file__).resolve().parent
CAMPAIGN = RUN.parent
GAME = RUN.parents[2]
LABEL = 'sidecar-gpu0-96M-regression-guard-01'
JOB = CAMPAIGN / LABEL
sys.path.insert(0, str(GAME / 'tools'))
from compare_sidecar_measurements import validate_backend, compare_sidecars
from sidecar_boot import load_snapshot

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for piece in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(piece)
    return digest.hexdigest()

def identity(pid):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return dict(start_ticks=int(fields[19]), state=fields[0])
    except (FileNotFoundError, ProcessLookupError):
        return None

def same_process(record):
    return (identity(record['pid']) or {}).get('start_ticks') == record['start_ticks']

started = datetime.now(timezone.utc).isoformat()
receipt_path = JOB / 'receipt.json'
assert receipt_path.is_file(), 'Final receipt must exist before this audit is run'
raw = receipt_path.read_bytes()
receipt = json.loads(raw)
assert receipt['phase'] == 'finished' and receipt['complete'] is True and receipt['active'] is False
startup = json.loads((RUN / 'quality96M-first-startup-independent-audit.json').read_bytes())
assert startup['PASS'] is True
lineage_path = CAMPAIGN / 'run-19/fresh3-96M-checkpoint-lineage.json'
assert sha(lineage_path) == 'aa701312ed0b4165b83e84e49b3add3e441d919d0e7b50b346bb33d38f06b4fa'
lineage = json.loads(lineage_path.read_bytes())
assert lineage['PASS'] is True and lineage['checks'] and all(value is True for value in lineage['checks'].values())
checks = {}
validation_error = None
leg = None
try:
    leg = validate_backend(receipt, verify_checkpoint=True)
    assert receipt['label'] == LABEL and receipt['receipt_validator'] == 'passed' and receipt['reason'] is None
    assert receipt['checkpoint_sha256'] == lineage['candidate']['sha256'] == startup['checkpoint_sha256']
    for key in ('training_steps', 'optimized_samples', 'learner_frame_count'):
        assert receipt['checkpoint_metadata'][key] == receipt['clocks'][key] == lineage['candidate']['saved_metadata'][key]
    assert receipt['source_checkpoint_path'] == receipt['job']['checkpoint'] == lineage['candidate']['path']
    assert receipt['checkpoint_metadata']['defaulted_metadata_fields'] == []
    assert all(receipt['checkpoint_metadata'][key] == value for key, value in lineage['candidate']['saved_metadata'].items() if key in receipt['checkpoint_metadata'])
    assert receipt['boundary']['clients'] == receipt['boundary']['expected'] == receipt['boundary']['acknowledged'] == 16
    assert receipt['boundary']['actor_slots'] == list(range(4096, 4112))
    references = []
    reference_rows = []
    reference_pins = {'sidecar-gpu0-64M-screen-01': 'a40030abe1ab8ab027f198c119ee5dbd2714fc1056fcf47aebbddce56aa55189', 'sidecar-gpu0-64M-confirm-01': '5f6628f79fd969f3a288f998cdb89d2aafb9ca1a0d655f964e63d9728374db8f'}
    for label, expected in reference_pins.items():
        reference_raw = (CAMPAIGN / label / 'receipt.json').read_bytes()
        assert hashlib.sha256(reference_raw).hexdigest() == expected
        prior = json.loads(reference_raw)
        reference_rows.extend(prior['rows'])
        checked = compare_sidecars(prior, receipt, iterations=100, verify_checkpoint=False)
        assert checked['backend_validated'] is True
        references.append(dict(label=label, receipt_sha256=hashlib.sha256(reference_raw).hexdigest()))
    assert receipt['source_hashes'] == receipt['ended_source_hashes'] == startup['source_hashes']
    assert all(sha(GAME / relative) == expected for relative, expected in receipt['source_hashes'].items())
    boot = load_snapshot(Path(receipt['job']['boot_assets']))
    assert boot['identity'] == receipt['boot_assets']['identity'] and boot['files'] == receipt['boot_assets']['files']
    assert all(value['identity'] == boot['identity'] and value['files'] == boot['files'] for value in receipt['boot_restores'].values())
    assert not receipt['cleanup_errors'] and not receipt['invalidity_reasons']
    assert not receipt['server_error'] and not receipt['inference_error'] and not any(receipt['actor_timeout_logs'].values())
    assert len(receipt['socket_wait']['actors']) == 16 and all(value['activation_count'] == 1 for value in receipt['socket_wait']['actors'].values())
    assert len(leg['rows']) == receipt['count'] == receipt['started'] and receipt['pending'] == receipt['abandoned'] == 0
    assert all(row['boundary_reason'] == 'wire_lives_exhausted' and row['end_unix_s'] <= receipt['ended_unix_s'] for row in leg['rows'])
    checks['final_receipt_full_backend_and_lineage_valid'] = True
except (ValueError, KeyError, AssertionError, OSError) as error:
    validation_error = str(error) or type(error).__name__
    checks['final_receipt_full_backend_and_lineage_valid'] = False
    references = []

# Independently distinguish runtime timeouts from intentional cleanup events.
runtime_counts, cleanup_counts, log_hashes = {}, {}, {}
cutoff = int(receipt['timeout_snapshot_unix_s'])
for slot in startup['actors']:
    content = (JOB / 'actors' / slot / 'console.log').read_bytes()
    log_hashes[slot] = hashlib.sha256(content).hexdigest()
    events = [line for line in content.decode(errors='replace').splitlines() if '[SOCKET ACTION TIMEOUT]' in line]
    observed = receipt['actor_timeout_logs_before_shutdown'][slot]
    measured = 0
    for index, line in enumerate(events):
        match = re.search(r'\bunix_s=(\d+)\b', line)
        measured += index < observed or match is None or int(match[1]) <= cutoff
    runtime_counts[slot] = measured
    cleanup_counts[slot] = len(events) - measured
checks['independent_timeout_classification_matches_receipt'] = runtime_counts == receipt['actor_timeout_logs'] and cleanup_counts == receipt['actor_cleanup_timeout_logs']
checks['zero_runtime_timeouts'] = not any(runtime_counts.values())

analysis_path = CAMPAIGN / 'run-19/quality96M-guard-first-analysis.json'
assert sha(analysis_path) == 'fd01088bbbc860083ef7f115bdd488aaaff19ec59ab3958163402007edd3f6cd'
analysis = json.loads(analysis_path.read_bytes())
management = analysis['management']
if leg is not None and checks['final_receipt_full_backend_and_lineage_valid']:
    reference_mean = statistics.mean(row['score'] for row in reference_rows)
    reference_median = statistics.median(row['score'] for row in reference_rows)
    candidate_mean = statistics.mean(row['score'] for row in leg['rows'])
    candidate_median = statistics.median(row['score'] for row in leg['rows'])
    checks['independent_management_arithmetic_matches'] = (management['reference']['count'] == len(reference_rows) == 217
        and management['reference']['mean'] == reference_mean and management['reference']['median'] == reference_median
        and management['thresholds'] == dict(mean=.9 * reference_mean, median=.9 * reference_median, severe_mean=.8 * reference_mean)
        and management['each_leg'][0]['mean'] == candidate_mean == receipt['mean']
        and management['each_leg'][0]['median'] == candidate_median == receipt['median']
        and management['each_leg'][0]['count'] == len(leg['rows']) == 81)
    checks['no_fixed_plan_alarm_or_confirmation'] = (candidate_mean >= .9 * reference_mean
        and candidate_median >= .9 * reference_median and len(leg['rows']) >= 64
        and management['status'] == 'no_preset_alarm_not_proof_of_noninferiority'
        and management['confirmation_required_by_first_leg'] is False
        and management['confirmation_still_needed'] is False
        and management['repeated_same_criterion_alarm'] is False
        and management['severe_first_leg_alert'] is False)
    checks['no_promotion_rebase_or_schedule_change'] = all(management[key] is False for key in ('promotion', 'reference_rebased', 'scheduled128M_changed', 'automatic_action', 'third_valid_cohort_authorized'))

# The runner writes its final receipt just before exit; allow bounded CUDA/process cleanup.
deadline = time.monotonic() + 15
while same_process(startup['runner']) and time.monotonic() < deadline:
    time.sleep(.2)
checks['original_runner_exited'] = not same_process(startup['runner'])
checks['all16_owned_actor_identities_gone'] = not any(same_process(value) for value in startup['actors'].values())
checks['main_trainer_identity_preserved'] = same_process(startup['main']['trainer'])
main = json.loads((RUN / 'actor192-all-connected.json').read_bytes())
checks['all192_pinned_main_actor_PIDs_alive'] = all(identity(pid) is not None for pid in main['mame_pids'])
gpu = subprocess.run(['nvidia-smi', '-i', receipt['job']['gpu_uuid'], '--query-compute-apps=pid,process_name,used_memory,gpu_uuid', '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
listener = subprocess.run(['ss', '-ltnp', '( sport = :9999 )'], capture_output=True, text=True, timeout=10)
checks['original_runner_GPU0_context_absent'] = gpu.returncode == 0 and not any(line.split(',')[0].strip() == str(startup['runner']['pid']) for line in gpu.stdout.splitlines())
checks['original_runner_port9999_listener_absent'] = listener.returncode == 0 and f'pid={startup["runner"]["pid"]},' not in listener.stdout
checks['receipt_bytes_stable_during_audit'] = receipt_path.read_bytes() == raw
health_path = RUN / 'quality96M-first-private-health.jsonl'
health_raw = health_path.read_bytes()
assert health_raw and health_raw.endswith(b'\n'), 'Nonempty complete-line health evidence is required'
health = [json.loads(line) for line in health_raw.splitlines()]
runtime_health_faults, cleanup_health_diagnostics = [], []
for row in health:
    faults = list(row.get('faults', []))
    if row.get('complete') and 'private_actor_timeout' in faults and not any(runtime_counts.values()):
        faults.remove('private_actor_timeout')
        cleanup_health_diagnostics.append(dict(utc=row['utc'], raw_observer_flag='private_actor_timeout', interpretation='All event timestamps classify as postmeasurement intentional cleanup; zero runtime timeouts. Raw health evidence is preserved.'))
    if faults:
        runtime_health_faults.append(dict(utc=row['utc'], faults=faults))
checks['score_blind_health_no_runtime_faults'] = not runtime_health_faults
checks['score_blind_health_no_read_errors'] = not any(row.get('read_error') for row in health)
report = dict(schema='robotron-96M-first-final-independent-audit-v1', started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(), PASS=all(checks.values()), checks=checks, validation_error=validation_error,
    receipt=dict(path=str(receipt_path), sha256=hashlib.sha256(raw).hexdigest(), valid=receipt['valid'], complete=receipt['complete'], phase=receipt['phase']),
    lineage=dict(path=str(lineage_path), sha256=sha(lineage_path)), references=references,
    denominator={key: receipt.get(key, receipt.get('cohort', {}).get(key)) for key in ('started', 'count', 'pending', 'abandoned')},
    admission=dict(start_ts=leg['start_ts'], close_ts=leg['close_ts'], latest_tail_end_unix_s=max(row['end_unix_s'] for row in leg['rows']), completed_tails_after_close=sum(row['end_unix_s'] > leg['close_ts'] for row in leg['rows'])) if leg is not None else None,
    final_statistics={key: receipt.get(key) for key in ('count', 'mean', 'median', 'sd', 'se')} if checks['final_receipt_full_backend_and_lineage_valid'] else None,
    clocks=receipt['clocks'], checkpoint_metadata=receipt['checkpoint_metadata'], numeric_policy=receipt['numeric_policy'], compile_report=receipt['compile_report'], runtime=receipt['runtime'],
    management_crosscheck=dict(analysis_path=str(analysis_path), analysis_sha256=sha(analysis_path), management=management), timeout_classification=dict(cutoff_unix_s=receipt['timeout_snapshot_unix_s'], runtime=runtime_counts, cleanup=cleanup_counts, actor_log_sha256=log_hashes), owned_processes=dict(runner=startup['runner'], actors=startup['actors']), GPU0_compute_observation=gpu.stdout, port9999_observation=listener.stdout,
    score_blind_health=dict(path=str(health_path), sha256=hashlib.sha256(health_raw).hexdigest(), bytes=len(health_raw), rows=len(health), runtime_faults=runtime_health_faults, postcomplete_cleanup_diagnostics=cleanup_health_diagnostics, read_errors=[dict(utc=row['utc'], error=row['read_error']) for row in health if row.get('read_error')], partial_score_fields_inspected=False),
    scope=dict(source_changes=False, model_or_state_writes=False, process_controls=False, GPU_context_created=False, bootstrap_scope='Only minimum100-draw official pair validation; intervals discarded. Root strict guard analyzer owns the10000-draw composite analysis and decision.'))
output = RUN / 'quality96M-first-final-independent-audit.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps(dict(PASS=report['PASS'], path=str(output), sha256=sha(output), statistics=report['final_statistics'], denominator=report['denominator'], validation_error=validation_error), indent=2))
