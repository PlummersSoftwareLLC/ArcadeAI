"""Root-only original F closure observation; inert without explicit tool acknowledgements.

Root must observe both original tool sessions terminal with actual exit0 before
using --execute. Files alone do not establish those tool-handle observations.
This checker never signals processes, controls units, queries Main, or changes
CONTROL/PUBLIC. It observes original births, four units/cgroups and three retained
owners, and briefly locks the EXISTING lease inode without writing it. Native
score/child-exit validation remains the separate closed-pair collector's job.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

CASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031')
BOOKS = [{'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/Root-original-R1-all32-physical-owner-observation-original01.json', 'sha256': 'd4618600940c150a1e60512c96a9c0977f2b840f513b01a4fa1bbbcd4d2b5ea9', 'bytes': 14488, 'identity': {'device': 2304, 'inode': 82728109, 'bytes': 14488, 'mtime_ns': 1793471728088910287, 'ctime_ns': 1793471728088910287, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/Root-active-C1-all32-anchored-runtime-index-original02.json', 'sha256': '93148134dead62b498eaaec31e805d8f6d178f32e3e70790ddb2dff6369bb923', 'bytes': 11320, 'identity': {'device': 2304, 'inode': 82731904, 'bytes': 11320, 'mtime_ns': 1793473677981351083, 'ctime_ns': 1793473677981351083, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}]
OUTER = dict(pid=1535267, birth=35349191, tool_session=2024)
RECORDER = dict(pid=1550281, birth=35471795, tool_session=55872)
RETAINED = dict(Main=dict(pid=208501, birth=27823352),
                fleet_v6=dict(pid=965562, birth=30270092),
                publisher=dict(pid=634434, birth=29236464))
UNIT_PREFIX = 'robotron-LR9375-S2-fixedcutoff-score-'
UNITS = [UNIT_PREFIX + leg + '-original01-20261031.' + kind
         for leg in ('r1', 'c1') for kind in ('service', 'timer')]
CGROUP_ROOT = Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')
LEASE = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
OUTPUT = CASE / 'Root-original2024-and55872-positive-closure-original01.json'


def require(value, message):
    if not value: raise ValueError(message)


def integer(value):
    return type(value) is int and value > 0


def identity(value):
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                mode=oct(stat.S_IMODE(value.st_mode)), uid=value.st_uid, nlink=value.st_nlink)


def immutable(path, *, expected=None, limit=1048576):
    require(path.is_absolute() and path.resolve() == path, 'Canonical immutable path required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
            and before.st_uid == 1001 and before.st_nlink == 1
            and 0 < before.st_size <= limit, 'Owned bounded immutable file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd)) == identity(before), 'Immutable open identity changed')
        with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(limit + 1)
        require(identity(os.fstat(fd)) == identity(before), 'Immutable file changed during read')
    finally: os.close(fd)
    require(identity(path.lstat()) == identity(before) and len(raw) == before.st_size,
            'Immutable path identity/size changed')
    result = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                  bytes=len(raw), identity=identity(before))
    if expected is not None: require(result == expected, 'Selected immutable full pin differs')
    return raw, result


def read_json(path, expected=None):
    raw, selected = immutable(path, expected=expected)
    value = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    require(type(value) is dict, 'JSON object required')
    return value, selected


def birth(pid, *, require_live=False):
    require(integer(pid), 'Positive exact integer PID required')
    try: raw = Path('/proc', str(pid), 'stat').read_text()
    except FileNotFoundError: return None
    fields = raw.rsplit(')', 1)[1].split()
    result = int(fields[19])
    require(result > 0, 'Positive process birth required')
    if require_live: require(fields[0] not in ('Z', 'X', 'x'), 'Retained owner is a zombie/dead process')
    return result


def observe_originals(owners):
    rows = []
    for owner in owners:
        current = birth(owner['pid'])
        require(current != owner['birth'], 'An original owned process is still present')
        rows.append(dict(**owner, observed_current_birth=current, original_birth_absent=True))
    return rows


def observe_retained():
    rows = {}
    for name, owner in RETAINED.items():
        current = birth(owner['pid'], require_live=True)
        require(current == owner['birth'], 'A retained Main/fleet/publisher owner changed or disappeared')
        rows[name] = dict(**owner, observed_current_birth=current, same_original_birth=True)
    return rows


def original_owners(r1, c1):
    require(r1['schema'] == 'robotron-Root-original-R1-all32-live-physical-owner-observation-v1'
            and c1['schema'] == 'robotron-Root-LR9375-original-C1-all32-live-anchored-index-v1',
            'Exact original ownerbook schemas required')
    require(r1['outer_owner'] == OUTER and c1['outer'] == OUTER and c1['tabular'] == RECORDER,
            'Original outer/recorder owner joins differ')
    rows = [dict(role='outer', pid=OUTER['pid'], birth=OUTER['birth'])]
    for leg, book, key, native_key, expected_native in (
            ('R1', r1, 'owners', 'native_owner', (1535503, 35349499)),
            ('C1', c1, 'actors', 'native', (1580150, 35722044))):
        native = book[native_key]
        require((native['pid'], native['birth']) == expected_native
                and native['unit'] == UNIT_PREFIX + leg.lower() + '-original01-20261031.service',
                'Original native owner/unit differs')
        rows.append(dict(role='native', leg=leg, pid=native['pid'], birth=native['birth']))
        actors = book[key]
        require(type(actors) is list and len(actors) == 32
                and {v['slot'] for v in actors} == set(range(4096, 4128)), 'Exact original32 slots required')
        for actor in actors:
            stamp = actor['original_birth'] if leg == 'R1' else actor['birth']
            require(integer(actor['slot']) and integer(actor['pid']) and integer(stamp)
                    and actor['parent_pid'] == native['pid'] and actor['proc_uid'] == 1001
                    and actor['prefix_verified'] is True
                    and actor['cgroup'] == '0::' + str(CGROUP_ROOT / native['unit']).removeprefix('/sys/fs/cgroup'),
                    'Original actor identity/physical source evidence differs')
            if leg == 'R1':
                require(actor['observed_birth'] == stamp and actor['same_original_birth'] is True
                        and actor['selected_cgroup_matches'] is True, 'Original R1 observation differs')
            rows.append(dict(role='MAME', leg=leg, slot=actor['slot'], pid=actor['pid'], birth=stamp))
    require(len(rows) == 67 and len({v['pid'] for v in rows}) == 67, 'Exactly67 distinct original owners required')
    rows.append(dict(role='tabular_recorder', pid=RECORDER['pid'], birth=RECORDER['birth']))
    require(len({v['pid'] for v in rows}) == 68, 'Recorder must be a distinct original owner')
    return rows


def cgroup_empty(unit):
    root = CGROUP_ROOT / unit
    try: metadata = root.lstat()
    except FileNotFoundError: return dict(path=str(root), absent=True, processes=[])
    require(stat.S_ISDIR(metadata.st_mode) and root.resolve() == root, 'Unexpected original cgroup path')
    groups = [root] + sorted(p for p in root.rglob('*') if p.is_dir())
    require(len(groups) <= 256, 'Unexpected original cgroup subtree')
    checked = []
    for group in groups:
        require(group.resolve() == group, 'Symlink in original cgroup subtree')
        try: values = (group / 'cgroup.procs').read_text().split()
        except FileNotFoundError: continue  # An empty removed cgroup is still absent.
        require(not values, 'An original unit cgroup still contains processes')
        checked.append(str(group))
    return dict(path=str(root), absent=False, checked_empty_groups=checked, processes=[])


def observe_units():
    rows = []
    for unit in UNITS:
        fields = ['Id', 'LoadState', 'ActiveState', 'SubState', 'InvocationID']
        if unit.endswith('.service'): fields += ['MainPID', 'ControlGroup']
        argv = ['/usr/bin/systemctl', '--user', 'show', unit, '--no-pager', '--property=' + ','.join(fields)]
        command = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        require(command.returncode == 0, 'Original unit SHOW failed')
        values = dict(line.split('=', 1) for line in command.stdout.splitlines() if '=' in line)
        require(values.get('Id') == unit and values.get('LoadState') == 'not-found'
                and values.get('ActiveState') == 'inactive' and values.get('SubState') == 'dead'
                and values.get('InvocationID') == '', 'Exact original unit is not absent')
        if unit.endswith('.service'):
            require(values.get('MainPID') == '0' and values.get('ControlGroup') == '',
                    'Original service PID/cgroup is not empty')
        rows.append(dict(unit=unit, argv=argv, actual_exit=command.returncode,
                         stdout=command.stdout, stderr=command.stderr, fields=values,
                         cgroup=cgroup_empty(unit)))
    return rows


def probe_existing_lease():
    def check(value):
        require(stat.S_ISREG(value.st_mode) and value.st_ino == 939 and value.st_uid == 1001
                and stat.S_IMODE(value.st_mode) == 0o600 and value.st_nlink == 1,
                'Existing owned GPU0 lease inode939 required; never recreate it')
    before = LEASE.lstat(); check(before)
    fd = os.open(LEASE, os.O_RDWR | os.O_NOFOLLOW)
    locked = False
    try:
        opened = os.fstat(fd); check(opened)
        require(identity(opened) == identity(before), 'Lease identity changed on open')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); locked = True
        require(identity(os.fstat(fd)) == identity(before) and identity(LEASE.lstat()) == identity(before),
                'Lease identity changed while locked')
        fcntl.flock(fd, fcntl.LOCK_UN); locked = False
    finally:
        if locked: fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    require(identity(LEASE.lstat()) == identity(before), 'Existing lease changed after release/close')
    return dict(path=str(LEASE), identity=identity(before), exclusive_nonblocking_acquire=True,
                unlock_completed=True, fd_closed=True, created=False, written=False, unlinked=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-source-sha256')
    parser.add_argument('--Root-actual2024-terminal0', action='store_true')
    parser.add_argument('--Root-actual55872-terminal0', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: Root must observe original2024 and55872 actual terminal0; no evidence reads or outputs')
        return 0
    require(args.Root_actual2024_terminal0 and args.Root_actual55872_terminal0,
            'Explicit Root acknowledgements of BOTH original tool terminal0 handles required')
    require(os.getuid() == 1001 and type(args.expected_source_sha256) is str
            and re.fullmatch('[0-9a-f]{64}', args.expected_source_sha256), 'Exact owned frozen checker SHA required')
    source_raw, source = immutable(Path(__file__).resolve())
    require(source['sha256'] == args.expected_source_sha256, 'Checker source SHA differs')
    require(OUTPUT.parent.resolve() == CASE and not OUTPUT.exists() and not OUTPUT.is_symlink(),
            'One fresh exact F-local positive proof required')
    r1, r1_pin = read_json(Path(BOOKS[0]['path']), BOOKS[0])
    c1, c1_pin = read_json(Path(BOOKS[1]['path']), BOOKS[1])
    owners = original_owners(r1, c1)
    outer, outer_pin = read_json(CASE / 'Root-controller-runtime-original01/result.json')
    recorder, recorder_pin = read_json(CASE / 'original-observation-loop-original01/result.json')
    require(type(outer.get('actual_exit')) is int and outer['actual_exit'] == 0 and outer.get('error') is None
            and outer.get('reporter_thread_closed') is True and outer.get('report_update_errors') == []
            and outer.get('native_or_original_controller_retried') is False and outer.get('legs') == ['R1', 'C1'],
            'Original outer result is not a clean unretried two-arm closure')
    require(type(recorder.get('actual_exit')) is int and recorder['actual_exit'] == 0
            and type(recorder.get('last_observer_actual_exit')) is int and recorder['last_observer_actual_exit'] == 0
            and recorder.get('instrumentation_error') is None
            and recorder.get('reason') == 'final_observation_after_original_outer_absence'
            and (recorder.get('pid'), recorder.get('birth')) == (RECORDER['pid'], RECORDER['birth']),
            'Original recorder/final observer result is not normal0')
    retained_before = observe_retained(); absent_before = observe_originals(owners)
    units = observe_units(); lease = probe_existing_lease()
    absent_after = observe_originals(owners); retained_after = observe_retained()
    for selected in (source, r1_pin, c1_pin, outer_pin, recorder_pin):
        immutable(Path(selected['path']), expected=selected)
    proof = dict(schema='robotron-Root-original-F-pair-and-tabular-positive-closure-v1', observed_unix_s=time.time(),
        checker=source, Root_tool_handle_acknowledgements=dict(original2024_actual_terminal0=True,
        original55872_actual_terminal0=True, source='Explicit Root CLI observations; not inferred from result files'),
        selected_ownerbooks=[r1_pin, c1_pin], outer_result=outer_pin, recorder_result=recorder_pin,
        outer_actual_exit=outer['actual_exit'], recorder_actual_exit=recorder['actual_exit'],
        final_observer_actual_exit=recorder['last_observer_actual_exit'],
        original_pair_owner_count=67, original_recorder_owner_count=1,
        original_birth_observations_before=absent_before, original_birth_observations_after=absent_after,
        retained_owners_before=retained_before, retained_owners_after=retained_after,
        exact_original_units=units, existing_GPU0_lease=lease,
        child_exit_codes_normalized=False, child_exit_codes_and_scores_read=False,
        quality_or_promotion_claim=False, signals_stops_restarts_API_CONTROL_PUBLIC_actions=False)
    raw = (json.dumps(proof, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(fd); os.fchmod(fd, 0o444)
    finally: os.close(fd)
    directory = os.open(CASE, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    _, output_pin = immutable(OUTPUT)
    print(json.dumps(dict(status='POSITIVE_ORIGINAL_PAIR_AND_RECORDER_CLOSURE', proof=output_pin), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
