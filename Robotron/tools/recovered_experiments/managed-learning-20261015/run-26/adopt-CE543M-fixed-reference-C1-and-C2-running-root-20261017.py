"""Root-only saved-result adoption and read-only live health observation."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import time
import urllib.request

RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
OUT = RUN/'CE543M-quality-fixed-reference-C1-pass-C2-running-root-20261017'
CAMPAIGN = RUN.parent/'quality-448M-vs-CE543M-20261017'
STATE = RUN.parent/'state.json'
assert not OUT.exists()
helper = RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'
assert hashlib.sha256(helper.read_bytes()).hexdigest() == 'd525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'
spec = importlib.util.spec_from_file_location('_root_saved_and_live', helper)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)

def load(path, digest=None):
    raw, pin = ops.read_file(path)
    if digest is not None:
        assert pin['sha256'] == digest, str(path)
    return json.loads(raw), pin

startup, startup_pin = load(RUN/'CE543M-quality-launch-and-C2-startup-root-reviewed1-20261017/actual-parent-C2-all16-main192-source-GPU-and-API.json', 'cf81b9d8156efc863404eb17cf082951c74b5d52f36cb8a849197c02b71410bf')
peer, peer_pin = load(RUN/'CE543M-quality-C2-startup-independent-saved-review-20261017/review-receipt.json', '4125b8d02057a3f883bc46e2bdf9ae6ea853c52365644ff89c669194ed42dea5')
assert peer['status'] == 'SAVED_C2_STARTUP_PASS' and peer['leg'] == 4
r2peer, r2peer_pin = load(RUN/'CE543M-quality-R2-original-rows-and-fixed-reference-C1-independent-saved-review-20261017/review-receipt.json', 'c0c23df2cc878e46a8f5dae813a70e4204beeebaa73b4a8236f3ba6747ac5ff5')
assert r2peer['status'] == 'PASS_INDEPENDENT_SAVED_ORIGINAL_R2_AND_FIXED_FRESH_REFERENCE_C1_GATES'
assert r2peer['actual_plan_sha256'] == '25aaded11bf956b715cc5fb58be1901d236a30444e74253594461f8d11c00d75'
for pin in r2peer['key_artifacts']:
    raw, actual = ops.read_file(pin['path'])
    assert all(actual[key] == pin[key] for key in ('path','sha256','bytes'))
c1accept, c1accept_pin = load(RUN/'CE543M-quality-C1-original-audit-R2-running-root-20261017/root-C1-explicit-narrow-manual-acceptance-R2-running.json', '4565a2cbf5b5eebc6abec1e199ef6525bc420a0bd698b2b80889df0fea5e2d70')
assert c1accept['audit_disposition'] == 'root_accepted_narrow_manual_review'
r2exec, r2exec_pin = load(RUN/'CE543M-quality-original-row-leg03-audit-root-execution-reviewed1-20261017/root-result-review-and-release.json', '03dc463fe5bc9b34d4886431c2c6fba8d85c27dbb1e8467aab7f78e12d66b84c')
assert r2exec['status'] == 'PASS_COMPLETED_LEG_AUDIT' and r2exec['original_exit'] == 0 and r2exec['source_pins_held'] is True
assert r2exec['original_archived_before_release'] is True and all(x['final_load_state'] == 'not-found' for x in r2exec['owned_release'])
r2audit, r2audit_pin = load(RUN/'CE543M-quality-original-row-leg03-audit/review-receipt.json', '960fba8d4892df1b5f9c26bb89708785c25d619b077e8385ddfe0286503f55a3')
assert r2audit['valid'] is True and not r2audit['flagged_console_lines']
receipts, pins = [], []
for index, role in [(1,'reference'),(2,'candidate'),(3,'reference')]:
    value, pin = load(CAMPAIGN/f'{index:02d}-{role}'/'receipt.json')
    assert value['complete'] and value['valid'] and not value['active']
    assert value['count'] == value['started'] == len(value['rows']) >= 50
    assert value['pending'] == value['abandoned'] == 0
    assert {row['client_slot'] for row in value['rows']} == set(range(4096,4112))
    assert all(row['complete'] and row['eligible'] and row['end_unix_s'] <= value['timeout_snapshot_unix_s'] for row in value['rows'])
    receipts.append(value); pins.append(pin)
reference_scores = [row['score'] for receipt in (receipts[0],receipts[2]) for row in receipt['rows']]
candidate_scores = [row['score'] for row in receipts[1]['rows']]
reference = dict(legs=[1,3],count=len(reference_scores),score_sum=sum(reference_scores),mean=statistics.mean(reference_scores),median=statistics.median(reference_scores))
reference.update(required_mean=reference['mean']*1.05, required_mean_exact='63030765/149', full_tails_included=True, historical_rows_used=False, candidate_rows_used=False)
assert (reference['count'],reference['score_sum'],reference['median']) == (149,60029300,424575)
assert reference['mean'] == r2peer['fixed_fresh_reference_pool']['mean']
c1 = dict(leg=2,count=len(candidate_scores),score_sum=sum(candidate_scores),mean=statistics.mean(candidate_scores),median=statistics.median(candidate_scores))
c1.update(mean_gain_percent=(c1['mean']/reference['mean']-1)*100,
    mean_gate_pass=20*c1['score_sum']*reference['count'] >= 21*reference['score_sum']*c1['count'],
    median_gate_pass=c1['median'] >= reference['median'],original_audit_exit=2,
    audit_disposition='root_accepted_narrow_manual_review',root_integrity_acceptance=c1accept_pin)
assert c1['mean_gate_pass'] and c1['median_gate_pass']

# Current original identities are bracketed against the reviewed startup; no restart/control action.
anchor = startup['held_main_anchor']
quality, quality_raw = ops.show(startup['quality_owner']['unit'])
assert quality['MainPID'] == '894289' and quality['InvocationID'] == '4bcb24eb3bb344da9dc67b483a8ee946'
assert quality['ActiveState'] == 'active' and quality['SubState'] == 'running' and quality['NRestarts'] == '0' and quality['Restart'] == 'no'
assert ops.process_start(894289) == 34316549 and ops.process_start(1053703) == 34757703
for owner in (anchor['main_owner'],anchor['fleet_owner']):
    value,_ = ops.show(owner['unit'])
    assert value['MainPID'] == str(owner['pid']) and value['InvocationID'] == owner['invocation_id'] and value['NRestarts'] == '0'
    assert value['ActiveState'] == 'active' and value['SubState'] == 'running'
    assert ops.process_start(owner['pid']) == owner['starttime_ticks']
for actual in [startup['main_process'],*startup['main_actors'],startup['evaluator'],*startup['C2_actors']]:
    assert ops.actual_process(actual,actual['cgroup'].removeprefix('0::')) == actual['mask']
for path,digest in {**anchor['source_hashes'],**anchor['control_hashes'],**anchor['unit_files']}.items():
    assert ops.read_file(path)[1]['sha256'] == digest, path
environment = {part.split(b'=',1)[0].decode():part.split(b'=',1)[1].decode() for part in Path('/proc/620749/environ').read_bytes().split(b'\0') if b'=' in part and part.split(b'=',1)[0].decode().startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_'))}
assert hashlib.sha256(json.dumps(environment,sort_keys=True).encode()).hexdigest() == anchor['environment_sha256']
gpu = ops.command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'])
assert gpu['returncode'] == 0
assert {(int(row.split(',')[0]),row.split(',')[1].strip()) for row in gpu['stdout'].splitlines() if row.strip()} == {(1053703,ops.GPU_UUIDS[0]),(620749,ops.GPU_UUIDS[1])}
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10) as response:
    api_raw=response.read(2<<20)
api=json.loads(api_raw)
assert api['client_count'] == 192 and api['training_enabled'] and not api['measurement_active']
assert api['host_pipeline']['learning_exposure']['optimizer']['process_id'] == 620749
assert all(api['host_pipeline'][k]['errors'] == 0 for k in ('inference','actor_refresh','target_refresh','learner_priority'))
graphs=api['host_pipeline']['inference_graphs']
assert graphs['ready'] and graphs['capture_count'] == 128 and graphs['validation_replay_count'] == 640 and graphs['fallback_count'] == graphs['runtime_capture_count'] == 0 and graphs['fatal_error'] is None
assert api['quality_campaign']['current_leg'] == 4 and not api['quality_campaign']['stale']
campaign_raw, campaign_pin=ops.read_file(CAMPAIGN/'status.json');campaign=json.loads(campaign_raw)
c2raw,c2pin=ops.read_file(CAMPAIGN/'04-candidate/status.json');c2=json.loads(c2raw)
assert campaign['state'] == 'running' and campaign['current_leg'] == 4 and campaign['legs'][3]['pid'] == 1053703
assert c2['active'] and not c2['complete'] and c2['phase'] == 'collecting' and c2['boundary']['acknowledged'] == 16
assert (c2['start_ts'],c2['close_ts']) == (1792256613.7541614,1792257813.7541614)
state_raw,state_pin=ops.read_file(STATE);state=json.loads(state_raw)
assert state['active_quality_job']['plan_sha256'] == campaign['plan_sha256'] == r2peer['actual_plan_sha256']
assert len(state['active_quality_job']['original_leg_audits']) == 2
now=time.time();utc=datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat()
OUT.mkdir()
gate_pin=ops.publish(OUT/'fixed-fresh-reference-and-C1-only-gates.json',dict(
    schema='robotron-root-fixed-fresh-reference-and-single-C1-gates-v1',status='PASS_C1_ONLY_FIXED_REFERENCE_FINAL_C2_PENDING',utc=utc,
    actual_plan_sha256=campaign['plan_sha256'],reference=reference,C1=c1,original_receipts=pins,
    independent_R2_pool_C1_review=r2peer_pin,C2_assessed=False,candidate_qualified=False,promotion=False,
    scope='Same final fresh149 R1+R2 reference is fixed for each candidate separately; no C pooling, retries or old141 reference. C1 original audit2 is preserved with explicit narrow manual integrity acceptance.'))
api_pin=ops.write_bytes(OUT/'actual-main-and-dashboard-API.json',api_raw)
progress_pin=ops.publish(OUT/'root-fixed-reference-C1-pass-C2-running.json',dict(
    status='PASS_FIXED_REFERENCE_C1_ONLY_C2_RUNNING_MAIN192_SOURCE_FREEZE_HELD',observed_utc=utc,
    fixed_reference_and_C1_only_gate=gate_pin,R2_original_audit=r2audit_pin,R2_original_execution=r2exec_pin,R2_independent_review=r2peer_pin,
    C2_startup=startup_pin,C2_startup_independent_review=peer_pin,current_original_evaluator=dict(pid=1053703,starttime_ticks=34757703),
    original_campaign_status=ops.write_bytes(OUT/'actual-campaign-status.json',campaign_raw),
    C2_actual_status=ops.write_bytes(OUT/'actual-C2-status.json',c2raw),
    C2_admission=dict(start=c2['start_ts'],close=c2['close_ts'],started=c2['started'],completed=c2['count'],pending=c2['pending'],abandoned=c2['abandoned']),
    quality_service=ops.publish(OUT/'actual-original-quality-service-show-command.json',quality_raw),
    GPU_owners=ops.publish(OUT/'actual-GPU-owners-command.json',gpu),main_API=api_pin,
    main_learner_frames=api['learner_frame_count'],main192_same_identities=True,source61_control2_unit4_and_environment_held=True,
    source_freeze_released=False,quality_campaign_complete=False,candidate_qualified=False,promotion=False,root_state_before=state_pin))
ops.write_bytes(OUT/'state-before-fixed-reference-and-C2-adoption.json',state_raw)
q=state['active_quality_job'];g=state['optimization_goal']
r2entry=dict(leg=3,role='reference',status='PASS_ORIGINAL_AND_INDEPENDENT_REVIEW',original_evaluator=r2peer['original_evaluator'],
    finished_record=ops.read_file(RUN/'CE543M-quality-original-row-leg03-audit-root-execution-reviewed1-20261017/original-finished-leg.json')[1],
    receipt=pins[2],audit_receipt=r2audit_pin,audit_execution=r2exec_pin,independent_review=r2peer_pin,
    statistics=r2peer['independent_statistics'],completion_tail=r2peer['completion_tail'])
q['original_leg_audits'].append(r2entry)
q.update(current_leg=4,current_evaluator_pid=1053703,current_evaluator_start_ticks=34757703,
    current_admission_start_unix_s=c2['start_ts'],current_admission_close_unix_s=c2['close_ts'],current_phase=c2['phase'],
    latest_runtime_observation=progress_pin['path'],latest_runtime_observation_sha256=progress_pin['sha256'],
    latest_running_wait=progress_pin,last_review_utc=utc,independent_current_C2_startup_review=peer_pin)
state.update(stage='run26_CE543M_C1_PASS_fixed149_reference_C2_collecting_main192',updated_utc=utc,updated_unix_s=now,last_review_utc=utc)
g.update(current_campaign_leg=4,current_campaign_phase='C2_collecting',last_review_utc=utc,last_review_learner_frames=api['learner_frame_count'],
    fixed_reference_and_C1_only_gate=gate_pin,latest_root_progress=progress_pin,actual_running_wait=progress_pin,
    completed_current_campaign_leg_audits=q['original_leg_audits'],
    completed_reference_candidate01_gate=dict(status='PASS_C1_ONLY_FIXED_FRESH_REFERENCE_FINAL_C2_PENDING',campaign=CAMPAIGN.name,reference_pool_final=True,
        fixed_reference=reference,C1=c1,root_gate=gate_pin,qualification_pass=None,C2_assessed=False))
g['completed_leg_audit_preparation'].update(status='R1_ORIGINAL0_C1_MANUAL_ORIGINAL2_PRESERVED_R2_ORIGINAL0_ALL_INDEPENDENT_PASS_C2_RUNNING',actual_leg_audit_executions=3)
g['later_leg_startup_preparation'].update(actual_C2=startup_pin,independent_C2_saved_review=peer_pin)
g['future_batch2048_experiment_preparation'].update(
    reviewed2_phase_CPU_metadata_guards_actual=ops.read_file(RUN/'batch2048-CPU-reviewed2-15-metadata-guards-root-20261017/original-guard-inline-execution.json')[1],
    future_shutdown_parser_guards_actual=ops.read_file(RUN/'interleaved-shutdown-parser12-guards-root-20261017/original-guard-inline-execution.json')[1],
    reviewed2_phase_routing_source_review=ops.read_file(RUN/'batch2048-reviewed2-phase-routing-independent-source-review-20261017/source-review-receipt.json')[1],
    remaining='Reviewed2 routing guards; real producer collector and historical binder; honest phase early-insurance/controller/deadline selection; CE2048 numerical readiness and future root precommit. Unactivated; current full source freeze held.')
assert STATE.read_bytes() == state_raw
payload=(json.dumps(state,indent=2,allow_nan=False)+'\n').encode();assert len(payload)<1<<20
tmp=STATE.with_name('.state-CE543M-fixed149-C2-root.tmp');assert not tmp.exists()
with tmp.open('xb') as stream:
    stream.write(payload);stream.flush();os.fsync(stream.fileno())
os.replace(tmp,STATE);ops.sync_directory(STATE.parent)
ops.publish(OUT/'canonical-adoption.json',dict(status='PASS',progress=progress_pin,fixed_reference_and_C1_gate=gate_pin,state_after=ops.read_file(STATE)[1],no_runtime_mutation=True))
print(json.dumps(dict(status='PASS',fixed_reference=reference,C1=c1,progress=progress_pin,main_learner_frames=api['learner_frame_count'],C2_started=c2['started'],C2_completed=c2['count'])))
