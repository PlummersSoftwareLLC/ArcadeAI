import argparse,ast,datetime,hashlib,json,os,pathlib,resource,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--source-dir',type=pathlib.Path,required=True);p.add_argument('--manifest',required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();assert a.source_dir.is_absolute() and a.output.is_absolute()
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 p.chmod(0o444)
def limits():
 for key,value in ((resource.RLIMIT_AS,512*1024**2),(resource.RLIMIT_CPU,10),(resource.RLIMIT_FSIZE,8*1024**2),(resource.RLIMIT_CORE,0)):resource.setrlimit(key,(value,value))
manifest=a.source_dir/a.manifest;assert sha(manifest)==a.manifest_sha256;m=json.loads(manifest.read_text());files=m.get('files',m.get('artifacts'));assert isinstance(files,dict)
def verify():
 for n,v in files.items():
  source=a.source_dir/n;assert source.is_file() and sha(source)==v['sha256'] and source.stat().st_size==v['bytes'],n;assert not source.stat().st_mode&0o222,n
verify();assert not a.output.exists();a.output.mkdir(mode=0o700);(a.output/'private-tmp').mkdir();(a.output/'source').mkdir();(a.output/'root-controller-source.py').write_bytes(pathlib.Path(__file__).read_bytes())
for n in [*files,a.manifest]:
 q=a.output/'source'/n.replace('/','_');q.write_bytes((a.source_dir/n).read_bytes());q.chmod(0o444)
env=dict(os.environ)
for n in list(env):
 if n.startswith(('DQN_','ROBOTRON_')) or n in ('LD_PRELOAD','PYTHONPATH','PYTHONSTARTUP'):env.pop(n,None)
env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(a.output/'private-tmp'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
select="import importlib,sys,unittest; sys.path.insert(0,sys.argv[1]); m=importlib.import_module(sys.argv[2]); s=unittest.defaultTestLoader.loadTestsFromModule(m); assert s.countTestCases()==int(sys.argv[3]); r=unittest.TextTestRunner(verbosity=2).run(s); assert not any(n=='torch' or n.startswith('torch.') or n=='numpy' or n.startswith('numpy.') for n in sys.modules); sys.exit(0 if r.wasSuccessful() and not r.skipped else 1)"
commands=[]
for name,count in [('test_process_scan',18),('test_storage_watcher',25),('test_rehearsal_contract',9)]:
 source=a.source_dir/(name+'.py');assert source.name in files;assert sum(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(ast.parse(source.read_text())))==count
 commands.append([sys.executable,'-I','-B','-c',select,str(a.source_dir.parent),a.source_dir.name+'.'+name,str(count)])
write(a.output/'execution-precommit.json',dict(schema='robotron-rehearsal-private-stdlib52-precommit-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=commands,manifest=str(manifest),manifest_sha256=a.manifest_sha256,source_pins=files,root_controller_sha256=sha(__file__),limits=dict(memory_address_bytes=512*1024**2,cpu_seconds=10,child_timeout_s=20,file_bytes=8*1024**2,observed_private_disk_bound_bytes=32*1024**2),CUDA_VISIBLE_DEVICES='',checkpoint_wait_stays_active=True,tests=dict(process_scan=18,storage=25,rehearsal_contract=9),scope='Stdlib mock/source guard tests only; no numerical framework/model/checkpoint/GPU/live workload'))
results=[];failed=False;started=time.monotonic();peak=0
for index,argv in enumerate(commands):
 before=time.monotonic();error=None;q=None
 try:
  with (a.output/(str(index)+'.stdout')).open('xb') as out,(a.output/(str(index)+'.stderr')).open('xb') as err:q=subprocess.run(argv,env=env,cwd=a.source_dir,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=20,preexec_fn=limits)
 except Exception as e:error=repr(e)
 result=dict(index=index,argv=argv,returncode=None if q is None else q.returncode,child_reaped=q is not None,error=error,elapsed_s=time.monotonic()-before,stdout_sha256=sha(a.output/(str(index)+'.stdout')),stderr_sha256=sha(a.output/(str(index)+'.stderr')));write(a.output/(str(index)+'.completion.json'),result);results.append(result)
 peak=max(peak,sum(x.stat().st_size for x in a.output.rglob('*') if x.is_file()));assert peak<=32*1024**2
 if result['returncode']!=0 or error:failed=True;break
verify();write(a.output/'execution-completion.json',dict(schema='robotron-rehearsal-private-stdlib52-completion-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='FAIL' if failed else 'PASS',original_child_results=results,source_unchanged=True,elapsed_s=time.monotonic()-started,observed_disk_peak_bytes=peak,tests_passed=52 if not failed else None,qualification_pass=False,GPU_execution=False,production_applied=False));print(json.dumps(dict(status='FAIL' if failed else 'PASS',output=str(a.output),completion_sha256=sha(a.output/'execution-completion.json'),children=[r['returncode'] for r in results],elapsed_s=time.monotonic()-started)));sys.exit(1 if failed else 0)
