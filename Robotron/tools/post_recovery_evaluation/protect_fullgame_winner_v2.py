"""Verify a recovered-round winner and reuse exclusive immutable publication.

Default inert. Publication needs the actual successful original assessment CPU
closure, all eight original game/review scopes and both independent quota64
gates. This never restores the learner or adopts the next reference epoch.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

HERE=Path(__file__).resolve().parent
PUBLISHER_SHA='1dca577cf4a09da0c9f4cf90e103335fc8259498eb7f98b8b65bfdf328f425c5'


def pipeline():
    spec=importlib.util.spec_from_file_location('_fullgame_protection_pipeline',HERE/'fullgame_review_pipeline_v3.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def validate_assessment_header(report,p):
    p.require(report['schema']=='robotron-recovered-round-fullgame-study-assessment-v1'
        and report['status']=='FOUR_ORIGINAL_COMPLETE_GAME_LEGS_QUALIFIED'
        and report['full_game_quality_qualified']is True and report['effective_complete_game_minimum']==64
        and report['promotion']is report['causal_learning_speed_gain_established']is report['useful_throughput_gain_established']is False,
        'Actual qualified fullgame assessment required; screening/engineering/failure cannot protect a winner')
    decision=report['original_quota64_decision']
    p.require(decision['all_candidate_gates_passed']is True and decision['candidate_pool_used']is False
        and decision['reference_roles']==['R1','R2']
        and all(decision['per_leg'][role]['count']==64 for role in p.ORDER)
        and all(decision['independent_candidates'][role]['passed']is decision['independent_candidates'][role]['mean_at_least_105_percent']
            is decision['independent_candidates'][role]['median_preserved']is True for role in ('C1','C2')),
        'Each independent64-game candidate mean/median gate must pass')


def protected_files(destination,h):
    return [h.pin(path)for path in sorted(destination.iterdir())
        if path.is_file()and(path.name.endswith('.pt')or path.name.endswith('.pt.json'))]


def prepare(assessment,closeout,output,label):
    p=pipeline();h=p.helpers();rp=h.pin(assessment.resolve());report=p.read(rp);validate_assessment_header(report,p)
    cp=h.pin(closeout.resolve());closed=p.read(cp)
    p.require(closed['schema']=='robotron-recovered-fullgame-final-assessment-original-closeout-v1'
        and closed['status']=='PASS'and closed['assessment']==rp,'Actual original final-assessment closeout required')
    p.require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',label)is not None,'Simple new protected label required')
    destination=p.ROOT/'models_dqn/managed-incumbents';output=output.resolve()
    p.require(output.is_relative_to(p.BASE)and output.parent.is_dir()and not output.exists(),'Exclusive original protection preparation required')
    p.require(not(destination/(label+'.pt')).exists()and not(destination/(label+'.pt.json')).exists(),'Never overwrite a protected label')
    prepared=p.read(report['native_prepared']);state=json.loads((p.ROOT/'logs/managed-learning-20261015/state.json').read_bytes())
    p.require(prepared['reference_epoch']==state['optimization_goal']['next_fixed_reference_epoch'],'Fixed-reference epoch was superseded')
    output.mkdir(mode=0o700);prior=h.put(output/'all-prior-protected-files.json',dict(schema='robotron-prior-protected-file-snapshot-v1',
        destination=str(destination),files=protected_files(destination,h)))
    job=dict(schema='robotron-recovered-fullgame-winner-protection-job-v1',assessment_report=rp,assessment_closeout=cp,
        previous_reference_epoch=prepared['reference_epoch'],prior_protected_files=prior,destination=str(destination),label=label,
        output=str(output/'runtime'),unit='robotron-fullgame-winner-protection-'+rp['sha256'][:12]+'-original01.service',
        original_attempt=1,no_retry=True,engineering_only=False,source=h.pin(Path(__file__).resolve()))
    job['inputs']=[rp,cp,prior,*p.read(prior)['files'],job['source'],h.pin(HERE/'fullgame_review_pipeline_v3.py'),
        h.pin(HERE/'assess_fullgame_study_v4.py'),h.pin(HERE/'sequence_fullgame_study_v4.py'),
        h.pin(HERE/'fullgame_review_entry_v2.py'),job['previous_reference_epoch']]
    jp=h.put(output/'job.json',job);verify(job,jp)
    return jp


def verify(job,job_pin):
    p=pipeline();h=p.helpers();evidence={job_pin['path']:job_pin['sha256']}
    def read(pin,as_json=True):
        value=p.read(pin,as_json=as_json);evidence[pin['path']]=pin['sha256'];return value
    def held(pin):
        h.checked(pin);evidence[pin['path']]=pin['sha256']
    p.require(job['schema']=='robotron-recovered-fullgame-winner-protection-job-v1'and job['engineering_only']is False
        and job['original_attempt']==1 and job['no_retry']is True and job['source']==h.pin(Path(__file__).resolve()),
        'Production original winner-protection job/source required')
    report=read(job['assessment_report']);validate_assessment_header(report,p)
    close=read(job['assessment_closeout'])
    p.require(close['schema']=='robotron-recovered-fullgame-final-assessment-original-closeout-v1'and close['status']=='PASS'
        and close['assessment']==job['assessment_report']and close['actual_exit']==0
        and close['all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified']is True
        and close['source']==h.pin(HERE/'sequence_fullgame_study_v4.py'), 'Actual original successful final-assessment scope required')
    preparation=read(close['assessment_preparation']);commit=read(preparation['review_precommit']);prepared=read(commit['native_prepared'])
    p.require(commit['engineering_only']is prepared['engineering_only']is False
        and report['review_precommit']==preparation['review_precommit']and report['native_prepared']==commit['native_prepared']
        and report['source']==commit['assessor']==h.pin(HERE/'assess_fullgame_study_v4.py')
        and report['pipeline']==commit['pipeline']==h.pin(HERE/'fullgame_review_pipeline_v3.py')
        and commit['review_entry']==h.pin(HERE/'fullgame_review_entry_v2.py')
        and commit['leg_reviewer']==h.pin(HERE/'review_fullgame_rounds_v3.py'), 'Exact original production assessment/review source joins required')
    cfg_pin=preparation['config'];cfg=read(cfg_pin)
    expected=['/usr/bin/python3.12','-I','-B',report['source']['path'],'--assess','--precommit',preparation['review_precommit']['path'],
        '--precommit-sha256',preparation['review_precommit']['sha256'],'--output',preparation['prospective_assessment_output']]
    p.require(cfg['argv']==expected and close['original_config']==cfg_pin
        and job['assessment_report']['path']==preparation['prospective_assessment_output'], 'Actual original assessor argv/output differs')
    final=p.owned_scope(cfg_pin,h)
    p.require(final['owner_pin']==close['original_owner']and final['closure_pin']==close['original_closure'], 'Final original owner/closure differs')
    carrier=read(close['original_controller_result'])
    p.require(type(carrier['actual_exit'])is int and carrier['actual_exit']==0 and carrier['original_attempt']==1
        and carrier['no_retry']is True and carrier['live_registration_errors']==[]and carrier['closure']==final['closure_pin'],
        'Original final controller failed, retried or selected other evidence')
    for pin in cfg['pins']:p.require(p.cpu_controller(h).pin(pin['path'])==pin,'Original final CPU launch input changed')
    pair=read(report['pair']);p.require(prepared['pair']==report['pair']and pair['engineering_only']is False
        and pair['minimum_complete_games_each']==64 and pair['all32_slots']is pair['full_tails']is pair['no_candidate_pooling']
        is pair['no_scientific_retry']is True,'Exact64/all32/full-tail/no-pooling/no-retry pair required')
    state=json.loads((p.ROOT/'logs/managed-learning-20261015/state.json').read_bytes())
    p.require(pair['protected_reference_epoch']==prepared['reference_epoch']==job['previous_reference_epoch']
        ==state['optimization_goal']['next_fixed_reference_epoch'],'Protected fixed reference changed before winner publication')
    epoch=read(job['previous_reference_epoch']);p.require(epoch['reference_policy']==pair['reference']['policy'],'Fixed protected reference differs')
    producer=p.load('_fullgame_protection_actual_screen_eligibility',HERE/'prepare_fullgame_study_v2.py')
    producer.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
    p.require(pair['screen_assessment']==prepared['screen_assessment'],'Original passing screen differs')
    p.require([row['leg']for row in report['original_scopes']]==p.ORDER
        and [case['leg']for case in prepared['cases']]==[case['leg']for case in commit['cases']]==p.ORDER,
        'Exact original four-leg assessment membership/order required')
    reviewer=p.load('_fullgame_protection_original_leg_predicates',HERE/'review_fullgame_rounds_v3.py');legs=[];previous_end=0
    for case,rc,proof in zip(prepared['cases'],commit['cases'],report['original_scopes']):
        role=case['leg'];subject=read(case['native_job']);review_job=read(rc['review_job']);review_cfg=read(rc['review_config'])
        p.require(rc['native_job']==case['native_job']and rc['leg']==proof['leg']==role,'Exact original native/review membership differs')
        p.validate_packet(case,review_job,review_cfg,h)
        ns=p.owned_scope(review_job['controller_config'],h,native=True);rs=p.owned_scope(rc['review_config'],h)
        p.require(ns['owner_pin']==proof['native_owner']and ns['closure_pin']==proof['native_closure']
            and rs['owner_pin']==proof['review_owner']and rs['closure_pin']==proof['review_closure']
            and commit['created_monotonic_s']<=ns['interval'][0]and previous_end<=ns['interval'][0]
            and ns['interval'][1]<=rs['interval'][0]<=rs['interval'][1]<=final['interval'][0],
            'Original runtime/review/assessment scope identity or sequence differs')
        previous_end=rs['interval'][1]
        native=read(proof['native_result']);policy,cohort=reviewer.validate_runtime_result(native,subject)
        selected=pair['reference'if role.startswith('R')else'candidate']
        p.require(subject['checkpoint']==selected['policy']and subject['quality_pair_precommit']==report['pair']
            and subject['expected_policy_clocks']==selected['saved_clocks'],'Original frozen policy/clocks/pair differ')
        reviewed=read(proof['independent_review'])
        p.require(reviewed['valid']is reviewed['full_game_score_verified']is True
            and reviewed['quality_qualified']is reviewed['promotion']is False and reviewed['actual_runtime_exit']==reviewed['actual_controller_exit']==0
            and reviewed['review_job']==rc['review_job']and reviewed['original_native_job']==case['native_job']
            and reviewed['original_result']==proof['native_result']and reviewed['original_owner']==ns['owner_pin']
            and reviewed['original_closure']==ns['closure_pin']and reviewed['policy']==policy
            and reviewed['quality_leg']==role and reviewed['quality_pair_precommit']==report['pair'],
            'Actual independent original complete-game review differs')
        for pin in reviewed['artifacts']:
            if set(pin['identity'])=={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}:held(pin)
            else:read(pin,False)
        for name,pin in native['journal'].items():
            held(pin);p.require(pin['sha256']==reviewed['original_games']['original_payload_sha256'][name],'Original game/start/life bytes changed')
        legs.append(dict(role=role,policy_sha256=policy['checkpoint_sha256'],cohort=cohort,cohort_selection=reviewed['cohort_selection'],
            evidence_verified=True,original_attempt=1,no_retry=True,native_identity=[ns['owner'][key]for key in ('pid','starttime_ticks','invocation_id')],
            review_identity=[rs['owner'][key]for key in ('pid','starttime_ticks','invocation_id')]))
    recomputed=p.numerical_decision(legs,pair['reference']['policy']['sha256'],pair['candidate']['policy']['sha256'],h)
    p.require(recomputed['original_quota64_decision']==report['original_quota64_decision']and recomputed['full_game_quality_qualified']is True,
        'Both original candidate gates must recompute identically without pooled rescue')
    prior=read(job['prior_protected_files']);destination=p.ROOT/'models_dqn/managed-incumbents'
    p.require(prior['schema']=='robotron-prior-protected-file-snapshot-v1'and prior['destination']==job['destination']==str(destination)
        and destination.resolve(strict=True)==destination and destination.stat().st_uid==os.getuid()and prior['files'],
        'Exact owned protected destination and prior-policy integrity snapshot required')
    for pin in prior['files']:
        p.require(Path(pin['path']).parent==destination and pin['identity']['mode']=='0o444'and pin['identity']['nlink']==1,
            'Prior protected policy/metadata path or identity differs');held(pin)
    held(pair['candidate']['policy']);held(pair['reference']['policy'])
    held(job['source']);held(report['source']);held(report['pipeline']);held(commit['review_entry']);held(commit['leg_reviewer'])
    for path,sha in evidence.items():p.require(h.pin(path)['sha256']==sha,'Original protection evidence changed during verification')
    p.require('torch'not in sys.modules,'Protection imported numerical runtime')
    return dict(schema='robotron-recovered-fullgame-protected-winner-v1',root_protection_job=job_pin,
        original_assessment_report=job['assessment_report'],original_assessment_closeout=job['assessment_closeout'],
        fixed_input_pair=report['pair'],assessment=recomputed['original_quota64_decision'],candidate_source=pair['candidate']['policy'],
        reference=pair['reference'],candidate_saved_clocks=pair['candidate']['saved_clocks'],evidence_sha256=evidence,
        previous_reference_epoch=job['previous_reference_epoch'],prior_protected_files=job['prior_protected_files'],
        original_scientific_audit_rerun=False,managed_incumbent_updated=False,live_learner_restored=False,
        learning_speed_gain_verified=False,useful_throughput_gain_verified=False,next_reference_epoch_adopted=False)


def publication_module(p,h):
    path=p.ROOT/'tools/startup_policy_journal_proposal/protect_certified_quality32_current_lr125_winner_v1.py'
    p.require(h.pin(path)['sha256']==PUBLISHER_SHA,'Validated copy/fsync/exclusive-link publication source changed')
    module=p.load('_fullgame_unchanged_atomic_publisher',path)
    module.verify=lambda job,jp,reader:verify(job,jp)
    return module


def execute(args):
    p=pipeline();h=p.helpers();p.require(h.pin(Path(__file__).resolve())['sha256']==args.source_sha256,'Actual protection source differs')
    jp=h.pin(args.job.resolve());p.require(jp['sha256']==args.job_sha256,'Actual original protection job differs');job=p.read(jp)
    p.require(job['schema']=='robotron-recovered-fullgame-winner-protection-job-v1'and job['engineering_only']is False
        and job['source']==h.pin(Path(__file__).resolve()),'Engineering or foreign jobs cannot execute winner publication')
    if not args.publish:return verify(job,jp)
    p.require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and'torch'not in sys.modules,'Bounded CPU-only publication required')
    import subprocess
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if'='in line)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',Restart='no',NRestarts='0')
    p.require(all(fields.get(k)==v for k,v in expected.items()),'Actual bounded2CPU/4GiB/180s publication scope differs')
    for pin in job['inputs']:h.checked(pin)
    output=Path(job['output']);p.require(not output.exists(),'Original protection output already consumed; no retry')
    output.mkdir(mode=0o700)
    h.put(output/'original-publication-intent.json',dict(original_job=jp,source=job['source'],actual_PID=os.getpid(),
        actual_scope=fields,original_attempt=1,no_retry=True,created_unix_s=time.time()))
    module=publication_module(p,h)
    result=module.publish(job,jp,None)
    final=Path(result['protected_checkpoint']);metadata=final.with_name(final.name+'.json')
    h.put(output/'report.json',dict(schema='robotron-recovered-fullgame-protection-original-CPU-result-v1',status='PASS',
        original_job=jp,actual_PID=os.getpid(),actual_scope=fields,protected_checkpoint=h.pin(final),protected_metadata=h.pin(metadata),
        original_assessment_report=job['assessment_report'],original_assessment_closeout=job['assessment_closeout'],
        publisher_source=h.pin(Path(module.__file__)),Torch_imported=False,GPU_or_MAME_launched=False,
        quality_qualified=False,promotion=False,next_reference_epoch_adopted=False))
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--prepare',action='store_true');a.add_argument('--execute',action='store_true')
    a.add_argument('--publish',action='store_true');a.add_argument('--assessment',type=Path);a.add_argument('--closeout',type=Path)
    a.add_argument('--output',type=Path);a.add_argument('--label');a.add_argument('--job',type=Path);a.add_argument('--job-sha256');a.add_argument('--source-sha256');args=a.parse_args()
    if args.prepare:print(json.dumps(prepare(args.assessment,args.closeout,args.output,args.label)),flush=True)
    elif args.execute:
        result=execute(args);print(json.dumps(dict(quality_qualified=result['assessment']['all_candidate_gates_passed'],protected_checkpoint=result.get('protected_checkpoint'),managed_incumbent_updated=False,live_learner_restored=False,next_reference_epoch_adopted=False)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
