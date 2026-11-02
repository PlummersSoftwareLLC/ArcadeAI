"""Bind a successfully closed original strict CPU job to one full disk backup."""
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--header', type=Path)
    p.add_argument('--header-sha256')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if not a.prepare:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    assert hashlib.sha256(a.header.read_bytes()).hexdigest() == a.header_sha256
    spec = importlib.util.spec_from_file_location('_prepare_stopped_backup', a.header)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    root = a.header.parent.parent
    cpu_root = root / 'stopped-CPU-original01'
    report_pin = h.metadata(cpu_root / 'runtime/cpu-verification.json')[0]
    report = h.read(report_pin)
    assert report['status'] == 'PASS'
    closure_pin = h.metadata(cpu_root / 'execution-original01/root-original-result-and-owned-release.json')[0]
    closure = h.read(closure_pin)
    assert closure['original_exit'] == 0 and closure['lifecycle_complete'] is True and closure['unit_released'] is True
    owner_pin = h.metadata(cpu_root / 'execution-original01/root-original-identity.json')[0]
    owner = h.read(owner_pin)
    v = h.load('verifier')
    original_cpu = h.read(report['original_job'])
    v.select_context(original_cpu)
    manifest = h.read(report['restoration_manifest'])
    selected = h.read(original_cpu['current_selection'])
    stop_job = h.read(h.metadata(root / 'observed-stop-preparation-original01/stop/job.json')[0])
    source_map = {Path(entry['path']).name: entry for entry in h.read(selected['input_closure'])['source_pins']}
    context = original_cpu['source_control_context']
    configuration = dict(learning_control=context['archived_control'], trainer_unit=context['archived_trainer_unit'],
                         game_settings=h.metadata(h.ROOT / 'models_dqn/game_settings.json')[0])
    job = dict(schema='robotron-verified-stopped-full-training-compressed-backup-job-v1',
        source=h.SOURCES['backup'], unit='robotron-current-continuous-compressed-backup3600-' + report_pin['sha256'][:16] + '.service',
        original_attempt=1, no_retry=True, maximum_compressed_bytes=128<<30, restoration_manifest=report['restoration_manifest'],
        strict_CPU_report=report_pin, strict_CPU_owner=owner_pin, strict_CPU_closure=closure_pin,
        original_population=stop_job['original_population'], fleet_terminal_archive=selected['fleet_terminal_archive'],
        current_source_archives=source_map, configuration_archives=configuration,
        destination_root=str(root / 'full-backup-original01'),
        destination_volume=dict(scope='ROOT_SELECTED_SAME_HOST_DISK', device=root.stat().st_dev))
    job['inputs'] = [h.SOURCES['backup'], report_pin, report['restoration_manifest'], owner_pin, closure_pin,
        stop_job['original_population'], selected['fleet_terminal_archive'], *source_map.values(),
        *configuration.values(), h.metadata(Path(__file__).resolve())[0]]
    backup = h.load('backup')
    # These two required runtime sources were not in the input-frontier
    # catalogue. Preserve their actual stopped bytes as additional archives;
    # numerical-package pins and all existing source pins remain exact.
    for name in sorted(set(backup.SOURCE_NAMES) - set(source_map)):
        entry = h.metadata(h.ROOT / 'Scripts/dqn' / name)[0]
        source_map[name] = entry
        job['inputs'].append(entry)
    # Reuse the exact production backup selection and owner proof as preflight.
    backup.FLEET = v.FLEET
    owners = backup.owners_closed(job, v)
    archive = backup.load(backup.ARCHIVE, backup.ARCHIVE_SHA, '_backup_preflight_archive')
    archive.archived_closure(closure, owner, backup.read_pin, exit_zero=True)
    entries = backup.selected_files(manifest, report, job)
    total = sum(e['identity']['bytes'] for e in entries)
    space = os.statvfs(root)
    available = space.f_bavail * space.f_frsize
    assert available >= job['maximum_compressed_bytes'] + (32 << 30)
    assert a.output.is_absolute() and not a.output.exists()
    a.output.mkdir(mode=0o700)
    jp = h.put(a.output / 'job.json', job)
    ctl = h.load('backup_controller')
    config = dict(unit=job['unit'], output=str(a.output / 'execution-original01'),
        argv=['/usr/bin/python3', '-I', '-B', h.SOURCES['backup']['path'], '--execute', '--job', jp['path'],
              '--job-sha256', jp['sha256'], '--source-sha256', h.SOURCES['backup']['sha256']],
        properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=3600',
                    'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'], observation_s=3660,
        pins=[ctl.pin(entry['path']) for entry in [jp, *job['inputs']]])
    cp = h.put(a.output / 'controller-config.json', config)
    ctl.checked_config(cp['path'])
    prepared = h.put(a.output / 'prepared-full-backup-NOT-LAUNCHED.json', dict(
        status='PREPARED_STOPPED_FULL_BACKUP_NOT_LAUNCHED', job=jp, config=cp, original_owners=owners,
        source_file_count=len(entries), planned_bytes=total, available_disk_bytes=available,
        original_CPU_exit=0, original_CPU_resources_closed=True,
        Root_controller_argv=['/usr/bin/python3.12', '-I', '-B', h.SOURCES['backup_controller']['path'],
            '--execute', '--config', cp['path'], '--expected-source-sha256', h.SOURCES['backup_controller']['sha256']],
        actual_backup_completed=False))
    print(json.dumps(dict(prepared={k: prepared[k] for k in ('path', 'sha256', 'bytes')},
                          planned_bytes=total, files=len(entries), unit=job['unit'])))


if __name__ == '__main__':
    main()
