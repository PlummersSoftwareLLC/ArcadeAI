#!/usr/bin/env python3
"""Independently check three archived rehearsal tensors; default is literal PLAN."""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import stat
import sys
import traceback

MAX_JSON = 8 * 1024**2
MAX_PAYLOAD = 640 * 1024**2
INPUT_NAMES = ('states', 'actions', 'rewards', 'next_states', 'dones',
               'horizons', 'is_expert', 'weights')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, mode=stat.S_IMODE(info.st_mode),
                uid=info.st_uid, gid=info.st_gid, nlink=info.st_nlink,
                size=info.st_size, mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)


def open_readonly(path, *, read_only=True):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(),
            'Input path must be canonical and nonsymlink: ' + str(path))
    stream = os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb')
    try:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                and (not read_only or not stat.S_IMODE(info.st_mode) & 0o222),
                'Input is not an owned regular single-link file with the required readonly policy')
        require(identity(path.lstat()) == identity(info), 'Input path/FD differ')
        return stream, identity(info)
    except BaseException:
        stream.close()
        raise


def fingerprint(path, *, read_only=True):
    stream, before = open_readonly(path, read_only=read_only)
    with stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(identity(os.fstat(stream.fileno())) == before == identity(Path(path).lstat()),
                'Input changed while hashing')
    return dict(path=str(path), sha256=digest, bytes=before['size'], identity=before)


def checked_json(record):
    require(record['bytes'] <= MAX_JSON, 'Metadata JSON exceeds fixed 8MiB limit')
    # Parent JSON outputs retain their original writable mode.  Their complete
    # pinned identity/hash is checked; only the three tensor inputs require444.
    observed = fingerprint(record['path'], read_only=False)
    require(observed == record, 'Pinned JSON changed: ' + record['path'])
    value = json.loads(Path(record['path']).read_text())
    require(fingerprint(record['path'], read_only=False) == observed, 'JSON changed during parse')
    return value


def write_json(path, value):
    with path.open('xb') as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def tensor_digest(torch, value):
    """Independent implementation of frozen helper's exact tree encoding."""
    digest = hashlib.sha256()
    def walk(item):
        if isinstance(item, torch.Tensor):
            require(item.device.type == 'cpu' and item.layout == torch.strided, 'Non-CPU/strided tensor')
            digest.update(str((str(item.dtype), list(item.shape))).encode())
            array = item.detach().contiguous().reshape(-1).view(torch.uint8).numpy()
            raw = memoryview(array).cast('B')
            for offset in range(0, len(raw), 1024**2):
                digest.update(raw[offset:offset + 1024**2])
        elif isinstance(item, Mapping):
            for key in sorted(item, key=lambda key: (type(key).__name__, str(key))):
                digest.update(repr(key).encode())
                walk(item[key])
        elif isinstance(item, (tuple, list)):
            digest.update(type(item).__name__.encode())
            for part in item:
                walk(part)
        else:
            require(item is None or type(item) in (str, int, float, bool), 'Unsupported tree scalar')
            digest.update(repr(item).encode())
    walk(value)
    return digest.hexdigest()


def finite_tree(torch, value, counts):
    if isinstance(value, torch.Tensor):
        require(value.device.type == 'cpu' and value.layout == torch.strided, 'Non-CPU/strided payload')
        require(bool(torch.isfinite(value).all()), 'Nonfinite retained tensor')
        counts['tensors'] += 1
        counts['elements'] += value.numel()
        counts['tensor_bytes'] += value.numel() * value.element_size()
    elif isinstance(value, Mapping):
        for key, item in value.items():
            require(type(key) in (str, int), 'Unsupported mapping key')
            finite_tree(torch, item, counts)
    elif isinstance(value, (tuple, list)):
        for item in value:
            finite_tree(torch, item, counts)
    else:
        require(value is None or type(value) in (str, int, float, bool), 'Unsupported retained scalar')
        require(type(value) is not float or math.isfinite(value), 'Nonfinite retained scalar')


def exact_tree(torch, actual, expected):
    if isinstance(actual, torch.Tensor) or isinstance(expected, torch.Tensor):
        return (isinstance(actual, torch.Tensor) and isinstance(expected, torch.Tensor)
                and actual.shape == expected.shape and actual.dtype == expected.dtype
                and torch.equal(actual, expected))
    if isinstance(actual, Mapping) or isinstance(expected, Mapping):
        return (isinstance(actual, Mapping) and isinstance(expected, Mapping)
                and set(actual) == set(expected)
                and all(exact_tree(torch, actual[key], expected[key]) for key in actual))
    if isinstance(actual, (list, tuple)) or isinstance(expected, (list, tuple)):
        return (type(actual) is type(expected) and len(actual) == len(expected)
                and all(exact_tree(torch, a, b) for a, b in zip(actual, expected)))
    return type(actual) is type(expected) and actual == expected


