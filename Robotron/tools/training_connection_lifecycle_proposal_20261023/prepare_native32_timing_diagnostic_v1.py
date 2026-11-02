"""Prepare a new bounded startup-only native diagnostic; never a quality leg."""
import ast,copy,hashlib,importlib.util,json,os,secrets,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023'
T=R/'quality32-protected1741-vs-currentLR125-initialReady-firstSave-original01-preparation-20261023';D=R/'native32-startup-only-main-timing-original01-preparation-20261023'
def load(path,name):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_timing_prepare_h')
def putsource(path,text):
 compile(text,str(path),'exec')
 with path.open('xb')as f:f.write(text.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
 return h.pin(path)
D.mkdir(mode=0o700)
basepath=P/'collect_owned_cap_health_v1.py';base=basepath.read_text()
extra='''

# Diagnostic subclass only; every original collector implementation above is
# byte-identical. No observation/ownership/transport predicate is replaced.
_OriginalCollector=Collector
class Collector(_OriginalCollector):
    def __init__(self,job,output):
        self.diagnostic_timings=[];self._timing_current=None
        super().__init__(job,output)
        actual_tcp=self.io.tcp
        self.io.tcp=lambda:self._timed('tcp',actual_tcp)
    def _resource(self):
        import sys
        cg=next(line.split(':',2)[2]for line in Path('/proc/self/cgroup').read_text().splitlines()if line.startswith('0::'))
        root=Path('/sys/fs/cgroup'+cg)
        return dict(monotonic_s=time.monotonic(),unix_s=time.time(),thread_CPU_s=time.thread_time(),process_CPU_s=time.process_time(),
            gil_enabled=sys._is_gil_enabled(),pid=os.getpid(),cgroup=cg,
            cpu_stat=(root/'cpu.stat').read_text(),cpu_pressure=(root/'cpu.pressure').read_text())
    def _timed(self,name,fn):
        if self._timing_current is None:return fn()
        start=time.monotonic();cpu=time.thread_time();error=None
        try:return fn()
        except BaseException as exc:error=repr(exc);raise
        finally:self._timing_current['stages'].append(dict(name=name,start_monotonic_s=start,end_monotonic_s=time.monotonic(),thread_CPU_s=time.thread_time()-cpu,error=error))
    def capture_deep(self):return self._timed('deep_census_and197_hashes',super().capture_deep)
    def all_fds(self):return self._timed('all384_FD_ownership',super().all_fds)
    def logs(self):return self._timed('all192_actor_logs',super().logs)
    def _observe(self):
        row=dict(index=self.index,before=self._resource(),stages=[]);self._timing_current=row
        actual=self.stream.observe
        self.stream.observe=lambda sample:self._timed('transport_proof',lambda:actual(sample))
        try:return super()._observe()
        except BaseException as error:row['error']=repr(error);raise
        finally:
            self.stream.observe=actual;row['after']=self._resource();self.diagnostic_timings.append(row);self._timing_current=None
'''
collectorpin=putsource(P/'collect_owned_cap_health_diagnostic_timing_v2.py',base+extra)
assert Path(collectorpin['path']).read_bytes()[:len(base.encode())]==base.encode()
pre=h.put(D/'startup-only-timing-diagnostic-precommit.json',dict(schema='robotron-startup-only-native32-timing-precommit-v1',purpose='DIAGNOSTIC_ONLY_NEVER_A_QUALITY_COHORT',
 hypothesis='Actual Torch/server/32MAME workload may delay strict main samples through quota pressure or collection-stage latency. Record actual per-stage timing and throttling; no causal fix selected.',
 checkpoint=h.pin(G/'models_dqn/managed-incumbents/freshCE-LR25-1741M-profile06-confirmed-reset-20261022.pt'),
 original_failed_study=h.pin(T/'closed-invalid-main-sample-gap-independent-root-original01/readback.json'),
 corrected_interpreter_evidence=h.pin(R/'health-observer-authentic32-prefix-native314-resource12-CPU-original01-preparation-20261023/independent-original-native314-resource12-raw-and-scope-closeout.json'),
 bounded_wall_s=120,intentional_stop='Immediately after all32 original1200 prefixes verify, or any original health failure/deadline. Full game tails intentionally not measured.',
 candidate_policy_not_loaded=True,failed_study_retried=False,quality_qualified=False,promotion=False,created_unix_s=time.time()))
native=(B/'run_compiled_full_tail32_quality_owned_health_template_v4.py').read_text();tree=ast.parse(native)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate_job')
old_validation=''.join(native.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
tail=old_validation[old_validation.index('    expected=dict(supervision='):]
validation='''def validate_job(job):
    require(job['schema']=='robotron-startup-only-native32-main-timing-diagnostic-v1'
        and job['diagnostic_role']=='startup_timing_only'and job['diagnostic_only']is True,
        'This source is diagnostic-only and cannot run a quality leg')
    require(not any(key in job for key in ('quality_leg','quality_pair_precommit','minimum_completed_games')),
        'Never adopt a scientific cohort or failed candidate into this diagnostic')
    require(job['diagnostic_precommit']['sha256']==DIAGNOSTIC_SHA and job['checkpoint']['sha256']==REFERENCE_SHA
        and job['expected_policy_clocks']==REFERENCE_CLOCKS,
        'Exact protected reference and original diagnostic precommit required')
    require(job['actor_slots']==list(SLOTS)and job['startup_trace_frames']==1200
        and job['origin_port']==19998 and job['proxy_ports']=={str(k):v for k,v in PORTS.items()}
        and job['device']=='cuda'and job['backend']=='inductor'and job['gpu_uuid']==GPU
        and job['cpu_threads']==2 and job['admission_s']==5400 and job['whole_cohort_timeout_s']==9000
        and type(job['wall_limit_s'])is int and job['wall_limit_s']==120,
        'Keep original startup/backend/actor scope, with explicit120s diagnostic stop')
    require(job['source_package']['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
        and job['validated_CPU_prefix']['sha256']=='7d0cc6f960626fef0b9c0a6c40f68f9dcb55fa98d351c6b25111792156cdb647',
        'Original common backend/source and certified startup proof required')
'''+tail
lines=native.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=[validation+'\n'];native=''.join(lines)
native=native.replace("protocol['schema']=='robotron-native-initial-readiness-main-health-protocol-v4'","protocol['schema']=='robotron-native-startup-timing-diagnostic-main-health-protocol-v1'")
needle='prior_groups=prefix.verified_groups(job,protocol,family,read_main,h)';assert native.count(needle)==1
native=native.replace(needle,"require(protocol['prior_case']is None,'No prior scientific evidence may be inherited');prior_groups=[]")
native=native.replace("job['quality_leg']","job['diagnostic_role']").replace("job['quality_pair_precommit']","job['diagnostic_precommit']")
native=native.replace("'robotron-compiled-full-tail32-quality-original-result-v1'","'robotron-startup-only-native32-timing-diagnostic-result-v1'")
native=native.replace("quality_leg=job['diagnostic_role'],quality_pair_precommit=job['diagnostic_precommit'],","diagnostic_role=job['diagnostic_role'],diagnostic_precommit=job['diagnostic_precommit'],diagnostic_only=True,")
native=native.replace("minimum_completed_games=job['minimum_completed_games'],","quality_game_count_requirement_not_applicable_to_this_diagnostic=True,")
needle='            status=controller.tick()';assert native.count(needle)==1
native=native.replace(needle,"""            if len(actors)==32 and all(row['proxy'].prefix_verified.is_set()for row in actors.values()):
                h.put(output/'original-all32-prefix-diagnostic-stop.json',dict(reason='PRECOMMITTED_STARTUP_ONLY_STOP',observed_unix_s=time.time(),
                    observed_monotonic_s=time.monotonic(),prefixes={str(slot):row['proxy'].prefix_summary for slot,row in actors.items()},quality_qualified=False))
                raise ValueError('PRECOMMITTED_STARTUP_ONLY_STOP_AFTER_ALL32_PREFIXES_NOT_A_QUALITY_RESULT')
"""+needle)
needle="    result=h.put(output/'result.json'";assert native.count(needle)==1
native=native.replace(needle,"    timing_pin=h.put(output/'original-collector-stage-timing.json',dict(records=[]if main_guard is None else main_guard.collector.diagnostic_timings,quality_qualified=False,diagnostic_only=True))\n"+needle)
needle="        complete=complete,errors=errors,";assert native.count(needle)==1
native=native.replace(needle,"        collector_diagnostic_timing=timing_pin,complete=complete,errors=errors,")
native=native.replace('PASS_ALL32_COMMON_COMPILED_CERTIFIED_QUALITY_COHORT_AND_HOST_DRAIN','IMPOSSIBLE_DIAGNOSTIC_SOURCE_MUST_STOP_BEFORE_COMPLETE_COHORT')
native=native.replace('ORIGINAL_COMPILED_QUALITY32_INVALID_NO_RETRY','ORIGINAL_STARTUP_ONLY_TIMING_DIAGNOSTIC_STOPPED_NO_QUALITY')
render=load(P/'render_owned_quality_family_v3.py','_timing_assignment')
deps=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='HEALTH_DEPENDENCIES'for t in n.targets)))
deps['collector']=collectorpin['sha256'];native=render.assignment(native,'HEALTH_DEPENDENCIES',deps)
native=native.replace('HERE=Path(__file__).resolve().parent',"DIAGNOSTIC_SHA="+repr(pre['sha256'])+"\nREFERENCE_SHA='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'\nREFERENCE_CLOCKS=dict(learner_frame_count=1741229950,training_steps=7128160,optimized_samples=27621148672,frame_count=3434514217)\nHERE=Path(__file__).resolve().parent")
runtime=putsource(B/'run_native32_startup_main_timing_diagnostic_original01_v1.py',native)
# Every actor, ROM, lease and tail helper keeps its exact original AST.
newtree=ast.parse(native)
for n in tree.body:
 if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name not in ('validate_job','run'):
  counterpart=next(x for x in newtree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef))and x.name==n.name)
  assert ast.dump(n)==ast.dump(counterpart),n.name
