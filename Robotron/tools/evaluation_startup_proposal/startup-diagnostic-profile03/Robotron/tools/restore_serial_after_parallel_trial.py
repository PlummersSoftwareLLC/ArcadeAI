#!/usr/bin/env python3
"""One guarded post-trial serial-source restoration; inspection is the default.

This deliberately does not run the experiment controller or load tensors. The
fresh insurance receipt must come from an independent CPU checkpoint verifier.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time

try:
    from . import parallel_state_fill_trial as trial
    from . import inference_worker_affinity as metrics
except ImportError:
    import parallel_state_fill_trial as trial
    import inference_worker_affinity as metrics

require = metrics.require
GAME = metrics.GAME
RUN = GAME / 'logs/managed-learning-20261015/run-26'
TRIAL = RUN / 'parallel-state-fill-live-20261016T2330Z'
APPLICATION = RUN / 'parallel-replay-production-application-20261016T2328Z'
TRAINER_UNIT = 'robotron-managed-run-26-d3b365c9-trainer.service'
FLEET_UNIT = 'robotron-managed-run-26-d3b365c9-fleet.service'
CONTROLLER_UNIT = 'robotron-parallel-state-fill-run26-20261016T2330Z.service'
CONTROLLER = (2968266, 28448605)
ARETURN = (3007387, 28546073)
MAIN_HASH = '306d64e050160f745cbafc0153f4301d93c94287cf36832131a8bfb36e60cd52'
SOURCE_PAIRS = (
    ('agent.py', 'before-agent.py',
     'c73878f53a37f5d151cfc7a4d1bed69517c9c4fb59a2ba1f1c9cc31670c0be64',
     '28977d6b925a4606a61b76438595f45ae054fc81aaaad989ab93e00d98a05668'),
    ('replay_buffer.py', 'before-replay_buffer.py',
     'e2b45eb6feb9a742d7a24ffad3044a8ee201aa60ddb73c9662117a72a9fb874f',
     '28556797d15e0acf9387030b87f9ccce0b18e1e3cfa629b63c2d7239a4206238'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_bytes(path, payload, mode):
    fd, name = tempfile.mkstemp(prefix='.serial-restore-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    finally:
        Path(name).unlink(missing_ok=True)


def save_status(directory, status):
    atomic_bytes(directory / 'status.json',
                 (json.dumps(status, indent=2, allow_nan=False) + '\n').encode(), 0o644)


def process_present(pid, ticks):
    try:
        return metrics.identity.stat_fields((Path('/proc') / str(pid) / 'stat').read_text())['starttime_ticks'] == ticks
    except FileNotFoundError:
        return False


def terminal_evidence(directory, host):
    """Bind the complete rejected experiment; an incomplete Areturn is refused."""
    require(directory.resolve() == TRIAL.resolve(), 'Unexpected trial directory')
    prebytes = (directory / 'precommit.json').read_bytes()
    statusbytes = (directory / 'status.json').read_bytes()
    pre, status = json.loads(prebytes), json.loads(statusbytes)
    require(status['precommit_sha256'] == sha(prebytes), 'Trial precommit mismatch')
    require(status['state'] == 'complete' and status['decision']['outcome'] == 'rejected',
            'A full rejected trial is required')
    recovery = status['recovery']
    require(not recovery['errors'] and not recovery['manual_recovery_required']
            and recovery['original_dropin_restored'] and not recovery['paused_actor_identity_issues'],
            'Trial recovery is not clean')
    require([r['phase'] for r in status['results']] == ['A', 'B', 'Areturn']
            and [r['phase'] for r in status['transitions']] == ['A', 'B', 'Areturn'],
            'All three phases must be complete and ordered')
    raw = (directory / 'observations.jsonl').read_bytes()
    require(raw.endswith(b'\n'), 'Trial observations have an incomplete final row')
    rows = [json.loads(line) for line in raw.splitlines()]
    require(rows and [key for key, _ in itertools.groupby(r['phase'] for r in rows)] == ['A', 'B', 'Areturn'],
            'Unexpected observation phases')
    for result, transition in zip(status['results'], status['transitions']):
        require(transition['state'] == 'ready' and result['operationally_valid']
                and result['duration_s'] >= 300, 'Incomplete or invalid phase')
        phase = [r for r in rows if r['phase'] == result['phase']]
        primary = [r for r in phase if r['stage'] == 'primary']
        require(primary and primary[0] == result['start'] and primary[-1] == result['end']
                and len(primary) == result['observations'], 'Phase endpoint/count mismatch')
        require(all(not r['issues'] and r['client_count'] == 192 for r in phase), 'Trial row has guard issues')
        require(primary[-1]['observed_monotonic_s'] - primary[0]['observed_monotonic_s'] == result['duration_s'],
                'Phase duration mismatch')
        require(all((r['stage'] == 'primary') ==
                    (r['observed_monotonic_s'] - transition['ready_monotonic_s'] >= pre['settle_s'])
                    for r in phase), 'Settling/primary boundary mismatch')
        delta = {k: primary[-1]['exposure']['optimizer']['total'][k] -
                    primary[0]['exposure']['optimizer']['total'][k] for k in result['optimizer_delta']}
        require(delta == result['optimizer_delta'] and delta['unavailable'] == 0, 'Optimizer result mismatch')
        rates = {'logical_samples_per_s': (primary[-1]['optimized_samples'] - primary[0]['optimized_samples']) / result['duration_s'],
                 'applied_admission_samples_per_s': delta['applied'] * 4096 / result['duration_s'],
                 'accepted_learner_per_s': (primary[-1]['exposure']['replay']['accepted_learner_total'] -
                                             primary[0]['exposure']['replay']['accepted_learner_total']) / result['duration_s']}
        require(all(rates[k] == result[k] for k in rates), 'Reported trial rates mismatch')
    a, b, ar = status['results']
    require(b['applied_admission_samples_per_s'] < 1.05 * max(a['applied_admission_samples_per_s'], ar['applied_admission_samples_per_s'])
            and status['decision']['automatic_promotion'] is False, 'Expected clean throughput rejection was not observed')
    require(not process_present(*CONTROLLER), 'Trial controller is still alive')
    unit = host.unit(CONTROLLER_UNIT)
    require(unit['ActiveState'] == 'inactive' and unit['MainPID'] == '0', 'Trial unit is not inactive')
    return pre, status, dict(precommit_sha256=sha(prebytes), status_sha256=sha(statusbytes),
                            observations_sha256=sha(raw), observations=len(rows))


def verified_insurance(checkpoint, verification, expected_sha, minimum):
    checkpoint, verification = checkpoint.resolve(strict=True), verification.resolve(strict=True)
    for path in (checkpoint, verification):
        require(path.is_file() and not (path.stat().st_mode & 0o222), 'Insurance files must be immutable')
    raw = verification.read_bytes()
    require(sha(raw) == expected_sha, 'Insurance verification receipt changed')
    receipt = json.loads(raw)
    before = checkpoint.stat()
    digest = metrics.file_digest(checkpoint)
    after = checkpoint.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Insurance changed while hashing')
    require(receipt['status'] == 'PASS' and Path(receipt['path']).resolve() == checkpoint
            and receipt['sha256'] == digest and receipt['bytes'] == before.st_size > 0,
            'CPU verification does not match insurance')
    require(receipt['cuda_initialized'] is False and receipt['visible_cuda_devices'] == 0,
            'Insurance was not verified without CUDA')
    require(receipt['finite']['tensors'] > 0 and receipt['finite']['tensor_elements'] > 0
            and receipt['adam_state_count'] == 81
            and math.isfinite(receipt['adam_step_min'])
            and receipt['adam_step_min'] == receipt['adam_step_max'] > 0,
            'Incomplete finite optimizer verification')
    scaler = receipt['grad_scaler']
    require(all(math.isfinite(scaler[k]) for k in ('scale', 'growth_factor', 'backoff_factor'))
            and scaler['scale'] > 0 and scaler['growth_factor'] > 1
            and 0 < scaler['backoff_factor'] < 1 and scaler['growth_interval'] > 0
            and scaler['_growth_tracker'] >= 0, 'Incomplete scaler verification')
    clocks = receipt['clocks']
    require(clocks['engine_version'] == 28 and clocks['state_size'] == 11128
            and clocks['frame_stack'] == 4, 'Insurance model architecture mismatch')
    require(all(type(clocks[k]) is int and clocks[k] >= minimum[k] for k in metrics.CLOCKS),
            'Insurance predates the final Areturn endpoint')
    require(clocks['epsilon'] == .1 and abs(clocks['expert_ratio'] - .1) < 1e-12,
            'Insurance recipe mismatch')
    return dict(path=str(checkpoint), sha256=digest, bytes=before.st_size,
                verification_path=str(verification), verification_sha256=expected_sha,
                clocks=clocks, scope='CPU-verified model-only insurance; replay remains live; never loaded by this tool')


def source_changes():
    changes = []
    for name, backup, expected, restored in SOURCE_PAIRS:
        path = GAME / 'Scripts/dqn' / name
        original, replacement = path.read_bytes(), (APPLICATION / backup).read_bytes()
        require(sha(original) == expected and sha(replacement) == restored, 'Source/backup does not match audited exact patch')
        changes.append(dict(path=str(path), before_sha256=expected, after_sha256=restored,
                            before=original.hex(), after=replacement.hex(), mode=stat.S_IMODE(path.stat().st_mode)))
    path = GAME / 'Scripts/dqn/main.py'
    original = path.read_bytes()
    old = b', no replay writes")'
    require(sha(original) == MAIN_HASH and original.count(old) == 1, 'Unexpected startup header source')
    replacement = original.replace(old, b', replay enabled")')
    changes.append(dict(path=str(path), before_sha256=MAIN_HASH, after_sha256=sha(replacement),
                        before=original.hex(), after=replacement.hex(), mode=stat.S_IMODE(path.stat().st_mode)))
    return changes


def health_plan(plan, row):
    return dict(plan, exposure_identity={k: metrics.exposure_key(row['exposure'][k]) for k in ('optimizer', 'replay')},
                initial_snapshot=row, batch_size=4096, replay_cap=8)


def prepare(host, args):
    require(not args.output_dir.exists(), 'Output directory must be new')
    require(args.output_dir.resolve().parent == RUN.resolve(), 'Cleanup output must be a new direct run-26 child')
    pre, final, evidence = terminal_evidence(args.trial_dir, host)
    current = host.describe()
    process = current['bindings']['worker']['trainer']
    require((process['pid'], process['starttime_ticks']) == ARETURN, 'Expected exact original Areturn trainer')
    host.adopt_initial(current)
    host.verify(dict(initial=pre['initial']), '0')
    require(current['bindings']['worker'] == final['transitions'][-1]['after']['bindings']['worker'],
            'Final Areturn worker identity changed')
    dropin = host.dropin_snapshot()
    require(dropin == pre['original_dropin'], 'Trial drop-in was not restored exactly')
    row = host.capture()
    checks = metrics.api_issues(row, health_plan({}, row))
    require(not checks and all(row['exposure'][k]['process_id'] == process['pid'] for k in ('optimizer', 'replay')),
            'Current trainer health/epoch guard failed: ' + repr(checks))
    insurance = verified_insurance(args.insurance_checkpoint, args.insurance_verification,
                                  args.insurance_verification_sha256, final['results'][-1]['end'])
    require(all(row[k] >= insurance['clocks'][k] for k in metrics.CLOCKS), 'Current training predates insurance')
    changes = source_changes()
    require(all(current['bindings']['source_hashes'][c['path']] == c['before_sha256'] for c in changes),
            'Staged source differs from live precommit bindings')
    return dict(schema='robotron-serial-source-restoration-v1', created_unix_s=time.time(),
                output_directory=str(args.output_dir.resolve()), trial_directory=str(args.trial_dir.resolve()),
                trial_evidence=evidence, initial=current, original_dropin=dropin, insurance=insurance,
                changes=changes, initial_snapshot=row,
                tool_hashes={str(Path(m.__file__).resolve()): metrics.file_digest(m.__file__)
                             for m in (sys.modules[__name__], metrics, trial)})


class SourceSet:
    """Lock and stage all three paths before stop; never start a partial set."""
    def __init__(self, plan, directory):
        self.changes, self.directory = plan['changes'], directory
        self.descriptors = []

    def __enter__(self):
        try:
            for index, change in enumerate(self.changes):
                path = Path(change['path'])
                require(not path.is_symlink(), 'Source path is a symlink')
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                self.descriptors.append(descriptor)
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                require(stat.S_IMODE(os.fstat(descriptor).st_mode) == change['mode'], 'Source permission changed')
                for role in ('before', 'after'):
                    data = bytes.fromhex(change[role])
                    require(sha(data) == change[role + '_sha256'], 'Staged bytes mismatch')
                    staged = self.directory / f'{index}-{role}-{path.name}'
                    with staged.open('xb') as stream:
                        stream.write(data);stream.flush();os.fchmod(stream.fileno(), 0o444);os.fsync(stream.fileno())
            sync_directory(self.directory)
            self.assert_group('before')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def assert_group(self, role):
        for change in self.changes:
            path = Path(change['path'])
            require(not path.is_symlink() and metrics.file_digest(path) == change[role + '_sha256']
                    and stat.S_IMODE(path.stat().st_mode) == change['mode'], 'Source set is not wholly ' + role)

    def install(self):
        self.assert_group('before')
        for change in self.changes:
            path = Path(change['path'])
            require(not path.is_symlink() and metrics.file_digest(path) == change['before_sha256'],
                    'Source changed immediately before replacement')
            atomic_bytes(Path(change['path']), bytes.fromhex(change['after']), change['mode'])
        self.assert_group('after')

    def restore_before(self):
        for change in self.changes:
            path = Path(change['path'])
            require(not path.is_symlink() and metrics.file_digest(path) in
                    (change['before_sha256'], change['after_sha256']), 'Unknown edit during source recovery')
        for change in self.changes:
            atomic_bytes(Path(change['path']), bytes.fromhex(change['before']), change['mode'])
        self.assert_group('before')

    def __exit__(self, *unused):
        for descriptor in reversed(self.descriptors):
            os.close(descriptor)
        self.descriptors = []


def assert_static(host, plan):
    for path, digest in plan['tool_hashes'].items():
        require(metrics.file_digest(path) == digest, 'Cleanup/helper source changed')
    _, _, evidence = terminal_evidence(Path(plan['trial_directory']), host)
    require(evidence == plan['trial_evidence'], 'Terminal experiment evidence changed')
    require(metrics.file_digest(plan['insurance']['path']) == plan['insurance']['sha256']
            and metrics.file_digest(plan['insurance']['verification_path']) == plan['insurance']['verification_sha256'],
            'Insurance changed after precommit')
    bindings = plan['initial']['bindings']
    files = {**bindings['source_hashes'], **bindings['control_hashes']}
    for unit in plan['initial']['unit_files'].values():
        files.update(unit)
    require(all(metrics.file_digest(path) == digest for path, digest in files.items()),
            'A bound source, control or service file changed before mutation')


def execute(host, plan):
    directory = Path(plan['output_directory'])
    host.verify(plan, '0')
    directory.mkdir(parents=True, exist_ok=False)
    # Byte payloads are already durably staged separately; keep precommit readable.
    public = copy.deepcopy(plan)
    for change in public['changes']:
        change.pop('before');change.pop('after')
    metrics.write_json(directory / 'precommit.json', public, immutable=True)
    sync_directory(directory)
    status = dict(state='preparing', manual_recovery_required=False, source_group='before', events=[])
    host.dropin_expected = trial.original_bytes(plan)
    with metrics.interrupt_handlers():
        try:
            with SourceSet(plan, directory) as sources:
                assert_static(host, plan);before = host.verify(plan, '0')
                host.metric_host.configure_logs(before['bindings']['logs'])
                host.begin_transition_logs(before['bindings']['logs'], before['trainer_stdout'])
                status['state'] = 'pausing';save_status(directory, status)
                host.pause(plan)
                status['state'] = 'stopping';save_status(directory, status)
                host.stop(before)
                status['old_imported_patched_trainer_absent'] = True
                assert_static(host, plan)
                status['state'] = 'restoring_sources';save_status(directory, status)
                host.no_sidecars();host.assert_retired_absent()
                require(host.unit(host.trainer_unit)['MainPID'] == '0', 'Unknown replacement appeared before source restoration')
                try:
                    sources.install()
                except BaseException:
                    with metrics.block_restore_signals():
                        try:
                            sources.restore_before();status['source_group'] = 'before_reconciled'
                        except BaseException as error:
                            status['source_group'] = 'mixed_or_unknown';status['source_reconciliation_error'] = str(error)
                    raise
                status['source_group'] = 'after'
                restored = copy.deepcopy(plan)
                for change in plan['changes']:
                    restored['initial']['bindings']['source_hashes'][change['path']] = change['after_sha256']
                status['expected_new_source_hashes'] = {c['path']: c['after_sha256'] for c in plan['changes']}
                sources.assert_group('after');host.assert_retired_absent()
                status['state'] = 'starting';save_status(directory, status)
                host.start()
                loaded = host.ready(restored, '0', actors=False)
                status['new_trainer'] = loaded['bindings']['worker']['trainer']
                require(status['new_trainer']['pid'] != ARETURN[0], 'Replacement trainer PID did not change')
                proof = host.bank_load_proof(loaded);status['bank_load_proof'] = proof
                with Path(proof['stdout']['path']).open('rb') as stream:
                    stream.seek(proof['start_byte']);payload = stream.read(proof['end_byte'] - proof['start_byte'])
                require(sha(payload) == proof['sha256'] and
                        b'Loaded model from: ' + str(GAME / 'models_dqn/robotron_dqn_latest.pt').encode() in payload,
                        'Owned startup did not confirm latest checkpoint load')
                status['events'].extend(host.transition_log_events())
                require(all(e['intentional_restart_compatible'] for e in status['events']), 'Unexpected transition fault')
                status['state'] = 'resuming';save_status(directory, status)
                host.resume()
                current = host.ready(restored, '0', actors=True)
                status['events'].extend(host.transition_log_events())
                require(all(e['intentional_restart_compatible'] for e in status['events']), 'Unexpected late transition fault')
                host.metric_host.configure_logs(current['bindings']['logs'])
                row = host.capture();local = health_plan(restored, row)
                for index in range(2):
                    if index:
                        host.sleep(2);previous = row;row = host.capture()
                    issues = metrics.api_issues(row, local, previous if index else None)
                    require(not issues, 'Post-restoration API guards: ' + repr(issues))
                    require(all(row['exposure'][k]['process_id'] == status['new_trainer']['pid'] for k in ('optimizer', 'replay')),
                            'API exposure belongs to another process')
                    require(all(row[k] >= plan['insurance']['clocks'][k] for k in metrics.CLOCKS), 'Saved learning clocks regressed')
                host.verify(restored, '0');sources.assert_group('after')
                status.update(state='complete', final_snapshot=row,
                              final_imported_sources='new owned trainer started after exact serial-source restoration')
        except BaseException as error:
            status.update(state='failed', error=str(error), manual_recovery_required=True)
        finally:
            with metrics.block_restore_signals():
                try:
                    status['events'].extend(host.transition_log_events())
                    if any(not e['intentional_restart_compatible'] for e in status['events']):
                        status.update(state='failed', manual_recovery_required=True)
                except BaseException as error:
                    status['final_log_error'] = str(error);status.update(state='failed', manual_recovery_required=True)
                try:
                    host.resume()
                except BaseException as error:
                    status['actor_resume_error'] = str(error);status.update(state='failed', manual_recovery_required=True)
                status['paused_actor_identity_issues'] = host.pause_issues
                status['no_automatic_failure_restart'] = True
                save_status(directory, status)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial-dir', type=Path, default=TRIAL)
    parser.add_argument('--insurance-checkpoint', type=Path, required=True)
    parser.add_argument('--insurance-verification', type=Path, required=True)
    parser.add_argument('--insurance-verification-sha256', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args(argv)
    try:
        host = trial.LiveHost(TRAINER_UNIT, FLEET_UNIT)
        plan = prepare(host, args)
        if args.launch:
            result = execute(host, plan)
        else:
            result = copy.deepcopy(plan)
            for change in result['changes']:
                change.pop('before');change.pop('after')
            result['dry_run'] = True
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result.get('state', 'complete') == 'complete' else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('Serial restoration refused: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
