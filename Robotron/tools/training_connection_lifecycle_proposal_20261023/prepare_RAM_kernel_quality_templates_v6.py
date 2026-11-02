"""Unselected quality templates bound to the independently tested kernel reader."""
import ast,copy,importlib.util,json,os,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
OLD=R/'transient-live-kernel-quality-template-contracts-CPU-original01-preparation-20261024'
D=R/'RAM-live-kernel-quality-template-contracts-CPU-original01-preparation-20261024'
C=R/'RAM-live-filtered-free314-client-CPU-original01-preparation-20261024'
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
oldruntime=Path(templates['runtime']['path']);newruntime=B/'run_compiled_full_tail32_quality_RAM_kernel_template_v5.py'
source=oldruntime.read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='OBSERVER_DEPENDENCIES')
oldline=source.splitlines()[node.lineno-1]
templates['runtime']=create(oldruntime,newruntime,[(oldline,'OBSERVER_DEPENDENCIES='+repr({key:value['sha256']for key,value in family['main_observer'].items()}))])
templates['native_controller']=create(templates['native_controller']['path'],B/'control_compiled_full_tail32_quality_RAM_kernel_template_v5.py',[(oldruntime.name,newruntime.name)])
templates['leg_reviewer']=create(templates['leg_reviewer']['path'],B/'read_compiled_quality32_RAM_kernel_template_v5.py',[(oldruntime.name,newruntime.name)])
renderer=create(oldjob['subject']['path'],P/'render_RAM_kernel_quality_family_v8.py',[(oldruntime.name,newruntime.name)])
templates['leg_preparer']=create(templates['leg_preparer']['path'],B/'prepare_quality32_RAM_kernel_leg_template_v3.py',[
    ("    family=json.loads(h.checked(readiness['source_family_manifest']).read_bytes())","    family=json.loads(h.checked(readiness['source_family_manifest']).read_bytes())\n    require(family['main_live_control']==readiness['main_live_control']and family['main_live_control']['sha256']=='52372d96fdbfbd2955c260ef864d456e034c8cfe015aa776b4391b5b2e679f8c','Exact tested RAM helper binding required')\n    h.checked(family['main_live_control'])"),
    ("    additions=[family['main_observer_interpreter'],","    additions=[family['main_live_control'],family['main_observer_interpreter'],")])
