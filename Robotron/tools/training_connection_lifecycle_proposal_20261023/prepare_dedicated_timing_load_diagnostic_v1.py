"""Prepare one new protected-reference load diagnostic with worker stage timings."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023'
B=G/'tools/startup_policy_journal_proposal'
D=R/'native32-dedicated-observer-critical-path600-original01-preparation-20261024'
OLD=R/'native32-dedicated-CPU-observer-startup-original01-preparation-20261023'

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

h=load(B/'run_full_policy_startup_v3.py','_timing_prepare_h')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_timing_prepare_reader')
def read(pin):return reader.read_pin(pin)
def write_source(path,text):
    compile(text,str(path),'exec')
    with path.open('xb')as stream:
        stream.write(text.encode());stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return h.pin(path)
def replace(text,a,b):
    assert text.count(a)==1,(a,text.count(a))
    return text.replace(a,b)

state=json.loads((R.parent/'state.json').read_text())
assert state['optimization_goal']['actual_running_wait']is None
assert state['optimization_goal']['all_current_original_handles_terminal'] is True
assert state['optimization_goal']['full_source_freeze'] is False
D.mkdir(mode=0o700)
worker_old=P/'run_dedicated_main_health_v1.py'
worker_text=worker_old.read_text()
timing_class='''
class DiagnosticTiming:
    """Bounded in-memory diagnostics, flushed only after original capture stops."""
    def __init__(self,job,source):
        self.job=job;self.source=source;self.rows=[];self.truncated=False;self.index=lambda:None
        self.cpu_path=Path('/sys/fs/cgroup'+own_cgroup(os.getpid()))/'cpu.stat'
        self.started=self.clock()
    def clock(self):
        try:stat={k:int(v)for k,v in (line.split()for line in self.cpu_path.read_text().splitlines())}
        except OSError as error:stat=dict(read_error=repr(error))
        return dict(monotonic_s=time.monotonic(),unix_s=time.time(),thread_cpu_s=time.thread_time(),
            process_cpu_s=time.process_time(),cpu_stat=stat)
    def append(self,row):
        if len(self.rows)>=65536:self.truncated=True;return
        row['event']=len(self.rows);self.rows.append(row)
    def gc_callback(self,phase,info):
        self.append(dict(kind='gc',phase=phase,info=dict(info),index=self.index(),
            monotonic_s=time.monotonic(),thread_id=threading.get_ident()))
    def call(self,name,function,*args,**kwargs):
        begin=self.clock();index=self.index();error=None
        try:return function(*args,**kwargs)
        except BaseException as exception:error=repr(exception);raise
        finally:
            end=self.clock()
            self.append(dict(kind='stage',stage=name,index=index,before=begin,after=end,error=error,
                unit_check=kwargs.get('unit_check'),requested_sleep_s=args[0]if name=='sleep'else None))
    def report(self):
        return dict(schema='robotron-diagnostic-observer-critical-path-timings-v1',job_source=self.source,
            original_native_job=self.job['native_job'],parent=self.job['parent'],original_nonce=self.job['nonce'],
            python_version=sys.version,python_executable=sys.executable,
            GIL_enabled=getattr(sys,'_is_gil_enabled',lambda:True)(),
            started=self.started,ended=self.clock(),events=self.rows,truncated=self.truncated,
            event_limit=65536,events_persisted_only_after_capture_stopped=True,
            observational_instrumentation_changes_some_cost=True,health_predicates_changed=False,
            scientific_case=False,quality_qualified=False)

'''
changes=[]
def change(a,b):
    global worker_text
    worker_text=replace(worker_text,a,b);changes.append((a,b))
change('import argparse,hashlib,importlib.util,json,os,signal,subprocess,sys,time',
       'import argparse,gc,hashlib,importlib.util,json,os,signal,subprocess,sys,threading,time')
change('def run(job,jp,h,protocol,worker_source):',timing_class+'def run(job,jp,h,protocol,worker_source):')
change("    owner=None;guard=None;latest=None;closed=None;failure=None;error=None;outcome=None;next_unit_check=0.;received=[]",
       "    native_context=json.loads(h.checked(job['native_job']).read_bytes())\n"
       "    require(native_context['schema']=='robotron-native32-dedicated-observer-timing-load-diagnostic-v1'and native_context['diagnostic_only']is True and 'quality_leg'not in native_context,'Instrumented worker is diagnostic-only')\n"
       "    timing=DiagnosticTiming(job,worker_source)\n"
       "    owner=None;guard=None;latest=None;closed=None;failure=None;error=None;outcome=None;next_unit_check=0.;received=[]")
change("        owner=verify_self(job);verify_parent(job['parent'],h,unit_check=True);emit('starting')",
       "        gc.callbacks.append(timing.gc_callback)\n"
       "        owner=verify_self(job);timing.call('initial_parent',verify_parent,job['parent'],h,unit_check=True);timing.call('emit.starting',emit,'starting')")
change("        guard=engine.MainHealth(job['health_job'],root,h,prior)",
       "        guard=engine.MainHealth(job['health_job'],root,h,prior)\n"
       "        timing.index=lambda:guard.collector.index")
change("            verify_parent(job['parent'],h,unit_check=tick>=next_unit_check)",
       "            timing.call('verify_parent',verify_parent,job['parent'],h,unit_check=tick>=next_unit_check)")
change("            latest=guard.observe();require(time.monotonic()<job['deadline_monotonic_s'],'Original native deadline reached during sample')",
       "            latest=timing.call('guard.observe',guard.observe);require(time.monotonic()<job['deadline_monotonic_s'],'Original native deadline reached during sample')")
change("            emit('running')","            timing.call('emit.running',emit,'running')")
change("            time.sleep(max(0.,tick+.2-time.monotonic()))",
       "            timing.call('sleep',time.sleep,max(0.,tick+.2-time.monotonic()))")
change("    writer_stopped=guard is not None and not guard.collector.writer.thread.is_alive()",
       "    if timing.gc_callback in gc.callbacks:gc.callbacks.remove(timing.gc_callback)\n"
       "    timing_pin=h.put(root/'diagnostic-critical-path-timing.json',timing.report())\n"
       "    writer_stopped=guard is not None and not guard.collector.writer.thread.is_alive()")
change("        protocol_source=job['protocol_source'],owner=owner,parent=job['parent'],nonce=job['nonce'],success=success,",
       "        protocol_source=job['protocol_source'],owner=owner,parent=job['parent'],nonce=job['nonce'],success=success,diagnostic_timing=timing_pin,")
back=worker_text
for a,b in reversed(changes):back=replace(back,b,a)
assert back==worker_old.read_text()
worker_pin=write_source(P/'run_dedicated_main_health_critical_path_diagnostic_v1.py',worker_text)
old_functions={n.name:ast.dump(n)for n in ast.parse(worker_old.read_text()).body if isinstance(n,ast.FunctionDef)}
new_functions={n.name:ast.dump(n)for n in ast.parse(worker_text).body if isinstance(n,ast.FunctionDef)}
assert [key for key in old_functions if old_functions[key]!=new_functions[key]]==['run']

control_old=P/'control_native_startup_timing_diagnostic180_v1.py'
control_text=replace(control_old.read_text(),"props.get('RuntimeMaxSec')=='180'","props.get('RuntimeMaxSec')=='780'")
control_text=replace(control_text,"180<=c['observation_s']<=300","780<=c['observation_s']<=900")
control_pin=write_source(P/'control_native_timing_load_diagnostic780_v1.py',control_text)
assert control_text.replace("props.get('RuntimeMaxSec')=='780'","props.get('RuntimeMaxSec')=='180'").replace("780<=c['observation_s']<=900","180<=c['observation_s']<=300")==control_old.read_text()

reference=h.pin(G/'models_dqn/managed-incumbents/freshCE-LR25-1741M-profile06-confirmed-reset-20261022.pt')
pre=h.put(D/'precommitted-critical-path600-diagnostic.json',dict(
    schema='robotron-original-dedicated-observer-critical-path600-precommit-v1',
    purpose='DIAGNOSE_CRITICAL_PATH_DELAY_UNDER_ACTUAL32_PROTECTED_REFERENCE_LOAD_NO_QUALITY',
    prior_failed_study=state['optimization_goal']['current_dedicatedObserver_study']['closed_readback'],
    checkpoint=reference,minimum_native_load_wall_s=600,wall_limit_s=720,unit_runtime_s=780,
    native_CPU=12,observer_CPU=2,expected_native_exit=1,
    stop='After600s native wall and all32 prefixes, or first original health/runtime failure or720s wall. Preserve every raw record and observed fault. No retries or scientific qualification.',
    instrumentation='In-memory bounded per-call wall/thread/process/quota timings for original parent checks, guard.observe, live publication/fsync and sleep, plus GC callbacks; flush only after capture stops.',
    instrumentation_some_cost=True,original_main_health_predicates_and_limits_unchanged=True,
    worker_source=worker_pin,native_controller=control_pin,failed_candidate_retried=False,
    quality_qualified=False,playing_gain_verified=False,created_unix_s=time.time()))
old_job=read(h.pin(OLD/'job.json'))
old_native=Path(old_job['runtime']['path']).read_text();native=old_native
native_changes=[]
def native_change(a,b):
    global native
    native=replace(native,a,b);native_changes.append((a,b))
native_change("DIAGNOSTIC_SHA='4decba64cec2bc6f486fa21a28b5c1ef153e3d18f5e4cca869004d164d23128c'",'DIAGNOSTIC_SHA='+repr(pre['sha256']))
native_change("'worker': '823e42c1cf8689e3e8827a528898ac8d4507c447c65ab8df3873e8c0f4b440c2'","'worker': "+repr(worker_pin['sha256']))
for a,b in [('robotron-native32-dedicated-observer-startup-diagnostic-v1','robotron-native32-dedicated-observer-timing-load-diagnostic-v1'),('robotron-native32-dedicated-observer-startup-diagnostic-result-v1','robotron-native32-dedicated-observer-timing-load-diagnostic-result-v1'),('robotron-native-dedicated-startup-diagnostic-main-health-protocol-v1','robotron-native-dedicated-timing-load-diagnostic-main-health-protocol-v1')]:native_change(a,b)
native_change("job['diagnostic_role']=='startup_only'","job['diagnostic_role']=='timing_load_only'")
native_change("job['wall_limit_s']==120","job['wall_limit_s']==720")
native_change("            if len(actors)==32 and all(row['proxy'].prefix_verified.is_set()for row in actors.values()):",
              "            if time.monotonic()-started>=600 and len(actors)==32 and all(row['proxy'].prefix_verified.is_set()for row in actors.values()):")
native_change('PRECOMMITTED_DEDICATED_STARTUP_ONLY_STOP_AFTER_ALL32_PREFIXES_NOT_A_QUALITY_RESULT','PRECOMMITTED_CRITICAL_PATH600_LOAD_STOP_AFTER_ALL32_PREFIXES_NOT_A_QUALITY_RESULT')
back=native
for a,b in reversed(native_changes):back=replace(back,b,a)
assert back==old_native
native_pin=write_source(B/'run_native32_dedicated_critical_path600_diagnostic_original01_v1.py',native)
job=copy.deepcopy(old_job)
job.update(schema='robotron-native32-dedicated-observer-timing-load-diagnostic-v1',diagnostic_role='timing_load_only',
    diagnostic_precommit=pre,runtime=native_pin,checkpoint=reference,output=str(D/'diagnostic-output-original01'),
    wall_limit_s=720,label='native32-dedicated-observer-critical-path600-original01-20261024',
    main_binding=h.pin(R/'currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024/postcapture-current-main-binding.json'),
    sessions={str(s):secrets.token_hex(16)for s in range(4096,4128)},connections={str(s):secrets.token_hex(16)for s in range(4096,4128)},
    created_unix_s=time.time())
old_protocol=read(job['main_health_protocol']);health=copy.deepcopy(old_protocol['health_job']);health['binding']=job['main_binding']
protocol=h.put(D/'diagnostic-main-health-protocol.json',dict(schema='robotron-native-dedicated-timing-load-diagnostic-main-health-protocol-v1',prior_case=None,health_job=health))
family=read(job['source_family_manifest']);family.update(schema='robotron-dedicated-critical-path600-diagnostic-source-family-v1',runtime=native_pin,diagnostic_precommit=pre)
family['main_observer']['worker']=worker_pin
fp=h.put(D/'diagnostic-source-family.json',family)
job.update(main_health_protocol=protocol,source_family_manifest=fp)
job['inputs']=list({p['path']:p for p in [*job['inputs'],native_pin,worker_pin,control_pin,pre,protocol,fp,job['main_binding']]}.values())
for pin in job['inputs']:h.checked(pin)
runtime=load(Path(native_pin['path']),'_prepared_critical_path600_native');runtime.validate_job(job)
jp=h.put(D/'job.json',job)
proof=h.put(D/'unselected-timing-and-diagnostic-source-provenance.json',dict(
    worker_original=h.pin(worker_old),instrumented_worker=worker_pin,worker_exact_reverse=True,worker_changed_functions=['run'],
    original_parent_self_identity_signal_deadline_and_raw_health_helpers_unchanged=True,
    original_scientific_sources_unchanged=True,original_native=old_job['runtime'],diagnostic_native=native_pin,
    native_exact_reverse=True,native_job=jp,precommit=pre,quality_qualified=False))
control=load(Path(control_pin['path']),'_prepared_critical_path600_control')
cfg=dict(unit='robotron-native32-dedicated-critical-path600-original01-20261024.service',output=str(D/'execution-original01'),
    argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',native_pin['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',native_pin['sha256']],
    properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=780',
        'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
    pins=[control.pin(p['path'])for p in [*job['inputs'],jp,proof]],observation_s=840)
cp=h.put(D/'controller-config.json',cfg);control.checked_config(cp['path'])
print(json.dumps(dict(config=cp,controller=control_pin,native=native_pin,worker=worker_pin,precommit=pre,provenance=proof)))
