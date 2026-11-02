"""Root-only, default-inert metadata assembler; never imports a runtime or reads a policy.

Prepare only after the actual dose, named copy, original CPU closure and observer
handoff. Root separately executes the frozen preflight and future original jobs.
Snapshot-source and checkpoint descriptors are held without opening their files.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import uuid

B = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
TEMPLATE = B / 'LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031'
CASE = B / 'post-repair-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
N2 = B / 'post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031'
CONTROL = '3b1a46f7de088698487877ff30171f7dbe1c9d289f39778065a16e85b48a5521'
CPU_SHA = '467cd0cd95a9bd68ace6227e165c398ce63e863f204437de58b7b10ed4100269'
COPY_SHA = 'ebf962087e394e95b292b28ef520d80deffc512b0e3eda606389d149f57d2083'
TAG = 'post-repair-LR625-dose60k-replay20M-learner16M-original01-20261031'
CLOCKS = {'training_steps', 'learner_frame_count', 'optimized_samples', 'frame_count'}
FULL8 = {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'}
FIXED = {'prepared': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json', 'sha256': '3722a9834fb33ad5cbf8ab151a5d8e4d3972bdbb606e0af2b97f96e0d0b59cc3'}, 'selection': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/Root-prospective-matched-fixed-cutoff-selection.json', 'sha256': 'c0263bd255a16e093badb7a76192f19beee86d9871176da7b5327f6a5a47d863'}, 'sources': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/Root-selected-fixed-cutoff-source-map.json', 'sha256': '81e715cb30e5660bb88711bee346cdabeb86413fca942fe167a663ea4bc49d38'}, 'configs': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/Root-original-controller-configs.json', 'sha256': 'e8de6a8e2bfe28d4c80d590d4b83b7b6692bd77dc138ac24d6c1fe72928201f3'}, 'R1': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/R1/job.json', 'sha256': 'ad5d0ac20ec34a926cee2f9dadb25ca5f338b1aad3da7462e018baa7b7fd89a4'}, 'C1': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/C1/job.json', 'sha256': '6a3a0634621727a1ee81b67cc7eb9dfe24c3c4a2809c48805c5115afd6a93df9'}, 'R1config': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/R1/Root-original-C218-config.json', 'sha256': 'eb59240e6b0da4ea603d4c4827485e2f16948dad2be7dfff30f8abbc22bfcf99'}, 'C1config': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/C1/Root-original-C218-config.json', 'sha256': 'd901e619c2be7494bb1c1a305897267f4fdb3d9774599799b413ca96f12b1a83'}, 'controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031/future-post-repair-frozen-screen-source-only-original01/Root-control-post-repair-LR625-vs-S2-C218-v1.py', 'sha256': '42838b75136c28d5dbaf5d34ac0b29aa7cbbc1f3e692c821c383a5ebf5764f0a'}, 'controller_proof': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031/future-post-repair-frozen-screen-source-only-original01/post-repair-LR625-C218-one-prefix-source-proof-v1.json', 'sha256': '0352d13d55a339a61bb0840f35f21aa0ee467678ef79fb85a7f6d8b44f58db79'}, 'preflight_source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031/future-post-repair-frozen-screen-source-only-original01/Root-preflight-post-repair-frozen-pair-v2.py', 'sha256': 'd9bdfac4da695f42bbf9633444c7fe11b0eeeeb6cc06063ec426bb9a76ae81a8'}}
PRIOR_JOBS = [{'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/df519-vs-S2-fixed-cutoff-liveness-screen-original01-20261031/R1/job.json', 'sha256': 'f832c101002b282690b42f3842e28b64000d0011b3cf538d4b6870eb2e8dbcb0'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/df519-vs-S2-fixed-cutoff-liveness-screen-original01-20261031/C1/job.json', 'sha256': '956efcc7a36434434d5aa9ef1d7459b5453895167bfe2838c7bb8a3acd20105a'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR625-postdose-vs-frozenS2-fixedcutoff-screen-original01-20261031/R1/job.json', 'sha256': '10d1cf9c9b716436a9e48449676aef67389c227755fe2bb3f04346f18c7c929e'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR625-postdose-vs-frozenS2-fixedcutoff-screen-original01-20261031/C1/job.json', 'sha256': 'fa68e6ead1236881f2c6ca4190572e1bb328bdc27279303e9e69c0b8fada3446'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/later-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031/R1/job.json', 'sha256': '1d9d3cae8c18f501b28bae97b71d1b0294b4f463e90a91c0456a5268a5153288'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/later-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031/C1/job.json', 'sha256': '17e536e7d1c08eb90ed37ca076cf54f5ce0175857837d6d110d8b2d49bdbb347'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/expert05-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031/R1/job.json', 'sha256': 'ea425e00ccc08db9bcd2df3c8e1a9f16d732d25f72ee794510023b63012917d8'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/expert05-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031/C1/job.json', 'sha256': 'e0875f67038df61f8c0a74be58a8899a1cef4281d118214d59d87faf27f5bada'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/R1/job.json', 'sha256': 'ad5d0ac20ec34a926cee2f9dadb25ca5f338b1aad3da7462e018baa7b7fd89a4'}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/C1/job.json', 'sha256': '6a3a0634621727a1ee81b67cc7eb9dfe24c3c4a2809c48805c5115afd6a93df9'}]


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def descriptor(value, immutable=True):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256', 'bytes', 'identity'}, 'Full metadata descriptor required')
    require(type(value['path']) is str and Path(value['path']).is_absolute(), 'Absolute descriptor path required')
    require(type(value['sha256']) is str and len(value['sha256']) == 64 and all(c in '0123456789abcdef' for c in value['sha256']), 'SHA256 required')
    require(type(value['bytes']) is int and value['bytes'] >= 0, 'Exact descriptor length required')
    i = value['identity']
    require(isinstance(i, dict) and set(i) == FULL8 and i['bytes'] == value['bytes'], 'Full8 descriptor required')
    require(all(type(i[k]) is int and i[k] >= 0 for k in FULL8 - {'mode'}), 'Typed full8 required')
    if immutable:
        require(i['uid'] == 1001 and i['mode'] == '0o444' and i['nlink'] == 1, 'Owned immutable single-link input required')
    return value


def read_checked(path, expected_sha, expected=None):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Exact absolute input path required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == 1001 and stat.S_IMODE(before.st_mode) == 0o444
            and before.st_nlink == 1 and before.st_size <= 2 << 20, 'Bounded owned immutable metadata/source required')
    stamp = identity(before)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd)) == stamp, 'Opened input identity differs')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read((2 << 20) + 1)
        require(identity(os.fstat(fd)) == stamp, 'Input changed during read')
    finally:
        os.close(fd)
    require(identity(path.lstat()) == stamp and len(raw) == before.st_size, 'Input changed after read')
    actual = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=stamp)
    require(actual['sha256'] == expected_sha, 'Immutable input digest differs: ' + str(path))
    if expected is not None:
        require(actual == descriptor(expected), 'Input full8 differs: ' + str(path))
    return raw, actual


def metadata(value):
    descriptor(value)
    require(Path(value['path']).suffix == '.json', 'Only selected JSON metadata may be followed')
    raw, pin = read_checked(value['path'], value['sha256'], value)
    data = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON: ' + x)))
    require(isinstance(data, dict), 'JSON object required')
    json.dumps(data, allow_nan=False)
    return data


def content(value):
    return {k: value[k] for k in ('path', 'sha256', 'bytes')}


def clocks(value):
    require(isinstance(value, dict) and set(value) == CLOCKS
            and all(type(v) is int and v >= 0 for v in value.values()), 'Four exact integer clocks required')
    return value


def near(value, expected):
    return type(value) in (int, float) and math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-12)


def reduced(value):
    return dict(path=value['path'], sha256=value['sha256'], bytes=value['bytes'],
                identity={k: value['identity'][k] for k in ('device', 'inode', 'mode', 'uid', 'nlink')})


def put(path, data):
    raw = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(path.lstat()))


def prepare(args):
    require(args.selection and args.selection_sha256, 'Root sealed input selection and digest required')
    raw, binding_pin = read_checked(args.selection, args.selection_sha256)
    binding = json.loads(raw)
    require(binding['schema'] == 'robotron-Root-post-repair-LR625-frozen-screen-DATA-inputs-v1'
            and binding['status'] == 'ROOT_SELECTED_ACTUAL_DOSE_COPY_CPU_AND_MAIN_CONTEXT_FOR_DATA_ONLY', 'Actual Root DATA selection required')
    prerequisites = binding['Root_prerequisites']
    require(set(prerequisites) == {'original55529_tool_terminal0', 'original55529_process_absent', 'CONTROL_handoff_complete'}
            and all(value is True for value in prerequisites.values()), 'Root actual tool/process/CONTROL acknowledgements required')
    fixed, pins = {}, {}
    for name, selected in FIXED.items():
        data, pins[name] = read_checked(selected['path'], selected['sha256'])
        if selected['path'].endswith('.json'):
            fixed[name] = json.loads(data)
    old = fixed['selection']
    require(pins['prepared']['sha256'] == '3722a9834fb33ad5cbf8ab151a5d8e4d3972bdbb606e0af2b97f96e0d0b59cc3', 'Fixed F template differs')
    require(old['ordered_legs'] == ['R1', 'C1'] and old['reference']['checkpoint']['sha256'] ==
            '06558cbc185b76b2b44229ddfe469d2a92037e70f89de2481e8fb055f2c736ad', 'Frozen S2 reference/order differs')
    main = binding['current_main']
    require(set(main) == {'owner', 'startup_authority', 'startup_held', 'API', 'environment', 'exposure'}, 'Exact current Main ABI required')
    require(main['owner']['pid'] == 1644742 and type(main['owner']['pid']) is int
            and main['owner']['starttime_ticks'] == 36415496 and type(main['owner']['starttime_ticks']) is int,
            'Repaired original Main owner differs')
    require(main['environment'] == old['current_main']['environment'] and main['API'] == old['current_main']['API'], 'Five-key recipe/API differs')
    require(set(main['exposure']) == {'optimizer', 'replay'}, 'Both current exposure identities required')
    for value in main['exposure'].values():
        require(set(value) == {'process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason'}
                and type(value['process_id']) is int and value['process_id'] == 1644742
                and type(value['instance_monotonic_ns']) is int and value['instance_monotonic_ns'] > 0
                and type(value['epoch']) is int and value['epoch'] > 0
                and type(value['epoch_reason']) is str and bool(value['epoch_reason']), 'Exact new Main exposure identity required')
    for key in ('startup_authority', 'startup_held'):
        descriptor(main[key])
        require(main[key] != old['current_main'][key], 'Old Main startup origin must not be reused')
    ctx = metadata(binding['current_Main_metadata'])
    sources = binding['current_Main_snapshot_sources']
    require(ctx['current_main_inline'] == main and ctx['sources'] == sources
            and ctx['role_counts'] == binding['current_Main_observed_role_counts']
            and ctx['observed_unix_s'] == binding['current_Main_observed_unix_s'], 'Sealed new Main context joins differ')
    require({'API', 'policy', 'game_settings'} <= set(sources) and len(sources) <= 16, 'Bounded ordinary Main snapshot descriptors required')
    for value in sources.values():
        descriptor(value)
    require(sum(p['sha256'] == CONTROL for p in sources.values()) == 1, 'One actual 3b learning-control snapshot required')
    require(type(binding['current_Main_observed_unix_s']) in (int, float) and math.isfinite(binding['current_Main_observed_unix_s'])
            and binding['current_Main_observed_unix_s'] > 0, 'Actual observation clock required')
    roles = binding['current_Main_observed_role_counts']
    require(set(roles) == {'TRAIN', 'EVAL'} and type(roles['TRAIN']) is int and roles['TRAIN'] == 155
            and type(roles['EVAL']) is int and 0 <= roles['EVAL'] <= 37, 'Truthful current role counts required')
    fleet = binding['current_fleet']
    require(type(fleet['pid']) is int and fleet['pid'] == 1646378 and type(fleet['birth']) is int
            and fleet['birth'] == 36456134 and bool(fleet['unit']) and bool(fleet['invocation_id']), 'Repaired original fleet differs')
    candidate = binding['candidate']
    require(set(candidate) == {'checkpoint', 'expected_policy_clocks', 'authority', 'display_name'}, 'Exact candidate descriptor ABI required')
    descriptor(candidate['checkpoint'])
    require(type(candidate['display_name']) is str and 1 <= len(candidate['display_name']) <= 96
            and all(32 <= ord(c) <= 126 for c in candidate['display_name']), 'Bounded printable policy label required')
    saved, floors = clocks(candidate['expected_policy_clocks']), clocks(binding['candidate_minimum_saved_clocks'])
    require(all(saved[k] >= floors[k] for k in CLOCKS), 'Saved policy clocks precede actual dose point')
    cpu = metadata(candidate['authority'])
    receipt = metadata(binding['candidate_published_policy_copy'])
    closed = metadata(binding['candidate_original_CPU_closeout'])
    point = metadata(binding['candidate_completed_dose_point'])
    require(cpu['schema'] == 'robotron-recovery-snapshot-CPU-verification-v1' and cpu['CUDA_initialized'] is False
            and cpu['verification_source']['sha256'] == CPU_SHA and cpu['optimizer_lrs'] == [5e-5 * .125]
            and cpu['clocks'] == saved and content(cpu['checkpoint']) == content(candidate['checkpoint'])
            and cpu['online_target_shapes_and_finiteness_verified'] is True and cpu['priority_phase_valid'] is True
            and cpu['Adam_parameters'] == 81 and cpu['quality_qualified'] is False, 'Actual unchanged policy-only CPU proof differs')
    require(receipt['schema'] == 'robotron-policy-only-published-FD-copy-v1' and receipt['independent_copy'] == candidate['checkpoint']
            and receipt['streaming_sha256'] == candidate['checkpoint']['sha256']
            and receipt['copy_source']['sha256'] == COPY_SHA
            and receipt['atomic_publisher_source']['sha256'] == 'd2a95ff0828df2a00ac86049965b6df304d26b50263b76d027d27a586ff77152'
            and receipt['source_path'] == str(B.parents[2] / 'models_dqn' / 'managed-checkpoints' / (TAG + '.pt'))
            and receipt['Main_or_model_or_optimizer_or_replay_control_mutated'] is False
            and receipt['fullstate_or_replay_backup_claimed'] is False, 'Exact named independent copy differs')
    require(type(closed['actual_normal_exit']) is int and closed['actual_normal_exit'] == 0
            and closed['original_process_absent'] is True and closed['observed_current_birth'] is None
            and closed['all_three_original_archives_normal0'] is True and closed['launch_cgroup_empty_or_absent'] is True
            and closed['unit_confirmed_not_found'] is True and closed['checkpoint'] == candidate['checkpoint']
            and content(closed['report']) == content(candidate['authority'])
            and content(closed['copy_receipt']) == content(binding['candidate_published_policy_copy'])
            and content(closed['actual_dose_endpoint']) == content(binding['candidate_completed_dose_point'])
            and closed['saved_clocks'] == saved and closed['actual_endpoint_four_clock_floors'] == floors,
            'Actual original CPU/copy/endpoint positive closure differs')
    require(point['status'] == 'ALL_THREE_ACTUAL_DOSE_TARGETS_REACHED'
            and point['Main_owner'] == dict(pid=1644742, birth=36415496)
            and point['control_sha256'] == CONTROL and near(point['actual_LR'], 5e-5 * .125)
            and type(point['actual_manual_expert_pct']) is int and point['actual_manual_expert_pct'] == -1
            and near(point['actual_effective_expert'], .1) and near(point['actual_epsilon'], .1)
            and clocks(point['logical_clocks_at_qualified_point']) == floors
            and point['optimizer_identity'] == main['exposure']['optimizer']
            and point['replay_identity'] == main['exposure']['replay'], 'Actual same-owner dose/recipe/clock/exposure joins differ')
    for key, target in [('applied_updates', 60000), ('replay_additions', 20000000), ('learner_frames', 16000000)]:
        require(type(point['actual_deltas'][key]) is int and point['actual_deltas'][key] >= target, 'Actual dose floor missing: ' + key)
    # Authenticate the named acknowledgement and Root's positive observer closeout,
    # without inventing their internal observation schema or re-observing owners.
    metadata(binding['candidate_named_acknowledgement'])
    metadata(binding['dose_observer_positive_closeout'])
    if binding.get('candidate_CPU_metadata_peer') is not None:
        metadata(binding['candidate_CPU_metadata_peer'])
    previous = set()
    for selected in PRIOR_JOBS:
        data, unused = read_checked(selected['path'], selected['sha256'])
        job = json.loads(data)
        previous.update(job['sessions'].values())
        previous.update(job['connections'].values())
    require(len(previous) == 640, 'Exact F plus previous512 transport identities required')
    tokens = [uuid.uuid4().hex for unused in range(128)]
    require(len(set(tokens)) == 128 and not set(tokens) & previous, 'New transport identity collision')
    require(not CASE.exists() and not CASE.is_symlink(), 'Entire future case must be fresh; no partial preparation reuse')
    source_raw = Path(__file__).read_bytes()
    source_pin = dict(path=str(Path(__file__).absolute()), sha256=hashlib.sha256(source_raw).hexdigest(),
                      bytes=len(source_raw), identity=identity(Path(__file__).lstat()))
    descriptor(source_pin)
    selected_sources = copy.deepcopy(fixed['prepared']['selected_sources'])
    selected_sources['controller'] = pins['controller']
    source_map = copy.deepcopy(fixed['sources'])
    source_map.update(selected=selected_sources, preflight_source=pins['preflight_source'], template_source_map_history=pins['sources'],
        current_controller_derivation=dict(exact_parent_proof=pins['controller_proof'],
            only_replacement='robotron-LR9375-S2-fixedcutoff-score- -> robotron-post-repair-LR625-S2-fixedcutoff-score-',
            inverse_whole_bytes_equal=True, changed_function='checked_config', other_function_ASTs_unchanged=12),
        current_controller_only_change='One future unit-prefix literal; native8c8 and all operation/resource kernels unchanged.',
        current_controller_source_peer=None,
        historical_proof_scope='Inherited proof pins are immutable scientific/source history; no old Main/candidate is active authority.')
    source_map['proofs'] = [*source_map['proofs'], pins['controller_proof'], source_pin]
    CASE.mkdir(mode=0o700)
    for leg in ('R1', 'C1'):
        (CASE / leg).mkdir(mode=0o700)
    sources_pin = put(CASE / 'Root-selected-fixed-cutoff-source-map.json', source_map)
    keep = ('schema', 'status', 'data_preparation_status', 'ordered_legs', 'screen_only', 'promotion', 'private_python',
            'reference', 'reference_saved_checkpoint_clocks', 'shared_boot_interpretation', 'protected_incumbent',
            'old_capture_window_or_462_inputs_required', 'old_scores_or_jobs_reused', 'private_origin_idle_timeout_s',
            'unfinished_freshness_bound_ns', 'assessment_plan', 'private_score_stall_timeout_s',
            'private_lua_score_stall_timeout_s', 'private_protocol_sources', 'matched_private_liveness_source_packet',
            'matched_private_liveness_source_peer', 'matched_private_liveness_CPU_report', 'matched_private_liveness_CPU_owned_closeout')
    selection = {k: copy.deepcopy(old[k]) for k in keep}
    selection.update(candidate=candidate, current_main=main, candidate_saved_checkpoint_clocks=saved,
        candidate_published_policy_copy=binding['candidate_published_policy_copy'],
        candidate_original_CPU_closeout=binding['candidate_original_CPU_closeout'],
        candidate_CPU_metadata_peer=binding.get('candidate_CPU_metadata_peer'),
        candidate_minimum_saved_clocks=floors, candidate_CPU_saved_clocks_meet_recorded_floor=True,
        qualified_dose_point_is_exact_checkpoint_applied_count=False, candidate_exact_saved_applied_counter=None,
        completed_dose_point=binding['candidate_completed_dose_point'],
        current_Main_metadata=binding['current_Main_metadata'], current_Main_snapshot_sources=sources,
        current_Main_observed_unix_s=binding['current_Main_observed_unix_s'], current_Main_observed_role_counts=roles,
        current_fleet=fleet, source_map=sources_pin, template_prepared_history=pins['prepared'],
        template_selection_history=pins['selection'], Root_selected_actual_policy_and_context_inputs=binding_pin,
        actual_current_Main_LR=5e-5 * .125, actual_current_Main_control_sha256=CONTROL,
        actual_current_Main_manual_expert_pct=-1, actual_current_Main_effective_expert=.1, actual_current_Main_epsilon=.1,
        private_protocol_training_experiment_label=fixed['R1']['training_experiment'],
        private_protocol_training_experiment_scope='Inherited private-server/journal protocol label only; not a claim about either checkpoint saved experiment or the current Main learning-control experiment.',
        Main_training_experiment_label_selected_by_LR_control=None,
        current_Main_learning_control_source=next(p for p in sources.values() if p['sha256'] == CONTROL),
        Main_startup_held_restoration_origin_only=True, new_Main_restore_claimed_by_this_policy_screen=False,
        source_authority_scope='New repaired Main origin is the selected actual startup/held metadata; this candidate is only a later policy copy. No new fullstate, replay restore, exact saved applied count or scaler qualification is claimed.',
        interpretation='Fresh frozen S2 reference then post-repair LR625 candidate; all32 first-game full cutoff scores each. No historical score adoption, IID/causal LR claim or automatic promotion.',
        future_output=str(CASE), selected_unix_s=time.time(), Root_live_resource_preflight_performed=False,
        Root_original_native_or_controller_validators_executed_by_this_preparation=False, actual_launch=None)
    selection_pin = put(CASE / 'Root-prospective-matched-fixed-cutoff-selection.json', selection)
    reference_receipts = [p for p in fixed['R1']['inputs'] if p['path'].endswith('/Root-stopped-S2-checkpoint-and-independent-copy.json')]
    require(len(reference_receipts) == 1, 'Exact historical S2 independent-copy provenance required')
    common = [selection_pin, sources_pin, source_pin, binding_pin, pins['preflight_source'], pins['controller'], pins['controller_proof'],
              pins['prepared'], pins['selection'], pins['sources'], *source_map['proofs'],
              *selected_sources.values(), main['startup_authority'], main['startup_held'],
              binding['current_Main_metadata'], *sources.values(), binding['candidate_completed_dose_point'],
              binding['candidate_published_policy_copy'], candidate['authority'], binding['candidate_original_CPU_closeout'],
              binding['candidate_named_acknowledgement'], binding['dose_observer_positive_closeout'], *reference_receipts]
    if binding.get('candidate_CPU_metadata_peer') is not None:
        common.append(binding['candidate_CPU_metadata_peer'])
    jobs, config_pins = {}, {}
    for index, leg in enumerate(('R1', 'C1')):
        job = copy.deepcopy(fixed[leg])
        policy = selection['reference' if leg == 'R1' else 'candidate']
        label = 'post-repair-LR625-vs-S2-fixedcutoff-' + leg + '-original01-20261031'
        job.update(output=str(CASE / leg / 'runtime-original01'), checkpoint=policy['checkpoint'],
            expected_policy_clocks=policy['expected_policy_clocks'], policy_authority=policy['authority'],
            current_main=main, screen_selection=selection_pin, label=label, measurement_label=label,
            sessions={str(slot): tokens[index * 64 + n] for n, slot in enumerate(job['actor_slots'])},
            connections={str(slot): tokens[index * 64 + 32 + n] for n, slot in enumerate(job['actor_slots'])})
        # Rebuild from actual dependencies, not basename substitutions in the
        # private source family or old Main/candidate/input manifests.
        dependencies = [*common, job['source_package'], job['seed_runtime'], job['screen_support'], job['completion_codec'],
                        *job['components'].values(), job['boot_seed']['module'], *job['boot_seed']['inputs'],
                        policy['checkpoint'], policy['authority']]
        unique = {}
        for value in dependencies:
            path = value['path']
            require(path not in unique or unique[path] == value, 'Conflicting dependency descriptors: ' + path)
            unique[path] = value
        job['inputs'] = list(unique.values())
        allowed = {'output', 'checkpoint', 'expected_policy_clocks', 'policy_authority', 'current_main',
                   'screen_selection', 'label', 'measurement_label', 'sessions', 'connections', 'inputs'}
        require(all(job[k] == fixed[leg][k] for k in job if k not in allowed), 'Scientific template field changed')
        job_pin = put(CASE / leg / 'job.json', job)
        config = copy.deepcopy(fixed[leg + 'config'])
        argv = copy.deepcopy(config['argv'])
        argv[argv.index('--job') + 1] = job_pin['path']
        argv[argv.index('--job-sha256') + 1] = job_pin['sha256']
        config.update(argv=argv, output=str(CASE / leg / 'controller-execution-original01'),
            unit='robotron-post-repair-LR625-S2-fixedcutoff-score-' + leg.lower() + '-original01-20261031.service',
            pins=[reduced(job_pin), reduced(job['runtime'])])
        config_pins[leg] = reduced(put(CASE / leg / 'Root-original-C218-config.json', config))
        jobs[leg] = dict(job=job_pin, argv=argv)
    configs_pin = put(CASE / 'Root-original-controller-configs.json', dict(ordered_legs=['R1', 'C1'],
        configs=config_pins, source=reduced(pins['controller']), no_launch_performed=True))
    prepared = dict(schema=fixed['prepared']['schema'], status='DATA_NOT_LAUNCHED', ordered_legs=['R1', 'C1'],
        screen_only=True, promotion=False, selection=selection_pin, source_selection=selection_pin, sources=sources_pin,
        selected_sources=selected_sources, preflight_source=pins['preflight_source'], controller_configs=configs_pin, jobs=jobs,
        template_prepared_history=pins['prepared'], current_Main_metadata=binding['current_Main_metadata'],
        Root_selected_actual_policy_and_context_inputs=binding_pin,
        actual_candidate_copy_receipt=binding['candidate_published_policy_copy'], actual_candidate_CPU_report=candidate['authority'],
        actual_candidate_CPU_closeout=binding['candidate_original_CPU_closeout'],
        actual_candidate_CPU_metadata_peer=binding.get('candidate_CPU_metadata_peer'),
        completed_dose_point=binding['candidate_completed_dose_point'], candidate_minimum_saved_clocks=floors,
        C1_requires_actual_R1_exit0_and32_valid_scores_and_all_owned_writers_closed=True,
        Root_live_resource_preflight_performed=False, original_validators_executed_by_this_preparation=False,
        launch_performed=False, original192_cohort_qualification_claimed=False,
        old_R1_scores_adopted=False, failed_old_C1_retried_or_rescued=False,
        actual_outer=None, actual_results=None)
    prepared_pin = put(CASE / 'prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json', prepared)
    print(json.dumps(dict(status='DATA_NOT_LAUNCHED', prepared=prepared_pin, selection=selection_pin,
                          controller_configs=configs_pin, jobs=jobs, actual_validators_or_launch=False), allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--selection')
    parser.add_argument('--selection-sha256')
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY: no metadata reads, output writes, imports or actions')
        return
    prepare(args)


if __name__ == '__main__':
    main()
