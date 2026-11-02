"""Root's exact terminal16 mock guards; retain originals before owned release."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = Path('/home/dave/source/repos/ArcadeAI')
RUN = REPO / 'Robotron/logs/managed-learning-20261015/run-26'
SRC = REPO / 'Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/quality_trial02_terminal_closure_proposal'
MANIFEST_SHA = 'eb890f858cff5250fd457ac0143d63cd342d47cdde1c36471d9485a0f2c9b1d1'
OUT = RUN / 'rawKL-trial02-quality-terminal16-guards-root-execution-reviewed1-20261017'
UNIT = 'robotron-rawkl-trial02-quality-terminal16-guards-reviewed1-20261017.service'
TIMER = UNIT.removesuffix('.service') + '.timer'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path):
    path = Path(path)
    info = path.stat()
    return dict(path=str(path), sha256=sha(path), bytes=info.st_size)


def save(path, value):
    path = Path(path)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        require(stream.write(raw) == len(raw), 'Short archival write')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(path)


def call(argv):
    # Failures remain raw command evidence; no command is automatically repeated.
    try:
        result = subprocess.run(argv, capture_output=True, text=True, errors='surrogateescape', timeout=15)
        return dict(argv=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    except (subprocess.TimeoutExpired, OSError) as error:
        def text(value):
            return value.decode('utf-8', 'surrogateescape') if isinstance(value, bytes) else (value or '')
        return dict(argv=argv, returncode=None, stdout=text(getattr(error, 'stdout', None)),
            stderr=text(getattr(error, 'stderr', None)), exception=type(error).__name__ + ': ' + str(error))


def fields(raw):
    return dict(line.split('=', 1) for line in raw['stdout'].splitlines() if '=' in line)


def show(unit):
    raw = call(['systemctl', '--user', 'show', unit, '--all'])
    value = fields(raw)
    require(raw['returncode'] == 0 or raw['returncode'] is not None and value.get('LoadState') == 'not-found', 'Cannot inspect exact unit: ' + unit)
    require('LoadState' in value, 'Missing authoritative LoadState: ' + unit)
    return value, raw


def start(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def load_pinned(expected):
    require(pin(expected['path']) == expected, 'Saved root evidence changed')
    return json.loads(Path(expected['path']).read_bytes())


def launch(manifest_sha):
    manifest = SRC / 'preparation-manifest.json'
    require(manifest_sha == MANIFEST_SHA == sha(manifest), 'Wrong sealed closure bundle')
    for name, entry in json.loads(manifest.read_bytes())['files'].items():
        require(sha(SRC / name) == entry['sha256'] and (SRC / name).stat().st_size == entry['bytes'], 'Source pin changed')
    pins = {}
    for path in SRC.iterdir():
        if path.is_file():
            require(not path.is_symlink() and path.stat().st_mode & 0o777 == 0o444, 'Unsealed source: ' + str(path))
            pins[path.name] = sha(path)
    testpath = SRC / 'test_quality_closure.py'
    expected = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
        for node in ast.walk(ast.parse(testpath.read_text())))
    require(expected == 16, 'Exact sixteen authored guards required')
    require(not OUT.exists() and all(show(unit)[0]['LoadState'] == 'not-found' for unit in (UNIT, TIMER)), 'New-only execution required')
    OUT.mkdir()
    (OUT / 'tmp').mkdir()
    code = 'import sys,unittest,importlib.util;spec=importlib.util.spec_from_file_location("_root_quality_terminal16_tests",' + repr(str(testpath)) + ');module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);suite=unittest.defaultTestLoader.loadTestsFromTestCase(module.QualityClosureGuards);assert suite.countTestCases()==16;r=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not r.wasSuccessful())'
    argv = ['systemd-run', '--user', '--unit=' + UNIT,
        '--property=Type=exec', '--property=RemainAfterExit=yes', '--property=Restart=no',
        '--property=CPUQuota=100%', '--property=MemoryMax=512M', '--property=MemorySwapMax=0',
        '--property=RuntimeMaxSec=60', '--property=TimeoutStopSec=5', '--property=TasksMax=32',
        '--property=WorkingDirectory=' + str(REPO),
        '--property=StandardOutput=append:' + str(OUT / 'stdout.txt'),
        '--property=StandardError=append:' + str(OUT / 'stderr.txt'),
        '--on-active=3s', '--timer-property=AccuracySec=100ms',
        '/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR=' + str(OUT / 'tmp'),
        '/usr/bin/python3.12', '-I', '-B', '-c', code]
    save(OUT / 'root-runner-source.py', Path(__file__).read_bytes())
    intent = save(OUT / 'root-launch-intent.json', dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        unit=UNIT, timer=TIMER, argv=argv, source_pins=pins, expected_tests=expected,
        root_runner_sha256=sha(__file__), scope='Exact stdlib FakeOps guards only; no actual closure/runtime/PT/GPU action'))
    returned = call(argv)
    returned.update(carrier_reaped_by_subprocess_run=returned['returncode'] is not None, returned_monotonic_ns=time.monotonic_ns())
    save(OUT / 'root-scheduling-carrier-return.json', returned)
    require(returned['returncode'] == 0, 'Scheduling failed or ambiguous; preserve without relaunch')
    timer, raw = show(TIMER)
    timer_show_pin = save(OUT / 'root-original-timer-observed-show-command.json', raw)
    timer_cat = call(['systemctl', '--user', 'cat', TIMER])
    timer_cat_pin = save(OUT / 'root-original-timer-observed-cat-command.json', timer_cat)
    require(timer['LoadState'] == 'loaded' and re.fullmatch('[0-9a-f]{32}', timer.get('InvocationID', ''))
        and timer.get('Triggers') == UNIT, 'Original timer lineage unavailable; preserve without relaunch')
    until = time.monotonic() + 6
    while True:
        service, raw = show(UNIT)
        if int(service.get('ExecMainPID', '0')) > 0:
            break
        require(time.monotonic() < until, 'Original test PID unobserved; preserve without relaunch')
        time.sleep(.1)
    observed_show = save(OUT / 'root-original-service-observed-show-command.json', raw)
    pid = int(service['ExecMainPID'])
    require(service['NRestarts'] == '0' and re.fullmatch('[0-9a-f]{32}', service['InvocationID']), 'Invalid original service identity')
    observed = dict(unit=UNIT, timer=TIMER, pid=pid, starttime_ticks=start(pid), invocation_id=service['InvocationID'],
        exec_start_monotonic_us=int(service['ExecMainStartTimestampMonotonic']), timer_invocation_id=timer['InvocationID'],
        launch_intent=intent, observed_show=observed_show, timer_observed_show=timer_show_pin,
        timer_observed_cat=timer_cat_pin, observed_live=service['MainPID'] == str(pid))
    save(OUT / 'root-observed-original-identity.json', observed)
    require(observed['exec_start_monotonic_us'] * 1000 > returned['returned_monotonic_ns'], 'Test started before carrier reap; identity preserved')
    print(json.dumps(dict(status='SCHEDULED_ONCE', original_pid=pid, original_invocation=observed['invocation_id'], expected_tests=16, unit=UNIT)))


def original_terminal(observed):
    value, raw = show(UNIT)
    require(value['MainPID'] == '0' and int(value['ExecMainPID']) == observed['pid']
        and value['InvocationID'] == observed['invocation_id'] and value['NRestarts'] == '0'
        and int(value['ExecMainStartTimestampMonotonic']) == observed['exec_start_monotonic_us']
        and value['SubState'] in ('exited', 'dead', 'failed') and int(value['ExecMainCode']) != 0,
        'Original same service is not retained terminal')
    return value, raw


def original_absent(observed):
    current = start(observed['pid'])
    require(current is None or observed['starttime_ticks'] is not None and current != observed['starttime_ticks'], 'Original test process remains or is unclassified')


def archive():
    observed = json.loads((OUT / 'root-observed-original-identity.json').read_bytes())
    intent = load_pinned(observed['launch_intent'])
    require(observed['unit'] == intent['unit'] == UNIT and observed['timer'] == intent['timer'] == TIMER, 'Foreign execution identity')
    require(intent['root_runner_sha256'] == sha(__file__), 'Root runner source changed')
    first_service = fields(load_pinned(observed['observed_show']))
    first_timer = fields(load_pinned(observed['timer_observed_show']))
    require(int(first_service['ExecMainPID']) == observed['pid'] and first_service['InvocationID'] == observed['invocation_id']
        and int(first_service['ExecMainStartTimestampMonotonic']) == observed['exec_start_monotonic_us']
        and first_timer['InvocationID'] == observed['timer_invocation_id'] and first_timer['Triggers'] == UNIT,
        'Original observed evidence/identity differs')
    service, service_raw = original_terminal(observed)
    timer_raw = call(['systemctl', '--user', 'show', TIMER, '--all'])
    timer = fields(timer_raw)
    commands = {'service-show': service_raw, 'timer-show': timer_raw}
    for label, unit, invocation in [('service', UNIT, observed['invocation_id']), ('timer', TIMER, observed['timer_invocation_id'])]:
        commands[label + '-cat'] = call(['systemctl', '--user', 'cat', unit])
        commands[label + '-journal'] = call(['journalctl', '--user', '_SYSTEMD_INVOCATION_ID=' + invocation, '--no-pager', '-o', 'short-precise'])
    archives = {}
    for name, command in commands.items():
        archives[name] = dict(command=save(OUT / ('original-' + name + '-command.json'), command),
            plain=save(OUT / ('original-' + name + '.txt'), command['stdout'].encode('utf-8', 'surrogateescape')))
    errors = []
    for name, command in commands.items():
        if command['returncode'] == 0:
            continue
        if name in ('timer-show', 'timer-cat') and timer.get('LoadState') == 'not-found' and command['returncode'] is not None:
            continue
        errors.append(name)
    if timer.get('LoadState') != 'not-found' and timer.get('InvocationID') != observed['timer_invocation_id']:
        errors.append('timer-invocation-replaced')
    if timer.get('LoadState') == 'not-found':
        initial = load_pinned(observed['timer_observed_cat'])
        if initial['returncode'] != 0:
            errors.append('original-timer-cat-unavailable')
    try:
        held = all(sha(SRC / name) == digest for name, digest in intent['source_pins'].items())
    except Exception:
        held = False
    try:
        stderr = (OUT / 'stderr.txt').read_text()
    except OSError:
        stderr = ''
    match = re.search(r'Ran (\d+) tests? in ', stderr)
    original = dict(original_pid=observed['pid'], original_starttime_ticks=observed['starttime_ticks'],
        original_invocation=observed['invocation_id'], original_timer_invocation=observed['timer_invocation_id'],
        original_exec_start_monotonic_us=observed['exec_start_monotonic_us'], original_exec_code=int(service['ExecMainCode']),
        original_exit=int(service['ExecMainStatus']), original_result=service['Result'],
        test_methods=None if match is None else int(match.group(1)), source_pins_held=held,
        archive_complete=not errors, archive_errors=errors, full_original_archives=archives,
        evidence_sha256={path.name:sha(path) for path in OUT.iterdir() if path.is_file()})
    save(OUT / 'root-original-terminal-archive.json', original)
    require(not errors, 'Incomplete original archives preserved; no release')
    releases = []
    for unit in (TIMER, UNIT):
        original_terminal(observed)
        original_absent(observed)
        prior, _ = show(unit)
        if prior['LoadState'] == 'not-found':
            releases.append(dict(unit=unit, already_absent=True, final_load_state='not-found'))
            continue
        require(unit != TIMER or prior['InvocationID'] == observed['timer_invocation_id'], 'Original timer replaced before release')
        stopped = call(['systemctl', '--user', 'stop', unit])
        save(OUT / ('release-' + unit + '-stop.json'), stopped)
        after, raw = show(unit)
        save(OUT / ('release-' + unit + '-show-command.json'), raw)
        known = [f'Unit {unit} not loaded.', f'Failed to stop {unit}: Unit {unit} not loaded.']
        require(stopped['returncode'] == 0 or stopped['returncode'] == 5 and after['LoadState'] == 'not-found'
            and stopped['stderr'].strip() in known, 'Unexpected exact-unit stop error; preserve without retry')
        if after['LoadState'] != 'not-found' and after.get('ActiveState') == 'failed':
            if unit == UNIT:
                original_terminal(observed)
            else:
                require(after['InvocationID'] == observed['timer_invocation_id'], 'Timer replaced before reset-failed')
            reset = call(['systemctl', '--user', 'reset-failed', unit])
            save(OUT / ('release-' + unit + '-reset.json'), reset)
            require(reset['returncode'] == 0, 'Exact reset-failed failed')
        final, raw = show(unit)
        save(OUT / ('release-' + unit + '-final-show-command.json'), raw)
        require(final['LoadState'] == 'not-found', 'Exact test unit not released')
        releases.append(dict(unit=unit, returncode=stopped['returncode'], final_load_state='not-found'))
    original_absent(observed)
    passed = original['original_exec_code'] == 1 and original['original_exit'] == 0 and original['original_result'] == 'success' and original['test_methods'] == intent['expected_tests'] == 16 and '\nOK\n' in stderr and held
    receipt = dict(status='PASS' if passed else 'FAILED', **original, original_archived_before_release=True,
        owned_release=releases, scope='Exact sixteen stdlib FakeOps guards only; no actual campaign closure or playing-quality inference')
    save(OUT / 'root-result-review-and-release.json', receipt)
    print(json.dumps(dict(status=receipt['status'], original_exit=original['original_exit'], directory=str(OUT))))


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('PLAN_ONLY: no input reads, queries, tests or unit actions')
    elif sys.argv[1] == 'launch' and len(sys.argv) == 3:
        launch(sys.argv[2])
    elif sys.argv[1] == 'archive' and len(sys.argv) == 2:
        archive()
    else:
        raise SystemExit('launch EXACT_MANIFEST_SHA or archive')
