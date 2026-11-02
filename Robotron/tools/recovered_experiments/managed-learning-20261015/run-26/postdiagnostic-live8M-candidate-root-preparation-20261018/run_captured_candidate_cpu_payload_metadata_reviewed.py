"""Root-only single retained CPU verification of the original completed capture."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI')
RUN = ROOT/'Robotron/logs/managed-learning-20261015/run-26'
PACK = ROOT/'Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/postdiagnostic_ce_quality_binding_proposal'
BINDER_SHA = 'e00c135d93ea83e0da23dd5b0a13e323f79023f0c3a111de4d2627bde1d13596'
RESULT = RUN/'postdiagnostic-live8M-candidate-trial01-20261018/result.json'
CAPTURE_RELEASE = RUN/'postdiagnostic-live8M-candidate-original01-root-execution-20261018/root-original-result-and-owned-release.json'
UNIT = 'robotron-postdiagnostic-live8M-candidate-CPU-original01-20261018.service'


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    p = Path(path)
    assert p.is_absolute() and p.resolve(strict=True) == p and p.suffix not in ('.pt', '.pth')
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        before = os.fstat(f.fileno())
        assert stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
        assert before.st_size <= 4 << 20
        raw = f.read((4 << 20) + 1)
        assert identity(before) == identity(os.fstat(f.fileno())) == identity(p.lstat())
    return dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(before))


def read(p):
    assert pin(p['path']) == p and p['identity']['mode'] == '0o444'
    value = json.loads(Path(p['path']).read_bytes())
    assert pin(p['path']) == p
    return value


def publish(path, value=None, raw=None):
    path = Path(path)
    if raw is None:
        raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as f:
        f.write(raw); f.flush(); os.fchmod(f.fileno(), 0o444); os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return pin(path)


def call(out, label, argv):
    started = time.time()
    r = subprocess.run(argv, capture_output=True, timeout=40)
    ended = time.time()
    streams = {kind: publish(out/(label+'-'+kind+'.txt'), raw=data)
        for kind, data in (('stdout', r.stdout), ('stderr', r.stderr))}
    record = dict(argv=argv, returncode=r.returncode,
        stdout=r.stdout.decode('utf-8', 'surrogateescape'),
        stderr=r.stderr.decode('utf-8', 'surrogateescape'),
        started_unix_s=started, ended_unix_s=ended)
    return record, dict(command=publish(out/(label+'-command.json'), record), **streams)


def show(unit):
    r = subprocess.run(['systemctl', '--user', 'show', unit, '--all'], capture_output=True, text=True, timeout=20)
    return dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)


def process_start(pid):
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
        return int(raw[raw.rfind(')')+2:].split()[19])
    except FileNotFoundError:
        return None


def execute(args):
    assert pin(Path(__file__).resolve())['sha256'] == args.expected_source_sha256
    source = PACK/'quality_bindings_payload_metadata.py'
    assert pin(source)['sha256'] == BINDER_SHA and pin(source)['identity']['mode'] == '0o444'
    spec = importlib.util.spec_from_file_location('_root_candidate_cpu_bindings', source)
    B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
    result_pin = pin(RESULT); result = read(result_pin)
    release_pin = pin(CAPTURE_RELEASE); release = read(release_pin)
    case_pin = result['root_case']; case = read(case_pin)
    B.check_root_capture(release, result_pin, case_pin, case, B.archive_text)
    assert result['status'] == 'CAPTURED_PENDING_ROOT_CPU' and result['CPU_executed'] is False
    job_pin = result['cpu_job']; job = read(job_pin)
    assert job['phase_snapshot']['purpose'] == 'candidate' and job['phase_snapshot']['observed_clients'] == 192
    command = result['cpu_argv']
    assert command == [case['cpu_python'], '-Xgil=0', '-I', '-B', str(B.PHASE), '--execute', '--job',
        job_pin['path'], '--expected-job-sha256', job_pin['sha256'], '--expected-verifier-sha256', B.PHASE_SHA]
    assert pin(B.PHASE)['sha256'] == B.PHASE_SHA and not Path(job['output_directory']).exists()
    timer = UNIT.removesuffix('.service')+'.timer'
    assert all(show(u).get('LoadState') == 'not-found' for u in (UNIT, timer))
    out = args.output
    assert out.is_absolute() and out.resolve(strict=False) == out and out.parent == RUN and not out.exists()
    out.mkdir(mode=0o700); (out/'tmp').mkdir(mode=0o700)
    environment = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=2', 'OPENBLAS_NUM_THREADS=2',
        'MKL_NUM_THREADS=2', 'NUMEXPR_NUM_THREADS=2', 'TMPDIR='+str(out/'tmp')]
    properties = ['Type=exec', 'RemainAfterExit=yes', 'Restart=no', 'CPUQuota=200%', 'MemoryMax=8G',
        'MemorySwapMax=0', 'TasksMax=256', 'RuntimeMaxSec=120', 'TimeoutStopSec=5',
        'WorkingDirectory='+str(ROOT), 'StandardOutput=append:'+str(out/'stdout.txt'),
        'StandardError=append:'+str(out/'stderr.txt')]
    argv = ['systemd-run', '--user', '--unit='+UNIT, '--on-active=3s', '--timer-property=AccuracySec=100ms']
    argv += ['--property='+p for p in properties]+environment+command
    intent = publish(out/'root-launch-intent.json', dict(unit=UNIT, timer=timer, argv=argv,
        numeric_argv=command, actual_CPU_job=job_pin, capture_result=result_pin,
        capture_release=release_pin, source=pin(Path(__file__).resolve()), original_attempts=1, no_retry=True))
    record, _ = call(out, 'root-scheduling-carrier', argv)
    assert record['returncode'] == 0
    original = owner = None
    deadline = time.monotonic()+160
    while time.monotonic() < deadline:
        s = show(UNIT); pid = int(s.get('MainPID', '0'))
        if original is None and pid:
            ticks = process_start(pid); assert ticks is not None
            owner = dict(pid=pid, starttime_ticks=ticks, invocation_id=s['InvocationID'], unit=UNIT, cgroup=s['ControlGroup'])
            original = dict(pid=pid, starttime_ticks=ticks, invocation_id=s['InvocationID'], unit=UNIT,
                timer=timer, timer_invocation_id=show(timer)['InvocationID'], launch_intent=intent, observed_live=True)
            publish(out/'root-original-identity.json', original)
            print(json.dumps(original), flush=True)
        if original is not None:
            assert s['InvocationID'] == original['invocation_id'] and s['NRestarts'] == '0'
            if s['ExecMainCode'] != '0' and s['MainPID'] == '0': break
        time.sleep(.05 if original is None else .25)
    else:
        raise RuntimeError('Observational deadline; original unit left untouched')
    assert original is not None
    completion = publish(out/'CPU-completion.json', dict(argv=command, exit_code=int(s['ExecMainStatus'])))
    groups = {}
    for kind, unit, invocation in (('service', UNIT, original['invocation_id']), ('timer', timer, original['timer_invocation_id'])):
        commands = dict(show=['systemctl', '--user', 'show', unit, '--all'], cat=['systemctl', '--user', 'cat', unit],
            journal=['journalctl', '--user', '_SYSTEMD_INVOCATION_ID='+invocation, '--no-pager', '-o', 'short-iso-precise'])
        for action, argv in commands.items():
            record, group = call(out, 'original-'+kind+'-'+action, argv)
            assert record['returncode'] == 0
            groups[kind+'_'+action] = group
    terminal = dict(original=original, full_original_archives=groups,
        original_exec_code=int(s['ExecMainCode']), original_exit=int(s['ExecMainStatus']), original_result=s['Result'])
    archive = publish(out/'root-original-terminal-archive.json', terminal)
    report = None; report_value = None
    report_path = Path(job['output_directory'])/'cpu-verification.json'
    if report_path.exists():
        original_report = pin(report_path)
        report = publish(out/'candidate-CPU-report-readonly.json', raw=Path(report_path).read_bytes())
        assert pin(report_path) == original_report
        report_value = read(report)
    for name in ('stdout', 'stderr'):
        p = out/(name+'.txt')
        if p.exists(): publish(out/('original-'+name+'-readonly.txt'), raw=p.read_bytes())
    released = []
    for kind, unit in (('timer', timer), ('service', UNIT)):
        before = show(unit)
        assert before.get('InvocationID') == original['timer_invocation_id' if kind == 'timer' else 'invocation_id']
        stop, stop_group = call(out, 'release-'+kind+'-stop', ['systemctl', '--user', 'stop', unit])
        assert stop['returncode'] == 0
        if show(unit).get('LoadState') != 'not-found':
            reset, _ = call(out, 'release-'+kind+'-reset-failed', ['systemctl', '--user', 'reset-failed', unit])
            assert reset['returncode'] == 0
        final, final_group = call(out, 'release-'+kind+'-final-show', ['systemctl', '--user', 'show', unit, '--all'])
        fields = dict(line.split('=', 1) for line in final['stdout'].splitlines() if '=' in line)
        assert fields['LoadState'] == 'not-found'
        released.append(dict(unit=unit, stop=stop_group['command'], stop_returncode=stop['returncode'],
            final_show=final_group['command'], final_load_state=fields['LoadState']))
    assert process_start(original['pid']) != original['starttime_ticks']
    passed = (terminal['original_exec_code'], terminal['original_exit'], terminal['original_result']) == (1, 0, 'success')
    passed = passed and report_value is not None and report_value['status'] == 'PASS' and report_value['cuda_initialized'] is False
    released_pin = publish(out/'root-original-CPU-result-and-owned-release.json', dict(schema='robotron-root-captured-candidate-CPU-original-release-v1',
        status='PASS' if passed else 'FAIL', original=original, original_pid=original['pid'],
        original_starttime_ticks=original['starttime_ticks'], original_invocation=original['invocation_id'],
        original_exec_code=terminal['original_exec_code'], original_exit=terminal['original_exit'], original_result=terminal['original_result'],
        CPU_report=report, cpu_job=job_pin, original_terminal_archive=archive,
        original_archived_before_release=True, owned_release=released, unit_released=True,
        known_original_absent=True, no_numeric_rerun=True, quality_acceptance=False))
    execution = publish(out/'CPU-execution.json', dict(owner=owner, timer=timer,
        show=groups['service_show']['stdout'], cat=groups['service_cat']['stdout'], journal=groups['service_journal']['stdout'],
        archived_before_release=True, released=True, release_receipt=released_pin,
        job=job_pin, report=report, completion=completion, command=command))
    print(json.dumps(dict(status='PASS' if passed else 'FAIL', CPU_execution=execution)), flush=True)
    return 0 if passed else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true'); p.add_argument('--expected-source-sha256'); p.add_argument('--output', type=Path)
    args = p.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, imports, runtime queries, verification or writes'); return 0
    assert args.expected_source_sha256 and args.output
    return execute(args)


if __name__ == '__main__':
    raise SystemExit(main())
