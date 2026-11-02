import pathlib,json,hashlib,os,subprocess,time,datetime
ROOT=pathlib.Path('/home/dave/source/repos/ArcadeAI');R=ROOT/'Robotron/logs/managed-learning-20261015/run-26';D=R/'quality384M-owned-terminal-unit-release-20261017';U='robotron-quality-256M-vs-384M-20261017.service';T=U.removesuffix('.service')+'.timer';INV='611d7a54ae7e4a649b0e1ed3505a7baa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def call(a):
 z=subprocess.run(a,text=True,capture_output=True,timeout=30);return {'argv':a,'returncode':z.returncode,'stdout':z.stdout,'stderr':z.stderr}
def show(u):
 z=call(['systemctl','--user','show',u]);return z,dict(x.split('=',1) for x in z['stdout'].splitlines() if '=' in x)
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 p.chmod(0o444)
archive=R/'quality384M-original-controller-terminal-root-archive-20261017/archive-receipt.json';clean=R/'quality384M-original-terminal-independent-cleanup-readiness-20261017/cleanup-readiness-receipt.json';default=R/'quality384M-strict-protection-default-review-20261017/root-review.json';assert sha(archive)=='3f02f7a652c3cb2e014b6d8329257758a2b2cc3034e7498d233ff118cc4459c2' and sha(clean)=='6e5de27a8a9f5dc6ca49edbdc306ec5f0016e14e1424b16e169da9126709130e' and sha(default)=='e053474a885208a6db9103cb132cc4c6d091b0037bb7b7c905b7c3e48a18c52c'
a=json.loads(archive.read_text());assert a['original_terminal_exit_archived_before_release'] and a['original_ExecMainCode']=='1' and a['original_ExecMainStatus']=='0'
before,p=show(U);assert p['InvocationID']==INV and p['MainPID']=='0' and p['ExecMainPID']=='3723673' and p['ExecMainCode']=='1' and p['ExecMainStatus']=='0' and p['SubState']=='exited' and p['Result']=='success'
D.mkdir();write(D/'pre-release-original-service-show.json',before);traw,t=show(T);write(D/'pre-release-timer-show.json',traw);write(D/'evidence-precommit.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_terminal_archive':str(archive),'archive_sha256':sha(archive),'cleanup_sha256':sha(clean),'strict_default_sha256':sha(default),'original_invocation':INV,'original_ExecMainPID':3723673,'original_ExecMainCode':1,'original_ExecMainStatus':0,'no_learner_action':True})
z=call(['systemctl','--user','stop',U]);write(D/'owned-service-stop-result.json',z);assert z['returncode']==0
if t.get('LoadState')!='not-found':
 assert t.get('Unit')==U and t.get('LoadState')=='loaded',t;z=call(['systemctl','--user','stop',T]);write(D/'owned-timer-stop-result.json',z);assert z['returncode']==0
for i in range(30):
 after,p=show(U);tafter,tp=show(T)
 if p.get('LoadState')=='not-found' and tp.get('LoadState')=='not-found':break
 time.sleep(.1)
write(D/'post-release-service-show.json',after);write(D/'post-release-timer-show.json',tafter);assert p.get('LoadState')==tp.get('LoadState')=='not-found'
r={'status':'PASS_OWNED_TERMINAL_SERVICE_AND_TIMER_RELEASED_AFTER_ORIGINAL_ARCHIVAL','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_invocation':INV,'original_ExecMainPID':3723673,'original_exit':0,'original_exit_source_archive_sha256':sha(archive),'original_exit_copied_before_stop':True,'owned_unit_released':True,'service_and_timer_not_found':True,'learner_or_fleet_changed':False,'source_freeze_still_held_through_publication':True,'promotion_performed':False}
write(D/'release-receipt.json',r);print(json.dumps({'receipt':str(D/'release-receipt.json'),'sha256':sha(D/'release-receipt.json'),'status':r['status']}))
