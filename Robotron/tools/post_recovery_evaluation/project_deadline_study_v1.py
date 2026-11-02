"""Passive four-leg dashboard projection after the original R1 projector exits.

No process controls, launches, scientific qualification or canonical state
mutation. Original sealed scores and independent qualifications remain primary.
"""
import argparse
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[2]
ORDER=['R1','C1','R2','C2']


def read(path):
    return json.loads(path.read_bytes())if path.exists()else None


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def atomic(path,value):
    temporary=path.with_name(path.name+'.four-leg-projection-next')
    with temporary.open('x')as stream:
        json.dump(value,stream,separators=(',',':'),allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
    os.replace(temporary,path)


def display(root,leg):
    folder=root/leg;job=read(folder/'job.json');native=Path(job['output'])
    raw=read(native/'status.json');closed=read(folder/'controller-original-result.json')
    q=read(folder/('root-'+leg+'-independent-qualified.json'))
    if q:phase='complete'
    elif closed:phase='closed_pending_independent_review'if closed['actual_exit']==0 else'original_failed_no_retry'
    elif raw:phase=raw['phase']
    elif (folder/'controller-original-launch.json').exists():phase='verifying_main_readiness'
    else:phase='pending'
    row=dict(phase=phase,complete=q is not None,updated_unix_s=time.time(),
             independently_qualified=q is not None,full_game_quality_qualified=False,
             reason='Fixed one-hour score screen; separate complete-game confirmation is required.')
    if raw:row['started']=raw['n_selected_first_games']
    if closed and closed['actual_exit']!=0:row.update(valid=False,reason='Original run failed and is preserved without retry.')
    if q:
        assert q['status']=='INDEPENDENT_DEADLINE32_QUALIFIED'and q['leg']==leg
        score=q['score_cutoff']
        row.update(n_scored=score['n_scored'],completed=score['n_completed'],n_censored=score['n_censored'],
                   mean_score=score['mean_score'],median_score=score['median_score'])
    if (native/'original-loaded-policy.json').exists():
        loaded=read(native/'original-loaded-policy.json');assert loaded['policy']['checkpoint_sha256']==job['checkpoint']['sha256']
        row.update(checkpoint_sha256=job['checkpoint']['sha256'],clocks=job['expected_policy_clocks'])
    return row


def run(args):
    packet=read(args.precommit.resolve());root=Path(packet['study_directory']);sequence=Path(packet['output'])
    study=read(root/'study-precommit.json');assert packet['ordered_legs']==ORDER
    intent=sequence/'passive-four-leg-projector-original01.json'
    with intent.open('x')as stream:
        json.dump(dict(pid=os.getpid(),birth=birth(os.getpid()),previous_projector=dict(pid=args.previous_projector_pid,
            birth=args.previous_projector_birth),source=str(Path(__file__).resolve()),no_process_controls=True),stream)
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    while birth(args.previous_projector_pid)==args.previous_projector_birth:time.sleep(2)
    print('ORIGINAL_R1_PROJECTOR_CLOSED_HANDOFF',flush=True)
    while True:
        active=(read(ROOT/'logs/managed-learning-20261015/state.json')or{}).get('active_quality_job')or{}
        if active.get('directory')!=str(root):return
        rows={leg:display(root,leg)for leg in ORDER}
        for leg,row in rows.items():atomic(root/leg/'display-status.json',row)
        outcome=read(sequence/'sequence-original-outcome.json');assessment=read(sequence/'four-original-screen-assessment.json')
        current=ORDER[max(0,min(3,int(active.get('current_leg',1))-1))]
        failed=outcome and outcome['status']!='FOUR_ORIGINAL_SCREENING_LEGS_REVIEWED'
        value=dict(schema='robotron-prepared-policy-screening-status-v1',state='failed'if failed else('screened'if assessment else'running'),
            updated_unix_s=time.time(),evaluation_started=True,current_leg=current,
            candidate_sha256=study['policies']['candidate']['checkpoint']['sha256'],quality_qualified=False,promotion=False)
        if failed:value['detail']='Original comparison sequence stopped; results and actual failures are preserved. No scientific retry.'
        elif assessment:
            value['detail']='All four score screens independently reviewed. '+('Both candidate gates passed; fresh complete-game confirmation is next.'if assessment['screening_passed']else'Candidate screening gates did not both pass; protected reference retained.')
        elif rows[current]['phase']=='complete':value['detail']=current+' independently reviewed; preparing the next original leg.'
        else:value['detail']=current+' '+rows[current]['phase'].replace('_',' ')+'. 32 frozen-policy first games with a fixed one-hour cutoff.'
        atomic(ROOT/'html/next-policy-evaluation.json',value)
        if outcome:return
        time.sleep(2)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');parser.add_argument('--precommit',type=Path)
    parser.add_argument('--previous-projector-pid',type=int);parser.add_argument('--previous-projector-birth',type=int);args=parser.parse_args()
    if args.run:run(args)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
