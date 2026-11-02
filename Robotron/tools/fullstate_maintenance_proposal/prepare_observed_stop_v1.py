"""Capture current owned metadata and assemble one stop job, without running it."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


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
    spec = importlib.util.spec_from_file_location('_capture_current_stop', a.header)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    preparation = a.header.parent.parent
    packet = json.loads((preparation / 'prepared-current-source-family.json').read_bytes())
    contracts = json.loads((preparation / 'CPU-metadata-recipe-contracts-original01.json').read_bytes())
    api_probe = json.loads((preparation / 'actual-live-stopAPI-readonly-original02/report.json').read_bytes())
    assert contracts['status'] == 'PASS_POSTREBOOT_MAINTENANCE_METADATA_RECIPE_ONLY'
    assert api_probe['status'] == 'PASS_ACTUAL_LIVE_INHERITED_STOP_API_READONLY'
    assert not a.output.exists() and a.output.parent.resolve(strict=True) == a.output.parent
    recovery = preparation.parent / 'reboot-recovery-20261031-original01'
    f = json.loads((recovery / 'fleet-v6-original01/status.json').read_bytes())
    assert time.time() - f['updated_unix_s'] < 5
    assert f['error_summary']['occurrences'] == 0
    assert f['counts']['active_train'] == 155 and f['counts']['reconnecting_train'] == 0
    assert all(f['counts'][k] == 0 for k in ('starting', 'retiring_eval', 'fault_cleanup', 'quarantined'))
    owner = packet['previous_owner']
    fleet = {('starttime_ticks' if k == 'birth' else k): v for k, v in f['supervisor'].items() if k != 'source'}
    linux = h.load('linux')
    linux.live_owner(owner)
    linux.live_owner(fleet)
    membership = h.read(f['original_membership'])
    original = membership['data']['original_slots']
    assert len(original) == 192 and len(f['slots']) == 192
    job = h.read(h.metadata(recovery / 'recovered-fleet-v6-job-original01.json')[0])
    actors = []
    for slot, row in sorted(f['slots'].items(), key=lambda kv: int(kv[0])):
        child = original[slot]['original_child']
        assert (row['original_pid'], row['original_birth']) == (child['pid'], child['birth'])
        proc = Path('/proc', str(child['pid']))
        try:
            fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            assert row['state'] == 'closed_eval' and row['eval_only'] is True
            state = 'absent'
        else:
            assert int(fields[19]) == child['birth'] and int(fields[1]) == fleet['pid']
            assert proc.stat().st_uid == os.getuid()
            assert (proc / 'cgroup').read_text().strip() == '0::' + fleet['cgroup']
            assert str((proc / 'exe').resolve()) == '/usr/games/mame'
            assert (proc / 'cmdline').read_bytes().decode().rstrip('\0').split('\0') == job['mame_argv']
            state = row['state']
        actors.append(dict(pid=child['pid'], starttime_ticks=child['birth'], slot=int(slot),
                           eval_only=row['eval_only'], state=state))
    members = set(map(int, (Path('/sys/fs/cgroup' + fleet['cgroup']) / 'cgroup.procs').read_text().split()))
    assert members == {fleet['pid'], *(r['pid'] for r in actors if r['state'] != 'absent')}
    persistent = {}
    names = {'Thread-1 (serve', 'Thread-2 (_samp', 'Thread-3 (_cons', 'Thread-4 (start', 'Thread-5 (stats'}
    for task in Path('/proc', str(owner['pid']), 'task').iterdir():
        try:
            name = (task / 'comm').read_text().strip()
            if name in names:
                persistent[task.name] = dict(comm=name, starttime_ticks=int(
                    (task / 'stat').read_text().rsplit(')', 1)[1].split()[19]))
        except FileNotFoundError:
            continue
    assert len(persistent) == 5
    startup_job = h.metadata(recovery / 'startup-metadata-original01/startup-job.json')[0]
    startup = h.read(startup_job)
    manifest = h.read(startup['restoration_manifest'])
    ring = copy.deepcopy({k: manifest['ring_and_banks'][k] for k in ('spec', 'ring')})
    # Only original storage identities and immutable NPY headers are read here.
    # Live body/metadata values remain explicitly unverified until owned stop.
    for desc in ring['ring']['arrays'].values():
        path = Path(desc['path'])
        before = path.stat()
        assert not path.is_symlink() and before.st_nlink == 1 and before.st_uid == os.getuid()
        assert (before.st_dev, before.st_ino, before.st_size) == tuple(desc['identity'][k] for k in ('device', 'inode', 'size'))
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            header = os.pread(fd, desc['data_offset'], 0)
            assert hashlib.sha256(header).hexdigest() == desc['header_sha256']
        finally:
            os.close(fd)
    a.output.mkdir(mode=0o700)
    storage = h.put(a.output / 'original-ring-storage-and-headers.json', ring)
    selection = dict(schema='robotron-root-current-continuous-preservation-selection-v1',
        owner=owner, fleet=fleet, expected_current_cap=8, first_current_main_stop=False,
        startup_job=startup_job,
        startup_held=h.metadata(recovery / 'startup-held-original01/verified-held-before-first-update.json')[0],
        startup_release_consumed=h.metadata(recovery / 'startup-held-original01/release-consumed.json')[0],
        budget_intent_source=h.SOURCES['budget_intent'], input_closure_producer=h.SOURCES['stop'],
        ring_storage_before=storage, input_closure=None, fleet_terminal_archive=None,
        zero_frame_FIFO_probe=dict(authorized=True, client_slot=1, eval_only=True,
            application_frames_to_send=0, scientific_or_natural_game_claimed=False),
        actual_CPU_result=None, actual_backup=None, actual_checkpoint_acquisition=None,
        actual_cold_start=None, actual_stop_authority=None)
    source_names = ('__init__.py', 'agent.py', 'config.py', 'connection_cleanup_receipts.py',
        'continuous_startup_bridge.py', 'game_journal.py', 'learning_control.py', 'main.py',
        'managed_driver.py', 'managed_measurement.py', 'metrics_dashboard.py', 'model.py',
        'replay_buffer.py', 'socket_server.py', 'training.py', 'bounded_fifo_cleanup_ack_v1.py')
    source_pins = [h.metadata(h.ROOT / 'Scripts/dqn' / n)[0] for n in source_names]
    observed = dict(schema='robotron-Root-current-continuous-preservation-observation-v1',
        observed_unix_s=time.time(), trainer=owner, fleet=fleet, actors=actors,
        persistent_native=persistent, current_source_pins=source_pins,
        base_control=h.metadata(h.ROOT / 'models_dqn/learning_control.json')[0],
        historical_cleanup_receipts=[], console=str(Path('/proc', str(owner['pid']), 'fd/1').readlink()),
        actor_command=job['mame_argv'], mame_executable='/usr/games/mame')
    sp = h.put(a.output / 'selection.json', selection)
    op = h.put(a.output / 'observation.json', observed)
    prepared = h.prepare_stop(Path(sp['path']), sp['sha256'], Path(op['path']), op['sha256'], a.output / 'stop')
    # Archive the effective unit text now, for a concrete forward override plan.
    archive = {}
    for unit in ('robotron-trainer.service', 'robotron-mame.service'):
        text = subprocess.check_output(['systemctl', '--user', 'cat', unit], timeout=15)
        archive[unit] = h.put(a.output / (unit + '.before.txt'), text)
    plan = h.put(a.output / 'forward-restart-plan-NOT-EXECUTED.json', dict(
        schema='robotron-forward-restart-plan-v1', previous_owner=owner, previous_fleet=fleet,
        prepared_stop=prepared, installed_unit_text_before=archive,
        startup_operator=packet['startup_operator'], future_fleet_constructor=packet['sources']['forward_fleet_constructor'],
        fresh_startup_metadata=str(preparation / 'post-backup-startup-metadata-original01'),
        fresh_startup_held=str(preparation / 'post-backup-startup-held-original01'),
        fresh_main_runtime=str(preparation / 'post-backup-Main-runtime-original01'),
        fresh_fleet_output=str(preparation / 'post-backup-fleet-v6-original01'),
        startup_cap=8, optimizer_lr=6.25e-6, batch_size=4096,
        installed_startup_sources=startup['source_pins'], priority_metric='ce',
        preconditions=['original stop0 and owner/population absent', 'independent readonly checkpoint acquisition',
            'original strict stopped CPU0 and resources closed', 'complete independently copied and hashed full backup',
            'fresh resume record preserves CE founder and exact saved checkpoint',
            'fresh one-use startup job and held restoration before first update',
            'exact held payload equality before Root release', 'fresh original fleet job/owner after actual release'],
        all_unknown_stopped_artifacts_must_be_bound_after_actual_original_stop=True,
        source_family=packet['sources'], recipe_or_service_changed=False, restart_performed=False))
    report = h.put(a.output / 'prepared-observed-stop-and-forward-plan.json', dict(
        status='PREPARED_CURRENT_STOP_AND_FORWARD_PLAN_NOT_LAUNCHED', prepared_stop=prepared,
        forward_plan=plan, live_actors=len(members)-1, original_actors=len(actors),
        original_ring_headers_checked=10, live_ring_payloads_read=False,
        captured_original_membership=f['original_membership'], observation=op, selection=sp,
        source=h.metadata(Path(__file__).resolve())[0], service_action_performed=False))
    print(json.dumps({k: report[k] for k in ('path', 'sha256', 'bytes')}))


if __name__ == '__main__':
    main()
