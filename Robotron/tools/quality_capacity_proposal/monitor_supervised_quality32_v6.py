"""Read-only root inspection of one prospectively registered supervised study.

No launch, signal, repair, retry, quality decision or policy publication. A root
job is created only after the actual original native/outer births are captured.
All accepted main censuses are rejoined to original raw API wires. Current main
recovery is provisional until the original observer also publishes its witness.
The unchanged scientific observer/reviewer retain all qualification authority.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
H = G/'tools/quality_capacity_proposal'
R = G/'logs/managed-learning-20261015/run-26'
SOURCES = {
    'observer': (H/'quality32_runtime_guard_v9.py', '14991fc668c950b8240059c8a128e0e34bd250d450397666b1f3c52d69c22c58'),
    'supervision': (H/'supervised_main_fleet_v2.py', '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'),
    'joins': (H/'supervised_main_observations_v2.py', '246b521be591bb35d995d0af29874482d039a0a549b144f125d978c66515ea7a'),
    'reviewer': (H/'review_closed_quality32_v9.py', '60f4c9ab189a1fe0a8ae3a2c7e854991e07e2f7aede88301458ce5913b29800a'),
    'wire': (G/'tools/eval_capacity_proposal/raw_api_witness_v1.py', '9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0'),
    'runtime': (G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py', '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'),
    'control': (H/'control_quality32_review_v1.py', '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'),
    'window': (R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py', 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reader_module():
    path = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'Exact reader changed')
    spec = importlib.util.spec_from_file_location('_root_supervised_monitor_reader', path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def accepted_prefix(paths, main, policy, read, modules, state=None, samples=None, wire_paths=None, census_paths=None):
    """Extend an accepted prefix; no mutable actor rebinding or stored-state trust."""
    supervision, joins, wire = (modules[key] for key in ('supervision', 'joins', 'wire'))
    samples = [] if samples is None else list(samples)
    wire_paths = set() if wire_paths is None else set(wire_paths)
    census_paths = set() if census_paths is None else set(census_paths)
    for pin in paths:
        sample = read(pin)
        require(sample.get('supervised_main_fleet_verified') is True
                and 'original192_actors_verified' not in sample, 'Explicit supervised observation required')
        require(sample['API_wire']['path'] not in wire_paths and sample['main_fleet_snapshot']['path'] not in census_paths,
                'Original raw API or census was reused')
        wire_paths.add(sample['API_wire']['path'])
        census_paths.add(sample['main_fleet_snapshot']['path'])
        api = wire.rejoin_witness(sample, lambda entry: read(entry, False))
        sample = dict(sample, API=api)
        _, state = joins.joined_census(policy, read(sample['main_fleet_snapshot']), sample, state, supervision)
        require(sample['main_fleet_state_sha256'] == joins.checksum(state), 'Published main state differs from replay')
        samples.append(sample)
    return state, samples, wire_paths, census_paths


def validate_prefix_exposure(main, samples, runtime, window):
    """Check all original exposure/health predicates for the sampled prefix only."""
    require(len(samples) >= 2, 'Two original main observations are required')
    manifest = dict(schema='robotron-main192-pilot-observations-v1', status='PASS', configuration_changed=False,
        main_owner=main['owner'], accounting_policy='single_inflight_optimizer_v1', rejected_observations=[])
    # The process state machine was already replayed against original counts.
    # This internal view reuses only the unchanged non-capacity predicates and
    # never becomes a published scientific observation or a closed-study claim.
    views = [dict(sample, original192_actors_verified=True, API=dict(sample['API'], client_count=192)) for sample in samples]
    runtime.validate_main_samples(main, manifest, views, samples[0]['monotonic_s'], samples[-1]['monotonic_s'], window.healthy)


def validate_current_progress(api, previous, elapsed_s, runtime):
    """Current health is not allowed to hide regressed/restarted learner counters."""
    require(all(type(api[key]) is int and api[key] >= previous[key] for key in
                ('frame_count', 'learner_frame_count', 'optimized_samples', 'training_steps')), 'Current main work clocks regressed')
    current = api['host_pipeline']['learning_exposure']
    old = previous['host_pipeline']['learning_exposure']
    for name in ('optimizer', 'replay'):
        require(current[name].get('enabled') is True and all(current[name][key] == old[name][key]
                    and type(current[name][key]) is int
                    for key in ('process_id', 'instance_monotonic_ns', 'epoch')), 'Current learner exposure identity changed')
    runtime.inspect_optimizer_observation(current['optimizer'])
    for bucket in ('total', 'since_epoch'):
        require(all(current['optimizer'][bucket][key] >= old['optimizer'][bucket][key]
                    for key in ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')),
                'Current optimizer outcome counters regressed')
    accepted = current['replay']['accepted_learner_total']
    require(current['replay']['available'] is True and type(accepted) is int
            and accepted >= old['replay']['accepted_learner_total'], 'Current replay accepted clock regressed')
    if elapsed_s >= 60:
        require(api['learner_frame_count'] > previous['learner_frame_count']
                and accepted > old['replay']['accepted_learner_total']
                and current['optimizer']['total']['applied'] > old['optimizer']['total']['applied'],
                'Main learner did not advance after the scientific interval closed')


def sample_files(directory):
    paths = sorted(directory.glob('*.json'))
    require([path.name for path in paths] == [f'{index:04d}.json' for index in range(len(paths))],
            'Missing or unexpected original main observation sequence')
    return paths


def original_unit(owner, closure_path, expected_argv, reader, control, runtime, window):
    """Observe exactly the captured live birth, or its original terminal closure."""
    shown = control.show(owner['unit'])
    read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
    live = shown.get('MainPID') == str(owner['pid'])
    closure_pin = None
    if live:
        require(shown.get('InvocationID') == owner['invocation_id'] and shown.get('NRestarts') == '0'
                and shown.get('ControlGroup') == owner['cgroup']
                and window.process_start(owner['pid']) == owner['starttime_ticks'], 'Original unit birth changed')
        argv = [value.decode() for value in Path('/proc', str(owner['pid']), 'cmdline').read_bytes().split(b'\0') if value]
        require(argv == expected_argv, 'Original live command differs')
    elif shown.get('LoadState') == 'loaded':
        control.original_terminal(shown, owner)
        require(window.process_start(owner['pid']) != owner['starttime_ticks'], 'Terminal original birth still exists')
    else:
        closure_pin = reader.pin(closure_path)
        closed = read(closure_pin)
        shown = runtime.archived_closure(closed, owner, read, exit_zero=False)
        require(window.process_start(owner['pid']) != owner['starttime_ticks'], 'Closed original process still exists')
    return dict(original=owner, live=live, actual_exit=None if live else int(shown['ExecMainStatus']),
                closure=closure_pin, start_monotonic_s=int(shown['ExecMainStartTimestampMonotonic'])/1e6,
                exit_monotonic_s=None if live else int(shown['ExecMainExitTimestampMonotonic'])/1e6)


def private_leg(record, plan, bindings, native, read, observer, process_start):
    """No recovery allowance applies to any evaluator or private MAME process."""
    index = record['index']
    spec = plan['legs'][index-1]
    display_path = Path(spec['evaluator_status_path'])
    require(display_path == Path(record['evaluator_status_path']) and record['receipt_path'] == spec['receipt_path']
            and record['console_log'] == spec['console_log'], 'Original private leg paths differ')
    display = json.loads(display_path.read_bytes()) if display_path.exists() else None
    evaluator_path = bindings/'leg-births'/f'leg{index}-evaluator.json'
    actors_path = bindings/'leg-births'/f'leg{index}-actors.json'
    if not evaluator_path.exists():
        require(record['state'] == 'running' and (display is None or display.get('phase') == 'warming')
                and (display is None or display.get('started', 0) == 0),
                'Live evaluator registry missing after startup; no historical adoption')
        return dict(index=index, role=record['role'], phase='waiting_original_evaluator_registry', verified_actor_births=0)
    evaluator = read(evaluator_path)
    require(evaluator['pid'] == record['pid'], 'Original evaluator PID changed')
    actors = read(actors_path) if actors_path.exists() else None
    counts = None
    if display is not None and all(key in display for key in ('count', 'started', 'pending', 'abandoned')):
        counts = {key: display[key] for key in ('count', 'started', 'pending', 'abandoned')}
        require(all(type(value) is int and value >= 0 for value in counts.values())
                and counts['count'] + counts['pending'] + counts['abandoned'] == counts['started'],
                'Private admitted/completed/tail partition differs')
    if record['state'] == 'running' and display is not None and display.get('phase') == 'finished':
        # The evaluator publishes its terminal display after stopping its MAME
        # children; the campaign parent may not have reaped it yet. Inspect the
        # retained original registry, never mistake normal cleanup for recovery.
        require(display.get('complete') is True and display.get('valid') is True
                and actors is not None and set(actors) == set(map(str, observer.SLOTS)),
                'Terminal private display lacks original successful completion')
        expected_pids = {slot: row['pid'] for slot, row in actors.items()}
        retained = {slot: row['pid'] for slot, row in display.get('socket_wait', {}).get('actors', {}).items()}
        current = display.get('actor_pids')
        require((current == expected_pids or (current is None and retained == expected_pids))
                and (not retained or retained == expected_pids)
                and counts is not None and counts['pending'] == counts['abandoned'] == 0,
                'Terminal private cleanup changed actors or retained incomplete tails')
        return dict(index=index, role=record['role'], phase='finished_waiting_original_parent_exit',
                    verified_actor_births=32, live_actor_births_verified=0,
                    counts=counts, original_record_state='running', qualification_pending_original_exit_and_review=True)
    if record['state'] == 'running':
        actual = observer.live_process(evaluator['pid'], native['pid'], native['cgroup'], spec['command'])
        require(actual['starttime_ticks'] == evaluator['starttime_ticks'] and actual['affinity'] == evaluator['affinity'],
                'Original evaluator birth or affinity changed')
        if actors is None:
            require(display is not None and display.get('phase') == 'warming' and display.get('started', 0) == 0,
                    'Original private actor registry missing after warmup')
            return dict(index=index, role=record['role'], phase='warming', verified_actor_births=0)
        require(display is not None and set(actors) == set(map(str, observer.SLOTS))
                and len({actor['pid'] for actor in actors.values()}) == 32
                and display['actor_pids'] == {slot: actor['pid'] for slot, actor in actors.items()},
                'Exact original32 private slot/PID registry required')
        for actor in actors.values():
            actual = observer.live_process(actor['pid'], evaluator['pid'], native['cgroup'], actor['command'])
            require(actual['starttime_ticks'] == actor['starttime_ticks'] and actual['affinity'] == actor['affinity'],
                    'A private actor was replaced or moved')
        if display['phase'] != 'warming':
            require(display['boundary']['ready'] is True and display['boundary']['acknowledged'] == 32,
                    'All32 private boundary acknowledgements required')
    else:
        require(record['returncode'] == 0 and actors is not None and set(actors) == set(map(str, observer.SLOTS)),
                'Original successful private leg and all32 birth records required')
        for process in [evaluator, *actors.values()]:
            require(process_start(process['pid']) != process['starttime_ticks'], 'Finished private original birth remains')
    return dict(index=index, role=record['role'], phase=None if display is None else display['phase'],
                verified_actor_births=32, live_actor_births_verified=32 if record['state'] == 'running' else 0,
                counts=counts, original_record_state=record['state'])


def inspect(job, reader, modules):
    read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
    supervision, joins, runtime, window, observer, control, wire, reviewer = (modules[key] for key in
        ('supervision', 'joins', 'runtime', 'window', 'observer', 'control', 'wire', 'reviewer'))
    Q = Path(job['preparation'])
    binding = read(job['campaign_binding'])
    main = read(job['main_binding'])
    reviewer.validate_main_binding(main, binding)
    policy = read(main['supervision_policy'])
    joins.validate_binding(main, policy, supervision)
    main = dict(main, baseline_API_value=read(main['baseline_API']))
    config, outer_plan = read(job['native_config']), read(job['outer_plan'])
    native, outer = read(job['native_owner']), read(job['outer_owner'])
    require(native['unit'] == config['unit'] == binding['campaign']['native_unit'] and outer['unit'] == outer_plan['unit']
            and config['guard_source'] == job['sources']['observer'], 'Original selected native/outer scope differs')
    owners = [original_unit(native, Q/'native-execution/native-terminal-archive/root-original-result-and-owned-release.json',
        config['argv'], reader, control, runtime, window), original_unit(outer,
        Q/'outer-controller-execution/native-terminal-archive/root-original-result-and-owned-release.json',
        outer_plan['argv'], reader, control, runtime, window)]
    bindings = Q/'runtime-bindings'
    state, samples, wire_paths, census_paths = None, [], set(), set()
    pins = []
    # Catch up on the same append-only accepted prefix if the initial replay
    # takes longer than one observer tick. No process or scientific retry occurs.
    for _ in range(4):
        paths = sample_files(bindings/'main-samples')
        require(len(paths) >= len(pins), 'Original main observations disappeared')
        additions = [reader.pin(path) for path in paths[len(pins):]]
        state, samples, wire_paths, census_paths = accepted_prefix(additions, main, policy, read, modules,
            state, samples, wire_paths, census_paths)
        pins.extend(additions)
        require(samples, 'No accepted original main observations')
        if not owners[0]['live'] or time.time() - samples[-1]['unix_s'] <= 15:
            break
    require(not list((bindings/'main-rejections').glob('*.json')), 'Original main guard rejected an observation')
    if owners[0]['live']:
        require(0 <= time.time() - samples[-1]['unix_s'] <= 30, 'Original main observer is stale')
    else:
        require(samples[0]['monotonic_s'] <= owners[0]['start_monotonic_s']
                and samples[-1]['monotonic_s'] >= owners[0]['exit_monotonic_s'],
                'Original observations do not cover native birth through exit')
    validate_prefix_exposure(main, samples, runtime, window)
    manifest_path = bindings/'main-observations.json'
    if manifest_path.exists():
        manifest = read(reader.pin(manifest_path))
        require(manifest['schema'] == joins.SCHEMA and manifest['status'] == 'PASS' and manifest['samples'] == pins
                and manifest['supervision_policy'] == main['supervision_policy'], 'Original terminal main manifest differs')
        require(manifest['supervision_summary'] == supervision.validate_closed(state), 'Closed supervision summary differs')
    census = supervision.collect(policy, state)
    current_wire = urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5).read(wire.MAX_WIRE_BYTES+1)
    api = wire.parse_wire(current_wire)
    now, monotonic = time.time(), time.monotonic()
    require(now >= samples[-1]['unix_s'] and monotonic >= samples[-1]['monotonic_s'],
            'Accepted observation lies beyond the current clock')
    validate_current_progress(api, samples[-1]['API'], monotonic-samples[-1]['monotonic_s'], runtime)
    if owners[0]['live']:
        _, current_state = joins.joined_census(policy, joins.pack(census, supervision),
            dict(API=api, unix_s=now, monotonic_s=monotonic), state, supervision)
        window.owner_and_files(joins.observed_main(main, census))
        joins.healthy(api, main['baseline_API_value'], main['experiment'], now, current_state, window.healthy)
    else:
        joins.validate_current(main, policy, census, state, supervision, window)
        window.healthy(api, main['baseline_API_value'], main['experiment'], now)
        current_state = state
    require(0 <= now - (G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime <= 360, 'Autosave stale')
    campaign = Path(binding['campaign']['output_directory'])
    require(str(campaign) == job['campaign'], 'Registered campaign directory differs')
    plan_entry = reader.pin(campaign/'plan.json')
    require(plan_entry['sha256'] == binding['campaign']['plan_sha256'], 'Original plan changed')
    plan = read(plan_entry)
    status = json.loads((campaign/'status.json').read_bytes())
    records = observer.validate_records(status, plan_entry['sha256'])
    legs = [private_leg(record, plan, bindings, native,
        lambda path: read(reader.pin(path)), observer, window.process_start) for record in records]
    for role in ('reference', 'candidate'):
        require(reader.pin(binding[role]['path']) == binding[role], 'Frozen role policy changed')
    for entry in job['sources'].values():
        require(reader.pin(entry['path']) == entry, 'Root monitor dependency changed during inspection')
    report = dict(unix_s=now, classification='LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED' if owners[0]['live'] else 'ORIGINAL_NATIVE_TERMINAL_AWAITING_FINAL_DISPOSITION',
        original_owners=owners, campaign_state=status['state'], current_leg=status.get('current_leg'), legs=legs,
        accepted_main_observations=len(samples), accepted_main_prefix_last=pins[-1],
        published_main_recoveries=len(state['completed_episodes']), published_main_pending=state['pending'] is not None,
        current_provisional_main_recoveries=len(current_state['completed_episodes']),
        current_provisional_main_pending=current_state['pending'] is not None,
        main=dict(client_count=api['client_count'], learner_frame_count=api['learner_frame_count'], training_steps=api['training_steps'],
            fps=api.get('fps') if type(api.get('fps')) in (int,float) and math.isfinite(api['fps']) else None),
        quality_qualified=False, scientific_approval_inferred=False, learning_speed_gain_verified=False,
        main_or_private_runtime_changed=False)
    return report, current_wire


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if not args.observe:
        print('PLAN_ONLY: no reads, queries, outputs, launches, releases or runtime changes')
        return 0
    reader = reader_module()
    entry = reader.pin(args.job)
    require(entry['sha256'] == args.job_sha256, 'Exact root monitor job required')
    job = reader.read_pin(entry)
    require(job['schema'] == 'robotron-supervised-quality32-root-monitor-job-v1'
            and job['monitor_source'] == reader.pin(Path(__file__).resolve()) and set(job['sources']) == set(SOURCES),
            'Source-bound original root monitor job required')
    modules = {}
    for name, (path, sha) in SOURCES.items():
        require(job['sources'][name] == reader.pin(path) and job['sources'][name]['sha256'] == sha,
                'Exact tested root monitor dependency required')
        modules[name] = reader.checked_module('_root_supervised_'+name+'_'+str(time.time_ns()), job['sources'][name])
    report, raw = inspect(job, reader, modules)
    output = Path(job['output'])
    require(output.parent == Path(job['preparation']) and output.name == 'root-live-monitor', 'Owned root monitor output required')
    output.mkdir(mode=0o700, exist_ok=True)
    stamp = str(time.time_ns())
    raw_pin = modules['window'].publish(output/(stamp+'-API-wire.raw'), raw)
    report['current_API_witness'] = modules['window'].publish(output/(stamp+'-API-witness.json'), modules['wire'].witness_fields(
        modules['wire'].parse_wire(raw), raw_pin))
    pin = modules['window'].publish(output/(stamp+'-report.json'), report)
    print(json.dumps(dict(report, receipt=pin), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
