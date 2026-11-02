import ast,copy,importlib.util,json,os,pathlib,secrets,sys,time
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26'
OLD=B/'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'
C=B/'short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101'
F=B/'quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101'
U=B/'short15-protectedb231-vs-stopped77f9-original01-20261101/future-fullgame-owned-ABI-logseal-source-original01'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_assemble77h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
read=lambda p:json.loads(pathlib.Path(p).read_text())
oldprep=read(OLD/'prepared-campaign.json');oldpair=read(OLD/'fixed-pair-precommit.json');oldfamily=read(OLD/'selected-source-family.json')
rolejob=read(F/'roles-CPU-original02/job.json');close=h.pin(F/'roles-CPU-original02/original-role-CPU-result-and-owned-closeout.json');assert read(close['path'])['actual_exit']==0
role_report=read(F/'roles-CPU-original02/report.json');assert role_report['status']=='PASS_FRESH_REFERENCE_AND_CANDIDATE_CPU_ACQUISITION'
pair=copy.deepcopy(oldpair);pair.update(created_unix_s=time.time(),selected_after_cutoff=h.pin(F/'next-controlled-comparison-selection.json'),actual_candidate_description='Stopped fullstate77f9 at LFC5160938463; distinct from failed1c; no past scores carried forward')
for role in ['reference','candidate']:
 r=role_report['roles'][role];pair['roles'][role]=dict(policy=r['checkpoint'],source_policy=r['source_checkpoint'],saved_clocks=r['clocks'],CPU_report=h.pin(pathlib.Path(rolejob['output'])/role/'CPU-policy-readback.json'),original_CPU_readback=close,policy_authority=r['original_policy_authority'])
pairpin=h.put(F/'fixed-pair-precommit.json',pair)
derivations=[]
def derive(name,parent,edits):
 raw=h.checked(parent).read_text();text=raw
 for before,after in edits:
  assert text.count(before)==1,(name,before[:70]);text=text.replace(before,after,1)
 back=text
 for before,after in reversed(edits):
  assert back.count(after)==1;back=back.replace(after,before,1)
 assert back==raw;ast.parse(text);p=F/'selected-source'/name
 with p.open('x')as f:f.write(text);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
 pin=h.pin(p);derivations.append(dict(parent=parent,selected=pin,exact_reverse_edits=True,edits=[dict(before=a,after=b)for a,b in edits]));return pin
def assignment(raw,name):
 return next(ast.get_source_segment(raw,n)for n in ast.parse(raw).body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id==name for t in n.targets))
base=h.pin(U/'run_owned_ABI_fullgame_UNBOUND_v1.py');raw=h.checked(base).read_text()
builder=ast.parse((G/'tools/full_game_confirmation_proposal/prepare_confirmation_native_v1.py').read_text())
function=next(n for n in builder.body if isinstance(n,ast.FunctionDef)and n.name=='main')
validation=next(n.value.value for n in function.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='validate'for t in n.targets))
policies={role:dict(sha256=r['policy']['sha256'],clocks=r['saved_clocks'])for role,r in pair['roles'].items()}
native=derive('run_fixed_b231_vs_stopped77f9_fullgame_v1.py',base,[
 (assignment(raw,'PAIR_SHA'),"PAIR_SHA="+repr(pairpin['sha256'])),
 (assignment(raw,'POLICIES'),'POLICIES='+repr(policies)),
 ('def run(job,jp,h):\n',validation+'def run(job,jp,h):\n'),
 ('    output=validate_job(job)\n','    output=validate_job(job)\n    validate_selected_family(job,h)\n')])
