#!/usr/bin/env python3
"""Bounded CPU-only CE/KL replay-priority diagnostic; never changes the trainer.

Uniform samples from ring and pinned saved-bank generations are copied once.
The copied rows and per-row results may be saved for reproducible review.
"""
import argparse
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ['CUDA_VISIBLE_DEVICES'] = ''
for _name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '2'

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from Robotron.tools.probe_checkpoint_cpu import load_partition, sample_budget, validate_arrays


def bank_generation(path, bank):
    """Pin the CURRENT generation, or a genuine legacy bank, without writes."""
    pointer = path / 'CURRENT.json'
    if not pointer.exists():
        return path, dict(format='legacy', path=str(path))
    data = json.loads(pointer.read_text())
    generation = data.get('generation')
    if (data.get('schema') != 'robotron-bank-generation-v1' or data.get('bank') != bank
            or not isinstance(generation, str) or not generation.startswith('gen-')
            or Path(generation).name != generation or '/' in generation or '\\' in generation):
        raise ValueError('Invalid bank generation pointer')
    resolved = path / 'generations' / generation
    if not resolved.is_dir():
        raise ValueError('Referenced saved bank generation is unavailable')
    return resolved, dict(format='generation', pointer=data, path=str(resolved))


def projected_target(target_p, rewards, dones, horizons, support, gamma, smoothing):
    """C51 projection in fp32, retaining exact-bin and terminal mass."""
    count = support.numel()
    transformed = rewards[:, None] + (1 - dones[:, None]) * gamma ** horizons[:, None] * support
    bins = (transformed.clamp(support[0], support[-1]) - support[0]) / (support[-1] - support[0]) * (count - 1)
    low, high = bins.floor().long().clamp(0, count - 1), bins.ceil().long().clamp(0, count - 1)
    same = low == high
    output = torch.zeros_like(target_p, dtype=torch.float32)
    output.scatter_add_(1, low, target_p.float() * torch.where(same, 1., high.float() - bins))
    output.scatter_add_(1, high, target_p.float() * torch.where(same, 0., bins - low.float()))
    return output * (1 - smoothing) + smoothing / count


def per_row_metrics(log_probabilities, targets):
    """CE is the training objective; KL removes only target entropy."""
    ce = -(targets.float() * log_probabilities.float()).sum(dim=1)
    entropy = -(targets.float() * targets.float().clamp_min(1e-12).log()).sum(dim=1)
    return ce, entropy, (ce - entropy).clamp_min(0)


def distribution(values):
    values = np.asarray(values, dtype=np.float64)
    return dict(count=len(values), mean=float(values.mean()), minimum=float(values.min()),
                maximum=float(values.max()), quantiles=dict(zip(
                    ('p0', 'p10', 'p25', 'p50', 'p75', 'p90', 'p99', 'p100'),
                    map(float, np.quantile(values, [0, .1, .25, .5, .75, .9, .99, 1])))))


def correlation(left, right):
    left, right = np.asarray(left), np.asarray(right)
    if np.std(left) == 0 or np.std(right) == 0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def counterfactual_weights(values, alpha=.7, beta=1., epsilon=1e-6):
    """Finite-population proxy only; not live-tree or actual learner weights."""
    priority = (np.maximum(np.asarray(values, dtype=np.float64), 0) + epsilon) ** alpha
    probability = priority / priority.sum()
    weight = (len(priority) * probability) ** (-beta)
    weight /= weight.max()
    contribution = probability * weight
    contribution /= contribution.sum()
    return dict(priority=distribution(priority), normalized_is_weight_over_uniform_pool=distribution(weight),
                expected_normalized_weight_under_priority_draw=float(np.dot(probability, weight)),
                sampling_effective_population_fraction=float(1 / np.dot(probability, probability) / len(priority)),
                largest_to_smallest_priority_ratio=float(priority.max() / priority.min()),
                effective_gradient_contribution_fraction=distribution(contribution),
                beta=beta, alpha=alpha, priority_epsilon=epsilon)


