"""Close original maximum-scope evidence and precommit one genuinely later save."""
import copy, hashlib, importlib.util, json, os, subprocess, time
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron'); R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023'; B=G/'tools/startup_policy_journal_proposal'
D=R/'currentLR125-initialReady-firstSave-original01-preparation-20261023'
def load(path,name,sha=None):
    raw=Path(path).read_bytes()
    if sha: assert hashlib.sha256(raw).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
h=load(B/'run_full_policy_startup_v3.py','_fresh_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_fresh_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
def read(pin,as_json=True): return reader.read_pin(pin,as_json=as_json)
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_fresh_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
closer=load(P/'independent_component_closeout_v3.py','_fresh_close')
scope=R/'initial-readiness-fullscope-CPU-original01-preparation-20261023'
proof=closer.closeout(scope,h,arc,read,0); report=read(h.pin(scope/'output-original01/report.json'))
assert report['tests']==2 and report['actual_original_replays'][0]['exact_original_closed_engine4_replay']
resource=report['explicit_synthetic_resource_scaling']
assert resource['samples']==48332 and resource['final_case_groups']==8192 and resource['initial_readiness_groups']==4
assert resource['recomputed_budget']['total_exception_groups']==1024
assert resource['actual_elapsed_s']<600 and resource['actual_peak_resident_KiB']<512*1024
assert resource['all_generated_records_explicitly_synthetic'] and resource['real_native_observation'] is False
for name in ['join_equivalence_proof','source_equivalence_proof','initial_readiness_component']: read(report[name])
combined=R/'initial-readiness-native-family-CPU-original01-preparation-20261023/independent-original-native-order-and-live600-raw-readback.json'
read(h.pin(combined))
proof.update(schema='robotron-initial-readiness-maximum-scope-independent-closeout-v1',actual_report=h.pin(scope/'output-original01/report.json'),
    actual_metrics=resource,prior_native_and_live_raw_closeout=h.pin(combined),real_native_game_execution=False,
    quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False)
proofpin=h.put(scope/'independent-original-fullscope-and-readiness-closeout.json',proof)
old=R/'currentLR125-dynamicProc-firstSave-original01-preparation-20261023'
monitor=h.pin(old/'postcapture-current-main-readonly-monitor-v2.py')
main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=30).stdout)
assert main['client_count']==192 and main['training_enabled'] and main['held_inputs']==197
assert main['learner_frame_count']>2700401151 and main['training_steps']>10721482 and main['optimized_samples']>42339395584
D.mkdir(mode=0o700)
health=read(h.pin(R/'owned-main-initial-readiness120-v4-original01-preparation-20261023/job.json'))
health['output']=str(D/'output-original01/prefix'); health['duration_s']=60
assert health['binding']==h.pin(old/'postcapture-current-main-binding.json')
assert health['initial_readiness_protocol']==dict(schema='robotron-bounded-initial-owned-readiness-v1',max_wait_s=2.,max_samples=11)
healthpin=h.put(D/'selected-prefix-health-inputs.json',health)
tag='currentLR125_initialReady_firstSave_original01_20261023'
selection=h.put(D/'first-later-policy-selection-precommit.json',dict(
    schema='robotron-owned-initial-readiness-first-save-selection-v1',tag=tag,
    after_learner_frame_count=main['learner_frame_count'],current_main_monitor=monitor,current_main=main,
    required_prefix_s=60,closed_maximum_scope=proofpin,prior_native_and_live_raw_closeout=h.pin(combined),
    old2700_study=h.pin(R/'quality32-protected1741-vs-currentLR125-dynamicProc-firstSave-original01-preparation-20261023/closed-invalid-initial-proc-repeat-independent-root-original01/readback.json'),
    old_candidate_retried=False,original_attempt=1,no_retry=True,learning_settings_changed=False,quality_qualified=False,created_unix_s=time.time()))
job=read(h.pin(old/'job.json')); job.update(output=str(D/'output-original01'),tag=tag,
    after_learner_frame_count=main['learner_frame_count'],engine=health['sources']['full_health_engine'],health_job=healthpin,binding=health['binding'],selection=selection)
jobpin=h.put(D/'job.json',job)
cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_fresh_cpu','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14')
oldcfg=read(h.pin(old/'controller-config.json')); argv=oldcfg['argv'][:]
argv[argv.index('--job')+1]=jobpin['path'];argv[argv.index('--job-sha256')+1]=jobpin['sha256']
pins=list(health['sources'].values())+[health['binding'],healthpin,selection,jobpin,job['driver'],proofpin]
cfg=dict(unit='robotron-currentLR125-initialReady-firstSave-original01-20261023.service',output=str(D/'execution-original01'),
    argv=argv,properties=oldcfg['properties'],pins=[cpu.pin(v['path']) for v in pins],observation_s=240)
