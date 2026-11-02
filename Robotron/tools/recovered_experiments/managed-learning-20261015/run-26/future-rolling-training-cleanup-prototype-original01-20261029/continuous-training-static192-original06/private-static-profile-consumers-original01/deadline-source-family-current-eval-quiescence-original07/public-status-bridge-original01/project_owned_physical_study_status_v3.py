"""Inert generic physical-study PUBLIC-only status bridge. Root owns handoff.

Reads original metadata; writes only public next-policy JSON and this own folder.
No canonical/study status, process control, scientific action or qualification.
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
O=Path(__file__).resolve().parent
A=None
S=None
FIRST_REVIEW=None
SEQUENCE_DIRECTORY=None
ORDER=['R1','C1','R2','C2']
UNIT=None
PUBLIC=G/'html/next-policy-evaluation.json'

def require(ok,message):
    if not ok:raise ValueError(message)

def read(path):
    path=Path(path)
    if not path.exists():return None
    require(path.is_file()and not path.is_symlink()and path.suffix!='.pt'and path.stat().st_size<4<<20,'Bounded non-model metadata required')
    return json.loads(path.read_bytes())

def load(path,digest,name):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Exact passive source differs')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def atomic(path,value):
    temporary=path.with_name(path.name+'.physical-public-original01-next')
    with temporary.open('x')as f:
        json.dump(value,f,separators=(',',':'),allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def live(owner):
    if not owner:return dict(live=None,started_unix_s=None,elapsed_s=None,time_basis='No original live owner observed')
    pid=owner['pid'];ticks=owner.get('starttime_ticks',owner.get('birth'))
    require(type(pid)is int and type(ticks)is int,'Original PID/birth required')
    try:
        fields=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
        alive=int(fields[19])==ticks and fields[0]not in('Z','X')
    except FileNotFoundError:alive=False
    # Linux process birth ticks use boot time. This is process age, not % work.
    nowboot=time.clock_gettime(time.CLOCK_BOOTTIME);now=time.time()
    age=max(0.,nowboot-ticks/os.sysconf('SC_CLK_TCK'))
    return dict(live=alive,started_unix_s=now-age,elapsed_s=age,time_basis='Original process birth ticks; process age, not work completion')

def controller_facts(folder,prefix):
    result=read(folder/(prefix+'controller-original-result.json'))
    child=read(folder/(prefix+'controller-original-child.json'))
    state=live(child)
    return result,state

def timing(job,leg,candidate):
    a=read(Path(job['output'])/'original-deadline-anchor.json')
    if not a:return None
    b=a['anchor']
    require(candidate=='c0acc8ad3aa411a00928b6f242b2e4a6299780b5a2991c75225d334c21af60f0'
        and a['original_job']['path']==str(S/leg/'job.json')
        and a['policy']['policy_sha256']==job['checkpoint']['sha256']
        and b['members']==32 and b['horizon_ns']==3600000000000
        and b['deadline_monotonic_ns']-b['anchor_monotonic_ns']==b['horizon_ns'], 'Original per-leg fixed anchor differs')
    before=time.monotonic_ns();wall=time.time_ns();after=time.monotonic_ns()
    value=dict(schema='robotron-fixed-deadline-display-timing-v1',anchor_monotonic_ns=b['anchor_monotonic_ns'],deadline_monotonic_ns=b['deadline_monotonic_ns'],members=b['members'],horizon_ns=b['horizon_ns'],derived_from_original_anchor=True,anchor=b,policy_sha256=job['checkpoint']['sha256'],source='original-deadline-anchor.json',candidate_sha256=candidate,leg=leg)
    if after-before<=1000000:
        offset=wall-(before+after)//2
        value.update(started_unix_s=(b['anchor_monotonic_ns']+offset)/1e9,deadline_unix_s=(b['deadline_monotonic_ns']+offset)/1e9,
            elapsed_s=max(0.,((before+after)//2-b['anchor_monotonic_ns'])/1e9),remaining_s=max(0.,(b['deadline_monotonic_ns']-(before+after)//2)/1e9),
            clock_mapping='Current bounded host cosample of original immutable monotonic anchor',clock_span_ns=after-before)
    return value

def leg_status(case,display,candidate):
    leg=case['leg'];folder=S/leg;job=read(folder/'job.json');native=Path(job['output'])
    q=folder/('root-'+leg+'-independent-qualified.json')
    row=dict(leg=leg,phase='pending',state='pending',independently_qualified=False,full_game_quality_qualified=False)
    if q.exists():
        # The unchanged guard alone reads qualified score/seal values.
        safe=display.display(S,leg)
        require(safe['independently_qualified']is True,'Qualified display guard refused')
        row.update(safe,state='qualified',phase='complete',n_completed=safe.get('completed'));return row
    native_result_exists=(native/'result.json').is_file()  # Never open the large native body.
    review_result,review_live=controller_facts(folder,'independent-review-')
    native_result,native_live=controller_facts(folder,'')
    first_terminal=read(FIRST_REVIEW/'first-R1-review-wrapper-terminal.json')if leg=='R1'else None
    first_intent=read(FIRST_REVIEW/'first-R1-review-wrapper-intent.json')if leg=='R1'else None
    first_live=live(dict(pid=first_intent['wrapper_pid'],birth=first_intent['wrapper_birth']))if first_intent else live(None)
    review_prepared=read(folder/'independent-review-prepared-original01.json')
    review_owner=None
    if review_prepared:
        cfg=read(review_prepared['review_config']['path']);review_owner=read(Path(cfg['output'])/'root-original-identity.json')
    reviewer_live=live(review_owner)
    native_owner=read(folder/'execution-original01/root-original-identity.json')
    native_process=live(native_owner)
    row.update(native_owner_live=native_process['live'],native_controller_live=native_live['live'],review_owner_live=reviewer_live['live'],review_controller_live=review_live['live'])
    raw=read(native/'status.json')
    if raw and type(raw.get('n_selected_first_games')) is int:row['n_started']=raw['n_selected_first_games']
    if native_result and native_result.get('actual_exit')!=0:
        row.update(phase='original_native_outcome_unresolved'if native_result.get('actual_exit')is None else'original_native_failed_no_retry',state='unresolved'if native_result.get('actual_exit')is None else'failed')
    elif first_terminal and first_terminal.get('status')=='ORIGINAL_REVIEW_UNQUALIFIED_PRESERVED_NO_RETRY':
        row.update(phase='original_review_unqualified_no_retry',state='failed')
    elif first_intent and not first_terminal and first_live['live']is False and not review_result:
        row.update(phase='original_review_owner_outcome_unresolved',state='unresolved')
    elif review_result:
        code=review_result.get('actual_exit')
        row.update(phase='review_closed_waiting_qualification'if code==0 else'original_review_outcome_unresolved'if code is None else'original_review_failed_no_retry',state='waiting'if code==0 else'unresolved'if code is None else'failed')
    elif reviewer_live['live']is True:
        row.update(phase='independent_review_running',state='running',wait='Original independent raw/runtime review; no estimate of completion percentage',**{k:v for k,v in reviewer_live.items()if k!='live'})
    elif review_owner and reviewer_live['live']is False and review_live['live']is True:
        row.update(phase='review_outcome_waiting_original_controller',state='waiting')
    elif review_live['live']is True:
        row.update(phase='independent_review_starting',state='running',**{k:v for k,v in review_live.items()if k!='live'})
    elif first_live['live']is True:
        row.update(phase='independent_review_starting',state='running',**{k:v for k,v in first_live.items()if k!='live'})
    elif review_prepared and review_live['live']is False:
        row.update(phase='original_review_outcome_unresolved',state='unresolved')
    elif native_result and native_result.get('actual_exit')==0:
        row.update(phase='closed_pending_independent_review',state='waiting')
    elif native_result_exists:
        row.update(phase='native_closed_waiting_original_controller',state='waiting')
    elif native_live['live']is False:
        row.update(phase='original_native_outcome_unresolved',state='unresolved')
    elif native_owner and native_process['live']is False:
        row.update(phase='native_outcome_waiting_original_controller',state='waiting')
    elif raw:
        row.update(phase='collecting'if raw.get('phase')=='active_deadline'else raw.get('phase','starting'),state='running',**{k:v for k,v in native_process.items()if k!='live'})
    elif native_live['live']is True:
        row.update(phase='verifying_main_readiness',state='running',**{k:v for k,v in native_live.items()if k!='live'})
    if row['phase'].startswith('independent_review')or review_prepared:
        row['review_budget']=dict(actual_reviewer_runtime_limit_s=1980,controller_observation_limit_s=2040,parent_limit_s=2400 if leg=='R1'else 21600,these_are_limits_not_ETAs=True)
    if row['phase']=='collecting':row['deadline_timing']=timing(job,leg,candidate)
    return row

def run(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Exact bridge source required')
    h=load(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','_W03_public_h')
    global A,S,FIRST_REVIEW,SEQUENCE_DIRECTORY,UNIT
    cfgpin=h.pin(args.config.resolve());require(cfgpin['sha256']==args.config_sha256,'Exact Root bridge selection required');cfg=json.loads(h.checked(cfgpin).read_bytes())
    require(cfg['schema']=='robotron-generic-physical-public-status-selection-v1'
        and cfg['source']==h.pin(Path(__file__).resolve()),'Exact generic public bridge source required')
    selection=json.loads(h.checked(cfg['launch_selection']).read_bytes())
    manifest=json.loads(h.checked(selection['prepared_manifest']).read_bytes())
    study=json.loads(h.checked(selection['study_precommit']).read_bytes())
    require(selection['schema']=='robotron-generic-physical-original-R1-launch-selection-v1'
        and selection['source']['sha256']=='e089e6f45ae8cc26813d589fbc36eab281fd20bec091e5f5f6151ed4e2c7337d'
        and selection['candidate_sha256']==study['policies']['candidate']['checkpoint']['sha256']=='c0acc8ad3aa411a00928b6f242b2e4a6299780b5a2991c75225d334c21af60f0'
        and study['policies']['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
        and [c['leg']for c in manifest['cases']]==ORDER
        and manifest['study_precommit']==selection['study_precommit'], 'Actual bound generic physical RCRC study required')
    A=Path(h.checked(selection['source'])).parent
    S=Path(selection['prepared_manifest']['path']).parent
    require(S.is_relative_to(G/'logs/managed-learning-20261015/run-26')
        and selection['prepared_manifest']['path']==str(S/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json')
        and selection['study_precommit']['path']==str(S/'study-precommit.json'), 'Actual canonical study paths required')
    first=json.loads(h.checked(cfg['first_review_source_preparation']).read_bytes())
    require(first['schema']=='robotron-generic-owned-first-physical-R1-review-source-family-v1'
        and first['source']['sha256']=='4a03ae27135b77c592f4e7a59672cec5547227c4b05b83ad46b6153c604b6f65'
        and first['selected_R1_source_preparation']==selection['source_preparation'], 'Same actual R1 first-review source contract required')
    FIRST_REVIEW=Path(h.checked(first['source'])).parent
    require(cfg['sequence_source']['sha256']=='d821a0121ad4b2cdec82877299d5666aecee56b42aa11c5ce70c738096cc80f9', 'Exact generic continuation source required')
    h.checked(cfg['sequence_source'])
    SEQUENCE_DIRECTORY=Path(cfg['sequence_directory'])
    require(SEQUENCE_DIRECTORY.is_absolute() and SEQUENCE_DIRECTORY.parent==S,
        'Root-selected future sequence output must be directly in this study')
    UNIT='robotron-physical-cohort-proof2s-'+selection['study_precommit']['sha256'][:16]+'-public-status-original01-20261029.service'
    require(cfg['unit']==UNIT,'Exact study-derived passive publisher unit required')
    handoff=json.loads(h.checked(cfg['publication_handoff']).read_bytes())
    require(handoff['schema']=='robotron-root-generic-public-status-writer-handoff-v1'
        and handoff['status']=='ROOT_MANUAL_PUBLIC_WRITER_RELEASED'
        and handoff['launch_selection']==cfg['launch_selection']
        and handoff['study_precommit']==selection['study_precommit']
        and handoff['public_path']==str(PUBLIC)
        and handoff['root_manual_writer_released'] is True
        and handoff['no_other_public_writer_selected_or_running'] is True,
        'Actual Root single-writer public handoff required')
    require(handoff['public_preimage']['path']==str(PUBLIC),'Actual public preimage path required')
    h.checked(handoff['public_preimage'])
    for prior in handoff['previous_automatic_publishers']:
        h.checked(prior['positive_owned_closeout'])
        require(live(prior['original'])['live']is False,'Previous actual public publisher birth remains')
        oldfields=dict(v.split('=',1)for v in subprocess.check_output(['systemctl','--user','show',prior['original']['unit']],text=True,timeout=5).splitlines()if'='in v)
        require(oldfields.get('LoadState')=='not-found','Previous actual publisher unit remains; one writer only')
    fields=dict(v.split('=',1)for v in subprocess.check_output(['systemctl','--user','show',UNIT],text=True,timeout=5).splitlines()if'='in v)
    require(fields.get('MainPID')==str(os.getpid())and fields.get('InvocationID')==os.environ.get('INVOCATION_ID')and fields.get('NRestarts')=='0'and fields.get('Restart')=='no','Original owned bridge unit required')
    expected=dict(Type='exec',ActiveState='active',SubState='running',RemainAfterExit='yes',CPUQuotaPerSecUSec='200ms',MemoryMax=str(128<<20),MemorySwapMax='0',TasksMax='32',RuntimeMaxUSec='8h',TimeoutStopUSec='10s',SendSIGKILL='no')
    require(all(fields.get(k)==v for k,v in expected.items()),'Exact bounded passive scope required')
    main_display=cfg['main_training_display']
    require(main_display['mode_installed']is True and main_display['main_mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE'
        and set(main_display)<={'mode_installed','main_mode','previous_phase_completed_evaluation'},
        'Only retained mode/descriptive history may pass through; no stale next_work stage')
    for case in manifest['cases']:h.checked(case['native_job'])
    display=load(G/'tools/post_recovery_evaluation/project_deadline_study_v3.py','5e2732552e58b5f081159525ad1470844f0ba965a8388b7c8b512c5d8abff7db','_W03_guarded_display')
    backup=O/'public-status-before-generic-bridge-original01.exact.json'
    with backup.open('xb')as f:f.write(PUBLIC.read_bytes());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    while True:
        active=(read(G/'logs/managed-learning-20261015/state.json')or{}).get('active_quality_job')or{}
        if active.get('directory')!=str(S):return 0
        rows=[leg_status(case,display,selection['candidate_sha256'])for case in manifest['cases']]
        seq=SEQUENCE_DIRECTORY;outcome=read(seq/'sequence-original-outcome.json');seqchild=read(seq/'sequence-original-child.json')
        if seqchild:
            commit=read(seq/'sequence-precommit.json');require(commit['source']==cfg['sequence_source']and commit['study_directory']==str(S)and commit['review_precommit']==read(selection['readiness']['path'])['review_precommit']and seqchild['original_precommit']==h.pin(seq/'sequence-precommit.json'),'Actual sequence source/study/precommit differs')
        chosen=next((r for r in rows if r['state']!='qualified'),rows[-1]);state=chosen['state']
        original_scope_live=any(r.get('native_owner_live')is True or r.get('review_owner_live')is True for r in rows)
        if outcome:
            state='closed'if outcome['status']=='FOUR_ORIGINAL_SCREENING_LEGS_REVIEWED'else'stopped'if outcome['status']=='STOPPED_NO_NEW_ACTIONS'else'failed'
        elif seqchild and live(seqchild)['live']is False:state='unresolved'
        detail=chosen['leg']+': '+chosen['phase'].replace('_',' ')+'. 32 original first games; one common fixed one-hour anchor.'
        if chosen.get('review_budget'):detail+=' Independent review limit33min; controller observation34min. These limits are not completion estimates.'
        if state in('failed','unresolved','stopped'):detail+=' Original evidence is preserved; no automatic retry or next action.'
        if outcome and outcome.get('original_scope_still_running_preserved')and original_scope_live:detail+=' An original payload remains live and preserved.'
        next_stage='Root screen verdict; separate fullgame confirmation only if eligible'if state=='closed'else'independent_review'if chosen['phase']in('collecting','closed_pending_independent_review','native_closed_waiting_original_controller')else'qualification'if 'review'in chosen['phase']else'next original leg only after qualification'
        value=dict(schema='robotron-prepared-policy-screening-status-v1',study_directory=str(S),state='review_pending'if state=='waiting'else'screened'if state=='closed'else state,stage=chosen['phase'],current_leg=chosen['leg'],updated_unix_s=time.time(),candidate_sha256=selection['candidate_sha256'],quality_qualified=False,promotion=False,detail=detail,legs=rows,next_stage=next_stage,limits_are_not_ETAs=True,original_payload_live=original_scope_live)
        if chosen.get('deadline_timing'):
            value['deadline_timing']=chosen['deadline_timing']
            value['deadline_anchor']=dict(anchor=chosen['deadline_timing']['anchor'],policy=dict(policy_sha256=chosen['deadline_timing']['policy_sha256']))
        value['next_work']=dict(main_display)
        # During actual collecting let the existing browser predicate validate
        # and render the common original anchor and decrement its own countdown.
        # Outside collecting replace the old setup override with this live phase.
        if not(state=='running' and chosen['phase']=='collecting' and chosen.get('deadline_timing')):
            if state=='closed':
                work_state='physical_screening_complete'
                work_stage='All four original screening legs independently reviewed'
                waiting='Root screening verdict; separate full-game confirmation only if eligible'
                eta='Screening and independent reviews are complete. No finishing time is set for the next required stage.'
            elif state in('failed','unresolved','stopped'):
                work_state='physical_'+state
                work_stage=chosen['leg']+' original outcome '+state+'; evidence preserved'
                waiting='Root review of the preserved original outcome; no automatic retry or next action'
                eta='No next completion time is set while the original outcome needs review.'
            else:
                work_state='physical_'+chosen['phase']
                work_stage=chosen['leg']+' · '+chosen['phase'].replace('_',' ')
                waiting=('Original independent review and qualification' if 'review' in chosen['phase']
                    else 'Original controller cleanup and independent review' if chosen['state']=='waiting'
                    else 'All 32 original starts and their common deadline anchor')
                eta=('No scoring countdown is active. Review runtime/observation limits are not finishing estimates.'
                    if 'review' in chosen['phase'] else 'No scoring deadline is set until the original common anchor exists.')
            value['next_work'].update(state=work_state,current_stage=work_stage,
                detail=detail,waiting_for=waiting,next_stage=next_stage,eta=eta,deadline_unix_s=None,
                updated_unix_s=value['updated_unix_s'],main_training_continues=None)
        # Never write canonical state or study/status/display-status: sequence owns them.
        atomic(PUBLIC,value);atomic(O/'generic-public-status-last-projection-original01.json',value)
        if state in('closed','failed','stopped','unresolved')and not original_scope_live:return 0
        time.sleep(2)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--config',type=Path);p.add_argument('--config-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if a.run:raise SystemExit(run(a))
    print('SOURCE_ONLY: no reads, queries, publication or process actions')
