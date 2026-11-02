"""One explicit CPU-only suite for the actual prepared cold64 job. No launch."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def execute(a):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=a.job.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-cold64-actual-job-and-cleanup-CPU-guards-v1'
    assert sys.version_info[:2]==(3,14) and sys._is_gil_enabled() is False
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not os.environ.get('LD_PRELOAD')
    chain=load('_cold_CPU_job_chain',Path(job['chain']['path']))
    for pin in job['inputs']:assert chain.pin(pin['path'])==pin
    prepared=json.loads(Path(job['prepared_manifest']['path']).read_bytes())
    native=json.loads(Path(prepared['native_job']['path']).read_bytes())
    assert not Path(native['output']).exists()
    output=Path(job['output']);assert not output.exists();output.mkdir(mode=0o700)
    actual=load('_cold_CPU_actual_job_tests',Path(job['actual_job_tests']['path']))
    actual.MANIFEST=Path(job['prepared_manifest']['path'])
    cases=load('_cold_CPU_marker_cleanup_tests',Path(job['native_cleanup_tests']['path']))
    suite=unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(actual.ActualColdJobController))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cases.Tests))
    start=time.time();r=unittest.TextTestRunner(verbosity=2).run(suite)
    assert not Path(native['output']).exists()
    assert 'torch' not in sys.modules
    for pin in job['inputs']:assert chain.pin(pin['path'])==pin
    report=dict(schema='robotron-cold64-actual-job-and-cleanup-CPU-guards-result-v1',passed=r.wasSuccessful(),tests_run=r.testsRun,
        tests_by_scope=dict(actual_job_entry_controller=10,native_prefix_marker_cleanup_reviewer=9),
        errors=[str(x) for x in r.errors],failures=[str(x) for x in r.failures],job=a.job.as_posix(),job_sha256=a.job_sha256,
        prepared_manifest=job['prepared_manifest'],native_job=prepared['native_job'],native_runtime=prepared['runtime'],
        interpreter=dict(executable=sys.executable,version=sys.version,major_minor=list(sys.version_info[:2]),GIL_enabled=sys._is_gil_enabled()),
        started_unix_s=start,ended_unix_s=time.time(),native_output_absent=True,GPU_MAME_units_modelbody_or_state_actions=False,
        scope='Ten actual prepared-job/entry/controller/420-resource/provenance checks plus nine cold marker/cleanup/reviewer fixtures; not a rerun of prior18component methods. Real Lua5.4 bounded ROM/IO mocks; worker fields explicitly mocked. Real ROM startup/native64 and independent original raw review remain required.')
    p=output/'report.json'
    with p.open('x') as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    print(json.dumps(dict(passed=report['passed'],tests_run=r.testsRun,report=chain.pin(p))))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--job',type=Path);p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
    else:raise SystemExit(execute(a))
