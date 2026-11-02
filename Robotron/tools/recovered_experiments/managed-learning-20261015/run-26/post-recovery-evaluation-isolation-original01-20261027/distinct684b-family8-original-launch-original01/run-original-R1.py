"""One authorized original R1 controller; its same Popen owns observation/reap."""
import json
import os
from pathlib import Path
import sys
import time
import importlib.util

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
A=Path(__file__).resolve().parent
S=A.parent/'distinct684b-buffered-family8-study-original01'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

h=load('_authorized_original_R1_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
assert h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
helper_path=G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py'
assert h.pin(helper_path)['sha256']=='b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4'
helper=load('_authorized_original_R1_owned_controller',helper_path)
ready_pin=h.pin(A/'fresh-resource-readiness-before-R1.json');ready=json.loads(h.checked(ready_pin).read_bytes())
assert ready['status']=='READY'and ready['configurations'][0]['leg']=='R1'
assert ready['CPU_qualifications_closed'] is True and ready['original_attempts_unused'] is True
assert 0<=time.time()-ready['checked_unix_s']<120
manifest_pin=ready['prepared_manifest'];manifest=json.loads(h.checked(manifest_pin).read_bytes());study=json.loads(h.checked(manifest['study_precommit']).read_bytes())
assert manifest['engineering_only'] is False
entry=ready['configurations'][0];case=manifest['cases'][0];job=json.loads(h.checked(case['native_job']).read_bytes());cfg=json.loads(h.checked(entry['config']).read_bytes())
assert job['leg']=='R1'and not Path(job['output']).exists()and not Path(cfg['output']).exists()
assert not (S/'R1/controller-original-launch.json').exists()
h.put(A/'original-R1-wrapper-intent.json',dict(source=h.pin(Path(__file__).resolve()),readiness=ready_pin,
    exact_original_job=case['native_job'],exact_original_config=entry['config'],original_attempt=1,no_retry=True,
    actual_wrapper_pid=os.getpid(),actual_wrapper_birth=helper.birth(os.getpid()),created_unix_s=time.time()))
plan=dict(schema='robotron-deadline32-dashboard-plan-v1',checkpoints={role:value['checkpoint']for role,value in study['policies'].items()},
    legs=[dict(index=index+1,role=row['role'],job=dict(label='Protected reference'if row['role']=='reference'else'Frozen candidate'),
        evaluator_status_path=str(S/row['leg']/'display-status.json'))for index,row in enumerate(manifest['cases'])])
h.put(S/'plan.json',plan)

def atomic(path,value):
    tmp=path.with_name(path.name+'.next')
    with tmp.open('w')as stream:json.dump(value,stream,separators=(',',':'),allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
    os.replace(tmp,path)

for row in manifest['cases']:
    atomic(S/row['leg']/'display-status.json',dict(phase='preparing_original_reference'if row['leg']=='R1'else'pending',complete=False))
atomic(S/'status.json',dict(state='running',current_leg=1,updated_unix_s=time.time(),
    legs=[dict(index=i+1,role=row['role'],state='running'if i==0 else'pending',started_unix_s=time.time()if i==0 else None,
        evaluator_status_path=str(S/row['leg']/'display-status.json'))for i,row in enumerate(manifest['cases'])]))

def register(stage,owner=None,child=None,initial=False,terminal=False):
    state=G/'logs/managed-learning-20261015/state.json';raw=state.read_bytes();data=json.loads(raw);goal=data['optimization_goal']
    active=data.get('active_quality_job')
    if initial:
        assert not active and not goal['scientific_job_running']and not goal.get('performance_job_running')
        epoch=json.loads(h.checked(goal['next_fixed_reference_epoch']).read_bytes())
        assert epoch['reference_policy']['sha256']==study['policies']['reference']['checkpoint']['sha256']
        active=dict(directory=str(S),state='running',current_leg=1,prepared_manifest=manifest_pin,
            candidate_sha256=study['policies']['candidate']['checkpoint']['sha256'],reference_sha256=study['policies']['reference']['checkpoint']['sha256'])
        data['active_quality_job']=active
        if goal.get('current_controlled_evaluation_blocker'):goal['previous_controlled_evaluation_blocker']=goal['current_controlled_evaluation_blocker']
        goal['current_controlled_evaluation_blocker']=None
        goal['DrivingSchool_stop_authorized']=True;goal['GPU0_release_user_decision_pending']=False
    else:assert active and active['directory']==str(S)
    if terminal:active['state']='failed'if 'FAILED'in stage else'review_pending'
    active.update(stage=stage,actual_original_scope=owner,actual_original_controller=child,
        wrapper_pid=os.getpid(),wrapper_birth=helper.birth(os.getpid()),readiness=ready_pin)
    goal['scientific_job_running']=not terminal and owner is not None
    goal['actual_running_wait']=None if terminal else dict(kind=stage,quality_leg='R1',wrapper_pid=os.getpid(),
        wrapper_birth=helper.birth(os.getpid()),scope=owner,controller=child,original_job=case['native_job'],no_retry=True)
    goal['last_progress']='Fresh independent684b original R1 screening: '+stage+'. Frozen candidate unchanged; independent review and fullgame confirmation still required.'
    encoded=(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(encoded)<1<<20
    backup=A/('state-before-'+stage.lower()+'.exact.json')
    with backup.open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    assert state.read_bytes()==raw
    tmp=state.with_name('state.authorized-original-R1.tmp')
    with tmp.open('xb')as stream:stream.write(encoded);stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
    assert state.read_bytes()==raw;os.replace(tmp,state);fd=os.open(state.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(event=stage,owner=owner,controller=child)),flush=True)

register('ORIGINAL_R1_CONTROLLER_STARTING',initial=True)

def on_live(owner,child):
    h.put(A/'actual-original-R1-live-owner.json',dict(original_job=case['native_job'],config=entry['config'],owner=owner,controller=child,
        wrapper_pid=os.getpid(),wrapper_birth=helper.birth(os.getpid()),observed_unix_s=time.time()))
    register('ORIGINAL_R1_NATIVE_RUNNING',owner,child)

result_pin=helper.invoke_controller_once(S/'R1','',entry['controller'],entry['config'],h,on_live)
result=json.loads(h.checked(result_pin).read_bytes())
if result['actual_exit']==0 and result['live_registration_errors']==[]:
    register('ORIGINAL_R1_NATIVE_CLOSED_PENDING_INDEPENDENT_REVIEW',terminal=True)
else:
    register('ORIGINAL_R1_FAILED_PENDING_INDEPENDENT_OWNED_RELEASE_REVIEW',terminal=True)
    h.put(A/'original-R1-controller-nonzero-no-retry.json',dict(result=result_pin,actual_exit=result['actual_exit'],
        live_registration_errors=result['live_registration_errors'],scientific_payload_retried=False,scope_release_must_be_independently_checked=True))
print(json.dumps(dict(controller_result=result_pin,actual_controller_exit=result['actual_exit'],scientific_payload_retried=False)),flush=True)
sys.exit(result['actual_exit'])