base=h.pin(OLD/'future-owned-overlap-observer-reviewer-original02/review_owned_overlap_fullgame_UNBOUND_v1.py');raw=h.checked(base).read_text()
reviewer=derive('review_fixed_b231_vs_stopped77f9_fullgame_v1.py',base,[(assignment(raw,'PAIR_SHA'),'PAIR_SHA='+repr(pairpin['sha256'])),(assignment(raw,'CASE'),'CASE=Path('+repr(str(F))+')')])
base=oldprep['campaign_assessor'];raw=h.checked(base).read_text()
assessor=derive('assess_fixed_b231_vs_stopped77f9_fullgame_v1.py',base,[(assignment(raw,'PAIR_SHA'),'PAIR_SHA='+repr(pairpin['sha256'])),(assignment(raw,'CASE'),'CASE=Path('+repr(str(F))+')')])
sourceproof=h.put(F/'selected-source/exact-source-bindings.json',dict(status='PASS_EXACT_PAIR_NAMESPACE_BINDINGS',pair=pairpin,derivations=derivations,qualified_parent_composition=h.pin(U/'CPU-source-composition-contracts.json'),scientific_games_started=False,promotion=False))
composition=read(U/'CPU-source-composition-contracts.json');seq=composition['sequence']
auth=read(OLD/'future-authenticated-early-C1-original01/qualified-prospective-authenticated-C1-preparation.json');numericproof=auth['numeric_CPU39'];numeric=read(numericproof['path'])['source']
rule=h.put(F/'predeclared-early-C1-rule.json',dict(schema='robotron-predeclared-fullgame-C1-failure-rule-v1',campaign_directory=str(F),pair=pairpin,required_closed_roles=['R1','C1','R2'],stage='after_R2_review_before_C2_launch',skip_C2_only_if_C1_gate_failed=True,promotion_shortcut_allowed=False,assessor=auth['source'],numeric_gate=numeric,scheduler=seq))
family=copy.deepcopy(oldfamily);family.update(pair=pairpin,native=native,leg_reviewer=reviewer,campaign_assessor=assessor,current_Main_health=composition['current_owned_health'],current_Main_owned_overlap=composition['current_owned_overlap'],native_source_proof=sourceproof,reviewer_source_proof=sourceproof,roles_CPU=h.pin(F/'roles-CPU-original02/report.json'),roles_CPU_closeout=close,sequence_source=seq,early_C1_assessor=auth['source'],early_C1_numeric=numeric,early_C1_rule=rule,full64_owned_Main_engineering=composition['prior_full64_engineering_qualification'])
familypin=h.put(F/'selected-source-family.json',family)
ctl=load('_assemble77ctl',h.checked(oldprep['native_controller']));current=read(C/'R1/job.json')
tokens=set();legs=[]
for oldleg in oldprep['legs']:
 role=oldleg['role'];model_role=oldleg['model_role'];directory=F/pathlib.Path(oldleg['directory']).name;directory.mkdir(mode=0o700)
 selected=pair['roles'][model_role];j=read(oldleg['native_job']['path'])
 j.update(runtime=native,output=str(directory/'runtime-original01'),quality_pair_precommit=pairpin,checkpoint=selected['policy'],expected_policy_clocks=selected['saved_clocks'],label='fixed-b231-vs-stopped77f9-'+role+'-original01-20261101',current_main=current['current_main'],current_fleet=current['current_fleet'],screen_support=current['screen_support'],current_v6_health_source=family['current_Main_health'],owned_TRAIN_overlap_source=family['current_Main_owned_overlap'],current_v6_health_qualification=family['full64_owned_Main_engineering'],source_family_manifest=familypin,selected_change='Fresh distinct stopped77f9 candidate versus protectedb231; source-qualified owned Main reconnect observer and ABI/log-seal corrections. Full64/two-per-slot/full-tail gates unchanged; predeclared C1 failure shortcut only.')
 j['quota64_validation']['qualified_full64_owned_Main_engineering']=family['full64_owned_Main_engineering']
 j['sessions']={str(slot):secrets.token_hex(16)for slot in range(4096,4128)};j['connections']={str(slot):secrets.token_hex(16)for slot in range(4096,4128)}
 fresh=set(j['sessions'].values())|set(j['connections'].values());assert len(fresh)==64 and not fresh.intersection(tokens);tokens.update(fresh)
 pins=[native,j['checkpoint'],j['source_package'],j['mame'],j['lua'],j['seed_runtime'],j['screen_support'],j['current_v6_health_source'],j['owned_TRAIN_overlap_source'],j['current_v6_health_qualification'],familypin,pairpin,selected['CPU_report'],selected['original_CPU_readback'],rule,seq,sourceproof,*j['quota64_source_pins'].values(),*j['quota64_validation'].values(),*j['full_tail_predecessors'].values(),j['historical_startup_acceptance_scope'],j['validated_CPU_prefix'],*j['boot_seed']['inputs'],j['boot_seed']['module']]
 pins.extend(family[k]for k in ['native_controller','leg_reviewer','campaign_assessor','decision_kernel','wire_auditor','games_auditor','original_log_reviewer','early_C1_assessor','early_C1_numeric'])
 pins.extend(j['current_fleet'][k]for k in ['job','original_membership','rolemap','physical_helper','source_authority'])
 pins.extend([j['current_fleet']['supervisor']['source'],j['current_main']['startup_authority'],j['current_main']['startup_held']])
 j['inputs']=list({pin['path']:pin for pin in pins}.values());jp=h.put(directory/'job.json',j)
 config=read(oldleg['native_controller_config']['path']);config.update(unit='robotron-b231-77f9-'+role.lower()+'-fullgame-original01.service',output=str(directory/'execution-original01'))
 config['argv']=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',native['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',native['sha256']]
 config['pins']=[ctl.pin(pin['path'])for pin in [jp,*j['inputs']]];cp=h.put(directory/'controller-config.json',config)
 prep=h.put(directory/'prepared-native.json',dict(schema='robotron-fixed-fullgame-native-leg-preparation-v1',role=role,pair=pairpin,native=native,job=jp,controller=oldprep['native_controller'],controller_config=cp,source_family=familypin,scientific_job_launched=False,promotion=False))
 rd=directory/'independent-review-original01';rd.mkdir(mode=0o700)
 rj=read(oldleg['review_job_template']['path']);rj.update(runtime=reviewer,native_prepared=prep,original_native_closeout_path=str(directory/'positive-original-native-closeout.json'),report=str(rd/'report.json'))
 rjp=h.put(directory/'review-job-template.json',rj)
 legs.append(dict(index=oldleg['index'],role=role,model_role=model_role,directory=str(directory),native_prepared=prep,native_job=jp,native_controller_config=cp,review_job_template=rjp,native_closeout_path=str(directory/'positive-original-native-closeout.json'),review_closeout_path=str(directory/'positive-original-review-closeout.json'),display_live_path=str(directory/'display-live.json'),display_receipt_path=str(directory/'display-reviewed.json')))
