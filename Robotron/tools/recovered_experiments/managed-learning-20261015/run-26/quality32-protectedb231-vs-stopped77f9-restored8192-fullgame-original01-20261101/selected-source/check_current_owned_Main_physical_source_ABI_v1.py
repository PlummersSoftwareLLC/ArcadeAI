import ast,copy,fcntl,importlib.util,json,os,pathlib,socket,subprocess,sys,time
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26'
F=B/'quality32-protectedb231-vs-stopped77f9-restored8192-fullgame-original01-20261101';C=B/'short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_final77h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
reader=load('_final77reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
read=lambda pin,as_json=True:reader.read_pin(pin,as_json=as_json)
pp=h.pin(F/'prepared-campaign.json');p=read(pp);family=read(p['source_family']);sequence=load('_final77sequence',h.checked(p['sequence_source']))
checks=[]
def check(name,value):
 assert value,name;checks.append(name)
check('exact prospective future sequence and all-four rule validation',sequence.validate_future_prepared(dict(runtime=p['sequence_source']),p,h)==F)
for key in ['native','native_controller','leg_reviewer','campaign_assessor','decision_kernel','wire_auditor','games_auditor','original_log_reviewer','current_Main_health','current_Main_owned_overlap','slot_closeout','source_package','early_C1_assessor','early_C1_numeric','sequence_source']:
 read(family[key],False);check('immutable selected source '+key,True)
bindings=read(h.pin(F/'selected-source/exact-source-bindings.json'))
for d in bindings['derivations']:
 old=read(d['parent'],False).decode();new=read(d['selected'],False).decode()
 a=[ast.dump(n)for n in ast.parse(old).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))]
 b=[ast.dump(n)for n in ast.parse(new).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))]
 check('all scientific runtime/review/assessment functions unchanged '+pathlib.Path(d['selected']['path']).name,a==b)
tokens=set();oldtokens=set()
old= B/'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'
for campaign in [old,B/'quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101']:
 for leg in json.loads((campaign/'prepared-campaign.json').read_text())['legs']:
  j=read(leg['native_job']);oldtokens.update(j['sessions'].values());oldtokens.update(j['connections'].values())
for role in ['R1','C1']:
 j=json.loads((C/role/'job.json').read_text());oldtokens.update(j['sessions'].values());oldtokens.update(j['connections'].values())
for leg in p['legs']:
 j=read(leg['native_job']);tokens.update(j['sessions'].values());tokens.update(j['connections'].values())
 check(leg['role']+' no reused scientific output',not pathlib.Path(j['output']).exists())
 check(leg['role']+' same predeclared C1 rule checked before first game',p['early_C1_rule']in j['inputs'])
check('256 distinct transport identities exclude previous campaigns/screens',len(tokens)==256 and not tokens.intersection(oldtokens))
short=read(h.pin(C/'prepared-with-review.json'))
auditor=load('_final77MainAuditor',h.checked(short['independent_owned_Main_auditor']))
rows=[]
for leg in [p['legs'][0],p['legs'][1]]:
 job=read(leg['native_job']);out=F/('preflight-owned-Main-'+leg['role']+'-original01');out.mkdir(mode=0o700)
 health=load('_final77health'+leg['role'],h.checked(job['current_v6_health_source']))
 guard=health.CurrentV6MainHealth(job,out,h);guard.start()
 for index in range(4):
  if index:time.sleep(5.1)
  guard.observe()
 report=guard.finish(None);result=dict(main_samples=guard.samples,main_health_report=report,main_observer_lifecycle=guard.lifecycle)
 audit=auditor.audit_main(job,result,lambda pin:read(pin),h)
 check(leg['role']+' original physical Main samples independently replay',audit['accepted']>=2 and audit['all_logical_clocks_advanced']and audit['final_accepted'])
 rows.append(dict(role=leg['role'],main_report=report,independent_audit=audit))
job=read(p['legs'][0]['native_job']);sockets=[]
try:
 for port in [19998,*range(20000,20032)]:
  s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port));sockets.append(s)
 check('all33 private ports simultaneously bindable',len(sockets)==33)
finally:
 for s in sockets:s.close()
with open(job['lease']['path'],'r+b')as f:
 fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);check('same permanent GPU0 lease free',h.pin(job['lease']['path'])==job['lease']);fcntl.flock(f,fcntl.LOCK_UN)
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
check('private GPU0 compute idle',gpu.returncode==0 and job['gpu_uuid']not in gpu.stdout)
check('no numerical runtime imported','torch'not in sys.modules and'numpy'not in sys.modules)
out=h.put(F/'preflight-physical-source-ABI-original01.json',dict(status='PASS_FRESH_FULLGAME_PHYSICAL_SOURCE_ABI_PREFLIGHT',observed_unix_s=time.time(),prepared=pp,checks=checks,checks_total=len(checks),Main=rows,selected_sequence=p['sequence_source'],selected_early_rule=p['early_C1_rule'],scientific_games_launched=False,confidence_qualified=False,promotion=False))
print(json.dumps(dict(status='PASS_FRESH_FULLGAME_PHYSICAL_SOURCE_ABI_PREFLIGHT',checks=len(checks),report={k:out[k]for k in ('path','sha256','bytes')})),flush=True)
