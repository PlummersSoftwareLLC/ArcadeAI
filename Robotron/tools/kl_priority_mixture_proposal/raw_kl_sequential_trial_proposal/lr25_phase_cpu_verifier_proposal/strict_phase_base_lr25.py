#!/usr/bin/env python3
"""CPU checkpoint verification for one root-bound maintenance job; default is literal PLAN."""
import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import resource
import stat
import sys
import traceback

SCHEMA = 'robotron-live8-maintenance-checkpoint-CPU-job-v1'
RESULT_SCHEMA = 'robotron-live8-maintenance-checkpoint-CPU-result-v1'
ABSENCE_SCHEMA = 'robotron-live8-owned-trainer-absence-v1'
LINEAGE_SCHEMA = 'robotron-live8-owned-restart-lineage-v1'
START_SCHEMA = 'robotron-live8-owned-trainer-start-request-v1'
MAX_JOB = 1 << 20
MAX_METADATA = 4 << 20
MAX_BOUND_FILES = 64
MODEL_NAMES = ('model.py', 'config.py', 'learning_control.py', '__init__.py')
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
EXPECTED = dict(engine_version=28, state_size=11128, single_frame_state_size=2782, frame_stack=4)
HELD_RECIPE_CONTEXT = dict(batch_size=4096, baseline_batch_size=512, epsilon=.1, expert_ratio=.1,
    n_step=3, max_samples_per_frame=8, c51_target_smoothing=0, learning_control_lr_scale=.25,
    lr_gear='climb', lr_anchor_step=0., optimizer_lr=1.25e-5, optimizer_eps=1.5e-4,
    fused=True, gamma=.995, num_atoms=51, v_min=-10., v_max=50.)
# Assigned ONLY after --execute has authenticated a root job; defaults do no path resolution/read.
DIRECTORY = GAME = SOURCE = None
SOURCE_HASHES = {}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def canonical(value, *, exists=True):
    require(isinstance(value, str), 'Path must be an explicit string')
    path = Path(value)
    require(path.is_absolute() and path == path.resolve(strict=exists), 'Path must be absolute/canonical: ' + value)
    return path


def fingerprint(path):
    path = canonical(str(path))
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), 'Expected nonsymlink regular file: ' + str(path))
    digest = hashlib.sha256()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Open race: ' + str(path))
        for chunk in iter(lambda: stream.read(4 << 20), b''):
            digest.update(chunk)
        require(identity(os.fstat(stream.fileno())) == identity(before), 'FD changed: ' + str(path))
    require(identity(path.lstat()) == identity(before), 'Path changed: ' + str(path))
    return dict(path=str(path), sha256=digest.hexdigest(), **identity(before))


def publish(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.link(temporary, path)
    temporary.unlink()
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, 'Invalid integer ' + name)
    return value


