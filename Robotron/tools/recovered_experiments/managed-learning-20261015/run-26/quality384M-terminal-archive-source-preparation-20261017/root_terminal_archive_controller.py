"""Archive the exact original quality controller terminal; never stop/release/publish. Default PLAN reads nothing."""
import pathlib,json,hashlib,os,stat,subprocess,datetime,sys
ROOT=pathlib.Path('/home/dave/source/repos/ArcadeAI');BASE=ROOT/'Robotron/logs/managed-learning-20261015';RUN=BASE/'run-26';Q=BASE/'quality-256M-vs-384M-20261017';J=RUN/'quality384M-original-controller-terminal-root-archive-20261017';U='robotron-quality-256M-vs-384M-20261017.service';INV='611d7a54ae7e4a649b0e1ed3505a7baa'
def call(a):
 z=subprocess.run(a,capture_output=True,text=True,timeout=30);return {'argv':a,'returncode':z.returncode,'stdout':z.stdout,'stderr':z.stderr}
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def stable(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def read(p):
 before=p.lstat();assert stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
 with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  assert stable(os.fstat(f.fileno()))==stable(before);b=f.read();assert stable(os.fstat(f.fileno()))==stable(before)
 assert stable(p.lstat())==stable(before);return b,{'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'device':before.st_dev,'inode':before.st_ino,'mode':oct(stat.S_IMODE(before.st_mode)),'mtime_ns':before.st_mtime_ns,'ctime_ns':before.st_ctime_ns}
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 p.chmod(0o444)
def copy(p,dst):
 b,fp=read(p)
 with dst.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 dst.chmod(0o444);return fp
def main():
 if '--execute' not in sys.argv[1:]:print('PLAN ONLY: after original611d quality controller terminal, archive exact show/cat/invocation journal, source and original plan/status/summary/console before any unit release. No release, publication, or runtime change.');return
 assert sys.argv[1:]==['--execute']
 raw=call(['systemctl','--user','show',U]);p=dict(x.split('=',1) for x in raw['stdout'].splitlines() if '=' in x);assert raw['returncode']==0 and p.get('InvocationID')==INV and p.get('ExecMainPID')=='3723673'
 if p.get('SubState')=='running':print('WAIT: exact original611d controller still running; no archive files created');return
 assert p.get('MainPID')=='0' and p.get('SubState') in ['exited','failed','dead'],p
 plan=json.loads((Q/'plan.json').read_text());assert sha(Q/'plan.json')=='81210cb86ad7cd78b3f9a7f4c764b83aad3364d0d8f0e382e29f340245a54704';assert not (ROOT/'Robotron/models_dqn/managed_save.request.json').exists()
 bound=RUN/'quality384M-actual-default-plan-prelaunch-20261017/root-default-plan-source-archive-review.json';assert sha(bound)=='27f39b2483a3c7c4e7362e6d600ff73464043b480248684db55b30c66cc51b6a'
 for path,spec in json.loads(bound.read_text())['source_entries'].items():assert sha(path)==spec['sha256'] and sha(spec['copy'])==spec['sha256']
 cat=call(['systemctl','--user','cat',U]);journal=call(['journalctl','--user','--no-pager','-o','json','_SYSTEMD_INVOCATION_ID='+INV]);assert cat['returncode']==journal['returncode']==0
 initial=RUN/'quality384M-actual-durable-launch-reviewed1-20261017/original-unit-cat.json';assert cat['stdout']==json.loads(initial.read_text())['stdout'],'Owned unit bytes changed'
 J.mkdir();write(J/'original-terminal-show.json',raw);write(J/'original-unit-cat.json',cat);write(J/'original-invocation-journal.json',journal);artifacts={}
 for src,name in [(pathlib.Path(__file__),'root-terminal-archive-controller.py'),(Q/'plan.json','campaign-plan.json'),(Q/'status.json','original-terminal-campaign-status.json'),(Q/'summary.json','original-terminal-campaign-summary.json'),(RUN/'quality384M-actual-durable-launch-reviewed1-20261017/console.log','original-controller-console.log'),(bound,'prelaunch-source-archive-review.json'),(initial,'original-start-unit-cat.json')]:artifacts[name]=copy(src,J/name)
 for index in range(1,5):
  role='reference' if index%2 else 'candidate';src=Q/f'{index:02d}-{role}'/'receipt.json'
  if src.exists():artifacts[f'leg{index}-original-receipt.json']=copy(src,J/f'leg{index}-original-receipt.json')
 after=call(['systemctl','--user','show',U]);a=dict(x.split('=',1) for x in after['stdout'].splitlines() if '=' in x);assert all(a.get(k)==p.get(k) for k in ['InvocationID','MainPID','ExecMainPID','ExecMainCode','ExecMainStatus','SubState']);write(J/'original-terminal-recheck-show.json',after)
 receipt={'schema':'robotron-original384-quality-controller-terminal-archive-v1','status':'ORIGINAL_TERMINAL_ARCHIVED_UNIT_RETAINED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unit':U,'original_invocation_id':INV,'original_ExecMainPID':3723673,'original_start_ticks':'30468106','original_ExecMainCode':p.get('ExecMainCode'),'original_ExecMainStatus':p.get('ExecMainStatus'),'original_Result':p.get('Result'),'original_SubState':p.get('SubState'),'original_terminal_exit_archived_before_release':True,'owned_unit_released':False,'promotion_performed':False,'source_freeze_still_held':True,'artifacts':artifacts,'scope':'Exact original terminal evidence only. Does not imply successful campaign/cleanup/quality qualification or authorize publication without completed original-row audits and strict protection default review.'}
 write(J/'archive-receipt.json',receipt);fd=os.open(J,os.O_DIRECTORY);os.fsync(fd);os.close(fd);print(json.dumps({'receipt':str(J/'archive-receipt.json'),'sha256':sha(J/'archive-receipt.json'),'original_ExecMainCode':p.get('ExecMainCode'),'original_ExecMainStatus':p.get('ExecMainStatus'),'unit_retained':True}))
if __name__=='__main__':main()
