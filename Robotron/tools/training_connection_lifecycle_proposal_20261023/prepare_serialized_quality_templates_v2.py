"""Unselected quality source family; forbid failed2739 and bind tested observer."""
import ast,copy,importlib.util,json,os,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
D=R/'serialized-free314-quality-template-contracts-CPU-original01-preparation-20261024'
OLD=R/'dedicated-observer-quality-template-contracts-CPU-original01-preparation-20261023'
C=R/'serialized-live-free314-client-CPU-original01-preparation-20261024'
FAILED_PAIR='a8d442fb60bd5d4859e2c3683f9e91e410c71d33d6b0de3e3b25d87f17d05cb2'
FAILED_SHA='95726b361f01bceab95bd5deaf6f5534dd1e8d4e7335e38904ae5ca3ee49987d'
FLOORS=dict(learner_frame_count=2739279553,training_steps=10864951,optimized_samples=42927044608,frame_count=5347766313)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_serial_templates_h')
cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_serial_templates_cpu')
def read(path):return json.loads(Path(path).read_bytes())
records=[]
def create(oldpath,target,changes):
    old=Path(oldpath).read_text();source=old
    for a,b in changes:assert source.count(a)==1,(oldpath,a,source.count(a));source=source.replace(a,b)
    reverse=source
    for a,b in reversed(changes):assert reverse.count(b)==1,(target,b);reverse=reverse.replace(b,a)
    assert reverse==old;compile(source,str(target),'exec')
    with target.open('xb')as f:f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    pin=h.pin(target);records.append(dict(original=h.pin(oldpath),prospective=pin,changes=changes,exact_reverse_verified=True));return pin
oldjob=read(OLD/'job.json');templates=copy.deepcopy(oldjob['templates']);family=read(C/'source-family-component.json')
oldpair="'24829cde7c4153795a335b9883a57e6c58ef4974879035245c8fbdff7ae16089')"
newpair=oldpair[:-1]+",'"+FAILED_PAIR+"')"
floor="all(type(POLICIES['candidate']['clocks'][key])is int and POLICIES['candidate']['clocks'][key]>value for key,value in "+repr(FLOORS)+".items())"
oldruntime=Path(templates['runtime']['path']);newruntime=B/'run_compiled_full_tail32_quality_serialized_free314_template_v2.py'
oldobs=next(n for n in ast.parse(oldruntime.read_text()).body if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='OBSERVER_DEPENDENCIES')
oldline=oldruntime.read_text().splitlines()[oldobs.lineno-1]
templates['runtime']=create(oldruntime,newruntime,[(oldpair,newpair),("POLICIES['candidate']['clocks']['learner_frame_count']>2715929502",floor),
    ("'3928b61f6262819236876c23d3503aed8d2286e1b1d9857eedc3c1d3905a1efc'),","'3928b61f6262819236876c23d3503aed8d2286e1b1d9857eedc3c1d3905a1efc','"+FAILED_SHA+"'),"),
    (oldline,'OBSERVER_DEPENDENCIES='+repr({k:v['sha256']for k,v in family['main_observer'].items()}))])
templates['native_controller']=create(Path(templates['native_controller']['path']),B/'control_compiled_full_tail32_quality_serialized_free314_template_v2.py',[(oldruntime.name,newruntime.name)])
templates['leg_reviewer']=create(Path(templates['leg_reviewer']['path']),B/'read_compiled_quality32_serialized_free314_template_v2.py',[(oldpair,newpair),
    ("POLICIES['candidate']['clocks']['learner_frame_count']>2715929502",floor+" and POLICIES['candidate']['sha256']!='"+FAILED_SHA+"'"),(oldruntime.name,newruntime.name)])
templates['campaign_assessor']=create(Path(templates['campaign_assessor']['path']),B/'assess_quality32_serialized_free314_campaign_template_v2.py',[(oldpair,newpair)])
templates['leg_preparer']=create(Path(templates['leg_preparer']['path']),B/'prepare_quality32_serialized_free314_leg_template_v2.py',[
    ("    additions=[*family['main_observer'].values(),","    additions=[family['main_observer_interpreter'],*family['main_observer'].values(),")])
renderer_changes=[
    ("KINDS=('runtime'","FAILED2739_PAIR="+repr(FAILED_PAIR)+"\nFAILED2739_POLICY="+repr(FAILED_SHA)+"\nFAILED2739_CLOCKS="+repr(FLOORS)+"\nKINDS=('runtime'"),
    ('pair_sha not in (OLD_PAIR,FAILED2690_PAIR,FAILED2700_PAIR,FAILED2715_PAIR)','pair_sha not in (OLD_PAIR,FAILED2690_PAIR,FAILED2700_PAIR,FAILED2715_PAIR,FAILED2739_PAIR)'),
    ('all(clocks[key]>value for key,value in FAILED2715_CLOCKS.items())','all(clocks[key]>value for key,value in FAILED2739_CLOCKS.items())'),
    ('sha not in (REFERENCE,OLD_POLICY,FAILED2690_POLICY,FAILED2700_POLICY,FAILED2715_POLICY)','sha not in (REFERENCE,OLD_POLICY,FAILED2690_POLICY,FAILED2700_POLICY,FAILED2715_POLICY,FAILED2739_POLICY)'),
    (oldruntime.name,newruntime.name)]
