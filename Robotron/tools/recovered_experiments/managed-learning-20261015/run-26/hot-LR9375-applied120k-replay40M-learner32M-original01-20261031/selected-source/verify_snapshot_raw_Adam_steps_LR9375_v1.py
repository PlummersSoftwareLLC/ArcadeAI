"""CPU-only validation of an immutable recovery snapshot; never loads the learner."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys



def raw_adam_step_proof(saved, torch):
    """Inspect raw checkpoint tensors BEFORE optimizer.load_state_dict casts them."""
    states = saved['optimizer_state_dict']['state']
    assert len(states) == 81
    steps = [state['step'] for state in states.values()]
    assert all(torch.is_tensor(step) and step.ndim == 0 and torch.is_floating_point(step)
               and bool(torch.isfinite(step)) for step in steps)
    values = [float(step) for step in steps]
    dtype_counts = {}
    for step in steps:
        name = str(step.dtype); dtype_counts[name] = dtype_counts.get(name, 0) + 1
    groups = []
    for group in saved['optimizer_state_dict']['param_groups']:
        betas = [float(value) for value in group['betas']]
        assert len(betas) == 2 and all(0 <= value < 1 for value in betas)
        groups.append(dict(betas=betas, fused=group.get('fused'), capturable=group.get('capturable')))
    scalar_float32 = dtype_counts == {'torch.float32': 81}
    return dict(schema='robotron-raw-checkpoint-Adam-scalar-step-proof-v1', parameters=81,
        all_steps_are_scalar_tensors=True, all_steps_finite=True, raw_dtype_counts=dtype_counts,
        all_raw_scalar_float32=scalar_float32, raw_step_min=min(values), raw_step_max=max(values),
        all_raw_scalar_float32_exact_2p24=scalar_float32 and all(value == 16777216.0 for value in values),
        parameter_group_flags=groups, inspected_before_optimizer_load_state_dict=True,
        counter_reset_or_optimizer_change=False)


def verify(checkpoint, report):
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    import torch
    torch.set_num_threads(2)
    root = Path('/home/dave/source/repos/ArcadeAI/Robotron')
    sys.path.insert(0, str(root / 'Scripts'))
    from dqn.model import RainbowNet
    before = checkpoint.stat()
    assert before.st_mode & 0o222 == 0
    with checkpoint.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    saved = torch.load(checkpoint, map_location='cpu', mmap=True, weights_only=False)
    phase = saved['priority_metric_phase']
    assert phase['valid'] is True and phase['metric'] == 'ce'
    assert saved['state_size'] == 11128
    model = RainbowNet(saved['state_size'])
    for key in ['online_state_dict', 'target_state_dict']:
        state = saved[key]
        assert all(torch.isfinite(t).all().item() for t in state.values()
                   if torch.is_floating_point(t))
        loaded = model.load_state_dict(state, strict=False)
        assert not loaded.unexpected_keys and set(loaded.missing_keys) <= {'support'}
    raw_step_proof = raw_adam_step_proof(saved, torch)
    optimizer = torch.optim.Adam(model.parameters())
    optimizer.load_state_dict(saved['optimizer_state_dict'])
    steps = []
    for parameter, state in optimizer.state.items():
        assert parameter.shape == state['exp_avg'].shape == state['exp_avg_sq'].shape
        assert torch.isfinite(state['exp_avg']).all().item()
        assert torch.isfinite(state['exp_avg_sq']).all().item()
        steps.append(float(state['step']))
    assert all(math.isfinite(step) for step in steps)
    assert len(steps) == 81 and min(steps) == max(steps) and min(steps) > 0
    lrs = [group['lr'] for group in optimizer.param_groups]
    assert lrs == [5e-5 * 0.1875]
    assert not torch.cuda.is_initialized()
    after = checkpoint.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_ino, after.st_size, after.st_mtime_ns)
    result = dict(schema='robotron-recovery-snapshot-CPU-verification-v1',
        checkpoint=dict(path=str(checkpoint), sha256=digest, bytes=before.st_size),
        clocks={k: saved[k] for k in ['training_steps', 'learner_frame_count',
                                      'optimized_samples', 'frame_count']},
        priority_phase_valid=True, priority_phase=phase, optimizer_lrs=lrs,
        Adam_step_min=min(steps), Adam_step_max=max(steps), Adam_parameters=len(steps),
        Adam_raw_step_proof=raw_step_proof,
        verification_source=dict(path=str(Path(__file__).resolve()),
            sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), bytes=Path(__file__).stat().st_size),
        online_target_shapes_and_finiteness_verified=True, CUDA_initialized=False,
        quality_qualified=False)
    with report.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(checkpoint_sha256=digest, training_steps=saved['training_steps'],
                          Adam_step=min(steps), CPU_verification_passed=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    verify(args.checkpoint.resolve(strict=True), args.report.resolve())
