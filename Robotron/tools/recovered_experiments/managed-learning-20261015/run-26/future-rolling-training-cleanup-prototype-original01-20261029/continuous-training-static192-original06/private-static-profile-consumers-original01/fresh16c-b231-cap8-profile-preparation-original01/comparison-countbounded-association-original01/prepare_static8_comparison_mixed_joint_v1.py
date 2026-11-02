"""Comparison-only association for already prepared7da profiles and NEW mixed engineering.

Default inert. Never prepares/reruns CPU scopes, probes, reads raw samples/model
bodies, launches jobs or changes controls. Root supplies only independently
closed immutable evidence. Existing7da profile source authority stays exact.
"""
import argparse,hashlib,importlib.util,json,math,os,sys
from pathlib import Path

PROFILE_PREPARER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/fresh16c-b231-cap8-profile-preparation-original01/prepare_fresh_static8_policy_profiles_v2.py', 'sha256': '7da958b7ffc2a7fb6a8b39a970886f86352226fc92a74e37dc363015cf2c561a', 'bytes': 29900, 'identity': {'device': 2304, 'inode': 85230511, 'bytes': 29900, 'mtime_ns': 1793284609080930169, 'ctime_ns': 1793284609080930169, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
MIXED={'packet': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/new-static-context-engineering-original01-preparation/count-bounded-long-original02-preparation/prepared-countbounded-long-and-mixed-static192-joint-SOURCE-ONLY-NOT-LAUNCHED-v2.json', 'sha256': 'f3d98132b6bd90f14acd23eaf8c9c64dcf3df384e127a100e5066c50d5394754', 'bytes': 17554, 'identity': {'device': 2304, 'inode': 85231223, 'bytes': 17554, 'mtime_ns': 1793285193026576171, 'ctime_ns': 1793285193026576171, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/new-static-context-engineering-original01-preparation/count-bounded-long-original02-preparation/independent-countbounded-static192-long-and-mixed-joint-v2-source-peer-v1.json', 'sha256': '073b2ebc412a64f30d4437fbbe72ed0e838301463b958b195d29695a00cf7b4f', 'bytes': 14642, 'identity': {'device': 2304, 'inode': 85231262, 'bytes': 14642, 'mtime_ns': 1793285231949806172, 'ctime_ns': 1793285231949806172, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'joint_producer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/new-static-context-engineering-original01-preparation/count-bounded-long-original02-preparation/finalize_static192_countbounded_engineering_v2.py', 'sha256': '43d606db51bd6ae915f18621e656632b11d2b43b231fdc73ae8ebb067d5e93a3', 'bytes': 20272, 'identity': {'device': 2304, 'inode': 85231011, 'bytes': 20272, 'mtime_ns': 1793285043447981377, 'ctime_ns': 1793285193011951326, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'long_closer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/new-static-context-engineering-original01-preparation/count-bounded-long-original02-preparation/close_static192_countbounded_long_v2.py', 'sha256': 'be04ed81f39326dbbcfe8544c2a55f65407e864bf061fa033cc46dbab25e6ede', 'bytes': 10162, 'identity': {'device': 2304, 'inode': 85230818, 'bytes': 10162, 'mtime_ns': 1793284939791694838, 'ctime_ns': 1793285193002951298, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
CANDIDATE='16c3e3294d97e8bd9899f753a311cd3c958e5fba1a1a5b765f29955a52b2b22d'
REFERENCE='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
LONG_CONTRACT='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S'

def require(ok,reason):
    if not ok:raise ValueError(reason)

def load_profile():
    path=Path(PROFILE_PREPARER['path']);raw=path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==PROFILE_PREPARER['sha256'],'Exact retained7da profile preparer required')
    spec=importlib.util.spec_from_file_location('_retained_static8_profiles7da',path);base=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base;exec(compile(raw,str(path),'exec'),base.__dict__)
    h,api=base.dependencies();h.checked(PROFILE_PREPARER)
    for entry in MIXED.values():h.checked(entry)
    return base

def mixed_engineering_association(joint_pin,s,case,h,read,FIXED):
    joint=read(joint_pin,h);family=read(FIXED['DL3_family'],h);mapping=read(FIXED['observer_map'],h)['observer_sources']
    require(joint['schema']=='robotron-continuous-static192-joint-engineering-readiness-v1'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY' and joint['source']==MIXED['joint_producer']
        and joint['case']==s['main_case'] and joint['input_inventory_authority']==case['input_inventory_authority']
        and joint['source_family']==family['typed_health_packet'] and joint['observer_sources']==mapping
        and joint['actual_held_input_count']==len(case['inputs']) and joint['historical_main_input_count']==247
        and joint['proof_gap_contract']=='robotron-main-proof-gap-2s-v1' and joint['maximum_gap_s']==2.0
        and joint['main_health_profile']=='STATIC_ORIGINAL192_NO_FAULT_ADOPTION' and joint['interval_s']==.2
        and joint['long_work_contract']==LONG_CONTRACT and joint['all_original_engineering_scopes_closed_at_recorded_closer']is True
        and joint['legacy_warmup_and_abort_only_reused_with_same_static8_case_inventory_and_sources']is True
        and joint['failed_original600_scope_not_reused_or_requalified']is True
        and joint['scientific_launch_qualified']is joint['quality_qualified']is joint['promotion']is False,
        'Exact new mixed engineering joint/source/domain required; failed old600 proof is excluded')
    authority=read(joint['job'],h)
    require(authority['schema']=='robotron-root-finalize-countbounded-static192-engineering-job-v2'
        and authority['case']==s['main_case'] and set(authority['contexts'])==set(joint['engineering'])=={'warmup','long','abort'},
        'Mixed joint original context authority differs')
    parent_births=set();worker_births=set()
    for mode,row in joint['engineering'].items():
        selected=authority['contexts'][mode]
        require(all(row[k]==selected[k]for k in ('prepared_contexts','launch_index','closeout')),'Per-mode context/index/closeout join differs')
        close=read(row['closeout'],h);new=mode=='long'
        require(close['schema']==('robotron-static192-countbounded-long-original-engineering-closeout-v2'if new else'robotron-static192-original-engineering-closeout-v1')
            and close['source']==(MIXED['long_closer']if new else FIXED['engineering_closer'])
            and close['status']=='PASS_ENGINEERING_ONLY' and close['kind']=='main-static192' and close['mode']==mode
            and close['launch_index']==row['launch_index'] and close['worker_lifecycle']==row['lifecycle']
            and close['actual_probe_result']==row['actual_probe_result']
            and close['original_parent_actual_exit']==row['original_parent_actual_exit']==0
            and close['worker_actual_exit']==row['worker_actual_exit']==(1 if mode=='abort'else 0)
            and close['all_original_births_units_cgroups_and_tmpfs_control_absent']is True
            and close['actual_parent_CPU_cores']==2 and close['actual_parent_memory_bytes']==4<<30
            and close['actual_parent_runtime_s']==(1800 if new else 780),
            'Exact per-mode closer/source/normal-parent/expected-worker/resources required')
        owner=read(close['original_live_owner'],h);terminal=read(close['parent_terminal'],h)
        expected=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],MainPID='0',ExecMainPID=str(owner['pid']),
            ExecMainCode='1',ExecMainStatus='0',NRestarts='0',Restart='no',CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),
            MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='30min'if new else'13min',TimeoutStopUSec='5s',SendSIGKILL='no')
        require(all(terminal.get(k)==v for k,v in expected.items()) and close['released_properties']['LoadState']=='not-found',
            'Retained actual parent terminal/resource/closure differs')
        pair=(owner['pid'],owner['birth']);require(pair not in parent_births,'Parent incarnation reused');parent_births.add(pair)
        report=read(row['actual_probe_result'],h)
        require(report['schema']==('robotron-static192-health-countbounded-native-interface-probe-v2'if new else'robotron-static192-health-actual-native-interface-probe-v1')
            and report['status']=='PASS_ENGINEERING_INTERFACE_ONLY' and report['mode']==mode
            and report['sources']==mapping and report['observer_lifecycle']==row['lifecycle']
            and report['case_inventory_authority']==case['input_inventory_authority']
            and report['maximum_gap_s']==2.0 and report['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'
            and report['main_health_profile']=='STATIC_ORIGINAL192_NO_FAULT_ADOPTION', 'Exact mixed probe/case/static8 contract differs')
        native=read(report['original_job'],h);life=read(row['lifecycle'],h);worker=read(life['worker_job'],h)
        require(native['main_binding']==s['main_case'] and life['native_job']==report['original_job']
            and worker['native_job']==report['original_job'] and worker['case']==s['main_case'] and worker['sources']==mapping
            and worker['schema']=='robotron-continuous-static192-observer-proof2s-job-v1' and worker['maximum_gap_s']==2.0
            and worker['initial_samples']==100 and worker['interval_s']==.2 and worker['work_s']==4200 and worker['runtime_s']==4260
            and worker['parent']['pid']==owner['pid'] and worker['parent']['birth']==owner['birth']
            and worker['parent']['invocation_id']==owner['invocation_id']
            and life['all_original_processes_reaped']is life['original_scope_released']is life['launcher_birth_absent']is True,
            'Actual worker/parent/case/static8/source/unchanged proof bounds differ')
        outcome=read(life['outcome'],h);wo=read(outcome['owner'],h);wp=(wo['pid'],wo['birth'])
        require(wp not in worker_births,'Worker incarnation reused');worker_births.add(wp)
        require(close['accepted_samples']==row['accepted_samples'] and close['unaccepted_samples']==row['unaccepted_samples']
            and outcome['all_writer_threads_stopped']is True and outcome['uncommitted_raw']==[], 'Durable count/worker closure differs')
        if new:
            require(joint['lifecycle']==row['lifecycle'] and joint['independent_raw_review']==row['independent_raw_review']
                and report['long_work_contract']==close['long_work_contract']==LONG_CONTRACT
                and report['long_minimum_work_s']==600 and report['long_maximum_work_s']==1200 and report['long_minimum_observed_samples']==3000
                and type(report['actual_long_work_s'])in(int,float) and math.isfinite(report['actual_long_work_s'])
                and 600<=report['actual_long_work_s']==close['actual_long_work_s']<=1200
                and type(report['last_validated_long_count'])is int
                and report['last_validated_long_count']==close['last_validated_long_count']>=3000,
                'New long must satisfy both600s and validated3000 samples within1200s')
        if mode=='abort':
            require(row['independent_raw_review']is None and report['independently_replayed_raw_review']is None
                and life['success']is False and outcome['success']is False,'Expected abort remains a failed worker, not a scientific pass')
        else:
            raw=read(row['independent_raw_review'],h)
            require(raw==report['independently_replayed_raw_review'] and raw['status']=='PASS' and raw['lifecycle']==row['lifecycle']
                and raw['original_job']==life['worker_job'] and raw['original_sources']==mapping
                and raw['accepted_samples']==close['accepted_samples']>=(3000 if new else 101)
                and raw['full_main_input_count']==len(case['inputs']) and raw['verified_maximum_gap_s']==2.0
                and raw['TRAIN155_originals_and_EVAL37_once_partition_verified']is True
                and outcome['success']is True and life['success']is True,
                'Actual same-mode independent complete raw-review metadata required')
    require(len(parent_births|worker_births)==6,'Mixed original parent/worker identities overlap')
    return joint

def prepare_comparison_selection(path,sha,output,engineering_joint,engineering_sha):
    base=load_profile();h,api=base.dependencies();FIXED=base.FIXED;read=base.read
    s,sp,case=base.selection(path,sha,h);result,cpu=base.capture(h)
    joint_pin=h.pin(Path(engineering_joint).resolve());require(joint_pin['sha256']==engineering_sha,'Exact actual engineering joint selected')
    mixed_engineering_association(joint_pin,s,case,h,read,FIXED)
    require(s['old_measurement_was_not_a_policy_quality_rejection']is True,'Explicit valid-policy/new-infrastructure selection required')
    root=Path(s['profile_root']);adoptions={};closed_inputs=[]
    for role in ('reference','candidate'):
        for mode in ('canonical','frozen'):
            directory=root/(role+'-'+mode+'-CPU-original01')
            packet=read(h.pin(directory/'prepared-NOT-LAUNCHED.json'),h)
            require(packet['profile_selection']==sp and packet['role']==role and packet['mode']==mode
                and packet['source']==PROFILE_PREPARER,'Every profile must be from this exact fresh selection/source')
            name='independent-original-canonical-CPU-closeout.json'if mode=='canonical'else'independent-original-profile-scope-closeout.json'
            cp=h.pin(directory/name);closed=read(cp,h)
            require(closed['status']=='PASS' and closed['actual_exit']==0
                and closed['all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified']is True
                and closed['preparer_source']==packet['source'],'Actual independently closed fresh original CPU required')
            job=read(packet['job'],h)
            require(job['checkpoint']['sha256']==(CANDIDATE if role=='candidate'else REFERENCE),'Profile policy binding differs')
            if mode=='frozen':
                ap=closed['profile_adoption'];adopted=read(ap,h)
                require(adopted['schema']=='robotron-frozen-profile-CPU-independent-adoption-v1'
                    and adopted['status']=='PASS' and adopted['original_job']==packet['job']
                    and adopted['actual_exit']==0 and adopted['original_scope_released']is True
                    and adopted['all_Q_bytes_and_actions_match']is True,'Fresh exact frozen adoption differs')
                adoptions[role]=ap
            closed_inputs.append(cp)
    output=Path(output).absolute();require(output.resolve()==output and not output.exists()and output.parent.is_dir(),'Fresh comparison metadata directory required')
    output.mkdir(mode=0o700)
    qualification=h.put(output/'original-valid-capture-qualification.json',dict(
        schema='robotron-root-original-valid-capture-qualification-v1',status='CAPTURE_CPU_VERIFIED_AND_ORIGINAL_SCOPE_CLOSED',
        capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],actual_original_exit=0,original_scope_released=True,
        numerical_CPU=FIXED['capture_CPU'],original_CPU_release=FIXED['capture_CPU_release'],original_observer_release=FIXED['capture_observer_release'],
        policy_checkpoint_sha256=CANDIDATE,new_exposure_credited=False,quality_qualified=False))
    reuse=h.put(output/'valid-capture-new-context-selection.json',dict(
        schema='robotron-root-valid-policy-new-infrastructure-context-selection-v1',status='ACTUAL_VALID_CAPTURE_SELECTED_FOR_NEW_COMPARISON',
        capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],new_main_source_authority=case['continuous']['source_authority'],
        new_original_membership=case['continuous']['original_membership'],original_capture_qualification=qualification,
        capture_is_independently_qualified_and_closed=True,old_measurement_was_not_a_policy_quality_rejection=True,
        all_four_comparison_legs_are_fresh=True,no_original_measurement_job_is_retried=True,no_old_score_or_cutoff_pool_is_reused=True,
        actual_old_capture_exposure_not_new_exposure=True,selected_policy=CANDIDATE,Root_profile_selection=sp))
    selected=h.put(output/'Root-DL3-comparison-selection.json',dict(
        schema='robotron-root-continuous-static192-fresh-comparison-selection-v1',status='ACTUAL_POST_MODE_CONTEXT_SELECTED',
        mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',main_case=s['main_case'],candidate_selection_mode='PRIOR_VALID_CAPTURE_NEW_INFRA_CONTEXT',
        capture_root=str(Path(FIXED['capture_result']['path']).parent),capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],
        policy_reevaluation_authority=reuse,current_runtime_profiles=dict(main_source_authority=case['continuous']['source_authority'],
        reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate']),source_family=FIXED['DL3_family'],source_peer=FIXED['DL3_peer'],
        fresh_profile_closeouts=closed_inputs,Root_profile_selection=sp,actual_static_engineering=joint_pin,launch_qualified=False,quality_qualified=False))
    return h.put(output/'prepared-DL3-prerequisites-NOT-LAUNCH-QUALIFIED.json',dict(
        selection=selected,reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate'],
        original_capture_qualification=qualification,policy_reevaluation_authority=reuse,source=h.pin(Path(__file__).resolve()),profile_preparer_source=PROFILE_PREPARER,mixed_engineering_sources=MIXED,
        actual_four_native_jobs=None,actual_metadata_CPU=None,actual_exact_job_guards=None,actual_review_precommit_CPU=None,
        scientific_launch_qualified=False,quality_qualified=False,CPU_or_scientific_job_launched=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-comparison-selection',action='store_true')
    p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--directory',type=Path)
    p.add_argument('--engineering-joint',type=Path);p.add_argument('--engineering-joint-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not a.prepare_comparison_selection:print('SOURCE_ONLY_INERT_NO_READS_ACTIONS_OR_JOB_PREPARATION');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.expected_source_sha256,'Exact selected association consumer required')
    require(all((a.selection,a.selection_sha256,a.directory,a.engineering_joint,a.engineering_joint_sha256)),'Actual immutable selection/joint and exclusive output required')
    result=prepare_comparison_selection(a.selection,a.selection_sha256,a.directory,a.engineering_joint,a.engineering_joint_sha256)
    print(json.dumps(dict(prepared=result,profile_CPU_repeated=False,scientific_payload_launched=False)),flush=True)

if __name__=='__main__':main()
