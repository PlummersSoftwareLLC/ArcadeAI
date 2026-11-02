"""Prospective read-only original192 continuous-main census; no import-time IO.

Only a separately Root-bound, completed original192 physical bootstrap is
accepted. This module cannot launch, repair, stop or adopt a replacement.
"""
import hashlib
import importlib.util
import json
import mmap
import stat
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
LINUX=ROOT/'tools/quality_capacity_proposal/supervised_main_fleet_v2.py'
LINUX_SHA='1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
STATIC=('parent_pid','cgroup','command','environment','affinity','uids','executable')
REGISTRY=Path(__file__).with_name('continuous_static192_registry_v1.py')
REGISTRY_SHA='2f3eddaf75ee3b9a875d0a621a63eeea7274eae3afa75bcceb309002233316d1'

def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def linux():
    require(hashlib.sha256(LINUX.read_bytes()).hexdigest() == LINUX_SHA, 'Linux reader changed')
    spec = importlib.util.spec_from_file_location('_round_health_linux', LINUX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def birth(process):
    return process['pid'], process['starttime_ticks']


def process_record(pid, reader):
    result = reader.process_record(pid)
    # Also bind DQN and CUDA recipe settings; omit unrelated environment data.
    environment = Path('/proc', str(pid), 'environ').read_bytes()
    for item in environment.split(b'\0'):
        if b'=' not in item:
            continue
        key, value = item.split(b'=', 1)
        name = key.decode()
        if name.startswith('DQN_') or name in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER'):
            result['environment'][name] = value.decode()
    stat = reader.process_stat(pid)
    require(stat is not None and stat['starttime_ticks'] == result['starttime_ticks'], 'Process raced capture')
    result['state'] = stat['state']
    return result


def unit_record(name, reader):
    raw = subprocess.check_output(['systemctl', '--user', 'show', name], text=True, timeout=5)
    values = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    require(values['ActiveState'] == 'active' and values['SubState'] == 'running'
            and values['NRestarts'] == '0', 'Main unit stopped or restarted')
    process = process_record(int(values['MainPID']), reader)
    require(process['cgroup'] == values['ControlGroup'], 'Main unit cgroup differs')
    return dict(unit=name, invocation=values['InvocationID'], process=process, raw_show=raw)


def file_identity(path):
    return stat_identity(path.stat())


def stat_identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(info.st_mode & 0o777), uid=info.st_uid, nlink=info.st_nlink)


def check_inputs(case, full=False):
    for path, value in case['inputs'].items():
        actual = Path(path)
        require(str(actual.resolve(strict=True)) == path and not actual.is_symlink()
                and file_identity(actual) == value['identity'], 'Held input identity changed: ' + path)
        if full:
            with actual.open('rb') as stream:
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and stat_identity(info) == value['identity'],
                        'Held source must remain the selected regular file: ' + path)
                if info.st_size:
                    with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
                        digest = hashlib.sha256(view).hexdigest()
                else:
                    digest = hashlib.sha256(b'').hexdigest()
                require(digest == value['sha256'], 'Held input bytes changed: ' + path)
                require(not actual.is_symlink() and file_identity(actual) == value['identity']
                        and stat_identity(os.fstat(stream.fileno())) == value['identity'],
                        'Held input changed during full hash: ' + path)


def validate_optimizer_accounting(value):
    """One admitted update may be in flight; unknown outcomes never qualify."""
    require(value['schema'] == 'robotron-optimizer-exposure-v1' and value['enabled'] is True,
            'Optimizer accounting disabled or foreign')
    names = ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')
    total, epoch = value['total'], value['since_epoch']
    for counters in (total, epoch):
        require(all(type(counters.get(name)) is int and counters[name] >= 0 for name in names)
                and counters['unavailable'] == 0
                and counters['outcomes_recorded'] == counters['applied'] + counters['amp_skipped'],
                'Unknown or inconsistent optimizer outcomes')
    pending = total['attempts_started'] - total['outcomes_recorded']
    require(pending in (0, 1)
            and epoch['attempts_started'] - epoch['outcomes_recorded'] == pending
            and all(epoch[name] <= total[name] for name in names)
            and epoch['outcomes_recorded'] > 0
            and type(value['unclassified_started_total']) is int
            and value['unclassified_started_total'] == pending
            and type(value['available']) is bool and value['available'] is (pending == 0),
            'Optimizer in-flight accounting differs')
    return pending


