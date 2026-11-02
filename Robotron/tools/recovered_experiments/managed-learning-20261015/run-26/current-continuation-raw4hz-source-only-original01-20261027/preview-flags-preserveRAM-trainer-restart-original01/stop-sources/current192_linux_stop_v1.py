"""Linux primitives/backend for one explicitly selected score-carry handoff.

The original prepared owner, current source pins, live rescue and a complete
post-stop adapter are prerequisites to the first network/control mutation.
No backend is prepared or run by importing this file.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import threading
import time


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
MODEL = GAME/'models_dqn'
CONTROL = MODEL/'learning_control.json'
ROOT_CGROUP = Path('/sys/fs/cgroup')
MAIN_UNIT = 'robotron-managed-run-26-continuation-raw4hz-original01-20261027-trainer.service'
OLD_SOCKET_SHA = '97d9a158e32f89d2b1bccb8bee309682cdf7acdfcc33dcb255752466b91d8fa3'
NEW_SOCKET_SHA = '97d9a158e32f89d2b1bccb8bee309682cdf7acdfcc33dcb255752466b91d8fa3'
WIRE_COUNT = 1890
WIRE_HEADER = '>HddBIBBBIBBB'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def starttime(path):
    raw = Path(path).read_text()
    return int(raw[raw.rfind(')')+2:].split()[19])


def process_start(pid):
    try:
        return starttime(Path('/proc', str(pid), 'stat'))
    except FileNotFoundError:
        return None


def full_pin(path):
    path = Path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and not path.is_symlink()
            and before.st_uid == os.getuid() and before.st_nlink == 1, 'Owned single regular file required')
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.lstat()
    def identity(v):
        return (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns, v.st_mode, v.st_uid, v.st_nlink)
    require(identity(before) == identity(after), 'Pinned file changed during read')
    return dict(path=str(path), sha256=sha, bytes=after.st_size,
        identity=dict(device=after.st_dev, inode=after.st_ino, bytes=after.st_size,
            mtime_ns=after.st_mtime_ns, ctime_ns=after.st_ctime_ns,
            mode=oct(after.st_mode & 0o777), uid=after.st_uid, nlink=after.st_nlink))


def checked(entry):
    # Existing original CPU controllers publish their documented five-field
    # identity ABI. Accept exactly that immutable ABI or the full snapshot ABI;
    # never synthesize missing historical timestamps or ignore supplied fields.
    full = {'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}
    controller = {'device','inode','mode','uid','nlink'}
    require(set(entry) == {'path','sha256','bytes','identity'}
            and set(entry['identity']) in (full,controller), 'Unknown pin identity ABI')
    observed = full_pin(entry['path'])
    require(all(observed[k] == entry[k] for k in ('path','sha256','bytes'))
            and all(observed['identity'][k] == v for k,v in entry['identity'].items())
            and (set(entry['identity']) == full or entry['identity']['mode'] == '0o444'),
            'Immutable/source input changed: '+entry['path'])
    raw = Path(entry['path']).read_bytes()
    require(len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'],
            'Pinned bytes changed during read')
    return raw


def publish(path, value):
    path = Path(path)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    return full_pin(path)


def atomic_owned_replace(path, expected, raw, *, suffix):
    """Optimistic owned-input check plus atomic replacement, never blind restore."""
    path = Path(path)
    require(expected['path'] == str(path) and full_pin(path) == expected, 'Owned mutable input changed')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', suffix), 'Unsafe transaction suffix')
    temporary = path.with_name(path.name+'.'+suffix+'.tmp')
    require(not temporary.exists(), 'Owned staging path already exists')
    temporary_identity = None
    try:
        with temporary.open('xb') as stream:
            created = os.fstat(stream.fileno())
            temporary_identity = (created.st_dev, created.st_ino)
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), int(expected['identity']['mode'], 8))
            os.fsync(stream.fileno())
        require(full_pin(path) == expected, 'Owned input changed before publication')
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary_identity is not None:
            try:
                current = temporary.lstat()
            except FileNotFoundError:
                current = None
            if current is not None and (current.st_dev,current.st_ino) == temporary_identity:
                temporary.unlink()
    return full_pin(path)


def module(entry, name):
    checked(entry)
    spec = importlib.util.spec_from_file_location(name, entry['path'])
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    checked(entry)
    return value


def show(unit):
    result = subprocess.run(['systemctl','--user','show',unit], capture_output=True, text=True, timeout=15)
    require(result.returncode == 0, 'Original unit query failed')
    return dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)


def live_owner(owner):
    value = show(owner['unit'])
    require(value.get('MainPID') == str(owner['pid'])
            and value.get('InvocationID') == owner['invocation_id']
            and value.get('ControlGroup') == owner['cgroup']
            and value.get('NRestarts') == '0' and value.get('SubState') == 'running'
            and process_start(owner['pid']) == owner['starttime_ticks'], 'Exact live owner changed')
    return value


def frame_map(api, expected_slots):
    rows = api['client_rows']
    require(type(rows) is list and len(rows) == len(expected_slots), 'Client row count differs')
    result = {}
    for row in rows:
        slot, cid = row['client_slot'], row['client_id']
        require(type(slot) is int and slot in expected_slots and slot not in result
                and type(cid) is int and cid >= 0, 'Unknown/duplicate client identity')
        seconds = row['session_seconds']
        require(type(seconds) in (int,float) and math.isfinite(seconds) and seconds >= 0,
                'Invalid accepted-frame counter')
        frames = seconds*60
        require(abs(frames-round(frames)) <= 1e-5, 'Session seconds do not represent an exact frame count')
        result[slot] = dict(cid=cid, frames=round(frames), evaluation=row['eval'])
    require(len({v['cid'] for v in result.values()}) == len(result), 'Duplicate client ID')
    return result


def validate_base_control(binding, raw, *, closed_base_measurement=None):
    """Allow only the recorded already-closed old final label as a base."""
    base = json.loads(raw)
    require(base['lr_scale'] == .125, 'Current recipe scale changed')
    measurement = base.get('measurement')
    if measurement is None:
        return None
    transition = binding.get('owned_final_control_transition')
    require(type(transition) is dict, 'A nonempty base measurement needs its exact closed authority')
    original = json.loads(checked(transition['base_control_archive']))
    event = json.loads(checked(transition['actual_final_pause_event']))
    label = 'scorecarry-current227-preserve-original01-20261027-final'
    expected = dict(label=label, checkpoint=None, cohort_s=3600, timeout_s=7200)
    require(original.get('measurement') is None and event['purpose'] == 'final'
            and event['label'] == label and event['control'] == transition['current_control']
            and transition['current_control']['path'] == str(CONTROL)
            and transition['current_control']['sha256'] == hashlib.sha256(raw).hexdigest()
            and base == dict(original, measurement=expected)
            and binding['baseline_API']['measurement_active'] is False
            and binding['baseline_API']['training_enabled'] is True,
            'Only the exact previous owned, already-closed final control may be the current base')
    require(type(closed_base_measurement) is dict
            and closed_base_measurement['sha256'] ==
                '489e47f8b0c9ce52a685d0281278e64400334678e161db5fd3acb729571a80cb'
            and closed_base_measurement['identity']['mode'] == '0o444',
            'Exact ROOT handled-before-current-boot qualification is required')
    qualification = json.loads(checked(closed_base_measurement))
    terminal_pin = qualification['actual_terminal_file']
    terminal = json.loads(checked(terminal_pin))  # Normal producer mode0664 is preserved.
    require(qualification['schema'] == 'robotron-root-readonly-closed-original-final-measurement-record-v1'
            and terminal_pin['path'] == str(MODEL/'managed-measurements'/(label+'.json'))
            and terminal_pin['sha256'] == 'ef998bcd59b58335179a0edb3b2e0d47a9c3654a84f867e88c2ff4bcdc1b5f9a'
            and terminal == qualification['actual_terminal_value']
            and terminal['active'] is False and terminal['phase'] == 'finished'
            and terminal['complete'] is True and terminal['valid'] is False
            and terminal['reason'] == 'trainer_shutdown' and terminal['label'] == label
            and terminal['request'] == expected
            and qualification['actual_current_api']['measurement_active'] is False
            and qualification['actual_current_api']['training_enabled'] is True
            and qualification['actual_current_api']['managed_measurement'] == {}
            and terminal['ended_unix_s'] < qualification['actual_current_api']['ts'],
            'The old base label must be a real terminal handled record, never a quality PASS')
    return measurement


def summarize_restart_censored_live_games(api, original_rows, raw_API_pin, main):
    """One saved API cutoff; not a completed-game or fixed-policy quality mean."""
    rows = [dict(row) for row in api['client_rows']
            if type(row.get('client_slot')) is int and 0 <= row['client_slot'] < 192]
    require(len(rows) == 192 and {row['client_slot'] for row in rows} == set(range(192))
            and len({row['client_id'] for row in rows}) == 192,
            'Cutoff requires every original live192 slot/CID exactly once')
    for row in rows:
        previous = original_rows[row['client_slot']]
        require(row['client_id'] == previous['cid'] and row['eval'] is previous['evaluation']
                and type(row['score']) is int and row['score'] >= 0,
                'Cutoff identity/role/full-score differs')
        row.update(score_at_snapshot=row['score'], status='restart_censored_snapshot',
                   natural_completion_confirmed_by_this_capture=False)
    scores = sorted(row['score'] for row in rows)
    score_sum = sum(scores)
    return dict(schema='robotron-main192-prestop-restart-censored-score-cutoff-v1',
        raw_API=raw_API_pin, producer_unix_s=api['ts'], original_owner=main['owner'],
        actual_recipe=main['experiment'], n_scored=192, n_restart_censored=192,
        n_natural_completed_counted=0, score_sum=score_sum, mean_score=score_sum/192,
        median_twice=scores[95]+scores[96], median_score=(scores[95]+scores[96])/2,
        over100M_slots=[row['client_slot'] for row in rows if row['score'] > 100_000_000],
        rows=sorted(rows, key=lambda row: row['client_slot']),
        original_actor_identity_registry=main['actors'],
        scope='Accepted unwrapped cs.game_score snapshot of current long-running training games; all pending rows conservatively restart-censored, not natural completions.',
        API_does_not_export_game_UID_or_last_score_accept_time=True,
        new_postrestart_live_average_has_fresh_game_cohort=True,
        four_fixed32_closed_quality_leg_results_unchanged=True)


CURRENT_NONINPUT_NATIVE = {
    1062559: (117472924, 'Thread-1 (serve'),  # Dashboard serve_forever.
    1062560: (117472924, 'Thread-2 (_samp'),  # Dashboard _sampling_loop.
    1062561: (117472925, 'Thread-3 (_cons'),  # AsyncReplayBuffer._consume; FIFO-tail gated.
    1062563: (117472929, 'Thread-4 (start'), # SocketServer.start; separately held listener.
    1062564: (117472929, 'Thread-5 (stats'), # main.stats_reporter.
}


def possible_input_or_cleanup(tid, born, name):
    known = CURRENT_NONINPUT_NATIVE.get(tid)
    if known is not None:
        require((born, name) == known, 'A source-bound persistent native task changed')
        return False
    # Timer's default name need not contain '(' and high sequence numbers
    # lose all function-name bytes. Unknown auto-threads are never exempted.
    return bool(re.match(r'^(?:Thread-[0-9]+(?:[ ()].*)?|Timer.*)$', name))


def potential_handlers(pid):
    require(pid == 1062324 and process_start(pid) == 117468652,
            'Only the exact current1062324 trainer native tasks may be inspected')
    result = {}
    for task in Path('/proc', str(pid), 'task').iterdir():
        try:
            born = starttime(task/'stat'); name = (task/'comm').read_text().strip()
            if possible_input_or_cleanup(int(task.name), born, name) and starttime(task/'stat') == born:
                result[int(task.name)] = dict(tid=int(task.name), starttime_ticks=born,
                    comm=name, wchan=(task/'wchan').read_text().strip())
        except FileNotFoundError:
            continue
    for tid, expected in CURRENT_NONINPUT_NATIVE.items():
        task = Path('/proc', str(pid), 'task', str(tid))
        require(task.exists() and (starttime(task/'stat'), (task/'comm').read_text().strip()) == expected,
                'A required current native task is absent or replaced')
    return result


class LinuxBackend:
    def __init__(self, job, *, context_only=False):
        require(job['schema'] == 'robotron-current-fresh192-preserveRAM-stop-job-v1'
                and job['authorized'] is True, 'Explicit selected handoff required')
        require(re.fullmatch(r'scorecarry-[A-Za-z0-9_-]{1,60}', job['case']), 'Unique bounded case label required')
        require(job.get('poststop_adapter') is not None, 'Complete verified post-stop adapter is required before actions')
        self.job = job
        self.out = Path(job['output'])
        require(self.out == Path(__file__).resolve().parent.parent/'stop-original01'
                and re.fullmatch(r'stop-preparation-original[0-9]{2}', Path(job['prepared']['path']).parent.name)
                and Path(job['prepared']['path']).parent.parent == self.out.parent
                and not self.out.exists(), 'One new execution under the prepared case required')
        self.reader = module(job['dependencies']['reader'], '_handoff_reader')
        self.raw = module(job['dependencies']['raw_API'], '_handoff_raw_API')
        self.guard = module(job['dependencies']['main_guard'], '_handoff_main_guard')
        self.bank_reader = module(job['dependencies']['bank_witness'], '_handoff_bank_witness')
        self.bank_intent = module(job['dependencies']['bank_shutdown_intent'], '_handoff_bank_shutdown_intent')
        self.socket_seal = module(job['dependencies']['socket_seal'], '_handoff_socket_seal')
        self.prepared = json.loads(checked(job['prepared']))
        require(self.prepared['schema'] == 'robotron-current-fresh192-preserveRAM-stop-prepared-v1'
                and self.prepared['status'] == 'PREPARED_CURRENT192_PRESERVERAM_STOP_ONLY_NOT_LAUNCHED'
                and self.prepared['original_main'] == self.prepared['current_binding'],
                'Exact current227 stop-only context required')
        selection = json.loads(checked(job['root_selection']))
        require(job['root_selection']['identity']['mode'] == '0o444'
                and selection['schema'] == 'robotron-root-fresh192-preserveRAM-stop-selection-v1'
                and selection['prepared_inputs'] == job['prepared']
                and selection['one_original_stop_only'] is True
                and selection['source_or_replacement_start_not_authorized'] is True
                and selection['source_and_guard_qualification_complete'] is True,
                'Exact ROOT stop-only source/guard selection is required')
        require(selection['backend_source'] == job['backend_source'] == full_pin(Path(__file__).resolve())
                and selection['poststop_adapter'] == job['poststop_adapter']
                and selection['recovery_source'] == job['recovery_source'], 'Selected stop source family differs')
        require(selection['current_binding'] == self.prepared['current_binding'],
                'ROOT must bind the actual new current192 registry, never a guessed future hash')
        require(selection['closed_base_measurement'] == job['closed_base_measurement'],
                'ROOT must bind the same actual handled-label qualification')
        self.main = json.loads(checked(self.prepared['original_main']))
        require(self.main['schema'] == 'robotron-current-fresh192-continuation-registry-v1'
                and type(selection['expected_source_count']) is int
                and len(self.main['held_hashes']) == selection['expected_source_count']
                and self.main['eval_count'] == 37 and self.main['training_count'] == 155,
                'Explicit actual current192 source/role registry required')
        self.owner = self.main['owner']
        require(self.owner['pid'] == 1062324 and self.owner['starttime_ticks'] == 117468652
                and self.owner['unit'] == MAIN_UNIT
                and self.owner['invocation_id'] == '429ceaf754ca49b495056180a0350411',
                'Only the explicitly prepared original trainer is allowed')
        self.listener = json.loads(checked(self.prepared['original_listener']))
        self.dashboard_accept = json.loads(checked(self.prepared['original_dashboard_accept']))
        require(self.dashboard_accept['owner'] == self.owner
                and (self.dashboard_accept['tid'], self.dashboard_accept['starttime_ticks'],
                     self.dashboard_accept['comm']) == (1062559, 117472924, 'Thread-1 (serve'),
                'Exact current dashboard accept task required')
        self.fleet = json.loads(checked(self.prepared['original_fleet']))
        self.supplemental0 = json.loads(checked(self.prepared['original_supplemental0']))
        self.original_actors = self.main['actors']
        self.actor_owner_keys = self.main['actor_ownership']
        self.producer_owners = dict(fleet=self.fleet, supplemental0=self.supplemental0)
        require(len(self.original_actors) == 192
                and {a['slot'] for a in self.original_actors} == set(range(192))
                and set(self.actor_owner_keys) == {str(s) for s in range(192)}
                and all(self.actor_owner_keys[str(s)] == ('supplemental0' if s == 0 else 'fleet')
                        for s in range(192)), 'Exact split-owner original192 registry required')
        for key, producer in self.producer_owners.items():
            identity = self.main['actual_owners'][key]
            require(all(producer[k] == identity[k] for k in
                        ('pid','starttime_ticks','unit','invocation_id','cgroup'))
                    and producer['original_actors'] == [a for a in self.original_actors
                        if self.actor_owner_keys[str(a['slot'])] == key],
                    'An input owner/actor subset is not the real captured original')
        require((self.fleet['pid'], self.fleet['starttime_ticks'], self.fleet['invocation_id']) ==
                    (1073404, 117607824, 'f791a854723b4f90ab5fa8a637a13868')
                and (self.supplemental0['pid'], self.supplemental0['starttime_ticks'],
                     self.supplemental0['invocation_id']) ==
                    (1122536, 117687032, 'ccdd44624bd142db8effc98139940e7d'),
                'Only the current original191 fleet and separate original slot0 may be held')
        self.anchor = json.loads(checked(self.prepared['component_proofs']['original_boot_anchor']))
        require(self.anchor['owner'] == self.owner and self.anchor['inferred_replay_pressure_anchor'] is None,
                'Original boot-anchor provenance differs')
        self.control_pin = full_pin(CONTROL)
        self.control_bytes = checked(job['base_control_archive'])
        require(CONTROL.read_bytes() == self.control_bytes
                and hashlib.sha256(self.control_bytes).hexdigest() == job['base_control_sha256'],
                'Current original control differs')
        self.base_control = json.loads(self.control_bytes)
        self.base_measurement = validate_base_control(self.main, self.control_bytes,
            closed_base_measurement=job['closed_base_measurement'])
        if self.base_measurement is not None:
            require(self.control_pin == self.main['owned_final_control_transition']['current_control'],
                    'Actual closed-base control identity changed before preparation')
        self.probe = None
        self.probe_id = None
        self.probe_tid = None
        self.actor_handlers = {}
        self.listener_child = ROOT_CGROUP.joinpath(self.owner['cgroup'].lstrip('/'))/('listener-'+job['case'])
        self.fleet_root = ROOT_CGROUP.joinpath(self.fleet['cgroup'].lstrip('/'))
        self.producer_roots = {key:ROOT_CGROUP.joinpath(owner['cgroup'].lstrip('/'))
                               for key,owner in self.producer_owners.items()}
        require(len(set(self.producer_roots.values())) == 2, 'Two distinct real producer cgroups required')
        self.producer_holds = dict(fleet=False, supplemental0=False)
        self.accept_held = self.fleet_frozen = self.original_stop_sent = False
        self.dashboard_child = self.listener_child.parent/('dashboard-'+job['case'])
        self.dashboard_accept_held = False
        self.dashboard_release_after_save_return = None
        self.stop_requested_unix_s = None
        self.stop_stdout_binding = None
        self.replacement = None
        self.counter = 0
        self.current_pause = None
        self.stage = 'created'
        self.stage_started = time.monotonic()
        self.stage_deadline = self.stage_started+30
        self.created = self.stage_started
        self._state_lock = threading.Lock()
        adapter = module(job['poststop_adapter'], '_handoff_poststop_adapter')
        require(callable(getattr(adapter, 'recover_committed', None)),
                'Committed recovery must exist before any runtime action')
        self.poststop = adapter.prepare(self)
        required = ('verify_stopped','install','start_once',
                    'verify_startup','verify_progress','recovery_state','sealed_bank_semantics')
        require(all(callable(getattr(self.poststop, name, None)) for name in required),
                'Post-stop adapter does not implement the full contract')
        recovery = module(job['recovery_source'], '_prepared_handoff_recovery')
        require(callable(getattr(recovery,'recover',None)), 'Complete recovery implementation is required')
        if context_only:
            return  # Read-only exact completed context, before execution outputs/controls.
        self.out.mkdir(mode=0o700)
        (self.out/'API-wires').mkdir()
        self.state()

    def bind_observation_pending(self, exception):
        self.ObservationPending = exception

    def event(self, name, value):
        return publish(self.out/name, value)

    def state(self):
        value = dict(schema='robotron-owned-handoff-recovery-state-v1', case=self.job['case'],
            controller_pid=os.getpid(), controller_starttime_ticks=process_start(os.getpid()),
            stage=self.stage, stage_started_monotonic_s=self.stage_started,
            stage_deadline_monotonic_s=self.stage_deadline, original_owner=self.owner,
            original_fleet=self.prepared['original_fleet'],
            original_supplemental0=self.prepared['original_supplemental0'],
            producer_holds=dict(self.producer_holds),
            producer_roots={k:str(v) for k,v in self.producer_roots.items()},
            original_listener=self.prepared['original_listener'],
            control_path=str(CONTROL), expected_owned_control=self.control_pin,
            base_control_archive=self.job['base_control_archive'], listener_child=str(self.listener_child),
            accept_held=self.accept_held, fleet_frozen=self.fleet_frozen,
            original_dashboard_accept=self.prepared['original_dashboard_accept'],
            dashboard_child=str(self.dashboard_child), dashboard_accept_held=self.dashboard_accept_held,
            original_stop_sent=self.original_stop_sent, original_stop_requested_unix_s=self.stop_requested_unix_s,
            original_stop_stdout_binding=self.stop_stdout_binding,
            replacement=self.replacement,
            poststop=self.poststop.recovery_state())
        with self._state_lock:
            target = self.out/'recovery-state.json'
            temporary = self.out/'recovery-state.tmp'
            with temporary.open('w') as stream:
                json.dump(value, stream, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)

    def rescue_live(self):
        rescue = json.loads(checked(self.job['rescue_owner']))
        live_owner(rescue)
        require(rescue['pid'] != os.getpid() and rescue['unit'] != self.owner['unit'],
                'Independent original rescue must be outside the trainer/controller')
        actual = [v.decode() for v in Path('/proc',str(rescue['pid']),'cmdline').read_bytes().split(b'\0') if v]
        require(actual == self.job['rescue_command'], 'Original rescue command differs')
        require(actual[:4] == ['/usr/bin/python3.12','-I','-B',self.job['recovery_source']['path']]
                and actual[4:] == ['--watch','--job',self.job['rescue_job']['path'],
                                  '--expected-job-sha256',self.job['rescue_job']['sha256']],
                'Exact pinned independent rescue program/job required')
        checked(self.job['recovery_source'])
        checked(self.job['rescue_job'])
        ready = json.loads(checked(self.job['rescue_ready']))
        require(ready['owner'] == rescue and ready['case'] == self.job['case']
                and ready['prepared_inputs_sha256'] == self.job['prepared']['sha256']
                and ready['recovery_source_sha256'] == self.job['recovery_source']['sha256'],
                'Independent rescue readiness is not bound to this handoff')
        return rescue

    def before_stage(self, stage):
        self.rescue_live()
        require(time.monotonic()-self.created <= 1800, 'Whole original handoff deadline exceeded')
        self.stage = stage
        self.stage_started = time.monotonic()
        limits = dict(dashboard_accept_held_and_cleanup_finished=25,
            original192_handlers_finished=50, real_bank_shutdown_intent_sealed=180,
            original_main_graceful_stop=240, newest_stopped_checkpoint_CPU_verified=300,
            same_replacement_startup_verified=900, original192_reconnected_and_learning=180)
        self.stage_deadline = self.stage_started+limits.get(stage, 30)
        self.state()

    def after_stage(self, stage, value):
        self.state()
        if isinstance(value, dict):
            self.event(stage+'.json', value)

    def wait(self, predicate, seconds, message):
        deadline = min(time.monotonic()+seconds, self.stage_deadline)
        while time.monotonic() < deadline:
            self.rescue_live()
            value = predicate()
            if value:
                return value
            time.sleep(.2)
        live = self.replacement or self.owner
        if self.original_stop_sent and process_start(live['pid']) == live['starttime_ticks']:
            raise self.ObservationPending(message+'; the same original handle is still live')
        raise RuntimeError(message)

    def api(self, *, observe_startup=False):
        import urllib.request
        self.counter += 1
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=3) as response:
            wire = response.read(self.raw.MAX_WIRE_BYTES+1)
        pin = self.event('API-wires/'+f'{self.counter:04}.raw', wire)
        value = self.raw.parse_wire(wire)
        fields = self.raw.witness_fields(value, pin)
        self.event('API-wires/'+f'{self.counter:04}.json', fields)
        owner = self.replacement or self.owner
        replay_pid = value['host_pipeline']['learning_exposure']['replay']['process_id']
        optimizer_pid = value['host_pipeline']['learning_exposure']['optimizer']['process_id']
        if (observe_startup and self.replacement is not None
                and replay_pid == optimizer_pid == self.owner['pid']):
            return None  # Archived previous-owner data is never startup proof.
        require(replay_pid == optimizer_pid == owner['pid'],
                'Original API owner changed')
        require(0 <= time.time()-value['ts'] <= 5 and 0 <= value['pipeline_snapshot_age_s'] <= 5,
                'Stale original API/pipeline')
        require(value['pipeline_read_error'] == value['bank_persistence_read_error'] == ''
                and value['bank_persistence']['write_failures'] == 0,
                'Original pipeline/bank health changed')
        require(all(value['host_pipeline'][name]['errors'] == 0 for name in self.raw.ERROR_KINDS),
                'Original pipeline recorded an error')
        recipe_ready = value['managed_experiment'] == self.main['experiment'] and value['lr'] == 6.25e-6
        if observe_startup and self.replacement is not None and not recipe_ready:
            return None
        require(recipe_ready,'Original recipe changed')
        return value

    def preflight(self):
        self.guard.owner_and_files(self.main)
        self.check_producer_owners_and_actors()
        api = self.api()
        self.guard.healthy(api, self.main['baseline_API'], self.main['experiment'], time.time())
        require(api['memory_buffer_size'] == 6000000 and not (MODEL/'managed_save.request.json').exists(),
                'Original replay/save slot changed')
        require(self.anchor['original_boot_checkpoint'] == self.poststop.config['boot_checkpoint']
                and api['host_pipeline']['inference_graphs']['postload_validations'] == 1
                and api['host_pipeline']['learning_exposure']['optimizer']['epoch'] == 1,
                'Original replay-budget provenance no longer applies')
        self.original_rows = frame_map(api, set(range(192)))
        # At six-digit Python thread sequence numbers, Timer/HTTP names are
        # truncated to the same prefix as handle_client. Preserve a superset;
        # requiring exactly192 here would reject the real healthy process.
        native = potential_handlers(self.owner['pid'])
        require(len(native) >= 192, 'Native census cannot cover all original clients')
        self.original_native = native
        require(not self.listener_child.exists() and all((root/'cgroup.freeze').read_text().strip() == '0'
                    for root in self.producer_roots.values()),
                'A listener/fleet hold already exists')
        self.rescue_live()
        return dict(owner=self.owner, original192_rows=self.original_rows,
                    original_native_candidates=native, prepared=self.job['prepared'])

    def native_count(self, count):
        value = potential_handlers(self.owner['pid'])
        return value if len(value) == count else None

    def native_candidates(self):
        return potential_handlers(self.owner['pid'])

    def open_probe(self, context):
        host, port = self.job['probe_endpoint']
        require(host in ('127.0.0.1','192.168.1.131') and port == 9998, 'Only the original local trainer endpoint')
        self.probe = socket.create_connection((host, port), timeout=3)
        self.probe.settimeout(3)
        self.probe.sendall(struct.pack('>H', (1 << 14) | (8191 << 1)))
        result = None
        def registered():
            nonlocal result
            api = self.api()
            if api['client_count'] != 193:
                return False
            rows = frame_map(api, set(range(192)) | {8191})
            require(all(rows[s]['cid'] == self.original_rows[s]['cid'] for s in range(192)),
                    'Original client identity changed while adding the probe')
            require(rows[8191]['evaluation'] is True and rows[8191]['frames'] == 0,
                    'Owned probe must be explicitly EVAL without frames')
            native = potential_handlers(self.owner['pid'])
            additional = [tid for tid, value in native.items()
                          if tid not in self.original_native
                          and value['wchan'].startswith('poll_schedule_timeout')]
            if len(additional) != 1:
                return False
            self.probe_id = rows[8191]['cid']
            self.probe_tid = native[additional[0]]
            self.actor_handlers = dict(self.original_native)
            result = dict(cid=self.probe_id, slot=8191, native=self.probe_tid,
                          local_endpoint=self.probe.getsockname(), peer_endpoint=self.probe.getpeername())
            return True
        self.wait(registered, 15, 'Owned probe did not register')
        return result

    def pause(self, purpose, probe):
        label = self.job['case']+'-'+purpose
        require(not (MODEL/'managed-measurements'/(label+'.json')).exists(), 'Measurement label already handled')
        data = dict(self.base_control, measurement=dict(label=label, checkpoint=None, cohort_s=3600, timeout_s=7200))
        raw = (json.dumps(data, indent=2)+'\n').encode()
        self.control_pin = atomic_owned_replace(CONTROL, self.control_pin, raw, suffix=self.job['case'])
        self.state()
        result = None
        def paused():
            nonlocal result
            api = self.api()
            managed = api['managed_measurement']
            if not (api['measurement_active'] is True and api['training_enabled'] is False
                    and managed.get('active') is True and managed.get('label') == label
                    and managed.get('phase') == 'warming'):
                return False
            result = dict(label=label, generation=managed['generation'], purpose=purpose,
                          control=self.control_pin, clocks={k:api[k] for k in
                          ('frame_count','learner_frame_count','training_steps','optimized_samples')})
            self.current_pause = result
            return True
        self.wait(paused, 20, 'Supported measurement did not pause')
        return result

    def check_pause(self, api, pause):
        managed = api['managed_measurement']
        require(api['measurement_active'] is True and api['training_enabled'] is False
                and managed['active'] is True and managed['label'] == pause['label']
                and managed['generation'] == pause['generation']
                and managed['phase'] in ('warming','collecting','draining'), 'Owned supported pause changed')
        return managed

    def measured_progress(self, pause):
        baseline = frame_map(self.api(), set(range(192)) | {8191})
        result = None
        def advanced():
            nonlocal result
            api = self.api()
            managed = self.check_pause(api, pause)
            rows = frame_map(api, set(range(192)) | {8191})
            require(all(rows[s]['cid'] == baseline[s]['cid'] for s in rows), 'Client changed during pause entry')
            boundary = managed.get('boundary',{})
            ready = (all(rows[s]['frames']-baseline[s]['frames'] >= 8 for s in range(192))
                and boundary.get('acknowledged') == 192
                and boundary.get('pending_client_ids') == [self.probe_id]
                and boundary.get('replay_pending_client_ids') == [])
            if ready:
                result = dict(generation=pause['generation'], measured_frame_deltas=
                              {str(s):rows[s]['frames']-baseline[s]['frames'] for s in range(192)})
            return ready
        self.wait(advanced, 15, 'Not every original actor advanced8 measured frames and acknowledged')
        return result

    def hold_listener(self, context):
        owner = self.owner
        live_owner(owner)
        info = self.listener
        task = Path('/proc',str(owner['pid']),'task',str(info['tid']))
        require(starttime(task/'stat') == info['starttime_ticks']
                and (task/'comm').read_text().strip() == info['comm']
                and (task/'cgroup').read_text().strip() == '0::'+owner['cgroup'], 'Original accept thread changed')
        parent = self.listener_child.parent
        require(parent.stat().st_uid == os.getuid() and (parent/'cgroup.type').read_text().strip() == 'domain'
                and not (parent/'cgroup.subtree_control').read_text().strip()
                and not any(p.is_dir() for p in parent.iterdir()), 'Unexpected original cgroup topology')
        self.listener_child.mkdir()
        self.accept_held = True
        self.state()  # Rescue knows the exact child before the first freeze.
        (self.listener_child/'cgroup.type').write_text('threaded\n')
        (self.listener_child/'cgroup.freeze').write_text('1\n')
        (self.listener_child/'cgroup.threads').write_text(str(info['tid'])+'\n')
        def frozen():
            fields = dict(line.split() for line in (self.listener_child/'cgroup.events').read_text().splitlines())
            return fields.get('frozen') == '1'
        self.wait(frozen, 3, 'Original accept thread did not freeze')
        require(set(map(int,(self.listener_child/'cgroup.threads').read_text().split())) == {info['tid']},
                'Unexpected thread inherited the temporary listener cgroup')
        self.api()  # A held application/API lock must fail before fleet freeze.
        return dict(original_listener=self.prepared['original_listener'], child=str(self.listener_child), frozen=True)

    def freeze_fleet(self, context):
        self.check_producer_owners_and_actors()
        self.guard.owner_and_files({**self.main, 'held_hashes':{p:h for p,h in self.main['held_hashes'].items() if p != str(CONTROL)}})
        cutoff_api = self.api()
        cutoff_raw = full_pin(self.out/'API-wires'/f'{self.counter:04}.raw')
        self.live_game_cutoff = self.event('pre-freeze-live192-restart-censored-score-cutoff.json',
            summarize_restart_censored_live_games(cutoff_api, self.original_rows, cutoff_raw, self.main))
        for key in ('fleet', 'supplemental0'):
            self.check_producer_owners_and_actors()
            root = self.producer_roots[key]
            require(root.resolve(strict=True) == root and root.stat().st_uid == os.getuid(),
                    'Exact owned producer cgroup required')
            self.producer_holds[key] = True
            self.state()  # Independent rescue records each intent BEFORE its kernel write.
            (root/'cgroup.freeze').write_text('1\n')
            self.wait(lambda: dict(line.split() for line in
                (root/'cgroup.events').read_text().splitlines()).get('frozen') == '1',
                5, 'Original producer cgroup did not freeze: '+key)
        self.fleet_frozen = True
        self.state()
        self.assert_producers_held()
        return dict(original_fleet=self.prepared['original_fleet'],
            original_supplemental0=self.prepared['original_supplemental0'],
            both_original_producer_cgroups_frozen=True, emulator_processes_terminated=False)

    def check_producer_owners_and_actors(self):
        for key, producer in self.producer_owners.items():
            live_owner(producer)
            root = self.producer_roots[key]
            for actor in producer['original_actors']:
                require(process_start(actor['pid']) == actor['starttime_ticks']
                        and sorted(os.sched_getaffinity(actor['pid'])) == actor['mask']
                        and Path('/proc',str(actor['pid']),'cgroup').read_text().strip() ==
                            '0::'+producer['cgroup'], 'Original producer actor identity/affinity/cgroup changed')
            expected = {a['pid'] for a in producer['original_actors']}
            actual = set()
            for raw_pid in (root/'cgroup.procs').read_text().split():
                try: command = Path('/proc',raw_pid,'cmdline').read_bytes().split(b'\0')
                except FileNotFoundError: continue
                if command[:1] == [b'/usr/games/mame']: actual.add(int(raw_pid))
            require(actual == expected, 'Unexpected/missing original MAME member in '+key)
        return True

    def assert_producers_held(self):
        self.check_producer_owners_and_actors()
        require(self.fleet_frozen and all(self.producer_holds.values()), 'Both original producer holds required')
        for root in self.producer_roots.values():
            require((root/'cgroup.freeze').read_text().strip() == '1'
                    and dict(line.split() for line in (root/'cgroup.events').read_text().splitlines()).get('frozen') == '1',
                    'An original producer escaped its positive kernel freeze')
        return True


    def seal_inputs(self, context, probe, listener, fleet, pause):
        seal = self.socket_seal.seal(self, context, probe, pause)
        require(seal.get('all193_socket_owners_verified') is True
                and seal.get('all193_receive_queues_empty') is True
                and seal.get('all193_handlers_waiting_for_input') is True,
                'Actual frozen-input ownership seal is incomplete')
        return seal

    def probe_frames(self, pause):
        api = self.api()
        self.check_pause(api, pause)
        require(self.probe is not None and self.accept_held and self.fleet_frozen, 'Probe input lacks exclusive maintenance')
        payload = struct.pack(WIRE_HEADER, WIRE_COUNT, 0., 0., 0, 0, 1, 0, 0, 20000, 2, 1, 3)+b'\0'*(WIRE_COUNT*4)
        packet = struct.pack('>I',len(payload))+payload
        for _ in range(8):
            self.probe.sendall(packet)
            result = bytearray()
            while len(result) < 6:
                chunk = self.probe.recv(6-len(result))
                require(chunk, 'Owned probe closed before its action')
                result.extend(chunk)
        return True

    def marker(self, probe, pause, seal):
        self.probe_frames(pause)
        result = None
        def acknowledged():
            nonlocal result
            api = self.api()
            managed = self.check_pause(api,pause)
            boundary = managed['boundary']
            if boundary.get('ready') and self.probe_id in boundary['acknowledged_client_ids']:
                require(boundary['generation'] == pause['generation'], 'FIFO marker generation changed')
                result = dict(generation=pause['generation'], probe_id=self.probe_id,
                    actual_reset_marker_acknowledged=True, boundary=boundary)
                return True
            return False
        self.wait(acknowledged, 10, 'Actual measurement FIFO reset did not acknowledge')
        return result

    def finish_original_handlers(self, context, probe, pause, seal):
        last_ping = time.monotonic()
        def finished():
            nonlocal last_ping
            if time.monotonic()-last_ping >= 5:
                self.probe_frames(pause)
                last_ping = time.monotonic()
            api = self.api()
            self.check_pause(api,pause)
            require(set(row['client_id'] for row in api['client_rows']).issubset(
                {v['cid'] for v in self.original_rows.values()} | {self.probe_id}), 'An unowned client entered the held listener')
            gone = not any(Path('/proc',str(self.owner['pid']),'task',str(tid)).exists() for tid in self.actor_handlers)
            if not gone or api['client_count'] != 1:
                return False
            require(frame_map(api,{8191})[8191]['cid'] == self.probe_id, 'Remaining client is not the owned probe')
            return True
        self.wait(finished, 45, 'Original192 handlers have not finished; do not save yet')
        return dict(original192_handler_threads_absent=True, original192_emulators_still_frozen=True)

    def cancel_pause(self, pause):
        self.control_pin = atomic_owned_replace(CONTROL,self.control_pin,self.control_bytes,suffix=self.job['case'])
        self.state()
        def restored():
            api = self.api()
            managed = api['managed_measurement']
            require(managed.get('phase') != 'restore_failed','Owned pause restoration failed')
            return (api['measurement_active'] is False and api['training_enabled'] is True
                    and managed.get('active') is False and managed.get('label') == pause['label']
                    and managed.get('phase') == 'finished')
        self.wait(restored,10,'Owned pause has not exposed a complete training-enabled restoration sample')
        self.current_pause = None
        return dict(owned_pause_restored=True, no_probe_frames_sent_while_unpaused=True)

    def drain_budget(self, context, seal):
        boot = self.anchor['original_boot_saved_clocks']
        result = None
        def exhausted():
            nonlocal result
            api = self.api()
            require(api['measurement_active'] is False and api['training_enabled'] is True
                    and api['client_count'] == 1, 'Unexpected input or pause during finite budget drain')
            frames = api['frame_count']-boot['frame_count']-max(0,api['measurement_frames']-boot['measurement_frame_count'])
            samples = api['optimized_samples']-boot['optimized_samples']
            opt = api['host_pipeline']['learning_exposure']['optimizer']
            require(api['host_pipeline']['inference_graphs']['postload_validations'] == 1
                    and opt['epoch'] == 1, 'Original replay-budget anchor provenance changed')
            done = (samples >= 8*max(1,frames) and opt['total']['attempts_started'] == opt['total']['outcomes_recorded']
                    and opt['unclassified_started_total'] == 0 and opt['total']['unavailable'] == 0)
            if done:
                result = dict(eligible_frames=frames, samples=samples, budget_exhausted=True,
                    owner=self.owner, original_anchor=self.prepared['component_proofs']['original_boot_anchor'])
            return done
        self.wait(exhausted,20,'Original finite sample budget did not drain')
        return result

    def close_probe(self, probe):
        self.probe.close()
        self.probe = None
        task = Path('/proc',str(self.owner['pid']),'task',str(self.probe_tid['tid']))
        self.wait(lambda: not task.exists(),5,'Owned probe handler has not finished')
        return dict(probe_handler_absent=True, no_additional_probe_input=True)

    def no_producers(self, context, seal):
        def absent():
            api = self.api()
            self.check_pause(api,self.current_pause)
            require(api['client_count'] in (0,1) and all(row['client_id'] == self.probe_id
                    for row in api['client_rows']), 'An unknown input producer appeared after probe closure')
            return api['client_count'] == 0 and not api['client_rows']
        self.wait(absent,5,'Cached owned-probe status has not exposed zero remaining input producers')
        require(not any(Path('/proc',str(self.owner['pid']),'task',str(tid)).exists()
                        for tid in [*self.actor_handlers,self.probe_tid['tid']]), 'An original handler remains')
        require(self.accept_held and self.fleet_frozen, 'Input holds were lost')
        self.assert_producers_held()
        # Account for truncated-name cleanup timers too. A completed client
        # count or known-handler subset alone is not a native-thread barrier.
        # HTTP request threads share bare high-sequence names with Timers.
        # No name-only exemption: literal cleanup closure is deferred until
        # the final API/bank view and the separate HTTP accept hold below.
        return dict(all_handlers_finished=True, listener_held=True, fleet_frozen=True,
                    cleanup_closure_deferred_until_HTTP_accept_hold=True)

    def hold_dashboard_finish_cleanup(self, context, banks):
        """Last API was in seal_banks; no dashboard request below this point."""
        require(banks['input_sources_sealed'] is True and banks['all_handlers_finished'] is True,
                'Game producers must already be closed')
        self.assert_producers_held()
        live_owner(self.owner)
        item = self.dashboard_accept
        task = Path('/proc', str(self.owner['pid']), 'task', str(item['tid']))
        def parked():
            require(starttime(task/'stat') == item['starttime_ticks']
                    and (task/'comm').read_text().strip() == item['comm'],
                    'Exact HTTP serve task changed')
            return (task/'wchan').read_text().strip().startswith('poll_schedule_timeout')
        self.wait(parked, 5, 'HTTP accept loop did not reach its source-bound poll wait')
        parent = self.dashboard_child.parent
        require(parent.stat().st_uid == os.getuid()
                and (parent/'cgroup.type').read_text().strip() in ('domain', 'domain threaded')
                and {q for q in parent.iterdir() if q.is_dir()} == {self.listener_child}
                and not self.dashboard_child.exists(), 'Unexpected HTTP-hold cgroup topology')
        self.dashboard_child.mkdir()
        self.dashboard_accept_held = True
        self.state()  # Independent recovery knows scope before the first hold.
        (self.dashboard_child/'cgroup.type').write_text('threaded\n')
        (self.dashboard_child/'cgroup.freeze').write_text('1\n')
        (self.dashboard_child/'cgroup.threads').write_text(str(item['tid'])+'\n')
        self.wait(lambda: dict(line.split() for line in
            (self.dashboard_child/'cgroup.events').read_text().splitlines()).get('frozen') == '1',
            3, 'HTTP accept task did not freeze')
        require(set(map(int,(self.dashboard_child/'cgroup.threads').read_text().split())) == {item['tid']}
                and starttime(task/'stat') == item['starttime_ticks'], 'HTTP hold inherited an unexpected task')
        # Existing preview long-poll is capped5s. General HTTP writes may
        # stall:15s is a qualification cutoff, never a promise they finish.
        # Failure unwinds this hold before restoring original controls.
        self.wait(lambda: not potential_handlers(self.owner['pid']), 15,
                  'Existing HTTP/Timer/unknown auto-thread did not finish; no SIGINT')
        time.sleep(1.1)
        require(not potential_handlers(self.owner['pid']),
                'Late cleanup/unknown auto-thread after HTTP admission closure')
        return dict(HTTP_accept_held=True, no_API_after_hold=True,
                    cleanup_Timer_and_unknown_autothreads_absent=True,
                    two_quiet_native_views_separated_s=1.1, HTTP_drain_cutoff_s=15,
                    existing_preview_longpoll_max_s=5, all_game_handler_native_births_absent=True)

    def release_dashboard_after_save_return(self):
        """Release only shutdown's HTTP join; this proves no save success."""
        require(self.dashboard_accept_held and self.original_stop_sent,
                'No exact pending-stop HTTP hold to release')
        live_owner(self.owner)
        item = self.dashboard_accept; child = self.dashboard_child; parent = child.parent
        task = Path('/proc', str(self.owner['pid']), 'task', str(item['tid']))
        require(child.resolve(strict=True) == child and child.stat().st_uid == os.getuid()
                and (child/'cgroup.type').read_text().strip() == 'threaded'
                and set(map(int,(child/'cgroup.threads').read_text().split())) == {item['tid']}
                and starttime(task/'stat') == item['starttime_ticks']
                and (task/'comm').read_text().strip() == item['comm'], 'HTTP release scope changed')
        (parent/'cgroup.threads').write_text(str(item['tid'])+'\n')
        (child/'cgroup.freeze').write_text('0\n')
        require(not (child/'cgroup.threads').read_text().strip(), 'HTTP hold still populated')
        child.rmdir(); self.dashboard_accept_held = False
        self.dashboard_release_after_save_return = dict(save_function_returned_signal_only=True,
            persistence_success_not_inferred=True, HTTP_serve_task_returned_before_finally_join=True)
        self.state()

    def seal_banks(self, context, pause, seal, budget, no_producers):
        result = None
        def sealed():
            nonlocal result
            before = self.api()
            self.check_pause(before,pause)
            stats = before['bank_persistence']
            if stats['writer_active'] or stats['output']['active'] is not None:
                return False
            banks = {name:self.bank_reader.read_bank_generation(name,MODEL/('robotron_dqn_latest_replay_'+name))
                     for name in ('hof','ephof')}
            time.sleep(1.1)  # Require a distinct original one-second cache generation.
            after = self.api()
            self.check_pause(after,pause)
            if after['bank_persistence']['writer_active'] or after['bank_persistence']['output']['active'] is not None:
                return False
            proof = self.bank_intent.validate(before,after,banks,
                expected_pid=self.owner['pid'],now=time.time())
            semantics = self.poststop.sealed_bank_semantics(banks)
            self.no_producers(context,seal)
            self.floor = {k:after[k] for k in ('frame_count','learner_frame_count','training_steps','optimized_samples')}
            result = dict(input_sources_sealed=True,all_handlers_finished=True,prefetch_paused=True,
                budget_exhausted=budget['budget_exhausted'],bank_shutdown_intent_verified=True,
                bank_pair=proof,bank_metadata_semantics=semantics,
                replay_exposure=after['host_pipeline']['learning_exposure']['replay'],
                clock_floor=self.floor,actual_paused_bank_intent_pair=True)
            return True
        self.wait(sealed,160,'Real bank generations did not become durably sealed')
        return result

    def stop_original(self, context, banks):
        live_owner(self.owner)
        require(b'PYTHONUNBUFFERED=1' in Path('/proc', str(self.owner['pid']), 'environ').read_bytes().split(b'\0'),
                'Original shutdown marker must reach its bound console before dashboard join')
        console = GAME/'logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/live-original01/trainer-console.log'
        before = console.lstat()
        require(console.resolve(strict=True) == console and stat.S_ISREG(before.st_mode)
                and before.st_uid == os.getuid() and before.st_nlink == 1,'Actual original console file required')
        for fd in (1,2):
            path = Path('/proc',str(self.owner['pid']),'fd',str(fd))
            descriptor = path.stat()
            require(path.readlink() == console and (descriptor.st_dev,descriptor.st_ino) == (before.st_dev,before.st_ino),
                    'Original stdout/stderr file binding changed')
        self.stop_stdout_binding = dict(path=str(console),device=before.st_dev,inode=before.st_ino,
            uid=before.st_uid,nlink=before.st_nlink,offset=before.st_size,owner=self.owner,
            scope='Original trainer fd1 and fd2 at the stop commit; subsequent bounded append bytes')
        self.original_stop_sent = True
        self.stop_requested_unix_s = time.time()
        self.state()
        os.kill(self.owner['pid'],signal.SIGINT)
        def retired():
            if self.dashboard_accept_held and process_start(self.owner['pid']) == self.owner['starttime_ticks']:
                info = console.lstat()
                require((info.st_dev,info.st_ino) == (before.st_dev,before.st_ino)
                        and 0 <= info.st_size-before.st_size <= 8*1024*1024,
                        'Bound original shutdown console append changed')
                with console.open('rb') as stream:
                    stream.seek(before.st_size); tail = stream.read(8*1024*1024+1)
                if b'Final model & settings saved' in tail:
                    # agent.save may catch persistence errors. This is only
                    # its RETURN boundary, needed for httpd.shutdown to join.
                    self.release_dashboard_after_save_return()
            return process_start(self.owner['pid']) is None and show(self.owner['unit']).get('MainPID') == '0'
        self.wait(retired,220,'Original trainer has not reached its actual terminal state')
        value = show(self.owner['unit'])
        require(value['InvocationID'] == self.owner['invocation_id'] and value['ExecMainPID'] == str(self.owner['pid'])
                and value['ExecMainCode'] == '1' and value['ExecMainStatus'] == '0'
                and value['NRestarts'] == '0' and value['ActiveState'] == 'inactive', 'Original main terminal outcome differs')
        return dict(actual_exit=0,original_absent=True,original_terminal=value,
                    stop_requested_unix_s=self.stop_requested_unix_s,terminal_observed_unix_s=time.time(),
                    stop_stdout_binding=self.stop_stdout_binding,
                    dashboard_release_after_save_return=self.dashboard_release_after_save_return)

    def verify_stopped(self,*args):
        return self.poststop.verify_stopped(*args)

    def install(self,*args):
        return self.poststop.install(*args)

    def start_once(self,*args):
        self.replacement = self.poststop.start_once(*args)
        self.state()
        return self.replacement

    def verify_startup(self,*args):
        return self.poststop.verify_startup(*args)

    def thaw_fleet(self,context,startup):
        self.assert_producers_held()
        for key in ('fleet','supplemental0'):
            self.check_producer_owners_and_actors()
            (self.producer_roots[key]/'cgroup.freeze').write_text('0\n')
            self.producer_holds[key] = False
            self.state()
        self.fleet_frozen = False
        self.state()
        return dict(original192_two_owner_fleet_thawed=True, no_actor_restart=True)


    def verify_progress(self,*args):
        return self.poststop.verify_progress(*args)

    def recover(self,controller,*,observation_pending):
        # Recovery is separately source-bound and shared with the independent
        # rescue. It may not start/retry a model or overwrite a foreign control.
        recovery = module(self.job['recovery_source'],'_handoff_recovery')
        if self.probe is not None:
            self.probe.close()
            self.probe = None
        self.state()
        return recovery.recover(self.job,self.out/'recovery-state.json',
            observation_pending=observation_pending)

    def finish(self,outcome):
        self.state()
        self.event('result.json',outcome)


