"""Assess the four original closed full-game legs using the established gate.

The original numerical kernel is loaded unchanged. C1/C2 are never pooled;
fresh R1/R2 form the fixed reference. This file never promotes or changes Main.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CASE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101')
PAIR_SHA='ce9ae1cb76965f5712984876815f6f43fd5f0b44b6cc1c5ba760548c817ccd05'
ORDER=('R1','C1','R2','C2')


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def assess(job,h,reader):
    inventory={}
    def read(pin,as_json=True):
        value=reader.read_pin(pin,as_json=as_json);inventory[pin['path']]=pin;return value
    require(job['schema']=='robotron-fixed-b231-1c-four-leg-assessment-v1'and job['pair']['sha256']==PAIR_SHA
        and Path(job['campaign_directory'])==CASE and [r['role']for r in job['legs']]==list(ORDER),
        'Exact original four-role campaign required')
    pair=read(job['pair']);family=read(job['source_family'])
    require(family['pair']==job['pair']and family['campaign_assessor']==h.pin(__file__)
        and family['decision_kernel']==job['original_decision_kernel'],
        'Fixed assessor/pair/source family differs')
    kernel=load('_fixed_fullgame_original_decision_kernel',h.checked(job['original_decision_kernel']))
    archive=load('_fixed_fullgame_assessment_archive',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    legs=[];numeric=None
    for item in job['legs']:
        role=item['role'];prepared=read(item['prepared']);native_job=read(prepared['job'])
        require(Path(prepared['job']['path']).parent.is_relative_to(CASE)
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
    decision=kernel.assess_validated_cohorts(legs,pair['roles']['reference']['policy']['sha256'],pair['roles']['candidate']['policy']['sha256'])
    require(decision['candidate_pool_used']is False,'Candidate pooling is forbidden')
    require('torch'not in sys.modules,'Independent assessment imported numerical runtime')
    return dict(status='PASS_ORIGINAL_FIXED_FOUR_LEG_ASSESSMENT',valid=True,observed_unix_s=time.time(),
        pair=job['pair'],source_family=job['source_family'],original_decision_kernel=job['original_decision_kernel'],
        decision=decision,all_candidate_gates_passed=decision['all_candidate_gates_passed'],
        promotion_eligible=decision['all_candidate_gates_passed'],promotion_performed=False,
        inference_scope='Observed fixed-protocol full-game confirmation. No causal learning-rate/throughput or independently calibrated population-confidence claim.',
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
    except Exception:report=dict(status='FAIL_ORIGINAL_FIXED_FOUR_LEG_ASSESSMENT',valid=False,error=traceback.format_exc(),promotion_eligible=False,promotion_performed=False)
    report['original_job']=jp;report['runtime']=job['runtime']
    out=h.put(job['report'],report);print(json.dumps(dict(status=report['status'],report=out,error=report.get('error'))),flush=True)
    return 0 if report['valid']else 1


if __name__=='__main__':raise SystemExit(main())
