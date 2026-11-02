"""Independent exact-owner deadline for an UNCONSUMED CE batch2048 trial.

Literal PLAN by default. This process is armed before the activation invocation;
it never infers a new CE2048 PID from the previous CE unit's current MainPID.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

SCHEMA = 'robotron-one-ce-batch2048-trial-job-v1'
EXECUTION_BLOCKERS = ('actual2048 producer capture/bind integration is incomplete',
    'honest phase early-insurance return consumer/provenance integration is incomplete',
    'current private CE2048 numerical readiness is unbound',
    'future actual root precommit and owner/checkpoint bindings are unbound')
PROFILE_PATH = '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_profile_horizon_proposal/profile.json'
PROFILE_SHA = 'e755e22ade5cb56537b08f41f412e856da09435d88e4e71e09b22aba521eac50'
PROFILE_BYTES = 764
PROFILE_VALUE = {'LR_compensation': False, 'batch_size': 2048, 'before_batch_size': 4096, 'deliberate_recipe_changes': ['DQN_BATCH_SIZE'], 'held_recipe_context': {'baseline_batch_size': 512, 'batch_size': 2048, 'c51_target_smoothing': 0, 'epsilon': 0.1, 'expert_ratio': 0.1, 'fused': True, 'gamma': 0.995, 'learning_control_lr_scale': 0.5, 'lr_anchor_step': 0.0, 'lr_gear': 'climb', 'max_samples_per_frame': 8, 'n_step': 3, 'num_atoms': 51, 'optimizer_eps': 0.00015, 'optimizer_lr': 2.5e-05, 'v_max': 50.0, 'v_min': -10.0}, 'priority_metric': 'ce', 'profile_id': 'ce_batch2048_efficacy_screen_v1', 'return_batch_size': 4096, 'schema': 'robotron-ce-batch2048-efficacy-profile-v1'}
OWNER_KEYS = {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'}
LIMIT = 2 << 20
STOP_INTENT_S = 3310
CEILING_S = 3600
FINAL_CORE_STATUS = 'FINAL_PRECOMMITTED_ROOT_AUTHORIZED'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def pin(path, maximum=LIMIT):
    path = Path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum,
            'Expected bounded regular metadata: ' + str(path))
        data = stream.read(maximum + 1)
        require(identity(os.fstat(stream.fileno())) == identity(before) == identity(path.lstat()),
            'Metadata changed while reading: ' + str(path))
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data), identity=identity(before)), data


def read_pin(expected):
    observed, data = pin(expected['path'])
    require(observed == expected and observed['identity']['uid'] == os.getuid()
        and observed['identity']['mode'] == '0o444' and observed['identity']['nlink'] == 1,
        'Immutable owned metadata PIN differs')
    return json.loads(data)


def profile_binding(profile, *, read=read_pin):
    require(isinstance(profile, dict) and
        {k:profile.get(k) for k in ('path','sha256','bytes')} ==
            dict(path=PROFILE_PATH, sha256=PROFILE_SHA, bytes=PROFILE_BYTES),
        'Exact immutable CE2048 profile required')
    value = read(profile)
    require(value == PROFILE_VALUE, 'Declared profile value differs')
    return dict(pin={k:profile[k] for k in ('path','sha256','bytes')}, value=value)


def validate_authorization(core, activation, *, read=read_pin):
    profile = core.get('batch_profile')
    binding = profile_binding(profile, read=read)
    boundary = activation['batch_boundary']
    require(core.get('activation_authorized') is True and core.get('status') == FINAL_CORE_STATUS
        and core.get('mode') == activation['mode'] == 'activate_batch2048'
        and core.get('phase_id') == activation['phase_id']
        and boundary['mode'] == 'activate_batch2048' and boundary['profile_binding'] == binding
        and boundary['before_batch_size'] == 4096 and boundary['after_batch_size'] == 2048
        and boundary['priority_metric'] == 'ce',
        'Only the exact final authorized CE4096-to-CE2048 start may execute/arm')


def publish(path, value, *, allow_nan=False):
    data = (json.dumps(value, indent=2, allow_nan=allow_nan) + '\n').encode()
    require(len(data) <= LIMIT, 'Metadata receipt exceeds bound')
    with Path(path).open('xb') as stream:
        stream.write(data); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(path)[0]


def clock():
    return dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        monotonic_s=time.monotonic(), wall_s=time.time())


def process_start(pid):
    try:
        text = Path('/proc', str(pid), 'stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return int(text[text.rfind(')') + 2:].split()[19])


def show(unit):
    result = subprocess.run(['systemctl', '--user', 'show', unit, '--all',
        '-p', 'MainPID', '-p', 'ActiveState', '-p', 'ControlGroup', '-p', 'InvocationID'],
        capture_output=True, text=True, check=True, timeout=5)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def classify(owner):
    """Absence is observed independently of a successful stop return code."""
    require(set(owner) == OWNER_KEYS, 'Exact adopted KL identity is required')
    unit = show(owner['unit'])
    start = process_start(owner['pid'])
    old_present = start == owner['starttime_ticks']
    members = Path('/sys/fs/cgroup') / owner['cgroup'].lstrip('/') / 'cgroup.procs'
    occupied = members.exists() and bool(members.read_text().split())
    if old_present:
        require(unit['MainPID'] in ('0', str(owner['pid'])) and unit['InvocationID'] == owner['invocation_id']
            and unit['ControlGroup'] in ('', owner['cgroup']), 'Exact KL process is no longer its bound unit owner')
        try:
            require(Path('/proc', str(owner['pid']), 'cgroup').read_text().strip() == '0::' + owner['cgroup'],
                'Exact KL process left its owned cgroup')
        except OSError as error:
            if error.errno not in (2, 3): raise
            return dict(state='RETIRING', unit=unit, old_process_present=None, cgroup_occupied=occupied)
        if unit['MainPID'] == '0':
            return dict(state='RETIRING', unit=unit, old_process_present=True, cgroup_occupied=occupied)
        return dict(state='SAME', unit=unit, old_process_present=True, cgroup_occupied=occupied)
    if unit['MainPID'] == '0' and not occupied and unit['InvocationID'] in ('', owner['invocation_id']):
        return dict(state='ABSENT', unit=unit, old_process_present=False, cgroup_occupied=False)
    if unit['MainPID'] in ('0', str(owner['pid'])) and unit['InvocationID'] == owner['invocation_id']:
        return dict(state='RETIRING', unit=unit, old_process_present=False, cgroup_occupied=occupied)
    # A new CE owner may already be present. It is NEVER a stop target here.
    return dict(state='REPLACEMENT_OR_OTHER_MEMBERS', unit=unit,
        old_process_present=False, cgroup_occupied=occupied)


class ActionLock:
    """Only short check->unit mutation sections; never save/copy/CPU/wait."""
    def __init__(self, path, expected):
        self.path, self.expected = Path(path), expected

    @contextlib.contextmanager
    def hold(self):
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            require(identity(os.fstat(fd)) == self.expected == identity(self.path.lstat()),
                'Owned unit-action lock changed')
            deadline = time.monotonic() + 15
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                except BlockingIOError:
                    require(time.monotonic() < deadline, 'Unit-action lock exceeded short bounded section')
                    time.sleep(.05)
            yield
        finally:
            os.close(fd)


def request_stop(owner, lock, *, probe=classify, command=subprocess.run):
    with lock.hold():
        observed = probe(owner)
        if observed['state'] == 'SAME':
            try:
                result = command(['systemctl', '--user', 'stop', '--no-block', owner['unit']],
                    capture_output=True, text=True, check=False, timeout=5)
            except BaseException as error:
                # Command submission may have happened before a timeout/error;
                # never call that a mere pre-request guard refusal.
                return dict(requested=True, outcome_unknown=True, error=repr(error), before=observed)
            return dict(requested=True, returncode=result.returncode,
                stdout=result.stdout[-4096:], stderr=result.stderr[-4096:], before=observed)
        return dict(requested=False, before=observed)


def read_requested(activation, planned, *, read=read_pin):
    """Validate an actual start clock without granting any PID authority."""
    root = Path(activation['output_directory'])
    path = root / 'owned-start-request.json'
    try: info = path.lstat()
    except FileNotFoundError: return None
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
        and 0 <= info.st_size <= LIMIT, 'Foreign/malformed activation marker')
    if stat.S_IMODE(info.st_mode) != 0o444: return None
    start_pin = pin(path)[0]; start = read(start_pin)
    require(start['schema'] == 'robotron-live8-owned-trainer-start-request-v1'
        and start['request_id'] == activation['request_id'] == planned['request_id']
        and start['trial_core'] == activation['trial_core']
        and start['insured_trainer'] == planned['old_owner']
        and start['unit'] == planned['old_owner']['unit']
        and start['cgroup'] == planned['old_owner']['cgroup']
        and start['experiment'] == activation['experiment'] and start['model_dir'] == activation['model_dir']
        and start['source_phase'] == 'after'
        and start['owned_start_requested'] is True and start['boot_id'] == planned['boot_id'],
        'Start marker does not bind the planned CE2048 start')
    record = read(start['phase_record'])
    require(record['metric'] == 'ce' and record['phase_id'] == activation['phase_id']
        and record['action'] == 'start' and record['root_precommit_sha256'] == activation['trial_core']['sha256'],
        'Start is not the precommitted CE2048 phase')
    return dict(start=start, start_pin=start_pin)


def read_adoption(activation, planned, *, read=read_pin):
    """An absent/being-published lineage is pending, never an adopted PID."""
    requested = read_requested(activation, planned, read=read)
    if requested is None: return None
    path = Path(activation['output_directory']) / 'owned-start-lineage.json'
    try: info = path.lstat()
    except FileNotFoundError: return None
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
        and 0 <= info.st_size <= LIMIT, 'Foreign/malformed adoption marker')
    if stat.S_IMODE(info.st_mode) != 0o444: return None
    lineage_pin = pin(path)[0]; lineage = read(lineage_pin)
    start, start_pin = requested['start'], requested['start_pin']
    owner = lineage['retired_trainer']
    require(set(owner) == OWNER_KEYS and owner != planned['old_owner']
        and owner['unit'] == start['unit'] and owner['cgroup'] == start['cgroup']
        and lineage['schema'] == 'robotron-live8-owned-restart-lineage-v1'
        and lineage['insured_trainer'] == planned['old_owner']
        and lineage['experiment'] == start['experiment'] and lineage['model_dir'] == start['model_dir']
        and lineage['source_phase'] == 'after'
        and lineage['authorized_start_adopted'] is True and lineage['unknown_replacement_adopted'] is False
        and lineage['request_id'] == start['request_id'] and lineage['start_request'] == start_pin,
        'No exact durable requested/adopted KL lineage')
    return dict(owner=owner, start=start, start_pin=start_pin, lineage_pin=lineage_pin)


def supervise(*, adoption, get_clock, probe, stop, sleep, emit, requested=None, maximum_polls=5402):
    """No source/API/journal/resource gate can prevent the exact-owner stop."""
    stop_attempt = None; stop_requested = False; guard_refusals = []
    errors = []; adopted = None; pending_start = None
    def report(result):
        try: emit(result)
        except Exception as error:
            result['publication_error'] = repr(error)
            try: print(json.dumps(result), flush=True)
            except Exception: pass
        return result
    for _ in range(maximum_polls):
        now = get_clock()
        if adopted is None:
            try:
                adopted = adoption()
                if requested is not None and pending_start is None: pending_start = requested()
            except Exception as error:
                errors.append(repr(error)[:512]); errors = errors[-32:]
            if adopted is None:
                if pending_start is not None:
                    origin = pending_start['start']
                    require(now['boot_id'] == origin['boot_id'], 'Boot changed during unadopted startup')
                    if now['monotonic_s'] - origin['monotonic_s'] >= STOP_INTENT_S:
                        return report(dict(status='UNADOPTED_START_MANUAL', start_request=pending_start,
                            observed_monotonic_s=now['monotonic_s'], errors=errors,
                            stop_requested=False, qualification_pass=False,
                            reason='Known fixed start origin reached ending intent without an adopted PID; never guess or stop old CE'))
                sleep(1); continue
        require(now['boot_id'] == adopted['start']['boot_id'], 'Boot changed')
        elapsed = now['monotonic_s'] - adopted['start']['monotonic_s']
        # Deadline action is independent of normal observation/source/reporting
        # failures. stop performs its own fresh exact identity check under lock.
        if elapsed >= STOP_INTENT_S and not stop_requested:
            stop_attempt = dict(attempted_at=now['monotonic_s'], result=None)
            try:
                stop_attempt['result'] = stop(adopted['owner'])
                stop_requested = bool(stop_attempt['result'] and stop_attempt['result'].get('requested'))
            except BaseException as error:
                stop_attempt['error'] = repr(error)
                guard_refusals.append(dict(stop_attempt))
                guard_refusals = guard_refusals[-320:]
        try:
            # Once an exact durable requested/adopted identity is known, a later
            # source/marker/log fault must not suppress that owner's deadline.
            observed = probe(adopted['owner'])
            now = get_clock()  # receipt time AFTER the potentially slow probe
            require(now['boot_id'] == adopted['start']['boot_id'], 'Boot changed')
            elapsed = now['monotonic_s'] - adopted['start']['monotonic_s']
            if observed['state'] == 'ABSENT':
                absent = dict(observed_monotonic_s=now['monotonic_s'], elapsed_s=elapsed, proof=observed)
                result = dict(status='RETIRED' if elapsed <= CEILING_S else 'CEILING_BREACH',
                    adopted=adopted, absence=absent, stop_attempt=stop_attempt, guard_refusals=guard_refusals, errors=errors,
                    qualification_pass=False)
                return report(result)
            if observed['state'] not in ('SAME', 'RETIRING'):
                # Never stop a replacement/new CE process. A missing independent
                # inactive/empty proof cannot be reconstructed from that owner.
                result = dict(status='MANUAL_RECONCILIATION', adopted=adopted,
                    observation=observed, stop_attempt=stop_attempt, guard_refusals=guard_refusals, errors=errors, qualification_pass=False)
                return report(result)
            if elapsed >= CEILING_S:
                result = dict(status='CEILING_BREACH', adopted=adopted, observation=observed,
                    stop_attempt=stop_attempt, guard_refusals=guard_refusals, errors=errors, qualification_pass=False)
                return report(result)
        except Exception as error:
            errors.append(repr(error)[:512]); errors = errors[-32:]
            # Reporting/normal source gates are deliberately outside stop(). An
            # identity probe failure cannot authorize a different PID or kill.
        now = get_clock()
        if now['monotonic_s'] - adopted['start']['monotonic_s'] >= CEILING_S:
            return report(dict(status='ABSENCE_UNPROVEN_AT_CEILING', adopted=adopted,
                observed_monotonic_s=now['monotonic_s'], stop_attempt=stop_attempt,
                guard_refusals=guard_refusals, errors=errors, qualification_pass=False))
        sleep(1)
    result = dict(status='UNBOUND_OR_UNOBSERVABLE_MANUAL', adopted=adopted,
        stop_attempt=stop_attempt, guard_refusals=guard_refusals, errors=errors, qualification_pass=False)
    return report(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path); parser.add_argument('--expected-job-sha256')
    parser.add_argument('--expected-source-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: independent one-trial exact-owner deadline; no reads/actions')
        return 0
    require(not EXECUTION_BLOCKERS, 'UNCONSUMED CE2048: ' + '; '.join(EXECUTION_BLOCKERS))
    require(args.job and args.expected_job_sha256 and args.expected_source_sha256, 'Explicit root bindings required')
    self_pin, _ = pin(__file__)
    require(self_pin['sha256'] == args.expected_source_sha256, 'Deadline source changed')
    jp, _ = pin(args.job); require(jp['sha256'] == args.expected_job_sha256, 'Job changed')
    job = read_pin(jp); require(job['schema'] == SCHEMA, 'Unexpected trial schema')
    require(job['sources']['deadline'] == self_pin, 'Deadline job/source binding differs')
    activation = read_pin(job['activation_job'])
    core = read_pin(activation['trial_core'])
    validate_authorization(core, activation)
    require(job['profile'] == core['batch_profile'], 'Trial profile differs from final authorized core')
    root = Path(job['output_directory']); root.mkdir(mode=0o700)
    lock_path = root / 'unit-actions.lock'
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        lock_identity = identity(os.fstat(fd)); os.fsync(fd)
    finally:
        os.close(fd)
    now = clock(); require(now['boot_id'] == job['boot_id'], 'Boot differs before arm')
    planned = dict(old_owner=job['old_owner'], request_id=activation['request_id'], boot_id=job['boot_id'])
    require(job['deadlines'] == dict(latch_s=3240, stop_intent_s=3310, owner_ceiling_s=3600), 'Fixed deadlines differ')
    publish(root / 'deadline-armed.json', dict(schema='robotron-ce-batch2048-deadline-armed-v1',
        job=jp, source=self_pin, pid=os.getpid(), starttime_ticks=process_start(os.getpid()),
        clock=now, lock_path=str(lock_path), lock_identity=lock_identity, planned=planned))
    lock = ActionLock(lock_path, lock_identity)
    result = supervise(adoption=lambda: read_adoption(activation, planned),
        requested=lambda: read_requested(activation, planned), get_clock=clock,
        probe=classify, stop=lambda owner: request_stop(owner, lock), sleep=time.sleep,
        emit=lambda value: publish(root / 'deadline-result.json', value))
    return 0 if result['status'] == 'RETIRED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
