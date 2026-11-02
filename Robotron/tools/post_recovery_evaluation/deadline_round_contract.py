"""Explicit background-health change; private deadline32 predicates stay fixed."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'logs/managed-learning-20261015/run-26'
LEGACY_NATIVE = BASE / 'deadline-score60min-protocol-original01-preparation-20261026/run_deadline32_leg_v1.py'
LEGACY_NATIVE_SHA = '85b2efdd43c8c1c7a0f48610908bec1ded2b936d066080328b6862fc394ae556'
LEGACY_REVIEW = LEGACY_NATIVE.with_name('review_deadline32_leg_v1.py')
LEGACY_REVIEW_SHA = 'f2b311fd6d375e6b1e35c571b91cfb8c209881855834941d5b0292b51a9bbf5e'
LEGACY_JOB = BASE / 'deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03/C2/job.json'
LEGACY_JOB_SHA = 'b6f9d229836f6cbe2897e2fa3ef6426209998ac9b361c47d1a48a95200cd1fc5'
HEALTH_SHAS = dict(
    client='b2bdb5b3bfe5545af5521d02c7558787e03dddfaa55ee89a165dee953c57eec9',
    worker='467e74e01558bde3365278ab8024754e17f7f35d525776e79e5898e943972ccf', health='d7b314c9cbc0ee61fd2b170e726c22fa9af2d4801f1c93b190056b676a599014')
PRIVATE_FIELDS = ('source_package', 'actor_source_sha256', 'loaded_rom_sha256',
    'prior_ROM_identity_proof', 'lua', 'mame', 'rompath', 'boot_seed', 'seed_runtime',
    'lease', 'main_sources', 'actor_slots', 'origin_port', 'proxy_ports', 'device',
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
    require(protocol['schema'] == 'robotron-native-round-main-health-protocol-v3'
            and protocol['case'] == job['main_binding'] and protocol['raw_API_required'] is True
            and protocol['close_requires_final_sample'] is True and protocol['hot_max_gap_s'] == .5
            and protocol['initial_samples'] == 100, 'Exact hot round-health protocol required')
    require(family['schema'] == 'robotron-deadline32-round-main-source-family-v1'
            and family['runtime'] == job['runtime'] and family['deadline_components'] == job['components']
            and family['main_observer'] == job['observer_sources']
            and family['current_main_binding'] == job['main_binding'], 'Native/family source binding differs')
    require(set(family['main_observer']) == {'client', 'worker', 'health', 'interpreter'}, 'Exact round observer family required')
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
    require(family['round_observer_reviewer']['sha256'] == '684b03cc840d1ff468d950ee80b27ecf88f12dab03a671d53c735ce4bfc80f8a', 'Exact independent round observer reviewer required')
    h.checked(family['round_observer_reviewer'])
    return validate_derivation(job['runtime']['path'], family['reviewer']['path'])


def validate_binding(job, protocol, family, read, h):
    binding = read(job['main_binding'])
    require(binding['schema'] == 'robotron-round-main-health-case-v1'
            and len(binding['inputs']) == 243 and binding['experiment'] == job['training_experiment'],
            'Exact243-input recovered main recipe context required')
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
    family = context['family']
    require(family['native_launch_qualified'] is True, 'Engineering family is never scientific launch authority')
    proof = json.loads(h.checked(family['full_fleet_hot_review']).read_bytes())
    reviewer = load('_deadline_full_fleet_readiness_reviewer', h.checked(family['round_observer_reviewer']))
    verified = reviewer.verify(proof['lifecycle'], h)
    require(verified['original_sources'] == family['main_observer'], 'Full-fleet proof uses a different observer source')
    lifecycle = json.loads(h.checked(proof['lifecycle']).read_bytes())
    outcome = json.loads(h.checked(lifecycle['outcome']).read_bytes())
    active = [json.loads(h.checked(value).read_bytes())['snapshot']['status']['active']
              for value in outcome['samples']]
    require(max(active) == 192, 'Actual192-client hot-interface proof required before scientific ownership')
    return verified
