"""New unselected free-threaded worker context and real component/failure jobs."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
C=R/'free314-main-health-client-context-CPU-original01-preparation-20261024'
N=R/'free314-main-health-six-failure-scopes-CPU-original01-preparation-20261024'
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_free314_prepare_h')
cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_free314_prepare_cpu')
def read(path):return json.loads(Path(path).read_bytes())
def put_source(path,text):
    compile(text,str(path),'exec')
    with path.open('xb')as f:f.write(text.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return h.pin(path)
def transform(path,changes,target):
    original=path.read_text();value=original
    for a,b in changes:assert value.count(a)==1,(a,value.count(a));value=value.replace(a,b)
    reverse=value
    for a,b in reversed(changes):assert reverse.count(b)==1;reverse=reverse.replace(b,a)
    assert reverse==original
    return put_source(target,value)

state=read(R.parent/'state.json');goal=state['optimization_goal']
assert goal['all_current_original_handles_terminal'] is True and goal['actual_running_wait']is None
assert goal['full_source_freeze'] is False
selection=goal['future_main_observer_isolation']['prospective_free314_selection'];h.checked(selection)
binary=h.pin('/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python')
worker_changes=[
    ('def run(job,jp,h,protocol,worker_source):',
     "def run(job,jp,h,protocol,worker_source):\n    require(sys.version_info[:2]==(3,14)and sys._is_gil_enabled()is False,'Exact free-threaded3.14 observer runtime required')\n    require(job['worker_interpreter']['path']==sys.executable=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','Exact selected observer interpreter path required');h.checked(job['worker_interpreter'])"),
    ("            tick=time.monotonic();require(tick<job['deadline_monotonic_s'],'Original native deadline reached; no late observer rescue')",
     "            require(sys._is_gil_enabled()is False,'Original observer GIL context changed')\n            tick=time.monotonic();require(tick<job['deadline_monotonic_s'],'Original native deadline reached; no late observer rescue')"),
    ("    require('torch'not in sys.modules,'Observer unexpectedly imported Torch')",
     "    require('torch'not in sys.modules,'Observer unexpectedly imported Torch')\n    require(sys.version_info[:2]==(3,14)and sys._is_gil_enabled()is False,'Original observer free-threaded context changed')"),
    ("        protocol_source=job['protocol_source'],owner=owner,parent=job['parent'],nonce=job['nonce'],success=success,",
     "        protocol_source=job['protocol_source'],owner=owner,parent=job['parent'],nonce=job['nonce'],success=success,\n        interpreter=dict(binary=job['worker_interpreter'],executable=sys.executable,version=sys.version,major_minor=list(sys.version_info[:2]),GIL_enabled=sys._is_gil_enabled()),")]
worker=transform(P/'run_dedicated_main_health_v1.py',worker_changes,P/'run_dedicated_main_health_free314_v2.py')
client_changes=[
    ("        for pin in self.sources.values():h.checked(pin)",
     "        for pin in self.sources.values():h.checked(pin)\n        self.interpreter=family['main_observer_interpreter'];h.checked(self.interpreter)\n        require(self.interpreter['path']=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','Exact free314 observer interpreter required')"),
    ("            protocol_source=self.sources['protocol'],health_job=protocol['health_job'],prior_groups=prior,observer_unit=unit[:-8]+'-mainhealth.service',",
     "            protocol_source=self.sources['protocol'],health_job=protocol['health_job'],prior_groups=prior,observer_unit=unit[:-8]+'-mainhealth.service',worker_interpreter=self.interpreter,"),
    ("        argv=['/usr/bin/python3.12','-I','-B',self.sources['worker']['path'],'--execute','--job',self.jobpin['path'],",
     "        argv=[self.interpreter['path'],'-Xgil=0','-I','-B',self.sources['worker']['path'],'--execute','--job',self.jobpin['path'],"),
    ("        pins=[*protocol['health_job']['sources'].values(),protocol['health_job']['binding'],*self.sources.values(),jp,job['runtime'],",
     "        pins=[self.interpreter,*protocol['health_job']['sources'].values(),protocol['health_job']['binding'],*self.sources.values(),jp,job['runtime'],")]
client=transform(P/'dedicated_main_health_client_v1.py',client_changes,P/'dedicated_main_health_client_free314_v2.py')
review_changes=[
    ("    control=h.load('_dedicated_review_control',h.checked(sources['controller']))",
     "    interpreter=family['main_observer_interpreter'];h.checked(interpreter)\n    require(interpreter['path']=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','Exact free314 observer binary required')\n    control=h.load('_dedicated_review_control',h.checked(sources['controller']))"),
    ("    expected_argv=['/usr/bin/python3.12','-I','-B',sources['worker']['path'],'--execute','--job',life['worker_job']['path'],",
     "    require(wj['worker_interpreter']==interpreter and outcome['interpreter']['binary']==interpreter\n        and outcome['interpreter']['executable']==interpreter['path']\n        and outcome['interpreter']['major_minor']==[3,14]and outcome['interpreter']['GIL_enabled']is False\n        and outcome['interpreter']['version'].startswith('3.14.'),'Actual original observer free-threaded runtime differs')\n    expected_argv=[interpreter['path'],'-Xgil=0','-I','-B',sources['worker']['path'],'--execute','--job',life['worker_job']['path'],"),
    ("    for pin in [life['worker_job'],native_pin,native['runtime'],native['main_health_protocol'],native['source_family_manifest'],wj['prior_groups'],*sources.values()]:",
     "    for pin in [interpreter,life['worker_job'],native_pin,native['runtime'],native['main_health_protocol'],native['source_family_manifest'],wj['prior_groups'],*sources.values()]:")]
reviewer=transform(P/'review_dedicated_main_health_v1.py',review_changes,P/'review_dedicated_main_health_free314_v2.py')
for name in ('load','birth','show','own_cgroup','verify_parent','verify_self','main'):
    def definition(path):return next(n for n in ast.parse(Path(path).read_text()).body if isinstance(n,ast.FunctionDef)and n.name==name)
    assert ast.dump(definition(P/'run_dedicated_main_health_v1.py'))==ast.dump(definition(worker['path'])),name
C.mkdir(mode=0o700);N.mkdir(mode=0o700)
oldC=R/'dedicated-native-client-finalizer-review-longscope-CPU-original01-preparation-20261023'
family=read(oldC/'source-family-component.json');family['main_observer'].update(client=client,worker=worker,reviewer=reviewer)
family['main_observer_interpreter']=binary
family['prospective_selection']=selection
fp=h.put(C/'source-family-component.json',family)
current_protocol=read(R/'native32-dedicated-observer-critical-path600-original01-preparation-20261024/diagnostic-main-health-protocol.json')
health=current_protocol['health_job']
pp=h.put(C/'component-main-health-protocol.json',dict(schema='robotron-free314-native-client-component-protocol-v1',health_job=health))
cjob=read(oldC/'job.json');cjob.update(output=str(C/'output-original01'),source_family_manifest=fp,main_health_protocol=pp,controller_directory=str(C))
cjp=h.put(C/'job.json',cjob)
cfg=read(oldC/'controller-config.json');cfg.update(unit='robotron-free314-native-client-component-original01-20261024.service',output=str(C/'execution-original01'),
    argv=['/usr/bin/python3.12','-I','-B',cjob['runtime']['path'],'--execute','--job',cjp['path'],'--job-sha256',cjp['sha256'],'--source-sha256',cjob['runtime']['sha256']])
component_pins=[cjp,fp,pp,*family['main_observer'].values(),binary,family['main_health_finalizer'],family['native_closure'],*health['sources'].values(),health['binding'],cjob['helpers'],cjob['reader'],cjob['runtime']]
cfg['pins']=[cpu.pin(pin['path'])for pin in {p['path']:p for p in component_pins}.values()]
ccp=h.put(C/'controller-config.json',cfg);cpu.checked_config(ccp['path'])
neg_changes=[
    ("for key in ['helpers','reader','archive','closer','CPU_controller','protocol_source','worker','parent_fixture']:",
     "for key in ['helpers','reader','archive','closer','CPU_controller','protocol_source','worker','parent_fixture','worker_interpreter']:"),
    ("argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--job',jp['path'],",
     "argv=([job['worker_interpreter']['path'],'-Xgil=0']if source==job['worker']else['/usr/bin/python3.12'])+['-I','-B',source['path'],'--execute','--job',jp['path'],"),
    ("wjob=dict(schema='robotron-dedicated-main-health-job-v1',output=str(directory/'observations'),helpers=job['helpers'],protocol_source=job['protocol_source'],health_job=job['health_job'],prior_groups=prior,",
     "wjob=dict(schema='robotron-dedicated-main-health-job-v1',output=str(directory/'observations'),helpers=job['helpers'],protocol_source=job['protocol_source'],health_job=job['health_job'],prior_groups=prior,worker_interpreter=job['worker_interpreter'],"),
    ("pins=[*job['health_job']['sources'].values(),job['health_job']['binding'],job['protocol_source'],selected['job'],selected['source'],prior]",
     "pins=[job['worker_interpreter'],*job['health_job']['sources'].values(),job['health_job']['binding'],job['protocol_source'],selected['job'],selected['source'],prior]")]
neg_driver=transform(P/'validate_dedicated_health_failures_v1.py',neg_changes,P/'validate_dedicated_health_free314_failures_v2.py')
oldN=R/'dedicated-main-health-six-failure-scopes-CPU-original01-preparation-20261023'
njob=read(oldN/'job.json');njob.update(output=str(N/'output-original01'),parent_unit='robotron-free314-six-negative-workers-original01-20261024.service',
    unit_prefix='robotron-free314-negative-original01-20261024',worker=worker,worker_interpreter=binary,health_job=health)
njp=h.put(N/'job.json',njob);ncfg=read(oldN/'controller-config.json')
ncfg.update(unit=njob['parent_unit'],output=str(N/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',neg_driver['path'],'--execute','--job',njp['path'],'--job-sha256',njp['sha256'],'--source-sha256',neg_driver['sha256']],
    pins=[cpu.pin(pin['path'])for pin in {p['path']:p for p in [njp,neg_driver,binary,worker,*[njob[key]for key in ('helpers','reader','archive','closer','CPU_controller','protocol_source','parent_fixture')],*health['sources'].values(),health['binding']]}.values()])
ncp=h.put(N/'controller-config.json',ncfg);cpu.checked_config(ncp['path'])
provenance=h.put(C/'free314-context-source-provenance.json',dict(schema='robotron-free314-unselected-health-context-source-provenance-v1',
    prospective_selection=selection,worker=worker,client=client,reviewer=reviewer,interpreter=binary,
    worker_changes=worker_changes,client_changes=client_changes,reviewer_changes=review_changes,
    exact_source_reverses_verified=True,worker_identity_signal_parent_deadline_and_main_helpers_AST_unchanged=True,
    cadence_s=.2,health_engine_and_all12_sources_unchanged=True,original_game_sources_unchanged=True,
    worker_scope_CPU=2,worker_scope_memory_GiB=4,scientific_selection=False,quality_qualified=False,created_unix_s=time.time()))
print(json.dumps(dict(component_config=ccp,negative_config=ncp,source_provenance=provenance,worker=worker,client=client,reviewer=reviewer)))
