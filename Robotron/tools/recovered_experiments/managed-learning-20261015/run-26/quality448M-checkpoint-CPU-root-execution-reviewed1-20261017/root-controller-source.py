#!/usr/bin/env python3
"""Root one-shot candidate CPU carrier; no reads or actions without an action."""
import argparse,datetime,hashlib,json,os,subprocess
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');RUN=R/'Robotron/logs/managed-learning-20261015/run-26'
SRC=RUN/'managed-candidate-checkpoint-CPU-verifier-proposal-20261017'
V=SRC/'verify_candidate_checkpoint.py';V_SHA='ea6ccfcd62e2683641475634ba1647856a988691a6cede3dbeda629dd03ba56b'
D=RUN/'quality448M-checkpoint-CPU-root-execution-reviewed1-20261017';U='robotron-verify448-checkpoint-cpu-reviewed1-20261017.service'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=15)
def show():
 q=call(['systemctl','--user','show',U]);return q,dict(x.split('=',1) for x in q.stdout.splitlines() if '=' in x)
def launch(a):
 assert a.job and a.job.is_absolute() and a.job_sha256 and sha(a.job)==a.job_sha256 and sha(V)==V_SHA
 job=json.loads(a.job.read_text());assert job['candidate']['tag']=='fresh3-448M' and job['candidate']['target_learner_frames']==452629023 and job['verifier_sha256']==V_SHA
 guards=json.loads((RUN/'managed-candidate-wrapper-tests-root-execution-reviewed1-20261017/root-result-review-and-release.json').read_text());assert guards['status']=='PASS' and guards['test_methods']==10 and guards['original_exit']==0
 assert show()[1]['LoadState']=='not-found' and not Path(job['output_directory']).exists()
 D.mkdir();(D/'private-tmp').mkdir()
 argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','MKL_NUM_THREADS=2','NUMEXPR_NUM_THREADS=2','TMPDIR='+str(D/'private-tmp'),str(R/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(V),'--execute','--job',str(a.job),'--expected-job-sha256',a.job_sha256,'--expected-verifier-sha256',V_SHA]
 command=['systemd-run','--user','--unit='+U]+['--property='+p for p in ['Type=exec','RemainAfterExit=yes','Restart=no','CPUQuota=200%','MemoryMax=3G','MemorySwapMax=0','TasksMax=128','RuntimeMaxSec=120','TimeoutStopSec=5','WorkingDirectory='+str(R),'StandardOutput=append:'+str(D/'stdout.txt'),'StandardError=append:'+str(D/'stderr.txt')]]+argv
 save(D/'root-launch-intent.json',dict(unit=U,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=command,job=str(a.job),job_sha256=a.job_sha256,verifier_sha256=V_SHA,output=job['output_directory'],source_sha256=sha(__file__),one_shot=True))
 with (D/'root-controller-source.py').open('xb') as f:f.write(Path(__file__).read_bytes());os.fchmod(f.fileno(),0o444)
 q=call(command);save(D/'root-launch-return.json',dict(returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));assert q.returncode==0,q.stderr
 _,v=show();pid=int(v['ExecMainPID']);assert pid>0 and v['InvocationID'] and v['NRestarts']=='0'
 live=v['MainPID']==str(pid);save(D/'root-original-owner.json',dict(pid=pid,invocation_id=v['InvocationID'],observed_live=live,start_ticks=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19] if live else None));print(json.dumps(dict(launched=True,pid=pid,invocation_id=v['InvocationID'])))
def archive(a):
 q,v=show();o=json.loads((D/'root-original-owner.json').read_text());intent=json.loads((D/'root-launch-intent.json').read_text());assert q.returncode==0 and v['MainPID']=='0' and v['SubState'] in ('exited','failed','dead') and v['ExecMainPID']==str(o['pid']) and v['InvocationID']==o['invocation_id'] and v['NRestarts']=='0'
 for name,t in [('original-unit-show.txt',q.stdout),('original-unit-cat.txt',call(['systemctl','--user','cat',U]).stdout),('original-invocation-journal.txt',call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+o['invocation_id'],'--no-pager','-o','short-precise']).stdout)]:
  with (D/name).open('x') as f:f.write(t);os.fchmod(f.fileno(),0o444)
 result=dict(unit=U,original_pid=o['pid'],original_invocation=o['invocation_id'],original_exec_code=int(v['ExecMainCode']),original_exit=int(v['ExecMainStatus']),original_result=v['Result'],memory_peak=v.get('MemoryPeak'),job_sha256=intent['job_sha256'],original_terminal_archived_before_release=True)
 save(D/'root-original-terminal-archive.json',result)
 passed=result['original_exec_code']==1 and result['original_exit']==0 and result['original_result']=='success'
 if passed:
  p=Path(intent['output'])/'cpu-verification.json';r=json.loads(p.read_text());j=json.loads(Path(intent['job']).read_text());assert sha(Path(intent['job']))==intent['job_sha256'] and sha(V)==V_SHA
  assert r['status']=='PASS' and r['sha256']==j['source']['sha256'] and r['bytes']==j['source']['bytes'] and r['actual_restore_or_optimizer_step'] is False and r['actual_quality_qualification'] is False
  result.update(status='PASS',cpu_verification=str(p),cpu_verification_sha256=sha(p))
 else:result.update(status='FAILED',terminal_unit_retained_for_review=True)
 if passed:
  q=call(['systemctl','--user','stop',U]);assert q.returncode==0,q.stderr;assert show()[1]['LoadState']=='not-found';result['owned_unit_released']=True
 save(D/'root-result-review-and-release.json',result);print(json.dumps(result))
def main():
 p=argparse.ArgumentParser();p.add_argument('action',nargs='?',choices=['launch','archive']);p.add_argument('--job',type=Path);p.add_argument('--job-sha256');a=p.parse_args()
 if not a.action:print('PLAN_ONLY: actual448 immutable job/source/terminal evidence required; no reads or actions');return
 globals()[a.action](a)
if __name__=='__main__':main()
