"""Default inert. Passive E078 R1 display; no launch, control or qualification.

Read scores only through the existing display function after an independent
qualification exists. An absent wrapper without a terminal record is unresolved.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
I=G/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027'
A=Path(__file__).resolve().parent
S=I/'durable-e078b0da-launcher-mmap-study-original01'
ORDER=['R1','C1','R2','C2']
UNIT='robotron-e078-original-R1-passive-display-original02-20261029.service'
MANIFEST_SHA='53cadb2588874e143bf4385bd1d446fa83d31eb6784b371aacd634ec37c7bfe3'


def require(value,message):
    if not value:raise RuntimeError(message)


def read(path):
    if not path.exists():return None
    require(path.is_file() and not path.is_symlink() and path.suffix!='.pt' and path.stat().st_size<2<<20,
        'Bounded non-model display metadata required')
    return json.loads(path.read_bytes())


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def atomic(path,value):
    temporary=path.with_name(path.name+'.e078-R1-projection-next')
    with temporary.open('x')as f:
        json.dump(value,f,separators=(',',':'),allow_nan=False);f.write('\n');f.flush()
        os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
    os.replace(temporary,path)


def run(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,
        'Exact Root-selected passive display source required')
    path=G/'tools/post_recovery_evaluation/project_deadline_study_v3.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='5e2732552e58b5f081159525ad1470844f0ba965a8388b7c8b512c5d8abff7db',
        'Original display-only score disclosure guard changed')
    spec=importlib.util.spec_from_file_location('_e078_qualified_display',path)
    display=importlib.util.module_from_spec(spec);spec.loader.exec_module(display)
    manifest_path=S/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json'
    require(hashlib.sha256(manifest_path.read_bytes()).hexdigest()==MANIFEST_SHA,'Exact E078 four-job manifest required')
    manifest=read(manifest_path);study=read(S/'study-precommit.json')
    require([c['leg']for c in manifest['cases']]==study['ordered_legs']==ORDER
        and manifest['engineering_only']is False
        and study['policies']['candidate']['checkpoint']['sha256']=='e078b0da4ce4e25146fab7484f8489f590e1086370746cb392afcd7f5f8adef5'
        and study['policies']['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        'Exact fresh fixed RCRC study required')
    fields=dict(v.split('=',1)for v in subprocess.check_output(['systemctl','--user','show',UNIT],text=True,timeout=5).splitlines()if'='in v)
    expected=dict(Id=UNIT,MainPID=str(os.getpid()),InvocationID=os.environ.get('INVOCATION_ID'),
        Type='exec',ActiveState='active',SubState='running',Restart='no',NRestarts='0',RemainAfterExit='yes',
        CPUQuotaPerSecUSec='200ms',MemoryMax=str(128<<20),MemorySwapMax='0',TasksMax='32',
        RuntimeMaxUSec='1h 21min',TimeoutStopUSec='10s',SendSIGKILL='no')
    require(expected['InvocationID']and all(fields.get(k)==v for k,v in expected.items()),'Exact durable passive display scope required')
    active=(read(G/'logs/managed-learning-20261015/state.json')or{}).get('active_quality_job')or{}
    require(active.get('directory')==str(S)and active.get('current_leg',1)in(1,'R1'),
        'Root must register this original R1 before display publication')
    epath=G/'html/next-policy-evaluation.json'
    backup=A/'next-policy-evaluation-before-original-R1-display02.exact.json'
    with backup.open('xb')as f:
        f.write(epath.read_bytes());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    legs=[dict(index=k+1,role='reference'if leg.startswith('R')else'candidate',
        evaluator_status_path=str(S/leg/'display-status.json'))for k,leg in enumerate(ORDER)]
    plan=dict(schema='robotron-deadline32-dashboard-plan-v1',
        checkpoints={role:study['policies'][role]['checkpoint']for role in ('reference','candidate')},
        legs=[dict(v,job=dict(label='Protected reference'if v['role']=='reference'else'Frozen candidate'))for v in legs])
    if (S/'plan.json').exists():require(read(S/'plan.json')==plan,'Existing display plan differs')
    else:
        with (S/'plan.json').open('x')as f:
            json.dump(plan,f,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    previous=None
    while True:
        active=(read(G/'logs/managed-learning-20261015/state.json')or{}).get('active_quality_job')or{}
        if active.get('directory')!=str(S)or active.get('current_leg',1)not in(1,'R1'):return 0
        intent=read(A/'original-R1-wrapper-intent.json')
        terminal=read(A/'original-R1-wrapper-terminal.json')
        owner=read(A/'actual-original-R1-live-owner.json')
        closed=read(S/'R1/controller-original-result.json')
        unresolved=bool(terminal and terminal['status']=='ORIGINAL_OUTCOME_UNRESOLVED_NO_RETRY')or bool(
            intent and not terminal and not closed and birth(intent['actual_wrapper_pid'])!=intent['actual_wrapper_birth'])
        row=display.display(S,'R1')
        if unresolved:row.update(phase='original_terminal_unresolved_no_retry',complete=False,independently_qualified=False,
            reason='Original wrapper is absent; no actual terminal outcome has been established. No retry.')
        failed=bool(closed and closed['actual_exit']!=0)
        state='unresolved'if unresolved else('failed'if failed else('review_pending'if closed else'running'if intent else'pending'))
        atomic(S/'R1/display-status.json',row)
        for leg in ORDER[1:]:
            atomic(S/leg/'display-status.json',dict(phase='cancelled'if failed else'pending',complete=False,count=0,
                independently_qualified=False,updated_unix_s=time.time(),full_game_quality_qualified=False))
        status=dict(state=state,current_leg=1,updated_unix_s=time.time(),
            legs=[dict(v,state=(state if k==0 else'cancelled'if failed else'pending'),
                started_unix_s=intent['created_unix_s']if k==0 and intent else None)for k,v in enumerate(legs)])
        atomic(S/'status.json',status)
        if unresolved:detail='Original reference R1 has no established terminal outcome. The original attempt is preserved without retry.'
        elif failed:detail='Original reference R1 failed. Its actual result is preserved without retry.'
        elif closed:detail='Original reference R1 closed; independent score/runtime review is pending.'
        elif row['phase']=='collecting':detail='Reference R1 is running 32 fixed-policy first games to a fixed one-hour cutoff. Candidate C1 follows only after independent review.'
        else:detail='Reference R1 '+row['phase'].replace('_',' ')+'. Training continues separately.'
        value=dict(schema='robotron-prepared-policy-screening-status-v1',state=state,updated_unix_s=time.time(),
            previous_status_archive=str(backup),evaluation_started=owner is not None,current_leg='R1',
            candidate_sha256=study['policies']['candidate']['checkpoint']['sha256'],quality_qualified=False,promotion=False,detail=detail,
            legs=[dict(leg=leg,phase=row['phase']if leg=='R1'else'cancelled'if failed else'pending',
                n_scored=row.get('n_scored')if leg=='R1'else None,n_completed=row.get('completed')if leg=='R1'else None,
                n_censored=row.get('n_censored')if leg=='R1'else None,mean_score=row.get('mean_score')if leg=='R1'else None,
                median_score=row.get('median_score')if leg=='R1'else None,
                independently_qualified=row['independently_qualified']if leg=='R1'else False)for leg in ORDER])
        anchor=read(Path(read(S/'R1/job.json')['output'])/'original-deadline-anchor.json')
        if anchor:value['deadline_anchor']=anchor
        atomic(epath,value)
        if row['phase']!=previous:
            print(json.dumps(dict(phase=row['phase'],state=state,observed_unix_s=time.time())),flush=True);previous=row['phase']
        if closed or unresolved:return 0
        time.sleep(2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if a.run:raise SystemExit(run(a))
    print('PLAN_ONLY: no reads, outputs, queries, launches or controls')
