import pathlib,json,hashlib,os,subprocess,datetime,time,socket
R=pathlib.Path('/home/dave/source/repos/ArcadeAI');RUN=R/'Robotron/logs/managed-learning-20261015/run-26';D=RUN/'quality384M-actual-default-plan-prelaunch-20261017';OUT=R/'Robotron/logs/managed-learning-20261015/quality-256M-vs-384M-20261017';U='robotron-quality-256M-vs-384M-20261017';J=RUN/'quality384M-actual-durable-launch-reviewed1-20261017'
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 p.chmod(0o444)
def call(a):
 q=subprocess.run(a,text=True,capture_output=True,timeout=20);return {'argv':a,'returncode':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
def show(u):
 q=call(['systemctl','--user','show',u]);return q,dict(x.split('=',1) for x in q['stdout'].splitlines() if '=' in x)
def start(pid):return pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
import argparse
p=argparse.ArgumentParser();p.add_argument('--plan-review',type=pathlib.Path,required=True);p.add_argument('--cpu-review',type=pathlib.Path,required=True);p.add_argument('--runtime-readiness',type=pathlib.Path,required=True);a=p.parse_args()
assert sha(D/'default-plan.json')=='60b9a11543bcd3560517fde4050ca09439883ed67837be967793fc81ab0e2e0c'
assert sha(D/'root-default-plan-source-archive-review.json')=='27f39b2483a3c7c4e7362e6d600ff73464043b480248684db55b30c66cc51b6a'
reviews={str(x):dict(sha256=sha(x),receipt=json.loads(x.read_text())) for x in [a.plan_review,a.cpu_review,a.runtime_readiness]}
for name,entry in reviews.items():
 data=entry['receipt'];assert data.get('status','').startswith('PASS'),(name,data.get('status'))
assert time.time()-a.runtime_readiness.stat().st_mtime<300,'Fresh runtime readiness required within300s'
source=json.loads((D/'root-default-plan-source-archive-review.json').read_text())
for src,spec in source['source_entries'].items():assert sha(src)==spec['sha256'] and sha(spec['copy'])==spec['sha256']
plan=json.loads((D/'default-plan.json').read_text());assert not OUT.exists()
for role,entry in plan['checkpoints'].items():assert sha(entry['source'])==entry['sha256']
assert not (R/'Robotron/models_dqn/managed_save.request.json').exists()
for u in [U+'.service',U+'.timer','robotron-checkpoint-384M-run26-rearmed-post-warmup-aa-reviewed1-20261017.service','robotron-verify384-checkpoint-cpu-reviewed1-20261017.service']:assert show(u)[1].get('LoadState')=='not-found',u
for u,pid,ticks,inv in [('robotron-managed-run-26-d3b365c9-trainer.service',3032848,'28609635','b14bebd992f84c80adc1fa21a7df3213'),('robotron-managed-run-26-d3b365c9-fleet.service',2258189,'26614335','5ade9b2810524877921946df11ea597e')]:
 q,s=show(u);assert s.get('MainPID')==str(pid) and s.get('InvocationID')==inv and s.get('SubState')=='running' and start(pid)==ticks
for netfile in ['/proc/net/tcp','/proc/net/tcp6']:
 for row in pathlib.Path(netfile).read_text().splitlines()[1:]:
  fields=row.split();assert not (int(fields[1].rsplit(':',1)[1],16)==9999 and fields[3]=='0A'),'Port9999 listener exists'
# Passive kernel socket-table read; no connection or fake handshake.
argv=json.loads((D/'default-argv.json').read_text());assert '--launch' not in argv and argv.count('--game-boundary-diagnostics')==1;argv.append('--launch')
J.mkdir();(J/'root-launch-controller.py').write_bytes(pathlib.Path(__file__).read_bytes())
launch=['systemd-run','--user','--on-active=3s','--timer-property=AccuracySec=100ms','--unit='+U,'--property=WorkingDirectory='+str(R),'--property=Restart=no','--property=RemainAfterExit=yes','--property=CollectMode=inactive','--property=KillMode=mixed','--property=KillSignal=SIGINT','--property=SendSIGKILL=no','--property=TimeoutStopSec=240s','--property=StandardOutput=append:'+str(J/'console.log'),'--property=StandardError=inherit',*argv]
assert sum(x.startswith('--unit=') for x in launch)==1 and '--wait' not in launch and '--collect' not in launch
write(J/'precommit.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unit':U,'argv':launch,'default_plan_sha256':sha(D/'default-plan.json'),'source_archive_review_sha256':sha(D/'root-default-plan-source-archive-review.json'),'independent_reviews':reviews,'checkpoint_proof_sha256':sha(RUN/'quality384M-checkpoint-verification-preparation-20261017/cpu-verification.json'),'source_freeze':True,'learning_changes':False,'scheduling_delay_s':3})
q=call(launch);write(J/'scheduling-carrier-result.json',dict(q,carrier_reaped_by_subprocess_run=True,returned_unix_s=time.time()));assert q['returncode']==0,q
raw,t=show(U+'.timer');write(J/'original-timer-show-after-carrier-reaped.json',raw)
assert t.get('ActiveState')=='active' and t.get('SubState')=='waiting','Carrier did not exit while timer still waiting; investigate without relaunch'
raw,service=show(U+'.service');write(J/'service-before-trigger.json',raw);assert service.get('MainPID')=='0','Service triggered before carrier reaped proof'
write(J/'launch-submitted.json',{'status':'DURABLE_LAUNCH_SUBMITTED','unit':U,'carrier_returncode':0,'carrier_reaped_before_trigger':True,'timer_waiting_after_carrier_reap':True,'campaign_output_absent_before_trigger':not OUT.exists(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
print(json.dumps({'status':'DURABLE_LAUNCH_SUBMITTED','unit':U,'root_launch':str(J),'carrier_reaped_before_trigger':True}))
