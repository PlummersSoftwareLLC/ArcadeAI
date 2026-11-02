"""Prospectively correct unexecuted review/assessment bindings; keep R1 running.

No game, reviewer, assessor or service is started. Original immutable sources,
jobs, configurations and the stopped observer outcome are preserved unchanged.
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
B = G/'tools/startup_policy_journal_proposal'
R = G/'logs/managed-learning-20261015/run-26'
N = R/'quality32-protected1741-vs-normal2259-after-JSON-original01-preparation-20261022'
A = N/'prospective-unexecuted-review197-amendment-original01'
SUFFIX = 'prospective197-original01'


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
    spec = importlib.util.spec_from_file_location('_queued197_amendment_h', B/'run_full_policy_startup_v3.py')
    h = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = h
    spec.loader.exec_module(h)
    require(h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'Helper changed')

    def birth(pid):
        try:
            return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
        except FileNotFoundError:
            return None

    old_intent_pin = h.pin(N/'original-sequence-observer-intent.json')
    old_intent = json.loads(h.checked(old_intent_pin).read_bytes())
    old_outcome_pin = h.pin(N/'original-sequence-observer-outcome.json')
    require(old_outcome_pin['sha256'] == 'ba092a44b5fe63bde800ec1b834555f59936fdd18ae3c63e65df1de2eb59e9a8', 'Stopped observer outcome changed')
    old_outcome = json.loads(h.checked(old_outcome_pin).read_bytes())
    require(old_outcome['status'] == 'SEQUENCING_STOPPED_NO_NEW_ACTIONS' and old_outcome['original_records'] == []
            and birth(old_intent['pid']) != old_intent['birth'], 'Old scheduler must be terminal before replacement preparation')
    for path in ('01-reference/independent-review-controller-original-launch.json',
                 'campaign-assessment-controller-original-launch.json', '02-candidate/job.json'):
        require(not (N/path).exists(), 'A future scientific action already executed: '+path)
    first = N/'01-reference'
    owner_pin = h.pin(first/'execution-original01/root-original-identity.json')
    owner = json.loads(h.checked(owner_pin).read_bytes())
    controller_pin = h.pin(first/'controller-original-child.json')
    controller = json.loads(h.checked(controller_pin).read_bytes())
    require(birth(owner['pid']) == owner['starttime_ticks'] and birth(controller['pid']) == controller['starttime_ticks'],
            'Same original R1 native/controller must continue live')
    old_ready_pin = h.pin(N/'new-original-quality-launch-readiness.json')
    require(old_ready_pin['sha256'] == 'ffb1bdb2d50d057bf80d325b3218239ad201b5a989e05f83aadb271cd7c3f9b9', 'Original readiness changed')
    old_ready = json.loads(h.checked(old_ready_pin).read_bytes())
    job_pin = h.pin(first/'job.json')
    main_binding = json.loads(h.checked(json.loads(h.checked(job_pin).read_bytes())['main_binding']).read_bytes())
    guard = h.load('_queued197_amendment_guard', R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
    guard.owner_and_files(main_binding)
    require(len(main_binding['held_hashes']) == 197, 'All197 current holds required')
    require(not A.exists(), 'One original prospective amendment preparation only')
    A.mkdir(mode=0o700)

    def publish(path, raw):
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        return h.pin(path)

    def replace(raw, before, after, count=1):
        require(raw.count(before) == count, 'Unexpected prospective replacement count: '+before)
        return raw.replace(before, after)

    derivations = {}
    originals = {}
    def source(role, path, substitutions):
        entry = old_ready[role]
        raw = h.checked(entry).read_text()
        original = raw
        for before, after, count in substitutions:
            raw = replace(raw, before, after, count)
        compile(raw, str(path), 'exec')
        pin = publish(path, raw.encode())
        derivations[role] = dict(original=entry, proposed=pin, patch=publish(A/(path.name+'.patch'),
            ''.join(difflib.unified_diff(original.splitlines(True), raw.splitlines(True),
                fromfile=Path(entry['path']).name, tofile=path.name)).encode()))
        originals[role] = original
        return pin

    reviewer = source('leg_reviewer', B/'read_compiled_quality32_2259_original_v2.py', [
        ("len(main['held_hashes'])==196", "len(main['held_hashes'])==197", 1)])
    assessor = source('campaign_assessor', B/'assess_quality32_2259_campaign_v2.py', [
        ("len(main_sources)==196", "len(main_sources)==197", 1),
        ("cpucfg_pin=h.pin(root/'independent-review-controller-config.json');cpucfg=read(cpucfg_pin)",
         "cpucfg_name=('independent-review-controller-config-prospective197-original01.json' if role=='R1' else 'independent-review-controller-config.json')\n            cpucfg_pin=h.pin(root/cpucfg_name);cpucfg=read(cpucfg_pin)", 1)])
    old_review_config_pin = h.pin(first/'independent-review-controller-config.json')
    old_review_config = json.loads(h.checked(old_review_config_pin).read_bytes())
    review_config = copy.deepcopy(old_review_config)
    review_config['argv'][3] = reviewer['path']
    review_config['argv'][-1] = reviewer['sha256']
    ctl = h.load('_queued197_amendment_ctl', G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    review_config['pins'] = [*review_config['pins'], ctl.pin(reviewer['path'])]
    review_config_pin = h.put(first/'independent-review-controller-config-prospective197-original01.json', review_config)
    ctl.checked_config(review_config_pin['path'])
    # R1's native job, admission, policy, scores, acceptance and review job remain
    # byte-identical. Only its never-launched reviewer/config are amended.
    ready = copy.deepcopy(old_ready)
    ready['leg_reviewer'] = reviewer
    ready['campaign_assessor'] = assessor
    replacements = {old_ready['leg_reviewer']['path']: reviewer, old_ready['campaign_assessor']['path']: assessor}
    ready['inputs'] = [replacements.get(entry['path'], entry) for entry in old_ready['inputs']]
    ready['inputs'] += [old_ready_pin, old_intent_pin, old_outcome_pin, review_config_pin]
    ready['prospective_unexecuted_review_amendment'] = dict(
        prior_readiness=old_ready_pin, prior_observer_intent=old_intent_pin, prior_observer_terminal=old_outcome_pin,
        R1_original_native_job=job_pin, R1_original_native_owner=owner_pin, R1_original_controller=controller_pin,
        superseded_unexecuted_R1_review_config=old_review_config_pin, selected_R1_review_config=review_config_pin,
        all197_holds_required=True, any_review_or_final_assessment_executed=False,
        native_or_scientific_retry=False, score_or_qualification_gate_change=False)
    ready['created_unix_s'] = time.time()
    ready_pin = h.put(N/'new-original-quality-launch-readiness-prospective197-original01.json', ready)
    old_assessment_job_pin = h.pin(N/'campaign-assessment-job.json')
    assessment_job = json.loads(h.checked(old_assessment_job_pin).read_bytes())
    assessment_job['launch_readiness_precommit'] = ready_pin
    assessment_job['sources']['leg_reviewer'] = reviewer
    assessment_job_pin = h.put(N/'campaign-assessment-job-prospective197-original01.json', assessment_job)
    old_assessment_config_pin = h.pin(N/'campaign-assessment-controller-config.json')
    assessment_config = json.loads(h.checked(old_assessment_config_pin).read_bytes())
    assessment_config['argv'] = ['/usr/bin/python3.12', '-I', '-B', assessor['path'], '--execute',
        '--job', assessment_job_pin['path'], '--job-sha256', assessment_job_pin['sha256'], '--source-sha256', assessor['sha256']]
    assessment_config['pins'] = [ctl.pin(entry['path']) for entry in ready['inputs']+[ready_pin, assessment_job_pin, assessor]]
    assessment_config_pin = h.put(N/'campaign-assessment-controller-config-prospective197-original01.json', assessment_config)
    ctl.checked_config(assessment_config_pin['path'])
    seq_old_pin = h.pin(B/'sequence_quality32_campaign_v2.py')
    require(seq_old_pin['sha256'] == 'a50663314ea202db0d51508a091b5800ecc5057c4c18396ab013c06b9a72c6a2', 'Original observer source changed')
    seq_raw = h.checked(seq_old_pin).read_text()
    seq_original = seq_raw
    for before, after, count in [
        ('sequence-events-original01', 'sequence-events-prospective197-original01', 1),
        ('sequence-state-backups-original01', 'sequence-state-backups-prospective197-original01', 2),
        ('sequencing-control.json', 'sequencing-control-prospective197-original01.json', 1),
        ('original-sequence-observer-intent.json', 'original-sequence-observer-prospective197-original01-intent.json', 2),
        ('original-sequence-observer-outcome.json', 'original-sequence-observer-prospective197-original01-outcome.json', 1),
        ("self.check_new_actions();cfg_pin=self.h.pin(directory/'independent-review-controller-config.json')",
         "self.check_new_actions();cfg_name=('independent-review-controller-config-prospective197-original01.json' if role=='R1' else 'independent-review-controller-config.json')\n        cfg_pin=self.h.pin(directory/cfg_name)", 1),
        ("first_owner=self.read(self.precommit['first_R1_native_owner'])",
         "prior=self.read(self.precommit['prior_observer_terminal'])\n        prior_intent=self.read(self.precommit['prior_observer_intent'])\n        require(prior['status']=='SEQUENCING_STOPPED_NO_NEW_ACTIONS' and prior['original_records']==[]\n            and birth(prior_intent['pid'])!=prior_intent['birth'],'Prior observer must be terminal without scientific actions')\n        first_owner=self.read(self.precommit['first_R1_native_owner'])", 1)]:
        seq_raw = replace(seq_raw, before, after, count)
    sequence_path = B/'sequence_quality32_2259_prospective197_v1.py'
    compile(seq_raw, str(sequence_path), 'exec')
    sequence_pin = publish(sequence_path, seq_raw.encode())
    derivations['sequencer'] = dict(original=seq_old_pin, proposed=sequence_pin, patch=publish(A/(sequence_path.name+'.patch'),
        ''.join(difflib.unified_diff(seq_original.splitlines(True), seq_raw.splitlines(True),
            fromfile=Path(seq_old_pin['path']).name, tofile=sequence_path.name)).encode()))
    for role, names in [('leg_reviewer', ('decode',)), ('campaign_assessor', ('metrics', 'assess_validated_cohorts'))]:
        # The strict JSON decoder lives in the unchanged games auditor. Here,
        # bind all pre-existing pure validation/numerical methods exactly.
        before = {n.name:ast.dump(n, include_attributes=False) for n in ast.parse(originals[role]).body if isinstance(n, ast.FunctionDef)}
        after = {n.name:ast.dump(n, include_attributes=False) for n in ast.parse(h.checked(derivations[role]['proposed']).read_bytes()).body if isinstance(n, ast.FunctionDef)}
        allowed = {'review'} if role == 'leg_reviewer' else {'execute'}
        require(set(before) == set(after) and {name for name in before if before[name] != after[name]} <= allowed,
                'A scientific validation/numerical/CLI function changed')
    guard.owner_and_files(main_binding)
    require(h.pin(first/'job.json') == job_pin and birth(owner['pid']) == owner['starttime_ticks'], 'Running R1 changed during preparation')
    receipt = h.put(A/'preparation.json', dict(schema='robotron-prospective-unexecuted-review197-binding-amendment-v1',
        state='PREPARED_PENDING_NEW_GUARDS_NO_SUCCESSOR_OBSERVER_STARTED', builder=h.pin(__file__),
        prior_observer_intent=old_intent_pin, prior_observer_terminal=old_outcome_pin,
        old_readiness=old_ready_pin, new_readiness=ready_pin, derivations=derivations,
        R1_native_job_unchanged=job_pin, R1_native_owner=owner_pin, R1_controller=controller_pin,
        old_unexecuted_R1_review_config=old_review_config_pin, new_R1_review_config=review_config_pin,
        old_unexecuted_assessment_job=old_assessment_job_pin, new_assessment_job=assessment_job_pin,
        old_unexecuted_assessment_config=old_assessment_config_pin, new_assessment_config=assessment_config_pin,
        successor_sequence_source=sequence_pin, scientific_thresholds_and_all_games_unchanged=True,
        original_reviews_or_final_assessments_executed=0, native_or_review_retry=False,
        current197_main_holds_and_original192_unchanged=True, main_runtime_changed=False, created_unix_s=time.time()))
    print(json.dumps(dict(preparation=receipt, readiness=ready_pin, successor=sequence_pin)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
