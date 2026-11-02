import ast,collections,hashlib,importlib.util,json,os,pathlib,queue,sys,threading,time,types,urllib.parse,urllib.request
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26'
D=B/'current-fleet-cleanup-timeout-diagnostic-original01-20261101';D.mkdir(mode=0o700);(D/'sources').mkdir(mode=0o700)
F=B/'quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101'
M=B/'post-engineering-fullstate-preservation-original03-20261101';fleetpath=M/'post-backup-fleet-v6-original01/status.json'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_queueRepairh',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
def putraw(p,raw):
 with p.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
 return h.pin(p)
fleetpin=putraw(D/'original-faulted-supervisor-status.raw.json',fleetpath.read_bytes());fleet=json.loads(h.checked(fleetpin).read_bytes())
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10)as f:api_pin=putraw(D/'original-Main-API.raw.json',f.read())
cleanup=[]
for slot in ['116','190','104']:
 row=fleet['slots'][slot];bound=json.loads(pathlib.Path(row['current_physical_binding']['path']).read_text());token=bound['data']['connection']['token']
 with urllib.request.urlopen('http://127.0.0.1:8771/api/connection_cleanup_token?'+urllib.parse.urlencode(dict(token=token)),timeout=10)as f:
  p=putraw(D/('original-cleanup-slot'+slot+'.raw.json'),f.read())
 value=json.loads(h.checked(p).read_bytes());assert value['cleanup_error']=='Original connection cleanup failed'and value['FIFO_reset_executed']
 cleanup.append(p)
log= B/'power-outage-recovery-20261027-original01/runtime/trainer-console.log'
lines=[]
with log.open('rb')as f:
 for n,line in enumerate(f,1):
  if b'[REPLAY] disconnect cleanup failed:'in line and b'token=1357169:4636985:'in line:lines.append(dict(line_number=n,exact_utf8_line=line.decode()))
logpin=h.put(D/'original-current-incarnation-ACK-timeout-lines.json',dict(source_path=str(log),selection='Exact existing diagnostic lines for current Main1357169; source is live and may append',lines=lines))
failure=h.put(F/'failed-original-physical-preflight-original01.json',dict(actual_tool_exit=1,tool_chunk='d0d69b',status='FAIL_BEFORE_ANY_SCIENTIFIC_GAME_MAIN_FLEET_FAULTED',error='Current v6 fleet stale or faulted',actual_fleet_faults_present=True,original_failure_records_path=str(F/'preflight-owned-Main-R1-original01/main-observations'),new_campaign_scientific_games_launched=False,promotion=False))
original=(G/'Scripts/dqn/socket_server.py').read_bytes();before=putraw(D/'sources/socket_server.before.py',original)
old=b'        self.async_buffer = AsyncReplayBuffer(agent) if agent and self.replay_enabled else None'
new=b'        self.async_buffer = AsyncReplayBuffer(agent, max_queue_size=8192) if agent and self.replay_enabled else None'
assert original.count(old)==1;candidate=original.replace(old,new,1);assert candidate.replace(new,old,1)==original
candidatepin=putraw(D/'sources/socket_server.queue8192.py',candidate)
oldtree=ast.parse(original);tree=ast.parse(candidate);oldqueue=next(n for n in oldtree.body if isinstance(n,ast.ClassDef)and n.name=='AsyncReplayBuffer');actual=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='AsyncReplayBuffer')
checks=[]
def check(n,x):
 assert x,n;checks.append(n)
check('entire actual AsyncReplayBuffer implementation unchanged',ast.dump(oldqueue)==ast.dump(actual))
ns=dict(queue=queue,threading=threading,time=time,deque=collections.deque,RL_CONFIG=types.SimpleNamespace(pre_death_lookback=120,elite_adaptive_window=200),metrics=types.SimpleNamespace(note_replay_drop=lambda n:None))
exec(compile(ast.Module(body=[actual],type_ignores=[]),'<actual-candidate-AsyncReplayBuffer>','exec'),ns);Buffer=ns['AsyncReplayBuffer']
server=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='SocketServer');init=next(n for n in server.body if isinstance(n,ast.FunctionDef)and n.name=='__init__')
assignment=next(n for n in init.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Attribute)and t.attr=='async_buffer'for t in n.targets))
expression=compile(ast.Expression(body=assignment.value),'<actual-candidate-server-replay-construction>','eval')
captured=[];factory=lambda *a,**kw:captured.append((a,kw))or kw
value=eval(expression,dict(AsyncReplayBuffer=factory,agent=object(),self=types.SimpleNamespace(replay_enabled=True)))
check('actual server constructor selects capacity8192',value==dict(max_queue_size=8192))
captured.clear();value=eval(expression,dict(AsyncReplayBuffer=factory,agent=object(),self=types.SimpleNamespace(replay_enabled=False)))
check('frozen inference-only server constructs no replay consumer',value is None and not captured)
# Saturate the actual full-size candidate queue. The next producer must block,
# and all admitted steps must later drain once through the original consumer.
entered=threading.Event();release=threading.Event();calls=[]
def step(value):
 if value=='first':
  entered.set();assert release.wait(5)
 calls.append(value);return len(calls)-1
