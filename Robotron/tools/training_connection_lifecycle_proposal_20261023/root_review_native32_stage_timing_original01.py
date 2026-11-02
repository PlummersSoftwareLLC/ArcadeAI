"""Independently close native startup timing and the simultaneous external guard."""
import fcntl,hashlib,importlib.util,json,os,socket,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023'
D=R/'native32-startup-only-main-timing-original01-preparation-20261023';A=D/'paired-external-full-health120-original01';O=D/'diagnostic-output-original01'
def load(path,name,sha=None):
 if sha:assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_stage_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_stage_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_stage_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
ctl=load(P/'control_native_startup_timing_diagnostic180_v1.py','_stage_ctl','ee321ea6370931a20c2ce4ee26f097d64d070defb83a5bac8b64f913508e1107');closer=load(P/'independent_component_closeout_v3.py','_stage_closer')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
def birth(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
op=h.pin(D/'execution-original01/root-original-identity.json');owner=read(op);cp=h.pin(D/'execution-original01/root-original-result-and-owned-release.json');closure=read(cp);cfgpin=h.pin(D/'controller-config.json');cfg=read(cfgpin)
ctl.checked_config(cfgpin['path']);fields=arc.archived_closure(closure,owner,read,exit_zero=False)
assert closure['original_exec_code']==1 and closure['original_exit']==1 and closure['original_result']=='exit-code'
for k,v in dict(CPUQuotaPerSecUSec='12s',MemoryMax=str(16<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='512',TimeoutStopUSec='30s',KillMode='mixed',SendSIGKILL='no',Restart='no').items():assert fields[k]==v,(k,fields.get(k))
assert ' '.join(cfg['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']
for pin in cfg['pins']:assert ctl.pin(pin['path'])==pin
for unit in [owner['unit'],owner['timer']]:assert ctl.show(unit)['LoadState']=='not-found'
assert birth(owner['pid'])!=owner['starttime_ticks']
assert not(Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')/owner['unit']).exists()
rpin=h.pin(O/'result.json');r=read(rpin);assert r['schema']=='robotron-startup-only-native32-timing-diagnostic-result-v1'and r['diagnostic_only']and not r['complete']
assert r['all_original_threads_stopped']and r['original_lease_released']and r['immutable_inputs_unchanged']and r['original_post_origin_child_reap']['all_original_children_reaped']
assert len(r['original_slots'])==32
for row in r['original_slots'].values():assert row['actual_exit']==0 and birth(row['pid'])!=row['birth']
failure=read(r['main_health_failure']);assert failure['observed_samples']==188 and failure['deep_samples']==9 and len(failure['actual_status'])==187 and not failure['writer_thread_alive']
assert len(failure['samples'])==188 and failure['writer_error']is None
enginepin=failure['health_job']['sources']['full_health_engine'];engine=load(Path(enginepin['path']),'_stage_engine',enginepin['sha256'])
try:engine.replay(failure['health_job'],failure['samples'],read(failure['initial_cursors']),read,h)
except ValueError as error:assert str(error)=='Skipped, reordered or delayed original stream sample'
else:raise AssertionError('Rejected original unexpectedly replayed successfully')
samples=[read(pin)['transport']for pin in failure['samples']];assert [v['index']for v in samples]==list(range(188))
gap=samples[-1]['observed_unix_s']-samples[-2]['observed_unix_s'];assert gap==0.5002601146697998
timings=read(r['collector_diagnostic_timing'])['records'];assert len(timings)==188
for sample,record in zip(samples,timings):
 assert record['index']==sample['index']and record['before']['unix_s']<=sample['observed_unix_s']<=record['after']['unix_s']
 assert record['before']['gil_enabled']is record['after']['gil_enabled']is False
 assert record['before']['pid']==record['after']['pid']==owner['pid']and owner['unit']in record['before']['cgroup']
last=timings[-1];previous=timings[-2]
def stat(value):return dict(line.split()for line in value['cpu_stat'].splitlines())
before,after=stat(last['before']),stat(last['after']);delta=int(after['nr_throttled'])-int(before['nr_throttled']);assert delta==3
fd=next(stage for stage in last['stages']if stage['name']=='all384_FD_ownership')
decomposition=dict(previous_post_observation_proof_s=previous['after']['unix_s']-samples[-2]['observed_unix_s'],
 full_wait_after_previous_finished_s=last['before']['unix_s']-previous['after']['unix_s'],current_before_observation_collection_s=samples[-1]['observed_unix_s']-last['before']['unix_s'])
assert abs(sum(decomposition.values())-gap)<1e-6
external_scope=closer.closeout(A,h,arc,read,0);externalpin=h.pin(A/'output-original01/report.json');external=read(externalpin)
assert len(external['samples'])==600 and external['deep_samples']==24 and external['writer']['thread_stopped']
external_raw=engine.replay(external['health_job'],external['samples'],read(external['initial_cursors']),read,h,original_statuses=external['actual_status'])
assert external_raw['transport']==external['transport']and external_raw['maximum_observation_gap_s']<.5
started=int(fields['ExecMainStartTimestampMonotonic'])/1e6;ended=int(fields['ExecMainExitTimestampMonotonic'])/1e6
assert external['guard_started_monotonic_s']<=started<ended<=external['guard_ended_monotonic_s']
lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');prior=h.pin(lease);assert prior['identity']['inode']==757 and prior['identity']['device']==32 and prior['bytes']==0
with lease.open('rb')as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);assert h.pin(lease)==prior;fcntl.flock(f,fcntl.LOCK_UN)
socks=[]
try:
 for port in [19998,*range(20000,20032)]:s=socket.socket();socks.append(s);s.bind(('127.0.0.1',port))
finally:
 for s in socks:s.close()
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader'],check=True,capture_output=True,text=True,timeout=10);assert 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'not in gpu.stdout
monitor=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-readonly-monitor-v2.py');main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
pp=h.put(D/'independent-original-native-gap-stages-and-external600-closeout.json',dict(schema='robotron-native32-startup-timing-and-external-health-independent-closeout-v1',
 native_config=cfgpin,native_owner=op,native_closure=cp,actual_native_exit=1,all6_actual_native_archives_resources_argv_pins_release_verified=True,actual_native_archive_status=closure['original_archive_status'],native_result=rpin,
 every_native_raw_sample_reproduced_original_rejection=True,native_samples=188,native_deep=9,failed_sample=187,actual_gap_s=gap,gap_limit_s=.5,gap_decomposition=decomposition,
 GIL_disabled_in_every_actual_native_sample=True,quota_throttled_periods_during_failing_capture=delta,failing_FD_scan_wall_s=fd['end_monotonic_s']-fd['start_monotonic_s'],failing_FD_scan_thread_CPU_s=fd['thread_CPU_s'],
 original_stage_timings=r['collector_diagnostic_timing'],external_original_scope=external_scope,external_report=externalpin,external_raw_replay=external_raw,
 external_capture_covers_entire_actual_native_interval=True,all32_actual_MAME_exit0_and_reaped=True,all_owned_threads_stopped=True,private_GPU0_idle=True,all33_ports_free=True,permanent_lease_unmodified_and_free=True,
 original_all32_prefix_stop_not_reached=True,scientific_study=False,failed2715_requalified=False,current_main=main,quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False))
choice=h.put(D/'next-fixed-cadence-diagnostic-selection.json',dict(schema='robotron-evidence-backed-native-cadence-diagnostic-selection-v1',evidence=pp,
 selected_prospective_change='Schedule next native health observation relative to the previous capture start; include capture/proof time in the .2s period instead of waiting an extra full .2s after completion.',
 rationale='Actual gap decomposes into previous proof time +full post-proof wait +next collection under quota pressure. The already fixed-cadence external observer independently remained valid across the entire native interval. Test cadence as a single factor before adding a separate scientific observer scope.',
 next_case='New bounded startup-only diagnostic, original resource/backend/reference/32actor/health limits unchanged; no game-score use or failed cohort retry.',
 native_worker_isolation_not_selected=True,timing_limit_changed=False,production_changed=False,quality_qualified=False,created_unix_s=time.time()))
S=R.parent/'state.json';raw=S.read_bytes();s=json.loads(raw);g=s['optimization_goal'];idx=read(g['current_recovery_index']);previous_index=g['current_recovery_index'];stage='ACTUAL_NATIVE_QUOTA_GAP_REPRODUCED_EXTERNAL600_VALID_FIXED_CADENCE_TEST_NEXT'
g.update(stage=stage,phase='CONTROLLED_NATIVE_CADENCE_CHANGE_DIAGNOSTIC_PREPARATION',actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,
 latest_goal_turn_classification='progress',last_progress='Actual native3.14 startup diagnostic reproduced gap.500260s with GIL disabled/3 quota-throttled periods; same interval external600/24 full raw replay passed. Gap includes previous proof +full.2s wait +next scan; fixed-cadence single-factor diagnostic next. No game gain.')
g['active_diagnostic_job'].update(state='CLOSED_ORIGINAL_NATIVE1_EXTERNAL0',independent_closeout=pp)
g['future_main_observer_isolation'].update(state='NOT_SELECTED_FIXED_CADENCE_SINGLE_FACTOR_TEST_FIRST',actual_native_timing_closeout=pp,next_selection=choice)
g['latest_goal_turn_assessment']=dict(classification='progress',evidence=pp,work=g['last_progress'])
idx.update(previous_recovery_index=previous_index,stage=stage,phase=g['phase'],actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,
 actual_native_stage_closeout=pp,next_cadence_diagnostic_selection=choice,current_main_health=main,next_action='Prepare NEW startup-only native diagnostic changing only health-watch cadence. Keep actual GIL-disabled interpreter,12CPU/16G/512 tasks, protected policy, all192/197/transport/game predicates. Compare actual quota/timing and require original cleanup; no failed study retry.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-native-gap-quota-external600-closed-cadence-next-original01.json',idx);g['current_recovery_index']=ip;g['next_action']=idx['next_action']
with(D/'canonical-before-native-timing-independent-closeout.raw.json').open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==raw;tmp=S.with_name('state.native-stage-closed.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==raw;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md';text=doc.read_text();a=text.index('Current optimization recovery:');b=text.index('The native initial baseline');doc.write_text(text[:a]+'''Current optimization recovery: [Actual native timing closed; fixed-cadence diagnostic next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-native-gap-quota-external600-closed-cadence-next-original01.json).
All original handles are terminal. No scientific evaluation/diagnostic is running.
Source holds released. No old study or diagnostic is to be relaunched.

Startup-only native39182 closed1 on actual main sample187 gap0.500260115s>.5s.
All188 raw samples/9 censuses reproduce the rejection. GIL was disabled in every
timing record; failing capture crossed3 quota-throttled periods. The full384-FD
scan took0.205346s wall/0.026780s thread CPU. Gap decomposition includes previous
proof completion, a full extra.2s wait and next collection. The simultaneous
external56368 observer closed0,600 samples/24 censuses, independently replayed
all data and covered the whole actual native interval without a gap failure.
Both actual scope archives/resources/argv/pins/releases, all32 MAME exit0/reaping,
all threads, free private GPU0/33 ports and unchanged lease were checked.

Next test only a fixed native observation period that includes collection/proof
time, rather than adding a full period after completion. Keep .5s gap and all
ownership/runtime/game gates. A new startup-only diagnostic must validate this
single change before selecting any later scientific study. Separate observer
scope remains unselected; no GIL, score, learning-speed or throughput gain claim.
Main192/197, retained LR125 and normal autosaves continue unchanged.

'''+text[b:])
print(json.dumps(dict(proof=pp,recovery=ip,next_choice=choice,main=main)))
