"""Independent raw/evidence review of original thread/process contention arms."""
import hashlib,importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023'
D=R/'health-observer-authentic32-prefix-contention-CPU-original01-preparation-20261023'
def load(path,name,sha=None):
    if sha:assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_review_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_review_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_review_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
closer=load(P/'independent_component_closeout_v3.py','_review_close')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
proof=closer.closeout(D,h,arc,read,0);job=read(h.pin(D/'job.json'));reportpin=h.pin(D/'output-original01/report.json');report=read(reportpin)
assert report['diagnostic_only']and not report['native_MAME_game_run']and not report['production_changed']
assert [arm['arm']for arm in report['arms']]==['thread','process']
enginepin=job['health_job']['sources']['full_health_engine'];engine=load(Path(enginepin['path']),'_review_engine',enginepin['sha256'])
results=[]
for arm in report['arms']:
    root=D/'output-original01'/arm['arm'];health=read(arm['health']);assert health['arm']==arm['arm']
    start=read(h.pin(root/'original-health-start.json'))
    assert len(arm['bursts'])==6 and arm['workload_threads_stopped']
    for burst in arm['bursts']:
        assert [r['slot']for r in burst['original32_prefixes']]==list(range(4096,4128))
        assert burst['all_threads_stopped']
        for row,subject in zip(burst['original32_prefixes'],job['prefix_subjects']):
            h.checked(subject['trace']);assert row['actual_trace_sha256']==subject['trace']['sha256']and row['events']==subject['events']
            assert row['original_prefix_verifier_unchanged']and row['start_monotonic_s']<=row['end_monotonic_s']
    def stat(snapshot):return dict(line.split()for line in snapshot['cpu.stat'].splitlines())
    before,after=stat(arm['before']),stat(arm['after'])
    assert int(after['nr_throttled'])==int(before['nr_throttled'])==0
    assert arm['before']['cpu.max']==arm['after']['cpu.max']=='200000 100000\n'
    if arm['arm']=='thread':
        assert not health['valid_closed_health']and health['samples']==11 and health['deep_censuses']==1
        failure=read(health['original_health_failure']);assert not failure['writer_thread_alive']and failure['writer_error']is None
        assert len(failure['samples'])==11 and len(failure['actual_status'])==10
        try:engine.replay(job['health_job'],failure['samples'],read(failure['initial_cursors']),read,h)
        except ValueError as error:assert str(error)=='Skipped, reordered or delayed original stream sample';replayed=dict(expected_original_rejection=repr(error),failed_original_requalified=False)
        else:raise AssertionError('Original failed thread arm was incorrectly qualified')
    else:
        assert health['valid_closed_health']and health['error']is None and health['samples']==114 and health['deep_censuses']==5
        original=read(health['original_health_closed']);assert original['writer']['thread_stopped']and original['writer']['all_original_samples_persisted']
        replayed=engine.replay(job['health_job'],original['samples'],read(original['initial_cursors']),read,h,original_statuses=original['actual_status'])
        assert replayed['samples']==114 and replayed['deep_samples']==5 and replayed['maximum_observation_gap_s']==health['maximum_observation_gap_s']<.5
        childpin=h.pin(root/'original-child-identity.json');child=read(childpin)
        assert start['pid']==child['pid']and start['birth']==child['birth']and arm['diagnostic_child_exit0_and_reaped']
        path=Path('/proc',str(child['pid']),'stat');assert not path.exists()or int(path.read_text().rsplit(')',1)[1].split()[19])!=child['birth']
        owner=read(proof['owner']);assert child['parent_pid']==owner['pid']and child['parent_birth']==owner['starttime_ticks']
        assert owner['unit']in child['cgroup']
    results.append(dict(arm=arm['arm'],actual_health=arm['health'],raw_independent_result=replayed,maximum_observation_gap_s=health['maximum_observation_gap_s'],
        six_matched32_authentic_prefix_workloads_verified=True,actual_CPU_quota_throttles_delta=0,all_workload_threads_stopped=True,
        workload_wall_s=[burst['after']['monotonic_s']-burst['before']['monotonic_s']for burst in arm['bursts']]))
monitor=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
proof.update(schema='robotron-original-authentic-prefix-contention-independent-readback-v1',actual_report=reportpin,arms=results,
    interpretation='Under this matched CPU diagnostic the thread arm failed at1.06255s while independent-process sampling closed114/5 with max0.28166s; no quota throttles in either arm. Supports prospective interpreter isolation; not proof of the entire native failure cause or future native reliability.',
    current_main=main,current_main_monitor=monitor,native_observer_IPC_lifecycle_fix_implemented=False,native_game_run=False,
    failed2715_requalified=False,quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False)
