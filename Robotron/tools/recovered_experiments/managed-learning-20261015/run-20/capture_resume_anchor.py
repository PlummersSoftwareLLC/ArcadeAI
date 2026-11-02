"""CPU-only final anchor capture; refuses a still-running old trainer."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stopped-trainer-pid', type=int, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--stopped-console', type=Path, required=True)
    args = parser.parse_args()
    assert not Path(f'/proc/{args.stopped_trainer_pid}').exists(), 'Trainer must finish shutdown first'
    console = args.stopped_console.read_text(errors='replace')
    assert 'Final model & settings saved' in console and 'Shutdown complete' in console
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert args.label and all(c.isalnum() or c in '-_' for c in args.label)
    import numpy as np
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    game = Path(__file__).resolve().parents[3]
    source = game / 'models_dqn/robotron_dqn_latest.pt'
    before = source.stat()
    target = game / 'models_dqn/managed-checkpoints' / (args.label + '.pt')
    assert not target.exists()
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    assert source.stat().st_mtime_ns == before.st_mtime_ns
    assert source.stat().st_size == before.st_size
    assert digest(source) == digest(target)
    assert source.stat().st_ino != target.stat().st_ino and target.stat().st_nlink == 1
    checkpoint = torch.load(target, map_location='cpu', weights_only=False)
    keys = ('engine_version', 'state_size', 'single_frame_state_size', 'frame_stack',
            'baseline_batch_size', 'training_steps', 'optimized_samples',
            'learner_frame_count', 'frame_count', 'total_training_steps',
            'last_target_update_samples', 'measurement_frame_count')
    meta = {k: checkpoint[k] for k in keys}
    assert meta['engine_version'] == 28 and meta['state_size'] == 11128
    assert meta['single_frame_state_size'] == 2782 and meta['frame_stack'] == 4
    assert meta['baseline_batch_size'] == 512
    assert meta['total_training_steps'] == meta['training_steps']
    assert meta['learner_frame_count'] >= 100634474
    assert meta['measurement_frame_count'] == 7550388
    prior_path = Path(__file__).resolve().parent.parent / 'run-19/fresh3-96M-checkpoint-lineage.json'
    assert digest(prior_path) == 'aa701312ed0b4165b83e84e49b3add3e441d919d0e7b50b346bb33d38f06b4fa'
    prior = json.loads(prior_path.read_text())['candidate']
    for name, expected in prior['state_dict_signatures'].items():
        actual = {k: dict(shape=list(t.shape), dtype=str(t.dtype)) for k, t in checkpoint[name].items()}
        assert actual == expected
        assert all(t.device.type == 'cpu' and bool(torch.isfinite(t).all()) for t in checkpoint[name].values())
    optimizer = checkpoint['optimizer_state_dict']
    assert len(optimizer['state']) == 81
    for state in optimizer['state'].values():
        for value in state.values():
            if torch.is_tensor(value):
                assert value.device.type == 'cpu' and bool(torch.isfinite(value).all())
    steps = sorted({float(v['step'].item()) for v in optimizer['state'].values()})
    assert min(steps) >= 784351
    replay_meta_path = Path('/dev/shm/robotron_dqn_latest_replay/_meta.npy')
    replay_meta = np.load(replay_meta_path, allow_pickle=False)
    assert replay_meta.shape == (3,) and np.isfinite(replay_meta).all()
    assert replay_meta[0] == int(replay_meta[0]) and 0 <= replay_meta[0] < 6000000
    assert replay_meta[1] == 6000000 and replay_meta[2] > 0
    banks = {}
    for bank in ('hof', 'ephof'):
        directory = game / f'models_dqn/robotron_dqn_latest_replay_{bank}'
        selector_path = directory / 'CURRENT.json'
        selector_bytes = selector_path.read_bytes()
        selector = json.loads(selector_bytes)
        generation = selector['generation']
        assert selector['schema'] == 'robotron-bank-generation-v1' and selector['bank'] == bank
        assert len(generation) == 36 and generation.startswith('gen-')
        assert all(c in '0123456789abcdef' for c in generation[4:])
        metadata_path = directory / 'generations' / selector['generation'] / f'{bank}_meta.npz'
        with np.load(metadata_path, allow_pickle=False) as payload:
            lengths = payload['ep_len']
            stride = int(payload['stride'].item())
            assert stride == {'hof': 1536, 'ephof': 2048}[bank] and lengths.shape == (192,)
            assert np.all(lengths >= 0) and np.all(lengths <= stride)
            assert int(payload['mutation_generation'].item()) == selector['mutation_generation']
            assert np.isfinite(payload['ep_score']).all()
            episodes = int(np.count_nonzero(lengths))
            transitions = int(lengths.sum())
            assert int(payload['state_size'].item()) == 11128
        assert episodes == 192 and transitions > 0
        assert selector_path.read_bytes() == selector_bytes
        banks[bank] = dict(selector=selector,
            selector_sha256=hashlib.sha256(selector_bytes).hexdigest(),
            metadata_path=str(metadata_path), metadata_sha256=digest(metadata_path),
            episodes=episodes, transitions=transitions)
    assert not torch.cuda.is_initialized()
    target.chmod(0o444)
    report = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source=str(source.relative_to(game)), checkpoint=str(target.relative_to(game)),
        sha256=digest(target), saved_metadata=meta, optimizer_state_count=81,
        optimizer_parameter_steps=steps, banks=banks, cpu_only=True,
        optimizer_tensors_finite_CPU=True,
        cuda_initialized=False, architecture_unchanged=True,
        architecture_reference_lineage=str(prior_path),
        replay_metadata=dict(path=str(replay_meta_path), sha256=digest(replay_meta_path),
                             values=replay_meta.tolist(), size=6000000),
        stopped_trainer_pid=args.stopped_trainer_pid,
        shutdown_console=dict(path=str(args.stopped_console.resolve()),
                              sha256=digest(args.stopped_console), clean_shutdown_messages_verified=True),
        scope='Actual saved clocks, architecture, optimizer and storage facts; learning controls must be separately verified by root against the run environment/control file.')
    args.run_dir.mkdir(parents=True, exist_ok=True)
    with (args.run_dir / 'final-resume-checkpoint.json').open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(report))
