"""Read one stable published autosave header; copy no model or replay data."""
import argparse
import importlib.util
import json
import os
import stat
import sys
import time
import traceback
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def birth(pid):
    return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])


def identity(value):
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                uid=value.st_uid, nlink=value.st_nlink)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no input reads or model loading')
        return 0
    h = load('_savedClockProbeH', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    jp = h.pin(args.job)
    assert jp['sha256'] == args.job_sha256
    job = json.loads(h.checked(jp).read_text())
    assert job['runtime'] == h.pin(Path(__file__).resolve())
    assert job['schema'] == 'robotron-readonly-stable-saved-header-probe-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not os.environ.get('LD_PRELOAD')
    code = 1
    try:
        owner = job['main_owner']
        assert birth(owner['pid']) == owner['birth']
        state = json.loads((G / 'logs/managed-learning-20261015/state.json').read_text())
        assert state['active_quality_job']['directory'] == job['campaign_directory']
        outer = json.loads((Path(job['campaign_directory']) / 'original-sequence-owner.json').read_text())
        assert birth(outer['pid']) == outer['birth']
        h.checked(job['active_fixed_pair'])
        source = Path(job['source_checkpoint'])
        assert source == G / 'models_dqn/robotron_dqn_latest.pt'
        before = source.stat()
        assert stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid() and before.st_nlink == 1
        import torch
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        saved = torch.load(source, map_location='cpu', mmap=True, weights_only=False)
        clocks = {key: saved[key] for key in ['training_steps', 'learner_frame_count', 'optimized_samples', 'frame_count']}
        assert all(type(value) is int and value >= 0 for value in clocks.values())
        after = source.stat()
        stable = identity(before) == identity(after)
        meets = stable and clocks['learner_frame_count'] >= job['minimum_saved_learner_frames']
        assert birth(owner['pid']) == owner['birth'] and birth(outer['pid']) == outer['birth']
        assert not torch.cuda.is_initialized()
        report = dict(status='STABLE_PUBLISHED_SAVED_HEADER' if stable else 'PUBLISHED_GENERATION_CHANGED_DURING_PROBE',
                      saved_clocks=clocks, source_before=identity(before), source_after=identity(after),
                      stable_generation=stable, saved_milestone_met=meets, CUDA_initialized=False,
                      checkpoint_or_replay_copied=False, model_or_inference_or_replay_constructed=False,
                      scope='Trusted local torch checkpoint loaded read-only with CPU mmap; scalar saved clocks only. No tensor finiteness/inference or quality qualification. Acquisition still performs its own final stable-header and full payload checks.')
        del saved
        code = 0
    except Exception:
        report = dict(status='FAILED_ORIGINAL_SAVED_HEADER_PROBE', error=traceback.format_exc(),
                      saved_milestone_met=False, checkpoint_or_replay_copied=False)
    report.update(original_job=jp, runtime=job['runtime'], observed_unix_s=time.time(),
                  minimum_saved_learner_frames=job['minimum_saved_learner_frames'],
                  quality_qualified=False, promotion=False)
    result = h.put(Path(job['report']), report)
    print(json.dumps(dict(status=report['status'], saved_milestone_met=report['saved_milestone_met'],
                          result={key: result[key] for key in ['path', 'sha256', 'bytes']})), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