def registry():
    require(hashlib.sha256(REGISTRY.read_bytes()).hexdigest() == REGISTRY_SHA,
            'Exact selected static192 registry verifier required')
    import sys
    name = '_prospective_continuous_static192_registry_v1'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, REGISTRY)
        value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
        sys.modules[name] = value
    return sys.modules[name]


class CensusFailure(ValueError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.raw_snapshot = dict(schema='robotron-rejected-continuous-static192-census-v1', evidence=evidence)


def stable_round_status(value):
    # Keep the existing worker collector interface. This is one static epoch,
    # not a declaration of another whole-round domain or score barrier. TRAIN
    # episode counters/scores can change without changing this membership.
    fields = ('schema', 'mode', 'epoch', 'supervisor', 'trainer', 'rolemap',
              'source_authority', 'original_membership', 'initial_admission', 'slots', 'counts', 'errors')
    return {k: value[k] for k in fields}


def observed_counts(sample):
    rows = sample['status']['slots']
    return dict(total=192, active_train=sum(r['state'] == 'active_train' for r in rows.values()),
                active_eval=sum(r['state'] == 'active_eval' for r in rows.values()),
                retiring_eval=sum(r['state'] == 'retiring_eval' for r in rows.values()),
                closed_eval=sum(r['state'] == 'closed_eval' for r in rows.values()))


def read_status(path):
    path = Path(path)
    require(path.resolve(strict=True) == path and not path.is_symlink(), 'Canonical publisher path required')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                and before.st_size <= 524288, 'Bounded actual normal publisher snapshot required')
        raw = stream.read(524289)
        require(len(raw) <= 524288 and stat_identity(before) == stat_identity(os.fstat(stream.fileno()))
                and stat_identity(before) == file_identity(path), 'Atomic publisher changed during capture')
    return raw, json.loads(raw)


def get(path):
    before = time.monotonic_ns()
    with urllib.request.urlopen('http://127.0.0.1:8771' + path, timeout=2) as response:
        raw = response.read(1_048_577)
    require(len(raw) <= 1_048_576, 'API body exceeds declared bound')
    after = time.monotonic_ns()
    return dict(path=path, before_monotonic_ns=before, after_monotonic_ns=after,
                raw_wire=raw.decode('utf-8'), sha256=hashlib.sha256(raw).hexdigest(), value=json.loads(raw))


def probe(pid, reader):
    before = time.monotonic()
    value = reader.process_stat(pid)
    return dict(pid=pid, path=str(Path('/proc', str(pid), 'stat')),
                before_monotonic_s=before, after_monotonic_s=time.monotonic(),
                absent=value is None, current_birth=None if value is None else value['starttime_ticks'],
                state=None if value is None else value['state'])


def raw_identity(pid):
    value = dict(pid=pid)
    for name in ('stat', 'cmdline', 'cgroup'):
        try:
            with Path('/proc', str(pid), name).open('rb') as stream:
                raw = stream.read(65537)
            value[name] = dict(raw=raw[:65536].decode('utf-8', 'backslashreplace'), truncated=len(raw) > 65536)
        except OSError as error:
            value[name] = dict(error=repr(error))
    return value


