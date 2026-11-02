"""Explicit background-health change; private deadline32 predicates stay fixed."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = ROOT / 'logs/managed-learning-20261015/run-26'
LEGACY_NATIVE = BASE / 'deadline-score60min-protocol-original01-preparation-20261026/run_deadline32_leg_v1.py'
LEGACY_NATIVE_SHA = '85b2efdd43c8c1c7a0f48610908bec1ded2b936d066080328b6862fc394ae556'
LEGACY_REVIEW = LEGACY_NATIVE.with_name('review_deadline32_leg_v1.py')
LEGACY_REVIEW_SHA = 'f2b311fd6d375e6b1e35c571b91cfb8c209881855834941d5b0292b51a9bbf5e'
LEGACY_JOB = BASE / 'deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03/C2/job.json'
LEGACY_JOB_SHA = 'b6f9d229836f6cbe2897e2fa3ef6426209998ac9b361c47d1a48a95200cd1fc5'
HEALTH_SHAS = {'registry': '2f3eddaf75ee3b9a875d0a621a63eeea7274eae3afa75bcceb309002233316d1', 'health_base': '6fcff86103d409a3646f523a6adf6a95cc9eabd3b0090826493aaa99a7b9fbcc', 'health': '73462699277d0382cdb981167284add7b95b6cf31f2073a708cb77e52f479372', 'worker': 'c1dad49f4ae56cf89d8083601485d737f5d96111df3834cbf10a5b833ef0273b', 'client': '629c288b062b6abd3af27b87c01d94c8ac1f988df899968d902943b689659fa9', 'durability': '5dbeb347474dd9289ae18a2de0c438820f535fa9d75badaa3cfbf82dff6c1aa5', 'control': 'a2ce55471f7ff14490553cf05871e79a0ff15c925d01441065821b0f95daade8'}
PRIVATE_FIELDS = ('source_package', 'actor_source_sha256', 'loaded_rom_sha256',
    'prior_ROM_identity_proof', 'lua', 'mame', 'rompath', 'boot_seed', 'seed_runtime',
    'main_sources', 'actor_slots', 'origin_port', 'proxy_ports', 'device',
    'backend', 'cpu_threads', 'inference_max_batch_size', 'gpu_uuid', 'horizon_ns',
    'startup_limit_s', 'wall_limit_s', 'cleanup_limit_s', 'inflight_drain_bound_ns',
    'startup_trace_frames', 'startup_admission_duration_ns', 'resources',
    'observer_resources', 'controller_observation_s', 'components')


def require(value, message):
    if not value:
        raise ValueError(message)


def source(path, digest):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Historical source changed')
    return path.read_bytes()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def functions(raw):
    return {node.name: node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef)}


def validate_derivation(native_path, review_path):
    original = functions(source(LEGACY_NATIVE, LEGACY_NATIVE_SHA))
    current = functions(Path(native_path).read_bytes())
    changed = {'validate_main_health_contract', 'validate_completed_context'}
    require(set(current) == set(original) | {'round_contract'}, 'Native function inventory changed')
    for name in set(original)-changed:
        if name == 'run':
            gate = ast.parse('round_contract().validate_launch(job, context, h)').body[0]
            positions = [index for index, node in enumerate(current[name].body)
                         if ast.dump(node) == ast.dump(gate)]
            original_position = next(index for index, node in enumerate(original[name].body)
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == 'owned')
            require(positions == [original_position], 'Exactly one extra launch gate must precede private ownership')
            current[name].body.pop(positions[0])
        require(ast.dump(original[name]) == ast.dump(current[name]), 'Private native predicate changed: ' + name)
    old_review = functions(source(LEGACY_REVIEW, LEGACY_REVIEW_SHA))
    new_review = functions(Path(review_path).read_bytes())
    retired = {'validate_observer4260_derivation', 'validate_protocol_provenance'}
    require(set(new_review) == set(old_review)-retired | {'round_contract'}, 'Reviewer function inventory changed')
    for name in set(old_review)-retired-{'review_health'}:
        require(ast.dump(old_review[name]) == ast.dump(new_review[name]), 'Private independent reviewer predicate changed: ' + name)
    return dict(private_native_functions_unchanged=sorted(set(original)-changed),
                private_review_functions_unchanged=sorted(set(old_review)-retired-{'review_health'}),
                background_health_contract_only=True, extra_preownership_launch_gate=True)


def validate_static(job, protocol, family, h):
    require(protocol['schema'] == 'robotron-native-continuous-static192-main-health-proof2s-protocol-v1'
            and protocol['case'] == job['main_binding'] and protocol['raw_API_required'] is True
            and protocol['close_requires_final_sample'] is True and protocol['hot_max_gap_s'] == 2.0
            and protocol['initial_samples'] == 100
            and protocol['raw_queue_protocol'] == 'pending-byte-digest-v2'
            and protocol['volatile_live_tmpfs'] is True
            and protocol['source_bound_retired_API_projection'] is True
            and protocol['source_bound_completed_original192_bootstrap'] is True
            and protocol['source_bound_static_original192_partition'] is True, 'Exact hot round-health protocol required')
    require(family['schema'] == 'robotron-deadline32-static192-proof2s-source-family-v1'
            and family['runtime'] == job['runtime'] and family['deadline_components'] == job['components']
            and family['main_observer'] == job['observer_sources']
            and family['current_main_binding'] == job['main_binding'], 'Native/family source binding differs')
    require(set(family['main_observer']) == {'client', 'worker', 'health', 'health_base', 'registry', 'interpreter', 'durability', 'control'}, 'Exact round observer family required')
    for key, digest in HEALTH_SHAS.items():
        require(family['main_observer'][key]['sha256'] == digest, 'Selected round observer source differs: ' + key)
    for value in family['main_observer'].values():
        h.checked(value)
    require(family['main_health_finalizer']['sha256'] == '64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee',
            'Original native watcher shutdown/finalizer required')
    h.checked(family['main_health_finalizer'])
    source(LEGACY_JOB, LEGACY_JOB_SHA)
    require(family['private_parent_job']['path'] == str(LEGACY_JOB)
            and family['private_parent_job']['sha256'] == LEGACY_JOB_SHA, 'Actual completed private source parent required')
    legacy = json.loads(h.checked(family['private_parent_job']).read_bytes())
    require(all(job[key] == legacy[key] for key in PRIVATE_FIELDS), 'Private ROM/policy backend/clock/resource/metric source context changed')
    recovery = json.loads(h.checked(family['lease_recovery_authority']).read_bytes())
    require(recovery['schema'] == 'robotron-post-outage-private-coordinator-restoration-v1'
            and recovery['status'] == 'RESTORED_NEW_BOOT_COORDINATOR'
            and recovery['absent_pre_outage_lease'] == legacy['lease']
            and recovery['restored_lease'] == job['lease']
            and recovery['created_exclusively_without_replacing_existing_file'] is True
            and recovery['exclusive_lock_acquisition_and_release_verified'] is True,
            'Exact restored permanent coordinator authority required')
    require(job['lease']['path'] == legacy['lease']['path'] and job['lease']['bytes'] == 0
            and job['lease']['identity']['mode'] == '0o600', 'Permanent coordinator path/bytes/mode changed')
    require(recovery['current_boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'Restored coordinator belongs to a different boot')
    h.checked(job['lease'])
    require(family['round_observer_reviewer']['sha256'] == 'f6dcd7b9ae7556bc1e669b3973a6c5797f845d89c23e2d62a4955b55b519590a', 'Exact independent round observer reviewer required')
    h.checked(family['round_observer_reviewer'])
    return validate_derivation(job['runtime']['path'], family['reviewer']['path'])


def validate_binding(job, protocol, family, read, h):
    binding = read(job['main_binding'])
    static_profile().validate_inventory(binding, h)
    require(binding['experiment'] == job['training_experiment'], 'Actual static-main recipe experiment differs')
    baseline = read(binding['baseline_snapshot'])
    health = load('_deadline_round_context_health', h.checked(family['main_observer']['health']))
    health.check_inputs(binding, full=True)
    health.validate(binding, baseline)
    wire = baseline['raw_API_wire'].encode('utf-8')
    require(hashlib.sha256(wire).hexdigest() == baseline['api_wire_sha256']
            and json.loads(wire) == baseline['api']
            and baseline['api']['managed_experiment'] == job['training_experiment'],
            'Raw baseline API/recipe context differs')
    return binding, baseline['api']


def validate_launch(job, context, h):
    require(os.environ.get('ROBOTRON_CONTINUOUS_TRAINING_MODE', '0') == '0'
            and os.environ.get('ROBOTRON_ROLLING_TRAINING_CLEANUP', '0') == '0'
            and os.environ.get('ROBOTRON_CONTINUOUS_STARTUP_HOLD', '0') == '0',
            'Private frozen sidecar must remain source-mode0 before ownership')
    family = context['family']
    require(family['native_launch_qualified'] is True, 'Engineering family is never scientific launch authority')
    proof = json.loads(h.checked(family['main_domain_hot_review']).read_bytes())
    reviewer = load('_deadline_main_domain_readiness_reviewer', h.checked(family['round_observer_reviewer']))
    verified = reviewer.verify(proof['lifecycle'], h)
    require(verified['proof_gap_contract'] == 'robotron-main-proof-gap-2s-v1'
            and verified['verified_maximum_gap_s'] == 2.0
            and verified['accepted_evidence_and_projection_gaps_verified'] is True
            and verified['main_health_profile'] == 'STATIC_ORIGINAL192_NO_FAULT_ADOPTION'
            and verified['source_bound_completed_original192_bootstrap_verified'] is True
            and verified['TRAIN155_originals_and_EVAL37_once_partition_verified'] is True,
            'Exact prospective2s engineering proof contract required')
    require(verified['original_sources'] == family['main_observer'], 'Main-domain proof uses a different observer source')
    lifecycle = json.loads(h.checked(proof['lifecycle']).read_bytes())
    worker = json.loads(h.checked(lifecycle['worker_job']).read_bytes())
    proved = json.loads(h.checked(worker['case']).read_bytes())
    current = context['main_binding']
    static_profile().same_domain(proved, current)
    static_profile().validate_inventory(current, h)
    require(proved['inputs'] == current['inputs'] and proved['slot_eval'] == current['slot_eval'],
            'Readiness proof belongs to a different complete source/role domain')
    static = ('pid', 'starttime_ticks', 'parent_pid', 'cgroup', 'command', 'environment', 'affinity', 'uids', 'executable')
    for role in ('trainer', 'fleet'):
        old, actual = proved['owners'][role], current['owners'][role]
        require(old['unit'] == actual['unit'] and old['invocation'] == actual['invocation']
                and all(old['process'][key] == actual['process'][key] for key in static),
                'Readiness proof belongs to a different original main owner')
    for kind in ('optimizer', 'replay'):
        require(all(proved['exposure'][kind][key] == current['exposure'][kind][key]
                    for key in ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')),
                'Readiness exposure lineage changed')
    outcome = json.loads(h.checked(lifecycle['outcome']).read_bytes())
    expected_slots = set(map(str, range(192)))
    for value in outcome['samples']:
        sample = json.loads(h.checked(value).read_bytes())['snapshot']
        static_profile().sample_domain(current, sample)
    return verified


def static_profile():
    path = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/static_profile_contract_v2.py')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == '5260662e651c6f26cde42bb04cde913dd51015658d071499b6966e661e6a451b',
            'Exact selected static input-inventory/domain verifier required')
    return load('_deadline_static_original192_profile', path)
