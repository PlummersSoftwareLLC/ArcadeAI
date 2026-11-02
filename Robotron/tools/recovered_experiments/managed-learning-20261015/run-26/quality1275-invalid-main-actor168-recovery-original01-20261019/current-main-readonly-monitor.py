"""Check the prospectively registered, supervised replacement fleet; no launch or repair."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
D = Path(__file__).resolve().parent

def load(path, sha, name):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

p = load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py', 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'reader')
w = load(R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py', 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', 'window')
c = load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py', '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'control')
a = load(G/'tools/eval_capacity_proposal/raw_api_witness_v1.py', '9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0', 'raw')
transition_pin = p.pin(D/'main-fleet-transition-independent-readback.json')
assert transition_pin['sha256'] == '0004b611d8e25f32db4ba5de27e7c91a39b676a79cd17fbce39c33fd098ef5e0'
transition = p.read_pin(transition_pin)
main = p.read_pin(transition['current_main_binding'])
w.owner_and_files(main)
fleet = transition['fleet']
for owner in (main['owner'], fleet):
    shown = c.show(owner['unit'])
    assert shown['MainPID'] == str(owner['pid']) and shown['InvocationID'] == owner['invocation_id']
    assert shown['NRestarts'] == '0' and w.process_start(owner['pid']) == owner['starttime_ticks']
live = {}
for line in Path('/sys/fs/cgroup' + fleet['cgroup'], 'cgroup.procs').read_text().splitlines():
    proc = Path('/proc', line)
    try:
        command = proc.joinpath('cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    except FileNotFoundError:
        continue
    if not command or command[0] != b'/usr/games/mame':
        continue
    env = dict(v.split(b'=', 1) for v in proc.joinpath('environ').read_bytes().split(b'\0') if b'=' in v)
    slot = int(env[b'ROBOTRON_CLIENT_SLOT'])
    assert slot not in live
    expected = transition['live_slot_processes'][str(slot)]
    stat = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()
    assert int(line) == expected['pid'] and int(stat[19]) == expected['starttime_ticks']
    assert int(stat[1]) == fleet['pid'] and [v.decode() for v in command] == expected['command']
    assert proc.joinpath('cgroup').read_text().strip() == '0::' + fleet['cgroup']
    assert env[b'ROBOTRON_SOCKET_ADDRESS'] == b'dell:9998' and env[b'ROBOTRON_EVAL_MODE'] == b'0'
    assert sorted(os.sched_getaffinity(int(line))) == expected['affinity']
    live[slot] = int(line)
assert set(live) == set(range(192))
wire = urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5).read()
api = a.parse_wire(wire)
w.healthy(api, p.read_pin(main['baseline_API']), main['experiment'], time.time())
assert 0 <= time.time() - (G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime <= 360
assert api['quality_campaign']['available'] is False and api['quality_campaign']['legs'] == []
for process in transition['original_private_births_absent']:
    assert w.process_start(process['pid']) != process['starttime_ticks']
for entry in transition['original_closures']:
    closed = p.read_pin(entry)
    assert closed['lifecycle_complete'] and closed['unit_released']
    assert all(c.show(closed['original'][key])['LoadState'] == 'not-found' for key in ('unit', 'timer'))
stamp = str(time.time_ns())
samples = D/'current-main-observations'
samples.mkdir(exist_ok=True)
wire_pin = w.publish(samples/(stamp + '-wire.json'), wire)
witness = w.publish(samples/(stamp + '-witness.json'), a.witness_fields(api, wire_pin))
result = dict(unix_s=time.time(), classification='MAIN192_HEALTHY_QUALITY1275_INVALID_CLOSED', client_count=api['client_count'], learner_frame_count=api['learner_frame_count'], training_steps=api['training_steps'], fps=api['fps'], training_enabled=api['training_enabled'], measurement_active=api['measurement_active'], held_inputs_verified=195, preserved_original_actors=191, registered_replacement_slot=168, dashboard_active_quality=False, API_witness=witness, quality_gain_verified=False, learning_speed_gain_verified=False)
w.publish(samples/(stamp + '-readback.json'), result)
print(json.dumps(result, allow_nan=False))