def collect(case, previous=None):
    evidence = dict(stage='owners', started_monotonic_s=time.monotonic())
    try:
        reader = linux(); started = evidence['started_monotonic_s']
        raw, status = read_status(case['continuous']['snapshot_path'])
        owners = {key: unit_record(case['units'][key], reader) for key in ('trainer', 'fleet')}
        evidence.update(raw_status=raw.decode(), owners=owners, children=[])
        fleet = owners['fleet']['process']
        child_ids = Path('/proc', str(fleet['pid']), 'task', str(fleet['pid']), 'children').read_text().split()
        evidence['original_children'] = child_ids
        require(len(child_ids) == len(set(child_ids)) <= 192, 'Unknown/duplicate supervisor child count')
        expected = {r['original_child']['pid']: slot for slot, r in case['continuous']['original_slots'].items()}
        actors = {}; capture = []
        for text in child_ids:
            pid = int(text); row = dict(pid=pid); evidence['children'].append(row)
            try:
                first = process_record(pid, reader); row['record'] = first
                second = process_record(pid, reader); row['confirm_record'] = second
                require(all(first[k] == second[k] for k in ('pid', 'starttime_ticks', *STATIC)),
                        'Original actor exec/identity raced capture')
                require(pid in expected and expected[pid] not in actors, 'Unknown/replaced/duplicate child PID')
                slot = expected[pid]
                require(first['environment'].get('ROBOTRON_CLIENT_SLOT') == slot, 'Original child slot changed')
                actors[slot] = first; capture.append(row)
            except (OSError, ValueError, KeyError) as error:
                row.update(error=repr(error), raw_rejection_identity=raw_identity(pid))
                raise
        evidence['stage'] = 'policy-API-and-absence'
        policy = get('/api/continuous_training_policy')
        connections = get('/api/continuous_training_connections')
        api = get('/api/now')
        probes = {slot: probe(row['original_child']['pid'], reader)
                  for slot, row in case['continuous']['original_slots'].items() if slot not in actors}
        raw_after, after = read_status(case['continuous']['snapshot_path'])
        require(stable_round_status(after) == stable_round_status(status), 'Continuous registry publication raced census')
        require(time.monotonic() - started <= 5, 'Continuous physical/registry/API census exceeded5s')
        ended = time.monotonic()
        return dict(schema='robotron-continuous-static192-main-health-snapshot-v1',
                    unix_s=time.time(), monotonic_s=ended, owners=owners,
                    status=status, raw_status_wire=raw.decode(), actors=actors,
                    original_children=child_ids, child_census=capture,
                    api=api['value'], raw_API_wire=api['raw_wire'], api_wire_sha256=api['sha256'],
                    policy_capture=policy, connections_capture=connections,
                    PID_absence=probes, capture_started_monotonic_s=started,
                    capture_ended_monotonic_s=ended)
    except (OSError, ValueError, KeyError) as failure:
        evidence.update(failure=repr(failure), ended_monotonic_s=time.monotonic())
        raise CensusFailure(repr(failure), evidence) from failure


def validate_policy(case, sample, capture, schema):
    c = case['continuous']; value = capture['value']; raw = capture['raw_wire'].encode()
    require(hashlib.sha256(raw).hexdigest() == capture['sha256'] and json.loads(raw) == value,
            'Policy/connection raw wire changed')
    require(type(capture['before_monotonic_ns']) is int and type(capture['after_monotonic_ns']) is int
            and capture['before_monotonic_ns'] <= value['observed_monotonic_ns'] <= capture['after_monotonic_ns']
            and 0 <= sample['monotonic_s'] - capture['before_monotonic_ns']/1e9 <= 2
            and capture['after_monotonic_ns']/1e9 <= sample['monotonic_s']
            and 0 <= sample['unix_s'] - value['observed_unix_s'] <= 2,
            'Actual original policy/connection observation is future/unbracketed/stale')
    require(value['schema'] == schema and value['server_stamp'] == c['server_stamp']
            and value['continuous_training_mode'] is True and value['main_measurement_entry_disabled'] is True
            and value['measurement_active'] is False and value['measurement_generation'] == c['policy_generation']
            and type(value['measurement_generation']) is int and value['ratchet_frozen'] is False
            and value['training_enabled'] is True and value['replay_admission_open'] is True
            and value['consumer_error'] is None, 'Actual permanent main-policy mode/epoch/fence changed')
    return value


