"""Register the verified new original four-leg campaign before its sole launch."""
import fcntl,hashlib,importlib.util,json,os,socket,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26'
B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023'
T=R/'quality32-protected1741-vs-currentLR125-initialReady-firstSave-original01-preparation-20261023'
D=R/'currentLR125-initialReady-firstSave-original01-preparation-20261023'
def load(p,name,sha):
    assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
    sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_reg_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_reg_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_reg_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
def read(p,as_json=True):return reader.read_pin(p,as_json=as_json)
sp=importlib.util.spec_from_file_location('_reg_cl',P/'independent_component_closeout_v3.py');cl=importlib.util.module_from_spec(sp);sp.loader.exec_module(cl)
V=T/'selected-family-source-guards-CPU-original01';proof=cl.closeout(V,h,arc,read,0);rp=h.pin(V/'output-original01/report.json');report=read(rp)
assert report['tests']==7 and len(report['negative_checks'])==20
proof.update(report=rp,tests=7,negative_checks=20,selected_family_unchanged_from_tested_renderer=True,scientific_case_launched=False)
guardproof=h.put(V/'independent-original-selected-family-and-CPU-closeout.json',proof)
ready_pin=h.pin(T/'new-original-quality-launch-readiness.json');ready=read(ready_pin);pair=read(ready['quality_pair'])
assert all(not(T/f).exists()for f in ['01-reference','02-candidate','03-reference','04-candidate'])
assert ready['initial_readiness_protocol']==dict(schema='robotron-bounded-initial-owned-readiness-v1',max_wait_s=2.,max_samples=11)
monitor=h.pin(D/'postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
assert main['client_count']==192 and main['held_inputs']==197 and main['training_enabled']
lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');prior=lease.stat()
assert (prior.st_dev,prior.st_ino,prior.st_uid,prior.st_mode&0o777,prior.st_size)==(32,757,1001,0o600,0)
with lease.open('rb')as f:
    fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);assert lease.stat()==prior;fcntl.flock(f,fcntl.LOCK_UN)
handles=[]
try:
    for port in [19998,*range(20000,20032)]:
        item=socket.socket();handles.append(item);item.bind(('0.0.0.0',port))
finally:
    for item in handles:item.close()
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader'],check=True,capture_output=True,text=True,timeout=10)
assert 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'not in gpu.stdout
preflight=h.put(T/'original-main-and-private-preflight-before-canonical-registration.json',dict(
    monitor=monitor,actual=main,source_guard_closeout=guardproof,all33_ports_bindable=True,private_GPU0_idle=True,
    GPU_compute_apps=gpu.stdout,permanent_lease=dict(device=prior.st_dev,inode=prior.st_ino,uid=prior.st_uid,size=prior.st_size),
    lease_acquired_and_released_without_replacement=True,created_unix_s=time.time()))
S=R.parent/'state.json';raw=S.read_bytes();s=json.loads(raw);g=s['optimization_goal'];previous=g['current_recovery_index']
prior_alias=h.put(T/'prior-canonical-quality-and-monitor-aliases.json',dict(top_active=s.get('active_quality_job'),goal_active=g.get('active_quality_job'),
    current_main_monitor=g.get('current_main_monitor'),current_main_binding=g.get('current_main_binding'),source_freeze=g.get('source_freeze'),full_source_freeze=g.get('full_source_freeze'),current_recovery_index=previous))
active=dict(state='prepared',directory=str(T),plan_path=str(T/'plan.json'),status_path=str(T/'status.json'),quality_pair=ready['quality_pair'],
    launch_readiness=ready_pin,current_leg=1,total_legs=4,reference_label='1741.2M protected reference',candidate_label='2715.9M startup-readiness LR125 candidate',
    original_attempts_per_leg=1,no_retries=True,promotion=False,quality_qualified=False,prior_closed_study=prior_alias,selected_family_guard=guardproof)
