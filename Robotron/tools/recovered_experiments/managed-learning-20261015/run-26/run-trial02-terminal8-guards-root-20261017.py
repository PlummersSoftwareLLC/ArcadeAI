"""Root's bounded stdlib guard invocation and original-unit archival."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = Path('/home/dave/source/repos/ArcadeAI')
RUN = REPO / 'Robotron/logs/managed-learning-20261015/run-26'
SRC = RUN / 'rawKL-trial02-terminal-release-root-preparation-20261017'
OUT = RUN / 'rawKL-trial02-terminal8-guards-root-execution-reviewed1-20261017'
UNIT = 'robotron-rawkl-trial02-terminal8-guards-reviewed1-20261017.service'
TIMER = UNIT.removesuffix('.service') + '.timer'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def call(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=15)

def show(unit):
    result = call(['systemctl', '--user', 'show', unit])
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line), result

def launch(manifest_sha):
    manifest = SRC / 'preparation-manifest.json'
    assert sha(manifest) == manifest_sha
    selected = ['test_terminal_release.py']
    pins = {}
    for path in SRC.iterdir():
        if path.is_file():
            assert path.stat().st_mode & 0o222 == 0, path
            pins[path.name] = sha(path)
    expected = sum(sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
        for node in ast.walk(ast.parse((SRC / name).read_text()))) for name in selected)
    assert expected == 8
    assert all(show(unit)[0].get('LoadState') == 'not-found' for unit in (UNIT, TIMER))
    OUT.mkdir(); (OUT / 'tmp').mkdir()
    testpath = SRC / 'test_terminal_release.py'
    code = 'import sys,unittest,importlib.util;spec=importlib.util.spec_from_file_location("_root_terminal8_tests",'+repr(str(testpath))+');module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);suite=unittest.defaultTestLoader.loadTestsFromModule(module);assert suite.countTestCases()=='+str(expected)+';r=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not r.wasSuccessful())'
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
    save(OUT / 'root-launch-intent.json', dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        argv=argv, source_pins=pins, expected_tests=expected, root_runner_sha256=sha(Path(__file__)),
        scope='Focused stdlib guard selection only; no learner/runtime/PT/model or GPU experiment actions'))
    result = call(argv)
    save(OUT / 'root-scheduling-carrier-return.json', dict(returncode=result.returncode,
        stdout=result.stdout, stderr=result.stderr))
    assert result.returncode == 0, result.stderr
    print(json.dumps(dict(status='SCHEDULED', expected_tests=expected, unit=UNIT, directory=str(OUT))))

def archive():
    fields, shown = show(UNIT)
    assert shown.returncode == 0 and fields['MainPID'] == '0' and int(fields['ExecMainPID']) > 0
    assert fields['SubState'] in ('exited', 'dead', 'failed') and fields['NRestarts'] == '0'
    assert re.fullmatch('[0-9a-f]{32}', fields['InvocationID'])
    for name, body in [('original-unit-show.txt', shown.stdout),
        ('original-unit-cat.txt', call(['systemctl', '--user', 'cat', UNIT]).stdout),
        ('original-invocation-journal.txt', call(['journalctl', '--user', '_SYSTEMD_INVOCATION_ID=' + fields['InvocationID'], '--no-pager', '-o', 'short-precise']).stdout)]:
        with (OUT / name).open('x') as stream:
            stream.write(body); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    stderr = (OUT / 'stderr.txt').read_text()
    match = re.search(r'Ran (\d+) tests? in ', stderr)
    count = None if match is None else int(match.group(1))
    intent = json.loads((OUT / 'root-launch-intent.json').read_text())
    held = all(sha(SRC / name) == digest for name, digest in intent['source_pins'].items())
    original = dict(original_pid=int(fields['ExecMainPID']), original_invocation=fields['InvocationID'],
        original_exec_code=int(fields['ExecMainCode']), original_exit=int(fields['ExecMainStatus']),
        original_result=fields['Result'], test_methods=count, source_pins_held=held,
        evidence_sha256={path.name:sha(path) for path in OUT.iterdir() if path.is_file()})
    save(OUT / 'root-original-terminal-archive.json', original)
    releases = []
    for unit in (TIMER, UNIT):
        prior, _ = show(unit)
        if prior.get('LoadState') == 'not-found':
            releases.append(dict(unit=unit, already_absent=True)); continue
        stopped = call(['systemctl', '--user', 'stop', unit])
        releases.append(dict(unit=unit, returncode=stopped.returncode, stderr=stopped.stderr))
        assert stopped.returncode == 0
        after, _ = show(unit)
        if after.get('LoadState') != 'not-found' and original['original_result'] != 'success':
            reset = call(['systemctl', '--user', 'reset-failed', unit]); assert reset.returncode == 0
        assert show(unit)[0].get('LoadState') == 'not-found'
    passed = original['original_exec_code'] == 1 and original['original_exit'] == 0 and original['original_result'] == 'success' and count == intent['expected_tests'] and '\nOK\n' in stderr and held
    receipt = dict(status='PASS' if passed else 'FAILED', **original,
        original_archived_before_release=True, owned_release=releases,
        scope='Future exact-terminal archival/release guards; no playing-quality or throughput inference')
    save(OUT / 'root-result-review-and-release.json', receipt)
    print(json.dumps(receipt))

if __name__ == '__main__':
    if sys.argv[1] == 'launch': launch(sys.argv[2])
    elif sys.argv[1] == 'archive': archive()
    else: raise SystemExit('launch MANIFEST_SHA or archive')
