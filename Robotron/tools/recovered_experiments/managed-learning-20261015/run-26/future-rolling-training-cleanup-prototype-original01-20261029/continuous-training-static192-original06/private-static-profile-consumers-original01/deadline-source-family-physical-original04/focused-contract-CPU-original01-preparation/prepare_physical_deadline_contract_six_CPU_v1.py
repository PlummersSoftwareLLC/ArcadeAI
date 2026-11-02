"""Default inert. Root-only fresh metadata preparation; no CPU/service/test launch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

SELECTION = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/focused-contract-CPU-original01-preparation/physical-deadline-contract-six-CPU-source-selection-v1.json', 'sha256': 'd1a9d42b2fe00c888006931c8e5a38e8ff5faf8b69c94775c4b0f5ea487ca906', 'bytes': 22722, 'identity': {'device': 2304, 'inode': 85331415, 'bytes': 22722, 'mtime_ns': 1793292251762602653, 'ctime_ns': 1793292251762602653, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/focused-contract-CPU-original01-preparation')

def require(value,message):
    if not value:raise ValueError(message)

def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)

def pin(path):
    path=Path(path);before=identity(path.stat());raw=path.read_bytes()
    require(identity(path.stat())==before,'Metadata input changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)

def checked(value):
    path=Path(value['path'])
    require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink()
            and pin(path)==value,'Exact held source changed')
    return path

def put(path,value):
    with path.open('x')as f:
        f.write(json.dumps(value,indent=2,allow_nan=False)+'\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return pin(path)

def reduced(value):
    return dict(value,identity={k:value['identity'][k]for k in('device','inode','mode','uid','nlink')})

def prepare(directory,expected_source_sha256):
    own=pin(Path(__file__).resolve());require(own['sha256']==expected_source_sha256,'Exact metadata preparer required')
    selected=json.loads(checked(SELECTION).read_bytes())
    require(selected['schema']=='robotron-physical192-six-CPU-source-selection-v1'
            and selected['expected_test_count']==6,'Exact six predicate source selection required')
    for value in selected['inputs']:checked(value)
    require(Path('/usr/bin/python3').resolve()==Path(selected['interpreter']['path']),'Selected interpreter alias differs')
    directory=directory.resolve()
    require(directory.parent==ROOT and directory.name=='actual-original01'
            and not directory.exists(),'Only fresh original01 metadata namespace allowed')
    directory.mkdir(mode=0o700)
    unit='robotron-physical-DL13-contract-six-CPU-original01-20261029.service'
    inputs=[*selected['inputs'],SELECTION,own]
    job=dict(schema='robotron-physical-deadline-contract-focused-original-CPU-job-v1',unit=unit,
        output=str(directory/'runtime'),source=selected['driver'],fixture=selected['fixture'],
        original_attempt=1,no_retry=True,inputs=inputs,expected_test_count=6,
        expected_report_schema='robotron-physical-deadline-contract-focused-original-CPU-report-v1',
        resources=dict(CPU_cores=2,memory_bytes=4<<30,runtime_s=180,tasks=128),
        actual_startup_or_fleet_runtime_qualified=False,scientific_launch_qualified=False,
        quality_qualified=False,promotion=False)
    jp=put(directory/'job.json',job)
    cfg=dict(unit=unit,output=str(directory/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',selected['driver']['path'],'--execute','--job',jp['path'],
              '--job-sha256',jp['sha256'],'--source-sha256',selected['driver']['sha256']],
        properties=selected['properties'],pins=[reduced(v)for v in[jp,*inputs]],observation_s=240)
    cp=put(directory/'controller-config.json',cfg)
    return dict(job=jp,config=cp,Root_controller_argv=['/usr/bin/python3.12','-I','-B',selected['controller']['path'],
        '--execute','--config',cp['path'],'--expected-source-sha256',selected['controller']['sha256']],
        Root_close_argv=['/usr/bin/python3.12','-I','-B',selected['closer']['path'],'--close','--directory',str(directory)])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--directory',type=Path);p.add_argument('--source-sha256');args=p.parse_args()
    if args.prepare:print(json.dumps(prepare(args.directory,args.source_sha256),indent=2),flush=True)
    else:print('PLAN_ONLY_NO_READS_IMPORTS_TESTS_PROBES_OR_ACTIONS')
