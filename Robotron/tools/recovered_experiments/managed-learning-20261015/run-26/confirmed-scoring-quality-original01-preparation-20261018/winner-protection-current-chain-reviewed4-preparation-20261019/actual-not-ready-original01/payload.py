import importlib.util,json,os,sys
from pathlib import Path
from types import SimpleNamespace
SOURCE='/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
JOB='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/winner-protection-current-chain-reviewed4-preparation-20261019/protection-job.json'
REPORT='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/winner-protection-current-chain-reviewed4-preparation-20261019/actual-not-ready-original01/result.json'
s=importlib.util.spec_from_file_location('_actual_guard',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.configure(SimpleNamespace(source_sha256='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071',job=Path(JOB),job_sha256='f40c6c6d41f846fbab6238a545719453debd3e1cf2b7e9aaf0497dd6430a460c'))
def inventory():
 result={}
 for p in sorted(Path(m.CFG['destination']).iterdir()):
  s=p.lstat();result[str(p)]=dict(device=s.st_dev,inode=s.st_ino,mode=s.st_mode,uid=s.st_uid,gid=s.st_gid,nlink=s.st_nlink,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)
 return result
before=inventory()
try:m.review(m.CFG['campaign_directory'])
except FileNotFoundError as error:
 assert error.filename==m.CFG['native_closure_path'],repr(error)
 rejection=dict(type=type(error).__name__,filename=error.filename,message=str(error))
else:raise AssertionError('Live campaign unexpectedly qualified')
after=inventory();assert before==after
assert 'torch' not in sys.modules
result=dict(status='PASS_LIVE_CAMPAIGN_REJECTED_BEFORE_PUBLICATION',expected_rejection=rejection,protected_inventory_count=len(before),protected_inventory_before=before,protected_inventory_after=after,protected_file_identities_unchanged=True,Torch_imported=False,publish_called=False,quality_qualified=False,promotion=False,source=m.pin(SOURCE),job=m.JOB_PIN)
with Path(REPORT).open('x') as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
print(json.dumps({k:result[k] for k in ('status','expected_rejection','protected_inventory_count','protected_file_identities_unchanged','publish_called')}))
