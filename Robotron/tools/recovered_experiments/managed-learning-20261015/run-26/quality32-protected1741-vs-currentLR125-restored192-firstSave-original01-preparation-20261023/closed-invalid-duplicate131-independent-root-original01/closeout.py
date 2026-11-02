"""Read original failed runtime and actual cleanup; never launch or retry science."""
import collections
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time


def main():
    if sys.argv[1:] != ['--execute']:
        print('PLAN_ONLY')
        return
    G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
    N = Path(__file__).resolve().parent.parent
    D = Path(__file__).resolve().parent
    L = N/'01-reference'
    O = L/'diagnostic-output-original01'
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    h = load('h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader = load('r', G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    audit = load('a', G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    ctl = load('c', G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    def read(entry, as_json=True):
        return reader.read_pin(entry, as_json=as_json)
    def put_bytes(path, raw):
        with path.open('xb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(), 0o444);os.fsync(stream.fileno())
        return h.pin(path)
    config = json.loads((L/'controller-config.json').read_text())
    result = read(h.pin(O/'result.json'))
    closure_pin = h.pin(L/'execution-original01/root-original-result-and-owned-release.json')
    owner_pin = h.pin(L/'execution-original01/root-original-identity.json')
    closure, owner = read(closure_pin), read(owner_pin)
    fields = audit.archived_closure(closure, owner, read, exit_zero=False)
    assert closure['original_exit'] == 1 and closure['lifecycle_complete'] is True
    wanted = dict(CPUQuotaPerSecUSec='12s',MemoryMax='17179869184',MemorySwapMax='0',
                  RuntimeMaxUSec='2h 41min',TasksMax='512',TimeoutStopUSec='30s',
                  KillMode='mixed',SendSIGKILL='no',Restart='no')
    assert all(fields.get(k) == v for k,v in wanted.items())
    expected = ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
                'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+config['output']+'/tmp'] + config['argv']
    assert 'argv[]='+' '.join(expected)+' ; ignore_errors=no ;' in fields['ExecStart']
    for entry in config['pins']:
        assert ctl.pin(entry['path']) == entry
    for unit in (owner['unit'],owner['timer']):
        assert ctl.show(unit)['LoadState'] == 'not-found'
    for pid in (2576570,2576584,2576593,owner['pid']):
        assert not Path('/proc',str(pid)).exists()
    assert result['status'] == 'ORIGINAL_COMPILED_QUALITY32_INVALID_NO_RETRY'
    assert result['quality_qualified'] is result['full_game_score_verified'] is False
    assert result['all_original_threads_stopped'] is result['original_lease_released'] is result['immutable_inputs_unchanged'] is True
    assert result['before_intentional_stop'] is None
    partial = result['controller_exit']['cohort']
    after = result['after_intentional_stop']
    assert (partial['count'],partial['started'],partial['pending'],partial['abandoned']) == (32,64,32,0)
    assert (after['count'],after['started'],after['pending'],after['abandoned'],after['valid']) == (32,64,0,32,False)
    assert set(result['original_slots']) == set(map(str,range(4096,4128)))
    for row in result['original_slots'].values():
        assert row['actual_exit'] == 0 and not Path('/proc',str(row['pid'])).exists()
        assert row['outputs_sealed_after_original_writer_closure'] is True and not row['original_unsealed_output_paths']
        for entry in row['files'].values():
            h.checked(entry)
    reap = result['original_post_origin_child_reap']
    assert reap['all_original_children_reaped'] is True and not reap['signals_sent'] and not reap['exit_statuses_normalized']
    for entry in result['journal'].values():
        h.checked(entry)
    failed_pin = h.pin(O/'main-observations/0600-failed-validation.json')
    failed = read(failed_pin)
    obs = failed['original_observation']
    api, census = read(obs['raw_API']), read(obs['snapshot'])
    assert failed['accepted'] is False and failed['raw_census_and_API_preserved_before_validation'] is True
    counts = collections.Counter(row['client_slot'] for row in api['client_rows'])
    assert api['client_count'] == len(api['client_rows']) == 193 and set(counts) == set(range(192))
    assert counts[131] == 2 and all(v == 1 for k,v in counts.items() if k != 131)
    rows = [row for row in api['client_rows'] if row['client_slot'] == 131]
    assert {row['client_id'] for row in rows} == {93,163} and {row['lives'] for row in rows} == {0,3}
    assert all(row['level'] == 75 and row['score'] == 80700 for row in rows)
    binding_pin = h.pin(N/'fresh-study-launch-preparation-original01/current-main-binding.json')
    binding = read(binding_pin)
    assert set(census['actors']) == set(map(str,range(192)))
    for actor in binding['actors']:
        actual = census['actors'][str(actor['slot'])]
        assert (actual['pid'],actual['starttime_ticks'],actual['affinity']) == (actor['pid'],actor['starttime_ticks'],actor['mask'])
    assert result['main_observation_failures'] == [failed_pin]
    for folder in ('02-candidate','03-reference','04-candidate'):
        assert not (N/folder).exists()
    assert not (L/'independent-quality-leg-review-original01').exists()
    lease = result['lease']['coordinator']
    h.checked(lease)
    with open(lease['path'],'rb') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(stream,fcntl.LOCK_UN)
    h.checked(lease)
    listeners = subprocess.run(['ss','-ltnp'],capture_output=True,timeout=20)
    assert listeners.returncode == 0
    listeners_pin = put_bytes(D/'live-listeners.txt',listeners.stdout)
    for line in listeners.stdout.decode().splitlines()[1:]:
        assert int(line.split()[3].rsplit(':',1)[1]) not in {19998,*range(20000,20032)}
    gpu = subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory',
                          '--format=csv,noheader'],capture_output=True,timeout=30)
    assert gpu.returncode == 0 and 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0' not in gpu.stdout.decode()
    gpu_pin = put_bytes(D/'live-GPU-compute-apps.txt',gpu.stdout)
    monitor = N/'fresh-study-launch-preparation-original01/root-current-main-readonly-monitor.py'
    health = subprocess.run(['/usr/bin/python3.12','-I','-B',str(monitor)],capture_output=True,timeout=60)
    assert health.returncode == 0
    log = Path(os.readlink('/proc/2258486/fd/1'))
    assert log == G/'logs/mame_instance_131.log' and stat.S_ISREG(log.stat().st_mode)
    with log.open('rb') as stream:
        info = os.fstat(stream.fileno());offset=max(0,info.st_size-40000)
        stream.seek(offset);chunk=stream.read(info.st_size-offset)
    log_pin = put_bytes(D/'slot131-current-log-tail.txt',chunk)
    assert b'[WAVECAP] wave advance 74 -> 75 - soft reset (training-data rebalance)' in chunk
    sequence_pin = h.pin(N/'original-fresh-sequence-observer-original01-outcome.json')
    sequence = read(sequence_pin)
    assert sequence['status'] == 'ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY'
    assert sequence['original_records'] == [] and sequence['quality_qualified'] is False
    report = dict(schema='robotron-closed-invalid-duplicate131-original-root-readback-v1',
        status='CLOSED_INVALID_MAIN_API193_DUPLICATE131_NO_RETRY',reader_source=h.pin(__file__),
        original_native_result=h.pin(O/'result.json'),original_controller_result=h.pin(L/'controller-original-result.json'),
        original_owner=owner_pin,original_closure=closure_pin,actual_original_argv=expected,
        actual_resource_fields={k:fields[k] for k in wanted},
        all6_original_descriptors_argv_resources_and_owned_release_verified=True,
        all32_original_MAME_actual_exit0_and_absent=True,all_original_threads_stopped=True,
        sequence_display_and_controller_absent=True,sequence=sequence_pin,
        sequence_tool=dict(handle=64695,actual_exit=1),display_tool=dict(handle=7464,actual_exit=0),
        original_failed_observation=failed_pin,original_failed_API=obs['raw_API'],original_failed_census=obs['snapshot'],
        failed_API=dict(client_count=193,duplicated_slot=131,rows=rows),
        all192_failed_physical_census_births_and_affinities_match_current_binding=True,main_binding=binding_pin,
        partial_before_shutdown={k:partial[k] for k in ('count','started','pending','abandoned','mean','median')},
        invalid_after_shutdown={k:after[k] for k in ('count','started','pending','abandoned','valid')},
        C1_R2_C2_not_prepared_or_launched=True,independent_scientific_reader_not_launched=True,
        all33_private_ports_absent=listeners_pin,private_GPU0_compute_apps_absent=gpu_pin,
        permanent_lease_unchanged_and_unheld=lease,
        slot131_current_cap_log=dict(path=str(log),device=info.st_dev,inode=info.st_ino,
            selected_offset=offset,selected_bytes=len(chunk),archive=log_pin,
            contemporaneous_original_cap_event_not_timestamp_joined=True),
        current_main_health=json.loads(health.stdout),
        diagnosis='Original API has brief duplicate slot131: old cid163/lives0 and new cid93/lives3 at score80700/wave75. All192 physical actors unchanged. Current same-process log contains cap75 reset/reconnect sequences. Reconnect overlap is a supported hypothesis; contemporaneous socket peer/PID ownership was not captured, so exact origin is unproven. No retroactive cap exception or proven remote-client claim.',
        source_freeze_release_ready=True,production_runtime_changed=False,quality_qualified=False,promotion=False,
        created_unix_s=time.time())
    pin = h.put(D/'readback.json',report)
    print(json.dumps(dict(proof=pin,partial=report['partial_before_shutdown'],after=report['invalid_after_shutdown'],
                          current_main=report['current_main_health'])),flush=True)


if __name__ == '__main__':
    main()
