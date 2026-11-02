"""Bind the root inspector to already captured original native/outer births.

Default is inert. This writes only its new monitor job and registration after
read-only checks; it never launches, changes learning, adopts a late private
birth, evaluates, releases units, retries or makes a scientific decision.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
MONITOR = G/'tools/quality_capacity_proposal/monitor_supervised_quality32_v5.py'
READER = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reader_module():
    require(hashlib.sha256(READER.read_bytes()).hexdigest() == 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'Exact reader required')
    spec = importlib.util.spec_from_file_location('_supervised_monitor_preparation_reader', READER)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def prepare(precommit_pin, monitor_pin, reader):
    read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
    pre = read(precommit_pin)
    require(pre['schema'] == 'robotron-supervised-quality32-followup-precommit-v1'
            and pre['original_attempt'] == 1 and pre['no_retry'] is True, 'Exact prospective study precommit required')
    require(monitor_pin['path'] == str(MONITOR) and reader.pin(MONITOR) == monitor_pin,
            'Exact tested inspector source required')
    monitor = reader.checked_module('_prepared_supervised_root_monitor_'+str(time.time_ns()), monitor_pin)
    Q = Path(pre['campaign_preparation'])
    require(Q.is_absolute() and Q.resolve() == Q, 'Resolved owned campaign preparation path required')
    paths = dict(native_owner=Q/'runtime-bindings/native-owner.json',
        outer_owner=Q/'outer-controller-execution/root-original-live-owner.json',
        native_config=Q/'original-native-controller-config.json', outer_plan=Q/'original-outer-launch-plan.json',
        campaign_binding=Q/'runtime-bindings/campaign-binding.json', main_binding=Q/'runtime-bindings/main-binding.json')
    target = Q/'root-live-monitor-job.json'
    registration_path = Q/'root-live-monitor-registration.json'
    # Do not create output directories while any original birth/binding is absent.
    require(not target.exists() and not registration_path.exists() and all(path.is_file() for path in paths.values()),
            'Original births/bindings missing or root monitor registration already consumed')
    pins = {key: reader.pin(path) for key, path in paths.items()}
    values = {key: read(entry) for key, entry in pins.items()}
    require(values['native_owner']['unit'] == pre['native_unit'] and values['outer_owner']['unit'] == pre['outer_unit']
            and values['native_config']['unit'] == pre['native_unit'] and values['outer_plan']['unit'] == pre['outer_unit']
            and values['campaign_binding']['campaign']['output_directory'] == pre['campaign_parameters']['directory'],
            'Actual original study units or directory differ from precommit')
    sources = {key: reader.pin(path) for key, (path, _) in monitor.SOURCES.items()}
    for key, (_, expected) in monitor.SOURCES.items():
        require(sources[key]['sha256'] == expected, 'Exact inspector dependency changed')
        read(sources[key], False)
    require(sources['observer'] == pre['selected_sources']['quality32_runtime_guard_v8.py']
            and sources['supervision'] == pre['selected_sources']['supervised_main_fleet_v1.py']
            and sources['joins'] == pre['selected_sources']['supervised_main_observations_v1.py']
            and sources['reviewer'] == pre['selected_sources']['review_closed_quality32_v8.py']
            and values['native_config']['guard_source'] == sources['observer'],
            'Inspector must use the actually selected scientific source chain')
    modules = {key: reader.checked_module('_monitor_preparation_'+key+'_'+str(time.time_ns()), sources[key])
               for key in ('control', 'window', 'runtime', 'reviewer', 'supervision', 'joins')}
    for role, config_key in [('native', 'native_config'), ('outer', 'outer_plan')]:
        owner = values[role+'_owner']
        require(owner.get('observed_live') is True, 'Original live birth witness required')
        status = monitor.original_unit(owner, Q/('unused-live-'+role+'-closure.json'), values[config_key]['argv'],
            reader, modules['control'], modules['runtime'], modules['window'])
        require(status['live'], 'Register root inspector only while both original services remain live')
    main, binding = values['main_binding'], values['campaign_binding']
    modules['reviewer'].validate_main_binding(main, binding)
    modules['joins'].validate_binding(main, read(main['supervision_policy']), modules['supervision'])
    job = dict(schema='robotron-supervised-quality32-root-monitor-job-v1', preparation=str(Q),
        campaign=pre['campaign_parameters']['directory'], followup_precommit=precommit_pin,
        monitor_source=monitor_pin, sources=sources, output=str(Q/'root-live-monitor'), **pins)
    job_pin = modules['window'].publish(target, job)
    command = ['/usr/bin/python3.12', '-I', '-B', monitor_pin['path'], '--observe', '--job', job_pin['path'], '--job-sha256', job_pin['sha256']]
    registration = modules['window'].publish(registration_path, dict(status='ROOT_INSPECTOR_REGISTERED_SAME_ORIGINAL_STUDY',
        unix_s=time.time(), job=job_pin, command=command, original_native=pins['native_owner'],
        original_outer=pins['outer_owner'], scientific_runtime_changed=False, quality_qualified=False))
    return dict(job=job_pin, command=command, registration=registration)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--precommit', type=Path)
    parser.add_argument('--precommit-sha256')
    parser.add_argument('--monitor-sha256')
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY: no reads, queries, copies, outputs or runtime changes')
        return 0
    reader = reader_module()
    pre_pin, monitor_pin = reader.pin(args.precommit), reader.pin(MONITOR)
    require(pre_pin['sha256'] == args.precommit_sha256 and monitor_pin['sha256'] == args.monitor_sha256,
            'Exact precommit and tested inspector SHA required')
    print(json.dumps(prepare(pre_pin, monitor_pin, reader), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
