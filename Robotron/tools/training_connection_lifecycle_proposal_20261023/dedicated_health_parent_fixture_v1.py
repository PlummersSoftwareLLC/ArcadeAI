"""Owned inert parent-lifecycle fixture; no training, sockets, GPU or model access."""
import argparse,hashlib,importlib.util,json,os,time
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
 if not a.execute:print('PLAN_ONLY');return 0
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
 raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;j=json.loads(raw)
 pin=j['helpers'];assert hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest()==pin['sha256']
 sp=importlib.util.spec_from_file_location('_holder_h',pin['path']);h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
 root=Path(j['output']);root.mkdir(mode=0o700);start=time.monotonic()
 h.put(root/'ready.json',dict(pid=os.getpid(),birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),invocation_id=os.environ['INVOCATION_ID']))
 while time.monotonic()-start<120:
  if (root/'finish-request.json').exists():
   request=json.loads((root/'finish-request.json').read_text());assert request=={'action':'normal_fixture_exit','job_sha256':a.job_sha256}
   h.put(root/'normal-exit.json',dict(reason='PRECOMMITTED_PARENT_EXIT_FIXTURE',monotonic_s=time.monotonic(),unix_s=time.time()));return 0
  time.sleep(.02)
 raise ValueError('Original parent fixture deadline; no restart')
if __name__=='__main__':raise SystemExit(main())
