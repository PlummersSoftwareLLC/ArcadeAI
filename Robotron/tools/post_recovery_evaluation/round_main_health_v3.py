"""Read-only main health for declared one-game training rounds.

An ordinary client disappearance is invalid unless its durable score explains
the retirement. Actor replacement within a round is rejected. The only accepted
new fleet is the next complete round after a verified192-score barrier. This
module does not change the unchanged private evaluator or qualify any cohort.
"""
import hashlib
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import statistics
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LINUX = ROOT / 'tools/quality_capacity_proposal/supervised_main_fleet_v2.py'
LINUX_SHA = '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
STATIC = ('parent_pid', 'cgroup', 'command', 'environment', 'affinity', 'uids', 'executable')


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


def read(path):
    return json.loads(path.read_bytes())


def file_identity(path):
    info = path.stat()
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
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == value['sha256'],
                        'Held input bytes changed: ' + path)


def completed_round(directory, journal):
    results, identities = {}, {}
    started = read(directory / 'started.json')
    for path in sorted(directory.glob('slot-*-result.json')):
        outer = read(path)
        row = outer['result']
        slot = str(row['client_slot'])
        require(outer['round'] == started['round'] and row['start_unix_s'] >= started['started_unix_s']
                and slot not in results and row['complete'] is True and row['eligible'] is True
                and row['known_start'] is True and row['boundary_reason'] in ('score_reset', 'zero_score_restart')
                and type(row['score']) is int and row['score'] >= 0, 'Invalid/duplicate main completion')
        require(journal.get(row['journal_game_id']) == row, 'Score receipt lacks matching committed journal row')
        results[slot] = outer
        identities[slot] = hashlib.sha256(path.read_bytes()).hexdigest()
    return results, identities


def collect(case):
    reader = linux()
    started = time.monotonic()
    root = Path(case['round_root'])
    raw_status = (root / 'status.json').read_bytes()
    status = json.loads(raw_status)
    require(status['completed'] == status['retired'], 'Retirement in flight; retry same owners')
    directory = root / ('round-%06d' % status['round'])
    owners = {role: unit_record(case['units'][role], reader) for role in ['trainer', 'fleet']}
    fleet = owners['fleet']['process']
    children = Path('/proc', str(fleet['pid']), 'task', str(fleet['pid']), 'children').read_text().split()
    actors = {}
    for child in children:
        record = process_record(int(child), reader)
        require(record['command'][0] == record['executable']['path'] == '/usr/games/mame', 'Unknown fleet child')
        slot = record['environment']['ROBOTRON_CLIENT_SLOT']
        require(slot not in actors, 'Duplicate process slot')
        actors[slot] = record
    wire = Path(case['completion_journal']).read_bytes()
    # An append being written is not a receipt until its terminating newline.
    journal = {row['journal_game_id']: row for row in
               (json.loads(line) for line in wire.split(b'\n')[:-1] if line)}
    results, receipts = completed_round(directory, journal)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        api_wire = response.read(1_048_577)
    require(len(api_wire) <= 1_048_576, 'Raw API exceeds bound')
    api = json.loads(api_wire)
    require(stable_round_status(json.loads((root / 'status.json').read_bytes())) == stable_round_status(status),
            'Round publication raced capture')
    previous = None
    if status['round'] > case['initial_round']:
        previous_directory = root / ('round-%06d' % (status['round'] - 1))
        previous_results, previous_receipts = completed_round(previous_directory, journal)
        summary = read(previous_directory / 'summary.json')
        scores = [outer['result']['score'] for outer in previous_results.values()]
        require(len(scores) == 192 and summary['mean'] == statistics.mean(scores)
                and summary['median'] == statistics.median(scores), 'Closed round score summary differs')
        with (previous_directory / 'scores.csv').open() as stream:
            csv_rows = list(csv.DictReader(stream))
        require(len(csv_rows) == 192 and len({row['slot'] for row in csv_rows}) == 192
                and all(int(row['score']) == previous_results[row['slot']]['result']['score']
                        for row in csv_rows), 'Closed round CSV differs')
        previous = dict(summary=summary,
                        results=previous_results, receipts=previous_receipts)
    require(time.monotonic() - started <= 5, 'Main census exceeded5s')
    return dict(schema='robotron-round-main-health-snapshot-v1', unix_s=time.time(),
        monotonic_s=time.monotonic(), owners=owners, actors=actors, status=status,
        started=read(directory / 'started.json'), results=results, receipt_hashes=receipts,
        previous_complete=previous, api=api, raw_API_wire=api_wire.decode('utf-8'), api_wire_sha256=hashlib.sha256(api_wire).hexdigest())


