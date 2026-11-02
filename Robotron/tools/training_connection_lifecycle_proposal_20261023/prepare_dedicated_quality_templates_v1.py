"""Generate new unselected dedicated-observer native/review/preparation sources."""
import ast,hashlib,importlib.util,json,os
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal';D=R/'dedicated-observer-quality-template-contracts-CPU-original01-preparation-20261023'
def load(path,name):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_dedicated_templates_h');assign=load(P/'render_owned_quality_family_v3.py','_dedicated_assign').assignment
def source(path,text):
 compile(text,str(path),'exec')
 with path.open('xb')as f:f.write(text.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
 return h.pin(path)
def replace(text,old,new):assert text.count(old)==1,(old,text.count(old));return text.replace(old,new)
failed_pair='24829cde7c4153795a335b9883a57e6c58ef4974879035245c8fbdff7ae16089'
failed_policy='3928b61f6262819236876c23d3503aed8d2286e1b1d9857eedc3c1d3905a1efc'
clocks=dict(learner_frame_count=2715929502,training_steps=10778819,optimized_samples=42574247936,frame_count=5303666777)
observer={key:h.pin(P/name)for key,name in dict(client='dedicated_main_health_client_v1.py',worker='run_dedicated_main_health_v1.py',protocol='dedicated_main_health_protocol_v1.py',controller='control_dedicated_main_health_scope_v1.py',reviewer='review_dedicated_main_health_v1.py').items()}
finalizer=h.pin(P/'finalize_dedicated_main_health_v1.py');templates={};old_runtime=B/'run_compiled_full_tail32_quality_owned_health_template_v4.py';native=old_runtime.read_text()
def exclusions(text):
 old="'399f029598471553677c730b97c2ecc174b6fc1c8e295f72e1b319840926890a')"
 text=replace(text,old,"'399f029598471553677c730b97c2ecc174b6fc1c8e295f72e1b319840926890a','"+failed_pair+"')")
 if '>2700401151'in text:text=text.replace('>2700401151','>2715929502')
 old="'ea53b8a0495a9c4788ae2c1e0deb9a379bb1ca962d383110eaed148f8dda013c')"
 if old in text:text=replace(text,old,"'ea53b8a0495a9c4788ae2c1e0deb9a379bb1ca962d383110eaed148f8dda013c','"+failed_policy+"')")
 return text
native=exclusions(native);native=assign(native,'FINALIZER_SHA',finalizer['sha256'])
native=replace(native,"PREFIX_VALIDATOR_SHA=",'OBSERVER_DEPENDENCIES='+repr({k:v['sha256']for k,v in observer.items()})+'\nPREFIX_VALIDATOR_SHA=')
native=replace(native,";(output/'main-observations').mkdir(mode=0o700)",'')
native=replace(native,"protocol['schema']=='robotron-native-initial-readiness-main-health-protocol-v4'","protocol['schema']=='robotron-native-dedicated-main-health-protocol-v5'")
native=replace(native,"and family['main_health_finalizer']['sha256']==FINALIZER_SHA,","and family['main_health_finalizer']['sha256']==FINALIZER_SHA\n            and set(family['main_observer'])==set(OBSERVER_DEPENDENCIES)\n            and all(family['main_observer'][key]['sha256']==sha for key,sha in OBSERVER_DEPENDENCIES.items()),")
native=replace(native,"        engine=load('_compiled32_owned_main_health',h.checked(protocol['health_job']['sources']['full_health_engine']))","        client=load('_compiled32_dedicated_main_health_client',h.checked(family['main_observer']['client']))")
native=replace(native,"        (output/'main-observations'/'samples').mkdir(mode=0o700)\n        main_guard=engine.MainHealth(protocol['health_job'],output/'main-observations',h,prior_groups)","        main_guard=client.DedicatedMainHealth(job,jp,protocol,family,h,started=started,deadline=deadline,prior_groups=prior_groups)\n        main_guard.start()")
native=replace(native,"        ready_stream=main_guard.collector.stream\n        require(ready_stream.ready_index is not None", "        ready_stream=main_guard.initial\n        require(ready_stream['index']is not None")
native=native.replace('first_qualified_baseline_index=ready_stream.ready_index','first_qualified_baseline_index=ready_stream[\'index\']').replace('first_qualified_baseline_unix_s=ready_stream.ready_unix_s','first_qualified_baseline_unix_s=ready_stream[\'unix_s\']').replace('unaccepted_initial_samples=ready_stream.initial_unaccepted_samples','unaccepted_initial_samples=ready_stream[\'unaccepted_samples\']')
native=replace(native,"            errors.extend(finalized_main['errors']);owned_threads.append(main_guard.collector.writer.thread)","            errors.extend(finalized_main['errors']);main_samples=finalized_main['statuses']")
native=replace(native,"                and all(worker is None or not worker.is_alive()for worker in owned_threads),","                and all(worker is None or not worker.is_alive()for worker in owned_threads)\n                and(main_guard is None or main_guard.child is None or main_guard.scope_complete),")
native=replace(native,"and main_initial_readiness is not None)","and main_initial_readiness is not None and main_guard.scope_complete and main_guard.lifecycle is not None)")
native=replace(native,"        main_health_protocol=job['main_health_protocol'],source_family_manifest=job['source_family_manifest'],","        main_health_protocol=job['main_health_protocol'],source_family_manifest=job['source_family_manifest'],\n        main_observer_lifecycle=None if main_guard is None else main_guard.lifecycle,\n        native_started_monotonic_s=started,native_deadline_monotonic_s=deadline,")
templates['runtime']=source(B/'run_compiled_full_tail32_quality_dedicated_health_template_v1.py',native)
control=(B/'control_compiled_full_tail32_quality_owned_health_template_v3.py').read_text();control=replace(control,old_runtime.name,Path(templates['runtime']['path']).name)
templates['native_controller']=source(B/'control_compiled_full_tail32_quality_dedicated_health_template_v1.py',control)
review=(B/'read_compiled_quality32_owned_health_template_v5.py').read_text();review=exclusions(review);review=assign(review,'RUNTIME_SHA',templates['runtime']['sha256']);review=replace(review,old_runtime.name,Path(templates['runtime']['path']).name)
review=replace(review,"'main_health_engine','main_prefix_validator'}","'main_health_engine','main_prefix_validator','main_observer_reviewer'}")
review=replace(review,"    require(type(result.get('initial_main_readiness'))is dict", "    require(type(result.get('main_observer_lifecycle'))is dict and type(result.get('initial_main_readiness'))is dict")
needle="        raw_main=health_engine.replay(protocol['health_job'],closed_main['samples'],"
insert="""        require(config['sources']['main_observer_reviewer']==family['main_observer']['reviewer'],
            'Original independent observer-review source differs')
        observer_checked=modules['main_observer_reviewer'].verify(job,native_pin,owner,controller_config['argv'],
            result['main_observer_lifecycle'],protocol,family,prior_groups,read,h)
        require(observer_checked['closed_report']==result['main_health_report'],
            'Native and independent worker closure reports differ')
        worker_life=read(result['main_observer_lifecycle'])
        worker_fields=rt.archived_closure(read(worker_life['worker_closure']),read(worker_life['worker_owner']),read,exit_zero=True)
        require(started<=result['native_started_monotonic_s']<=closed_main['guard_started_monotonic_s']
            and result['native_deadline_monotonic_s']==result['native_started_monotonic_s']+job['wall_limit_s']
            and closed_main['guard_ended_monotonic_s']<=result['native_deadline_monotonic_s']
            and started<=int(worker_fields['ExecMainStartTimestampMonotonic'])/1e6
            <int(worker_fields['ExecMainExitTimestampMonotonic'])/1e6<=ended,
            'Original separate worker did not stay inside the native interval/deadline')
        report['main_observer_independently_verified']=observer_checked
"""
review=replace(review,needle,insert+needle)
templates['leg_reviewer']=source(B/'read_compiled_quality32_dedicated_health_template_v1.py',review)
prepare=(B/'prepare_quality32_owned_health_leg_template_v3.py').read_text();prepare=replace(prepare,'robotron-native-initial-readiness-main-health-protocol-v4','robotron-native-dedicated-main-health-protocol-v5')
prepare=replace(prepare,"additions=[*readiness['inputs'],", "additions=[*family['main_observer'].values(),*readiness['inputs'],")
prepare=replace(prepare,"main_prefix_validator=family['main_prefix_validator'])","main_prefix_validator=family['main_prefix_validator'],main_observer_reviewer=family['main_observer']['reviewer'])")
templates['leg_preparer']=source(B/'prepare_quality32_dedicated_health_leg_template_v1.py',prepare)
assess=exclusions((B/'assess_quality32_owned_health_campaign_template_v3.py').read_text())
templates['campaign_assessor']=source(B/'assess_quality32_dedicated_health_campaign_template_v1.py',assess)
templates['sequence']=h.pin(B/'sequence_fresh_quality32_owned_health_template_v1.py');templates['display_source']=h.pin(B/'watch_quality32_owned_health_display_template_v1.py')
renderer=(P/'render_owned_quality_family_v3.py').read_text()
renderer=replace(renderer,"KINDS=",'FAILED2715_PAIR='+repr(failed_pair)+'\nFAILED2715_POLICY='+repr(failed_policy)+'\nFAILED2715_CLOCKS='+repr(clocks)+'\nKINDS=')
renderer=replace(renderer,'(OLD_PAIR,FAILED2690_PAIR,FAILED2700_PAIR)','(OLD_PAIR,FAILED2690_PAIR,FAILED2700_PAIR,FAILED2715_PAIR)')
renderer=replace(renderer,'for key,value in FAILED2700_CLOCKS.items()','for key,value in FAILED2715_CLOCKS.items()')
renderer=replace(renderer,'(REFERENCE,OLD_POLICY,FAILED2690_POLICY,FAILED2700_POLICY)','(REFERENCE,OLD_POLICY,FAILED2690_POLICY,FAILED2700_POLICY,FAILED2715_POLICY)')
renderer=replace(renderer,old_runtime.name,Path(templates['runtime']['path']).name)
renderpin=source(P/'render_dedicated_quality_family_v4.py',renderer)
oldtree=ast.parse(old_runtime.read_text());newtree=ast.parse(native)
for n in oldtree.body:
 if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name not in ('run','validate_job'):
  other=next(x for x in newtree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef))and x.name==n.name);assert ast.dump(n)==ast.dump(other),n.name
def definition(text,name):return next(x for x in ast.parse(text).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))and x.name==name)
for name in ['metrics','assess_validated_cohorts']:assert ast.dump(definition((B/'assess_quality32_owned_health_campaign_template_v3.py').read_text(),name))==ast.dump(definition(assess,name))
D.mkdir(mode=0o700)
provenance=h.put(D/'unselected-dedicated-native-source-provenance.json',dict(schema='robotron-unselected-dedicated-observer-source-family-v1',templates=templates,renderer=renderpin,observer_sources=observer,finalizer=finalizer,
 original_native=h.pin(old_runtime),original_game_actor_ROM_lease_tail_helpers_AST_unchanged=True,original_confirmation_math_AST_unchanged=True,
 failed2715_pair=failed_pair,failed2715_policy=failed_policy,all_four_clock_floor=clocks,native_case_started=False,quality_qualified=False))
print(json.dumps(dict(provenance=provenance,renderer=renderpin,templates=templates)))
