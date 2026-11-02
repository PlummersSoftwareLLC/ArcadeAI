"""Unselected quality templates bound to the independently tested kernel reader."""
import ast,copy,importlib.util,json,os,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
OLD=R/'filtered-kernel-quality-template-contracts-CPU-original01-preparation-20261024'
D=R/'transient-live-kernel-quality-template-contracts-CPU-original01-preparation-20261024'
C=R/'transient-live-filtered-free314-client-CPU-original01-preparation-20261024'
F=R/'inet-diag-filtered-capture-family-contracts-CPU-original01-preparation-20261024'
M=R/'inet-diag-filtered-fullscope-CPU-original01-preparation-20261024'
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_kernel_template_h');cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_kernel_template_cpu')
def read(path):return json.loads(Path(path).read_bytes())
records=[]
def create(original,path,changes):
    before=Path(original).read_text();source=before
    for a,b in changes:assert source.count(a)==1,(a,source.count(a));source=source.replace(a,b)
    reverse=source
    for a,b in reversed(changes):assert reverse.count(b)==1;reverse=reverse.replace(b,a)
    assert reverse==before;compile(source,str(path),'exec')
    with path.open('xb')as f:f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    result=h.pin(path);records.append(dict(original=h.pin(original),prospective=result,changes=changes,exact_reverse_verified=True));return result
oldjob=read(OLD/'job.json');templates=copy.deepcopy(oldjob['templates']);health=read(F/'unselected-health-job.json');family=read(C/'source-family-component.json')
oldruntime=Path(templates['runtime']['path']);newruntime=B/'run_compiled_full_tail32_quality_transient_kernel_template_v4.py'
oldcodec='7f39fb03c43bb9856873913d59329bbe05717bfc8fd5a47abbfd7b1a31bc1a7f';newcodec=family['main_observer']['protocol']['sha256']
assert newcodec=='f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10'
templates['runtime']=create(oldruntime,newruntime,[(oldcodec,newcodec)])
templates['native_controller']=create(templates['native_controller']['path'],B/'control_compiled_full_tail32_quality_transient_kernel_template_v4.py',[(oldruntime.name,newruntime.name)])
templates['leg_reviewer']=create(templates['leg_reviewer']['path'],B/'read_compiled_quality32_transient_kernel_template_v4.py',[(oldruntime.name,newruntime.name)])
renderer=create(oldjob['subject']['path'],P/'render_transient_kernel_quality_family_v7.py',[(oldruntime.name,newruntime.name)])
D.mkdir(mode=0o700)
provenance=h.put(D/'source-changes-and-unchanged-scientific-gates.json',dict(schema='robotron-unselected-transient-kernel-quality-family-provenance-v1',source_changes=records,
    only_observer_codec_dependency_hash_changed=True,all12_health_sources_unchanged=True,
    all_game_actor_ROM_lease_and_confirmation_math_AST_unchanged=True,failed2739_pair_policy_and_all4_clock_floors_unchanged=True,
    min50_all32_every_tail_and_separate_C1_C2_5percent_mean_and_preserved_median_unchanged=True,
    actual_native600_positive_closure_still_required=True,no_policy_or_scientific_selection=True,quality_qualified=False,created_unix_s=time.time()))
job=copy.deepcopy(oldjob);job.update(output=str(D/'output-original01'),templates=templates,subject=renderer,observer_sources=family['main_observer'],
    client_component_job=h.pin(C/'job.json'),client_component_report=h.pin(C/'output-original01/report.json'),client_component_owner=h.pin(C/'execution-original01/root-original-identity.json'),client_component_config=h.pin(C/'controller-config.json'),
    prospective_source_provenance=provenance)
jp=h.put(D/'job.json',job);cfg=read(OLD/'controller-config.json');driver=job['driver']
pins=[v for v in job.values()if isinstance(v,dict)and 'path'in v]+[jp,*templates.values(),*family['main_observer'].values(),family['main_observer_interpreter'],*health['sources'].values(),health['binding']]
pins += [h.pin(p['path'])for p in read(C/'controller-config.json')['pins']]
cfg.update(unit='robotron-transient-kernel-quality-templates-original01-20261024.service',output=str(D/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',driver['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],pins=[cpu.pin(p['path'])for p in {p['path']:p for p in pins}.values()])
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path']);print(json.dumps(dict(config=cp,renderer=renderer,provenance=provenance)))
