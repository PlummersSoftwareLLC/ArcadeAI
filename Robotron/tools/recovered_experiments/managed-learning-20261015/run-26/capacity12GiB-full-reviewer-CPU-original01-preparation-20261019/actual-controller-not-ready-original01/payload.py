from pathlib import Path
import importlib.util,json,os,sys,hashlib
SOURCE='/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/control_original_pilot.py'
CONFIG='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/future-capacity32-runtime-pilot-preparation-20261019/original-pilot-controller-config-reviewed2.json'
SOURCE_SHA='db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9'
CONFIG_SHA='d8612d7905e3f8d70240069f8dc8e94083e2e486ad6d013eedf106dd651a5b6a'
assert hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest()==SOURCE_SHA
assert hashlib.sha256(Path(CONFIG).read_bytes()).hexdigest()==CONFIG_SHA
s=importlib.util.spec_from_file_location('_actual_pilot_controller_guard',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def inventory():
 result={}
 for path in sorted(Path('/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/managed-incumbents').iterdir()):
  v=path.lstat();result[str(path)]=dict(device=v.st_dev,inode=v.st_ino,mode=v.st_mode,uid=v.st_uid,nlink=v.st_nlink,bytes=v.st_size,mtime_ns=v.st_mtime_ns,ctime_ns=v.st_ctime_ns)
 return result
absent=['/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/future-capacity32-runtime-pilot-preparation-20261019/pilot-root-execution', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/future-capacity32-runtime-pilot-preparation-20261019/runtime-bindings', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/future-capacity32-runtime-pilot-preparation-20261019/independent-original32-pilot-review', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/capacity32-protected845-runtime-original01-20261019']
assert all(not Path(path).exists() for path in absent)
expected='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/native-terminal-archive/root-original-result-and-owned-release.json'
assert not Path(expected).exists()
before=inventory()
blocked_events=[]
def no_runtime_queries(event,args):
 if event in ('subprocess.Popen','os.system','os.posix_spawn','socket.connect'):
  blocked_events.append(event);raise AssertionError('No runtime query before current quality closure: '+event)
sys.addaudithook(no_runtime_queries)
try:m.main(['--execute','--config',CONFIG,'--config-sha256',CONFIG_SHA,'--source-sha256',SOURCE_SHA])
except FileNotFoundError as error:
 assert error.filename==expected,repr(error)
 rejection=dict(type=type(error).__name__,filename=error.filename,message=str(error))
else:raise AssertionError('Still-live quality unexpectedly allowed a pilot launch')
config=json.loads(Path(CONFIG).read_bytes())
spec=importlib.util.spec_from_file_location('_static12_controller_guard',config['guard_source']['path']);gmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(gmod)
reader=gmod.reader_module();job=reader.read_pin(config['pilot_controller_job']);selected=reader.read_pin(job['reviewer_selection']);review_job=reader.read_pin(selected['job']);plan=reader.read_pin(review_job['pilot_plan'])
g=gmod.MainGuard(config,dict(reader=reader,job=job,plan=plan,review_job=review_job));g.validate_config(config)
assert config['properties'].count('MemoryMax=12G')==1
for value in ('8G','16G'):
 changed=json.loads(json.dumps(config));changed['properties']=[p.replace('MemoryMax=12G','MemoryMax='+value) for p in changed['properties']]
 try:g.validate_config(changed)
 except ValueError:pass
 else:raise AssertionError('A different resource limit passed exact config validation')
assert not blocked_events
assert 'torch' not in sys.modules and not m._LAUNCHES and m._GUARD is None
after=inventory();assert before==after
assert all(not Path(path).exists() for path in absent)
assert 'torch' not in sys.modules and not m._LAUNCHES and m._GUARD is None
result=dict(status='PASS_CURRENT_QUALITY_PREVENTS_12GIB_PILOT_LAUNCH',static_exact12GiB_config_pass=True,static8GiB_and16GiB_configs_rejected=True,runtime_query_events=blocked_events,expected_rejection=rejection,protected_file_count=len(before),protected_file_identities_unchanged=True,protected_inventory_before=before,protected_inventory_after=after,future_runtime_directories_created=False,scheduling_attempts=0,Torch_imported=False,GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,source=m.pin(SOURCE),config=m.pin(CONFIG))
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity12GiB-full-reviewer-CPU-original01-preparation-20261019/actual-controller-not-ready-original01/result.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
print(json.dumps({key:result[key] for key in ('status','expected_rejection','protected_file_count','protected_file_identities_unchanged','scheduling_attempts')}))
