#!/usr/bin/env python3
"""Prepared one-shot CPU verification of the future unique 384M candidate.

Default: print the plan only; do not inspect/copy/load any candidate or receipt.
Execution requires --execute, explicit expected identity arguments, a completed
gate and root's future released window. See PREPARATION.txt for the argv template.

No agent, replay, forward/backward, optimizer step, campaign or promotion.
Failures and partial owned artifacts are retained; this script never retries.
"""
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
import shutil
import stat
import sys
import traceback


DIRECTORY = Path(__file__).resolve().parent
GAME = DIRECTORY.parents[3]
SOURCE = GAME / 'models_dqn/managed-checkpoints/fresh3-384M.pt'
GATE = DIRECTORY.parent / 'fresh3-384M-gate.json'
TARGET = 388629023
TAG = 'fresh3-384M'
EXPERIMENT = 'best10M-fresh3-eps10-cap8-nosmooth'
EXPECTED = dict(engine_version=28, state_size=11128,
                single_frame_state_size=2782, frame_stack=4)
SOURCE_HASHES = {
    'model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4',
    'config.py': 'f2794754a14e9f13c82b613aa131698246a08dc9021c18f1b78fda7c4b484498',
    'learning_control.py': '29a74b25be391290b07373cdce4680ae7513db31596929f0bc9972aaf0ab220d',
    '__init__.py': 'a2b3412fc502b7631295d639092e320d73f848895b994edc16bf9eebf8b5054c',
}
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
ARCHIVE = DIRECTORY.parent / 'inference-affinity-v2-live-20261017T0012Z-independent-final-analysis'
PROVENANCE = {
    GAME / 'Scripts/dqn/agent.py': '28977d6b925a4606a61b76438595f45ae054fc81aaaad989ab93e00d98a05668',
    GAME / 'tools/checkpoint_at_frame.py': '5d8d7ab2456f2d6a8ad89327596cec654feae9a66db98190a07c87063a3be2b1',
    DIRECTORY.parent / 'fresh3-384M-gate-launch-20261017.json': 'fc2f72dc4862227323b5fd5e45e3e9c09442cb9a2f71de31dd7221418c3c8aa0',
    ARCHIVE / 'unit-files/1-robotron-managed-run-26-d3b365c9-trainer.service': 'cf561ca968fb446500f960b50f017be64f8c465d234b6aa20b4f8fe72aa21a0e',
    ARCHIVE / 'source-and-controls/Robotron/models_dqn/learning_control.json': '036e85a226500a47a6d5bb251e1f0ae3d1def0ac45c11d25278d2f94ec5076dc',
    DIRECTORY.parent / 'quality320M-checkpoint-verification-20261017/verify_saved_checkpoint.py': 'e21268a5e8ee076bbcd89437d895a8e24e850977acd1d12ce9b8e91760ce9192',
}
HELD_RECIPE_CONTEXT = dict(
    experiment=EXPERIMENT, batch_size=4096, baseline_batch_size=512,
    epsilon=.1, expert_ratio=.1, n_step=3, max_samples_per_frame=8,
    c51_target_smoothing=0, learning_control_lr_scale=.5,
    lr_gear='climb', lr_anchor_step=0., optimizer_lr=2.5e-5,
    optimizer_eps=1.5e-4, fused=True, gamma=.995,
    num_atoms=51, v_min=-10., v_max=50.,
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid,
                nlink=info.st_nlink)


def fingerprint(path):
    """Hash one nonsymlink regular file, proving path/FD stability throughout."""
    path = Path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), f'Not a regular nonsymlink file: {path}')
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), f'Open race: {path}')
        for chunk in iter(lambda: stream.read(4 << 20), b''):
            digest.update(chunk)
        require(identity(os.fstat(stream.fileno())) == identity(before), f'FD changed: {path}')
    require(identity(path.lstat()) == identity(before), f'Path changed: {path}')
    return dict(path=str(path), sha256=digest.hexdigest(), **identity(before))


def publish(path, value):
    """New result only. Errors never overwrite prior verification evidence."""
    path = Path(path)
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.link(temporary, path)  # exclusive publication of a complete file
    temporary.unlink()
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, f'Invalid integer {name}: {value!r}')
    return value


