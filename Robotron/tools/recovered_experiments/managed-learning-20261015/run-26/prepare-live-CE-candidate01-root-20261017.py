"""Root metadata preparation only; the capture is launched separately once."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import urllib.request

REPO = Path('/home/dave/source/repos/ArcadeAI')
RUN = REPO/'Robotron/logs/managed-learning-20261015/run-26'
SRC = REPO/'Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/live_ce_candidate_capture_helper_proposal'
HEALTH = RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'
assert hashlib.sha256(HEALTH.read_bytes()).hexdigest() == 'd525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'
spec = importlib.util.spec_from_file_location('_root_ce_metadata_files', HEALTH)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)

checks = {
    SRC/'preparation-manifest.json': 'a9731dbd713091ca11b37ae834db24d7b86426ab7c207fb691f972b95f15de92',
    SRC/'capture_live_CE_candidate.py': '980bc51130e00a5394b98e6ef2abbc414147df794b722a06f597cf135424ffff',
    RUN/'live-CE-candidate-capture8-guards-root-20261017/original-guard-inline-execution.json': '4ce634b4dcbc04fd2d22885a7ba6bcb020aef22bfdf15b1a8ca5d8b659f7a441',
    RUN/'rawKL-trial02-quality-root-freeze-release-20261017/root-explicit-source-freeze-release.json': '6d509af8bab78803f2f57088f5ef62efa1b07be4f107da45cde906ce6aade34f',
}
for path, digest in checks.items():
    assert ops.read_file(path)[1]['sha256'] == digest
manifest = json.loads((SRC/'preparation-manifest.json').read_bytes())
for entry in manifest['files']:
    actual = ops.read_file(entry['path'])[1]
    assert actual['sha256'] == entry['sha256'] and actual['identity']['mode'] == '0o444'

binding_path = RUN/'rawKL-trial02-quality-binding-root-preparation-20261017/root-quality-binding-job.json'
raw, binding_pin = ops.read_file(binding_path)
assert binding_pin['sha256'] == '3b16c36da91c63fd4fb218f1fed3c1c5a5fe8caff73534d880aeaeccfe4c81fe'
evidence = json.loads(raw)['evidence']
history = {key: evidence[source] for key, source in (
    ('outer_job', 'outer_job'), ('activation_job', 'activation_job'),
    ('activation', 'activation'), ('CE_return', 'ce_return'))}
old = {key: ops.pinned(value) for key, value in history.items()}
with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=10) as response:
    raw_api = response.read()
api = json.loads(raw_api)
assert api['client_count'] == 192 and api['training_enabled'] and not api['measurement_active']
assert api['host_pipeline']['inference']['errors'] == 0
assert api['host_pipeline']['learning_exposure']['optimizer']['process_id'] == 620749
nominal = api['learner_frame_count']//1000000
tag = f'freshCE-{nominal}M-20261017-candidate01'
model = REPO/'Robotron/models_dqn'
assert not any((model/'managed-checkpoints'/f'{tag}.pt{suffix}').exists() for suffix in ('', '.tmp', '.bak'))
assert not any((model/name).exists() for name in ('managed_save.request.json', 'managed_save.request.json.failed'))

prep = RUN/'live-CE-candidate01-root-preparation-20261017'
execution = RUN/'live-CE-candidate01-capture-root-execution-reviewed1-20261017'
assert not prep.exists() and not execution.exists()
prep.mkdir()
execution.mkdir()
(execution/'tmp').mkdir()
ops.publish(prep/'root-previous-metadata-only-refusals.json', dict(
    refusals=['Initial root parser expected manifest files mapping; actual manifest uses a list.',
              'Second inline command had a syntax error before execution.'],
    actual_capture_requests_or_unit_launches=0, outputs_before_refusals=0,
    actual_guard_retries=0, scientific_evaluator_or_audit_retries=0))
api_pin = ops.write_bytes(prep/'actual-precommit-main-API.json', raw_api)
job = json.loads((SRC/'root-job.template.json').read_bytes())
job.update(
    cpu_python=str(REPO/'.venv-gb300/bin/python'),
    expected_owner=old['CE_return']['owner'],
    experiment=old['activation_job']['experiment'], history=history,
    output_directory=str(RUN/'live-CE-candidate01-capture-20261017'),
    root_release=dict(source_freeze_released=True,
        freeze_release=ops.read_file(RUN/'rawKL-trial02-quality-root-freeze-release-20261017/root-explicit-source-freeze-release.json')[1],
        quality_cleanup=ops.read_file(RUN/'rawKL-trial02-quality-terminal-closure-root-20261017/cleanup-receipt.json')[1]),
    startup_tag=old['outer_job']['return_intent']['startup_tag'], tag=tag)
job_pin = ops.publish(prep/'root-job.json', job)
unit = 'robotron-live-ce-candidate01-capture-20261017.service'
timer = unit.removesuffix('.service')+'.timer'
inner = ['/usr/bin/python3.12', '-I', '-B', str(SRC/'capture_live_CE_candidate.py'),
    '--execute', '--job', job_pin['path'], '--expected-job-sha256', job_pin['sha256'],
    '--expected-source-sha256', checks[SRC/'capture_live_CE_candidate.py']]
argv = ['systemd-run', '--user', '--unit='+unit, '--on-active=3s',
    '--timer-property=AccuracySec=100ms', '--property=Type=exec',
    '--property=RemainAfterExit=yes', '--property=Restart=no', '--property=CPUQuota=200%',
    '--property=MemoryMax=768M', '--property=MemorySwapMax=0', '--property=TasksMax=128',
    '--property=RuntimeMaxSec=120', '--property=TimeoutStopSec=5',
    '--property=WorkingDirectory='+str(REPO),
    '--property=StandardOutput=append:'+str(execution/'stdout.txt'),
    '--property=StandardError=append:'+str(execution/'stderr.txt'),
    '/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
    'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR='+str(execution/'tmp'), *inner]
source_pins = {str(path): digest for path, digest in checks.items()}
source_pins[job_pin['path']] = job_pin['sha256']
intent = ops.publish(execution/'root-launch-intent.json', dict(
    status='PREPARED_UNEXECUTED', unit=unit, timer=timer, argv=argv,
    source_pins=source_pins, root_job=job_pin,
    expected_result=str(RUN/'live-CE-candidate01-capture-20261017/result.json'),
    trigger_main_API=api_pin, nominal_M_at_precommit=nominal,
    precommit_learner_frame_count=api['learner_frame_count'], tag=tag,
    qualifies_or_CPU_pass=False,
    scope='One live model-only save and independent copy; no pause/restart/recipe change/CPU load/quality claim.'))
state_path = RUN.parent/'state.json'
state = json.loads(state_path.read_bytes())
state['optimization_goal']['post_quality_next_CE_capture'].update(
    actual_job={key: job_pin[key] for key in ('path', 'sha256', 'bytes')},
    tag=tag, status='PRECOMMITTED_ONCE_PENDING_OWNED_LAUNCH')
state['stage'] = 'run26_next_live_CE_candidate01_capture_precommitted'
state['updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
state['updated_unix_s'] = datetime.datetime.now().timestamp()
temporary = state_path.with_name('state.json.root-captureprecommit-tmp')
temporary.write_text(json.dumps(state, indent=2)+'\n')
os.replace(temporary, state_path)
print(json.dumps(dict(job=job_pin, intent=intent, tag=tag,
    actual_precommit_learner_frames=api['learner_frame_count'])))
