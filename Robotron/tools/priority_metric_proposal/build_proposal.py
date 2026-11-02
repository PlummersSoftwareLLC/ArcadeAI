"""Generate review-only source copies and patch; never writes production files."""
from datetime import datetime, timezone
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = ROOT / 'Robotron/logs/managed-learning-20261015/run-26/priority-analysis'


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f'Expected exactly one source anchor: {before[:100]!r}')
    return source.replace(before, after, 1)


def prepare(output_dir=OUTPUT):
    output_dir = Path(output_dir)
    originals = {name: (ROOT / 'Robotron/Scripts/dqn' / name).read_text()
                 for name in ('config.py', 'loss_kernel.py', 'training.py', 'agent.py')}
    modified = dict(originals)
    text = modified['config.py']
    text = replace_once(text, '@dataclass\nclass RLConfigData:', '''def _validated_per_priority_metric(value):
    metric = str(value).strip().lower()
    if metric not in ("ce", "kl"):
        raise ValueError("DQN_PER_PRIORITY_METRIC must be ce or kl")
    return metric


@dataclass
class RLConfigData:''')
    text = replace_once(text, '    priority_alpha: float = 0.7\n', '''    priority_alpha: float = 0.7
    # Opt-in sampling experiment only; the categorical CE objective is unchanged.
    per_priority_metric: str = _validated_per_priority_metric(os.getenv("DQN_PER_PRIORITY_METRIC", "ce"))
''')
    modified['config.py'] = text
    text = modified['loss_kernel.py']
    text = replace_once(text, '\n\nclass TrainingLoss', '''

def categorical_priority_values(cross_entropy, projected, metric):
    """Detached replay surprise, independent of the CE training objective."""
    cross_entropy = cross_entropy.detach().float()
    if metric == "ce":
        return cross_entropy
    if metric != "kl":
        raise ValueError("PER priority metric must be ce or kl")
    with torch.no_grad():
        target = projected.detach().float()
        entropy = -(target * target.clamp_min(1e-12).log()).sum(dim=1)
        return (cross_entropy - entropy).clamp_min(0.0)


class TrainingLoss''')
    text = replace_once(text, 'def __init__(self, online_net, target_net, cfg, diagnostics=True):',
                        'def __init__(self, online_net, target_net, cfg, diagnostics=True, return_priorities=False):')
    text = replace_once(text, '        self.diagnostics = bool(diagnostics)\n', '''        self.diagnostics = bool(diagnostics)
        self.return_priorities = bool(return_priorities)
        self.priority_metric = str(getattr(cfg, "per_priority_metric", "ce"))
        if self.priority_metric not in ("ce", "kl"):
            raise ValueError("PER priority metric must be ce or kl")
''')
    text = replace_once(text, '        return weighted_loss, ce_loss, bc_loss, diagnostic_values\n', '''        if self.return_priorities:
            priorities = categorical_priority_values(ce_loss, projected, self.priority_metric)
            return weighted_loss, ce_loss, bc_loss, diagnostic_values, priorities
        return weighted_loss, ce_loss, bc_loss, diagnostic_values
''')
    modified['loss_kernel.py'] = text
    text = modified['agent.py']
    for diagnostics in ('False', 'True'):
        text = replace_once(text, f'TrainingLoss(self.online_net, self.target_net, RL_CONFIG, diagnostics={diagnostics})',
                            f'TrainingLoss(self.online_net, self.target_net, RL_CONFIG, diagnostics={diagnostics}, return_priorities=True)')
    text = replace_once(text, 'warm_loss, _, _, _ = loss_fn(', 'warm_loss, _, _, _, _ = loss_fn(')
    modified['agent.py'] = text
    text = modified['training.py']
    text = replace_once(text, '    from .learning_exposure import capture_amp_found_inf\n',
                        '    from .learning_exposure import capture_amp_found_inf\n    from .loss_kernel import categorical_priority_values\n')
    text = replace_once(text, '    from learning_exposure import capture_amp_found_inf\n',
                        '    from learning_exposure import capture_amp_found_inf\n    from loss_kernel import categorical_priority_values\n')
    text = replace_once(text, '            weighted_loss, ce_loss, bc_loss, kernel_diag = kernel(',
                        '            weighted_loss, ce_loss, bc_loss, kernel_diag, priority_values = kernel(')
    text = replace_once(text, '    # ── NaN / Inf guard', '''    priority_metric = str(getattr(cfg, "per_priority_metric", "ce"))
    if not kernel_active:
        priority_values = categorical_priority_values(ce_loss, m_joint, priority_metric)
    # Keep the default CE readback/layout exact. KL adds a vector to the same
    # existing readback; CE slice diagnostics retain their original meaning.
    scalar_offset = B * (2 if priority_metric == "kl" else 1)

    # ── NaN / Inf guard''')
    text = replace_once(text, '            outcome_host_index = B + len(scalars)',
                        '            outcome_host_index = scalar_offset + len(scalars)')
    text = replace_once(text, '        packed = torch.cat((ce_loss.detach().float(), torch.stack(scalars)))', '''        row_outputs = (ce_loss.detach().float(),)
        if priority_metric == "kl":
            row_outputs += (priority_values,)
        packed = torch.cat((*row_outputs, torch.stack(scalars)))''')
    text = replace_once(text, '    td_errors = host[:B]\n', '''    td_errors = host[:B]  # CE retained for existing slice diagnostics.
    priority_errors = host[B:2 * B] if priority_metric == "kl" else td_errors
''')
    for before, after in [('host[B:B+3]', 'host[scalar_offset:scalar_offset+3]'),
                          ('host[B+3:B+9]', 'host[scalar_offset+3:scalar_offset+9]'),
                          ('host[B+9:B+15]', 'host[scalar_offset+9:scalar_offset+15]'),
                          ('agent.memory.update_priorities(indices, td_errors)', 'agent.memory.update_priorities(indices, priority_errors)'),
                          ('agent.memory.update_priorities(indices, td_errors, timing_out=priority_timings)', 'agent.memory.update_priorities(indices, priority_errors, timing_out=priority_timings)'),
                          ('metrics.last_priority_mean = float(np.mean(td_errors))', 'metrics.last_priority_mean = float(np.mean(priority_errors))')]:
        text = replace_once(text, before, after)
    modified['training.py'] = text
    patch = []
    manifest = {}
    for name, source in modified.items():
        compile(source, name, 'exec')
        destination = output_dir / 'staged/Robotron/Scripts/dqn' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source)
        path = 'Robotron/Scripts/dqn/' + name
        patch.extend(difflib.unified_diff(originals[name].splitlines(keepends=True), source.splitlines(keepends=True),
                                        fromfile='a/' + path, tofile='b/' + path))
        manifest[path] = dict(base_sha256=hashlib.sha256(originals[name].encode()).hexdigest(),
                              proposed_sha256=hashlib.sha256(source.encode()).hexdigest())
    (HERE / 'optional-kl-priorities.patch').write_text(''.join(patch))
    (output_dir / 'proposal-manifest.json').write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
        status='UNAPPLIED_REVIEW_ONLY', source_files=manifest,
        behavior='Default CE unchanged; KL opt-in changes detached replay priority only; CE objective, diagnostics and all clocks unchanged.',
        metadata='run_telemetry.create_report records vars(config) and DQN_* environment, including per_priority_metric.',
        caution='Changing priority scale affects sampling, IS normalization, bank weights and insertion hints/caps; it requires a separately precommitted learning trial.'), indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    prepare(parser.parse_args().output_dir)
