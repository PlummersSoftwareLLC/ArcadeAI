"""Verify the actual new held/released trainer and prepare its fresh fleet job.

Default inert. No services are started and no learning controls are changed.
Requires the original full backup to have passed and released its resources.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time
from types import SimpleNamespace
import urllib.request


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--header', type=Path)
    parser.add_argument('--header-sha256')
    parser.add_argument('--output', type=Path)
    a = parser.parse_args()
    if not a.prepare:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    assert hashlib.sha256(a.header.read_bytes()).hexdigest() == a.header_sha256
    h = load('_restored_fleet_header', a.header)
    root = a.header.parent.parent
    packet = h.read(h.metadata(root / 'prepared-current-source-family.json')[0])
    pin = lambda path: h.metadata(path)[0]
    read = lambda path: h.read(pin(path))
    job_pin = pin(root / 'post-backup-startup-metadata-original01/startup-job.json')
    job = h.read(job_pin)
    held_pin = pin(root / 'post-backup-startup-held-original01/verified-held-before-first-update.json')
    release_pin = pin(root / 'post-backup-startup-held-original01/ROOT-release.json')
    consumed_pin = pin(root / 'post-backup-startup-held-original01/release-consumed.json')
    held, release, consumed = map(h.read, (held_pin, release_pin, consumed_pin))
    assert held['original_job'] == job_pin and held['checkpoint'] == job['checkpoint']
    assert release['original_job'] == consumed['original_job'] == job_pin
    assert release['held_report'] == consumed['held_report'] == held_pin
    assert consumed['Root_release'] == release_pin
    assert held['owner'] == release['owner'] == consumed['owner']
    assert held['restoration_manifest'] == job['restoration_manifest']
    assert held['status'] == 'VERIFIED_HELD_BEFORE_FIRST_UPDATE'
    assert held['all_online_target_Adam_scaler_payloads_equal'] is True
    assert held['optimizer_implementation_flags_exactly_equal'] is True
    assert held['optimizer_attempts_before_release'] == held['new_replay_inserts_before_release'] == 0
    assert consumed['no_optimizer_or_replay_work_before_release'] is True
    replay = held['replay']
    assert all(replay[k] is True for k in ('full_original_mmap_adoption',
        'all_eight_scalar_replay_payloads_equal', 'all_PER_leaf_priorities_equal'))
    assert set(replay['banks']) == {'hof', 'ephof'}
    assert all(v['all_valid_field_payloads_and_episode_metadata_equal'] is True for v in replay['banks'].values())
    operator = load('_restored_fleet_startup_operator', packet['startup_operator']['path'])
    assert h.metadata(packet['startup_operator']['path'])[0] == packet['startup_operator']
    actual_owner = operator.actual_owner(held['owner'], job_pin, 8)
    for entry in job['source_pins']:
        assert pin(entry['path']) == entry

    backup_pin = pin(root / 'full-backup-original01/backup-manifest.json')
    backup = h.read(backup_pin)
    assert backup['status'] == 'COMPLETE_COMPRESSED_DECOMPRESSED_READBACK_HASHED_AND_FSYNCED'
    assert backup['destination_payload_reread_hash_performed'] is True
    assert backup['restoration_manifest'] == job['restoration_manifest']
    assert backup['strict_CPU_report'] == job['stopped_CPU_report']
    b = h.load('backup')
    archive = b.load(b.ARCHIVE, b.ARCHIVE_SHA, '_restored_fleet_archive')
    for stem in ('stopped-CPU-original01', 'backup-preparation-original02'):
        closure = read(root / stem / 'execution-original01/root-original-result-and-owned-release.json')
        original_owner = read(root / stem / 'execution-original01/root-original-identity.json')
        assert closure['original_exit'] == 0 and closure['lifecycle_complete'] and closure['unit_released']
        archive.archived_closure(closure, original_owner, b.read_pin, exit_zero=True)
        b.absent(original_owner['pid'], original_owner['starttime_ticks'])
        group = '/user.slice/user-1001.slice/user@1001.service/app.slice/' + original_owner['unit']
        assert not Path('/sys/fs/cgroup' + group).exists()

    def api(path):
        with urllib.request.urlopen('http://127.0.0.1:8771' + path, timeout=10) as response:
            value = json.load(response)
        return value

    now = api('/api/now')
    connections = api('/api/continuous_training_connections')
    owner = held['owner']
    expected_stamp = dict(pid=owner['pid'], birth=owner['birth'],
        source_sha256=next(v['sha256'] for v in job['source_pins'] if Path(v['path']).name == 'socket_server.py'))
    assert connections['server_stamp'] == expected_stamp and connections['connections'] == []
    assert connections['continuous_training_mode'] is True and connections['measurement_active'] is False
    assert 0 <= time.time() - connections['observed_unix_s'] <= 5
    assert 0 <= time.time() - now['ts'] <= 5
    assert now['client_count'] == 0 and now['client_rows'] == []
    assert now['lr'] == 6.25e-6 and now['epsilon'] == .1
    assert now['memory_buffer_size'] == 6000000 and now['training_enabled'] is True
    assert now['pipeline_read_error'] == now['bank_persistence_read_error'] == ''
    assert now['measurement_active'] is False
    assert now['learner_frame_count'] == held['saved_scalars']['learner_frame_count']
    assert a.output.is_absolute() and not a.output.exists()
    a.output.mkdir(mode=0o700)
    owner_record = h.put(a.output / 'actual-new-Main-owner.json', actual_owner)
    now_pin = h.put(a.output / 'Main-now-before-fleet.json', now)
    connections_pin = h.put(a.output / 'Main-connections-before-fleet.json', connections)
    by_name = {Path(v['path']).name: v for v in job['source_pins']}
    trainer = dict(owner, source=by_name['main.py'], server_stamp=expected_stamp)
    engineering = h.put(a.output / 'actual-fullstate-restoration-engineering-check.json', dict(
        schema='robotron-root-current-fullstate-restoration-engineering-check-v1',
        status='PASS_ENGINEERING_ONLY', actual_exit=0, observed_unix_s=time.time(),
        CPU_report=job['stopped_CPU_report'], current_held_exact_restoration=held_pin,
        new_one_use_release_consumed=consumed_pin, full_backup_manifest=backup_pin,
        original_CPU_scope_closed=True, original_backup_scope_closed=True,
        postrelease_API=now_pin, postrelease_connections=connections_pin,
        actual_new_owner=owner, existing_installed_mode_source_family_unchanged=False,
        replay_queue_constructor_only_changed_to8192=True,
        existing_strict_CPU_used_not_a_new_CPU_test=True, quality_qualified=False, promotion=False))
    authority = h.put(a.output / 'actual-new-Main-startup-authority.json', dict(
        schema='robotron-root-continuous-main-startup-qualified-v1', trainer=trainer,
        all_model_optimizer_replay_banks_clocks_preserved=True,
        new_mode_source_and_CPU_qualified=True, actual_CPU_scope_closeouts=[engineering],
        new_held_report=held_pin, new_Root_release=release_pin, new_release_consumed=consumed_pin,
        preservation_scope='Exact stopped state restored before first update; prior recovery gap remains historical.',
        RNG_or_MAME_state_restored=False, quality_qualified=False, promotion=False))
    selection = h.put(a.output / 'fresh-fleet-selection.json', dict(
        schema='robotron-root-repaired-v6-fleet-DATA-selection-v1', new_Main_owner_record=owner_record,
        new_startup_job=job_pin, new_held_report=held_pin, new_Root_release=release_pin,
        new_release_consumed=consumed_pin, new_startup_authority=authority,
        current_backup_manifest=backup_pin, fleet_output=str(root / 'post-backup-fleet-v6-original01'),
        journal_directory=str(root / 'post-backup-Main-runtime-original01')))
    constructor_pin = packet['sources']['forward_fleet_constructor']
    assert pin(constructor_pin['path']) == constructor_pin
    constructor = load('_actual_new_fleet_constructor', constructor_pin['path'])
    constructor.prepare(SimpleNamespace(expected_source_sha256=constructor_pin['sha256'],
        selection=selection['path'], selection_sha256=selection['sha256'],
        output=str(a.output / 'fresh-continuous-supervisor-v6-job.json')))


if __name__ == '__main__':
    main()
