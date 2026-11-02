"""Root-owned bounded one-shot384 verifier controller. Default is read-free PLAN."""
import argparse,datetime,hashlib,json,os,pathlib,shutil,subprocess,sys,time
ROOT=pathlib.Path('/home/dave/source/repos/ArcadeAI');RUN=ROOT/'Robotron/logs/managed-learning-20261015/run-26';D=RUN/'quality384M-checkpoint-verification-preparation-20261017';V=D/'verify_saved_checkpoint.py';J=RUN/'quality384M-checkpoint-verification-execution-reviewed1-20261017';U='robotron-verify384-checkpoint-cpu-reviewed1-20261017.service';V_SHA='527f2b9928bae9d58f7d8cd9984dfa126aa32f671af3e48935087870a1c9edd9'
def digest(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 p.chmod(0o444)
def call(a):
 q=subprocess.run(a,text=True,capture_output=True);return {'argv':a,'returncode':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
def props():
 q=call(['systemctl','--user','show',U]);return q,dict(line.split('=',1) for line in q['stdout'].splitlines() if '=' in line)
def main():
 if '--execute' not in sys.argv[1:]:
  print('PLAN ONLY: after actual384 gate completion/original-exit archival and release, execute unchanged527 verifier once with actualcandidate SHA/bytes/gate SHA; CPU2/3GiB/128tasks/120s/1GiB observed artifacts, CUDA hidden; preserve original exit before unit release.');return 0
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--checkpoint-sha256',required=True);p.add_argument('--checkpoint-bytes',type=int,required=True);p.add_argument('--gate-sha256',required=True);p.add_argument('--gate-closure',type=pathlib.Path,required=True);p.add_argument('--gate-closure-sha256',required=True);a=p.parse_args()
 assert digest(V)==V_SHA and a.gate_closure.is_absolute() and digest(a.gate_closure)==a.gate_closure_sha256
 proof=json.loads(a.gate_closure.read_text());assert proof['original_unit']=='robotron-checkpoint-384M-run26-rearmed-post-warmup-aa-reviewed1-20261017.service' and proof['original_invocation_id']=='2eca9cff5b5a4bc4a873f532507ea9c6' and proof['original_ExecMainPID']==3593422 and proof['original_ExecMainCode']==1 and proof['original_ExecMainStatus']==0 and proof['original_exit_archived_before_release'] is True and proof['owned_unit_released'] is True
 assert not (ROOT/'Robotron/models_dqn/managed_save.request.json').exists()
 candidate=ROOT/'Robotron/models_dqn/managed-checkpoints/fresh3-384M.pt';gate=RUN/'fresh3-384M-gate.json'
 assert candidate.stat().st_size==a.checkpoint_bytes and digest(candidate)==a.checkpoint_sha256 and digest(gate)==a.gate_sha256
 for name in ['cpu-verification.json','verification-error.json','verification-copy.pt','private-source','private-runtime']:assert not (D/name).exists(),name
 _,pr=props();assert pr.get('LoadState')=='not-found';J.mkdir();(J/'private-tmp').mkdir();shutil.copyfile(__file__,J/'root-controller-source.py');shutil.copyfile(V,J/'verifier-source.py')
 argv=[str(ROOT/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(V),'--execute','--expected-checkpoint',str(candidate),'--expected-sha256',a.checkpoint_sha256,'--expected-bytes',str(a.checkpoint_bytes),'--expected-target','388629023','--expected-tag','fresh3-384M','--expected-gate-sha256',a.gate_sha256]
 launch=['systemd-run','--user','--unit='+U,'--property=WorkingDirectory='+str(ROOT),'--property=Restart=no','--property=RemainAfterExit=yes','--property=CollectMode=inactive','--property=MemoryMax=3G','--property=MemorySwapMax=0','--property=CPUQuota=200%','--property=TasksMax=128','--property=RuntimeMaxSec=120s','--property=TimeoutStopSec=5s','--property=StandardOutput=append:'+str(J/'stdout'),'--property=StandardError=append:'+str(J/'stderr'),'/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','NUMEXPR_NUM_THREADS=2','TMPDIR='+str(J/'private-tmp'),*argv]
 write(J/'execution-precommit.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),unit=U,launch_argv=launch,verifier_argv=argv,verifier_sha256=V_SHA,root_controller_sha256=digest(__file__),gate_closure=str(a.gate_closure),gate_closure_sha256=a.gate_closure_sha256,actual_checkpoint_sha256=a.checkpoint_sha256,actual_checkpoint_bytes=a.checkpoint_bytes,actual_gate_sha256=a.gate_sha256,limits=dict(memory_bytes=3*2**30,CPU_percent=200,tasks=128,runtime_s=120,observed_artifact_limit_bytes=2**30),scope='One-shot static saved384 CPU verification, no learner restore/forward/backward/optimizer/replay/CUDA/quality claim'))
 q=call(launch);write(J/'launch-result.json',q);assert q['returncode']==0,q
 start=time.monotonic();inv=None;peak=0;resource_abort=None
 while True:
  raw,pr=props()
  if inv is None and pr.get('InvocationID'):
   inv=pr['InvocationID'];write(J/'original-owner.json',{'invocation_id':inv,'MainPID':pr.get('MainPID'),'ExecMainPID':pr.get('ExecMainPID'),'start_monotonic':pr.get('ExecMainStartTimestampMonotonic')})
  if inv:assert pr.get('InvocationID')==inv
  size=sum(f.stat().st_size for directory in (D,J) for f in directory.rglob('*') if f.is_file());peak=max(peak,size)
  if size>2**30 and resource_abort is None:
   resource_abort='Observed artifact bytes exceeded1GiB';write(J/'resource-abort.json',dict(reason=resource_abort,bytes=size,invocation=inv));write(J/'owned-abort-signal.json',call(['systemctl','--user','kill','--kill-whom=all','--signal=SIGTERM',U]))
  if pr.get('SubState') in ('exited','failed','dead') and pr.get('ExecMainPID') not in (None,'0'):break
  assert time.monotonic()-start<125,'Retain owned unit and investigate; controller observation exceeded125s'
  time.sleep(.25)
 write(J/'original-terminal-show.json',raw);write(J/'original-unit-cat.json',call(['systemctl','--user','cat',U]));write(J/'original-invocation-journal.json',call(['journalctl','--user','--no-pager','-o','json','_SYSTEMD_INVOCATION_ID='+inv]));assert digest(V)==V_SHA and digest(candidate)==a.checkpoint_sha256 and digest(gate)==a.gate_sha256
 passed=resource_abort is None and pr.get('ExecMainCode')=='1' and pr.get('ExecMainStatus')=='0' and (D/'cpu-verification.json').exists()
 if passed:
  verified=json.loads((D/'cpu-verification.json').read_text());passed=verified['status']=='PASS' and verified['script_sha256']==V_SHA and verified['sha256']==a.checkpoint_sha256 and not verified['cuda_initialized'] and verified['visible_cuda_devices']==0
 write(J/'execution-completion.json',dict(status='PASS' if passed else 'FAIL',original_ExecMainCode=pr.get('ExecMainCode'),original_ExecMainStatus=pr.get('ExecMainStatus'),invocation_id=inv,memory_peak_bytes=pr.get('MemoryPeak'),observed_disk_peak_bytes=peak,elapsed_s=time.monotonic()-start,resource_abort=resource_abort,original_exit_archived_before_release=True,source_unchanged=True))
 if not passed:
  print(json.dumps(dict(status='FAIL',unit=U,invocation=inv,output=str(J),unit_retained_for_review=True)));return 1
 write(J/'owned-unit-release.json',call(['systemctl','--user','stop',U]));_,after=props();assert after.get('LoadState')=='not-found'
 result=dict(status='PASS_SAVED384_STATIC_CPU_VERIFICATION',unit=U,invocation_id=inv,original_exit=0,original_exit_archived_before_release=True,owned_unit_released=True,checkpoint_sha256=a.checkpoint_sha256,gate_sha256=a.gate_sha256,cpu_verification=str(D/'cpu-verification.json'),cpu_verification_sha256=digest(D/'cpu-verification.json'),execution_completion_sha256=digest(J/'execution-completion.json'),scope='Static checkpoint finite/strictmodel/Adam/scaler/clocks only; no coherent replay anchor/restore or quality qualification')
 write(J/'root-result-review-and-release.json',result);print(json.dumps(result));return 0
if __name__=='__main__':raise SystemExit(main())