assert len(tokens)==256
plan=h.put(F/'plan.json',dict(schema='robotron-fixed-fullgame-dashboard-plan-v1',checkpoints={k:v['policy']for k,v in pair['roles'].items()},legs=[dict(index=r['index'],role=r['model_role'],job=dict(label='Protected champion'if r['model_role']=='reference'else'Candidate'),evaluator_status_path=r['display_live_path'],receipt_path=r['display_receipt_path'])for r in legs]))
prepared=copy.deepcopy(oldprep);prepared.update(campaign_directory=str(F),pair=pairpin,source_family=familypin,native=native,leg_reviewer=reviewer,campaign_assessor=assessor,legs=legs,dashboard_plan=plan,sequence_source=seq,early_C1_assessor=auth['source'],early_C1_numeric=numeric,early_C1_numeric_CPU_proof=numericproof,early_C1_rule=rule)
pp=h.put(F/'prepared-campaign.json',prepared)
with (F/'status.json').open('x')as f:json.dump(dict(state='prepared',current_leg=None,legs=[dict(index=r['index'],role=r['model_role'],state='pending')for r in legs],outcome=None,updated_unix_s=time.time()),f);f.flush();os.fsync(f.fileno())
checkerbase=h.pin(G/'tools/full_game_confirmation_proposal/check_fixed_confirmation_preflight_v1.py');raw=h.checked(checkerbase).read_text()
checker=derive('check_fixed_stopped77f9_preflight_v1.py',checkerbase,[(assignment(raw,'F'),'F=Path('+repr(str(F))+')'),("    sequence_path=Path(__file__).with_name('run_fixed_confirmation_sequence_v1.py')","    sequence_path=Path("+repr(seq['path'])+")")])
print(json.dumps(dict(prepared={k:pp[k]for k in ('path','sha256','bytes')},checker={k:checker[k]for k in ('path','sha256','bytes')},pair_sha=pairpin['sha256'],fresh_game_transport_identities=len(tokens),sequence_sha=seq['sha256'])))
