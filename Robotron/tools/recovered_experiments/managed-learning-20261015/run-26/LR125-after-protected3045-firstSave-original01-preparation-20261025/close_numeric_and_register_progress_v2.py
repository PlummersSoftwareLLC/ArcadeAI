"""Close the original numerical job and register its evidence without loading Torch."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
D = R / 'LR125-after-protected3045-firstSave-original01-preparation-20261025'
P = G / 'tools/training_connection_lifecycle_proposal_20261023'


def load(path, name, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_reg_h',
         '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader = load(G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py', '_reg_reader',
              'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
arc = load(G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py', '_reg_arc',
           '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')


def read(pin, as_json=True):
    return reader.read_pin(pin, as_json=as_json)


def raw_archive(path, data):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    return h.pin(path)


def replace_cas(path, before, after):
    assert path.read_bytes() == before
    temporary = path.with_name(path.name + '.after3045-cas.tmp')
    with temporary.open('xb') as stream:
        stream.write(after)
        stream.flush()
        os.fchmod(stream.fileno(), 0o664)
        os.fsync(stream.fileno())
    assert path.read_bytes() == before
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# The shared closer predicates are preserved except these three exact literals.
# directory expressions and precommitted numeric TasksMax differ from capture layout.
closer_path = P / 'independent_component_closeout_v3.py'
original = closer_path.read_text()
effective = original
replacements = [
    ("TasksMax='128'", "TasksMax='256'"),
    ("directory/'controller-config.json'", "directory/'candidate-CPU-preparation-original01/candidate-CPU-controller-config.json'"),
    ("directory/'execution-original01'", "directory/'candidate-CPU-execution-original01'"),
]
for old, new in replacements:
    assert effective.count(old) == 1
    effective = effective.replace(old, new)
reversed_source = effective
for old, new in reversed(replacements):
    reversed_source = reversed_source.replace(new, old)
assert reversed_source == original
namespace = {}
exec(compile(effective, str(closer_path) + '::owned-numeric-layout', 'exec'), namespace)
configpin = h.pin(D / 'candidate-CPU-preparation-original01/candidate-CPU-controller-config.json')
assert configpin['sha256'] == '7317c15eb03635e6d8b72888fe2f5e2cb475136a49cbc10b7fec07331ebb8f16'
assert 'TasksMax=256' in read(configpin)['properties']
closure = namespace['closeout'](D, h, arc, read, 0)
jobpin = h.pin(D / 'candidate-CPU-preparation-original01/candidate-CPU-job.json')
job = read(jobpin)
report_path = D / 'candidate-CPU-verification-original01/cpu-verification.json'
report_bytes = report_path.read_bytes()
report_pin = raw_archive(D / 'candidate-CPU-preparation-original01/original-CPU-verification.raw.json', report_bytes)
report = read(report_pin)
assert report['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-result-v1'
assert report['status'] == 'PASS' and report['root_job'] == job
assert report['sha256'] == job['source']['sha256'] == job['verification_copy']['sha256']
assert report['phase_metadata_verified'] is True
assert report['cuda_initialized'] is False and report['visible_cuda_devices'] == 0
assert report['actual_restore_or_optimizer_step'] is False
assert report['actual_quality_qualification'] is False
assert report['adam_state_count'] == 81 and report['adam_group_count'] == 1
assert report['adam_group']['lr'] == 6.25e-6
assert report['held_recipe_context'] == job['source_control_context']['held_recipe_context']
assert report['recipe_specialization']['reverse_exact_raw_source'] is True
assert report['recipe_specialization']['numeric_function_bodies_changed'] is False
assert report['recipe_specialization']['saved_metadata_normalized'] is False
for model in report['models'].values():
    assert model == dict(strict_cpu_load=True, tensor_count=100, parameter_count=17837490)
for value in report['bound_files'].values():
    actual = h.pin(value['path'])
    assert actual['sha256'] == value['sha256'] and actual['bytes'] == value['bytes']
    assert all(actual['identity'][k] == value[k] for k in actual['identity'])
clocks = {k: report['clocks'][k] for k in job['clock_floor']}
assert all(clocks[k] >= job['clock_floor'][k] for k in clocks)
assert report['phase_current_clocks'] == clocks
assert report['adam_step_min'] == report['adam_step_max']
assert report['logical_training_steps_minus_adam_step'] == clocks['training_steps'] - report['adam_step_min']
old = read(h.pin(R / 'currentLR125-quota64Protocol-firstSave-original01-preparation-20261024/candidate-CPU-preparation-original01/original-CPU-verification.raw.json'))
proof = dict(schema='robotron-after3045-original-numerical-independent-closeout-v1',
    original_tool_session_id=53220, actual_observed_tool_exit=0, closure=closure,
    directory_specialization=dict(source=h.pin(closer_path), replacements=replacements, exact_reverse=True),
    original_report=report_pin, job=jobpin, source=job['source'], verification_copy=job['verification_copy'],
    saved_clocks=clocks, all_bound_file_identities_verified=True,
    finite_and_strict_models_and_adam_and_scaler_checked_by_original_CPU=True,
    saved_adam_step_delta=report['logical_training_steps_minus_adam_step'],
    previous_saved_adam_step_delta=old['logical_training_steps_minus_adam_step'],
    adam_step_delta_limit='Logical admission clocks differ from actual Adam slots; cause not independently established. No effective-update or learning-speed claim.',
    quality_qualified=False, learning_speed_gain_verified=False, throughput_gain_verified=False)
proofpin = h.put(D / 'independent-original-numerical-and-scope-closeout.json', proof)

state_path = G / 'logs/managed-learning-20261015/state.json'
before = state_path.read_bytes()
state = json.loads(before)
goal = state['optimization_goal']
preimage = raw_archive(D / 'canonical-state-before-capture-and-numeric-registration.json', before)
# Lossless removal of obsolete live aliases from earlier, already closed studies.
keys = [k for k in goal if k.startswith(('current_R1_', 'current_C1_', 'current_main_full_R1_'))]
history = h.put(D / 'historical-closed-leg-aliases-before-after3045-registration.json',
                dict(schema='robotron-lossless-historical-goal-aliases-v1', canonical_preimage=preimage,
                     values={k: goal[k] for k in keys}, historical_only=True))
for key in keys:
    del goal[key]
capturepin = h.pin(D / 'independent-original-capture-and-current-main-closeout.json')
capture = read(capturepin)
binding = capture['postcapture_binding']
monitor = capture['postcapture_monitor']
assert read(binding)['held_hashes'] == read(h.pin(D / 'postcapture-current-main-binding.json'))['held_hashes']
goal.update(stage='PROTECTED3045_LATER3262_NUMERIC_PASSED_SELECTOR_FAMILY_PREPARATION',
    phase='BETWEEN_STUDIES_PREPARE_SELECTOR_SOURCE_FAMILY_AND_RUNTIME_VALIDATION',
    actual_running_wait=None, all_current_original_handles_terminal=True,
    current_main_binding=binding, current_main_monitor=monitor,
    current_main_monitor_command='/usr/bin/python3.12 -I -B ' + monitor['path'],
    current_main_binding_kind='CURRENT_MAIN192_EXACT_OWNED_AFTER3045_SAVE_COMPLETION_TRANSITION',
    after3045_historical_closed_aliases=history,
    current_later_candidate_preparation=dict(directory=str(D), capture_closeout=capturepin,
        numerical_closeout=proofpin, numerical_report=report_pin, policy=job['source'],
        saved_clocks=clocks, quality_qualified=False, status='CAPTURE_AND_ORIGINAL_CPU_CLOSED_VALID'),
    last_progress='Fresh later3262 policy captured and numerical CPU53220 closed0; main192/197 binding reconciled. Next isolated selector family/actual writer aliases/initializer/runtime validation. Candidate quality unmeasured.')
recovery = dict(schema='robotron-optimization-current-recovery-index-v3', goal_status='active',
    created_unix_s=time.time(), previous_recovery_index=goal['current_recovery_index'],
    canonical_preimage=preimage, stage=goal['stage'], phase=goal['phase'],
    current_main_binding=binding, current_main_monitor=monitor,
    current_main_monitor_command=goal['current_main_monitor_command'],
    actual_running_wait=None, all_current_original_handles_terminal=True,
    scientific_job_running=False, source_freeze=False, full_source_freeze=False,
    reference=goal['current_fixed_reference_policy'], next_fixed_reference_score_pool=None,
    protected_winner_readback=goal['protected_winner_readback'],
    current_later_candidate_preparation=goal['current_later_candidate_preparation'],
    current_selector_CPU_experiment=goal['current_selector_CPU_experiment'],
    next_controlled_experiment_preparation=goal['next_controlled_experiment_preparation'],
    historical_closed_aliases=history, latest_goal_turn_classification='progress',
    previous_goal_turn_classification='progress',
    classification_basis='Recovered actual capture69299 terminal0; verified owned capture and reconciled exactly one completed-slot hold; original numeric53220 terminal0 independently closed, all bound identities/strict model/Adam/phase checks. No quality or speed claim.',
    next_action='Prepare isolated selector family using protected3045 as reference and freshly captured3262 candidate; actual journal-writer alias guards, actual preparer-to-native initializer guards and bounded display projection; then precommit controlled engineering runtime validation. Fresh full-game R1/R2+C1/C2 required before any new quality promotion.')
recoverypin = h.put(R / 'current-optimization-recovery-index-20261025-protected3045-later3262-numeric-passed-original01.json', recovery)
goal['current_recovery_index'] = recoverypin
goal['current_optimization_recovery_index'] = recoverypin
after = (json.dumps(state, separators=(',', ':'), allow_nan=False) + '\n').encode()
assert len(after) < 1048576
assert {k:v for k,v in state.items() if k != 'optimization_goal'} == {k:v for k,v in json.loads(before).items() if k != 'optimization_goal'}
replace_cas(state_path, before, after)
doc = G / 'DELL_SETUP.md'
docbefore = doc.read_bytes()
raw_archive(D / 'DELL_SETUP-before-capture-and-numeric-registration.md', docbefore)
marker = b'Earlier five-minute observation, retained for history:\n'
assert docbefore.count(marker) == 1
suffix = marker + docbefore.split(marker, 1)[1]
top = '''# Dell GB300 Robotron setup

Current optimization recovery: [Protected3045; later3262 candidate CPU verified](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261025-protected3045-later3262-numeric-passed-original01.json).

The protected3045 policy b23152ec remains the next fixed reference POLICY.
Its completed independent C1/C2 means were11.5923M/11.3168M against4.3274M;
all19 prior protected checkpoints and original receipts remain intact.
Next-study reference scores have not been collected. Dashboard finished/qualified
describes the completed campaign; no new candidate quality has been established.

Fresh later policy df4314b0 was captured through the original managed-save path.
Capture69299 and numerical CPU53220 both actually exited0 and released their
owned scopes. Numerical saved learner frames3262935672; both models strict-load
with finite state,81 Adam slots at6.25e-6 and valid saved CE phase metadata.
The logical-versus-Adam step difference5750 is reported; its cause is unmeasured.
No restore, optimizer step, live recipe change or quality/speed claim was made.
The owned completion-slot hash alone was reconciled; all other196 source holds
and192 actor identities are retained. The historical pre-save prefix cannot
pass a later CURRENT-slot replay; that limitation is preserved in its closeout.

Selector serialization proposal d15cd0f3 remains uninstalled. Its controlled CPU
experiment passed19 original guards per implementation plus8116 semantic checks.
Active-tail median CPU savings18.2..20.7% concern reconstructed journal fixtures;
actual emulator FPS, useful training throughput and learning speed are unmeasured.
Next prepare a fresh isolated family with protected3045 and later3262, actual
GameJournal writer alias/nested-copy guards, actual preparer/native initializer
guards and a bounded display-summary fix. Then precommit engineering runtime
validation while preserving all full-game quality gates. No experiment is running.
Main192/197/autosaves healthy at retainedLR125/cap8/wavecap75; goal remains active.

'''
replace_cas(doc, docbefore, top.encode() + suffix)
h.put(D / 'canonical-registration-and-document-receipt.json', dict(schema='robotron-after3045-registration-v1',
    recovery=recoverypin, state_sha256=hashlib.sha256(after).hexdigest(), state_bytes=len(after),
    document_sha256=hashlib.sha256(doc.read_bytes()).hexdigest(), document_historical_suffix_preserved=True,
    only_optimization_goal_changed=True, old_aliases_preserved=history, numerical_closeout=proofpin))
print(json.dumps(dict(recovery=recoverypin, numerical_closeout=proofpin, saved_clocks=clocks, state_bytes=len(after))))
