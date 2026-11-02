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
cfg=h.pin(D/'controller-config.json')
assert cfg['sha256']=='cfc388685001804057eb2cea7e45e6c3ab571446a73cdc66ab177c28d3e68c3a'
source=h.pin(B/'control_compiled_full_tail32_quality_v1.py')
assert source['sha256']=='4842730c93c42d7cf05c108d61c5eb644f650bd870511887c38773ede8234889'
commit=h.pin(D/'original-leg-precommit.json')
assert commit['sha256']=='409f81e5ada9e0ef198b0e7e1ae76f8c2a25c0d2cb0efe97cccf0056a6221909'
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
closure=D/'execution-original01/root-original-result-and-owned-release.json'
result=h.put(D/'controller-original-result.json',dict(actual_exit=code,original_attempt=1,no_retry=True,
    intent=intent,stdout=h.pin(D/'controller-original-stdout.txt'),stderr=h.pin(D/'controller-original-stderr.txt'),
    closure=h.pin(closure)if closure.exists()else None,ended_unix_s=time.time()))
print(json.dumps(dict(actual_exit=code,result=result)),flush=True)
sys.exit(code)