pp=h.put(D/'independent-original-matched-prefix-and-raw-arm-closeout.json',proof)
# Correct the earlier design's mislabeled failed_policy field without rewriting
# its sealed bytes: this new design uses the actual policy pin from the job.
design=h.put(D/'prospective-independent-health-interpreter-design-v2.json',dict(schema='robotron-prospective-health-interpreter-design-v2',
    supporting_diagnostic=pp,prior_design_not_overwritten=h.pin(R/'quality32-protected1741-vs-currentLR125-initialReady-firstSave-original01-preparation-20261023/closed-invalid-main-sample-gap-independent-root-original01/next-observer-isolation-design-precommit.json'),
    prior_design_failed_policy_field_was_pair_pin=True,failed_policy=job['failed_policy'],failed_pair=job['failed_pair'],
    required=['Independent interpreter autonomously samples unchanged MainHealth engine at .2s without parent requests controlling capture cadence.',
        'Authenticate source/job/protocol pins and exact parent/child birth, UID and native cgroup; no Torch/CUDA import in health process.',
        'Bounded typed fail-closed IPC with deadlines, sequence and immutable closure receipts; parent death or health failure stops further scientific work.',
        'Actual readiness must close before sidecar/Torch/policy/MAME; preserve every original sample/status and whole-four-leg budgets.',
        'Native close/failure must drain writer, seal originals, independently replay all observations and prove original child normal exit/reaping before scope release.',
        'Keep .5s gap,2s window,192 actors/197 inputs, original game checks, min50/all32/all tails, fixed-reference C1/C2 mean+5%/median gates and native timeout.',
        'Add failed2715 pair/policy and four clocks to future renderer exclusions; genuinely later policy and entirely new original study only after native/protocol tests.'],
    implemented=False,selected_for_scientific_case=False,production_changed=False,quality_qualified=False,created_unix_s=time.time()))
S=R.parent/'state.json';raw=S.read_bytes();s=json.loads(raw);g=s['optimization_goal'];old=read(g['current_recovery_index'])
stage='MATCHED_PREFIX_DIAGNOSTIC_CLOSED_PROCESS114_RAW_PASS_THREAD_GAP_REPRODUCED'
g.update(stage=stage,phase='INDEPENDENT_HEALTH_INTERPRETER_IMPLEMENTATION_NEXT',actual_running_wait=None,all_current_original_handles_terminal=True,
    latest_goal_turn_classification='progress',last_progress='Matched six32-prefix workloads reproduced thread gap1.06255s; isolated interpreter independently closed114 samples/5 censuses, maxgap.28166s, no quota throttles. All original scopes/child lifecycle closed. Implement native IPC/isolation next; no game or speed gain.')
g['future_main_observer_isolation'].update(state='MATCHED_DIAGNOSTIC_INDEPENDENTLY_CLOSED_SUPPORTS_IMPLEMENTATION',design=design,independent_closeout=pp)
g['latest_goal_turn_assessment']=dict(classification='progress',evidence=pp,work=g['last_progress'])
index=dict(old);index.update(previous_recovery_index=g['current_recovery_index'],stage=stage,phase=g['phase'],actual_running_wait=None,all_current_original_handles_terminal=True,
    diagnostic_independent_closeout=pp,diagnostic_job_historical=index.pop('diagnostic_job'),diagnostic_registration_historical=index.pop('diagnostic_registration'),
    prospective_observer_isolation_design=design,current_main_health=main,next_action='Implement bounded authenticated autonomous health-interpreter IPC and native finalization/review integration. Test real subprocess lifecycle/failure paths and raw equivalence, then a native combined-load diagnostic before a genuinely later quality policy/new study. Failed2715 remains invalid; no retry.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-prefix-contention-closed-process114-pass-isolation-next-original01.json',index);g['current_recovery_index']=ip;g['next_action']=index['next_action'];s['updated_unix_s']=time.time()
with(D/'canonical-before-independent-contention-closeout.raw.json').open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==raw;tmp=S.with_name('state.prefix-contention-closed.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==raw;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md';text=doc.read_text();a=text.index('Current optimization recovery:');b=text.index('The native initial baseline')
doc.write_text(text[:a]+'''Current optimization recovery: [Matched contention diagnostic closed; independent observer implementation next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-prefix-contention-closed-process114-pass-isolation-next-original01.json).
All original handles are terminal. No scientific evaluation/diagnostic is running.
Source holds are released. Do not restart any prior study or diagnostic.

Original40336 closed0. Two precommitted25-second diagnostic arms used the same
six bursts of32 authentic producer-prefix verifications. The health thread failed
at sample10 with1.062550306s gap. The separate interpreter closed114 samples/5
censuses, independently replayed exactly, with maxgap0.281661749s. Neither arm
had CPU quota throttles. The failed thread arm's full11 raw samples reproduce
its rejection; it is not requalified. All six actual archives/resources/argv/
pins/releases and the original child normal exit/reaping were independently checked.

This supports implementing an autonomous health interpreter; it does not prove
the whole native failure cause or future native reliability. Authenticated bounded
IPC, actual parent/child lifecycle and native finalization/review integration
remain unimplemented. Keep timing/ownership/game gates unchanged. No game, quality,
learning-speed or useful-throughput gain is established. Main192/197 is healthy.

'''+text[b:])
print(json.dumps(dict(independent_closeout=pp,recovery=ip,next_design=design,main=main)))
