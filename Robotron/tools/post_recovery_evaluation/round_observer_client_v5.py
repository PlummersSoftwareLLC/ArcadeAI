"""Native evaluator interface for one independently scoped round observer.

No original observer can be restarted, adopted or replaced. Cleanup only targets
the recorded invocation after its worker has exited and its evidence is sealed.
"""
import os
from pathlib import Path
import secrets
import subprocess
import time


class DedicatedMainHealth:
    def __init__(self, job, jp, protocol, family, h, *, started, deadline, prior_groups):
        self.h, self.native, self.native_pin = h, job, jp
        self.started, self.deadline = started, deadline
        self.child = None
        self.scope_complete = False
        self.lifecycle = None
        self.initial = None
        self.worker_owner = None
        self.finished = False
        self.last_live = None
        self.sources = family['main_observer']
        h.checked(self.sources['client'])
        self.common = h.load('_native_round_observer_protocol', h.checked(self.sources['worker']))
        c = self.common
        c.require(self.sources['client'] == h.pin(__file__), 'Actual round client source differs')
        c.require(protocol['schema'] == 'robotron-native-round-main-health-protocol-v5'
                  and protocol['case'] == job['main_binding'] and prior_groups == []
                  and protocol['raw_API_required'] is True and protocol['close_requires_final_sample'] is True
                  and protocol['hot_max_gap_s'] == .5 and protocol['initial_samples'] == 100,
                  'Fresh original round-health protocol required')
        for value in self.sources.values():
            h.checked(value)
        self.root = Path(job['output']) / 'main-health-scope'
        self.root.mkdir(mode=0o700)
        self.output = Path(job['output']) / 'main-observations'
        self.parent = c.owner()
        self.parent['argv'] = [part.decode() for part in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]]
        nonce = secrets.token_hex(16)
        self.unit = 'robotron-round-health-' + nonce + '.service'
        c.require(c.show(self.unit)['LoadState'] == 'not-found', 'Original observer unit already exists')
        self.job = dict(schema=c.SCHEMA, attempt=1, no_retry=True, nonce=nonce,
            unit=self.unit, output=str(self.output), parent=self.parent,
            native_job=jp, native_runtime=job['runtime'], case=job['main_binding'],
            sources=self.sources, interval_s=.2, initial_samples=100, maximum_gap_s=.5,
            work_s=4200, runtime_s=4260, deadline_monotonic_s=deadline)
        self.jobpin = h.put(self.root / 'job.json', self.job)
        self.owner_pin = None

    def start(self):
        c = self.common
        c.require(self.child is None and not self.finished, 'Original observer launch is single-use')
        interpreter = self.sources['interpreter']['path']
        command = ['systemd-run', '--user', '--unit=' + self.unit,
            '-p', 'CPUQuota=200%', '-p', 'MemoryMax=4G', '-p', 'MemorySwapMax=0',
            '-p', 'TasksMax=128', '-p', 'RuntimeMaxSec=4260', '-p', 'Restart=no',
            '-p', 'RemainAfterExit=yes', '-p', 'TimeoutStopSec=5', '-p', 'SendSIGKILL=no',
            '/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1', interpreter, '-I', '-B', self.sources['worker']['path'],
            '--execute', '--job', self.jobpin['path'], '--job-sha256', self.jobpin['sha256']]
        self.command = command
        with (self.root / 'launcher-console.log').open('xb') as log:
            self.child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            self.launcher_birth = c.birth(self.child.pid)
            c.require(self.launcher_birth is not None, 'Original launcher birth unavailable')
            self.launcher_pin = self.h.put(self.root / 'original-launcher.json',
                dict(pid=self.child.pid, birth=self.launcher_birth, argv=command))
            code = self.child.wait(timeout=10)
        c.require(code == 0, 'Original observer launch failed; no retry')
        fields = c.show(self.unit)
        c.require(fields['ActiveState'] == 'active' and fields['SubState'] == 'running'
                  and fields['NRestarts'] == '0', 'Original observer is not running')
        pid = int(fields['MainPID'])
        self.worker_owner = dict(pid=pid, birth=c.birth(pid), unit=self.unit,
            invocation_id=fields['InvocationID'], cgroup=fields['ControlGroup'], uid=os.getuid())
        c.require(self.worker_owner['birth'] is not None, 'Original worker birth unavailable')
        self.owner_pin = self.h.put(self.root / 'original-unit.json', dict(
            owner=self.worker_owner, raw_properties=fields, argv=command))
        limit = min(self.deadline, time.monotonic() + 30)
        while time.monotonic() < limit:
            c.require(c.birth(pid) == self.worker_owner['birth'], 'Original worker ended before readiness')
            path = self.output / 'live.json'
            if path.exists():
                value = self._accept(c.read(path, limit=128 << 10))
                if self.initial is not None:
                    return value
            time.sleep(.1)
        raise ValueError('Original observer did not close its100-sample readiness proof')

    def _accept(self, value):
        c = self.common
        c.require(value['schema'] == 'robotron-round-observer-live-v1'
                  and value['job'] == self.jobpin and value['nonce'] == self.job['nonce']
                  and value['owner'] == self.worker_owner and value['state'] == 'running',
                  'Original observer live identity differs')
        c.require(c.birth(self.worker_owner['pid']) == self.worker_owner['birth']
                  and 0 <= time.monotonic() - value['updated_monotonic_s'] <= .5,
                  'Original observer stopped or publication expired')
        if self.last_live is not None:
            c.require(value['observed_samples'] >= self.last_live['observed_samples'], 'Original observer publication regressed')
        self.last_live = value
        self.initial = value['initial']
        return dict(phase=value['phase'], sample=value['latest_sample'],
                    observed_samples=value['observed_samples'], initial=self.initial)

    def observe(self):
        self.common.require(not self.finished and self.worker_owner is not None, 'Original observer is terminal or unstarted')
        return self._accept(self.common.read(self.output / 'live.json', limit=128 << 10))

    def finish(self, *, case_already_failed):
        c = self.common
        c.require(not self.finished, 'Original observer finalization is single-use')
        self.finished = True
        result = dict(report=None, failure=None, errors=[], writer_stopped=False,
                      scope_complete=False, statuses=[])
        if self.worker_owner is None:
            result['errors'].append('Original worker identity was not captured; no scope release inferred')
            return result
        request_path = self.output / 'finish-request.json'
        if c.birth(self.worker_owner['pid']) == self.worker_owner['birth']:
            c.write(request_path, dict(job=self.jobpin, nonce=self.job['nonce'], parent=self.parent,
                action='abort' if case_already_failed else 'close', created_monotonic_s=time.monotonic()))
        limit = time.monotonic() + 35
        while c.birth(self.worker_owner['pid']) == self.worker_owner['birth'] and time.monotonic() < limit:
            time.sleep(.1)
        fields = c.show(self.unit)
        c.require(fields['InvocationID'] == self.worker_owner['invocation_id']
                  and fields['ExecMainPID'] == str(self.worker_owner['pid'])
                  and fields['NRestarts'] == '0', 'Original worker invocation changed')
        c.require(fields['MainPID'] == '0' and c.birth(self.worker_owner['pid']) != self.worker_owner['birth'],
                  'Original worker completion unknown; no release')
        expected = dict(CPUQuotaPerSecUSec='2s', MemoryMax=str(4 << 30), MemorySwapMax='0',
            TasksMax='128', RuntimeMaxUSec='1h 11min', Restart='no', TimeoutStopUSec='5s', SendSIGKILL='no')
        c.require(all(fields[key] == value for key, value in expected.items()), 'Original observer resources differ')
        outcome_pin = self.h.pin(self.output / 'outcome.json')
        outcome = c.read(c.checked(outcome_pin))
        c.require(outcome['job'] == self.jobpin and outcome['nonce'] == self.job['nonce']
                  and c.read(c.checked(outcome['owner'])) == self.worker_owner
                  and outcome['parent'] == self.parent, 'Original observer outcome identity differs')
        success = (not case_already_failed and outcome['success'] is True and outcome['error'] is None
                   and outcome['signals_received'] == [] and fields['ExecMainCode'] == '1'
                   and fields['ExecMainStatus'] == '0' and fields['Result'] == 'success')
        if success:
            request = c.read(c.checked(outcome['finish_request']))
            final = c.read(c.checked(outcome['samples'][-1]))['snapshot']
            c.require(outcome['final_snapshot_after_finish_request'] is True
                      and final['monotonic_s'] >= outcome['finish_observed_monotonic_s']
                      >= request['created_monotonic_s'], 'Fresh final main proof is missing')
        closure = self.h.put(self.root / 'original-worker-terminal-properties.json', fields)
        stopped = subprocess.run(['systemctl', '--user', 'stop', self.unit], capture_output=True, text=True, timeout=10)
        c.require(stopped.returncode == 0, 'Original exited worker scope could not be released')
        after = c.show(self.unit)
        c.require(after['MainPID'] == '0' and after['ActiveState'] == 'inactive'
                  and not Path('/sys/fs/cgroup' + self.worker_owner['cgroup']).exists(),
                  'Original observer scope remains')
        self.scope_complete = True
        result.update(scope_complete=True, writer_stopped=outcome['all_writer_threads_stopped'])
        report = self.h.put(self.root / ('closed-report.json' if success else 'failure-report.json'),
            dict(schema='robotron-round-observer-closed-report-v1', outcome=outcome_pin,
                 job=self.jobpin, actual_status=outcome['samples'], success=success))
        result['report' if success else 'failure'] = report
        result['statuses'] = outcome['samples']
        if not success:
            result['errors'].append('Original observer failed; original outcome retained')
        self.lifecycle = self.h.put(self.root / 'native-observer-lifecycle.json', dict(
            schema='robotron-round-observer-native-lifecycle-v1', native_job=self.native_pin,
            worker_job=self.jobpin, owner=self.owner_pin, terminal_properties=closure, launcher=self.launcher_pin,
            outcome=outcome_pin, released_properties=after, launcher_exit=self.child.returncode,
            launcher_birth_absent=c.birth(self.child.pid) != self.launcher_birth,
            all_original_processes_reaped=True, original_scope_released=True, success=success,
            native_started_monotonic_s=self.started, native_deadline_monotonic_s=self.deadline,
            quality_qualified=False))
        return result
