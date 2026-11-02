"""Project declared original quality receipts into dashboard files; no actions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

ORDER=('R1','C1','R2','C2')
FOLDERS=('01-reference','02-candidate','03-reference','04-candidate')

def read(path):
    try:
        if path.stat().st_size>16<<20:return {}
        return json.loads(path.read_bytes())
    except (FileNotFoundError,ProcessLookupError,json.JSONDecodeError):return {}

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def alive(row):
    return type(row.get('pid'))is int and birth(row['pid'])==row.get('starttime_ticks',row.get('birth'))

def publish(path,value):
    temporary=path.with_name(path.name+'.next')
    with temporary.open('w')as stream:
        json.dump(value,stream,separators=(',',':'),allow_nan=False);stream.write('\n')
        stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o664)
    os.replace(temporary,path)

def terminal_zero(root,name):
    result=read(root/name)
    if result.get('actual_exit')!=0:return False
    closure=read(Path(result.get('closure',{}).get('path','/nonexistent-quality-display-closure')))
    return closure.get('original_exit')==0 and closure.get('lifecycle_complete')is True and closure.get('unit_released')is True

def project(root,index):
    folder=FOLDERS[index];directory=root/folder;native=read(directory/'diagnostic-output-original01/status.json')
    result=read(directory/'diagnostic-output-original01/result.json')
    owner=read(directory/'execution-original01/root-original-identity.json')
    controller=read(directory/'controller-original-child.json')
    cpu_owner=read(directory/'independent-review-execution-original01/root-original-identity.json')
    report=read(directory/'independent-quality-leg-review-original01/review.json')
    native_exit=read(directory/'controller-original-result.json');cpu_exit=read(directory/'independent-review-controller-original-result.json')
    loaded=read(directory/'diagnostic-output-original01/original-loaded-policy.json')
    policy=loaded.get('policy',{});control=native.get('controller',{})
    cohort=result.get('before_intentional_stop')or control.get('cohort',{})
    count=cohort.get('count',0)
    data=dict(label=('1741.2M protected reference'if index%2==0 else'2561.1M current LR125 candidate'),
        count=count,started=cohort.get('started',0),pending=cohort.get('pending',0),
        mean=cohort.get('mean')if count else None,median=cohort.get('median')if count else None,
        se=cohort.get('se')if count else None,start_ts=cohort.get('start_ts'),close_ts=cohort.get('close_ts'),
        checkpoint_sha256=policy.get('checkpoint_sha256'),clocks={'learner_frame_count':policy.get('learner_frame_count')},
        valid=None,complete=False,phase='pending',reason=None,updated_unix_s=time.time())
    if (native_exit and native_exit.get('actual_exit')!=0)or(cpu_exit and cpu_exit.get('actual_exit')!=0)or report.get('valid')is False:
        state='failed';data.update(phase='invalid',valid=False,reason=report.get('error')or'Original execution/review failed; no retry')
    elif report.get('valid')is True and terminal_zero(directory,'controller-original-result.json')and terminal_zero(directory,'independent-review-controller-original-result.json'):
        state='finished';data.update(phase='finished',valid=True,complete=True)
    elif alive(cpu_owner):state='running';data.update(phase='independent_review',reason='Independent review in progress')
    elif alive(owner)or alive(controller):state='running';data['phase']=control.get('phase')or'warming'
    elif native_exit.get('actual_exit')==0:
        state='running';data.update(phase='awaiting_independent_review',reason='Native complete; independent review pending')
    elif owner or controller:
        state='unknown';data.update(phase='awaiting_terminal_receipt',reason='Original process no longer observed; terminal receipt pending')
    else:state='pending'
    publish(root/'display'/f'{folder}.json',data)
    return dict(index=index+1,role='reference'if index%2==0 else'candidate',state=state,
        evaluator_status_path=str(root/'display'/f'{folder}.json'),receipt_path=str(root/'display'/f'{folder}.json'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--campaign');parser.add_argument('--readiness-sha256')
    args=parser.parse_args()
    if not args.run:print('PLAN_ONLY');return 0
    root=Path(args.campaign);ready=root/'new-original-quality-launch-readiness.json'
    assert root.is_absolute()and root.resolve()==root and hashlib.sha256(ready.read_bytes()).hexdigest()==args.readiness_sha256
    assert read(ready)['campaign_directory']==str(root)
    intent=root/'display-observer-original-intent.json'
    with intent.open('x')as stream:
        json.dump(dict(pid=os.getpid(),birth=birth(os.getpid()),source=str(Path(__file__).resolve()),
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            readiness_sha256=args.readiness_sha256,read_only_science=True,created_unix_s=time.time()),stream,indent=2)
        stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(observer_pid=os.getpid(),birth=birth(os.getpid()),intent=str(intent))),flush=True)
    deadline=time.monotonic()+43000
    while time.monotonic()<deadline:
        legs=[project(root,index)for index in range(4)]
        current=next((row['index']for row in legs if row['state']in ('running','unknown','failed')),None)
        state='running'if current else'prepared';outcome=None;reason=None
        if any(row['state']=='failed'for row in legs):state='failed';outcome='invalid';reason='Original leg failed; no retry'
        assessment=read(root/'independent-campaign-assessment-original01/assessment.json')
        if assessment.get('valid')is False:state='failed';outcome='invalid';reason=assessment.get('error')
        elif assessment.get('valid')is True and terminal_zero(root,'campaign-assessment-controller-original-result.json'):
            state='finished';outcome='qualified'if assessment.get('quality_qualified')else'not_improved'
        elif all(row['state']=='finished'for row in legs):state='running';reason='All legs reviewed; final campaign assessment pending';current=4
        publish(root/'status.json',dict(state=state,current_leg=current,total_legs=4,legs=legs,
            updated_unix_s=time.time(),outcome=outcome,reason=reason))
        if state in ('finished','failed'):return 0
        time.sleep(5)
    publish(root/'display-observer-deadline.json',dict(state='observer_deadline',original_science_not_restarted=True,unix_s=time.time()))
    return 1

if __name__=='__main__':raise SystemExit(main())
