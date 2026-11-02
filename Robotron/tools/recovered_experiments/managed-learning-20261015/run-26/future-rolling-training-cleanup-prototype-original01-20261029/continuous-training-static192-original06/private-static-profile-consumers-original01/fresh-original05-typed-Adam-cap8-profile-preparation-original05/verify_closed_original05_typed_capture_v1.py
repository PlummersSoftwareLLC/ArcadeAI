"""Exact closed original05 capture eligibility; default inert, no model loading.

This replays the ACTUAL typed progress helper on fixed recorded metadata.
It neither calls the before-anchor startup helper after its phase nor treats
its now-false no-anchor precondition as a continuing runtime condition.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

CANDIDATE='4ab677004e8a178f69d4438583a07d00a76f3b90e09eb08870ad0528fc08f871'
FIXED={'plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/window-plan-typed-Adam-adopted-v1.json', 'sha256': 'c0aecb8f555571e7f52ffd9341328b25629097ac3b3cc0816bffe72889528a5e', 'bytes': 61861, 'identity': {'device': 2304, 'inode': 81397990, 'bytes': 61861, 'mtime_ns': 1793327440360811628, 'ctime_ns': 1793327440360811628, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'prior_plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/window-plan.json', 'sha256': '97dd5446aa9f4289f3d2ac4bbaffb9e2776847d7f736a5cce4f797e85277857a', 'bytes': 56491, 'identity': {'device': 2304, 'inode': 81397970, 'bytes': 56491, 'mtime_ns': 1793326457945642689, 'ctime_ns': 1793326457945642689, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/result.json', 'sha256': '9c61d9c1203b88cd9ff13f94d08f775580276f90526d7d8b763af76adda0beb5', 'bytes': 2273, 'identity': {'device': 2304, 'inode': 81398037, 'bytes': 2273, 'mtime_ns': 1793331087831753210, 'ctime_ns': 1793331087831753210, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/endpoint-CPU.json', 'sha256': '2aab1aa66962b9aac21eae5d4e294d9fe55d29568215d3ee0f56c53bdcbe1e75', 'bytes': 3145, 'identity': {'device': 2304, 'inode': 81398034, 'bytes': 3145, 'mtime_ns': 1793331087042149249, 'ctime_ns': 1793331087042149249, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'CPU_owner': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-owner.json', 'sha256': '4775693d5b3318d5bb50edd28d27a3caaa6967a5d2be80f089d9543c71172282', 'bytes': 12755, 'identity': {'device': 2304, 'inode': 81398033, 'bytes': 12755, 'mtime_ns': 1793331084260318856, 'ctime_ns': 1793331084260318856, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'CPU_terminal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-terminal.json', 'sha256': 'c279cc662dd7b1c061c420cc611048e75a29b6d9e2a258712249a27b80032804', 'bytes': 12008, 'identity': {'device': 2304, 'inode': 81398035, 'bytes': 12008, 'mtime_ns': 1793331087810236240, 'ctime_ns': 1793331087810236240, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'CPU_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-owned-release.json', 'sha256': '46cabf631403536a3101357204712062b18426c164296a1149b7c160ac9874b0', 'bytes': 34529, 'identity': {'device': 2304, 'inode': 81398036, 'bytes': 34529, 'mtime_ns': 1793331087824092544, 'ctime_ns': 1793331087824092544, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'CPU_launch': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-launch.json', 'sha256': '82ffd6a86f31fd9b3432b083d1979400e3781181bbeff429e5e4c95dc9db172a', 'bytes': 1338, 'identity': {'device': 2304, 'inode': 81398032, 'bytes': 1338, 'mtime_ns': 1793331084253096655, 'ctime_ns': 1793331084253096655, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'anchor': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/anchor.raw.json', 'sha256': '4b8908606d860209fb330df0e74bff2487c6de9b53ff9cd1046d99707b89f70a', 'bytes': 126546, 'identity': {'device': 2304, 'inode': 81397996, 'bytes': 126546, 'mtime_ns': 1793327440519076484, 'ctime_ns': 1793327440519076484, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'threshold': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/first-threshold.raw.json', 'sha256': 'aa255b789bdd0a16a315ac71526af77775d110f483afe2aaf5feb820e44fee1e', 'bytes': 126525, 'identity': {'device': 2304, 'inode': 81398028, 'bytes': 126525, 'mtime_ns': 1793331043853164188, 'ctime_ns': 1793331043853164188, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'context': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/capture-context.raw.json', 'sha256': '480626a71be560c1b31c2c93936862b3e51a5d16f6be7835bc418b01bd0f3d7a', 'bytes': 126601, 'identity': {'device': 2304, 'inode': 81398031, 'bytes': 126601, 'mtime_ns': 1793331084228438682, 'ctime_ns': 1793331084228438682, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'entry_authority': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-CPU-authority.json', 'sha256': '42b76c1f9e54ef8a2d7a086dddc7065e81507dfcf6dff5f4061a8a7e791a18b9', 'bytes': 2246, 'identity': {'device': 2304, 'inode': 81397850, 'bytes': 2246, 'mtime_ns': 1793323469732135418, 'ctime_ns': 1793323469732135418, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'entry_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-CPU-original01/endpoint-CPU.json', 'sha256': '201d546e43ac545612d9cebee4b09f3d767b24c201c37f25ec9233b37c636aa4', 'bytes': 2117, 'identity': {'device': 2304, 'inode': 81397847, 'bytes': 2117, 'mtime_ns': 1793323468884708979, 'ctime_ns': 1793323468884708979, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'typed_entry_authority': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-same-entry-typed-Adam-CPU-authority-original01.json', 'sha256': 'c355b8ce6b93c28cb89d893adbf04cbf9be264833b4a41e894e90c68d9589b19', 'bytes': 2556, 'identity': {'device': 2304, 'inode': 81397988, 'bytes': 2556, 'mtime_ns': 1793327440356794286, 'ctime_ns': 1793327440356794286, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'typed_entry_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/endpoint-CPU.json', 'sha256': '385bc603faf2433f5b67281da66847995f4239f2910282a12b088e4c4e016eb7', 'bytes': 3163, 'identity': {'device': 2304, 'inode': 81397978, 'bytes': 3163, 'mtime_ns': 1793326460792335443, 'ctime_ns': 1793326460792335443, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'typed_entry_owner': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/CPU-original-owner.json', 'sha256': '2a1e44393d638e8a3f39813429d07a8efe817a9420918989c08365516b2bef83', 'bytes': 12945, 'identity': {'device': 2304, 'inode': 81397977, 'bytes': 12945, 'mtime_ns': 1793326458032782659, 'ctime_ns': 1793326458032782659, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'typed_entry_terminal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/CPU-original-terminal.json', 'sha256': '9f02a2f2d1bd3d1e76f0c12776b9b00ff29e6466dac210b6ce062dd2efff6d2b', 'bytes': 12182, 'identity': {'device': 2304, 'inode': 81397979, 'bytes': 12182, 'mtime_ns': 1793326461577667214, 'ctime_ns': 1793326461577667214, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'typed_entry_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/CPU-owned-release.json', 'sha256': '738ad5df7b2239efd8a3d7adf485b2d7f7fb45093fd91d2e97cb1cdb519cbd58', 'bytes': 34925, 'identity': {'device': 2304, 'inode': 81397980, 'bytes': 34925, 'mtime_ns': 1793326461588126641, 'ctime_ns': 1793326461588126641, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'source_amendment': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-selected-typed-Adam-source-amendment-original01.json', 'sha256': '4b89655b76abd1ec655ec6a9964890b330bfbb605c3bf9b6096e98249b4b5c5b', 'bytes': 7226, 'identity': {'device': 2304, 'inode': 81397989, 'bytes': 7226, 'mtime_ns': 1793327440358537325, 'ctime_ns': 1793327440358537325, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'observer_launch': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-typed-window-observer-actual-launch-original01.json', 'sha256': 'f1a7f317a9ab87bb30a411d085a159539da4beda6be779335531fe7576af7c0d', 'bytes': 14585, 'identity': {'device': 2304, 'inode': 81397995, 'bytes': 14585, 'mtime_ns': 1793327440426264750, 'ctime_ns': 1793327440426264750, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'observer_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-original05-observer-owned-closeout-original01/Root-original05-observer-normal0-owned-release.json', 'sha256': 'eaac2f883af9ade171ad8ae93db78c48e432882961934e86d179ae9c57ad72a7', 'bytes': 11247, 'identity': {'device': 2304, 'inode': 81398068, 'bytes': 11247, 'mtime_ns': 1793332499788233754, 'ctime_ns': 1793332499788233754, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'watcher': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/watch_replay_progress_typed_Adam_saturation_v3.py', 'sha256': '98ffb7eee78101b91ea29e9252b9368b011bed2befa75504fa14c240ded945a5', 'bytes': 19453, 'identity': {'device': 2304, 'inode': 81397871, 'bytes': 19453, 'mtime_ns': 1793324444286292431, 'ctime_ns': 1793324763227915708, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'library': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04-preparation/watch_learning_window_continuous_v4.py', 'sha256': '4dc714d1677f58ebebd39002e1c9f42df4828fe0ef87795b714a2f2c210938fd', 'bytes': 18615, 'identity': {'device': 2304, 'inode': 85351385, 'bytes': 18615, 'mtime_ns': 1793306998562707000, 'ctime_ns': 1793306998562863608, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'verifier': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/verify_snapshot_raw_Adam_steps_v1.py', 'sha256': '5bac4062afcf3cdf57726e13e2f1eacc37af4a819932da752452ccace93919bb', 'bytes': 5201, 'identity': {'device': 2304, 'inode': 81397870, 'bytes': 5201, 'mtime_ns': 1793324703499017045, 'ctime_ns': 1793324763227915708, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'source_family': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/prepared-original05-typed-Adam-saturation-capture-successor-SOURCE-ONLY-UNSELECTED-v1.json', 'sha256': 'e376bbebbdf0ad9fbfa9c6b68c19f9323dca665aca63094595933664e83e4798', 'bytes': 14277, 'identity': {'device': 2304, 'inode': 81397937, 'bytes': 14277, 'mtime_ns': 1793324776630808634, 'ctime_ns': 1793324776630808634, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'source_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/independent-original05-typed-Adam-saturation-verifier-and-watcher-source-peer-v1.json', 'sha256': 'd7c60a03b43db89ff03aba7fc39035788adb4153b23638a58205e12f1d684e56', 'bytes': 11286, 'identity': {'device': 2304, 'inode': 81397938, 'bytes': 11286, 'mtime_ns': 1793324931731027397, 'ctime_ns': 1793324931731027397, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'root_selection': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/Root-selected-fresh-continuous-window-original05.json', 'sha256': '69628f61c4fe2b16e6a322f28fe9d5704777435f67c37a43f402d4acf49f69ce', 'bytes': 35523, 'identity': {'device': 2304, 'inode': 81397835, 'bytes': 35523, 'mtime_ns': 1793323383743743878, 'ctime_ns': 1793323383743743878, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'domain_helper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/physical_profile_contract_v5.py', 'sha256': '182b5678948fdc3e05c234f76dfeb0dcb1298560fb4815274742dab4e159d73c', 'bytes': 16858, 'identity': {'device': 2304, 'inode': 85235757, 'bytes': 16858, 'mtime_ns': 1793311425821202483, 'ctime_ns': 1793311527249199177, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}


def require(value,reason):
    if not value:raise ValueError(reason)


def thin(value):return {k:value[k]for k in ('path','sha256','bytes')}


def checked_bytes(value,h):
    """Normalize only a recorded thin/reduced descriptor, preserving all fields."""
    path=Path(value['path']);actual=h.pin(path)
    require(path.is_absolute() and path.resolve(strict=True)==path and not path.is_symlink()
        and actual['identity']['mode']=='0o444' and actual['identity']['nlink']==1
        and actual['identity']['uid']==os.getuid() and 0<=actual['bytes']<=2<<20,
        'Bounded immutable recorded capture evidence required')
    require(thin(actual)==thin(value) and all(actual['identity'].get(k)==v for k,v in value.get('identity',{}).items()),
        'Recorded capture evidence changed')
    return h.checked(actual).read_bytes()


def read(value,h):return json.loads(checked_bytes(value,h))


def load(role,h):
    value=FIXED[role];raw=checked_bytes(value,h)
    spec=importlib.util.spec_from_file_location('_original05_closed_'+role,value['path'])
    module=importlib.util.module_from_spec(spec);exec(compile(raw,value['path'],'exec'),module.__dict__)
    return module


def normal_terminal(terminal,live,pid,invocation,resources):
    require(live['MainPID']==str(pid) and live['InvocationID']==invocation
        and terminal['ExecMainPID']==str(pid) and terminal['InvocationID']==invocation
        and terminal['MainPID']=='0' and terminal['ExecMainCode']=='1' and terminal['ExecMainStatus']=='0'
        and all(live[k]==terminal[k]==v for k,v in resources.items()),'Original normal0/resources differ')


def closed_CPU(prefix,h):
    cpu=read(FIXED['CPU' if prefix=='endpoint' else 'typed_entry_CPU'],h)
    owner=read(FIXED['CPU_owner' if prefix=='endpoint' else 'typed_entry_owner'],h)
    terminal=read(FIXED['CPU_terminal' if prefix=='endpoint' else 'typed_entry_terminal'],h)
    release=read(FIXED['CPU_release' if prefix=='endpoint' else 'typed_entry_release'],h)
    live=owner['actual_properties']
    normal_terminal(terminal,live,owner['pid'],owner['invocation_id'],dict(Type='simple',Restart='no',NRestarts='0',
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='3min'))
    require(owner['unit']==live['Id']==release['unit'] and bool(live['ControlGroup'])
        and release['original']==live and release['terminal']==terminal and release['original_birth_absent'] is True
        and release['after_release']['MainPID']=='0' and release['after_release']['ActiveState']=='inactive',
        'Original typed CPU positive release differs')
    require(cpu['verification_source']==thin(FIXED['verifier']) and cpu['CUDA_initialized'] is False
        and cpu['online_target_shapes_and_finiteness_verified'] is True and cpu['priority_phase_valid'] is True
        and cpu['priority_phase']['metric']=='ce' and cpu['optimizer_lrs']==[3.125e-6]
        and cpu['Adam_parameters']==81,'Exact recorded typed numerical verifier required')
    return cpu


def command(record,argv,h):
    require(record['argv']==argv and type(record['exit']) is int and record['exit']==0
        and record['timed_out'] is False and record['error'] is None,'Original archive/release command was not successful')
    raw=checked_bytes(record['stdout'],h);checked_bytes(record['stderr'],h)
    return dict(line.split('=',1)for line in raw.decode().splitlines()if '=' in line)


def verify_closed_capture(h):
    plan=read(FIXED['plan'],h);prior=read(FIXED['prior_plan'],h);result=read(FIXED['result'],h)
    amendment=read(FIXED['source_amendment'],h);source_family=read(FIXED['source_family'],h)
    read(FIXED['source_peer'],h)
    require(plan['verifier']==FIXED['verifier']['path'] and plan['observer_library']==thin(FIXED['library']),
        'Exact original typed verifier and observer library required')
    require(plan['capture_source_amendment']==thin(FIXED['source_amendment'])
        and plan['prior_unstarted_plan']==thin(FIXED['prior_plan'])
        and plan['root_selection']==prior['root_selection']
        and {k:v for k,v in plan.items()if k not in {'verifier','inputs','prior_unstarted_plan','capture_source_amendment','entry_verification','entry_typed_authority'}}
            =={k:v for k,v in prior.items()if k not in {'verifier','inputs','prior_unstarted_plan','capture_source_amendment','entry_verification','entry_typed_authority'}},
        'Original passed entry/unstarted plan was silently changed')
    require(amendment['schema']=='robotron-root-original05-typed-Adam-entry-source-amendment-v1'
        and amendment['status']=='ROOT_SELECTED_NEW_SOURCES_SAME_PASSED_ENTRY_BEFORE_OWN_ANCHOR'
        and amendment['prior_unstarted_plan']==thin(FIXED['prior_plan'])
        and amendment['root_selection']==plan['root_selection']
        and amendment['source_family']==thin(FIXED['source_family'])
        and amendment['selected_sources']==source_family['selected_sources']
        and amendment['selected_sources']=={key:thin(FIXED[key])for key in ('watcher','verifier','library')}
        and amendment['old_plan_or_entry_modified'] is False and amendment['old_window_counts_reused'] is False,
        'Explicit original typed source/entry adoption differs')
    expected={value['path']:value for value in prior['inputs']}
    for value in [*amendment['new_evidence_inputs'],plan['capture_source_amendment']]:
        require(value['path']not in expected or expected[value['path']]==value,'Conflicting original input alias')
        expected[value['path']]=value
    require(plan['inputs']==list(expected.values()),'Original source/input holds lost or refreshed')
    for value in plan['inputs']:
        # Existing thin3 plan guards may be ordinary664 source files; the
        # immutable full8 continuous-context domain remains separate below.
        actual=h.pin(Path(value['path']));require(thin(actual)==value,'Original capture input bytes changed')
    root=read(FIXED['root_selection'],h)
    require(plan['root_selection']==root_pin(FIXED['root_selection'])
        and plan['owner']==root['owner']==plan['continuous_context']['owner']
        and plan['expected_exposure_lineage']==root['expected_exposure_lineage']
        and plan['continuous_context']['source_and_control_inputs']==root['source_and_control_inputs']
        and plan['continuous_context']['server_stamp']==root['server_stamp']
        and plan['continuous_context']['policy_generation']==root['policy_generation']
        and plan['continuous_context']['slot_eval']==root['slot_eval']
        and plan['continuous_context']['environment']==root['environment']
        and root['prior_window_counts_reused'] is False,'Original Root capture provenance differs')
    domain=load('domain_helper',h)
    for value in plan['continuous_context']['source_and_control_inputs']:
        h.checked(domain.normalize_capture_fullpin(value))
    original_entry=read(FIXED['entry_authority'],h);old_cpu=read(FIXED['entry_CPU'],h)
    typed_authority=read(FIXED['typed_entry_authority'],h);entry=closed_CPU('entry',h);cpu=closed_CPU('endpoint',h)
    require(plan['entry_typed_authority']==thin(FIXED['typed_entry_authority'])
        and plan['entry_verification']==thin(FIXED['typed_entry_CPU'])
        and typed_authority['preserved_original_entry_authority']==thin(FIXED['entry_authority'])
        and typed_authority['actual_CPU_verification']==thin(FIXED['typed_entry_CPU'])
        and typed_authority['original_exit']==0 and typed_authority['original_scope_released'] is True
        and original_entry['endpoint']==typed_authority['checkpoint']==entry['checkpoint']==old_cpu['checkpoint']
        and old_cpu['clocks']==entry['clocks'] and old_cpu['Adam_step_min']==entry['Adam_step_min']==plan['entry_Adam_step'],
        'Same passed immutable original05 entry and new typed CPU proof required')
    require(result['state']=='captured_CPU_verified' and result['owner']==plan['owner']
        and result['thresholds']==plan['thresholds']==dict(elapsed_s=3600,applied_updates=5000,replay_inserts=1000000)
        and result['endpoint']==cpu['checkpoint'] and result['endpoint']['sha256']==CANDIDATE
        and result['endpoint']['bytes']==275186008 and result['CPU_verification']==thin(FIXED['CPU'])
        and result['original_DQN_window_unchanged'] is True and result['quality_qualified'] is result['promotion'] is False,
        'Only exact completed original05 endpoint is eligible')
    anchor=read(FIXED['anchor'],h);threshold=read(FIXED['threshold'],h);current=read(FIXED['context'],h)
    observer=load('library',h);watcher=load('watcher',h)
    exposures=[observer.exposure(value)for value in (anchor,threshold,current)]
    for value in exposures:
        for kind in ('optimizer','replay'):
            row=value[kind];require(row['available'] is row['enabled'] is True
                and {k:row[k]for k in observer.FIELDS}==plan['expected_exposure_lineage'][kind],'Original own epoch changed')
        total=value['optimizer']['total']
        require(total['unavailable']==0 and total['attempts_started']==total['outcomes_recorded']
            and total['outcomes_recorded']==total['applied']+total['amp_skipped'],'Original actual optimizer outcomes differ')
    require(result['added']==watcher.additions(current,anchor,result['added']['elapsed_s'])
        and watcher.ready(result['added'],plan['thresholds']),'Own observed dose/attribution differs')
    progress=watcher.endpoint_progress_proof(cpu,entry,plan,anchor,threshold,result['added'],observer)
    require(progress==result['progress_proof'] and progress['classification']=='EXACT_RAW_FLOAT32_2P24_Adam_SATURATION_WITH_OWN_APPLIED_DOSE',
        'Exact recorded typed progress proof must be independently recomputed')
    launch=read(FIXED['observer_launch'],h);closed=read(FIXED['observer_release'],h)
    owner=closed['original'];live=launch['first_actual_scope'];unit=owner['unit']
    require(launch['actual_exit']==0 and launch['original']==owner and launch['plan']==thin(FIXED['plan'])
        and launch['argv'][-3:]==[FIXED['watcher']['path'],'--plan',FIXED['plan']['path']],
        'Actual original observer launch/source/plan differs')
    require(closed['schema']=='robotron-Root-original-candidate-window-observer-closeout-v1'
        and closed['status']=='ORIGINAL_WINDOW_CAPTURED_CPU_VERIFIED_OBSERVER_NORMAL0_ARCHIVED_RELEASED'
        and type(closed['actual_exit'])is int and closed['actual_exit']==0
        and closed['original_birth_absent'] is closed['cgroup_absent'] is True
        and closed['captured_cgroup']==live['ControlGroup'] and bool(live['ControlGroup'])
        and closed['actual_result']==thin(FIXED['result']) and closed['endpoint_CPU_owned_release']==thin(FIXED['CPU_release']),
        'Positive original observer normal0 and owned closure required')
    require(len(closed['archives'])==3,'Exact original show/cat/journal archives required')
    terminal=command(closed['archives'][0],['systemctl','--user','show',unit],h)
    command(closed['archives'][1],['systemctl','--user','cat',unit],h)
    command(closed['archives'][2],['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+owner['invocation_id']],h)
    normal_terminal(terminal,live,owner['pid'],owner['invocation_id'],dict(Type='exec',Restart='no',NRestarts='0',
        RemainAfterExit='yes',CPUQuotaPerSecUSec='1s',MemoryMax=str(256<<20),MemorySwapMax='0',TasksMax='32',
        RuntimeMaxUSec='4h 7min',TimeoutStopUSec='10s',SendSIGKILL='no'))
    release=closed['release'];require(release['unit']==unit and release['confirmed_absent'] is True,'Original owned release not positive')
    command(release['before'],['systemctl','--user','show',unit],h)
    command(release['stop'],['systemctl','--user','stop',unit],h)
    final=command(release['final'],['systemctl','--user','show',unit],h)
    require(final['MainPID']=='0' and final['ActiveState']=='inactive' and final['LoadState']=='not-found',
        'Original observer unit was not positively released')
    return dict(result=result,CPU=cpu,plan=plan,progress=progress,entry_CPU=entry,
        capture_plan=FIXED['plan'],capture_result=FIXED['result'],source=h.pin(Path(__file__).resolve()),
        all_original_CPU_and_observer_closures_verified=True,classification_transfer_to_other_endpoint=False)


def root_pin(value):
    """The capture Root selection used integer modes; normalize no other field."""
    out=json.loads(json.dumps(value));out['identity']['mode']=int(out['identity']['mode'],8)
    return out


if __name__=='__main__':print('SOURCE_ONLY_INERT_NO_ACTIONS')
