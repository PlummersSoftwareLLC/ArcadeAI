"""Prepare one new reference-only load after independent capacity closure."""
import ast,copy,fcntl,importlib.util,json,os,secrets,socket,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
D=R/'native32-inet-diag-filtered-free314-load600-original01-preparation-20261024'
OLD=R/'native32-serialized-free314-observer-load600-original01-preparation-20261024'
C=R/'inet-diag-filtered-serialized-free314-client-CPU-original01-preparation-20261024'
N=R/'inet-diag-filtered-serialized-free314-six-failures-CPU-original01-preparation-20261024'
F=R/'inet-diag-filtered-capture-family-contracts-CPU-original01-preparation-20261024'
Q=R/'inet-diag-filtered-query-feasibility-CPU-original01-preparation-20261024'
M=R/'inet-diag-filtered-fullscope-CPU-original01-preparation-20261024'
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_filtered_native_h')
def read(pin):return json.loads(h.checked(pin).read_bytes())
goal=json.loads((R.parent/'state.json').read_bytes())['optimization_goal']
assert goal['actual_running_wait']is None and goal['all_current_original_handles_terminal']and not goal['full_source_freeze']
proofs=dict(contracts=h.pin(F/'independent-original187-rejections-five-failures-and-filtered-capture-source-closeout.json'),
    query=h.pin(Q/'independent-original40-filtered-kernel-dumps-query-predicate-and-scope-closeout.json'),
    positive=h.pin(C/'independent-original-inet-diag-filtered-client-runtime-and-raw-closeout.json'),
    negative=h.pin(N/'independent-original-six-failures-eight-scopes-and-signal-readback.json'),
    resource=h.pin(M/'independent-original-filtered-capacity-and-scope-closeout.json'),
    capture_provenance=h.pin(F/'source-family-provenance.json'),
    prior_failed_native=h.pin(OLD/'independent-original-failed999-three-identical-rows-and-all-scopes-closeout.json'))
