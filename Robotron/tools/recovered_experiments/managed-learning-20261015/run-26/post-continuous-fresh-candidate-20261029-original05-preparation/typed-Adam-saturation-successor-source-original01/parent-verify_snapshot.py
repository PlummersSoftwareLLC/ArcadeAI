"""CPU-only validation of an immutable recovery snapshot; never loads the learner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def verify(checkpoint, report):
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    import torch
    torch.set_num_threads(2)
    root = Path(__file__).resolve().parents[2]
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
    optimizer = torch.optim.Adam(model.parameters())
    optimizer.load_state_dict(saved['optimizer_state_dict'])
    steps = []
    for parameter, state in optimizer.state.items():
        assert parameter.shape == state['exp_avg'].shape == state['exp_avg_sq'].shape
        assert torch.isfinite(state['exp_avg']).all().item()
        assert torch.isfinite(state['exp_avg_sq']).all().item()
        steps.append(float(state['step']))
    assert len(steps) == 81 and min(steps) == max(steps) and min(steps) > 0
    lrs = [group['lr'] for group in optimizer.param_groups]
    assert lrs == [3.125e-6]
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
