#!/usr/bin/env python3
"""Request a managed checkpoint at a learner-frame threshold, cancelling on a branch change."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    with urllib.request.urlopen('http://localhost:8771/api/now', timeout=10) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=int, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=21600)
    args = parser.parse_args()
    if args.target < 1 or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.tag) or args.timeout <= 0:
        parser.error('positive target/timeout and a simple checkpoint tag are required')
    control = ROOT/'models_dqn/learning_control.json'
    request = ROOT/'models_dqn/managed_save.request.json'
    saved = ROOT/f'models_dqn/managed-checkpoints/{args.tag}.pt'
    if saved.exists() or args.output.exists():
        parser.error('checkpoint or gate report already exists')
    deadline = time.monotonic()+args.timeout
    triggered = None
    print(f'Waiting for learner frame {args.target}: {args.tag}', flush=True)
    while time.monotonic() < deadline:
        if json.loads(control.read_text()).get('experiment') != args.experiment:
            raise SystemExit('Experiment changed; gate cancelled')
        if triggered is not None:
            if saved.exists():
                report = dict(tag=args.tag, target=args.target, experiment=args.experiment,
                              checkpoint=str(saved), trigger_snapshot=triggered,
                              saved_utc=datetime.now(timezone.utc).isoformat())
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open('x') as stream:
                    json.dump(report, stream, indent=2)
                print(f'Saved {saved}', flush=True)
                return
        else:
            try:
                value = snapshot()
            except (OSError, ValueError) as exc:
                print(f'Snapshot unavailable: {exc}', flush=True)
                time.sleep(5)
                continue
            if value.get('learner_frame_count', 0) >= args.target and not value.get('measurement_active'):
                if saved.exists():
                    raise SystemExit('Checkpoint appeared before request; refusing overwrite')
                fd, temporary = tempfile.mkstemp(prefix='.gate-', dir=request.parent)
                try:
                    with os.fdopen(fd, 'w') as stream:
                        json.dump(dict(tag=args.tag), stream)
                        stream.flush()
                        os.fsync(stream.fileno())
                    try:
                        os.link(temporary, request)  # never replace another pending save
                    except FileExistsError:
                        time.sleep(1)
                        continue
                finally:
                    Path(temporary).unlink(missing_ok=True)
                triggered = {key: value.get(key) for key in
                             ('learner_frame_count', 'frame_count', 'training_steps',
                              'optimized_samples', 'client_count')}
                print(f'Requested {args.tag}: {triggered}', flush=True)
        time.sleep(1)
    raise SystemExit('Checkpoint gate timed out')


if __name__ == '__main__':
    main()