def summarize(ce, entropy, kl, alpha=.7, beta=1.):
    ce, entropy, kl = map(lambda x: np.asarray(x, dtype=np.float64), (ce, entropy, kl))
    size = max(1, int(np.ceil(len(ce) * .1)))
    ce_top, kl_top = np.argsort(ce)[-size:], np.argsort(kl)[-size:]
    return dict(ce=distribution(ce), target_entropy=distribution(entropy), kl=distribution(kl),
                entropy_fraction_of_mean_ce=float(entropy.mean() / ce.mean()) if ce.mean() else None,
                pearson_ce_vs_entropy=correlation(ce, entropy), pearson_kl_vs_entropy=correlation(kl, entropy),
                pearson_ce_vs_kl=correlation(ce, kl),
                top_decile_overlap_fraction=float(len(set(ce_top) & set(kl_top)) / size),
                ce_counterfactual=counterfactual_weights(ce, alpha, beta),
                kl_counterfactual=counterfactual_weights(kl, alpha, beta))


def evaluate(online, target, arrays, cfg):
    tensors = {key: torch.from_numpy(value) for key, value in arrays.items()}
    rows = torch.arange(len(arrays['actions']))
    states, next_states = tensors['states'].float(), tensors['next_states'].float()
    with torch.inference_mode():
        log_p = online.joint_dist(states, log=True)[rows, tensors['actions'].long()]
        best = online.q_values_joint(next_states).argmax(dim=1)
        target_p = target.joint_dist(next_states)[rows, best]
        projected = projected_target(target_p, tensors['rewards'].float(), tensors['dones'].float(),
                                     tensors['horizons'].float(), online.support, cfg.gamma, cfg.c51_target_smoothing)
        ce, entropy, kl = per_row_metrics(log_p, projected)
        torch.testing.assert_close(projected.sum(1), torch.ones(len(rows)), rtol=1e-5, atol=1e-6)
    return {key: value.numpy() for key, value in dict(ce=ce, entropy=entropy, kl=kl).items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--runtime-metadata', type=Path, required=True)
    parser.add_argument('--replay-dir', type=Path, default=Path('/dev/shm/robotron_dqn_latest_replay'))
    parser.add_argument('--bank-base', type=Path, default=ROOT / 'Robotron/models_dqn/robotron_dqn_latest_replay')
    parser.add_argument('--ring-size', type=int)
    parser.add_argument('--samples', type=int, default=256)
    parser.add_argument('--seed', type=int, default=81955)
    parser.add_argument('--save-sample', type=Path)
    parser.add_argument('--sample-file', type=Path, help='Reuse an existing copied .npz sample; skips all live replay reads')
    args = parser.parse_args()
    if not 1 <= args.samples <= 256:
        parser.error('sample budget must be within 1..256')
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    runtime = json.loads(args.runtime_metadata.read_text())['config']
    with contextlib.redirect_stdout(sys.stderr):
        from Robotron.Scripts.dqn.config import RL_CONFIG
        from Robotron.Scripts.dqn.model import RainbowNet
    cfg = copy.copy(RL_CONFIG)
    for key in ('gamma', 'n_step', 'c51_target_smoothing', 'priority_alpha', 'priority_beta_start',
                'priority_beta_frames', 'priority_eps'):
        setattr(cfg, key, runtime[key])
    if any(runtime[key] != getattr(cfg, key) for key in ('state_size', 'num_atoms', 'v_min', 'v_max')):
        raise ValueError('Runtime metadata does not match imported model architecture/support')
    provenance = {}
    partitions = {}
    saved = {}
    if args.sample_file:
        fields = ('states', 'next_states', 'actions', 'rewards', 'dones', 'horizons', 'is_expert', 'actor_kind')
        with np.load(args.sample_file, allow_pickle=False) as sample:
            for name in ('ring', 'hof', 'ephof'):
                if f'{name}_states' not in sample:
                    continue
                arrays = {key:sample[f'{name}_{key}'].copy() for key in fields}
                count = len(arrays['actions'])
                arrays, rejected = validate_arrays(arrays, cfg)
                if rejected or len(arrays['actions']) != count:
                    raise ValueError(f'{name}: saved sample has invalid rows')
                partitions[name] = (dict(saved_sample=str(args.sample_file), sample_count=count), arrays)
        if not partitions or sum(len(a['actions']) for _, a in partitions.values()) > 256:
            raise ValueError('Saved sample must contain 1..256 rows total')
    else:
        paths = {'ring': args.replay_dir}
        for bank in ('hof', 'ephof'):
            path, provenance[bank] = bank_generation(Path(f'{args.bank_base}_{bank}'), bank)
            paths[bank] = path
        rng = np.random.default_rng(args.seed)
        budgets = sample_budget(args.samples, list(paths))
        for name, path in paths.items():
            if budgets[name] == 0:
                continue
            # Saved replay _meta is [data_ptr, valid_size, max_priority]. The
            # reusable historical probe treated data_ptr as size; correct it here.
            saved_ring_size = int(np.load(path / '_meta.npy', allow_pickle=False)[1]) if name == 'ring' else None
            ring_size = args.ring_size if args.ring_size is not None else saved_ring_size
            result = load_partition(path, name, rng, budgets[name], ring_size)
            if result is None:
                continue
            metadata, arrays = result
            if name == 'ring':
                metadata['saved_size'] = saved_ring_size
                metadata['explicit_ring_size'] = args.ring_size
            arrays, rejected = validate_arrays(arrays, cfg)
            if rejected or len(arrays['actions']) != budgets[name]:
                raise ValueError(f'{name}: sample contained {rejected} rejected rows; no silent replacement')
            partitions[name] = (metadata, arrays)
    for name, (_, arrays) in partitions.items():
        saved.update({f'{name}_{key}': value for key, value in arrays.items()})
    with args.checkpoint.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
        source.seek(0)
        checkpoint = torch.load(source, map_location='cpu', weights_only=True)
    if checkpoint['state_size'] != cfg.state_size:
        raise ValueError('Checkpoint state width mismatch')
    online, target = RainbowNet(cfg.state_size).cpu().eval(), RainbowNet(cfg.state_size).cpu().eval()
    online.load_state_dict(checkpoint['online_state_dict'], strict=True)
    target.load_state_dict(checkpoint['target_state_dict'], strict=True)
    if not all(torch.isfinite(value).all() for network in (online, target) for value in network.state_dict().values()):
        raise ValueError('Nonfinite checkpoint')
    beta = cfg.priority_beta_start + min(1., max(0, checkpoint['frame_count'] - checkpoint.get('measurement_frame_count', 0))
        / cfg.priority_beta_frames) * (1 - cfg.priority_beta_start)
    report = {}
    all_values = []
    for name, (metadata, arrays) in partitions.items():
        values = evaluate(online, target, arrays, cfg)
        saved.update({f'{name}_{key}': value for key, value in values.items()})
        report[name] = dict(metadata=metadata, summary=summarize(values['ce'], values['entropy'], values['kl'], cfg.priority_alpha, beta))
        all_values.append(values)
    pooled = {key: np.concatenate([value[key] for value in all_values]) for key in ('ce', 'entropy', 'kl')}
    if args.save_sample:
        np.savez_compressed(args.save_sample, **saved)
    output = dict(schema='robotron-priority-diagnostic-v1', utc=datetime.now(timezone.utc).isoformat(), device='cpu',
        torch_threads=torch.get_num_threads(), seed=args.seed, rows=sum(len(arrays['actions']) for _, arrays in partitions.values()),
        checkpoint=dict(path=str(args.checkpoint.resolve()), sha256=digest, **{key:checkpoint.get(key) for key in
            ('frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples', 'engine_version')}),
        runtime_metadata=str(args.runtime_metadata), config={key:getattr(cfg,key) for key in
            ('gamma', 'n_step', 'c51_target_smoothing', 'priority_alpha', 'priority_eps')}, beta=beta,
        bank_provenance=provenance, partitions=report, pooled_summary=summarize(pooled['ce'], pooled['entropy'], pooled['kl'], cfg.priority_alpha, beta),
        saved_sample=str(args.save_sample) if args.save_sample else None,
        reused_sample=str(args.sample_file) if args.sample_file else None,
        caveats=[
            'Uniform bounded partition samples are not the live prioritized/quota mixture; banks are saved snapshots.',
            'Live ring rows are copied without trainer locks; concurrent overwrites can produce mixed-column samples undetected by validation.',
            'Counterfactual normalized IS weights treat only the sampled rows as the entire population; they are not actual live replay weights.',
            'Only tree-drawn ring rows use PER. Recent/interest quotas retain weight1 and bank rows use mean PER weight; pooled summaries do not model that mixture.',
            'At beta1, exact unnormalized importance correction cancels priority in expected gradient contribution; batch-max normalization changes overall scale, and finite batches/quotas differ.',
            'Different priorities can change optimization scale, rare-event coverage, new-row priority caps/hints and learned behavior. No gameplay benefit is established.',
            'No checkpoint, live source, replay, trainer, RNG state, configuration, control, or GPU is modified.'])
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
