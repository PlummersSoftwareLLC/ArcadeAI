"""Select/print/close one NEW exact D7 guard; default inert, never launch.

The earlier default guard packet stays unlaunched and immutable. No scientific
source/job bytes are changed. Only ROOT can invoke the printed CPU controller.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

LOCAL = Path(__file__).resolve().parent
GENERATOR_SHA = '2511a0c465df372af331312a5e647804c2cd5c369ae1ff237bb130c65c45b7fa'
PREPARER_SHA = '5445dc72090ea2823d3eac1d368cc0db51e5c30133e7e11668459f436fac0606'
CLOSER_SHA = '2afa743774550aa613703aab64f82ec0da6f539509978e82744c7b9a7d99110a'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup():
    path = LOCAL/'prepare_closed_metadata_authority_D7_v2.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == GENERATOR_SHA,
            'Selected closed metadata generator differs')
    g = load('_D7_guard_authority_generator', path)
    return g, g.helpers()


def prepare(selection, selection_sha, authority_path, authority_sha):
    g, h = setup()
    root_pin, selected, policy_pin, policy = g.selection(selection, selection_sha, h)
    authority_pin = h.pin(Path(authority_path).resolve())
    require(authority_pin['sha256'] == authority_sha and authority_pin['path'] == selected['authority_output'],
            'Actual NEW closed-metadata reuse authority differs')
    a = g.read(authority_pin, h)
    require(a['ROOT_selection'] == root_pin and a['source_contract'] == policy_pin
            and a['metadata_closeout'] == selected['metadata_closeout']
            and a['native_prepared'] == selected['native_prepared'], 'Selected actual metadata authority differs')
    manifest = g.read(a['native_prepared'], h)
    metadata_report = g.read(a['metadata_report'], h)
    old_packet_pin = metadata_report['exact_CPU_packet']
    old_packet = g.read(old_packet_pin, h)
    require(old_packet['native_prepared_manifest'] == a['native_prepared'],
            'Default unlaunched guard belongs to another study')
    old_config = g.read(old_packet['config'], h)
    old_job = g.read(old_packet['CPU_job'], h)
    require(old_job['prepared_manifest'] == a['native_prepared']
            and not Path(old_job['output']).exists() and not Path(old_config['output']).exists(),
            'Default guard has already run or created its output')
    controller = load('_D7_unused_default_guard_controller', h.checked(old_packet['controller']))
    require(controller.checked_config(old_packet['config']['path']) == old_config,
            'Default guard controller config differs')
    for unit in (old_config['unit'], old_config['unit'].removesuffix('.service')+'.timer'):
        require(controller.show(unit)['LoadState'] == 'not-found', 'Default guard scope has not been released/unused')
    for case in manifest['cases']:
        subject = g.read(case['native_job'], h)
        require(not Path(subject['output']).exists()
                and not Path(subject['prelaunch_family_guard_closeout']).exists()
                and not Path(case['unqualified_controller_config']['path']).parent.joinpath('execution-original01').exists(),
                'Native/guard paths must remain unused')
    source = h.pin(LOCAL/'prepare_round_cpu_guard_D7_v12.py')
    require(source['sha256'] == PREPARER_SHA, 'Actual prospective guard preparer differs')
    preparer = load('_D7_selected_closed_guard_preparer', h.checked(source))
    root = LOCAL.parent/'actual-closed-metadata-guard-original01'
    require(not root.exists(), 'One exclusive original guard preparation only')
    packet = preparer.prepare(Path(a['native_prepared']['path']), root, authority_pin)
    closer = h.pin(LOCAL/'close_round_study_cpu_closed_metadata_D7_v9.py')
    require(closer['sha256'] == CLOSER_SHA, 'Exact reviewed guard closeout source differs')
    result = dict(schema='robotron-D7-selected-closed-metadata-CPU-guard-v1',
        native_prepared=a['native_prepared'], source_contract=policy_pin,
        ROOT_selection=root_pin, closed_metadata_readiness_authority=authority_pin,
        unlaunched_default_guard_packet=old_packet_pin, selected_guard_packet=packet,
        selected_guard_preparer=source, selected_guard_closer=closer,
        native_guard_destinations_unchanged=True, default_guard_executed=False,
        CPU_qualified=False, native_launch_qualified=False, source=h.pin(Path(__file__).resolve()))
    return h.put(LOCAL.parent/'selected-closed-metadata-guard-original01.json', result)


def selected(path, expected_sha):
    g, h = setup()
    pin = h.pin(Path(path).resolve())
    require(pin['sha256'] == expected_sha, 'Selected guard override differs')
    value = g.read(pin, h)
    require(value['schema'] == 'robotron-D7-selected-closed-metadata-CPU-guard-v1'
            and value['source'] == h.pin(Path(__file__).resolve())
            and value['native_guard_destinations_unchanged'] is True
            and value['CPU_qualified'] is value['native_launch_qualified'] is False,
            'Exact immutable guard override required')
    return g, h, value


def launch_argv(path, expected_sha):
    g, h, value = selected(path, expected_sha)
    packet = g.read(value['selected_guard_packet'], h)
    return ['/usr/bin/python3.12','-I','-B',packet['controller']['path'],'--execute',
            '--config',packet['config']['path'],'--expected-source-sha256',packet['controller']['sha256']]


def close(path, expected_sha):
    g, h, value = selected(path, expected_sha)
    source = value['selected_guard_closer']
    require(source['sha256'] == CLOSER_SHA, 'Selected guard closer differs')
    module = load('_D7_actual_guard_closer', h.checked(source))
    packet = value['selected_guard_packet']
    return module.close(packet['path'], packet['sha256'], source['sha256'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--print-launch', action='store_true')
    modes.add_argument('--close', action='store_true')
    p.add_argument('--selection', type=Path)
    p.add_argument('--selection-sha256')
    p.add_argument('--authority', type=Path)
    p.add_argument('--authority-sha256')
    p.add_argument('--selected', type=Path)
    p.add_argument('--selected-sha256')
    p.add_argument('--source-sha256')
    a = p.parse_args()
    if not (a.prepare or a.print_launch or a.close):
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == a.source_sha256,
            'Actual guard selector source differs')
    if a.prepare:
        value = prepare(a.selection,a.selection_sha256,a.authority,a.authority_sha256)
    elif a.print_launch:
        value = launch_argv(a.selected,a.selected_sha256)
    else:
        value = close(a.selected,a.selected_sha256)
    print(json.dumps(value), flush=True)


if __name__ == '__main__':
    main()