cfgpin=h.put(D/'controller-config.json',cfg)
# Preserve the complete preimage, then publish a bounded, byte-CAS state update.
state=R.parent/'state.json'; raw=state.read_bytes(); s=json.loads(raw); g=s['optimization_goal']
with (D/'canonical-state-before-readiness-save-preparation.raw.json').open('xb') as f:
    f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
stage='READINESS_ALL_CPU_RESOURCE_AND_RAW_VALIDATIONS_CLOSED_FRESH_SAVE_PREPARED'
g.update(stage=stage,actual_running_wait=None,all_current_original_handles_terminal=True,
    latest_goal_turn_classification='progress',next_action='Launch only the newly precommitted initialReady first-save capture; after its actual closure verify the exact completed-slot transition and numerical CPU state, then bind a genuinely new fixed pair/source family. All failed studies remain invalid.',
    latest_progress='Readiness maximum synthetic48332/8192/1024 resource scope independently closed0, actual528.2729s/101376KiB; real600 raw replay exact. New later one-save selection prepared; no quality gain.',
    latest_goal_turn_assessment=dict(classification='progress',proof=proofpin,work='Independent original maximum-scope closure and next fresh managed-save precommit; no quality or speed claim.'))
g['future_initial_owned_main_readiness'].update(state='ALL_CONTRACTS_LIVE_RAW_AND_MAXIMUM_RESOURCE_VALIDATED',maximum_scope_closeout=proofpin)
g['active_continuation_capture']=dict(state='PREPARED_NOT_RUNNING',directory=str(D),job=jobpin,controller_config=cfgpin,selection=selection)
oldindex=read(g['current_recovery_index']); index=copy.deepcopy(oldindex)
index.update(stage=stage,phase='FRESH_LATER_POLICY_SAVE_PREPARATION',previous_recovery_index=g['current_recovery_index'],actual_running_wait=None,
    all_current_original_handles_terminal=True,current_main_health=main,closed_maximum_scope=proofpin,active_readonly_diagnostic=None,
    next_action=g['next_action'],fresh_save_preparation=g['active_continuation_capture'],created_unix_s=time.time())
indexpin=h.put(R/'current-optimization-recovery-index-20261023-readiness-all-pass-fresh-save-prepared-original01.json',index)
g['current_recovery_index']=indexpin; s['updated_unix_s']=time.time()
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode(); assert len(encoded)<1048576
assert state.read_bytes()==raw
tmp=state.with_name('state.readiness-save-prepared-original01.tmp')
with tmp.open('xb') as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert state.read_bytes()==raw; os.replace(tmp,state)
fd=os.open(state.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md'; text=doc.read_text(); split=text.index('## Historical2700 closure')
top='''# Dell GB300 Robotron setup

Current optimization recovery: [All readiness/resource validations closed; fresh later save prepared](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-readiness-all-pass-fresh-save-prepared-original01.json).
All previous original handles, including resource benchmark19744, are terminal.
No scientific evaluation is running. The new initialReady first-save capture is
prepared and has not been launched. Read canonical state for a newer live handle.

The original maximum resource fixture closed0 and its six actual archives,
resources, argv, source pins and owned releases were independently checked.
It reviewed48,332 synthetic observations with8192 groups/1024 exceptions,
including four readiness groups, in528.2729s with101376KiB peak resident memory.
Its real600-sample engine4 replay exactly matched the closed independent review.
Synthetic observations are not actual9660s game evidence or throughput gains.

Readiness component7 tests/27 rejections and native/template8 tests/40 rejections
passed. Native first baseline must close before sidecar/Torch/policy/MAME setup;
the typed receipt is independently joined to original raw observations and clocks.
Full original game/runtime gates and both independent+5% mean/preserved median
confirmations remain unchanged. No MAME/game has yet run with these new sources.

Main3615927,192 actors and197 held inputs remain healthy at retained LR125,
normal autosaves, no restore/replay reset. Next capture one genuinely later policy,
verify its numerical CPU state, and bind an entirely fresh four-leg study. Failed
2630/2690/2700 originals remain invalid; their candidates are not retried.

'''
doc.write_text(top+text[split:])
print(json.dumps(dict(closeout=proofpin,controller_config=cfgpin,recovery=indexpin,canonical_bytes=len(encoded))))