def check_pin(pin, evidence, label, *, metadata=False):
    require(isinstance(pin, dict) and set(pin) == {'path', 'sha256', 'bytes', 'identity'}, 'Invalid pin: ' + label)
    require(re.fullmatch(r'[0-9a-f]{64}', pin['sha256'] or ''), 'Invalid SHA256: ' + label)
    integer(pin['bytes'], label + '.bytes', 1)
    if metadata:
        require(pin['bytes'] <= MAX_METADATA, 'Metadata/source exceeds4MiB: ' + label)
    path = canonical(pin['path'])
    require(path.lstat().st_size == pin['bytes'], 'Bound size differs before hashing: ' + label)
    observed = fingerprint(path)
    expected_identity = {key: observed[key] for key in ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink')}
    require(observed['sha256'] == pin['sha256'] and observed['bytes'] == pin['bytes']
            and expected_identity == pin['identity'], 'Bound identity/SHA/bytes differ: ' + label)
    files = evidence.setdefault('bound_files', {})
    require(label in files or len(files) < MAX_BOUND_FILES, 'Bound-file budget exhausted')
    previous = files.get(label)
    require(previous is None or previous == observed, 'Binding changed: ' + label)
    evidence['bound_files'][label] = observed
    return observed


def pinned_json(pin, evidence, label):
    before = check_pin(pin, evidence, label, metadata=True)
    value = json.loads(Path(pin['path']).read_text())
    require(fingerprint(pin['path']) == before, 'JSON changed during parse: ' + label)
    return value


def trainer_identity(value):
    require(isinstance(value, dict) and set(value) == {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'},
            'Invalid explicitly bound trainer identity')
    integer(value['pid'], 'trainer.pid', 1); integer(value['starttime_ticks'], 'trainer.starttime_ticks', 1)
    require(re.fullmatch(r'robotron-managed-[A-Za-z0-9_.-]+-trainer\.service', value['unit'] or '')
            and re.fullmatch(r'[0-9a-f]{32}', value['invocation_id'] or ''), 'Invalid trainer unit/invocation')
    require(isinstance(value['cgroup'], str) and value['cgroup'].startswith('/user.slice/')
            and value['cgroup'].endswith('/' + value['unit'])
            and '..' not in value['cgroup'].split('/'), 'Invalid trainer cgroup')
    return value


def exact_absence(trainer):
    """Read only the explicitly named old PID and owned cgroup, never enumerate processes."""
    path = Path('/proc') / str(trainer['pid']) / 'stat'
    try:
        text = path.read_text()
    except (FileNotFoundError, ProcessLookupError):
        state = 'absent'
    else:
        require(int(text.split(' ', 1)[0]) == trainer['pid'] and ')' in text, 'Malformed exact PID stat')
        fields = text[text.rfind(')') + 2:].split()
        require(len(fields) > 19, 'Incomplete exact PID stat')
        current_start = int(fields[19])
        require(current_start != trainer['starttime_ticks'], 'Old trainer still alive')
        state = 'PID_reused_different_start'
    group = Path('/sys/fs/cgroup') / trainer['cgroup'].lstrip('/') / 'cgroup.procs'
    try:
        members = group.read_text().split()
    except (FileNotFoundError, ProcessLookupError):
        members = []
        group_state = 'absent'
    else:
        group_state = 'present_empty'
    require(not members, 'Owned trainer cgroup is nonempty; possible replacement/child')
    return dict(trainer=dict(trainer), old_PID_state=state, owned_cgroup_state=group_state)


def read_job(args):
    require(args.job is not None and re.fullmatch(r'[0-9a-f]{64}', args.expected_job_sha256 or '')
            and re.fullmatch(r'[0-9a-f]{64}', args.expected_verifier_sha256 or ''), 'Explicit job/verifier SHA256 required')
    source = fingerprint(Path(__file__).resolve())
    require(source['sha256'] == args.expected_verifier_sha256, 'Verifier source SHA256 differs')
    require(canonical(str(args.job)).stat().st_size <= MAX_JOB, 'Root job exceeds1MiB before hash')
    record = fingerprint(args.job)
    require(record['sha256'] == args.expected_job_sha256 and record['bytes'] <= MAX_JOB, 'Root job SHA/size differs')
    job = json.loads(Path(args.job).read_text())
    require(fingerprint(args.job) == record, 'Root job changed during parse')
    common = {'schema', 'mode', 'verifier_sha256', 'experiment', 'source', 'verification_copy',
              'clock_floor', 'source_control_context', 'output_directory'}
    require(isinstance(job, dict) and job.get('schema') == SCHEMA and job.get('mode') in ('insurance', 'stopped_latest'),
            'Unsupported maintenance job schema/mode')
    extra = 'insurance' if job['mode'] == 'insurance' else 'stopped_latest'
    require(set(job) == common | {extra} and job['verifier_sha256'] == source['sha256'], 'Unexpected job fields/source')
    require(isinstance(job['experiment'], str) and re.fullmatch(r'[A-Za-z0-9_-]{1,120}', job['experiment']), 'Invalid experiment')
    require(isinstance(job['clock_floor'], dict) and set(job['clock_floor']) == set(CLOCKS), 'Four-clock floor required')
    for key in CLOCKS: integer(job['clock_floor'][key], 'clock_floor.' + key, 1)
    output = canonical(job['output_directory'], exists=False)
    require(not output.exists() and output.parent.is_dir() and output.parent.stat().st_uid == os.getuid(),
            'Verification output must be NEW under owned parent')
    return job, record, source, output


def check_context(job, evidence):
    global GAME, SOURCE_HASHES
    context = job['source_control_context']
    require(isinstance(context, dict) and set(context) == {'game_root', 'model_dir', 'model_package',
            'archived_control', 'archived_trainer_unit', 'provenance', 'held_recipe_context'}, 'Invalid source/control context')
    GAME = canonical(context['game_root'])
    model_dir = canonical(context['model_dir'])
    require(GAME.is_dir() and model_dir.is_dir(), 'Game/model directories missing')
    require(context['held_recipe_context'] == HELD_RECIPE_CONTEXT, 'Declared held recipe differs; separately review a new recipe')
    package = context['model_package']
    require(isinstance(package, dict) and set(package) == set(MODEL_NAMES), 'Exactly four model-package pins required')
    SOURCE_HASHES = {}
    for name, pin in package.items():
        require(pin['path'] == str(GAME / 'Scripts/dqn' / name), 'Model-package path differs: ' + name)
        check_pin(pin, evidence, 'model/' + name, metadata=True)
        SOURCE_HASHES[name] = pin['sha256']
    control = pinned_json(context['archived_control'], evidence, 'archived_control')
    require(control['experiment'] == job['experiment'] and control['lr_scale'] == .25
            and control['epsilon_ramp']['start'] == control['epsilon_ramp']['end'] == .1,
            'Archived held-control experiment/recipe differs')
    check_pin(context['archived_trainer_unit'], evidence, 'archived_trainer_unit', metadata=True)
    require(isinstance(context['provenance'], list) and len(context['provenance']) <= MAX_BOUND_FILES - 12,
            'Too many provenance pins')
    for index, pin in enumerate(context['provenance']):
        check_pin(pin, evidence, 'provenance/%02d' % index, metadata=True)
    evidence['held_recipe_context'] = HELD_RECIPE_CONTEXT
    evidence['recipe_scope'] = ('Root-bound source and archived control/unit context. Only persisted fields are checked in '
        'the checkpoint; batch/nstep/cap/smoothing/multiplier/runtime ownership are not independently reobserved.')
    return model_dir


def check_mode(job, evidence, model_dir):
    floor = job['clock_floor']
    if job['mode'] == 'insurance':
        spec = job['insurance']
        require(isinstance(spec, dict) and set(spec) == {'tag', 'trainer', 'trigger_snapshot', 'completed_request'},
                'Invalid insurance binding')
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', spec['tag'] or ''), 'Invalid unique insurance tag')
        trainer = trainer_identity(spec['trainer'])
        trigger = pinned_json(spec['trigger_snapshot'], evidence, 'insurance_trigger_snapshot')
        require({key: trigger[key] for key in CLOCKS} == floor and trigger['client_count'] == 192
                and not trigger.get('measurement_active', False)
                and trigger['host_pipeline']['learning_exposure']['optimizer']['process_id'] == trainer['pid'],
                'Insurance floor/actual trigger/trainer scope differs')
        require(spec['completed_request']['path'] == str(model_dir / 'managed_save.request.json.completed'),
                'Insurance completion must bind the actual managed request slot')
        completed = pinned_json(spec['completed_request'], evidence, 'insurance_completed_request')
        require(completed == {'tag': spec['tag']} and job['source']['path'] ==
                str(model_dir / 'managed-checkpoints' / (spec['tag'] + '.pt')), 'Completed tag/source path differs')
        evidence['insurance_trigger'] = {key: trigger[key] for key in (*CLOCKS, 'client_count')}
    else:
        spec = job['stopped_latest']
        required = {'old_trainer', 'absence_receipt', 'insurance_verification'}
        require(isinstance(spec, dict) and required <= set(spec) <= required | {'owned_restart_lineage'},
                'Invalid stopped-latest binding')
        trainer = trainer_identity(spec['old_trainer'])
        absence = pinned_json(spec['absence_receipt'], evidence, 'stopped_absence_receipt')
        require(absence.get('schema') == ABSENCE_SCHEMA and absence.get('trainer') == trainer
                and absence.get('unit_main_pid') == 0 and absence.get('unit_active_state') == 'inactive'
                and absence.get('old_process_absent') is True and absence.get('owned_cgroup_empty') is True
                and absence.get('latest_path') == job['source']['path'], 'Root stopped-owner/absence receipt differs')
        require(job['source']['path'] == str(model_dir / 'robotron_dqn_latest.pt'), 'Stopped source is not current latest path')
        insurance = pinned_json(spec['insurance_verification'], evidence, 'insurance_CPU_verification')
        require(insurance.get('schema') == RESULT_SCHEMA and insurance.get('status') == 'PASS'
                and insurance.get('mode') == 'insurance' and insurance['root_job']['experiment'] == job['experiment']
                and insurance['root_job']['source_control_context']['model_dir'] == str(model_dir)
                and {key: insurance['clocks'][key] for key in CLOCKS} == floor,
                'Stopped latest floor is not the verified insurance from this trainer/branch')
        insured = trainer_identity(insurance['root_job']['insurance']['trainer'])
        if insured != trainer:
            require('owned_restart_lineage' in spec, 'Different retired trainer needs explicit owned restart lineage')
            lineage = pinned_json(spec['owned_restart_lineage'], evidence, 'owned_restart_lineage')
            require(lineage.get('schema') == LINEAGE_SCHEMA and lineage.get('insured_trainer') == insured
                    and lineage.get('retired_trainer') == trainer and lineage.get('authorized_start_adopted') is True
                    and lineage.get('unknown_replacement_adopted') is False
                    and lineage.get('experiment') == job['experiment'] and lineage.get('model_dir') == str(model_dir)
                    and lineage.get('source_phase') in ('before', 'after')
                    and trainer['unit'] == insured['unit'] and trainer['cgroup'] == insured['cgroup'],
                    'Owned restart lineage differs from the insured branch/unit/source phase')
            request = pinned_json(lineage['start_request'], evidence, 'owned_restart_start_request')
            require(request.get('schema') == START_SCHEMA and request.get('insured_trainer') == insured
                    and request.get('unit') == trainer['unit'] and request.get('cgroup') == trainer['cgroup']
                    and request.get('experiment') == job['experiment'] and request.get('model_dir') == str(model_dir)
                    and request.get('source_phase') == lineage['source_phase']
                    and request.get('owned_start_requested') is True
                    and isinstance(request.get('request_id'), str) and 1 <= len(request['request_id']) <= 120
                    and request['request_id'] == lineage.get('request_id'), 'Known owned start-request binding differs')
        else:
            require('owned_restart_lineage' not in spec, 'Initial-trainer verification needs no restart lineage')
        identities = [insured] + ([] if insured == trainer else [trainer])
        evidence['retired_identities_requiring_absence'] = identities
        evidence['absence_before'] = [exact_absence(value) for value in identities]
        evidence['verified_insurance_floor'] = dict(floor)


def check_root_copy(job, evidence):
    global SOURCE
    SOURCE = canonical(job['source']['path'])
    require(type(job['source']['bytes']) is int and 200 << 20 <= job['source']['bytes'] <= 400 << 20,
            'Checkpoint outside inherited200..400MiB parse bound before hash')
    require(job['verification_copy']['bytes'] == job['source']['bytes'], 'Declared root-copy size differs')
    before = check_pin(job['source'], evidence, 'source_checkpoint')
    require(200 << 20 <= before['bytes'] <= 400 << 20, 'Checkpoint outside inherited200..400MiB parse bound')
    copied = check_pin(job['verification_copy'], evidence, 'root_readonly_verification_copy')
    require(copied['sha256'] == before['sha256'] and copied['bytes'] == before['bytes'], 'Root copy bytes differ')
    require((copied['device'], copied['inode']) != (before['device'], before['inode'])
            and copied['uid'] == os.getuid() and copied['nlink'] == 1 and copied['mode'] == '0o444',
            'Root verification copy must be independent, owned, single-link and0444')
    evidence.update(source_before=before, verification_copy=copied)
    return Path(copied['path'])


def numerical_setup(evidence):
    require(not any(name == 'torch' or name.startswith('torch.') or name == 'numpy'
                    or name.startswith('dqn') for name in sys.modules), 'Fresh process required')
    # These values precede every numerical/config/model import. No production
    # config/control/settings/journal paths are imported or opened.
    for key in list(os.environ):
        if key.startswith(('DQN_', 'ROBOTRON_')) or key in ('LD_PRELOAD', 'PYTHONPATH'):
            os.environ.pop(key, None)
    private = DIRECTORY / 'private-source'
    private.mkdir(exist_ok=False)
    runtime = DIRECTORY / 'private-runtime'
    runtime.mkdir(exist_ok=False)
    (runtime / 'models').mkdir()
    publish(runtime / 'models/game_settings.json', {})
    publish(runtime / 'control.json', {})
    os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                      OPENBLAS_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2',
                      PYTHONDONTWRITEBYTECODE='1', DQN_FRAME_STACK='4',
                      DQN_BATCH_SIZE='4096', DQN_N_STEP='3', DQN_MAX_SAMPLES_PER_FRAME='8',
                      DQN_C51_TARGET_SMOOTHING='0', DQN_FUSED_ADAM='1',
                      ROBOTRON_DQN_MODEL_DIR=str(runtime / 'models'),
                      ROBOTRON_DQN_CONTROL_PATH=str(runtime / 'control.json'),
                      ROBOTRON_RUN_DIR=str(runtime / 'journal'),
                      ROBOTRON_TRAIN_GPU='0', ROBOTRON_INFERENCE_GPU='0')
    sys.dont_write_bytecode = True
    originals, copies = {}, {}
    for name, expected in SOURCE_HASHES.items():
        source = GAME / 'Scripts/dqn' / name
        originals[name] = fingerprint(source)
        require(originals[name]['sha256'] == expected, f'Current model source drift: {name}')
        data = source.read_bytes()
        require(hashlib.sha256(data).hexdigest() == expected, f'Source copy race: {name}')
        with (private / name).open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        (private / name).chmod(0o444)
        copies[name] = fingerprint(private / name)
    evidence['current_model_source'] = originals
    evidence['private_model_source'] = copies
    import torch
    torch.set_num_threads(2); torch.set_num_interop_threads(2)
    require(not torch.cuda.is_initialized() and torch.cuda.device_count() == 0, 'CUDA must remain hidden/uninitialized')
    package = '_live8_maintenance_private_dqn'
    specification = importlib.util.spec_from_file_location(package, private / '__init__.py',
                                                          submodule_search_locations=[str(private)])
    module = importlib.util.module_from_spec(specification)
    sys.modules[package] = module
    specification.loader.exec_module(module)
    model = importlib.import_module(package + '.model')
    config = sys.modules[package + '.config']
    for name in SOURCE_HASHES:
        imported = sys.modules[package if name == '__init__.py' else package + '.' + name[:-3]]
        require(Path(imported.__file__).resolve() == private / name, f'Module path escaped private copy: {name}')
    require(config.MODEL_DIR == str(runtime / 'models') and
            str(config.learning_control.path) == str(runtime / 'control.json'), 'Config paths escaped isolation')
    require(config.RL_CONFIG.state_size == 11128 and config.RL_CONFIG.frame_stack == 4 and
            config.RL_CONFIG.single_frame_state_size == 2782, 'Current model geometry differs')
    for name in ('batch_size', 'n_step', 'max_samples_per_frame', 'c51_target_smoothing',
                 'baseline_batch_size', 'gamma', 'num_atoms', 'v_min', 'v_max'):
        require(getattr(config.RL_CONFIG, name) == HELD_RECIPE_CONTEXT[name], f'Private config differs: {name}')
    evidence['runtime'] = dict(torch_version=torch.__version__, CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],
                              torch_threads=torch.get_num_threads(), interop_threads=torch.get_num_interop_threads(),
                              model_module=str(model.__file__), config_module=str(config.__file__))
    return torch, model


