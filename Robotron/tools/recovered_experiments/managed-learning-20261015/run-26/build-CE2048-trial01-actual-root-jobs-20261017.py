"""Bind one actual CE2048 trial. Readonly preparation; never arm or start here."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import sys

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
RUN = GAME/'logs/managed-learning-20261015/run-26'
OUT = RUN/'CE2048-trial01-final-root-preparation-20261017'
Q = GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
SRC = Q/'batch2048_one_trial_execution_release_reviewed2_proposal'
INS = RUN/'preCE2048-insurance-20261017T180010Z-root-acquisition'
sys.path.insert(0,str(GAME/'tools'))
sys.dont_write_bytecode = True

def load(path,digest,name):
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location(name,path)
    value = importlib.util.module_from_spec(spec);sys.modules[name] = value
    spec.loader.exec_module(value)
    return value

adapter = load(SRC/'run_CE_batch_transition.py','479b4b4da50de7c78cb94a730a12a4603e3e6c2281fffac1533a5a4a22822202','root_actual_CE2048_adapter')
base = adapter.load_v4()
def pin(path):
    return base.fingerprint(Path(path))
def save(path,value):
    return base.publish(Path(path),value)
def read(path):
    return json.loads(Path(path).read_text())

known = read(RUN/'CE2048-live-trial-root-field-matrix-source-preparation-20261017/known-sources-and-actual-evidence.json')
addendum = read(RUN/'CE2048-live-trial-selected-release-reviewed2-addendum-20261017/selected-sources-addendum.json')
selected = known['selected_sources']
selected.update(addendum['selected_sources_override'])
for key,value in list(selected.items()):
    actual = pin(value['path'])
    assert all(actual[field] == value[field] for field in ('path','sha256','bytes'))
    selected[key] = actual
old = read(RUN/'rawKL-trial02-final-root-preparation-20261017/activation-job-FINAL.json')
before = read(OUT/'actual-before-current620749-main192.json')
primitives = base.load_module(old['helper_pins']['live_host']['path'],'root_actual_CE2048_host')
class Host(primitives.LiveHost):
    def runtime_dropin(self):
        return Path(old['original_dropin']['path'])
host = Host(old['trainer_unit'],old['fleet_unit'])
assert host.describe() == before, 'Actual owner/source/unit/control binding changed since capture'
host.adopt_initial(before);host.metric_host.configure_logs(before['bindings']['logs'])
fresh = host.capture()
plan = dict(batch_size=4096,replay_cap=8,initial_snapshot=dict(csv=fresh['csv']),exposure_identity={name:primitives.metrics.exposure_key(fresh['exposure'][name]) for name in ('optimizer','replay')})
assert not primitives.metrics.api_issues(fresh,plan) and fresh['client_count'] == 192
masks = read(OUT/'actual-original192-and-worker-masks.json')
assert all(sorted(os.sched_getaffinity(int(pid))) == mask for pid,mask in masks['actors'].items())
assert host.metric_host.mask(before['bindings']['worker']) == masks['worker']
insurance = pin(INS/'CPU-root-preparation/insurance-CPU-readonly-report.json')
verifier = read(INS/'CPU-root-preparation/current-verified-python-binding-and-context.json')['verifier']
base.validate_python_binding(verifier,insurance,hash_executable=True)
profile = pin(Q/'batch2048_profile_horizon_proposal/profile.json')
prerequisite = pin(RUN/'CE2048-private-readiness-actual-proof-inputs-root-20261017/actual-execution-prerequisites.json')
protected = pin(GAME/'models_dqn/managed-incumbents/freshCE-543M-confirmed.pt')
assert protected['sha256'] == '8b86546355ade166937a8287a008c7854276ed773a103eb815287dde00d6fb7e'
source_peer = pin(RUN/'batch2048-execution-release-reviewed2-independent-runtime-source-review-20261017/source-review-receipt.json')
guard = pin(RUN/'batch2048-execution-release-reviewed2-8-guards-root-20261017/original-guard-inline-execution.json')
assert read(guard['path'])['exit_code'] == 0 and read(guard['path'])['guard_count'] == 8
policy = dict(schema='robotron-one-CE2048-root-policy-v1',trial_id='CE_batch2048_efficacy_20261017_trial01',
    authorization='One controlled trial under the active continuous improvement Goal; no automatic retry or relaxed confirmation.',
    hypothesis='At fixed sample reuse cap, smaller batches provide more Adam update opportunities per admitted sample. Efficacy and useful speed remain unproven.',
    only_deliberate_change=dict(before_batch=4096,treatment_batch=2048,return_batch=4096,metric='ce',LR_compensation=False),
    held_recipe=read(profile['path'])['held_recipe_context'],
    horizon=dict(min_learner_action_frames=8000000,min_all_five_origin_accepted_physical_writes=6000000,operator='AND',selection='First durable original LATCH; no peak selection, extension or retry'),
    deadlines=dict(durable_LATCH_s=3240,independent_stop_intent_s=3310,exact_owner_absent_by_s=3600,origin='Actual owned treatment start request on the same boot'),
    candidate_and_return='One model-only save at the first eligible LATCH; exact treatment owner retirement, one candidate CPU proof, then newest stopped CPU proof at max(early,LATCH,candidate) clocks. Return4096 from actual newest; never restore the protected or insurance policy for normal return.',
    future_confirmation=dict(reference_checkpoint=protected['path'],reference_sha256=protected['sha256'],order=['reference','candidate','reference','candidate'],admission_s=1200,min_games_each=50,slots=16,full_tails=True,diagnostics=True,mean_ratio_min=1.05,median_at_least_fixed_reference=True,candidate_gates_independent=True,pool_candidates_for_rescue=False),
    interpretation='Frozen-policy confirmation is separate from a causal batch or learning-speed claim. Report logical steps, applied admissions, physical writes, actor/learner clocks and wall time separately.',
    execution_envelope=dict(controller_runtime_s=7200,deadline_runtime_s=6000,treatment_owner_ceiling_s=3600),
    actual_future_owner=None,actual_future_candidate=None,actual_future_clocks=None,goal_continues_after_confirmation=True)
policy_pin = save(OUT/'root-policy-FINAL.json',policy)
evidence = save(OUT/'root-evidence-FINAL.json',dict(source_manifest=pin(SRC/'preparation-manifest.json'),source_peer=source_peer,actual8_guards=guard,
    actual_prerequisite=prerequisite,actual_before=pin(OUT/'actual-before-current620749-main192.json'),actual_storage=pin(OUT/'actual-live-storage-asof-descriptors.json'),
    insurance=insurance,insurance_original0_and_release=pin(INS/'CPU-root-execution/root-result-review-and-release.json'),insurance_independent_review=pin(RUN/'preCE2048-current620749-insurance-independent-saved-review-20261017/review-receipt.json'),
    verified_python=pin(INS/'CPU-root-preparation/current-verified-python-binding-and-context.json'),protected_checkpoint=protected,protected_metadata=pin(Path(protected['path']+'.json')),
    actual_future_owner=None,trial_armed=False))
phase_id = 'ce_batch2048_efficacy_20261017_trial01'
core = dict(status='FINAL_PRECOMMITTED_ROOT_AUTHORIZED',activation_authorized=True,mode='activate_batch2048',phase_id=phase_id,batch_profile=profile,execution_prerequisites=prerequisite,root_policy=policy_pin,root_evidence=evidence)
core_pin = save(OUT/'trial-core-FINAL.json',core)
job = copy.deepcopy(old)
job.update(schema=adapter.SCHEMA,mode='activate_batch2048',output_directory=str(RUN/'CE2048-trial01-activation-20261017'),
    before=before,actor_masks=masks['actors'],worker_mask=masks['worker'],baseline_csv=fresh['csv'],
    settings_lifecycle=read(OUT/'actual-settings-lifecycle.json'),sources=[],verifier=verifier,
    trial_core=core_pin,prerequisites=dict(quality_release=pin(RUN/'CE543M-quality-root-freeze-release-20261017/root-explicit-source-freeze-release.json')),
    protected_reference=protected,original_dropin=read(OUT/'actual-original-phase-dropin.json'),running_phase=known['current_running_phase'],completed_dormant_capture=None,
    phase_id=phase_id,request_id='CE2048_trial01_activate_20261017',startup_tag='CE2048-startup-20261017-trial01',
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),insurance_verification=insurance,insurance_receipt=pin(INS/'saved-insurance-receipt.json'),
    current_completed_request=read(OUT/'actual-current-completed-request.json'),ending_proof=None,batch_profile=profile,
    batch_boundary=adapter.boundary().direction('activate_batch2048',adapter.boundary().PROFILE_BINDING),
    phase_verifier=dict(script=selected['phase4096'],strict_base=selected['strict4096']),phase_verifier2048=dict(script=selected['phase2048'],strict_base=selected['strict2048']),
    producer_collector=dict(script=selected['collector'],manifest=selected['collector_manifest']),producer_capture=None,phase_early_insurance_result=None,execution_prerequisites=prerequisite)
job['helper_pins'].update(controller=selected['adapter'],v4=selected['v4'],phase_script=selected['phase4096'],phase_strict=selected['strict4096'],horizon=selected['horizon'],profile_boundary=selected['profile_boundary'],phase_early=selected['early_insurance'],execution_readiness=selected['execution_readiness'])
job['static_pins'] = [pin(SRC/'preparation-manifest.json'),source_peer,guard,policy_pin,evidence,prerequisite,pin(RUN/'CE2048-live-trial-selected-release-reviewed2-addendum-20261017/preparation-manifest.json')]
assert base.fingerprint(Path(job['current_completed_request']['path']),base.MAX_JSON) == job['current_completed_request']
activation_pin = save(OUT/'activation-job-FINAL.json',job)
verified,actual = adapter.read_job(argparse.Namespace(job=Path(activation_pin['path']),expected_job_sha256=activation_pin['sha256'],expected_controller_sha256=selected['adapter']['sha256']),base)
assert verified == job and actual == activation_pin
python_identity = {key:copy.deepcopy(verifier['python_binding'][key]) for key in ('argv_path','link_target','link_identity','executable','pyvenv_cfg','library_context')}
trial = dict(schema='robotron-one-ce-batch2048-trial-job-v1',sources={name:selected[name] for name in ('controller','deadline','early_insurance','adapter','horizon','execution_readiness')},
    activation_job=activation_pin,trial_core=core_pin,old_owner=base.read_json(insurance)['root_job']['insurance']['trainer'],boot_id=job['boot_id'],
    output_directory=str(RUN/'CE2048-trial01-controller-20261017'),deadlines=dict(latch_s=3240,stop_intent_s=3310,owner_ceiling_s=3600),observation_budget_bytes=32<<20,
    early_insurance=dict(tag='CE2048-early-insurance-20261017-trial01',cpu_unit='robotron-CE2048-early-insurance-trial01-20261017.service',save_timeout_s=60,cpu_timeout_s=120,profile=profile,collector=job['producer_collector'],python_identity=python_identity,producer_expectation=None),
    candidate_tag='CE2048-first-8M-20261017-trial01',return_intent=dict(phase_id='ce4096_after_batch2048_20261017_trial01',request_id='CE2048_trial01_return4096_20261017',startup_tag='CE4096-after2048-startup-20261017-trial01',output_directory=str(RUN/'CE2048-trial01-return4096-20261017')),
    profile=profile,execution_prerequisites=prerequisite)
assert all(not Path(value).exists() for value in (trial['output_directory'],job['output_directory'],trial['return_intent']['output_directory']))
trial_pin = save(OUT/'one-trial-job-FINAL.json',trial)
ready = adapter.execution_readiness()
ready.preflight_transition(Path(activation_pin['path']),activation_pin['sha256'],selected['adapter']['path'],selected['adapter']['sha256'])
ready.preflight_trial(Path(trial_pin['path']),trial_pin['sha256'],selected['controller']['path'],selected['controller']['sha256'])
deadline = load(selected['deadline']['path'],selected['deadline']['sha256'],'root_actual_CE2048_deadline')
deadline.validate_authorization(core,job)
receipt = save(OUT/'root-FINAL-readonly-validation.json',dict(status='PASS_FINAL_ACTUAL_CE2048_ROOT_JOBS_READONLY_VALIDATED_NOT_ARMED',core=core_pin,activation=activation_pin,trial=trial_pin,policy=policy_pin,evidence=evidence,armed=False,executed=False,actual_future_owner=None))
print(json.dumps(dict(status='FINAL_PREPARED_NOT_ARMED',core=core_pin,activation=activation_pin,trial=trial_pin,readonly_validation=receipt)))
