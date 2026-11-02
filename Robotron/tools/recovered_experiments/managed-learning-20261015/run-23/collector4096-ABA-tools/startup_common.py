"""Dependency-light shared checks. Import performs no I/O or runtime inspection."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

HERE = Path(__file__).parent
BASELINE_SHA = '9538b27a07b493be7bb607a595eb61c38bff170a30852f3f3c983d09b3c39653'

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def valid_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

def small_raw(path, expected=None):
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and path.stat().st_size < 3_000_000,
            'Need a bounded nonsymlink evidence file: ' + str(path))
    raw = path.read_bytes()
    require(expected is None or valid_sha(expected) and digest(raw) == expected,
            'Changed small evidence: ' + str(path))
    return raw

def doc(path, expected=None):
    return json.loads(small_raw(path, expected))

def baseline():
    value = doc(HERE / 'baseline-contract.json', BASELINE_SHA)
    require(len(value['source20']) == 20 and len(value['private12']) == 12,
            'Incomplete pinned source inventory')
    for row in value['pins'].values():
        small_raw(row['path'], row['sha256'])
    control = doc(value['control']['path'], value['control']['sha256'])
    require(control == value['control']['snapshot'], 'Learning controls changed')
    return value

def arguments(description, *, observe=False):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--execute', action='store_true', help='Explicitly inspect the real run; default is inert plan only')
    parser.add_argument('--run-dir')
    parser.add_argument('--prior-run')
    parser.add_argument('--trainer-pid', type=int)
    parser.add_argument('--expected-wait', choices=['.5', '0.5', '1', '1.0'])
    parser.add_argument('--resume-manifest-sha256', help='Root-pinned final-resume-checkpoint.json SHA')
    if observe:
        parser.add_argument('--cpu-report-sha256', help='SHA from this run\'s completed CPU audit')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'mode': 'PLAN_ONLY_NO_RUNTIME_READS', 'execute': False,
                          'required': ['run-dir', 'prior-run', 'trainer-pid', 'expected-wait',
                                       'resume-manifest-sha256'] + (['cpu-report-sha256'] if observe else []),
                          'scope': description}))
        return None
    for key in ('run_dir', 'prior_run', 'trainer_pid', 'expected_wait', 'resume_manifest_sha256'):
        require(getattr(args, key) is not None, 'Missing --' + key.replace('_', '-'))
    require(args.trainer_pid > 0 and valid_sha(args.resume_manifest_sha256), 'Bad PID or manifest SHA')
    if observe:
        require(valid_sha(args.cpu_report_sha256), 'Need explicit CPU report SHA')
    args.expected_wait = float(args.expected_wait)
    return args

def run_paths(args, contract):
    run, prior, campaign = Path(args.run_dir).resolve(), Path(args.prior_run).resolve(), Path(contract['campaign'])
    require(run != prior and run.parent == prior.parent == campaign
            and re.fullmatch(r'run-\d+', run.name) and re.fullmatch(r'run-\d+', prior.name)
            and run.is_dir() and prior.is_dir(), 'Need existing distinct campaign run directories')
    return run, prior, Path(contract['game']), Path(contract['repository'])

def selected_environment(env):
    return {key: value for key, value in env.items()
            if key.startswith(('ROBOTRON_', 'DQN_')) or key == 'CUDA_VISIBLE_DEVICES'}

def delta(before, after):
    return {key: [before.get(key), after.get(key)] for key in before.keys() | after.keys()
            if before.get(key) != after.get(key)}

def check_environment(env, expected_file, prior_env, contract, run, wait):
    selected = selected_environment(env)
    require(selected == expected_file and env.get('LD_PRELOAD') is None, 'Actual/recorded environment differs or trainer preloaded')
    normalized = dict(selected)
    normalized['ROBOTRON_RUN_DIR'] = contract['environment']['ROBOTRON_RUN_DIR']
    require(float(normalized['DQN_INFERENCE_BATCH_WAIT_MS']) == wait, 'Actual collector wait differs')
    normalized['DQN_INFERENCE_BATCH_WAIT_MS'] = contract['environment']['DQN_INFERENCE_BATCH_WAIT_MS']
    require(normalized == contract['environment'] and selected['ROBOTRON_RUN_DIR'] == str(run),
            'Other recipe/environment change')
    prior_normal = dict(prior_env)
    prior_normal['ROBOTRON_RUN_DIR'] = contract['environment']['ROBOTRON_RUN_DIR']
    require(float(prior_normal['DQN_INFERENCE_BATCH_WAIT_MS']) in (.5, 1), 'Bad prior wait')
    prior_normal['DQN_INFERENCE_BATCH_WAIT_MS'] = contract['environment']['DQN_INFERENCE_BATCH_WAIT_MS']
    require(prior_normal == contract['environment'], 'Prior recipe differs from pinned run23')
    changes = delta(prior_env, selected)
    require('ROBOTRON_RUN_DIR' in changes and set(changes) <= {'ROBOTRON_RUN_DIR', 'DQN_INFERENCE_BATCH_WAIT_MS'},
            'Environment delta exceeds run path + collector')
    return selected, changes

def check_config(current, prior, contract, wait):
    normalized = dict(current)
    expected = dict(contract['config'])
    if 'inference_batch_wait_ms' in current:
        require(current['inference_batch_wait_ms'] == wait, 'Recorded config collector wait differs')
    # Older schemas can omit this one field. The actual environment remains mandatory.
    normalized.pop('inference_batch_wait_ms', None)
    expected.pop('inference_batch_wait_ms', None)
    prior_normal = dict(prior)
    prior_normal.pop('inference_batch_wait_ms', None)
    require(normalized == prior_normal == expected, 'Unexpected config change')
    return delta(prior, current)

def check_sources(contract):
    source = {name: digest(small_raw(Path(contract['repository']) / name)) for name in contract['source20']}
    private = {name: digest(small_raw(Path(contract['game']) / name)) for name in contract['private12']}
    require(source == contract['source20'] and private == contract['private12'], 'Source20/private12 changed')
    return source, private

def identity(path):
    path = Path(path)
    require(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode), 'Need regular nonsymlink file')
    s = path.stat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns, mode=stat.S_IMODE(s.st_mode), nlink=s.st_nlink)

def process(pid):
    path = Path('/proc') / str(pid)
    parts = path.joinpath('stat').read_text().rsplit(')', 1)[1].split()
    require(parts[0] != 'Z', 'Trainer is a zombie')
    return dict(pid=pid, start_ticks=int(parts[19]), ppid=int(parts[1]))

def outcome_checks(exposure, pid):
    opt, replay = exposure['optimizer'], exposure['replay']
    expected = {'attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable'}
    require(opt['enabled'] and replay['enabled'] and opt['process_id'] == replay['process_id'] == pid,
            'Counter process/enable mismatch')
    require(replay['available'] is True and all(type(row['instance_monotonic_ns']) is int
            and row['instance_monotonic_ns'] > 0 for row in (opt, replay)), 'Counter instance unavailable/malformed')
    require(opt['epoch'] == replay['epoch'] == 1 and opt['epoch_reason'] == 'optimizer_restore_begin'
            and replay['epoch_reason'] == 'directory_adopt_begin', 'Unexpected load epochs')
    require(opt['total'] == opt['since_epoch'] and set(opt['total']) == expected, 'Optimizer load straddling')
    totals = opt['total']
    require(all(type(v) is int and v >= 0 for v in totals.values()), 'Malformed optimizer counters')
    require(totals['attempts_started'] == totals['outcomes_recorded'] == 1
            and totals['applied'] + totals['amp_skipped'] == 1 and totals['unavailable'] == 0
            and opt['unclassified_started_total'] == opt['prior_epoch_outcomes_total'] == 0
            and opt['available'] is True and opt['last_reason'] == 'single_cuda_found_inf',
            'First postload attempt not one fully classified AMP outcome')
    categories = {'dqn', 'epsilon', 'expert', 'eval', 'unattributed'}
    require(all(set(replay[key]) == categories and all(type(v) is int and v == 0 for v in replay[key].values())
                for key in ('accepted_by_source_total', 'accepted_by_source_since_epoch')), 'Missing/nonzero replay source partition')
    require(replay['accepted_total'] == replay['accepted_learner_total'] == replay['accepted_since_epoch']
            == replay['accepted_learner_since_epoch'] == 0
            and not any(replay['accepted_by_source_total'].values())
            and not any(replay['accepted_by_source_since_epoch'].values()), 'Imported replay treated as fresh')
    return {'optimizer': opt, 'replay': replay,
            'note': 'One known applied or AMP-skipped postload attempt; no per-row gradient attribution. Imported6M and banks excluded. Each process/epoch is a new baseline.'}

def publish(path, report):
    raw = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
    return publish_raw(path, raw)

def publish_raw(path, raw):
    """Retain an API response verbatim, including any disclosed Inf-gradient value."""
    with Path(path).open('xb') as file:
        file.write(raw); file.flush(); os.fchmod(file.fileno(), 0o444); os.fsync(file.fileno())
    return digest(raw)
