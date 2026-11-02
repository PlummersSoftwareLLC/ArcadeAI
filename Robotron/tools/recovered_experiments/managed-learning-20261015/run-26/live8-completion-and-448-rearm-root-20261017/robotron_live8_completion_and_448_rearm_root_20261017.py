#!/usr/bin/env python3
"""Adopt completed observation evidence and rearm only the existing 448M gate."""
import datetime,hashlib,json,os,subprocess,time,urllib.request
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';BASE=G/'logs/managed-learning-20261015';RUN=BASE/'run-26'
D=RUN/'live8-completion-and-448-rearm-root-20261017'
U='robotron-checkpoint-448M-run26-post-live8v4-20261017.service'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=10)
def pin(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def main():
    sp=BASE/'state.json';old=sp.read_bytes();s=json.loads(old);gate=s['next_checkpoint'];assert gate['status']=='paused_for_live8_owned_window_v4' and gate['target_learner_frames']==452629023 and gate['tag']=='fresh3-448M'
    c=RUN/'live8-owned-maintenance-reviewed4-20261017';result=json.loads((c/'result.json').read_text());assert result['status']=='COMPLETE' and result['capture_complete'] and not result['manual_recovery_required']
    release=RUN/'live8-owned-maintenance-root-execution-reviewed4-20261017/root-result-review-and-release.json';rel=json.loads(release.read_text());assert rel['status']=='PASS' and rel['original_exit']==0
    audit=RUN/'live8-owned-maintenance-reviewed4-independent-saved-result-audit-20261017/review-receipt.json';assert sha(audit)=='5c73ef6520c36ff26ddf7334782ae7407692c566f4d526d24e087c6725feaaf4'
    h=RUN/'live8-success-current-health-root-reviewed2-20261017/root-current-health-PASS.json';health=json.loads(h.read_text());assert health['status']=='PASS'
    analysis=RUN/'live8-actual-CE-offline-analysis-reviewed1-20261017/analysis.json';a=json.loads(analysis.read_text());assert a['status']=='OBSERVATIONAL_DESCRIPTIONS_COMPLETE' and len(a['attempts'])==8 and a['outcomes']==dict(applied_admission=8,amp_skipped=0)
    ar=RUN/'live8-actual-CE-analysis-root-execution-reviewed1-20261017/root-result-review-and-release.json';assert json.loads(ar.read_text())['status']=='PASS'
    for unit in [gate['unit'],'robotron-live8-maintenance-reviewed4-20261017.service','robotron-live8-actualCE-analysis-reviewed1-20261017.service',U]:assert 'LoadState=not-found' in call(['systemctl','--user','show',unit,'-p','LoadState']).stdout,unit
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as f:v=json.load(f)
    assert v['learner_frame_count']<gate['target_learner_frames'] and v['client_count']==192 and v['training_enabled'] and not v['measurement_active'] and v['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth'
    assert v['host_pipeline']['learning_exposure']['optimizer']['process_id']==4140916
    assert not (G/'models_dqn/managed_save.request.json').exists() and not Path(gate['output']).exists() and not (G/'models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    helper=G/'tools/checkpoint_at_frame.py';assert sha(helper)=='5d8d7ab2456f2d6a8ad89327596cec654feae9a66db98190a07c87063a3be2b1'
    remaining=gate['original_deadline_unix_s']-time.time();assert remaining>60
    D.mkdir();(D/'state-before.json').write_bytes(old)
    cmd=['systemd-run','--user','--unit='+U,'--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=100%','--property=MemoryMax=256M','--property=TasksMax=16','--property=RuntimeMaxSec='+str(int(remaining)+20),'--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(R),'--property=StandardOutput=append:'+str(D/'waiter-stdout.txt'),'--property=StandardError=append:'+str(D/'waiter-stderr.txt'),str(R/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',str(helper),'--target','452629023','--tag','fresh3-448M','--experiment',v['managed_experiment'],'--output',gate['output'],'--timeout',str(remaining)]
    save(D/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=cmd,original_deadline_unix_s=gate['original_deadline_unix_s'],remaining_timeout_s=remaining,previous_owned_pause=gate['pause_receipt'],helper_sha256=sha(helper),protected384_unchanged=True,quality_not_launched=True,source_sha256=sha(Path(__file__))))
    out=call(cmd);save(D/'root-launch-return.json',dict(returncode=out.returncode,stdout=out.stdout,stderr=out.stderr));assert out.returncode==0,out.stderr
    raw=call(['systemctl','--user','show',U]).stdout;fields=dict(x.split('=',1) for x in raw.splitlines() if '=' in x);pid=int(fields['MainPID']);assert pid>0 and fields['ActiveState']=='active' and fields['InvocationID'];ticks=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
    (D/'new-waiter-running-show.txt').write_text(raw)
    new=dict(gate,status='waiting',unit=U,pid=pid,start_ticks=ticks,invocation_id=fields['InvocationID'],launch_receipt=str(D/'root-launch-intent.json'),launch_receipt_sha256=sha(D/'root-launch-intent.json'),rearmed_after_successful_live8=True,previous_waiter=dict(unit=gate['unit'],pid=gate['pid'],invocation_id=gate['invocation_id'],pause_receipt=gate['pause_receipt']))
    completed=dict(s['active_maintenance'],status='COMPLETE',original_exit=0,result=pin(c/'result.json'),original_terminal_release=pin(release),independent_saved_metadata_source_review=pin(audit),actual_capture_rows=8,applied_admission=8,amp_skipped=0,original_failed_v3_preserved=True,actual_payload_bytes=4062272904,actual_CE_analysis=pin(analysis),actual_CE_original_terminal=pin(ar),current_health=pin(h),units_released=True,learning_rule_changed=False,observer_dormant_after8=True)
    if s.get('last_completed_maintenance') is not None and not any(x.get('invocation_id')==s['last_completed_maintenance'].get('invocation_id') for x in s['maintenance_job_history']):s['maintenance_job_history'].append(s['last_completed_maintenance'])
    s['last_completed_maintenance']=completed;s['active_maintenance']=None;s['active_maintenance_job']=None
    s['pending_live8_acquisition'].update(status='actual_v4_original8_acquired_CPU_analysis_complete',actual_live8_capture=completed,actual_CE_observational_analysis=pin(analysis),conditional_target_reconstruction='next_source_preparation_only',model_priority_recipe_change=False)
    s['next_checkpoint']=new;s['next_screen']['next_checkpoint']=new;s['next_screen']['status']='384M_confirmed_live8_observation_complete_448M_waiting';s['stage']='run26_384M_confirmed_live8_observed_main_training_448M_waiting'
    prior=s['active_runtime'];s['runtime_history'].append(dict(prior,archived_reason='Superseded runtime identity after audited v3 normal recovery and v4 observation-only boot; original receipts preserved'))
    runtime=dict(prior);runtime.update(trainer_pid=4140916,trainer_start_ticks='31570251',trainer_invocation_id='cf4f26d3c5b84d9ab1302ded3a073519',status='training192_held_recipe_after_live8_observation',resume_learner_frame_count=435450662,resume_optimized_samples=7113928704,resume_training_steps=2090214,resume_fleet_frame_count=871030534,hof_transitions_restored=87496,ephof_transitions_restored=393201,bank_source_sha256=health['source_hashes'][str(G/'Scripts/dqn/replay_buffer.py')],agent_source_sha256=health['source_hashes'][str(G/'Scripts/dqn/agent.py')],socket_server_sha256=health['source_hashes'][str(G/'Scripts/dqn/socket_server.py')],startup_audit=str(audit),startup_audit_sha256=sha(audit),current_health=pin(h),live8_observation=completed,learning_rule_change=False)
    s['active_runtime']=runtime
    now=datetime.datetime.now(datetime.timezone.utc).isoformat();goal=s['optimization_goal'];goal.update(status='active',active_maintenance_job=None,last_completed_maintenance=completed,next_checkpoint=new,last_review_utc=now,last_review_learner_frames=v['learner_frame_count'],last_readonly_health=pin(h),latest_progress='Original first8 captured and actualCE CPU analysis complete; 192 actors advancing,384 protected,448M gate rearmed at original deadline; conditional CE/KL priority investigation next')
    receipt=dict(status='COMPLETED_OBSERVATION_CONTINUING_OPTIMIZATION',utc=now,capture=completed,next_checkpoint=new,current_learner_frames=v['learner_frame_count'],next_experiment='Conditional same-PRE recomputed CE/entropy/KL and weighting calibration before any learning treatment',confirmation_criteria_unchanged=True,goal_active=True,protected384_unchanged=True,incumbent_history_entries=len(s['incumbent_history']),draw_unknown_label_scope='Inherited sampler unknown labels remain in original analysis; outer outcomes are eight executed applied admissions; no claim of actual per-row entropy/KL or measured gradients')
    save(D/'root-continuation-receipt.json',receipt);goal['last_progress_receipt']=str(D/'root-continuation-receipt.json');goal['last_progress_receipt_sha256']=sha(D/'root-continuation-receipt.json');s['updated_utc']=now;s['updated_unix_s']=time.time()
    assert sp.read_bytes()==old
    temp=BASE/'.state.live8-completion-448-rearm-root.tmp'
    with temp.open('x') as f:json.dump(s,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,sp)
    with (D/Path(__file__).name).open('xb') as f:f.write(Path(__file__).read_bytes());os.fchmod(f.fileno(),0o444)
    print(json.dumps(dict(status=receipt['status'],next_waiter=new,root_receipt_sha256=sha(D/'root-continuation-receipt.json'))))
if __name__=='__main__':main()
