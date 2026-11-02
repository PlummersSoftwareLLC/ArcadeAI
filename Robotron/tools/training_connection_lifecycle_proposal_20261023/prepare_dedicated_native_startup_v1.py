"""Close9/66 source contracts and prepare one NEW dedicated-observer startup test."""
import ast,copy,importlib.util,json,os,secrets,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
F=R/'dedicated-observer-quality-template-contracts-CPU-original01-preparation-20261023';D=R/'native32-dedicated-CPU-observer-startup-original01-preparation-20261023'
def load(path,name):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_dedicated_start_h');reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_dedicated_start_reader');arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_dedicated_start_arc');cl=load(P/'independent_component_closeout_v3.py','_dedicated_start_cl')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
proof=cl.closeout(F,h,arc,read,0);reportpin=h.pin(F/'output-original01/report.json');report=read(reportpin)
assert report['tests']==9 and len(report['negative_checks'])==66
jobfamily=read(h.pin(F/'job.json'));provenance=read(h.pin(F/'unselected-dedicated-native-source-provenance.json'))
for pin in [*jobfamily['templates'].values(),*jobfamily['observer_sources'].values(),jobfamily['subject'],jobfamily['dedicated_finalizer']]:h.checked(pin)
proof.update(report=reportpin,tests=9,negative_checks=66,unselected_source_provenance=h.pin(F/'unselected-dedicated-native-source-provenance.json'),unchanged_game_helpers_and_confirmation_math_verified=True,twenty_wrong_actual_worker_lifecycle_joins_rejected=True,quality_qualified=False)
guardpath=F/'independent-original-nine-contracts66-and-selected-source-closeout.json'
if guardpath.exists():
 oldproof=read(h.pin(guardpath));assert oldproof['owner']==proof['owner']and oldproof['closure']==proof['closure']and oldproof['report']==reportpin
 guardproof=h.pin(guardpath)
else:guardproof=h.put(guardpath,proof)
D.mkdir(mode=0o700,exist_ok=True)
assert not(D/'job.json').exists()and not(D/'execution-original01').exists(),'No prepared original job or payload may be replaced/adopted'
reference=h.pin(G/'models_dqn/managed-incumbents/freshCE-LR25-1741M-profile06-confirmed-reset-20261022.pt')
pre_value=dict(schema='robotron-dedicated-observer-native-startup-diagnostic-precommit-v1',purpose='STARTUP_AND_OWN_CPU_MONITOR_INTEGRATION_ONLY_NOT_A_QUALITY_COHORT',
 checkpoint=reference,source_contract_closeout=guardproof,bounded_wall_s=120,
 intentional_stop='After all32 original1200 prefixes verify, on an original failure, or120s native wall. Close health independently to inspect monitoring coverage; no game/confirmation qualification.',
 expected_native_original_exit=1,positive_integration_requires='All32 original closed prefixes, correct loaded protected reference, independently valid own2CPU worker/full raw replay and all actual scope/private cleanup proofs.',
 prior_scientific_candidate_retried=False,prior_diagnostic_restarted=False,candidate_policy_not_loaded=True,quality_qualified=False,promotion=False,created_unix_s=time.time())
pre_path=D/'startup-only-dedicated-observer-precommit.json'
if pre_path.exists():
 original=read(h.pin(pre_path));pre_value['created_unix_s']=original['created_unix_s'];assert pre_value==original;pre=h.pin(pre_path)
