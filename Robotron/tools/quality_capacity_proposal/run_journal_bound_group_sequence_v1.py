"""Run each prospectively bound original CPU group once; stop on any failure."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CONTROLLER=G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
CONTROLLER_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True);a=p.parse_args()
    path=Path(a.plan);raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.plan_sha256
    plan=json.loads(raw)
    reader_path=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    assert hashlib.sha256(reader_path.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    spec=importlib.util.spec_from_file_location('bound_sequence_reader',reader_path)
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    assert r.pin(Path(__file__))==plan['source'] and len(plan['groups'])==36
    assert hashlib.sha256(CONTROLLER.read_bytes()).hexdigest()==CONTROLLER_SHA
    out=path.parent
    # Exclusive sequence claim prevents a second launch of these same jobs.
    with (out/'root-original-sequence-claim.json').open('x') as f:
        start=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
        json.dump(dict(pid=os.getpid(),starttime_ticks=start,plan=r.pin(path),source=plan['source'],attempt=1),f)
        f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    def event(value):
        row=dict(unix_s=time.time(),**value)
        with (out/'progress.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
        print(json.dumps(row),flush=True)
    def health(index):
        command=plan['main_observer_command']
        h=subprocess.run(command,capture_output=True,timeout=40)
        for kind,b in [('stdout',h.stdout),('stderr',h.stderr)]:
            with (out/f'main-before-group-{index:02d}-{kind}.bin').open('xb') as f:
                f.write(b);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        assert h.returncode==0
        value=json.loads(h.stdout)
        assert value['classification']=='ORIGINAL_WINDOW_TERMINAL_CLOSED' and value['held_inputs']==195
        assert value['original192_verified'] and value['main']['client_count']==192
        return value['main']
    event(dict(status='ORIGINAL_SEQUENCE_STARTED',groups=36,source_selected_for_science=False))
    for index,group in enumerate(plan['groups'],1):
        config=group['config'];r.read_pin(config)
        before=health(index)
        event(dict(status='GROUP_START',index=index,group=group['name'],config=config,main=before))
        command=['/usr/bin/python3.12','-I','-B',str(CONTROLLER),'--execute','--config',config['path'],
                 '--expected-source-sha256',CONTROLLER_SHA]
        result=subprocess.run(command,capture_output=True)
        for kind,b in [('stdout',result.stdout),('stderr',result.stderr)]:
            with (out/f'group-{index:02d}-controller-{kind}.bin').open('xb') as f:
                f.write(b);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        closed=Path(group['closure_path'])
        receipt=r.pin(closed) if closed.exists() else None
        event(dict(status='GROUP_CLOSED' if result.returncode==0 else 'GROUP_FAILED_STOP_NO_RETRY',index=index,
            group=group['name'],controller_exit=result.returncode,closure=receipt))
        if result.returncode!=0:return 1
    event(dict(status='ALL36_ORIGINAL_CONTROLLERS_EXIT0_CLOSED_INDEPENDENT_READBACK_PENDING',
        source_selected_for_science=False,quality_qualified=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
