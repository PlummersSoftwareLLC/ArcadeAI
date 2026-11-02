from pathlib import Path
import ast,copy,importlib.util,json,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';C=B/'short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101';F=B/'short15-protectedb231-vs-distinct8dae-fast-pending-original01-20261101';N=B/'future-fast-pending-physical-watch-source-original01-20261101';L=N/'published-pending-trigger-engineering-original03'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_pre8H',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');reader=load('_pre8Reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py');read=lambda p,as_json=True:reader.read_pin(p,as_json=as_json);checks=[]
def check(name,v):
 if not v:raise ValueError(name)
 checks.append(name)
p=read(h.pin(F/'prepared-with-review.json'));old=read(h.pin(C/'prepared-with-review.json'));sel=read(p['selection']);native=load('_pre8Native',h.checked(p['selected_sources']['native']));ctl=load('_pre8Ctl',h.checked(p['selected_sources']['controller']));cpu=load('_pre8CPU',h.checked(p['independent_review']['CPU_controller']));audit=load('_pre8Audit',h.checked(p['independent_owned_Main_auditor']))
check('Fresh distinct candidate8dae and protectedb231 exact identities',sel['candidate']['checkpoint']['sha256']=='8dae5cccd52624755d291a086cc363c7da3995a821cc1bc2c58310ce4bcb9537' and sel['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883')
check('Fixed15minute endpoint and descriptive5/10 checkpoints; no promotion',sel['screen_horizon_ns']==900_000_000_000 and sel['checkpoint_offsets_ns']==[300_000_000_000,600_000_000_000]and sel['short_screen_is_promotion_evidence']is False and sel['promotion']is False)
old_ast=ast.parse(Path(old['selected_sources']['native']['path']).read_text());new_ast=ast.parse(h.checked(p['selected_sources']['native']).read_text());w=next(n for n in ast.walk(new_ast)if isinstance(n,ast.FunctionDef)and n.name=='watch_main');loop=next(n for n in w.body if isinstance(n,ast.While));check('Only observer pending sleep changes to0.2s; stable cadence5s',ast.unparse(loop.test)=='not health_stop.wait(0.2 if main_guard.pending_since is not None else 5)');loop.test=ast.parse('not health_stop.wait(5)',mode='eval').body;check('Whole native AST otherwise exactly qualified parent',ast.dump(old_ast,include_attributes=False)==ast.dump(new_ast,include_attributes=False))
for k in ['controller','outer','recorder','report','score_auditor','horizon_checkpoint_auditor','lua','health','owned_overlap']:
 check('Exact unchanged '+k,p['selected_sources'][k]==old['selected_sources'][k]);h.checked(p['selected_sources'][k])
# Review code differs only by new study root/selection and the stricter auditor.
r_ast=ast.parse(h.checked(p['independent_review']['source']).read_text());o_ast=ast.parse(h.checked(old['independent_review']['source']).read_text());nodes={n.targets[0].id:n for n in o_ast.body if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
for i,n in enumerate(r_ast.body):
 if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id in ['C','OWNED_MAIN_AUDITOR']:r_ast.body[i]=copy.deepcopy(nodes[n.targets[0].id])
for n in ast.walk(r_ast):
 if isinstance(n,ast.Constant)and n.value==p['selection']['sha256']:n.value=old['selection']['sha256']
check('Reviewer predicate AST unchanged apart from exact new bindings',ast.dump(r_ast,include_attributes=False)==ast.dump(o_ast,include_attributes=False))
all_ids=[];configs=read(p['controller_configs']);jobs={}
for leg in ['R1','C1']:
 j=read(p['jobs'][leg]['job']);jobs[leg]=j;native.validate_job(j);check(leg+' actual native/context preflight',native.validate_completed_context(j,h)['source_root'].is_dir());cfg=read(configs['configs'][leg]);ctl.checked_config(configs['configs'][leg]['path']);cpu.checked_config(p['independent_review']['configs'][leg]['path'])
 check(leg+' exact original controller argv',cfg['argv']==p['jobs'][leg]['argv']);check(leg+' new current Main2784587 binding',j['current_main']['owner']['pid']==2784587 and j['current_fleet']['supervisor']['pid']==2794949);check(leg+' fresh output does not exist',not Path(j['output']).exists());
 for pin in j['inputs']:h.checked(pin)
 all_ids.extend([*j['sessions'].values(),*j['connections'].values()])
 check(leg+' frozen policy and authority source pinned',h.pin(j['checkpoint']['path'])==j['checkpoint']and h.pin(j['policy_authority']['path'])==j['policy_authority'])
check('128 wholly fresh unique transport identities',len(all_ids)==len(set(all_ids))==128)
# Execute the added predicate on fast, stable, late and malformed sequences.
def sample(rows):
 return audit.check_pending_cadence([{'physical_v6':dict(index=i)}for i in range(len(rows))],lambda p:rows[p['index']])
check('Stable stream makes no pending coverage claim',sample([dict(accepted=True,started_monotonic_s=0,completed_monotonic_s=1)])==[])
fast=sample([dict(accepted=False,started_monotonic_s=0,completed_monotonic_s=.1),dict(accepted=True,started_monotonic_s=.3,completed_monotonic_s=1.3)]);check('Actual following fast observation accepted',len(fast)==1 and abs(fast[0]['next_observation_gap_s']-.2)<1e-9)
for label,rows in [('Old5s pending delay rejected',[dict(accepted=False,started_monotonic_s=0,completed_monotonic_s=.1),dict(accepted=True,started_monotonic_s=5.1,completed_monotonic_s=6)]),('Pending final sample rejected',[dict(accepted=False,started_monotonic_s=0,completed_monotonic_s=.1)]),('Nonpositive observation gap rejected',[dict(accepted=False,started_monotonic_s=0,completed_monotonic_s=.1),dict(accepted=True,started_monotonic_s=.1,completed_monotonic_s=1)])]:
 try:sample(rows)
 except ValueError:check(label,True)
 else:raise ValueError(label)
# Actual original live engineering data are only a Main-replay integration case,
# never reference/candidate score evidence.
e=read(h.pin(L/'independent-result-and-positive-owned-closeout.json'));check('Prior original engineering fully closed actual0',e['all_original_resources_closed']and e['actual_original_native_exit']==0 and e['actual_original_tool_exit']==0)
r=read(h.pin(L/'report.json'));m=read(r['physical_health_report']);binding=read(read(h.pin(L/'job.json'))['bindings']);wrapped=audit.audit_main(binding,dict(main_health_report=r['physical_health_report'],main_samples=m['samples'],main_observer_lifecycle=dict(original_observer_thread_closed=True,no_child_scope_created=True)),read,h)
check('New independent wrapper replays all49 actual physical samples with strict parent',wrapped['accepted']==49 and wrapped['pending']==0 and wrapped['all_original_strict_predicates_retained']and wrapped['live_pending_coverage']is False)
check('Read-only validation imports no numerical runtime','torch'not in sys.modules and 'numpy'not in sys.modules)
result=h.put(F/'CPU-preflight-and-additional-cadence-contracts-original01.json',dict(status='PASS_FRESH_DISTINCT8DAE_SHORT_SCREEN_CPU_PREFLIGHT',observed_unix_s=time.time(),prepared=h.pin(F/'prepared-with-review.json'),checks=checks,checks_total=len(checks),actual_stable_Main_wrapper_replay=wrapped,pending_branch_live_coverage=False,scientific_arm_launched=False,prior_failed77f9_not_retried_or_rescued=True,all_old_health_and_score_predicates_unchanged=True,extra_pending_cadence_predicate_added=True,quality_qualified=False,promotion=False))
print(json.dumps(dict(checks=len(checks),result={k:result[k]for k in ['path','sha256','bytes']})),flush=True)
