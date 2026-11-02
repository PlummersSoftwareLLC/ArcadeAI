"""Dormant root-only continuous-guard SAME-.25 candidate CPU launcher. Default PLAN reads nothing.

One completed original capture, one retained numerical child, exact six-group
archives and owned timer-first release. No capture/control/producer actions.
No import/compile/test/execution is implied by this source preparation.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import traceback

ROOT = Path('/home/dave/source/repos/ArcadeAI')
RUN = ROOT/'Robotron/logs/managed-learning-20261015/run-26'
PACK = ROOT/'Robotron/tools/continuous_guard_same_lr25_continuation_proposal'
BINDER_SHA = '2934df1534c1ff82fdd30e0dec930146fdeb74c2589547abd76967df3fe40989'
SELECTOR = ROOT/'Robotron/tools/continuous_guard_same_lr25_continuation_proposal/capture_candidate.py'
SELECTOR_SHA = 'ca6b29903f0330d2c7c989bf2e881b41f1af3fe3bf14ce4b010827b8d57e0eed'
PHASE = ROOT/'Robotron/tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
RECIPE_SOURCE = PACK/'recipe.py'
RECIPE_SHA = '9bc9a24f5f36c5dbe4f6385c1f47a5698bcda0bd6178f7546b263ee136aa1c3a'
PHASE_SHA = '14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
RESULT_PATH = RUN/'continuous-guard-same-LR25-continuation-capture-trial01-20261018/result.json'
CAPTURE_RELEASE_PATH = RUN/'continuous-guard-same-LR25-continuation-capture-original01-root-execution-20261018/root-original-result-and-owned-release.json'
UNIT = 'robotron-continuous-guard-same-LR25-candidate-CPU-original01-20261018.service'
CASE_SCHEMA = 'robotron-root-continuous-guard-same-LR25-candidate-CPU-launch-case-v1'
RECIPE = dict(priority_metric='ce', batch_size=4096, learning_control_lr_scale=.25,
    scheduled_lr=1.25e-5, max_samples_per_frame=8)
_ATTEMPTS = set()

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
    assert r.returncode == 0, 'Read-only show failed rc=%s: %s' % (r.returncode, r.stderr[:4096])
    return dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)


def process_start(pid):
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
        return int(raw[raw.rfind(')')+2:].split()[19])
    except FileNotFoundError:
        return None


def preflight(args):
    if not __debug__:
        raise RuntimeError('Ownership assertions must remain enabled; no optimized interpreter')
    assert pin(Path(__file__).resolve())['sha256'] == args.expected_source_sha256
    root_case_pin = pin(args.case)
    assert root_case_pin['sha256'] == args.expected_case_sha256
    root_case = read(root_case_pin)
    assert set(root_case) == {'schema','capture_result','capture_release','phase_cpu_job','unit','output_directory'}
    assert root_case['schema'] == CASE_SCHEMA and root_case['unit'] == UNIT
    assert root_case['capture_result']['path'] == str(RESULT_PATH)
    assert root_case['capture_release']['path'] == str(CAPTURE_RELEASE_PATH)
    source = PACK/'quality_bindings.py'
    assert pin(source)['sha256'] == BINDER_SHA and pin(source)['identity']['mode'] == '0o444'
    assert pin(SELECTOR)['sha256'] == SELECTOR_SHA and pin(PHASE)['sha256'] == PHASE_SHA
    assert pin(RECIPE_SOURCE)['sha256'] == RECIPE_SHA and pin(RECIPE_SOURCE)['identity']['mode'] == '0o444'
    spec = importlib.util.spec_from_file_location('_root_current_recipe_cpu_bindings', source)
    B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
    assert pin(source)['sha256'] == BINDER_SHA and B.PHASE == PHASE and B.PHASE_SHA == PHASE_SHA
    result_pin, release_pin = root_case['capture_result'], root_case['capture_release']
    result, release = read(result_pin), read(release_pin)
    case_pin = result['root_case']; case = read(case_pin)
    B.check_root_capture(release, result_pin, case_pin, case, B.archive_text)
    assert result['schema'] == 'robotron-continuous-guard-same-lr25-continuation-result-v1'
    assert result['status'] == 'CAPTURED_PENDING_ROOT_CPU' and result['CPU_executed'] is False
    assert result['qualification_pass'] is False and result['owner_actions'] is False and result['model_only'] is True
    assert result['control_changed'] is True and result['hold_recipe_through_quality'] is True and result['restored_control'] is False
    assert case['recipe'] == result['recipe'] == RECIPE and result['root_case'] == result['root_precommit']
    job_pin = root_case['phase_cpu_job']; assert job_pin == result['cpu_job']
    job = read(job_pin); selected = B.load_selector().load('recipe').from_held(job['source_control_context']['held_recipe_context'])
    assert selected == RECIPE and job['verifier_sha256'] == PHASE_SHA and job['strict_phase_base_sha256'] == B.STRICT_SHA
    assert job['original_strict_base_sha256'] == B.BASE_SHA
    phase = job['phase_snapshot']; current = result['current_phase']
    assert phase['purpose'] == 'candidate' and phase['observed_clients'] == 192
    assert phase['owner'] == result['owner'] and current == dict(record=phase['phase_record'],
        boot_checkpoint=phase['boot_checkpoint'], boot_verification=phase['boot_verification'], expected=phase['expected_phase'])
    assert phase['expected_phase']['metric'] == 'ce' and phase['expected_phase']['valid'] is True
    assert current['record']['sha256'] == '75ec8703405edfb250100006cab8ff44a364cbc84e33583697a985306fd21f10'
    assert job['source'] == result['source'] and job['verification_copy'] == result['verification_copy']
    assert phase['acquisition'] == result['acquisition']
    source_model, copied = job['source'], job['verification_copy']
    candidate = dict(tag=case['tags']['endpoint'], **B.triple(source_model)); B.candidate_descriptor(candidate)
    assert source_model['path'] != copied['path'] and all(source_model[k] == copied[k] for k in ('sha256','bytes'))
    assert (source_model['identity']['device'],source_model['identity']['inode']) != (copied['identity']['device'],copied['identity']['inode'])
    assert all(p['identity']['mode'] == '0o444' and p['identity']['uid'] == os.getuid() and
        p['identity']['nlink'] == 1 and p['identity']['bytes'] == candidate['bytes'] for p in (source_model,copied))
    archived_control = read(job['source_control_context']['archived_control'])
    assert archived_control['lr_scale'] == .25 and archived_control['experiment'] == case['experiment']
    assert job['experiment'] == case['experiment']
    command = result['cpu_argv']
    assert len(command) == 12 and command == [case['cpu_python'], '-Xgil=0', '-I', '-B', str(PHASE), '--execute', '--job',
        job_pin['path'], '--expected-job-sha256', job_pin['sha256'], '--expected-verifier-sha256', PHASE_SHA]
    out = Path(root_case['output_directory'])
    assert out.is_absolute() and out.resolve(strict=False) == out and out.parent == RUN and not out.exists()
    assert out.name == 'continuous-guard-same-LR25-candidate-CPU-original01-root-execution-20261018'
    assert not Path(job['output_directory']).exists()
    return dict(B=B, root_case_pin=root_case_pin, root_case=root_case, result=result, result_pin=result_pin,
        release_pin=release_pin, case=case, case_pin=case_pin, job=job, job_pin=job_pin, command=command,
        candidate=candidate, out=out, binder_pin=pin(source))


def require_terminal(s, original):
    assert s.get('Id') == UNIT and s.get('InvocationID') == original['invocation_id'] and s.get('NRestarts') == '0'
    assert s.get('MainPID') == '0' and s.get('ExecMainPID') == str(original['pid'])
    assert s.get('ExecMainCode') == '1' and s.get('ExecMainStatus','').isdigit()


def check_report_job_file(report_job_file, job_pin):
    """Exact declared FLAT10 report fingerprint for one genuine FULL8 job PIN.

    Metadata only. No model/numeric field normalization and no file access.
    The caller has already authenticated the job through read(job_pin).
    """
    integer_fields = {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'uid', 'nlink'}
    identity_fields = integer_fields | {'mode'}
    assert type(job_pin) is dict and set(job_pin) == {'path', 'sha256', 'bytes', 'identity'}
    assert type(job_pin['identity']) is dict and set(job_pin['identity']) == identity_fields
    assert type(job_pin['path']) is str and Path(job_pin['path']).is_absolute()
    assert type(job_pin['sha256']) is str and len(job_pin['sha256']) == 64 and all(
        c in '0123456789abcdef' for c in job_pin['sha256'])
    assert type(job_pin['bytes']) is int and job_pin['bytes'] > 0
    ident = job_pin['identity']
    assert all(type(ident[k]) is int for k in integer_fields)
    assert ident['device'] >= 0 and ident['inode'] > 0 and ident['uid'] >= 0
    assert ident['mtime_ns'] > 0 and ident['ctime_ns'] > 0 and ident['nlink'] == 1
    assert type(ident['mode']) is str and ident['mode'] == '0o444'
    assert job_pin['bytes'] == ident['bytes']
    assert type(report_job_file) is dict and set(report_job_file) == identity_fields | {'path', 'sha256'}
    assert type(report_job_file['path']) is str and type(report_job_file['sha256']) is str
    assert type(report_job_file['mode']) is str
    assert all(type(report_job_file[k]) is int for k in integer_fields)
    expected = dict(path=job_pin['path'], sha256=job_pin['sha256'], **ident)
    assert report_job_file == expected, 'Report job_file differs from the exact flattened job fingerprint'


def check_CPU_semantics(context, terminal, report_value, completion_value, groups):
    """Strict native/report metadata gates, then the unchanged scientific checks."""
    assert type(terminal) is dict and type(terminal['original_exec_code']) is int
    assert type(terminal['original_exit']) is int and type(terminal['original_result']) is str
    assert (terminal['original_exec_code'], terminal['original_exit'], terminal['original_result']) == (1, 0, 'success')
    assert type(report_value) is dict and type(report_value['status']) is str and report_value['status'] == 'PASS'
    assert type(completion_value) is dict and set(completion_value) == {'argv', 'exit_code'}
    assert type(completion_value['exit_code']) is int and completion_value['exit_code'] == 0
    assert type(completion_value['argv']) is list
    check_report_job_file(report_value['job_file'], context['job_pin'])
    B = context['B']
    B.check_cpu(context['job'], report_value, completion_value, context['candidate'])
    B.check_CPU_command(dict(cat=groups['service_cat']['stdout'], show=groups['service_show']['stdout']),
        completion_value, B.archive_text)


def run_original(context, progress):
    B, job, job_pin = context['B'], context['job'], context['job_pin']
    command, out = context['command'], context['out']
    timer = UNIT.removesuffix('.service')+'.timer'
    assert all(show(u).get('LoadState') == 'not-found' for u in (UNIT, timer))
    out.mkdir(mode=0o700); (out/'tmp').mkdir(mode=0o700)
    progress.update(stage='before_scheduling', output_created=True)
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
        numeric_argv=command, actual_CPU_job=job_pin, capture_result=context['result_pin'],
        capture_release=context['release_pin'], source=pin(Path(__file__).resolve()),
        launch_case=context['root_case_pin'], binder=context['binder_pin'], original_attempts=1, no_retry=True))
    progress['stage'] = 'scheduling_carrier'
    record, _ = call(out, 'root-scheduling-carrier', argv)
    assert record['returncode'] == 0
    original = owner = None
    deadline = time.monotonic()+160
    progress['stage'] = 'observing_original'
    while time.monotonic() < deadline:
        s = show(UNIT); progress['last_service_show'] = s; pid = int(s.get('MainPID', '0'))
        if original is None and pid:
            ticks = process_start(pid); assert ticks is not None
            again = show(UNIT); timer_live = show(timer)
            assert s.get('Id') == again.get('Id') == UNIT and s.get('NRestarts') == again.get('NRestarts') == '0'
            assert again.get('MainPID') == str(pid) and again.get('InvocationID') == s.get('InvocationID')
            assert process_start(pid) == ticks and len(s.get('InvocationID','')) == 32
            assert timer_live.get('Id') == timer and timer_live.get('Unit') == UNIT and timer_live.get('LoadState') == 'loaded'
            assert len(timer_live.get('InvocationID','')) == 32
            owner = dict(pid=pid, starttime_ticks=ticks, invocation_id=s['InvocationID'], unit=UNIT, cgroup=s['ControlGroup'])
            original = dict(pid=pid, starttime_ticks=ticks, invocation_id=s['InvocationID'], unit=UNIT,
                timer=timer, timer_invocation_id=timer_live['InvocationID'], launch_intent=intent, observed_live=True)
            progress['original'] = original
            publish(out/'root-original-identity.json', original)
            print(json.dumps(original), flush=True)
        if original is not None:
            assert s.get('Id') == UNIT and s['InvocationID'] == original['invocation_id'] and s['NRestarts'] == '0'
            assert pid in (0,original['pid'])
            if s['ExecMainCode'] != '0' and s['MainPID'] == '0': break
        time.sleep(.05 if original is None else .25)
    else:
        raise RuntimeError('Observational deadline; original unit left untouched')
    assert original is not None
    progress.update(stage='original_terminal', original_exec_code=s.get('ExecMainCode'), original_status=s.get('ExecMainStatus'), original_result=s.get('Result'))
    require_terminal(s, original)
    completion_value = dict(argv=command, exit_code=int(s['ExecMainStatus']))
    progress['completion'] = publish(out/'CPU-completion.json', completion_value)
    groups = {}; ended = []
    for kind, unit, invocation in (('service', UNIT, original['invocation_id']), ('timer', timer, original['timer_invocation_id'])):
        commands = dict(show=['systemctl', '--user', 'show', unit, '--all'], cat=['systemctl', '--user', 'cat', unit],
            journal=['journalctl', '--user', '_SYSTEMD_INVOCATION_ID='+invocation, '--no-pager', '-o', 'short-iso-precise'])
        for action, argv in commands.items():
            progress['stage'] = 'archive_'+kind+'_'+action
            record, group = call(out, 'original-'+kind+'-'+action, argv)
            groups[kind+'_'+action] = group; progress['archive_groups'] = dict(groups)
            assert record['returncode'] == 0
            ended.append(record['ended_unix_s'])
    service_show = dict(line.split('=',1) for line in Path(groups['service_show']['stdout']['path']).read_text().splitlines() if '=' in line)
    timer_show = dict(line.split('=',1) for line in Path(groups['timer_show']['stdout']['path']).read_text().splitlines() if '=' in line)
    require_terminal(service_show, original)
    assert service_show['ExecMainStatus'] == s['ExecMainStatus'] and service_show['Result'] == s['Result']
    assert timer_show.get('Id') == timer and timer_show.get('LoadState') == 'loaded' and timer_show.get('Unit') == UNIT and timer_show.get('InvocationID') == original['timer_invocation_id']
    terminal = dict(original=original, full_original_archives=groups,
        original_exec_code=int(s['ExecMainCode']), original_exit=int(s['ExecMainStatus']), original_result=s['Result'])
    archive = publish(out/'root-original-terminal-archive.json', terminal); progress['terminal_archive'] = archive
    report = None; report_value = None
    report_path = Path(job['output_directory'])/'cpu-verification.json'
    if report_path.exists():
        original_report = pin(report_path)
        report = publish(out/'candidate-CPU-report-readonly.json', raw=Path(report_path).read_bytes())
        assert pin(report_path) == original_report
        report_value = read(report)
    progress['report'] = report
    for name in ('stdout', 'stderr'):
        p = out/(name+'.txt')
        if p.exists(): publish(out/('original-'+name+'-readonly.txt'), raw=p.read_bytes())
    semantic_error = None
    try:
        check_CPU_semantics(context, terminal, report_value, completion_value, groups)
    except Exception as error:
        semantic_error = repr(error)
    progress['semantic_error'] = semantic_error
    released = []; progress['owned_release'] = released
    for kind, unit in (('timer', timer), ('service', UNIT)):
        progress['stage'] = 'release_'+kind
        before = show(unit)
        if kind == 'timer':
            assert before.get('Id') == timer and before.get('Unit') == UNIT and before.get('LoadState') == 'loaded' and before.get('InvocationID') == original['timer_invocation_id']
        else:
            require_terminal(before,original)
            assert before['ExecMainStatus'] == s['ExecMainStatus'] and before['Result'] == s['Result']
        item = dict(unit=unit,stop=None,stop_returncode=None,reset_failed=None,final_show=None,final_load_state=None); released.append(item)
        stop, stop_group = call(out, 'release-'+kind+'-stop', ['systemctl', '--user', 'stop', unit])
        item.update(stop=stop_group['command'],stop_returncode=stop['returncode'])
        assert stop['returncode'] == 0 and max(ended) <= stop['started_unix_s']
        after_stop = show(unit)
        if after_stop.get('LoadState') != 'not-found':
            assert after_stop.get('Id') == unit and after_stop.get('ActiveState') == 'failed'
            if kind == 'timer':assert after_stop.get('InvocationID') == original['timer_invocation_id'] and after_stop.get('Unit') == UNIT
            else:require_terminal(after_stop,original)
            reset, reset_group = call(out, 'release-'+kind+'-reset-failed', ['systemctl', '--user', 'reset-failed', unit])
            item['reset_failed'] = reset_group['command']
            assert reset['returncode'] == 0
        final, final_group = call(out, 'release-'+kind+'-final-show', ['systemctl', '--user', 'show', unit, '--all'])
        fields = dict(line.split('=', 1) for line in final['stdout'].splitlines() if '=' in line)
        assert final['returncode'] == 0 and fields.get('Id') == unit and fields['LoadState'] == 'not-found'
        item.update(final_show=final_group['command'],final_load_state=fields['LoadState'])
    assert process_start(original['pid']) != original['starttime_ticks']
    progress.update(stage='owned_release_complete',unit_released=True)
    passed = semantic_error is None
    released_pin = publish(out/'root-original-CPU-result-and-owned-release.json', dict(schema='robotron-root-captured-candidate-CPU-original-release-v1',
        status='PASS' if passed else 'FAIL', original=original, original_pid=original['pid'],
        original_starttime_ticks=original['starttime_ticks'], original_invocation=original['invocation_id'],
        original_exec_code=terminal['original_exec_code'], original_exit=terminal['original_exit'], original_result=terminal['original_result'],
        CPU_report=report, cpu_job=job_pin, original_terminal_archive=archive,
        original_archived_before_release=True, owned_release=released, unit_released=True,
        known_original_absent=True, no_numeric_rerun=True, quality_acceptance=False,semantic_error=semantic_error))
    execution_value = dict(owner=owner, timer=timer,
        show=groups['service_show']['stdout'], cat=groups['service_cat']['stdout'], journal=groups['service_journal']['stdout'],
        archived_before_release=True, released=True, release_receipt=released_pin,
        job=job_pin, report=report, completion=progress['completion'], command=command)
    execution = publish(out/'CPU-execution.json', execution_value)
    if passed:
        B.check_CPU_release(execution_value,job_pin,report,progress['completion'],completion_value,
            B.read,B.archive_text,lambda p:B.archived_bytes(p,allow_empty=True))
    print(json.dumps(dict(status='PASS' if passed else 'FAIL', CPU_execution=execution)), flush=True)
    return 0 if passed else (terminal['original_exit'] if terminal['original_exit'] else 1)


def execute(args):
    context = preflight(args); key = context['root_case_pin']['sha256']
    assert key not in _ATTEMPTS, 'One original numerical scheduling attempt per process'
    _ATTEMPTS.add(key)
    progress = dict(stage='preflight_complete',original=None,owned_release=[],unit_released=False,
        root_case=context['root_case_pin'],job=context['job_pin'],payload_retried=False)
    try:
        return run_original(context,progress)
    except BaseException as error:
        failure = dict(schema='robotron-root-current-recipe-CPU-original-failure-v1',status='ORIGINAL_FAILURE_PRESERVED_NO_RETRY',
            error=repr(error),traceback=traceback.format_exc(),progress=progress,
            original_exit_unknown=progress.get('original_exec_code') != '1',no_retry=True,
            additional_unit_actions_on_exception=False,quality_acceptance=False)
        out=context['out']
        if progress.get('output_created'):
            if isinstance(error,subprocess.TimeoutExpired):
                failure['timeout_command']=error.cmd;failure['timeout_s']=error.timeout
                failure['timeout_completion_unknown']=True
                for kind,data in (('stdout',error.stdout or b''),('stderr',error.stderr or b'')):
                    failure['partial_'+kind]=publish(out/('failed-command-partial-'+kind+'.txt'),raw=data)
            failure_pin=publish(out/'root-CPU-attempt-failure.json',failure)
            print(json.dumps(dict(status=failure['status'],failure=failure_pin)),flush=True)
        else:print(json.dumps(dict(status=failure['status'],error=repr(error),unit_scheduled=False)),flush=True)
        status=progress.get('original_status')
        return int(status) if progress.get('original_exec_code') == '1' and status and int(status) else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true');p.add_argument('--case',type=Path)
    p.add_argument('--expected-case-sha256');p.add_argument('--expected-source-sha256')
    args=p.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads, imports, runtime queries, verification or writes');return 0
    assert args.case and args.expected_case_sha256 and args.expected_source_sha256
    return execute(args)


if __name__ == '__main__':
    raise SystemExit(main())
