import ast,importlib.util,json
from pathlib import Path
from types import SimpleNamespace
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';L=B/'future-fast-pending-physical-watch-source-original01-20261101/published-pending-trigger-engineering-original03'
s=importlib.util.spec_from_file_location('_triggerCPUH',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
j=json.loads((L/'job.json').read_text());src=ast.parse(h.checked(j['runtime']).read_text());node=next(n for n in src.body if isinstance(n,ast.FunctionDef)and n.name=='wait_for_published_pending');code=compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),j['runtime']['path'],'exec');checks=[]
def check(name,value):
 assert value,name
 checks.append(name)
def simulate(*,at=None,role='reconnecting_train',epoch='original',fault=False,limit=.1):
 clock=SimpleNamespace(t=0.0);reads=[]
 def sleep(delay):assert 0<=delay<=.02;clock.t+=delay
 time=SimpleNamespace(monotonic=lambda:clock.t,sleep=sleep)
 class P:
  def stat(self):return SimpleNamespace(st_ino=1,st_mtime_ns=int(at is not None and clock.t>=at),st_size=100)
 class Guard:
  expected=dict(status_path='/original/status.json',epoch='original')
  def status(self):
   reads.append(clock.t);state=role if at is not None and clock.t>=at else 'active_train'
   return dict(epoch=epoch,errors=['fault']if fault else[],error_summary=dict(occurrences=int(fault)),slots={'144':dict(state=state)})
 context=dict(time=time,Path=lambda path:P());exec(code,context)
 return context['wait_for_published_pending'](Guard(),limit),reads
(r,snapshot),reads=simulate();check('Stable wait expires within declared bound',r['reason']=='NO_PUBLISHED_PENDING_WITHIN_PREDECLARED_WAIT' and .1<=r['wait_s']<=.12 and snapshot is None)
check('Unchanged snapshot is parsed only once',len(reads)==1 and r['snapshot_reads']==1 and r['stat_checks']<=7)
(r,snapshot),reads=simulate(at=0);check('Already published TRAIN reconnect triggers immediately',r['pending_slots']==[144]and r['wait_s']==0 and snapshot['slots']['144']['state']=='reconnecting_train')
(r,snapshot),reads=simulate(at=.06);check('New published TRAIN reconnect detected before next normal5s tick',r['pending_slots']==[144]and .06<=r['wait_s']<=.08 and len(reads)==2)
(r,snapshot),reads=simulate(at=.04,role='retiring_eval');check('Real EVAL retirement is also a wake-up hint',r['pending_slots']==[144]and snapshot['slots']['144']['state']=='retiring_eval')
(r,snapshot),reads=simulate(at=.04,role='closed_eval');check('Already closed EVAL does not invent pending coverage',r['pending_slots']==[]and snapshot is None)
for name,kwargs in [('Changed original epoch rejected',dict(epoch='replacement')),('Existing fleet fault rejected',dict(fault=True))]:
 try:simulate(**kwargs)
 except AssertionError:check(name,True)
 else:raise AssertionError(name)
check('Wake-up helper contains no process launch, signal or socket access',not any(isinstance(n,ast.Attribute)and n.attr in ['Popen','kill','send_signal','connect','socket','system','run','write_text','write_bytes','open']for n in ast.walk(node)))
for pin in j['inputs']:h.checked(pin)
p=h.put(L/'CPU-trigger-contracts-original01.json',dict(status='PASS_PUBLISHED_PENDING_TRIGGER_CPU_CONTRACTS',checks=checks,checks_total=len(checks),source=j['runtime'],prospective_native=j['prospective_native'],scope='Actual extracted wake-up helper run with deterministic changed/unchanged snapshot and time models. This validates scheduling and fail-closed behavior only; pending branch still needs actual live process/TCP observation and independent replay.',all_health_guards_unchanged=True,live_pending_coverage=False,quality_qualified=False,promotion=False))
print(json.dumps(dict(checks=len(checks),result={k:p[k]for k in ['path','sha256','bytes']})))
