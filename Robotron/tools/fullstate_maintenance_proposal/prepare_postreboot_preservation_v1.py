"""Prepare private maintenance sources for the observed post-reboot runtime.

Default inert. This copies bounded source/metadata files only. It never reads
model/replay payloads, changes live sources, or invokes service operations.
"""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pprint
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
PARENT = B / 'future-current-main-cold-cap-state-preservation-original01-20261030'
REC = B / 'reboot-recovery-20261031-original01'
FORWARD = B / 'current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031'
OWNER = dict(pid=599082, starttime_ticks=1650370, unit='robotron-trainer.service',
             invocation_id='bd90079895534cbb9c0813cebe1f6e8c',
             cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-trainer.service')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def assignment(text, name, value):
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    assert len(nodes) == 1, name
    old = ast.get_source_segment(text, nodes[0])
    return replace_once(text, old, name + '=' + pprint.pformat(value, sort_dicts=True))


def execute(output):
    assert output.is_absolute() and output.parent.resolve(strict=True) == output.parent and not output.exists()
    header_path = PARENT / 'prepare_current_continuous_preservation_header_v3.py'
    assert hashlib.sha256(header_path.read_bytes()).hexdigest() == 'e2877afb6695fcf3c08015331a0b0b6a0f1f12578cacba6a82d1d4dfff1af8b7'
    header = load('_postreboot_parent_header', header_path)
    startup = header.read(header.metadata(REC / 'startup-metadata-original01/startup-job.json')[0])
    held = header.read(header.metadata(REC / 'startup-held-original01/verified-held-before-first-update.json')[0])
    assert {k: held['owner'][k if k != 'starttime_ticks' else 'birth'] for k in OWNER} == OWNER
    for entry in startup['source_pins']:
        assert header.metadata(entry['path'])[0] == entry, entry['path']
    current = {Path(p['path']).name: p['sha256'] for p in startup['source_pins']}
    control_pin, control_raw = header.metadata(G / 'models_dqn/learning_control.json')
    control = json.loads(control_raw)
    assert control['lr_scale'] == .125 and control.get('measurement') is None
    originals = copy.deepcopy(header.SOURCES)
    # Verify all parent pins before deriving any source.
    for entry in originals.values():
        assert header.metadata(entry['path'])[0] == entry, entry['path']
    output.mkdir(mode=0o700)
    sources = output / 'sources'
    sources.mkdir(mode=0o700)
    derived = {}
    deltas = []

    def save(role, parent, text):
        parent_path = Path(parent['path'])
        old = parent_path.read_text()
        ast.parse(text)
        target = sources / parent_path.name
        pin = header.put(target, text.encode())
        derived[role] = pin
        deltas.append(dict(role=role, parent=parent, selected=pin,
                           patch=''.join(difflib.unified_diff(old.splitlines(True), text.splitlines(True)))))
        return pin

    parent = originals['inputs']
    text = Path(parent['path']).read_text()
    old_inputs = load('_postreboot_old_inputs', parent['path'])
    assert len(old_inputs.CURRENT_SHAS) == 5
    shas = {k: current[k] for k in old_inputs.CURRENT_SHAS}
    save('inputs', parent, assignment(text, 'CURRENT_SHAS', shas))
    parent_stop = load('_postreboot_old_stop', originals['stop']['path'])
    kernel_parent = header.metadata(parent_stop.KERNEL)[0]
    assert kernel_parent['sha256'] == parent_stop.KERNEL_SHA
    kernel_text = replace_once(Path(kernel_parent['path']).read_text(),
                               "value['lr'] == 3.125e-6", "value['lr'] == 6.25e-6")
    kernel_text = replace_once(kernel_text, "base['lr_scale'] == .0625", "base['lr_scale'] == .125")
    kernel_text = replace_once(kernel_text, 'Current .0625 recipe', 'Current .125 recipe')
    kernel_pin = save('stop_kernel', kernel_parent, kernel_text)
    text = Path(originals['stop']['path']).read_text()
    text = replace_once(text, ast.get_source_segment(text, next(n for n in ast.parse(text).body
        if isinstance(n, ast.Assign) and any(getattr(t, 'id', None) == 'KERNEL' for t in n.targets))),
        'KERNEL=Path(' + repr(kernel_pin['path']) + ')')
    text = replace_once(text, parent_stop.KERNEL_SHA, kernel_pin['sha256'])
    save('stop', originals['stop'], text)
    save('budget_intent', originals['budget_intent'], Path(originals['budget_intent']['path']).read_text())

    parent = originals['verifier']
    text = Path(parent['path']).read_text()
    assert text.count('3.125e-6') == 3
    text = text.replace('3.125e-6', '6.25e-6')
    text = text.replace('.0625', '.125')
    text = replace_once(text, '    replacements=list(recipe.RECIPE_REPLACEMENTS)',
        "    targets={b'optimizer_lr=3.125e-6,': b'optimizer_lr=6.25e-6,',\n"
        "             b'learning_control_lr_scale=.0625,': b'learning_control_lr_scale=.125,',\n"
        "             b\"control['lr_scale'] == .0625\": b\"control['lr_scale'] == .125\"}\n"
        '    replacements=[(old, targets.get(new,new))\n'
        '                  for old,new in recipe.RECIPE_REPLACEMENTS]')
    verifier = save('verifier', parent, text)
    parent = originals['backup']
    text = replace_once(Path(parent['path']).read_text(), originals['verifier']['sha256'], verifier['sha256'])
    save('backup', parent, text)

    catalogue = {k: derived.get(k, v) for k, v in originals.items()}
    catalogue['stop_kernel'] = kernel_pin
    text = assignment(header_path.read_text(), 'SOURCES', catalogue)
    text = replace_once(text, 'optimizer_lr=3.125e-6', 'optimizer_lr=6.25e-6')
    text = replace_once(text, 'learning_control_lr_scale=.0625', 'learning_control_lr_scale=.125')
    text = replace_once(text, "json.loads(control_raw)['lr_scale']==.0625", "json.loads(control_raw)['lr_scale']==.125")
    new_header = save('header', header.metadata(header_path)[0], text)

    operator = FORWARD / 'future-post-backup-held-startup-source-original01/prepare_and_release_repaired_current_fullstate_startup_v5.py'
    # Keep the already-qualified startup operator identity used by the fleet constructor.
    assert hashlib.sha256(operator.read_bytes()).hexdigest() == '11f7e4f1d1d8b11b373d4922c704ab072a57fc85f976d919c41995821df95d1a'
    fleet_path = FORWARD / 'future-repaired-v6-fleet-DATA-source-original01/prepare_repaired_current_v6_fleet_job_v1.py'
    assert hashlib.sha256(fleet_path.read_bytes()).hexdigest() == '8bd6160755ffe689fbf6c7efd2d1589065bcdba0c2c7b48244b68b6e9dd1f06a'
    fleet_parent = header.metadata(fleet_path)[0]
    text = fleet_path.read_text()
    text = replace_once(text, "    base=read(BASE); require(len(base['inputs'])==79,'Fixed0b63 input inventory differs')",
        "    base=read(BASE); require(len(base['inputs'])==79,'Fixed0b63 input inventory differs')\n"
        '    selected_previous_owner=' + repr(OWNER))
    text = replace_once(text, "manifest['owner']['pid']==base['trainer']['pid']",
                        "manifest['owner']['pid']==selected_previous_owner['pid']")
    text = replace_once(text, "manifest['owner']['starttime_ticks']==base['trainer']['birth']",
                        "manifest['owner']==selected_previous_owner")
    text = replace_once(text, "    installed=job['source_pins']",
        "    require((owner['pid'],owner['birth'],owner['invocation_id']) !=\n"
        "        (selected_previous_owner['pid'],selected_previous_owner['starttime_ticks'],selected_previous_owner['invocation_id']),\n"
        "        'A fresh incarnation after the selected post-reboot owner is required')\n"
        "    installed=job['source_pins']")
    save('forward_fleet_constructor', fleet_parent, text)
    derivations = header.put(output / 'exact-parent-derivations.json', dict(
        builder=header.metadata(Path(__file__).resolve())[0], deltas=deltas))
    packet = header.put(output / 'prepared-current-source-family.json', dict(
        schema='robotron-postreboot-preservation-source-preparation-v1',
        status='SOURCE_PREPARED_NOT_CPU_TESTED_NOT_SELECTED_OR_LAUNCHED',
        observed_unix_s=time.time(), previous_owner=OWNER, installed_startup_source_pins=startup['source_pins'],
        sources=derived, source_catalogue=catalogue, derivations=derivations,
        startup_operator=header.metadata(operator)[0], actual_saved_optimizer_lr=6.25e-6,
        observed_current_control_pin=control_pin, observed_current_control=control,
        main_recipe_changed=False, live_sources_changed=False, service_action_performed=False,
        model_or_ring_payloads_read=False, actual_stop_or_backup=False))
    print(json.dumps({k: packet[k] for k in ('path', 'sha256', 'bytes')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.execute:
        assert args.output
        execute(args.output)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