def read_gate(evidence, args):
    before = fingerprint(GATE)
    require(before['sha256'] == args.expected_gate_sha256, 'Completed gate hash differs from explicit binding')
    gate = json.loads(GATE.read_text())
    require(fingerprint(GATE) == before, 'Gate changed while parsing')
    evidence['gate_file'] = before
    evidence['gate_receipt'] = gate
    require(set(gate) == {'tag', 'target', 'experiment', 'checkpoint', 'trigger_snapshot', 'saved_utc'},
            'Unexpected completed-gate schema (the actual helper has no COMPLETE/status field)')
    require(gate['tag'] == TAG and gate['target'] == TARGET and gate['experiment'] == EXPERIMENT,
            'Gate does not describe the exact selected experiment/target/tag')
    require(gate['checkpoint'] == str(SOURCE), 'Gate checkpoint path differs')
    require(isinstance(gate['saved_utc'], str) and
            datetime.fromisoformat(gate['saved_utc']).tzinfo is not None, 'Invalid gate save timestamp')
    trigger = gate['trigger_snapshot']
    require(isinstance(trigger, dict) and set(trigger) == {*CLOCKS, 'client_count'}, 'Invalid trigger schema')
    for key in CLOCKS:
        integer(trigger[key], 'trigger.' + key, 1)
    integer(trigger['client_count'], 'trigger.client_count', 1)
    require(trigger['learner_frame_count'] >= TARGET and trigger['client_count'] == 192,
            'Gate triggered below target or without all192 clients')
    return gate


