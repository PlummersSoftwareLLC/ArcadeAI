"""New reference-only native load with strict serialized live-file protocol."""
import ast,copy,fcntl,importlib.util,json,os,secrets,socket,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
D=R/'native32-serialized-free314-observer-load600-original01-preparation-20261024'
OLD=R/'native32-free314-observer-load600-original01-preparation-20261024'
C=R/'serialized-live-free314-client-CPU-original01-preparation-20261024'
N=R/'serialized-live-free314-six-failures-CPU-original01-preparation-20261024'
S=R/'serialized-live-protocol-CPU-original01-preparation-20261024'
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_serialized_native_prepare_h')
def read(pin):return json.loads(h.checked(pin).read_bytes())
def replace(text,a,b):assert text.count(a)==1,(a,text.count(a));return text.replace(a,b)
state=json.loads((R.parent/'state.json').read_bytes());goal=state['optimization_goal']
assert goal['actual_running_wait']is None and goal['all_current_original_handles_terminal']and not goal['full_source_freeze']
proofs=dict(protocol=h.pin(S/'independent-original-strict-guards-locks5000-publications-and-scope-closeout.json'),
    positive=h.pin(C/'independent-original-serialized-client-runtime-and-raw-closeout.json'),
    negative=h.pin(N/'independent-original-six-failures-eight-scopes-and-signal-readback.json'),
    source_provenance=h.pin(S/'source-and-reproduction-provenance.json'),
    prior_failed_native=h.pin(OLD/'independent-original-failed-native-live-protocol-raw1006-and-scopes-closeout.json'))
