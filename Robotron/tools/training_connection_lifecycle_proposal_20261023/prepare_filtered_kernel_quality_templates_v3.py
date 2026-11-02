"""Unselected quality templates bound to the independently tested kernel reader."""
import ast,copy,importlib.util,json,os,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
OLD=R/'serialized-free314-quality-template-contracts-CPU-original01-preparation-20261024'
D=R/'filtered-kernel-quality-template-contracts-CPU-original01-preparation-20261024'
C=R/'inet-diag-filtered-serialized-free314-client-CPU-original01-preparation-20261024'
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
oldruntime=Path(templates['runtime']['path']);source=oldruntime.read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='HEALTH_DEPENDENCIES')
oldline=source.splitlines()[node.lineno-1];newruntime=B/'run_compiled_full_tail32_quality_filtered_kernel_template_v3.py'
templates['runtime']=create(oldruntime,newruntime,[(oldline,'HEALTH_DEPENDENCIES='+repr({k:v['sha256']for k,v in health['sources'].items()}))])
templates['native_controller']=create(templates['native_controller']['path'],B/'control_compiled_full_tail32_quality_filtered_kernel_template_v3.py',[(oldruntime.name,newruntime.name)])
templates['leg_reviewer']=create(templates['leg_reviewer']['path'],B/'read_compiled_quality32_filtered_kernel_template_v3.py',[(oldruntime.name,newruntime.name)])
renderer=create(oldjob['subject']['path'],P/'render_filtered_kernel_quality_family_v6.py',[(oldruntime.name,newruntime.name)])
driver=create(oldjob['driver']['path'],P/'validate_filtered_kernel_quality_family_v3.py',[
    ("        def test_original_game_actor_lease_and_exact_confirmation_math_ASTs_are_preserved(self):",'''        def test_kernel_capture_sources_match_actual_closed_observer_context(self):
            reader=load('_kernel_template_context_reader',job['reader'])
            def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
            actual=read(job['client_component_job']);protocol=read(actual['main_health_protocol'])
            self.assertEqual(runtime.HEALTH_DEPENDENCIES,{key:value['sha256']for key,value in protocol['health_job']['sources'].items()})
            self.assertEqual(read(job['kernel_capture_contracts'])['typed_negative_rejections'],187)
            capacity=read(job['kernel_resource_closeout'])
            self.assertTrue(capacity['resource_passed']);self.assertEqual(capacity['synthetic_samples'],48332)
            self.assertLess(capacity['actual_elapsed_s'],600)
            self.assertEqual(len(runtime.HEALTH_DEPENDENCIES),12)

        def test_original_game_actor_lease_and_exact_confirmation_math_ASTs_are_preserved(self):''')])
D.mkdir(mode=0o700)
provenance=h.put(D/'source-changes-and-unchanged-scientific-gates.json',dict(schema='robotron-unselected-filtered-kernel-quality-family-provenance-v1',source_changes=records,
    two_health_source_hashes_bound_to_actual_closed_component=True,other10_health_sources_unchanged=True,
    all_game_actor_ROM_lease_and_confirmation_math_AST_unchanged=True,failed2739_pair_policy_and_all4_clock_floors_unchanged=True,
    min50_all32_every_tail_and_separate_C1_C2_5percent_mean_and_preserved_median_unchanged=True,
    actual_native600_positive_closure_still_required=True,no_policy_or_scientific_selection=True,quality_qualified=False,created_unix_s=time.time()))
job=copy.deepcopy(oldjob);job.update(output=str(D/'output-original01'),templates=templates,subject=renderer,driver=driver,observer_sources=family['main_observer'],
    client_component_job=h.pin(C/'job.json'),client_component_report=h.pin(C/'output-original01/report.json'),client_component_owner=h.pin(C/'execution-original01/root-original-identity.json'),client_component_config=h.pin(C/'controller-config.json'),
    kernel_capture_contracts=h.pin(F/'independent-original187-rejections-five-failures-and-filtered-capture-source-closeout.json'),kernel_resource_closeout=h.pin(M/'independent-original-filtered-capacity-and-scope-closeout.json'),prospective_source_provenance=provenance)
jp=h.put(D/'job.json',job);cfg=read(OLD/'controller-config.json')
pins=[v for v in job.values()if isinstance(v,dict)and 'path'in v]+[jp,*templates.values(),*family['main_observer'].values(),family['main_observer_interpreter'],*health['sources'].values(),health['binding']]
pins += [h.pin(p['path'])for p in read(C/'controller-config.json')['pins']]
cfg.update(unit='robotron-filtered-kernel-quality-templates-original01-20261024.service',output=str(D/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',driver['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],pins=[cpu.pin(p['path'])for p in {p['path']:p for p in pins}.values()])
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path']);print(json.dumps(dict(config=cp,renderer=renderer,provenance=provenance)))
