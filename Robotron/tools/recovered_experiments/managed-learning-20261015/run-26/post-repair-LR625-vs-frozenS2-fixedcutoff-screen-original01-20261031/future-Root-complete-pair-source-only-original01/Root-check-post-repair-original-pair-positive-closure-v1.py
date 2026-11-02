"""Root-only postpair closure observation; default inert.

Root MUST observe original tool7081 actually terminal0 before --execute. The
selected terminal record retains that external observation; files alone do not
prove tool-handle completion. This checker then observes actual original process
birth absence, four unit/cgroup absences, retained owners, and the EXISTING939
lease. It never signals, stops, restarts, queries APIs or writes CONTROL/PUBLIC.
Spawn/exit metadata is source-owned history, not a past independent /proc census.
The separate offline collector validates score arithmetic and authentic STOP.
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

CASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-repair-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031')
PREPARED_SHA = 'ced18ab5a19ae57036db9a9368baaf2d4895d9306f9f029ceb7e37a298713c6b'
CONTROLLER_SHA = '42838b75136c28d5dbaf5d34ac0b29aa7cbbc1f3e692c821c383a5ebf5764f0a'
OUTER = dict(pid=1690128, birth=36842992, tool_session=7081)
RETAINED = dict(Main=dict(pid=1644742, birth=36415496, unit='robotron-trainer.service',
    invocation_id='1ebea2dabe3043b295774b8380fc3960'),
    fleet_v6=dict(pid=1646378, birth=36456134, unit='robotron-mame.service',
    invocation_id='7a1a1ed8799746caaf0a7cc2f80d810d'),
    publisher=dict(pid=634434, birth=29236464))
UNIT_PREFIX = 'robotron-post-repair-LR625-S2-fixedcutoff-score-'
UNITS = [UNIT_PREFIX + leg + '-original01-20261031.' + kind
         for leg in ('r1', 'c1') for kind in ('service', 'timer')]
CGROUP_ROOT = Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')
LEASE = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
OUTPUT = CASE / 'Root-original7081-positive-closure-original01.json'


def require(value, message):
    if not value: raise ValueError(message)

def integer(value):
    return type(value) is int and value > 0

def identity(value):
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                mode=oct(stat.S_IMODE(value.st_mode)), uid=value.st_uid, nlink=value.st_nlink)

def immutable(path, *, expected=None, limit=4194304):
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


def observe_retained():
    rows = {}
    for name, owner in RETAINED.items():
        current = birth(owner['pid'], require_live=True)
        require(current == owner['birth'], 'A retained Main/fleet/publisher original changed or disappeared')
        value = dict(**owner, observed_current_birth=current, same_original_birth=True)
        if 'unit' in owner:
            fields = ['Id', 'MainPID', 'InvocationID', 'ActiveState', 'SubState', 'ControlGroup']
            argv = ['/usr/bin/systemctl', '--user', 'show', owner['unit'], '--no-pager', '--property=' + ','.join(fields)]
            command = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
            observed = dict(line.split('=', 1) for line in command.stdout.splitlines() if '=' in line)
            require(command.returncode == 0 and observed.get('Id') == owner['unit']
                    and observed.get('MainPID') == str(owner['pid']) and observed.get('InvocationID') == owner['invocation_id']
                    and observed.get('ActiveState') == 'active' and observed.get('SubState') == 'running'
                    and observed.get('ControlGroup') == str(CGROUP_ROOT / owner['unit']).removeprefix('/sys/fs/cgroup'),
                    'Retained original unit identity differs')
            require(birth(owner['pid'], require_live=True) == owner['birth'], 'Retained birth changed across SHOW')
            value['unit_observation'] = dict(argv=argv, actual_exit=command.returncode,
                stdout=command.stdout, stderr=command.stderr, fields=observed)
        rows[name] = value
    return rows


def held_json(path, inventory, pin=None):
    value, actual = read_json(path)
    if pin is not None:
        require(all(actual[k] == pin[k] for k in ('path', 'sha256', 'bytes'))
                and all(actual['identity'].get(k) == v for k, v in pin.get('identity', {}).items()), 'Selected metadata digest/identity differs')
    inventory.append(actual)
    return value, actual


def derive_original_owners(inventory):
    prepared_path = CASE / 'prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json'
    prepared, prepared_pin = held_json(prepared_path, inventory)
    require(prepared_pin['sha256'] == PREPARED_SHA and prepared['ordered_legs'] == ['R1', 'C1']
            and prepared['selected_sources']['controller']['sha256'] == CONTROLLER_SHA, 'Exact selected current pair required')
    selected, _ = held_json(CASE / 'Root-prospective-matched-fixed-cutoff-selection.json', inventory, prepared['selection'])
    configs, _ = held_json(CASE / 'Root-original-controller-configs.json', inventory, prepared['controller_configs'])
    require(selected['current_main']['owner']['pid'] == RETAINED['Main']['pid']
            and selected['current_main']['owner']['starttime_ticks'] == RETAINED['Main']['birth']
            and selected['current_main']['owner']['unit'] == RETAINED['Main']['unit']
            and selected['current_main']['owner']['cgroup'] == str(CGROUP_ROOT / RETAINED['Main']['unit']).removeprefix('/sys/fs/cgroup')
            and selected['current_main']['owner']['invocation_id'] == RETAINED['Main']['invocation_id']
            and selected['current_fleet'] == RETAINED['fleet_v6'], 'Retained selected Main/fleet owner differs')
    outer, outer_pin = held_json(CASE / 'Root-controller-runtime-original01/owner.json', inventory)
    require((outer['pid'], outer['birth']) == (OUTER['pid'], OUTER['birth'])
            and outer['prepared'] == str(prepared_path) and outer['controller_sha256'] == CONTROLLER_SHA,
            'Actual original outer owner/source differs')
    rows = [dict(role='outer', pid=OUTER['pid'], birth=OUTER['birth'], owner_record=outer_pin)]
    for leg in ('R1', 'C1'):
        job_pin = prepared['jobs'][leg]['job']
        job, _ = held_json(CASE / leg / 'job.json', inventory, job_pin)
        config, _ = held_json(CASE / leg / 'Root-original-C218-config.json', inventory, configs['configs'][leg])
        native, native_pin = held_json(CASE / leg / 'controller-execution-original01/root-original-identity.json', inventory)
        ctl, _ = held_json(CASE / leg / 'controller-execution-original01/root-original-result-and-owned-release.json', inventory)
        result, result_pin = held_json(CASE / leg / 'runtime-original01/result.json', inventory)
        result.pop('main_samples', None)  # Never follow individual Main/API sample references.
        unit = UNIT_PREFIX + leg.lower() + '-original01-20261031.service'
        require(native['observed_live'] is True and native['unit'] == config['unit'] == unit
                and native['timer'] == unit[:-8] + '.timer' and ctl['original'] == native
                and native['pid'] == result['lease']['owner_pid'] and native['starttime_ticks'] == result['lease']['owner_birth']
                and integer(native['pid']) and integer(native['starttime_ticks']), 'Original native controller/lease identity differs')
        require(config['argv'] == prepared['jobs'][leg]['argv'] and job['screen_selection'] == prepared['selection']
                and result['original_job'] == job_pin and result['leg'] == job['leg'] == leg,
                'Original job/config/result identity differs')
        require(type(ctl['original_exit']) is int and ctl['original_exit'] == 0
                and ctl['unit_released'] is ctl['lifecycle_complete'] is ctl['audit_success'] is True
                and ctl['payload_retried'] is False and ctl['error'] is None,
                'Original controller normal0/owned closure required')
        require(result['complete'] is True and result['errors'] == [] and result['main_health_failure'] is None
                and result['all_original_threads_stopped'] is result['original_lease_released'] is result['immutable_inputs_unchanged'] is True
                and result['original_post_origin_child_reap']['all_original_children_reaped'] is True,
                'Original native/writer/lease/reap closure required')
        require(set(result['original_slots']) == {str(s) for s in range(4096, 4128)}
                and set(result['original_post_origin_child_reap']['original_children']) == set(result['original_slots']), 'All32 original child records required')
        rows.append(dict(role='native', leg=leg, pid=native['pid'], birth=native['starttime_ticks'],
                         unit=unit, invocation_id=native['invocation_id'], owner_record=native_pin, native_result=result_pin))
        for slot in range(4096, 4128):
            actor, actor_pin = held_json(CASE / leg / 'runtime-original01/actors' / str(slot) / 'original-actor.json', inventory)
            final = result['original_slots'][str(slot)]
            reaped = result['original_post_origin_child_reap']['original_children'][str(slot)]
            require(type(actor['slot']) is int and actor['slot'] == slot and integer(actor['pid']) and integer(actor['starttime_ticks'])
                    and actor['pid'] == final['pid'] == reaped['pid']
                    and actor['starttime_ticks'] == final['birth'] == reaped['birth']
                    and actor['original_job'] == job_pin and actor['session'] == job['sessions'][str(slot)]
                    and actor['connection'] == job['connections'][str(slot)]
                    and actor['argv'][0] == job['mame']['path']
                    and type(final['actual_exit']) is int and final['actual_exit'] == reaped['actual_exit'],
                    'Original source-owned actor/job/transport/PID-birth/reap records differ')
            rows.append(dict(role='MAME', leg=leg, slot=slot, pid=actor['pid'], birth=actor['starttime_ticks'],
                             actual_exit=final['actual_exit'], owner_record=actor_pin))
    require(len(rows) == len({(v['pid'], v['birth']) for v in rows}) == 67, 'Exactly67 distinct original PID-birth identities required')
    return rows, prepared_pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-source-sha256')
    parser.add_argument('--Root-actual7081-terminal0', action='store_true')
    parser.add_argument('--terminal-record', type=Path)
    parser.add_argument('--terminal-record-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: require actual Root tool7081 terminal0; no evidence reads or outputs')
        return 0
    require(args.Root_actual7081_terminal0, 'Root must actually observe original tool7081 terminal0; not inferred from files')
    require(os.getuid() == 1001 and type(args.expected_source_sha256) is str
            and re.fullmatch('[0-9a-f]{64}', args.expected_source_sha256), 'Exact owned frozen checker SHA required')
    source_raw, source = immutable(Path(__file__).resolve())
    require(source['sha256'] == args.expected_source_sha256, 'Checker source SHA differs')
    require(args.terminal_record is not None and args.terminal_record.parent == CASE
            and args.terminal_record.suffix == '.json' and type(args.terminal_record_sha256) is str,
            'Exact case-local Root actual terminal record and digest required')
    require(OUTPUT.parent.resolve() == CASE and not OUTPUT.exists() and not OUTPUT.is_symlink(), 'One fresh exact case-local positive proof required')
    inventory = [source]
    terminal, terminal_pin = held_json(args.terminal_record, inventory)
    require(terminal_pin['sha256'] == args.terminal_record_sha256
            and type(terminal['original_tool_session']) is int and terminal['original_tool_session'] == 7081
            and type(terminal['actual_tool_result']['exit_code']) is int and terminal['actual_tool_result']['exit_code'] == 0,
            'Retained actual original tool7081 exit0 observation required')
    owners, prepared_pin = derive_original_owners(inventory)
    outer, outer_pin = held_json(CASE / 'Root-controller-runtime-original01/result.json', inventory)
    require(type(outer.get('actual_exit')) is int and outer['actual_exit'] == 0 and outer.get('error') is None
            and outer.get('reporter_thread_closed') is True and outer.get('report_update_errors') == []
            and outer.get('native_or_original_controller_retried') is False and outer.get('legs') == ['R1', 'C1'],
            'Original outer result is not clean unretried terminal0/report-thread closure')
    retained_before = observe_retained(); absent_before = observe_originals(owners)
    units = observe_units(); lease = probe_existing_lease()
    absent_after = observe_originals(owners); retained_after = observe_retained()
    for selected in inventory:
        immutable(Path(selected['path']), expected=selected)
    proof = dict(schema='robotron-Root-original-post-repair-LR625-pair-positive-closure-v1', observed_unix_s=time.time(),
        checker=source, prepared=prepared_pin, terminal_record=terminal_pin,
        Root_tool_handle_acknowledgements=dict(original7081_actual_terminal0=True,
            source='Explicit Root CLI observation plus retained actual_tool_result; never inferred from result-file completion'),
        outer_result=outer_pin, outer_actual_exit=outer['actual_exit'], original_pair_owner_count=67, original_recorder_owner_count=0,
        original_birth_observations_before=absent_before, original_birth_observations_after=absent_after,
        retained_owners_before=retained_before, retained_owners_after=retained_after,
        exact_original_units=units, existing_GPU0_lease=lease, source_and_owner_metadata_inventory=inventory,
        original_owner_records_scope='Source-owned original Popen/job/transport/controller metadata, not an independent historical live /proc census',
        child_exit_codes_normalized=False, independent_score_validation_performed=False,
        embedded_Main_summary_rows_discarded=True, individual_Main_or_API_sample_paths_followed=False,
        quality_or_promotion_claim=False, signals_stops_restarts_API_CONTROL_PUBLIC_actions=False)
    raw = (json.dumps(proof, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    directory = os.open(CASE, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    _, output_pin = immutable(OUTPUT)
    print(json.dumps(dict(status='POSITIVE_ORIGINAL_PAIR_CLOSURE_NO_EXTRA_RECORDER', proof=output_pin), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
