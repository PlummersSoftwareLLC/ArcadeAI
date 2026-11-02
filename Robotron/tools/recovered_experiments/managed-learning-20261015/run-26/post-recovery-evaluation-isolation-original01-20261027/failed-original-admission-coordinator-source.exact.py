import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron');T=G/'tools/post_recovery_evaluation'
I=G/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
h=load('h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
lp=h.pin(I/'natural-round-admission-four-original-live-launches-original28.json')
launch=json.loads(h.checked(lp).read_bytes())
def read(pin):return json.loads(h.checked(pin).read_bytes())
def show(unit):
    r=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=10)
    assert r.returncode==0
    return dict(x.split('=',1)for x in r.stdout.splitlines()if'='in x)
def birth(pid):
    p=Path('/proc',str(pid),'stat')
    return int(p.read_text().rsplit(')',1)[1].split()[19])if p.exists()else None
closer=load('closer',T/'close_reconnect_engineering_v1.py');closed={}
started=time.monotonic();last_print=0
while len(closed)<2:
    status=[]
    for row in launch['records']:
        if row['mode']!='long'or row['kind']in closed:continue
        owner=read(row['original_live_owner']);props=show(owner['unit'])
        assert props['InvocationID']==owner['invocation_id']and props['ExecMainPID']==str(owner['pid'])and props['NRestarts']=='0'
        if props['MainPID']=='0':
            assert props['ExecMainCode']=='1'and props['ExecMainStatus']=='0',dict(kind=row['kind'],actual=props)
            assert birth(owner['pid'])!=owner['birth']
            closed[row['kind']]=closer.close(Path(lp['path']),lp['sha256'],row['kind'],'long')
            print(json.dumps(dict(event='ORIGINAL_LONG_CLOSED',kind=row['kind'],closeout=closed[row['kind']])),flush=True)
        else:
            assert int(props['MainPID'])==owner['pid']and birth(owner['pid'])==owner['birth']
            path=Path(row['output'])/'runtime/main-health-scope/job.json';job=read(h.pin(path))
            live_path=Path(job['live_control_path'])/'live.json'
            if live_path.exists():
                value=json.loads(live_path.read_bytes());age=time.monotonic()-value['updated_monotonic_s']
                # Once close is requested, absence or stopped publication is
                # expected; terminal owner/worker evidence still governs.
                closing=(Path(row['output'])/'runtime/main-observations/finish-request.json').exists()
                if not closing:assert age<=.5
                status.append(dict(kind=row['kind'],parent=owner['pid'],samples=value['observed_samples'],age_s=age,closing=closing))
    if time.monotonic()-last_print>=20:
        print(json.dumps(dict(event='SAME_ORIGINAL_SCOPES_OBSERVED',live=status,elapsed_s=time.monotonic()-started)),flush=True);last_print=time.monotonic()
    assert time.monotonic()-started<780,'Observation bound reached; never relaunch'
    if len(closed)<2:time.sleep(5)

# Record positive closure of the exact currently registered engineering job.
STATE=G/'logs/managed-learning-20261015/state.json';raw=STATE.read_bytes();state=json.loads(raw);goal=state['optimization_goal']
assert state.get('active_quality_job')is None and goal['scientific_job_running']is False
assert goal['current_round_admission_probes']==lp and goal['performance_job_running']is True
all_closed=dict(closed)
for row in launch['records']:
    if row['mode']=='abort':all_closed[row['kind']+'_abort']=h.pin(Path(row['output'])/'independent-original-engineering-closeout.json')
before=I/'state-before-original-admission-probes-positive-close.exact.json'
with before.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
goal['performance_job_running']=False;goal['current_round_admission_probe_closures']=all_closed
cp=I.parent/'post-reconnect-next-candidate-20261028-original01'
goal['actual_running_wait']=dict(kind='ORIGINAL_NEW_PROSPECTIVE_CANDIDATE_WINDOW',pid=3845216,birth=11357777,
    tool_session=5123,original_owner=h.pin(cp/'original-window-wrapper-intent.json'),all_admission_probes_closed=True)
goal['last_progress']='All four original nine-source admission interfaces positively closed: long modes passed actual raw replay and abort outcomes preserved. Preparing new exact deadline10/fullgame6 contexts; original candidate watcher continues. No quality gain or promotion.'
encoded=(json.dumps(state,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(encoded)<1<<20
temporary=STATE.with_name('state.original-admission-probes-closed.tmp')
with temporary.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert STATE.read_bytes()==raw;os.replace(temporary,STATE);fd=os.open(STATE.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

d=I/'admission-evaluators-preparation-CPU-original01';d.mkdir(mode=0o700)
control_pin=h.pin(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
control=load('control',Path(control_pin['path']));source=h.pin(T/'prepare_admission_evaluator_engineering_cpu_v1.py')
adapt=h.pin(I/'natural-round-admission-deadline10-fullgame6-source-adaptation-original28.json');adaptation=read(adapt)
fields={k:h.pin(I/p)for k,p in dict(reference_profile='reference-frozen-profile-v2-CPU-original01/independent-profile-adoption.json',
    entry_profile='entry-frozen-profile-v2-CPU-original01/independent-profile-adoption.json',
    deadline_readiness='natural-round-admission-deadline-long-engineering-original01/runtime/independent-raw-review.json',
    lease_recovery='post-outage-permanent-private-coordinator-restoration-original01.json').items()}
inputs=[source,adapt,*[h.pin(T/n)for n in adaptation['new_sources']],*fields.values(),*all_closed.values()]
job=dict(schema='robotron-admission-evaluators-preparation-CPU-v1',
    unit='robotron-admission-evaluators-preparation-CPU-original01-20261028.service',output=str(d/'runtime'),
    inputs=inputs,original_attempt=1,no_retry=True,**fields)
jp=h.put(d/'job.json',job)
cfg=dict(unit=job['unit'],output=str(d/'execution-original01'),argv=['/usr/bin/python3','-I','-B',source['path'],
    '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',source['sha256']],
    properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
    pins=[control.pin(p['path'])for p in [jp,*inputs]],observation_s=240)
cfgpin=h.put(d/'controller-config.json',cfg);control.checked_config(cfgpin['path'])
sequence=load('sequence',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py')
result=sequence.invoke_controller_once(d,'',control_pin,cfgpin,h);print(json.dumps(dict(event='PREPARATION_ORIGINAL_TERMINAL',result=result)),flush=True)
assert read(result)['actual_exit']==0
close=load('cpuclose',T/'close_engineering_cpu_scope_v2.py').close(d)
print(json.dumps(dict(event='PREPARATION_CLOSED',closeout=close,report=h.pin(d/'runtime/report.json'))),flush=True)
