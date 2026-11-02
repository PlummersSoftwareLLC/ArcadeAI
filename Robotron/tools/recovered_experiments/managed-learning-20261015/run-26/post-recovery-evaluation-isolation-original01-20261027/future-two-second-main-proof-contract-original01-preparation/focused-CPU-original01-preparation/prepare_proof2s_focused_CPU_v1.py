"""Default inert. Prepare source-only CPU envelope; never launch any unit."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

P=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
OUT=P/'actual-focused-CPU-original01'
CONTROL=G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
CONTROL_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
TEST=P/'test_proof2s_contract_bounds_v1.py'
TEST_SHA='582bbf8fbf1696becb174338cacc13dc443fe7164b66826280deb2681f9242cd'
DRIVER=P/'run_proof2s_focused_CPU_v1.py'
DRIVER_SHA='047e393b60651c65717a7b5d80ab950bae5a32cc6ebd4ea991c672d54b2ab220'
UNIT='robotron-proof2s-focused-predicates-CPU-original01-20261029.service'
PROPERTIES=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
    'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']


def require(value,message):
    if not value:raise ValueError(message)


def pin(path):
    path=Path(path);require(not path.is_symlink() and path.resolve(strict=True)==path,'Canonical regular input required')
    before=path.stat()
    identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    raw=path.read_bytes();require(stat.S_ISREG(before.st_mode)and identity(path.stat())==identity(before),'Input changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def selected(path,sha):
    value=pin(path);require(value['sha256']==sha,'Exact frozen source required: '+str(path));return value


def put(path,value):
    with path.open('x')as stream:
        stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return pin(path)


def reduced(value):
    return dict(value,identity={k:value['identity'][k]for k in ('device','inode','mode','uid','nlink')})


def command(config):
    return ['/usr/bin/python3.12','-I','-B',str(CONTROL),'--execute','--config',config['path'],
        '--expected-source-sha256',CONTROL_SHA]


def prepare():
    test=selected(TEST,TEST_SHA);driver=selected(DRIVER,DRIVER_SHA);controller=selected(CONTROL,CONTROL_SHA)
    # This fixture module has only standard imports/constants/definitions.
    # Its actual methods are not called during metadata preparation.
    spec=importlib.util.spec_from_file_location('_proof2s_fixture_source_contract',TEST)
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    sources={role:selected(path,sha)for role,(path,sha)in fixture.SOURCES.items()}
    own=pin(Path(__file__).resolve())
    require(own['identity']['mode']==test['identity']['mode']==driver['identity']['mode']=='0o444',
        'Authored preparation/driver/fixture sources must be frozen')
    require(not OUT.exists(),'New original CPU case only; never reuse a failed output')
    inputs=list({v['path']:v for v in [own,test,driver,controller,*sources.values()]}.values())
    OUT.mkdir(mode=0o700)
    job=dict(schema='robotron-proof2s-focused-original-CPU-job-v1',unit=UNIT,output=str(OUT/'runtime'),
        source=driver,fixture=test,original_attempt=1,no_retry=True,inputs=inputs,
        source_contract='Prospective2s evidence/publication bound; retained500ms cached-API TTLs remain strict.',
        original_failed_500ms_studies_requalified=False,scientific_launch_qualified=False,quality_qualified=False,promotion=False)
    jp=put(OUT/'job.json',job)
    cfg=dict(unit=UNIT,output=str(OUT/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',driver['path'],'--execute','--job',jp['path'],
              '--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=PROPERTIES,observation_s=240,pins=[reduced(v)for v in [jp,*inputs]])
    cp=put(OUT/'controller-config.json',cfg)
    return put(OUT/'prepared-original-focused-CPU-NOT-LAUNCHED.json',dict(
        schema='robotron-proof2s-focused-CPU-preparation-v1',source=own,job=jp,config=cp,
        controller=controller,argv=command(cp),actual_CPU_terminal=None,actual_owned_release=None,
        tests_executed=False,CPU_launched=False,scientific_launch_qualified=False,quality_qualified=False,promotion=False))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group()
    m.add_argument('--prepare',action='store_true');m.add_argument('--print-controller-command',action='store_true')
    args=p.parse_args(argv)
    if args.prepare:print(json.dumps(prepare()),flush=True)
    elif args.print_controller_command:
        selected(CONTROL,CONTROL_SHA)
        packet=json.loads((OUT/'prepared-original-focused-CPU-NOT-LAUNCHED.json').read_bytes())
        require(pin(packet['config']['path'])==packet['config'],'Prepared original config changed')
        print(json.dumps(dict(argv=command(packet['config']),launch_performed=False)),flush=True)
    else:print('PLAN_ONLY: no reads, outputs, imports, tests, queries or launches')


if __name__=='__main__':main()
