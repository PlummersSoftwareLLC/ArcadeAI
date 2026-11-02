import ast,copy,importlib.util,json,pathlib,threading,time
from types import SimpleNamespace
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26'
R=B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101';N=B/'future-fast-pending-physical-watch-source-original01-20261101'
s=importlib.util.spec_from_file_location('_pollCPUWriter',R/'sources/prepare_current_continuous_preservation_header_v3.py');h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
proof=h.read(h.metadata(N/'archived-reconnect-evidence-and-source-only-proposal.json')[0]);checks=[]
def check(name,value):
 assert value,name
 checks.append(name)
def watch(source):
 module=ast.parse(pathlib.Path(source['path']).read_text());run=next(n for n in module.body if isinstance(n,ast.FunctionDef)and n.name=='run')
 node=next(n for n in ast.walk(run)if isinstance(n,ast.FunctionDef)and n.name=='watch_main')
 return compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)],type_ignores=[])),source['path'],'exec')
P=G/'logs/managed-learning-20261015/run-26/short15-protectedb231-vs-distinct8dae-source-only-original01-20261101'
proposal=h.read(h.metadata(P/'source-only-fast-pending-and-distinct-pair-proposal.json')[0])
parent=watch(proposal['parent_native']);future=watch(proposal['prospective_native'])
def simulate(code,windows=(),horizon=35,*,initial_stop=False,collect_failure=False,stop_at_lock=False):
 clock=SimpleNamespace(t=0.0);guard=SimpleNamespace(pending_since=None);errors=[];records=[];waits=[];stopped=threading.Event()
 class Stop:
  flag=initial_stop
  def wait(self,delay):
   waits.append(delay)
   if self.flag:return True
   if clock.t+delay>=horizon:clock.t=horizon;self.flag=True;return True
   clock.t+=delay;return False
  def is_set(self):return self.flag
 stop=Stop()
 class Lock:
  def __enter__(self):
   if stop_at_lock:stop.flag=True
  def __exit__(self,*args):return False
 def collect():
  if collect_failure:raise RuntimeError('declared collection failure')
  begin=clock.t;before=any(a<=begin<b for a,b in windows);clock.t+=.03 if before else 1.1
  after=any(a<=clock.t<b for a,b in windows)
  changed=any(begin<t<=clock.t for a,b in windows for t in (a,b))
  pending=before or after or changed
  if pending:
   if guard.pending_since is None:guard.pending_since=begin
   if clock.t-guard.pending_since>10:raise ValueError('Original reconnect/retirement did not close within10s; no health rescue')
  else:guard.pending_since=None
  records.append(dict(begin=begin,end=clock.t,pending=pending,global_pending_since=guard.pending_since))
 context=dict(health_stop=stop,main_guard=guard,main_lock=Lock(),collect_main=collect,errors=errors,stopped=stopped)
 exec(code,context);context['watch_main']()
 return dict(errors=errors,stopped=stopped.is_set(),waits=waits,records=records)
for name,code in [('parent',parent),('future',future)]:
 stable=simulate(code);check(name+' stable cadence stays5s',not stable['errors']and set(stable['waits'])=={5})
 stop=simulate(code,initial_stop=True);check(name+' stop interrupts before collection',stop['records']==[]and not stop['errors'])
 failure=simulate(code,collect_failure=True);check(name+' collection failure stops once',len(failure['errors'])==1 and failure['stopped'])
 lock=simulate(code,stop_at_lock=True);check(name+' stop while taking lock prevents collection',lock['records']==[]and not lock['errors'])
 late=simulate(code,windows=[(4.5,25)]);check(name+' permanently pending still fails10s',len(late['errors'])==1 and 'within10s'in late['errors'][0])
 delayed=simulate(code,windows=[(4.5,15.6)]);check(name+' late closure cannot rescue deadline',len(delayed['errors'])==1 and delayed['stopped'])
 short=simulate(code,windows=[(4.5,5.8)]);check(name+' isolated quick transition accepted',not short['errors']and any(not r['pending']for r in short['records']))
origin=h.read(proof['accepted334'])['completed_monotonic_s'];windows=[]
for row in proof['short_reconnects']:
 a=h.read(row['wait_event'])['monotonic_ns']/1e9-origin;b=h.read(row['authenticated_new_binding'])['monotonic_ns']/1e9-origin
 windows.append((a,b))
old=simulate(parent,windows,horizon=35);new=simulate(future,windows,horizon=35)
check('archived short-transition timing reproduces parent global expiry',len(old['errors'])==1 and 'within10s'in old['errors'][0])
check('future cadence obtains accepted samples between distinct short transitions',not new['errors']and any(not r['pending']for r in new['records']))
check('future uses both normal5s and pending0.2s waits',set(new['waits'])=={5,.2})
check('future model never accepts pending span past10s',all(r['global_pending_since']is None or r['end']-r['global_pending_since']<=10 for r in new['records']))
check('no numerical runtime imported','torch'not in __import__('sys').modules and 'numpy'not in __import__('sys').modules)
report=h.put(P/'CPU-short-native-poll-cadence-contracts-original01.json',dict(status='PASS_EXTRACTED_WATCH_LOOP_POLLING_CONTRACTS_ENGINEERING_ONLY',observed_unix_s=time.time(),parent=proposal['parent_native'],future=proposal['prospective_native'],checks=checks,checks_total=len(checks),model_scope='Actual extracted nested watch_main functions executed with deterministic event/clock/collector harness. Collector models unchanged global10s rule,0.03s pending metadata and1.1s full collection using actual archived reconnect windows. Not a substitute for live process/TCP/closure validation.',archived_parent_trace=old,prospective_trace=new,all7s_ACK_10s_health_15s_gap_guards_unchanged=True,live_runtime_executed=False,quality_qualified=False,promotion=False))
print(json.dumps(dict(status='PASS_EXTRACTED_WATCH_LOOP_POLLING_CONTRACTS_ENGINEERING_ONLY',checks=len(checks),report={k:report[k]for k in ['path','sha256','bytes']})))
