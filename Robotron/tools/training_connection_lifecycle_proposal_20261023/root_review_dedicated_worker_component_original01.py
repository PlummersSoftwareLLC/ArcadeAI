"""Independently verify component protocol, both actual scopes and all raw data."""
import hashlib,importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
D=R/'dedicated-main-health-protocol-and-live-worker-CPU-original01-preparation-20261023';W=D/'output-original01/worker-original01'
def load(path,name,sha=None):
 if sha:assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_dedicated_review_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_dedicated_review_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_dedicated_review_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
closer=load(P/'independent_component_closeout_v3.py','_dedicated_review_closer')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
parent_scope=closer.closeout(D,h,arc,read,0);worker_scope=closer.closeout(W,h,arc,read,0)
reportpin=h.pin(D/'output-original01/report.json');report=read(reportpin);job=read(h.pin(D/'job.json'))
contract=read(report['pure_protocol_contract']);assert contract['tests']==3 and len(contract['negative_checks'])==38 and contract['synthetic_fixture_fields']
wjp=h.pin(W/'job.json');wj=read(wjp);outcomepin=h.pin(W/'observations/outcome.json');outcome=read(outcomepin)
assert outcome['success']is True and outcome['error']is None and outcome['signals_received']==[]and outcome['all_writer_threads_stopped']is True
assert outcome['job']==wjp and outcome['worker_source']==job['worker']and outcome['protocol_source']==job['protocol_source']
assert outcome['parent']==wj['parent']and outcome['nonce']==wj['nonce']and outcome['failure_report']is None
parent=read(parent_scope['owner']);worker=read(worker_scope['owner']);p=wj['parent'];o=outcome['owner']
assert p['pid']==parent['pid']and p['birth']==parent['starttime_ticks']and p['unit']==parent['unit']and p['invocation_id']==parent['invocation_id']
assert p['source']==job['driver']and p['job']==h.pin(D/'job.json')and p['uid']==1001
assert o['pid']==worker['pid']and o['starttime_ticks']==worker['starttime_ticks']and o['unit']==worker['unit']and o['invocation_id']==worker['invocation_id']and o['uid']==1001
def actual_first(root):return dict(line.split('=',1)for line in(root/'execution-original01/original-first-observed-show-stdout.txt').read_text().splitlines()if '='in line)
pf,wf=actual_first(D),actual_first(W)
assert p['cgroup']==pf['ControlGroup']and o['cgroup']==wf['ControlGroup']and p['cgroup']!=o['cgroup']
assert ' '.join(p['argv'])+' ; ignore_errors=no ;'in pf['ExecStart']and pf['MainPID']==str(p['pid'])and wf['MainPID']==str(o['pid'])
finish=read(report['finish_request']);assert finish['job']==wjp and finish['nonce']==wj['nonce']and finish['parent']==p and finish['action']=='close'
protocol=load(Path(job['protocol_source']['path']),'_dedicated_review_protocol',job['protocol_source']['sha256'])
assert protocol.validate_finish(finish,wjp,wj,finish['created_monotonic_s']+.01)=='close'
initial=report['initial_live'];protocol.validate_live(initial,wjp,wj,o,initial['emitted_monotonic_s']+.01)
assert report['parent_pause_without_capture_requests_s']==2 and report['autonomous_sample_progress']==10
closed=read(outcome['closed_report']);assert closed['writer']['thread_stopped']and closed['writer']['all_original_samples_persisted']
engine_pin=job['health_job']['sources']['full_health_engine'];engine=load(Path(engine_pin['path']),'_dedicated_review_replay',engine_pin['sha256'])
raw=engine.replay(job['health_job'],closed['samples'],read(closed['initial_cursors']),read,h,original_statuses=closed['actual_status'])
assert raw==report['complete_original_raw_replay']and raw['samples']==127 and raw['deep_samples']==5
assert raw['transport']==closed['transport']and raw['maximum_observation_gap_s']<.5
def terminal(root):
 c=read(h.pin(root/'execution-original01/root-original-result-and-owned-release.json'));own=read(h.pin(root/'execution-original01/root-original-identity.json'))
 return arc.archived_closure(c,own,read,exit_zero=True)
pt,wt=terminal(D),terminal(W)
ps,pe=int(pt['ExecMainStartTimestampMonotonic'])/1e6,int(pt['ExecMainExitTimestampMonotonic'])/1e6
ws,we=int(wt['ExecMainStartTimestampMonotonic'])/1e6,int(wt['ExecMainExitTimestampMonotonic'])/1e6
assert ps<ws<=closed['guard_started_monotonic_s']<=raw['first_deep_monotonic_s']<=raw['last_deep_monotonic_s']<=closed['guard_ended_monotonic_s']<=outcome['ended_monotonic_s']<=we<pe
assert wj['parent_started_monotonic_s']<closed['guard_started_monotonic_s']and outcome['ended_monotonic_s']<wj['deadline_monotonic_s']
monitor=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
proof=h.put(D/'independent-original-protocol38-and-autonomous127-raw-both-scopes-closeout.json',dict(schema='robotron-dedicated-observer-component-independent-closeout-v1',
 original_parent_scope=parent_scope,original_worker_scope=worker_scope,actual_report=reportpin,pure_protocol=report['pure_protocol_contract'],tests=3,negative_checks=38,
 worker_job=wjp,worker_outcome=outcomepin,exact_actual_parent_birth_source_job_argv_unit_and_worker_identity_verified=True,
 actual_separate_CPU2_cgroups_verified=True,parent_paused_s=2,autonomous_sample_progress=10,finish=report['finish_request'],
 raw_independent_replay=raw,all127_original_samples_and5_censuses_replayed=True,all_actual_original_archives_resources_argv_pins_and_releases_verified=True,
 parent_worker_controller_normal_exit0_and_reaping_verified=True,original_parent_worker_and_capture_intervals_verified=True,
 current_main=main,current_main_monitor=monitor,native_integration_implemented=False,actual_abort_foreign_finish_parent_death_signal_tests_still_required=True,
 scientific_case_started=False,quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False))
