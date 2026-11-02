"""One original CPU contract run for the actual current capture metadata."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import unittest


def pin(path):
    path=Path(path)
    def identity(s):
        return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
            ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    before=identity(path.stat());raw=path.read_bytes();assert identity(path.stat())==before
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256');args=parser.parse_args()
    assert args.job and args.expected_job_sha256 and pin(args.job)['sha256']==args.expected_job_sha256
    job=json.loads(args.job.read_bytes());assert job['schema']=='profile06-current-capture-metadata-CPU-job-v1'
    assert pin(Path(__file__))==job['sources']['CPU_runner']
    for entry in job['sources'].values():assert pin(entry['path'])==entry and entry['identity']['mode']=='0o444'
    source=job['sources']['tests'];spec=importlib.util.spec_from_file_location('_original_current_capture_contracts',source['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    started=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(suite)
    for entry in job['sources'].values():assert pin(entry['path'])==entry
    assert 'torch' not in sys.modules
    passed=result.wasSuccessful() and result.testsRun==22 and len(result.skipped)==0
    report=dict(schema='profile06-current-capture-metadata-original22-CPU-report-v1',status='PASS' if passed else 'FAIL',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        seconds=time.monotonic()-started,tested_sources=job['sources'],mocked_unit_HTTP_and_process_events=True,
        real_private_flow_and_endpoint_artifacts=True,production_changed=False,live_window_not_launched_by_this_CPU=True,actual_strict_CPU_verifier_not_run_by_contracts=True,mocked_closed_provenance_callbacks=True,private_copy_payload_is_not_a_model=True,
        original_test_retried=False,quality_qualified=False,promotion=False,learning_speed_gain_verified=False)
    path=Path(job['report']);raw=(json.dumps(report,indent=2)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o444)
    print(json.dumps(dict(report=pin(path),status=report['status'],tests=result.testsRun)),flush=True)
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