def validate(case, sample, previous=None):
    reg = registry(); c = case['continuous']
    require(case['schema'] == reg.CASE_SCHEMA, 'Explicit new continuous health case required')
    view = reg.validate_snapshot(case, sample, previous)
    require(sample['schema'] == 'robotron-continuous-static192-main-health-snapshot-v1'
            and json.loads(sample['raw_status_wire']) == sample['status'], 'Raw registry publication changed')
    require(0 <= sample['monotonic_s'] - sample['capture_started_monotonic_s'] <= 5
            and sample['capture_started_monotonic_s'] <= sample['capture_ended_monotonic_s'] <= sample['monotonic_s'],
            'Physical census capture bracket differs')
    for role in ('trainer', 'fleet'):
        actual, baseline = sample['owners'][role], case['owners'][role]
        require(actual['unit'] == baseline['unit'] and actual['invocation'] == baseline['invocation']
                and birth(actual['process']) == birth(baseline['process'])
                and all(actual['process'][key] == baseline['process'][key] for key in STATIC),
                'Original main owner/source/recipe/affinity/cgroup changed')
    reg.owner_join(c['trainer'], sample['owners']['trainer'])
    reg.owner_join(c['supervisor'], sample['owners']['fleet'])
    actors = sample['actors']; absent = reg.SLOTS - set(actors)
    require(set(actors) <= reg.SLOTS and absent <= view['retiring'] | view['closed']
            and not set(actors) & view['closed'] and set(sample['PID_absence']) == absent,
            'An original TRAIN/active EVAL vanished, unknown child appeared, or closed EVAL remains live')
    census = sample['child_census']
    require(len(census) == len(sample['original_children']) == len(actors)
            and {str(row['pid']) for row in census} == set(sample['original_children']),
            'Raw original child census coverage differs')
    for slot, actor in actors.items():
        original = c['original_slots'][slot]['original_child']
        matches = [entry for entry in census if entry['pid'] == actor['pid']]
        require(len(matches) == 1 and matches[0]['record'] == actor
                and all(actor[k] == matches[0]['confirm_record'][k] for k in ('pid', 'starttime_ticks', *STATIC))
                and actor['pid'] == original['pid'] and actor['starttime_ticks'] == original['birth']
                and actor['parent_pid'] == c['supervisor']['pid'] and actor['cgroup'] == c['supervisor']['cgroup']
                and actor['command'] == case['actor_command'] and actor['executable'] == case['actor_executable']
                and actor['environment'] == reg.expected_environment(case, slot)
                and actor['affinity'] == case['actor_affinity'] and actor['uids'] == [os.getuid()]*4
                and actor['state'] not in ('T', 't', 'Z', 'X', 'x'),
                'Actual original MAME birth/argv/role/source/env/affinity/state changed')
    for slot in absent:
        old = c['original_slots'][slot]['original_child']; probe = sample['PID_absence'][slot]
        require(probe['pid'] == old['pid'] and probe['path'] == str(Path('/proc', str(old['pid']), 'stat'))
                and (probe['absent'] is True and probe['current_birth'] is probe['state'] is None
                     or probe['absent'] is False and type(probe['current_birth']) is int and probe['current_birth'] != old['birth'])
                and sample['capture_started_monotonic_s'] <= probe['before_monotonic_s']
                <= probe['after_monotonic_s'] <= sample['capture_ended_monotonic_s'],
                'No fresh positive original birth absence for retired EVAL')
    validate_policy(case, sample, sample['policy_capture'], 'robotron-continuous-main-policy-v1')
    connections = validate_policy(case, sample, sample['connections_capture'], 'robotron-continuous-active-connections-v1')
    current = connections['connections']; conn_slots = [str(x['client_slot']) for x in current]
    require(len(conn_slots) == len(set(conn_slots)) and set(conn_slots) <= set(actors)
            and set(actors) - set(conn_slots) <= view['retiring'], 'Fresh connection batch misses active original or has unknown slot')
    for slot, connection in zip(conn_slots, current):
        expected = reg.binding(case, slot, c['original_slots'][slot]['connection_binding'],
                               c['original_slots'][slot]['original_child'])
        require(connection == expected, 'Fixed original connection token/CID/role/endpoints changed')
    api = sample['api']; raw = sample['raw_API_wire'].encode()
    require(hashlib.sha256(raw).hexdigest() == sample['api_wire_sha256'] and json.loads(raw) == api,
            'Raw main API changed')
    require(api['training_enabled'] is True and api['measurement_active'] is False
            and 0 <= sample['unix_s'] - api['ts'] <= 5 and 0 <= api['pipeline_snapshot_age_s'] <= 5
            and all(api[key] == value for key, value in case['recipe'].items()), 'Main recipe/training API stale or changed')
    for kind in ('optimizer', 'replay'):
        actual = api['host_pipeline']['learning_exposure'][kind]
        require(all(actual[key] == case['exposure'][kind][key]
                    for key in ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')),
                'Original optimizer/replay lineage changed')
        require(actual['enabled'] is True, 'Learning exposure disabled')
        if kind == 'optimizer': validate_optimizer_accounting(actual)
        else: require(actual['available'] is True, 'Replay exposure unavailable')
    if previous is not None:
        require(0 <= sample['monotonic_s'] - previous['monotonic_s'] <= 2,
                'Prospective accepted main-proof gap exceeds2s')
        require(all(api[key] >= previous['api'][key] for key in
                    ('training_steps', 'learner_frame_count', 'optimized_samples', 'frame_count')),
                'Main coherent clock rolled back')
    return view


if __name__ == '__main__':
    print('SOURCE_ONLY_INERT_NO_READS_WRITES_PROBES_OR_ACTIONS')