def finite_tree(value, torch, counts, path='checkpoint'):
    if isinstance(value, torch.Tensor):
        require(value.device.type == 'cpu' and value.layout == torch.strided, f'Unexpected tensor device/layout: {path}')
        counts['tensors'] += 1; counts['tensor_elements'] += value.numel()
        require(bool(torch.isfinite(value).all()), f'Nonfinite tensor: {path}')
    elif isinstance(value, Mapping):
        for key, item in value.items():
            require(type(key) in (str, int), f'Unsupported mapping key at {path}')
            finite_tree(item, torch, counts, f'{path}/{key}')
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            finite_tree(item, torch, counts, f'{path}/{index}')
    elif type(value) is float:
        counts['scalars'] += 1
        require(math.isfinite(value), f'Nonfinite scalar: {path}')
    elif type(value) is int:
        counts['integer_scalars'] += 1
    else:
        require(value is None or type(value) in (str, bool), f'Unsupported checkpoint value: {path}:{type(value)}')


def validate_checkpoint(path, floor, evidence, *, metadata_callback=None):
    torch, source_model = numerical_setup(evidence)
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    require(isinstance(checkpoint, dict), 'Checkpoint must be a dictionary')
    counts = dict(tensors=0, scalars=0, integer_scalars=0, tensor_elements=0)
    evidence['finite'] = counts
    finite_tree(checkpoint, torch, counts)
    for key, expected in EXPECTED.items():
        require(type(checkpoint.get(key)) is int and checkpoint[key] == expected, f'Checkpoint geometry differs: {key}')
    for key in (*CLOCKS, 'total_training_steps', 'measurement_frame_count', 'last_target_update_samples', 'baseline_batch_size'):
        integer(checkpoint.get(key), key)
    for key in CLOCKS:
        require(checkpoint[key] >= floor[key], f'Saved {key} predates the bound four-clock floor')
    require(checkpoint['last_target_update_samples'] <= checkpoint['optimized_samples'], 'Target clock exceeds sample clock')
    require(checkpoint['baseline_batch_size'] == 512, 'Unexpected schedule baseline batch size')
    require(math.isclose(checkpoint['epsilon'], .1, rel_tol=0, abs_tol=1e-12) and
            math.isclose(checkpoint['expert_ratio'], .1, rel_tol=0, abs_tol=1e-12), 'Saved exploration differs')
    require(checkpoint.get('lr_gear') == HELD_RECIPE_CONTEXT['lr_gear'] and
            type(checkpoint.get('lr_anchor_step')) in (int, float) and
            checkpoint['lr_anchor_step'] == HELD_RECIPE_CONTEXT['lr_anchor_step'],
            'Saved LR gear/anchor differs from held recipe')
    evidence['clocks'] = {key: value for key, value in checkpoint.items()
                          if not isinstance(value, (Mapping, list, tuple, torch.Tensor))}
    network = source_model.RainbowNet(11128).cpu()
    expected_state = network.state_dict()
    models = {}
    for label in ('online_state_dict', 'target_state_dict'):
        state = checkpoint.get(label)
        require(isinstance(state, Mapping) and set(state) == set(expected_state), f'Strict model keys differ: {label}')
        for name, expected in expected_state.items():
            actual = state[name]
            require(isinstance(actual, torch.Tensor) and actual.shape == expected.shape and actual.dtype == expected.dtype,
                    f'Strict shape/dtype differs: {label}/{name}')
        require(torch.equal(state['support'], expected_state['support']), f'C51 support differs: {label}')
        loaded = network.load_state_dict(state, strict=True)
        require(not loaded.missing_keys and not loaded.unexpected_keys, f'Strict load failed: {label}')
        models[label] = dict(strict_cpu_load=True, tensor_count=len(state),
                             parameter_count=sum(parameter.numel() for parameter in network.parameters()))
    evidence['models'] = models
    optimizer = checkpoint['optimizer_state_dict']
    require(isinstance(optimizer, Mapping) and set(optimizer) == {'state', 'param_groups'}, 'Unexpected Adam schema')
    groups, states = optimizer['param_groups'], optimizer['state']
    evidence['adam_state_count'] = len(states)
    evidence['adam_group_count'] = len(groups)
    require(isinstance(groups, list) and len(groups) == 1 and isinstance(states, Mapping) and len(states) == 81,
            'Expected one Adam group and81 initialized states')
    group = groups[0]
    require(isinstance(group, Mapping), 'Adam group must be a mapping')
    evidence['adam_group'] = {key: value for key, value in group.items() if key != 'params'}
    for name, expected in (('lr', HELD_RECIPE_CONTEXT['optimizer_lr']), ('eps', HELD_RECIPE_CONTEXT['optimizer_eps']),
                           ('weight_decay', 0.)):
        require(type(group.get(name)) in (int, float) and
                math.isclose(group[name], expected, rel_tol=0, abs_tol=1e-12), f'Saved Adam {name} differs')
    require(tuple(group.get('betas', ())) == (.9, .999) and group.get('fused') is True and
            group.get('amsgrad') is False and group.get('maximize') is False,
            'Saved Adam fused/default algorithm differs')
    parameters = list(network.named_parameters())
    ids = groups[0]['params']
    require(isinstance(ids, list) and all(type(item) is int for item in ids) and
            len(ids) == len(parameters) and len(set(ids)) == len(ids) and set(states).issubset(ids),
            'Adam parameter identities differ')
    evidence['adam_uninitialized_parameter_names'] = [name for parameter_id, (name, _) in zip(ids, parameters)
                                                       if parameter_id not in states]
    by_id = dict(zip(ids, parameters)); steps = []
    evidence['adam_steps'] = {}
    for parameter_id, state in states.items():
        require(set(state) == {'step', 'exp_avg', 'exp_avg_sq'}, 'Unexpected Adam slot schema')
        name, parameter = by_id[parameter_id]
        step = state['step']
        require(isinstance(step, torch.Tensor) and step.ndim == 0 and step.numel() == 1, f'Invalid Adam step: {name}')
        value = float(step.item())
        require(value > 0 and value.is_integer(), f'Nonpositive/noninteger Adam step: {name}')
        steps.append(value)
        evidence['adam_steps'][name] = value
        for moment in ('exp_avg', 'exp_avg_sq'):
            require(state[moment].shape == parameter.shape and state[moment].dtype == parameter.dtype,
                    f'Adam moment geometry differs: {name}/{moment}')
        require(bool((state['exp_avg_sq'] >= 0).all()), f'Negative Adam second moment: {name}')
    require(min(steps) == max(steps), 'Adam step clocks differ')
    evidence['logical_training_steps_minus_adam_step'] = checkpoint['training_steps'] - int(steps[0])
    evidence['adam_clock_scope'] = (
        'All81 slot clocks must agree; their actual difference from logical training_steps is reported, '
        'not forced equal or attributed solely to AMP skips. Root reviews any unexplained difference.')
    scaler = checkpoint['grad_scaler_state_dict']
    require(isinstance(scaler, dict) and set(scaler) == {'scale', 'growth_factor', 'backoff_factor', 'growth_interval', '_growth_tracker'},
            'Missing/unexpected GradScaler state')
    require(scaler['scale'] > 0 and scaler['growth_factor'] > 1 and 0 < scaler['backoff_factor'] < 1,
            'Invalid finite GradScaler scale/factors')
    integer(scaler['growth_interval'], 'scaler.growth_interval', 1)
    integer(scaler['_growth_tracker'], 'scaler._growth_tracker')
    require(scaler['_growth_tracker'] < scaler['growth_interval'], 'Invalid scaler growth tracker')
    evidence.update(adam_state_count=len(states), adam_step_min=min(steps), adam_step_max=max(steps), grad_scaler=scaler,
                    cuda_initialized=torch.cuda.is_initialized(), visible_cuda_devices=torch.cuda.device_count())
    require(not evidence['cuda_initialized'] and evidence['visible_cuda_devices'] == 0, 'CUDA initialized unexpectedly')
    for name, expected in SOURCE_HASHES.items():
        require(fingerprint(GAME / 'Scripts/dqn' / name) == evidence['current_model_source'][name], f'Source changed: {name}')
        require(fingerprint(DIRECTORY / 'private-source' / name) == evidence['private_model_source'][name], f'Private source changed: {name}')
    if metadata_callback is not None:
        metadata_callback(checkpoint, evidence)


