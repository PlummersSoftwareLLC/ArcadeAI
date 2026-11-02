"""Install the prepared fresh startup override after the original backup closes.

Default inert. Installation and daemon-reload only; does not start the trainer.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--header', type=Path)
    parser.add_argument('--header-sha256')
    a = parser.parse_args()
    if not a.install:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    assert hashlib.sha256(a.header.read_bytes()).hexdigest() == a.header_sha256
    spec = importlib.util.spec_from_file_location('_verified_override_header', a.header)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    root = a.header.parent.parent
    pin = lambda path: h.metadata(path)[0]
    read = lambda path: h.read(pin(path))
    job = read(root / 'post-backup-startup-metadata-original01/startup-job.json')
    backup = read(root / 'full-backup-original01/backup-manifest.json')
    assert backup['status'] == 'COMPLETE_STREAM_HASHED_AND_FSYNCED'
    assert backup['restoration_manifest'] == job['restoration_manifest']
    assert backup['strict_CPU_report'] == job['stopped_CPU_report']
    b = h.load('backup')
    archive = b.load(b.ARCHIVE, b.ARCHIVE_SHA, '_startup_override_closure')
    for stem in ('stopped-CPU-original01', 'backup-preparation-original02'):
        closure = read(root / stem / 'execution-original01/root-original-result-and-owned-release.json')
        owner = read(root / stem / 'execution-original01/root-original-identity.json')
        assert closure['original_exit'] == 0 and closure['lifecycle_complete'] and closure['unit_released']
        archive.archived_closure(closure, owner, b.read_pin, exit_zero=True)
        b.absent(owner['pid'], owner['starttime_ticks'])
        assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', owner['unit']).exists()
    assert not Path(job['output_directory']).exists(), 'Fresh startup output required'
    for unit in ('robotron-trainer.service', 'robotron-mame.service'):
        assert subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', 'MainPID', '--value'], text=True).strip() == '0'
    source = root / 'post-backup-startup-metadata-original01/99-post-engineering-preservation.conf.REVIEW-NOT-INSTALLED'
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'ac23fc4b062bbc63766ca407ef93d2fec4bf4c0c7aac8bb8fa022be195a34843'
    target = Path('/home/dave/.config/systemd/user/robotron-trainer.service.d/99-post-engineering-preservation.conf')
    assert target.parent.resolve(strict=True) == target.parent and not target.exists()
    assert target.parent.stat().st_uid == os.getuid()
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(target.parent, os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, timeout=30)
    output = subprocess.check_output(['systemctl', '--user', 'show', 'robotron-trainer.service',
        '-p', 'Environment', '-p', 'Type', '-p', 'Restart', '-p', 'ExecStart', '-p', 'MainPID'], text=True)
    values = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
    env = dict(row.split('=', 1) for row in shlex.split(values['Environment']))
    job_pin = pin(root / 'post-backup-startup-metadata-original01/startup-job.json')
    assert values['MainPID'] == '0' and values['Type'] == 'exec' and values['Restart'] == 'no'
    assert env['ROBOTRON_CONTINUOUS_STARTUP_JOB'] == job_pin['path']
    assert env['ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256'] == job_pin['sha256']
    assert env['DQN_MAX_SAMPLES_PER_FRAME'] == '8'
    assert env['DQN_PRIORITY_PHASE_RECORD'] == job['resume_record']['path']
    assert env['DQN_PRIORITY_PHASE_RECORD_SHA256'] == job['resume_record']['sha256']
    assert env['ROBOTRON_RUN_DIR'] == str(root / 'post-backup-Main-runtime-original01')
    assert '--records ' + str(root / 'post-backup-startup-metadata-original01') in values['ExecStart']
    receipt = h.put(root / 'post-backup-startup-metadata-original01/actual-startup-override-installed.json', dict(
        status='FRESH_STARTUP_OVERRIDE_INSTALLED_NOT_STARTED', observed_unix_s=time.time(),
        source=pin(source), installed=pin(target), effective_unit=values,
        original_backup_passed_and_closed=True, service_started=False))
    print(json.dumps({k: receipt[k] for k in ('path', 'sha256', 'bytes')}))


if __name__ == '__main__':
    main()
