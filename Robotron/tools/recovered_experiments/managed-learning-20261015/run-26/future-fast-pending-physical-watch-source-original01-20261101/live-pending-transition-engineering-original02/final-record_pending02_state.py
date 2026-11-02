from pathlib import Path
import hashlib,importlib.util,json,os,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';N=B/'future-fast-pending-physical-watch-source-original01-20261101';L=N/'live-pending-transition-engineering-original02';P=B.parent/'state.json';D=G/'DELL_SETUP.md';U=G/'html/next-policy-evaluation.json'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
h=load('_recPendingH',B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101/sources/prepare_current_continuous_preservation_header_v3.py')
phase=sys.argv[1];number={'prepared':175,'running':176,'closed':177}[phase]
old=P.read_bytes();db=D.read_bytes();ub=U.read_bytes();s=json.loads(old);g=s['optimization_goal']; prior=s['current_optimization_recovery_index']
expected={175:'552e95d90779fc02186829a7790447b78d7ff51563a79948ec8cfad861e591b8'}
if number in expected:assert prior['sha256']==expected[number]
else:assert f'original{number-1}.json' in prior['path']
pre={k:h.put(L/(f'{k}-before-index{number}.exact'+suf),b)for k,suf,b in [('canonical','.json',old),('DELL','.md',db),('public','.json',ub)]}
prep=h.metadata(L/'prepared-not-launched.json')[0];wait=None;owner=None
if phase=='running':
 c=json.loads((L/'controller-original-child.json').read_text());o=json.loads((L/'execution-original01/root-original-identity.json').read_text());birth=lambda pid:int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]);assert birth(c['pid'])==c['starttime_ticks'] and birth(o['pid'])==o['starttime_ticks']
 owner=dict(native=o,controller=c);wait=dict(kind='FINITE_READONLY_PENDING_TRANSITION_ENGINEERING',tool_session=int(sys.argv[2]),native_pid=o['pid'],native_birth=o['starttime_ticks'],controller_pid=c['pid'],directory=str(L),original_attempt=1,no_retry=True)
summary={
 'prepared':'Prepared a fresh finite read-only live monitor check requiring40accepted physicalsamples,1pending transition and accepted recovery. No actor signals or addedgame workload; unchanged7sACK/10soverlap/15sgap. Original failedscientificR1 staysinvalid; no policy verdict. Launch once then inspect originalresults.',
 'running':'Original finite read-only pending-transition monitor check is running. Observe the same original tool/process, never relaunch. Needs40accepted samples plus1pending and accepted recovery; no pending by520s means coverageinsufficient. Training155TRAIN/remainingEVAL continues; original scientificR1 remainsinvalid.',
 'closed':'Original finite read-only case33593 monitor/controller exited0 and allresourcesclosed; outer postprocessing exited1 on a reader-ABI mismatch, preserved then independently reviewed read-only. All90 physicalsamples replayed,0pending, maxgap5.884s: stableintegration only, pendingbranch NOT qualified. Original failed77f9R1 remainsinvalid. Next verify distinct8dae CPU/inference preparation, and obtain livepending coverage in a fresh predeclared case before any scientific comparison. No actor reconnects induced; Maintraining continues.'}[phase]
result=h.metadata(L/'independent-result-and-positive-owned-closeout.json')[0]if phase=='closed'else None
value=dict(schema='robotron-current-optimization-recovery-index-v1',status='FINITE_READONLY_PENDING_TRANSITION_ENGINEERING_'+phase.upper(),observed_unix_s=time.time(),prior_index=prior,preimages=pre,preparation=prep,original_owner=owner,independent_result=result,actual_running_wait=wait,main_training_running=True,scientific_job_running=False,engineering_job_running=phase=='running',next_action=summary,promotion=False)
ip=h.put(L/f'pending-transition-engineering-{phase}-index-original{number}.json',value);small={k:ip[k]for k in ['path','sha256','bytes']};job={k:prep[k]for k in ['path','sha256','bytes']}
for dest in [s,g]:
 dest.update(current_optimization_recovery_index=small,actual_running_wait=wait,main_training_running=True,scientific_job_running=False,engineering_job_running=phase=='running',active_engineering_job=job if phase!='closed'else None)
 if result:dest['latest_engineering_result']={k:result[k]for k in ['path','sha256','bytes']}

if phase=='closed':
 candidate=h.metadata(B/'distinct-stopped8dae-policy-preparation-original01-20261101/CPU-roles-original01/prepared-CPU-roles.json')[0]
 g['next_distinct_candidate_CPU_preparation']={k:candidate[k]for k in ['path','sha256','bytes']}
g['next_action']=summary;s['updated_unix_s']=time.time();g['updated_unix_s']=time.time()
out=(json.dumps(s,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(out)<1<<20
public=json.loads(ub);public['stage']='observer_transition_engineering_'+phase;public['updated_unix_s']=time.time();public['observation_unix_s']=time.time();public['next_work'].update(state=public['stage'],current_stage='Checking live game reconnections'if phase!='closed'else 'Reviewing the live monitor check',detail='Training continues. A read-only monitor check requires an observed reconnect and complete recovery. The previous A/B run remains invalid.',waiting_for='Original bounded read-only check'if phase=='running'else 'Engineering validation',updated_unix_s=time.time(),observation_unix_s=time.time())
updated=(json.dumps(public,indent=2,allow_nan=False)+'\n').encode()
def cas(path,before,after):
 assert path.read_bytes()==before
 t=path.with_name(path.name+f'.pending02-{number}.tmp')
 with t.open('xb')as f:f.write(after);f.flush();os.fsync(f.fileno())
 assert path.read_bytes()==before;os.replace(t,path);fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
cas(P,old,out);cas(D,db,(f'Robotron recovery index{number}: {small["path"]}\n{summary}\n\n'.encode()+db));cas(U,ub,updated)
print(json.dumps(dict(index=small,state_bytes=len(out),phase=phase,actual_running_wait=wait)))
