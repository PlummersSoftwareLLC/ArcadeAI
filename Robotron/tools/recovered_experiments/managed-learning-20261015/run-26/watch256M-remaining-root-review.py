#!/usr/bin/env python3
"""Read-only campaign observer; writes independent immutable audits, never signals."""
import hashlib,json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI')
sys.path.insert(0,str(ROOT/'Robotron/tools'))
import run_quality_campaign as campaign
import protect_quality_winner as protection
DIRECTORY=ROOT/'Robotron/logs/managed-learning-20261015/quality-192M-vs-256M-20261016'
OUTPUT=DIRECTORY.parent/'run-26'
EXPECTED='c246a9422ee76a973904379013a8e4e87bdb9887fb8e5133c2c5e57f8dc86782'
PID,TICKS=2689385,27786562

def identity(pid):
    raw=Path(f'/proc/{pid}/stat').read_text()
    return int(raw[raw.rfind(')')+2:].split()[19])

def write(name,value):
    path=OUTPUT/name
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444)
    print(json.dumps(dict(wrote=str(path),utc=value.get('utc'),leg=value.get('leg'),outcome=value.get('assessment',{}).get('outcome'))),flush=True)

raw=(DIRECTORY/'plan.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==EXPECTED
plan=json.loads(raw)
campaign.check_precommit(plan)
deadline=time.monotonic()+4200
reviewed=set()
last=None
while time.monotonic()<deadline:
    state=json.loads((DIRECTORY/'status.json').read_text())
    assert state['plan_sha256']==EXPECTED
    for index in (3,4):
        record=next((row for row in state['legs'] if row['index']==index),None)
        if record and record['state']=='finished' and index not in reviewed:
            assert record['returncode']==0
            campaign.check_precommit(plan)
            spec=plan['legs'][index-1]
            receipt,leg,digest=campaign.load_leg(spec,plan)
            result=dict(utc=datetime.now(timezone.utc).isoformat(),campaign_plan_sha256=EXPECTED,leg=index,role=spec['role'],checkpoint_sha256=receipt['checkpoint_sha256'],receipt_sha256=digest,summary=campaign.summarize(leg),valid=True,whole_games=len(leg['rows']),all_16_slots=True,pending=receipt['cohort'].get('pending'),abandoned=receipt['cohort'].get('abandoned'),campaign_outcome='Strict overall assessment only after all four original cohorts finish')
            write(f'quality256M-{spec["role"]}02-root-validation.json',result)
            reviewed.add(index)
    if state['state']=='finished':
        audited=protection.review(DIRECTORY)
        audited['utc']=datetime.now(timezone.utc).isoformat()
        write('quality256M-completed-root-review.json',audited)
        raise SystemExit(0)
    assert identity(PID)==TICKS,'Runner exited/replaced before finished evidence'
    current=state.get('current_leg')
    record=next(row for row in state['legs'] if row['index']==current)
    live=Path(f'/proc/{record["pid"]}/stat').exists()
    note=(current,record['state'])
    if note!=last:
        print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),runner_pid=PID,runner_start_ticks=TICKS,current_leg=current,leg_pid=record['pid'],leg_process_present=live)),flush=True)
        last=note
    time.sleep(30)
raise SystemExit('Read-only observer deadline expired; campaign unaffected')
