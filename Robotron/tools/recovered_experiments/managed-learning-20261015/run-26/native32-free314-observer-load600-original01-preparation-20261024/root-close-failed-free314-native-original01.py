"""Close original failed load and reviewer; never relaunch either subject."""
import importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023'
D=Path(__file__).resolve().parent
V=D/'independent-failed-live-protocol-raw1006-CPU-original01'
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
h=load(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','_close_h')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_close_r')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_close_a')
c=load(P/'independent_component_closeout_v3.py','_close_c')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
review=read(h.pin(V/'output-original01/report.json'))
assert review['native_live_protocol_failed'] and review['raw_main_health_still_valid'] and not review['native600_load_requirement_achieved']
closure=c.closeout(V,h,arc,read,0)
main=json.loads(subprocess.check_output(['/usr/bin/python3.12','-I','-B',str(R/'currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024/postcapture-current-main-readonly-monitor-v2.py')],text=True))
out=D/'independent-original-failed-native-live-protocol-raw1006-and-scopes-closeout.json'
h.put(out,dict(schema='robotron-original-failed-native-live-protocol-raw1006-closeout-v1',independent_review=h.pin(V/'output-original01/report.json'),independent_review_scope=closure,native_original_exit=1,observer_original_exit=0,samples=1006,deep_samples=39,max_gap_s=.28827953338623047,actual600s_requirement_achieved=False,quality_qualified=False,all_original_results_preserved=True,cause='Retired-inode atomic replacement race suspected; original fstat fields not retained',current_main=main,created_unix_s=time.time()))
S=R.parent/'state.json';before=S.read_bytes()
h.put(D/'canonical-preimage-before-failed-free314-closeout.json',json.loads(before))
s=json.loads(before);g=s['optimization_goal']
g.update(stage='FREE314_NATIVE_LIVE_PROTOCOL_FAILED_INDEPENDENTLY_CLOSED',phase='DETERMINISTIC_ATOMIC_REPLACEMENT_RACE_INVESTIGATION',source_freeze=False,full_source_freeze=False,actual_running_wait=None,all_current_original_handles_terminal=True,current_quality_source_freeze_state='RELEASED_AFTER_FAILED_FREE314_DIAGNOSTIC_AND_ALL_ORIGINAL_CLOSURES',last_progress='Original free314 native failed its live-file check after1006 healthy raw samples/39 deep/maxgap0.288280s; native1/worker0/reviewer0 independently closed. Actual600s requirement failed. No scientific cohort or score. Main192/197 healthy. Investigate real atomic-replace reader race without changing active production.',next_action='Run a new CPU-only deterministic filesystem reproduction of the original live-file reader against its own atomic publisher; retain original failure and immutable finish checks. If reproduced, build prospective live-only snapshot reader and validate strict negative guards before new integration.',latest_goal_turn_progress=dict(classification='progress',evidence=h.pin(out),scientific_qualification=False,created_unix_s=time.time()))
a=g['future_main_observer_isolation']
a['current_free314_native_load']=dict(state='CLOSED_INVALID_EARLY_LIVE_PROTOCOL_FAILURE',original_job=h.pin(D/'job.json'),independent_closeout=h.pin(out),samples=1006,deep_samples=39,max_gap_s=.28827953338623047,actual600_requirement=False,quality_qualified=False)
a['state']='CLOSED_FREE314_NATIVE_PROTOCOL_FAILURE__REPRODUCE_ATOMIC_REPLACE_READER_RACE'
old=R/'current-optimization-recovery-index-20261024-native32-free314-observer-reference600-running-original01.json'
idx=json.loads(old.read_text());idx.update(stage=g['stage'],phase=g['phase'],previous_recovery_index=h.pin(old),actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,current_main_health=main,next_action=g['next_action'],created_unix_s=time.time(),free314_failed_native_independent_closeout=h.pin(out))
new=R/'current-optimization-recovery-index-20261024-free314-native-live-protocol-failed-closed-original01.json';h.put(new,idx)
raw=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(raw)<1048576
assert S.read_bytes()==before;tmp=S.with_name('state.free314-live-protocol-closed.tmp')
with tmp.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
os.replace(tmp,S);fd=os.open(S.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
setup=G/'DELL_SETUP.md';txt=setup.read_text();a=txt.index('Current optimization recovery:');b=txt.index('The native initial baseline closed',a)
text='''Current optimization recovery: [Free314 native live-protocol failure independently closed](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261024-free314-native-live-protocol-failed-closed-original01.json).
Original native37773 exited1, its free314 observer exited0, and independent
review91057 exited0. All original scopes archived/released; no test is running.
The native failed a live-file ownership/type/link check before600s. The observer
retained1006 healthy samples/39 censuses, maxgap0.288280s. This is NOT a600s pass,
quality cohort, score or proven reliability fix. Original failed2739 stays invalid.

Next: reproduce the suspected atomic-replacement race with real filesystem
operations in a bounded CPU-only fixture. The original file descriptor metadata
was not retained, so the exact retrospective failing field remains unproven.
Preserve strict immutable finish checks and all health/game gates. No current
production source, trainer, actor, learning recipe or checkpoint is changed.
Source holds released only after independent actual original closure. Main192/
197 and autosaves remain healthy. No managed save or failed-study retry selected.

'''
setup.write_text(txt[:a]+text+txt[b:])
print(json.dumps(dict(closeout=h.pin(out),recovery=h.pin(new),state_bytes=len(raw),main=main)))
