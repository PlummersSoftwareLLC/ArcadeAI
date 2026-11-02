"""Exact closed predecessor and effective evaluator provenance; definitions only.

The failed914M disposition is never normalized into a positive quality result.
The held main socket remains f44. Effective helper provenance is additional.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

CLOSED = {'invalid_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/same-LR25-914M-original-invalid-R1-forensic-archive-20261018/root-original-invalid914M-disposition-and-source-freeze-release.json', 'sha256': 'bbb073f647c0dfcece6f29053daa0306eda400f1f1bb2d3cd57614442af5d39e', 'bytes': 7608, 'identity': {'device': 2304, 'inode': 82575401, 'bytes': 7608, 'mtime_ns': 1792349187106174825, 'ctime_ns': 1792349187106174825, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'invalid_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/same-LR25-914M-invalid-R1-forensic-independent-saved-review-20261018/review-receipt.json', 'sha256': '1e1357cd48ef9cf93f650e21e472550bf8a811773c55654017d610751108537d', 'bytes': 13779, 'identity': {'device': 2304, 'inode': 82575405, 'bytes': 13779, 'mtime_ns': 1792349288919554880, 'ctime_ns': 1792349288919554880, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'guard_six': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/continuous-zero-dip-wave2-reviewed2-CPU-original01-root-preparation-20261018/root-actual-six-regressions-and-private-wire-outcomes.json', 'sha256': '113b280c98c6eba8c54531f74e7e5db1e41bc5b297e174db27ee8a3b66862ec7', 'bytes': 8592, 'identity': {'device': 2304, 'inode': 82575442, 'bytes': 8592, 'mtime_ns': 1792350427528617254, 'ctime_ns': 1792350427528617254, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'guard_six_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/continuous-zero-dip-wave2-reviewed2-CPU-independent-saved-review-20261018/review-receipt.json', 'sha256': 'daf501f7cc5f149dfcd832bf740048f447dfc637a2e4eaff587f4f450b5681f8', 'bytes': 19766, 'identity': {'device': 2304, 'inode': 82575444, 'bytes': 19766, 'mtime_ns': 1792350489464518022, 'ctime_ns': 1792350489464518022, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'companion_manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/frozen_continuous_guard_evaluator_proposal/preparation-manifest.json', 'sha256': '978442569ec182e6da58e3331c723810c380c7e9a03c466ceabde452eba47a89', 'bytes': 15337, 'identity': {'device': 2304, 'inode': 82575421, 'bytes': 15337, 'mtime_ns': 1792350582377190475, 'ctime_ns': 1792350582377190475, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'companion_source_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/frozen-continuous-guard-evaluator-independent-source-review-20261018/source-review-receipt.json', 'sha256': 'd1876ecace4daaedb5e93ff55769f936e53534da494636b8e8d3f44fd3c6109c', 'bytes': 11483, 'identity': {'device': 2304, 'inode': 82575448, 'bytes': 11483, 'mtime_ns': 1792350748173603776, 'ctime_ns': 1792350748173603776, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'companion_four': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/continuous-zero-dip-native-companion-four-guards-original01-root-execution-20261018/root-original-result-and-owned-release.json', 'sha256': '0d32089ec3d430a61d094ee2b19bb8f5b25105a07d9cc49ddf9bbfbea3691691', 'bytes': 22225, 'identity': {'device': 2304, 'inode': 82575507, 'bytes': 22225, 'mtime_ns': 1792350874516309960, 'ctime_ns': 1792350874516309960, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'native_profile': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/continuous-zero-dip-native-companion-original01-root-preparation-20261018/root-native-interpreter-effective-guard-code-stability.json', 'sha256': 'a98e716cde95706e9573744cc91f2e45a7ce5bc0f2724a7cff4af4d406b2fbac', 'bytes': 5056, 'identity': {'device': 2304, 'inode': 82575508, 'bytes': 5056, 'mtime_ns': 1792350954147509370, 'ctime_ns': 1792350954147509370, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'companion_four_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/continuous-zero-dip-native-companion-four-guards-independent-saved-review-20261018/review-receipt.json', 'sha256': '4e39303e870b304aebac7fe5009c5e7fc418152dde45e5449464c9bde7ce9037', 'bytes': 11797, 'identity': {'device': 2304, 'inode': 82575513, 'bytes': 11797, 'mtime_ns': 1792351148776959914, 'ctime_ns': 1792351148776959914, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
SELECTION = {'schema': 'robotron-effective-continuous-guard-selection-v1', 'canonical_base_socket': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py', 'sha256': 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed', 'bytes': 140517, 'identity': {'device': 2304, 'inode': 79696030, 'bytes': 140517, 'mtime_ns': 1792306967914113042, 'ctime_ns': 1792306967928089640, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'guard_manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/continuous_zero_dip_wave2_proposal/preparation-reviewed2-manifest.json', 'sha256': '947981d64af6c3cfce1d7191f1a02ce40f8ca79b5273aaee0dcc7a43b1760fd4', 'bytes': 43567, 'identity': {'device': 2304, 'inode': 82575417, 'bytes': 43567, 'mtime_ns': 1792349968255924515, 'ctime_ns': 1792349968255924515, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'installer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/continuous_zero_dip_wave2_proposal/effective_guard.py', 'sha256': 'b9f90525cfd6366d595fdc8cc82646064197d7caee07169ce58e1e24b2118eb4', 'bytes': 7359, 'identity': {'device': 2304, 'inode': 82575412, 'bytes': 7359, 'mtime_ns': 1792349863506522733, 'ctime_ns': 1792349968248763047, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'effective_helper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/continuous_zero_dip_wave2_proposal/effective_guard_body.py', 'sha256': 'f7a4d367162bafb87f4bc94ddad54573a76ab9159ae11e07540b2690c2c6eba4', 'bytes': 973, 'identity': {'device': 2304, 'inode': 82575413, 'bytes': 973, 'mtime_ns': 1792349863506339981, 'ctime_ns': 1792349968250763055, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'companion_evaluator': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/frozen_continuous_guard_evaluator_proposal/run_frozen_sidecar.py', 'sha256': 'c3a2ef29245b9d6a2e8309520f67d3b1f92061c38b395fa4ef8773631287dea3', 'bytes': 44210, 'identity': {'device': 2304, 'inode': 82575419, 'bytes': 44210, 'mtime_ns': 1792350254560546589, 'ctime_ns': 1792350512552904585, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'function': '_continuous_play_score_dip', 'installation': 'one module-global helper before SocketServer construction; original module globals/RL_CONFIG', 'canonical_source_hashes_are_base_provenance': True, 'stable_source_fingerprint': '0f8b8e491aa09bd6bd926dea14afc31affa6595e511362facccc1d88694f2b80'}
EXPERIMENT = 'CE4096-continuous-zero-dip-guard-LR25-continuation-trial01-20261018'
INVALID_PLAN_SHA = 'b61ef2cbdd1779e6491d1a181f60260e8474aa633a1a3da9c9a117c3744c7324'
INVALID_BINDING_SHA = 'fde2f3b3a23f407f6473bb75594d326229da22cef15290ef2186c74e2680c232'
NATIVE_UNIT = 'robotron-quality-same-LR25-vs-CE845-original01-20261018.service'
LOCAL_KEYS = {'module', 'function', 'code', 'globals', 'RL_CONFIG'}


def require(value, message):
    if not value:
        raise ValueError(message)


def source_pin(pin):
    """Only the five fixed physical source/declaration files; never a tensor."""
    allowed = {SELECTION[k]['path'] for k in ('canonical_base_socket', 'guard_manifest',
        'installer', 'effective_helper', 'companion_evaluator')}
    require(type(pin) is dict and pin.get('path') in allowed, 'Exact guard source path required')
    path = Path(pin['path'])
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno()); raw = stream.read((512 << 10)+1)
        after = os.fstat(stream.fileno())
    def identity(info):
        return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
            mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
            mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
        and before.st_nlink == 1 and len(raw) == before.st_size <= 512 << 10
        and identity(before) == identity(after) == identity(path.lstat()) == pin['identity']
        and hashlib.sha256(raw).hexdigest() == pin['sha256'] and len(raw) == pin['bytes'],
        'Physical base/guard/companion source identity differs')
    return pin


def check_selection(value, reader, *, source_reader=source_pin):
    require(value == SELECTION, 'Exact effective guard source declaration required')
    unsigned = {key: item for key, item in value.items() if key != 'stable_source_fingerprint'}
    require(hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode()).hexdigest() == value['stable_source_fingerprint'],
        'Effective source fingerprint differs')
    for key in ('canonical_base_socket', 'guard_manifest', 'installer', 'effective_helper', 'companion_evaluator'):
        require(source_reader(value[key]) == value[key], 'Effective source PIN differs')
    profile = reader(CLOSED['native_profile'])
    require(profile['schema'] == 'robotron-root-native-interpreter-effective-guard-metadata-stability-check-v1'
        and profile['status'] == 'PASS_NATIVE_COMPANION_INSTALLER_AND_CODE_FINGERPRINT_STABLE'
        and profile['selection'] == value and profile['optimize'] == 0 and profile['gil_enabled'] is False
        and profile['DQN_Torch_NumPy_imported'] is False
        and profile['companion_source_sha256'] == value['companion_evaluator']['sha256']
        and profile['runtime_code_sha256'] == 'c11562ba189bdadc1ce3f70f0e3ecdaa92d4f2201dbb239e3a129f95564d1ef4'
        and all(row['runtime_code_sha256'] == profile['runtime_code_sha256']
            and row['identities_unchanged'] is True for row in profile['checks']),
        'Actual native interpreter profile must remain explicit metadata evidence')
    return profile


def check_runtime(effective, selection, reader, *, source_reader=source_pin):
    profile = check_selection(selection, reader, source_reader=source_reader)
    require(type(effective) is dict and effective['selection'] == selection
        and effective['verified_before_serving'] is True and effective['verified_after_cleanup'] is True
        and effective['verification_error'] is None and type(effective['verification_count']) is int
        and effective['verification_count'] >= 2
        and effective['runtime_code_sha256'] == profile['runtime_code_sha256']
        and effective['python_version'] == profile['python_version']
        and effective['python_cache_tag'] == profile['python_cache_tag'],
        'Effective guard native profile/verification is missing or mismatched')
    before, after = effective['local_identity_before'], effective['local_identity_after']
    require(type(before) is dict and set(before) == LOCAL_KEYS and before == after
        and all(type(value) is int and value > 0 for value in before.values()),
        'Exact positive local module/function/code/globals/config IDs must remain unchanged')
    # Deliberately exclude process-local IDs/check counts from cross-leg equality.
    return {key: effective[key] for key in ('selection', 'runtime_code_sha256', 'python_version', 'python_cache_tag')}


def check_invalid_release(value, peer, owner):
    require(value['schema'] == 'robotron-root-original-invalid914M-disposition-and-source-freeze-release-v1'
        and value['status'] == 'ORIGINAL_INVALID_TERMINAL_DESCRIPTOR_RETAINED_SOURCE_FREEZE_RELEASED'
        and value['source_freeze_released'] is True and value['descriptor_retained'] is True
        and value['original_unit_released'] is False and value['original_timer_already_garbage_collected'] is True
        and value['original']['unit'] == NATIVE_UNIT and value['original']['pid'] == 67638
        and value['original']['starttime_ticks'] == 43813785
        and value['original']['invocation_id'] == 'a85440fb223f498d86dace1e32496911'
        and value['original']['exec_code'] == 1 and value['original']['exit'] == 1
        and value['original']['result'] == 'exit-code' and value['main_pid'] == 0
        and value['raw_six_archive_statuses'] == [0, 0, 0, 0, 1, 0]
        and value['service_stop_attempts'] == 1 and value['additional_stop_or_reset'] is False,
        'Only the exact failed914M terminal disposition is authority; no healthy closure alias')
    scientific = value['scientific_disposition']
    require(scientific['outcome'] == 'incomplete' and scientific['R1_valid'] is False
        and scientific['R1_completed_games'] == 44 and scientific['R1_admitted_games'] == 56
        and scientific['R1_pending_games_at_abort'] == 11 and scientific['R1_abandoned_games'] == 1
        and scientific['candidate_cohorts_run'] == 0 and scientific['candidate_quality_assessed'] is False
        and scientific['protected_reference_changed'] is False and scientific['original_native_exit'] == 1
        and scientific['original_invalid_receipts_rewritten'] is False
        and scientific['partial_reference_pool_usable'] is False and scientific['retry_or_rescue'] is False,
        'Original invalid914M science must remain unusable and unassessed')
    require(peer['schema'] == 'robotron-independent-saved-invalid914M-forensic-disposition-review-v1'
        and peer['status'] == 'PASS_CLOSED_INVALID_NATIVE1_FORENSIC_DISPOSITION_DESCRIPTOR_RETAINED'
        and peer['evidence']['root_invalid_disposition_and_limited_freeze_release'] == CLOSED['invalid_release'],
        'Independent closed invalid-disposition peer join differs')
    require(value['production_source_changed'] is False and value['control_changed'] is False
        and value['model_structure_changed'] is False and value['main_health']['client_count'] == 192
        and value['main_health']['training_enabled'] is True and value['main_health']['lr'] == 1.25e-5
        and value['held_file_hashes_unchanged_before_release']['counts'] ==
            dict(source_hashes=62, control_hashes=2, unit_files=3),
        'Invalid campaign release must preserve the held main192/.25 inventory')
    require(set(value['optimizer_replay_identities']) == {'optimizer', 'replay'},
            'Both preserved exposure identities required')
    for row in value['optimizer_replay_identities'].values():
        require(set(row) == {'process_id', 'instance_monotonic_ns', 'epoch'}
            and row['process_id'] == owner['pid'] and all(type(v) is int and v > 0 for v in row.values()),
            'Same main optimizer/replay identities required')
    return value



def check_retained_terminal(value):
    """Readonly failed914M tombstone exception; never a release or live-owner alias."""
    if value.get('LoadState') == 'not-found':
        return value
    expected=dict(LoadState='loaded',Id=NATIVE_UNIT,MainPID='0',ExecMainPID='67638',
        InvocationID='a85440fb223f498d86dace1e32496911',NRestarts='0',ExecMainCode='1',
        ExecMainStatus='1',Result='exit-code',ActiveState='failed',SubState='failed',
        ControlGroup='',TriggeredBy='')
    require(all(value.get(key)==item for key,item in expected.items()),
            'Only exact idle original invalid914M descriptor is allowed')
    return value


def prerequisites(reader, owner):
    invalid = reader(CLOSED['invalid_release']); peer = reader(CLOSED['invalid_peer'])
    check_invalid_release(invalid, peer, owner)
    six, six_peer = reader(CLOSED['guard_six']), reader(CLOSED['guard_six_peer'])
    require(six['status'] == 'PASS_ORIGINAL_NATIVE0_SIX_CPU_REGRESSIONS_AND_OWNED_RELEASE'
        and six['test_count'] == 6 and six['skips'] == 0 and six['executions'] == 1
        and six['packet'] == SELECTION['guard_manifest']
        and six['production_source_changed'] is False and six['main_restarted'] is False
        and six['original914M_quality_retry'] is False
        and six_peer['status'] == 'PASS_CLOSED_SIX_ENGINEERING_GUARDS_NATIVE0_DIRECT_UNIT_OWNED_RELEASE'
        and six_peer['source_packet'] == SELECTION['guard_manifest']
        and six_peer['result'] == six['actual_original_result'],
        'Actual original six CPU guards and independent closed peer required')
    companion_peer = reader(CLOSED['companion_source_peer'])
    require(companion_peer['status'] == 'SOURCE_ONLY_PASS_UNSELECTED_UNEXECUTED'
        and companion_peer['preparation_manifest'] == CLOSED['companion_manifest'],
        'Exact independent companion SOURCE peer required, never a runtime claim')
    four = reader(CLOSED['companion_four'])
    require(four['schema'] == 'robotron-root-audit-original-result-and-GC-aware-owned-release-v1'
        and four['status'] == 'ORIGINAL_AUDIT_EXIT0_ARCHIVED_AND_RELEASED'
        and four['original_exec_code'] == 1 and four['original_exit'] == 0 and four['original_result'] == 'success'
        and four['all_six_original_archive_commands_succeeded'] is True
        and four['original_archived_before_release'] is True and four['unit_released'] is True
        and four['lifecycle_complete'] is True and four['payload_retried'] is False and four['error'] is None,
        'Actual closed companion metadata guards must preserve native0/full owned closure')
    four_peer=reader(CLOSED['companion_four_peer'])
    require(four_peer['status']=='PASS_CLOSED_ORIGINAL_FOUR_METADATA_GUARDS_AND_OWNED_RELEASE'
        and four_peer['evidence']['original_release']==CLOSED['companion_four']
        and four_peer['evidence']['native_scalar_integration']==CLOSED['native_profile']
        and four_peer['evidence']['preparation_manifest']==CLOSED['companion_manifest'],
        'Closed companion four-guard/native-profile peer join differs')
    check_selection(SELECTION, reader)
    return dict(release=invalid, release_pin=CLOSED['invalid_release'], peer=CLOSED['invalid_peer'],
        guard_selection=SELECTION, guard_six=CLOSED['guard_six'], guard_six_peer=CLOSED['guard_six_peer'],
        companion_source_peer=CLOSED['companion_source_peer'], companion_four=CLOSED['companion_four'],
        companion_four_peer=CLOSED['companion_four_peer'],
        native_profile=CLOSED['native_profile'])