def main(argv=None):
    global DIRECTORY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256')
    parser.add_argument('--expected-verifier-sha256')
    args = parser.parse_args(argv)
    if args.execute:
        raise RuntimeError('Use verify_phase_snapshot_lr25.py: explicit hot-change context and CE lineage required')
    if not args.execute:
        print('PLAN_ONLY: explicit root job required; no job/checkpoint/context reads, imports or output mutation')
        return 0
    evidence = None
    try:
        require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and 'LD_PRELOAD' not in os.environ
                and 'PYTHONPATH' not in os.environ, 'Start with CUDA hidden and LD_PRELOAD/PYTHONPATH unset')
        require(not any(name == 'torch' or name.startswith('torch.') or name == 'numpy'
                        or name.startswith('dqn') for name in sys.modules), 'Fresh stdlib-only interpreter required')
        job, job_record, self_record, output = read_job(args)
        DIRECTORY = output
        DIRECTORY.mkdir(mode=0o700, exist_ok=False)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 << 20, 32 << 20))
        evidence = dict(schema=RESULT_SCHEMA, status='RUNNING', mode=job['mode'], utc=now(),
                        script=self_record, job_file=job_record, root_job=job,
                        scope='CPU structure/finite/current-model/clock verification only; no replay/coherent-anchor/restore/quality claim')
        model_dir = check_context(job, evidence)
        check_mode(job, evidence, model_dir)
        copied = check_root_copy(job, evidence)
        validate_checkpoint(copied, job['clock_floor'], evidence)
        if job['mode'] == 'stopped_latest':
            evidence['absence_after'] = [exact_absence(value) for value in evidence['retired_identities_requiring_absence']]
        # Every explicitly bound source/copy/control/unit/completion/proof retains
        # its original full identity/SHA. This includes no atime comparison.
        for label, before in evidence['bound_files'].items():
            require(fingerprint(before['path']) == before, 'Bound file changed after verification: ' + label)
        require(fingerprint(args.job) == job_record and fingerprint(Path(__file__).resolve()) == self_record,
                'Root job/verifier changed during verification')
        evidence.update(status='PASS', finished_utc=now(), path=str(copied),
                        sha256=job['verification_copy']['sha256'], bytes=job['verification_copy']['bytes'],
                        mode_bits='0o444', actual_restore_or_optimizer_step=False)
        publish(DIRECTORY / 'cpu-verification.json', evidence)
        print(json.dumps(dict(status='PASS', mode=job['mode'], path=str(copied),
                             sha256=evidence['sha256'], clocks=evidence['clocks']), indent=2))
        return 0
    except BaseException as error:
        if evidence is not None:
            evidence.update(status='FAIL', finished_utc=now(), error=repr(error), traceback=traceback.format_exc())
            try:
                publish(DIRECTORY / 'verification-error.json', evidence)
            except BaseException as secondary:
                print('Failure receipt could not persist: ' + repr(secondary), file=sys.stderr)
        else:
            print('Root-job/pre-output verification failed: ' + repr(error), file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
