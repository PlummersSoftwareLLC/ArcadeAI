import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
F = B / 'quality32-protectedb231-vs-distinct8dae-fullgame-original01-20261101'
spec = importlib.util.spec_from_file_location('_launchFull8H', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
job_pin = h.pin(F / 'original-sequence-job.json')
job = json.loads(h.checked(job_pin).read_text())
for key in ['runtime', 'prepared', 'preflight', 'physical_preflight']:
    h.checked(job[key])
assert json.loads(h.checked(job['preflight']).read_text())['checks_total'] == 31
assert json.loads(h.checked(job['physical_preflight']).read_text())['checks_total'] == 36
state = json.loads((B.parent / 'state.json').read_text())
assert state['active_quality_job']['directory'] == str(F)
assert not (F / 'original-sequence-owner.json').exists()
argv = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
        '/usr/bin/python3', '-I', '-B', job['runtime']['path'], '--execute', '--job',
        job_pin['path'], '--job-sha256', job_pin['sha256']]
intent = h.put(F / 'original-wrapper-launch-intent.json', dict(
    argv=argv, sequence_job=job_pin, original_attempt=1, no_retry=True,
    started_unix_s=time.time(), previous_scientific_scores_reused=False))
stdout_path = F / 'original-wrapper-stdout.txt'
stderr_path = F / 'original-wrapper-stderr.txt'
with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
    process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
    born = int(Path('/proc', str(process.pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    child = h.put(F / 'original-wrapper-outer-child.json', dict(
        pid=process.pid, birth=born, observed_live=process.poll() is None, launch_intent=intent))
    print(json.dumps(dict(event='ORIGINAL_FULLGAME_SEQUENCE_STARTED', pid=process.pid, birth=born,
                          owner={key: child[key] for key in ['path', 'sha256', 'bytes']})), flush=True)
    while process.poll() is None:
        time.sleep(1)
    code = process.wait()
    stdout.flush()
    stderr.flush()
    os.fsync(stdout.fileno())
    os.fsync(stderr.fileno())
    os.fchmod(stdout.fileno(), 0o444)
    os.fchmod(stderr.fileno(), 0o444)
result = h.put(F / 'original-wrapper-actual-exit.json', dict(
    actual_exit=code, original_pid=process.pid, original_birth=born,
    original_Popen_reaped=True, original_attempt=1, no_retry=True,
    original_launch_intent=intent, stdout=h.pin(stdout_path), stderr=h.pin(stderr_path),
    ended_unix_s=time.time()))
print(json.dumps(dict(event='ORIGINAL_FULLGAME_SEQUENCE_CLOSED', actual_exit=code,
                      result={key: result[key] for key in ['path', 'sha256', 'bytes']})), flush=True)
raise SystemExit(code)