job=copy.deepcopy(json.loads((T/'01-reference/job.json').read_text()))
for key in ['quality_leg','quality_pair_precommit','quality_launch_readiness','minimum_completed_games']:job.pop(key,None)
job.update(schema='robotron-startup-only-native32-main-timing-diagnostic-v1',diagnostic_only=True,diagnostic_role='startup_timing_only',diagnostic_precommit=pre,
 runtime=runtime,output=str(D/'diagnostic-output-original01'),wall_limit_s=120,label='startup-only-native32-main-timing-original01-20261023',created_unix_s=time.time(),
 main_binding=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-binding.json'),
 sessions={str(s):secrets.token_hex(16)for s in range(4096,4128)},connections={str(s):secrets.token_hex(16)for s in range(4096,4128)})
health=json.loads((R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/selected-prefix-health-inputs.json').read_text())
health['binding']=job['main_binding'];health['sources']['collector']=collectorpin
protocol=h.put(D/'diagnostic-main-health-protocol.json',dict(schema='robotron-native-startup-timing-diagnostic-main-health-protocol-v1',prior_case=None,health_job=health))
family=h.put(D/'diagnostic-source-family-manifest.json',dict(schema='robotron-startup-only-diagnostic-source-family-v1',runtime=runtime,
 main_prefix_validator=h.pin(P/'closed_main_health_prefix_v2.py'),main_health_finalizer=h.pin(P/'finalize_owned_main_health_v1.py'),diagnostic_precommit=pre,diagnostic_only=True))
job.update(main_health_protocol=protocol,source_family_manifest=family)
additions=[runtime,collectorpin,protocol,family,pre,job['main_binding'],*health['sources'].values()]
job['inputs']=list({entry['path']:entry for entry in [*job['inputs'],*additions]}.values())
for entry in job['inputs']:h.checked(entry)
subject=load(Path(runtime['path']),'_startup_only_native')
subject.validate_job(job);negative=[]
for key,value in [('schema','robotron-compiled-full-tail32-quality-original-v1'),('wall_limit_s',121),('checkpoint',{'sha256':'3928b61f6262819236876c23d3503aed8d2286e1b1d9857eedc3c1d3905a1efc'}),('quality_leg','R1'),('minimum_completed_games',50)]:
 wrong=copy.deepcopy(job);wrong[key]=value
 try:subject.validate_job(wrong)
 except (ValueError,KeyError):negative.append(key)
 else:raise AssertionError('Invalid diagnostic selection accepted '+key)
jp=h.put(D/'job.json',job)
contract=h.put(D/'diagnostic-source-scope-and-five-rejections.json',dict(original_native=h.pin(B/'run_compiled_full_tail32_quality_owned_health_template_v4.py'),runtime=runtime,
 unchanged_original_helpers_AST=True,collector_original_bytes_exact_prefix=True,original_collector=h.pin(basepath),instrumented_collector=collectorpin,
 job=jp,diagnostic_positive_scope_pass=True,rejected=negative,scientific_case=False,quality_qualified=False))
# Bounded controller keeps exact normal exit/six-archive ownership machinery.
ctl=(P/'control_health_diagnostic_native_resources180_v1.py').read_text()
assert ctl.count("props.get('TimeoutStopSec','5')=='5'")==1
ctl=ctl.replace("props.get('TimeoutStopSec','5')=='5'","props.get('TimeoutStopSec')=='30' and props.get('KillMode')=='mixed'")
ctl=ctl.replace("'TasksMax','TimeoutStopSec','SendSIGKILL'}","'TasksMax','TimeoutStopSec','SendSIGKILL','KillMode'}")
controlpin=putsource(P/'control_native_startup_timing_diagnostic180_v1.py',ctl)
cpu=load(Path(controlpin['path']),'_startup_control')
cfg=dict(unit='robotron-native32-startup-main-timing-original01-20261023.service',output=str(D/'execution-original01'),
 argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
 properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
 pins=[cpu.pin(pin['path'])for pin in [*job['inputs'],jp,contract]],observation_s=240)
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path'])
print(json.dumps(dict(precommit=pre,source_scope_contract=contract,runtime=runtime,controller=controlpin,config=cp)))