renderer=create(P/'render_dedicated_quality_family_v4.py',P/'render_serialized_free314_quality_family_v5.py',renderer_changes)
driver_changes=[
    ('subject.FAILED2715_CLOCKS.items()}))','subject.FAILED2739_CLOCKS.items()}))'),
    ('+subject.FAILED2715_PAIR+"\')"','+subject.FAILED2715_PAIR+"\',\'"+subject.FAILED2739_PAIR+"\')"'),
    ("        def test_original_game_actor_lease_and_exact_confirmation_math_ASTs_are_preserved(self):",'''        def test_closed2739_pair_policy_and_all_four_clock_floors_reject(self):
            with self.assertRaises(ValueError):subject.render(templates,pair,subject.FAILED2739_PAIR,'synthetic')
            negative.append('closed2739_pair_forbidden')
            data=copy.deepcopy(pair);data['candidate']['policy']['sha256']=subject.FAILED2739_POLICY
            with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
            negative.append('closed2739_policy_forbidden')
            for key,floor in subject.FAILED2739_CLOCKS.items():
                data=copy.deepcopy(pair);data['candidate']['saved_clocks'][key]=floor
                with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
                negative.append('closed2739_nonlater_'+key)
            self.assertIn("family['main_observer_interpreter']",rendered['leg_preparer']['source'])

        def test_original_game_actor_lease_and_exact_confirmation_math_ASTs_are_preserved(self):'''),
    ("                ('wrong_argv',life['worker_config'],lambda d:d.update(argv=['foreign'])),",'''                ('wrong_argv',life['worker_config'],lambda d:d.update(argv=['foreign'])),
                ('wrong_worker_binary',life['worker_job'],lambda d:d['worker_interpreter'].update(sha256='0'*64)),
                ('GIL_enabled',life['worker_outcome'],lambda d:d['interpreter'].update(GIL_enabled=True)),
                ('wrong_worker_version',life['worker_outcome'],lambda d:d['interpreter'].update(major_minor=[3,12])),
                ('wrong_outcome_binary',life['worker_outcome'],lambda d:d['interpreter']['binary'].update(sha256='0'*64)),
                ('old_python_argv',life['worker_config'],lambda d:d.update(argv=['/usr/bin/python3.12',*d['argv'][2:]])),''')]
driver=create(P/'validate_dedicated_quality_family_v1.py',P/'validate_serialized_free314_quality_family_v2.py',driver_changes)
D.mkdir(mode=0o700)
provenance=h.put(D/'unselected-source-transforms-and-scientific-gates.json',dict(schema='robotron-unselected-serialized-free314-quality-family-provenance-v1',source_transforms=records,
    failed2739_pair=FAILED_PAIR,failed2739_policy=FAILED_SHA,all_four_clock_floors=FLOORS,
    original_game_helpers_and_confirmation_math_unchanged=True,minimum50_all32_every_admitted_tail_and_separate_confirmations_unchanged=True,
    observer_component=h.pin(C/'independent-original-serialized-client-runtime-and-raw-closeout.json'),
    native_load600_must_still_be_independently_closed_before_selection=True,no_policy_selected_or_loaded=True,quality_qualified=False,created_unix_s=time.time()))
job=copy.deepcopy(oldjob);job.update(output=str(D/'output-original01'),subject=renderer,driver=driver,templates=templates,observer_sources=family['main_observer'],
    client_component_job=h.pin(C/'job.json'),client_component_report=h.pin(C/'output-original01/report.json'),client_component_owner=h.pin(C/'execution-original01/root-original-identity.json'),client_component_config=h.pin(C/'controller-config.json'),prospective_source_provenance=provenance)
jp=h.put(D/'job.json',job);cfg=read(OLD/'controller-config.json')
pins=[jp,driver,renderer,provenance,*templates.values(),*family['main_observer'].values(),family['main_observer_interpreter'],
    *[job[k]for k in ('helpers','reader','original_runtime','original_assessor','old_native_job','selection','proposed_transport','proposed_engine','dedicated_finalizer','client_component_job','client_component_report','client_component_owner','client_component_config')]]
# Include every actual worker/source join already selected by the component.
component_cfg=read(C/'controller-config.json')
pins += [h.pin(p['path'])for p in component_cfg['pins']]
cfg.update(unit='robotron-serialized-free314-quality-templates-original01-20261024.service',output=str(D/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',driver['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],pins=[cpu.pin(p['path'])for p in {p['path']:p for p in pins}.values()])
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path']);print(json.dumps(dict(config=cp,renderer=renderer,provenance=provenance)))
