"""Freeze a distinct1741-vs2259 study after the verified producer repair.

Preparation only. No games, GPU work, service operations, runtime mutation,
policy promotion or reuse of the failed2202 study's scores.
"""
import argparse
import ast
import copy
import difflib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
B = G/'tools/startup_policy_journal_proposal'
OLD = R/'quality32-protected1741-vs-normal2202-start-certified-original01-preparation-20261022'
NEW = R/'quality32-protected1741-vs-normal2259-after-JSON-original01-preparation-20261022'


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY')
        return 0
    spec = importlib.util.spec_from_file_location('_new2259_pair_h', B/'run_full_policy_startup_v3.py')
    h = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = h
    spec.loader.exec_module(h)
    require(h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'Helper changed')
    state = json.loads((R.parent/'state.json').read_bytes())
    goal = state['optimization_goal']
    fix = goal['future_dashboard_JSON_fix']
    require(fix['production_applied'] is True and goal['actual_running_wait'] is None
            and state['active_maintenance_job'] is None, 'Verified closed producer maintenance required')
    registration_pin = fix['independent_registration']
    require(registration_pin['sha256'] == '3da66bab9abd69b7dab1ef7c32f1177ac3e15843a192d3873611f284ed03f581', 'Actual deployed registration changed')
    registration = json.loads(h.checked(registration_pin).read_bytes())
    main = json.loads(h.checked(registration['current_main_binding']).read_bytes())
    guard = h.load('_new2259_pair_guard', R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
    require(h.pin(guard.__file__)['sha256'] == 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', 'Guard changed')
    guard.owner_and_files(main)
    old_pair_pin = h.pin(OLD/'campaign-inputs-and-gates-precommit.json')
    require(old_pair_pin['sha256'] == '79ae0a32e8d924d36517dbd76e6b97bb34309f695d0b913a28da514b3a269b90', 'Original pair changed')
    pair = copy.deepcopy(json.loads(h.checked(old_pair_pin).read_bytes()))
    insurance_pin = fix['current_normal_insurance']
    require(insurance_pin['sha256'] == '385755762289fe8efd7f8f1a4f43c3f0feb7fe50f0a57f2dbcfc5de462420326', 'New candidate CPU closure changed')
    insurance = json.loads(h.checked(insurance_pin).read_bytes())
    report_pin = insurance['report']
    report = json.loads(h.checked(report_pin).read_bytes())
    require(insurance['actual_exit'] == 0 and report['status'] == 'PASS' and report['phase_metadata_verified'] is True, 'Actual strict CPU/phase proof required')
    candidate_job = json.loads(h.checked(report['job']).read_bytes())
    policy = candidate_job['candidate']
    h.checked(policy)
    require(policy == report['candidate'] and policy['sha256'] == 'c97f7d82118c6d743d3ce9649a709ef49f93946e349f55c5e9ab47339a27af9b', 'Exact new2259 candidate required')
    require(report['clocks']['learner_frame_count'] == 2259572926 and policy['sha256'] != pair['candidate']['policy']['sha256'], 'Distinct frozen candidate required')
    for name in ('reference',):
        for key in ('policy', 'CPU_report', 'original_CPU_readback'):
            h.checked(pair[name][key])
    failed_pin = h.pin(OLD/'01-reference/independent-quality-leg-review-original01/review.json')
    require(failed_pin['sha256'] == 'faa19ec62f6a2bdda1e338c538d61af739c511f580e92e45bf74c300cdb24ad2', 'Failed original science changed')
    require(not NEW.exists(), 'One new study preparation only')
    NEW.mkdir(mode=0o700)
    pair.update(state='DISTINCT_INPUT_PAIR_FIXED_AFTER_VERIFIED_PRODUCER_JSON_REPAIR',
        candidate=dict(policy=policy, saved_clocks={k:report['clocks'][k] for k in ('learner_frame_count', 'training_steps', 'optimized_samples')},
                       original_CPU_readback=insurance_pin, CPU_report=report_pin),
        prerequisites=[
            'Exact producer JSON repair deployed through independently verified current-state handoff; original failed2202 study and every score remain invalid/excluded.',
            'Bind and verify the new2259 pair/runtime/controller/per-leg reviewer/assessor and unchanged full-game, wire, threshold and no-retry predicates before launching fresh R1.',
            'Fresh current-main197-source/recipe/finite/autosave and original192 supervision; unchanged GPU0 permanent coordinator and available private resources.',
            'Fresh R1/C1/R2/C2 jobs, unique births/sessions, fixed5400s admissions, min50/all32/full tails/runtime valid; each candidate separately meets mean>=fresh reference*1.05 and preserves median.'
        ],
        prior_failed_study_pair=old_pair_pin, prior_failed_study_review=failed_pin,
        actual_producer_repair_registration=registration_pin,
        old_study_scores_excluded=True, old_reader_or_cohort_retried=False,
        candidate_selection='First preserved2259 normal autosave from forward-handoff preparation; selected now before any new quality observations. No main rewind.',
        created_unix_s=time.time())
    # Every original scientific denominator, time budget and candidate gate is
    # retained exactly. Only candidate/provenance/prerequisites are changed.
    original_pair = json.loads(h.checked(old_pair_pin).read_bytes())
    changed = {'state', 'candidate', 'prerequisites', 'created_unix_s', 'prior_failed_study_pair', 'prior_failed_study_review',
               'actual_producer_repair_registration', 'old_study_scores_excluded', 'old_reader_or_cohort_retried', 'candidate_selection'}
    require(all(pair[key] == value for key, value in original_pair.items() if key not in changed), 'Unselected pair/gate changed')
    pair_pin = h.put(NEW/'campaign-inputs-and-gates-precommit.json', pair)

    def publish(path, raw):
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        return h.pin(path)

    def replace(raw, old, new, count):
        require(raw.count(old) == count, 'Unexpected replacement count: '+old)
        return raw.replace(old, new)

    names = dict(native_runtime=('run_compiled_full_tail32_quality_v1.py', 'run_compiled_full_tail32_quality2259_v1.py'),
        native_controller=('control_compiled_full_tail32_quality_v1.py', 'control_compiled_full_tail32_quality2259_v1.py'),
        leg_reviewer=('read_compiled_quality32_original_v2.py', 'read_compiled_quality32_2259_original_v1.py'),
        campaign_assessor=('assess_quality32_campaign_v1.py', 'assess_quality32_2259_campaign_v1.py'),
        leg_preparer=('prepare_quality32_leg_v1.py', 'prepare_quality32_2259_leg_v1.py'))
    old_readiness_pin = h.pin(OLD/'new-original-quality-launch-readiness.json')
    require(old_readiness_pin['sha256'] == '717e861e6d66269162751b75871cf5a383012c637ad0a2e4531a494a57a86dee', 'Original source family changed')
    old_readiness = json.loads(h.checked(old_readiness_pin).read_bytes())
    sources = {}
    derivations = {}
    for role, (old_name, new_name) in names.items():
        entry = old_readiness[role]
        require(Path(entry['path']) == B/old_name, 'Original source role changed')
        original = h.checked(entry).read_text()
        raw = original
        if role in ('native_runtime', 'leg_reviewer', 'campaign_assessor', 'leg_preparer'):
            raw = replace(raw, old_pair_pin['sha256'], pair_pin['sha256'], 1)
        if role in ('native_runtime', 'leg_reviewer'):
            raw = replace(raw, '1741/2202', '1741/2259', 1)
            raw = replace(raw, original_pair['candidate']['policy']['sha256'], policy['sha256'], 1)
            old_clocks = dict(learner_frame_count=2202676281, training_steps=8863417, optimized_samples=34728761344, frame_count=4322965788)
            for key, value in old_clocks.items():
                raw = replace(raw, key+'='+str(value), key+'='+str(report['clocks'][key]), 1)
        if role in ('native_controller', 'leg_reviewer'):
            raw = replace(raw, names['native_runtime'][0], names['native_runtime'][1], 1)
        if role == 'leg_reviewer':
            raw = replace(raw, old_readiness['native_runtime']['sha256'], sources['native_runtime']['sha256'], 1)
        if role == 'leg_preparer':
            raw = replace(raw, 'quality1741-vs-normal2202-start-certified-', 'quality1741-vs-normal2259-after-JSON-', 1)
            raw = replace(raw, 'quality1741-2202-', 'quality1741-2259-json-', 1)
            raw = replace(raw, "unit='robotron-quality32-'+leg.lower()", "unit='robotron-quality32-2259json-'+leg.lower()", 1)
        compile(raw, str(B/new_name), 'exec')
        sources[role] = publish(B/new_name, raw.encode())
        # Changes to executable behavior are limited to source/pair/path pins in
        # these exact two validation/preparation functions; numerical and audit
        # logic, strict JSON decoding, cohort gates and lifecycle stay intact.
        def functions(source):
            tree = ast.parse(source)
            return {node.name: ast.dump(node, include_attributes=False) for node in tree.body if isinstance(node, ast.FunctionDef)}
        before, after = functions(original), functions(raw)
        allowed = {'native_controller': {'checked_config'}, 'leg_reviewer': {'validate_scope'}, 'leg_preparer': {'prepare'}}.get(role, set())
        require(set(before) == set(after) and {key for key in before if before[key] != after[key]} <= allowed, 'Unselected scientific function changed')
        patch = ''.join(difflib.unified_diff(original.splitlines(True), raw.splitlines(True), fromfile=old_name, tofile=new_name))
        derivations[role] = dict(original=entry, new=sources[role], changed_top_level_functions=sorted(key for key in before if before[key] != after[key]),
            patch=publish(NEW/(new_name+'.patch'), patch.encode()))
    guard.owner_and_files(main)
    result = h.put(NEW/'prospective-pair-and-source-construction-original01.json', dict(
        schema='robotron-distinct2259-after-JSON-pair-source-construction-v1', status='PAIR_AND_SOURCES_PREPARED_NO_COHORT_LAUNCH',
        builder=h.pin(__file__), pair=pair_pin, new_sources=sources, derivations=derivations,
        actual_producer_repair_registration=registration_pin, prospective_main_binding=registration['current_main_binding'],
        gates_and_denominators_unchanged=True, old_failed_case_excluded=True,
        candidate_2259_CPU_finite_phase_proof=insurance_pin, current_main_not_rewound=True,
        new_source_scope_guards_and_launch_readiness_still_required=True,
        quality_qualified=False, promotion=False, main_runtime_changed=False, created_unix_s=time.time()))
    print(json.dumps(dict(result=result, pair=pair_pin, sources=sources)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
