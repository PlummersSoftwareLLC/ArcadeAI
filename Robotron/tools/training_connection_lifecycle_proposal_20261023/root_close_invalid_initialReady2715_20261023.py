"""Independently preserve and close the failed original2715 timing-gap study."""
import fcntl,hashlib,importlib.util,json,os,socket,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023'
T=R/'quality32-protected1741-vs-currentLR125-initialReady-firstSave-original01-preparation-20261023';L=T/'01-reference';O=L/'diagnostic-output-original01';D=R/'currentLR125-initialReady-firstSave-original01-preparation-20261023'
def load(path,name,sha=None):
    if sha:assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_close_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_close_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_close_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None
ownerpin=h.pin(L/'execution-original01/root-original-identity.json');owner=read(ownerpin)
closurepin=h.pin(L/'execution-original01/root-original-result-and-owned-release.json');closure=read(closurepin)
fields=arc.archived_closure(closure,owner,read,exit_zero=False)
assert closure['original_exec_code']==1 and closure['original_exit']==1 and closure['original_result']=='exit-code'
for k,v in dict(Id=owner['unit'],CPUQuotaPerSecUSec='12s',MemoryMax=str(16<<30),MemorySwapMax='0',RuntimeMaxUSec='2h 41min',TasksMax='512',TimeoutStopUSec='30s',KillMode='mixed',SendSIGKILL='no',Restart='no',NRestarts='0').items():assert fields[k]==v,(k,fields.get(k))
cfg=read(h.pin(L/'controller-config.json'));assert ' '.join(cfg['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']
for pin in cfg['pins']:
    actual=h.pin(pin['path']);assert all(actual[k]==pin[k]for k in ['path','sha256','bytes']);assert all(actual['identity'][k]==v for k,v in pin['identity'].items())
for unit in [owner['unit'],owner['timer']]:
    show=subprocess.run(['systemctl','--user','show',unit],check=True,capture_output=True,text=True,timeout=5)
    current=dict(x.split('=',1)for x in show.stdout.splitlines()if '='in x);assert current['Id']==unit and current['LoadState']=='not-found'
assert birth(owner['pid'])!=owner['starttime_ticks']
first_show=(L/'execution-original01/original-first-observed-show-stdout.txt').read_text()
first_fields=dict(line.split('=',1)for line in first_show.splitlines()if '='in line)
assert first_fields['InvocationID']==owner['invocation_id'] and first_fields['MainPID']==str(owner['pid'])
cg=Path('/sys/fs/cgroup'+first_fields['ControlGroup']);assert not(cg/'cgroup.procs').exists()or not(cg/'cgroup.procs').read_text().strip()
resultpin=h.pin(O/'result.json');result=read(resultpin);failure=read(result['main_health_failure'])
assert not result['complete'] and result['all_original_threads_stopped'] and result['original_lease_released'] and result['immutable_inputs_unchanged']
assert result['original_post_origin_child_reap']['all_original_children_reaped']
assert len(result['original_slots'])==32
for slot,row in result['original_slots'].items():assert row['actual_exit']==0 and birth(row['pid'])!=row['birth']
assert failure['observed_samples']==231 and failure['deep_samples']==11 and len(failure['samples'])==231 and len(failure['actual_status'])==230
assert failure['writer_thread_alive']is False and failure['writer_error']is None
samples=[read(pin)for pin in failure['samples']]
assert [x['transport']['index']for x in samples]==list(range(231))
gaps=[(samples[i]['transport']['observed_unix_s']-samples[i-1]['transport']['observed_unix_s'],i)for i in range(1,len(samples))]
assert [(gap,i)for gap,i in gaps if gap>.5]==[(0.5348658561706543,230)]
jobpin=h.pin(L/'job.json');job=read(jobpin);protocol=read(job['main_health_protocol'])
enginepin=protocol['health_job']['sources']['full_health_engine'];engine=load(Path(enginepin['path']),'_close_engine',enginepin['sha256'])
try:engine.replay(failure['health_job'],failure['samples'],read(failure['initial_cursors']),read,h)
except ValueError as error:assert str(error)=='Skipped, reordered or delayed original stream sample';rejection=repr(error)
else:raise AssertionError('Failed full original raw sequence unexpectedly replayed')
receiptpin=result['initial_main_readiness'];receipt=read(receiptpin);loadedpin=h.pin(O/'original-loaded-policy.json');loaded=read(loadedpin);admission=read(h.pin(O/'original-fixed-admission.json'))
assert receipt['original_job']==jobpin and receipt['runtime']==job['runtime'] and receipt['main_health_protocol']==job['main_health_protocol']
assert type(receipt['first_qualified_baseline_index'])is int and receipt['first_qualified_baseline_index']==receipt['unaccepted_initial_samples']==0
assert receipt['first_qualified_baseline_unix_s']==samples[0]['transport']['observed_unix_s']
assert receipt['first_qualified_baseline_unix_s']<=receipt['observed_unix_s']<=loadedpin['identity']['mtime_ns']/1e9<=admission['open_unix_ns']/1e9
assert receiptpin['identity']['mtime_ns']<=loadedpin['identity']['mtime_ns'] and receipt['before_sidecar_Torch_policy_or_MAME']is True
assert loaded['policy']['checkpoint_sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
cohort=result['after_intentional_stop'];assert cohort['count']==0 and cohort['abandoned']==32 and cohort['pending']==0
assert all(not(T/f).exists()for f in ['02-candidate','03-reference','04-candidate'])
seq=read(h.pin(T/'original-fresh-sequence-observer-original01-intent.json'));disp=read(h.pin(T/'display-observer-original-intent.json'))
controller=read(h.pin(L/'controller-original-child.json'));assert birth(seq['pid'])!=seq['birth']and birth(disp['pid'])!=disp['birth']and birth(controller['pid'])!=controller['starttime_ticks']
lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');prior=lease.stat();assert(prior.st_dev,prior.st_ino,prior.st_uid,prior.st_mode&0o777,prior.st_size)==(32,757,1001,0o600,0)
with lease.open('rb')as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);assert lease.stat()==prior;fcntl.flock(f,fcntl.LOCK_UN)
handles=[]
try:
    for port in [19998,*range(20000,20032)]:item=socket.socket();handles.append(item);item.bind(('0.0.0.0',port))
finally:
    for item in handles:item.close()
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader'],check=True,capture_output=True,text=True,timeout=10);assert 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'not in gpu.stdout
monitor=h.pin(D/'postcapture-current-main-readonly-monitor-v2.py');main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
F=T/'closed-invalid-main-sample-gap-independent-root-original01';F.mkdir(mode=0o700)
proof=h.put(F/'readback.json',dict(schema='robotron-invalid2715-original-gap-independent-closeout-v1',native_owner=ownerpin,native_closure=closurepin,
    all6_actual_original_archives_resources_argv_pins_release_and_birth_absence_verified=True,actual_archive_commands=closure['original_archive_status'],
    original_result=resultpin,original_health_failure=result['main_health_failure'],every_raw_sample_replayed=True,raw_sample_count=231,deep_censuses=11,
    first_rejected_sample_index=230,actual_gap_s=0.5348658561706543,limit_s=.5,raw_rejection=rejection,failed_original_not_requalified=True,
    initial_readiness=receiptpin,readiness_before_loaded_policy_and_admission_verified=True,initial_readiness_waiting_exercised=False,
    all32_actual_MAME_exit0_and_reaped=True,all_owned_threads_stopped=True,completed_games=0,abandoned_games=32,C1_R2_C2='NOT_RUN',
    private_GPU0_idle=True,all33_ports_free=True,permanent_lease_unmodified_and_free=True,all_tool_handles_terminal=[83086,75485,97387,1892,49968],
    current_main=main,current_main_monitor=monitor,quality_qualified=False,promotion=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False,
    cause_scope='Observed timing gap is proved; Python GIL/native prefix verification or CPU scheduling contention is a hypothesis requiring a controlled diagnostic.',created_unix_s=time.time()))
design=h.put(F/'next-observer-isolation-design-precommit.json',dict(schema='robotron-prospective-health-observer-isolation-design-v1',
    problem_proof=proof,failed_pair=h.pin(T/'campaign-inputs-and-gates-precommit.json'),failed_policy=job['quality_pair_precommit'],
    hypothesis='Native health sampling shares an interpreter and CPU cgroup with Torch and32 prefix-verification threads; an independent interpreter may reduce observation delays without changing proof limits.',
    required_diagnostic=['Record original per-sample schedule/collection/queue durations and actual CPU quota/pressure; distinguish GIL contention from scheduler/I/O.',
        'Compare thread and independent-process observers under matched authentic prefix-processing workload; preserve all samples, failures, actual clocks and resource scopes.',
        'Require exact typed fail-closed IPC, before-private-setup readiness, owned child lifecycle/reaping, original archives, full raw replay and unchanged shared four-leg budgets.',
        'Keep .5s gap,2s closure, original192 actors/197 sources, game gates and native deadline unchanged; no candidate/evaluation retry.'],
    selected=False,production_changed=False,quality_qualified=False,created_unix_s=time.time()))
S=R.parent/'state.json';raw=S.read_bytes();s=json.loads(raw);g=s['optimization_goal'];assert s['active_quality_job']['directory']==str(T)
for active in [s['active_quality_job'],g['active_quality_job']]:active.update(state='closed_invalid',outcome='invalid',current_leg=1 if active is s['active_quality_job']else'R1',closed_readback=proof,no_retry=True,C1_R2_C2='NOT_RUN')
g.update(stage='INITIALREADY2715_CLOSED_INVALID_SAMPLE_GAP_OBSERVER_ISOLATION_DIAGNOSIS_NEXT',phase='NO_SCIENTIFIC_JOB_RUNNING',actual_running_wait=None,
    all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,current_quality_source_freeze_state='RELEASED_AFTER_ACTUAL_INVALID2715_CLOSURE',
    latest_goal_turn_classification='progress',last_progress='New2715 R1 closed invalid at original sample230 gap0.534865856s>.5s. All231 raw samples reproduced the rejection; zero complete/32 abandoned games; all private children exited0/reaped. Main192/197 healthy. Observer-isolation diagnostic next; no retry or score claim.')
g['current_initialReady_study'].update(state='CLOSED_INVALID_SAMPLE_GAP',closed_readback=proof,protection_forbidden=True)
g['future_initial_owned_main_readiness'].update(state='ACTUAL_NATIVE_BASELINE_AND_BEFORE_POLICY_ORDER_VERIFIED_NEW_CASE_FAILED_LATER_SAMPLE_GAP',scientific_guard_selected=False)
g['future_main_observer_isolation']=dict(design=design,state='DESIGNED_NOT_IMPLEMENTED',quality_qualified=False)
g['latest_goal_turn_assessment']=dict(classification='progress',proof=proof,work=g['last_progress'])
index=read(g['current_recovery_index']);index.update(previous_recovery_index=g['current_recovery_index'],stage=g['stage'],phase=g['phase'],actual_running_wait=None,
    all_current_original_handles_terminal=True,scientific_job_running=False,source_freeze=False,full_source_freeze=False,original_closed_readback=proof,
    initial_baseline_live_readback_historical=index.pop('initial_baseline_live_readback'),current_main_health=main,sequence_actual_exit=1,display_actual_exit=0,
    failed2715_candidate_retried=False,protection_forbidden=True,next_observer_isolation_design=design,
    next_action='Implement a controlled observer-timing diagnosis before selecting any later policy/new study. Keep all timing/ownership/game gates and failed2715 exclusion. No study is running.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-initialReady2715-closed-gap-isolation-next-original01.json',index);g['current_recovery_index']=ip;g['next_action']=index['next_action']
with(F/'canonical-before-invalid-closeout.raw.json').open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==raw;tmp=S.with_name('state.initialReady2715-closed.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==raw;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
# Truthful terminal dashboard projection; later roles were never launched.
status=T/'status.json';projection=json.loads(status.read_text());projection.update(state='finished',outcome='invalid',reason='R1 original main sample gap0.534865856s>.5s; zero complete games. C1/R2/C2 not run.',updated_unix_s=time.time())
for i,leg in enumerate(projection['legs']):leg['state']='failed'if i==0 else'not_run'
with (F/'dashboard-status-before-terminal-correction.raw.json').open('xb')as f:f.write(status.read_bytes());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
tmp=status.with_name('status.closed-original01.tmp')
with tmp.open('x')as f:json.dump(projection,f,separators=(',',':'));f.flush();os.fsync(f.fileno())
os.replace(tmp,status)
doc=G/'DELL_SETUP.md';text=doc.read_text();a=text.index('Current optimization recovery:');b=text.index('The original maximum resource fixture')
doc.write_text(text[:a]+'''Current optimization recovery: [Original2715 closed invalid; observer timing diagnosis next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-initialReady2715-closed-gap-isolation-next-original01.json).
All actual handles are terminal. No scientific evaluation is running; source
holds are released. Do not restart sequence83086/display75485 or this candidate.

The native initial baseline closed at raw index0, and its receipt precedes the
loaded reference policy and game admission. The later sample230 had a0.534865856s
gap, exceeding the unchanged0.5s limit. All231 raw samples/11 censuses reproduce
the original rejection. Zero completed/32 abandoned games give no score.
C1/R2/C2 were not run. Actual six archive outcomes/resources/argv/pins/releases
were checked; all32 MAME exited0/reaped, all threads stopped, GPU0/33 ports and
the unchanged permanent lease are free. Main192/197, LR125 and autosaves healthy.

The next controlled diagnostic will distinguish interpreter contention from CPU
scheduling/I/O and assess an independent health-observer interpreter. This is a
hypothesis/design, not an implemented fix. Keep all original timing and game
proof limits; do not retry this2715 policy/pair or rescue failed results.

'''+text[b:])
print(json.dumps(dict(closed_readback=proof,recovery=ip,next_design=design,main=main)))