else:pre=h.put(pre_path,pre_value)
oldpath=Path(jobfamily['templates']['runtime']['path']);native=oldpath.read_text();tree=ast.parse(native)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate_job');oldvalidation=''.join(native.splitlines(keepends=True)[node.lineno-1:node.end_lineno]);tail=oldvalidation[oldvalidation.index('    expected=dict(supervision='):]
validation='''def validate_job(job):
    require(job['schema']=='robotron-native32-dedicated-observer-startup-diagnostic-v1'
        and job['diagnostic_role']=='startup_only'and job['diagnostic_only']is True,
        'This runtime is a startup/monitor diagnostic, never a quality leg')
    require(not any(key in job for key in ('quality_leg','quality_pair_precommit','minimum_completed_games')),
        'No failed scientific cohort/candidate adoption')
    require(job['diagnostic_precommit']['sha256']==DIAGNOSTIC_SHA and job['checkpoint']['sha256']==REFERENCE_SHA
        and job['expected_policy_clocks']==REFERENCE_CLOCKS,'Exact protected reference/precommit required')
    require(job['actor_slots']==list(SLOTS)and job['startup_trace_frames']==1200 and job['origin_port']==19998
        and job['proxy_ports']=={str(k):v for k,v in PORTS.items()}and job['device']=='cuda'and job['backend']=='inductor'
        and job['gpu_uuid']==GPU and job['cpu_threads']==2 and job['admission_s']==5400 and job['whole_cohort_timeout_s']==9000
        and type(job['wall_limit_s'])is int and job['wall_limit_s']==120,'Exact bounded startup-only scope required')
    require(job['source_package']['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
        and job['validated_CPU_prefix']['sha256']=='7d0cc6f960626fef0b9c0a6c40f68f9dcb55fa98d351c6b25111792156cdb647',
        'Original common compiled backend/certified prefix required')
'''+tail
lines=native.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=[validation+'\n'];native=''.join(lines)
def replace(text,a,b):assert text.count(a)==1,(a,text.count(a));return text.replace(a,b)
native=replace(native,'HERE=Path(__file__).resolve().parent',"DIAGNOSTIC_SHA="+repr(pre['sha256'])+"\nREFERENCE_SHA="+repr(reference['sha256'])+"\nREFERENCE_CLOCKS=dict(learner_frame_count=1741229950,training_steps=7128160,optimized_samples=27621148672,frame_count=3434514217)\nHERE=Path(__file__).resolve().parent")
native=replace(native,"protocol['schema']=='robotron-native-dedicated-main-health-protocol-v5'","protocol['schema']=='robotron-native-dedicated-startup-diagnostic-main-health-protocol-v1'")
native=replace(native,'prior_groups=prefix.verified_groups(job,protocol,family,read_main,h)',"require(protocol['prior_case']is None,'Diagnostic cannot inherit scientific evidence');prior_groups=[]")
native=native.replace("job['quality_leg']","job['diagnostic_role']").replace("job['quality_pair_precommit']","job['diagnostic_precommit']")
native=replace(native,"schema='robotron-compiled-full-tail32-quality-original-result-v1'","schema='robotron-native32-dedicated-observer-startup-diagnostic-result-v1'")
native=replace(native,"quality_leg=job['diagnostic_role'],quality_pair_precommit=job['diagnostic_precommit'],","diagnostic_role=job['diagnostic_role'],diagnostic_precommit=job['diagnostic_precommit'],diagnostic_only=True,")
native=replace(native,"minimum_completed_games=50,","quality_game_count_requirement_not_applicable_to_this_diagnostic=True,")
needle='            status=controller.tick()'
native=replace(native,needle,"""            if len(actors)==32 and all(row['proxy'].prefix_verified.is_set()for row in actors.values()):
                h.put(output/'original-all32-prefix-diagnostic-stop.json',dict(reason='PRECOMMITTED_DEDICATED_STARTUP_ONLY_STOP',
                    observed_unix_s=time.time(),observed_monotonic_s=time.monotonic(),
                    prefixes={str(slot):row['proxy'].prefix_summary for slot,row in actors.items()},quality_qualified=False))
                raise ValueError('PRECOMMITTED_DEDICATED_STARTUP_ONLY_STOP_AFTER_ALL32_PREFIXES_NOT_A_QUALITY_RESULT')
"""+needle)
# Only this diagnostic may close a healthy observer after its intentional early
# game stop. Scientific native code still aborts its observer on any failed leg.
native=replace(native,"case_already_failed=bool(errors))","case_already_failed=False)  # diagnostic health coverage only; never qualifies games")
native=replace(native,"    result=h.put(output/'result.json'","    require(not complete,'Startup-only diagnostic must not reach quality-complete branch')\n    result=h.put(output/'result.json'")
native=native.replace('PASS_ALL32_COMMON_COMPILED_CERTIFIED_QUALITY_COHORT_AND_HOST_DRAIN','IMPOSSIBLE_STARTUP_DIAGNOSTIC_QUALITY_COMPLETE').replace('ORIGINAL_COMPILED_QUALITY32_INVALID_NO_RETRY','ORIGINAL_DEDICATED_STARTUP_DIAGNOSTIC_STOPPED_NO_QUALITY')
path=B/'run_native32_dedicated_observer_startup_diagnostic_original01_v1.py';compile(native,str(path),'exec')
with path.open('xb')as f:f.write(native.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
runtime=h.pin(path)
for n in tree.body:
 if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name not in ('run','validate_job'):
  other=next(x for x in ast.parse(native).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))and x.name==n.name);assert ast.dump(n)==ast.dump(other),n.name
