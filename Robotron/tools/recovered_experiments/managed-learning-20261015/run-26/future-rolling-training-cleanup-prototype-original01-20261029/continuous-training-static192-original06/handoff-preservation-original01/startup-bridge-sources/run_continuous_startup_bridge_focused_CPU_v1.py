"""Default inert; one Root-operated continuous-startup before-first-update bridge CPU qualification."""
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
    require(job['schema']=='robotron-continuous-startup-bridge-focused-CPU-job-v1'
        and job['source']==source and job['original_attempt']==1 and job['no_retry']is True,
        'One exact original prospective CPU fixture job required')
    for value in job['inputs']:
        require(pin(value['path'])==value,'Selected original fixture source changed')
    witness=json.loads(Path(job['interpreter_symlink_binding']['path']).read_bytes())
    require(pin(job['interpreter_symlink_binding']['path'])==job['interpreter_symlink_binding'],
        'Exact interpreter witness required')
    require(witness['schema']=='robotron-exact-known-free314-interpreter-symlink-binding-v1'
        and sys.executable==witness['path']=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python'
        and pin(sys.executable)==witness['source_pin']
        and str(Path(sys.executable).resolve(strict=True))==witness['resolved_target']
        and len(witness['links'])==2,'Exact selected interpreter chain required')
    for row in witness['links']:
        q=Path(row['path']);v=q.lstat()
        identity=dict(device=v.st_dev,inode=v.st_ino,bytes=v.st_size,mtime_ns=v.st_mtime_ns,
            ctime_ns=v.st_ctime_ns,mode=oct(stat.S_IMODE(v.st_mode)),uid=v.st_uid,nlink=v.st_nlink)
        require(q.is_symlink() and os.readlink(q)==row['readlink']
            and identity==row['lstat_identity'],'Exact selected interpreter link differs')
    output=Path(job['output']);require(not output.exists(),'Fresh original CPU output only')
    output.mkdir(mode=0o700);started=time.monotonic()
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and 'LD_PRELOAD'not in os.environ and 'PYTHONPATH'not in os.environ,
        'CPU-hidden explicit numerical scope required')
    os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
    import torch
    import numpy as np
    torch.set_num_threads(2);torch.set_num_interop_threads(2);torch.set_default_device('cpu')
    require(not torch.cuda.is_initialized()and torch.cuda.device_count()==0,'No visible/initialized CUDA required')
    def deny_cuda_init(*_a,**_kw):raise RuntimeError('No CUDA initialization in tiny CPU fixture')
    torch.cuda._lazy_init=deny_cuda_init
    def audit(event,arguments):
        if event=='import' and arguments[0].split('.')[0]in('tensorflow','cupy'):
            raise RuntimeError('No GPU/model library import in focused fixture')
        # Actual Torch/NumPy CPU native libraries are allowed; CUDA lazy-init is independently blocked.
        if event in ('subprocess.Popen','os.system','socket.__new__'):
            raise RuntimeError('No service/process/socket/native launch in focused fixture')
        if event=='open' and isinstance(arguments[0],(str,bytes,os.PathLike)):
            text=os.fsdecode(arguments[0])
            if text.endswith('.pt') or '/models_dqn/'in text or '/dev/shm/robotron_'in text or '/roms/'in text or text=='/usr/games/mame':
                raise RuntimeError('No model/ROM/MAME body access in focused fixture')
    sys.addaudithook(audit)
    fixture=job['fixture'];require(pin(fixture['path'])==fixture,'Exact fixture file required')
    spec=importlib.util.spec_from_file_location('_continuous_startup_bridge_fixture',fixture['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(module.Tests)
    require(suite.countTestCases()==6,'Six focused actual bridge groups required; no inherited suite rerun')
    print(json.dumps(dict(phase='TINY_CPU_TORCH_NUMPY_STARTUP_BRIDGE',methods=6)),flush=True)
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite)
    for value in job['inputs']:
        require(pin(value['path'])==value,'Fixture source changed during original CPU run')
    require(not torch.cuda.is_initialized()and torch.cuda.device_count()==0,'CUDA unexpectedly initialized/visible')
    report=dict(schema='robotron-continuous-startup-bridge-focused-CPU-report-v1',status='PASS'if result.wasSuccessful()else'FAIL',
        original_job=jp,actual_PID=os.getpid(),source=source,fixture=fixture,
        tests_run=result.testsRun,failures=[str(t)for t,_ in result.failures],errors=[str(t)for t,_ in result.errors],
        elapsed_s=time.monotonic()-started,Torch_imported=True,NumPy_imported=True,CUDA_initialized=False,
        visible_CUDA_devices=0,GPU_or_MAME_launched=False,production_model_or_array_bodies_opened=False,
        actual_bridge_functions_with_tiny_CPU_tensor_and_mmap_payloads_exercised=True,
        actual_owner_service_queries_and_producer_authority_are_synthetic=True,
        full_6M_or_81Adam_or_production_restore_qualification=False,
        before_worker_listener_order_scope='source AST order plus actual no-work/release consumer; no real main launched',
        runtime_or_scientific_startup_qualified=False,
        scientific_launch_qualified=False,quality_qualified=False,promotion=False)
    publish(output/'report.json',report)
    print(json.dumps(dict(report=str(output/'report.json'),status=report['status'])),flush=True)
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');args=p.parse_args()
    if args.execute:raise SystemExit(execute(args))
    print('PLAN_ONLY: no reads, tests, outputs, imports, probes or actions')
