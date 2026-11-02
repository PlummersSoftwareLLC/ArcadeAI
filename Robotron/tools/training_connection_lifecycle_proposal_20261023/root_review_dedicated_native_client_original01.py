"""Independent actual native-shaped client, long worker scope and full raw readback."""
import importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal';D=R/'dedicated-native-client-finalizer-review-longscope-CPU-original01-preparation-20261023'
def load(path,name):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_client_root_h');reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_client_root_reader');arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_client_root_arc');cl=load(P/'independent_component_closeout_v3.py','_client_root_cl')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
scope=cl.closeout(D,h,arc,read,0);jp=h.pin(D/'job.json');job=read(jp);reportpin=h.pin(D/'output-original01/report.json');report=read(reportpin)
family=read(job['source_family_manifest']);protocol=read(job['main_health_protocol']);reviewer=load(Path(family['main_observer']['reviewer']['path']),'_client_root_worker_review')
owner=read(scope['owner']);cfg=read(h.pin(D/'controller-config.json'))
checked=reviewer.verify(job,jp,owner,cfg['argv'],report['observer_lifecycle'],protocol,family,[],read,h)
assert checked==report['independent_worker_review']
life=read(report['observer_lifecycle']);wo=read(life['worker_owner']);wc=read(life['worker_closure']);wf=arc.archived_closure(wc,wo,read,exit_zero=True)
pc=read(scope['closure']);pf=arc.archived_closure(pc,owner,read,exit_zero=True)
assert int(pf['ExecMainStartTimestampMonotonic'])<int(wf['ExecMainStartTimestampMonotonic'])<int(wf['ExecMainExitTimestampMonotonic'])<int(pf['ExecMainExitTimestampMonotonic'])
closed=read(checked['closed_report']);engine=load(Path(protocol['health_job']['sources']['full_health_engine']['path']),'_client_root_engine')
raw=engine.replay(protocol['health_job'],closed['samples'],read(closed['initial_cursors']),read,h,original_statuses=closed['actual_status'])
assert raw==report['complete_original_raw_replay']and raw['transport']==closed['transport']and raw['samples']>=100 and raw['deep_samples']>=5
assert report['finalized']['errors']==[]and report['finalized']['scope_complete']and report['finalized']['watch_stopped']and report['finalized']['writer_stopped']
assert report['all_actual_original_statuses']==len(closed['actual_status'])==len(closed['samples'])
assert report['actual_observer_runtime_scope_s']==9660 and report['actual_capture_s']<40
monitor=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-readonly-monitor-v2.py');main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
pp=h.put(D/'independent-original-client-watch-finalizer-longscope-and-raw-closeout.json',dict(schema='robotron-dedicated-native-client-component-independent-readback-v1',parent_scope=scope,original_report=reportpin,worker_independent_review=checked,
 actual_parent_and_worker_scope_intervals_verified=True,all_actual_scope_archives_resources_argv_pins_release_and_reaping_verified=True,raw_replay=raw,
 initial_ready=report['initial_ready'],initial_baseline=report['initial_baseline'],watch_snapshots=report['watch_snapshots'],all_original_statuses=report['all_actual_original_statuses'],
 actual_long_scope_bound_s=9660,actual_short_component_capture_s=report['actual_capture_s'],not_an_actual9660_second_observation=True,
 current_main=main,native_MAME_template_integration_still_required=True,scientific_case=False,quality_qualified=False,production_changed=False))
S=R.parent/'state.json';before=S.read_bytes();s=json.loads(before);g=s['optimization_goal'];idx=read(g['current_recovery_index']);previous=g['current_recovery_index']
archive=h.put(D/'prior-observer-research-and-component-aliases.json',g['future_main_observer_isolation'])
g['future_main_observer_isolation']=dict(state='CLIENT_FINALIZER_REVIEW_AND_LONG_SCOPE_COMPONENT_INDEPENDENTLY_VALIDATED_NATIVE_TEMPLATE_INTEGRATION_PENDING',prior_research_and_component_alias_archive=archive,
 failure_scope_closeout=h.pin(R/'dedicated-main-health-six-failure-scopes-CPU-original01-preparation-20261023/independent-original-six-failures-eight-scopes-and-signal-readback.json'),client_component_closeout=pp,current_sources=family['main_observer'],finalizer=family['main_health_finalizer'],native_integration_selected=False,quality_qualified=False)
stage='DEDICATED_NATIVE_CLIENT_FINALIZER_REVIEW_LONGSCOPE_AND_RAW_INDEPENDENTLY_CLOSED'
g.update(stage=stage,phase='UNSELECTED_NATIVE_PREPARER_REVIEWER_TEMPLATE_INTEGRATION',actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,latest_goal_turn_classification='progress',last_progress='Real native-shaped client/readiness/status-watch/finalizer and independent scope reviewer passed in own9660s-bounded worker allocation; actual short capture/raw replay and both actual scope intervals/archives/releases verified. Six prior negative cases remain distinct; integrate native templates next, no games or gain.')
g['active_diagnostic_job']=dict(state='CLOSED_ORIGINAL_PARENT0_WORKER0',directory=str(D),independent_closeout=pp,scientific_case=False,quality_qualified=False)
g['latest_goal_turn_assessment']=dict(classification='progress',evidence=pp,work=g['last_progress'])
idx.update(previous_recovery_index=previous,stage=stage,phase=g['phase'],actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,native_client_component_closeout=pp,current_main_health=main,
 next_action='Integrate tested dedicated client/finalizer/reviewer and source pins into NEW unselected native/preparer/reviewer templates and renderer with failed2715 exclusions. Validate source/game-gate/worker-scope negative joins, then a NEW actual32 startup-only diagnostic before a later frozen policy/fresh scientific study.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-dedicated-native-client-longscope-closed-template-integration-next-original01.json',idx);g['current_recovery_index']=ip;g['next_action']=idx['next_action']
with(D/'canonical-before-independent-native-client-closeout.raw.json').open('xb')as f:f.write(before);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==before;tmp=S.with_name('state.dedicated-native-client-closed.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==before;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md';text=doc.read_text();a=text.index('Current optimization recovery:');b=text.index('The native initial baseline');doc.write_text(text[:a]+'''Current optimization recovery: [Native client/long-scope component closed; template integration next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-dedicated-native-client-longscope-closed-template-integration-next-original01.json).
All actual handles are terminal. No scientific evaluation/diagnostic is running.
Source holds released. Do not restart prior studies, diagnostics or95582.

New UNSELECTED dedicated client, status watch, finalizer,9660s signal-aware
controller and independent worker-scope reviewer passed an actual short component.
Client waited for original clean readiness before continuing, status watch stopped
and joined, worker/controller exited0 and reaped, and all original raw statuses
were retained rather than substituting live snapshots. Both actual scopes' six
archives/resources/argv/pins/releases and parent/worker/capture intervals were
independently checked; every raw sample/census replayed. This is a short component,
not an actual9660s observation or native MAME/game proof.

Six actual negative cases/eight scopes and prior3 contracts/38 rejections are
also independently closed, including raw KILL2/9 and missing outcome. Next bind
these tested sources into NEW unselected native/preparer/reviewer templates,
preserve all game/timing/copy/ownership/budget gates, add failed2715 exclusions,
and require a NEW actual32 startup-load diagnostic before any later scientific
policy/study. No playing/learning/useful-throughput gain claimed. Main192/197,
retained LR125 and normal autosaves continue unchanged.

'''+text[b:]);print(json.dumps(dict(proof=pp,recovery=ip,raw_samples=raw['samples'],deep=raw['deep_samples'],main=main)))
