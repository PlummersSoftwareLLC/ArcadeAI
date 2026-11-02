from pathlib import Path
import ast,copy,hashlib,importlib.util,json,os,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron'); B=G/'logs/managed-learning-20261015/run-26'; N=B/'future-fast-pending-physical-watch-source-original01-20261101'; O=N/'live-engineering-original01'; L=N/'live-pending-transition-engineering-original02'
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
h=load('_prepPending02',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
head=load('_pending02header',B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101/sources/prepare_current_continuous_preservation_header_v3.py')
assert not L.exists();L.mkdir(mode=0o700)
def putbytes(p,b):return head.put(p,b)
old=(O/'run_live_fast_pending_watch_engineering_v1.py').read_text();new=old
edits=[
("job['schema']=='robotron-readonly-fast-pending-watch-engineering-v1'and job['accepted_samples_required']==40", "job['schema']=='robotron-readonly-fast-pending-transition-engineering-v2'and job['accepted_samples_required']==40 and job['pending_samples_required']==1 and job['stable_observation_window_s']==520"),
("if len(accepted)>=job['accepted_samples_required']:health_stop.set()", "covered = len(samples)>len(accepted) and not value['phase']['overlap_pending']\n  if len(accepted)>=job['accepted_samples_required'] and (covered or time.monotonic()-started>=job['stable_observation_window_s']):health_stop.set()"),
("len(accepted)==40", "len(accepted)>=40"),
("report=dict(status='PASS_READONLY_LIVE_FAST_PENDING_PHYSICAL_WATCH_ENGINEERING',physical_health_report=final,", "covered = len(samples)-len(accepted)>=job['pending_samples_required']\n  report=dict(status='PASS_LIVE_PENDING_TRANSITION_WATCH_ENGINEERING' if covered else 'STABLE_LIVE_WATCH_COVERAGE_INSUFFICIENT_NO_PENDING',pending_branch_live_coverage=covered,physical_health_report=final,")]
for a,b in edits:
 assert new.count(a)==1,(a,new.count(a));new=new.replace(a,b)
ast.parse(new)
rp=putbytes(L/'run_live_pending_transition_engineering_v2.py',new.encode())
jold=json.loads((O/'job.json').read_text()); bindings=jold['bindings'];h.checked(bindings)
j=copy.deepcopy(jold);j.update(schema='robotron-readonly-fast-pending-transition-engineering-v2',runtime=rp,accepted_samples_required=40,pending_samples_required=1,stable_observation_window_s=520,output=str(L/'runtime-original01'),report=str(L/'report.json'))
j['inputs']=[rp if x==jold['runtime'] else x for x in j['inputs']]
for x in j['inputs']:h.checked(x)
jp=h.put(L/'job.json',j)
prep=json.loads((O/'prepared-not-launched.json').read_text());controller=prep['controller'];ctl=load('_pending02ctl',h.checked(controller))
c=copy.deepcopy(json.loads((O/'controller-config.json').read_text()));c['unit']='robotron-pending-transition-CPU-'+jp['sha256'][:12]+'.service';c['output']=str(L/'execution-original01')
for i,x in enumerate(c['argv']):
 if x==jold['runtime']['path']:c['argv'][i]=rp['path']
 if x==str(O/'job.json'):c['argv'][i]=jp['path']
 if x==prep['job']['sha256']:c['argv'][i]=jp['sha256']
c['pins']=[ctl.pin(p['path']) for p in [jp]+j['inputs']];cp=h.put(L/'controller-config.json',c);ctl.checked_config(cp['path'])
def watch(src):
 run=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='main');return None
pre=h.put(L/'prepared-not-launched.json',dict(status='PRECOMMITTED_FINITE_READONLY_PENDING_TRANSITION_ENGINEERING_NOT_LAUNCHED',controller=controller,controller_config=cp,job=jp,
 success_rule='At least40 accepted actual physical/TCP samples, at least1 pending transition, final sample accepted; independent replay and original positive closure required. No induced actor reconnects.',
 finite_stop='Stop on coverage and40accepted; otherwise stop on accepted sample after520s. Max540s collection/550s wall/600s resource scope. No transition means coverage insufficient, not qualification.',
 preserved_bounds=dict(cleanup_ACK_s=7,overlap_s=10,collection_s=10,observer_gap_s=15),
 actual_extracted_watch_loop_unchanged=True,previous_stable40_result=h.pin(O/'independent-stable-live-engineering-result-and-positive-closeout.json'),
 no_model_or_actor_or_GPU_context=True,no_Main_control_changes=True,scientific_cohort=False,quality_qualified=False,promotion=False))
print(json.dumps({k:pre[k]for k in ['path','sha256','bytes']}))
