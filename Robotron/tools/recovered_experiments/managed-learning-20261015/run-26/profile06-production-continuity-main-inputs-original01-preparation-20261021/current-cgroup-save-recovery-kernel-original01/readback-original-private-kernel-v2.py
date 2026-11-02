"""Read the one completed private kernel fixture and its four original lifecycles.

No fixture, recovery watcher or test payload is started by this reader.
"""
from pathlib import Path
import hashlib, importlib.util, json, os, re, shlex, stat, sys, time, urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
K = Path(__file__).resolve().parent
H = K.parent


def ident(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(p):
    p = Path(p); before = ident(p.stat()); raw = p.read_bytes()
    assert ident(p.stat()) == before
    return dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=before)


def put(p, raw):
    with p.open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno()); os.fchmod(f.fileno(), 0o444)
    return pin(p)


def load(p, sha, name):
    p = Path(p); before = pin(p)
    assert before['sha256'] == sha and before['identity']['mode'] == '0o444'
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert pin(p) == before
    return m


def main():
    out = K/'root-kernel-and-all24-lifecycles-independent-readback-v2.json'
    archives = K/'independent-original-payload-archives-v2'
    assert not out.exists() and not archives.exists()
    runtime = load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445', '_kernel_read_runtime')
    reader = runtime.protector()
    control = load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py',
        '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', '_kernel_read_control')
    prep_pin = pin(H/'private-kernel-controller-preparation-original01.json')
    assert prep_pin['sha256'] == '28389d59a9c47bc73c388428dcebb2a838bb8c69c1c9d2feed6375d8d2fa71f7'
    prep = reader.read_pin(prep_pin)
    assert prep['expected_private_fixture_exits'] == dict(fleet=0, rescue=0, controller=23)
    for entry in prep['full8_selected_inputs'] + [prep['config'], prep['source']]:
        assert pin(entry['path']) == entry
    report_pin = pin(K/'root-independent-readback.json'); report = reader.read_pin(report_pin)
    assert report['status'] == 'ACTUAL_ORIGINAL_WATCH_RECOVERY_INTEGRATION_PASS'
    assert report['variant'] == 'lost_controller_during_exact_replacement_save_publication_pause'
    assert report['original_exits'] == prep['expected_private_fixture_exits']
    for key in ['all18_original_descriptors_verified', 'original192_child_PIDs_and_affinities_preserved',
                'private_heartbeat_resumed']:
        assert report[key] is True
    for key in ['emergency_cleanup_used', 'production_changed', 'model_replay_or_numerical_restore_tested']:
        assert report[key] is False
    assert not (K/'emergency-cleanup-used.json').exists() and not (K/'root-failure-preserved.json').exists()
    contracts = reader.read_pin(pin(H/'current-owner-handoff-contracts-CPU-original01/root-independent-readback.json'))
    for name, entry in report['source_pins'].items():
        assert pin(entry['path']) == entry
        if name != 'prove_handoff_recovery_v1.py':
            selected = contracts['tested_sources'][name]
            assert pin(selected['path']) == selected
            assert reader.read_pin(entry, as_json=False) == reader.read_pin(selected, as_json=False)
        else:
            assert entry['sha256'] == prep['source']['sha256']
    closures = {}; payloads = []; archives.mkdir()
    for role, directory, config_path, expected_exit in [
        ('root', H/'private-kernel-root-controller-original01', Path(prep['config']['path']), 0),
        *((r, K/(r+'-execution'), K/(r+'-config.json'), e) for r,e in prep['expected_private_fixture_exits'].items())]:
        owner_pin = pin(directory/'root-original-identity.json'); owner = reader.read_pin(owner_pin)
        closure_pin = pin(directory/'root-original-result-and-owned-release.json'); closure = reader.read_pin(closure_pin)
        config_pin = pin(config_path); config = reader.read_pin(config_pin)
        assert owner['unit'] == config['unit'] and owner['unit'].startswith('robotron-profile06-')
        fields = runtime.archived_closure(closure, owner,
            lambda e, as_json=True: reader.read_pin(e, as_json=as_json), exit_zero=expected_exit == 0)
        assert closure['original_exit'] == expected_exit and closure['original_exec_code'] == 1
        assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
        assert fields['MemoryMax'] == str(4<<30) and fields['MemorySwapMax'] == '0'
        assert runtime.duration_seconds(fields['RuntimeMaxUSec']) == 180
        expected_tasks = '256' if role in ('root','fleet') else '128'
        assert 'TasksMax='+expected_tasks in config['properties'] and fields['TasksMax'] == expected_tasks
        assert runtime.duration_seconds(fields['TimeoutStopUSec']) == 5
        assert fields['Restart'] == fields['SendSIGKILL'] == 'no'
        expected = ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
                    'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
        match = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}', fields['ExecStart'])
        assert match and shlex.split(match[1]) == expected
        born_pin = pin(directory/'original-first-observed-show-command.json')
        born_record = reader.read_pin(born_pin)
        assert born_record['argv'] == ['systemctl','--user','show',owner['unit']]
        assert born_record['exit'] == 0 and born_record['timed_out'] is False
        born_fields = dict(line.split('=',1) for line in reader.read_pin(born_record['stdout'],as_json=False).decode().splitlines() if '=' in line)
        reader.read_pin(born_record['stderr'],as_json=False)
        assert born_fields['MainPID'] == str(owner['pid']) and born_fields['InvocationID'] == owner['invocation_id']
        original_cgroup = born_fields['ControlGroup']
        assert original_cgroup.startswith('/user.slice/user-1001.slice/') and original_cgroup.endswith('/'+owner['unit'])
        assert not Path('/proc', str(owner['pid'])).exists()
        assert not Path('/sys/fs/cgroup'+original_cgroup).exists()
        for unit in [owner['unit'], owner['timer']]:
            assert control.show(unit)['LoadState'] == 'not-found'
        for name in ['stdout.txt','stderr.txt']:
            path = directory/name; original = pin(path)
            archive = put(archives/(role+'-'+name), path.read_bytes())
            assert archive['sha256'] == original['sha256'] and pin(path) == original
            payloads.append(dict(original=original, archive=archive))
        closures[role] = dict(owner=owner_pin, closure=closure_pin, config=config_pin, original_live_descriptor=born_pin,
            actual_exit=expected_exit, descriptor_exits=[e['exit'] for e in closure['full_original_archives']])
    injection_pin = pin(K/'work/injection.json'); injection = reader.read_pin(injection_pin)
    fixture = report['original_fixture']; owner = fixture['owner']
    assert injection['replacement'] == owner
    assert injection['variant'] == report['variant'] and injection['owned_descendant_children'] == 192
    assert all(injection[key] is True for key in ['exact_private_replacement_kernel_frozen',
        'main_heartbeat_stopped','actual_selected_startup_save_pause','no_process_stop_or_continue_signal'])
    assert injection['production_changed'] is False
    rescue = reader.read_pin(report['actual_watch_recovery'])
    assert rescue['restart_retry'] is False and rescue['controller_was_live_at_deadline'] is False
    assert rescue['original_controller'] == injection['controller']
    recovered = rescue['recovery']
    assert recovered['owner'] == owner and recovered['original_handle_preserved'] is True
    assert recovered['observation_pending'] is False and recovered['errors'] == []
    for key in ['restart_retry','replacement_terminated','source_rollback','protected_policy_loaded','replay_cleared']:
        assert recovered[key] is False
    completed_pin = pin(K/'work/fixture-completed.json'); completed = reader.read_pin(completed_pin)
    assert completed['original192_retained'] is True and completed['owner'] == owner
    assert completed['actors'] == fixture['actors'] and len(completed['actors']) == 192
    assert len({a['pid'] for a in completed['actors']}) == 192
    assert all(not Path('/proc', str(a['pid'])).exists() for a in completed['actors'])
    assert not Path('/sys/fs/cgroup'+owner['cgroup']).exists()
    guard = load(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
        'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', '_kernel_read_main_guard')
    prepared = reader.read_pin(pin(H/'prepared-inputs.json')); main_binding = reader.read_pin(prepared['original_main'])
    guard.owner_and_files(main_binding)
    raw = urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10).read()
    api = json.loads(raw)
    guard.healthy(api, reader.read_pin(main_binding['baseline_API']), main_binding['experiment'], time.time())
    api_pin = put(K/'main-API-after-original-kernel-test.raw.json',raw)
    assert 'torch' not in sys.modules
    result = dict(schema='profile06-original-private-kernel-and-four-lifecycles-readback-v1',
        status='ACTUAL_SELECTED_SAVE_PAUSE_KERNEL_AND_ALL24_ORIGINAL_DESCRIPTORS_PASS',
        observed_unix_s=time.time(), source=pin(Path(__file__)), original_preparation=prep_pin,
        original_fixture_report=report_pin, selected_source_byte_identity_verified=True,
        original_closures=closures, all24_original_descriptors_and_owned_releases_verified=True,
        actual_exits=dict(root=0,fleet=0,rescue=0,controller=23), intentional_controller_exit23_preserved=True,
        original_injection=injection_pin, original_watch_recovery=report['actual_watch_recovery'],
        original_fixture_completion=completed_pin, payload_archives=payloads,
        current_main_binding=prepared['original_main'], current_main_API=api_pin,
        current_main195_holds_and_original192_verified=True, production_changed=False,
        model_replay_or_numerical_restore_tested=False, original_kernel_test_retried=False,
        quality_qualified=False, promotion=False, learning_speed_gain_verified=False)
    final_pin = put(out,(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(dict(readback=final_pin,status=result['status'],actual_exits=result['actual_exits'])))


if __name__ == '__main__':
    if sys.argv[1:] == ['--observe']:
        main()
    else:
        print('PLAN_ONLY: read the original completed kernel fixture; no tests or live actions')
