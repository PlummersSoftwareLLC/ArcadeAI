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
FAMILY={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/prepared-future-original05-typed-main-journal128-deadline13-SOURCE-ONLY-v1.json', 'sha256': '40dea9736e58f93d709316d683c5716abfc23ef8f2f6b2b4d5660c16efdc514f', 'bytes': 34223, 'identity': {'device': 2304, 'inode': 85460150, 'bytes': 34223, 'mtime_ns': 1793335975145224755, 'ctime_ns': 1793335975145224755, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PARENT_COMPARISON={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/fresh-original05-typed-Adam-cap8-profile-preparation-original05/actual-4ab-b231-fresh-comparison-prerequisites-original01/Root-physical192-comparison-selection.json', 'sha256': 'a396a559c80442e2507d0aba9f76d43d0a0658043ccce466017d67343467205c', 'bytes': 12394, 'identity': {'device': 2304, 'inode': 85460117, 'bytes': 12394, 'mtime_ns': 1793335615920224471, 'ctime_ns': 1793335615920224471, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
SOURCES={'prepare_selected_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/metadata1200-original01/prepare_selected_typed128_metadata1200_v7.py', 'sha256': 'fa526c470e6b49f69c154767ad119d68e23156a9bfa862cb31b0081e079164a1', 'bytes': 6117, 'identity': {'device': 2304, 'inode': 85460159, 'bytes': 6117, 'mtime_ns': 1793336111830197632, 'ctime_ns': 1793336111830197632, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'control_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/metadata1200-original01/control_metadata1200_v2.py', 'sha256': '5e5951cda9607c6e1cfe2c40435bd84568d211b0ce6796e9bee4d129ca9671a2', 'bytes': 17293, 'identity': {'device': 2304, 'inode': 85460155, 'bytes': 17293, 'mtime_ns': 1793336111809875683, 'ctime_ns': 1793336111809875683, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'close_metadata600_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/metadata1200-original01/close_metadata1200_v2.py', 'sha256': 'bdb7a7c5052f27caf63c9756e93bbf005e82a17b968e974a182550920f61f933', 'bytes': 5164, 'identity': {'device': 2304, 'inode': 85460157, 'bytes': 5164, 'mtime_ns': 1793336111823992685, 'ctime_ns': 1793336111823992685, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'metadata_same_invocation_readiness_cache_v1.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/metadata1200-original01/metadata_same_invocation_typed128_cache_v3.py', 'sha256': 'f922b53cd612ec68e187e4dbd0f4717c53dc36ef6d9eaaac9f4331250723f8d2', 'bytes': 15139, 'identity': {'device': 2304, 'inode': 85460153, 'bytes': 15139, 'mtime_ns': 1793336111797107228, 'ctime_ns': 1793336111797107228, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'prepare_round_cpu_guard_with_exact_resume_v1.py': {'bytes': 11094, 'identity': {'bytes': 11094, 'ctime_ns': 1793335975049163422, 'device': 2304, 'inode': 85460133, 'mode': '0o444', 'mtime_ns': 1793335975049020894, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/prepare_round_cpu_guard_v10.py', 'sha256': '89be5b822f48cbff2b455e46fad8e8add2fd672cf0c0ab8a3f90d4d1cbc1218b'}}
READINESS_SOURCES={'native': {'bytes': 40120, 'identity': {'bytes': 40120, 'ctime_ns': 1793335974972163200, 'device': 2304, 'inode': 85460125, 'mode': '0o444', 'mtime_ns': 1793335974971888991, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/run_deadline32_rounds_v11.py', 'sha256': '82dfcacb1cf8b6ab6f52269a7eab0067bfc4b5a603917fea80c9d963cd2d4a0d'}, 'contract': {'bytes': 18182, 'identity': {'bytes': 18182, 'ctime_ns': 1793335974956163154, 'device': 2304, 'inode': 85460123, 'mode': '0o444', 'mtime_ns': 1793335974955597904, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/deadline_round_contract_v11.py', 'sha256': '76c4e83c564f9c3148ae6b3ea006d3f57e42ae345dd4dcd1c66a409218261659'}, 'preparer': {'bytes': 35713, 'identity': {'bytes': 35713, 'ctime_ns': 1793335975061217089, 'device': 2304, 'inode': 85460135, 'mode': '0o444', 'mtime_ns': 1793335975061217089, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/prepare_round_study_v10.py', 'sha256': '589f64a3765f6888c55c42ba53db932c0c4f99956cef23759311fa85f33233c6'}, 'reviewer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/review_continuous_physical192_observer_v5.py', 'sha256': '30ea4d2eb6d97b5ccbd04e262f7b4c45e47af268f7644f7893ad88deba47a133', 'bytes': 21011, 'identity': {'device': 2304, 'inode': 85353807, 'bytes': 21011, 'mtime_ns': 1793309436233689867, 'ctime_ns': 1793309543258994858, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'registry': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/continuous_physical192_registry_v5.py', 'sha256': '8cc5340708a73ffb97b16be4b96e72b3d5560ee0b371b7ffd8d67c4074cf76b4', 'bytes': 49518, 'identity': {'device': 2304, 'inode': 85353797, 'bytes': 49518, 'mtime_ns': 1793309467460439411, 'ctime_ns': 1793309543185873072, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
NAMESPACE_OVERLAY={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/future-original05-typed-main-journal128-family-original01/metadata1200-original01/selected-four-fresh-typed128-preparer-source-composition-v1.json', 'sha256': '2ebb108de77ed0bdd01e5f6ffd59f522bca507fe06ec5030d383d26c4882a29b', 'bytes': 4550, 'identity': {'device': 2304, 'inode': 85460161, 'bytes': 4550, 'mtime_ns': 1793336111835018927, 'ctime_ns': 1793336111835018927, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
CANDIDATE='4ab677004e8a178f69d4438583a07d00a76f3b90e09eb08870ad0528fc08f871'
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
    composition=read(NAMESPACE_OVERLAY,h)
    require(composition['schema']=='robotron-explicit-four-fresh-typed128-preparer-source-composition-v1'
        and composition['selected_family']==FAMILY
        and composition['parent_preparer']==family['typed_capture_eligibility_parent']
        and composition['selected_preparer']==READINESS_SOURCES['preparer']
        and composition['native_controller']==family['sources']['control_deadline32_rounds_v11.py']
        and composition['exact_source_derivation']==family['source_derivation']
        and composition['all_four_jobs_fresh']is True
        and composition['old_score_jobs_or_R1_qualification_reused']is False,
        'Exact selected typed-capture/capacity source composition required')
    derivation=read(family['source_derivation'],h)
    for row in derivation['sources'].values():
        for key in ('parent','selected','patch'):h.checked(row[key])
    selected=h.checked(READINESS_SOURCES['preparer']).read_text()
    controller=h.checked(family['sources']['control_deadline32_rounds_v11.py']).read_text()
    require(Path(READINESS_SOURCES['preparer']['path']).parent==Path(family['sources']['control_deadline32_rounds_v11.py']['path']).parent,
        'Actual source siblings required')
    require(namespace_expression(selected,'prepare')==namespace_expression(controller,'checked_config'),
        'Current-parser producer/controller namespace expressions differ')
    require("job.name == 'job.json'"in controller and "h.put(directory/'job.json', job)"in selected,
        'All four standard fresh job.json paths required')
    return dict(schema='robotron-source-only-metadata-namespace-preflight-v1',overlay=NAMESPACE_OVERLAY,
        parent_preparer=composition['parent_preparer'],selected_preparer=READINESS_SOURCES['preparer'],
        unchanged_native_controller=family['sources']['control_deadline32_rounds_v11.py'],
        producer_controller_namespace_AST_equal=True,exact_frozen_source_composition_verified=True,
        all_four_standard_job_paths_equal=True,scientific_payload_executed=False)

def prepare(comparison,sha,output,study,lease_recovery):
    h=load('_physical_metadata_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h.checked(FAMILY)
    for v in SOURCES.values():h.checked(v)
    sp=h.pin(comparison.resolve());require(sp['sha256']==sha,'Exact actual comparison selection required')
    s=read(sp,h);family=read(FAMILY,h)
    namespace_check=namespace_preflight(h,family)
    require(s['schema']=='robotron-root-current-eval-quiescence-fresh-comparison-selection-v5'
        and s['status']=='ACTUAL_POST_MODE_CONTEXT_SELECTED' and s['source_family']==FAMILY
        and s['source_peer']['identity']['mode']=='0o444','Exact newly qualified physical comparison selection required')
    parent=read(PARENT_COMPARISON,h)
    require(s['parent_comparison_selection']==PARENT_COMPARISON and s['all_four_new_legs_are_fresh']is True,
        'Explicit immutable Root selection of the whole new family required')
    retained={k:v for k,v in s.items()if k not in ('source_family','source_peer','parent_comparison_selection','all_four_new_legs_are_fresh')}
    require(retained=={k:v for k,v in parent.items()if k not in ('source_family','source_peer')},
        'Only the explicit whole-family/peer selection may differ from exact four-profile comparison facts')
    peer=read(s['source_peer'],h)
    require(peer['selected_family']==FAMILY and peer['source_and_ABI_GO']is True,
        'Exact independent new-family source peer required')
    case=read(s['main_case'],h);joint=read(s['actual_physical_engineering'],h)
    require(case['schema']=='robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
        and joint['schema']=='robotron-original192-immutable-bootstrap-live-pidfd-joint-engineering-readiness-v4'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['case']==s['main_case'] and joint['input_inventory_authority']==case['input_inventory_authority']
        and joint['source_family']==family['typed_health_packet'],'Actual new physical main engineering association differs')
    capture=read(s['capture_result'],h)
    require(capture['state']=='captured_CPU_verified'and capture['endpoint']['sha256']==CANDIDATE,'Selected closed typed original05 4ab capture required')
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
    inputs=[FAMILY,s['source_peer'],PARENT_COMPARISON,*family['sources'].values(),family['typed_capture_eligibility_parent'],family['typed_capture_closed_verifier'],family['source_derivation'],family['main_journal_capacity_overlay'],family['observer_source_map'],family['shared_profile_helper'],sp,s['main_case'],
        case['input_inventory_authority'],case['continuous']['source_authority'],s['actual_physical_engineering'],
        s['capture_result'],s['capture_plan'],s['fresh_capture_context_association'],association['original_capture_qualification'],
        profile_selection['cap8_runtime_authority'],cap['retained_unit_environment'],*association['supplemental_capture_guard_inputs'],s['Root_profile_selection'],
        *s['fresh_profile_closeouts'],profiles['reference_profile'],profiles['candidate_profile'],
        h.pin(Path(__file__).resolve()),NAMESPACE_OVERLAY,*SOURCES.values(),*READINESS_SOURCES.values()]
    for path,row in case['inputs'].items():inputs.append(dict(path=path,sha256=row['sha256'],bytes=row['identity']['bytes'],identity=row['identity']))
    # Selected original05 amended window inputs are89 THIN3 ordinary source/metadata
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
    unit='robotron-4ab-typed128-metadata1200-'+sp['sha256'][:16]+'.service'
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
