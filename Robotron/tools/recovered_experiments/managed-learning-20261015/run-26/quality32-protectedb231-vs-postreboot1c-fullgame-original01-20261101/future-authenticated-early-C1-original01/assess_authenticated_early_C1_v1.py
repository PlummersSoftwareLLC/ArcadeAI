"""Authenticate a future predeclared three-leg C1 failure decision.

Never schedules, cancels or promotes. Current active campaign is excluded.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CASE=G/'logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'
PAIR_SHA='9ea5d482628964107a0543665239c5147599e543c0e3ecd0d51b759e8c7e6b62'
ORDER=('R1','C1','R2')
NUMERIC_GATE_SHA='7c5ceadf9b155d2d80067729079d9eb75c6be38a9a6755f034ac3f68fcf1e2a4'


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def validate_future_precommit(job,h,read):
    case=Path(job['campaign_directory'])
    require(job['schema']=='robotron-predeclared-early-C1-three-leg-assessment-v1'
        and case.is_absolute() and case.resolve()==case and case.is_relative_to(G/'logs/managed-learning-20261015/run-26')
        and case!=CASE and job['pair']['sha256']!=PAIR_SHA
        and [r['role']for r in job['legs']]==list(ORDER),
        'Fresh future case and exact original first-three roles required; active campaign excluded')
    rule=read(job['predeclared_rule'])
    require(rule['schema']=='robotron-predeclared-fullgame-C1-failure-rule-v1'
        and rule['campaign_directory']==str(case) and rule['pair']==job['pair']
        and rule['required_closed_roles']==list(ORDER)
        and rule['stage']=='after_R2_review_before_C2_launch'
        and rule['skip_C2_only_if_C1_gate_failed']is True
        and rule['promotion_shortcut_allowed']is False
        and rule['assessor']==h.pin(__file__) and rule['numeric_gate']==job['numeric_gate']
        and job['numeric_gate']['sha256']==NUMERIC_GATE_SHA,
        'Exact future predeclared rule/numerical helper/source required')
    proof=read(job['numeric_CPU_proof'])
    require(proof['status']=='PASS_PROSPECTIVE_EXACT_C1_REJECTION_CPU_ONLY'
        and proof['tests_total']==39 and proof['source']==job['numeric_gate']
        and proof['original_kernel']==job['original_decision_kernel']
        and proof['exact_reverse_edit_proof']is True,
        'Qualified original numeric source derivation required')
    return case,rule


def assess(job,h,reader):
    inventory={}
    def read(pin,as_json=True):
        value=reader.read_pin(pin,as_json=as_json);inventory[pin['path']]=pin;return value
    case,rule=validate_future_precommit(job,h,read)
    pair=read(job['pair']);family=read(job['source_family'])
    require(family['pair']==job['pair']and family['early_C1_assessor']==h.pin(__file__)
        and family['early_C1_rule']==job['predeclared_rule']
        and family['early_C1_numeric']==job['numeric_gate']
        and family['decision_kernel']==job['original_decision_kernel'],
        'Fixed assessor/pair/source family differs')
    kernel=load('_fixed_fullgame_original_decision_kernel',h.checked(job['numeric_gate']))
    archive=load('_fixed_fullgame_assessment_archive',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    legs=[];numeric=None
    for item in job['legs']:
        role=item['role'];prepared=read(item['prepared']);native_job=read(prepared['job'])
        require(job['predeclared_rule']in native_job['inputs'],
            'This same immutable early-stop rule must have been a checked input of every original leg')
        require(Path(prepared['job']['path']).parent.is_relative_to(case)
            and prepared['pair']==job['pair']and native_job['quality_leg']==role
            and native_job['source_family_manifest']==job['source_family'],
            'Original leg namespace/role/pair/source family differs')
        native_close=read(item['native_closeout']);review_close=read(item['review_closeout'])
        require(native_close['status']=='PASS_ORIGINAL_FULLGAME_LEG_NATIVE_SCOPE_CLOSED'
            and review_close['status']=='PASS_ORIGINAL_FULLGAME_LEG_REVIEW_SCOPE_CLOSED'
            and native_close['actual_exit']==review_close['actual_exit']==0
            and native_close['original_Popen_reaped']is review_close['original_Popen_reaped']is True
            and native_close['all_original_controller_resources_closed']is review_close['all_original_controller_resources_closed']is True,
            'Each original native and independent review must close normally without replacement')
        report=read(review_close['report']);result=read(native_close['native_result'])
        require(report['status']=='PASS_SCIENTIFIC_FULLGAME_LEG_RAW64_PREFIX32_PERMIT_STOP32_BOUNDED_MAIN'
            and report['valid']is report['full_game_score_verified']is report['slot_permit_body_hash_replay_performed']is True
            and report['role']==role and report['pair']==job['pair']
            and report['native_job']==prepared['job']and report['native_result']==native_close['native_result']
            and report['original_native_closeout']==item['native_closeout']
            and report['review_runtime']==family['leg_reviewer']
            and result['complete']is True and result['errors']==[]and result['original_attempt']==1 and result['no_retry']is True,
            'Each original full-game leg must have the selected independent complete raw review')
        if numeric is None:numeric=report['numeric_policy']
        require(report['numeric_policy']==numeric and report['compile_report']['all_shapes_verified']==list(range(1,17)),
            'Original legs used different numerical policies or unverified compiled batches')
        owners={}
        for name,close in [('native',native_close),('review',review_close)]:
            owner=read(close['owner']);archive.archived_closure(read(close['closure']),owner,read,exit_zero=True)
            require(birth(owner['pid'])!=owner['starttime_ticks'],'An original closed-scope process remains')
            owners[name]=(owner['pid'],owner['starttime_ticks'],owner['invocation_id'])
        selected=pair['roles']['reference'if role.startswith('R')else'candidate']
        require(report['policy_sha256']==native_job['checkpoint']['sha256']==selected['policy']['sha256']
            and report['cohort']==result['before_intentional_stop'],'Original score cohort or frozen role policy differs')
        legs.append(dict(role=role,cohort=report['cohort'],cohort_selection=report['cohort_selection'],
            policy_sha256=report['policy_sha256'],native_identity=owners['native'],review_identity=owners['review'],
            evidence_verified=True,original_attempt=1,no_retry=True))
    decision=kernel.assess_first_candidate(legs,pair['roles']['reference']['policy']['sha256'],pair['roles']['candidate']['policy']['sha256'])
    require(decision['candidate_pool_used']is False,'Candidate pooling is forbidden')
    require('torch'not in sys.modules,'Independent assessment imported numerical runtime')
    return dict(status='PASS_AUTHENTICATED_PREDECLARED_C1_FAILURE_ASSESSMENT',valid=True,observed_unix_s=time.time(),
        pair=job['pair'],source_family=job['source_family'],original_decision_kernel=job['original_decision_kernel'],
        decision=decision,stop_remaining_legs=decision['stop_remaining_legs'],C2_required=decision['C2_required'],
        predeclared_rule=job['predeclared_rule'],promotion_eligible=False,promotion_performed=False,
        cancellation_or_scheduling_performed=False,C2_execution_status_not_assessed=True,
        inference_scope='Exact impossibility of promotion if fully reviewed C1 fails; passing C1 still requires C2. No population inferiority, confidence or throughput claim.',
        original_legs=job['legs'],inputs=list(inventory.values()))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    h=load('_fixed_fullgame_assessment_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader=load('_fixed_fullgame_assessment_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    jp=h.pin(args.job);require(jp['sha256']==args.job_sha256,'Exact original assessment job required')
    job=reader.read_pin(jp);h.checked(job['runtime'])
    try:report=assess(job,h,reader)
    except Exception:report=dict(status='FAIL_AUTHENTICATED_PREDECLARED_C1_ASSESSMENT',valid=False,error=traceback.format_exc(),promotion_eligible=False,promotion_performed=False)
    report['original_job']=jp;report['runtime']=job['runtime']
    out=h.put(job['report'],report);print(json.dumps(dict(status=report['status'],report=out,error=report.get('error'))),flush=True)
    return 0 if report['valid']else 1


if __name__=='__main__':raise SystemExit(main())
