"""Archive exact trial02 originals, then release owned terminal units only.

PLAN by default. Root alone executes. No trial, trainer or actor stop/start.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import traceback

RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
JOB = RUN/'rawKL-trial02-final-root-preparation-20261017/one-trial-job-FINAL.json'
JOB_SHA = '187c5d9500b213d9468c504e60443577a8ac1dafd2241874c62d98124ed9b44a'
SCHEMA = 'robotron-trial02-original-terminal-and-owned-release-v1'
MAX_TEXT = 8 << 20
OWNERS = {
    'trial_controller': dict(unit='robotron-rawkl-trial02-controller-20261017.service', pid=545337,
        starttime_ticks=33273360, invocation_id='6879051172d24f729778398f171a37d4'),
    'deadline': dict(unit='robotron-rawkl-trial02-deadline-20261017.service', pid=542640,
        starttime_ticks=33266229, invocation_id='f7935f091de1400e86572b845b9852a4'),
}
LAUNCH = RUN/'rawKL-trial02-root-execution-20261017'
OBSERVED = {
    'trial_controller': LAUNCH/'controller/root-observed-identity-332754284926159.json',
    'deadline': LAUNCH/'deadline/root-observed-identity-332695083541286.json',
}
EARLY_UNIT = 'robotron-rawkl-early-insurance-trial02-20261017.service'
GPU_UUIDS = {0: 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',
    1: 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'}
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
BLOCKED = {'run_one_trial.py', 'deadline_guard.py', 'run_raw_kl_transition.py',
    'verify_phase_snapshot.py', 'verify_maintenance_checkpoint.py', 'cuda_trace_parent.py',
    'cuda_trace_worker.py', 'checkpoint_at_frame.py', 'whole_agent_smoke.py',
    'parallel_state_fill_trial.py', 'inference_worker_affinity.py', 'cpu_reservation_trial.py',
    'run_forward_ce_repair.py'}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def read_file(path, limit=MAX_TEXT, allow_empty=False):
    path = Path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and (0 if allow_empty else 1) <= before.st_size <= limit,
            'Expected bounded regular file: '+str(path))
        data = stream.read(limit+1)
        require(len(data) == before.st_size and identity(os.fstat(stream.fileno())) == identity(before)
            == identity(path.lstat()), 'File changed: '+str(path))
    return data, dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data), identity=identity(before))


def pinned(pin):
    data, actual = read_file(pin['path'])
    require(actual == pin, 'Exact saved PIN changed: '+pin['path'])
    return json.loads(data)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_bytes(path, data, allow_empty=False):
    path = Path(path)
    require((0 if allow_empty else 1) <= len(data) <= MAX_TEXT, 'Archive size exceeds bound')
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        sealed = identity(os.fstat(stream.fileno()))
    sync_directory(path.parent)
    actual_data, pin = read_file(path, allow_empty=allow_empty)
    require(actual_data == data and pin['identity'] == sealed, 'Archive changed')
    return pin


def publish(path, value):
    return write_bytes(path, (json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


def command(argv, timeout=15):
    result = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    require(len(result.stdout) <= MAX_TEXT and len(result.stderr) <= MAX_TEXT, 'Full command output exceeds archive bound')
    return dict(argv=argv, returncode=result.returncode,
        stdout=result.stdout.decode('utf-8', 'surrogateescape'),
        stderr=result.stderr.decode('utf-8', 'surrogateescape'), observed_unix_s=time.time())


def fields(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def show(unit):
    result = command(['systemctl', '--user', 'show', unit, '--all'])
    value = fields(result['stdout'])
    require(result['returncode'] == 0 or value.get('LoadState') == 'not-found', 'Unit show failed: '+unit)
    require('LoadState' in value, 'No authoritative LoadState: '+unit)
    return value, result


def process_start(pid):
    try:
        text = Path('/proc', str(pid), 'stat').read_text()
    except FileNotFoundError:
        return None
    return int(text[text.rfind(')')+2:].split()[19])


def cgroup_empty(group):
    root = Path('/sys/fs/cgroup')/group.lstrip('/')
    if not root.exists():
        return
    paths = list(root.rglob('cgroup.procs'))
    require(len(paths) <= 512, 'Unexpected owned cgroup extent')
    for path in paths:
        require(not path.read_text().split(), 'Owned/private child remains: '+str(path))


def bound_owner(label, observed):
    expected = OWNERS[label]
    require(observed['unit'] == expected['unit'] and observed['pid'] == observed['original_pid'] == expected['pid']
        and observed['starttime_ticks'] == expected['starttime_ticks']
        and observed['invocation'] == expected['invocation_id'] and observed['nrestarts'] == '0',
        'Original observed identity differs: '+label)
    group = ('/user.slice/user-%s.slice/user@%s.service/app.slice/%s' %
        (os.getuid(), os.getuid(), expected['unit']))
    return dict(expected, cgroup=group)


def original_terminal(owner, value):
    require(value.get('LoadState') != 'not-found' and value.get('MainPID') == '0'
        and value.get('ExecMainPID') == str(owner['pid'])
        and value.get('InvocationID') == owner['invocation_id'] and value.get('NRestarts') == '0'
        and value.get('ControlGroup') in ('', owner['cgroup'])
        and value.get('ExecMainCode') not in (None, '', '0'), 'Original is not retained terminal: '+owner['unit'])


def parents_terminal(owners, released=(), require_absent=True):
    result = {}
    for label, owner in owners.items():
        value, raw = show(owner['unit'])
        if owner['unit'] in released and value.get('LoadState') == 'not-found':
            cgroup_empty(owner['cgroup'])
        else:
            original_terminal(owner, value)
        if require_absent:
            require(process_start(owner['pid']) != owner['starttime_ticks'], 'Original PID still alive')
            cgroup_empty(owner['cgroup'])
        result[label] = (value, raw)
    return result


def archive_command(output, name, raw, plain=False, journal=False):
    record = dict(raw)
    if plain:
        record['stdout_PIN'] = write_bytes(output/(name+'.txt'), raw['stdout'].encode('utf-8', 'surrogateescape'),
            allow_empty=journal)
    record['command_PIN'] = publish(output/(name+'-command.json'), raw)
    return record


def check_trial(trial, deadline, ce, activation):
    require(trial['status'] == 'COMPLETE' and trial['manual_recovery_required'] is False
        and trial['qualification_pass'] is False and trial.get('candidate') is not None,
        'Trial not COMPLETE; root explicit forward repair/reconciliation required')
    require(deadline['status'] == 'RETIRED' and 0 <= deadline['absence']['elapsed_s'] <= 3600
        and deadline['absence']['proof']['state'] == 'ABSENT'
        and deadline['absence']['proof']['old_process_present'] is False
        and deadline['absence']['proof']['cgroup_occupied'] is False
        and deadline['adopted']['owner'] == trial['retired_owner'] == activation['owner'],
        'Independent timely exact KL absence missing')
    require(ce['status'] == 'READY' and ce['manual_recovery_required'] is False
        and ce['qualification_pass'] is False and ce['owner'] != activation['owner']
        and ce['startup_phase_proof']['phase']['expected']['metric'] == 'ce'
        and not ce['first_resume']['failures'] and not ce['final_resume']['failures'],
        'Actual new CE return/admission proof missing')
    return ce['owner']


def actual_process(expected, group):
    pid = expected['pid']
    require(process_start(pid) == expected['starttime_ticks'], 'Process start changed')
    root = Path('/proc')/str(pid)
    uid = next(line.split()[1:] for line in (root/'status').read_text().splitlines() if line.startswith('Uid:'))
    require(list(map(int, uid)) == expected['uid']
        and [os.fsdecode(x) for x in (root/'cmdline').read_bytes().split(b'\0') if x] == expected['cmdline']
        and os.readlink(root/'cwd') == expected['cwd'] and os.readlink(root/'exe') == expected['exe']
        and (root/'cgroup').read_text().strip() == '0::'+group, 'Process identity/cgroup changed')
    mask = sorted(os.sched_getaffinity(pid))
    require(process_start(pid) == expected['starttime_ticks'], 'Process changed during identity proof')
    return mask


def current_ce_and_resources(job, activation_job, activation, ce, record):
    owner = ce['owner']; current, _ = show(owner['unit'])
    require(current['MainPID'] == str(owner['pid']) and current['InvocationID'] == owner['invocation_id']
        and current['ControlGroup'] == owner['cgroup'] and current['ActiveState'] == 'active'
        and current['SubState'] == 'running' and current['Restart'] == 'no', 'New CE owner not retained/running')
    original = activation_job['before']; binding = ce['healthy']['binding']
    phase_proof = pinned(ce['startup_phase_proof']['phase_CPU'])
    phase = ce['startup_phase_proof']['phase']
    ce_record = pinned(phase['record'])
    require(phase_proof['status'] == 'PASS' and phase_proof['phase_metadata_verified'] is True
        and phase_proof['saved_priority_metric_phase']['metric'] == 'ce'
        and phase_proof['saved_priority_metric_phase']['valid'] is True
        and phase_proof['saved_priority_metric_phase']['phase_id'] == phase['expected']['phase_id']
        and phase_proof['saved_priority_metric_phase']['phase_record_sha256'] == phase['record']['sha256']
        and ce_record['action'] == 'start' and ce_record['metric'] == 'ce' and ce_record['previous_metric'] == 'kl'
        and ce_record['checkpoint'] == {key:ce['boot_checkpoint']['source'][key] for key in ('path','sha256','bytes')}
        and phase_proof['root_job']['phase_snapshot']['owner'] == owner
        and phase_proof['root_job']['phase_snapshot']['observed_clients'] == 0,
        'Actual CE startup strict phase proof differs')
    require(binding['bindings']['actors'] == original['bindings']['actors']
        and binding['bindings']['source_hashes'] == activation['installed_sources']
        and binding['bindings']['control_hashes'] == original['bindings']['control_hashes']
        and binding['fleet']['MainPID'] == original['fleet']['MainPID']
        and binding['supervisor_start_ticks'] == original['supervisor_start_ticks'], 'CE fleet/source closure differs')
    masks = {str(actor['pid']): actual_process(actor, original['bindings']['fleet_cgroup'])
        for actor in original['bindings']['actors']}
    require(len(masks) == 192 and masks == activation_job['actor_masks'], 'Original192 masks changed')
    worker = binding['bindings']['worker']; main_mask = actual_process(worker['trainer'], owner['cgroup'])
    require(main_mask == activation_job['worker_mask'], 'Main affinity changed')
    fleet, _ = show(activation_job['fleet_unit'])
    require(fleet['MainPID'] == original['fleet']['MainPID']
        and fleet['ControlGroup'] == original['fleet']['ControlGroup']
        and process_start(int(fleet['MainPID'])) == original['supervisor_start_ticks'], 'Fleet supervisor changed')
    environment = dict(os.fsdecode(part).split('=',1) for part in
        Path('/proc',str(owner['pid']),'environ').read_bytes().split(b'\0') if b'=' in part)
    require(all(environment.get(key) == value for key,value in binding['environment'].items())
        and environment.get('DQN_PER_PRIORITY_METRIC') == 'ce'
        and not any(environment.get(key) for key in ('DQN_RECOMPUTED_CE_CAPTURE_DIR','DQN_EXECUTED_CE_TRACE_DIR')),
        'Actual CE environment changed')
    tid = worker['thread']; require(process_start(tid['tid']) == tid['starttime_ticks'], 'Inference TID changed')
    inference = sorted(os.sched_getaffinity(tid['tid']))
    require(inference == activation_job['worker_mask']
        and Path('/proc', str(owner['pid']), 'task', str(tid['tid'])).exists(), 'Inference membership/mask changed')
    hashes = {}
    for path, digest in dict(activation['installed_sources'], **original['bindings']['control_hashes']).items():
        _, pin = read_file(path); require(pin['sha256'] == digest, 'Held source/control changed: '+path); hashes[path] = digest
    for label, files in original['unit_files'].items():
        for path, digest in files.items():
            _, pin = read_file(path); require(pin['sha256'] == digest, 'Held unit source changed')
    for unit in (EARLY_UNIT, EARLY_UNIT.removesuffix('.service')+'.timer'):
        value, _ = show(unit); require(value['LoadState'] == 'not-found', 'Early CPU unit still loaded')
    observed_actors = set()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry/'cmdline').read_bytes().split(b'\0')
        except OSError as error:
            if error.errno in (2, 3): continue
            raise
        require(not any(os.path.basename(os.fsdecode(arg)) in BLOCKED for arg in argv if arg),
            'Parent/private numerical helper remains: '+entry.name)
        if argv and os.path.basename(os.fsdecode(argv[0])) == 'mame' and b'robotron' in argv:
            observed_actors.add(int(entry.name))
    require(observed_actors == {actor['pid'] for actor in original['bindings']['actors']},
        'Global Robotron MAME inventory is not exactly the original192')
    private = list(Path('/dev/shm').glob('robotron-snapshot-smoke-*'))
    require(not any(p.is_dir() for p in private), 'Private tmpfs remains')
    app = Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')
    for group in app.parent.glob('robotron-snapshot-smoke-*'):
        cgroup_empty('/'+str(group.relative_to('/sys/fs/cgroup')))
    cgroup_empty('/user.slice/user-%s.slice/user@%s.service/app.slice/%s' % (os.getuid(), os.getuid(), EARLY_UNIT))
    for table in ('tcp', 'tcp6'):
        for line in Path('/proc/net', table).read_text().splitlines()[1:]:
            row = line.split(); require(not (row[3] == '0A' and int(row[1].rsplit(':',1)[1],16) == 9999), 'Port9999 listener remains')
    lease = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
    before = lease.lstat(); require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid(), 'Lease identity differs')
    fd = os.open(lease, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd)) == identity(before) == identity(lease.lstat()), 'Lease open race')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)
    gpu = command(['nvidia-smi', '--query-gpu=index,uuid', '--format=csv,noheader,nounits'])
    apps = command(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'])
    require(gpu['returncode'] == apps['returncode'] == 0, 'GPU observation failed')
    gpu_map = {int(row.split(',')[0].strip()):row.split(',')[1].strip() for row in gpu['stdout'].splitlines() if row.strip()}
    app_rows = [(int(row.split(',')[0].strip()),row.split(',')[1].strip()) for row in apps['stdout'].splitlines() if row.strip()]
    require(gpu_map == GPU_UUIDS and app_rows == [(owner['pid'], GPU_UUIDS[1])],
        'Known GPU mapping differs/GPU0 not free/main not sole GPU1 process')
    record('GPU-index-map', gpu); record('GPU-processes', apps)
    # API values can legitimately contain a NaN grad_norm for a recorded AMP skip.
    # Preserve raw response bytes; no parser or gradient-value rewrite.
    import urllib.request
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=3) as response:
        raw = response.read(2 << 20)
    api = json.loads(raw); pipeline = api['host_pipeline']; graphs = pipeline['inference_graphs']
    require(api['client_count'] == 192 and api['training_enabled'] is True
        and 0 <= time.time()-float(api['ts']) <= 5
        and pipeline['learning_exposure']['optimizer']['process_id'] == owner['pid']
        and pipeline['learning_exposure']['replay']['process_id'] == owner['pid']
        and graphs['ready'] and graphs['capture_count'] == 128 and graphs['validation_replay_count'] == 640
        and graphs['postload_validations'] >= 1 and graphs['runtime_capture_count'] == graphs['fallback_count'] == 0
        and graphs['fatal_error'] is None and all(pipeline[key]['errors'] == 0 for key in
            ('inference','actor_refresh','target_refresh','learner_priority'))
        and all(api[key] >= phase_proof['clocks'][key] for key in CLOCKS),
        'Current CE192/graphs/API owner differs')
    after, _ = show(owner['unit'])
    require(process_start(owner['pid']) == owner['starttime_ticks'] and after['MainPID'] == str(owner['pid'])
        and after['InvocationID'] == owner['invocation_id'], 'CE owner changed during cleanup proof')
    return dict(owner=owner, actor_masks=masks, main_mask=main_mask, inference_mask=inference,
        source_control_hashes=hashes, GPU0_free=True, sole_main_on_GPU1=True,
        lease_unheld=True, port9999_unused=True, no_private_tmpfs_or_helpers=True), raw


def release_one(unit, owners, released, record):
    exact = {owner['unit'] for owner in owners.values()}
    exact.update(value.removesuffix('.service')+'.timer' for value in tuple(exact))
    require(unit in exact, 'No release authority for another unit')
    parents_terminal(owners, released)
    before, raw = show(unit); record('release-before-'+unit, raw)
    if before['LoadState'] == 'not-found':
        return dict(unit=unit, already_absent=True, actual_stop_returncode=None, final_load_state='not-found')
    stopped = command(['systemctl', '--user', 'stop', unit], timeout=30); record('stop-'+unit, stopped)
    after, raw = show(unit); record('release-after-stop-'+unit, raw)
    if stopped['returncode'] != 0:
        require(stopped['returncode'] == 5 and after['LoadState'] == 'not-found'
            and stopped['stderr'].strip() in {f'Unit {unit} not loaded.',
                f'Failed to stop {unit}: Unit {unit} not loaded.'}, 'Exact stop failed: '+unit)
    reset = None
    if after['LoadState'] != 'not-found' and after.get('ActiveState') == 'failed':
        parents_terminal(owners, released)
        reset = command(['systemctl', '--user', 'reset-failed', unit]); record('reset-failed-'+unit, reset)
        require(reset['returncode'] == 0, 'Exact archived failed-unit reset failed')
    until = time.monotonic()+5
    while True:
        after, raw = show(unit)
        if after['LoadState'] == 'not-found' or time.monotonic() >= until: break
        time.sleep(.1)
    record('release-final-'+unit, raw)
    require(after['LoadState'] == 'not-found', 'Exact unit still loaded: '+unit)
    return dict(unit=unit, already_absent=False, actual_stop_returncode=stopped['returncode'],
        reset_failed_returncode=None if reset is None else reset['returncode'], final_load_state='not-found')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256'); parser.add_argument('--expected-source-sha256')
    parser.add_argument('--output-directory', type=Path); args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: archive both original trial02 terminals before exact owned release; no reads/actions')
        return 0
    require(args.job == JOB and args.expected_job_sha256 == JOB_SHA and args.output_directory is not None,
        'Exact actual trial02 root job and NEW output required')
    _, source = read_file(Path(__file__).resolve())
    require(source['sha256'] == args.expected_source_sha256 and source['identity']['mode'] == '0o444'
        and source['identity']['uid'] == os.getuid() and source['identity']['nlink'] == 1, 'Cleanup source changed/not sealed')
    data, job_pin = read_file(args.job)
    require(job_pin['sha256'] == JOB_SHA and job_pin['identity']['mode'] == '0o444'
        and job_pin['identity']['uid'] == os.getuid() and job_pin['identity']['nlink'] == 1, 'Root job changed/not sealed')
    job = json.loads(data); output = args.output_directory
    require(output.is_absolute() and output == output.resolve(strict=False) and output.parent == RUN
        and not output.exists(), 'NEW direct run26 output required')
    owners = {}; historical = {}
    for label in OWNERS:
        data, pin = read_file(OBSERVED[label]); observed = json.loads(data)
        owners[label] = bound_owner(label, observed); historical[label] = (data, pin)
    # No output creation or mutation at all while either original MainPID is nonzero.
    originals = parents_terminal(owners, require_absent=False)
    output.mkdir(mode=0o700); sync_directory(output.parent)
    commands = []
    def record(name, raw):
        pin = publish(output/('%03d-'%len(commands)+name+'-raw-command.json'), raw)
        commands.append(pin); return pin
    result = dict(schema=SCHEMA, status='PRESERVING_ORIGINALS', owned_cleanup_complete=False,
        qualification_pass=False, root_job=job_pin, source=source, original_executions={},
        output_directory=str(output), raw_commands=commands, releases=[])
    try:
        for label, owner in owners.items():
            value, raw = originals[label]
            saved_show = archive_command(output, label+'-original-show', raw, plain=True)
            cat = command(['systemctl','--user','cat',owner['unit']]); require(cat['returncode'] == 0, 'Original unit cat failed')
            saved_cat = archive_command(output, label+'-original-cat', cat, plain=True)
            journal = command(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+owner['invocation_id'],'--no-pager','-o','short-iso-precise'])
            require(journal['returncode'] == 0, 'Original invocation journal failed')
            saved_journal = archive_command(output, label+'-original-journal', journal, plain=True, journal=True)
            launch_dir = LAUNCH/('controller' if label=='trial_controller' else 'deadline')
            provenance = {}
            for name, data in [('root-observed-identity.json', historical[label][0]),
                ('root-launch-intent.json', read_file(launch_dir/'root-launch-intent.json')[0])]:
                provenance[name] = write_bytes(output/(label+'-'+name), data)
            timer = owner['unit'].removesuffix('.service')+'.timer'; timer_show, timer_raw = show(timer)
            record(label+'-timer-show',timer_raw); record(label+'-timer-cat',command(['systemctl','--user','cat',timer]))
            result['original_executions'][label] = dict(owner=owner, show=saved_show['stdout_PIN'],
                cat=saved_cat['stdout_PIN'], journal=saved_journal['stdout_PIN'],
                show_command=saved_show['command_PIN'], cat_command=saved_cat['command_PIN'],
                journal_command=saved_journal['command_PIN'], root_launch_and_observed=provenance,
                exec_code=int(value['ExecMainCode']), exit_status=int(value['ExecMainStatus']),
                result=value.get('Result'), archived_before_release=True, released=False)
        # All originals (including failures), timer evidence and root provenance are durable before this point.
        result['original_archive'] = publish(output/'original-executions-before-any-release.json',
            dict(schema=SCHEMA, original_executions=result['original_executions'], root_job=job_pin, source=source))
        trial_data, trial_pin = read_file(Path(job['output_directory'])/'result.json'); trial=json.loads(trial_data)
        result['actual_trial_status']=trial['status']
        result['actual_trial_result']=dict(original=trial_pin, archive=write_bytes(output/'actual-trial-result.json',trial_data))
        deadline_data, deadline_pin = read_file(Path(job['output_directory'])/'deadline-result.json'); deadline=json.loads(deadline_data)
        result['actual_deadline_result']=dict(original=deadline_pin, archive=write_bytes(output/'actual-deadline-result.json',deadline_data))
        activation=pinned(trial['activation']); ce=pinned(trial['CE_return'])
        result['CE_return']=trial['CE_return']
        result['actual_CE_return_status']=ce['status']
        ce_owner=check_trial(trial,deadline,ce,activation)
        require(all(x['exec_code']==1 and x['exit_status']==0 and x['result']=='success'
            for x in result['original_executions'].values()), 'Original parent failure; root explicit forward repair required')
        parents_terminal(owners)
        act_job=pinned(job['activation_job'])
        resources, raw_api=current_ce_and_resources(job,act_job,activation,ce,record)
        result['current_CE_and_resources']=publish(output/'current-CE-192-resources.json',resources)
        result['current_CE_raw_API']=write_bytes(output/'current-CE-raw-API.json',raw_api)
        released=[]; releases=result['releases']
        order=[owner['unit'].removesuffix('.service')+'.timer' for owner in owners.values()]
        order += [owner['unit'] for owner in owners.values()]
        for unit in order:
            releases.append(release_one(unit,owners,released,record));released.append(unit)
            for entry in result['original_executions'].values():
                if entry['owner']['unit'] == unit: entry['released']=True
        result.update(status='PASS_OWNED_TERMINAL_CLEANUP',owned_cleanup_complete=True,
            actual_trial_status='COMPLETE',new_CE_owner=ce_owner,original_archived_before_release=True,
            releases=releases,root_forward_repair_required=False,root_reconciliation_required=False)
        publish(output/'cleanup-receipt.json',result)
        return 0
    except BaseException as error:
        result.update(status='ARCHIVED_REQUIRES_ROOT_RECONCILIATION',error=repr(error),traceback=traceback.format_exc(),
            owned_cleanup_complete=False,root_reconciliation_required=True,
            root_forward_repair_required=True if result.get('actual_trial_status')=='FAILED'
                or result.get('actual_CE_return_status')=='FAILED' else None)
        publish(output/'cleanup-receipt.json',result)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
