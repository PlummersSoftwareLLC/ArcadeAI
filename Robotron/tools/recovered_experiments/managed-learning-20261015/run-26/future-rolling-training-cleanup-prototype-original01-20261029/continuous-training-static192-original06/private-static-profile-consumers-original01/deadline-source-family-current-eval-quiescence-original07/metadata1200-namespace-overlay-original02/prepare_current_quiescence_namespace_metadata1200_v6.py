"""Root-only physical comparison metadata1200 data preparation; default inert."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
FAMILY={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/prepared-current-EVAL-quiescence-profile-deadline13-corrected-guard-SOURCE-ONLY-v6.json', 'sha256': '997ca21fabf6fd2a1edc183ff6857ee60d97119b2ff352580632a609e7260e26', 'bytes': 31130, 'identity': {'device': 2304, 'inode': 85358608, 'bytes': 31130, 'mtime_ns': 1793312011317572079, 'ctime_ns': 1793312011317572079, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PEER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/independent-current-EVAL-quiescence-readiness120-private13-and-fresh-capture-association-source-peer-v6.json', 'sha256': 'ae3e5b6deb2c5fef092411d65e7428679ea991ee9052cc2d8b22a0dd5c79cca8', 'bytes': 25692, 'identity': {'device': 2304, 'inode': 85358806, 'bytes': 25692, 'mtime_ns': 1793312070106492592, 'ctime_ns': 1793312070106492592, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
SOURCES={'prepare_selected_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/metadata1200-namespace-overlay-original02/prepare_selected_current_quiescence_metadata1200_v5.py', 'sha256': '36af7abcb1d75f06acd9c809d8902a366581d848e08bbbae57b23767ecb19ebc', 'bytes': 6117, 'identity': {'device': 2304, 'inode': 85459366, 'bytes': 6117, 'mtime_ns': 1793315773857174275, 'ctime_ns': 1793315773857174275, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'control_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/metadata1200-namespace-overlay-original02/control_metadata1200_v2.py', 'sha256': '5e5951cda9607c6e1cfe2c40435bd84568d211b0ce6796e9bee4d129ca9671a2', 'bytes': 17293, 'identity': {'device': 2304, 'inode': 85459362, 'bytes': 17293, 'mtime_ns': 1793315773851155951, 'ctime_ns': 1793315773851155951, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'close_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/metadata1200-namespace-overlay-original02/close_metadata1200_v2.py', 'sha256': 'a89744b35f2914b01bf05fbccdffcd0e62abdc2b846359edbb5af1207c911be3', 'bytes': 5182, 'identity': {'device': 2304, 'inode': 85459364, 'bytes': 5182, 'mtime_ns': 1793315773853730008, 'ctime_ns': 1793315773853730008, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'metadata_same_invocation_readiness_cache_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/metadata600-current-quiescence-original01/metadata_same_invocation_quiescence_cache_v2.py', 'sha256': 'c40b5c2b44cae9ac06ee7166c96d8186e8fdcd6b9f1cd90514291113f14d13c5', 'bytes': 14680, 'identity': {'device': 2304, 'inode': 85459238, 'bytes': 14680, 'mtime_ns': 1793314847798961457, 'ctime_ns': 1793314847798961457, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'prepare_round_cpu_guard_with_exact_resume_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/prepare_round_cpu_guard_v10.py', 'sha256': '787e91589ddedb506bceb66e20e36d8ca6d62b3b9a6b301209ada1bf3f3c4bd4', 'bytes': 11094, 'identity': {'device': 2304, 'inode': 85358602, 'bytes': 11094, 'mtime_ns': 1793312011307913418, 'ctime_ns': 1793312011307913418, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
READINESS_SOURCES={'native': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/run_deadline32_rounds_v11.py', 'sha256': '9a980a2e9d04ee1506e8ba68c82c580e0cb2a114af75603c1449ccb491f99d8f', 'bytes': 40120, 'identity': {'device': 2304, 'inode': 85357793, 'bytes': 40120, 'mtime_ns': 1793311807216464222, 'ctime_ns': 1793311807228163371, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'contract': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/deadline_round_contract_v11.py', 'sha256': '5a39c2747533209384797e170e848f88f02c0679afc3aafd96615b90cb813870', 'bytes': 13733, 'identity': {'device': 2304, 'inode': 85357786, 'bytes': 13733, 'mtime_ns': 1793311807196428592, 'ctime_ns': 1793311807225163359, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'preparer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/prepare_round_study_namespace_v11.py', 'sha256': '9fd78ff77b8a5b01868e44f0e66f13ecc75e638169963a4c7f847607ea7e18a5', 'bytes': 30929, 'identity': {'device': 2304, 'inode': 85365407, 'bytes': 30929, 'mtime_ns': 1793315773836486974, 'ctime_ns': 1793315773836486974, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'reviewer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/review_continuous_physical192_observer_v5.py', 'sha256': '30ea4d2eb6d97b5ccbd04e262f7b4c45e47af268f7644f7893ad88deba47a133', 'bytes': 21011, 'identity': {'device': 2304, 'inode': 85353807, 'bytes': 21011, 'mtime_ns': 1793309436233689867, 'ctime_ns': 1793309543258994858, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'registry': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/continuous_physical192_registry_v5.py', 'sha256': '8cc5340708a73ffb97b16be4b96e72b3d5560ee0b371b7ffd8d67c4074cf76b4', 'bytes': 49518, 'identity': {'device': 2304, 'inode': 85353797, 'bytes': 49518, 'mtime_ns': 1793309467460439411, 'ctime_ns': 1793309543185873072, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
NAMESPACE_OVERLAY={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/metadata1200-namespace-overlay-original02/selected-study-preparer-namespace-overlay-v1.json', 'sha256': 'b46ec2ac35ec5a707cea3576f058c25e01f0e3205ca623036575c6e32b2d64e3', 'bytes': 5531, 'identity': {'device': 2304, 'inode': 85459361, 'bytes': 5531, 'mtime_ns': 1793315773847519747, 'ctime_ns': 1793315773847519747, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
CANDIDATE='c0acc8ad3aa411a00928b6f242b2e4a6299780b5a2991c75225d334c21af60f0'
REFERENCE='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'

def require(v,reason):
    if not v:raise ValueError(reason)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def read(p,h):
    require(p['identity']['mode']=='0o444','Immutable actual comparison evidence required')
    return json.loads(h.checked(p).read_bytes())

def namespace_expression(source,function):
    fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)and n.name==function)
    rows=[n.value for n in ast.walk(fn)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='namespace'for t in n.targets)]
    require(len(rows)==1,'Exactly one selected namespace expression required')
    value=copy.deepcopy(rows[0])
    for node in ast.walk(value):
        if isinstance(node,ast.Name)and node.id=='study_pin':node.id='study'
    return ast.dump(value,include_attributes=False)

def namespace_preflight(h,family):
    overlay=read(NAMESPACE_OVERLAY,h)
    require(overlay['schema']=='robotron-explicit-study-preparer-namespace-overlay-v1'
        and overlay['parent_family']==FAMILY and overlay['parent_source_peer']==PEER
        and overlay['parent_preparer']==family['sources']['prepare_round_study_v10.py']
        and overlay['selected_preparer']==READINESS_SOURCES['preparer']
        and overlay['unchanged_native_controller']==family['sources']['control_deadline32_rounds_v11.py'],
        'Exact selected metadata-only namespace overlay required')
    original=h.checked(overlay['parent_preparer']).read_text()
    selected=h.checked(overlay['selected_preparer']).read_text()
    old="namespace = 'deadline32-current-eval-quiescence-proof2s-'"
    new="namespace = 'deadline32-physical192-proof2s-'"
    require(original.count(old)==1 and selected==original.replace(old,new),
        'Only the selected one-prefix metadata producer correction is allowed')
    require(Path(overlay['selected_preparer']['path']).parent==Path(overlay['unchanged_native_controller']['path']).parent,
        'Selected preparer must retain exact F7 sibling paths')
    expression=namespace_expression(selected,'prepare')
    require(expression==namespace_expression(h.checked(overlay['unchanged_native_controller']).read_text(),'checked_config')
        ==overlay['namespace_expression_AST'],'Producer/controller namespace expressions differ')
    return dict(schema='robotron-source-only-metadata-namespace-preflight-v1',overlay=NAMESPACE_OVERLAY,
        parent_preparer=overlay['parent_preparer'],selected_preparer=overlay['selected_preparer'],
        unchanged_native_controller=overlay['unchanged_native_controller'],producer_controller_namespace_AST_equal=True,
        only_one_prefix_changed=True,scientific_payload_executed=False)

def prepare(comparison,sha,output,study,lease_recovery):
    h=load('_physical_metadata_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h.checked(FAMILY);h.checked(PEER)
    for v in SOURCES.values():h.checked(v)
    sp=h.pin(comparison.resolve());require(sp['sha256']==sha,'Exact actual comparison selection required')
    s=read(sp,h);family=read(FAMILY,h)
    namespace_check=namespace_preflight(h,family)
    require(s['schema']=='robotron-root-current-eval-quiescence-fresh-comparison-selection-v5'
        and s['status']=='ACTUAL_POST_MODE_CONTEXT_SELECTED' and s['source_family']==FAMILY
        and s['source_peer']==PEER,'Exact newly qualified physical comparison selection required')
    case=read(s['main_case'],h);joint=read(s['actual_physical_engineering'],h)
    require(case['schema']=='robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
        and joint['schema']=='robotron-original192-immutable-bootstrap-live-pidfd-joint-engineering-readiness-v4'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['case']==s['main_case'] and joint['input_inventory_authority']==case['input_inventory_authority']
        and joint['source_family']==family['typed_health_packet'],'Actual new physical main engineering association differs')
    capture=read(s['capture_result'],h)
    require(capture['state']=='captured_CPU_verified'and capture['endpoint']['sha256']==CANDIDATE,'Selected closed original04 c0acc capture required')
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
    association=read(s['fresh_capture_context_association'],h)
    qualification=read(association['original_capture_qualification'],h)
    profile_selection=read(s['Root_profile_selection'],h)
    cap=read(profile_selection['cap8_runtime_authority'],h)
    require(association['current_main_case']==s['main_case']
        and association['current_engineering_joint']==s['actual_physical_engineering']
        and association['capture_plan']==s['capture_plan'] and association['capture_result']==s['capture_result']
        and qualification['status']=='CAPTURE_CPU_VERIFIED_AND_ORIGINAL_SCOPE_CLOSED'
        and qualification['actual_original_exit']==0 and qualification['original_scope_released']is True,
        'Exact fresh capture qualification/current-context association required')
    inputs=[FAMILY,PEER,*family['sources'].values(),family['shared_profile_helper'],sp,s['main_case'],
        case['input_inventory_authority'],case['continuous']['source_authority'],s['actual_physical_engineering'],
        s['capture_result'],s['capture_plan'],s['fresh_capture_context_association'],association['original_capture_qualification'],
        profile_selection['cap8_runtime_authority'],cap['retained_unit_environment'],*association['supplemental_capture_guard_inputs'],s['Root_profile_selection'],
        *s['fresh_profile_closeouts'],profiles['reference_profile'],profiles['candidate_profile'],
        h.pin(Path(__file__).resolve()),NAMESPACE_OVERLAY,*SOURCES.values(),*READINESS_SOURCES.values()]
    for path,row in case['inputs'].items():inputs.append(dict(path=path,sha256=row['sha256'],bytes=row['identity']['bytes'],identity=row['identity']))
    # Current standalone window inputs are77 THIN3 ordinary source/metadata
    # pins; its64 FULL8 context holds were separately joined in the association.
    plan=read(s['capture_plan'],h)
    for value in plan['inputs']:
        require(type(value)is dict and set(value)=={'path','sha256','bytes'},'Exact THIN3 window source pin required')
        actual=h.pin(value['path'])
        require(all(actual[key]==expected for key,expected in value.items()),'Current capture source/control changed')
        inputs.append(actual)

    for v in inputs:h.checked(v)
    guard=load('_metadata_exact_resume_guard_preflight',h.checked(SOURCES['prepare_round_cpu_guard_with_exact_resume_v1.py']))
    held_input_classification=guard.preflight_held_inputs(list({v['path']:v for v in inputs}.values()))
    output.mkdir(mode=0o700)
    unit='robotron-c0acc-quiescence-namespace-metadata1200-'+sp['sha256'][:16]+'.service'
    job=dict(schema='robotron-selected-admission-study-CPU-preparation-v1',unit=unit,original_attempt=1,no_retry=True,
        output=str(output/'runtime'),study_directory=str(study),comparison_selection=sp,capture_result=s['capture_result'],
        candidate_sha256=CANDIDATE,reference_profile=profiles['reference_profile'],candidate_profile=profiles['candidate_profile'],
        deadline_readiness=s['actual_physical_engineering'],lease_recovery=h.pin(lease_recovery.resolve()),
        metadata_readiness_reuse_cache=SOURCES['metadata_same_invocation_readiness_cache_v1.py'],
        metadata_readiness_reuse_sources=READINESS_SOURCES,
        metadata_guard_preparer=SOURCES['prepare_round_cpu_guard_with_exact_resume_v1.py'],
        metadata_study_preparer=READINESS_SOURCES['preparer'],metadata_namespace_overlay=NAMESPACE_OVERLAY,
        metadata_namespace_preparation_preflight=namespace_check,
        inputs=list({v['path']:v for v in inputs}.values()))
    # Root must select the retained exact coordinator authority; never create a lease.
    require(read(job['lease_recovery'],h)['status']=='RESTORED_NEW_BOOT_COORDINATOR','Retained coordinator authority required')
    job['inputs'].append(job['lease_recovery'])
    jp=h.put(output/'job.json',job)
    control=load('_physical_metadata600_controller',h.checked(SOURCES['control_metadata600_v1.py']))
    cfg=dict(unit=unit,output=str(output/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',SOURCES['prepare_selected_metadata600_v1.py']['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',SOURCES['prepare_selected_metadata600_v1.py']['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=1200','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=1260,pins=[control.pin(v['path'])for v in[jp,*job['inputs']]])
    cp=h.put(output/'controller-config.json',cfg)
    return h.put(output/'prepared-physical-selected-metadata600-NOT-LAUNCHED.json',dict(job=jp,config=cp,
        actual_comparison_selection=sp,source=h.pin(Path(__file__).resolve()),
        held_input_classification_preflight=held_input_classification,metadata_guard_preparer=SOURCES['prepare_round_cpu_guard_with_exact_resume_v1.py'],
        Root_controller_argv=['/usr/bin/python3.12','-I','-B',SOURCES['control_metadata600_v1.py']['path'],'--execute','--config',cp['path'],
            '--expected-source-sha256',SOURCES['control_metadata600_v1.py']['sha256']],
        Root_close_argv=['/usr/bin/python3.12','-I','-B',SOURCES['close_metadata600_v1.py']['path'],'--close','--directory',str(output)],
        scientific_launch_qualified=False,actual_CPU_launched=False,quality_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--comparison-selection',type=Path)
    p.add_argument('--lease-recovery',type=Path);p.add_argument('--comparison-selection-sha256');p.add_argument('--output',type=Path);p.add_argument('--study-directory',type=Path);a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a.comparison_selection,a.comparison_selection_sha256,a.output,a.study_directory,a.lease_recovery)),flush=True)
    else:print('PLAN_ONLY_NO_READS_IMPORTS_TESTS_OR_ACTIONS')
