from pathlib import Path
import importlib.util,json,os,sys,hashlib
SOURCE='/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/review_original_pilot_reviewed2.py'
JOB='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/future-capacity32-runtime-pilot-preparation-20261019/independent-original-review-job.json'
assert hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest()=='e975e09f50e052e80dd763b4aa506b61d2c487b63dfd1148bbd6a1bd97e9602e'
assert hashlib.sha256(Path(JOB).read_bytes()).hexdigest()=='39fea32eeecb0fb2c8245d7d9f250758cb3128ed62539e7722705b695d2c188c'
s=importlib.util.spec_from_file_location('_actual_capreview_guard',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
reader=m.protector();job_pin=reader.pin(JOB);job=reader.read_pin(job_pin)
def inventory():
 result={}
 for path in sorted(Path('/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/managed-incumbents').iterdir()):
  v=path.lstat();result[str(path)]=dict(device=v.st_dev,inode=v.st_ino,mode=v.st_mode,uid=v.st_uid,nlink=v.st_nlink,bytes=v.st_size,mtime_ns=v.st_mtime_ns,ctime_ns=v.st_ctime_ns)
 return result
before=inventory();assert not Path(job['output']).exists()
try:m.review(job,job_pin,reader)
except FileNotFoundError as error:
 assert error.filename==job['closed_context_path'],repr(error)
 rejection=dict(type=type(error).__name__,filename=error.filename,message=str(error))
else:raise AssertionError('Unlaunched pilot unexpectedly reviewed')
assert not Path(job['output']).exists();after=inventory();assert before==after
assert 'torch' not in sys.modules
result=dict(status='PASS_UNLAUNCHED_PILOT_REJECTED_BEFORE_RUNTIME_QUERIES_OR_OUTPUT',expected_rejection=rejection,protected_file_count=len(before),protected_file_identities_unchanged=True,review_output_created=False,protected_inventory_before=before,protected_inventory_after=after,Torch_imported=False,GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,source=reader.pin(SOURCE),job=job_pin)
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original03-preparation-20261019/actual-not-ready-original01/result.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
print(json.dumps({key:result[key] for key in ('status','expected_rejection','protected_file_count','protected_file_identities_unchanged','review_output_created')}))