driver=create(oldjob['driver']['path'],P/'validate_RAM_kernel_quality_family_v4.py',[
    ("        def test_original_game_actor_lease_and_exact_confirmation_math_ASTs_are_preserved(self):",'        def test_RAM_control_helper_release_and_new_negative_joins(self):\n            reader=load(\'_RAM_template_reader\',job[\'reader\'])\n            def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)\n            cj=read(job[\'client_component_job\']);cr=read(job[\'client_component_report\']);cf=read(cj[\'source_family_manifest\']);cp=read(cj[\'main_health_protocol\'])\n            self.assertEqual(cf[\'main_live_control\'],job[\'RAM_helper\'])\n            self.assertEqual(read(job[\'RAM_contracts\'])[\'original_codec_guards\'],38)\n            self.assertEqual(read(job[\'RAM_contracts\'])[\'RAM_negative_guards\'],31)\n            preparer=rendered[\'leg_preparer\'][\'source\']\n            self.assertIn("family[\'main_live_control\']==readiness[\'main_live_control\']",preparer)\n            self.assertIn("additions=[family[\'main_live_control\']",preparer)\n            owner=read(job[\'client_component_owner\']);argv=read(job[\'client_component_config\'])[\'argv\'];lp=cr[\'observer_lifecycle\'];life=read(lp)\n            review=load(\'_actual_RAM_observer_review\',cf[\'main_observer\'][\'reviewer\'])\n            checked=review.verify(cj,job[\'client_component_job\'],owner,argv,lp,cp,cf,[],read,h)\n            self.assertEqual(checked,cr[\'independent_worker_review\']);self.assertTrue(checked[\'RAM_control_review\'][\'original_root_absent\'])\n            release=read(life[\'live_control_release\']);intent=read(release[\'intent\'])\n            archived=next(item[\'archived\']for item in intent[\'files\']if Path(item[\'original\'][\'path\']).name==\'live.json\')\n            variants=[\n                (\'missing_RAM_release\',lp,lambda d:d.update(live_control_release={})),\n                (\'false_RAM_release\',life[\'live_control_release\'],lambda d:d.update(original_root_absent=False)),\n                (\'RAM_job_nonce\',life[\'worker_job\'],lambda d:d[\'live_control\'].update(nonce=\'f\'*32)),\n                (\'RAM_path_escape\',life[\'worker_job\'],lambda d:d[\'live_control\'].update(live_path=\'/tmp/foreign\')),\n                (\'RAM_helper_digest\',life[\'worker_job\'],lambda d:d[\'live_control_helper\'].update(sha256=\'0\'*64)),\n                (\'RAM_outcome_binding\',life[\'worker_outcome\'],lambda d:d.update(live_control={}))]\n            for name,pin,mutation in variants:\n                changed=copy.deepcopy(read(pin));mutation(changed)\n                def fixture_read(entry,as_json=True):\n                    if entry==pin and as_json:return copy.deepcopy(changed)\n                    return read(entry,as_json)\n                with self.assertRaises((ValueError,KeyError,TypeError)):\n                    review.verify(cj,job[\'client_component_job\'],owner,argv,lp,cp,cf,[],fixture_read,h)\n                negative.append(\'RAM_join:\'+name)\n            value=json.loads(read(archived,False));value[\'nonce\']=\'f\'*32\n            def changed_bytes(entry,as_json=True):\n                if entry==archived and not as_json:return json.dumps(value).encode()\n                return read(entry,as_json)\n            with self.assertRaises((ValueError,KeyError,TypeError)):\n                review.verify(cj,job[\'client_component_job\'],owner,argv,lp,cp,cf,[],changed_bytes,h)\n            negative.append(\'RAM_join:archived_final_nonce\')\n\n        def test_original_game_actor_lease_and_exact_confirmation_math_ASTs_are_preserved(self):')])
D.mkdir(mode=0o700)
provenance=h.put(D/'source-changes-and-unchanged-scientific-gates.json',dict(schema='robotron-unselected-RAM-kernel-quality-family-provenance-v1',source_changes=records,
    three_observer_hashes_and_RAM_helper_bound_to_actual_closed_components=True,codec_f59_and_all12_health_sources_unchanged=True,
    all_game_actor_ROM_lease_and_confirmation_math_AST_unchanged=True,failed2739_pair_policy_and_all4_clock_floors_unchanged=True,
    min50_all32_every_tail_and_separate_C1_C2_5percent_mean_and_preserved_median_unchanged=True,
    actual_uninstrumented_RAM_native600_positive_closure_still_required=True,no_policy_or_scientific_selection=True,quality_qualified=False,created_unix_s=time.time()))
job=copy.deepcopy(oldjob);job.update(output=str(D/'output-original01'),templates=templates,subject=renderer,driver=driver,observer_sources=family['main_observer'],
    client_component_job=h.pin(C/'job.json'),client_component_report=h.pin(C/'output-original01/report.json'),client_component_owner=h.pin(C/'execution-original01/root-original-identity.json'),client_component_config=h.pin(C/'controller-config.json'),RAM_helper=family['main_live_control'],RAM_contracts=family['RAM_live_control_contracts'],prospective_source_provenance=provenance)
jp=h.put(D/'job.json',job);cfg=read(OLD/'controller-config.json')
pins=[v for v in job.values()if isinstance(v,dict)and 'path'in v]+[jp,*templates.values(),*family['main_observer'].values(),family['main_observer_interpreter'],family['main_live_control'],*health['sources'].values(),health['binding']]
pins += [h.pin(p['path'])for p in read(C/'controller-config.json')['pins']]
cfg.update(unit='robotron-RAM-kernel-quality-templates-original01-20261024.service',output=str(D/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',driver['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],pins=[cpu.pin(p['path'])for p in {p['path']:p for p in pins}.values()])
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path']);print(json.dumps(dict(config=cp,renderer=renderer,provenance=provenance)))
