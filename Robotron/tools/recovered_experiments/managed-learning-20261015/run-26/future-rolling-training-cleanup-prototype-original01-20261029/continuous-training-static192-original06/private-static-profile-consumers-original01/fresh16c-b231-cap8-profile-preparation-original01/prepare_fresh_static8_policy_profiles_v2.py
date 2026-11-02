"""Fresh static-main cap8 CPU profiles for valid16c and protected3045. Default inert.

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
FIXED={'profile_api': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/prepare_and_close_profile_cpu_v2.py', 'sha256': 'dc4b811b57b05e0a439ef2345d0dc73f6db42578b672511d13ec08ddda65ff8c', 'bytes': 10053, 'identity': {'device': 2304, 'inode': 84708521, 'bytes': 10053, 'mtime_ns': 1793221310159594380, 'ctime_ns': 1793221310159594380, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'benchmark': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/benchmark_sidecar_inference.py', 'sha256': '39d90c6dc70d69a4fef4c7244868819ddd06f7cc4283998d821632cf0ce2bde5', 'bytes': 16421, 'identity': {'device': 2304, 'inode': 79965881, 'bytes': 16421, 'mtime_ns': 1792122331445724145, 'ctime_ns': 1792122331445724145, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'frozen_driver': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/check_frozen_profile_cpu_v2.py', 'sha256': '941333f31ec4a1f4e83a9c4ebc7cc639459b0654057e3237daf52f424bf7ae7d', 'bytes': 3034, 'identity': {'device': 2304, 'inode': 84702870, 'bytes': 3034, 'mtime_ns': 1793160670301732716, 'ctime_ns': 1793160670301732716, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'adopter': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/adopt_profile_scope_v2.py', 'sha256': '30d6fb41599a6eb2977421dd1cb2a5638bc6b148c349cfea2b10d7ab7372f8bb', 'bytes': 7225, 'identity': {'device': 2304, 'inode': 84704201, 'bytes': 7225, 'mtime_ns': 1793171634710878615, 'ctime_ns': 1793171634710878615, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py', 'sha256': '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'bytes': 17290, 'identity': {'device': 2304, 'inode': 81930188, 'bytes': 17290, 'mtime_ns': 1792424008109022468, 'ctime_ns': 1792424257834393599, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'DL3_family': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-original03/prepared-static-profile-deadline13-startup-hold0-SOURCE-ONLY-NOT-QUALIFIED.json', 'sha256': '5fb6653fddb2f54a5f8459c2d10ec7e73ac3189b576197eeeb2eef48c34af646', 'bytes': 15084, 'identity': {'device': 2304, 'inode': 85225945, 'bytes': 15084, 'mtime_ns': 1793277397071730499, 'ctime_ns': 1793277397071730499, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'DL3_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-original03/independent-static-private-deadline13-startup-hold0-source-peer-v1.json', 'sha256': '287fa94109ae1ab2093efeb20ca363f1d35429415278a3bdaf5178c4cf2b96f6', 'bytes': 32845, 'identity': {'device': 2304, 'inode': 85225960, 'bytes': 32845, 'mtime_ns': 1793277634486328346, 'ctime_ns': 1793277634486328346, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'observer_map': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-original01/prospective-static192-eight-role-observer-source-map-v1.json', 'sha256': '4629c151898362a71c3aa1f011c2088154c1cd69b9abc8959efdad79103c7410', 'bytes': 5914, 'identity': {'device': 2304, 'inode': 85225313, 'bytes': 5914, 'mtime_ns': 1793271076085048764, 'ctime_ns': 1793271076085048764, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'protected_reference_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03/R1/job.json', 'sha256': 'f34511e9e860342887681958fadc7e465e7b49a7c115d15dd36e57a9cf0b0d33', 'bytes': 95725, 'identity': {'device': 2304, 'inode': 80763099, 'bytes': 95725, 'mtime_ns': 1793055492480886407, 'ctime_ns': 1793055492480886407, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/window-plan.json', 'sha256': '43ace243055948eba395f97ba96faef339997c5d94cec6b50aea3104dbe9ae68', 'bytes': 22728, 'identity': {'device': 2304, 'inode': 85091488, 'bytes': 22728, 'mtime_ns': 1793255608603967147, 'ctime_ns': 1793255608603967147, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/result.json', 'sha256': 'a8dc3dfa27cec1f2c050fe6faef4b5229c11cf7b01d54b5bde77c7f2a9942536', 'bytes': 1377, 'identity': {'device': 2304, 'inode': 85095142, 'bytes': 1377, 'mtime_ns': 1793259346605715431, 'ctime_ns': 1793259346605715431, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/endpoint-CPU.json', 'sha256': 'd9dfb33918a98a3164f503fafe7bc6ac4dfca1df15c252b531f4d0dd1eca8990', 'bytes': 2112, 'identity': {'device': 2304, 'inode': 85095139, 'bytes': 2112, 'mtime_ns': 1793259345749905132, 'ctime_ns': 1793259345749905132, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_threshold': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/first-threshold.raw.json', 'sha256': '9258dd24a08677bc77bfccd93be7f0b159f2d2b502da06e30a0ff9d7f381ebc1', 'bytes': 123537, 'identity': {'device': 2304, 'inode': 85095121, 'bytes': 123537, 'mtime_ns': 1793259248515085077, 'ctime_ns': 1793259248515085077, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_anchor': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/anchor.raw.json', 'sha256': 'df466635c6496f934e4bb5f4b282e8489bed3d62839a165ee4f11f48b2a3455d', 'bytes': 130987, 'identity': {'device': 2304, 'inode': 85091502, 'bytes': 130987, 'mtime_ns': 1793255643320103002, 'ctime_ns': 1793255643320103002, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/CPU-owned-release.json', 'sha256': '497d229164572c3585a529c8d988211398bbb4f5be68e1365ce43c811c31454f', 'bytes': 33674, 'identity': {'device': 2304, 'inode': 85095141, 'bytes': 33674, 'mtime_ns': 1793259346595313573, 'ctime_ns': 1793259346595313573, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_observer_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-natural-turnover-durable-next-candidate-20261029-original03/ROOT-original-observer03-owned-release.json', 'sha256': '906d4711761f90aea0b9231ffc3f15cb24f292ed64149eeb80bbfa13ae1281e3', 'bytes': 13051, 'identity': {'device': 2304, 'inode': 85095222, 'bytes': 13051, 'mtime_ns': 1793259543263658909, 'ctime_ns': 1793259543263658909, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'engineering_closer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/new-static-context-engineering-original01-preparation/close_static192_engineering_v1.py', 'sha256': 'ecbca38b9f56fc2a78b2efba92e777167aff1b023ad07d83db455cffca5a80e9', 'bytes': 9222, 'identity': {'device': 2304, 'inode': 85225683, 'bytes': 9222, 'mtime_ns': 1793275099767441667, 'ctime_ns': 1793277217676427364, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
PRIVATE_ENV={'ROBOTRON_CONTINUOUS_TRAINING_MODE':'0','ROBOTRON_ROLLING_TRAINING_CLEANUP':'0','ROBOTRON_CONTINUOUS_STARTUP_HOLD':'0','DQN_MAX_SAMPLES_PER_FRAME':'8'}

def require(ok,reason):
    if not ok:raise ValueError(reason)

def load(name,entry):
    p=Path(entry['path']);require(hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],'Selected existing source changed')
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def dependencies():
    h=load('_static8_profile_helpers',FIXED['helpers'])
    for entry in FIXED.values():h.checked(entry)
    return h,load('_static8_original_profile_API',FIXED['profile_api'])

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
    require(s['schema']=='robotron-root-static-cap8-fresh16c-profile-selection-v1'
        and s['status']=='ACTUAL_TYPED_CONTEXT_SELECTED_FOR_FRESH_CPU_PROFILES'
        and s['source_family']==FIXED['DL3_family'] and s['source_peer']==FIXED['DL3_peer']
        and re.fullmatch('[0-9a-f]{32}',s['study_uuid']or'')and s['study_uuid']!='0'*32
        and s['all_four_profiles_are_fresh']is True and s['no_old_scores_or_jobs_reused']is True
        and s['candidate_policy_sha256']==CANDIDATE and s['reference_policy_sha256']==REFERENCE,'Actual new static context profile selection required')
    case=read(s['main_case'],h);c=case['continuous']
    require(case['schema']=='robotron-continuous-static192-health-case-v1'
        and c['mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE' and c['accepted_profile']=='STATIC_ORIGINAL192_NO_FAULT_ADOPTION'
        and set(case['slot_eval'])==set(map(str,range(192))) and all(type(v)is bool for v in case['slot_eval'].values())
        and sum(case['slot_eval'].values())==37,'Actual postbarrier original192 context required')
    case_input_pins(case,h)
    for entry in (c['source_authority'],c['original_membership'],c['initial_barrier'],case['input_inventory_authority']):read(entry,h)
    cap=read(s['cap8_runtime_authority'],h)
    require(cap['schema']=='robotron-root-current-static-cap8-profile-context-v1'
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
    return s,sp,case

def engineering_association(joint_pin,s,case,h):
    joint=read(joint_pin,h)
    family=read(FIXED['DL3_family'],h)
    require(joint['schema']=='robotron-continuous-static192-joint-engineering-readiness-v1'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['case']==s['main_case'] and joint['input_inventory_authority']==case['input_inventory_authority']
        and joint['source_family']==family['typed_health_packet']
        and joint['observer_sources']==read(FIXED['observer_map'],h)['observer_sources']
        and joint['proof_gap_contract']=='robotron-main-proof-gap-2s-v1' and joint['maximum_gap_s']==2.0
        and joint['all_original_engineering_scopes_closed_at_recorded_closer']is True,'Actual independently closed current static engineering joint required')
    require(set(joint['engineering'])=={'warmup','long','abort'},'Exact new three-mode engineering joint required')
    closeouts={mode:row['closeout']for mode,row in joint['engineering'].items()}
    require(set(closeouts)=={'warmup','long','abort'},'Three fresh original static engineering modes required')
    mapping=read(FIXED['observer_map'],h)['observer_sources']
    for mode,entry in closeouts.items():
        closed=read(entry,h)
        require(closed['schema']=='robotron-static192-original-engineering-closeout-v1'
            and closed['status']=='PASS_ENGINEERING_ONLY' and closed['kind']=='main-static192' and closed['mode']==mode
            and closed['source']==FIXED['engineering_closer'] and closed['original_parent_actual_exit']==0 and closed['worker_actual_exit']==(1 if mode=='abort' else 0)
            and closed['all_original_births_units_cgroups_and_tmpfs_control_absent']is True,'Original static engineering closure differs')
        probe=read(closed['actual_probe_result'],h);native=read(probe['original_job'],h);life=read(closed['worker_lifecycle'],h);worker=read(life['worker_job'],h)
        require(native['main_binding']==s['main_case'] and worker['case']==s['main_case'] and worker['sources']==mapping
            and probe['proof_gap_contract']=='robotron-main-proof-gap-2s-v1' and probe['maximum_gap_s']==2.0
            and probe['main_health_profile']=='STATIC_ORIGINAL192_NO_FAULT_ADOPTION','Engineering is not this exact static context/source family')
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
    inputs=[checkpoint,FIXED['benchmark'],sp,s['main_case'],s['cap8_runtime_authority'],read(s['cap8_runtime_authority'],h)['retained_unit_environment'],*case_input_pins(case,h),case['input_inventory_authority'],case['continuous']['source_authority'],policy['authority'],h.pin(Path(__file__).resolve()),*FIXED.values()]
    if mode=='canonical':argv=[FIXED['benchmark']['path'],'--cpu-facts','--checkpoint',checkpoint['path'],'--directory',job['output']]
    else:
        authority=h.pin(Path(canonical_closeout).resolve());closed=read(authority,h)
        require(closed['schema']=='robotron-original-canonical-CPU-profile-closeout-v1'and closed['status']=='PASS'
            and closed['checkpoint']==checkpoint and closed['actual_exit']==0,'Fresh same-policy canonical original closure required')
        prepared=read(h.pin(Path(canonical_closeout).parent/'prepared-NOT-LAUNCHED.json'),h)
        require(prepared['profile_selection']==sp and prepared['role']==role and prepared['mode']=='canonical','No old canonical profile adoption')
        job.update(driver=FIXED['frozen_driver'],package=old['source_package'],canonical_CPU_facts=closed['immutable_facts'])
        inputs += [authority,*[v for v in job.values()if isinstance(v,dict)]]
    for value in {v['path']:v for v in inputs}.values():h.checked(value)
    directory.mkdir(mode=0o700);jp=h.put(directory/'job.json',job)
    if mode=='frozen':argv=[job['driver']['path'],'--job',jp['path'],'--job-sha256',jp['sha256']]
    control=load('_static8_profile_controller',FIXED['controller'])
    config=dict(unit='robotron-static8-'+s['study_uuid']+'-'+role+'-'+mode+'-CPU-original01.service',output=str(directory/'execution-original01'),argv=['/usr/bin/env',*[k+'='+v for k,v in PRIVATE_ENV.items()],str(ROOT.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',*argv],properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],observation_s=240,pins=[control.pin(v['path'])for v in {v['path']:v for v in [jp,*inputs]}.values()])
    cp=h.put(directory/'controller-config.json',config);require(control.checked_config(cp['path'])==config,'Existing CPU controller ABI differs')
    return h.put(directory/'prepared-NOT-LAUNCHED.json',dict(mode=mode,role=role,job=jp,config=cp,profile_selection=sp,source=h.pin(Path(__file__).resolve()),controller=FIXED['controller'],Root_controller_argv=['/usr/bin/python3.12','-I','-B',FIXED['controller']['path'],'--execute','--config',cp['path'],'--expected-source-sha256',FIXED['controller']['sha256']],strict_existing_numerical_driver_unchanged=True,current_static_engineering_qualified=False,scientific_launch_qualified=False,CPU_or_study_launched=False,quality_qualified=False,promotion=False))


def prepare_comparison_selection(path,sha,output,engineering_joint,engineering_sha):
    h,api=dependencies();s,sp,case=selection(path,sha,h);result,cpu=capture(h)
    joint_pin=h.pin(Path(engineering_joint).resolve());require(joint_pin['sha256']==engineering_sha,'Exact actual engineering joint selected')
    engineering_association(joint_pin,s,case,h)
    require(s['old_measurement_was_not_a_policy_quality_rejection']is True,'Explicit valid-policy/new-infrastructure selection required')
    root=Path(s['profile_root']);adoptions={};closed_inputs=[]
    for role in ('reference','candidate'):
        for mode in ('canonical','frozen'):
            directory=root/(role+'-'+mode+'-CPU-original01')
            packet=read(h.pin(directory/'prepared-NOT-LAUNCHED.json'),h)
            require(packet['profile_selection']==sp and packet['role']==role and packet['mode']==mode
                and packet['source']==h.pin(Path(__file__).resolve()),'Every profile must be from this exact fresh selection/source')
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
