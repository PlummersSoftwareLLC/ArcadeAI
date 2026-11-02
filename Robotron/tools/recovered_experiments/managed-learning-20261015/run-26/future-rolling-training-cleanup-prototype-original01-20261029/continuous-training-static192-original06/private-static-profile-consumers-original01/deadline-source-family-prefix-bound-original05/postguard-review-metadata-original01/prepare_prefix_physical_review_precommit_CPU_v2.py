"""Root-only fresh physical review precommit+CPU data; default inert, never launches."""
import argparse
import importlib.util
import json
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
F=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05')
FAMILY={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/prepared-prefix-bound-physical-profile-deadline13-SOURCE-ONLY-v1.json', 'sha256': 'eb5070a9ea134c5b16e553e024c554a948d70f469d862d93b7867ae9e9d675bd', 'bytes': 15750, 'identity': {'device': 2304, 'inode': 85333934, 'bytes': 15750, 'mtime_ns': 1793297226461341101, 'ctime_ns': 1793297226461341101, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PEER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/independent-prefix-bound-private-deadline13-source-and-consumer-peer-v1.json', 'sha256': '73d6c9bcd637d20ff03e54f1c97d6cbd8d2eb471c13c381a46f8080d5ace0234', 'bytes': 40389, 'identity': {'device': 2304, 'inode': 85334110, 'bytes': 40389, 'mtime_ns': 1793297575963658137, 'ctime_ns': 1793297575963658137, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
FINALIZER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/postguard-owned-operations-generic-original02/finalize_physical_study_readiness_v2.py', 'sha256': '5b0563d2eba82f45b0123e05da6260f4d72199b2132fc1b8787cbdaf58667622', 'bytes': 5796, 'identity': {'device': 2304, 'inode': 85333609, 'bytes': 5796, 'mtime_ns': 1793295575231960279, 'ctime_ns': 1793295575231960279, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}

def require(v,reason):
    if not v:raise ValueError(reason)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def prepare(manifest,guards,readiness):
    h=load('_physical_review_CPU_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    read=lambda p:json.loads(h.checked(p).read_bytes())
    h.checked(FAMILY);h.checked(PEER);h.checked(FINALIZER)
    mp,gp,bp=[h.pin(p.resolve())for p in(manifest,guards,readiness)]
    m,g,b=map(read,(mp,gp,bp));root=manifest.resolve().parent
    require(m['engineering_only']is False and g['status']=='PASS'and len(g['guards'])==4
        and b['prepared_manifest']==mp and b['exact_four_guards']==gp
        and b['CPU_qualifications_closed']is b['original_attempts_unused']is True,
        'Actual new four-job guards and qualified configs/readiness required')
    p=load('_physical_review_preparer',h.checked(read(FAMILY)['sources']['prepare_deadline_independent_review_v4.py']))
    rp=p.precommit(manifest.resolve(),guards.resolve(),root/'review-precommit-original01')
    packet=read(rp);driver=h.pin(F/'check_deadline_review_preparation_cpu_v3.py')
    CPU=root/'deadline-review-preparation-CPU-original01'
    require(not CPU.exists(),'One fresh original review-preparation CPU only')
    values=[*read(FAMILY)['sources'].values(),FAMILY,PEER,FINALIZER,rp,mp,gp,bp,h.pin(Path(__file__).resolve())]
    for case in packet['cases']:
        job=read(case['native_job']);values.extend([case['native_job'],case['native_config'],case['guard'],*job['inputs']])
    inputs=list({v['path']:v for v in values}.values())
    for v in inputs:h.checked(v)
    CPU.mkdir(mode=0o700)
    job=dict(schema='robotron-deadline-review-preparation-CPU-engineering-job-v1',
        unit='robotron-physical-reviewprep-'+mp['sha256'][:16]+'-original01.service',output=str(CPU/'runtime'),
        source=driver,review_precommit=rp,original_attempt=1,no_retry=True,inputs=inputs)
    jp=h.put(CPU/'job.json',job);control=load('_physical_review_CPU_controller',G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    cfg=dict(unit=job['unit'],output=str(CPU/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',driver['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=240,pins=[control.pin(v['path'])for v in[jp,*inputs]])
    cp=h.put(CPU/'controller-config.json',cfg);require(control.checked_config(cp['path'])==cfg,'Exact review CPU config differs')
    return h.put(CPU/'prepared-physical-review-precommit-CPU-NOT-LAUNCHED.json',dict(review_precommit=rp,CPU_job=jp,config=cp,
        source=h.pin(Path(__file__).resolve()),Root_controller_argv=['/usr/bin/python3.12','-I','-B',str(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'),'--execute','--config',cp['path'],'--expected-source-sha256',h.pin(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')['sha256']],
        Root_close_argv=['/usr/bin/python3.12','-I','-B',str(G/'tools/post_recovery_evaluation/close_engineering_cpu_scope_v2.py'),'--close','--directory',str(CPU)],
        actual_CPU_launched=False,scientific_launch_qualified=False,quality_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--manifest',type=Path);p.add_argument('--guards',type=Path);p.add_argument('--readiness',type=Path);a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a.manifest,a.guards,a.readiness)),flush=True)
    else:print('PLAN_ONLY_NO_READS_IMPORTS_OR_ACTIONS')
