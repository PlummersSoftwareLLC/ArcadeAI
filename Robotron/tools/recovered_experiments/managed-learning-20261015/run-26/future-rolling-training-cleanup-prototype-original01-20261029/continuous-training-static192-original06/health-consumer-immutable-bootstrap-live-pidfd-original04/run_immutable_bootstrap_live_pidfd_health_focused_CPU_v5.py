"""Default inert; one original Root-operated pure predicate CPU qualification."""
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


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    path=Path(path);before=path.stat()
    identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
        mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    raw=path.read_bytes();require(identity(path.stat())==identity(before),'Changed fixture input')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def publish(path,value):
    with path.open('x')as stream:
        stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())


def execute(args):
    source=pin(Path(__file__).resolve());require(source['sha256']==args.source_sha256,'Exact CPU driver required')
    jp=pin(Path(args.job).resolve());require(jp['sha256']==args.job_sha256,'Exact original CPU job required')
    job=json.loads(Path(jp['path']).read_bytes())
    require(job['schema']=='robotron-immutable-bootstrap-live-pidfd-focused-original-CPU-job-v4'
        and job['source']==source and job['original_attempt']==1 and job['no_retry']is True,
        'One exact original prospective CPU fixture job required')
    for value in job['inputs']:
        require(pin(value['path'])==value,'Selected original fixture source changed')
    output=Path(job['output']);require(not output.exists(),'Fresh original CPU output only')
    output.mkdir(mode=0o700);started=time.monotonic()
    def audit(event,arguments):
        if event=='import' and arguments[0].split('.')[0]in('torch','tensorflow','cupy'):
            raise RuntimeError('No GPU/model library import in focused fixture')
        if event in ('subprocess.Popen','os.system','socket.__new__','ctypes.dlopen'):
            raise RuntimeError('No service/process/socket/native launch in focused fixture')
        if event=='open' and isinstance(arguments[0],(str,bytes,os.PathLike)):
            text=os.fsdecode(arguments[0])
            if text.endswith('.pt') or '/roms/'in text or text=='/usr/games/mame':
                raise RuntimeError('No model/ROM/MAME body access in focused fixture')
    sys.addaudithook(audit)
    fixture=job['fixture'];require(pin(fixture['path'])==fixture,'Exact fixture file required')
    spec=importlib.util.spec_from_file_location('_immutable_bootstrap_live_pidfd_health_fixture',fixture['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(module.Tests)
    require(suite.countTestCases()==6,'Six focused methods required; no inherited suite rerun')
    print(json.dumps(dict(phase='FOCUSED_IMMUTABLE_BOOTSTRAP_LIVE_PIDFD_V4',methods=6)),flush=True)
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite)
    for value in job['inputs']:
        require(pin(value['path'])==value,'Fixture source changed during original CPU run')
    require('torch'not in sys.modules,'Torch unexpectedly imported')
    report=dict(schema='robotron-immutable-bootstrap-live-pidfd-focused-original-CPU-report-v4',status='PASS'if result.wasSuccessful()else'FAIL',
        original_job=jp,actual_PID=os.getpid(),source=source,fixture=fixture,
        tests_run=result.testsRun,failures=[str(t)for t,_ in result.failures],errors=[str(t)for t,_ in result.errors],
        elapsed_s=time.monotonic()-started,Torch_imported=False,GPU_or_MAME_launched=False,
        pure_SHA_bound_actual_registry_health_and_transport_functions=True,
        temporary_immutable_synthetic_events_and_TCP_API_evidence=True,
        selected_fixture_includes_actual_keeper_descriptor_collector_with_synthetic_readers=True,
        live_proc_API_unit_pidfd_or_ioctl_operations_called=False,
        actual_MAME_model_or_score_bodies_read=False,
        actual_startup_authority_or_192_runtime_qualified=False,
        worker_or_raw_reviewer_main_executed=False,
        historical_failed_studies_remain_invalid=True,
        scientific_launch_qualified=False,quality_qualified=False,promotion=False)
    publish(output/'report.json',report)
    print(json.dumps(dict(report=str(output/'report.json'),status=report['status'])),flush=True)
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');args=p.parse_args()
    if args.execute:raise SystemExit(execute(args))
    print('PLAN_ONLY: no reads, tests, outputs, imports, probes or actions')
