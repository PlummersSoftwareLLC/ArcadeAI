import argparse, datetime, hashlib, json, os, pathlib, resource, subprocess, sys, time

def digest(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def publish(p, obj):
    data=(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    with pathlib.Path(p).open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    pathlib.Path(p).chmod(0o444)

def child_limits():
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(10,10))
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024**2,8*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))

p=argparse.ArgumentParser();p.add_argument('--source-dir',type=pathlib.Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--manifest-name',required=True);p.add_argument('--test-name',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
assert a.source_dir.is_absolute() and a.output.is_absolute()
manifest=a.source_dir/a.manifest_name
assert digest(manifest)==a.manifest_sha256
m=json.loads(manifest.read_text()); pins=m.get('files',m.get('artifacts'));assert isinstance(pins,dict)
assert a.test_name in pins
for name,item in pins.items():
    source=a.source_dir/name
    assert source.is_file() and source.stat().st_size==item['bytes'] and digest(source)==item['sha256'],name
    assert not source.stat().st_mode&0o222,name
assert not a.output.exists();a.output.mkdir(mode=0o700)
(a.output/'runner-source.py').write_bytes(pathlib.Path(__file__).read_bytes());(a.output/'runner-source.py').chmod(0o444)
for name in [*pins,a.manifest_name]:
    target=a.output/('source-'+name.replace('/','_'));target.write_bytes((a.source_dir/name).read_bytes());target.chmod(0o444)
env=dict(os.environ)
for name in ('LD_PRELOAD','PYTHONPATH','PYTHONSTARTUP'):env.pop(name,None)
env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
argv=[sys.executable,'-I','-B',str(a.source_dir/a.test_name),'-v'];pre=dict(schema='robotron-bounded-stdlib-source-test-precommit-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=argv,manifest=str(manifest),manifest_sha256=a.manifest_sha256,source_pins=pins,runner_sha256=digest(__file__),limits=dict(address_space_bytes=512*1024**2,cpu_seconds=10,timeout_seconds=20,file_bytes=8*1024**2),CUDA_VISIBLE_DEVICES='',scope='Synthetic stdlib source guards only; no actual future campaign/model/game data or runtime mutation')
publish(a.output/'execution-precommit.json',pre)
start=time.monotonic();failure=None;result=None
try:
    with (a.output/'stdout').open('xb') as stdout,(a.output/'stderr').open('xb') as stderr:
        result=subprocess.run(argv,cwd=a.source_dir,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=20,preexec_fn=child_limits,check=False)
except Exception as e:
    failure=type(e).__name__+': '+str(e)
after={name:digest(a.source_dir/name) for name in pins};unchanged=all(after[n]==pins[n]['sha256'] for n in pins)
code=None if result is None else result.returncode
receipt=dict(schema='robotron-bounded-stdlib-source-test-completion-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),original_exit=code,child_reaped=result is not None,elapsed_s=time.monotonic()-start,failure=failure,source_unchanged=unchanged,after_sha256=after,stdout_sha256=digest(a.output/'stdout'),stderr_sha256=digest(a.output/'stderr'),qualification_pass=False,production_applied=False,status='PASS' if code==0 and unchanged and failure is None else 'FAIL')
publish(a.output/'execution-completion.json',receipt)
print(json.dumps(receipt,indent=2));sys.exit(0 if receipt['status']=='PASS' else 1)