def validate_current_stop_job(job):
    """Use the same actual constructor without execution outputs or controls."""
    backend = LinuxBackend(job, context_only=True)
    backend.guard.owner_and_files(backend.main)
    live_owner(backend.owner); backend.check_producer_owners_and_actors(); backend.rescue_live()
    import urllib.request
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=3) as response:
        wire = response.read(backend.raw.MAX_WIRE_BYTES+1)
    require(len(wire) <= backend.raw.MAX_WIRE_BYTES, 'Bound exact-context API read')
    api = backend.raw.parse_wire(wire)
    backend.guard.healthy(api, backend.main['baseline_API'],
                          backend.main['experiment'], time.time())
    exposure = api['host_pipeline']['learning_exposure']
    require(exposure['optimizer']['process_id'] == exposure['replay']['process_id'] == backend.owner['pid']
            and exposure['optimizer']['epoch'] == exposure['replay']['epoch'] == 1
            and api['memory_buffer_size'] == 6000000, 'Exact current epoch/hot6M context differs')
    roles = frame_map(api, set(range(192)))
    require(all(roles[int(slot)]['evaluation'] is role['eval'] for slot, role in
                backend.main['actual_roles'].items()), 'Current roles changed')
    potential_handlers(backend.owner['pid'])
    return dict(schema='robotron-current192-preserveRAM-stop-completed-context-prebody-v1', status='PASS',
                owner=backend.owner, held_inputs=len(backend.main['held_hashes']), actors=192, recipe_scale=.125,
                optimizer_lr=6.25e-6, complete_constructor_context_verified=True,
                execution_outputs_created=False, controls_or_signals=False,
                checkpoint_or_tensor_bodies_loaded=False)


def prepare(job):
    return LinuxBackend(job)
