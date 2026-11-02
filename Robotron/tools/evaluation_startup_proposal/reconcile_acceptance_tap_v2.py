"""Strict passive content join. Never certify a game start or runtime outcome."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

SCHEMA = 'robotron-ROM-start-tap-v1'
LIMIT, WRITE_LIMIT, EVENT_LIMIT = 4096, 512, 4620
FAILURE_MARKER = b'ROBOTRON_STARTUP_ACCEPTANCE_TAP_FAILURE'
RAW_MATCHER_SHA = '0d2a612b6cfa1726e7f0c9f163d0484a8ce3c29cc3ee8e06323c798032f7c7ba'
ROM3_SHA = 'f9a8f0054d1855adaee37e33c9f14491be24e6f1898bd558444aa8d53c8ce37b'
ROM10_SHA = '2346893d291a2f070e27048209f87b514c44e445eee7d02e6cf71dd9c5680069'
COMMON = {'schema', 'kind', 'slot', 'session', 'sequence'}
KEYS = {
    'header': {'input_limit','write_limit','status_address','cpu_tag','bank_tag','region_tag','region_size',
        'region_bytewidth','region_bitwidth','span_region_offset','span_bytes','ROM_span_hex','OS_vector_hex',
        'initialization_hex','initial_pc','initial_instruction_pc','initial_dp','initial_a','initial_bank_entry',
        'inputs_observed','raw_provenance_only','full_ROM_image_verified','start_eligibility_changed'},
    'installed': {'inputs_observed','frame','raw_provenance_only'},
    'input': {'frame','epoch','exchange','start','coin','apply_ok','socket_ok','inputs_observed'},
    'status_write': {'write_ordinal','address','data','mask','previous_status','pc','instruction_pc','dp','a',
        'bank_entry','instruction_hex','last_input_frame','epoch','exchange','last_start','last_coin',
        'last_apply_ok','last_socket_ok','inputs_observed','score_hex','raw_reserves','raw_wave','credit',
        'current_player','player_count'},
    'footer': {'reason','inputs_observed','writes_observed','faults','failed','logging_failed','last_input_frame',
        'capacity_reached','raw_provenance_only','real_ROM_start_acceptance_proven','start_eligibility_changed'},
}


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'Tap integer type/range differs')
    return value


def boolean(value):
    require(type(value) is bool, 'Tap flag must be a boolean')
    return value


def fixed(row, expected):
    require(all(type(row.get(key)) is type(value) and row[key] == value for key,value in expected.items()),
            'Tap fixed declaration/value differs')


def hex_bytes(value, length):
    require(type(value) is str and re.fullmatch('[0-9a-f]{'+str(length*2)+'}', value),
            'Tap byte witness differs')
    return bytes.fromhex(value)


def decode(raw):
    require(type(raw) is bytes and raw and raw.endswith(b'\n') and len(raw) <= EVENT_LIMIT*2048,
            'Incomplete/oversized tap prefix')
    lines = raw.splitlines()
    require(3 <= len(lines) <= EVENT_LIMIT and all(len(line)+1 <= 2048 for line in lines),
            'Tap event/line bounds differ')
    def unique(pairs):
        result = {}
        for key,value in pairs:
            require(key not in result, 'Duplicate tap JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('Nonfinite tap JSON: '+value)
    rows = [json.loads(line, object_pairs_hook=unique, parse_constant=nonfinite) for line in lines]
    require(all(type(row) is dict and type(row.get('kind')) is str and row['kind'] in KEYS
                and set(row) == COMMON | KEYS[row['kind']] for row in rows),
            'Unknown/missing/extra tap event fields')
    return rows


def _raw_matcher():
    # Independently load the exact reviewed matcher. Never accept a caller's
    # self-reported match or share the live server capture's global state.
    path = Path(__file__).resolve().parent/'startup_server_prefix_v2.py'
    def identity(info):
        return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                stat.S_IMODE(info.st_mode),info.st_uid,info.st_nlink)
    before = path.stat()
    require(path == path.resolve(strict=True) and stat.S_ISREG(before.st_mode)
            and stat.S_IMODE(before.st_mode) == 0o444 and before.st_uid == os.getuid()
            and before.st_nlink == 1 and before.st_size <= 64*1024, 'Immutable raw matcher required')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == RAW_MATCHER_SHA
            and identity(before) == identity(path.stat()), 'Raw matcher source differs')
    spec = importlib.util.spec_from_file_location('_independent_passive_tap_raw_matcher', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(identity(before) == identity(path.stat())
            and hashlib.sha256(path.read_bytes()).hexdigest() == RAW_MATCHER_SHA,
            'Raw matcher changed during import')
    return module


def _header(row, rom3, rom10):
    fixed(row, dict(input_limit=LIMIT,write_limit=WRITE_LIMIT,status_address=0x9859,
        cpu_tag=':maincpu',bank_tag=':mainbank',region_tag=':maincpu',region_size=0x19000,
        region_bytewidth=1,region_bitwidth=8,span_region_offset=0x126C0,span_bytes=245,
        inputs_observed=0,raw_provenance_only=True,full_ROM_image_verified=False,start_eligibility_changed=False))
    require(hex_bytes(row['ROM_span_hex'],245) == rom3[0x6c0:0x7b5]
            and hex_bytes(row['OS_vector_hex'],3) == rom10[:3]
            and hex_bytes(row['initialization_hex'],15) == rom10[0x106:0x115],
            'Entire captured loaded startup span/vector/initialization differs from pinned ROM')
    for name in ('initial_pc','initial_instruction_pc'):
        integer(row[name],0,65535)
    for name in ('initial_dp','initial_a'):
        integer(row[name],0,255)
    integer(row['initial_bank_entry'],0,1)


def _slot(rows, raw_frames, slot, session, rom3, rom10):
    for ordinal,row in enumerate(rows,1):
        fixed(row,dict(schema=SCHEMA,slot=slot,session=session,sequence=ordinal))
    require(rows[0]['kind'] == 'header' and rows[1]['kind'] == 'installed'
            and rows[-1]['kind'] == 'footer'
            and all(row['kind'] in ('input','status_write') for row in rows[2:-1]),
            'Tap installation/footer order differs')
    _header(rows[0],rom3,rom10)
    fixed(rows[1],dict(inputs_observed=0,frame=-1,raw_provenance_only=True))
    inputs = writes = before_input = common_restarts = 0
    candidates = []
    last = dict(last_input_frame=-1,epoch=0,exchange=0,last_start=0,last_coin=0,
                last_apply_ok=False,last_socket_ok=False)
    for row in rows[2:-1]:
        if row['kind'] == 'input':
            require(inputs < len(raw_frames), 'Tap has an unjoined input')
            original = raw_frames[inputs]
            fixed(row,dict(frame=inputs,epoch=original['epoch'],exchange=original['exchange'],
                start=original['start_input'],coin=original['coin_input'],apply_ok=original['apply_ok'],
                socket_ok=original['socket_ok'],inputs_observed=inputs+1))
            last = dict(last_input_frame=inputs,epoch=row['epoch'],exchange=row['exchange'],
                last_start=row['start'],last_coin=row['coin'],last_apply_ok=row['apply_ok'],last_socket_ok=row['socket_ok'])
            inputs += 1
            continue
        writes += 1
        require(writes <= WRITE_LIMIT, 'Tap write capacity exceeded')
        fixed(row,dict(write_ordinal=writes,address=0x9859,mask=255,inputs_observed=inputs,**last))
        for name in ('data','previous_status','dp','a','raw_reserves','raw_wave','credit','current_player','player_count'):
            integer(row[name],0,255)
        for name in ('pc','instruction_pc'):
            integer(row[name],0,65535)
        integer(row['bank_entry'],0,1)
        instruction = hex_bytes(row['instruction_hex'],2)
        hex_bytes(row['score_hex'],4)
        curpc = row['instruction_pc']
        if row['bank_entry'] == 1 and 0x26C0 <= curpc <= 0x27B3:
            require(instruction == rom3[curpc-0x2000:curpc-0x2000+2], 'Mapped instruction bytes differ')
        if inputs == 0:
            before_input += 1
        site = row['bank_entry'] == 1 and row['dp'] == 0x98 and instruction == b'\x97\x59'
        if site and curpc == 0x27A5 and row['pc'] == 0x27A7:
            common_restarts += 1
        if (site and curpc == 0x2751 and row['pc'] == 0x2753 and row['data'] == row['a'] == 127
                and row['previous_status'] & 0x80 and inputs > 0 and last['last_start'] == 1
                and last['last_apply_ok'] is True and last['last_socket_ok'] is True):
            # This is a write-site observation, not first-start certification.
            # Preserve the next raw frame so later review can reason about
            # pre-play counters and admission clocks without inventing them.
            following = raw_frames[inputs] if inputs < len(raw_frames) else None
            candidates.append(dict(sequence=row['sequence'],write_ordinal=writes,
                applied_input_frame=last['last_input_frame'],exchange=last['exchange'],
                following_raw_frame=None if following is None else {key:following[key] for key in
                    ('frame','raw_status','raw_score_hex','raw_reserves','raw_wave','wire_alive','wire_score','wire_start')},
                real_ROM_start_acceptance_proven=False))
    require(0 < inputs == len(raw_frames) <= LIMIT, 'Tap/raw input coverage differs')
    footer = rows[-1]
    fixed(footer,dict(inputs_observed=inputs,writes_observed=writes,faults=0,failed=False,logging_failed=False,
        last_input_frame=inputs-1,capacity_reached=inputs==LIMIT,raw_provenance_only=True,
        real_ROM_start_acceptance_proven=False,start_eligibility_changed=False))
    require(footer['reason'] in ('machine_stop','capacity')
            and (footer['reason'] != 'capacity' or inputs == LIMIT), 'Tap close reason/capacity differs')
    return dict(inputs=inputs,status_writes=writes,writes_before_first_input=before_input,
        common_restart_write_observations=common_restarts,START1_write_observations=candidates,
        captured_loaded_span_matches_pinned_ROM=True,full_loaded_ROM_image_verified=False,
        first_start_certified=False,admission_clock_ordering_verified=False)


def reconcile(lua_prefixes, server_prefix, tap_prefixes, actor_consoles, sessions, rom3, rom10, *, limit=4096):
    """Match all declared content; final original-unit/runtime proof is separate."""
    require(type(sessions) is dict and 1 <= len(sessions) <= 32
            and all(type(slot) is int and 4096 <= slot <= 4127 for slot in sessions)
            and all(type(s) is str and re.fullmatch('[a-f0-9]{32}',s) for s in sessions.values())
            and len(set(sessions.values())) == len(sessions), 'Bound distinct private slots/sessions required')
    require(type(limit) is int and 16 <= limit <= LIMIT, 'Raw prefix limit differs')
    for values in (lua_prefixes,tap_prefixes,actor_consoles):
        require(type(values) is dict and set(values) == set(sessions), 'Complete declared prefix/console inventory required')
    require(type(rom3) is type(rom10) is bytes and len(rom3) == len(rom10) == 4096
            and hashlib.sha256(rom3).hexdigest() == ROM3_SHA
            and hashlib.sha256(rom10).hexdigest() == ROM10_SHA, 'Exact pinned ROM chips required')
    for console in actor_consoles.values():
        require(type(console) is bytes and len(console) <= 16*1024*1024
                and FAILURE_MARKER not in console, 'Actor console missing/oversized or diagnostic failure marker present')
    raw = _raw_matcher()
    joined = raw.reconcile(lua_prefixes,server_prefix,sessions,limit=limit)
    summaries = {}
    for slot,session in sorted(sessions.items()):
        frames = raw.decode_lines(lua_prefixes[slot],limit+32)[2:-1]
        summaries[str(slot)] = _slot(decode(tap_prefixes[slot]),frames,slot,session,rom3,rom10)
    return dict(status='MATCHED_PASSIVE_TAP_CONTENT_ONLY',raw_prefix_reconciliation=joined,
        actor_slots=len(sessions),matched_inputs=sum(v['inputs'] for v in summaries.values()),slots=summaries,
        input_sha256=dict(server=hashlib.sha256(server_prefix).hexdigest(),
            lua={str(k):hashlib.sha256(v).hexdigest() for k,v in lua_prefixes.items()},
            tap={str(k):hashlib.sha256(v).hexdigest() for k,v in tap_prefixes.items()},
            console={str(k):hashlib.sha256(v).hexdigest() for k,v in actor_consoles.items()}),
        original_runtime_outcome_verified=False,raw_ROM_start_acceptance_proven=False,
        start_eligibility_changed=False,protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False)


if __name__ == '__main__':
    print('LIBRARY_ONLY: no reads, imports of game code, runtime discovery or launches')
