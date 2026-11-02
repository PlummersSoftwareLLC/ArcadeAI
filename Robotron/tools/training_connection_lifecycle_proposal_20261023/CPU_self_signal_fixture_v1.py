"""Private controller-conformance fixture: send SIGTERM only to this own PID."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-private-self-SIGTERM-controller-fixture-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''and job['signal']==15 and job['wait_s']==.5
    print(json.dumps(dict(status='PRIVATE_SELF_SIGNAL_EXPECTED_NOT_PAYLOAD_SUCCESS',own_pid=os.getpid(),signal=15,production_touched=False)),flush=True)
    time.sleep(.5);os.kill(os.getpid(),signal.SIGTERM)
    raise AssertionError('Default self-SIGTERM must not return normally')


if __name__=='__main__':raise SystemExit(main())
