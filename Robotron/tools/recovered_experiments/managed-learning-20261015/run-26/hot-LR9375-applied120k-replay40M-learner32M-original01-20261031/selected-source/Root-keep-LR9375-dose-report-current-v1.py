"""Root-owned bounded observation loop; no learning settings or policy actions."""
import hashlib,json,os,subprocess,time
from pathlib import Path
N=Path(__file__).resolve().parent.parent
OBSERVER=N/'selected-source/Root-observe-LR9375-autoexpert-dose-v1.py'
SHA='d2d506c990df35b354a0ef97f176cdf37b195be761098c142c3380910efd86ab'
OUT=N/'Root-original-dose-observation-loop-original01'
def save(name,obj):
 p=OUT/name;t=p.with_name('.'+name+'.tmp')
 with t.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(t,p)
def main():
 assert hashlib.sha256(OBSERVER.read_bytes()).hexdigest()==SHA
 OUT.mkdir(exist_ok=False)
 birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
 owner=dict(pid=os.getpid(),birth=birth,started_unix_s=time.time(),observer_sha256=SHA,CONTROL_writer='this original loop via serial one-shot observer only',bound_s=14400,cadence_s=45,no_learning_setting_or_policy_actions=True)
 save('owner.json',owner);print(json.dumps(dict(event='started',**owner)),flush=True)
 started=time.monotonic();pending=0;count=0;finish=None;actual_exit=0
 while True:
  tick=time.monotonic();assert hashlib.sha256(OBSERVER.read_bytes()).hexdigest()==SHA
  r=subprocess.run(['/usr/bin/python3.12','-I','-B',str(OBSERVER)],capture_output=True,text=True,timeout=30)
  count+=1
  record=dict(index=count,observed_unix_s=time.time(),actual_exit=r.returncode,stdout=r.stdout,stderr=r.stderr)
  with (OUT/'original-observations.jsonl').open('a') as f:f.write(json.dumps(record,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
  if r.returncode!=0:finish='original_observer_command_failed';actual_exit=1;print(json.dumps(record),flush=True);break
  v=json.loads(r.stdout);save('latest.json',v);print(json.dumps(v,allow_nan=False),flush=True)
  if v['status']=='REJECTED':finish='observation_requires_Root_review';actual_exit=2;break
  pending=pending+1 if v['status']=='PENDING' else 0
  if pending>=20:finish='twenty_consecutive_pending_observations_require_Root_review';actual_exit=3;break
  if v['status']=='VALID' and v['all_reached']:finish='all_primary_dose_thresholds_reached';break
  if time.monotonic()-started>=14400:finish='observation_time_bound_requires_Root_review';actual_exit=4;break
  time.sleep(max(0,45-(time.monotonic()-tick)))
 result=dict(owner=owner,ended_unix_s=time.time(),observations=count,finish=finish,actual_exit=actual_exit,last_observation=json.loads((OUT/'latest.json').read_text()) if (OUT/'latest.json').exists() else None,child_observer_closed=True,learning_controls_or_policy_mutated=False)
 save('result.json',result);(OUT/'result.json').chmod(0o444);print(json.dumps(dict(event='closed',**result)),flush=True);return actual_exit
if __name__=='__main__':raise SystemExit(main())