s['active_quality_job']=active;g['active_quality_job']=dict(active,current_leg='R1')
g.update(status='active',stage='FRESH_INITIALREADY2715_ALL_FOUR_NEW_QUALITY_LEGS_PREPARED',phase='SOURCE_BOUND_ORIGINAL_SEQUENCE_READY',
    source_freeze=True,full_source_freeze=True,current_quality_source_freeze_state='HELD_FOR_FRESH_INITIALREADY2715_ORIGINAL_FOUR_LEG_CAMPAIGN',
    current_main_monitor=monitor,current_main_binding=ready['current_main_binding'],current_main_monitor_command='/usr/bin/python3.12 -I -B '+monitor['path'],
    actual_running_wait=None,all_current_original_handles_terminal=True,latest_goal_turn_classification='progress')
g['active_continuation_capture'].update(state='CLOSED_NUMERICAL_CPU_PASS',capture_closeout=h.pin(D/'independent-original-capture-and-current-main-closeout.json'),numerical_closeout=h.pin(D/'independent-original-numerical-CPU-closeout.json'))
g['current_initialReady_study']=dict(directory=str(T),readiness=ready_pin,precommit=h.pin(T/'original-fresh-sequence-precommit.json'),
    candidate_numerical_CPU=h.pin(D/'independent-original-numerical-CPU-closeout.json'),source_guard_closeout=guardproof,main_preflight=preflight,
    capture_limitation='Original60s prefix closed before managed-slot transition; later current-hash replay was not qualified. No original historical substitution or failed-study rescue.',
    quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False)
g['last_progress']='Fresh2715.9M policy numerical CPU and seven selected source contracts/20 rejections passed. New four-leg sequence ready, main192/197 and private preflight healthy; no gain claimed.'
g['latest_goal_turn_assessment']=dict(classification='progress',proof=guardproof,work=g['last_progress'])
index=dict(schema='robotron-continuous-optimization-recovery-index-v1',goal_status='active',stage=g['stage'],phase=g['phase'],
    previous_recovery_index=previous,canonical_state=str(S),campaign_directory=str(T),quality_pair=ready['quality_pair'],candidate_policy=pair['candidate']['policy'],
    candidate_clocks=pair['candidate']['saved_clocks'],reference=pair['reference'],launch_readiness=ready_pin,source_family_manifest=ready['source_family_manifest'],
    source_guard_closeout=guardproof,current_main_binding=ready['current_main_binding'],current_main_monitor=monitor,current_main_monitor_command=g['current_main_monitor_command'],
    current_main_health=main,actual_running_wait=None,all_current_original_handles_terminal=True,scientific_job_running=False,source_freeze=True,full_source_freeze=True,
    initial_readiness_protocol=ready['initial_readiness_protocol'],prior_failed_studies_retried=False,quality_qualified=False,promotion=False,
    learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False,
    next_action='Launch only this new original sequence/display; verify actual readiness receipt precedes loaded policy and game admission, all32 original prefixes and held-main health. No retry of failed studies.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-initialReady2715-four-leg-ready-original01.json',index);g['current_recovery_index']=ip;g['next_action']=index['next_action'];s['updated_unix_s']=time.time()
with (T/'canonical-before-initialReady-ready.raw.json').open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==raw
tmp=S.with_name('state.initialReady-ready.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==raw;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md';text=doc.read_text();start=text.index('Current optimization recovery:');end=text.index('The original maximum resource fixture')
doc.write_text(text[:start]+'''Current optimization recovery: [Fresh startup-readiness quality campaign prepared](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-initialReady2715-four-leg-ready-original01.json).
All preparation originals closed0; seven selected-family contracts/20 rejections passed.
Later candidate3928b61f (LF2,715,929,502) passed numerical CPU verification.
Main binding/monitor now point to its exact owned completed-slot transition.
All33 private ports, GPU0 and the unchanged permanent lease were verified free.
The new four-leg campaign is prepared; read canonical state for a newer live handle.

'''+text[end:])
print(json.dumps(dict(registered=True,state_bytes=len(encoded),source_guard=guardproof,recovery=ip,precommit=h.pin(T/'original-fresh-sequence-precommit.json'))))