def load_payload(torch, record):
    require(0 < record['bytes'] <= MAX_PAYLOAD, 'Payload outside fixed 640MiB maximum')
    before = fingerprint(record['path'])
    require(before == record, 'Payload identity/hash/size differs before load')
    stream, info = open_readonly(record['path'])
    with stream:
        require(info == before['identity'], 'Payload descriptor identity differs')
        value = torch.load(stream, map_location='cpu', weights_only=True)
        require(identity(os.fstat(stream.fileno())) == info, 'Payload changed during CPU load')
    require(fingerprint(record['path']) == before, 'Payload changed after CPU load')
    return value, before


def check_values(torch, payload, conditional, saved_mask, meta):
    cap, rec, row = meta['capture'], meta['recompute'], meta['row']
    counts = {}
    for name, value in (('capture', payload), ('conditional', conditional), ('mask', saved_mask)):
        counts[name] = dict(tensors=0, elements=0, tensor_bytes=0)
        finite_tree(torch, value, counts[name])
    require(payload['attempt'] == 1 and payload['nonfinite_copies'] == 0
            and payload['capture_id'] == row['draw_capture_id'] == payload['draw']['capture_id'],
            'Capture ID/attempt or finite-copy status differs')
    require(payload['tensor_bytes'] == counts['capture']['tensor_bytes'], 'Stored raw tensor byte accounting differs')
    require(payload['draw']['schema'] == 'robotron-replay-draw-observation-v1', 'Draw metadata schema differs')
    steps = cap['before']['steps']
    require(len(steps) == 99 and sum(v == 1655313 for v in steps.values()) == 81
            and sum(v == 0 for v in steps.values()) == 18, 'Expected 81 initialized Adam clocks and18 default-zero observations')
    require(set(payload['online']) == set(payload['target']) == set(steps) | {'support'},
            'PRE model keys do not cover99 named parameters plus support')
    for name, tensor in payload['online'].items():
        other = payload['target'][name]
        require(tensor.dtype == other.dtype == torch.float32 and tensor.shape == other.shape,
                'PRE online/target parameter geometry or original FP32 dtype differs')
    require(payload['online']['support'].shape == (51,), 'Support geometry differs')
    online_hash = tensor_digest(torch, payload['online'])
    target_hash = tensor_digest(torch, payload['target'])
    require(online_hash == cap['before']['online'] == rec['before']['online']
            and target_hash == rec['before']['target'], 'Captured PRE model fingerprint differs')
    inputs = payload['inputs']
    require(set(inputs) == set(INPUT_NAMES), 'Actual eight input names differ')
    dtypes = (torch.float32, torch.long, torch.float32, torch.float32,
              torch.float32, torch.float32, torch.bool, torch.float32)
    for name, dtype in zip(INPUT_NAMES, dtypes):
        expected_shape = (4096, 11128) if name in ('states', 'next_states') else (4096,)
        require(inputs[name].dtype == dtype and inputs[name].shape == expected_shape,
                'Actual input geometry/dtype differs: ' + name)
    ranges = {name: dict(minimum=float(value.min()), maximum=float(value.max()))
              for name, value in inputs.items()}
    require(all(0 <= ranges[name]['minimum'] <= ranges[name]['maximum'] <= 1
                for name in ('states', 'next_states', 'dones', 'is_expert'))
            and 0 <= ranges['actions']['minimum'] <= ranges['actions']['maximum'] < 81
            and 1 <= ranges['horizons']['minimum'] <= ranges['horizons']['maximum'] <= 3
            and ranges['weights']['minimum'] > 0, 'Private fixture input range differs')
    require(payload['schedule'].dtype == torch.float32 and payload['schedule'].shape == (3,),
            'Actual schedule geometry differs')
    draw = payload['draw']
    require(draw['supplied_weights_float32'].dtype == torch.float32
            and torch.equal(inputs['weights'], draw['supplied_weights_float32']), 'Actual weights differ from draw')
    for name in ('actions', 'rewards', 'dones', 'horizons', 'is_expert'):
        require(torch.equal(inputs[name], draw['small_batch_fields'][name].to(dtype=inputs[name].dtype)),
                'Actual small field differs from draw: ' + name)
    for name in ('index', 'draw_capture_id', 'optimizer_outcome', 'actual_exposure_delta',
                 'optimizer_observation', 'before', 'at_loss', 'after'):
        require(payload['outcome'][name] == row[name], 'Embedded actual outcome differs: ' + name)
    pre = payload['pre_context']
    require(pre['loss_sha256'] == meta['lock']['original_loss_sha256'] and pre['use_amp'] is True
            and pre['learner_device'] == pre['schedule_device'] == 'cuda:0'
            and pre['input_devices'] == ['cuda:0'] * 8 and pre['modes'] == {'online': True, 'target': False},
            'Actual original-loss/device/autocast/mode context differs')
    actual = payload['actual']
    require(set(actual) == {'ce', 'weighted_loss', 'bc_loss', 'diagnostic_values'}, 'Original four-output names differ')
    require(actual['ce'].shape == (4096,) and actual['ce'].dtype == torch.float32
            and actual['weighted_loss'].shape == actual['bc_loss'].shape == ()
            and actual['diagnostic_values'].shape == (12,), 'Original four-output geometry differs')
    require(conditional['scope'] == 'CONDITIONAL RECOMPUTED; never actual executed target', 'Conditional scope differs')
    outputs = conditional['raw_outputs']
    require(isinstance(outputs, tuple) and len(outputs) == 5 and isinstance(outputs[4], tuple)
            and len(outputs[4]) == 10, 'Retained conditional five-output ABI differs')
    require(exact_tree(torch, conditional['expected_actual_capture'], actual), 'Copied expected original outputs differ')
    require(conditional['source_capture_payload'] == cap['payload']
            and conditional['source_capture_row'] == cap['row'], 'Conditional source capture binding differs')
    actual_ce, expected_ce = outputs[1], actual['ce']
    require(actual_ce.shape == expected_ce.shape == (4096,) and actual_ce.dtype == expected_ce.dtype,
            'Actual/recomputed CE structure differs')
    tolerance = meta['lock']['tolerances']['ce']
    require(tolerance == {'atol': 2e-5, 'rtol': 2e-4}, 'Original CE tolerances differ')
    bad = ~torch.isclose(actual_ce, expected_ce, **tolerance, equal_nan=False)
    difference = (actual_ce.double() - expected_ce.double()).abs()
    require(set(saved_mask) == {'ce'} and saved_mask['ce'].dtype == torch.bool
            and saved_mask['ce'].shape == (4096,) and torch.equal(saved_mask['ce'], bad), 'Saved mask differs from native predicate')
    comparison = rec['ce_comparison']
    recomputed = dict(violations=int(bad.sum()), max_abs=float(difference.max()),
                      actual_sha256=tensor_digest(torch, actual_ce), expected_sha256=tensor_digest(torch, expected_ce))
    require(all(recomputed[key] == comparison[key] for key in recomputed), 'Independent native CE statistics/fingerprints differ')
    require(recomputed['violations'] == 0 and comparison['passed'] and comparison['coordinate_examples'] == []
            and not bool(bad.any()), 'Original-tolerance CE mismatch; no qualification or rescue')
    rng = dict(capture=tensor_digest(torch, payload['rng']),
               conditional_pre=tensor_digest(torch, conditional['rng_before']),
               conditional_post=tensor_digest(torch, conditional['rng_after']))
    require(rng['capture'] == rng['conditional_pre'] == rng['conditional_post']
            == rec['rng_observations']['pre'] == rec['rng_observations']['post']
            and exact_tree(torch, payload['rng'], conditional['rng_before'])
            and exact_tree(torch, conditional['rng_before'], conditional['rng_after']), 'Retained RNG evidence differs')
    return dict(finite_tree_counts=counts, CE=recomputed, original_tolerance=tolerance,
                saved_mask_exact=True, RNG=rng, PRE_online_sha256=online_hash,
                PRE_target_sha256=target_hash, named_parameter_clock_observations=99,
                initialized_Adam_clocks_from_JSON=81, default_zero_uninitialized_observations_from_JSON=18,
                input_ranges=ranges, inputs_sha256=tensor_digest(torch, inputs),
                schedule_sha256=tensor_digest(torch, payload['schedule']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--pins', type=Path)
    parser.add_argument('--pins-sha256')
    parser.add_argument('--source-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY_UNEXECUTED: three archived CPU weights-only loads; no input reads or framework import')
        return 0
    require(args.pins is not None and args.output is not None, 'Explicit pins and NEW output required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and 'LD_PRELOAD' not in os.environ
            and 'PYTHONPATH' not in os.environ, 'CUDA-hidden and import/preload-free environment required')
    require(not any(name.split('.')[0] in ('torch', 'numpy', 'dqn') for name in sys.modules), 'Fresh stdlib-only process required')
    self_record = fingerprint(Path(__file__).resolve())
    require(self_record['sha256'] == args.source_sha256, 'Explicit verifier source pin differs')
    pins_record = fingerprint(args.pins)
    require(pins_record['sha256'] == args.pins_sha256 and pins_record['bytes'] <= MAX_JSON, 'Explicit pins changed')
    pins = json.loads(args.pins.read_text())
    require(pins['schema'] == 'robotron-one-recomputed-CE-independent-CPU-inputs-v1'
            and pins['verifier_sha256'] == args.source_sha256, 'Wrong job/source schema')
    require(args.output.is_absolute() and args.output == args.output.resolve()
            and str(args.output) == pins['output'] and not args.output.exists()
            and args.output.parent.is_dir(), 'Output must be the precommitted NEW canonical path')
    args.output.mkdir(mode=0o700)
    report = dict(status='RUNNING', schema=pins['schema'], source=self_record, pins=pins_record,
                  original_tolerance_qualification=False, production_applied=False)
    try:
        meta = {name: checked_json(record) for name, record in pins['JSON'].items()}
        for record in pins['sources']:
            observed = fingerprint(record['path'], read_only=False)
            require(observed == record, 'Bound source changed')
        require(meta['aggregate']['variants'] == [meta['capture'], meta['recompute']]
                and meta['aggregate']['status'] == 'OBSERVATIONS_COMPLETE'
                and meta['capture']['consumed_attempts'] == 1 and meta['capture']['optimizer_outcome'] == 'amp_skipped'
                and meta['recompute']['before'] == meta['recompute']['after'], 'Saved role/result controls differ')
        require(pins['payloads'] == {'capture': meta['capture']['payload'],
                'conditional': meta['recompute']['retained_conditional_payload'], 'mask': meta['recompute']['ce_mismatch_mask']},
                'Three exact payload descriptors differ')
        capture_dir = Path(pins['payloads']['capture']['path']).parent
        recompute_dir = Path(pins['payloads']['conditional']['path']).parent
        require(sorted(str(p) for p in capture_dir.glob('*.pt')) == [pins['payloads']['capture']['path']]
                and sorted(str(p) for p in recompute_dir.glob('*.pt')) == sorted(pins['payloads'][n]['path'] for n in ('conditional', 'mask'))
                and not (capture_dir / 'final.json').exists(), 'Unexpected scientific payload inventory')
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024**2, 32 * 1024**2))
        import torch
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        require(not torch.cuda.is_initialized(), 'Unexpected CUDA initialization')
        loaded, observations = {}, {}
        for name in ('capture', 'conditional', 'mask'):
            loaded[name], observations[name] = load_payload(torch, pins['payloads'][name])
        report['numerical'] = check_values(torch, loaded['capture'], loaded['conditional'], loaded['mask'], meta)
        require(not torch.cuda.is_initialized(), 'CPU verification initialized CUDA')
        for record in pins['JSON'].values():
            checked_json(record)
        for name, record in pins['payloads'].items():
            require(fingerprint(record['path']) == observations[name], 'Payload changed after interpretation')
        for record in pins['sources']:
            after = fingerprint(record['path'], read_only=False)
            require(after == record, 'Source changed after interpretation')
        require(fingerprint(args.pins) == pins_record and fingerprint(Path(__file__).resolve()) == self_record, 'Verifier/pins changed')
        report.update(status='PASS_INDEPENDENT_RETAINED_CE_VALUES', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      payload_hashes_before_after=observations, torch_version=torch.__version__, CPU_threads=torch.get_num_threads(),
                      CUDA_initialized=False, qualification_pass=False,
                      limitations=['Only archived rehearsal data were loaded; no checkpoint/model construction/training/backward/RNG restore.',
                          'Capture outcome is an AMP skip, not an applied optimizer update.99 clock observations contain81 initialized states and18 default zeros.',
                          'PRE model/input finite and CE/mask/RNG fingerprints independently checked; POST optimizer tensors were not archived or loaded.',
                          'Only4096 conditional per-row CE compared.Offline target/entropy/KL are conditional; actual executed target/entropy/rank remain unobserved.',
                          'No live-eight, full-agent lifecycle, coherent snapshot/restore, throughput or learning-quality qualification.'])
        write_json(args.output / 'CPU-tensor-review.json', report)
        print(json.dumps(dict(status=report['status'], output=str(args.output / 'CPU-tensor-review.json'),
                             violations=report['numerical']['CE']['violations'], qualification_pass=False)))
        return 0
    except BaseException as error:
        report.update(status='FAIL', error=repr(error), traceback=traceback.format_exc(), qualification_pass=False)
        try:
            write_json(args.output / 'failure.json', report)
        except BaseException as secondary:
            print('Failure report could not persist: ' + repr(secondary), file=sys.stderr)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
