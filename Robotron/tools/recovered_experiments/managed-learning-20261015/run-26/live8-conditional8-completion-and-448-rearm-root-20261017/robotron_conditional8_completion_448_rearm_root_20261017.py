#!/usr/bin/env python3
"""Adopt the complete failed-CE comparison honestly, then rearm448 unchanged."""
import datetime,hashlib,json,os,subprocess,time,urllib.request
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';B=G/'logs/managed-learning-20261015';RUN=B/'run-26'
D=RUN/'live8-conditional8-completion-and-448-rearm-root-20261017';O=RUN/'live8-conditional8-reconstruction-reviewed1-20261017';E=RUN/'live8-conditional8-root-execution-reviewed1-20261017'
U='robotron-checkpoint-448M-run26-post-conditional8-20261017.service'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=10)
def main():
    sp=B/'state.json';old=sp.read_bytes();s=json.loads(old);gate=s['next_checkpoint'];assert gate['status']=='paused_for_conditional8_owned_window' and gate['target_learner_frames']==452629023 and gate['original_deadline_unix_s']==1792245505.2003896
    phase=json.loads((O/'recompute8/phase-result.json').read_text());parent=json.loads((O/'result.json').read_text());release=json.loads((E/'root-result-review-and-release.json').read_text());cleanup=json.loads((E/'root-owned-terminal-cleanup-review.json').read_text())
    assert phase['status']==parent['status']=='OBSERVATIONS_COMPLETE' and phase['comparison_pass'] is False and parent['comparison_pass'] is False and phase['qualification_pass'] is False and len(phase['attempts'])==8
    assert release['status']=='PASS' and release['original_exit']==0 and release['original_invocation']=='0224a6cfea854b50ab5974c64bff4ced' and cleanup['owned_cleanup_complete'] and cleanup['child_actual_returncode']==0
    rows=[]
    for index,row in enumerate(phase['attempts'],1):
        assert row['index']==index and row['comparison_pass'] is False and row['ce_comparison']['tolerance']==dict(rtol=.0002,atol=.00002) and row['update_guard_counts']==dict(optimizer_step=0,scaler_step=0,scaler_update=0)
        rows.append(dict(index=index,violations=row['ce_comparison']['violations'],rows=4096,max_abs=row['ce_comparison']['max_abs'],comparison_pass=False,rng_post_changed=row['rng_observations']['post_changed']))
    for unit in [U,gate['unit'],'robotron-snapshot-smoke-live8-conditional8-reviewed1-20261017.service']:assert 'LoadState=not-found' in call(['systemctl','--user','show',unit,'-p','LoadState']).stdout
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as f:api=json.load(f)
    assert api['client_count']==192 and api['training_enabled'] and not api['measurement_active'] and api['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth' and api['learner_frame_count']<452629023 and api['host_pipeline']['learning_exposure']['optimizer']['process_id']==4140916
    assert not (G/'models_dqn/managed_save.request.json').exists() and not Path(gate['output']).exists() and not (G/'models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    protected=G/'models_dqn/managed-incumbents/fresh3-384M-confirmed.pt';assert sha(protected)=='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963' and protected.stat().st_mode&0o222==0 and protected.stat().st_nlink==1
    helper=G/'tools/checkpoint_at_frame.py';assert sha(helper)=='5d8d7ab2456f2d6a8ad89327596cec654feae9a66db98190a07c87063a3be2b1'
    remaining=gate['original_deadline_unix_s']-time.time();assert remaining>60
    D.mkdir();(D/'state-before.json').write_bytes(old)
    command=['systemd-run','--user','--unit='+U,'--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=100%','--property=MemoryMax=256M','--property=TasksMax=16','--property=RuntimeMaxSec='+str(int(remaining)+20),'--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(R),'--property=StandardOutput=append:'+str(D/'stdout.txt'),'--property=StandardError=append:'+str(D/'stderr.txt'),str(R/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',str(helper),'--target','452629023','--tag','fresh3-448M','--experiment',api['managed_experiment'],'--output',gate['output'],'--timeout',str(remaining)]
    save(D/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=command,original_deadline_unix_s=gate['original_deadline_unix_s'],remaining_timeout_s=remaining,previous_gate=gate,conditional8_cleanup=pin(E/'root-owned-terminal-cleanup-review.json'),source_sha256=sha(Path(__file__)),quality_not_launched=True))
    out=call(command);save(D/'root-launch-return.json',dict(returncode=out.returncode,stdout=out.stdout,stderr=out.stderr));assert out.returncode==0,out.stderr
    raw=call(['systemctl','--user','show',U]).stdout;f=dict(x.split('=',1) for x in raw.splitlines() if '=' in x);pid=int(f['MainPID']);assert pid>0 and f['ActiveState']=='active' and f['InvocationID']
    ticks=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19];(D/'new-running-unit-show.txt').write_text(raw)
    new=dict(gate,status='waiting',unit=U,pid=pid,start_ticks=ticks,invocation_id=f['InvocationID'],launch_receipt=str(D/'root-launch-intent.json'),launch_receipt_sha256=sha(D/'root-launch-intent.json'),rearmed_after_conditional8=True,previous_waiter=dict(unit=gate['unit'],pid=gate['pid'],invocation_id=gate['invocation_id'],pause_receipt=gate['pause_receipt']))
    completed=dict(s['active_diagnostic_job'],status='observations_complete_original_CE_comparison_failed_all8',original_parent_exit=0,original_child_exit=0,source_phase=pin(O/'recompute8/phase-result.json'),parent_result=pin(O/'result.json'),original_terminal_release=pin(E/'root-result-review-and-release.json'),root_cleanup_review=pin(E/'root-owned-terminal-cleanup-review.json'),comparison_pass=False,qualification_pass=False,per_attempt_CE_results=rows,total_CE_violations=sum(x['violations'] for x in rows),total_CE_rows=32768,cause='Unestablished; different physical GPU and conditional compilation are potential factors, not attributed causes',units_released=True,main_training_unchanged=True)
    s['completed_diagnostic_jobs'].append(completed);s['active_diagnostic_job']=None;s['pending_live8_acquisition']['conditional_target_reconstruction']=completed;s['next_checkpoint']=new;s['next_screen']['next_checkpoint']=new;s['next_screen']['status']='384M_confirmed_conditional8_CE_mismatch_retained_448M_waiting';s['stage']='run26_384M_confirmed_main_training_conditional8_complete_448M_waiting'
    goal=s['optimization_goal'];goal.update(active_diagnostic_job=None,last_completed_diagnostic=completed,next_checkpoint=new,latest_progress='Conditional8 completed with all8 original-tolerance CE comparisons failed; all retained, no rescue. Owned cleanup complete, main192healthy and448waiter rearmed originaldeadline. CPU four-readout sensitivity is next, no treatment/quality claim.')
    goal['future_kl_priority_calibration'].update(state='conditional8_complete_all8_original_CE_mismatch_CPU_sensitivity_pending',active_conditional8=None,completed_conditional8=completed)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat();receipt=dict(status='CONDITIONAL8_COMPLETE_CE_MISMATCH_RETAINED_GOAL_CONTINUES',utc=now,completed=completed,next_checkpoint=new,current_learner_frames=api['learner_frame_count'],protected384_sha256=sha(protected),incumbent_history_entries=len(s['incumbent_history']),goal_active=True,next_action='Execute reviewed CPU four-readout tests and all8 conditional sensitivities; preserve each original failed CE mask and select next evidence-backed experiment')
    save(D/'root-continuation-receipt.json',receipt);goal['last_progress_receipt']=str(D/'root-continuation-receipt.json');goal['last_progress_receipt_sha256']=sha(D/'root-continuation-receipt.json');goal['last_review_utc']=now;goal['last_review_learner_frames']=api['learner_frame_count'];s['updated_utc']=now;s['updated_unix_s']=time.time();assert sp.read_bytes()==old
    temp=sp.with_name('.state.conditional8-complete-448-rearm-root.tmp')
    with temp.open('x') as stream:json.dump(s,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,sp)
    with (D/Path(__file__).name).open('xb') as stream:stream.write(Path(__file__).read_bytes());os.fchmod(stream.fileno(),0o444)
    print(json.dumps(dict(status=receipt['status'],new_waiter=new,CE_violations=completed['total_CE_violations'],learner_frames=api['learner_frame_count'],receipt_sha256=goal['last_progress_receipt_sha256'])))
if __name__=='__main__':main()
