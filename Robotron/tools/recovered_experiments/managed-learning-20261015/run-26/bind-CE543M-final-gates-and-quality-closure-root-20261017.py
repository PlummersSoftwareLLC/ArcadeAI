"""Root-only metadata binding after the original four cohorts and reviews."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import time

RUN=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
CAMPAIGN=RUN.parent/'quality-448M-vs-CE543M-20261017'
OUT=RUN/'CE543M-quality-final-fixed-gates-and-closure-preparation-root-20261017'
PLAN_SHA='25aaded11bf956b715cc5fb58be1901d236a30444e74253594461f8d11c00d75'
BINDING_SHA='f43719ed4dc60a4c275a7414995aa79d0f40062c76964200cf8700a8abe50dc3'
HELPER=RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--c2-independent',type=Path)
    parser.add_argument('--c2-review-sha256')
    parser.add_argument('--math-independent',type=Path)
    parser.add_argument('--math-review-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no imports/evidence/output/actions; genuine final review PINs required');return
    assert args.c2_independent and args.math_independent and args.c2_review_sha256 and args.math_review_sha256
    assert not OUT.exists()
    assert hashlib.sha256(HELPER.read_bytes()).hexdigest()=='d525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'
    spec=importlib.util.spec_from_file_location('_root_final_quality_metadata',HELPER)
    ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)
    def load(path,digest=None):
        raw,pin=ops.read_file(path)
        if digest is not None:assert pin['sha256']==digest,str(path)
        return json.loads(raw),pin
    c2review,c2pin=load(args.c2_independent,args.c2_review_sha256)
    mathreview,mathpin=load(args.math_independent,args.math_review_sha256)
    assert str(c2review['status']).startswith('PASS') and c2review['leg']==4 and c2review['actual_plan_sha256']==PLAN_SHA
    assert str(mathreview['status']).startswith('PASS')
    state_path=RUN.parent/'state.json';before,beforepin=ops.read_file(state_path);state=json.loads(before)
    assert state['active_quality_job']['plan_sha256']==PLAN_SHA and len(state['active_quality_job']['original_leg_audits'])==3
    plan,planpin=load(CAMPAIGN/'plan.json',PLAN_SHA)
    campaign,campaignpin=load(CAMPAIGN/'status.json');summary,summarypin=load(CAMPAIGN/'summary.json')
    assert campaign['state']=='finished' and campaign['plan_sha256']==summary['plan_sha256']==PLAN_SHA
    assert summary['stop_signal'] is None
    original,showraw=ops.show('robotron-quality-448M-vs-CE543M-20261017.service')
    assert (original['MainPID'],original['ExecMainPID'],original['InvocationID'],original['ExecMainCode'],original['ExecMainStatus'],original['NRestarts'],original['Result'])==('0','894289','4bcb24eb3bb344da9dc67b483a8ee946','1','0','0','success')
    assert ops.process_start(894289)!=34316549
    startup_names=[('R1','reviewed3'),('C1','reviewed1'),('R2','reviewed1'),('C2','reviewed1')]
    entries=[];legs=[];receipts=[];reviews=[];executions=[];audits=[]
    for index in range(1,5):
        role='reference' if index in (1,3) else 'candidate'
        prefix=f'CE543M-quality-original-row-leg{index:02d}-audit'
        eroot=RUN/(prefix+'-root-execution-reviewed1-20261017')
        receipt,rpin=load(CAMPAIGN/f'{index:02d}-{role}'/'receipt.json')
        audit,apin=load(RUN/prefix/'review-receipt.json');execution,epin=load(eroot/'root-result-review-and-release.json')
        finished,fpin=load(eroot/'original-finished-leg.json')
        old=state['active_quality_job']['original_leg_audits'][index-1] if index<4 else None
        review_path=old['independent_review']['path'] if old else args.c2_independent
        review,vpin=load(review_path,old['independent_review']['sha256'] if old else args.c2_review_sha256)
        label,version=startup_names[index-1]
        startup,spin=load(RUN/f'CE543M-quality-launch-and-{label}-startup-root-{version}-20261017'/f'actual-parent-{label}-all16-main192-source-GPU-and-API.json')
        assert campaign['legs'][index-1]==finished and finished['state']=='finished' and finished['returncode']==0
        assert receipt['valid'] is True and receipt['complete'] is True and receipt['active'] is False
        assert receipt['count']==receipt['started']==len(receipt['rows'])>=50 and receipt['pending']==receipt['abandoned']==0
        assert {row['client_slot'] for row in receipt['rows']}==set(range(4096,4112))
        assert all(row['complete'] and row['eligible'] and row['end_unix_s']<=receipt['timeout_snapshot_unix_s'] for row in receipt['rows'])
        assert receipt['checkpoint_sha256']==plan['checkpoints'][role]['sha256']
        assert execution['source_pins_held'] is True and execution['original_archived_before_release'] is True
        assert execution['audit_receipt']['sha256']==apin['sha256'] and audit['leg']==index
        assert str(review['status']).startswith('PASS') and review['leg']==index and review['actual_plan_sha256']==PLAN_SHA
        assert review['original_evaluator']['pid']==finished['pid']
        assert all(review['original_audit'][k]==execution[v] for k,v in [('pid','original_pid'),('starttime_ticks','original_starttime_ticks'),('invocation_id','original_invocation'),('exec_code','original_exec_code'),('exit_status','original_exit'),('result','original_result')])
        assert all(any((x['path'],x['sha256'],x['bytes'])==(pin['path'],pin['sha256'],pin['bytes']) for x in review['key_artifacts']) for pin in (apin,epin))
        if index==2:
            assert audit['valid'] is False and execution['original_exit']==2 and old['audit_disposition']=='root_accepted_narrow_manual_review'
            disposition='root_accepted_narrow_manual_review'
            _,manualpin=load(old['root_manual_acceptance']['path'],'4565a2cbf5b5eebc6abec1e199ef6525bc420a0bd698b2b80889df0fea5e2d70')
        else:
            assert audit['valid'] is True and execution['original_exit']==0 and execution['original_result']=='success'
            assert audit['receipt_sha256']==rpin['sha256'] and audit['plan_sha256']==PLAN_SHA
            disposition='original_audit_valid'
        actors=[{key:x[key] for key in ('slot','pid','starttime_ticks')} for x in startup[label+'_actors']]
        evaluator={key:startup['evaluator'][key] for key in ('pid','starttime_ticks')}
        assert evaluator['pid']==finished['pid'] and len(actors)==16
        legs.append(dict(index=index,receipt=rpin,finished_record=fpin,audit_receipt=apin,audit_execution=epin,
            independent_review=vpin,startup_observation=spin,evaluator=evaluator,actors=actors))
        scores=[row['score'] for row in receipt['rows']]
        stats=dict(count=len(scores),score_sum=sum(scores),mean=statistics.mean(scores),median=statistics.median(scores))
        entries.append(dict(leg=index,role=role,status='PASS_ORIGINAL_AND_INDEPENDENT_REVIEW' if index!=2 else old['status'],
            original_evaluator=review['original_evaluator'],finished_record=fpin,receipt=rpin,audit_receipt=apin,audit_execution=epin,
            independent_review=vpin,statistics=stats,completion_tail=audit.get('completion_tail',old.get('completion_tail') if old else None),
            original_audit_exit=execution['original_exit'],audit_disposition=disposition))
        if index==2:entries[-1]['root_manual_acceptance']=manualpin
        receipts.append(receipt);reviews.append(vpin);executions.append(execution);audits.append(apin)
    ref_scores=[row['score'] for n in (0,2) for row in receipts[n]['rows']]
    reference=dict(count=len(ref_scores),score_sum=sum(ref_scores),mean=statistics.mean(ref_scores),median=statistics.median(ref_scores))
    assert (reference['count'],reference['score_sum'],reference['median'])==(149,60029300,424575)
    checks=[]
    for n in (1,3):
        stats=entries[n]['statistics'];passed_mean=20*stats['score_sum']*reference['count']>=21*reference['score_sum']*stats['count']
        passed_median=stats['median']>=reference['median']
        check=dict(index=n+1,**stats,mean_gain_percent=(stats['mean']/reference['mean']-1)*100,
            mean_pass=passed_mean,median_pass=passed_median)
        recorded=summary['candidate_checks'][len(checks)]
        assert recorded['index']==check['index'] and recorded['mean']==stats['mean'] and recorded['median']==stats['median']
        assert recorded['mean_pass']==passed_mean and recorded['median_pass']==passed_median
        checks.append(check)
    qualified=all(c['mean_pass'] and c['median_pass'] for c in checks)
    outcome='qualified_improvement' if qualified else 'not_improved'
    assert campaign['outcome']==summary['outcome']==outcome and summary['qualified_improvement']==qualified
    binding,bindingpin=load(RUN/'CE543M-quality-binding-root-preparation-20261017/root-quality-binding-job.json',BINDING_SHA)
    timer,_=load(RUN/'CE543M-quality-durable-launch-20261017/original-timer-show-after-carrier-reaped.json')
    timer_inv=ops.fields(timer['stdout'])['InvocationID']
    OUT.mkdir();utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    gate=ops.publish(OUT/'root-original-four-cohort-fixed-gates.json',dict(status='PASS_ALL4_ORIGINALS_INDEPENDENT_REVIEWS_AND_FIXED_GATES',utc=utc,
        plan_sha256=PLAN_SHA,binding_job_sha256=BINDING_SHA,campaign_outcome=outcome,qualification_pass=qualified,
        fixed_fresh_reference=reference,required_mean_exact='63030765/149',individual_candidate_checks=checks,
        original_leg_audits=entries,independent_final_math_review=mathpin,C1_manual_integrity_acceptance=manualpin,
        source_freeze_released=False,promotion=False,candidate_pool_used_for_gates=False,no_retries_or_extensions=True,
        original_parent_terminal=ops.publish(OUT/'original-parent-terminal-show-command.json',showraw)))
    acceptance=ops.publish(OUT/'root-explicit-all4-quality-acceptance.json',dict(status='PASS_ROOT_EXPLICIT_ALL4_ORIGINAL_QUALITY_ACCEPTANCE',
        plan_sha256=PLAN_SHA,binding_job_sha256=BINDING_SHA,accepted_leg_indices=[1,2,3,4],campaign_outcome=outcome,
        leg_receipt_sha256=[x['receipt']['sha256'] for x in legs],audit_original_exit=[x['original_exit'] for x in executions],
        audit_receipt_sha256=[x['sha256'] for x in audits],audit_disposition=[x['audit_disposition'] for x in entries],
        independent_review_sha256=[x['sha256'] for x in reviews],root_gate=gate,independent_final_math_review=mathpin,
        C1_original_exit2_and_failed_report_preserved=True,source_freeze_released=False,promotion=False))
    job=ops.publish(OUT/'quality-terminal-closure-job.json',dict(schema='robotron-CE543M-quality-owned-closure-job-v1',binding_job=bindingpin,
        timer_invocation_id=timer_inv,terminal_status=campaignpin,terminal_summary=summarypin,root_acceptance=acceptance,
        legs=legs,output_directory=str(RUN/'CE543M-quality-terminal-closure-root-reviewed1-20261017')))
    ops.write_bytes(OUT/'state-before-final-all4-gates-adoption.json',before)
    q=state['active_quality_job'];g=state['optimization_goal']
    q.update(state='finished',outcome=outcome,current_phase='finished_pending_owned_cleanup',original_leg_audits=entries,
        last_review_utc=utc,final_root_gate=gate,root_all4_acceptance=acceptance,source_freeze_released=False)
    g.update(current_campaign_phase='all4_confirmed_pending_owned_cleanup',current_campaign_outcome=outcome,
        completed_current_campaign_leg_audits=entries,latest_root_progress=gate,actual_running_wait=None,last_review_utc=utc,
        final_quality_all4_gates=gate,final_quality_all4_acceptance=acceptance)
    g['completed_leg_audit_preparation'].update(actual_leg_audit_executions=4,status='ALL4_ORIGINAL_AUDITS_REVIEWED_C1_MANUAL_EXIT2_PRESERVED')
    g['prepared_quality_parent_closure'].update(status='ACTUAL_FINAL_JOB_BOUND_PENDING_ROOT_CLOSURE',actual_final_job=job,actual_closure=None,source_freeze_released=False)
    state.update(stage='run26_CE543M_all4_confirmation_PASS_pending_owned_cleanup_and_publication',updated_utc=utc,updated_unix_s=time.time(),last_review_utc=utc)
    raw=(json.dumps(state,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<1<<20 and state_path.read_bytes()==before
    temporary=state_path.with_name('.state-CE543M-final-gates-root.tmp')
    with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,state_path);ops.sync_directory(state_path.parent)
    print(json.dumps(dict(status='PASS_FINAL_ROOT_ALL4_ACCEPTANCE_AND_CLOSURE_JOB_BOUND',gate=gate,acceptance=acceptance,closure_job=job,reference=reference,candidate_checks=checks)))

if __name__=='__main__':main()
