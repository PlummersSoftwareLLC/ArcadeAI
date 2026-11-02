"""One root-owned KL trial, literal PLAN by default; SOURCE PREPARATION ONLY.

The separate deadline_guard invocation must be armed first. This controller
performs no automatic trial/candidate/CPU retry and never boots older bytes.
"""
import argparse
import base64
import copy
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback

SCHEMA = 'robotron-one-raw-kl-trial-job-v1'
ADAPTER = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/live_transition_post_stop_floor_companion/run_raw_kl_transition.py')
ADAPTER_SHA = '7d0aa20b5ef4fc1d6c889718ee688387cd684cf702cced503714435132b949d6'
HORIZON = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/sequential_trial_precommit_proposal/horizon_observer_proposal/horizon_observer.py')
HORIZON_SHA = '25d70b4a3888dcba83ea9020c333cba32cfbd19c93b6e69037d6299b161fd7ec'
PLAN = 'PLAN_ONLY: one precommitted KL trial; no reads/helper imports/runtime/actions'
JOURNAL_BYTES = 32 << 20


def require(value, message):
    if not value:
        raise RuntimeError(message)


def load(path, sha, name):
    data = Path(path).read_bytes()
    require(hashlib.sha256(data).hexdigest() == sha, 'Consumed source changed: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def bounded_copy_dispatch(base, trial, activation):
    """Local adapter for genuine source/JSON callers of V4's model-only copier.

    V4's checkpoint copier remains unchanged. Only the pinned eight source names,
    exact managed request slots/owned request temp, and declared metadata PINs
    may use the small-file branch into this trial's three new output roots.
    """
    original = base.exclusive_copy
    roots = [Path(trial['output_directory']), Path(activation['output_directory']),
        Path(trial['return_intent']['output_directory'])]
    package = Path(activation['game_root']) / 'Scripts/dqn'
    model = Path(activation['model_dir'])
    metadata = set()
    def collect(value):
        if isinstance(value, dict):
            if set(value) == {'path', 'sha256', 'bytes', 'identity'} and value['bytes'] <= base.MAX_SOURCE:
                metadata.add(value['path'])
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(activation)
    names = {'__init__.py', 'model.py', 'config.py', 'learning_control.py',
        'agent.py', 'training.py', 'loss_kernel.py', 'priority_phase.py'}
    def copy_file(source, target):
        source, target = Path(source), Path(target)
        require(target.is_absolute() and target == target.resolve(strict=False)
            and target.parent == target.parent.resolve(strict=True)
            and any(target.is_relative_to(root) for root in roots), 'Copy destination escapes a known trial root')
        if source.suffix == '.pt':
            return original(source, target)  # inherited model size/identity rules
        require(any(target.is_relative_to(root) for root in roots)
            and target.suffix in ('.py', '.json', '.txt'), 'Small-copy destination is not a known trial archive')
        known = (str(source) in metadata or source.parent == package and source.name in names
            or source.parent == model and (source.name in ('managed_save.request.json',
                'managed_save.request.json.completed', 'managed_save.request.json.failed')
                or source.name.startswith('.managed-phase-request-')))
        require(known, 'Unregistered small-copy source')
        before = base.fingerprint(source, base.MAX_SOURCE)
        require(0 < before['bytes'] <= base.MAX_SOURCE and before['identity']['uid'] == os.getuid()
            and before['identity']['nlink'] == 1, 'Small-copy size/owner/link policy differs')
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as src, target.open('xb') as dst:
            require(base.identity(os.fstat(src.fileno())) == before['identity'], 'Small-copy open race')
            for chunk in iter(lambda: src.read(1 << 20), b''):
                dst.write(chunk)
            require(base.identity(os.fstat(src.fileno())) == before['identity'], 'Small-copy source changed')
            dst.flush(); os.fchmod(dst.fileno(), 0o444); os.fsync(dst.fileno())
        base.fsync_directory(target.parent)
        require(base.fingerprint(source, base.MAX_SOURCE) == before, 'Small-copy path changed')
        copied = base.fingerprint(target, base.MAX_SOURCE)
        require(copied['sha256'] == before['sha256'] and copied['bytes'] == before['bytes']
            and (copied['identity']['device'], copied['identity']['inode']) !=
                (before['identity']['device'], before['identity']['inode']), 'Small independent copy differs')
        return before, copied
    base.exclusive_copy = copy_file


def raw_api_publication(base, deadline, trial, activation):
    strict = base.publish
    roots = [Path(trial['output_directory']), Path(activation['output_directory']),
        Path(trial['return_intent']['output_directory'])]
    names = {'API-before-resume.json', 'API-after192.json', 'trigger-API.json', 'pre-ending-health.json'}
    def publish(path, value):
        path = Path(path)
        if path.name in names and any(path.is_relative_to(root) for root in roots):
            # Raw API may legitimately contain unrelated grad_norm NaN on a
            # recorded AMP skip. Retain that token; do not change any counters,
            # finite model/scaler checks or ordinary strict JSON publications.
            return deadline.publish(path, value, allow_nan=True)
        return strict(path, value)
    base.publish = publish


def observer_job(adapter, horizon, base, activation, activation_pin):
    start = base.read_json(activation['start_request'])
    before = base.read_json(activation['before_resume_api_PIN'])
    job = dict(schema=horizon.SCHEMA, owner=activation['owner'],
        start_request={key:start[key] for key in ('boot_id', 'monotonic_s', 'unix_s')},
        boot_four_clocks=activation['boot_four_clocks'],
        healthy192_monotonic_s=activation['healthy192_monotonic_s'],
        trial_core_sha256=activation['trial_core']['sha256'],
        activation_receipt_sha256=activation_pin['sha256'],
        before_resume_api=before, policy=copy.deepcopy(horizon.POLICY))
    horizon.validate_job(job)
    require(start['phase_record'] == activation['phase_record']
        and start['trial_core'] == activation['trial_core'], 'Activation/start source lineage differs')
    return job


def live_api_plan(runtime, observer, baseline_csv):
    exposure = observer['before_resume_api']['host_pipeline']['learning_exposure']
    # Metrics ABI deliberately has three keys; the frozen horizon separately
    # keeps epoch_reason as its fourth identity component.
    return dict(batch_size=4096, replay_cap=8, initial_snapshot=dict(csv=baseline_csv),
        exposure_identity={kind:runtime.metrics.exposure_key(exposure[kind]) for kind in ('optimizer', 'replay')})


def durable_event(event, observer, root, *, publish, get_clock):
    """Never reinterpret the first decision if its durable publication is late."""
    path = root / ('observation-%04d.json' % event['sequence'])
    event_pin = publish(path, event)  # fsync of file and directory completes here
    completed = get_clock()
    require(completed['boot_id'] == observer['start_request']['boot_id'], 'Boot changed at receipt completion')
    require(completed['monotonic_s'] >= event['observed_monotonic_s']
        >= observer['start_request']['monotonic_s'], 'Receipt time precedes actual observation/start')
    elapsed = completed['monotonic_s'] - observer['start_request']['monotonic_s']
    receipt = dict(event=event_pin, completed_monotonic_s=completed['monotonic_s'],
        elapsed_s=elapsed, boot_id=completed['boot_id'],
        scope='Measured completion of the original event file+directory fsync; this metadata is published afterward')
    receipt_pin = publish(root / ('durability-%04d.json' % event['sequence']), receipt)
    if event['state'] == 'LATCH':
        require(elapsed <= 3240, 'Original LATCH publication completed after3240; retain decision, no candidate')
    return dict(event=event_pin, durability=receipt_pin)


class ReceiptJournal:
    """Fixed32MiB total, with metadata space reserved before each event write."""
    def __init__(self, *, publish, get_clock, root, observer):
        self.publish, self.get_clock, self.root, self.observer = publish, get_clock, root, observer
        self.used = 0; self.failure = None

    def emit(self, event):
        require(self.failure is None, 'Original receipt failure cannot be retried/replaced')
        def write(path, value):
            data_size = len((json.dumps(value, indent=2, allow_nan=True) + '\n').encode())
            if path.name.startswith('durability-'):
                require(data_size <= 4096, 'Durability metadata exceeds pre-reserved space')
            require(self.used + data_size <= JOURNAL_BYTES, 'Journal byte limit exceeded')
            result = self.publish(path, value)
            self.used += data_size
            return result
        try:
            size = len((json.dumps(event, indent=2, allow_nan=True) + '\n').encode())
            require(self.used + size + 4096 <= JOURNAL_BYTES, 'Fixed32MiB observation journal exhausted')
            return durable_event(event, self.observer, self.root, publish=write, get_clock=self.get_clock)
        except BaseException as error:
            self.failure = repr(error)
            raise


def install_action_boundary(runtime, deadline, lock, *, before_CE_start=None, before_KL_start=None):
    """Reuse LiveHost methods; replace only the short systemctl request boundary."""
    host = runtime.host
    def command(*args):
        # Ordinary source/sidecar gates run OUTSIDE the short mutation lock. The
        # independent deadline uses its own source-independent exact-owner path.
        host.no_sidecars()
        operation = args[0]
        expected = runtime.trainer_id() if operation == 'stop' and host.known_trainer else None
        with lock.hold():
            if operation == 'stop' and expected is not None:
                observed = deadline.classify(expected)
                require(observed['state'] in ('SAME', 'ABSENT'), 'Refusing stop after owner replacement')
                if observed['state'] == 'ABSENT':
                    return subprocess.CompletedProcess(args, 0, '', '')
            if operation == 'start':
                require(host.unit(runtime.job['trainer_unit'])['MainPID'] == '0', 'A new owner appeared before start')
                host.assert_retired_absent()
                if before_CE_start is not None:
                    before_CE_start()
                elif before_KL_start is not None:
                    before_KL_start()
            return subprocess.run(['systemctl', '--user', *args], capture_output=True,
                text=True, check=True, timeout=10)
    host.command = command


def registered_terminal(registration, entry, runtime, *, read_terminal, fields=None):
    owner = registration.get('owner')
    require(owner is not None and owner['pid'] == int(entry.name), 'No previously observed owned CPU terminal identity')
    if fields is None:
        result = subprocess.run(['systemctl', '--user', 'show', registration['unit'], '--all',
            '-p', 'LoadState', '-p', 'MainPID', '-p', 'ExecMainPID', '-p', 'InvocationID',
            '-p', 'ControlGroup', '-p', 'NRestarts', '-p', 'ExecMainCode', '-p', 'ExecMainStatus',
            '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result'],
            capture_output=True, text=True, check=False, timeout=5)
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if fields.get('LoadState') == 'not-found':
        require(read_terminal is not None and registration.get('terminal_archive') is not None,
            'Collected unit defaults cannot prove the original CPU terminal state')
        original = read_terminal(registration['terminal_archive'])
        require(original['original_owner'] == owner and original['original_pid'] == owner['pid']
            and original['original_invocation'] == owner['invocation_id']
            and original['original_nrestarts'] == 0 and original['original_exec_code'] in (1, 2, 3),
            'Archived original CPU identity/status differs')
    else:
        require(fields.get('LoadState') == 'loaded' and fields['MainPID'] == '0'
            and fields['ExecMainPID'] == str(owner['pid']) and fields['InvocationID'] == owner['invocation_id']
            and fields['NRestarts'] == '0' and fields['SubState'] in ('exited', 'dead', 'failed')
            and int(fields['ExecMainCode']) in (1, 2, 3)
            and fields['ControlGroup'] in ('', owner['cgroup']), 'Registered CPU is not its original retained terminal')
    try:
        start = runtime.metrics.identity.stat_fields((entry / 'stat').read_text())['starttime_ticks']
    except OSError as error:
        if error.errno not in (errno.ENOENT, errno.ESRCH): raise
        start = None
    require(start is None, 'Classified PID still exists or was reused; no inherited CPU scanner exemption')
    members = Path('/sys/fs/cgroup') / owner['cgroup'].lstrip('/') / 'cgroup.procs'
    require(not members.exists() or not members.read_text().split(), 'Original CPU cgroup is not empty')
    return True


def _owned_cpu(registration, entry, argv, runtime, *, adopt, read_terminal, get_registration):
    """Only the registered ONE retained strict7d worker or its exact carrier."""
    if registration is None:
        return False
    observed = [os.fsdecode(value) for value in argv if value]
    pid = int(entry.name)
    if observed == registration['command']:
        unit = subprocess.run(['systemctl', '--user', 'show', registration['unit'], '--all',
            '-p', 'LoadState', '-p', 'MainPID', '-p', 'ExecMainPID', '-p', 'InvocationID',
            '-p', 'ControlGroup', '-p', 'NRestarts', '-p', 'ExecMainCode', '-p', 'ExecMainStatus',
            '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result'],
            capture_output=True, text=True, check=False, timeout=5)
        fields = dict(line.split('=', 1) for line in unit.stdout.splitlines() if '=' in line)
        if fields.get('LoadState') == 'not-found' or fields.get('MainPID') == '0':
            current = get_registration() if get_registration else registration
            return registered_terminal(current, entry, runtime, read_terminal=read_terminal, fields=fields)
        require(fields['MainPID'] == str(pid) and re.fullmatch('[0-9a-f]{32}', fields['InvocationID'])
            and fields['NRestarts'] == '0' and fields['ControlGroup'].endswith('/' + registration['unit']),
            'Registered CPU unit/argv identity differs')
        fields_before = runtime.metrics.identity.stat_fields((entry / 'stat').read_text())
        status = dict(line.split(':', 1) for line in (entry / 'status').read_text().splitlines() if ':' in line)
        require([int(value) for value in status['Uid'].split()] == [os.getuid()] * 4
            and (entry / 'cwd').resolve() == Path(runtime.job['game_root'])
            and (entry / 'exe').resolve() == Path(registration['command'][0]).resolve(),
            'Registered CPU executable/cwd/UID differs')
        require((entry / 'cgroup').read_text().strip() == '0::' + fields['ControlGroup'], 'Registered CPU left its unit')
        actual = dict(pid=pid, starttime_ticks=fields_before['starttime_ticks'], unit=registration['unit'],
            invocation_id=fields['InvocationID'], cgroup=fields['ControlGroup'])
        require(registration['owner'] is None or registration['owner'] == actual, 'Registered CPU owner replaced')
        # The requested exact argv includes the job/source digest flags. No
        # unrelated verifier with the same basename receives this allowance.
        require(registration['job']['path'] in observed and registration['job']['sha256'] in observed,
            'Registered CPU argv lacks its exact immutable job')
        require((entry / 'cmdline').read_bytes().split(b'\0') == argv, 'Registered CPU argv changed')
        require(runtime.metrics.identity.stat_fields((entry / 'stat').read_text())['starttime_ticks']
            == fields_before['starttime_ticks'], 'Registered CPU PID changed during identity check')
        adopt(actual)
        return True
    if observed == registration['argv']:
        # The short systemd-run carrier is our direct child in OUR cgroup; its
        # reaped return must precede its detached3s timer's numerical invocation.
        carrier = registration['carrier']
        fields = runtime.metrics.identity.stat_fields((entry / 'stat').read_text())
        status = dict(line.split(':', 1) for line in (entry / 'status').read_text().splitlines() if ':' in line)
        require(carrier is not None and carrier['pid'] == pid and carrier['reaped'] is False
            and carrier['starttime_ticks'] == fields['starttime_ticks'] and carrier['argv'] == observed
            and int(status['PPid'].strip()) == os.getpid()
            and (entry / 'cgroup').read_text() == Path('/proc/self/cgroup').read_text(),
            'Unregistered scheduling carrier ancestry/cgroup')
        require((entry / 'cmdline').read_bytes().split(b'\0') == argv, 'Scheduling argv changed')
        require(runtime.metrics.identity.stat_fields((entry / 'stat').read_text())['starttime_ticks']
            == fields['starttime_ticks'], 'Scheduling PID changed during exact identity check')
        return True
    return False


def owned_cpu(registration, entry, argv, runtime, *, adopt, read_terminal=None, get_registration=None):
    try:
        return _owned_cpu(registration, entry, argv, runtime, adopt=adopt,
            read_terminal=read_terminal, get_registration=get_registration)
    except OSError as error:
        if error.errno not in (errno.ENOENT, errno.ESRCH) or registration is None:
            raise
        require([os.fsdecode(value) for value in argv if value] == registration['command'],
            'Only the exact registered numerical child has a terminal disappearance join')
        current = get_registration() if get_registration else registration
        return registered_terminal(current, entry, runtime, read_terminal=read_terminal)


def allow_registered_early_cpu(runtime, base, helper_getter):
    """Exact copied ea4c scanner plus a single registered child identity join."""
    def exclusive():
        helper = helper_getter()
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal() or int(entry.name) == os.getpid():
                continue
            try:
                argv = (entry / 'cmdline').read_bytes().split(b'\0')
            except OSError as error:
                if error.errno in (errno.ENOENT, errno.ESRCH):
                    continue  # only initial unclassified cmdline churn
                raise
            names = set(base.BLOCKED) | {'run_raw_kl_transition.py', 'verify_phase_snapshot.py'}
            if any(os.path.basename(os.fsdecode(arg)) in names for arg in argv if arg):
                registration = None if helper is None else helper.registration()
                require(owned_cpu(registration, entry, argv, runtime,
                    adopt=helper.adopt_cpu if helper is not None else lambda owner: None,
                    read_terminal=base.read_json, get_registration=None if helper is None else helper.registration),
                    'Competing owned helper ' + entry.name)
        runtime.request_guard()
        require(not any(item.is_dir() for item in Path('/dev/shm').glob('robotron-snapshot-smoke-*')),
            'Private diagnostic tmpfs remains')
        app = Path('/sys/fs/cgroup') / runtime.job['before']['trainer']['ControlGroup'].lstrip('/')
        for group in app.parent.glob('robotron-snapshot-smoke-*'):
            members = list(group.rglob('cgroup.procs'))
            require(len(members) <= 256 and all(not item.read_text().split() for item in members),
                'Private cgroup remains populated')
    runtime.exclusive = exclusive


def physical_retirement(deadline, owner, lock, *, get_clock, sleep, publish, root, origin):
    """Failure boundary only: no CPU, source repair, replacement adoption or boot."""
    result = dict(owner=owner, stop=None, absence=None, qualification_pass=False)
    try:
        result['stop'] = deadline.request_stop(owner, lock)
    except BaseException as error:
        result['stop_error'] = repr(error)
    stop_wait_deadline = time.monotonic() + 240
    while True:
        now = get_clock()
        try:
            observed = deadline.classify(owner)
            completed = get_clock()
            if observed['state'] == 'ABSENT':
                result.update(status='RETIRED', absence=observed,
                    observed_monotonic_s=completed['monotonic_s'],
                    within_owner_ceiling=None if origin is None else completed['monotonic_s'] <= origin + 3600)
                break
            if observed['state'] not in ('SAME', 'RETIRING'):
                result.update(status='MANUAL_RECONCILIATION', observation=observed); break
        except Exception as error:
            result['last_probe_error'] = repr(error)
        if (origin is not None and now['monotonic_s'] >= origin + 3600) or time.monotonic() >= stop_wait_deadline:
            result.update(status='CEILING_BREACH'); break
        sleep(1)
    try:
        publish(root / 'failure-retirement.json', result)
    except BaseException as error:
        result['receipt_error'] = repr(error)
    return result


def require_deadline_retirement(deadline, root, owner):
    report = deadline.read_pin(deadline.pin(root / 'deadline-result.json')[0])
    require(report['status'] == 'RETIRED' and report['adopted']['owner'] == owner
        and report['absence']['elapsed_s'] <= 3600
        and report['absence']['proof']['state'] == 'ABSENT',
        'Independent physical retirement proof absent; no CE start')
    return report


def ending_candidate(adapter, base, deadline, helper, runtime, spec, root, event, early, observer):
    require(event['state'] == 'LATCH' and early['status'] == 'PASS', 'First LATCH requires already-PASS early insurance')
    floor = adapter.clock_max(base.read_json(early['insurance_report'])['clocks'],
        adapter.four(event['first_eligible_observation']))
    began = deadline.clock()['monotonic_s']
    runtime.host.pause(dict(initial=runtime.job['before']))
    require(deadline.clock()['monotonic_s'] - began <= 10, 'Candidate pause exceeded fixed10s reserve')
    snapshot = helper.Snapshot(adapter, base, runtime,
        dict(tag=spec['tag'], save_timeout_s=60), root)
    snapshot.start(runtime.raw_api(), floor)
    while True:
        result = snapshot.tick()
        require(result['status'] != 'FAILED', 'First candidate save failed; no replacement')
        if result['status'] == 'COMPLETE':
            break
        require(deadline.clock()['monotonic_s'] - began <= 70, 'First candidate save exceeded reserve')
        time.sleep(.25)
    candidate = snapshot.freeze(purpose='candidate', phase=spec['phase'])
    finished = deadline.clock()
    require(finished['monotonic_s'] - began <= 70
        and finished['monotonic_s'] <= observer['start_request']['monotonic_s'] + 3310,
        'First candidate freeze missed reserved stop-intent time; no second candidate')
    return candidate


def make_return_job(adapter, base, runtime, trial, activation, observer_pin, decision_pin,
                    candidate, early, before, root):
    """All slow preparation happens AFTER actual known KL stop/absence."""
    runtime.absence()
    result = copy.deepcopy(runtime.job)
    intent = trial['return_intent']
    core = dict(schema='robotron-raw-kl-owned-return-intent-v1', mode='return_ce',
        phase_id=intent['phase_id'], trial_core=activation['trial_core'],
        activation_owner=activation['owner'], original_start=activation['start_request'],
        decision=decision_pin, early_insurance=early['insurance_report'])
    core_pin = base.publish(root / 'return-intent-core.json', core)
    result.update(mode='return_ce', before=before, phase_id=intent['phase_id'],
        request_id=intent['request_id'], startup_tag=intent['startup_tag'],
        output_directory=intent['output_directory'], trial_core=core_pin,
        sources=[], running_phase=activation['startup_phase_proof']['phase'],
        completed_dormant_capture=None, current_completed_request=copy.deepcopy(runtime.current_completed),
        insurance_verification=early['insurance_report'], insurance_receipt=early['saved_receipt'],
        verifier=early['verifier'], baseline_csv=trial['pre_ending_csv'],
        ending_proof=dict(observer_job=observer_pin, activation_receipt=trial['activation_receipt'],
            decision=decision_pin, candidate=candidate))
    result['settings_lifecycle']['initial'] = copy.deepcopy(runtime.settings.current)
    result['original_dropin'].update(content_base64=base64.b64encode(runtime.host.dropin_expected).decode(),
        mode=0o644)
    result['helper_pins']['controller'] = copy.deepcopy(trial['sources']['adapter'])
    require(result['schema'] == adapter.SCHEMA and result['running_phase']['expected']['metric'] == 'kl',
        'Return must retain the actual running KL founder phase')
    jp = base.publish(root / 'return-job.json', result)
    # The frozen read_job now checks actual model bytes/metadata and the ending
    # context; these operations cannot delay the already completed KL stop.
    args = argparse.Namespace(job=Path(jp['path']), expected_job_sha256=jp['sha256'],
        expected_controller_sha256=ADAPTER_SHA)
    checked, checked_pin = adapter.read_job(args, base)
    require(checked == result and checked_pin == jp, 'Prepared return job changed')
    return checked, jp


def inherit_retirement(previous, following, owner, *, lease_path=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')):
    """Transfer an existing owned lease and registered retirement, not a PID observation."""
    previous.absence()
    require(previous.retired_owner == previous.retirement_candidate == owner
        and previous.host.known_trainer is not None
        and previous.host.known_trainer['pid'] == owner['pid']
        and previous.host.known_trainer['identity'] in previous.host.retired_trainers,
        'No exact known registered KL retirement to transfer')
    following.host.adopt_initial(following.job['before'])
    require(following.host.known_trainer['identity'] == previous.host.known_trainer['identity'],
        'Return host would adopt a different prior owner')
    following.host.retired_trainers = copy.deepcopy(previous.host.retired_trainers)
    following.retirement_candidate = copy.deepcopy(owner)
    following.retired_owner = copy.deepcopy(owner)
    following.settings = previous.settings
    require(following.lease_fd is None and previous.lease_fd is not None,
        'Retired handoff must preserve the same existing lease FD')
    held = os.fstat(previous.lease_fd)
    require((held.st_dev, held.st_ino) == (lease_path.lstat().st_dev, lease_path.lstat().st_ino)
        and held.st_uid == os.getuid(), 'Held lease FD is not the exact original lease path')
    fcntl.flock(previous.lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # same open description; no unlock/reopen
    following.lease_fd, previous.lease_fd = previous.lease_fd, None
    following.host.paused, previous.host.paused = previous.host.paused, []
    require(previous.host.metric_host is not None, 'The genuine prior bound log reader is missing')
    following.host.metric_host = previous.host.metric_host
    following.host.current = copy.deepcopy(following.job['before'])
    following.host.metric_host.configure_logs(following.job['before']['bindings']['logs'])
    following.host.begin_transition_logs(following.job['before']['bindings']['logs'],
        following.job['before']['trainer_stdout'])
    following.absence()


def return_after_retirement(adapter, base, runtime, owner):
    """Pinned ea4c granular tail; candidate and latest CPU precede any CE start."""
    result = dict(schema=adapter.RESULT_SCHEMA, mode='return_ce', status='RUNNING',
        qualification_pass=False, manual_recovery_required=False)
    try:
        runtime.absence()
        result['ending'] = runtime.post_stop_ending(owner)
        boot = runtime.stopped_checkpoint(owner, 'newest-stopped')
        banks = runtime.banks.stopped_state(runtime.job['bank_spec'])
        # Candidate5 remains byte-identical. No reconciliation or rollback here.
        for path, digest in runtime.expected_sources('after').items():
            require(base.fingerprint(path, base.MAX_SOURCE)['sha256'] == digest,
                'Source changed before explicit CE start: ' + path)
        new_owner = runtime.start_phase()
        loaded = runtime.ready_transport('after', banks, actors=False)
        raw = runtime.raw_api(); adapter.zero_replay(raw, new_owner['pid'])
        startup = runtime.startup_snapshot(raw)
        before = runtime.raw_api(); require(before['client_count'] == 0, 'Actors admitted before CE startup proof')
        adapter.zero_replay(before, new_owner['pid'])
        bp = base.publish(runtime.output / 'API-before-resume.json', before)
        runtime.inspect('after'); runtime.banks.assert_unchanged(banks, runtime.job['bank_spec'])
        resumed = base.resume_all(runtime.host); require(not resumed['failures'], 'Original actor resume failed')
        healthy = runtime.ready_transport('after', banks, actors=True)
        result.update(status='READY', owner=new_owner, start_request=runtime.start_request,
            boot_checkpoint=boot, startup_phase_proof=startup, loaded=loaded,
            before_resume_api_PIN=bp, healthy=healthy, first_resume=resumed)
    except BaseException as error:
        result.update(status='FAILED', error=repr(error), traceback=traceback.format_exc(),
            manual_recovery_required=True)
        if runtime.start_request is not None:
            try:
                unit = runtime.host.unit(runtime.job['trainer_unit'])
                if unit['MainPID'] != '0':
                    require(runtime.host.known_trainer is not None, 'Unadopted CE process; manual only')
                    for actor in runtime.job['before']['bindings']['actors']:
                        if actor not in runtime.host.paused:
                            with runtime.metrics.block_restore_signals():
                                runtime.host.paused.append(actor)
                                runtime.host.signal_actor(actor, signal.SIGSTOP)
                    runtime.host.wait_paused()
                    result['failed_requested_CE_retired'] = runtime.stop_owned()
                else: runtime.absence()
            except BaseException as cleanup:
                result['new_CE_stop_error'] = repr(cleanup)
        # No second boot, invalid-phase repair or historical checkpoint restore.
    finally:
        result['final_resume'] = base.resume_all(runtime.host)
        result['CPU_ledger'] = dict(runtime.cpu_attempts)
        if result['final_resume']['failures']:
            result['manual_recovery_required'] = True
    return result


def run(trial, *, adapter, horizon, helper, base, deadline, root, armed):
    lock = deadline.ActionLock(armed['lock_path'], armed['lock_identity'])
    activation_job = deadline.read_pin(trial['activation_job'])
    args = argparse.Namespace(job=Path(trial['activation_job']['path']),
        expected_job_sha256=trial['activation_job']['sha256'], expected_controller_sha256=ADAPTER_SHA)
    job, jp = adapter.read_job(args, base)
    require(job == activation_job and job['mode'] == 'activate_kl', 'Only the one planned activation is allowed')
    output = Path(job['output_directory']); output.mkdir(mode=0o700)
    base.publish(output / 'root-job.json', job)
    backups = output / 'sources'; backups.mkdir(mode=0o700)
    runtime = adapter.runtime_class(base)(job, output)
    require(runtime.insured == trial['old_owner'], 'Deadline plan does not bind the actual insured old CE owner')
    def guard_KL_start():
        require(deadline.process_start(armed['pid']) == armed['starttime_ticks']
            and not (root / 'deadline-result.json').exists(),
            'Independent deadline is no longer armed; no KL start')
    install_action_boundary(runtime, deadline, lock, before_KL_start=guard_KL_start)
    following = None; early = None; activation = None; observer = None; start_origin = None; journal = None
    allow_registered_early_cpu(runtime, base, lambda: early)
    result = dict(schema='robotron-one-raw-kl-trial-result-v1', status='RUNNING',
        qualification_pass=False, manual_recovery_required=False)
    try:
        with runtime.metrics.interrupt_handlers():
            activation, primary = adapter.transition(runtime, base.Sources(job['sources'], backups), base)
            activation_pin = deadline.publish(output / 'result.json', activation)
            result['activation'] = activation_pin
            require(activation['status'] == 'READY' and not activation['manual_recovery_required']
                and primary is None, 'Original activation failed; no second start')
            adopted = deadline.read_adoption(activation_job, armed['planned'])
            require(adopted is not None and adopted['owner'] == activation['owner'], 'No exact durable KL adoption')
            start_origin = adopted['start']['monotonic_s']
            observer = observer_job(adapter, horizon, base, activation, activation_pin)
            observer_pin = deadline.publish(root / 'observer-job.json', observer)
            journal = ReceiptJournal(publish=lambda path, value: deadline.publish(path, value, allow_nan=True),
                get_clock=deadline.clock, root=root, observer=observer)
            early_root = root / 'early-insurance'
            early = helper.EarlyInsurance(adapter, base, runtime, trial['early_insurance'], early_root)
            early_started = False; terminal_receipt = None
            local = live_api_plan(runtime, observer, job['baseline_csv'])
            def evidence():
                nonlocal early_started
                for source_pin in trial['sources'].values():
                    require(deadline.pin(source_pin['path'])[0] == source_pin, 'One-trial source identity changed')
                if not early_started:
                    early.start(); early_started = True
                early.tick()
                state = early.result()
                require(state['status'] != 'FAILED', 'First early insurance failed; no replacement')
                runtime.inspect('after')
                row = runtime.host.capture()
                issues = runtime.metrics.api_issues(row, local)
                compatible_events = runtime.fault_scan()  # unchanged strict predicate; may return supported events
                require(not issues, 'Held192 source/recipe/journal/exposure guard failed: ' + repr(issues))
                return dict(ok=True, owner=activation['owner'], early_insurance_status=state['status'])
            def emit(event):
                nonlocal terminal_receipt
                receipt = journal.emit(event)
                if event['state'] != 'CONTINUE':
                    terminal_receipt = receipt
            event = horizon.poll(observer, get_api=runtime.raw_api, get_owner=runtime.trainer_id,
                get_evidence=evidence, get_clock=deadline.clock, sleep=time.sleep, emit=emit)
            result.update(observer=observer_pin, decision=terminal_receipt)
            require(event['state'] in ('LATCH', 'INCOMPLETE'), 'Original observer INVALID; manual forward boundary')
            early_result = early.result()
            require(early_result['status'] == 'PASS', 'Early insurance not PASS at first ending; no candidate or wait')
            # Source/192 proof is taken BEFORE pause, and no return read_job or
            # checkpoint validation is placed before the immediate ending stop.
            before = runtime.inspect('after'); row = runtime.host.capture()
            require(not runtime.metrics.api_issues(row, local), 'Pre-ending healthy192 proof failed')
            base.publish(root / 'pre-ending-health.json', dict(before=before, API=row))
            candidate = None
            if event['state'] == 'LATCH':
                candidate_root = root / 'candidate'
                candidate = ending_candidate(adapter, base, deadline, helper, runtime,
                    dict(tag=trial['candidate_tag'], phase=activation['startup_phase_proof']['phase']),
                    candidate_root, event, early_result, observer)
            else:
                runtime.host.pause(dict(initial=runtime.job['before']))
            owner = runtime.stop_owned()
            require(owner == activation['owner'], 'Ending retired a different owner')
            result['retired_owner'] = owner
            final_faults = runtime.host.transition_log_events()  # AFTER stop, before resetting offsets
            result['final_KL_faults'] = base.publish(root / 'final-KL-transition-log-events.json', final_faults)
            require(all(event.get('intentional_restart_compatible') is True for event in final_faults),
                'Late KL runtime fault before retirement; no ordinary CE return')
            # Record exact independent absence BEFORE a possible new CE owner
            # can occupy the same cgroup and make that proof unavailable.
            until = time.monotonic() + 10
            while not (root / 'deadline-result.json').exists() and time.monotonic() < until:
                time.sleep(.1)
            require_deadline_retirement(deadline, root, owner)
            derived = copy.deepcopy(trial)
            derived.update(activation_receipt=activation_pin, pre_ending_csv=row['csv'])
            return_job, return_pin = make_return_job(adapter, base, runtime, derived, activation,
                observer_pin, terminal_receipt['event'], candidate, early_result, before, root)
            return_root = Path(return_job['output_directory']); return_root.mkdir(mode=0o700)
            base.publish(return_root / 'root-job.json', return_job)
            following = adapter.runtime_class(base)(return_job, return_root)
            inherit_retirement(runtime, following, owner)
            install_action_boundary(following, deadline, lock,
                before_CE_start=lambda: require_deadline_retirement(deadline, root, owner))
            ce = return_after_retirement(adapter, base, following, owner)
            result['CE_return'] = base.publish(return_root / 'result.json', ce)
            require(ce['status'] == 'READY' and not ce['manual_recovery_required'], 'Newest-state CE return failed; no retry')
            result.update(status='COMPLETE' if event['state'] == 'LATCH' else 'INCOMPLETE_RETURNED_CE',
                candidate=candidate, early_insurance=early_result['insurance_report'])
    except BaseException as error:
        result.update(status='FAILED', error=repr(error), traceback=traceback.format_exc(), manual_recovery_required=True)
        if activation is not None and activation.get('status') == 'READY':
            # No metadata read/log/source gate before attempting known-owner
            # retirement. A missing cached clock never permits a different PID.
            try:
                result['failure_retirement'] = physical_retirement(deadline, activation['owner'], lock,
                    get_clock=deadline.clock, sleep=time.sleep, publish=deadline.publish, root=root, origin=start_origin)
            except BaseException as cleanup:
                result['failure_retirement_error'] = repr(cleanup)
    finally:
        # No logging/source/API/insurance condition gates the attempted undo.
        result['final_resume'] = dict(activation_host=base.resume_all(runtime.host),
            return_host=None if following is None else base.resume_all(following.host))
        if result['final_resume']['activation_host']['failures'] or (
                result['final_resume']['return_host'] is not None and result['final_resume']['return_host']['failures']):
            result['manual_recovery_required'] = True
        if early is not None:
            result['early_insurance_at_terminal'] = early.result()
        if journal is not None:
            result['observation_journal'] = dict(maximum_bytes=JOURNAL_BYTES,
                durably_written_bytes=journal.used, first_failure=journal.failure)
        if following is not None:
            following.close()
        runtime.close()
    return result


def read_trial(args, deadline):
    self_pin, _ = deadline.pin(__file__)
    require(self_pin['sha256'] == args.expected_controller_sha256, 'Controller source differs')
    jp, _ = deadline.pin(args.job)
    require(jp['sha256'] == args.expected_job_sha256, 'Root trial job differs')
    trial = deadline.read_pin(jp)
    require(trial['schema'] == SCHEMA and trial['sources']['controller'] == self_pin,
        'Wrong one-trial/source binding')
    require(trial['sources']['adapter']['path'] == str(ADAPTER)
        and trial['sources']['adapter']['sha256'] == ADAPTER_SHA
        and trial['sources']['horizon']['path'] == str(HORIZON)
        and trial['sources']['horizon']['sha256'] == HORIZON_SHA,
        'Frozen adapter/horizon must remain unchanged')
    require(trial['deadlines'] == dict(latch_s=3240, stop_intent_s=3310, owner_ceiling_s=3600),
        'One-trial deadlines differ')
    require(trial['observation_budget_bytes'] == JOURNAL_BYTES, 'Fixed observer journal budget differs')
    activation = deadline.read_pin(trial['activation_job'])
    require(activation['mode'] == 'activate_kl' and activation['trial_core'] == trial['trial_core']
        and activation['boot_id'] == trial['boot_id'], 'Activation/core/boot binding differs')
    core = deadline.read_pin(trial['trial_core'])
    deadline.validate_authorization(core, activation)
    require(trial['early_insurance']['save_timeout_s'] == 60 and trial['early_insurance']['cpu_timeout_s'] == 120,
        'Early insurance bounds differ')
    tags = [trial['candidate_tag'], trial['early_insurance']['tag'], activation['startup_tag'],
        trial['return_intent']['startup_tag']]
    require(len(set(tags)) == 4 and all(re.fullmatch('[A-Za-z0-9_-]{1,80}', value or '') for value in tags),
        'Exactly one unique tag per operation is required')
    root = Path(trial['output_directory'])
    armed_pin, _ = deadline.pin(root / 'deadline-armed.json')
    require(armed_pin['sha256'] == args.expected_armed_sha256, 'Exact independently armed receipt required')
    armed = deadline.read_pin(armed_pin)
    require(armed['job'] == jp and armed['source'] == trial['sources']['deadline']
        and armed['planned']['old_owner'] == trial['old_owner']
        and armed['clock']['boot_id'] == trial['boot_id']
        and deadline.process_start(armed['pid']) == armed['starttime_ticks'],
        'Independent deadline process is not currently the exact armed owner')
    require(Path(armed['lock_path']) == root / 'unit-actions.lock', 'Unexpected unit-action lock path')
    return trial, jp, root, armed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256'); parser.add_argument('--expected-controller-sha256')
    parser.add_argument('--expected-armed-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print(PLAN); return 0
    require(args.job and args.expected_job_sha256 and args.expected_controller_sha256
        and args.expected_armed_sha256, 'Explicit actual root bindings required')
    require(not any(name == 'torch' or name.startswith(('torch.', 'numpy', 'dqn')) for name in sys.modules),
        'Fresh stdlib-only parent required')
    # Authenticate the sibling as data before its first import. The independent
    # deadline invocation has already authenticated this same immutable job.
    data = args.job.read_bytes()
    require(0 < len(data) <= 2 << 20 and hashlib.sha256(data).hexdigest() == args.expected_job_sha256,
        'Root job changed before helper bootstrap')
    draft = json.loads(data)
    source = draft['sources']['deadline']
    require(source['path'] == str(Path(__file__).parent / 'deadline_guard.py'), 'Unexpected deadline sibling')
    deadline = load(source['path'], source['sha256'], '_one_kl_deadline_bootstrap')
    trial, jp, root, armed = read_trial(args, deadline)
    for value in trial['sources'].values():
        require(deadline.pin(value['path'])[0] == value, 'Consumed source PIN changed')
    adapter = load(ADAPTER, ADAPTER_SHA, '_one_kl_transition')
    horizon = load(HORIZON, HORIZON_SHA, '_one_kl_horizon')
    helper = load(trial['sources']['early_insurance']['path'], trial['sources']['early_insurance']['sha256'], '_one_kl_early')
    base = adapter.load_v4()
    bounded_copy_dispatch(base, trial, deadline.read_pin(trial['activation_job']))
    raw_api_publication(base, deadline, trial, deadline.read_pin(trial['activation_job']))
    result = run(trial, adapter=adapter, horizon=horizon, helper=helper, base=base,
        deadline=deadline, root=root, armed=armed)
    result['root_job'] = jp
    deadline.publish(root / 'result.json', result)
    return 0 if result['status'] in ('COMPLETE', 'INCOMPLETE_RETURNED_CE') and not result['manual_recovery_required'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
