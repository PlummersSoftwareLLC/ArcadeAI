"""Fresh original04 capture and readiness120 quiescence cap8 CPU profiles. Default inert.

Root-only explicit modes prepare metadata or reuse the unchanged original CPU
closer. No mode launches a CPU/service/game/scientific job or changes learning.
Unknown current case/engineering/cap evidence is supplied by immutable Root
selection after its real qualifications; no old profile/score is adopted.
"""
import argparse,hashlib,importlib.util,json,os,re,sys
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CANDIDATE='c0acc8ad3aa411a00928b6f242b2e4a6299780b5a2991c75225d334c21af60f0'
REFERENCE='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
FIXED={'profile_api': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/prepare_and_close_profile_cpu_v2.py', 'sha256': 'dc4b811b57b05e0a439ef2345d0dc73f6db42578b672511d13ec08ddda65ff8c', 'bytes': 10053, 'identity': {'device': 2304, 'inode': 84708521, 'bytes': 10053, 'mtime_ns': 1793221310159594380, 'ctime_ns': 1793221310159594380, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'benchmark': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/benchmark_sidecar_inference.py', 'sha256': '39d90c6dc70d69a4fef4c7244868819ddd06f7cc4283998d821632cf0ce2bde5', 'bytes': 16421, 'identity': {'device': 2304, 'inode': 79965881, 'bytes': 16421, 'mtime_ns': 1792122331445724145, 'ctime_ns': 1792122331445724145, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'frozen_driver': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/check_frozen_profile_cpu_v2.py', 'sha256': '941333f31ec4a1f4e83a9c4ebc7cc639459b0654057e3237daf52f424bf7ae7d', 'bytes': 3034, 'identity': {'device': 2304, 'inode': 84702870, 'bytes': 3034, 'mtime_ns': 1793160670301732716, 'ctime_ns': 1793160670301732716, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'adopter': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/adopt_profile_scope_v2.py', 'sha256': '30d6fb41599a6eb2977421dd1cb2a5638bc6b148c349cfea2b10d7ab7372f8bb', 'bytes': 7225, 'identity': {'device': 2304, 'inode': 84704201, 'bytes': 7225, 'mtime_ns': 1793171634710878615, 'ctime_ns': 1793171634710878615, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py', 'sha256': '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'bytes': 17290, 'identity': {'device': 2304, 'inode': 81930188, 'bytes': 17290, 'mtime_ns': 1792424008109022468, 'ctime_ns': 1792424257834393599, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'observer_map': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-quiescence-readiness120-overlay-original06/prospective-current-EVAL-quiescence-readiness120-eight-role-source-map-v1.json', 'sha256': 'c8231a36c0028567a6a7da884046aa98ceeaf0fc6f0c338e4230fd305fb7e553', 'bytes': 7725, 'identity': {'device': 2304, 'inode': 85355715, 'bytes': 7725, 'mtime_ns': 1793310753661479590, 'ctime_ns': 1793310753661479590, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'protected_reference_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03/R1/job.json', 'sha256': 'f34511e9e860342887681958fadc7e465e7b49a7c115d15dd36e57a9cf0b0d33', 'bytes': 95725, 'identity': {'device': 2304, 'inode': 80763099, 'bytes': 95725, 'mtime_ns': 1793055492480886407, 'ctime_ns': 1793055492480886407, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'engineering_closer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/quiescence-readiness120-engineering-original05-preparation/close_physical192_engineering_v5.py', 'sha256': '8f812f5cefb8e4e77182062bfb73f77e48598279508dc2d8c2de5c2a8500b026', 'bytes': 11451, 'identity': {'device': 2304, 'inode': 85355802, 'bytes': 11451, 'mtime_ns': 1793310835429468528, 'ctime_ns': 1793310960502771650, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_family': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/prepared-current-EVAL-quiescence-profile-deadline13-corrected-guard-SOURCE-ONLY-v6.json', 'sha256': '997ca21fabf6fd2a1edc183ff6857ee60d97119b2ff352580632a609e7260e26', 'bytes': 31130, 'identity': {'device': 2304, 'inode': 85358608, 'bytes': 31130, 'mtime_ns': 1793312011317572079, 'ctime_ns': 1793312011317572079, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/independent-current-EVAL-quiescence-readiness120-private13-and-fresh-capture-association-source-peer-v6.json', 'sha256': 'ae3e5b6deb2c5fef092411d65e7428679ea991ee9052cc2d8b22a0dd5c79cca8', 'bytes': 25692, 'identity': {'device': 2304, 'inode': 85358806, 'bytes': 25692, 'mtime_ns': 1793312070106492592, 'ctime_ns': 1793312070106492592, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'engineering_finalizer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/quiescence-readiness120-engineering-original05-preparation/finalize_physical192_engineering_v5.py', 'sha256': '3c83509c3c7e7eab08ed6417a4c96289fef6fd4cd2dc067853db2cb2fbbc568d', 'bytes': 22687, 'identity': {'device': 2304, 'inode': 85355803, 'bytes': 22687, 'mtime_ns': 1793310960504620138, 'ctime_ns': 1793310960506771667, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'shared_domain_helper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/physical_profile_contract_v5.py', 'sha256': '182b5678948fdc3e05c234f76dfeb0dcb1298560fb4815274742dab4e159d73c', 'bytes': 16858, 'identity': {'device': 2304, 'inode': 85235757, 'bytes': 16858, 'mtime_ns': 1793311425821202483, 'ctime_ns': 1793311527249199177, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_case': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-quiescence-readiness120-overlay-original06/actual-main-case-original01/current-EVAL-quiescence-readiness120-main-case-v1.json', 'sha256': 'e40c635508121ebdc65ced786f0c058160bed000318c7a614b9154085ef4c55a', 'bytes': 1337713, 'identity': {'device': 2304, 'inode': 85355949, 'bytes': 1337713, 'mtime_ns': 1793310977681079532, 'ctime_ns': 1793310977681079532, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_inventory': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-quiescence-readiness120-overlay-original06/actual-main-case-original01/exact-held-input-inventory-readiness120-v1.json', 'sha256': '98c6a33fc3ab082a85d6df60de39570bb6549930cccc9aa91c509f424ffbd01a', 'bytes': 317478, 'identity': {'device': 2304, 'inode': 85355948, 'bytes': 317478, 'mtime_ns': 1793310977633750693, 'ctime_ns': 1793310977633750693, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/window-plan.json', 'sha256': 'a2073154505e7c0b32d52001600d5cb5fdc814df9965741c53c067f1c6bcfd6b', 'bytes': 56485, 'identity': {'device': 2304, 'inode': 85352186, 'bytes': 56485, 'mtime_ns': 1793307735377045436, 'ctime_ns': 1793307735377045436, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/result.json', 'sha256': '886cbc7c509cc00dc267ac1d79f0073153a94f42139662bc49f21deea51b5ff4', 'bytes': 1351, 'identity': {'device': 2304, 'inode': 85356835, 'bytes': 1351, 'mtime_ns': 1793311547827216801, 'ctime_ns': 1793311547827216801, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/endpoint-CPU.json', 'sha256': '67d3b16bece9fc103f9e0ae0d207d99a1b7aba2775452753582e99fc66512e2d', 'bytes': 2099, 'identity': {'device': 2304, 'inode': 85356829, 'bytes': 2099, 'mtime_ns': 1793311547034981720, 'ctime_ns': 1793311547034981720, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_anchor': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/anchor.raw.json', 'sha256': '98bad132af83672d3d796a2f374b7e945211d02276a811e9560914a8c96f1bac', 'bytes': 127960, 'identity': {'device': 2304, 'inode': 85352202, 'bytes': 127960, 'mtime_ns': 1793307746778636039, 'ctime_ns': 1793307746778636039, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_threshold': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/first-threshold.raw.json', 'sha256': '28dd99c794b9a5e8b5e1cf95837a52c90ccd5adc18bebe2f5139c3af901388e9', 'bytes': 128267, 'identity': {'device': 2304, 'inode': 85356429, 'bytes': 128267, 'mtime_ns': 1793311347380789566, 'ctime_ns': 1793311347380789566, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_context': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/capture-context.raw.json', 'sha256': 'c16ddd9aa3426e202e2d438ba4acdbc9acac777f64fb0b5b3bc926ea7e182723', 'bytes': 128003, 'identity': {'device': 2304, 'inode': 85356806, 'bytes': 128003, 'mtime_ns': 1793311544235029244, 'ctime_ns': 1793311544235029244, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_owner': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/CPU-original-owner.json', 'sha256': '9d2572284711d166f5e84cc3b075fbff385e776148b907ac61dfe8ca393781aa', 'bytes': 12307, 'identity': {'device': 2304, 'inode': 85356828, 'bytes': 12307, 'mtime_ns': 1793311544265137938, 'ctime_ns': 1793311544265137938, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_terminal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/CPU-original-terminal.json', 'sha256': '18960aa396548a846ceb8c4626258052b895f1efcb4f02d2df035599ef1b2ecd', 'bytes': 11560, 'identity': {'device': 2304, 'inode': 85356832, 'bytes': 11560, 'mtime_ns': 1793311547809348155, 'ctime_ns': 1793311547809348155, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/CPU-owned-release.json', 'sha256': '683c60ce06f2267570601e574d03f1e056beb2529662746bac59a00f4dcfed94', 'bytes': 33633, 'identity': {'device': 2304, 'inode': 85356834, 'bytes': 33633, 'mtime_ns': 1793311547819926757, 'ctime_ns': 1793311547819926757, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_observer_launch': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04-preparation/Root-original-observer-launch-original04.json', 'sha256': '79c51d9351c8836b77b85e3812b4f0d2c06e926c12c39974dec4276a1f8f4701', 'bytes': 13252, 'identity': {'device': 2304, 'inode': 85352201, 'bytes': 13252, 'mtime_ns': 1793307746688702090, 'ctime_ns': 1793307746688702090, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_observer_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04/Root-original-observer-owned-closeout-original01/Root-original04-observer-positive-owned-release.json', 'sha256': '48b12ff7c5547fbcb1aee74a43e64495c24ba9fdb7a0468a879de45e83ae5f03', 'bytes': 13738, 'identity': {'device': 2304, 'inode': 85357745, 'bytes': 13738, 'mtime_ns': 1793311795070210826, 'ctime_ns': 1793311795070210826, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_root_selection': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04-preparation/Root-selected-fresh-continuous-window-original04.json', 'sha256': '01dd007c7326eb63832ca0176217d2140c684b58cd1644ae3cd381fb07a8a7c9', 'bytes': 35517, 'identity': {'device': 2304, 'inode': 85351925, 'bytes': 35517, 'mtime_ns': 1793307511977839231, 'ctime_ns': 1793307511978256288, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
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

def capture_input_pins(plan,h):
    # Window inputs are exactly thin3 pins, not the full8 source/control domain.
    values=[]
    for value in plan['inputs']:
        require(type(value)is dict and set(value)=={'path','sha256','bytes'},'Exact thin3 original window input required')
        path=Path(value['path']);require(path.is_absolute() and not path.is_symlink() and path.is_file(),'Regular selected capture input required')
        actual=h.pin(path)
        require(all(actual[key]==value[key] for key in value),'Original window input changed')
        values.append(actual)
    require(values and len({v['path'] for v in values})==len(values),'Distinct original window inputs required')
    return values

def normal_terminal(terminal,live,pid,invocation,expected):
    require(terminal['Id']==live['Id'] and terminal['MainPID']=='0'
        and terminal['ExecMainPID']==str(pid) and terminal['InvocationID']==invocation
        and terminal['ExecMainCode']=='1' and terminal['ExecMainStatus']=='0'
        and all(terminal[key]==value and live[key]==value for key,value in expected.items()),
        'Exact original normal0 terminal and unchanged resources required')

def capture(h):
    plan=read(FIXED['capture_plan'],h);result=read(FIXED['capture_result'],h);cpu=read(FIXED['capture_CPU'],h)
    threshold=read(FIXED['capture_threshold'],h);anchor=read(FIXED['capture_anchor'],h);current=read(FIXED['capture_context'],h)
    shared=load('_fresh_capture_pin_normalization',FIXED['shared_domain_helper'])
    require(shared.normalize_capture_fullpin(plan['root_selection'])==FIXED['capture_root_selection'],
        'Exact original Root-selected full8 provenance required')
    root=read(FIXED['capture_root_selection'],h)
    require(plan['continuous_context']['source_and_control_inputs']==root['source_and_control_inputs']
        and plan['continuous_context']['owner']==plan['owner']==root['owner']
        and plan['expected_exposure_lineage']==root['expected_exposure_lineage']
        and root['prior_window_counts_reused']is False,'Original selected continuous window context differs')
    capture_input_pins(plan,h)
    for value in plan['continuous_context']['source_and_control_inputs']:
        h.checked(shared.normalize_capture_fullpin(value))
    require(result['state']=='captured_CPU_verified' and result['promotion']is False and result['quality_qualified']is False
        and result['original_DQN_window_unchanged']is True and result['owner']==plan['owner']
        and all(result['CPU_verification'][k]==FIXED['capture_CPU'][k]for k in ('path','sha256','bytes')),
        'Actual own completed fresh capture required')
    require(plan['thresholds']==dict(elapsed_s=3600,applied_updates=5000,replay_inserts=1000000)
        and result['thresholds']==plan['thresholds']
        and all(result['added'][k]>=v for k,v in plan['thresholds'].items())
        and sum(result['added']['by_source'].values())==result['added']['replay_inserts'],
        'Original own exposure targets differ')
    exposures=[value['host_pipeline']['learning_exposure']for value in (anchor,threshold,current)]
    for exposure in exposures:
        for kind in ('optimizer','replay'):
            record=exposure[kind]
            require(record['available']is True and record['enabled']is True
                and {key:record[key]for key in ('process_id','instance_monotonic_ns','epoch','epoch_reason')}
                    ==plan['expected_exposure_lineage'][kind], 'Original own exposure epoch/owner differs')
        total=exposure['optimizer']['total']
        require(total['unavailable']==0 and 0<=total['attempts_started']-total['outcomes_recorded']<=1
            and total['outcomes_recorded']==total['applied']+total['amp_skipped'],'Original optimizer outcomes differ')
    first,last=exposures[0],exposures[2]
    require(result['added']['applied_updates']==last['optimizer']['total']['applied']-first['optimizer']['total']['applied']
        and result['added']['replay_inserts']==last['replay']['accepted_total']-first['replay']['accepted_total']
        and result['added']['by_source']=={key:value-first['replay']['accepted_by_source_total'][key]
            for key,value in last['replay']['accepted_by_source_total'].items()},'Fresh original counter deltas differ')
    require(cpu['checkpoint']==result['endpoint'] and result['endpoint']['sha256']==CANDIDATE
        and cpu['online_target_shapes_and_finiteness_verified']is True and cpu['priority_phase_valid']is True
        and cpu['priority_phase']['metric']=='ce' and cpu['Adam_parameters']==81
        and cpu['optimizer_lrs']==[3.125e-6] and cpu['Adam_step_min']==cpu['Adam_step_max']>plan['entry_Adam_step']
        and cpu['CUDA_initialized']is False,'Strict original numerical eligibility differs')
    require(all(type(v)is int and v>=threshold[k]>=anchor[k] for k,v in cpu['clocks'].items())
        and cpu['clocks']['training_steps']>anchor['training_steps'],'Saved clocks predate own exposure')
    owner=read(FIXED['capture_CPU_owner'],h);terminal=read(FIXED['capture_CPU_terminal'],h)
    release=read(FIXED['capture_CPU_release'],h);live=owner['actual_properties']
    require(owner['unit']==plan['CPU_unit']==live['Id'] and live['MainPID']==str(owner['pid'])
        and live['InvocationID']==owner['invocation_id'] and type(owner['birth'])is int and owner['birth']>0,
        'Original CPU owner differs')
    normal_terminal(terminal,live,owner['pid'],owner['invocation_id'],dict(Type='simple',Restart='no',NRestarts='0',
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='3min'))
    require(release['unit']==owner['unit'] and release['terminal']==terminal and release['original']==live
        and release['original_birth_absent']is True and release['after_release']['MainPID']=='0'
        and release['after_release']['ActiveState']=='inactive' and bool(live['ControlGroup']),
        'Actual original CPU terminal/release differs')
    observer=read(FIXED['capture_observer_release'],h);launch=read(FIXED['capture_observer_launch'],h)
    end=read(observer['actual_terminal'],h);observed=launch['systemctl_show'];original=launch['owner']
    require(observer['schema']=='robotron-root-learning-window-original-scope-closure-v1'
        and observer['status']=='ORIGINAL_EXIT0_ARCHIVED_AND_POSITIVELY_RELEASED'
        and observer['original_launch']==FIXED['capture_observer_launch'] and observer['original']==original
        and observer['unit']==observed['Id'] and launch['returncode']==launch['systemctl_show_returncode']==0
        and observed['MainPID']==str(original['pid']) and observed['InvocationID']==original['invocation_id']
        and type(original['birth_ticks'])is int and original['birth_ticks']>0,
        'Exact original observer launch and owner receipt required')
    normal_terminal(end,observed,original['pid'],original['invocation_id'],dict(Type='exec',Restart='no',NRestarts='0',
        RemainAfterExit='yes',CPUQuotaPerSecUSec='1s',MemoryMax=str(256<<20),MemorySwapMax='0',TasksMax='32',
        RuntimeMaxUSec='4h 7min',TimeoutStopUSec='10s',SendSIGKILL='no'))
    require(observer['original_birth_absent']is True and observer['original_cgroup_absent']is True
        and bool(observed['ControlGroup']) and observer['after_release']['LoadState']=='not-found'
        and observer['after_release']['MainPID']=='0' and observer['after_release']['ActiveState']=='inactive'
        and observer['window_result']==FIXED['capture_result'] and observer['endpoint_CPU']==FIXED['capture_CPU']
        and observer['endpoint_CPU_owned_release']==FIXED['capture_CPU_release']
        and all(observer['endpoint'][key]==result['endpoint'][key]for key in ('path','sha256','bytes')),
        'Original completed observer positive release and capture joins differ')
    require(all(value==result['endpoint'][key]for key,value in cpu['checkpoint'].items()),'Endpoint CPU checkpoint differs')
    return result,cpu

def capture_qualification_payload(h):
    return dict(schema='robotron-root-original-valid-capture-qualification-v1',
        status='CAPTURE_CPU_VERIFIED_AND_ORIGINAL_SCOPE_CLOSED',source=h.pin(Path(__file__).resolve()),
        capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],actual_original_exit=0,original_scope_released=True,
        numerical_CPU=FIXED['capture_CPU'],original_CPU_owner=FIXED['capture_CPU_owner'],original_CPU_terminal=FIXED['capture_CPU_terminal'],
        original_CPU_release=FIXED['capture_CPU_release'],original_observer_launch=FIXED['capture_observer_launch'],
        original_observer_release=FIXED['capture_observer_release'],capture_root_selection=FIXED['capture_root_selection'],
        policy_checkpoint_sha256=CANDIDATE,new_exposure_credited=False,quality_qualified=False)

def qualify_capture(output):
    h,api=dependencies();capture(h)
    output=Path(output).absolute();require(output.resolve()==output and not output.exists()and output.parent.is_dir(),
        'Fresh capture-qualification metadata directory required')
    output.mkdir(mode=0o700)
    return h.put(output/'original-valid-capture-qualification.json',capture_qualification_payload(h))

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
    require(s['schema']=='robotron-root-current-quiescence-cap8-fresh-window-profile-selection-v5'
        and s['status']=='ACTUAL_TYPED_CONTEXT_SELECTED_FOR_FRESH_CPU_PROFILES'
        and s['source_family']==FIXED['physical_family'] and s['source_peer']==FIXED['physical_peer']
        and re.fullmatch('[0-9a-f]{32}',s['study_uuid']or'')and s['study_uuid']!='0'*32
        and s['all_four_profiles_are_fresh']is True and s['no_old_scores_or_jobs_reused']is True
        and s['candidate_policy_sha256']==CANDIDATE and s['reference_policy_sha256']==REFERENCE,'Actual fresh physical context profile selection required')
    case=read(s['main_case'],h);c=case['continuous']
    require(case['schema']=='robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
        and c['mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE' and c['accepted_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
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
    capture(h)
    require(read(s['original_capture_qualification'],h)==capture_qualification_payload(h),'Exact independently qualified and closed fresh capture required')
    association=shared.validate_fresh_capture_association(s['fresh_capture_context_association'],
        plan_pin=FIXED['capture_plan'],result_pin=FIXED['capture_result'],plan=read(FIXED['capture_plan'],h),
        case=case,case_pin=s['main_case'],engineering_joint_pin=s['main_qualification'],h=h)
    require(association['original_capture_qualification']==s['original_capture_qualification'],
        'Current context must associate the same actual capture qualification')
    return s,sp,case

def engineering_association(joint_pin,s,case,h):
    joint=read(joint_pin,h);family=read(FIXED['physical_family'],h)
    mapped=read(FIXED['observer_map'],h);mapping=mapped['observer_sources']
    require(joint['schema']=='robotron-original192-immutable-bootstrap-live-pidfd-joint-engineering-readiness-v4'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['source']==FIXED['engineering_finalizer']
        and joint['case']==s['main_case']==FIXED['physical_case']
        and joint['input_inventory_authority']==case['input_inventory_authority']==FIXED['physical_inventory']
        and joint['source_family']==family['typed_health_packet']
        and joint['observer_sources']==mapping and joint['observer_reviewer']==mapped['observer_reviewer']
        and joint['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'
        and joint['maximum_gap_s']==2.0 and joint['interval_s']==.2
        and joint['main_health_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
        and joint['current_once_only_EVAL_quiescence_with_historical_error_and_ready_false_preserved_verified']is True
        and joint['original_cleanup_deadline_handoff_CID_reuse_or_refill_success_from_exception_claimed']is False
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
        require(closed['schema']=='robotron-original192-immutable-bootstrap-live-pidfd-original-engineering-closeout-v4'
            and closed['status']=='PASS_ENGINEERING_ONLY' and closed['kind']=='main-current-once-EVAL-quiescence192'
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
            and probe['main_health_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5',
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
        and raw['main_health_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
        and all(raw[key]is True for key in ('source_bound_original192_physical_bootstrap_verified',
            'TRAIN155_original_physical_and_current_TCP_verified',
            'EVAL37_original_connection_and_strict_retirement_evidence_verified',
            'EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified',
            'prior_completed_EVAL_prefix_and_current_suffix_verified',
            'immutable_original192_bootstrap_certificate_verified','fresh_original_keeper_pidfd_census_verified',
            'authentic_published_normal0_exit_facts_and_monotone_coverage_verified',
            'current_once_only_EVAL_quiescence_with_historical_error_and_ready_false_preserved_verified'))
        and raw['original_cleanup_deadline_handoff_CID_reuse_or_refill_success_from_exception_claimed']is False,
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
    inputs=[checkpoint,FIXED['benchmark'],sp,s['main_case'],s['main_qualification'],s['cap8_runtime_authority'],read(s['cap8_runtime_authority'],h)['retained_unit_environment'],*case_input_pins(case,h),case['input_inventory_authority'],case['continuous']['source_authority'],policy['authority'],s['original_capture_qualification'],s['fresh_capture_context_association'],
        *capture_input_pins(read(FIXED['capture_plan'],h),h),h.pin(Path(__file__).resolve()),*FIXED.values()]
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
    qualification=s['original_capture_qualification']
    selected=h.put(output/'Root-physical192-comparison-selection.json',dict(
        schema='robotron-root-current-eval-quiescence-fresh-comparison-selection-v5',status='ACTUAL_POST_MODE_CONTEXT_SELECTED',
        mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',main_case=s['main_case'],candidate_selection_mode='FRESH_POST_MODE_CAPTURE',
        capture_root=str(Path(FIXED['capture_result']['path']).parent),capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],
        fresh_capture_context_association=s['fresh_capture_context_association'],current_runtime_profiles=dict(main_source_authority=case['continuous']['source_authority'],
        reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate']),source_family=FIXED['physical_family'],source_peer=FIXED['physical_peer'],
        fresh_profile_closeouts=closed_inputs,Root_profile_selection=sp,actual_physical_engineering=joint_pin,launch_qualified=False,quality_qualified=False))
    return h.put(output/'prepared-physical192-prerequisites-NOT-LAUNCH-QUALIFIED.json',dict(
        selection=selected,reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate'],
        original_capture_qualification=qualification,fresh_capture_context_association=s['fresh_capture_context_association'],source=h.pin(Path(__file__).resolve()),
        actual_four_native_jobs=None,actual_metadata_CPU=None,actual_exact_job_guards=None,actual_review_precommit_CPU=None,
        scientific_launch_qualified=False,quality_qualified=False,CPU_or_scientific_job_launched=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--prepare-canonical',action='store_true');g.add_argument('--prepare-frozen',action='store_true');g.add_argument('--close',action='store_true');g.add_argument('--prepare-comparison-selection',action='store_true');g.add_argument('--qualify-capture',action='store_true')
    p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--role',choices=('candidate','reference'));p.add_argument('--directory',type=Path);p.add_argument('--canonical-closeout',type=Path);p.add_argument('--engineering-joint',type=Path);p.add_argument('--engineering-joint-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not(a.prepare_canonical or a.prepare_frozen or a.close or a.prepare_comparison_selection or a.qualify_capture):print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.expected_source_sha256,'Exact selected constructor required')
    if a.qualify_capture:
        require(a.directory,'Fresh capture qualification output required')
        answer=qualify_capture(a.directory)
    elif a.close:
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
