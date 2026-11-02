"""Read current systemd-owned Robotron identities and two advancing API samples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request


def identity(pid):
    root = Path('/proc') / str(pid)
    stat = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, birth_ticks=int(stat[19]), state=stat[0],
                cgroup=(root / 'cgroup').read_text(),
                command=(root / 'cmdline').read_bytes().replace(b'\0', b' ').decode())


def unit(name):
    values = subprocess.check_output(['systemctl', '--user', 'show', name,
        '-p', 'MainPID', '-p', 'ActiveState', '-p', 'NRestarts'], text=True)
    fields = dict(line.split('=', 1) for line in values.splitlines())
    assert fields['ActiveState'] == 'active' and int(fields['MainPID']) > 0
    return dict(name=name, properties=fields, process=identity(int(fields['MainPID'])))


def sample():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        raw = json.load(response)
    keys = ['ts', 'training_steps', 'learner_frame_count', 'optimized_samples',
            'frame_count', 'fps', 'client_count', 'training_enabled', 'training_round',
            'lr', 'epsilon', 'expert_ratio', 'measurement_active']
    return {key: raw.get(key) for key in keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--interval', type=float, default=20)
    args = parser.parse_args()
    assert 5 <= args.interval <= 45
    trainer = unit('robotron-trainer.service')
    fleet = unit('robotron-mame.service')
    pid = fleet['process']['pid']
    children = [identity(int(value)) for value in
        Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
    first = sample()
    assert first['training_enabled'] and first['client_count'] == 192
    assert len(children) == 192
    time.sleep(args.interval)
    second = sample()
    for original in [trainer, fleet]:
        current = unit(original['name'])['process']
        for key in ['pid', 'birth_ticks', 'cgroup', 'command']:
            assert current[key] == original['process'][key]
    for key in ['training_steps', 'learner_frame_count', 'optimized_samples', 'frame_count']:
        assert second[key] > first[key], key
    assert second['training_enabled'] and second['client_count'] == 192
    root = Path(__file__).resolve().parents[2]
    sources = ['Scripts/dqn/game_journal.py', 'Scripts/dqn/socket_server.py',
               'Scripts/dqn/metrics_dashboard.py', 'Scripts/main.lua',
               'tools/power_recovery/round_fleet.py']
    report = dict(schema='robotron-recovered-round-runtime-observation-v1',
        trainer=trainer, fleet=fleet, children=children, samples=[first, second],
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        sources={str(root / p): hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources},
        created_unix_s=time.time(), quality_qualified=False,
        useful_training_throughput_qualified=False)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(trainer_pid=trainer['process']['pid'], fleet_pid=pid,
        clients=second['client_count'], steps_advanced=second['training_steps']-first['training_steps'],
        fps=second['fps'], output=str(args.output))))


if __name__ == '__main__':
    main()
