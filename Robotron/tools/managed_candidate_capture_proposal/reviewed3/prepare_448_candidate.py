#!/usr/bin/env python3
"""Root-only candidate preparation; literal PLAN until explicit --execute.

Archives the retained original watcher, then makes an independent CPU input
and exact verifier job. No save request, service action, model import or load.
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import traceback
import urllib.request

REPO = Path('/home/dave/source/repos/ArcadeAI')
GAME = REPO/'Robotron'
RUN = GAME/'logs/managed-learning-20261015/run-26'
MODEL = GAME/'models_dqn'
PRETRIGGER = RUN/'fresh3-448M-root-live-capture-binding-20261017/pretrigger-root-live-binding.json'
PRETRIGGER_SHA = '8d8c94ff1696f86b643a591e233016dd21642f0c0995738fac9e9f0c3c083084'
CONTEXT_JOB = RUN/'live8-owned-maintenance-reviewed4-20261017/initial-stopped/cpu-job.json'
CONTEXT_SHA = 'a7f689e23923b63693f2aacd43db4efd2157700be1836502ed8a14dac031544b'
VERIFIER = RUN/'managed-candidate-checkpoint-CPU-verifier-proposal-20261017/verify_candidate_checkpoint.py'
VERIFIER_SHA = 'ea6ccfcd62e2683641475634ba1647856a988691a6cede3dbeda629dd03ba56b'
BASE_VERIFIER_SHA = '7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
HELPER_SHA = '5d8d7ab2456f2d6a8ad89327596cec654feae9a66db98190a07c87063a3be2b1'
TAG = 'fresh3-448M'
TARGET = 452629023
EXPERIMENT = 'best10M-fresh3-eps10-cap8-nosmooth'
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
UNIT = 'robotron-checkpoint-448M-run26-post-route1-20261017.service'
WATCHER = dict(pid=64907, starttime_ticks=31871087, unit=UNIT,
    invocation_id='7a0c4af840184de4bd8ffe479eb4c4bf',
    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+UNIT)
TRAINER = dict(pid=4140916, starttime_ticks=31570251,
    unit='robotron-managed-run-26-d3b365c9-trainer.service',
    invocation_id='cf4f26d3c5b84d9ab1302ded3a073519',
    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-managed-run-26-d3b365c9-trainer.service')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(value):
    # Reads may change atime. Every other ownership/content identity is bound.
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
        mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
        mode=oct(stat.S_IMODE(value.st_mode)), uid=value.st_uid, nlink=value.st_nlink)


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Noncanonical path: '+str(path))
    return path


def pin(path, maximum=4 << 20, minimum=1):
    path = canonical(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and minimum <= before.st_size <= maximum, 'Unexpected regular-file bounds/owner: '+str(path))
        observed = identity(before)
        require(identity(path.lstat()) == observed, 'Path/FD race before read')
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(identity(os.fstat(stream.fileno())) == observed and identity(path.lstat()) == observed,
                'File changed during read: '+str(path))
    return dict(path=str(path), sha256=digest, bytes=before.st_size, identity=observed)


def read_json(path, expected_sha=None):
    before = pin(path)
    require(expected_sha is None or before['sha256'] == expected_sha, 'Pinned JSON changed: '+str(path))
    value = json.loads(Path(path).read_text())
    require(pin(path) == before, 'JSON changed during parse')
    return value, before


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bytes(path, data, *, allow_empty_archive=False):
    with Path(path).open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    sync_directory(Path(path).parent)
    return pin(path, minimum=0 if allow_empty_archive else 1)


def write_json(path, value):
    return write_bytes(path, (json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


def command(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    require(result.returncode == 0, 'Read-only command failed: '+repr(argv)+' '+result.stderr)
    return result.stdout


def fields(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def proc_start(pid):
    return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])


def trainer_now():
    text = command(['systemctl', '--user', 'show', TRAINER['unit']])
    value = fields(text)
    require(value['MainPID'] == str(TRAINER['pid']) and value['InvocationID'] == TRAINER['invocation_id']
            and value['ControlGroup'] == TRAINER['cgroup'] and value['ActiveState'] == 'active'
            and value['SubState'] == 'running' and proc_start(TRAINER['pid']) == TRAINER['starttime_ticks'],
            'Trainer identity changed; no replacement adoption')
    cgroup = [line.split(':', 2)[2] for line in Path('/proc', str(TRAINER['pid']), 'cgroup').read_text().splitlines()
              if line.startswith('0::')]
    require(cgroup == [TRAINER['cgroup']], 'Trainer cgroup differs')
    return dict(TRAINER), text


def terminal_watcher():
    text = command(['systemctl', '--user', 'show', UNIT, '--all'])
    value = fields(text)
    require(value.get('InvocationID') == WATCHER['invocation_id']
            and value.get('ExecMainPID') == str(WATCHER['pid'])
            and value.get('NRestarts') == '0', 'Original retained watcher identity unavailable/different')
    if value.get('MainPID') != '0' or value.get('SubState') not in ('exited', 'dead', 'failed'):
        require(value.get('ControlGroup') == WATCHER['cgroup'], 'Running watcher cgroup differs')
        return None, None  # WAIT, no output or candidate read.
    require(value['ExecMainCode'] == '1' and value['ExecMainStatus'] == '0' and value['Result'] == 'success',
            'Original watcher did not exit0; preserve failure for root, never fabricate candidate success')
    # systemd may clear ControlGroup after the exact original process exits.
    # The pretrigger-owned cgroup remains authoritative for absence checks;
    # a different nonempty cgroup never becomes an eligible owner.
    require(value.get('ControlGroup') in (WATCHER['cgroup'], ''), 'Terminal watcher cgroup differs')
    try:
        require(proc_start(WATCHER['pid']) != WATCHER['starttime_ticks'], 'Original watcher still exists')
    except (FileNotFoundError, ProcessLookupError):
        pass
    group = Path('/sys/fs/cgroup')/WATCHER['cgroup'].lstrip('/')
    if group.exists():
        require(not (group/'cgroup.procs').read_text().split(), 'Original watcher cgroup is not empty')
    return value, text


def terminal_identity(value):
    # Full original show is archived, but volatile cgroup memory/accounting
    # counters are not service identity and may still change after process exit.
    return {name: value[name] for name in ('MainPID', 'ExecMainPID', 'InvocationID',
        'ControlGroup', 'ActiveState', 'SubState', 'NRestarts', 'ExecMainCode', 'ExecMainStatus', 'Result')}


def check_api(value, floor=None):
    require(value['client_count'] == 192 and value['training_enabled'] is True
            and value['measurement_active'] is False and value['managed_experiment'] == EXPERIMENT,
            'Held branch/192-client state differs')
    require(value['host_pipeline']['learning_exposure']['optimizer']['process_id'] == TRAINER['pid']
            and value['lr'] == 2.5e-5 and all(math.isfinite(value[name]) for name in ('loss', 'grad_norm', 'lr')),
            'API owner/learning recipe differs')
    for name in CLOCKS:
        require(type(value[name]) is int and value[name] > 0
                and (floor is None or value[name] >= floor[name]), 'API four-clock floor differs: '+name)


def independent_copy(source, destination):
    """Never chmod/link/modify source: tagged saves may alias live model files."""
    source = canonical(source)
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno()); observed = identity(before)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and 200 << 20 <= before.st_size <= 400 << 20 and identity(source.lstat()) == observed,
                'Candidate source bounds/owner/identity differ')
        digest = hashlib.sha256()
        with Path(destination).open('xb') as output:
            for chunk in iter(lambda: stream.read(4 << 20), b''):
                digest.update(chunk); output.write(chunk)
            output.flush(); os.fsync(output.fileno()); os.fchmod(output.fileno(), 0o444); os.fsync(output.fileno())
        require(identity(os.fstat(stream.fileno())) == observed and identity(source.lstat()) == observed,
                'Candidate source changed during independent copy')
    sync_directory(Path(destination).parent)
    original = dict(path=str(source), sha256=digest.hexdigest(), bytes=before.st_size, identity=observed)
    copied = pin(destination, maximum=400 << 20)
    require(copied['sha256'] == original['sha256'] and copied['bytes'] == original['bytes']
            and (copied['identity']['device'], copied['identity']['inode']) != (observed['device'], observed['inode'])
            and copied['identity']['nlink'] == 1 and copied['identity']['mode'] == '0o444',
            'CPU copy is not independent, single-link0444, byte-identical')
    return original, copied


def prepare(directory):
    directory = canonical(directory)
    require(directory.is_relative_to(RUN) and directory != RUN and not directory.exists()
            and directory.parent.is_dir(), 'Preparation directory must be NEW under run26')
    binding, binding_pin = read_json(PRETRIGGER, PRETRIGGER_SHA)
    context_job, context_pin = read_json(CONTEXT_JOB, CONTEXT_SHA)
    require(binding['schema'] == 'robotron-owned-candidate-pretrigger-live-binding-v1'
            and binding['trainer'] == TRAINER and binding['gate_unit'] == WATCHER
            and binding['gate']['tag'] == TAG and binding['gate']['target_learner_frames'] == TARGET
            and binding['gate']['original_deadline_unix_s'] == 1792245505.2003896,
            'Pretrigger owner/target/deadline binding differs')
    pre_api, _ = read_json(binding['current_api']['path'], binding['current_api']['sha256'])
    check_api(pre_api)
    require(pre_api['learner_frame_count'] < TARGET, 'Authoritative before observation was not pretrigger')
    require(pin(VERIFIER)['sha256'] == VERIFIER_SHA, 'CPU wrapper source changed')
    require(pin(GAME/'tools/checkpoint_at_frame.py')['sha256'] == HELPER_SHA, 'Checkpoint helper source changed')
    terminal, terminal_text = terminal_watcher()
    if terminal is None:
        return dict(status='WAIT_ORIGINAL_WATCHER_STILL_RUNNING', outputs_created=False)
    before_owner, trainer_text = trainer_now()
    gate_path = Path(binding['gate']['output'])
    gate, gate_pin = read_json(gate_path)
    source = MODEL/'managed-checkpoints'/(TAG+'.pt')
    require(set(gate) == {'tag', 'target', 'experiment', 'checkpoint', 'trigger_snapshot', 'saved_utc'}
            and gate['tag'] == TAG and gate['target'] == TARGET and gate['experiment'] == EXPERIMENT
            and gate['checkpoint'] == str(source), 'Authentic completed gate differs')
    trigger = gate['trigger_snapshot']
    require(set(trigger) == set(CLOCKS)|{'client_count'} and trigger['client_count'] == 192
            and trigger['learner_frame_count'] >= TARGET, 'Gate triggered early or without192')
    require(all(type(trigger[name]) is int and trigger[name] >= pre_api[name] for name in CLOCKS),
            'Authentic gate four-clock floor predates the pretrigger proof')
    completed_path = MODEL/'managed_save.request.json.completed'
    completed, completed_pin = read_json(completed_path)
    require(completed == {'tag': TAG} and not (MODEL/'managed_save.request.json').exists(),
            'Actual completed slot changed or another save pending')
    context = copy.deepcopy(context_job['source_control_context'])
    require(context['game_root'] == str(GAME) and context['model_dir'] == str(MODEL), 'Context roots differ')
    for name, item in context['model_package'].items():
        require(item['path'] == str(GAME/'Scripts/dqn'/name) and pin(item['path']) == item,
                'Model source context changed: '+name)
    for item in context['provenance']:
        require(pin(item['path']) == item, 'Historical provenance changed')
    control_path = MODEL/'learning_control.json'
    control, control_pin = read_json(control_path, context['archived_control']['sha256'])
    require(control['experiment'] == EXPERIMENT and control['lr_scale'] == .5
            and control['epsilon_ramp']['start'] == control['epsilon_ramp']['end'] == .1,
            'Current control branch/recipe differs')
    directory.mkdir(mode=0o700)
    archive = {}
    for name, data in (
            ('original-watcher-show.txt', terminal_text.encode()),
            ('original-watcher-cat.txt', command(['systemctl', '--user', 'cat', UNIT]).encode()),
            ('original-watcher-journal.txt', command(['journalctl', '--user', '_SYSTEMD_INVOCATION_ID='+WATCHER['invocation_id'], '--no-pager', '-o', 'short-precise']).encode()),
            ('trainer-before-show.txt', trainer_text.encode()),
            ('archived-current-trainer-unit.txt', command(['systemctl', '--user', 'cat', TRAINER['unit']]).encode())):
        archive[name] = write_bytes(directory/name, data, allow_empty_archive=name=='original-watcher-journal.txt')
    archived_control = write_bytes(directory/'archived-current-learning-control.json', control_path.read_bytes())
    require(pin(control_path) == control_pin and archived_control['sha256'] == control_pin['sha256'], 'Current control changed while archived')
    archive['matching-gate.json'] = write_bytes(directory/'matching-gate.json', gate_path.read_bytes())
    archive['matching-completed-request.json'] = write_bytes(directory/'matching-completed-request.json', completed_path.read_bytes())
    require(pin(gate_path) == gate_pin and pin(completed_path) == completed_pin, 'Gate/completed slot changed during archival')
    repeat, _ = terminal_watcher()
    require(repeat is not None and terminal_identity(repeat) == terminal_identity(terminal),
            'Original terminal identity changed while archived')
    terminal_pin = write_json(directory/'original-terminal-archive.json', dict(
        schema='robotron-owned-candidate-original-terminal-archive-v1', gate_unit=WATCHER,
        original_exec_code=1, original_exit=0, original_result='success',
        original_terminal_archived_before_release=True, service_retained_no_release_by_preparer=True,
        files=archive, pretrigger=binding_pin, current_control=archived_control,
        source_preparer=pin(Path(__file__).resolve())))
    original, copied = independent_copy(source, directory/'verification-copy.pt')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as stream:
        after_api = json.load(stream)
    check_api(after_api, trigger)
    after_owner, after_trainer_text = trainer_now()
    require(after_owner == before_owner == binding['trainer'], 'Trainer changed during candidate preparation')
    after_api_pin = write_json(directory/'current-after-capture-api.json', after_api)
    after_trainer_pin = write_bytes(directory/'trainer-after-show.txt', after_trainer_text.encode())
    require(pin(gate_path) == gate_pin and pin(completed_path) == completed_pin
            and not (MODEL/'managed_save.request.json').exists()
            and identity(source.lstat()) == original['identity'], 'Capture inputs/request changed after preparation')
    capture_pin = write_json(directory/'capture-execution.json', dict(
        schema='robotron-owned-candidate-capture-execution-v1', trainer_before=binding['trainer'],
        trainer_after=after_owner, experiment=EXPERIMENT, model_dir=str(MODEL), tag=TAG,
        target_learner_frames=TARGET, gate_path=str(gate_path), gate_sha256=gate_pin['sha256'],
        checkpoint_path=str(source), checkpoint_sha256=original['sha256'], checkpoint_bytes=original['bytes'],
        gate_unit=WATCHER, original_exec_code=1, original_exit=0, original_result='success',
        original_terminal_archived_before_release=True, terminal_archive=terminal_pin))
    context['archived_control'] = archived_control
    context['archived_trainer_unit'] = archive['archived-current-trainer-unit.txt']
    context['provenance'] += [context_pin, binding_pin, terminal_pin, after_api_pin, after_trainer_pin,
                              archive['matching-gate.json'], archive['matching-completed-request.json']]
    require(len(context['provenance']) <= 52, 'Context provenance budget exceeded')
    job = dict(schema='robotron-managed-candidate-checkpoint-CPU-job-v1', verifier_sha256=VERIFIER_SHA,
        base_verifier_sha256=BASE_VERIFIER_SHA, experiment=EXPERIMENT, source=original, verification_copy=copied,
        source_control_context=context, output_directory=str(directory/'cpu-output'),
        candidate=dict(tag=TAG, target_learner_frames=TARGET, gate=gate_pin,
                       completed_request=completed_pin, capture_execution=capture_pin))
    job_pin = write_json(directory/'root-job.json', job)
    result = dict(status='PREPARED_NOT_CPU_VERIFIED', job=job_pin, verification_copy=copied,
        original_terminal_archive=terminal_pin, capture_execution=capture_pin,
        original_watcher_unit_retained=True, no_source_chmod_or_hardlink=True,
        limitations='Historical context remains provenance only; fresh capture owns trainer continuity. No tensor loads, CPU verification, quality, publication or unit release by this preparer.')
    write_json(directory/'preparation-result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: wait for exact retained original448 terminal0; archive and independent copy/job only; no reads, queries, outputs or CPU import')
        return 0
    require(args.directory is not None, 'Explicit root-owned NEW directory required')
    result = prepare(args.directory)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
