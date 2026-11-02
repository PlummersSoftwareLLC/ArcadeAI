"""Passive R1 dashboard projection; never launch, stop or qualify a payload."""
import importlib.util
import json
import os
from pathlib import Path
import time

A=Path(__file__).resolve().parent;S=A.parent/'distincta6e17a3c-single-journal-family11-study-original01';G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
native=S/'R1/deadline-output-original01';result=S/'R1/controller-original-result.json'
job=json.loads((S/'R1/job.json').read_bytes());previous_phase=None
module_path=G/'tools/post_recovery_evaluation/project_deadline_study_v3.py'
spec=importlib.util.spec_from_file_location('_passive_confirmed_R1_rows',module_path)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def atomic(path,value):
    tmp=path.with_name(path.name+'.projection-next')
    with tmp.open('w')as stream:json.dump(value,stream,separators=(',',':'),allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
    os.replace(tmp,path)

def read(path):return json.loads(path.read_bytes())if path.exists()else None

e_path=G/'html/next-policy-evaluation.json';original=e_path.read_bytes();backup=A/'next-policy-evaluation-before-live-R1.exact.json'
with backup.open('xb')as stream:stream.write(original);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
ready=read(A/'fresh-resource-readiness-before-R1.json');ready_stat=(A/'fresh-resource-readiness-before-R1.json').stat()
while True:
    owner=read(A/'actual-original-R1-live-owner.json');raw=read(native/'status.json');loaded=read(native/'original-loaded-policy.json');anchor=read(native/'original-deadline-anchor.json');closed=read(result)
    if closed:phase='closed_pending_independent_review'if closed['actual_exit']==0 else'original_failed_no_retry'
    elif anchor:phase='active_deadline'
    elif loaded:phase='certifying_32_original_starts'
    elif (native/'original-initial-main-readiness.json').exists():phase='loading_and_compiling_frozen_reference'
    elif owner:phase='verifying_main_readiness'
    else:phase='starting_original_controller'
    display=p.display(S,'R1')
    phase=display['phase']
    atomic(S/'R1/display-status.json',display)
    status=read(S/'status.json');status['updated_unix_s']=time.time();status['state']=('review_pending'if closed['actual_exit']==0 else'failed')if closed else'running'
    if closed:
        status['legs'][0]['state']='review_pending'if closed['actual_exit']==0 else'failed'
        if closed['actual_exit']!=0:
            for leg in status['legs'][1:]:leg['state']='cancelled'
    atomic(S/'status.json',status)
    e=dict(schema='robotron-prepared-policy-screening-status-v1',previous_status_archive=str(backup));e.update(state=('closed'if closed['actual_exit']==0 else'failed')if closed else'running',updated_unix_s=time.time(),evaluation_started=owner is not None,
        current_leg='R1',candidate_sha256=read(S/'study-precommit.json')['policies']['candidate']['checkpoint']['sha256'],original_native_job=str(S/'R1/job.json'),original_controller_result=str(result),quality_qualified=False,promotion=False)
    e['legs']=[dict(leg=leg,phase=display['phase']if leg=='R1'else'pending',n_scored=display.get('n_scored')if leg=='R1'else None,n_completed=display.get('completed')if leg=='R1'else None,n_censored=display.get('n_censored')if leg=='R1'else None,mean_score=display.get('mean_score')if leg=='R1'else None,independently_qualified=display.get('independently_qualified',False)if leg=='R1'else False)for leg in ['R1','C1','R2','C2']]
    if anchor:e['deadline_anchor']=anchor
    if closed:e['detail']='Original reference R1 closed; independent score/runtime review is pending.'if closed['actual_exit']==0 else'Original R1 failed; preserved for review and will not be retried.'
    elif anchor:
        e['detail']='Reference R1 is running 32 frozen-policy games. Each score is sealed at its one-hour cutoff; candidate C1 follows after independent review.'
        e['deadline_anchor']=anchor
    else:e['detail']='Reference R1 is initializing on its dedicated GPU: '+phase.replace('_',' ')+'. Live training continues separately.'
    atomic(e_path,e)
    if phase!=previous_phase:
        print(json.dumps(dict(phase=phase,selected_starts=raw['n_selected_first_games']if raw else None,observed_unix_s=time.time())),flush=True);previous_phase=phase
    if closed:break
    time.sleep(2)