def validate(case, sample, previous=None):
    expected_slots = set(map(str, range(192)))
    status, actors, results = sample['status'], sample['actors'], sample['results']
    require(status['total'] == 192 and status['completed'] == status['retired'] == len(results)
            and status['active'] + len(results) == 192, 'Round counts differ from score receipts')
    require(set(actors) | set(results) == expected_slots, 'Actor vanished without a committed score')
    require(set(actors) <= expected_slots and set(results) <= expected_slots, 'Unknown actor slot')
    active = set(actors) - set(results)
    frozen = set(actors) & set(results)
    require(len(active) == status['active'], 'Active actor count differs from round status')
    for role in ['trainer', 'fleet']:
        actual, baseline = sample['owners'][role], case['owners'][role]
        require(actual['unit'] == baseline['unit'] and actual['invocation'] == baseline['invocation']
                and birth(actual['process']) == birth(baseline['process'])
                and all(actual['process'][key] == baseline['process'][key] for key in STATIC),
                'Original main owner, recipe, cgroup or executable changed')
    fleet = sample['owners']['fleet']['process']
    for slot, actor in actors.items():
        env = actor['environment']
        expected_env = dict(case['actor_environment'], ROBOTRON_CLIENT_SLOT=slot,
            ROBOTRON_ACTOR_ROUND=str(status['round']),
            ROBOTRON_EVAL_MODE='1' if case['slot_eval'][slot] else '2',
            ROBOTRON_PREVIEW_CLIENT='1' if slot == '0' else '0')
        require(actor['parent_pid'] == fleet['pid'] and actor['cgroup'] == fleet['cgroup']
                and actor['uids'] == [os.getuid()] * 4 and actor['affinity']
                and env == expected_env and actor['command'] == case['actor_command']
                and actor['affinity'] == case['actor_affinity']
                and actor['executable'] == case['actor_executable']
                and env['ROBOTRON_CLIENT_SLOT'] == slot
                and env['ROBOTRON_ACTOR_ROUND'] == str(status['round'])
                and env['ROBOTRON_SOCKET_ADDRESS'] == 'dell:9998'
                and env['ROBOTRON_RETIRE_AFTER_GAME'] == '1'
                and env['ROBOTRON_EVAL_MODE'] == ('1' if case['slot_eval'][slot] else '2'),
                'Actor ownership, role, round or socket changed')
        require((slot in frozen and actor['state'] in ('T', 't')
                 and results[slot]['pid'] == actor['pid'])
                or (slot in active and actor['state'] not in ('T', 't', 'Z', 'X', 'x')),
                'Completed actor still executing, or active actor stopped')
    api = sample['api']
    rows = api['client_rows']
    slots = [str(row['client_slot']) for row in rows]
    require(len(slots) == len(set(slots)) == api['client_count'] and set(slots) - frozen == active
            and set(slots) <= set(actors), 'Unknown, duplicate or missing API client')
    require(api['training_enabled'] is True and api['measurement_active'] is False
            and api['lr'] == 3.125e-6 and 0 <= sample['unix_s'] - api['ts'] <= 5
            and 0 <= api['pipeline_snapshot_age_s'] <= 5, 'Main training state stale or changed')
    for key in ['optimizer', 'replay']:
        actual = api['host_pipeline']['learning_exposure'][key]
        require(all(actual[field] == case['exposure'][key][field] for field in
                    ['process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason']),
                'Main optimizer/replay lineage changed')
        if key == 'optimizer':
            validate_optimizer_accounting(actual)
        else:
            require(actual['available'] is True, 'Replay exposure unavailable')
    if previous is None:
        require(status['round'] == case['initial_round'], 'Unexplained initial round')
        return
    require(0 <= sample['monotonic_s'] - previous['monotonic_s'] <= 30, 'Observation gap exceeds30s')
    old_round = previous['status']['round']
    if status['round'] == old_round:
        require(set(previous['results']) <= set(results), 'Completed slot lost or restarted')
        require(all(previous['receipt_hashes'][slot] == sample['receipt_hashes'][slot]
                    for slot in previous['results']), 'Committed score receipt changed')
        for slot in set(previous['actors']) & set(actors):
            original, current = previous['actors'][slot], actors[slot]
            require(birth(original) == birth(current)
                    and all(original[key] == current[key] for key in STATIC),
                    'Unplanned actor replacement within a round')
        for slot in set(previous['actors']) - set(actors):
            require(results[slot]['pid'] == previous['actors'][slot]['pid'], 'Retirement PID differs')
    else:
        require(status['round'] == old_round + 1, 'Unobserved skipped training rounds')
        closed = sample['previous_complete']
        require(closed is not None and set(closed['results']) == expected_slots
                and closed['summary']['complete'] is True and closed['summary']['completed'] == 192
                and closed['summary']['retired'] == 192
                and sample['started']['started_unix_s'] >= closed['summary']['updated_unix_s'],
                'Next fleet started without the complete durable192-score barrier')
        require(all(closed['receipts'][slot] == digest for slot, digest in
                    previous['receipt_hashes'].items()), 'Closed prior score receipt changed')
        old_births = {birth(actor) for actor in previous['actors'].values()}
        require(not old_births & {birth(actor) for actor in actors.values()}, 'Old actor survived round turnover')
    for key in ['training_steps', 'learner_frame_count', 'optimized_samples', 'frame_count']:
        require(api[key] >= previous['api'][key], 'Main clock rolled back')


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


def stable_round_status(value):
    # The publication heartbeat alone does not alter the round, roster, or scores.
    return {key: item for key, item in value.items() if key != 'updated_unix_s'}
