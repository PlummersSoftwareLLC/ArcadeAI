"""Prospective static-original192 health predicates. No import-time actions.

The publisher may recover faults for operations. A scientific case here never
adopts that replacement: it binds one completed original bootstrap and exactly
one original process/connection per slot for its whole lifetime.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat

MODE = 'CONTINUOUS_TRAIN155_EVAL37_ONCE'
SCHEMA = 'robotron-continuous-training-static192-snapshot-v2'
CASE_SCHEMA = 'robotron-continuous-static192-health-case-v1'
SLOTS = set(map(str, range(192)))
STATES = ('starting', 'active_train', 'active_eval', 'retiring_eval',
          'closed_eval', 'fault_cleanup', 'quarantined')
FIXED_SLOT = ('original_child', 'spawn_intent', 'original_child_receipt', 'connection_binding')
ORIGINAL_FIELDS = ('eval_only', 'incarnation', 'original_child', 'spawn_intent',
                   'original_child_receipt', 'connection_binding')
COMPACT_FIELDS = {'eval_only', 'incarnation', 'state', 'original_pid', 'original_birth',
                  'original_slot_sha256', 'natural_result', 'closure',
                  'prior_fault_closure', 'quarantine_reason', 'faults'}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'Finite nonnegative clock/counter required')
    return value


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def read_pin(value, *, as_json=True, immutable=True):
    """Full SHA/full stable8 identity of a bounded immutable actual event."""
    require(type(value) is dict and set(value) == {'path', 'sha256', 'bytes', 'identity'},
            'Exact full8 metadata pin required')
    path = Path(value['path'])
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Canonical immutable evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and identity(before) == value['identity']
                and before.st_uid == os.getuid() and before.st_nlink == 1
                and (not immutable or stat.S_IMODE(before.st_mode) == 0o444)
                and 0 <= before.st_size == value['bytes'] <= 2_000_000,
                'Immutable bounded regular event identity differs')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            raw = stream.read(2_000_001)
        require(len(raw) == value['bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256']
                and identity(os.fstat(fd)) == value['identity']
                and identity(path.lstat()) == value['identity'], 'Event bytes/identity changed')
    finally:
        os.close(fd)
    return json.loads(raw) if as_json else raw


def owner_join(owner, live):
    require(type(owner['pid']) is int and type(owner['birth']) is int
            and owner['pid'] > 0 and owner['birth'] > 0
            and owner['pid'] == live['process']['pid']
            and owner['birth'] == live['process']['starttime_ticks']
            and owner['unit'] == live['unit']
            and owner['invocation_id'] == live['invocation']
            and owner['cgroup'] == live['process']['cgroup'],
            'Registry owner does not name the actual original unit/process')


def event(case, value, kind, slot, incarnation=1):
    body = read_pin(value)
    c = case['continuous']
    require(body['schema'] == 'robotron-continuous-training-event-v1'
            and body['mode'] == MODE and body['epoch'] == c['epoch']
            and body['kind'] == kind and body['slot'] == slot
            and type(body['incarnation']) is int and body['incarnation'] == incarnation
            and body['supervisor'] == c['supervisor'] and body['trainer'] == c['trainer']
            and body['source_authority'] == c['source_authority'],
            'Event kind/slot/original incarnation/owner/source authority differs')
    number(body['unix_s']); number(body['monotonic_ns'])
    require(type(body['monotonic_ns']) is int, 'Integer event clock required')
    return body


def original(case, slot, row):
    c = case['continuous']; anchor = c['original_slots'][slot]
    require(all(row[key] == anchor[key] for key in FIXED_SLOT)
            and row['incarnation'] == 1 and type(row['incarnation']) is int
            and type(row['faults']) is int and row['faults'] == 0
            and row['prior_fault_closure'] is None and row['quarantine_reason'] is None,
            'Fixed context cannot adopt replacement, rebound connection or fault')
    child = row['original_child']
    require(set(child) == {'pid', 'birth', 'parent', 'cgroup', 'launch_argv', 'controlled_env'}
            and type(child['pid']) is int and child['pid'] > 0
            and type(child['birth']) is int and child['birth'] > 0
            and child['parent'] == c['supervisor']['pid']
            and child['cgroup'] == c['supervisor']['cgroup']
            and child['launch_argv'] == c['launch_argv']
            and child['controlled_env'] == expected_environment(case, slot),
            'Original child role/argv/environment/parent/cgroup differs')
    return child


def expected_environment(case, slot):
    return dict(case['actor_environment'], ROBOTRON_CLIENT_SLOT=slot,
                ROBOTRON_ACTOR_ROUND='1', ROBOTRON_EVAL_MODE='1' if case['slot_eval'][slot] else '2',
                ROBOTRON_RETIRE_AFTER_GAME='1' if case['slot_eval'][slot] else '0',
                ROBOTRON_PREVIEW_CLIENT='1' if slot == '0' else '0')


def original_digest(row):
    projection = {key: row[key] for key in ORIGINAL_FIELDS}
    raw = json.dumps(projection, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def slot_view(case, slot, compact):
    """Explicit compact-wire join; never modify the retained raw publisher."""
    anchor = case['continuous']['original_slots'][slot]
    require(set(compact) == COMPACT_FIELDS
            and type(compact['original_pid']) is int and type(compact['original_birth']) is int
            and compact['original_pid'] == anchor['original_child']['pid']
            and compact['original_birth'] == anchor['original_child']['birth']
            and compact['original_slot_sha256'] == original_digest(anchor)
            and compact['eval_only'] is anchor['eval_only']
            and type(compact['incarnation']) is int and compact['incarnation'] == anchor['incarnation'],
            'Compact slot is not this exact immutable original physical/source/role row')
    view = dict(anchor)
    view.update({key: compact[key] for key in ('state', 'natural_result', 'closure',
                 'prior_fault_closure', 'quarantine_reason', 'faults')})
    return view


def binding(case, slot, pin, child):
    body = event(case, pin, 'physical-connection', int(slot))
    value = body['data']; actor = value['actor']; conn = value['connection']
    expected = expected_environment(case, slot)
    require(value['previous_binding'] is None
            and actor['pid'] == child['pid'] and actor['birth'] == child['birth']
            and actor['parent'] == child['parent'] and actor['cgroup'] == child['cgroup']
            and actor['uid'] == os.getuid() and actor['command'] == case['actor_command']
            and actor['exe'] == case['actor_executable']['path']
            and actor['environment'] == expected,
            'Initial physical connection lacks original exact MAME/role evidence')
    require(type(conn['client_slot']) is int and conn['client_slot'] == int(slot)
            and type(conn['client_id']) is int and conn['client_id'] >= 0
            and type(conn['eval_only']) is bool and conn['eval_only'] is case['slot_eval'][slot]
            and type(conn['connection_ns']) is int and conn['connection_ns'] > 0
            and type(conn['token']) is str and 1 <= len(conn['token']) <= 128,
            'Physical connection slot/role/CID/token differs')
    tcp = value['process_owned_TCP']
    require(type(tcp['inode']) is int and tcp['inode'] > 0
            and tcp['local'] == conn['socket_endpoints']['peer']
            and tcp['remote'] == conn['socket_endpoints']['server']
            and tcp['remote'][1] == 9998, 'Initial process-owned TCP endpoint join differs')
    return conn


def validate_case(case):
    require(case['schema'] == CASE_SCHEMA and set(case['slot_eval']) == SLOTS
            and all(type(x) is bool for x in case['slot_eval'].values())
            and sum(case['slot_eval'].values()) == 37, 'Exact fixed155TRAIN/37EVAL case required')
    c = case['continuous']
    require(c['mode'] == MODE and set(c['original_slots']) == SLOTS
            and set(c['input_environment_by_slot']) == SLOTS
            and type(c['policy_generation']) is int and c['policy_generation'] >= 0
            and c['accepted_profile'] == 'STATIC_ORIGINAL192_NO_FAULT_ADOPTION'
            and c['maximum_proof_gap_s'] == 2.0 and c['narrow_API_exception_TTL_s'] == .5,
            'Explicit prospective static-original192 profile required')
    require(Path(c['snapshot_path']).is_absolute()
            and Path(c['snapshot_path']).name == 'status.json'
            and str(Path(c['snapshot_path']).parent) == case['round_root'],
            'Existing worker status path must select this exact continuous publisher')
    owner_join(c['supervisor'], case['owners']['fleet'])
    owner_join(c['trainer'], case['owners']['trainer'])
    require(case['owners']['trainer']['process']['environment']['ROBOTRON_CONTINUOUS_TRAINING_MODE'] == '1'
            and case['actor_environment']['ROBOTRON_SOCKET_ADDRESS'] == 'dell:9998'
            and set(case['recipe']) == {'lr', 'epsilon', 'expert_ratio'}
            and all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in case['recipe'].values())
            and case['actor_command'][0] == case['actor_executable']['path'] == '/usr/games/mame'
            and case['actor_executable']['path'] in case['inputs'],
            'Exact source-mode1 main, fixed live recipe and literal MAME/socket required')
    require(c['epoch'] == '%s:%s:%s' % (c['supervisor']['pid'], c['supervisor']['birth'],
                                      c['supervisor']['invocation_id']), 'Supervisor epoch differs')
    rolemap = read_pin(c['rolemap'])
    require(rolemap['slot_eval'] == case['slot_eval'], 'Immutable192 role authority differs')
    source = read_pin(c['source_authority'])
    require(source['schema'] == 'robotron-root-continuous-main-startup-qualified-v1'
            and source['trainer'] == c['trainer']
            and source['all_model_optimizer_replay_banks_clocks_preserved'] is True
            and source['new_mode_source_and_CPU_qualified'] is True
            and source['actual_CPU_scope_closeouts'], 'Actual qualified continuous startup/source authority required')
    for entry in source['actual_CPU_scope_closeouts']:
        close = read_pin(entry)
        require(close['actual_exit'] == 0 and close['status'] == 'PASS_ENGINEERING_ONLY',
                'Original closed actual CPU qualification required')
    for key in ('supervisor', 'trainer'):
        read_pin(c[key]['source'], as_json=False, immutable=False)
    require(set(c['server_stamp']) == {'pid', 'birth', 'source_sha256'}
            and c['server_stamp'] == c['trainer']['server_stamp']
            and c['server_stamp']['pid'] == c['trainer']['pid']
            and c['server_stamp']['birth'] == c['trainer']['birth'], 'Original server stamp differs')
    require(c['source_pins'] and len({entry['path'] for entry in c['source_pins']}) == len(c['source_pins']),
            'Distinct actual installed/source input pins required')
    for entry in c['source_pins']:
        require(case['inputs'].get(entry['path']) == dict(sha256=entry['sha256'], identity=entry['identity']),
                'Continuous source must remain an ordinary fully held case input')
        read_pin(entry, as_json=False, immutable=False)
    held = {entry['path']: entry for entry in c['source_pins']}
    require(all(c[key]['source']['path'] in held and held[c[key]['source']['path']] == c[key]['source']
                for key in ('supervisor', 'trainer'))
            and any(entry['sha256'] == c['server_stamp']['source_sha256'] for entry in c['source_pins']),
            'Actual supervisor/main/server source stamps must be ordinary held source inputs')
    barrier = event(case, c['initial_barrier'], 'initial-all192-barrier', None, 0)
    membership = event(case, c['original_membership'], 'original192-membership', None, 0)
    require(membership['data']['original_slots'] == c['original_slots']
            and membership['monotonic_ns'] <= barrier['monotonic_ns'],
            'Immutable original192 membership differs from the actual bootstrap barrier')
    b = barrier['data']
    require(b['slots'] == list(range(192)) and b['slot_eval'] == case['slot_eval']
            and b['original_membership'] == c['original_membership']
            and set(b['physical_connections']) == SLOTS,
            'No complete immutable original192 physical bootstrap barrier')
    births, cids, tokens = set(), set(), set()
    for slot, row in c['original_slots'].items():
        require(set(row) == set(ORIGINAL_FIELDS) and row['eval_only'] is case['slot_eval'][slot],
                'Immutable original row fields/role differ')
        child = original(case, slot, dict(row, faults=0, prior_fault_closure=None, quarantine_reason=None))
        require(b['physical_connections'][slot] == row['connection_binding'],
                'Barrier lacks this original physical connection')
        intent = event(case, row['spawn_intent'], 'spawn-intent', int(slot))
        spawned = event(case, row['original_child_receipt'], 'original-child', int(slot))
        input_env = c['input_environment_by_slot'][slot]
        require(input_env['ROBOTRON_CLIENT_SLOT'] == slot and input_env['ROBOTRON_ACTOR_ROUND'] == '1'
                and input_env['ROBOTRON_EVAL_MODE'] == '0' and input_env['ROBOTRON_PREVIEW_FPS'] == '30'
                and input_env['ROBOTRON_RETIRE_AFTER_GAME'] == ('1' if case['slot_eval'][slot] else '0'),
                'Literal original role-wrapper INPUT controls differ')
        policy = intent['data']['policy']
        require(policy['schema'] == 'robotron-continuous-main-policy-v1'
                and policy['server_stamp'] == c['server_stamp']
                and policy['continuous_training_mode'] is True and policy['main_measurement_entry_disabled'] is True
                and policy['measurement_active'] is False and policy['ratchet_frozen'] is False
                and policy['replay_admission_open'] is True and policy['consumer_error'] is None
                and policy['training_enabled'] is True and type(policy['measurement_generation']) is int
                and policy['measurement_generation'] == c['policy_generation']
                and 0 <= intent['monotonic_ns'] - policy['observed_monotonic_ns'] <= 2_000_000_000,
                'Original spawn lacked the fresh actual permanent main-policy fence')
        # The original Popen receipt precedes controlled OUTPUT env capture.
        initial = dict(child, controlled_env=None)
        require(spawned['data']['original_child'] == initial
                and spawned['data']['spawn_intent'] == row['spawn_intent']
                and intent['data']['argv'] == c['launch_argv']
                and intent['data']['input_environment'] == c['input_environment_by_slot'][slot]
                and intent['data']['previous_closure'] is None
                and intent['monotonic_ns'] <= spawned['monotonic_ns'] <= barrier['monotonic_ns'],
                'Original Popen/spawn chronology or literal argv differs')
        conn = binding(case, slot, row['connection_binding'], child)
        bound = event(case, row['connection_binding'], 'physical-connection', int(slot))
        require(spawned['monotonic_ns'] <= bound['monotonic_ns'] <= barrier['monotonic_ns']
                and bound['monotonic_ns'] - spawned['monotonic_ns'] <= 5_000_000_000,
                'Original retained Popen did not reach exact physically bound MAME within5s')
        pair = (child['pid'], child['birth'])
        require(pair not in births and conn['client_id'] not in cids and conn['token'] not in tokens,
                'Duplicate original physical birth/CID/connection token')
        births.add(pair); cids.add(conn['client_id']); tokens.add(conn['token'])
    return c


def natural(case, slot, row):
    outer = event(case, row['natural_result'], 'natural-result', int(slot))
    data = outer['data']; result = data['result']
    raw = read_pin(data['raw_line'], as_json=False)
    require(raw.endswith(b'\n') and raw.count(b'\n') == 1 and json.loads(raw) == result
            and data['natural_complete'] is True
            and all(result[k] is True for k in ('complete', 'eligible', 'known_start'))
            and result['boundary_reason'] in ('score_reset', 'zero_score_restart')
            and type(result['client_slot']) is int and result['client_slot'] == int(slot)
            and result['eval_only'] is True and type(result['score']) is int and result['score'] >= 0
            and type(result['journal_game_id']) is str and result['journal_game_id']
            and number(result['start_unix_s']) < number(result['end_unix_s']) <= outer['unix_s'],
            'EVAL retirement lacks one committed eligible full natural journal row')
    conn = binding(case, slot, row['connection_binding'], row['original_child'])
    require(type(result['client_id']) is int and result['client_id'] == conn['client_id'],
            'Natural result belongs to another original connection')
    intent = event(case, row['spawn_intent'], 'spawn-intent', int(slot))
    require(result['start_unix_s'] >= intent['unix_s']
            and result['start_context']['measurement_generation'] == case['continuous']['policy_generation']
            and result['start_context']['measurement_active'] is False and result['start_context']['ratchet_frozen'] is False,
            'Natural EVAL game predates this original spawn or crosses the fixed main-policy mode')
    return outer, result


def closed(case, slot, row, natural_event, result):
    outer = event(case, row['closure'], 'original-reaped-closure', int(slot))
    data = outer['data']; child = row['original_child']
    require(type(data['actual_exit']) is int and data['actual_exit'] == 0
            and data['original_pid'] == child['pid'] and data['original_birth'] == child['birth']
            and data['original_wait_reaped'] is True and data['original_birth_absent'] is True
            and data['natural_result'] == row['natural_result'] and data['restart_censored'] is False
            and natural_event['monotonic_ns'] <= outer['monotonic_ns'],
            'EVAL closure is not its original normal0/wait/reap/absence')
    conn = binding(case, slot, row['connection_binding'], child)
    receipts = data['connection_cleanup']
    require(len(receipts) == 1, 'Static original connection must have one cleanup receipt')
    receipt = receipts[0]
    positive = ('original_handler_stopped', 'original_owned_timer_stopped',
                'owned_timer_callback_succeeded', 'journal_disconnect_succeeded',
                'FIFO_reset_executed', 'replay_consumer_healthy', 'ready_for_external_join')
    require(receipt['schema'] == 'robotron-prospective-connection-cleanup-receipt-v2'
            and receipt['server_stamp'] == case['continuous']['server_stamp']
            and receipt['token'] == conn['token'] and receipt['client_id'] == conn['client_id']
            and receipt['connection_ns'] == conn['connection_ns']
            and receipt['socket_endpoints'] == conn['socket_endpoints']
            and receipt['client_slot'] == int(slot) and receipt['eval_only'] is True
            and all(receipt[k] is True for k in positive) and receipt['cleanup_error'] is None
            and receipt['terminal_receipt'] == result
            and receipt['terminal_line_sha256'] == natural_event['data']['raw_line']['sha256'],
            'EVAL closure lacks original connection Thread/Timer/FIFO/raw-line cleanup join')
    return outer


def validate_snapshot(case, sample, previous=None):
    """Typed publisher partition. Every physical predicate is checked separately."""
    c = case['continuous']; value = sample['status']
    require(value['schema'] == SCHEMA and value['mode'] == MODE and value['epoch'] == c['epoch']
            and value['supervisor'] == c['supervisor'] and value['trainer'] == c['trainer']
            and value['rolemap'] == c['rolemap'] and value['source_authority'] == c['source_authority']
            and value['original_membership'] == c['original_membership']
            and value['errors'] == [] and type(value['errors']) is list and set(value['slots']) == SLOTS,
            'Wrong/stale/partial/faulted continuous192 publisher authority')
    require(0 <= number(sample['unix_s']) - number(value['updated_unix_s']) <= 2
            and type(value['updated_monotonic_ns']) is int
            and 0 <= sample['monotonic_s'] - value['updated_monotonic_ns']/1e9 <= 2,
            'Continuous publisher is future or stale')
    admission = value['initial_admission']
    require(admission['complete'] is True and admission['slots_ever_bound'] == list(range(192))
            and admission['immutable_all192_barrier'] == c['initial_barrier'],
            'Scientific health never precedes the complete original192 barrier')
    counts = {state: 0 for state in STATES}; naturals = {}; closed_slots = set(); retiring = set()
    slots = {slot: slot_view(case, slot, row) for slot, row in value['slots'].items()}
    for slot, row in slots.items():
        require(type(row['eval_only']) is bool and row['eval_only'] is case['slot_eval'][slot],
                'Fixed slot role changed')
        original(case, slot, row)
        require(row['state'] in STATES, 'Unknown continuous slot state')
        counts[row['state']] += 1
        if not row['eval_only']:
            require(row['state'] == 'active_train' and row['natural_result'] is row['closure'] is None,
                    'TRAIN must stay active in its original process across games')
        else:
            require(row['state'] in ('active_eval', 'retiring_eval', 'closed_eval'),
                    'EVAL cannot restart or enter a fault state within a fixed case')
            if row['state'] == 'active_eval':
                require(row['natural_result'] is row['closure'] is None, 'Active EVAL already retired')
            else:
                outer, result = natural(case, slot, row); naturals[slot] = (outer, result)
                if row['state'] == 'retiring_eval':
                    require(row['closure'] is None and 0 <= sample['unix_s'] - outer['unix_s'] <= 10,
                            'EVAL retirement is stuck or already closed')
                    retiring.add(slot)
                else:
                    closed(case, slot, row, outer, result); closed_slots.add(slot)
        if previous is not None:
            old = previous['status']['slots'][slot]
            order = {'active_eval': 0, 'retiring_eval': 1, 'closed_eval': 2}
            require(not row['eval_only'] or order[row['state']] >= order[old['state']],
                    'EVAL retirement state regressed')
            for field in ('natural_result', 'closure'):
                require(old[field] is None or row[field] == old[field], 'Immutable EVAL evidence changed')
    require(value['counts'] == counts and all(type(x) is int for x in value['counts'].values())
            and counts['active_train'] == 155
            and counts['active_eval'] + counts['retiring_eval'] + counts['closed_eval'] == 37,
            'Typed active/retiring/closed partition is not exactly155TRAIN+37EVAL')
    return dict(retiring=retiring, closed=closed_slots, naturals=naturals, counts=counts, slots=slots)


if __name__ == '__main__':
    print('SOURCE_ONLY_INERT_NO_READS_WRITES_PROBES_OR_ACTIONS')
