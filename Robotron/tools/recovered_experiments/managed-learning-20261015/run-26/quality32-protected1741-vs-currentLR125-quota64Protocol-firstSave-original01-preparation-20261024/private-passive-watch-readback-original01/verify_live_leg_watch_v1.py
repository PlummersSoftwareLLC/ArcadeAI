"""Private passive readback only; never schedules, signals, qualifies or publishes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import urllib.request

sys.dont_write_bytecode = True
G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HELPER_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
LEG_FOLDERS = {'R1': '01-reference', 'C1': '02-candidate', 'R2': '03-reference', 'C2': '04-candidate'}


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def review(a, h, out):
    job_pin = h.pin(a.job)
    assert job_pin['sha256'] == a.job_sha256
    job = json.loads(h.checked(job_pin).read_bytes())
    assert job['may_control_or_schedule'] is False and job['duration_s'] == 300 and job['poll_s'] == 30
    assert LEG_FOLDERS[job['quality_leg']] == job['leg_folder']
    root = Path(job['campaign']) / job['leg_folder']
    native = root / 'diagnostic-output-original01'
    watch = Path(job['output'])
    outcome_pin = h.pin(watch / 'watch-outcome.json')
    assert outcome_pin['sha256'] == a.outcome_sha256

    def read(pin):
        return json.loads(h.checked(pin).read_bytes())

    def archive(path, raw):
        with path.open('xb') as f:
            f.write(raw)
            f.flush()
            os.fchmod(f.fileno(), 0o444)
            os.fsync(f.fileno())
        return h.pin(path)

    for pin in job['inputs']:
        h.checked(pin)
    outcome = read(outcome_pin)
    assert outcome['status'] == 'BOUNDED_PASSIVE_WATCH_COMPLETE' and outcome['error'] is None
    intent = read(outcome['intent'])
    assert birth(intent['pid']) != intent['birth']
    records = [read(pin) for pin in outcome['observations']]
    assert len(records) == 11 and 300 <= records[-1]['elapsed_s'] <= 310
    native_owner = next(p for p in job['original_parents'] if p['role'].endswith('native'))
    samples = []
    for i, record in enumerate(records):
        assert record['quality_leg'] == job['quality_leg']
        assert all(p['birth'] == p['observed_birth'] for p in record['original_parents'])
        api = read(record['API_raw'])
        assert api['host_pipeline']['learning_exposure'] == record['actual_main_learning_exposure']
        sample_pin = h.pin(watch / f'native-status-{i:03d}.json')
        status = read(sample_pin)
        assert status['original_pid'] == native_owner['pid'] and status['original_birth'] == native_owner['birth']
        cohort = status['controller']['cohort']
        assert cohort['valid'] is True and cohort['abandoned'] == 0
        assert cohort['count'] + cohort['pending'] == cohort['started'] <= 64
        assert len(cohort['started_ids']) == len(set(cohort['started_ids'])) == cohort['started']
        assert len(status['slots']) == 32
        if i:
            assert record['raw_health_index'] > records[i - 1]['raw_health_index']
            previous = samples[-1]['status']
            assert set(previous['controller']['cohort']['started_ids']).issubset(cohort['started_ids'])
            assert cohort['count'] >= previous['controller']['cohort']['count']
            assert status['controller']['start_ts'] == previous['controller']['start_ts']
            assert status['controller']['close_ts'] == previous['controller']['close_ts']
            for slot, row in status['slots'].items():
                old = previous['slots'][slot]
                assert row['pid'] == old['pid'] and row['birth'] == old['birth']
                assert row['sequence'] > old['sequence']
        samples.append(dict(pin=sample_pin, status=status))
    parents = []
    for parent in job['original_parents']:
        assert birth(parent['pid']) == parent['birth']
        parents.append(dict(**parent, observed_birth=birth(parent['pid'])))
    raw = (native / 'status.json').read_bytes()
    status = json.loads(raw)
    age = time.time() - status['observed_unix_s']
    assert 0 <= age <= 6
    current_pin = archive(out / 'current-native-status.raw.json', raw)
    cohort = status['controller']['cohort']
    assert cohort['valid'] is True and cohort['abandoned'] == 0
    assert cohort['count'] + cohort['pending'] == cohort['started'] <= 64
    assert set(samples[-1]['status']['controller']['cohort']['started_ids']).issubset(cohort['started_ids'])
    actors = []
    for slot, row in status['slots'].items():
        assert birth(row['pid']) == row['birth'] and row['error'] is None and row['ledger']['rejected'] == 0
        actor = read(h.pin(native / f'actors/{slot}/original-actor.json'))
        argv = Path('/proc', str(row['pid']), 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
        assert argv == actor['argv'] and row['pid'] == actor['pid'] and row['birth'] == actor['starttime_ticks']
        actors.append(dict(slot=int(slot), pid=row['pid'], birth=row['birth'], argv_verified=True,
                           wire_sequence_delta=row['sequence'] - samples[0]['status']['slots'][slot]['sequence']))
    native_job_pin = h.pin(root / 'job.json')
    native_job = read(native_job_pin)
    assert len(native_job['inputs']) == 244
    for pin in native_job['inputs']:
        h.checked(pin)
    monitor = h.checked(job['main_monitor'])
    main = json.loads(subprocess.check_output(['/usr/bin/python3.12', '-I', '-B', monitor], text=True, timeout=25))
    main_pin = h.put(out / 'current-main.json', main)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        raw = response.read(1048577)
    assert len(raw) <= 1048576
    api = json.loads(raw)
    quality = api['quality_campaign']
    expected_index = list(LEG_FOLDERS).index(job['quality_leg']) + 1
    assert quality['current_leg'] == expected_index and quality['state'] == 'running' and quality['stale'] is False
    leg = quality['legs'][expected_index - 1]
    assert leg['state'] == 'running'
    if leg['count'] == 0:
        assert leg['mean'] is None
    api_pin = archive(out / 'current-dashboard-API.raw.json', raw)
    report = dict(schema='robotron-private-live-leg-watch-readback-v1', created_unix_s=time.time(),
                  quality_leg=job['quality_leg'], source=h.pin(__file__), argv=sys.argv,
                  caller_supplied_original_tool_session=a.original_tool_session,
                  caller_supplied_original_tool_exit=a.original_tool_exit,
                  watch_job=job_pin, watch_outcome=outcome_pin, original_passive_process_absent=True,
                  observations_verified=11, native_status_observations=[s['pin'] for s in samples],
                  span_s=records[-1]['elapsed_s'], raw_health_index_span=[records[0]['raw_health_index'], records[-1]['raw_health_index']],
                  original_parents_live=parents, original32_actor_births_argv_live=actors,
                  native_job=native_job_pin, native_input_holds_verified=244,
                  current_native_status=current_pin, current_native_status_age_at_capture_s=age,
                  producer_cohort={k: cohort[k] for k in ('count', 'started', 'pending', 'abandoned', 'mean', 'median', 'valid')},
                  current_main=main_pin,
                  main_FPS_range=[min(r['current_main']['fleet_fps'] for r in records), max(r['current_main']['fleet_fps'] for r in records)],
                  autosave_age_samples_s=[r['current_main']['autosave_age_s'] for r in records],
                  optimizer_available_flags=[r['actual_main_learning_exposure']['optimizer']['available'] for r in records],
                  optimizer_unclassified_started=[r['actual_main_learning_exposure']['optimizer']['unclassified_started_total'] for r in records],
                  dashboard_API=api_pin, dashboard_quality_campaign=quality,
                  limitations=['Private snapshot/process/input readback only. Original all64 game/startup/wire/life/raw-health/runtime reviews and separate confirmation gates remain mandatory.',
                               'Started membership may grow prospectively to64; later completed games do not replace earlier admitted games.',
                               'Optimizer availability may be false during an in-flight attempt. Snapshot flags are retained; no parameter movement or useful-throughput gain is inferred.'],
                  scientific_sources_recipe_or_controls_changed=False, full_game_score_verified=False,
                  quality_qualified=False, policy_promoted=False, learning_speed_gain_verified=False,
                  throughput_gain_verified=False)
    assert 'torch' not in sys.modules
    pin = h.put(out / 'readback.json', report)
    print(json.dumps(dict(readback=pin, quality_leg=job['quality_leg'], cohort=report['producer_cohort'],
                          main_fps=main['fleet_fps'])), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--readback', action='store_true')
    p.add_argument('--job')
    p.add_argument('--job-sha256')
    p.add_argument('--source-sha256')
    p.add_argument('--outcome-sha256')
    p.add_argument('--original-tool-session', type=int)
    p.add_argument('--original-tool-exit', type=int)
    a = p.parse_args()
    if not a.readback:
        print('PLAN_ONLY: no experiment reads, scheduling, control or qualification')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == a.source_sha256
    assert a.original_tool_exit == 0 and a.original_tool_session > 0
    helper = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == HELPER_SHA
    spec = importlib.util.spec_from_file_location('_private_watch_readback_helpers', helper)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    out = Path(a.job).resolve(strict=True).parent / 'independent-live-watch-readback-original01'
    out.mkdir(mode=0o700)
    try:
        review(a, h, out)
    except Exception as error:
        pin = h.put(out / 'passive-readback-failure.json', dict(
            classification='PASSIVE_READBACK_FAILURE_NOT_A_NATIVE_OUTCOME', error=repr(error),
            traceback=traceback.format_exc(), source=h.pin(__file__), argv=sys.argv,
            original_handle_outcome_inferred=False, created_unix_s=time.time()))
        print(json.dumps(dict(failure=pin)), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
