"""CPU metadata/recipe checks for a private post-reboot maintenance family.

No service, model, replay, GPU or MAME operation is performed.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--prepared-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    assert hashlib.sha256(args.prepared.read_bytes()).hexdigest() == args.prepared_sha256
    packet = json.loads(args.prepared.read_bytes())
    sources = packet['sources']
    header = load('_maintenance_CPU_header', sources['header']['path'])
    assert header.metadata(args.prepared)[0]['sha256'] == args.prepared_sha256
    for entry in sources.values():
        assert header.metadata(entry['path'])[0] == entry
    verifier = header.load('verifier')
    inputs = header.load('inputs')
    checks = []

    def check(name, value):
        assert value, name
        checks.append(name)

    def rejects(name, operation):
        try:
            operation()
        except (AssertionError, RuntimeError, ValueError, KeyError):
            checks.append(name)
            return
        raise AssertionError('Invalid recipe accepted: ' + name)

    recipe_path, recipe_sha = verifier.DEPENDENCIES['recipe_verifier']
    check('exact parent recipe helper', hashlib.sha256(recipe_path.read_bytes()).hexdigest() == recipe_sha)
    recipe = load('_maintenance_CPU_original_recipe', recipe_path)
    for cap in (8, 12):
        context = dict(header.HELD, max_samples_per_frame=cap)
        job = dict(source_control_context=dict(held_recipe_context=context), expected_current_cap=cap)
        strict, specialization = verifier.select_current_recipe(job, recipe)
        check(f'cap{cap} actual selected LR and full recipe', strict.HELD_RECIPE_CONTEXT == context
              and specialization['selected_recipe']['scheduled_lr'] == 6.25e-6)
        raw = recipe.STRICT_PATH.read_bytes()
        effective = raw
        for row in specialization['literal_replacements']:
            old, new = row['original'].encode(), row['effective'].encode()
            check(f'cap{cap} exact literal {row["original"]}', effective.count(old) == 1)
            effective = effective.replace(old, new)
        check(f'cap{cap} effective numerical body hash', hashlib.sha256(effective).hexdigest()
              == specialization['effective_source_sha256'])
        for row in reversed(specialization['literal_replacements']):
            effective = effective.replace(row['effective'].encode(), row['original'].encode())
        check(f'cap{cap} strict numerical body reverse proof', effective == raw)
    for key, value in [('optimizer_lr', 3.125e-6), ('optimizer_lr', 2.5e-5),
                       ('learning_control_lr_scale', .0625), ('n_step', 1),
                       ('c51_target_smoothing', .01), ('optimizer_eps', 1e-8),
                       ('batch_size', 512), ('expert_ratio', .0), ('epsilon', .0),
                       ('n_step', 3.0), ('fused', False)]:
        context = dict(header.HELD)
        context[key] = value
        rejects(f'reject {key}={value}', lambda context=context: verifier.select_current_recipe(
            dict(source_control_context=dict(held_recipe_context=context), expected_current_cap=8), recipe))
    for cap in (True, 8.0, 0, 16):
        rejects(f'reject invalid cap {cap!r}', lambda cap=cap: verifier.select_current_recipe(
            dict(source_control_context=dict(held_recipe_context=header.HELD), expected_current_cap=cap), recipe))

    derivations = header.read(packet['derivations'])
    for row in derivations['deltas']:
        if row['role'] == 'budget_intent':
            check(row['role'] + ' original body byte-identical',
                  Path(row['parent']['path']).read_bytes() == Path(row['selected']['path']).read_bytes())
    kernel_delta = next(v for v in derivations['deltas'] if v['role'] == 'stop_kernel')
    old_kernel = Path(kernel_delta['parent']['path']).read_text()
    new_kernel = Path(kernel_delta['selected']['path']).read_text()
    check('inherited stop kernel only expected API LR and control scale changed',
          new_kernel.replace("value['lr'] == 6.25e-6", "value['lr'] == 3.125e-6").replace(
              "base['lr_scale'] == .125", "base['lr_scale'] == .0625").replace(
                  'Current .125 recipe', 'Current .0625 recipe') == old_kernel
          and new_kernel.count("value['lr'] == 6.25e-6") == 1)
    check('selected control context matches actual canonical control',
          header.HELD['learning_control_lr_scale'] == packet['observed_current_control']['lr_scale'] == .125
          and header.metadata(packet['observed_current_control_pin']['path'])[0] == packet['observed_current_control_pin'])
    stop_delta = next(v for v in derivations['deltas'] if v['role'] == 'stop')
    old_tree = ast.parse(Path(stop_delta['parent']['path']).read_text())
    new_tree = ast.parse(Path(stop_delta['selected']['path']).read_text())
    check('stop producer functions unchanged; private dependency pin only',
          [ast.dump(n) for n in old_tree.body if isinstance(n, ast.FunctionDef)] ==
          [ast.dump(n) for n in new_tree.body if isinstance(n, ast.FunctionDef)])
    backup = header.load('backup')
    check('backup authenticates new private strict verifier', backup.VERIFIER_SHA == sources['verifier']['sha256']
          and backup.VERIFIER == Path(sources['verifier']['path']))
    check('current writer source family matches actual loaded startup sources',
          all(any(Path(v['path']).name == name and v['sha256'] == sha
                  for v in packet['installed_startup_source_pins']) for name, sha in inputs.CURRENT_SHAS.items()))
    root = args.prepared.parent.parent
    recovery = root / 'reboot-recovery-20261031-original01'
    fleet_status = json.loads((recovery / 'fleet-v6-original01/status.json').read_bytes())
    fleet = {k if k != 'birth' else 'starttime_ticks': v
             for k, v in fleet_status['supervisor'].items() if k != 'source'}
    selection = dict(schema='robotron-root-current-continuous-preservation-selection-v1',
                     owner=packet['previous_owner'], fleet=fleet,
                     expected_current_cap=8, first_current_main_stop=False,
                     startup_job=header.metadata(recovery / 'startup-metadata-original01/startup-job.json')[0],
                     startup_held=header.metadata(recovery / 'startup-held-original01/verified-held-before-first-update.json')[0],
                     startup_release_consumed=header.metadata(recovery / 'startup-held-original01/release-consumed.json')[0])
    anchor = inputs.startup_anchor(selection)
    check('actual recovered held/release provenance', anchor['owner'] == selection['owner']
          and anchor['fleet'] == selection['fleet'] and anchor['startup_job'] == selection['startup_job'])
    damaged = copy.deepcopy(selection)
    damaged['owner']['starttime_ticks'] += 1
    rejects('reject wrong current original birth', lambda: inputs.startup_anchor(damaged))
    damaged = copy.deepcopy(selection)
    damaged['expected_current_cap'] = 12
    rejects('reject cap different from actual held restoration', lambda: inputs.startup_anchor(damaged))

    # The fleet constructor still uses the qualified actor/job transformation.
    delta = next(v for v in derivations['deltas'] if v['role'] == 'forward_fleet_constructor')
    old_tree = ast.parse(Path(delta['parent']['path']).read_text())
    new_tree = ast.parse(Path(delta['selected']['path']).read_text())
    old_functions = {n.name: ast.dump(n) for n in old_tree.body if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: ast.dump(n) for n in new_tree.body if isinstance(n, ast.FunctionDef)}
    check('fleet constructor unrelated functions unchanged',
          set(old_functions) == set(new_functions)
          and all(old_functions[k] == new_functions[k] for k in old_functions if k != 'prepare'))
    old = Path(delta['parent']['path']).read_text()
    new = Path(delta['selected']['path']).read_text()
    before = "    base=read(BASE); require(len(base['inputs'])==79,'Fixed0b63 input inventory differs')"
    new = new.replace(before + '\n    selected_previous_owner=' + repr(packet['previous_owner']), before, 1)
    new = new.replace("manifest['owner']['pid']==selected_previous_owner['pid']", "manifest['owner']['pid']==base['trainer']['pid']", 1)
    new = new.replace("manifest['owner']==selected_previous_owner", "manifest['owner']['starttime_ticks']==base['trainer']['birth']", 1)
    extra = ("    require((owner['pid'],owner['birth'],owner['invocation_id']) !=\n"
             "        (selected_previous_owner['pid'],selected_previous_owner['starttime_ticks'],selected_previous_owner['invocation_id']),\n"
             "        'A fresh incarnation after the selected post-reboot owner is required')\n")
    check('fleet adds exact fresh-incarnation rejection', new.count(extra) == 1)
    new = new.replace(extra, '', 1)
    check('fleet exact reverse derivation', new == old)
    check('no numerical runtime imported', 'torch' not in sys.modules and 'numpy' not in sys.modules)
    report = header.put(args.output, dict(
        status='PASS_POSTREBOOT_MAINTENANCE_METADATA_RECIPE_ONLY', tests_run=len(checks), checks=checks,
        observed_unix_s=time.time(), preparation=header.metadata(args.prepared)[0],
        test_source=header.metadata(Path(__file__).resolve())[0], actual_boot_descriptor=anchor,
        full_stopped_state_verified=False, live_stop_executed=False, checkpoint_or_ring_payload_read=False,
        live_restart_or_fleet_constructor_execution_qualified=False))
    print(json.dumps(dict(status='PASS_POSTREBOOT_MAINTENANCE_METADATA_RECIPE_ONLY', tests_run=len(checks),
                          report={k: report[k] for k in ('path', 'sha256', 'bytes')})))


if __name__ == '__main__':
    main()