buf=Buffer(types.SimpleNamespace(step=step),max_queue_size=8192)
producer=None
try:
 buf.step_async('first',client_id=1);assert entered.wait(2)
 for n in range(8192):buf.step_async(n,client_id=1)
 check('actual queue reaches8192 without dropping',buf.queue.qsize()==8192 and buf.dropped_steps==0)
 done=threading.Event()
 def overflow():buf.step_async('last',client_id=1);done.set()
 producer=threading.Thread(target=overflow);producer.start()
 check('full queue applies preserving backpressure',not done.wait(.05))
 release.set();producer.join(5);check('blocked producer resumes',done.is_set()and not producer.is_alive())
 barrier=buf.barrier_async();check('sole consumer drains through original FIFO barrier',barrier.wait(5))
 check('all8194 steps consumed once in FIFO order',calls==['first',*range(8192),'last'])
 check('no queue overflow experience drops',buf.dropped_steps==0)
finally:
 release.set()
 if producer is not None:producer.join(5)
 buf.stop()
check('stopped original consumer really closed',not buf._thread.is_alive()and buf._drain_complete.is_set())
# A reset must not overtake a previously admitted step or acknowledge early.
entered=threading.Event();release=threading.Event();calls=[]
buf=Buffer(types.SimpleNamespace(step=step),max_queue_size=8,batch_size=1)
try:
 buf.step_async('first',client_id=1);assert entered.wait(2);buf.step_async('old2',client_id=1)
 ack=buf.reset_client_async(1);buf.step_async('new1',client_id=1);barrier=buf.barrier_async()
 check('reset cannot acknowledge before preceding work',not ack.is_set())
 release.set();assert barrier.wait(5)
 check('reset executes between old and new client work',ack.is_set()and calls==['first','old2','new1']and list(buf._client_indices[1])==[2]and list(buf._episode_indices[1])==[2])
finally:release.set();buf.stop()
# Consumer failure still closes admission and makes persistence unqualified.
entered=threading.Event()
def fail_step(value):entered.set();raise ValueError('intentional-consumer-failure')
buf=Buffer(types.SimpleNamespace(step=fail_step),max_queue_size=8)
buf.step_async(1,client_id=1);assert entered.wait(2)
deadline=time.monotonic()+2
while buf.cleanup_health()['consumer_error']is None and time.monotonic()<deadline:time.sleep(.001)
check('consumer failure remains unhealthy',buf.cleanup_health()['admission_open']is False and'intentional-consumer-failure'in buf.cleanup_health()['consumer_error'])
try:buf.step_async(2,client_id=1)
except RuntimeError:check('failed consumer admits no further work',True)
else:raise AssertionError('failed consumer admitted a command')
try:buf.stop()
except RuntimeError as e:check('failed drain cannot qualify persistence','persistence is unqualified'in str(e))
else:raise AssertionError('failed consumer persistence qualified')
check('failed consumer thread closed after drain',not buf._thread.is_alive())
check('no numerical runtime/GPU imported','torch'not in sys.modules and'numpy'not in sys.modules)
report=h.put(D/'candidate-queue8192-CPU-contracts-original01.json',dict(status='PASS_STAGED_QUEUE8192_PRESERVING_FIFO_CONTRACTS',observed_unix_s=time.time(),checks=checks,checks_total=len(checks),before=before,candidate=candidatepin,actual_constructor_only_change=True,queue_backlog_capacity_before=64000,queue_backlog_capacity_candidate=8192,experience_dropping_or_reset_reordering_added=False,cleanup_ACK_deadline_or_supervisor_validity_checks_relaxed=False,existing_failed_cleanup_receipts_modified=False,live_source_or_runtime_changed=False,actual_throughput_or_latency_gain_qualified=False,live_controlled_validation_still_required=True,Main_API=api_pin,faulted_supervisor=fleetpin,cleanup_samples=cleanup,original_log_timeouts=logpin,physical_preflight_failure=failure,promotion=False))
print(json.dumps(dict(status='PASS_STAGED_QUEUE8192_PRESERVING_FIFO_CONTRACTS',checks=len(checks),current_incarnation_timeouts=len(lines),report={k:report[k]for k in ('path','sha256','bytes')})),flush=True)