def private_copy(evidence, args):
    before = fingerprint(SOURCE)
    evidence['source_before'] = before
    require(before['sha256'] == args.expected_sha256 and before['bytes'] == args.expected_bytes,
            'Candidate differs from explicit expected SHA256/bytes')
    destination = DIRECTORY / 'verification-copy.pt'
    with os.fdopen(os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source, destination.open('xb') as output:
        require(identity(os.fstat(source.fileno())) == {key: before[key] for key in identity(os.fstat(source.fileno()))},
                'Source identity changed before copy')
        shutil.copyfileobj(source, output, 4 << 20)
        output.flush(); os.fsync(output.fileno())
    destination.chmod(0o444)
    copied = fingerprint(destination)
    after = fingerprint(SOURCE)
    evidence.update(source_after_copy=after, verification_copy=copied)
    require(before == after, 'Source changed during copy')
    require(copied['sha256'] == before['sha256'] and copied['bytes'] == before['bytes'], 'Copy bytes differ')
    require((copied['device'], copied['inode']) != (before['device'], before['inode']), 'Copy aliases source inode')
    require(copied['uid'] == os.getuid() and copied['nlink'] == 1 and copied['mode'] == '0o444',
            'Verification copy is not an independently owned single-link readonly file')
    return destination


def check_provenance(evidence):
    evidence['bound_provenance'] = {}
    for path, expected in PROVENANCE.items():
        observed = fingerprint(path)
        require(observed['sha256'] == expected, f'Bound source/provenance drift: {path}')
        evidence['bound_provenance'][str(path)] = observed
    report = json.loads((DIRECTORY.parent / 'fresh3-384M-gate-launch-20261017.json').read_text())
    argv = report['argv']
    for flag, value in (('--target', str(TARGET)), ('--tag', TAG), ('--experiment', EXPERIMENT), ('--output', str(GATE))):
        require(argv.count(flag) == 1 and argv[argv.index(flag) + 1] == value, f'Original gate report differs: {flag}')
    require(report['target_learner_frames'] == TARGET and report['script_sha256'] ==
            PROVENANCE[GAME / 'tools/checkpoint_at_frame.py'], 'Original gate helper/target differs')
    control = json.loads((ARCHIVE / 'source-and-controls/Robotron/models_dqn/learning_control.json').read_text())
    require(control['experiment'] == EXPERIMENT and control['lr_scale'] == .5 and
            control['epsilon_ramp']['start'] == control['epsilon_ramp']['end'] == .1,
            'Archived held-control recipe differs')
    evidence['held_recipe_context'] = HELD_RECIPE_CONTEXT
    evidence['recipe_scope'] = (
        'Archived launch/control plus pinned config context; checkpoint verifies only persisted fields. '
        'Batch/n-step/cap/smoothing/control scale and runtime identity are not persisted or independently reobserved.')


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
    package = '_quality384M_private_dqn'
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


def validate_checkpoint(path, gate, evidence):
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
        require(checkpoint[key] >= gate['trigger_snapshot'][key], f'Saved {key} predates gate trigger')
    require(checkpoint['learner_frame_count'] >= TARGET, 'Saved learner frame clock below target')
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-checkpoint', type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--expected-bytes', type=int)
    parser.add_argument('--expected-target', type=int)
    parser.add_argument('--expected-tag')
    parser.add_argument('--expected-gate-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(dict(status='PLAN_ONLY', source=str(SOURCE), gate=str(GATE), minimum_learner_frames=TARGET,
                              tag=TAG, experiment=EXPERIMENT, expected_checkpoint_sha256=None, expected_checkpoint_bytes=None,
                              output_directory=str(DIRECTORY), source_hashes=SOURCE_HASHES,
                              provenance_hashes={str(path): value for path, value in PROVENANCE.items()},
                              held_recipe_context=HELD_RECIPE_CONTEXT,
                              authorization='Wait for actual completed gate plus explicit root GO; no candidate/artifact read or output mutation performed'), indent=2))
        return 0
    if (args.expected_checkpoint != SOURCE or args.expected_target != TARGET or args.expected_tag != TAG or
            not re.fullmatch(r'[0-9a-f]{64}', args.expected_sha256 or '') or
            not re.fullmatch(r'[0-9a-f]{64}', args.expected_gate_sha256 or '') or
            args.expected_bytes is None or not (200 << 20 <= args.expected_bytes <= 400 << 20)):
        parser.error('--execute requires exact384M checkpoint/target/tag and actual lowercase SHA256/bytes/gate SHA256 bindings')
    evidence = dict(status='RUNNING', utc=now(), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    execution_arguments=vars(args) | {'expected_checkpoint': str(args.expected_checkpoint)},
                    scope='Independent CPU finite/clock/strict-current-geometry verification copy only; no replay/coherent-resume/quality/promotion claim')
    try:
        require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not os.environ.get('LD_PRELOAD') and
                not os.environ.get('PYTHONPATH'), 'Launch with CUDA hidden and LD_PRELOAD/PYTHONPATH unset before interpreter')
        require(not any((DIRECTORY / name).exists() for name in
                        ('cpu-verification.json', 'verification-error.json', 'verification-copy.pt', 'private-source', 'private-runtime')),
                'One-shot output already exists; do not overwrite/retry')
        check_provenance(evidence)
        gate = read_gate(evidence, args)
        copied = private_copy(evidence, args)
        validate_checkpoint(copied, gate, evidence)
        evidence['source_after_verification'] = fingerprint(SOURCE)
        evidence['copy_after_verification'] = fingerprint(copied)
        require(evidence['source_after_verification'] == evidence['source_before'], 'Source changed after load')
        require(evidence['copy_after_verification'] == evidence['verification_copy'], 'Verification copy changed after load')
        require(fingerprint(GATE) == evidence['gate_file'], 'Gate changed after verification')
        for path in PROVENANCE:
            require(fingerprint(path) == evidence['bound_provenance'][str(path)], f'Bound provenance changed: {path}')
        evidence.update(status='PASS', finished_utc=now(), path=str(copied), sha256=evidence['verification_copy']['sha256'],
                        bytes=evidence['verification_copy']['bytes'], mode=evidence['verification_copy']['mode'])
        publish(DIRECTORY / 'cpu-verification.json', evidence)
        print(json.dumps(dict(status='PASS', path=str(copied), sha256=evidence['sha256'], clocks=evidence['clocks']), indent=2))
        return 0
    except BaseException as error:
        evidence.update(status='FAIL', finished_utc=now(), error=repr(error), traceback=traceback.format_exc())
        try:
            publish(DIRECTORY / 'verification-error.json', evidence)
        except BaseException as publication_error:
            print(f'Could not preserve failure receipt: {publication_error!r}', file=sys.stderr)
        print(evidence['traceback'], file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
