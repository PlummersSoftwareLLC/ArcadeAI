"""One controller process, one scheduling attempt, same-process observation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

D=Path(__file__).resolve().parent
B=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal')
spec=importlib.util.spec_from_file_location('_original_tail_launcher_helpers',B/'run_full_policy_startup_v3.py')
h=importlib.util.module_from_spec(spec);sys.modules[spec.name]=h;spec.loader.exec_module(h)
assert h.pin(B/'run_full_policy_startup_v3.py')['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
cfg=h.pin(D/'quality-pair-scope-controller-config.json')
assert cfg['sha256']=='5894ce6d0bb2d4416efe5305bee49ffab01168f2fa624ecc4d7afeecaf634a5e'
source=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py'))
assert source['sha256']=='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
commit=h.pin(D/'original-five-quality-pair-scope-precommit.json')
assert commit['sha256']=='28ae9cf16e1e349e4ade4c3c7890bc1e8b10d63e6acbb435d4b7ab527e48564a'
assert not (D/'controller-original-launch.json').exists()
argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--config',cfg['path'],
      '--expected-source-sha256',source['sha256']]
intent=h.put(D/'controller-original-launch.json',dict(source=h.pin(__file__),config=cfg,
    controller_source=source,case_precommit=commit,argv=argv,original_attempt=1,no_retry=True,unix_s=time.time()))
with (D/'controller-original-stdout.txt').open('xb')as stdout,(D/'controller-original-stderr.txt').open('xb')as stderr:
    process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
    stat=Path('/proc',str(process.pid),'stat').read_text()
    child=h.put(D/'controller-original-child.json',dict(pid=process.pid,
        starttime_ticks=int(stat.rsplit(')',1)[1].split()[19]),observed_live=process.poll()is None,intent=intent))
    print(json.dumps(dict(controller=child)),flush=True)
    code=process.wait()
    stdout.flush();stderr.flush();os.fsync(stdout.fileno());os.fsync(stderr.fileno())
    os.fchmod(stdout.fileno(),0o444);os.fchmod(stderr.fileno(),0o444)
closure=D/'quality-pair-scope-execution-original01/root-original-result-and-owned-release.json'
result=h.put(D/'controller-original-result.json',dict(actual_exit=code,original_attempt=1,no_retry=True,
    intent=intent,stdout=h.pin(D/'controller-original-stdout.txt'),stderr=h.pin(D/'controller-original-stderr.txt'),
    closure=h.pin(closure)if closure.exists()else None,ended_unix_s=time.time()))
print(json.dumps(dict(actual_exit=code,result=result)),flush=True)
sys.exit(code)
