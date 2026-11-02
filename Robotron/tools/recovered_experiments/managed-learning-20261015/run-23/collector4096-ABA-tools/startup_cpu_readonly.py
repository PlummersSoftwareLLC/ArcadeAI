"""Explicit CPU-only audit of ONE new collector-trial resume anchor; default inert."""
import datetime
import io
import json
import math
import os
from pathlib import Path
import re
import resource
import time

import startup_common as common

def finite_tree(value, torch):
    if torch.is_tensor(value):
        common.require(value.device.type == 'cpu' and bool(torch.isfinite(value).all()), 'Nonfinite/non-CPU saved tensor')
        return 1
    if isinstance(value, dict):
        return sum(finite_tree(item, torch) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(finite_tree(item, torch) for item in value)
    return 0

def scalar(value, torch):
    if torch.is_tensor(value):
        common.require(value.device.type == 'cpu' and value.numel() == 1, 'Bad saved scalar tensor')
        value = value.item()
    return value

def validate_checkpoint(saved, manifest, reference, torch):
    """Fakeable CPU validation; no file, process or runtime access."""
    count = finite_tree(saved, torch)
    common.require(count == 443, 'Expected complete443 saved CPU tensor inventory')
    metadata = {key: saved[key] for key in manifest['saved_metadata']}
    common.require(metadata == manifest['saved_metadata'], 'Actual saved clocks differ from root manifest')
    for key in ('training_steps', 'total_training_steps', 'optimized_samples', 'learner_frame_count',
                'frame_count', 'measurement_frame_count', 'last_target_update_samples'):
        common.require(type(metadata[key]) is int and metadata[key] >= 0, 'Bad clock: ' + key)
    common.require(metadata['training_steps'] == metadata['total_training_steps']
                   and metadata['last_target_update_samples'] <= metadata['optimized_samples']
                   and metadata['measurement_frame_count'] == 7550388
                   and metadata['baseline_batch_size'] == 512, 'Target/measurement/baseline clocks differ')
    geometry = {}
    for name, signature in reference['state_dict_signatures'].items():
        actual = saved[name]
        common.require(isinstance(actual, dict) and list(actual) == list(signature), 'Network field/order changed')
        geometry[name] = {key: dict(shape=list(value.shape), dtype=str(value.dtype)) for key, value in actual.items()}
        common.require(geometry[name] == signature, 'Network architecture changed')
    opt = saved['optimizer_state_dict']
    common.require(isinstance(opt['state'], dict) and len(opt['state']) == manifest['optimizer_state_count'] == 81,
                   'Adam81 state absent/reset')
    ids, groups = [], []
    for group in opt['param_groups']:
        common.require(isinstance(group['params'], list) and all(type(value) is int for value in group['params']),
                       'Malformed optimizer parameter IDs')
        ids.extend(group['params'])
        groups.append(dict({key: scalar(value, torch) for key, value in group.items() if key != 'params'},
                           parameter_count=len(group['params'])))
    # JSON canonicalization preserves the tuple/list convention of recorded Adam betas.
    groups = json.loads(json.dumps(groups, allow_nan=False))
    common.require(groups == reference['optimizer']['groups'], 'Optimizer geometry/LR recipe changed')
    order = list(reference['state_dict_signatures']['online_state_dict'])
    names = [name for name in order if name != 'support']
    common.require(len(order) == 100 and len(names) == 99 and len(ids) == len(set(ids)) == 99
                   and all(type(owner) is int for owner in opt['state']) and set(opt['state']).issubset(ids),
                   'Cannot bind ordered99 parameters to Adam81 owners')
    owners = dict(zip(ids, names, strict=True))
    for owner, row in opt['state'].items():
        parameter = saved['online_state_dict'][owners[owner]]
        for field in ('exp_avg', 'exp_avg_sq'):
            value = row[field]
            common.require(torch.is_tensor(value) and value.shape == parameter.shape and value.dtype == parameter.dtype,
                           'Adam moment paired to wrong online parameter')
    raw_steps = [scalar(row['step'], torch) for row in opt['state'].values()]
    common.require(all(type(value) in (int, float) and math.isfinite(value)
                   and float(value).is_integer() and 0 <= value <= metadata['training_steps'] for value in raw_steps),
                   'Malformed Adam parameter step')
    steps = sorted({float(value) for value in raw_steps})
    common.require(steps == manifest['optimizer_parameter_steps'],
                   'Adam parameter clocks differ')
    common.require(saved['epsilon'] == .1 and abs(saved['expert_ratio'] - .1) < 1e-12
                   and saved['lr_gear'] == 'climb' and type(saved['lr_anchor_step']) in (int, float)
                   and saved['lr_anchor_step'] == 0, 'Saved learning controls changed')
    scaler = saved['grad_scaler_state_dict']
    common.require(isinstance(scaler, dict) and set(scaler) == {'scale','growth_factor','backoff_factor','growth_interval','_growth_tracker'},
                   'Required AMP GradScaler state missing/malformed')
    common.require(all(type(value) in (int, float) and math.isfinite(value) for value in scaler.values())
                   and scaler['scale'] > 0 and scaler['growth_factor'] > 1 and 0 < scaler['backoff_factor'] < 1
                   and type(scaler['growth_interval']) is int and scaler['growth_interval'] > 0
                   and type(scaler['_growth_tracker']) is int and 0 <= scaler['_growth_tracker'] < scaler['growth_interval'],
                   'Invalid AMP GradScaler scalars')
    return dict(metadata=metadata, optimizer_state_count=81, optimizer_parameter_steps=steps,
                optimizer_groups=groups, grad_scaler_state_dict=scaler, geometry=geometry,
                finite_tensor_count=count, all_saved_tensors_finite_CPU=True)

def clock_delta(metadata, prior_manifest, steps):
    old = prior_manifest['saved_metadata']
    keys = {'logical_updates':'training_steps','optimized_samples':'optimized_samples',
            'learner_frames':'learner_frame_count','fleet_frames':'frame_count',
            'last_target_update_samples':'last_target_update_samples'}
    delta = {key: metadata[field] - old[field] for key, field in keys.items()}
    prior_steps = prior_manifest['optimizer_parameter_steps']
    common.require(len(prior_steps) == len(steps) == 1, 'Unexpected nonuniform historical Adam clocks')
    delta['Adam_parameter_steps'] = steps[0] - prior_steps[0]
    delta['logical_minus_Adam_delta'] = delta['logical_updates'] - delta['Adam_parameter_steps']
    common.require(delta['optimized_samples'] == 4096 * delta['logical_updates']
                   and all(value >= 0 for value in delta.values())
                   and metadata['measurement_frame_count'] == old['measurement_frame_count'],
                   'Saved4096 chronology changed or clocks rewound')
    return delta

def execute(args):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(); tick = time.monotonic()
    common.require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'Explicit CUDA_VISIBLE_DEVICES= required')
    contract = common.baseline()
    run, prior, game, _ = common.run_paths(args, contract)
    output = run / 'startup-independent-checkpoint-cpu.json'
    common.require(not output.exists(), 'CPU anchor already audited; refuse repeat payload read')
    source, private = common.check_sources(contract)
    process_before = common.process(args.trainer_pid)
    manifest = common.doc(run / 'final-resume-checkpoint.json', args.resume_manifest_sha256)
    common.require(manifest['cpu_only'] and manifest['optimizer_tensors_finite_CPU']
                   and manifest['cuda_initialized'] is False and manifest['architecture_unchanged'], 'Bad root resume manifest')
    common.require(not Path('/proc', str(manifest['stopped_trainer_pid'])).exists(), 'Prior trainer still live')
    shutdown = manifest['shutdown_console']
    text = common.small_raw(shutdown['path'], shutdown['sha256']).decode(errors='replace')
    common.require(shutdown['clean_shutdown_messages_verified'] and 'Final model & settings saved' in text
                   and 'Shutdown complete' in text and Path(shutdown['path']).parent.resolve() == prior,
                   'Prior final-save/shutdown proof missing')
    anchor, latest = game / manifest['checkpoint'], game / manifest['source']
    common.require(anchor.parent == game / 'models_dqn/managed-checkpoints'
                   and str(latest) == contract['environment']['DQN_EXACT_GRAPH_CHECKPOINT'], 'Unexpected anchor/latest path')
    before, latest_stat = common.identity(anchor), common.identity(latest)
    common.require(before['mode'] == 0o444 and before['nlink'] == 1 and before['bytes'] == latest_stat['bytes']
                   and (before['inode'], before['device']) != (latest_stat['inode'], latest_stat['device']), 'Anchor protection/independence differs')
    # ONE body read: SHA and CPU torch.load consume the same immutable byte snapshot.
    payload = anchor.read_bytes()
    common.require(common.digest(payload) == manifest['sha256'], 'New anchor SHA differs')
    import numpy as np
    import torch
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    common.require(not torch.cuda.is_initialized(), 'CUDA unexpectedly initialized')
    checkpoint = torch.load(io.BytesIO(payload), map_location='cpu', weights_only=True)
    reference = common.doc(contract['pins']['final192_lineage']['path'], contract['pins']['final192_lineage']['sha256'])['candidate']
    facts = validate_checkpoint(checkpoint, manifest, reference, torch)
    banks = {}
    for bank, expected in manifest['banks'].items():
        common.require(bank in ('hof', 'ephof'), 'Unknown bank')
        directory = game / ('models_dqn/robotron_dqn_latest_replay_' + bank)
        selector_path = directory / 'CURRENT.json'
        selector_raw = common.small_raw(selector_path, expected['selector_sha256']); selector = json.loads(selector_raw)
        common.require(selector == expected['selector'] and selector['schema'] == 'robotron-bank-generation-v1'
                       and selector['bank'] == bank and re.fullmatch(r'gen-[0-9a-f]{32}', selector['generation'])
                       and type(selector['mutation_generation']) is int and selector['mutation_generation'] >= 0,
                       'Bank selector/schema/generation changed')
        path = directory / 'generations' / selector['generation'] / (bank + '_meta.npz')
        common.require(str(path) == expected['metadata_path'], 'Bank metadata path differs')
        metadata_raw = common.small_raw(path, expected['metadata_sha256'])
        with np.load(io.BytesIO(metadata_raw), allow_pickle=False) as data:
            stride = int(data['stride'].item()); lengths = data['ep_len']
            common.require(stride == {'hof':1536,'ephof':2048}[bank] and lengths.shape == (192,)
                           and np.issubdtype(lengths.dtype, np.integer) and np.all(lengths >= 0) and np.all(lengths <= stride)
                           and np.isfinite(data['ep_score']).all() and int(data['state_size'].item()) == 11128
                           and int(data['mutation_generation'].item()) == selector['mutation_generation'], 'Bad bank metadata')
            episodes, transitions = int(np.count_nonzero(lengths)), int(lengths.sum())
            common.require(episodes == expected['episodes'] == 192 and transitions == expected['transitions'], 'Bank count differs')
        common.require(selector_path.read_bytes() == selector_raw, 'Bank selector changed during inspection')
        banks[bank] = dict(selector=selector, selector_sha256=expected['selector_sha256'],
                          metadata_sha256=expected['metadata_sha256'], episodes=episodes, transitions=transitions, match=True)
    common.require(set(banks) == {'hof','ephof'}, 'Both banks required')
    ring_info = manifest['replay_metadata']
    common.require(ring_info['path'] == '/dev/shm/robotron_dqn_latest_replay/_meta.npy', 'Unexpected ring metadata path')
    ring = np.load(io.BytesIO(common.small_raw(ring_info['path'], ring_info['sha256'])), allow_pickle=False)
    common.require(ring.shape == (3,) and np.isfinite(ring).all() and ring.tolist() == ring_info['values']
                   and ring[0] == int(ring[0]) and 0 <= ring[0] < 6000000 and ring[1] == ring_info['size'] == 6000000
                   and ring[2] > 0, 'Saved6M ring metadata differs')
    saved_delta = clock_delta(facts['metadata'], common.doc(prior / 'final-resume-checkpoint.json'), facts['optimizer_parameter_steps'])
    common.require(common.identity(anchor) == before and common.identity(latest) == latest_stat
                   and common.process(args.trainer_pid) == process_before and not torch.cuda.is_initialized(),
                   'Anchor/latest/process changed or CUDA initialized')
    report = dict(schema='robotron-collector4096-independent-resume-cpu-v1', PASS=True,
                  started_utc=started, finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  elapsed_s=time.monotonic()-tick, pid=os.getpid(), trainer=process_before,
                  run_dir=str(run), prior_run=str(prior), expected_wait_ms=args.expected_wait,
                  resume_manifest_sha256=args.resume_manifest_sha256, anchor=str(anchor), anchor_sha256=manifest['sha256'],
                  anchor_stat=before, latest_stat_only=latest_stat, model_body_reads=1,
                  CUDA_VISIBLE_DEVICES='', CUDA_initialized=False, torch_threads=torch.get_num_threads(),
                  torch_interop_threads=torch.get_num_interop_threads(), max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  **facts, banks=banks, ring_metadata=ring.tolist(), saved_clock_delta_vs_prior_resume_anchor=saved_delta,
                  source_hashes=source, private12_hashes=private, baseline_contract_sha256=common.BASELINE_SHA,
                  clock_delta_interpretation='Actual saved logical/sample clocks versus per-parameter Adam exposure; no per-event overflow/cause proof. Prior resume anchor is historical, not newly reset/imported experience.',
                  scope='One new final anchor body read/hash/CPU load; no old/latest model body, replay data body, CUDA context, API, controls or source mutation. AMP/scaler presence and source restoration contract are checked, not live heap values. RNG/actor trajectories are not checkpoint-reproduced.')
    result = common.publish(output, report)
    print(json.dumps(dict(PASS=True, path=str(output), sha256=result, anchor_sha256=manifest['sha256'], saved_clock_delta=saved_delta)))

def main():
    args = common.arguments(__doc__)
    if args is not None:
        execute(args)

if __name__ == '__main__':
    main()
