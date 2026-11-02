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
assert cfg['sha256']=='21d752ff1f3440d30bc1c1bf2f7f26f47479b021df7572a3ec4cd548ea6b63b0'
source=h.pin(B/'control_compiled_full_tail32_v2.py')
assert source['sha256']=='6c82de8169446395c35485596e3d0648be31e0000ef9e940341ece3c36a8a67e'
commit=h.pin(D/'original-cleanup-v2-case-precommit.json')
assert commit['sha256']=='7d803608d72affd6878098fbdb53a2565c8363f6c62dd0c6bb038d271cbe6451'
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
