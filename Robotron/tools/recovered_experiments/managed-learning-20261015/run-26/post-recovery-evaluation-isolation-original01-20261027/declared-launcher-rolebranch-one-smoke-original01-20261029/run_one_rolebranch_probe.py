"""One owned diagnostic command; no game, training control, or scientific result."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
OUT = Path(__file__).resolve().parent
CASE = ROOT/'logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original01/fresh-main-case.json'


def put(name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    with (OUT/name).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def now():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        return json.load(response)


def identity(pid):
    root = Path('/proc', str(pid))
    stat = (root/'stat').read_text().rsplit(')', 1)[1].split()
    command = [x.decode() for x in (root/'cmdline').read_bytes().split(b'\0') if x]
    environment = {}
    for item in (root/'environ').read_bytes().split(b'\0'):
        if b'=' in item:
            key, value = item.split(b'=', 1)
            if key.startswith((b'ROBOTRON_', b'DQN_')) or key in (b'LD_PRELOAD', b'CUDA_VISIBLE_DEVICES'):
                environment[key.decode()] = value.decode()
    exe = os.readlink(root/'exe')
    again = (root/'stat').read_text().rsplit(')', 1)[1].split()
    assert stat[19] == again[19]
    return dict(pid=pid, birth=int(stat[19]), parent_pid=int(stat[1]), state=stat[0],
                executable=exe, command=command, environment=environment,
                monotonic_s=time.monotonic())


def run():
    assert not (OUT/'original-launch.json').exists(), 'Original probe only'
    case = json.loads(CASE.read_bytes())
    fleet = case['owners']['fleet']['process']
    assert int(Path('/proc', str(fleet['pid']), 'stat').read_text().rsplit(')', 1)[1].split()[19]) == fleet['starttime_ticks']
    before = now()
    env = dict(item.decode().split('=', 1) for item in Path('/proc', str(fleet['pid']), 'environ').read_bytes().split(b'\0') if b'=' in item)
    env.update(ROBOTRON_CLIENT_SLOT='0', ROBOTRON_ACTOR_ROUND=str(before['training_round']['round']),
               ROBOTRON_RETIRE_AFTER_GAME='1', ROBOTRON_PREVIEW_FPS='30')
    wrapper = ROOT/'tools/power_recovery/mame_with_roles.sh'
    assert env['MAME_BIN'] == str(wrapper)
    for path, expected in case['inputs'].items():
        if path in (str(wrapper), str(ROOT/'tools/power_recovery/mame_with_roles.py')):
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected['sha256']
    argv = [str(wrapper), *case['actor_command'][1:], '-showusage']
    with (OUT/'stdout.log').open('xb') as stdout, (OUT/'stderr.log').open('xb') as stderr:
        child = subprocess.Popen(argv, env=env, cwd=OUT, stdout=stdout, stderr=stderr)
        birth = int(Path('/proc', str(child.pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
        put('original-launch.json', dict(pid=child.pid, birth=birth, parent_pid=os.getpid(), argv=argv,
            created_unix_s=time.time(), purpose='Explicit showusage command after original game argument tail; smoke only',
            live_case_sha256=hashlib.sha256(CASE.read_bytes()).hexdigest(), no_scientific_result=True))
        records = []
        deadline = time.monotonic()+10
        try:
            while child.poll() is None:
                try:
                    record = identity(child.pid)
                    assert record['birth'] == birth and record['parent_pid'] == os.getpid()
                    records.append(record)
                except (OSError, AssertionError) as failure:
                    records.append(dict(unaccepted_capture=repr(failure), pid=child.pid, monotonic_s=time.monotonic()))
                if time.monotonic() >= deadline:
                    raise TimeoutError('Original diagnostic command exceeded10s')
                time.sleep(.0005)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=3)
            code = child.wait(timeout=3)
            put('original-process-records.json', records)
            put('original-terminal.json', dict(pid=child.pid, birth=birth, actual_Popen_exit=code,
                original_birth_absent=not Path('/proc', str(child.pid)).exists(), ended_unix_s=time.time()))
    after = now()
    put('before-main.raw.json', before)
    put('after-main.raw.json', after)
    data = (OUT/'stdout.log').read_text(errors='replace')
    mame = [r for r in records if r.get('executable') == '/usr/games/mame' and r.get('command') == [*case['actor_command'], '-showusage']]
    assert code == 0 and len(data) > 1000 and 'showusage' in data.lower(), 'Installed binary did not positively report usage'
    assert mame, 'Actual same-birth MAME output stage was not observed'
    for r in mame:
        assert r['environment']['ROBOTRON_EVAL_MODE'] == ('1' if case['slot_eval']['0'] else '2')
        assert r['environment']['ROBOTRON_PREVIEW_CLIENT'] == '1'
        assert r['environment']['ROBOTRON_SOCKET_WAIT_PORT'] == '9998'
        assert r['environment']['LD_PRELOAD'] == case['actor_environment']['LD_PRELOAD']
    assert before['host_pipeline']['learning_exposure']['optimizer']['process_id'] == after['host_pipeline']['learning_exposure']['optimizer']['process_id'] == 294486
    put('result.json', dict(status='OWNED_ROLE_BRANCH_USAGE_SMOKE_PASS', actual_exit=code,
        same_PID_birth_MAME_observed=True, output_role_verified=True, stdout_bytes=len(data),
        observed_executables=sorted({r['executable'] for r in records if 'executable' in r}),
        client_count_before=before['client_count'], client_count_after=after['client_count'],
        scientific_or_load_or500ms_qualification=False))
    print(json.dumps(dict(status='OWNED_ROLE_BRANCH_USAGE_SMOKE_PASS', pid=child.pid, birth=birth, exit=code)))


if __name__ == '__main__':
    run()
