"""Fresh physical-original192 cap8 CPU profiles for valid16c and protected3045. Default inert.

Root-only explicit modes prepare metadata or reuse the unchanged original CPU
closer. No mode launches a CPU/service/game/scientific job or changes learning.
Unknown current case/engineering/cap evidence is supplied by immutable Root
selection after its real qualifications; no old profile/score is adopted.
"""
import argparse,hashlib,importlib.util,json,os,re,sys
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CANDIDATE='16c3e3294d97e8bd9899f753a311cd3c958e5fba1a1a5b765f29955a52b2b22d'
REFERENCE='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
FIXED={'profile_api': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/prepare_and_close_profile_cpu_v2.py', 'sha256': 'dc4b811b57b05e0a439ef2345d0dc73f6db42578b672511d13ec08ddda65ff8c', 'bytes': 10053, 'identity': {'device': 2304, 'inode': 84708521, 'bytes': 10053, 'mtime_ns': 1793221310159594380, 'ctime_ns': 1793221310159594380, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'benchmark': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/benchmark_sidecar_inference.py', 'sha256': '39d90c6dc70d69a4fef4c7244868819ddd06f7cc4283998d821632cf0ce2bde5', 'bytes': 16421, 'identity': {'device': 2304, 'inode': 79965881, 'bytes': 16421, 'mtime_ns': 1792122331445724145, 'ctime_ns': 1792122331445724145, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'frozen_driver': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/check_frozen_profile_cpu_v2.py', 'sha256': '941333f31ec4a1f4e83a9c4ebc7cc639459b0654057e3237daf52f424bf7ae7d', 'bytes': 3034, 'identity': {'device': 2304, 'inode': 84702870, 'bytes': 3034, 'mtime_ns': 1793160670301732716, 'ctime_ns': 1793160670301732716, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'adopter': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/adopt_profile_scope_v2.py', 'sha256': '30d6fb41599a6eb2977421dd1cb2a5638bc6b148c349cfea2b10d7ab7372f8bb', 'bytes': 7225, 'identity': {'device': 2304, 'inode': 84704201, 'bytes': 7225, 'mtime_ns': 1793171634710878615, 'ctime_ns': 1793171634710878615, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py', 'sha256': '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'bytes': 17290, 'identity': {'device': 2304, 'inode': 81930188, 'bytes': 17290, 'mtime_ns': 1792424008109022468, 'ctime_ns': 1792424257834393599, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'observer_map': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-physical-original192-v4-cohort-original03/prospective-prefix-bound-physical192-eight-role-observer-source-map-v3.json', 'sha256': '5e5c77c2554dacbe86b9ac0cd38eebe09d6eb1cbfe427310482dfdc8fd0b2bf1', 'bytes': 5859, 'identity': {'device': 2304, 'inode': 85333788, 'bytes': 5859, 'mtime_ns': 1793296831684141031, 'ctime_ns': 1793296831684141031, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'protected_reference_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03/R1/job.json', 'sha256': 'f34511e9e860342887681958fadc7e465e7b49a7c115d15dd36e57a9cf0b0d33', 'bytes': 95725, 'identity': {'device': 2304, 'inode': 80763099, 'bytes': 95725, 'mtime_ns': 1793055492480886407, 'ctime_ns': 1793055492480886407, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/window-plan.json', 'sha256': '43ace243055948eba395f97ba96faef339997c5d94cec6b50aea3104dbe9ae68', 'bytes': 22728, 'identity': {'device': 2304, 'inode': 85091488, 'bytes': 22728, 'mtime_ns': 1793255608603967147, 'ctime_ns': 1793255608603967147, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/result.json', 'sha256': 'a8dc3dfa27cec1f2c050fe6faef4b5229c11cf7b01d54b5bde77c7f2a9942536', 'bytes': 1377, 'identity': {'device': 2304, 'inode': 85095142, 'bytes': 1377, 'mtime_ns': 1793259346605715431, 'ctime_ns': 1793259346605715431, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/endpoint-CPU.json', 'sha256': 'd9dfb33918a98a3164f503fafe7bc6ac4dfca1df15c252b531f4d0dd1eca8990', 'bytes': 2112, 'identity': {'device': 2304, 'inode': 85095139, 'bytes': 2112, 'mtime_ns': 1793259345749905132, 'ctime_ns': 1793259345749905132, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_threshold': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/first-threshold.raw.json', 'sha256': '9258dd24a08677bc77bfccd93be7f0b159f2d2b502da06e30a0ff9d7f381ebc1', 'bytes': 123537, 'identity': {'device': 2304, 'inode': 85095121, 'bytes': 123537, 'mtime_ns': 1793259248515085077, 'ctime_ns': 1793259248515085077, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_anchor': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/anchor.raw.json', 'sha256': 'df466635c6496f934e4bb5f4b282e8489bed3d62839a165ee4f11f48b2a3455d', 'bytes': 130987, 'identity': {'device': 2304, 'inode': 85091502, 'bytes': 130987, 'mtime_ns': 1793255643320103002, 'ctime_ns': 1793255643320103002, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/CPU-owned-release.json', 'sha256': '497d229164572c3585a529c8d988211398bbb4f5be68e1365ce43c811c31454f', 'bytes': 33674, 'identity': {'device': 2304, 'inode': 85095141, 'bytes': 33674, 'mtime_ns': 1793259346595313573, 'ctime_ns': 1793259346595313573, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_observer_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/ROOT-original-observer03-owned-release.json', 'sha256': '906d4711761f90aea0b9231ffc3f15cb24f292ed64149eeb80bbfa13ae1281e3', 'bytes': 13051, 'identity': {'device': 2304, 'inode': 85095222, 'bytes': 13051, 'mtime_ns': 1793259543263658909, 'ctime_ns': 1793259543263658909, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'engineering_closer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/physical-original192-v4-cohort-engineering-original02-preparation/close_physical192_engineering_v2.py', 'sha256': 'd6c5c36eae4aa572e5cb267e997611c498235b81155ecf3dabc3c0083db27392', 'bytes': 10640, 'identity': {'device': 2304, 'inode': 85333809, 'bytes': 10640, 'mtime_ns': 1793296943121816746, 'ctime_ns': 1793297368870129458, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_family': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/prepared-prefix-bound-physical-profile-deadline13-SOURCE-ONLY-v1.json', 'sha256': 'eb5070a9ea134c5b16e553e024c554a948d70f469d862d93b7867ae9e9d675bd', 'bytes': 15750, 'identity': {'device': 2304, 'inode': 85333934, 'bytes': 15750, 'mtime_ns': 1793297226461341101, 'ctime_ns': 1793297226461341101, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/independent-prefix-bound-private-deadline13-source-and-consumer-peer-v1.json', 'sha256': '73d6c9bcd637d20ff03e54f1c97d6cbd8d2eb471c13c381a46f8080d5ace0234', 'bytes': 40389, 'identity': {'device': 2304, 'inode': 85334110, 'bytes': 40389, 'mtime_ns': 1793297575963658137, 'ctime_ns': 1793297575963658137, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'engineering_finalizer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/physical-original192-v4-cohort-engineering-original02-preparation/finalize_physical192_engineering_v2.py', 'sha256': '7e6f3d4cef9bd899d19ce3037e696f60c7741cea7d16da5af3520cb6e0965739', 'bytes': 18803, 'identity': {'device': 2304, 'inode': 85333810, 'bytes': 18803, 'mtime_ns': 1793297158552209540, 'ctime_ns': 1793297368876129478, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'shared_domain_helper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/physical_profile_contract_v3.py', 'sha256': '16f842452a56d5a2ae9f3c01b6cd4581623d2463c333ed785e8b8ea53a0909e8', 'bytes': 6254, 'identity': {'device': 2304, 'inode': 85234721, 'bytes': 6254, 'mtime_ns': 1793291613694928533, 'ctime_ns': 1793291613694928533, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_case': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/fresh-v4-cohort-binding-original01-preparation/actual-new-v4-physical192-case-original01/new-v4-physical192-main-case.json', 'sha256': '6f7b6e4340030e301fd410947b527a14d957bc6392e9576a4f85a889fd8ce162', 'bytes': 1296548, 'identity': {'device': 2304, 'inode': 85333952, 'bytes': 1296548, 'mtime_ns': 1793297300889794305, 'ctime_ns': 1793297300889794305, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_inventory': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/fresh-v4-cohort-binding-original01-preparation/actual-new-v4-physical192-case-original01/exact-held-input-inventory.json', 'sha256': '19465e464242bae3c96ee385625995a72e731d69c76d62f227db80331e734a03', 'bytes': 259573, 'identity': {'device': 2304, 'inode': 85333951, 'bytes': 259573, 'mtime_ns': 1793297300871663044, 'ctime_ns': 1793297300871663044, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
PRIVATE_ENV={'ROBOTRON_CONTINUOUS_TRAINING_MODE':'0','ROBOTRON_ROLLING_TRAINING_CLEANUP':'0','ROBOTRON_CONTINUOUS_STARTUP_HOLD':'0','DQN_MAX_SAMPLES_PER_FRAME':'8'}

def require(ok,reason):
    if not ok:raise ValueError(reason)

def load(name,entry):
    p=Path(entry['path']);require(hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],'Selected existing source changed')
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def dependencies():
    h=load('_physical192_profile_helpers',FIXED['helpers'])
    for entry in FIXED.values():h.checked(entry)
    return h,load('_physical192_original_profile_API',FIXED['profile_api'])

def read(entry,h):
    require(entry['identity']['mode']=='0o444' and entry['identity']['uid']==os.getuid() and entry['identity']['nlink']==1,'Immutable owned metadata required')
    return json.loads(h.checked(entry).read_bytes())

def capture(h):
    plan=read(FIXED['capture_plan'],h);result=read(FIXED['capture_result'],h);cpu=read(FIXED['capture_CPU'],h)
    threshold=read(FIXED['capture_threshold'],h);anchor=read(FIXED['capture_anchor'],h)
    require(result['state']=='captured_CPU_verified' and result['promotion']is False and result['quality_qualified']is False
        and result['owner']==plan['owner'] and result['CPU_verification']['sha256']==FIXED['capture_CPU']['sha256'],'Actual own valid capture required')
    require(plan['thresholds']==dict(elapsed_s=3600,applied_updates=5000,replay_inserts=1000000)
        and all(result['added'][k]>=v for k,v in plan['thresholds'].items())
        and sum(result['added']['by_source'].values())==result['added']['replay_inserts'],'Original own exposure targets differ')
    require(cpu['checkpoint']==result['endpoint'] and result['endpoint']['sha256']==CANDIDATE
        and cpu['online_target_shapes_and_finiteness_verified']is True and cpu['priority_phase_valid']is True
        and cpu['priority_phase']['metric']=='ce' and cpu['Adam_parameters']==81
        and cpu['optimizer_lrs']==[3.125e-6] and cpu['Adam_step_min']==cpu['Adam_step_max']>plan['entry_Adam_step']
        and cpu['CUDA_initialized']is False,'Retained strict numerical eligibility differs')
    require(all(type(v)is int and v>=threshold[k]>=anchor[k] for k,v in cpu['clocks'].items())
        and cpu['clocks']['training_steps']>anchor['training_steps'],'Saved clocks predate own exposure')
    release=read(FIXED['capture_CPU_release'],h);terminal=release['terminal'];owner=release['original']
    require(terminal['MainPID']=='0' and terminal['ExecMainPID']==owner['MainPID']
        and terminal['InvocationID']==owner['InvocationID'] and terminal['ExecMainCode']=='1' and terminal['ExecMainStatus']=='0'
        and release['original_birth_absent']is True and release['after_release']['ActiveState']=='inactive','Original capture CPU closure differs')
    observer=read(FIXED['capture_observer_release'],h);end=read(observer['actual_terminal'],h)
    require(end['Id']=='robotron-durable-candidate-window-original03-20261029.service'
        and end['ExecMainPID']=='387795' and end['InvocationID']=='5bec4ee382be4037bf9f1b1cec096a0d'
        and end['MainPID']=='0' and end['ExecMainCode']=='1' and end['ExecMainStatus']=='0'
        and observer['original_birth_absent']is True and observer['original_cgroup_absent']is True
        and observer['after_release']['LoadState']=='not-found','Original completed observer closure differs')
    return result,cpu

def case_input_pins(case,h):
    require(isinstance(case['inputs'],dict) and case['inputs'],'Exact typed-case input map required')
    result=[]
    for path,row in case['inputs'].items():
        entry=dict(path=path,sha256=row['sha256'],bytes=row['identity']['bytes'],identity=row['identity'])
        h.checked(entry)
        result.append(entry)
    return result

def selection(path,sha,h):
    sp=h.pin(Path(path).resolve());require(sp['sha256']==sha,'Exact fresh Root selection required');s=read(sp,h)
    require(s['schema']=='robotron-root-physical192-cap8-fresh16c-profile-selection-v2'
        and s['status']=='ACTUAL_TYPED_CONTEXT_SELECTED_FOR_FRESH_CPU_PROFILES'
        and s['source_family']==FIXED['physical_family'] and s['source_peer']==FIXED['physical_peer']
        and re.fullmatch('[0-9a-f]{32}',s['study_uuid']or'')and s['study_uuid']!='0'*32
        and s['all_four_profiles_are_fresh']is True and s['no_old_scores_or_jobs_reused']is True
        and s['candidate_policy_sha256']==CANDIDATE and s['reference_policy_sha256']==REFERENCE,'Actual fresh physical context profile selection required')
    case=read(s['main_case'],h);c=case['continuous']
    require(case['schema']=='robotron-continuous-physical-original192-health-case-v2'
        and c['mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE' and c['accepted_profile']=='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE'
        and set(case['slot_eval'])==set(map(str,range(192))) and all(type(v)is bool for v in case['slot_eval'].values())
        and sum(case['slot_eval'].values())==37,'Actual original192 physical context required')
    case_input_pins(case,h)
    require(s['main_case']==FIXED['physical_case']
        and case['input_inventory_authority']==FIXED['physical_inventory'],
        'Exact newly prepared physical case/inventory required, never old static authority')
    shared=load('_physical192_profile_domain',FIXED['shared_domain_helper'])
    shared.validate_inventory(case,h)
    for entry in (c['source_authority'],c['original_membership'],c['initial_barrier'],case['input_inventory_authority']):read(entry,h)
    cap=read(s['cap8_runtime_authority'],h)
    require(cap['schema']=='robotron-root-current-physical192-cap8-profile-context-v2'
        and cap['main_case']==s['main_case'] and cap['trainer']==c['trainer'] and cap['source_authority']==c['source_authority']
        and cap['environment']['DQN_MAX_SAMPLES_PER_FRAME']=='8'
        and cap['environment']['ROBOTRON_CONTINUOUS_TRAINING_MODE']=='1'
        and cap['retained_original_unit_environment_verified']is True,'Actual retained current cap8 owner/environment evidence required')
    retained=read(cap['retained_unit_environment'],h)['trainer'];proc=retained['process'];env=proc['environment']
    require(retained['unit']==c['trainer']['unit'] and retained['invocation']==c['trainer']['invocation_id']
        and proc['pid']==c['trainer']['pid'] and proc['starttime_ticks']==c['trainer']['birth']
        and proc['cgroup']==c['trainer']['cgroup']
        and all(env.get(k)==v for k,v in {'DQN_MAX_SAMPLES_PER_FRAME':'8','DQN_BATCH_SIZE':'4096','DQN_N_STEP':'3','DQN_PER_PRIORITY_METRIC':'ce','ROBOTRON_CONTINUOUS_TRAINING_MODE':'1'}.items())
        and all(env.get(k)==v for k,v in cap['environment'].items()),'Retained actual owner/environment does not prove this cap8 recipe')
    engineering_association(s['main_qualification'],s,case,h)
    return s,sp,case

def engineering_association(joint_pin,s,case,h):
    joint=read(joint_pin,h);family=read(FIXED['physical_family'],h)
    mapped=read(FIXED['observer_map'],h);mapping=mapped['observer_sources']
    require(joint['schema']=='robotron-continuous-physical192-joint-engineering-readiness-v1'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['source']==FIXED['engineering_finalizer']
        and joint['case']==s['main_case']==FIXED['physical_case']
        and joint['input_inventory_authority']==case['input_inventory_authority']==FIXED['physical_inventory']
        and joint['source_family']==family['typed_health_packet']
        and joint['observer_sources']==mapping and joint['observer_reviewer']==mapped['observer_reviewer']
        and joint['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'
        and joint['maximum_gap_s']==2.0 and joint['interval_s']==.2
        and joint['main_health_profile']=='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE'
        and joint['admission_basis']=='EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS'
        and joint['simultaneous192_actors_claimed']is False
        and joint['all_original_engineering_scopes_closed_at_recorded_closer']is True
        and joint['all_three_modes_are_fresh_originals_for_this_physical_case']is True
        and joint['old_static_or_countbounded_failures_reused_or_requalified']is False
        and joint['long_work_contract']=='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S',
        'Actual fresh physical three-scope engineering joint required before any CPU profile')
    require(set(joint['engineering'])=={'warmup','long','abort'},'Exact fresh physical engineering modes required')
    for mode,row in joint['engineering'].items():
        closed=read(row['closeout'],h)
        require(closed['schema']=='robotron-physical192-original-engineering-closeout-v1'
            and closed['status']=='PASS_ENGINEERING_ONLY' and closed['kind']=='main-physical192'
            and closed['mode']==mode and closed['source']==FIXED['engineering_closer']
            and closed['original_parent_actual_exit']==0
            and closed['worker_actual_exit']==(1 if mode=='abort' else 0)
            and closed['actual_parent_CPU_cores']==2 and closed['actual_parent_memory_bytes']==4<<30
            and closed['actual_parent_runtime_s']==(1800 if mode=='long' else 780)
            and closed['all_original_births_units_cgroups_and_tmpfs_control_absent']is True,
            'Actual fresh physical engineering original closure differs')
        probe=read(closed['actual_probe_result'],h);native=read(probe['original_job'],h)
        life=read(closed['worker_lifecycle'],h);worker=read(life['worker_job'],h)
        require(row['lifecycle']==closed['worker_lifecycle']
            and native['main_binding']==s['main_case'] and worker['case']==s['main_case']
            and worker['sources']==probe['sources']==mapping
            and probe['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'
            and probe['maximum_gap_s']==2.0
            and probe['main_health_profile']=='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE',
            'Engineering is not this exact physical context/source family')
        if mode=='long':
            require(closed['long_work_contract']==probe['long_work_contract']
                        =='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S'
                and 600<=closed['actual_long_work_s']==probe['actual_long_work_s']<=1200
                and closed['last_validated_long_count']==probe['last_validated_long_count']>=3000,
                'Sustained600s and validated3000 samples are both required')
    raw=read(joint['independent_raw_review'],h)
    require(joint['lifecycle']==joint['engineering']['long']['lifecycle']
        and joint['independent_raw_review']==joint['engineering']['long']['independent_raw_review']
        and raw['status']=='PASS' and raw['lifecycle']==joint['lifecycle']
        and raw['original_sources']==mapping and raw['accepted_samples']>=3000
        and raw['full_main_input_count']==len(case['inputs'])
        and raw['main_health_profile']=='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE'
        and all(raw[key]is True for key in ('source_bound_original192_physical_bootstrap_verified',
            'TRAIN155_original_physical_and_current_TCP_verified',
            'EVAL37_original_connection_and_strict_retirement_evidence_verified',
            'EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified',
            'prior_completed_EVAL_prefix_and_current_suffix_verified')),
        'Exact already-completed physical raw review required; no old raw replay is substituted')
    return joint

def prepare(path,sha,role,output,canonical_closeout=None):
    require(role in ('candidate','reference'),'Exact selected role required')
    h,api=dependencies();s,sp,case=selection(path,sha,h);result,cpu=capture(h)
    old=read(FIXED['protected_reference_job'],h)
    policy=dict(checkpoint=result['endpoint'],expected_policy_clocks=cpu['clocks'],authority=FIXED['capture_CPU']) if role=='candidate' else dict(checkpoint=old['checkpoint'],expected_policy_clocks=old['expected_policy_clocks'],authority=old['policy_authority'])
    require(policy['checkpoint']['sha256']==(CANDIDATE if role=='candidate' else REFERENCE),'Exact selected policy differs')
    checkpoint=h.pin(policy['checkpoint']['path']);require(all(checkpoint[k]==v for k,v in policy['checkpoint'].items()) and checkpoint['identity']['mode']=='0o444','Actual immutable checkpoint changed')
    mode='canonical'if canonical_closeout is None else'frozen'
    directory=Path(output).absolute();profile_root=Path(s['profile_root'])
    require(profile_root.is_absolute() and profile_root.resolve()==profile_root and profile_root.is_dir()
        and str(profile_root).startswith(str(ROOT/'logs/managed-learning-20261015/run-26')+'/')
        and directory==profile_root/(role+'-'+mode+'-CPU-original01')
        and directory.resolve()==directory and not directory.exists(),'Exact fresh selected profile directory required')
    require(profile_root!=Path(FIXED['capture_result']['path']).parent and Path(FIXED['capture_result']['path']).parent not in profile_root.parents,'New context must not write inside historical capture')
    job=dict(checkpoint=checkpoint,benchmark=FIXED['benchmark'],output=str(directory/'runtime'))
    inputs=[checkpoint,FIXED['benchmark'],sp,s['main_case'],s['main_qualification'],s['cap8_runtime_authority'],read(s['cap8_runtime_authority'],h)['retained_unit_environment'],*case_input_pins(case,h),case['input_inventory_authority'],case['continuous']['source_authority'],policy['authority'],h.pin(Path(__file__).resolve()),*FIXED.values()]
    if mode=='canonical':argv=[FIXED['benchmark']['path'],'--cpu-facts','--checkpoint',checkpoint['path'],'--directory',job['output']]
    else:
        authority=h.pin(Path(canonical_closeout).resolve());closed=read(authority,h)
        require(closed['schema']=='robotron-original-canonical-CPU-profile-closeout-v1'and closed['status']=='PASS'
            and closed['checkpoint']==checkpoint and closed['actual_exit']==0,'Fresh same-policy canonical original closure required')
        prepared=read(h.pin(Path(canonical_closeout).parent/'prepared-NOT-LAUNCHED.json'),h)
        require(prepared['profile_selection']==sp and prepared['role']==role and prepared['mode']=='canonical'
            and prepared['source']==h.pin(Path(__file__).resolve()),'No old canonical profile adoption')
        job.update(driver=FIXED['frozen_driver'],package=old['source_package'],canonical_CPU_facts=closed['immutable_facts'])
        inputs += [authority,*[v for v in job.values()if isinstance(v,dict)]]
    for value in {v['path']:v for v in inputs}.values():h.checked(value)
    directory.mkdir(mode=0o700);jp=h.put(directory/'job.json',job)
    if mode=='frozen':argv=[job['driver']['path'],'--job',jp['path'],'--job-sha256',jp['sha256']]
    control=load('_physical192_profile_controller',FIXED['controller'])
    config=dict(unit='robotron-physical192-'+s['study_uuid']+'-'+role+'-'+mode+'-CPU-original01.service',output=str(directory/'execution-original01'),argv=['/usr/bin/env',*[k+'='+v for k,v in PRIVATE_ENV.items()],str(ROOT.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',*argv],properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],observation_s=240,pins=[control.pin(v['path'])for v in {v['path']:v for v in [jp,*inputs]}.values()])
    cp=h.put(directory/'controller-config.json',config);require(control.checked_config(cp['path'])==config,'Existing CPU controller ABI differs')
    return h.put(directory/'prepared-NOT-LAUNCHED.json',dict(mode=mode,role=role,job=jp,config=cp,profile_selection=sp,source=h.pin(Path(__file__).resolve()),controller=FIXED['controller'],Root_controller_argv=['/usr/bin/python3.12','-I','-B',FIXED['controller']['path'],'--execute','--config',cp['path'],'--expected-source-sha256',FIXED['controller']['sha256']],strict_existing_numerical_driver_unchanged=True,recorded_physical_engineering_qualified=True,fresh_runtime_or_resource_probe_performed=False,actual_physical_engineering=s['main_qualification'],scientific_launch_qualified=False,CPU_or_study_launched=False,quality_qualified=False,promotion=False))


def prepare_comparison_selection(path,sha,output,engineering_joint,engineering_sha):
    h,api=dependencies();s,sp,case=selection(path,sha,h);result,cpu=capture(h)
    joint_pin=h.pin(Path(engineering_joint).resolve());require(joint_pin['sha256']==engineering_sha,'Exact actual engineering joint selected')
    require(joint_pin==s['main_qualification'],'Comparison must use the same actual joint that gated fresh profiles')
    engineering_association(joint_pin,s,case,h)
    require(s['old_measurement_was_not_a_policy_quality_rejection']is True,'Explicit valid-policy/new-infrastructure selection required')
    root=Path(s['profile_root']);adoptions={};closed_inputs=[]
    for role in ('reference','candidate'):
        for mode in ('canonical','frozen'):
            directory=root/(role+'-'+mode+'-CPU-original01')
            packet=read(h.pin(directory/'prepared-NOT-LAUNCHED.json'),h)
            require(packet['profile_selection']==sp and packet['role']==role and packet['mode']==mode
                and packet['source']==h.pin(Path(__file__).resolve()),'Every profile must be from this exact fresh physical selection/source')
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
    selected=h.put(output/'Root-physical192-comparison-selection.json',dict(
        schema='robotron-root-continuous-physical192-fresh-comparison-selection-v2',status='ACTUAL_POST_MODE_CONTEXT_SELECTED',
        mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',main_case=s['main_case'],candidate_selection_mode='PRIOR_VALID_CAPTURE_NEW_INFRA_CONTEXT',
        capture_root=str(Path(FIXED['capture_result']['path']).parent),capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],
        policy_reevaluation_authority=reuse,current_runtime_profiles=dict(main_source_authority=case['continuous']['source_authority'],
        reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate']),source_family=FIXED['physical_family'],source_peer=FIXED['physical_peer'],
        fresh_profile_closeouts=closed_inputs,Root_profile_selection=sp,actual_physical_engineering=joint_pin,launch_qualified=False,quality_qualified=False))
    return h.put(output/'prepared-physical192-prerequisites-NOT-LAUNCH-QUALIFIED.json',dict(
        selection=selected,reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate'],
        original_capture_qualification=qualification,policy_reevaluation_authority=reuse,source=h.pin(Path(__file__).resolve()),
        actual_four_native_jobs=None,actual_metadata_CPU=None,actual_exact_job_guards=None,actual_review_precommit_CPU=None,
        scientific_launch_qualified=False,quality_qualified=False,CPU_or_scientific_job_launched=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--prepare-canonical',action='store_true');g.add_argument('--prepare-frozen',action='store_true');g.add_argument('--close',action='store_true');g.add_argument('--prepare-comparison-selection',action='store_true')
    p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--role',choices=('candidate','reference'));p.add_argument('--directory',type=Path);p.add_argument('--canonical-closeout',type=Path);p.add_argument('--engineering-joint',type=Path);p.add_argument('--engineering-joint-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not(a.prepare_canonical or a.prepare_frozen or a.close or a.prepare_comparison_selection):print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.expected_source_sha256,'Exact selected constructor required')
    if a.close:
        h,api=dependencies();answer=api.close(a.directory)
    elif a.prepare_comparison_selection:
        require(a.selection and a.selection_sha256 and a.directory and a.engineering_joint and a.engineering_joint_sha256,'Exact selection/engineering joint and fresh metadata output required')
        answer=prepare_comparison_selection(a.selection,a.selection_sha256,a.directory,a.engineering_joint,a.engineering_joint_sha256)
    else:
        require(a.selection and a.selection_sha256 and a.role and a.directory,'Explicit actual Root selection/role/output required')
        require(bool(a.canonical_closeout)==bool(a.prepare_frozen),'Only frozen mode takes its actual canonical closeout')
        answer=prepare(a.selection,a.selection_sha256,a.role,a.directory,a.canonical_closeout)
    print(json.dumps(dict(prepared_or_closed=answer,CPU_or_scientific_job_launched=False,Root_only_controller_source=FIXED['controller'])),flush=True)

if __name__=='__main__':main()
