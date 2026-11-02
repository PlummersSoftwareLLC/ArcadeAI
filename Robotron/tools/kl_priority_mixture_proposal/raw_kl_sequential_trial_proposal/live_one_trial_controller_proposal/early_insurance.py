"""One asynchronous live model-only insurance; no work at import/default.

The root controller owns the active runtime, observation clock and ending. Only
Snapshot.start/tick mutate its managed-request bookkeeping, on the main thread.
Model copying and the single retained CPU unit run in a background thread. No
Torch, NumPy, application import, model decoding or replay copy occurs here.
"""
import copy
import errno
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
import time
import traceback

MAX_MODEL = 512 << 20
OWNER_KEYS = {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def command(argv, *, timeout=5):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    absent_show = argv[:3] == ['systemctl', '--user', 'show'] and 'LoadState=not-found' in result.stdout.splitlines()
    require(result.returncode == 0 or absent_show, 'Owned command failed: '+repr(argv)+': '+result.stderr[:1024])
    return result.stdout


def publish_text(base, path, text):
    require(0 < len(text.encode()) <= base.MAX_SOURCE, 'Bounded nonempty unit/source archive required')
    with Path(path).open('x') as stream:
        stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
    descriptor = os.open(Path(path).parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return base.fingerprint(path, base.MAX_SOURCE)


class Snapshot:
    """One unique managed request, then one explicit independent freeze.

    tick returns PENDING/COMPLETE/FAILED and never reads model bytes. freeze is
    called only in the early background task or after the candidate latch/pause.
    The caller enforces its ending wall budget independently of filesystem I/O.
    """
    def __init__(self, adapter, base, runtime, spec, output, *, clock=time.monotonic, wall=time.time):
        self.adapter, self.base, self.runtime = adapter, base, runtime
        self.spec, self.output = copy.deepcopy(spec), Path(output)
        require(self.output.is_absolute(), 'Snapshot output must be an explicit absolute owned path')
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', self.spec['tag'] or ''), 'Unique snapshot tag required')
        require(self.spec['save_timeout_s'] == 60, 'Snapshot save budget differs')
        self.clock, self.wall = clock, wall
        self.state, self.error, self.frozen = 'NEW', None, None
        self.freeze_started = False
        self.owner = self.raw_pin = self.transition = self.completed = self.floor = None

    def start(self, raw, clock_floor):
        require(self.state == 'NEW', 'Managed snapshot is one-shot')
        self.state = 'STARTING'
        try:
            runtime, base = self.runtime, self.base
            self.owner = copy.deepcopy(runtime.trainer_id())
            require(set(self.owner) == OWNER_KEYS, 'Actual owned trainer identity required')
            require(raw['client_count'] in (0, 192) and type(raw['client_count']) is int and
                    raw['host_pipeline']['learning_exposure']['optimizer']['process_id'] == self.owner['pid'] and
                    not raw.get('measurement_active', False), 'Snapshot API owner/client scope differs')
            self.floor = self.adapter.four(clock_floor)
            require(all(raw[key] >= value for key, value in self.floor.items()), 'Snapshot floor exceeds observed clocks')
            self.output.mkdir(mode=0o700)
            self.raw_pin = base.publish(self.output/'trigger-API.json', raw)
            model = Path(runtime.job['model_dir'])
            self.target = model/'managed-checkpoints'/(self.spec['tag']+'.pt')
            require(all(not Path(str(self.target)+suffix).exists() for suffix in ('', '.tmp', '.bak')),
                    'Snapshot source/tmp/bak must all be new')
            require(not (model/'managed_save.request.json').exists() and runtime.pending is None,
                    'Another managed request is pending')
            require(not (model/'managed_save.request.json.failed').exists(), 'Unresolved failed request')
            self.transition = dict(before=None, before_unix_s=self.wall())
            slot = model/'managed_save.request.json.completed'
            if slot.exists():
                before = base.fingerprint(slot, base.MAX_JSON)
                require(before == runtime.current_completed, 'Current completion changed before new request')
                actual, archive = base.exclusive_copy(slot, self.output/'completed-before.json')
                self.transition['before'] = dict(actual_pin=actual, archive=archive)
            require(self.spec['tag'] != runtime.job['startup_tag'], 'Insurance/candidate cannot reuse startup tag')
            self.started = self.clock()
            with runtime.metrics.block_restore_signals():
                pending = self.adapter.publish_request(base, model, self.output/'request.json', self.spec['tag'],
                                                      lambda value: setattr(runtime, 'pending', value))
            self.transition.update(request=dict(actual_pin=pending['pin'], archive=pending['archive']),
                                   request_unix_s=pending['publication']['before_expose_unix_s'])
            self.state = 'PENDING'
        except BaseException as error:
            self.state, self.error = 'FAILED', error
            raise
        return self.result()

    def tick(self):
        if self.state != 'PENDING':
            return self.result()
        try:
            require(self.clock() <= self.started + 60, 'First managed snapshot timed out; no retry')
            runtime, base = self.runtime, self.base
            require(runtime.trainer_id() == self.owner, 'Snapshot owner changed')
            runtime.request_guard()
            model = Path(runtime.job['model_dir']);slot = model/'managed_save.request.json.completed'
            failed = model/'managed_save.request.json.failed'
            if failed.exists() and base.read_json(base.fingerprint(failed, base.MAX_JSON)) == {'tag': self.spec['tag']}:
                raise RuntimeError('First managed snapshot failed; no retry')
            observed = base.fingerprint(slot, base.MAX_JSON)
            if base.read_json(observed) != {'tag': self.spec['tag']}:
                return self.result()
            pending = runtime.pending
            require(pending is not None and self.adapter.request_identity(observed['identity']) ==
                    self.adapter.request_identity(pending['pin']['identity']) and observed['identity']['nlink'] == 1,
                    'Completion is not the originally published owned request')
            actual, archive = base.exclusive_copy(slot, self.output/'completed-after.json')
            require(actual == observed, 'Completed request changed during archive')
            self.owner_after = copy.deepcopy(runtime.trainer_id())
            require(self.owner_after == self.owner, 'Snapshot owner changed across actual completion archive')
            self.transition.update(after=dict(actual_pin=actual, archive=archive), after_unix_s=self.wall())
            self.completed = copy.deepcopy(actual)
            with runtime.metrics.block_restore_signals():
                pending['publication']['completed_identity'] = actual['identity']
                runtime.current_completed = copy.deepcopy(actual); runtime.pending = None
            self.state = 'COMPLETE'
        except BaseException as error:
            self.state, self.error = 'FAILED', error
        return self.result()

    def result(self):
        return dict(status=self.state, error=None if self.error is None else repr(self.error),
                    completed=copy.deepcopy(self.completed), tag=self.spec['tag'])

    def freeze(self, *, purpose='candidate', phase):
        require(self.state == 'COMPLETE' and not self.freeze_started, 'Freeze one completed snapshot exactly once')
        self.freeze_started = True
        # Seal only the new completed model. No alias/replacement can be adopted.
        descriptor = os.open(self.target, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(descriptor)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                    and 0 < before.st_size <= MAX_MODEL and self.base.identity(before) == self.base.identity(self.target.lstat()),
                    'New snapshot is not an owned bounded single-link model')
            os.fchmod(descriptor, 0o444); os.fsync(descriptor)
            require(self.base.identity(os.fstat(descriptor)) == self.base.identity(self.target.lstat()),
                    'Snapshot path replaced while sealing')
        finally:
            os.close(descriptor)
        source, copied = self.base.exclusive_copy(self.target, self.output/'model-readonly-copy.pt')
        require(source['sha256'] == copied['sha256'] and source['bytes'] == copied['bytes'] and
                copied['identity']['mode'] == '0o444' and
                (source['identity']['device'], source['identity']['inode']) !=
                (copied['identity']['device'], copied['identity']['inode']), 'Independent readonly model copy differs')
        acquisition = dict(schema='robotron-owned-phase-snapshot-acquisition-v1', purpose=purpose,
            experiment=self.runtime.job['experiment'], model_dir=self.runtime.job['model_dir'],
            owner_before=self.owner, owner_after=self.owner_after,
            client_count=self.base.read_json(self.raw_pin)['client_count'], source_checkpoint=self.adapter.triple(source),
            clock_floor=self.floor, phase_record_sha256=phase['record']['sha256'], boot_checkpoint=phase['boot_checkpoint'],
            tag=self.spec['tag'], completed_slot_transition=self.transition, stopped_absence=None)
        self.frozen = dict(source=source, verification_copy=copied,
                           acquisition=self.base.publish(self.output/'acquisition.json', acquisition))
        return copy.deepcopy(self.frozen)


class RetainedCPU:
    """Single direct7d CPU service. Success archives its original unit before release.

    Failure retains the original failed service and evidence. Requested unit,
    exact argv/job and the actual child owner are exposed for the controller's
    narrowly scoped competing-helper guard; no basename exemption is granted.
    """
    def __init__(self, base, *, run=command, schedule=None, clock=time.monotonic, sleep=time.sleep):
        self.base, self.run, self.clock, self.sleep = base, run, clock, sleep
        self.schedule = schedule

    def show(self, unit):
        text = self.run(['systemctl', '--user', 'show', unit])
        return dict(line.split('=', 1) for line in text.splitlines() if '=' in line), text

    def run_once(self, helper, job_pin, verifier, directory):
        base, spec = self.base, helper.spec
        base.pin(verifier['script'], base.MAX_SOURCE)
        base.validate_python_binding(verifier, helper.original_insurance, hash_executable=True)
        unit = spec['cpu_unit'];timer = unit.removesuffix('.service')+'.timer'
        for name in (unit, timer):
            state, _ = self.show(name)
            require(state.get('LoadState') == 'not-found', 'Early CPU unit/timer name already exists')
        numerical = [verifier['python'], '-Xgil=0', '-I', '-B', '-u', verifier['script']['path'], '--execute',
            '--job', job_pin['path'], '--expected-job-sha256', job_pin['sha256'],
            '--expected-verifier-sha256', verifier['script']['sha256']]
        argv = ['systemd-run', '--user', '--unit='+unit, '--property=Type=exec', '--property=RemainAfterExit=yes',
            '--property=Restart=no', '--property=CPUQuota=200%', '--property=MemoryMax=3G',
            '--property=MemorySwapMax=0', '--property=TasksMax=64', '--property=RuntimeMaxSec=120',
            '--property=TimeoutStopSec=5', '--property=WorkingDirectory='+helper.runtime.job['game_root'],
            '--property=StandardOutput=append:'+str(directory/'stdout.txt'),
            '--property=StandardError=append:'+str(directory/'stderr.txt'),
            '--property=UnsetEnvironment=LD_PRELOAD PYTHONPATH',
            '--setenv=CUDA_VISIBLE_DEVICES=', '--setenv=PYTHONDONTWRITEBYTECODE=1',
            '--setenv=OMP_NUM_THREADS=2', '--setenv=MKL_NUM_THREADS=2',
            '--setenv=OPENBLAS_NUM_THREADS=2', '--setenv=NUMEXPR_NUM_THREADS=2',
            '--on-active=3s', '--timer-property=AccuracySec=100ms'] + numerical
        intent = base.publish(directory/'execution-intent.json', dict(kind='insurance', unit=unit, timer=timer,
            argv=argv, job=job_pin, command=numerical, only_one_attempt=True))
        helper.register_request(dict(request=intent, unit=unit, timer=timer, job=job_pin,
                                     argv=argv, command=numerical, owner=None, carrier=None,
                                     terminal_archive=None, release=None))
        # The detached scheduling carrier must return and be reaped before firing.
        launch = helper.schedule(argv) if self.schedule is None else self.schedule(helper, argv)
        carrier_done = self.clock()
        base.publish(directory/'carrier-completion.json', dict(returncode=0, stdout=launch, reaped_monotonic_s=carrier_done))
        deadline = carrier_done + spec['cpu_timeout_s'] + 8
        adopted = None
        while True:
            state, text = self.show(unit)
            if state.get('LoadState') == 'loaded' and int(state.get('ExecMainPID', '0')) > 0:
                pid = int(state['ExecMainPID'])
                require(int(state.get('ExecMainStartTimestampMonotonic', '0')) / 1000000 > carrier_done,
                        'Early CPU started before scheduling carrier reaped')
                terminal = state.get('SubState') in ('exited', 'dead', 'failed') or state.get('ActiveState') == 'failed'
                if adopted is None and not terminal and state.get('ActiveState') in ('active', 'activating'):
                    proc = Path('/proc', str(pid))
                    try:
                        fields = (proc/'stat').read_text().rsplit(')', 1)[1].split()
                        actual_argv = [os.fsdecode(value) for value in (proc/'cmdline').read_bytes().split(b'\0') if value]
                        if not actual_argv:
                            raise ProcessLookupError(errno.ESRCH, 'CPU cmdline empty at possible terminal transition')
                        require(proc.stat().st_uid == os.getuid() and (proc/'exe').resolve(strict=True) ==
                                Path(verifier['python']).resolve(strict=True) and actual_argv == numerical and
                                (proc/'stat').read_text().rsplit(')', 1)[1].split()[19] == fields[19],
                                'Retained CPU UID/executable/argv/start bracket differs')
                        adopted = dict(pid=pid, starttime_ticks=int(fields[19]), unit=unit,
                            invocation_id=state['InvocationID'], cgroup=state['ControlGroup'])
                        helper.adopt_cpu(adopted)
                    except OSError as error:
                        if error.errno not in (errno.ENOENT, errno.ESRCH):
                            raise
                        ended, ended_text = self.show(unit)
                        require(ended.get('LoadState') == 'loaded' and int(ended['ExecMainPID']) == pid and
                                ended['InvocationID'] == state['InvocationID'] and ended['NRestarts'] == '0' and
                                ended.get('SubState') in ('exited', 'dead', 'failed'),
                                'CPU disappeared without its same retained original terminal')
                        state, text, terminal = ended, ended_text, True
                        adopted = helper.registration()['owner']
                if terminal:
                    break
            require(self.clock() <= deadline, 'Retained early CPU failed to terminate within fixed bound')
            self.sleep(.1)
        if adopted is None:
            adopted = helper.registration()['owner']  # Root's exact-argv guard may have observed it first.
        if adopted is not None:
            require(state['InvocationID'] == adopted['invocation_id'] and int(state['ExecMainPID']) == adopted['pid'],
                    'Original CPU unit identity changed')
        # Archive original loaded unit and invocation while retained, before stop/reset.
        show_pin = publish_text(base, directory/'original-terminal-show.txt', text)
        cat_pin = publish_text(base, directory/'original-terminal-cat.txt', self.run(['systemctl', '--user', 'cat', unit]))
        journal_pin = publish_text(base, directory/'original-invocation-journal.txt', self.run([
            'journalctl', '--user', '--no-pager', '-o', 'short-iso-precise', '_SYSTEMD_INVOCATION_ID='+state['InvocationID']]))
        completion = dict(original_invocation=state['InvocationID'], original_pid=int(state['ExecMainPID']),
            original_exec_code=int(state['ExecMainCode']), original_exit=int(state['ExecMainStatus']),
            result=state['Result'], unit_released=False, original_owner=adopted,
            original_nrestarts=int(state['NRestarts']),
            terminal_show=show_pin, terminal_cat=cat_pin, invocation_journal=journal_pin)
        completion_pin = base.publish(directory/'original-execution-completion.json', completion)
        if adopted is not None:
            helper.record_terminal(completion_pin)
        require(adopted is not None, 'Original unit archived but no independently observed CPU PID/start; no invented identity')
        require(completion['original_exec_code'] == 1 and completion['original_exit'] == 0 and completion['original_nrestarts'] == 0 and
                completion['result'] == 'success', 'Original early insurance CPU failed; retained, no retry')
        report_pin = base.fingerprint(Path(base.read_json(job_pin)['output_directory'])/'cpu-verification.json', base.MAX_JSON)
        report = base.read_json(report_pin)
        require(report['status'] == 'PASS' and report['mode'] == 'insurance' and
                report['job_file']['sha256'] == job_pin['sha256'] and report['root_job'] == base.read_json(job_pin),
                'Original early CPU report does not match its actual job')
        before, _ = self.show(unit)
        require(before['InvocationID'] == adopted['invocation_id'] and int(before['ExecMainPID']) == adopted['pid'] and
                before['ExecMainStatus'] == '0', 'Original CPU changed before exact release')
        # A successful terminal unit is now archived; release only its exact names.
        releases = []
        for name in (timer, unit):
            actual, _ = self.show(name)
            if actual.get('LoadState') == 'not-found':
                releases.append(dict(unit=name, already_absent=True)); continue
            if name == unit:
                require(actual['InvocationID'] == adopted['invocation_id'] and int(actual['ExecMainPID']) == adopted['pid'],
                        'CPU owner changed during release')
            else:
                require(unit in actual.get('Triggers', '').split(), 'Registered timer no longer targets owned CPU unit')
            self.run(['systemctl', '--user', 'stop', name])
            after, _ = self.show(name)
            require(after.get('LoadState') == 'not-found' or after.get('ActiveState') == 'inactive',
                    'Owned CPU unit/timer did not release')
            releases.append(dict(unit=name, already_absent=False, final_load_state=after.get('LoadState')))
        reviewed = base.publish(directory/'result-review-and-release.json', dict(status='PASS', kind='insurance',
            original_invocation=adopted['invocation_id'], original_pid=adopted['pid'], original_exec_code=1,
            original_exit=0, original_result='success', original_archived_before_release=True,
            numeric_report_sha256=report_pin['sha256'], original_completion=completion_pin, actual_unit=unit,
            releases=releases, original_owner=adopted))
        helper.record_release(reviewed)
        return dict(insurance_report=report_pin, successful_execution=intent,
                    successful_completion=completion_pin, successful_result=reviewed)


class EarlyInsurance:
    def __init__(self, adapter, base, runtime, spec, output, *, executor=None, spawn=None,
                 clock=time.monotonic, wall=time.time, run=command):
        require(set(spec) == {'tag', 'cpu_unit', 'save_timeout_s', 'cpu_timeout_s'} and
                spec['cpu_timeout_s'] == 120 and spec['save_timeout_s'] == 60 and
                re.fullmatch(r'robotron-[A-Za-z0-9_-]+\.service', spec['cpu_unit'] or ''), 'Explicit unique bounded early CPU spec required')
        self.adapter, self.base, self.runtime, self.spec = adapter, base, runtime, copy.deepcopy(spec)
        self.output = Path(output); self.clock, self.wall, self.run = clock, wall, run
        self.snapshot = Snapshot(adapter, base, runtime, spec, self.output/'snapshot', clock=clock, wall=wall)
        self.executor = executor or RetainedCPU(base, run=run, clock=clock)
        self.spawn = spawn or self._spawn
        self._lock = threading.Lock(); self._result = dict(status='NEW'); self._registration = None
        self.worker_started = False
        self.original_insurance = copy.deepcopy(runtime.job['insurance_verification'])

    @staticmethod
    def _spawn(function):
        thread = threading.Thread(target=function, name='one-early-insurance', daemon=True); thread.start()
        return thread

    def register_request(self, value):
        with self._lock:
            require(self._registration is None, 'Early CPU launch is one-shot')
            self._registration = copy.deepcopy(value)

    def adopt_cpu(self, owner):
        with self._lock:
            require(self._registration is not None and set(owner) == OWNER_KEYS and
                    owner['unit'] == self._registration['unit'] and owner['pid'] > 0 and owner['starttime_ticks'] > 0 and
                    re.fullmatch('[0-9a-f]{32}', owner['invocation_id'] or '') and owner['cgroup'], 'Actual registered CPU identity required')
            previous = self._registration['owner']
            require(previous is None or previous == owner, 'Never adopt replacement early CPU')
            self._registration['owner'] = copy.deepcopy(owner)

    def registration(self):
        with self._lock:
            return copy.deepcopy(self._registration)

    def record_terminal(self, pin):
        value = self.base.read_json(pin)
        require(pin['identity']['mode'] == '0o444' and pin['identity']['uid'] == os.getuid() and
                pin['identity']['nlink'] == 1, 'Readonly owned original CPU terminal archive required')
        with self._lock:
            owner = self._registration['owner']
            require(owner is not None and value['original_owner'] == owner and
                    value['original_pid'] == owner['pid'] and value['original_invocation'] == owner['invocation_id'] and
                    self._registration['terminal_archive'] is None, 'Original CPU terminal does not join registered actual owner')
            self._registration['terminal_archive'] = copy.deepcopy(pin)

    def record_release(self, pin):
        value = self.base.read_json(pin)
        with self._lock:
            owner = self._registration['owner']
            require(self._registration['terminal_archive'] is not None and self._registration['release'] is None and
                    value['original_completion'] == self._registration['terminal_archive'] and
                    value['original_owner'] == owner and value['actual_unit'] == owner['unit'] and
                    value['original_archived_before_release'] is True and value['original_exit'] == 0,
                    'Exact CPU release lacks its immutable original terminal proof')
            self._registration['release'] = copy.deepcopy(pin)

    def schedule(self, argv):
        # The scanner refreshes registration INSIDE each classified PID branch.
        # It waits for this short birth-registration critical section, rather
        # than seeing a child whose exact start identity has not been recorded.
        with self._lock:
            require(self._registration is not None and not self._registration.get('carrier_attempted', False),
                    'One registered detached scheduling carrier only')
            self._registration['carrier_attempted'] = True
            process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                fields = Path('/proc', str(process.pid), 'stat').read_text().rsplit(')', 1)[1].split()
                self._registration['carrier'] = dict(pid=process.pid, starttime_ticks=int(fields[19]),
                                                      argv=list(argv), reaped=False)
            except BaseException as error:
                self._registration['carrier_birth_error'] = repr(error)
                try:
                    if process.poll() is None:
                        process.terminate()
                    process.communicate(timeout=2)
                except BaseException as cleanup:
                    self._registration['carrier_birth_cleanup_error'] = repr(cleanup)
                raise
        try:
            stdout, stderr = process.communicate(timeout=2)
            require(process.returncode == 0, 'Original scheduling carrier failed: '+stderr[:1024])
            return stdout
        except BaseException:
            try:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=2)
            except BaseException as cleanup:
                with self._lock:
                    self._registration['carrier']['cleanup_error'] = repr(cleanup)
            raise
        finally:
            with self._lock:
                self._registration['carrier']['reaped'] = process.returncode is not None
                self._registration['carrier']['returncode'] = process.returncode

    def result(self):
        with self._lock:
            return copy.deepcopy(self._result)

    def start(self):
        require(self.result()['status'] == 'NEW', 'Early insurance cannot be restarted')
        with self._lock:
            self._result = dict(status='PENDING', phase='prepare')
        try:
            return self._start()
        except BaseException as error:
            with self._lock:
                self._result = dict(status='FAILED', phase='prepare', error=repr(error), traceback=traceback.format_exc())
            raise

    def _start(self):
        self.output.mkdir(mode=0o700)
        raw = self.runtime.raw_api()
        require(raw['client_count'] == 192 and raw['training_enabled'] is True, 'Early insurance needs actual healthy192, no pause')
        self.owner = copy.deepcopy(self.runtime.trainer_id())
        self.runtime.inspect('after')
        # All mutable source/unit/control observations happen on this main thread.
        pairs, self.context = self.runtime.phase_sources('early-insurance')
        self.source_pairs = self.base.publish(self.output/'source-archive-pairs.json', pairs)
        old_control = self.context['archived_control'];self.base.pin(old_control, self.base.MAX_JSON)
        _, control = self.base.exclusive_copy(old_control['path'], self.output/'archived-control.json')
        self.context['archived_control'] = control
        unit = self.runtime.job['trainer_unit']
        self.context['archived_trainer_unit'] = publish_text(self.base, self.output/'trainer-unit-cat.txt',
            self.run(['systemctl', '--user', 'cat', unit]))
        self.unit_show = publish_text(self.base, self.output/'trainer-unit-show.txt',
            self.run(['systemctl', '--user', 'show', unit]))
        self.phase = dict(record=copy.deepcopy(self.runtime.record_pin),
            boot_checkpoint=self.adapter.triple(self.runtime.current_checkpoint['source']),
            boot_verification=copy.deepcopy(self.runtime.current_checkpoint['verification']),
            expected=self.adapter.expected_start(self.runtime.record, self.runtime.record_pin,
                                                self.base.read_json(self.runtime.current_checkpoint['verification'])))
        self.snapshot.start(raw, self.adapter.four(raw))
        require(self.snapshot.owner == self.owner, 'Early owner changed during request preparation')
        with self._lock:
            self._result = dict(status='PENDING', phase='managed-save')
        return self.result()

    def tick(self):
        if self.result()['status'] != 'PENDING' or self.worker_started:
            return self.result()
        state = self.snapshot.tick()
        if state['status'] == 'FAILED':
            with self._lock:
                self._result = dict(status='FAILED', error=state['error'], phase='managed-save')
        elif state['status'] == 'COMPLETE':
            self.worker_started = True
            # Small state is frozen BEFORE dispatch; worker never calls runtime
            # static/inspect/API/owner methods or mutates managed-request state.
            self.verifier = copy.deepcopy(self.runtime.job['verifier'])
            try:
                self.worker = self.spawn(self._background)
            except BaseException as error:
                with self._lock:
                    self._result = dict(status='FAILED', phase='background-dispatch', error=repr(error))
        return self.result()

    def _background(self):
        try:
            frozen = self.snapshot.freeze(purpose='candidate', phase=self.phase)
            saved = self.base.publish(self.output/'saved-insurance-receipt.json', dict(
                schema='robotron-owned-early-KL-insurance-v1', tag=self.spec['tag'], trainer=self.owner,
                source=frozen['source'], copy=frozen['verification_copy'], trigger=self.snapshot.raw_pin,
                completed_request=self.snapshot.transition['after']['archive'],
                no_trainer_actor_stop_or_recipe_source_change=True))
            context = copy.deepcopy(self.context)
            context['provenance'] = [self.source_pairs, self.unit_show, self.snapshot.raw_pin, saved,
                self.snapshot.transition['request']['archive'], self.snapshot.transition['after']['archive'],
                self.phase['record'], self.phase['boot_verification']]
            job = dict(schema='robotron-live8-maintenance-checkpoint-CPU-job-v1', mode='insurance',
                verifier_sha256=self.verifier['script']['sha256'], experiment=self.runtime.job['experiment'],
                source=frozen['source'], verification_copy=frozen['verification_copy'], clock_floor=self.snapshot.floor,
                source_control_context=context, output_directory=str(self.output/'cpu-output'),
                insurance=dict(tag=self.spec['tag'], trainer=self.owner, trigger_snapshot=self.snapshot.raw_pin,
                               completed_request=self.snapshot.completed))
            job_pin = self.base.publish(self.output/'CPU-root-job.json', job)
            execution_dir = self.output/'CPU-execution';execution_dir.mkdir(mode=0o700)
            proof = self.executor.run_once(self, job_pin, self.verifier, execution_dir)
            verifier = copy.deepcopy(self.verifier);verifier['context'] = context
            for key in ('successful_execution', 'successful_completion', 'successful_result'):
                verifier['python_binding'][key] = proof[key]
            # Frozen v4 validates all NEW actual retained-unit provenance and the
            # original exact interpreter symlink/library binding, without Torch.
            self.base.validate_python_binding(verifier, proof['insurance_report'], hash_executable=False)
            with self._lock:
                self._result = dict(status='PASS', insurance_report=proof['insurance_report'],
                    insurance_verification=proof['insurance_report'], saved_receipt=saved, insurance_receipt=saved,
                    verifier=verifier, frozen=frozen)
        except BaseException as error:
            failure = dict(status='FAILED', phase='freeze-or-first-CPU', error=repr(error), traceback=traceback.format_exc())
            try:
                self.base.publish(self.output/'early-insurance-failure.json', failure)
            except BaseException as reporting:
                failure['reporting_error'] = repr(reporting)
            with self._lock:
                self._result = failure