assert read(proofs['protocol'])['strict_original_read_and_publish_bodies_AST_unchanged']
assert read(proofs['positive'])['actual_worker_GIL0_and_binary_verified']
assert read(proofs['negative'])['all8_actual_scope_archives_resources_argv_pins_release_and_birth_absence_verified']
old_job=read(h.pin(OLD/'job.json'));old_family=read(old_job['source_family_manifest'])
context=read(h.pin(C/'source-family-component.json'))
monitor=h.pin(R/'currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024/postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],capture_output=True,text=True,check=True,timeout=25).stdout)
assert main['client_count']==192 and main['held_inputs']==197
h.checked(old_job['lease']);fd=os.open(old_job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
finally:os.close(fd)
for port in (19998,*range(20000,20032)):
    with socket.socket()as sock:sock.bind(('127.0.0.1',port))
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=10)
assert old_job['gpu_uuid']not in gpu.stdout
D.mkdir(mode=0o700)
pre=h.put(D/'precommitted-serialized-free314-reference-load600-diagnostic.json',dict(
    schema='robotron-serialized-free314-reference-native32-load600-precommit-v1',
    purpose='STRICT_SERIALIZED_LIVE_PROTOCOL_NATIVE_LOAD_INTEGRATION_ONLY_NO_QUALITY_RESULT',
    checkpoint=old_job['checkpoint'],component_proofs=proofs,selected_context=h.pin(C/'source-family-component.json'),
    worker_interpreter=context['main_observer_interpreter'],poll_s=.2,live_lock_wait_s=.1,
    original_strict_reader_and_publisher_AST_unchanged=True,immutable_finish_and_live_validation_unchanged=True,
    minimum_native_wall_s=600,wall_limit_s=720,unit_runtime_s=780,native_CPU=12,worker_CPU=2,
    expected_native_exit=1,expected_positive_observer_exit=0,
    stop='After600s native wall and all32 original prefixes, or first original health/runtime failure or720s wall. No retry.',
    health_game_ownership_timing_and_budget_limits_unchanged=True,original_health_sources=old_job['main_health_protocol'],
    prior_failed_native_and_scientific2739_not_retried=True,candidate_not_loaded=True,current_main=main,current_main_monitor=monitor,
    lease_unchanged_and_free=True,all33_private_ports_free=True,private_GPU_empty=True,
    quality_qualified=False,playing_gain_verified=False,learning_speed_gain_verified=False,created_unix_s=time.time()))
old_source=Path(old_job['runtime']['path']).read_text();source=old_source;changes=[]
def change(a,b):
    global source
    source=replace(source,a,b);changes.append((a,b))
change('DIAGNOSTIC_SHA='+repr(old_job['diagnostic_precommit']['sha256']),'DIAGNOSTIC_SHA='+repr(pre['sha256']))
change(old_family['main_observer']['protocol']['sha256'],context['main_observer']['protocol']['sha256'])
for a,b in [('robotron-native32-free314-observer-load-diagnostic-v1','robotron-native32-serialized-free314-observer-load-diagnostic-v1'),
            ('robotron-native32-free314-observer-load-diagnostic-result-v1','robotron-native32-serialized-free314-observer-load-diagnostic-result-v1'),
            ('robotron-native-free314-observer-load-diagnostic-main-health-protocol-v1','robotron-native-serialized-free314-observer-load-diagnostic-main-health-protocol-v1'),
            ('PRECOMMITTED_FREE314_REFERENCE600_LOAD_STOP','PRECOMMITTED_SERIALIZED_FREE314_REFERENCE600_LOAD_STOP'),
            ('ORIGINAL_FREE314_REFERENCE_LOAD_DIAGNOSTIC_STOPPED_NO_QUALITY','ORIGINAL_SERIALIZED_FREE314_REFERENCE_LOAD_DIAGNOSTIC_STOPPED_NO_QUALITY')]:change(a,b)
reverse=source
for a,b in reversed(changes):reverse=replace(reverse,b,a)
assert reverse==old_source
unchanged=[]
for node in ast.parse(old_source).body:
    if isinstance(node,(ast.FunctionDef,ast.ClassDef))and node.name not in ('run','validate_job'):
        current=next(n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name==node.name)
        assert ast.dump(node)==ast.dump(current);unchanged.append(node.name)
path=B/'run_native32_serialized_free314_observer_load600_diagnostic_original01_v1.py';compile(source,str(path),'exec')
with path.open('xb')as f:f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
runtime=h.pin(path);job=copy.deepcopy(old_job)
job.update(schema='robotron-native32-serialized-free314-observer-load-diagnostic-v1',runtime=runtime,diagnostic_precommit=pre,
    output=str(D/'diagnostic-output-original01'),label='native32-serialized-free314-observer-load600-original01-20261024',
    sessions={str(s):secrets.token_hex(16)for s in range(4096,4128)},connections={str(s):secrets.token_hex(16)for s in range(4096,4128)},created_unix_s=time.time())
protocol=read(old_job['main_health_protocol']);protocol['schema']='robotron-native-serialized-free314-observer-load-diagnostic-main-health-protocol-v1'
pp=h.put(D/'diagnostic-main-health-protocol.json',protocol)
family=copy.deepcopy(old_family);family.update(schema='robotron-serialized-free314-native32-load-diagnostic-source-family-v1',runtime=runtime,
    main_observer=context['main_observer'],main_observer_interpreter=context['main_observer_interpreter'],diagnostic_precommit=pre,serialized_protocol_components=proofs)
fp=h.put(D/'diagnostic-source-family.json',family);job.update(main_health_protocol=pp,source_family_manifest=fp)
job['inputs']=list({pin['path']:pin for pin in [*job['inputs'],runtime,pre,pp,fp,*family['main_observer'].values(),family['main_observer_interpreter'],*proofs.values()]}.values())
for pin in job['inputs']:h.checked(pin)
native=load(path,'_serialized_native');native.validate_job(job);negative=[]
for key,value in [('schema','robotron-compiled-full-tail32-quality-original-v1'),('checkpoint',dict(sha256='95726b361f01bceab95bd5deaf6f5534dd1e8d4e7335e38904ae5ca3ee49987d')),('wall_limit_s',719),('actor_slots',list(range(4096,4127))),('quality_leg','R1')]:
    wrong=copy.deepcopy(job);wrong[key]=value
    try:native.validate_job(wrong)
    except (ValueError,KeyError):negative.append(key)
    else:raise AssertionError('Wrong diagnostic scope accepted '+key)
jp=h.put(D/'job.json',job)
provenance=h.put(D/'diagnostic-serialized-source-and-five-scope-rejections.json',dict(original_native=old_job['runtime'],native=runtime,
    source_replacements=changes,exact_source_reverse_verified=True,unchanged_AST_helpers=unchanged,
    all_original_actor_ROM_lease_transport_helpers_AST_unchanged=True,component_proofs=proofs,rejected_scopes=negative,
    original12_health_sources_unchanged=True,poll_s=.2,no_profiler_or_GC_callbacks=True,scientific_case=False,quality_qualified=False))
control_pin=h.pin(P/'control_native_timing_load_diagnostic780_v1.py');control=load(Path(control_pin['path']),'_serialized_native_control')
cfg=dict(unit='robotron-native32-serialized-free314-observer-load600-original01-20261024.service',output=str(D/'execution-original01'),
    argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
    properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=780','TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
    pins=[control.pin(pin['path'])for pin in [*job['inputs'],jp,provenance,control_pin]],observation_s=840)
cp=h.put(D/'controller-config.json',cfg);control.checked_config(cp['path'])
print(json.dumps(dict(config=cp,controller=control_pin,job=jp,provenance=provenance)))
