"""Prospective static-original192 health predicates. No import-time actions.

The physical cohort keeps all original process identities. TRAIN may reconnect
through freshly proved current owned TCP; EVAL retains its original connection
and strict once-only natural retirement. No replacement actor is adopted.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

MODE = 'CONTINUOUS_TRAIN155_EVAL37_ONCE'
SCHEMA = 'robotron-original192-immutable-bootstrap-projection-v4'
CASE_SCHEMA = 'robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
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


def completed_prefix(case):
    """Exact immutable old-cohort bytes; never an authority for new EVAL rows."""
    c=case['continuous'];record_pin=c['completed_clients_prefix'];value=read_pin(record_pin)
    require(set(value)=={'schema','canonical_path','canonical_identity','archive','prefix_bytes',
                        'prefix_sha256','cohort_min_spawn_unix_s'}
            and value['schema']=='robotron-prior-cohort-EVAL-completed-prefix-v1'
            and value['canonical_path']==str(Path(c['eval_journal_directory'])/'completed_clients.jsonl')
            and set(value['canonical_identity'])=={'device','inode','mode','uid','nlink'}
            and value['canonical_identity']['uid']==os.getuid()
            and value['canonical_identity']['nlink']==1
            and type(value['prefix_bytes'])is int and 0<=value['prefix_bytes']<=262144
            and value['archive']['bytes']==value['prefix_bytes']
            and value['archive']['sha256']==value['prefix_sha256'],
            'Exact immutable prior-cohort completed prefix authority required')
    for entry in (record_pin,value['archive']):
        require(case['inputs'].get(entry['path'])==dict(sha256=entry['sha256'],identity=entry['identity']),
                'Completed-prefix record/archive must be exact held inputs')
    raw=read_pin(value['archive'],as_json=False)
    require(len(raw)==value['prefix_bytes'] and hashlib.sha256(raw).hexdigest()==value['prefix_sha256']
            and (not raw or raw.endswith(b'\n')),'Prior completed prefix bytes/commit boundary differs')
    cutoff=number(value['cohort_min_spawn_unix_s']);require(cutoff>0,'Actual new-cohort spawn cutoff required')
    for line in raw.splitlines(keepends=True):
        row=json.loads(line)
        require(number(row['start_unix_s'])<number(row['end_unix_s'])<cutoff,
                'Skipped completed row is not strictly before the new cohort')
    return value,raw


def validate_completed_prefix_capture(case,sample):
    value,raw=completed_prefix(case);capture=sample['EVAL_completed_prefix_capture']
    require(capture['record']==case['continuous']['completed_clients_prefix']
            and capture['canonical_path']==value['canonical_path']
            and capture['raw_prefix_wire'].encode()==raw
            and capture['prefix_bytes']==value['prefix_bytes']
            and capture['prefix_sha256']==value['prefix_sha256']
            and all(capture['canonical_identity'][k]==v for k,v in value['canonical_identity'].items())
            and type(capture['canonical_identity']['bytes'])is int
            and value['prefix_bytes']<=capture['canonical_identity']['bytes']<=262144
            and sample['capture_started_monotonic_s']<=number(capture['before_monotonic_s'])
            <=number(capture['after_monotonic_s'])<=sample['capture_ended_monotonic_s']<=sample['monotonic_s'],
            'Actual completed prefix capture/identity/bytes/bracket differs')
    return value


def validate_case(case):
    require(case['schema'] == CASE_SCHEMA and set(case['slot_eval']) == SLOTS
            and all(type(x) is bool for x in case['slot_eval'].values())
            and sum(case['slot_eval'].values()) == 37, 'Exact fixed155TRAIN/37EVAL case required')
    c = case['continuous']
    require(c['mode'] == MODE and set(c['original_slots']) == SLOTS
            and set(c['input_environment_by_slot']) == SLOTS
            and type(c['policy_generation']) is int and c['policy_generation'] >= 0
            and c['accepted_profile'] == 'PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
            and c['maximum_proof_gap_s'] == 2.0 and c['narrow_API_exception_TTL_s'] == .5,
            'Explicit prospective static-original192 profile required')
    require(Path(c['snapshot_path']).is_absolute()
            and Path(c['snapshot_path']).name == 'status.json'
            and str(Path(c['snapshot_path']).parent) == case['round_root'],
            'Historical supervisor output provenance must remain exact')
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
    require(all(held.get(entry['path'])==entry for entry in source['canonical_sources']),
            'Every qualified actual canonical source must remain an exact ordinary held input')
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
    prefix,_=completed_prefix(case)
    births, cids, tokens = set(), set(), set()
    spawn_starts=[]
    for slot, row in c['original_slots'].items():
        require(set(row) == set(ORIGINAL_FIELDS) and row['eval_only'] is case['slot_eval'][slot],
                'Immutable original row fields/role differ')
        child = original(case, slot, dict(row, faults=0, prior_fault_closure=None, quarantine_reason=None))
        require(b['physical_connections'][slot] == row['connection_binding'],
                'Barrier lacks this original physical connection')
        intent = event(case, row['spawn_intent'], 'spawn-intent', int(slot))
        spawn_starts.append(number(intent['unix_s']))
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
    require(prefix['cohort_min_spawn_unix_s']==min(spawn_starts),
            'Historical-prefix cutoff is not the actual earliest new original spawn')
    require(Path(c['eval_journal_directory']).is_absolute(), 'Exact ordinary main journal directory required')
    witness=c.get('eval_exit_witness')
    require(witness is not None, 'Explicit retained original37 pidfd authority required')
    if witness is not None:
        require(set(witness)=={'selection','source','anchors','output','holder'}
                and witness['source']['sha256']=='fe306753c9cbb20e715b76d60c116ef9ce47a768c1a1afe0b00c03eac02a095c',
                'Exact prospective retained-kernel witness source required')
        read_pin(witness['source'],as_json=False)
        anchors=read_pin(witness['anchors']);selected=read_pin(witness['selection'])
        require(anchors['schema']=='robotron-original37-EVAL-pidfd-held-anchors-v1'
                and anchors['source']==witness['source'] and anchors['selection']==witness['selection']
                and anchors['holder']==witness['holder']
                and anchors['all37_acquired_while_originals_live'] is True
                and set(anchors['originals'])=={s for s in SLOTS if case['slot_eval'][s]}
                and Path(witness['anchors']['path'])==Path(witness['output'])/'held-original37-anchors.json'
                and selected['output']==witness['output'], 'Actual held-before-exit37 witness authority differs')
        for slot,anchor in anchors['originals'].items():
            child=c['original_slots'][slot]['original_child'];value=anchor['original']
            require(all(value[k]==child[k] for k in ('pid','birth','parent'))
                    and value['uid']==os.getuid()
                    and value['initial_connection_binding']==c['original_slots'][slot]['connection_binding'],
                    'Held pidfd anchor is not an exact original EVAL physical/connection identity')
        require(case['inputs'].get(witness['source']['path'])==dict(sha256=witness['source']['sha256'],identity=witness['source']['identity']),
                'Kernel witness source must be an ordinary fully held input')
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


def original_physical(case, slot, row):
    """Keep physical/source ownership; operational TRAIN labels are not truth."""
    anchor = case['continuous']['original_slots'][slot]
    require(all(row[key] == anchor[key] for key in ORIGINAL_FIELDS),
            'Runtime compact row no longer names its immutable original physical anchor')
    child = row['original_child']; c = case['continuous']
    require(child['parent'] == c['supervisor']['pid'] and child['cgroup'] == c['supervisor']['cgroup']
            and child['launch_argv'] == c['launch_argv']
            and child['controlled_env'] == expected_environment(case,slot)
            and anchor['incarnation'] == 1, 'Original physical/source role changed')
    return child


def current_connections(case, sample):
    rows = sample['connections_capture']['value']['connections']
    require(type(rows) is list and len(rows) <= 192, 'Bounded current handler rows required')
    result = {}; cids = set(); tokens = set(); endpoints = set()
    for row in rows:
        require(set(row) == {'token','client_id','client_slot','eval_only','connection_ns','socket_endpoints'}
                and type(row['client_slot']) is int and 0 <= row['client_slot'] < 192
                and type(row['client_id']) is int and row['client_id'] >= 0
                and type(row['eval_only']) is bool
                and type(row['connection_ns']) is int and 0 < row['connection_ns'] <= sample['connections_capture']['value']['observed_monotonic_ns']
                and type(row['token']) is str and 1 <= len(row['token']) <= 128,
                'Strict current handler identity fields required')
        slot = str(row['client_slot']); pair = row['socket_endpoints']
        require(row['eval_only'] is case['slot_eval'][slot]
                and set(pair) == {'peer','server'}
                and all(type(pair[k]) is list and len(pair[k]) == 2
                    and type(pair[k][0]) is str and type(pair[k][1]) is int
                    and 0 < pair[k][1] <= 65535 for k in pair)
                and pair['server'][1] == 9998, 'Current slot role/socket endpoint differs')
        endpoint = (tuple(pair['peer']),tuple(pair['server']))
        require(slot not in result and row['client_id'] not in cids
                and row['token'] not in tokens and endpoint not in endpoints,
                'Duplicate current slot/CID/token/socket pair')
        if case['slot_eval'][slot]:
            old = case['continuous']['original_slots'][slot]
            require(row == binding(case,slot,old['connection_binding'],old['original_child']),
                    'EVAL changed its original one-game connection')
        result[slot] = row;cids.add(row['client_id']);tokens.add(row['token']);endpoints.add(endpoint)
    return result


def eval_natural(case, sample, slot, row, previous=None, completed=None):
    """Independent exact producer lines; never backdate a supervisor event."""
    evidence = sample.get('EVAL_journal_evidence',{}).get(slot)
    if evidence is None:
        require(row['natural_result'] is None, 'Published EVAL natural row lacks independent journal evidence')
        return None
    require(case['slot_eval'][slot] is True and evidence['schema'] == 'robotron-independent-original-EVAL-journal-evidence-v1',
            'Only original EVAL may have independent natural completion evidence')
    raw = evidence['raw_line'].encode(); result = json.loads(raw)
    require(raw.endswith(b'\n') and raw.count(b'\n') == 1
            and hashlib.sha256(raw).hexdigest() == evidence['raw_line_sha256']
            and raw == (json.dumps(result,allow_nan=False,separators=(',',':'))+'\n').encode()
            and evidence['main_raw_line'] == evidence['raw_line']
            and evidence['retirement_raw_line'] == evidence['raw_line']
            and evidence['main_path'] == str(Path(case['continuous']['eval_journal_directory'])/'games.jsonl')
            and evidence['retirement_path'] == str(Path(case['continuous']['eval_journal_directory'])/'completed_clients.jsonl'),
            'Exact fsynced main/retirement canonical journal-line join differs')
    prefix=completed if completed is not None else completed_prefix(case)[0]
    require(type(evidence['retirement_line_offset'])is int
            and evidence['retirement_line_offset']>=prefix['prefix_bytes']
            and type(evidence['retirement_prefix_identity']['bytes'])is int
            and evidence['retirement_line_offset']+len(raw)<=evidence['retirement_prefix_identity']['bytes']<=262144
            and all(evidence['retirement_prefix_identity'][k]==v for k,v in prefix['canonical_identity'].items()),
            'New EVAL evidence is not within the exact current-cohort journal suffix')
    original = case['continuous']['original_slots'][slot]
    conn = binding(case,slot,original['connection_binding'],original['original_child'])
    spawn = event(case,original['spawn_intent'],'spawn-intent',int(slot))
    require(all(result.get(k) is True for k in ('complete','eligible','known_start'))
            and result['eval_only'] is True and type(result['client_slot']) is int
            and result['client_slot'] == int(slot) and type(result['client_id']) is int
            and result['client_id'] == conn['client_id']
            and result['boundary_reason'] in ('score_reset','zero_score_restart')
            and type(result['score']) is int and result['score'] >= 0
            and type(result['journal_game_id']) is str and result['journal_game_id']
            and spawn['unix_s'] <= number(result['start_unix_s']) < number(result['end_unix_s'])
            <= number(evidence['first_observed_unix_s']) <= sample['unix_s']
            and number(evidence['first_observed_monotonic_s']) <= sample['monotonic_s']
            and result['start_context']['measurement_generation'] == case['continuous']['policy_generation']
            and result['start_context']['measurement_active'] is False
            and result['start_context']['ratchet_frozen'] is False,
            'Independent row is not this original known-start eligible EVAL/fixed policy')
    if previous is not None and slot in previous.get('EVAL_journal_evidence',{}):
        old = previous['EVAL_journal_evidence'][slot]
        require(evidence == old, 'Original EVAL evidence changed or observation clock renewed')
    if row['natural_result'] is not None:
        old_event, old_result = natural(case,slot,row)
        require(old_result == result and old_event['data']['raw_line']['sha256'] == evidence['raw_line_sha256'],
                'Legacy natural producer conflicts with exact independent journal')
    return evidence, result


def classify_cleanup_postconditions(value):
    """Pure current component facts; never rewrite raw error/ready or grant reuse.

    The exception category proves eventual quiescence only. It does not prove
    the original wait met its deadline or identify the exception subtype.
    Overall closed-EVAL acceptance additionally requires the original kernel
    normal0/reap/birth-absence, natural journal and current no-TCP proofs.
    """
    flags=('original_handler_stopped','original_owned_timer_stopped','owned_timer_callback_succeeded',
           'journal_disconnect_succeeded','FIFO_reset_executed','replay_consumer_healthy')
    require(all(type(value.get(key))is bool for key in flags)
            and type(value.get('ready_for_external_join'))is bool,
            'Typed actual cleanup primitive/ready facts required')
    error=value['cleanup_error'];ready=value['ready_for_external_join'];complete=all(value[key]is True for key in flags)
    if error is None:
        require(not ready or complete,'Original ready flag contradicts cleanup primitives')
        category='ORDINARY_CLEANUP_COMPLETED'if complete and ready else'CLEANUP_INCOMPLETE'
        proved=complete and ready
    else:
        require(error=='Original connection cleanup failed' and type(error)is str
                and ready is False and complete and value.get('replay_admission_open')is True,
                'Unknown cleanup error or incomplete historical-exception postconditions')
        category='CURRENT_ONCE_ONLY_EVAL_QUIESCENCE_AFTER_RECORDED_DISCONNECT_EXCEPTION';proved=True
    return dict(classification=category,current_postconditions_proved=proved,
        historical_cleanup_error=error,original_ready_for_external_join=ready,
        original_cleanup_success_or_CID_reuse_claimed=False,
        original_deadline_or_wait_exception_subtype_proved=False,
        refill_external_handoff_or_reservation_release_authorized=False)


def require_fresh_replay_admission(case,sample):
    """Same source-bound policy proof, explicitly required for the new category."""
    capture=sample['policy_capture'];value=capture['value'];raw=capture['raw_wire'].encode()
    require(hashlib.sha256(raw).hexdigest()==capture['sha256'] and json.loads(raw)==value
            and value['schema']=='robotron-continuous-main-policy-v1'
            and value['server_stamp']==case['continuous']['server_stamp']
            and type(capture['before_monotonic_ns'])is int and type(capture['after_monotonic_ns'])is int
            and type(value['observed_monotonic_ns'])is int
            and capture['before_monotonic_ns']<=value['observed_monotonic_ns']<=capture['after_monotonic_ns']
            and capture['after_monotonic_ns']/1e9<=sample['monotonic_s']
            and 0<=sample['monotonic_s']-capture['before_monotonic_ns']/1e9<=2
            and 0<=number(sample['unix_s'])-number(value['observed_unix_s'])<=2
            and value['continuous_training_mode']is True and value['main_measurement_entry_disabled']is True
            and value['measurement_active']is False and value['ratchet_frozen']is False
            and type(value['measurement_generation'])is int
            and value['measurement_generation']==case['continuous']['policy_generation']
            and value['training_enabled']is True and value['replay_admission_open']is True
            and value['consumer_error']is None,
            'Historical cleanup exception requires fresh original healthy/open replay admission')


def eval_cleanup(case, sample, slot, result, evidence, *, require_ready=True):
    capture = sample.get('EVAL_cleanup_captures',{}).get(slot)
    require(capture is not None, 'Absent/retiring EVAL lacks its actual original cleanup capture')
    raw = capture['raw_wire'].encode(); value = capture['value']
    require(hashlib.sha256(raw).hexdigest() == capture['sha256'] and json.loads(raw) == value
            and capture['before_monotonic_ns'] <= value['observed_monotonic_ns'] <= capture['after_monotonic_ns']
            and capture['after_monotonic_ns']/1e9 <= sample['monotonic_s']
            and 0 <= sample['monotonic_s']-capture['before_monotonic_ns']/1e9 <= 2,
            'Original EVAL cleanup raw capture is future/unbracketed/stale')
    original=case['continuous']['original_slots'][slot]
    conn=binding(case,slot,original['connection_binding'],original['original_child'])
    positive=('original_handler_stopped','original_owned_timer_stopped','owned_timer_callback_succeeded',
              'journal_disconnect_succeeded','FIFO_reset_executed','replay_consumer_healthy','ready_for_external_join')
    require(value['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
            and value['server_stamp']==case['continuous']['server_stamp']
            and value['token']==conn['token'] and value['client_id']==conn['client_id']
            and value['client_slot']==int(slot) and value['eval_only'] is True
            and value['connection_ns']==conn['connection_ns'] and value['socket_endpoints']==conn['socket_endpoints']
            and all(type(value[k]) is bool for k in positive),
            'Original EVAL cleanup raw identity/role/terminal source differs')
    if value['terminal_receipt'] is not None:
        require(value['terminal_receipt']==result and value['terminal_line_sha256']==evidence['raw_line_sha256'],
                'Original EVAL cleanup terminal conflicts with the exact raw journal line')
    derived=classify_cleanup_postconditions(value)
    if derived['classification']=='CURRENT_ONCE_ONLY_EVAL_QUIESCENCE_AFTER_RECORDED_DISCONNECT_EXCEPTION':
        require(case['continuous']['accepted_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
                and case['continuous']['server_stamp']['source_sha256']=='a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423'
                and value['replay_admission_open']is True,
                'Only the exact selected a076 once-only EVAL postcondition domain is authorized')
        require_fresh_replay_admission(case,sample)
    if require_ready or derived['current_postconditions_proved']:
        require(derived['current_postconditions_proved']is True and value['terminal_receipt']==result
                and value['terminal_line_sha256']==evidence['raw_line_sha256'],
                'Original EVAL natural terminal lacks current positive Thread/Timer/FIFO closure')
    return derived


def kernel_eval_exit(case, sample, slot):
    selected=case['continuous'].get('eval_exit_witness')
    pin=sample.get('EVAL_kernel_exit_receipts',{}).get(slot)
    require(selected is not None and pin is not None, 'No original positive EVAL exit/reap witness')
    publication=sample['EVAL_exit_witness_capture']['publication']['value']
    require(publication['exit_receipts'].get(slot)==pin,
            'Kernel exit file was not published after its producer fsync returned')
    anchors=read_pin(selected['anchors']); selection=read_pin(selected['selection']); value=read_pin(pin)
    require(anchors['schema']=='robotron-original37-EVAL-pidfd-held-anchors-v1'
            and anchors['selection']==selected['selection'] and anchors['source']==selected['source']
            and anchors['holder']==selected['holder'] and anchors['all37_acquired_while_originals_live'] is True
            and value['schema']=='robotron-original-EVAL-retained-pidfd-exit-v1'
            and value['anchors']==selected['anchors'] and value['selection']==selected['selection']
            and value['source']==selected['source'] and value['holder']==selected['holder']
            and value['nonce']==anchors['nonce']==selection['nonce']
            and value['slot']==int(slot) and value['anchor']==anchors['originals'][slot]
            and value['original']==selection['originals'][slot]
            and value['descriptor']==value['anchor']['descriptor']
            and value['request_ioctl']==0xc050ff0b and value['request_mask']==0x28
            and value['original_Popen_wait_called_claimed'] is False
            and value['actor_signals_or_wait_or_reap_performed'] is False,
            'Source-bound held-before-exit kernel EVAL authority differs')
    old=case['continuous']['original_slots'][slot]; child=old['original_child']; original=value['original']
    require(original['pid']==child['pid'] and original['birth']==child['birth']
            and original['parent']==child['parent'] and original['uid']==os.getuid()
            and original['initial_connection_binding']==old['connection_binding']
            and Path(pin['path'])==Path(selected['output'])/('exit-slot-%03d.json'%int(slot)),
            'Kernel receipt is not the original selected EVAL birth/connection/path')
    raw=bytes.fromhex(value['returned_raw80_hex']); initial=bytes.fromhex(value['anchor']['initial_info']['raw80_hex'])
    require(len(raw)==len(initial)==80 and value['returned_info']['raw80_hex']==value['returned_raw80_hex'],
            'Exact80-byte retained kernel buffers required')
    returned=struct.unpack_from('=Q',raw,0)[0]; supported=struct.unpack_from('=Q',raw,72)[0]
    status=struct.unpack_from('=i',raw,60)[0]
    require(returned & 8 and returned & 32 and supported & 8
            and not struct.unpack_from('=Q',initial,0)[0] & 8
            and struct.unpack_from('=Q',initial,0)[0] & 3 == 3
            and struct.unpack_from('=I',initial,16)[0]==child['pid']
            and struct.unpack_from('=I',initial,20)[0]==child['pid']
            and struct.unpack_from('=I',initial,24)[0]==child['parent']
            and struct.unpack_from('=I',initial,28)[0]==os.getuid()
            and struct.unpack_from('=I',initial,36)[0]==os.getuid()
            and value['returned_info']['returned_mask']==returned
            and value['returned_info']['supported_mask']==supported
            and value['returned_info']['exit_code_raw']==value['raw_wait_status']==status
            and os.WIFEXITED(status) and os.WEXITSTATUS(status)==0
            and value['normal_exit_zero'] is value['normal_exit'] is True
            and value['normal_exit_status']==0 and value['signal_termination'] is False
            and value['original_birth_absent'] is True and value['status']=='KERNEL_REAPED_NORMAL0'
            and value['anchor']['capture_end_monotonic_ns'] <= value['capture_begin_monotonic_ns']
            <= value['capture_end_monotonic_ns'] <= value['observed_monotonic_ns']
            <= sample['monotonic_s']*1e9,
            'No positive retained normal0 waitstatus/reap truth for original EVAL')
    return value


def bootstrap_projection(case):
    """Historical bootstrap certificate; this never claims current liveness.

    Current health comes only from the separately captured original processes,
    owned TCP, source/role/epoch/API and strict EVAL natural/kernel cleanup proof.
    No mutable publisher file or historical timestamp is a liveness authority.
    """
    c=case['continuous']
    rows={}
    for slot, original in c['original_slots'].items():
        rows[slot]=dict(eval_only=original['eval_only'],incarnation=original['incarnation'],
            state='active_eval' if original['eval_only'] else 'active_train',
            original_pid=original['original_child']['pid'],original_birth=original['original_child']['birth'],
            original_slot_sha256=original_digest(original),natural_result=None,closure=None,
            prior_fault_closure=None,quarantine_reason=None,faults=0)
    value=dict(schema=SCHEMA,mode=MODE,epoch=c['epoch'],historical_bootstrap_only=True,
        current_health_claimed=False,supervisor=c['supervisor'],trainer=c['trainer'],
        rolemap=c['rolemap'],source_authority=c['source_authority'],
        original_membership=c['original_membership'],slots=rows,
        initial_admission=dict(complete=True,slots_ever_bound=list(range(192)),
            immutable_all192_barrier=c['initial_barrier']))
    # Detached JSON values cannot alias/mutate the selected in-memory case.
    return json.loads(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False))


def validate_snapshot(case, sample, previous=None):
    """Physical TRAIN truth comes from raw actors/current handlers, never labels."""
    c=case['continuous'];value=sample['status']
    completed=validate_completed_prefix_capture(case,sample)
    require(value==bootstrap_projection(case),
            'Historical original192 bootstrap certificate differs from held membership/barrier')
    if previous is not None:
        require(set(previous.get('EVAL_journal_evidence',{})) <= set(sample.get('EVAL_journal_evidence',{})),
                'A previously accepted original EVAL natural proof disappeared')
    validated_kernel={}
    for slot in sample.get('EVAL_kernel_exit_receipts',{}):
        require(slot in SLOTS and case['slot_eval'][slot] is True,'Unknown kernel EVAL exit slot')
        validated_kernel[slot]=kernel_eval_exit(case,sample,slot)
    current=current_connections(case,sample);actors=sample['actors']
    counts=dict(active_train=0,active_eval=0,retiring_eval=0,closed_eval=0)
    naturals={};closed_slots=set();retiring=set();normalized={};cleanup_classes={}
    for slot,compact in value['slots'].items():
        row=slot_view(case,slot,compact); original_physical(case,slot,row)
        require(row['eval_only'] is case['slot_eval'][slot], 'Physical original role changed')
        if not case['slot_eval'][slot]:
            require(slot in actors and slot in current, 'Original TRAIN lacks current physical actor/handler/TCP')
            state='active_train'
        else:
            proof=eval_natural(case,sample,slot,row,previous,completed)
            if proof is None:
                require(slot in actors and slot in current, 'Original EVAL vanished without exact natural terminal')
                state='active_eval'
            else:
                evidence,result=proof;naturals[slot]=proof
                if slot in actors:
                    require(0<=sample['unix_s']-result['end_unix_s']<=10,
                            'Natural EVAL original remained live beyond its bounded retirement')
                    state='retiring_eval';retiring.add(slot)
                else:
                    cleanup=sample.get('EVAL_cleanup_captures',{}).get(slot)
                    cleanup_proof=eval_cleanup(case,sample,slot,result,evidence,require_ready=False)
                    cleanup_classes[slot]=cleanup_proof
                    if cleanup_proof['classification']=='CURRENT_ONCE_ONLY_EVAL_QUIESCENCE_AFTER_RECORDED_DISCONNECT_EXCEPTION':
                        require(slot in validated_kernel, 'Historical cleanup exception still requires positive original kernel normal0/reap')
                    # Absence alone never supplies normal0/reap. The inherited
                    # bounded retiring state explicitly retains pending proof.
                    exit_known=False
                    if row['closure'] is not None and row['natural_result'] is not None:
                        old_event,old_result=natural(case,slot,row)
                        require(old_result==result, 'Original owner closure natural row differs')
                        closed(case,slot,row,old_event,result);exit_known=True
                    elif slot in validated_kernel:
                        exit_known=True
                    if cleanup_proof['current_postconditions_proved'] is True:
                        eval_cleanup(case,sample,slot,result,evidence)
                    if exit_known and cleanup_proof['current_postconditions_proved'] is True:
                        state='closed_eval';closed_slots.add(slot)
                    else:
                        require(0<=sample['unix_s']-result['end_unix_s']<=10,
                                'EVAL normal-exit/ThreadTimerFIFO proof remained unresolved beyond10s')
                        state='retiring_eval';retiring.add(slot)
        normalized[slot]=dict(state=state,eval_only=case['slot_eval'][slot],
            original_pid=row['original_child']['pid'],original_birth=row['original_child']['birth'])
        counts[state]+=1
    require(counts['active_train']==155 and sum(counts.values())==192
            and counts['active_eval']+counts['retiring_eval']+counts['closed_eval']==37,
            'Exact155 original TRAIN /37 once-only original EVAL partition required')
    if previous is not None:
        for slot in SLOTS:
            if case['slot_eval'][slot] and slot not in previous['actors']:
                require(slot not in actors, 'A retired original EVAL actor reappeared')
    return dict(counts=counts,naturals=naturals,closed=closed_slots,retiring=retiring,
                current_connections=current,normalized_slots=normalized,cleanup_classifications=cleanup_classes)


if __name__ == '__main__':
    print('SOURCE_ONLY_INERT_NO_READS_WRITES_PROBES_OR_ACTIONS')
