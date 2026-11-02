import ast,copy,importlib.util,json,os,pathlib,secrets,sys,time,urllib.request
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26'
P=B/'quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101'
F=B/'quality32-protectedb231-vs-stopped77f9-restored8192-fullgame-original01-20261101'
R=B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_restore8192FG',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
def read(p):return json.loads(pathlib.Path(p).read_text())
def rp(p):return json.loads(h.checked(p).read_text())
parent=read(P/'prepared-campaign.json');oldpair=rp(parent['pair']);oldfamily=rp(parent['source_family'])
runtimepin=h.pin(R/'actual-restored-current-training-runtime.json');runtime=rp(runtimepin)
assert runtimepin['sha256']=='9aae9f274568ee7c2c8af8a575e971f269d02590be439a9308ae7157f8340cc3'
fleet=read(runtime['fleet_status_path']);fj=rp(runtime['fleet_job'])
assert fleet['errors']==[] and fleet['error_summary']['occurrences']==0 and fleet['initial_admission']['complete']is True
assert fleet['trainer']==runtime['trainer'] and fleet['supervisor']==runtime['fleet']
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as f:now=json.load(f)
assert now['pipeline_read_error']==now['bank_persistence_read_error']=='' and now['training_enabled']is True
assert now['learner_frame_count']>5254630919
F.mkdir(mode=0o700);(F/'selected-source').mkdir(mode=0o700)
selection=h.put(F/'next-controlled-comparison-selection.json',dict(
 schema='robotron-fresh-restored8192-fullgame-selection-v1',observed_unix_s=time.time(),
 current_runtime=runtimepin,previous_unstarted_preparation=parent['pair'],
 parent_failed_preflight=h.pin(P/'failed-original-physical-preflight-original01.json'),
 previous_scientific_games_started=False,fresh_case_required_after_actual_owner_change=True,
 frozen_roles_reused_exactly=True,fresh_games_and_transport_identities_required=True,
 candidate_selection_unchanged='Stopped77f9 at LFC5160938463, selected after valid15min short endpoint; no fullgame winner inferred',
 current_replay_queue_constructor=h.pin(G/'Scripts/dqn/socket_server.py'),
 queue_FIFO_CPU=h.pin(B/'current-fleet-cleanup-timeout-diagnostic-original01-20261101/candidate-queue8192-CPU-contracts-original01.json'),
 actual_restored192_census=runtime['independent_census'],quality_qualified=False,promotion=False))
for role in oldpair['roles'].values():
 h.checked(role['policy']);h.checked(role['CPU_report']);h.checked(role['original_CPU_readback'])
 assert rp(role['original_CPU_readback'])['actual_exit']==0
pair=copy.deepcopy(oldpair);pair.update(created_unix_s=time.time(),selected_after_cutoff=selection,
 actual_candidate_description='Same stopped77f9 frozen policy; fresh restored8192 current Main/fleet, no scores or old actor identities carried forward')
pairpin=h.put(F/'fixed-pair-precommit.json',pair)
derivations=[]
def assignment(raw,name):
 return next(ast.get_source_segment(raw,n)for n in ast.parse(raw).body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id==name for t in n.targets))
