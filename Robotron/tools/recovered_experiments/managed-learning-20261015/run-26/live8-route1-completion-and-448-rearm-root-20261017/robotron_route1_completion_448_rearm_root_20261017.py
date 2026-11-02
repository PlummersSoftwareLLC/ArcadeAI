#!/usr/bin/env python3
"""Adopt the complete failed-CE comparison honestly, then rearm448 unchanged."""
import datetime,hashlib,json,os,subprocess,time,urllib.request
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';B=G/'logs/managed-learning-20261015';RUN=B/'run-26'
D=RUN/'live8-route1-completion-and-448-rearm-root-20261017';O=RUN/'live8-route1-sameGPU-diagnostic-reviewed1-20261017';E=RUN/'live8-route1-root-execution-reviewed1-20261017'
U='robotron-checkpoint-448M-run26-post-route1-20261017.service'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=10)
def main():
    sp=B/'state.json';old=sp.read_bytes();s=json.loads(old);gate=s['next_checkpoint'];assert gate['status']=='paused_for_route1_owned_window' and gate['target_learner_frames']==452629023 and gate['original_deadline_unix_s']==1792245505.2003896
    phase=json.loads((O/'route1/phase-result.json').read_text());parent=json.loads((O/'result.json').read_text());release=json.loads((E/'root-result-review-and-release.json').read_text());cleanup=json.loads((E/'root-owned-terminal-cleanup-review.json').read_text())
    assert phase['status']==parent['status']=='OBSERVATIONS_COMPLETE' and phase['qualification_pass'] is False
    assert phase['selected_original_index']==1 and phase['attempted_forward_routes']==['original4','conditional5'] and len(phase['routes'])==2
    assert release['status']=='PASS' and release['original_exit']==0 and release['original_invocation']=='9add1bb8b1064f0ba2150536bfd70fc3' and cleanup['owned_cleanup_complete'] and cleanup['child_actual_returncode']==0
    rows=[]
    for name,row in phase['comparisons'].items():
        assert row['tolerance']==dict(rtol=.0002,atol=.00002)
        rows.append(dict(comparison=name,violations=row['violations'],rows=4096,max_abs=row['max_abs'],comparison_pass=row['passed']))
    for row in phase['routes']:
        assert row['update_guard_counts']==dict(optimizer_step=0,scaler_step=0,scaler_update=0) and row['model_before']==row['model_after']
    for unit in [U,gate['unit'],'robotron-snapshot-smoke-live8-route1-reviewed1-20261017.service']:assert 'LoadState=not-found' in call(['systemctl','--user','show',unit,'-p','LoadState']).stdout
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as f:api=json.load(f)
    assert api['client_count']==192 and api['training_enabled'] and not api['measurement_active'] and api['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth' and api['learner_frame_count']<452629023 and api['host_pipeline']['learning_exposure']['optimizer']['process_id']==4140916
    assert not (G/'models_dqn/managed_save.request.json').exists() and not Path(gate['output']).exists() and not (G/'models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    protected=G/'models_dqn/managed-incumbents/fresh3-384M-confirmed.pt';assert sha(protected)=='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963' and protected.stat().st_mode&0o222==0 and protected.stat().st_nlink==1
    helper=G/'tools/checkpoint_at_frame.py';assert sha(helper)=='5d8d7ab2456f2d6a8ad89327596cec654feae9a66db98190a07c87063a3be2b1'
    remaining=gate['original_deadline_unix_s']-time.time();assert remaining>60
    D.mkdir();(D/'state-before.json').write_bytes(old)
    command=['systemd-run','--user','--unit='+U,'--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=100%','--property=MemoryMax=256M','--property=TasksMax=16','--property=RuntimeMaxSec='+str(int(remaining)+20),'--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(R),'--property=StandardOutput=append:'+str(D/'stdout.txt'),'--property=StandardError=append:'+str(D/'stderr.txt'),str(R/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',str(helper),'--target','452629023','--tag','fresh3-448M','--experiment',api['managed_experiment'],'--output',gate['output'],'--timeout',str(remaining)]
    save(D/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=command,original_deadline_unix_s=gate['original_deadline_unix_s'],remaining_timeout_s=remaining,previous_gate=gate,route1_cleanup=pin(E/'root-owned-terminal-cleanup-review.json'),source_sha256=sha(Path(__file__)),quality_not_launched=True))
    out=call(command);save(D/'root-launch-return.json',dict(returncode=out.returncode,stdout=out.stdout,stderr=out.stderr));assert out.returncode==0,out.stderr
    raw=call(['systemctl','--user','show',U]).stdout;f=dict(x.split('=',1) for x in raw.splitlines() if '=' in x);pid=int(f['MainPID']);assert pid>0 and f['ActiveState']=='active' and f['InvocationID']
    ticks=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19];(D/'new-running-unit-show.txt').write_text(raw)
    new=dict(gate,status='waiting',unit=U,pid=pid,start_ticks=ticks,invocation_id=f['InvocationID'],launch_receipt=str(D/'root-launch-intent.json'),launch_receipt_sha256=sha(D/'root-launch-intent.json'),rearmed_after_route1=True,previous_waiter=dict(unit=gate['unit'],pid=gate['pid'],invocation_id=gate['invocation_id'],pause_receipt=gate['pause_receipt']))
    completed=dict(s['active_diagnostic_job'],status='fixed_route_observations_complete',original_parent_exit=0,original_child_exit=0,source_phase=pin(O/'route1/phase-result.json'),parent_result=pin(O/'result.json'),original_terminal_release=pin(E/'root-result-review-and-release.json'),root_cleanup_review=pin(E/'root-owned-terminal-cleanup-review.json'),comparison_pass=phase['comparison_pass'],qualification_pass=False,CE_results=rows,prior_all8_CE_failure_unchanged=True,cause='Two fixed calls cannot exclude nondeterminism or uniquely identify an ABI or capture/device/profile cause',units_released=True,main_training_unchanged=True)
    s['completed_diagnostic_jobs'].append(completed);s['active_diagnostic_job']=None;s['next_checkpoint']=new;s['next_screen']['next_checkpoint']=new;s['next_screen']['status']='384M_confirmed_route1_complete_448M_waiting';s['stage']='run26_384M_confirmed_main_training_route1_complete_448M_waiting'
    goal=s['optimization_goal'];goal.update(active_diagnostic_job=None,last_completed_diagnostic=completed,next_checkpoint=new,latest_progress='Fixed same-GPU route1 diagnostic complete, original8 CE failures retained. Owned cleanup complete; main192 and448watcher restored at original target/deadline. Next priority448 capture and fresh quality.')
    goal['future_kl_priority_calibration'].update(state='sameGPU_route1_complete_review_required_448_quality_priority',active_route1=None,completed_route1=completed)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat();receipt=dict(status='ROUTE1_OBSERVATIONS_COMPLETE_GOAL_CONTINUES',utc=now,completed=completed,next_checkpoint=new,current_learner_frames=api['learner_frame_count'],protected384_sha256=sha(protected),incumbent_history_entries=len(s['incumbent_history']),goal_active=True,next_action='Review fixed route1 observations without rescuing original8 failure;448 capture/CPU validation/freshRCRC quality next')
    save(D/'root-continuation-receipt.json',receipt);goal['last_progress_receipt']=str(D/'root-continuation-receipt.json');goal['last_progress_receipt_sha256']=sha(D/'root-continuation-receipt.json');goal['last_review_utc']=now;goal['last_review_learner_frames']=api['learner_frame_count'];s['updated_utc']=now;s['updated_unix_s']=time.time();assert sp.read_bytes()==old
    temp=sp.with_name('.state.route1-complete-448-rearm-root.tmp')
    with temp.open('x') as stream:json.dump(s,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,sp)
    with (D/Path(__file__).name).open('xb') as stream:stream.write(Path(__file__).read_bytes());os.fchmod(stream.fileno(),0o444)
    print(json.dumps(dict(status=receipt['status'],new_waiter=new,CE_results=rows,learner_frames=api['learner_frame_count'],receipt_sha256=goal['last_progress_receipt_sha256'])))
if __name__=='__main__':main()
