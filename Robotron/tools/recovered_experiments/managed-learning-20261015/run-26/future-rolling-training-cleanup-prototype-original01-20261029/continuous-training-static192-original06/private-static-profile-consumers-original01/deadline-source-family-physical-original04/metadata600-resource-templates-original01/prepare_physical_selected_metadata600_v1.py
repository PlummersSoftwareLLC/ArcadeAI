"""Root-only physical comparison metadata600 data preparation; default inert."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
FAMILY={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/prepared-physical-profile-deadline13-SOURCE-ONLY-NOT-QUALIFIED-v1.json', 'sha256': '18832e401535058524d15f03d519b16c2b11df45bfb762d68d385773678b334d', 'bytes': 17430, 'identity': {'device': 2304, 'inode': 85329177, 'bytes': 17430, 'mtime_ns': 1793291627826718793, 'ctime_ns': 1793291627826718793, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PEER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/independent-physical-profile-deadline13-consumer-source-peer-v1.json', 'sha256': '2a2dcac026e95726d67722331b4862316fcafb9337cd30e29162c46eb5765eeb', 'bytes': 41681, 'identity': {'device': 2304, 'inode': 85329629, 'bytes': 41681, 'mtime_ns': 1793291742883554486, 'ctime_ns': 1793291742883554486, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
SOURCES={'prepare_selected_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/metadata600-resource-templates-original01/prepare_selected_metadata600_v1.py', 'sha256': 'cf4c8944fef4a308c3f2365c98fc8199b63250f93802b858fd665e99e72462c6', 'bytes': 4411, 'identity': {'device': 2304, 'inode': 85332114, 'bytes': 4411, 'mtime_ns': 1793293249432860601, 'ctime_ns': 1793293249432860601, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'control_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/metadata600-resource-templates-original01/control_metadata600_v1.py', 'sha256': '5679d36399de4f0c7cc83edd900728112110115fb9f9d44d20c9a3e3b7753f55', 'bytes': 17290, 'identity': {'device': 2304, 'inode': 85332116, 'bytes': 17290, 'mtime_ns': 1793293249440450418, 'ctime_ns': 1793293249440450418, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'close_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/metadata600-resource-templates-original01/close_metadata600_v1.py', 'sha256': 'c920542cc0d3e365e5d82f8ed507d0c7371998192aa9aeccfbb8b9610baf2a3f', 'bytes': 5162, 'identity': {'device': 2304, 'inode': 85332118, 'bytes': 5162, 'mtime_ns': 1793293249442822265, 'ctime_ns': 1793293249442822265, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
CANDIDATE='16c3e3294d97e8bd9899f753a311cd3c958e5fba1a1a5b765f29955a52b2b22d'
REFERENCE='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'

def require(v,reason):
    if not v:raise ValueError(reason)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def read(p,h):
    require(p['identity']['mode']=='0o444','Immutable actual comparison evidence required')
    return json.loads(h.checked(p).read_bytes())

def prepare(comparison,sha,output,study,lease_recovery):
    h=load('_physical_metadata_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h.checked(FAMILY);h.checked(PEER)
    for v in SOURCES.values():h.checked(v)
    sp=h.pin(comparison.resolve());require(sp['sha256']==sha,'Exact actual comparison selection required')
    s=read(sp,h);family=read(FAMILY,h)
    require(s['schema']=='robotron-root-continuous-physical192-fresh-comparison-selection-v2'
        and s['status']=='ACTUAL_POST_MODE_CONTEXT_SELECTED' and s['source_family']==FAMILY
        and s['source_peer']==PEER,'Exact newly qualified physical comparison selection required')
    case=read(s['main_case'],h);joint=read(s['actual_physical_engineering'],h)
    require(case['schema']=='robotron-continuous-physical-original192-health-case-v2'
        and joint['schema']=='robotron-continuous-physical192-joint-engineering-readiness-v1'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['case']==s['main_case'] and joint['input_inventory_authority']==case['input_inventory_authority']
        and joint['source_family']==family['typed_health_packet'],'Actual new physical main engineering association differs')
    capture=read(s['capture_result'],h)
    require(capture['state']=='captured_CPU_verified'and capture['endpoint']['sha256']==CANDIDATE,'Selected valid16c capture required')
    profiles=s['current_runtime_profiles']
    require(profiles['main_source_authority']==case['continuous']['source_authority'],'Actual profile/main source authority differs')
    for role,sha in (('reference',REFERENCE),('candidate',CANDIDATE)):
        a=read(profiles[role+'_profile'],h);proof=read(a['profile_proof'],h)
        require(a['schema']=='robotron-frozen-profile-CPU-independent-adoption-v1'and a['status']=='PASS'
            and a['actual_exit']==0 and a['original_scope_released']is True and a['all_Q_bytes_and_actions_match']is True
            and proof['checkpoint']['sha256']==sha,'Actual newly selected frozen profile/policy differs')
    output=output.absolute();study=study.absolute()
    require(output.resolve()==output and study.resolve()==study and output.parent.is_dir()and study.parent.is_dir()
        and not output.exists()and not study.exists(),'Fresh original metadata and study paths required')
    inputs=[FAMILY,PEER,*family['sources'].values(),family['shared_profile_helper'],sp,s['main_case'],
        case['input_inventory_authority'],case['continuous']['source_authority'],s['actual_physical_engineering'],
        s['capture_result'],s['capture_plan'],s['policy_reevaluation_authority'],s['Root_profile_selection'],
        *s['fresh_profile_closeouts'],profiles['reference_profile'],profiles['candidate_profile'],
        h.pin(Path(__file__).resolve()),*SOURCES.values()]
    for path,row in case['inputs'].items():inputs.append(dict(path=path,sha256=row['sha256'],bytes=row['identity']['bytes'],identity=row['identity']))
    for v in inputs:h.checked(v)
    output.mkdir(mode=0o700)
    unit='robotron-physical16c-metadata600-'+sp['sha256'][:16]+'.service'
    job=dict(schema='robotron-selected-admission-study-CPU-preparation-v1',unit=unit,original_attempt=1,no_retry=True,
        output=str(output/'runtime'),study_directory=str(study),comparison_selection=sp,capture_result=s['capture_result'],
        candidate_sha256=CANDIDATE,reference_profile=profiles['reference_profile'],candidate_profile=profiles['candidate_profile'],
        deadline_readiness=s['actual_physical_engineering'],lease_recovery=h.pin(lease_recovery.resolve()),
        inputs=list({v['path']:v for v in inputs}.values()))
    # Root must select the retained exact coordinator authority; never create a lease.
    require(read(job['lease_recovery'],h)['status']=='RESTORED_NEW_BOOT_COORDINATOR','Retained coordinator authority required')
    job['inputs'].append(job['lease_recovery'])
    jp=h.put(output/'job.json',job)
    control=load('_physical_metadata600_controller',h.checked(SOURCES['control_metadata600_v1.py']))
    cfg=dict(unit=unit,output=str(output/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',SOURCES['prepare_selected_metadata600_v1.py']['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',SOURCES['prepare_selected_metadata600_v1.py']['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=660,pins=[control.pin(v['path'])for v in[jp,*job['inputs']]])
    cp=h.put(output/'controller-config.json',cfg)
    return h.put(output/'prepared-physical-selected-metadata600-NOT-LAUNCHED.json',dict(job=jp,config=cp,
        actual_comparison_selection=sp,source=h.pin(Path(__file__).resolve()),
        Root_controller_argv=['/usr/bin/python3.12','-I','-B',SOURCES['control_metadata600_v1.py']['path'],'--execute','--config',cp['path'],
            '--expected-source-sha256',SOURCES['control_metadata600_v1.py']['sha256']],
        Root_close_argv=['/usr/bin/python3.12','-I','-B',SOURCES['close_metadata600_v1.py']['path'],'--close','--directory',str(output)],
        scientific_launch_qualified=False,actual_CPU_launched=False,quality_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--comparison-selection',type=Path)
    p.add_argument('--lease-recovery',type=Path);p.add_argument('--comparison-selection-sha256');p.add_argument('--output',type=Path);p.add_argument('--study-directory',type=Path);a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a.comparison_selection,a.comparison_selection_sha256,a.output,a.study_directory,a.lease_recovery)),flush=True)
    else:print('PLAN_ONLY_NO_READS_IMPORTS_TESTS_OR_ACTIONS')
