"""Independently close selected-family checks and register four fresh quality legs."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023'
B=G/'tools/startup_policy_journal_proposal'
D=R/'currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024'
T=R/'quality32-protected1741-vs-currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024'
V=T/'selected-family-source-guards-CPU-original01'
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
h=load(B/'run_full_policy_startup_v3.py','_dedicated_register_h')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_dedicated_register_reader')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_dedicated_register_arc')
closer=load(P/'independent_component_closeout_v3.py','_dedicated_register_close')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
scope=closer.closeout(V,h,arc,read,0)
rp=h.pin(V/'output-original01/report.json');report=read(rp)
assert report['tests']==8 and len(report['negative_checks'])==20
ready_pin=h.pin(T/'new-original-quality-launch-readiness.json');ready=read(ready_pin)
pair_pin=ready['quality_pair'];pair=read(pair_pin)
assert report['readiness']==ready_pin and report['quality_qualified'] is False
assert pair['candidate']['saved_clocks']['learner_frame_count']==2739279553
assert pair['candidate']['policy']['sha256']=='95726b361f01bceab95bd5deaf6f5534dd1e8d4e7335e38904ae5ca3ee49987d'
for pin in ready['inputs']:h.checked(pin)
for folder in ('01-reference','02-candidate','03-reference','04-candidate'):
    assert not (T/folder).exists()
assert not (T/'original-fresh-sequence-observer-original01-intent.json').exists()
pp=h.put(V/'independent-original-selected-family-and-CPU-closeout.json',dict(
    schema='robotron-selected-dedicated-observer-quality-family-independent-closeout-v1',
    actual_scope=scope,original_report=rp,tests=8,negative_checks=20,
    readiness=ready_pin,quality_pair=pair_pin,source_family=ready['source_family_manifest'],
    all_selected_sources_and_tested_observer_pins_verified=True,
    all_original_game_helpers_and_confirmation_math_unchanged=True,
    original_endpoint_CPU_scope_verified=True,all_four_original_legs_absent=True,
    quality_qualified=False,created_unix_s=time.time()))
monitor=h.pin(D/'postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],capture_output=True,text=True,check=True,timeout=25).stdout)
assert main['client_count']==192 and main['held_inputs']==197 and main['training_enabled'] is True
template=read(ready['native_job_template']);h.checked(template['lease'])
fd=os.open(template['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
try:
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
finally:os.close(fd)
sockets=[]
try:
    for port in (19998,*range(20000,20032)):
        sock=socket.socket();sockets.append(sock);sock.bind(('127.0.0.1',port))
finally:
    for sock in sockets:sock.close()
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=10)
assert template['gpu_uuid'] not in gpu.stdout
preflight=h.put(T/'original-main-and-private-preflight-before-canonical-registration.json',dict(
    current_main=main,current_main_monitor=monitor,current_main_binding=ready['current_main_binding'],
    lease=template['lease'],permanent_lease_unchanged_and_unheld=True,all33_private_ports_free=True,
    private_GPU_empty=True,GPU_processes=gpu.stdout,selected_family_closeout=pp,
    quality_qualified=False,created_unix_s=time.time()))
S=R.parent/'state.json';before=S.read_bytes();state=json.loads(before);goal=state['optimization_goal']
aliases=h.put(T/'prior-canonical-quality-and-monitor-aliases.json',dict(
    root_active=state.get('active_quality_job'),goal_active=goal.get('active_quality_job'),
    prior_recovery_index=goal['current_recovery_index'],prior_diagnostic=goal.get('active_diagnostic_job')))
active=dict(state='prepared',directory=str(T),plan_path=str(T/'plan.json'),status_path=str(T/'status.json'),
    quality_pair=pair_pin,launch_readiness=ready_pin,current_leg=1,total_legs=4,
    reference_label='1741.2M protected reference',candidate_label='2739.3M LR125 candidate; dedicated health observer',
    original_attempts_per_leg=1,no_retries=True,promotion=False,quality_qualified=False,
    prior_closed_study=aliases,selected_family_guard=pp)
state['active_quality_job']=active
goal['active_quality_job']=dict(active,current_leg='R1')
goal.update(stage='FRESH2739_LR125_DEDICATED_OBSERVER_QUALITY_READY',phase='FOUR_FRESH_ORIGINAL_COMPLETE_GAME_LEGS',
    actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=True,full_source_freeze=True,
    latest_goal_turn_classification='progress',
    last_progress='Later2739.279553M snapshot95726b CPU phase/Adam/model verification passed; new fixed pair and dedicated-observer family passed8 selected tests/20 rejections after9/66 unselected contracts and actual32 startup316/13 independent integration. All four quality legs fresh; launch once.')
goal['active_diagnostic_job']=None
goal['current_dedicatedObserver_study']=dict(state='PREPARED_NOT_YET_LAUNCHED',directory=str(T),pair=pair_pin,
    capture=h.pin(D/'independent-original-capture-and-current-main-closeout.json'),
    numerical=h.pin(D/'independent-original-numerical-CPU-closeout.json'),selected_family_closeout=pp,
    current_main_binding=ready['current_main_binding'],current_main_monitor=monitor,quality_qualified=False)
goal['future_main_observer_isolation'].update(state='SELECTED_PROSPECTIVELY_FOR_NEW2739_FIXED_PAIR',
    native_integration_selected=True,selected_family=ready['source_family_manifest'],quality_qualified=False)
old_index=goal['current_recovery_index'];index=read(old_index)
index.update(previous_recovery_index=old_index,stage=goal['stage'],phase=goal['phase'],
    actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=True,full_source_freeze=True,
    current_quality_campaign=str(T),current_quality_pair=pair_pin,current_quality_readiness=ready_pin,
    current_policy_capture_closeout=goal['current_dedicatedObserver_study']['capture'],
    current_policy_numerical_closeout=goal['current_dedicatedObserver_study']['numerical'],
    current_selected_family_closeout=pp,current_main_monitor=monitor,current_main_health=main,
    next_action='Launch the declared fresh sequence and display once; retain their actual identities. Verify actual R1 separate observer/readiness/startup, then monitor original full games. No old study/candidate retry; no promotion until independently valid C1 and C2 each meet fixed NEW R1+R2 mean/median gates.',
    created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261024-fresh2739-dedicated-observer-quality-ready-original01.json',index)
goal['current_recovery_index']=ip;goal['next_action']=index['next_action']
with (T/'canonical-before-fresh2739-dedicated-ready.raw.json').open('xb')as stream:
    stream.write(before);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
encoded=json.dumps(state,separators=(',',':'),allow_nan=False).encode()
assert len(encoded)<1048576 and S.read_bytes()==before
tmp=S.with_name('state.fresh2739-dedicated-ready.tmp')
with tmp.open('xb')as stream:
    stream.write(encoded);stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
assert S.read_bytes()==before
os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(dict(recovery=ip,selected_family_closeout=pp,preflight=preflight,state_bytes=len(encoded))))
