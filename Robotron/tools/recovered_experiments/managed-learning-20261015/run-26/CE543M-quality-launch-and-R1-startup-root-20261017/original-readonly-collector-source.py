"""Root read-only startup evidence for the genuine CE543M quality incarnation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

REPO = Path('/home/dave/source/repos/ArcadeAI')
RUN = REPO/'Robotron/logs/managed-learning-20261015/run-26'
CAMPAIGN = RUN.parent/'quality-448M-vs-CE543M-20261017'
LAUNCH = RUN/'CE543M-quality-durable-launch-20261017'
UNIT = 'robotron-quality-448M-vs-CE543M-20261017.service'
OUT = RUN/'CE543M-quality-launch-and-R1-startup-root-20261017'
HELPER = RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'
assert hashlib.sha256(HELPER.read_bytes()).hexdigest() == 'd525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'
spec = importlib.util.spec_from_file_location('_root_CE543_startup_files', HELPER)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)

def process(pid):
    root = Path('/proc')/str(pid)
    before = ops.process_start(pid)
    value = dict(pid=pid, starttime_ticks=before,
        ppid=int((root/'stat').read_text().rsplit(')', 1)[1].split()[1]),
        uid=list(map(int, next(line.split()[1:] for line in (root/'status').read_text().splitlines() if line.startswith('Uid:')))),
        cmdline=[os.fsdecode(part) for part in (root/'cmdline').read_bytes().split(b'\0') if part],
        cwd=os.readlink(root/'cwd'), exe=os.readlink(root/'exe'),
        cgroup=(root/'cgroup').read_text().strip(), mask=sorted(os.sched_getaffinity(pid)))
    assert before is not None and before == ops.process_start(pid)
    assert value['uid'] == [os.getuid()]*4
    return value

identity = json.loads((LAUNCH/'original-controller-identity.json').read_bytes())
assert (identity['pid'], identity['starttime_ticks'], identity['invocation_id'], identity['unit']) == (
    894289, 34316549, '4bcb24eb3bb344da9dc67b483a8ee946', UNIT)
quality, raw_quality = ops.show(UNIT)
assert quality['MainPID'] == quality['ExecMainPID'] == str(identity['pid'])
assert quality['InvocationID'] == identity['invocation_id'] and quality['NRestarts'] == '0'
assert quality['ActiveState'] == 'active' and quality['SubState'] == 'running'
quality_process = process(identity['pid'])
assert quality_process['starttime_ticks'] == identity['starttime_ticks']
assert str(CAMPAIGN) in quality_process['cmdline'] and '--launch' in quality_process['cmdline']
timer, raw_timer = ops.show(UNIT.removesuffix('.service')+'.timer')
saved_timer = ops.fields(json.loads((LAUNCH/'original-timer-show-after-carrier-reaped.json').read_bytes())['stdout'])
assert timer['LoadState'] == 'not-found' or timer['InvocationID'] == saved_timer['InvocationID']

plan_raw, plan_pin = ops.read_file(CAMPAIGN/'plan.json')
assert plan_pin['sha256'] == '25aaded11bf956b715cc5fb58be1901d236a30444e74253594461f8d11c00d75'
plan = json.loads(plan_raw)
preview = json.loads((RUN/'CE543M-quality-default-plan-root-20261017/default-plan.json').read_bytes())
assert {key for key in plan if plan[key] != preview[key]} <= {'created_unix_s'}
state = json.loads((CAMPAIGN/'status.json').read_bytes())
status_raw = (CAMPAIGN/'01-reference/status.json').read_bytes()
status = json.loads(status_raw)
assert state['state'] == 'running' and state['current_leg'] == 1 and state['plan_sha256'] == plan_pin['sha256']
assert state['legs'][0]['pid'] == 894298
assert status['active'] and status['phase'] == 'collecting' and not status['complete']
assert status['boundary']['acknowledged'] == 16 and status['boundary']['ready']
assert status['boundary']['actor_slots'] == list(range(4096, 4112))
assert status['checkpoint_sha256'] == '1e085a128e237c2bb0636b073e5053dd8bf5be932bcbd8249543b3af20e23021'
assert status['clocks']['learner_frame_count'] == 452630871
evaluator = process(894298)
assert evaluator['starttime_ticks'] == 34316739 and evaluator['ppid'] == identity['pid']
assert evaluator['cgroup'] == '0::'+quality['ControlGroup']
actors = [dict(process(pid), slot=int(slot)) for slot, pid in status['actor_pids'].items()]
assert len(actors) == len({actor['pid'] for actor in actors}) == 16
assert {actor['slot'] for actor in actors} == set(range(4096, 4112))
for actor in actors:
    assert actor['ppid'] == evaluator['pid'] and actor['cgroup'] == evaluator['cgroup']
    assert Path(actor['exe']).name == 'mame' and 'robotron' in actor['cmdline']
    assert '-cfg_directory' in actor['cmdline']
    private_cfg = actor['cmdline'][actor['cmdline'].index('-cfg_directory')+1]
    assert private_cfg.startswith('/dev/shm/robotron-snapshot-smoke-')

binding_raw, binding_pin = ops.read_file(RUN/'CE543M-quality-binding-root-preparation-20261017/root-quality-binding-job.json')
assert binding_pin['sha256'] == 'f43719ed4dc60a4c275a7414995aa79d0f40062c76964200cf8700a8abe50dc3'
binding = json.loads(binding_raw)
anchor = binding['runtime_anchor']
capture = ops.pinned(binding['evidence']['capture_result'])
capture_job = ops.pinned(capture['root_job'])
history = capture_job['history']
activation_job = ops.pinned(history['activation_job'])
ce = ops.pinned(history['CE_return'])
original = activation_job['before']
held = ce['healthy']['binding']['bindings']
main = process(anchor['main_owner']['pid'])
assert ops.actual_process(held['worker']['trainer'], anchor['main_owner']['cgroup']) == list(range(72))
main_actors = []
for expected in original['bindings']['actors']:
    mask = ops.actual_process(expected, original['bindings']['fleet_cgroup'])
    actual = process(expected['pid'])
    assert mask == activation_job['actor_masks'][str(expected['pid'])] == list(range(72))
    main_actors.append(dict(actual, slot=expected['slot']))
assert len(main_actors) == 192
for owner in (anchor['main_owner'], anchor['fleet_owner']):
    unit, _ = ops.show(owner['unit'])
    assert unit['MainPID'] == str(owner['pid']) and unit['InvocationID'] == owner['invocation_id']
    assert ops.process_start(owner['pid']) == owner['starttime_ticks']
thread = anchor['inference_worker']
assert ops.process_start(thread['tid']) == thread['starttime_ticks']
assert sorted(os.sched_getaffinity(thread['tid'])) == thread['mask'] == list(range(72))
for path, digest in {**anchor['source_hashes'], **anchor['control_hashes'], **anchor['unit_files']}.items():
    assert ops.read_file(path)[1]['sha256'] == digest
environment = {part.split(b'=',1)[0].decode():part.split(b'=',1)[1].decode()
    for part in Path('/proc',str(main['pid']),'environ').read_bytes().split(b'\0')
    if b'=' in part and part.split(b'=',1)[0].decode().startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_'))}
assert hashlib.sha256(json.dumps(environment,sort_keys=True).encode()).hexdigest() == anchor['environment_sha256']

gpu = ops.command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'])
assert gpu['returncode'] == 0
gpu_owners = {(int(row.split(',')[0]),row.split(',')[1].strip()) for row in gpu['stdout'].splitlines() if row.strip()}
assert gpu_owners == {(evaluator['pid'],ops.GPU_UUIDS[0]),(main['pid'],ops.GPU_UUIDS[1])}
import urllib.request
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10) as response:
    raw_api = response.read()
api = json.loads(raw_api)
assert api['client_count'] == 192 and api['training_enabled'] and not api['measurement_active']
assert api['host_pipeline']['learning_exposure']['optimizer']['process_id'] == main['pid']
graphs = api['host_pipeline']['inference_graphs']
assert graphs['ready'] and graphs['capture_count'] == 128 and graphs['validation_replay_count'] == 640
assert graphs['fallback_count'] == graphs['runtime_capture_count'] == 0 and graphs['fatal_error'] is None
assert all(api['host_pipeline'][key]['errors'] == 0 for key in ('inference','actor_refresh','target_refresh','learner_priority'))
assert ops.process_start(identity['pid']) == identity['starttime_ticks']
OUT.mkdir()
api_pin = ops.write_bytes(OUT/'actual-main-API.json', raw_api)
status_pin = ops.write_bytes(OUT/'actual-original-R1-status.json', status_raw)
ops.publish(OUT/'actual-quality-service-show-all-command.json',raw_quality)
ops.publish(OUT/'actual-quality-timer-show-all-command.json',raw_timer)
ops.publish(OUT/'actual-GPU-owner-command.json',gpu)
proof = dict(status='PASS_ORIGINAL_PARENT_R1_ALL16_MAIN192_FROZEN_SOURCE_AND_GPU_STARTUP',
    observed_unix_s=time.time(), actual_plan=plan_pin, preview_only_created_unix_s_diff=True,
    quality_owner=identity, quality_unit=quality, quality_timer=timer,
    quality_process=quality_process, evaluator=evaluator, R1_actors=actors,
    held_main_anchor=anchor, main_process=main, main_actors=main_actors,
    selected_main_environment_sha256=anchor['environment_sha256'],
    actual_main_API=api_pin, actual_R1_status=status_pin,
    R1_admission_start_unix_s=status['start_ts'], R1_admission_close_unix_s=status['close_ts'],
    source_freeze_held=True, actual_qualification_pass=False,
    scope='Original running identities and isolation only; no incomplete cohort score inference.')
pin = ops.publish(OUT/'actual-parent-R1-all16-main192-source-GPU-and-API.json',proof)
print(json.dumps(dict(status=proof['status'],proof=pin,evaluator=evaluator['pid'],
    all16_slots=True,main192=True,main_learner_frames=api['learner_frame_count'])))
