"""Own exactly one original two-arm screen process until its actual exit."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CASE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:
        parser.print_help();return 0
    hp=G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(hp.read_bytes()).hexdigest()=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    spec=importlib.util.spec_from_file_location('_launch_helper',hp)
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    preflight=json.loads((CASE/'positive-preflight.json').read_text())
    assert preflight['status']=='PASS' and 0<=time.time()-preflight['observed_unix_s']<600
    prepared=h.pin(CASE/'prepared-with-review.json');data=json.loads(h.checked(prepared).read_text())
    source=data['selected_sources']['outer'];controller=data['selected_sources']['controller']
    configs=data['controller_configs']
    for entry in (source,controller,configs,data['selection']):h.checked(entry)
    argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute',
        '--source-sha256',source['sha256'],'--prepared',prepared['path'],
        '--prepared-sha256',prepared['sha256'],'--controller',controller['path'],
        '--controller-sha256',controller['sha256'],'--configs',configs['path'],
        '--configs-sha256',configs['sha256'],'--control',str(G/'html/next-policy-evaluation.json'),
        '--output',str(CASE/'Root-controller-runtime-original01')]
    h.put(CASE/'original-sequence-launch-intent.json',dict(argv=argv,
        source=h.pin(Path(__file__)),preflight=h.pin(CASE/'positive-preflight.json'),
        original_attempt=1,no_retry=True,observed_unix_s=time.time()))
    with (CASE/'original-sequence-stdout.txt').open('xb') as stdout,(CASE/'original-sequence-stderr.txt').open('xb') as stderr:
        child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
        birth=int(Path('/proc',str(child.pid),'stat').read_text().rsplit(')',1)[1].split()[19])
        h.put(CASE/'original-sequence-child.json',dict(pid=child.pid,birth=birth,
            argv=argv,observed_unix_s=time.time(),parent_pid=os.getpid()))
        print(json.dumps(dict(original_sequence_pid=child.pid,birth=birth,case=str(CASE))),flush=True)
        code=child.wait()
        for stream in (stdout,stderr):
            stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    h.put(CASE/'original-sequence-actual-exit.json',dict(actual_exit=code,
        original_pid=child.pid,original_birth=birth,original_Popen_reaped=True,
        stdout=h.pin(CASE/'original-sequence-stdout.txt'),stderr=h.pin(CASE/'original-sequence-stderr.txt'),
        ended_unix_s=time.time(),no_retry=True))
    print(json.dumps(dict(original_sequence_actual_exit=code)),flush=True)
    return code


if __name__=='__main__':
    raise SystemExit(main())
