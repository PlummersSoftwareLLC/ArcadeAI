"""Adopt verified original failure and close the passive observation record."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
R = N.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def replace_bytes(path, raw, expected):
    assert path.read_bytes() == expected
    tmp = path.with_name(path.name + '.invalid-adoption-next')
    with tmp.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fchmod(f.fileno(), 0o664)
        os.fsync(f.fileno())
    assert path.read_bytes() == expected
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    helper = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    h = load('_invalid_adopt_h', helper)
    reader = load('_invalid_adopt_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    read = lambda pin, as_json=True: reader.read_pin(pin, as_json=as_json)
    disposition = h.pin(N / 'original-campaign-invalid-C1-horizon-independent-closeout-original01/independent-invalid-original-campaign-disposition.json')
    assert disposition['sha256'] == '7361fb02997c08e1d6f9bac9f84be5945151e549b8c35a9e23c896c9b0498074'
    report = read(disposition)
    assert report['original_scientific_case_closed'] is True and report['quality_qualified'] is False
    archive = N / 'canonical-invalid-original-campaign-adoption-original01'
    archive.mkdir(mode=0o700)
    watch = N / 'original-C1-interval-watch3600-original03'
    receipt_pin = h.pin(watch / 'watch-receipt.json')
    receipt = read(receipt_pin)
    assert receipt['observation_count'] == len(receipt['observations']) == 61 and receipt['elapsed_s'] >= 3600
    previous = None
    first = None
    max_age = 0
    for pin in receipt['observations']:
        o = read(pin)
        status, starts, loaded, job, sample = [read(o[k], k != 'measurement_starts_prefix') for k in
            ('status_snapshot', 'measurement_starts_prefix', 'loaded_policy', 'original_job', 'main_sample')]
        starts = [json.loads(line) for line in starts.splitlines()]
        policy = loaded['policy']
        assert policy['checkpoint_sha256'] == job['checkpoint']['sha256'] == 'df4314b05aceddeec263e598690fe803e32985497a0e26b38f36162452291bb4'
        by_slot = {}
        for row in starts:
            by_slot.setdefault(row['client_slot'], row)
        assert sorted(by_slot) == list(range(4096, 4128))
        assert len(o['identities']) == 32
        for identity in o['identities']:
            slot = identity['slot']
            row = by_slot[slot]
            cert = row['context']['startup_certificate']
            body = {k: v for k, v in cert.items() if k != 'identifier'}
            assert hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() == cert['identifier'] == identity['certificate_identifier']
            assert cert['policy'] == policy and cert['slot'] == slot
            assert cert['session'] == job['sessions'][str(slot)] and cert['connection'] == job['connections'][str(slot)]
            assert row['journal_game_id'] == identity['journal_game_id']
            live = status['slots'][str(slot)]
            assert live['pid'] == identity['pid'] and live['birth'] == identity['birth'] and live['sequence'] == identity['sequence']
            assert live['prefix_verified'] is True and live['error'] is None and live['actual_exit'] is None
            if previous:
                old = next(v for v in previous['identities'] if v['slot'] == slot)
                assert all(identity[k] == old[k] for k in ('pid', 'birth', 'certificate_identifier', 'journal_game_id'))
                assert identity['sequence'] > old['sequence'] >= 1200
        transport = sample['transport']
        raw_api = base64.b64decode(transport['raw_API']['base64'])
        assert hashlib.sha256(raw_api).hexdigest() == transport['raw_API']['sha256']
        assert json.loads(raw_api)['client_count'] == 192
        main = o['main']
        assert main['client_count'] == 192 and main['held_inputs'] == 197 and main['autosave_age_s'] <= 360
        assert o['cohort']['count'] == 18 and o['cohort']['started'] == 45 and o['cohort']['pending'] == 27 and o['cohort']['abandoned'] == 0
        max_age = max(max_age, main['autosave_age_s'])
        if previous:
            assert o['main_sample_index'] > previous['main_sample_index']
            assert main['learner_frame_count'] > previous['main']['learner_frame_count']
            assert main['training_steps'] > previous['main']['training_steps']
        first = first or o
        previous = o
    passive_close = dict(schema='robotron-original-C1-passive3600-terminal-independent-readback-v1',
                         created_unix_s=time.time(), intent=h.pin(watch / 'watch-intent.json'), receipt=receipt_pin,
                         actual_tool_session=51746, actual_tool_terminal_exit=0, actual_original_birth_absent=not Path('/proc/1817911').exists(),
                         observations_checked=61, elapsed_s=receipt['elapsed_s'],
                         all61_immutable_observation_status_start_policy_job_and_raw_main_pins_checked=True,
                         original_first_start_certificate_identifiers_recomputed=1952,
                         all_observed_original32_identities_and_advancing_sequences_verified=True,
                         all_observed_main192_held197_autosaves_healthy=True,
                         raw_main_first=first['main_sample_index'], raw_main_last=previous['main_sample_index'],
                         maximum_observed_autosave_age_s=max_age, quality_qualified=False,
                         scientific_case_closed_by_this_watch=False, classification='verified_wait')
    passive_pin = h.put(watch / 'independent-original3600s-watch-terminal-readback.json', passive_close)
    mon = R / 'LR125-after-protected3045-firstSave-original01-preparation-20261025/postcapture-current-main-readonly-monitor-v2.py'
    command = ['/usr/bin/python3.12', '-I', '-B', str(mon)]
    process = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    main = json.loads(process.stdout)
    h.put(archive / 'current-main-readback.json', main)
    state_path = R.parent / 'state.json'
    preimage = state_path.read_bytes()
    state = json.loads(preimage)
    original_state = copy.deepcopy(state)
    g = state['optimization_goal']
    prior_pin = g['current_recovery_index']
    recovery = copy.deepcopy(read(prior_pin))
    h.put(archive / 'canonical-state-before-invalid-disposition.raw.json', json.loads(preimage))
    # Archive exact bytes too; JSON serialization above is intentionally just a readable copy.
    exact = archive / 'canonical-state-before-invalid-disposition.exact.json'
    with exact.open('xb') as f:
        f.write(preimage);f.flush();os.fchmod(f.fileno(), 0o444);os.fsync(f.fileno())
    stage = 'PROTECTED3045_RETAINED_LATER3262_ORIGINAL_C1_INVALID_CLOSED'
    phase = 'FAILED_ORIGINAL_PRESERVED_NEXT_CONCURRENCY64_ENGINEERING_PREPARATION'
    next_action = ('Original sequence33348 exit1, display96370 exit0, passive51746 exit0 and both C1 scopes are closed. '
                   'Do not poll/relaunch them or retry later3262 confirmation. Keep protected3045 and live main192/197 unchanged. '
                   'Finish isolated A32/B64 source/interface/refusal guards and CPU pre-lease initializer proof; then prepare '
                   'one prospective protected-policy ABBA active600 evaluator-count engineering experiment with common12CPU/24GiB, '
                   'batch16 and complete startup/main/runtime review. No native jobs are ready yet; no quality/performance gain claimed.')
    updates = dict(status='active', stage=stage, phase=phase, current_phase=phase,
                   current_campaign=str(N), current_campaign_leg='C1', current_campaign_outcome='invalid; R2/C2 not run',
                   current_campaign_phase=phase, current_campaign_final_disposition=disposition,
                   source_freeze=False, full_source_freeze=False, scientific_job_running=False,
                   all_current_original_scientific_handles_terminal=True, actual_running_wait=None,
                   current_passive_watch=None, last_completed_passive_watch=passive_pin,
                   active_quality_job=None, current_active_quality_job=None, current_scientific_study=dict(
                       directory=str(N), state='invalid_closed', disposition=disposition, quality_qualified=False,
                       failed_original_preserved=True, retry_allowed=False),
                   current_fixed_reference_pool=None, next_fixed_reference_score_pool=None,
                   current_main_readback=main, quality_qualified=False,
                   last_closed_original_scientific_campaign=disposition,
                   latest_goal_turn_classification='progress', previous_goal_turn_classification=g.get('latest_goal_turn_classification'),
                   classification_basis='Independently closed original invalid C1 scopes and all32 actors, preserved no-retry failure, closed original61-observation passive watch, verified main192/197 and corrected canonical stale-running aliases. Isolated concurrency source preparation remains incomplete.',
                   latest_progress='C1 invalid at fixed admission horizon:18 complete,45 starts,27 abandoned,19 missing second starts. Protected3045 retained. Native/worker exit1, all32 MAME exit0, owned scopes released; no R2/C2 launches. Main192/197 healthy.',
                   next_action=next_action, last_updated_unix_s=time.time())
    g.update(updates)
    recovery.update({k:v for k,v in updates.items() if k not in ('current_campaign','current_phase')})
    recovery.update(previous_recovery_index=prior_pin, canonical_preimage=h.pin(exact), created_unix_s=time.time(),
                    goal_status='active', all_current_original_handles_terminal=True,
                    current_passive_live_readback=None, current_closed_campaign_disposition=disposition,
                    current_concurrency_source_preparation=h.pin(N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02/source-derivation-INCOMPLETE.json'),
                    current_concurrency_CPU_fixtures=h.pin(N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02/CPU-fixture-index.json'))
    recovery_path = R / 'current-optimization-recovery-index-20261026-later3262-C1-invalid-closed-capacity64-preparation-original01.json'
    recovery_pin = h.put(recovery_path, recovery)
    g['current_recovery_index'] = g['current_optimization_recovery_index'] = recovery_pin
    assert {k:v for k,v in state.items() if k != 'optimization_goal'} == {k:v for k,v in original_state.items() if k != 'optimization_goal'}
    raw = (json.dumps(state, separators=(',', ':'), allow_nan=False) + '\n').encode()
    assert len(raw) < 1 << 20
    replace_bytes(state_path, raw, preimage)
    adoption = h.put(archive / 'canonical-invalid-original-disposition-adoption.json', dict(
        previous_exact_state=h.pin(exact), recovery=recovery_pin, disposition=disposition,
        state_after=h.pin(state_path), only_optimization_goal_section_changed=True,
        state_size_bytes=len(raw), classification='progress', created_unix_s=time.time()))
    doc = G / 'DELL_SETUP.md'
    old = doc.read_bytes()
    doc_pre = archive / 'DELL_SETUP-before-invalid-disposition.exact.md'
    with doc_pre.open('xb') as f:
        f.write(old);f.flush();os.fchmod(f.fileno(), 0o444);os.fsync(f.fileno())
    separator = b'Earlier five-minute observation, retained for history:\n'
    assert old.count(separator) == 1
    suffix = old.split(separator, 1)[1]
    header = f'''# Dell GB300 Robotron setup

Current optimization recovery: [Later3262 C1 invalid and closed; protected3045 retained](logs/managed-learning-20261015/run-26/{recovery_path.name}). Goal active; classification: progress. Exact receipts, history, identities and next actions are in the recovery index.

The original protected3045-vs-later3262 study is CLOSED INVALID. C1 reached its fixed21540s admission horizon with18 complete/45 started/27 abandoned and19 missing second starts. That selected subset is not a candidate-quality result. Original sequence33348 exited1; R2/C2 were never prepared or launched. No retries, pooling, deadline extension or promotion. The protected3045 b23152ec policy and prior protected results remain preserved; later3262 df4314b0 remains unqualified.

Independent failure closeout7361fb02 verifies native and dedicated main-health worker actual exits1, all6 archived descriptors per scope, argv/resources/input pins, original births and both unit/cgroup releases. All32 original MAME children exited0; journal/actor artifacts are sealed, threads closed, the permanent GPU coordinator was preserved and the original lease released. The isolated study source freeze is released; this does not authorize changing the live trainer. Fresh R1 passed all64/32slots/full tails with mean11,227,660.15625 and median11,681,062.5, but no fresh R1+R2 reference pool exists.

Display96370 exited0 and already projects the campaign failure. Passive51746/PID1817911 exited0 after61 observations/3601.543s; independent closure checks all61 immutable observations/raw-main samples and1952 certificates, advancing actor and learner clocks and192/197/autosave health. Never poll/relaunch these terminal handles, the old33348 sequence or earlier42588/16061/89405/42139/68001/4419/driver38418. No private scientific job remains running.

Main trainer PID3615927/birth78856521 remains healthy on physicalGPU1 GB300 with192 actors/197 held inputs, LR6.25e-6 and normal300s autosaves. Current readback: learner frames{main['learner_frame_count']}, training steps{main['training_steps']}, fleet{main['fleet_fps']:.1f}FPS, save age{main['autosave_age_s']:.1f}s. These are descriptive counters, not verified learning-speed or throughput gains. PrivateGPU0 is RTX PRO2000 Blackwell.

Next work: complete isolated future-concurrency64 source/interface/refusal guards and CPU pre-lease initializer proof, then prepare a new original protected-policy ABBA active600 engineering comparison: A32x2 versusB64x1,64 games, common12CPU/24GiB, batch16. Existing source-derivation018f8012 and CPU-fixture indexe0be05ac are INCOMPLETE/UNSELECTED; no native launch is ready. Actual64 startup, main/runtime review and separately fixed A/B gates remain required. FPS alone cannot establish full-cohort wall-time gain. Prior failed source-generation artifacts remain preserved.

Future request-timing recorder9bd14777 passed13 CPU guards in each actual3.12/3.14.8 free-threaded runtime. Live integration/parity/overhead remain unselected. Raw current ROM reserves were not observable from the old life estimate journal; future reserve diagnostics must retain confirmed-reset completion rules. Conditional publisherfadf3e03 remains guarded and unused. Promotion always requires four valid full cohorts and separate C1/C2>=1.05 fixed fresh R1+R2 mean with median preserved and all64/full-tail/all-slot/runtime checks.

'''
    replace_bytes(doc, header.encode() + separator + suffix, old)
    h.put(archive / 'documentation-invalid-original-disposition-adoption.json', dict(
        previous_document=h.pin(doc_pre), document_after=h.pin(doc), recovery=recovery_pin,
        historical_suffix_preserved_verbatim=True, canonical_adoption=adoption, created_unix_s=time.time()))
    print(json.dumps(dict(recovery=recovery_pin, adoption=adoption, state_bytes=len(raw), passive_closeout=passive_pin)))


if __name__ == '__main__':
    main()
