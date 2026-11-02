#!/usr/bin/env python3
"""Prepared, UNEXECUTED Robotron CPU71 exclusion A/B/A controller.

Default only prints a static plan; --launch requires separately reviewed root
scheduling after the frozen quality campaign. No production file is edited.
--restore-only ORIGINALS --launch performs identity-bound emergency undo only.
This excludes owned Robotron competitors, never OS/IRQ/unrelated users.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import socket
import stat
import sys
import time
import traceback


HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
SCHEMA = 'robotron-inference-cpu-reservation-v1'
ALL = tuple(range(72))
OTHERS = tuple(range(71))
INFERENCE = (71,)
DESIGN_SHA = '0c726f69860311906e0dd04407dadce0c26edc58b3f5ddfb626d0d662a02838e'
PEER_SHA = 'a17e6ed06d27dceb11850489623ffde7a86ba0a98fceb513899de70444e47c41'
PEER = GAME / 'logs/managed-learning-20261015/run-26/inference-cpu-reservation-design-peer-review-20261017/review-receipt.json'
SIGNALS = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
MAX_RECORD_BYTES = 2 << 20
BLOCKED = {'run_quality_campaign.py', 'run_frozen_sidecar.py',
           'inference_worker_affinity.py', 'cpu_affinity_pilot.py',
           'parallel_state_fill_trial.py', 'whole_agent_smoke.py',
           'whole_agent_smoke_worker.py', 'forensic_parent.py', 'forensic_worker.py',
           'restore_serial_after_parallel_trial.py', 'checkpoint_at_frame.py',
           'cpu_reservation_trial.py'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def task_key(owner, row):
    return (owner['identity']['pid'], owner['identity']['starttime_ticks'],
            row['tid'], row['starttime_ticks'])


def mask(row):
    return tuple(row['affinity'])


def load_helpers():
    """Lazy stdlib-only imports; no old pilot plan/apply/restore policy used."""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(GAME.parent))
    base = importlib.import_module('Robotron.tools.inference_worker_affinity')
    identity = importlib.import_module('Robotron.tools.cpu_affinity_pilot')
    require(Path(base.__file__).resolve() == GAME / 'tools/inference_worker_affinity.py', 'Wrong observation helper')
    require(Path(identity.__file__).resolve() == GAME / 'tools/cpu_affinity_pilot.py', 'Wrong identity helper')
    return base, identity


class Journal:
    """Failure latches: never append behind a possibly torn record."""
    def __init__(self, path, *, create=True, start_sequence=0):
        self.path = Path(path)
        self.stream = self.path.open('x' if create else 'a')
        self.sequence = start_sequence
        self.failed = False
        self.errors = []
        if create:
            try:
                self.stream.flush(); os.fsync(self.stream.fileno())
                descriptor = os.open(self.path.parent, os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)  # new journal name durable before ANY treatment intent
                finally:
                    os.close(descriptor)
            except BaseException:
                self.stream.close()
                raise

    def record(self, kind, **fields):
        require(not self.failed, 'Journal previously failed')
        row = dict(sequence=self.sequence + 1, kind=kind, monotonic_s=time.monotonic(), **fields)
        try:
            payload = json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
            require(len(payload.encode()) <= MAX_RECORD_BYTES, 'Bounded journal record budget exceeded')
            require(os.fstat(self.stream.fileno()).st_size + len(payload.encode()) <= 512 << 20,
                    'Bounded512MiB journal budget exceeded')
            self.stream.write(payload)
            self.stream.flush(); os.fsync(self.stream.fileno())
            self.sequence += 1
        except BaseException as error:
            self.failed = True
            self.errors.append(repr(error))
            raise
        return row

    def best(self, kind, **fields):
        if self.failed:
            return False
        try:
            self.record(kind, **fields)
            return True
        except BaseException:
            return False

    def close(self):
        try:
            self.stream.close()
        except BaseException as error:
            self.failed = True; self.errors.append(repr(error))


class UnavailableJournal:
    """Emergency undo remains possible even when opening its log failed."""
    failed = True

    def __init__(self, error):
        self.errors = [repr(error)]

    def best(self, kind, **fields):
        return False

    def close(self):
        pass


class System:
    """Only this adapter reads /proc or changes an exact owned task mask."""
    def __init__(self, base, identity, trainer_pid, fleet_unit):
        self.base, self.identity = base, identity
        self.host = base.Host(trainer_pid, fleet_unit)

    now = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    def topology(self):
        online = sorted(self.base.online_cpus())
        nodes = {node.name: (node / 'cpulist').read_text().strip()
                 for node in sorted(Path('/sys/devices/system/node').glob('node[0-9]*'))}
        require(online == list(ALL) and len(nodes) == 1 and list(nodes.values()) == ['0-71'],
                'Require all72 CPUs online on the expected single NUMA node')
        return dict(online=online, numa_nodes=nodes)

    def no_competitors(self):
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal() or int(entry.name) == os.getpid():
                continue
            try:
                argv = [os.fsdecode(arg) for arg in (entry / 'cmdline').read_bytes().split(b'\0') if arg]
            except (FileNotFoundError, ProcessLookupError):
                continue
            require(not any(Path(arg).name in BLOCKED for arg in argv),
                    f'Conflicting quality/performance/checkpoint/diagnostic carrier PID{entry.name}')
        self.host.no_sidecars()
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            probe.bind(('::1', 9999))  # never listen/connect or create a game client

    def bindings(self):
        self.no_competitors()
        result = self.host.bindings()
        result['reservation_topology'] = self.topology()
        files = [HERE / name for name in ('cpu_reservation_trial.py', 'test_cpu_reservation_trial.py',
                                         'PREPARATION.txt', 'DESIGN.txt')]
        require(sha(HERE / 'DESIGN.txt') == DESIGN_SHA and sha(PEER) == PEER_SHA, 'Approved design/peer provenance changed')
        result['source_hashes'].update({str(path): sha(path) for path in [*files, PEER]})
        return result

    def verify_owner(self, owner):
        return self.identity.verify_process(owner)

    def thread_ids(self, owner):
        return self.identity.thread_ids(owner['identity']['pid'])

    def task(self, owner, tid):
        pid = owner['identity']['pid']
        before = self.identity.read_thread(pid, tid)
        affinity = sorted(os.sched_getaffinity(tid))
        comm = (Path('/proc') / str(pid) / 'task' / str(tid) / 'comm').read_text().strip()
        after = self.identity.read_thread(pid, tid)
        require(before['starttime_ticks'] == after['starttime_ticks'], 'TID reused while reading mask')
        return dict(tid=tid, starttime_ticks=after['starttime_ticks'], affinity=affinity, comm=comm)

    def scan_owner(self, owner):
        pid = owner['identity']['pid']
        for _ in range(8):
            self.verify_owner(owner)
            tids = self.thread_ids(owner)
            try:
                rows = [self.task(owner, tid) for tid in tids]
            except (FileNotFoundError, ProcessLookupError):
                continue
            if tids == self.thread_ids(owner):
                self.verify_owner(owner)
                return rows
        raise RuntimeError(f'Owner{pid} thread set failed bounded stabilization')

    def scan(self, owners):
        for _ in range(8):
            rows = [dict(kind=owner['kind'], identity=owner['identity'],
                         threads=self.scan_owner(owner)) for owner in owners]
            if all(self.identity.thread_ids(owner['identity']['pid']) == [row['tid'] for row in current['threads']]
                   for owner, current in zip(owners, rows)):
                for owner in owners:
                    self.verify_owner(owner)
                return rows
        raise RuntimeError('Whole-fleet thread sets failed bounded stabilization')

    def set_task(self, owner, row, target, expected_current):
        self.verify_owner(owner)
        actual = self.task(owner, row['tid'])
        require(task_key(owner, actual) == task_key(owner, row), 'TID identity changed before syscall')
        require(mask(actual) == tuple(expected_current), 'External current-mask change before syscall')
        os.sched_setaffinity(row['tid'], set(target))
        self.verify_owner(owner)
        after = self.task(owner, row['tid'])
        require(task_key(owner, after) == task_key(owner, row) and mask(after) == tuple(target),
                'Affinity identity/readback failed after syscall')

    def commit(self, path, value, *, immutable=False):
        self.identity.atomic_json(path, value, exclusive=immutable)
        if immutable:
            Path(path).chmod(0o444)
            with Path(path).open('rb') as stream:
                os.fsync(stream.fileno())
            descriptor = os.open(Path(path).parent, os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)


class ThreadState:
    def __init__(self, system, originals, journal):
        self.system, self.originals, self.journal = system, originals, journal
        self.owners = originals['processes']
        worker = originals['worker']
        self.worker = (worker['trainer']['pid'], worker['trainer']['starttime_ticks'],
                       worker['thread']['tid'], worker['thread']['starttime_ticks'])
        self.original = {task_key(owner, row): mask(row) for owner in self.owners for row in owner['threads']}
        self.expected = dict(self.original)
        self.allowed = {key: {value} for key, value in self.original.items()}
        self.possibly_mutated = set()
        self.newborn = set()
        self.treatment_started = False

    def observe(self, rows, phase, *, transition=False):
        worker_seen, matches = False, []
        for owner in rows:
            for row in owner['threads']:
                key = task_key(owner, row)
                if row['comm'] == self.system.base.THREAD_NAME and owner['kind'] == 'trainer':
                    matches.append(key)
                worker_seen |= key == self.worker
                if key not in self.expected:
                    self.newborn.add(key)  # available for emergency undo even if journaling fails
                    self.expected[key] = ALL if phase != 'B' else OTHERS
                    self.allowed[key] = {ALL}
                    self.journal.record('new_thread', key=list(key), observed=list(mask(row)),
                                        restore=list(ALL), fallback='original_same_owner_leader')
                expected = self.expected[key] if transition else (INFERENCE if key == self.worker else OTHERS) if phase == 'B' else ALL
                require(mask(row) == expected, f'Unexpected thread mask key{key}: {mask(row)} != {expected}')
        require(worker_seen and matches == [self.worker], 'Inference task missing/reused/ambiguous')

    def scan_guard(self, phase, *, transition=False):
        started = self.system.now()
        rows = self.system.scan(self.owners)
        elapsed = self.system.now() - started
        self.journal.record('thread_scan', phase=phase, transition=transition,
                            scan_start=started, scan_duration_s=elapsed, processes=rows)
        require(elapsed <= 1.0, 'Complete all-thread guard exceeded fixed1s scan budget')
        self.observe(rows, phase, transition=transition)
        return rows

    def treatment_write(self, owner, row, target):
        key = task_key(owner, row)
        require(tuple(target) == (INFERENCE if key == self.worker else OTHERS), 'Undeclared treatment target')
        with self.system.base.block_restore_signals():
            current = self.expected[key]
            self.journal.record('intent', key=list(key), expected=list(current), target=list(target), restore=list(ALL))
            self.system.verify_owner(owner)
            try:
                actual = self.system.task(owner, row['tid'])
            except (FileNotFoundError, ProcessLookupError):
                self.system.verify_owner(owner)
                require(key != self.worker, 'Original inference task exited before treatment')
                self.journal.record('task_exited_before_syscall', key=list(key))
                return False
            require(task_key(owner, actual) == key and mask(actual) == current, 'Task/current mask changed after durable intent')
            self.allowed.setdefault(key, {ALL}).add(tuple(target))
            self.possibly_mutated.add(key)  # MUST precede the syscall, including a failing syscall
            self.expected[key] = tuple(target)
            try:
                self.system.set_task(owner, row, target, current)
            except (FileNotFoundError, ProcessLookupError):
                self.system.verify_owner(owner)
                require(key != self.worker, 'Original inference task exited during treatment')
                try:
                    latest = self.system.task(owner, row['tid'])
                except (FileNotFoundError, ProcessLookupError):
                    latest = None
                require(latest is None or task_key(owner, latest) != key,
                        'Same task still present after unexplained syscall/readback lookup failure')
                self.journal.record('task_exited_after_possible_syscall', key=list(key))
                return False
            self.journal.record('applied', key=list(key), target=list(target))
            return True

    def apply_b(self):
        rows = self.scan_guard('A')
        self.journal.record('B_transition_begin')
        self.treatment_started = True
        worker_row = None
        for owner in rows:
            for row in owner['threads']:
                if task_key(owner, row) == self.worker:
                    worker_row = owner, row
                else:
                    self.treatment_write(owner, row, OTHERS)
        self.scan_guard('B', transition=True)  # reject unexpected newborn masks; never repair
        require(worker_row is not None, 'No original inference task')
        self.treatment_write(*worker_row, INFERENCE)
        self.scan_guard('B')

    def restore(self):
        """No API/source/global binding/journal health may gate eligible undo."""
        errors, restored, fallbacks = [], [], []
        for owner in self.owners:
            pid = owner['identity']['pid']
            proven = False
            for attempt in range(8):
                try:
                    self.system.verify_owner(owner)
                except Exception as error:
                    errors.append(dict(pid=pid, operation='owner_identity', error=repr(error)))
                    break  # still attempt EVERY other original owner
                enumeration_ok = True
                try:
                    tids = set(self.system.thread_ids(owner))
                except Exception as error:
                    errors.append(dict(pid=pid, operation='enumeration', error=repr(error)))
                    tids, enumeration_ok = set(), False
                # Enumeration/one unreadable task must never hide other sealed
                # or in-memory known tasks in this SAME verified owner.
                known_tids = {key[2] for key in self.expected if key[:2] == (
                    pid, owner['identity']['starttime_ticks'])}
                seen = set()
                inspection_ok = True
                for tid in sorted(tids | known_tids):
                    try:
                        row = self.system.task(owner, tid)
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    except Exception as error:
                        errors.append(dict(pid=pid, tid=tid, operation='task_inspection', error=repr(error)))
                        inspection_ok = False
                        continue
                    key, current = task_key(owner, row), mask(row)
                    seen.add(key)
                    is_new = key not in self.original
                    # A narrow newborn is plausible experiment inheritance only
                    # after a possibly-mutated parent in THIS exact owner. In A
                    # (or with no valid recovery intents), preserve external
                    # newborn masks instead of normalizing them on abort.
                    inheritance = {ALL}
                    if is_new:
                        for changed in self.possibly_mutated:
                            if changed[:2] == key[:2]:
                                intended = self.allowed.get(changed, {ALL})
                                if OTHERS in intended:
                                    inheritance.add(OTHERS)
                                if changed == self.worker and INFERENCE in intended:
                                    inheritance.add(INFERENCE)
                    allowed = inheritance if is_new else self.allowed.get(key, {ALL})
                    if current not in allowed:
                        errors.append(dict(key=list(key), operation='external_mask_skip', affinity=list(current)))
                        continue
                    if is_new:
                        fallbacks.append(list(key))
                    if current == ALL:
                        continue
                    # This diagnostic is best effort; failure NEVER prevents undo.
                    self.journal.best('restore_intent', key=list(key), current=list(current),
                                      restore=list(ALL), leader_fallback=is_new)
                    try:
                        self.system.set_task(owner, row, ALL, current)
                        self.expected[key] = ALL
                        restored.append(list(key))
                        self.journal.best('restored', key=list(key), leader_fallback=is_new)
                    except (FileNotFoundError, ProcessLookupError):
                        pass  # bounded next pass reclassifies exit/reuse, never writes its replacement blindly
                    except Exception as error:
                        errors.append(dict(key=list(key), operation='restore_write', error=repr(error)))
                proof, proof_ok = set(), True
                try:
                    proof_tids = self.system.thread_ids(owner)
                except Exception as error:
                    errors.append(dict(pid=pid, operation='proof_enumeration', error=repr(error)))
                    proof_tids, proof_ok = [], False
                for tid in proof_tids:
                    try:
                        row = self.system.task(owner, tid)
                        proof.add(task_key(owner, row))
                        proof_ok &= mask(row) == ALL
                    except Exception as error:
                        proof_ok = False
                        errors.append(dict(pid=pid, tid=tid, operation='task_readback', error=repr(error)))
                try:
                    self.system.verify_owner(owner)
                except Exception as error:
                    errors.append(dict(pid=pid, operation='proof_owner_identity', error=repr(error)))
                    proof_ok = False
                if enumeration_ok and inspection_ok and proof_ok and seen == proof:
                    proven = True
                    break
            if not proven:
                errors.append(dict(pid=pid, operation='owner_not_proven_restored'))
            elif owner['kind'] == 'trainer' and self.worker not in proof:
                errors.append(dict(pid=pid, operation='original_inference_not_proven_live'))
        return dict(masks_restored=not errors, manual_recovery_required=bool(errors),
                    errors=errors, changed_tasks=restored, newborn_leader_fallbacks=fallbacks,
                    journal_failed=self.journal.failed, journal_errors=list(self.journal.errors))


def prepare(system, directory):
    system.no_competitors()
    directory = Path(directory).resolve()
    require(directory.is_relative_to(GAME / 'logs') and not directory.exists(), 'Require a NEW directory under Robotron/logs')
    original_bindings = system.bindings()
    # Reuse the unchanged fixed recipe/exposure/API validator without invoking
    # its one-thread mutation/restore engine.
    plan = system.base.prepare(system.host, directory)
    require(original_bindings['worker'] == plan['bindings']['worker'], 'Inference identity changed during preparation')
    owners = [dict(kind='trainer', identity=original_bindings['worker']['trainer'])]
    owners += [dict(kind='mame', identity=actor) for actor in original_bindings['actors']]
    captured = system.scan(owners)
    require(len(captured) == 193, 'Require exactly original trainer+192 actors')
    for owner in captured:
        require(all(mask(row) == ALL for row in owner['threads']), 'Every original thread must have all72 CPUs')
        require(any(row['tid'] == owner['identity']['pid'] for row in owner['threads']), 'Owner leader unavailable')
        owner['default_original_affinity'] = list(ALL)
    require(system.bindings() == original_bindings, 'Full bindings changed during preparation')
    plan.update(schema=SCHEMA, bindings=original_bindings, phases=['A', 'B', 'Areturn'],
                settle_s=90, window_s=300, poll_s=1, binding_check_s=30,
                scan_budget_s=1.0, treatment='CPU71 excluded from other owned Robotron tasks',
                design_sha256=DESIGN_SHA, design_peer_sha256=PEER_SHA)
    originals = dict(schema=SCHEMA, project=str(GAME), uid=os.getuid(), boot_id=system.identity.boot_id(),
                     worker=original_bindings['worker'], processes=captured)
    return plan, originals


def run_trial(system, plan, originals):
    directory = Path(plan['output_directory'])
    status = dict(schema=SCHEMA, state='preparing', results=[], automatic_promotion=False)
    journal = None
    state = None
    with system.base.interrupt_handlers():
        try:
            require(originals['boot_id'] == system.identity.boot_id() and originals['uid'] == os.getuid()
                    and originals['project'] == str(GAME), 'Originals boot/user/project changed')
            require(system.bindings() == plan['bindings'], 'Bindings changed before durable precommit')
            directory.mkdir(parents=True, exist_ok=False)
            system.commit(directory / 'originals.json', originals, immutable=True)
            plan['originals_sha256'] = sha(directory / 'originals.json')
            system.commit(directory / 'precommit.json', plan, immutable=True)
            committed = sha(directory / 'precommit.json')
            journal = Journal(directory / 'mutation-journal.jsonl')
            state = ThreadState(system, originals, journal)
            # No affinity call can precede the complete originals/precommit above.
            state.scan_guard('A')
            system.host.configure_logs(plan['bindings']['logs'])
            previous = plan['initial_snapshot']
            status['state'] = 'running'
            with (directory / 'observations.jsonl').open('x') as stream:
                for phase in plan['phases']:
                    require(sha(directory / 'precommit.json') == committed, 'Immutable precommit changed')
                    require(system.bindings() == plan['bindings'], 'Full source/control/owner bindings changed')
                    if phase == 'B':
                        state.apply_b()
                    elif phase == 'Areturn':
                        with system.base.block_restore_signals():
                            restored = state.restore()
                        require(restored['masks_restored'] and not restored['journal_failed'], 'Areturn restoration incomplete')
                    state.scan_guard(phase)
                    started, checked, anchor, rows = system.now(), system.now(), None, []
                    journal.record('phase_start', phase=phase, phase_start=started,
                                   log_offsets=system.host.log_offsets)
                    while True:
                        tick = system.now()
                        row = system.host.capture()
                        row['phase'] = phase
                        row['stage'] = 'settle'
                        if row['observed_monotonic_s'] - started >= plan['settle_s']:
                            anchor = row['observed_monotonic_s'] if anchor is None else anchor
                            row['stage'] = 'primary'
                        row['issues'] = system.base.api_issues(row, plan, previous)
                        try:
                            state.scan_guard(phase)
                            if system.now() - checked >= plan['binding_check_s']:
                                require(system.bindings() == plan['bindings'], 'Full bindings changed')
                                checked = system.now()
                        except (OSError, ValueError, RuntimeError) as error:
                            row['issues'].append('all_thread_guard:' + repr(error))
                        row['guard_cycle_s'] = system.now() - tick
                        rows.append(row)
                        stream.write(json.dumps(row, allow_nan=False) + '\n'); stream.flush()
                        require(not row['issues'], 'Observation invalid: ' + repr(row['issues']))
                        previous = row
                        if anchor is not None and row['observed_monotonic_s'] - anchor >= plan['window_s']:
                            require(system.bindings() == plan['bindings'], 'Phase end bindings changed')
                            state.scan_guard(phase)
                            break
                        system.sleep(max(0, plan['poll_s'] - (system.now() - tick)))
                    status['results'].append(system.base.summarize_phase(rows, plan))
                    system.commit(directory / 'status.json', status)
            status.update(state='complete', decision=system.base.judge(status['results'], plan))
        except BaseException as error:
            status.update(state='failed', error=repr(error), traceback=traceback.format_exc(),
                          decision=dict(outcome='invalid', automatic_promotion=False))
        finally:
            # Handler lifetime encloses cleanup. Repeated handled signals wait
            # until all eligible owners and final status publication are tried.
            with system.base.block_restore_signals():
                restoration = state.restore() if state is not None else dict(
                    masks_restored=True, manual_recovery_required=False, reason='no_affinity_call_reached')
                status['restoration'] = restoration
                if journal is not None:
                    journal.close()
                    restoration['journal_failed'] = journal.failed
                    restoration['journal_errors'] = list(journal.errors)
                if not restoration['masks_restored'] or restoration.get('journal_failed') or SIGNALS.intersection(signal.sigpending()):
                    status.update(state='failed', decision=dict(outcome='invalid', automatic_promotion=False))
                    restoration['manual_recovery_required'] = not restoration['masks_restored'] or restoration.get('journal_failed', False)
                try:
                    if directory.exists():
                        system.commit(directory / 'status.json', status)
                except BaseException as error:
                    status.update(state='failed', status_publication_error=repr(error),
                                  decision=dict(outcome='invalid', automatic_promotion=False))
                    restoration['manual_recovery_required'] = True
                    print(json.dumps(status, allow_nan=False), file=sys.stderr)
    return status


def validate_originals(system, path):
    path = Path(path).absolute()
    require(path == path.resolve(strict=True), 'Originals path contains a symlink')
    require(path.name == 'originals.json' and path.is_relative_to(GAME / 'logs'), 'Unexpected originals path')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o444, 'Originals must be owned single-link readonly regular file')
    original = json.loads(path.read_text())
    plan = json.loads(path.with_name('precommit.json').read_text())
    require(plan['originals_sha256'] == sha(path), 'Originals/precommit digest mismatch')
    require(original['schema'] == SCHEMA and original['project'] == str(GAME)
            and original['uid'] == os.getuid() and original['boot_id'] == system.identity.boot_id(), 'Wrong project/user/boot')
    owners = original['processes']
    require(len(owners) == 193 and [owner['kind'] for owner in owners] == ['trainer'] + ['mame'] * 192,
            'Unexpected original owner set')
    require([owner['identity']['client_slot'] for owner in owners[1:]] == list(range(192)), 'Original slots differ')
    require(len({owner['identity']['pid'] for owner in owners}) == 193, 'Duplicate original owner PID')
    for owner in owners:
        require(tuple(owner['default_original_affinity']) == ALL and
                all(mask(row) == ALL for row in owner['threads']), 'Unexpected original masks')
    return path, original


def restore_only(system, path):
    path, original = validate_originals(system, path)
    # Valid complete journal prefix is sufficient for earlier durable intents.
    # A torn last record never authorizes another original task's mask change.
    intents, sequence, damaged = [], 0, False
    journal_path = path.with_name('mutation-journal.jsonl')
    try:
        with journal_path.open('r') as stream:
            while line := stream.readline(MAX_RECORD_BYTES):
                try:
                    row = json.loads(line)
                    require(line.endswith('\n') and type(row['sequence']) is int and row['sequence'] == sequence + 1,
                            'Torn/out-of-order journal')
                    if row['kind'] == 'intent':
                        require(len(row['key']) == 4 and all(type(value) is int for value in row['key'])
                                and isinstance(row['target'], list) and isinstance(row['restore'], list), 'Malformed intent')
                except (ValueError, KeyError, TypeError, RuntimeError):
                    damaged = True; break
                sequence = row['sequence']
                if row['kind'] == 'intent':
                    intents.append(row)
    except OSError:
        damaged = True
    try:
        journal = Journal(journal_path, create=False, start_sequence=sequence)
    except Exception as error:
        journal = UnavailableJournal(error)
    if damaged:
        journal.failed = True; journal.errors.append('missing/torn journal; only valid prefix intents available')
    state = ThreadState(system, original, journal)
    for row in intents:
        key = tuple(row['key'])
        target = INFERENCE if key == state.worker else OTHERS
        if key in state.original and tuple(row['target']) == target and tuple(row['restore']) == ALL:
            state.allowed[key].add(target)
            state.possibly_mutated.add(key)
    with system.base.interrupt_handlers(), system.base.block_restore_signals():
        result = state.restore()
        journal.close()
        result['journal_failed'] = journal.failed
        result['journal_errors'] = list(journal.errors)
        result['manual_recovery_required'] |= journal.failed
        try:
            system.commit(path.with_name(f'recovery-{time.time_ns()}.json'), result, immutable=True)
        except BaseException as error:
            result['manual_recovery_required'] = True
            result['publication_error'] = repr(error)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trainer-pid', type=int)
    parser.add_argument('--fleet-unit')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--restore-only', type=Path)
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args(argv)
    if not args.launch:
        print(json.dumps(dict(schema=SCHEMA, status='PLAN_ONLY_NO_RUNTIME_QUERIES',
            phases=['A', 'B', 'Areturn'], settle_s=90, primary_s=300, inference_cpu=71,
            other_owned_tasks_cpus=list(OTHERS), original_cpus=list(ALL),
            automatic_promotion=False, live_authorization=False,
            scope='Separate Robotron allocation hypothesis; after320M quality/review only'), indent=2))
        return 0
    try:
        base, identity = load_helpers()
        if args.restore_only:
            require(args.trainer_pid is None and args.fleet_unit is None and args.output_dir is None,
                    'Restore-only does not accept live experiment inputs')
            system = System(base, identity, 0, '')
            result = restore_only(system, args.restore_only)
            print(json.dumps(result, indent=2))
            return int(result['manual_recovery_required'])
        require(args.trainer_pid and args.fleet_unit and args.output_dir, 'Launch requires exact trainer PID/fleet unit/new output directory')
        system = System(base, identity, args.trainer_pid, args.fleet_unit)
        plan, originals = prepare(system, args.output_dir)
        result = run_trial(system, plan, originals)
        print(json.dumps(result, indent=2))
        return int(result['state'] != 'complete')
    except BaseException as error:
        print(f'Reservation refused/failed; exact-owner recovery may be required: {error!r}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
