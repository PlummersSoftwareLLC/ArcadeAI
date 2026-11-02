"""Root's one original registration/launch operation; never retries a payload."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
A = Path(__file__).resolve().parent
I = A.parent
S = I / 'durable-window03-D7-fixed-RCRC-study-original01'
L = I / 'durable-window03-D7-selected-metadata600-original01-preparation'
STATE = G / 'logs/managed-learning-20261015/state.json'
helper_path = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
assert hashlib.sha256(helper_path.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
spec = importlib.util.spec_from_file_location('_root_launch_helpers', helper_path)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

def thin(pin):
    return {k: pin[k] for k in ('path', 'sha256', 'bytes')}

def exclusive_bytes(path, body, mode=0o444):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as f:
        f.write(body)
        f.flush()
        os.fchmod(f.fileno(), mode)
        os.fsync(f.fileno())

def command(argv, timeout=30):
    started = time.time()
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return dict(argv=argv, actual_exit=p.returncode, stdout=p.stdout, stderr=p.stderr,
                started_unix_s=started, ended_unix_s=time.time())

def unit_owner(unit):
    raw = subprocess.check_output(['systemctl', '--user', 'show', unit], text=True, timeout=5)
    fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    pid = int(fields.get('MainPID', '0'))
    birth = None
    if pid:
        birth = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    return dict(unit=unit, pid=pid, starttime_ticks=birth,
                invocation_id=fields.get('InvocationID'), properties=fields,
                observed_unix_s=time.time())

before = STATE.read_bytes()
state = json.loads(before)
previous = state['current_optimization_recovery_index']
assert previous['sha256'] == 'b3e2061b15736ed834cac0d603a8fe19333694995ba4007d0dc7fa850859e916'
assert state['active_quality_job'] is None
assert not (A / 'ROOT-original-launch-command-results-original01.json').exists()
assert not (A / 'original-R1-wrapper-intent.json').exists()
assert not (A / 'fresh-main-final-before-R1.raw.json').exists()
source_path = A / 'prepared-window03-D7-R1-wrapper-display-SOURCE-ONLY-NOT-LAUNCHED.json'
source_pin = h.pin(source_path)
assert source_pin['sha256'] == 'cd89c4e0d759c43d0289246c6a2a7c51d39f700b10964dfea62ffabde3e02d64'
source = json.loads(source_path.read_bytes())
peer = h.pin(A / 'independent-window03-D7-owned-R1-review-continuation-source-peer-v1.json')
assert peer['sha256'] == '98fa1581016e3d463c17693fce7db16be827710feeb671d4eff64d99411646ff'
template = json.loads((A / 'ROOT-operation-inputs-UNFILLED.json').read_bytes())
template.update(
    base_readiness=h.pin(S / 'ROOT-resource-readiness-original01.json'),
    review_precommit=h.pin(S / 'review-precommit-original01/precommitted-four-reviews.json'),
    review_CPU=h.pin(S / 'deadline-review-preparation-CPU-original01/independent-original-CPU-scope-closeout.json'),
    output_readiness=str(A / 'ROOT-same-operation-final-readiness-original01.json'),
    output_selection=str(A / 'ROOT-original-R1-launch-selection-original01.json'))
assert template['review_CPU']['sha256'] == 'c2f36d27226ff35f073d6a1e1c8bfe88f027c4ad4c12478eb3df31d2400bac68'
inputs = h.put(A / 'ROOT-filled-operation-inputs-original01.json', template)
backup = A / 'ROOT-canonical-before-original60.exact.json'
exclusive_bytes(backup, before)
guard_pin = h.pin(L / 'actual-closed-metadata-guard-original01/all-four-exact-native-guard-receipts.json')
assert guard_pin['sha256'] == 'fafeed9fe5087fc98ad46079081795d2b5e9912eec6010760620cc1d4ebe2180'
generator = A / 'prepare_owned_R1_launch_v1.py'
assert hashlib.sha256(generator.read_bytes()).hexdigest() == '5084790b274eb435811a16ebb9c791871f523f2f64c23f003562fe7106d79b7d'

# Freshness-dependent generation, canonical registration and launch stay together.
generated = command(['/usr/bin/python3.12', '-I', '-B', str(generator), '--prepare',
                     '--inputs', inputs['path'], '--inputs-sha256', inputs['sha256'],
                     '--source-sha256', '5084790b274eb435811a16ebb9c791871f523f2f64c23f003562fe7106d79b7d'], 60)
h.put(A / 'ROOT-original-same-operation-generation-result.json', generated)
assert generated['actual_exit'] == 0, generated['stderr']
launch = json.loads(generated['stdout'])
selection = json.loads(Path(launch['launch_selection']['path']).read_bytes())
assert selection['candidate_sha256'] == '16c3e3294d97e8bd9899f753a311cd3c958e5fba1a1a5b765f29955a52b2b22d'
active = dict(directory=str(S), candidate_sha256=selection['candidate_sha256'],
              reference_sha256=selection['reference_sha256'], current_leg='R1', state='starting',
              study_manifest=thin(selection['prepared_manifest']),
              launch_selection=thin(launch['launch_selection']), registered_unix_s=time.time(),
              original_attempt=1, no_retry=True)
index = h.put(A / 'ROOT-current-optimization-index-original60-D7-R1-registered.json', dict(
    schema='robotron-root-current-optimization-index-v1', previous=previous,
    created_unix_s=time.time(), stage='D7_REFERENCE_R1_REGISTERED_STARTING',
    candidate_sha256=selection['candidate_sha256'], source_preparation=thin(source_pin),
    independent_source_peer=thin(peer), guard_index=thin(guard_pin),
    review_CPU=thin(template['review_CPU']), readiness=thin(launch['readiness']),
    launch_selection=thin(launch['launch_selection']), exact_registration=active,
    canonical_preimage=thin(h.pin(backup)), wrapper_launched_yet=False,
    quality_qualified=False, promotion=False))
state['stage'] = 'D7_REFERENCE_R1_REGISTERED_STARTING'
state['current_optimization_recovery_index'] = thin(index)
state['active_quality_job'] = active
state['active_deadline_score_job'] = dict(active)
state['active_readonly_validation_job'] = None
state['updated_unix_s'] = time.time()
g = state['optimization_goal']
g.update(current_reconnect_evaluator_integration=thin(index), active_quality_job=dict(active),
         current_active_quality_job=dict(active), active_deadline_score_job=dict(active),
         active_readonly_validation_job=None, scientific_job_running=True,
         current_campaign=str(S), current_campaign_leg='R1', current_campaign_phase='R1_STARTING',
         current_source_family_qualified=dict(source_preparation=thin(source_pin),
             source_family=thin(source['source_family']), guard_index=thin(guard_pin),
             review_CPU=thin(template['review_CPU'])))
g['dashboard_progress'] = dict(status='D7_REFERENCE_R1_STARTING',
    current_stage='Starting protected-reference R1 with 32 fixed-policy games',
    waiting_for='All 32 original first games to pass admission and establish the scoring deadline',
    eta='One hour from all-32 admission, followed by closure and independent review',
    deadline_unix_s=None, next_stage='Review R1, then start candidate C1',
    quality_qualified=False)
serialized = (json.dumps(state, separators=(',', ':'), allow_nan=False)+'\n').encode()
assert len(serialized) < 1048576, len(serialized)
assert STATE.read_bytes() == before, 'Canonical preimage changed before registration'
temporary = STATE.with_name('state.json.ROOT-original60-next')
exclusive_bytes(temporary, serialized, STATE.stat().st_mode & 0o777)
os.replace(temporary, STATE)
age = time.time() - json.loads(Path(launch['readiness']['path']).read_bytes())['checked_unix_s']
assert 0 <= age < 30, age
wrapper_result = command(launch['wrapper_argv'], 20)
wrapper_owner = unit_owner(selection['wrapper_unit']) if wrapper_result['actual_exit'] == 0 else None
display_result = command(launch['passive_display_argv'], 20) if wrapper_result['actual_exit'] == 0 else None
display_owner = unit_owner(selection['projector_unit']) if display_result and display_result['actual_exit'] == 0 else None
receipt = h.put(A / 'ROOT-original-launch-command-results-original01.json', dict(
    schema='robotron-root-original-D7-R1-registration-and-launch-v1',
    canonical_registration=thin(index), operation_inputs=inputs,
    generation_result=thin(h.pin(A / 'ROOT-original-same-operation-generation-result.json')),
    launch_selection=launch['launch_selection'], readiness_age_before_wrapper_s=age,
    wrapper_command=wrapper_result, wrapper_original_owner=wrapper_owner,
    passive_display_command=display_result, passive_display_original_owner=display_owner,
    no_retry=True, quality_qualified=False, promotion=False, recorded_unix_s=time.time()))
print(json.dumps(dict(receipt=thin(receipt), readiness_age_before_wrapper_s=age,
    wrapper_exit=wrapper_result['actual_exit'], wrapper_owner={k:v for k,v in (wrapper_owner or {}).items() if k!='properties'},
    display_exit=display_result['actual_exit'] if display_result else None,
    display_owner={k:v for k,v in (display_owner or {}).items() if k!='properties'},
    canonical_bytes=len(serialized))), flush=True)
assert wrapper_result['actual_exit'] == 0 and display_result and display_result['actual_exit'] == 0
