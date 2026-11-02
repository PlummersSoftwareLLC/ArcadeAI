"""Default inert. Exact owned pre-exec census; never launches or controls a process."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SLOTS = set(map(str, range(192)))
MAX_LAUNCH_AGE_S = 5
SCHEMA = 'robotron-declared-owned-launcher-census-v1'
SOURCES = {
    str(ROOT/'tools/power_recovery/round_fleet.py'): 'f6bba59d7d69b2d437728ff6fcabdd4e575a5b14aa22e25dbab4a72a3463b4d2',
    str(ROOT/'tools/power_recovery/mame_with_roles.sh'): 'e7c798484c53a76c83a8203e879900dd1920919188fe5d67675d926d6f8283a4',
    str(ROOT/'tools/power_recovery/mame_with_roles.py'): '531e70d6531fb3ab8506c1d93abd50d4c02b46f15d1abec59e5aab2c196e3d86',
}
EXECUTABLES = {'env': '/usr/bin/env', 'bash': '/usr/bin/bash', 'python': '/usr/bin/python3.12'}
ORDER = {'env': 0, 'bash': 1, 'python': 2, 'mame': 3}
IDENTITY_KEYS = ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid')
STATIC = ('parent_pid', 'cgroup', 'command', 'environment', 'affinity', 'uids', 'executable')


def require(value, reason):
    if not value:
        raise ValueError(reason)


class CensusFailure(ValueError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.raw_snapshot = dict(schema='robotron-rejected-partial-launcher-census-v1', evidence=evidence)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def small_pin(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(), 'Canonical input required')
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= 16 << 20, 'Bounded source/executable required')
    raw = path.read_bytes()
    require(identity(path.stat()) == identity(before), 'Input changed during read')
    return dict(sha256=hashlib.sha256(raw).hexdigest(), identity=identity(before))


def prepare_case(case):
    """Data/source reads only; no API, proc census, writes, or process actions."""
    result = copy.deepcopy(case)
    for path, digest in SOURCES.items():
        require(result['inputs'][path]['sha256'] == digest and small_pin(path) == result['inputs'][path],
                'Declared unchanged launch source differs')
    executables = {}
    for stage, path in EXECUTABLES.items():
        selected = small_pin(path)
        require(path not in result['inputs'] or result['inputs'][path] == selected, 'Conflicting executable input')
        result['inputs'][path] = selected
        executables[stage] = dict(path=path, identity={k: selected['identity'][k] for k in IDENTITY_KEYS})
    result['inputs'][str(Path(__file__).resolve())] = small_pin(Path(__file__).resolve())
    result['launcher_contract'] = dict(schema=SCHEMA, maximum_launch_age_s=MAX_LAUNCH_AGE_S,
        source_sha256=SOURCES, stage_executables=executables,
        clock_anchor=sample_clock(),
        role_authority='unchanged original192 slot_eval; input fleet environment differs from final MAME role environment',
        scientific_launch_qualified=False)
    verify_contract(result)
    return result


def verify_contract(case):
    contract = case['launcher_contract']
    require(set(contract) == {'schema', 'maximum_launch_age_s', 'source_sha256', 'stage_executables', 'clock_anchor',
            'role_authority', 'scientific_launch_qualified'}
            and contract['schema'] == SCHEMA and contract['maximum_launch_age_s'] == MAX_LAUNCH_AGE_S
            and contract['source_sha256'] == SOURCES and contract['scientific_launch_qualified'] is False,
            'Exact prospective launcher contract required')
    require(set(case['slot_eval']) == SLOTS and all(type(v) is bool for v in case['slot_eval'].values()), 'Exact192 roles required')
    require(all(case['inputs'][path]['sha256'] == digest for path, digest in SOURCES.items()), 'Original launch source authority changed')
    require(set(contract['stage_executables']) == set(EXECUTABLES), 'Exact executable stages required')
    for stage, path in EXECUTABLES.items():
        expected = dict(path=path, identity={k:case['inputs'][path]['identity'][k] for k in IDENTITY_KEYS})
        require(contract['stage_executables'][stage] == expected, 'Launcher executable authority differs')
    fleet = case['owners']['fleet']['process']
    require(contract['stage_executables']['python'] == fleet['executable'], 'Fleet and launcher Python identity differs')
    require(case['actor_command'][0] == case['actor_executable']['path'] == '/usr/games/mame', 'Exact original MAME output required')
    check_clock(contract['clock_anchor'], contract['clock_anchor'])


def sample_clock():
    before = time.monotonic()
    boot = time.clock_gettime(time.CLOCK_BOOTTIME)
    after = time.monotonic()
    return dict(ticks_per_second=os.sysconf('SC_CLK_TCK'), boottime_s=boot,
        monotonic_before_s=before, monotonic_after_s=after)


def check_clock(clock, anchor):
    require(set(clock) == set(anchor) == {'ticks_per_second','boottime_s','monotonic_before_s','monotonic_after_s'},
            'Exact bounded boot/monotonic witness required')
    for pair in (clock, anchor):
        require(type(pair['ticks_per_second']) is int and pair['ticks_per_second'] == os.sysconf('SC_CLK_TCK')
                and all(type(pair[k]) in (int,float) and math.isfinite(pair[k]) and pair[k] > 0
                        for k in ('boottime_s','monotonic_before_s','monotonic_after_s'))
                and 0 <= pair['monotonic_after_s']-pair['monotonic_before_s'] <= .001,
                'Clock witness span or actual kernel tick rate differs')
    lo,hi = clock['boottime_s']-clock['monotonic_after_s'],clock['boottime_s']-clock['monotonic_before_s']
    old_lo,old_hi = anchor['boottime_s']-anchor['monotonic_after_s'],anchor['boottime_s']-anchor['monotonic_before_s']
    require(lo <= old_hi+1e-6 and old_lo <= hi+1e-6, 'Boot clock offset changed or was forged')


def expected_input(case, slot, number):
    return dict(case['owners']['fleet']['process']['environment'], ROBOTRON_CLIENT_SLOT=slot,
        ROBOTRON_ACTOR_ROUND=str(number), ROBOTRON_RETIRE_AFTER_GAME='1', ROBOTRON_PREVIEW_FPS='30')


def expected_commands(case):
    tail = case['actor_command'][1:]
    shell = str(ROOT/'tools/power_recovery/mame_with_roles.sh')
    script = str(ROOT/'tools/power_recovery/mame_with_roles.py')
    return dict(env=['/usr/bin/env', 'bash', shell, *tail], bash=['bash', shell, *tail],
        python=['/usr/bin/python3.12', '-I', '-B', script, *tail])


def phase(case, actor):
    if actor['command'] == case['actor_command'] and actor['executable'] == case['actor_executable']:
        return 'mame'
    for stage, command in expected_commands(case).items():
        if actor['command'] == command and actor['executable'] == case['launcher_contract']['stage_executables'][stage]:
            return stage
    raise ValueError('Unknown fleet child executable or literal launch argv')


def check_child(case, actor, number, clock):
    verify_contract(case)
    check_clock(clock,case['launcher_contract']['clock_anchor'])
    stage = phase(case, actor)
    slot = actor['environment'].get('ROBOTRON_CLIENT_SLOT')
    require(slot in SLOTS, 'Unknown launcher slot')
    if stage == 'mame':
        return stage
    fleet = case['owners']['fleet']['process']
    require(actor['parent_pid'] == fleet['pid'] and actor['cgroup'] == fleet['cgroup']
            and actor['uids'] == [os.getuid()]*4 and actor['affinity'] == case['actor_affinity']
            and actor['environment'] == expected_input(case, slot, number)
            and actor['state'] not in ('T', 't', 'Z', 'X', 'x'), 'Owned launcher input role/environment/identity differs')
    hz, now = clock['ticks_per_second'], clock['boottime_s']
    require(type(hz) is int and hz > 0 and type(now) in (int, float) and math.isfinite(now)
            and type(actor['starttime_ticks']) is int and actor['starttime_ticks'] > 0
            and 0 <= now - actor['starttime_ticks']/hz <= MAX_LAUNCH_AGE_S,
            'Owned launcher exceeded declared5s age or has invalid birth clock')
    return stage


def raw_identity(pid):
    """Best-effort bounded rejection identity; absence remains absence, never success."""
    root = Path('/proc', str(pid)); result = dict(pid=pid)
    for name in ('stat', 'cmdline', 'cgroup'):
        try:
            with (root/name).open('rb') as stream:
                data = stream.read(65537)
            result[name] = dict(raw=data[:65536].decode('utf-8', 'backslashreplace'), truncated=len(data)>65536)
        except OSError as error:
            result[name] = dict(error=repr(error))
    try:
        result['executable_path'] = os.readlink(root/'exe')
    except OSError as error:
        result['executable_error'] = repr(error)
    return result


def capture_children(case, fleet, record, children, number):
    """No retries: retain every attempted child identity before classifying."""
    clock = sample_clock()
    evidence = dict(schema=SCHEMA, original_children=list(children), round=number, clock=clock, children=[])
    actors, failures = {}, []
    for child in children:
        entry = dict(pid=int(child)); evidence['children'].append(entry)
        try:
            first = record(int(child)); entry['record'] = first
            second = record(int(child)); entry['confirm_record'] = second
            require(all(first[k] == second[k] for k in ('pid', 'starttime_ticks', *STATIC)), 'Child exec raced capture')
            stage = check_child(case, first, number, clock); entry['stage'] = stage
            slot = first['environment']['ROBOTRON_CLIENT_SLOT']
            require(slot not in actors, 'Duplicate physical launch slot')
            actors[slot] = first
        except (OSError, ValueError, KeyError) as error:
            entry.update(error=repr(error), raw_rejection_identity=raw_identity(int(child)))
            failures.append(repr(error))
    if failures:
        raise CensusFailure('; '.join(failures), evidence)
    return actors, evidence


def verify_sample(case, sample, admitted, previous=None):
    verify_contract(case)
    census = sample['launcher_census']
    require(census['schema'] == SCHEMA and census['round'] == admitted['round'], 'Launcher census round differs')
    check_clock(census['clock'],case['launcher_contract']['clock_anchor'])
    require(0 <= sample['monotonic_s']-census['clock']['monotonic_after_s'] <= 5,
            'Launcher census clock is outside the original bounded sample')
    require(len(census['original_children']) == len(census['children']) == len(sample['actors'])
            and len(set(census['original_children'])) == len(census['original_children']), 'Child census coverage differs')
    found = {}
    for entry in census['children']:
        actor, confirm = entry['record'], entry['confirm_record']
        require(entry['pid'] == actor['pid'] == confirm['pid']
                and all(actor[k] == confirm[k] for k in ('pid', 'starttime_ticks', *STATIC)), 'Archived child identity bracket differs')
        slot = actor['environment']['ROBOTRON_CLIENT_SLOT']
        require(slot not in found and sample['actors'][slot] == actor, 'Archived child differs from physical census')
        require(entry['stage'] == check_child(case, actor, admitted['round'], census['clock']), 'Archived launcher stage differs')
        found[slot] = entry['stage']
    require(set(found) == set(sample['actors'])
            and {str(row['pid']) for row in census['children']} == set(census['original_children']), 'Original child PID roster differs')
    launching = {slot for slot, stage in found.items() if stage != 'mame'}
    if launching:
        require(admitted['bootstrap'] is True and launching <= admitted['registering']
                and not launching & set(admitted['results']), 'Launcher requires original bounded bootstrap and cannot be registered/completed')
        elapsed = sample['monotonic_s']-census['clock']['monotonic_after_s']
        round_age = sample['unix_s']-admitted['started']['started_unix_s']
        hz = census['clock']['ticks_per_second']
        require(all(census['clock']['boottime_s']-sample['actors'][slot]['starttime_ticks']/hz+elapsed
                    <= round_age+1/hz+.05 for slot in launching),
                'Launcher birth predates the proved new-round start')
    if previous is not None and admitted['round'] == (previous.get('round_admission') or {}).get('effective_round', previous['status']['round']):
        old_census = previous.get('launcher_census')
        old_phases = {entry['record']['environment']['ROBOTRON_CLIENT_SLOT']:entry['stage'] for entry in old_census['children']} if old_census else {}
        for slot in set(previous['actors']) & set(sample['actors']):
            old, current = previous['actors'][slot], sample['actors'][slot]
            require((old['pid'],old['starttime_ticks']) == (current['pid'],current['starttime_ticks']), 'Launcher PID/birth changed before exact MAME exec')
            old_stage = old_phases.get(slot, 'mame')
            require(ORDER[found[slot]] >= ORDER[old_stage], 'Launcher exec phase regressed')
        require(all(slot in sample['actors'] for slot, stage in old_phases.items() if stage != 'mame'),
                'Unexecuted launcher vanished without original exact MAME proof')
    return launching


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-case'); parser.add_argument('--case-sha256'); parser.add_argument('--output')
    args = parser.parse_args()
    if args.prepare_case is None:
        print('INERT: no reads, outputs, processes or controls'); return
    path = Path(args.prepare_case); require(small_pin(path)['sha256'] == args.case_sha256, 'Exact selected case required')
    value = prepare_case(json.loads(path.read_bytes()))
    output = Path(args.output); raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    with output.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
    print(json.dumps(dict(path=str(output),sha256=hashlib.sha256(raw).hexdigest(),scientific_launch_qualified=False)))


if __name__ == '__main__':
    main()
