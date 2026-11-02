"""One root-only R2/C2 startup observation; default PLAN has no reads or actions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import urllib.request

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
RUN = GAME/'logs/managed-learning-20261015/run-26'
PLAN_SHA = 'fdb13f963f7433d8dcd816934fe266f327760a7953d47a1208f752f284d5fe85'
PINS = {
    'plan': (RUN/'CE2048-trial02-first-LATCH-followup-quality-actual-launch-root-20261017/actual-native-plan-readonly-copy.json', PLAN_SHA),
    'launch': (RUN/'CE2048-trial02-first-LATCH-followup-quality-actual-launch-root-20261017/root-original-running-identity-and-plan.json', '343537e2b5ab1752d8bcef52568c743f7115c8ed49b1a2cc03687861bc47fa51'),
    'binding': (RUN/'CE2048-trial02-first-LATCH-followup-quality-root-preparation-20261017/root-quality-binding-job.json', '25bde9295865770d9a0317ad32a65efa464abb3f71ec3d68f8adc0c8978eeb5b'),
    'baseline': (RUN/'CE2048-trial02-first-LATCH-followup-quality-root-preparation-20261017/runtime-baseline.json', '445b8eea9c5a5009564a04d014fb81aca6957ad1381ed29c332c6987a8e22022'),
    'C1_pattern': (RUN/'CE2048-trial02-first-LATCH-followup-quality-C1-startup-root-20261017/root-C1-startup-and-main-health.json', '86ba80c0169249bee54efce081dc7583decbf62c7ef692357df203d3bee795e0')}
UID = 1001
LIMIT = 8 << 20
GPU0 = 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
GPU1 = 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def read_file(path, readonly=False):
    p = Path(path)
    require(p.is_absolute() and p.resolve(strict=True) == p and p.suffix not in ('.pt', '.pth', '.npy', '.npz'), 'Canonical metadata/source only')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == UID and before.st_nlink == 1
            and 0 < before.st_size <= LIMIT and (not readonly or stat.S_IMODE(before.st_mode) == 0o444), 'Owned bounded file differs')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            raw = f.read(LIMIT + 1)
        require(len(raw) == before.st_size and identity(before) == identity(os.fstat(fd)) == identity(p.lstat()), 'File changed during read')
    finally:
        os.close(fd)
    return raw, dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(before))


def decode(raw):
    return json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite metadata: ' + x)))


def pinned(pin):
    raw, actual = read_file(pin['path'], True)
    require(all(actual[k] == pin[k] for k in ('path', 'sha256', 'bytes')), 'Saved metadata PIN differs')
    if 'identity' in pin:
        require(actual['identity'] == pin['identity'], 'Saved metadata identity differs')
    return decode(raw)


class Evidence:
    def __init__(self, out):
        self.out = out
        self.commands = []

    def write(self, name, raw):
        require(len(raw) <= LIMIT, 'Output exceeds bound')
        p = self.out/name
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            require(f.write(raw) == len(raw), 'Short archive write')
            f.flush(); os.fchmod(f.fileno(), 0o444); os.fsync(f.fileno())
        fd = os.open(self.out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return read_file(p, True)[1]

    def save(self, name, value):
        return self.write(name, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode())

    def call(self, argv):
        require((len(argv) == 5 and argv[:3] == ['systemctl', '--user', 'show'] and argv[-1] == '--all')
            or argv == ['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'], 'Read-only query allowlist')
        r = subprocess.run(argv, capture_output=True, check=False, timeout=10)
        value = dict(argv=argv, returncode=r.returncode, stdout=r.stdout.decode('utf-8', 'surrogateescape'), stderr=r.stderr.decode('utf-8', 'surrogateescape'))
        pin = self.save('%02d-command.json' % len(self.commands), value)
        self.commands.append(pin)
        require(r.returncode == 0, 'Read-only command failed')
        return value

    def show(self, unit):
        value = self.call(['systemctl', '--user', 'show', unit, '--all'])
        return dict(line.split('=', 1) for line in value['stdout'].splitlines() if '=' in line)


def proc_bytes(path):
    with Path(path).open('rb') as f:
        raw = f.read((1 << 20) + 1)
    require(len(raw) <= 1 << 20, 'Process metadata exceeds bound')
    return raw


def ticks(pid):
    return int(proc_bytes(Path('/proc', str(pid), 'stat')).rsplit(b')', 1)[1].split()[19])


def process(pid, expected, cgroup, expected_start=None, expected_parent=None):
    require(type(pid) is int and pid > 0, 'Positive actual PID required')
    base = Path('/proc', str(pid)); before = ticks(pid)
    status = dict(x.split(':', 1) for x in proc_bytes(base/'status').decode().splitlines() if ':' in x)
    value = dict(pid=pid, starttime_ticks=before, ppid=int(status['PPid']), uid=[int(x) for x in status['Uid'].split()],
        argv=[os.fsdecode(x) for x in proc_bytes(base/'cmdline').split(b'\0') if x],
        cwd=os.readlink(base/'cwd'), exe=os.readlink(base/'exe'), cgroup=proc_bytes(base/'cgroup').decode(),
        mask=sorted(os.sched_getaffinity(pid)))
    require(ticks(pid) == before and (expected_start is None or before == expected_start), 'Actual PID/start changed')
    require(expected_parent is None or value['ppid'] == expected_parent, 'Actual child parent differs')
    require(value['uid'] == [UID]*4 and all(value[k] == expected[k] for k in ('argv', 'cwd', 'exe', 'mask'))
        and cgroup in [x.split(':', 2)[2] for x in value['cgroup'].splitlines()], 'Actual process command/UID/path/mask/cgroup differs')
    return value


def observe(e, leg):
    loaded = {}; pins = {}
    for name, (path, sha) in PINS.items():
        raw, pin = read_file(path, True)
        require(pin['sha256'] == sha, 'Selected current source/metadata family differs: ' + name)
        loaded[name] = decode(raw); pins[name] = pin
    plan, launch, cfg, baseline, old = (loaded[k] for k in ('plan', 'launch', 'binding', 'baseline', 'C1_pattern'))
    require(pins['baseline'] == cfg['runtime_baseline'], 'Selected current baseline differs')
    campaign = Path(plan['output_directory']); name = 'R2' if leg == 3 else 'C2'; spec = plan['legs'][leg-1]
    require(spec['index'] == leg and spec['role'] == ('reference' if leg == 3 else 'candidate'), 'Selected leg role differs')
    raw, _ = read_file(campaign/'plan.json'); require(hashlib.sha256(raw).hexdigest() == PLAN_SHA, 'Actual native plan changed')
    raw, _ = read_file(campaign/'status.json'); native = decode(raw); native_pin = e.write('campaign-status-readonly.json', raw)
    record = next(x for x in native['legs'] if x['index'] == leg)
    require(native['plan_sha256'] == PLAN_SHA and native['state'] == 'running' and native['current_leg'] == leg
        and record['state'] == 'running' and record['role'] == spec['role'], 'Chosen original leg not running; no wait')
    owner = {k:v for k,v in launch['owner'].items() if k != 'observed_live'}
    require(owner['pid'] == 1673818 and owner['starttime_ticks'] == 36563185 and owner['invocation_id'] == '942c390f35d84884bd41f3d04ac9d7ff', 'Original parent anchor differs')
    parent = e.show(owner['unit'])
    require(parent['MainPID'] == parent['ExecMainPID'] == str(owner['pid']) and parent['InvocationID'] == owner['invocation_id']
        and parent['NRestarts'] == '0' and parent['SubState'] == 'running' and parent['ControlGroup'] == owner['cgroup']
        and ticks(owner['pid']) == owner['starttime_ticks'], 'Original live quality parent differs')
    raw, _ = read_file(record['evaluator_status_path']); status = decode(raw); status_pin = e.write(name+'-status-readonly.json', raw)
    boundary = status['boundary']; slots = list(range(4096, 4112))
    require(status['phase'] == 'collecting' and status['valid'] is None and status['active'] is True and status['complete'] is False
        and status['job'] == spec['job'] and status['checkpoint_sha256'] == plan['checkpoints'][spec['role']]['sha256']
        and status['close_ts']-status['start_ts'] == 1200 and boundary['ready'] is True
        and boundary['clients'] == boundary['expected'] == boundary['acknowledged'] == 16
        and len(boundary['acknowledged_client_ids']) == len(set(boundary['acknowledged_client_ids'])) == 16
        and boundary['actor_slots'] == boundary['required_actor_slots'] == slots
        and boundary['pending_client_ids'] == boundary['replay_pending_client_ids'] == [], 'Selected evaluator not genuinely collecting/all16 ACK; no wait')
    template = launch['R1_process']; expected = dict(template, argv=spec['command'])
    evaluator = process(record['pid'], expected, owner['cgroup'], expected_parent=owner['pid'])
    actor_pids = status['actor_pids']; require(set(actor_pids) == {str(s) for s in slots} and len(set(actor_pids.values())) == 16, 'Exact16 actor PID map differs')
    pattern = next(x for x in old['actors'] if x['slot'] == 4096); actors = []
    for slot in slots:
        directory = Path(spec['job']['directory'])/'actors'/str(slot)
        expected = dict(argv=[x.replace(pattern['cwd'], str(directory)) for x in pattern['argv']], cwd=str(directory), exe=pattern['exe'], mask=template['mask'])
        actors.append(dict(slot=slot, **process(actor_pids[str(slot)], expected, owner['cgroup'], expected_parent=evaluator['pid'])))
    resources = pinned(baseline['actual_main192_resources']); main = baseline['main_owner']; fleet = baseline['fleet_owner']
    require(main['pid'] == 1626184 and main['starttime_ticks'] == 36413669 and main['invocation_id'] == '168cea96ca864434b5cf12a3651ee39e', 'Original maintenance main anchor differs')
    for actual_owner in (main, fleet):
        show = e.show(actual_owner['unit'])
        require(show['MainPID'] == str(actual_owner['pid']) and show['InvocationID'] == actual_owner['invocation_id'] and show['NRestarts'] == '0'
            and show['SubState'] == 'running' and show['ControlGroup'] == actual_owner['cgroup'], 'Original main/fleet unit changed')
    main_process = process(main['pid'], resources['main'], main['cgroup'], main['starttime_ticks'])
    process(fleet['pid'], resources['fleet'], fleet['cgroup'], fleet['starttime_ticks'])
    actual_main_actors = {x['pid']:x for x in resources['actors']}; original = baseline['actors']; checks = []
    require(len(original) == len(actual_main_actors) == 192 and {x['slot'] for x in original} == set(range(192)), 'Original192 baseline differs')
    for actor in original:
        current = process(actor['pid'], actual_main_actors[actor['pid']], fleet['cgroup'], actor['starttime_ticks'])
        require(current['mask'] == actor['mask'], 'Original actor mask changed')
        checks.append(dict(pid=actor['pid'], starttime_ticks=current['starttime_ticks'], slot=actor['slot'], mask=current['mask']))
    worker = baseline['inference_worker']; require(ticks(worker['tid']) == worker['starttime_ticks'] and sorted(os.sched_getaffinity(worker['tid'])) == worker['mask'], 'Inference worker identity/mask changed')
    environment = dict(os.fsdecode(x).split('=',1) for x in proc_bytes(Path('/proc', str(main['pid']), 'environ')).split(b'\0')
        if b'=' in x and os.fsdecode(x).startswith(('DQN_', 'ROBOTRON_', 'CUDA_', 'TORCHINDUCTOR_')))
    maintenance = pinned(cfg['evidence']['maintenance_result']); phase = maintenance['startup']['phase']
    phase_record = pinned(phase['record'])
    require(maintenance['owner'] == main and phase['record']['sha256'] == '9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1'
        and phase_record['metric'] == 'ce' and environment['DQN_PRIORITY_PHASE_RECORD'] == phase['record']['path'], 'Actual maintenance owner/phase differs')
    require(environment == pinned(baseline['actual_selected_environment']) and environment['DQN_BATCH_SIZE'] == '4096'
        and environment['DQN_PER_PRIORITY_METRIC'] == 'ce' and environment['DQN_PRIORITY_PHASE_RECORD_SHA256'] == '9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1', 'Current CE4096 environment/phase changed')
    for group in ('source_hashes', 'control_hashes', 'unit_files'):
        for path, sha in baseline[group].items():
            raw, _ = read_file(path); require(hashlib.sha256(raw).hexdigest() == sha, 'Held source/control/unit changed')
    for group in ('evaluator_source_hashes', 'execution_source_hashes'):
        for path, sha in plan[group].items():
            path = Path(path); path = path if path.is_absolute() else GAME/path
            raw, _ = read_file(path); require(hashlib.sha256(raw).hexdigest() == sha, 'Frozen evaluator/execution source changed')
    gpu = e.call(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'])
    gpu_rows = [(int(line.split(',')[0]), line.split(',')[1].strip()) for line in gpu['stdout'].splitlines() if line.strip()]
    require(sorted(gpu_rows) == sorted([(main['pid'], GPU1), (evaluator['pid'], GPU0)]), 'Exact GPU0 evaluator/GPU1 main ownership differs')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        api_raw = response.read(LIMIT+1)
    api_pin = e.write('main-API.raw.json', api_raw); api = json.loads(api_raw)
    pipeline = api['host_pipeline']; graph = pipeline['inference_graphs']
    errors = [pipeline[k]['errors'] for k in ('inference','actor_refresh','target_refresh','learner_priority')]
    require(abs(time.time()-api['ts']) <= 5 and api['client_count'] == 192 and api['training_enabled'] is True and api['measurement_active'] is False
        and all(pipeline['learning_exposure'][k]['process_id'] == main['pid'] for k in ('optimizer','replay'))
        and errors == [0]*4 and graph['ready'] is True and graph['capture_count'] == 128 and graph['validation_replay_count'] == 640
        and graph['fallback_count'] == graph['runtime_capture_count'] == 0 and graph['fatal_error'] is None, 'Fresh main192/API/errors/graphs differ')
    closing = decode(read_file(campaign/'status.json')[0]); current = next(x for x in closing['legs'] if x['index'] == leg)
    require(closing['current_leg'] == leg and current['state'] == 'running' and current['pid'] == evaluator['pid']
        and ticks(evaluator['pid']) == evaluator['starttime_ticks'] and ticks(main['pid']) == main['starttime_ticks']
        and ticks(owner['pid']) == owner['starttime_ticks'] and abs(time.time()-api['ts']) <= 5, 'Startup owner/leg changed during observation')
    health = dict(observed_unix_s=time.time(), pid=main['pid'], client_count=192, training_enabled=True, pipeline_errors=sum(errors), graphs_ready=True,
        fallback_count=0, runtime_capture_count=0, **{k:api[k] for k in ('learner_frame_count','frame_count','training_steps','optimized_samples')})
    return dict(status='PASS_'+name+'_ALL16_ADMISSION_ORIGINAL_MAIN192', observed_unix_s=time.time(), actual_plan_sha256=PLAN_SHA,
        evaluator=evaluator, actors=actors, original_main_actor_checks=checks, boundary=boundary, job=spec['job'], checkpoint_sha256=status['checkpoint_sha256'],
        **{name+'_status':status_pin}, main_API=api_pin, main_health=health, GPU_owners=gpu['stdout'], admission_start=status['start_ts'], admission_close=status['close_ts'],
        source_freeze=True, final_leg_validity_deferred=True, quality_result='not_assessed', source_inputs=pins, native_campaign_status=native_pin, main_process=main_process)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--leg', type=int, choices=(3,4))
    parser.add_argument('--output', type=Path); parser.add_argument('--expected-source-sha256'); args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads, queries, waits, actions or output'); return 0
    require(args.leg and args.output and args.expected_source_sha256, 'Explicit leg/source/output required')
    out = args.output; require(out.is_absolute() and out.parent == RUN and out.parent.resolve(strict=True) == RUN and not os.path.lexists(out), 'Fresh direct run26 output required')
    out.mkdir(mode=0o700)
    fd = os.open(RUN, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    e = Evidence(out); started = time.time()
    try:
        _, source = read_file(__file__, True); require(source['sha256'] == args.expected_source_sha256, 'Explicit source differs')
        result = observe(e, args.leg); result.update(source=source, started_unix_s=started, ended_unix_s=time.time(), raw_command_metadata=e.commands)
        pin = e.save('root-'+('R2' if args.leg == 3 else 'C2')+'-startup-and-main-health.json', result)
        print(json.dumps(dict(status=result['status'], record=pin), allow_nan=False)); return 0
    except BaseException as error:
        pin = e.save('root-startup-refusal.json', dict(status='REFUSED_NO_WAIT_OR_RETRY', leg=args.leg, started_unix_s=started,
            ended_unix_s=time.time(), error=dict(type=type(error).__name__, message=str(error)), raw_command_metadata=e.commands, actions=False))
        print(json.dumps(dict(status='REFUSED_NO_WAIT_OR_RETRY', record=pin), allow_nan=False)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
