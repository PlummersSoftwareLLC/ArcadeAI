from pathlib import Path
import ast,copy,importlib.util,json,pprint,secrets,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';C=B/'short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101';P=B/'short15-protectedb231-vs-distinct8dae-source-only-original01-20261101';D=B/'distinct-stopped8dae-policy-preparation-original01-20261101';N=B/'future-fast-pending-physical-watch-source-original01-20261101';F=B/'short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101';R=B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'
def load(n,p):
 spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);sys.modules[n]=m;spec.loader.exec_module(m);return m
h=load('_fresh8shortH',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');head=load('_fresh8shortHead',R/'sources/prepare_current_continuous_preservation_header_v3.py')
assert not F.exists();F.mkdir(mode=0o700);(F/'selected-source').mkdir(mode=0o700);(F/'review-source').mkdir(mode=0o700)
prev=json.loads((C/'prepared-with-review.json').read_text());blueprint=json.loads((P/'selection-blueprint-current-context-original02-NOT-LAUNCHABLE.json').read_text());bindings=json.loads((N/'live-engineering-original01/actual-current-observer-bindings.json').read_text())
policy=h.put(F/'prospective-monitor-readiness-and-actual-branch-review-policy.json',dict(schema='robotron-prospective-observer-scheduling-readiness-policy-v1',observed_unix_s=time.time(),applies_only_to_new_unstarted_study=str(F),supersedes_self_imposed_separate_pending_coverage_launch_prerequisite=True,
 rationale='The only native code change shortens the wait after a pending observation from5s to0.2s. All actual process/TCP/cleanup validators and7sACK/10s overlap/10s collection/15s gap limits remain exact. CPU models on actual extracted loops and archived short-transition windows pass, and independent actual stable integration passed40 and90 samples. A fresh screen can validate actual runtime data directly, with an additional independent pending-cadence predicate. An unused pending branch is not claimed live-qualified and does not invalidate otherwise fully validated actual score data.',
 exact_short_native_CPU19=h.pin(P/'CPU-short-native-poll-cadence-contracts-original01.json'),stable_live90=h.pin(N/'live-pending-transition-engineering-original02/independent-result-and-positive-owned-closeout.json'),
 in_flight_engineering_case_criteria_unchanged=True,in_flight_engineering_case_must_close_before_scientific_launch=True,
 scientific_validity='Every ordinary original independent startup,score,fullphysical Main,cleanup,source and owned-closure predicate must pass. Every actual pending observation must additionally have a following physical observation starting less than5s after its completion. No pending means no live-pending coverage claim. Any failure invalidates that original arm; no retry/rescue.',
 fullgame_promotion_gates_unchanged=True,prior_failed77f9R1_remains_invalid=True,prior_scores_reused=False,short_endpoint_only=True,promotion=False))
np=head.put(F/'selected-source/native.py',Path(blueprint['private_protocol_sources']['runtime']['path']).read_bytes());assert np['sha256']==blueprint['private_protocol_sources']['runtime']['sha256']
namespace='robotron-short15-b231-8dae-original03-20261101-'
parent_controller=prev['selected_sources']['controller'];controller_source=h.checked(parent_controller).read_text()
old_guard="'robotron-short15-b231-77f9-b576c8496d-'+leg+'-original01-20261101.service'"
new_guard=repr(namespace)+"+leg+'.service'"
assert controller_source.count(old_guard)==1
controller_source=controller_source.replace(old_guard,new_guard)
assert controller_source.count(prev['selected_sources']['native']['path'])==1
controller_source=controller_source.replace(prev['selected_sources']['native']['path'],np['path'])
controller_pin=head.put(F/'selected-source/controller.py',controller_source.encode())
base=prev['independent_owned_Main_auditor']
auditor='''"""Original strict Main replay plus a prospective faster-pending scheduling check."""\nimport importlib.util,sys\nPARENT = '''+repr(base)+'''\n\ndef check_pending_cadence(samples,read):\n raw=[read(s['physical_v6'])for s in samples];rows=[]\n for i,value in enumerate(raw):\n  if value['accepted']:continue\n  if i+1>=len(raw):raise ValueError('Pending final sample has no real recovery observation')\n  gap=raw[i+1]['started_monotonic_s']-value['completed_monotonic_s']\n  if not 0<gap<5:raise ValueError('Actual pending cadence did not obtain next observation before5s')\n  rows.append(dict(after_pending_index=i,next_observation_gap_s=gap))\n return rows\n\ndef audit_main(job,result,read,h):\n spec=importlib.util.spec_from_file_location('_unchanged_strict_Main_replay',h.checked(PARENT));m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)\n original=m.audit_main(job,result,read,h)\n cadence=check_pending_cadence(result['main_samples'],read)\n return dict(original,all_original_strict_predicates_retained=True,actual_pending_cadence_audited=True,live_pending_coverage=bool(cadence),actual_pending_next_observation_gaps=cadence)\n'''
ap=head.put(F/'selected-source/owned_main_with_pending_cadence_v1.py',auditor.encode());sources=copy.deepcopy(prev['selected_sources']);sources.update(native=np,owned_main_auditor=ap,controller=controller_pin);sources.pop('independent_leg_review',None)
source_map=h.put(F/'selected-source-map.json',sources)
selected=copy.deepcopy(blueprint);selected.update(status='ROOT_SELECTED_NOT_LAUNCHED',selected_unix_s=time.time(),private_protocol_sources=dict(runtime=np,lua=selected['private_protocol_sources']['lua']),prospective_monitor_readiness_policy=policy)
for k in ['preparation_scope','supersedes_source_only_blueprint','supersession_reason']:selected.pop(k,None)
sp=h.put(F/'selection.json',selected)
controller=load('_fresh8shortCtl',h.checked(sources['controller']));cpu=load('_fresh8shortCpu',h.checked(prev['independent_review']['CPU_controller']))
# Explicit current inputs replace the old Main/selection family; immutable boot,
# wire/score components and validated package remain exactly selected.
state=json.loads((B.parent/'state.json').read_text());runtime=h.pin(R/'actual-restored-current-training-runtime.json');control=h.pin(G/'models_dqn/learning_control.json')
fixed=[sp,source_map,runtime,selected['proposal'],policy,control,np,ap,prev['independent_owned_Main_auditor'],*list(bindings.values())[:0]]
def collect_pins(value):
 if isinstance(value,dict):
  if set(['path','sha256','bytes','identity'])<=set(value):return [value]
  return [p for child in value.values()for p in collect_pins(child)]
 if isinstance(value,list):return [p for child in value for p in collect_pins(child)]
 return []
fixed+=collect_pins(bindings)
jobmap={};configs={};all_ids=[]
for leg,role in [('R1','reference'),('C1','candidate')]:
 parent=json.loads((C/leg/'job.json').read_text());j=copy.deepcopy(parent);out=F/leg;out.mkdir(mode=0o700)
 j.update(runtime=np,output=str(out/'runtime-original01'),screen_selection=sp,checkpoint=selected[role]['checkpoint'],policy_authority=selected[role]['authority'],expected_policy_clocks=selected[role]['expected_policy_clocks'],label=F.name+'-'+leg,measurement_label=F.name+'-'+leg,**bindings)
 j['sessions']={str(s):secrets.token_hex(16)for s in j['actor_slots']};j['connections']={str(s):secrets.token_hex(16)for s in j['actor_slots']};all_ids.extend([*j['sessions'].values(),*j['connections'].values()])
 newinputs=fixed+[j['checkpoint'],j['policy_authority'],j['completion_codec'],j['screen_support'],j['seed_runtime'],j['source_package'],j['lua'],*j['components'].values(),*j['boot_seed']['inputs'],j['boot_seed']['module']]
 seen={};j['inputs']=[]
 for pin in newinputs:
  if pin['path']not in seen:seen[pin['path']]=pin;j['inputs'].append(pin)
  else:assert seen[pin['path']]==pin
 jp=h.put(out/'job.json',j);argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',np['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',np['sha256']]
 c=copy.deepcopy(json.loads(Path(json.loads((C/'controller-configs.json').read_text())['configs'][leg]['path']).read_text()));c.update(unit=namespace+leg.lower()+'.service',output=str(out/'controller-execution-original01'),argv=argv,pins=[controller.pin(p['path'])for p in [jp,np]])
 cp=h.put(out/'controller-config.json',c);configs[leg]=cp;jobmap[leg]=dict(job=jp,argv=argv)
assert len(set(all_ids))==len(all_ids)==128
configs_pin=h.put(F/'controller-configs.json',dict(ordered_legs=['R1','C1'],configs=configs))
review_parent=prev['independent_review']['source'];review=h.checked(review_parent).read_text();oldC="C=Path("+repr(str(C))+")";assert oldC in review;review=review.replace(oldC,"C=Path("+repr(str(F))+")")
old_sha=json.loads((C/'selection.json').read_text());old_selection_sha=prev['selection']['sha256'];assert review.count(old_selection_sha)==1;review=review.replace(old_selection_sha,sp['sha256'])
start=review.index('OWNED_MAIN_AUDITOR=');end=review.index('\ndef audit_main',start);review=review[:start]+'OWNED_MAIN_AUDITOR='+pprint.pformat(ap)+'\n'+review[end:];ast.parse(review)
rp=head.put(F/'review-source/review_current_short_screen_leg_v1.py',review.encode());sources['independent_leg_review']=rp
rconfigs={};reports={}
for leg in ['R1','C1']:
 rd=F/(leg+'-independent-review-original01');rd.mkdir(mode=0o700);oldrc=json.loads((C/(leg+'-independent-review-original01')/'controller-config.json').read_text());rc=copy.deepcopy(oldrc);rc.update(unit='robotron-short15-8dae-review-'+sp['sha256'][:10]+'-'+leg.lower()+'.service',output=str(rd/'execution-original01'),argv=['/usr/bin/python3','-I','-B',rp['path'],'--execute','--leg',leg,'--source-sha256',rp['sha256'],'--output',str(rd/'report.json')],pins=[cpu.pin(p['path'])for p in [rp,sp,jobmap[leg]['job'],ap]])
 rconfigs[leg]=h.put(rd/'controller-config.json',rc);cpu.checked_config(rconfigs[leg]['path']);reports[leg]=str(rd/'report.json')
protocol=copy.deepcopy(prev['independent_review']);protocol.update(source=rp,configs=rconfigs,reports=reports)
prepared=dict(ordered_legs=['R1','C1'],selection=sp,selected_sources=sources,screen_only=True,promotion=False,jobs=jobmap,independent_owned_Main_auditor=ap,horizon_checkpoint_auditor=prev['horizon_checkpoint_auditor'],controller_configs=configs_pin,independent_review=protocol,derivations=dict(parent_controller=parent_controller,controller_namespace_and_native_path_only_changed=True,failed_unstarted_preparation=h.pin(B/'short15-protectedb231-vs-distinct8dae-fast-pending-original01-20261101/original-failed-CPU-preflight-NO-SCIENTIFIC-LAUNCH.json'),parent_prepared=h.pin(C/'prepared-with-review.json'),monitor_readiness=policy,source_only_proposal=h.pin(P/'source-only-fast-pending-and-current-context-proposal-original02.json')))
pp=h.put(F/'prepared-with-review.json',prepared)
print(json.dumps(dict(prepared={k:pp[k]for k in ['path','sha256','bytes']},selection_sha=sp['sha256'],fresh_transport_identities=128,scientific_launch_started=False)))
