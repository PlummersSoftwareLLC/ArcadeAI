import pathlib,hashlib,json,subprocess,os,datetime,time,stat
ROOT=pathlib.Path('/home/dave/source/repos/ArcadeAI');R=ROOT/'Robotron/logs/managed-learning-20261015/run-26';U='robotron-checkpoint-384M-run26-rearmed-post-warmup-aa-reviewed1-20261017.service';INV='2eca9cff5b5a4bc4a873f532507ea9c6';J=R/'fresh3-384M-gate-terminal-root-archive-20261017'
def call(a):
 q=subprocess.run(a,text=True,capture_output=True);return {'argv':a,'returncode':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
def show():
 q=call(['systemctl','--user','show',U]);return q,dict(x.split('=',1) for x in q['stdout'].splitlines() if '=' in x)
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 p.chmod(0o444)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def fingerprint(p):
 before=p.lstat();assert stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
 with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  assert os.fstat(f.fileno())==before;h=hashlib.file_digest(f,'sha256').hexdigest();assert os.fstat(f.fileno())==before
 assert p.lstat()==before
 return {'path':str(p),'sha256':h,'bytes':before.st_size,'device':before.st_dev,'inode':before.st_ino,'mode':oct(stat.S_IMODE(before.st_mode)),'mtime_ns':before.st_mtime_ns,'ctime_ns':before.st_ctime_ns}
raw,p=show();assert p.get('InvocationID')==INV and p.get('ExecMainPID')=='3593422'
if p.get('SubState')=='running':print('WAIT: exact owned384 watcher still running');raise SystemExit(0)
assert p.get('ActiveState')=='active' and p.get('SubState')=='exited' and p.get('MainPID')=='0' and p.get('ExecMainCode')=='1' and p.get('ExecMainStatus')=='0',p
candidate=ROOT/'Robotron/models_dqn/managed-checkpoints/fresh3-384M.pt';gate=R/'fresh3-384M-gate.json';request=ROOT/'Robotron/models_dqn/managed_save.request.json';completed=request.with_name(request.name+'.completed')
if request.exists() or json.loads(completed.read_text())!={'tag':'fresh3-384M'}:print('WAIT: original save completion not yet settled');raise SystemExit(0)
g=json.loads(gate.read_text());assert g['tag']=='fresh3-384M' and g['target']==388629023 and g['experiment']=='best10M-fresh3-eps10-cap8-nosmooth' and g['checkpoint']==str(candidate) and g['trigger_snapshot']['learner_frame_count']>=388629023 and g['trigger_snapshot']['client_count']==192
model=fingerprint(candidate);gatefp=fingerprint(gate);assert 200*2**20<=model['bytes']<=400*2**20
J.mkdir();(J/'root-archive-controller.py').write_bytes(pathlib.Path(__file__).read_bytes());write(J/'original-terminal-show.json',raw);write(J/'original-unit-cat.json',call(['systemctl','--user','cat',U]));write(J/'original-invocation-journal.json',call(['journalctl','--user','--no-pager','-o','json','_SYSTEMD_INVOCATION_ID='+INV]));write(J/'completed-gate.json',g);write(J/'managed-save-completed.json',json.loads(completed.read_text()));write(J/'candidate-fingerprint.json',model);write(J/'gate-fingerprint.json',gatefp)
fd=os.open(J,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
again,after=show();assert after.get('InvocationID')==INV and after.get('SubState')=='exited' and after.get('MainPID')=='0' and after.get('ExecMainPID')=='3593422' and after.get('ExecMainCode')=='1' and after.get('ExecMainStatus')=='0'
write(J/'pre-release-recheck.json',again);write(J/'owned-unit-release.json',call(['systemctl','--user','stop',U]));post,props=show();write(J/'post-release-show.json',post);assert props.get('LoadState')=='not-found'
assert fingerprint(candidate)==model and fingerprint(gate)==gatefp and not request.exists()
receipt={'schema':'robotron-original384-gate-terminal-closure-v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_unit':U,'original_invocation_id':INV,'original_ExecMainPID':3593422,'original_ExecMainCode':1,'original_ExecMainStatus':0,'original_exit_archived_before_release':True,'owned_unit_released':True,'target_learner_frames':388629023,'original_deadline_unix_s':1792220146.61131,'candidate':model,'gate':gatefp,'trigger_snapshot':g['trigger_snapshot'],'scope':'Original successful save/waiter terminal and immutable file identity only; saved model CPU verification/quality still pending'}
write(J/'receipt.json',receipt);print(json.dumps({'receipt':str(J/'receipt.json'),'receipt_sha256':sha(J/'receipt.json'),'candidate':model,'gate':gatefp},indent=2))
