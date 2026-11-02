"""Replay a read-only pilot through the generated reviewer's real health loop.

This explicit engineering adapter does not execute or qualify a complete-game
review. It supplies the pilot's finish-report pin under the native field name.
"""
import argparse
import ast
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('job', 'result', 'reviewer', 'CPU-integration', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    h = load('_live_owned_review_h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    job = json.loads(args.job.read_text())
    pilot = json.loads(args.result.read_text())
    cpu = json.loads(args.CPU_integration.read_text())
    require(cpu['status'] == 'PASS' and cpu['reviewer'] == h.pin(args.reviewer),
            'Exact CPU-qualified reviewer source required')
    require(pilot['status'] == 'PASS_READ_ONLY_V6_PHYSICAL_ENGINEERING_ONLY'
            and pilot['error'] is None and len(pilot['samples']) == 20
            and pilot['elapsed_s'] <= 150 and pilot['original_job'] == h.pin(args.job),
            'Original finite read-only pilot did not pass')
    h.checked(job['runtime'])
    h.checked(job['health_source'])
    h.checked(job['owned_TRAIN_overlap_source'])
    owner = json.loads((Path(job['output'])/'original-owner.json').read_text())
    require(owner['runtime'] == job['runtime'] and owner['job'] == h.pin(args.job)
            and owner['child_scope_created'] is False,
            'Original no-child-scope owner differs')
    proc = Path('/proc', str(owner['pid']), 'stat')
    live_birth = int(proc.read_text().rsplit(')', 1)[1].split()[19]) if proc.exists() else None
    require(live_birth != owner['birth'], 'Original pilot process remains live')

    def read(pin):
        return json.loads(h.checked(pin).read_text())

    finished = read(pilot['observer_close'])
    require(finished['samples'] == pilot['samples'], 'Pilot and executed finish streams differ')
    # The original synchronous driver called finish(None) and returned its pin.
    # The pinned observer's finish contract sets these flags immediately before
    # writing that report. These adapter fields are not a native result receipt.
    result = dict(main_samples=pilot['samples'], main_health_report=pilot['observer_close'],
        main_observer_lifecycle=dict(original_observer_thread_closed=True, no_child_scope_created=True))
    adapted_job = dict(job, current_v6_health_source=job['health_source'])
    tree = ast.parse(args.reviewer.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
        and any(isinstance(child, ast.Constant) and child.value == '_eng_review_actual_v6_health'
                for child in ast.walk(node)))
    start = next(i for i, node in enumerate(function.body) if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'source' for target in node.targets)
        and '_eng_review_actual_v6_health' in ast.unparse(node))
    end = next(i for i in range(start, len(function.body)) if isinstance(function.body[i], ast.For)
        and isinstance(function.body[i].target, ast.Name) and function.body[i].target.id == 'pin'
        and 'bindings.values()' in ast.unparse(function.body[i].iter))
    extracted = ast.parse('def review_health(result,job,h,read):\n    pass').body[0]
    extracted.body = copy.deepcopy(function.body[start:end+1])
    extracted.body.append(ast.parse('return dict(accepted=accepted,pending=pending,max_gap=max_gap)').body[0])
    env = dict(load=load, require=require, math=math)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[extracted], type_ignores=[])),
                 '<actual-generated-reviewer-health-loop>', 'exec'), env)
    outcome = env['review_health'](result, adapted_job, h, read)
    bindings, rebind_slots = {}, set()
    for sample in pilot['samples']:
        raw = read(sample['physical_v6'])
        for key, event in raw['bindings'].items():
            pin = raw['fleet_before']['slots'][key]['current_physical_binding']
            bindings[pin['path']] = pin
            if event['data'].get('previous_binding') is not None:
                rebind_slots.add(int(key))
    require(outcome['accepted'] == 20 and outcome['pending'] == 0 and rebind_slots,
            'Expected real accepted census and retained rebound cleanup checks')
    require('torch' not in sys.modules, 'CPU-only review imported torch')
    report = h.put(args.output, dict(
        status='PASS_OWNED_OVERLAP_OBSERVER_CPU33_AND_LIVE20_REVIEW_ONLY',
        job=h.pin(args.job), pilot_result=h.pin(args.result), reviewer=h.pin(args.reviewer),
        observer=job['health_source'], owned_helper=job['owned_TRAIN_overlap_source'],
        review_source=h.pin(Path(__file__)), CPU_integration=h.pin(args.CPU_integration),
        original_owner=owner, original_birth_absent=True, extracted_real_reviewer_health_AST=True,
        explicit_pilot_field_adapter=True, executed_finish_report=pilot['observer_close'],
        outcome=outcome, distinct_original_bindings_checked=len(bindings),
        real_original_TRAIN_rebind_slots_with_cleanup_checked=sorted(rebind_slots),
        live_overlap_seen_in_retained_samples=False, overlap_ownership_callbacks_CPU_synthetic_only=True,
        full_native_game_or_whole_reviewer_or_statistical_qualification=False,
        failed_original_science_rescued=False, promotion=False))
    print(json.dumps(dict(status='PASS',report=report,real_rebound_slots=len(rebind_slots),outcome=outcome)))


if __name__ == '__main__':
    main()
