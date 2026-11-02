"""Close independent startup review and register the next fresh scientific phase."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023'
B=G/'tools/startup_policy_journal_proposal'
D=R/'native32-dedicated-CPU-observer-startup-original01-preparation-20261023'
V=D/'independent-startup-retained-faults-review-CPU-original01'

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

h=load(B/'run_full_policy_startup_v3.py','_startup_close_h')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_startup_close_reader')
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_startup_close_arc')
closer=load(P/'independent_component_closeout_v3.py','_startup_close_scope')
def read(pin,as_json=True):
    return reader.read_pin(pin,as_json=as_json)

scope=closer.closeout(V,h,arc,read,0)
rp=h.pin(V/'output-original01/report.json')
report=read(rp)
assert len(report['all32_original_prefixes'])==32
assert report['original_raw_replay']['samples']==316 and report['original_raw_replay']['deep_samples']==13
assert report['quality_qualified'] is report['scientific_case'] is report['full_game_validation_performed'] is False
assert report['original_completed_quality_games']==0 and report['original_incomplete_games']==32
assert all(log['terminal_faults_retained'] and not log['full_tail_success'] for log in report['actor_logs'])
job=read(h.pin(V/'job.json'))
prior=[job[key] for key in ('prior_reviewer_defect_closed','prior_postprefix_reviewer_defect_closed','prior_actor_log_reviewer_defect_closed')]
for pin in prior:
    proof=read(pin)
    assert proof['scope']['actual_exit']==1
monitor=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
assert main['client_count']==192 and main['held_inputs']==197 and main['training_enabled'] is True
pp=h.put(D/'independent-original-native32-startup316-and-worker-scope-closeout.json',dict(
    schema='robotron-native32-dedicated-observer-startup-independent-closeout-v1',
    status='ORIGINAL_STARTUP_AND_MONITOR_INTEGRATION_PASS_NO_SCIENTIFIC_RESULT',
    actual_review_scope=scope, original_independent_report=rp,
    failed_review_attempts_preserved=prior, native_and_worker_originals_rerun=False,
    native_original_exit=1, worker_original_exit=0, independent_final_review_original_exit=0,
    all32_prefixes=32, raw_samples=316, physical_censuses=13,
    maximum_observation_gap_s=report['original_raw_replay']['maximum_observation_gap_s'],
    original_cutoff_transport_faults_retained=True, original_completed_quality_games=0,
    all_actual_scope_archives_resources_argv_pins_releases_and_reaping_verified=True,
    current_main=main, current_main_monitor=monitor,
    new_later_frozen_policy_and_four_fresh_scientific_legs_still_required=True,
    quality_qualified=False, playing_gain_verified=False, learning_speed_gain_verified=False,
    production_recipe_changed=False, created_unix_s=time.time()))
S=R.parent/'state.json'
before=S.read_bytes()
state=json.loads(before)
goal=state['optimization_goal']
prior_index=goal['current_recovery_index']
index=read(prior_index)
stage='DEDICATED_NATIVE32_STARTUP_AND_ALL316_RAW_INDEPENDENTLY_CLOSED_FRESH_SCIENCE_NEXT'
goal.update(stage=stage,phase='FRESH_LATER_POLICY_ACQUISITION_WITH_DEDICATED_OBSERVER_SOURCE_FAMILY',
    actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,
    latest_goal_turn_classification='progress',
    last_progress='Actual32 startup prefixes and316 raw samples/13 physical censuses independently verified under separate own2CPU observer; maxgap0.27734s, zero exceptions. Intentional native1 and all cutoff faults retained, worker0 and final reviewer0; original inputs/cleanup/scopes closed. No game score. Next later frozen policy/new four-leg pair.')
goal['future_main_observer_isolation'].update(state='ACTUAL_NATIVE32_STARTUP_AND_DEDICATED_CPU_OBSERVER_INDEPENDENTLY_VALIDATED_READY_FOR_NEW_SCIENTIFIC_SELECTION',
    actual_native_diagnostic_closeout=pp,native_integration_selected=False,quality_qualified=False)
goal['active_diagnostic_job']=dict(state='CLOSED_NATIVE1_WORKER0_REVIEW0_INTENTIONAL_NO_QUALITY',directory=str(D),independent_closeout=pp,scientific_case=False,quality_qualified=False)
goal['latest_goal_turn_assessment']=dict(classification='progress',evidence=pp,work=goal['last_progress'])
next_action='Acquire one genuinely later frozen managed snapshot after a fresh60s unchanged-health prefix; verify saved numerical phase/clocks and publish a new fixed pair/source family using dedicated2CPU observer. Validate selected family, launch four fresh R1/C1/R2/C2 once, no failed-study or candidate retry.'
index.update(previous_recovery_index=prior_index,stage=stage,phase=goal['phase'],actual_running_wait=None,
    all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,
    dedicated_native32_startup_independent_closeout=pp,current_main_health=main,current_main_monitor=monitor,
    next_action=next_action,created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261024-dedicated-native32-startup316-closed-fresh-science-next-original01.json',index)
goal['current_recovery_index']=ip
goal['next_action']=next_action
with (D/'canonical-before-independent-startup316-closeout.raw.json').open('xb') as stream:
    stream.write(before);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
encoded=json.dumps(state,separators=(',',':'),allow_nan=False).encode()
assert len(encoded)<1048576 and S.read_bytes()==before
tmp=S.with_name('state.dedicated-startup316-closed.tmp')
with tmp.open('xb') as stream:
    stream.write(encoded);stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
assert S.read_bytes()==before
os.replace(tmp,S)
fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md'
text=doc.read_text()
a=text.index('Current optimization recovery:')
b=text.index('The native initial baseline')
replacement='''Current optimization recovery: [Native32 startup/316 raw samples closed; fresh science next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261024-dedicated-native32-startup316-closed-fresh-science-next-original01.json).
All original diagnostics and reviews are terminal; source holds released.
Do not restart32192 or prior failed studies/reviews.

Actual32 MAME startup prefixes, full loaded ROM, protected greedy compiled policy,
all316 original health samples/13 physical censuses, separate own2CPU worker,
actual scope intervals/resources/argv/pins/archives/releases and private cleanup
were independently checked. Max observation gap0.277340s, zero exceptions.
The startup-only precommit intentionally stopped unfinished games: native exit1,
all32 cutoff transport/Lua faults and32 incomplete games remain recorded.
Worker and final independent reviewer exited0. Three earlier reviewer defects
are preserved with their original nonzero scope closeouts. No native rerun.

This establishes startup/monitor integration only: zero completed quality games,
no score, promotion, learning-speed or useful-throughput claim. Main192/197,
retained LR125 and normal autosaves continue. Next acquire one later frozen
snapshot, bind the tested dedicated-observer source family into a NEW fixed
pair, validate it, and run four fresh scientific legs with unchanged min50,
all32/full-tail/runtime and independent C1/C2 confirmation gates.

'''
doc.write_text(text[:a]+replacement+text[b:])
print(json.dumps(dict(proof=pp,recovery=ip,current_main=main,state_bytes=len(encoded))))