def derive(name,parent,edits,function_AST_unchanged=True):
 raw=h.checked(parent).read_text();new=raw
 for before,after in edits:assert new.count(before)==1;new=new.replace(before,after,1)
 back=new
 for before,after in reversed(edits):assert back.count(after)==1;back=back.replace(after,before,1)
 assert back==raw;ast.parse(new)
 a=[ast.dump(n)for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
 b=[ast.dump(n)for n in ast.parse(new).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
 if function_AST_unchanged:assert a==b
 p=F/'selected-source'/name
 with p.open('x')as f:f.write(new);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
 pin=h.pin(p);derivations.append(dict(parent=parent,selected=pin,exact_reverse_edits=True,
  all_function_and_class_AST_unchanged=a==b,edits=[dict(before=a,after=b)for a,b in edits]));return pin
nativeparent=parent['native'];raw=h.checked(nativeparent).read_text()
native=derive('run_fixed_b231_vs_stopped77f9_restored8192_v1.py',nativeparent,[(assignment(raw,'PAIR_SHA'),'PAIR_SHA='+repr(pairpin['sha256']))])
def case_source(key,name):
 p=parent[key];raw=h.checked(p).read_text();return derive(name,p,[(assignment(raw,'PAIR_SHA'),'PAIR_SHA='+repr(pairpin['sha256'])),(assignment(raw,'CASE'),'CASE=Path('+repr(str(F))+')')])
reviewer=case_source('leg_reviewer','review_fixed_b231_vs_stopped77f9_restored8192_v1.py')
assessor=case_source('campaign_assessor','assess_fixed_b231_vs_stopped77f9_restored8192_v1.py')
sourceproof=h.put(F/'selected-source/exact-source-bindings.json',dict(status='PASS_EXACT_PAIR_NAMESPACE_BINDINGS',pair=pairpin,
 derivations=derivations,qualified_parent_composition=oldfamily['native_source_proof'],
 current_runtime=runtimepin,all_native_review_assessment_function_AST_unchanged=True,scientific_games_started=False,promotion=False))
rule=copy.deepcopy(rp(parent['early_C1_rule']));rule.update(campaign_directory=str(F),pair=pairpin)
rulepin=h.put(F/'predeclared-early-C1-rule.json',rule)
family=copy.deepcopy(oldfamily);family.update(pair=pairpin,native=native,leg_reviewer=reviewer,campaign_assessor=assessor,
 native_source_proof=sourceproof,reviewer_source_proof=sourceproof,early_C1_rule=rulepin,
 actual_current_runtime=runtimepin,current_queue8192_CPU=rp(selection)['queue_FIFO_CPU'])
familypin=h.put(F/'selected-source-family.json',family)
oldmain=rp(parent['legs'][0]['native_job'])['current_main'];current_main=copy.deepcopy(oldmain)
owner=runtime['trainer'];current_main['owner']={k:owner[k]for k in ['pid','unit','invocation_id','cgroup']};current_main['owner']['starttime_ticks']=owner['birth']
current_main['environment']['ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256']=runtime['startup_job']['sha256']
current_main['exposure']={k:{field:now['host_pipeline']['learning_exposure'][k][field]for field in ['process_id','instance_monotonic_ns','epoch','epoch_reason']}for k in ['optimizer','replay']}
current_main.update(startup_authority=runtime['startup_authority'],startup_held=runtime['held_report'])
current_fleet={k:fleet[k]for k in ['epoch','supervisor','trainer','source_authority','original_membership','rolemap']}
current_fleet.update(physical_helper=fj['physical_helper'],job=runtime['fleet_job'],status_path=runtime['fleet_status_path'])
binding=h.put(F/'actual-current-Main-fleet-binding.json',dict(current_main=current_main,current_fleet=current_fleet,
 runtime=runtimepin,observation=h.put(F/'Main-now-at-precommit.json',now),source_and_recipe_not_changed=True))
ctl=load('_restoredFGCtl',h.checked(parent['native_controller']));tokens=set();oldtokens=set();legs=[]
for leg in parent['legs']:
 previous=rp(leg['native_job']);oldtokens.update(previous['sessions'].values());oldtokens.update(previous['connections'].values())
for oldleg in parent['legs']:
 role=oldleg['role'];model_role=oldleg['model_role'];directory=F/pathlib.Path(oldleg['directory']).name;directory.mkdir(mode=0o700)
 selected=pair['roles'][model_role];j=rp(oldleg['native_job'])
 j.update(runtime=native,output=str(directory/'runtime-original01'),quality_pair_precommit=pairpin,
  checkpoint=selected['policy'],expected_policy_clocks=selected['saved_clocks'],
  label='fixed-b231-vs-stopped77f9-restored8192-'+role+'-original01-20261101',
  current_main=current_main,current_fleet=current_fleet,source_family_manifest=familypin,
  selected_change='Fresh exact same-policy pair on newly restored Main/fleet with constructor-only replay8192. Scientific runtime/reviewer/decision function AST unchanged; all64/two-per32/full tails and independent C1/C2 gates unchanged.')
 j['sessions']={str(slot):secrets.token_hex(16)for slot in range(4096,4128)}
 j['connections']={str(slot):secrets.token_hex(16)for slot in range(4096,4128)}
 fresh=set(j['sessions'].values())|set(j['connections'].values());assert len(fresh)==64 and not fresh.intersection(tokens|oldtokens);tokens.update(fresh)
 pins=[native,j['checkpoint'],j['source_package'],j['mame'],j['lua'],j['seed_runtime'],j['screen_support'],j['current_v6_health_source'],j['owned_TRAIN_overlap_source'],j['current_v6_health_qualification'],familypin,pairpin,selected['CPU_report'],selected['original_CPU_readback'],rulepin,parent['sequence_source'],sourceproof,runtimepin,binding,*j['quota64_source_pins'].values(),*j['quota64_validation'].values(),*j['full_tail_predecessors'].values(),j['historical_startup_acceptance_scope'],j['validated_CPU_prefix'],*j['boot_seed']['inputs'],j['boot_seed']['module']]
 pins.extend(family[k]for k in ['native_controller','leg_reviewer','campaign_assessor','decision_kernel','wire_auditor','games_auditor','original_log_reviewer','early_C1_assessor','early_C1_numeric'])
 pins.extend(j['current_fleet'][k]for k in ['job','original_membership','rolemap','physical_helper','source_authority'])
 pins.extend([j['current_fleet']['supervisor']['source'],j['current_main']['startup_authority'],j['current_main']['startup_held']])
 j['inputs']=list({p['path']:p for p in pins}.values());jp=h.put(directory/'job.json',j)
 cfg=rp(oldleg['native_controller_config']);cfg.update(unit='robotron-b231-77f9-q8192-'+role.lower()+'-fullgame-original01.service',output=str(directory/'execution-original01'))
 cfg['argv']=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',native['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',native['sha256']]
 cfg['pins']=[ctl.pin(p['path'])for p in [jp,*j['inputs']]];cp=h.put(directory/'controller-config.json',cfg)
 prep=h.put(directory/'prepared-native.json',dict(schema='robotron-fixed-fullgame-native-leg-preparation-v1',role=role,pair=pairpin,native=native,job=jp,controller=parent['native_controller'],controller_config=cp,source_family=familypin,scientific_job_launched=False,promotion=False))
 rd=directory/'independent-review-original01';rd.mkdir(mode=0o700);review=rp(oldleg['review_job_template'])
 review.update(runtime=reviewer,native_prepared=prep,original_native_closeout_path=str(directory/'positive-original-native-closeout.json'),report=str(rd/'report.json'))
 rjp=h.put(directory/'review-job-template.json',review)
 legs.append(dict(index=oldleg['index'],role=role,model_role=model_role,directory=str(directory),native_prepared=prep,native_job=jp,native_controller_config=cp,review_job_template=rjp,native_closeout_path=str(directory/'positive-original-native-closeout.json'),review_closeout_path=str(directory/'positive-original-review-closeout.json'),display_live_path=str(directory/'display-live.json'),display_receipt_path=str(directory/'display-reviewed.json')))
assert len(tokens)==256 and not tokens.intersection(oldtokens)
plan=h.put(F/'plan.json',dict(schema='robotron-fixed-fullgame-dashboard-plan-v1',checkpoints={k:v['policy']for k,v in pair['roles'].items()},legs=[dict(index=r['index'],role=r['model_role'],job=dict(label='Protected champion'if r['model_role']=='reference'else'Candidate'),evaluator_status_path=r['display_live_path'],receipt_path=r['display_receipt_path'])for r in legs]))
prepared=copy.deepcopy(parent);prepared.update(campaign_directory=str(F),pair=pairpin,source_family=familypin,native=native,leg_reviewer=reviewer,campaign_assessor=assessor,legs=legs,dashboard_plan=plan,early_C1_rule=rulepin)
pp=h.put(F/'prepared-campaign.json',prepared)
with(F/'status.json').open('x')as f:json.dump(dict(state='prepared',current_leg=None,legs=[dict(index=r['index'],role=r['model_role'],state='pending')for r in legs],outcome=None,updated_unix_s=time.time()),f);f.flush();os.fsync(f.fileno())
checkerbase=h.pin(G/'tools/full_game_confirmation_proposal/check_fixed_confirmation_preflight_v1.py');raw=h.checked(checkerbase).read_text()
checker=derive('check_fixed_restored8192_preflight_v1.py',checkerbase,[(assignment(raw,'F'),'F=Path('+repr(str(F))+')'),("    sequence_path=Path(__file__).with_name('run_fixed_confirmation_sequence_v1.py')","    sequence_path=Path("+repr(parent['sequence_source']['path'])+")")],function_AST_unchanged=False)
print(json.dumps(dict(prepared={k:pp[k]for k in ['path','sha256','bytes']},checker={k:checker[k]for k in ['path','sha256','bytes']},pair_sha=pairpin['sha256'],fresh_transport_identities=len(tokens))))