capacity=read(proofs['resource'])
assert capacity['resource_passed']is True and capacity['synthetic_samples']==48332 and capacity['prior_case_groups']==8192 and capacity['actual_elapsed_s']<600
assert read(proofs['contracts'])['typed_negative_rejections']==187
assert read(proofs['query'])['exact_original_source_OR_destination_port9998_predicate']is True
assert read(proofs['positive'])['actual_worker_GIL0_and_binary_verified']is True
assert read(proofs['negative'])['all8_actual_scope_archives_resources_argv_pins_release_and_birth_absence_verified']is True
oldjob=read(h.pin(OLD/'job.json'));oldfamily=read(oldjob['source_family_manifest']);oldhealth=read(oldjob['main_health_protocol'])['health_job']
health=read(h.pin(F/'unselected-health-job.json'));context=read(h.pin(C/'source-family-component.json'))
assert context['main_observer']==oldfamily['main_observer']
monitor=h.pin(R/'currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024/postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.check_output(['/usr/bin/python3.12','-I','-B',monitor['path']],text=True,timeout=25));assert main['client_count']==192 and main['held_inputs']==197
h.checked(oldjob['lease']);fd=os.open(oldjob['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
finally:os.close(fd)
for port in (19998,*range(20000,20032)):
    with socket.socket()as sock:sock.bind(('127.0.0.1',port))
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=10);assert oldjob['gpu_uuid']not in gpu.stdout
D.mkdir(mode=0o700)
pre=h.put(D/'precommitted-filtered-inet-diag-reference-load600.json',dict(schema='robotron-filtered-inet-diag-reference600-precommit-v1',
    purpose='FIXED_PORT_KERNEL_TCP_DUMP_NATIVE_LOAD_INTEGRATION_ONLY_NO_QUALITY_RESULT',checkpoint=oldjob['checkpoint'],component_proofs=proofs,
    selected_health_job=h.pin(F/'unselected-health-job.json'),worker_interpreter=context['main_observer_interpreter'],poll_s=.2,
    minimum_native_wall_s=600,wall_limit_s=720,unit_runtime_s=780,native_CPU=12,worker_CPU=2,expected_native_exit=1,expected_positive_observer_exit=0,
    stop='After600s native wall and all32 original prefixes, or first original health/runtime failure or720s wall. No retry.',
    health_ownership_timing_budget_and_game_gates_unchanged=True,old_failed_native_and_scientific_cases_not_retried=True,
    candidate_not_loaded=True,current_main=main,current_main_monitor=monitor,private_resources_free=True,quality_qualified=False,created_unix_s=time.time()))
original=Path(oldjob['runtime']['path']).read_text();source=original;changes=[]
def change(a,b):
    global source
    assert source.count(a)==1,(a,source.count(a));source=source.replace(a,b);changes.append((a,b))
change('DIAGNOSTIC_SHA='+repr(oldjob['diagnostic_precommit']['sha256']),'DIAGNOSTIC_SHA='+repr(pre['sha256']))
for key in ('io','primitives'):change(oldhealth['sources'][key]['sha256'],health['sources'][key]['sha256'])
for a,b in [('robotron-native32-serialized-free314-observer-load-diagnostic-v1','robotron-native32-inet-diag-filtered-free314-load-diagnostic-v1'),
    ('robotron-native32-serialized-free314-observer-load-diagnostic-result-v1','robotron-native32-inet-diag-filtered-free314-load-diagnostic-result-v1'),
    ('robotron-native-serialized-free314-observer-load-diagnostic-main-health-protocol-v1','robotron-native-inet-diag-filtered-free314-load-main-health-protocol-v1'),
    ('PRECOMMITTED_SERIALIZED_FREE314_REFERENCE600_LOAD_STOP','PRECOMMITTED_INET_DIAG_FILTERED_REFERENCE600_LOAD_STOP'),
    ('ORIGINAL_SERIALIZED_FREE314_REFERENCE_LOAD_DIAGNOSTIC_STOPPED_NO_QUALITY','ORIGINAL_INET_DIAG_FILTERED_REFERENCE_LOAD_STOPPED_NO_QUALITY')]:change(a,b)
reverse=source
for a,b in reversed(changes):assert reverse.count(b)==1;reverse=reverse.replace(b,a)
assert reverse==original;unchanged=[]
for node in ast.parse(original).body:
    if isinstance(node,(ast.FunctionDef,ast.ClassDef))and node.name not in ('run','validate_job'):
        other=next(n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name==node.name)
        assert ast.dump(node)==ast.dump(other);unchanged.append(node.name)
runtime_path=B/'run_native32_inet_diag_filtered_free314_load600_diagnostic_original01_v1.py';compile(source,str(runtime_path),'exec')
with runtime_path.open('xb')as f:f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
runtime=h.pin(runtime_path);job=copy.deepcopy(oldjob);job.update(schema='robotron-native32-inet-diag-filtered-free314-load-diagnostic-v1',runtime=runtime,diagnostic_precommit=pre,
    output=str(D/'diagnostic-output-original01'),label='native32-inet-diag-filtered-free314-load600-original01-20261024',
    sessions={str(s):secrets.token_hex(16)for s in range(4096,4128)},connections={str(s):secrets.token_hex(16)for s in range(4096,4128)},created_unix_s=time.time())
protocol=read(oldjob['main_health_protocol']);protocol.update(schema='robotron-native-inet-diag-filtered-free314-load-main-health-protocol-v1',health_job=health)
pp=h.put(D/'diagnostic-main-health-protocol.json',protocol)
family=copy.deepcopy(oldfamily);family.update(schema='robotron-inet-diag-filtered-native32-load-source-family-v1',runtime=runtime,diagnostic_precommit=pre,
    main_observer=context['main_observer'],main_observer_interpreter=context['main_observer_interpreter'],inet_diag_capture_components=proofs)
fp=h.put(D/'diagnostic-source-family.json',family);job.update(main_health_protocol=pp,source_family_manifest=fp)
job['inputs']=list({p['path']:p for p in [*job['inputs'],runtime,pre,pp,fp,*health['sources'].values(),*proofs.values()]}.values())
for pin in job['inputs']:h.checked(pin)
native=load(runtime_path,'_filtered_native_case');native.validate_job(job);negative=[]
for key,value in [('schema','robotron-compiled-full-tail32-quality-original-v1'),('checkpoint',dict(sha256='95726b361f01bceab95bd5deaf6f5534dd1e8d4e7335e38904ae5ca3ee49987d')),('wall_limit_s',719),('actor_slots',list(range(4096,4127))),('quality_leg','R1')]:
    wrong=copy.deepcopy(job);wrong[key]=value
    try:native.validate_job(wrong)
    except (ValueError,KeyError):negative.append(key)
    else:raise AssertionError('Wrong diagnostic scope accepted '+key)
jp=h.put(D/'job.json',job)
provenance=h.put(D/'filtered-capture-native-source-and-five-scope-rejections.json',dict(original_native=oldjob['runtime'],native=runtime,source_replacements=changes,
    exact_source_reverse_verified=True,unchanged_AST_helpers=unchanged,all_original_actor_ROM_lease_transport_helpers_AST_unchanged=True,
    component_proofs=proofs,rejected_scopes=negative,other10_health_sources_unchanged=True,health_and_game_limits_unchanged=True,scientific_case=False,quality_qualified=False))
control_pin=h.pin(P/'control_native_timing_load_diagnostic780_v1.py');control=load(Path(control_pin['path']),'_filtered_native_control')
cfg=dict(unit='robotron-native32-inet-diag-filtered-free314-load600-original01-20261024.service',output=str(D/'execution-original01'),
    argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
    properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=780','TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
    pins=[control.pin(p['path'])for p in [*job['inputs'],jp,provenance,control_pin]],observation_s=840)
cp=h.put(D/'controller-config.json',cfg);control.checked_config(cp['path']);print(json.dumps(dict(config=cp,controller=control_pin,job=jp,provenance=provenance)))
