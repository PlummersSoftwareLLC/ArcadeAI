"""Root-only fresh physical review precommit+CPU data; default inert, never launches."""
import argparse
import importlib.util
import json
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
F=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04')
FAMILY={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/prepared-physical-profile-deadline13-SOURCE-ONLY-NOT-QUALIFIED-v1.json', 'sha256': '18832e401535058524d15f03d519b16c2b11df45bfb762d68d385773678b334d', 'bytes': 17430, 'identity': {'device': 2304, 'inode': 85329177, 'bytes': 17430, 'mtime_ns': 1793291627826718793, 'ctime_ns': 1793291627826718793, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PEER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/independent-physical-profile-deadline13-consumer-source-peer-v1.json', 'sha256': '2a2dcac026e95726d67722331b4862316fcafb9337cd30e29162c46eb5765eeb', 'bytes': 41681, 'identity': {'device': 2304, 'inode': 85329629, 'bytes': 41681, 'mtime_ns': 1793291742883554486, 'ctime_ns': 1793291742883554486, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
FINALIZER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/postguard-owned-operations-original01/finalize_physical_study_readiness_v1.py', 'sha256': '45b608e2f15e76a4fa1d090461948c2f98871246120c250e71e2540995e06c62', 'bytes': 5672, 'identity': {'device': 2304, 'inode': 85332220, 'bytes': 5672, 'mtime_ns': 1793293594970844707, 'ctime_ns': 1793293594970844707, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}

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