old=R/'quality32-protected1741-vs-currentLR125-initialReady-firstSave-original01-preparation-20261023';job=copy.deepcopy(read(h.pin(old/'01-reference/job.json')))
for key in ['quality_leg','quality_pair_precommit','quality_launch_readiness','minimum_completed_games']:job.pop(key,None)
job.update(schema='robotron-native32-dedicated-observer-startup-diagnostic-v1',diagnostic_role='startup_only',diagnostic_only=True,diagnostic_precommit=pre,
 runtime=runtime,output=str(D/'diagnostic-output-original01'),wall_limit_s=120,label='native32-dedicated-observer-startup-original01-20261023',checkpoint=reference,
 main_binding=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-binding.json'),
 sessions={str(s):secrets.token_hex(16)for s in range(4096,4128)},connections={str(s):secrets.token_hex(16)for s in range(4096,4128)},created_unix_s=time.time())
health=read(h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/selected-prefix-health-inputs.json'));health['binding']=job['main_binding']
protocol=h.put(D/'diagnostic-main-health-protocol.json',dict(schema='robotron-native-dedicated-startup-diagnostic-main-health-protocol-v1',prior_case=None,health_job=health))
family=h.put(D/'diagnostic-source-family.json',dict(schema='robotron-dedicated-startup-diagnostic-source-family-v1',runtime=runtime,main_observer=jobfamily['observer_sources'],
 main_health_finalizer=jobfamily['dedicated_finalizer'],main_prefix_validator=h.pin(P/'closed_main_health_prefix_v2.py'),native_closure=h.pin(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),diagnostic_precommit=pre))
job.update(main_health_protocol=protocol,source_family_manifest=family)
job['inputs']=list({v['path']:v for v in [*job['inputs'],runtime,pre,protocol,family,*jobfamily['observer_sources'].values(),jobfamily['dedicated_finalizer'],job['main_binding'],*health['sources'].values()]}.values())
for pin in job['inputs']:h.checked(pin)
subject=load(path,'_dedicated_start_runtime');subject.validate_job(job);negative=[]
for key,value in [('schema','robotron-compiled-full-tail32-quality-original-v1'),('quality_leg','R1'),('minimum_completed_games',50),('wall_limit_s',121),('checkpoint',dict(sha256='3928b61f6262819236876c23d3503aed8d2286e1b1d9857eedc3c1d3905a1efc'))]:
 wrong=copy.deepcopy(job);wrong[key]=value
 try:subject.validate_job(wrong)
 except (ValueError,KeyError):negative.append(key)
 else:raise AssertionError('Wrong diagnostic scope accepted '+key)
jp=h.put(D/'job.json',job)
contract=h.put(D/'diagnostic-source-scope-and-five-rejections.json',dict(native_template=jobfamily['templates']['runtime'],runtime=runtime,job=jp,unchanged_original_game_helpers_AST=True,diagnostic_scope_positive=True,rejected=negative,
 intentional_stop_does_not_qualify_games=True,scientific_native_abort_behavior_unchanged=True,quality_qualified=False))
cpu=load(P/'control_native_startup_timing_diagnostic180_v1.py','_dedicated_start_ctl')
cfg=dict(unit='robotron-native32-dedicated-observer-startup-original01-20261023.service',output=str(D/'execution-original01'),
 argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
 properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],pins=[cpu.pin(v['path'])for v in [*job['inputs'],jp,contract]],observation_s=240)
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path'])
print(json.dumps(dict(source_guard_closeout=guardproof,native_config=cp,diagnostic_contract=contract,job=jp)))
