"""Read original R1 receipts and C1 passive observations without scientific reruns."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).parent


def module(path, name, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    return value


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def execute(output):
    assert output.parent == N and output.is_absolute() and output.resolve() == output and not output.exists()
    output.mkdir(mode=0o700)
    h = module(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
               '_closed_h', '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = module(G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                    '_closed_reader', 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    rt = module(G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
                '_closed_rt', '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
    q = module(N / 'isolated-source-family-original01/read_quality32_quota64_selected_original01_v2.py',
               '_closed_q', 'cc3da91fcf15aa16baa445d88f3501811ea5fdc08e9f87f422be9f654275db2d')
    artifacts = []

    def read(pin, as_json=True):
        value = reader.read_pin(pin, as_json=as_json)
        artifacts.append(pin)
        return value

    def pinned(path):
        pin = h.pin(path)
        return pin, read(pin)

    root = N / '01-reference'
    display_pin, display = pinned(root / 'original-closed-display-summary.json')
    review_pin = display['original_independent_review']
    review = read(review_pin)
    job_pin, job = pinned(root / 'job.json')
    native_pin, native = pinned(root / 'diagnostic-output-original01/result.json')
    cfg_pin, cfg = pinned(root / 'controller-config.json')
    acceptance_pin, acceptance = pinned(root / 'precommitted-acceptance-scope.json')
    q.validate_scope(job, job_pin, acceptance, cfg)
    policy, cohort = q.validate_runtime_result(native, job)
    assert review['valid'] is review['full_game_score_verified'] is True
    assert review['quality_qualified'] is review['promotion'] is False
    assert review['quality_leg'] == job['quality_leg'] == 'R1'
    assert review['original_native_job'] == job_pin and review['original_result'] == native_pin
    assert review['policy'] == policy and review['original_acceptance'] == acceptance_pin
    assert review['minimum_quality_complete_games'] == 50 and review['expected_selected_games'] == 64
    assert review['all32_actual_MAME_exits'] == 0 and review['actual_descriptor_exits'] == [0] * 6
    for key in ('all_admitted_games_retained', 'all6_original_descriptors_verified',
                'exact_owned_births_unit_timer_cgroup_absent', 'private_GPU_ports_and_coordinator_released',
                'original_outputs_sealed_after_writer_exit'):
        assert review[key] is True
    assert review['main_health_case_roles'] == ['R1']
    assert review['main_observer_independently_verified']['own_CPU2_actual_scope_verified'] is True
    scopes = []
    for role, directory, config_name, result_name, cpu_runtime in [
        ('native', root / 'execution-original01', root / 'controller-config.json', root / 'controller-original-result.json', None),
        ('reviewer', root / 'independent-review-execution-original01', root / 'independent-review-controller-config.json', root / 'independent-review-controller-original-result.json', 1980),
        ('worker', root / 'diagnostic-output-original01/main-health-scope/execution-original01', root / 'diagnostic-output-original01/main-health-scope/controller-config.json', None, 22260),
    ]:
        owner_pin, owner = pinned(directory / 'root-original-identity.json')
        closure_pin, closure = pinned(directory / 'root-original-result-and-owned-release.json')
        config_pin, config = pinned(config_name)
        fields = rt.archived_closure(closure, owner, read, exit_zero=True)
        if result_name is not None:
            controller_pin, controller = pinned(result_name)
            assert controller['actual_exit'] == 0 and controller['original_attempt'] == 1 and controller['no_retry'] is True
            assert controller['closure'] == closure_pin
        if role == 'native':
            q.validate_native_fields(fields, config, owner, rt.duration_seconds)
            assert review['original_owner'] == owner_pin
        else:
            assert rt.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
            assert fields['MemoryMax'] == str(4 << 30) and fields['MemorySwapMax'] == '0'
            assert rt.duration_seconds(fields['RuntimeMaxUSec']) == cpu_runtime and fields['TasksMax'] == '128'
            assert rt.duration_seconds(fields['TimeoutStopUSec']) == 5 and fields['SendSIGKILL'] == fields['Restart'] == 'no'
            assert ' '.join(config['argv']) + ' ; ignore_errors=no ;' in fields['ExecStart']
        for pin in config['pins']:
            current = h.pin(pin['path'])
            assert all(current[k] == pin[k] for k in ('path', 'sha256', 'bytes'))
            assert all(current['identity'][k] == v for k, v in pin['identity'].items())
        assert birth(owner['pid']) != owner['starttime_ticks']
        current_units = []
        for unit in (owner['unit'], owner['timer']):
            proc = subprocess.run(['systemctl', '--user', 'show', unit], capture_output=True, text=True, timeout=5)
            assert proc.returncode == 0
            values = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
            assert values['Id'] == unit and values['LoadState'] == 'not-found'
            if unit == owner['unit']:
                assert values['MainPID'] == '0'
            current_units.append(dict(argv=proc.args, exit=proc.returncode, stdout=proc.stdout, stderr=proc.stderr))
        cgroup = Path('/sys/fs/cgroup' + fields['ControlGroup'])
        assert not cgroup.exists() or not (cgroup / 'cgroup.procs').read_text().strip()
        scopes.append(dict(role=role, owner=owner_pin, closure=closure_pin, config=config_pin,
                           all6_archived_descriptors_and_resources_argv_verified=True,
                           config_pin_count=len(config['pins']), all_declared_config_pin_fields_verified=True,
                           original_birth_absent=True, current_units=current_units))
    for slot, actor in native['original_slots'].items():
        assert birth(actor['pid']) != actor['birth'] and actor['actual_exit'] == 0
    rows = cohort['rows']
    journal = {name: read(pin, False) for name, pin in native['journal'].items()}
    for name, pin in native['journal'].items():
        assert pin['sha256'] == review['original_games']['original_payload_sha256'][name]
    games = {r['journal_game_id']: r for r in map(json.loads, journal['games.jsonl'].splitlines())}
    starts = {r['journal_game_id']: r for r in map(json.loads, journal['measurement_starts.jsonl'].splitlines())}
    for row in rows:
        assert games[row['journal_game_id']] == row and row['journal_game_id'] in starts
    scores = [r['score'] for r in rows]
    stats = dict(count=len(scores), score_sum=sum(scores), mean=statistics.mean(scores), median=statistics.median(scores))
    assert set(review['original_games']['admitted_ids']) == set(cohort['started_ids']) == {r['journal_game_id'] for r in rows}
    assert len(scores) == len(set(cohort['started_ids'])) == 64 and cohort['pending'] == cohort['abandoned'] == 0
    assert cohort['slot_admitted_counts'] == {str(s): 2 for s in range(4096, 4128)}
    assert all(stats[k] == review['original_games']['statistics'][k] for k in stats)
    assert all(stats[k] == cohort[k] == display['cohort'][k] for k in ('count', 'mean', 'median'))
    w = N / 'original-R1-interval-watch3600-original07'
    intent_pin, intent = pinned(w / 'watch-intent.json')
    receipt_pin, receipt = pinned(w / 'watch-receipt.json')
    assert birth(intent['pid']) != intent['birth'] and receipt['observation_count'] == len(receipt['observations']) == 61
    assert 3600 <= receipt['elapsed_s'] < 3660 and receipt['native_terminal_or_complete_transition_observed'] is False
    observations = [read(pin) for pin in receipt['observations']]
    for obs in observations:
        status = read(obs['status_snapshot'])
        read(obs['measurement_starts_prefix'], False)
        read(obs['loaded_policy']); read(obs['original_job']); read(obs['main_sample'])
        assert len(obs['identities']) == 32 and obs['main']['client_count'] == 192 and obs['main']['held_inputs'] == 197
        assert obs['all32_actual_MAME_births_and_argv_live'] and obs['all32_certificate_identifiers_recomputed']
        assert obs['cohort']['abandoned'] == 0 and status['controller']['cohort']['count'] == obs['cohort']['count']
    for a, b in zip(observations, observations[1:]):
        assert a['main_sample_index'] < b['main_sample_index']
        for x, y in zip(a['identities'], b['identities']):
            assert all(x[k] == y[k] for k in ('slot', 'pid', 'birth', 'certificate_identifier', 'journal_game_id'))
            assert x['sequence'] < y['sequence']
    watch_close = h.put(w / 'independent-original3600s-watch-terminal-readback.json', dict(
        source=h.pin(__file__), intent=intent_pin, receipt=receipt_pin, actual_tool_session=89405,
        actual_tool_terminal_exit=0, original_birth_absent=True, all61_observation_pins_and_dependencies_checked=True,
        original32_identities_and_advances_checked=True, raw_main_first=observations[0]['main_sample_index'],
        raw_main_last=observations[-1]['main_sample_index'], quality_qualified=False, created_unix_s=time.time()))
    c = N / 'original-C1-interval-watch3600-original01'
    c_intent_pin, c_intent = pinned(c / 'watch-intent.json')
    assert birth(c_intent['pid']) == c_intent['birth']
    c_observations = [pinned(c / f'{i:02d}/observation.json') for i in (0, 1)]
    a, b = [v for p, v in c_observations]
    assert b['main_sample_index'] > a['main_sample_index']
    for x, y in zip(a['identities'], b['identities']):
        assert all(x[k] == y[k] for k in ('slot', 'pid', 'birth', 'certificate_identifier', 'journal_game_id'))
        assert y['sequence'] > x['sequence']
    actual_argv = Path('/proc', str(c_intent['pid']), 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
    assert actual_argv[3] == c_intent['source']['path'] and '--observe' in actual_argv
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-original-R1-closed-C1-live-independent-readback-v1', source=h.pin(__file__),
                  original_R1_review=review_pin, original_R1_stats=stats, original_R1_all64_fulltail_valid=True,
                  original_R1_native_worker_reviewer_scopes=scopes, original_R1_all32_births_absent=True,
                  original_R1_raw_journal_hashes_and_selected_game_rows_verified=True,
                  original_R1_scientific_review_not_rerun=True,
                  original_R1_review_artifact_count=len(review['artifacts']),
                  limits=['Original scientific review is consumed, not repeated. Its full raw wire/ROM/startup/main replay remains bound by the immutable review; all its artifact pins will also be checked by the original final campaign assessor.',
                          'R1 alone cannot establish the fixed R1+R2 mean. C1 is incomplete and no candidate gate or promotion is claimed.'],
                  closed_R1_watch=watch_close, C1_watch=dict(tool_session_id=42588, pid=c_intent['pid'], birth=c_intent['birth'],
                  intent=c_intent_pin, source=c_intent['source'], output=str(c), actual_argv=actual_argv,
                  actually_live_now=True, initial_observations=[p for p, v in c_observations],
                  all32_actual_identities_certificates_prefix1200_and_advances_verified=True,
                  planned_duration_s=3600, interval_s=60, completed=False),
                  C1_initial_partial_cohort=b['cohort'], main=b['main'], artifacts=artifacts,
                  quality_qualified=False, candidate_pool_used=False, main_runtime_changed=False,
                  scientific_attempts_started=0, classification='progress', created_unix_s=time.time())
    result = h.put(output / 'readback.json', report)
    print(json.dumps(dict(report=result, R1=stats, closed_R1_watch=watch_close,
                          C1_watch=report['C1_watch'], C1_partial=b['cohort'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.inspect:
        assert args.output is not None
        execute(args.output)
    else:
        print('PLAN_ONLY')
