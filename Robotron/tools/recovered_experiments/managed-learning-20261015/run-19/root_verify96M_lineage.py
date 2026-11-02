"""Root's independent CPU verification and exclusive lineage publication."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(path):
    s = path.stat()
    return dict(size=s.st_size, mtime_ns=s.st_mtime_ns, inode=s.st_ino,
                device=s.st_dev, mode=oct(s.st_mode & 0o777), nlink=s.st_nlink)


def tensors(value):
    if torch.is_tensor(value):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from tensors(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from tensors(item)


if __name__ == '__main__':
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    begin = time.monotonic()
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    root = Path(__file__).resolve().parent
    proposal = root / 'proposed-fresh3-96M-checkpoint-lineage.json'
    assert sha(proposal) == 'b41857a7dc3754067e909dcc256c9d1018500402bf71ee63bf9008162d2280af'
    report = json.loads(proposal.read_text())
    assert report['PASS'] is True and all(v is True for v in report['checks'].values())
    candidate = report['candidate']
    path = Path(candidate['path'])
    before = identity(path)
    assert before == candidate['stat']
    assert sha(path) == candidate['sha256'] == '15584a029e0db15279586e310afbe2c2af8af14953e27597413d52dfad20ba6d'
    saved = torch.load(path, map_location='cpu', weights_only=False)
    assert all(saved[k] == v for k, v in candidate['saved_metadata'].items())
    for key, expected in candidate['state_dict_signatures'].items():
        actual = {name: dict(shape=list(t.shape), dtype=str(t.dtype))
                  for name, t in saved[key].items()}
        assert actual == expected
    old = json.loads((root.parent / 'run-14/fresh3-64M-checkpoint-lineage.json').read_text())
    assert candidate['state_dict_signatures'] == old['candidate']['state_dict_signatures']
    opt = saved['optimizer_state_dict']
    assert len(opt['state']) == candidate['optimizer']['state_count'] == 81
    steps = sorted({float(s['step'].item()) if torch.is_tensor(s['step']) else float(s['step'])
                    for s in opt['state'].values()})
    assert steps == candidate['optimizer']['step_values'] == [784351.0]
    assert min(steps) >= max(old['candidate']['optimizer']['step_values'])
    for actual, expected in zip(opt['param_groups'], candidate['optimizer']['groups'], strict=True):
        assert len(actual['params']) == expected['parameter_count']
        for key, value in expected.items():
            if key == 'parameter_count':
                continue
            got = actual[key]
            if isinstance(got, tuple):
                got = list(got)
            assert got == value
    all_tensors = list(tensors(saved))
    assert all(t.device.type == 'cpu' for t in all_tensors)
    assert all(not t.is_floating_point() or bool(torch.isfinite(t).all()) for t in all_tensors)
    assert not torch.cuda.is_initialized()
    gate = report['trigger_gate']
    assert sha(gate['path']) == gate['sha256']
    assert json.loads(Path(gate['path']).read_text()) == gate['record']
    assert gate['record']['target'] == 100629023
    assert Path(gate['record']['checkpoint']).resolve() == path.resolve()
    meta = candidate['saved_metadata']
    assert meta['learner_frame_count'] >= gate['record']['target']
    assert meta['training_steps'] == meta['total_training_steps']
    assert meta['baseline_batch_size'] == 512
    for key in ('training_steps', 'optimized_samples', 'learner_frame_count'):
        assert meta[key] > old['candidate']['saved_metadata'][key]
    exposures = report['actual_recorded_batch_exposure']
    for row in exposures['since64M']:
        assert row['optimized_samples_delta'] == row['logical_updates_delta'] * row['recorded_batch_size']
    for batch, total in exposures['totals'].items():
        rows = [r for r in exposures['since64M'] if r['recorded_batch_size'] == int(batch)]
        assert total['logical_updates'] == sum(r['logical_updates_delta'] for r in rows)
        assert total['optimized_samples'] == sum(r['optimized_samples_delta'] for r in rows)
    assert sha(path) == candidate['sha256'] and identity(path) == before
    report['proposal_only'] = False
    report['root_verification'] = dict(
        status='PASS', started_utc=started,
        finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        elapsed_s=time.monotonic() - begin,
        method='Independent root CPU load, SHA before/after, stat, saved metadata, network geometry, finite CPU tensors, Adam81/groups/steps, gate and exposure arithmetic.',
        CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],
        CUDA_initialized=torch.cuda.is_initialized(), torch_threads=torch.get_num_threads(),
        proposal_sha256=sha(proposal), verifier_sha256=sha(__file__))
    report['checks']['root_independent_CPU_verification'] = True
    final = root / 'fresh3-96M-checkpoint-lineage.json'
    with final.open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write('\n')
    final.chmod(0o444)
    print(json.dumps(dict(PASS=True, path=str(final), sha256=sha(final),
                         checkpoint_sha256=candidate['sha256'], root_verification=report['root_verification'])))