S=R.parent/'state.json';before=S.read_bytes();s=json.loads(before);g=s['optimization_goal'];idx=read(g['current_recovery_index']);previous=g['current_recovery_index']
stage='DEDICATED_CPU_WORKER_PROTOCOL3_NEGATIVES38_AND_REAL_AUTONOMOUS127_RAW_INDEPENDENTLY_CLOSED'
g.update(stage=stage,phase='DEDICATED_OBSERVER_FAILURE_PATHS_AND_NATIVE_INTEGRATION_NEXT',actual_running_wait=None,all_current_original_handles_terminal=True,
 source_freeze=False,full_source_freeze=False,latest_goal_turn_classification='progress',last_progress='Implemented unselected own2CPU observer and typed parent/job/source/nonce/status/finish protocol;3 contracts/38 rejections passed. Real worker captured127/5, advanced10 samples during2s parent pause, and both actual scopes/closures/raw replay independently passed. Failure paths and native integration remain; no game gain.')
g['future_main_observer_isolation'].update(state='IMPLEMENTED_COMPONENT_PROTOCOL_AND_REAL_SEPARATE_SCOPE_INDEPENDENTLY_VALIDATED_NATIVE_INTEGRATION_PENDING',component_job=h.pin(D/'job.json'),component_closeout=proof,
 worker=job['worker'],protocol=job['protocol_source'],native_integration_selected=False)
g['active_diagnostic_job']=dict(state='CLOSED_ORIGINAL_PARENT0_WORKER0',directory=str(D),independent_closeout=proof,scientific_case=False,quality_qualified=False)
g['latest_goal_turn_assessment']=dict(classification='progress',evidence=proof,work=g['last_progress'])
idx.update(previous_recovery_index=previous,stage=stage,phase=g['phase'],actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,
 dedicated_worker_component_closeout=proof,dedicated_worker_source=job['worker'],dedicated_protocol_source=job['protocol_source'],current_main_health=main,
 next_action='Test real owned worker abort/foreign-finish/wrong-parent/signal handling and preserve their actual terminal classifications. Then implement native client/finalizer plus long-scope controller and independent reviewer joins. Keep all timing/copy/ownership/budget/game gates, add failed2715 exclusions, and validate a NEW startup-only actual-load case before a later scientific policy/fresh four-leg study.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-dedicated-worker-protocol38-live127-closed-native-integration-next-original01.json',idx);g['current_recovery_index']=ip;g['next_action']=idx['next_action']
with(D/'canonical-before-dedicated-component-independent-closeout.raw.json').open('xb')as f:f.write(before);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==before;tmp=S.with_name('state.dedicated-component-closed.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==before;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md';text=doc.read_text();a=text.index('Current optimization recovery:');b=text.index('The native initial baseline');doc.write_text(text[:a]+'''Current optimization recovery: [Dedicated observer component independently closed; native integration next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-dedicated-worker-protocol38-live127-closed-native-integration-next-original01.json).
All actual handles are terminal. No scientific evaluation/diagnostic is running.
Source holds released. Do not restart prior studies, diagnostics or component4355.

UNSELECTED autonomous worker and bounded typed control protocol are implemented.
Three pure contracts/38 rejection checks passed. Original4355 parent and its real
worker each used a distinct2CPU/4G/180s/128task scope and closed0. Worker advanced
10 captures during an actual2s parent pause, then closed127 samples/5 censuses.
Every raw sample/status, exact parent/worker births, source/job/argv/unit/nonce,
original intervals, both scopes' six archives/resources/pins/releases and normal
exit/reaping were independently checked. Main192/197 and autosaves remain healthy.

Real abort/foreign finish/wrong parent/signal failure cases are still required.
Native client/finalizer, long-scope controller, reader/preparer/source-family
integration and new actual32 startup-load verification remain unimplemented.
No code is selected for scientific quality yet; no game/playing/learning-speed/
useful-throughput gain is established. Keep .5s gap, max2 copies, original192/197,
whole-case budgets and every original full-game/C1/C2 promotion gate unchanged.

Evidence selecting dedicated CPU allocation: actual native39182 failed a.500260s
gap under quota pressure; its independent external600/24 passed. Fixed cadence
native60582 bounded maxgap.305962s but rejected5 copies of inode359713499, while
external44327 independently replayed600/24 quietly. Both originals/private
resources closed. Actual native uses free-threaded3.14; prior3.12/GIL comparison
does not establish native cause. No failed study or candidate is retried.

'''+text[b:])
print(json.dumps(dict(proof=proof,recovery=ip,main=main)))
