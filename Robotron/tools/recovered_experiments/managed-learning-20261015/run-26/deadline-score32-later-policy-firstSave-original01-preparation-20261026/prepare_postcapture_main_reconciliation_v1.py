"""New read-only main binding/census/monitor; only owned save receipt changed."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/evaluator-count-active600-counterbalanced-engineering-original04/postfailure-supervised-slot2-main-reconciliation-original01'
NEW = HERE / 'postcapture-current-main-reconciliation-original01'
SLOT = '/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/managed_save.request.json.completed'
SUPERVISION = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/supervised_main_fleet_v2.py')


def pin(path):
    path = path.resolve(); assert path.suffix != '.pt', 'No model-body reads'
    s = path.stat(); raw = path.read_bytes(); after = path.stat()
    assert (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
        identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                      ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def read(value):
    assert pin(Path(value['path'])) == value
    return json.loads(Path(value['path']).read_text())


def put(path, value):
    with path.open('x' if not isinstance(value, bytes) else 'xb') as stream:
        if isinstance(value, bytes): stream.write(value)
        else: json.dump(value, stream, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    return pin(path)


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            assert not os.fsdecode(args[0]).endswith('.pt'), 'Forbidden model-body open'
        if event == 'import': assert args[0].split('.')[0] not in ('torch', 'numpy', 'dqn')
    sys.addaudithook(audit)
    old_pin = pin(OLD / 'current-main-binding.json')
    assert old_pin['sha256'] == 'd22c93b618b45d98fdf256f5f1cd29a117dacd841b540c10a5a0adcc81818804'
    old = read(old_pin); policy = read(old['supervision_policy'])
    # Preserve the pre-existing historical policy digest honestly. The active
    # dedicated main-health path checks the physical policy and all197 holds
    # separately; this NEW future policy will explicitly name the NEW map.
    assert policy['held_hashes_sha256'] == '2f7a57f987057ddfd2c4b4b8766e1075fded53d6748d4b69ff80c28c94a136e1'
    assert checksum(old['held_hashes']) == 'f056f3ed7c19230f3fc434e0329e322d8d3d367015fc0ec8e3ea5136c6bcc100'
    producer = {}
    expected = {
        'capture': ('output-original01/result.json', 'aaf2cd9ede7a20fd793162bfb4372b1cdb542576abe19f6ef01a74cad06002aa'),
        'capture_lifecycle': ('execution-original01/root-original-result-and-owned-release.json', '8e0f007f9cfe46d11ef5071040ae7a292b70c4c65f1a246b8f200f55f4c2581d'),
        'root_capture_scope': ('root-capture-owned-scope-closeout.json', 'e971ed545fb257374c32a1d17223e8bab6ff4b24df3291b19109ed8fa0672ade'),
        'numerical': ('candidate-CPU-verification-original02/cpu-verification.json', 'a0d9efad485ff5718f2f2d15a31cae8a043e1382e722c9970d7961f72b802772'),
        'independent_numerical': ('independent-original02-numerical-SMALL-review.json', '7fbc44fbc67aa4abfdbb39669d2b0db1bed2c025403c35ec9364566a44d5d11e'),
        'root_numerical_adoption': ('root-candidate-numerical-adoption.json', '14ad8057cfc5e55a3582f82cfee66099b181991a2aa60981e4ea2a0cce9a5827')}
    for key, (name, digest) in expected.items():
        producer[key] = pin(HERE / name); assert producer[key]['sha256'] == digest
    capture = read(producer['capture']); closure = read(producer['capture_lifecycle'])
    assert capture['owner'] == old['owner'] == policy['trainer']
    assert capture['tag'] == 'deadlineScore32_LR125_nextSave_original01_20261026'
    assert capture['original_attempt'] == 1 and capture['no_retry'] is True
    assert closure['original_exit'] == 0 and closure['unit_released'] is closure['lifecycle_complete'] is closure['audit_success'] is True
    transition = capture['completed_slot_transition']
    assert transition['before']['actual_pin']['path'] == transition['after']['actual_pin']['path'] == SLOT
    assert transition['before']['actual_pin']['sha256'] == old['held_hashes'][SLOT]
    before = read(transition['before']['archive'])
    assert before != {'tag': capture['tag']}
    for key in ('request', 'after'):
        assert read(transition[key]['archive']) == {'tag': capture['tag']}
        assert transition[key]['archive']['sha256'] == transition[key]['actual_pin']['sha256'] == 'fef32d508895b88495158b8d887666f94727eeeee64197a39bb19bf680a9a6d1'
    assert pin(Path(SLOT)) == transition['after']['actual_pin']
    assert not Path(SLOT.removesuffix('.completed')).exists()
    for key in ('device', 'inode', 'bytes', 'mtime_ns'):
        assert transition['request']['actual_pin']['identity'][key] == transition['after']['actual_pin']['identity'][key]
    assert transition['before_unix_s'] <= transition['request_unix_s'] <= transition['after_unix_s']
    numerical = read(producer['numerical']); independent = read(producer['independent_numerical'])
    assert numerical['status'] == independent['status'] == 'PASS'
    assert numerical['sha256'] == independent['source']['sha256'] == capture['checkpoint']['sha256']
    # Authenticate only small source and metadata, never MAME executable/model.
    sup_pin = pin(SUPERVISION)
    assert sup_pin['sha256'] == '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
    spec = importlib.util.spec_from_file_location('_reconciliation_real_supervision', SUPERVISION)
    sup = importlib.util.module_from_spec(spec); spec.loader.exec_module(sup)
    snapshot = sup.collect(policy)
    sup.validate_snapshot(policy, snapshot, 192)
    assert set(snapshot['actors']) == set(map(str, range(192)))
    for actor in old['actors']:
        actual = snapshot['actors'][str(actor['slot'])]
        assert (actual['pid'], actual['starttime_ticks'], actual['affinity']) == (actor['pid'], actor['starttime_ticks'], actor['mask'])
        assert actual == policy['baseline_actors'][str(actor['slot'])]
    assert old['verified_between_study_replacement_count'] == 3 and old['historical_original_actor_survivors'] == 189
    old_actors_transition = read(old['verified_between_study_actor_transition'])
    held = {path: pin(Path(path))['sha256'] for path in old['held_hashes']}
    assert len(held) == 197 and [path for path in held if held[path] != old['held_hashes'][path]] == [SLOT]
    NEW.mkdir(mode=0o700)
    snapshot_pin = put(NEW / 'actual-original-owner-and192-unchanged-census.json', snapshot)
    new_policy = deepcopy(policy); new_policy['held_hashes_sha256'] = checksum(held)
    assert {key for key in policy if policy[key] != new_policy[key]} == {'held_hashes_sha256'}
    sup.validate_policy(new_policy); sup.validate_snapshot(new_policy, snapshot, 192)
    policy_pin = put(NEW / 'current-main-supervision-policy.json', new_policy)
    receipt_proof = put(NEW / 'closed-owned-save-receipt-transition.json', dict(
        schema='robotron-closed-owned-main-save-receipt-transition-v1', old_binding=old_pin,
        old_supervision_policy=old['supervision_policy'], new_supervision_policy=policy_pin,
        actual_producer_proofs=producer, exact_completed_slot_transition=transition,
        changed_held_paths=[SLOT], all_other_held_inputs_unchanged=196,
        unchanged_owner=old['owner'], unchanged_actor_census=snapshot_pin,
        unchanged_between_study_replacements=3, unchanged_historical_original_survivors=189,
        old_actor_transition_evidence=old['verified_between_study_actor_transition'],
        old_policy_limits_and_actor_owner_values_unchanged=True,
        historical_prior_policy_held_hashes_checksum=policy['held_hashes_sha256'],
        historical_prior_binding_held_hashes_checksum=checksum(old['held_hashes']),
        historical_policy_fingerprint_not_claimed_to_match_later197_binding=True,
        prospective_new197_map_checksum=new_policy['held_hashes_sha256'],
        old_policy_and_bindings_or_historical_studies_rewritten=False,
        new_native_or_model_or_production_or_canonical_state_actions=False))
    binding = deepcopy(old); binding['held_hashes'] = held; binding['supervision_policy'] = policy_pin
    binding['postcapture_receipt_prior_binding'] = old_pin
    binding['postcapture_owned_save_receipt_transition'] = receipt_proof
    binding['postcapture_current_binding_reason'] = 'One closed owned managed-save completed-slot receipt transition; all196 other holds and the original trainer/fleet/current192 actor identities and roles unchanged. Future binding only.'
    allowed = {'held_hashes', 'supervision_policy', 'postcapture_receipt_prior_binding',
               'postcapture_owned_save_receipt_transition', 'postcapture_current_binding_reason'}
    assert {key for key in set(old) | set(binding) if old.get(key) != binding.get(key)} == allowed
    binding_pin = put(NEW / 'current-main-binding.json', binding)
    old_monitor_pin = pin(OLD / 'current-main-readonly-monitor.py')
    assert old_monitor_pin['sha256'] == 'cb91f00a95bc39dba8ad55a068100bbe7f3547beeeadfc70591cb5161f367022'
    original = Path(old_monitor_pin['path']).read_text()
    assert original.count(repr(old_pin)) == 1
    modified = original.replace(repr(old_pin), repr(binding_pin))
    assert modified.replace(repr(binding_pin), repr(old_pin)) == original
    monitor_pin = put(NEW / 'current-main-readonly-monitor.py', modified.encode())
    started = time.time()
    command = [sys.executable, '-I', '-B', monitor_pin['path']]
    observed = subprocess.run(command, capture_output=True, timeout=30)
    stdout_pin = put(NEW / 'actual-new-monitor-stdout.json', observed.stdout)
    stderr_pin = put(NEW / 'actual-new-monitor-stderr.txt', observed.stderr)
    assert observed.returncode == 0 and observed.stderr == b''
    status = json.loads(observed.stdout)
    assert status['owner'] == old['owner'] and status['client_count'] == 192 and status['held_inputs'] == 197
    assert status['verified_between_study_replacements'] == 3 and status['historical_original_actor_survivors'] == 189
    assert status['bound192_actor_identities_and_affinities_verified'] is True and status['training_enabled'] is True
    assert status['measurement_active'] is False and status['production_changed_by_this_monitor'] is False
    assert pin(Path(SLOT)) == transition['after']['actual_pin'] and pin(Path(old_pin['path'])) == old_pin
    proof = dict(schema='robotron-postcapture-reconciled-main197-monitor-preparation-v1',
        created_unix_s=time.time(), current_binding=binding_pin, current_monitor=monitor_pin,
        current_supervision_policy=policy_pin, receipt_transition=receipt_proof,
        original_192_census=snapshot_pin, exact_producer_proofs=producer,
        old_binding_preserved=old_pin, old_monitor_preserved=old_monitor_pin,
        actual_new_monitor=dict(argv=command, started_unix_s=started, exit=observed.returncode,
            stdout=stdout_pin, stderr=stderr_pin, status=status),
        all_other196_holds_unchanged=True, same_original_owner_and_all192_commands_envs_affinities_cgroups_verified=True,
        same_three_between_study_replacements=True, policy_delta_only_held_hash_checksum=True,
        monitor_delta_only_binding_pin=True, canonical_state_changed=False,
        old_failed_monitor_and_all_prior_history_preserved=True, production_or_model_changed=False,
        root_adoption_required_before_canonical_registration=True, preparation_source=pin(Path(__file__)))
    print(json.dumps(put(NEW / 'postcapture-main-reconciliation-NOT-CANONICALLY-ADOPTED.json', proof)), flush=True)


if __name__ == '__main__':
    main()
