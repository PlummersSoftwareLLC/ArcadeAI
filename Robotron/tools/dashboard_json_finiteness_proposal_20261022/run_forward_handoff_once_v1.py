"""Own exactly one selected forward-handoff runner; never retry it."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
D = R/'dashboard-JSON-production-continuity-live-controller-original01-preparation-20261022'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    spec = importlib.util.spec_from_file_location('_JSON_handoff_once_h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = h
    spec.loader.exec_module(h)
    assert h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    plan_pin = h.pin(D/'plan.json')
    assert plan_pin['sha256'] == '3e75bbed674bcbcdb5d775d6fed5c968d375409940214a6bfe473ecbac6a7e9b'
    plan = json.loads(h.checked(plan_pin).read_bytes())
    h.checked(plan['runner_source'])
    argv = ['/usr/bin/python3.12', '-I', '-B', plan['runner_source']['path'],
            '--execute', '--plan', plan_pin['path'], '--expected-plan-sha256', plan_pin['sha256']]
    intent = h.put(D/'runner-original-execution-intent.json', dict(
        argv=argv, plan=plan_pin, wrapper=h.pin(__file__), original_attempt=1, no_retry=True, created_unix_s=time.time()))
    stdout_path = D/'runner-original-stdout.txt'
    stderr_path = D/'runner-original-stderr.txt'
    with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
        raw = Path('/proc', str(process.pid), 'stat').read_text()
        child = h.put(D/'runner-original-child.json', dict(pid=process.pid,
            starttime_ticks=int(raw.rsplit(')', 1)[1].split()[19]), observed_live=process.poll() is None,
            argv=argv, intent=intent, created_unix_s=time.time()))
        print(json.dumps(dict(event='ONE_ORIGINAL_FORWARD_RUNNER_STARTED', child=child)), flush=True)
        actual_exit = process.wait()
        stdout.flush()
        stderr.flush()
        os.fchmod(stdout.fileno(), 0o444)
        os.fchmod(stderr.fileno(), 0o444)
        os.fsync(stdout.fileno())
        os.fsync(stderr.fileno())
    result = h.put(D/'runner-original-result.json', dict(actual_exit=actual_exit, original_attempt=1, no_retry=True,
        child=child, intent=intent, stdout=h.pin(stdout_path), stderr=h.pin(stderr_path), ended_unix_s=time.time()))
    print(json.dumps(dict(event='ORIGINAL_FORWARD_RUNNER_TERMINAL', result=result)), flush=True)
    return actual_exit


if __name__ == '__main__':
    sys.exit(main())
