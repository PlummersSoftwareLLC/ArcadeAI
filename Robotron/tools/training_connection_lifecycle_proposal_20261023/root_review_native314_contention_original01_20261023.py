"""Close corrected actual-interpreter diagnostic without inferring a native fix."""
import hashlib,importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023'
D=R/'health-observer-authentic32-prefix-native314-resource12-CPU-original01-preparation-20261023'
def load(path,name,sha=None):
 if sha:assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_native_close_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_native_close_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_native_close_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
ctl=load(P/'control_health_diagnostic_native_resources180_v1.py','_native_close_ctl','384fb9629429cad28187cfa4bb5fc50383c6255211ea31d0d5f393869d29edb8')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
def birth(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
cfgpin=h.pin(D/'controller-config.json');cfg=read(cfgpin);ctl.checked_config(cfgpin['path'])
op=h.pin(D/'execution-original01/root-original-identity.json');owner=read(op);cp=h.pin(D/'execution-original01/root-original-result-and-owned-release.json');closed=read(cp);fields=arc.archived_closure(closed,owner,read,exit_zero=True)
for k,v in dict(CPUQuotaPerSecUSec='12s',MemoryMax=str(16<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='512',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no').items():assert fields[k]==v,(k,fields.get(k))
assert ' '.join(cfg['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']
assert cfg['argv'][:4]==['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B']
for pin in cfg['pins']:assert ctl.pin(pin['path'])==pin
for unit in [owner['unit'],owner['timer']]:assert ctl.show(unit)['LoadState']=='not-found'
assert birth(owner['pid'])!=owner['starttime_ticks']
cg=Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')/owner['unit'];assert not cg.exists()
job=read(h.pin(D/'job.json'));rp=h.pin(D/'output-original01/report.json');report=read(rp);ep=job['health_job']['sources']['full_health_engine'];engine=load(Path(ep['path']),'_native_replay',ep['sha256']);arms=[]
for arm in report['arms']:
 ah=read(arm['health']);assert ah['valid_closed_health']and ah['error']is None and ah['deep_censuses']==5
 interpreter=ah['final_resource']['interpreter'];assert interpreter['free_threading_build']==1 and interpreter['gil_enabled']is False and interpreter['xoptions']=={'gil':'0'}and interpreter['executable']==cfg['argv'][0]
 health=read(ah['original_health_closed']);raw=engine.replay(job['health_job'],health['samples'],read(health['initial_cursors']),read,h,original_statuses=health['actual_status'])
 assert raw['transport']==health['transport']and raw['samples']==ah['samples']and raw['maximum_observation_gap_s']==ah['maximum_observation_gap_s']<.5
 assert health['writer']['all_original_samples_persisted']and health['writer']['thread_stopped']
 assert len(arm['bursts'])==6 and arm['workload_threads_stopped']
 for burst in arm['bursts']:
  assert [row['slot']for row in burst['original32_prefixes']]==list(range(4096,4128))and burst['all_threads_stopped']
  for row,subject in zip(burst['original32_prefixes'],job['prefix_subjects']):h.checked(subject['trace']);assert row['actual_trace_sha256']==subject['trace']['sha256']and row['events']==subject['events']
 def stat(value):return dict(line.split()for line in value['cpu.stat'].splitlines())
 before,after=stat(arm['before']),stat(arm['after']);throttles=int(after['nr_throttled'])-int(before['nr_throttled'])
 assert arm['before']['cpu.max']==arm['after']['cpu.max']=='1200000 100000\n'
 if arm['arm']=='process':
  child=read(h.pin(D/'output-original01/process/original-child-identity.json'));assert arm['diagnostic_child_exit0_and_reaped']and birth(child['pid'])!=child['birth']and child['parent_pid']==owner['pid']and child['parent_birth']==owner['starttime_ticks']and owner['unit']in child['cgroup']
 arms.append(dict(arm=arm['arm'],raw_replay=raw,original_health=arm['health'],actual_interpreter=interpreter,CPU_quota_throttles_delta=throttles,all6x32_original_prefix_workloads_verified=True))
monitor=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-readonly-monitor-v2.py');main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
proof=h.put(D/'independent-original-native314-resource12-raw-and-scope-closeout.json',dict(schema='robotron-native314-contention-corrected-independent-closeout-v1',config=cfgpin,owner=op,closure=cp,original_report=rp,
 all6_actual_original_archives_resources_argv_pins_release_and_child_reaping_verified=True,actual_archive_status=closed['original_archive_status'],arms=arms,current_main=main,
 interpretation='Both actual-native-interpreter arms closed with max gaps .353877/.343002s under12CPU and authentic prefix-only workload. No clear native process-isolation advantage established; prior3.12 fixture cannot establish native GIL cause. Next measure actual Torch/server/32MAME workload and per-stage timing/CPU throttling.',
 no_MAME_game_run=True,observer_isolation_fix_selected=False,quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False))
S=R.parent/'state.json';raw=S.read_bytes();s=json.loads(raw);g=s['optimization_goal'];idx=read(g['current_recovery_index']);previous=g['current_recovery_index'];stage='CORRECTED_NATIVE314_BOTH_ARMS_RAW_VALID_NO_ISOLATION_ADVANTAGE_ESTABLISHED'
g.update(stage=stage,phase='ACTUAL_NATIVE_LOAD_TIMING_DIAGNOSIS_NEXT',actual_running_wait=None,all_current_original_handles_terminal=True,latest_goal_turn_classification='progress',last_progress='Corrected native3.14/free-threaded/12CPU diagnostic independently closed: thread111/5 maxgap.353877s, process112/5 maxgap.343002s; both pass,12 throttles each. Prior3.12 result does not justify native GIL diagnosis. Actual native-load timing/pressure instrumentation next, no game gain.')
g['future_main_observer_isolation'].update(state='NOT_SELECTED_CORRECTED_ACTUAL_INTERPRETER_BOTH_ARMS_PASS',native314_independent_closeout=proof,prior312_native_causal_claim=False)
g['latest_goal_turn_assessment']=dict(classification='progress',evidence=proof,work=g['last_progress'])
idx.update(previous_recovery_index=previous,stage=stage,phase=g['phase'],actual_running_wait=None,all_current_original_handles_terminal=True,native314_independent_closeout=proof,
 diagnostic_job_historical=idx.pop('diagnostic_job'),diagnostic_registration_historical=idx.pop('diagnostic_registration'),current_main_health=main,
 next_action='Prepare a distinct bounded native32 startup-only timing diagnostic, with actual protected reference/Torch/server/MAME and unchanged health gap checks. Record observer stage times and native CPU throttle/pressure; no scientific cohort retry or game-score qualification. Select observer/cadence/resource change only from this evidence.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-native314-both-arms-closed-actual-load-diagnosis-next-original01.json',idx);g['current_recovery_index']=ip;g['next_action']=idx['next_action']
with(D/'canonical-before-corrected-native314-closeout.raw.json').open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==raw;tmp=S.with_name('state.corrected-native314-closed.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==raw;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md';text=doc.read_text();a=text.index('Current optimization recovery:');b=text.index('The native initial baseline');doc.write_text(text[:a]+'''Current optimization recovery: [Corrected actual-interpreter comparison closed; native-load timing next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-native314-both-arms-closed-actual-load-diagnosis-next-original01.json).
All original handles are terminal. No scientific evaluation/diagnostic is running.
Source holds are released. Do not restart prior studies or diagnostics.

Original4577 used actual native3.14.8 free-threaded/-Xgil=0 in BOTH arms and
native12CPU/16G/512tasks, with180s diagnostic bound. Both authentic-prefix/live
health arms passed: thread111 samples/5 censuses maxgap0.353877068s; separate
process112/5 maxgap0.343001604s. Each had12 quota throttles. All raw samples were
independently replayed and all six scope archives/resources/argv/pins/releases
and original child normal exit/reaping verified. This prefix-only test did not
include actual Torch/server/32MAME traffic and establishes no clear native
advantage for interpreter separation.

The earlier40336 comparison used3.12/GIL andCPU2, unlike the native evaluator;
its thread failure/process success cannot establish the native delay cause or
justify a GIL fix. Interpreter separation remains unselected. Next measure
actual native startup load, collector phase times and CPU throttle/pressure in
a new bounded diagnostic. No timing/game gate change, retry or gain claimed.

'''+text[b:])
print(json.dumps(dict(proof=proof,recovery=ip,main=main)))
