"""Independent original v2 startup, rolling-ledger and applied-STOP checks.

These stdlib functions never launch or modify a runtime. Postprefix raw frames
are not retained by this protocol; sparse digests cannot reconstruct them.
No old reviewer main or consumed guard methods are invoked.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
SLOTS=tuple(range(4096,4128))
COHORT_SELECTION = dict(
    schema='robotron-fixed-slot64-selection-v1',
    strategy='first_two_known_starts_per_declared_slot', actor_slots=list(SLOTS),
    games_per_slot=2, expected_games=64, minimum_complete_games=50,
    outer_start_horizon_s=21540, whole_cohort_timeout_from_enter_s=21600,
    timestamp_close_role='outer_start_horizon',
    selector_source_sha256='494dcdbcb0ae30f95f4724435e6bf61c68bec3aa7fc3705e39636c0ba60ddbd0')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def dependencies():
    global games_audit,codec
    expected={
        Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/audit_fixed_slot64_games_v1.py'):'89405d07f20e1c43c51fdd7b7cf103418353d9740cbf040adee0f35b70de2c91',
        G/'tools/startup_policy_journal_proposal/wire_codec_v2.py':'94e95bc1f6fb8c2063393e57512f43acba57611da9d6e33ba94c857d967ca0f3'}
    for path,sha in expected.items():
        require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Original wire-audit dependency changed')
    paths=list(expected)
    games_audit=load('_quota64_wire_games_helpers_'+str(len(sys.modules)),paths[0])
    codec=load('_quota64_wire_v2_codec_'+str(len(sys.modules)),paths[1])
    for path,sha in expected.items():
        require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Wire-audit dependency changed during import')


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def wire_rows(raw):
    require(type(raw)is bytes and len(raw)<=64*1024*1024,'Original proxy witness bound differs')
    rows=games_audit.lines(raw)
    require(len(rows)<=8192 and [r['proxy_event']for r in rows]==list(range(1,len(rows)+1))
            and all(type(r['proxy_event'])is int for r in rows),'Original proxy event sequence differs')
    allowed={'tail_ledger_header','origin_exchange','before_authorizing_response','before_wrapped_response',
        'response_send_complete','original_boot_coin_readiness','actual_policy_journal_handoff',
        'original_host_drain_start_registered','tail_ledger_checkpoint','original_closed_prefix_verified',
        'before_original_host_drained_STOP','original_drained_peer_EOF'}
    require(all(r['kind']in allowed for r in rows),'Original proxy failure or unrecognized record')
    return rows


def unique_kind(rows,kind):
    selected=[r for r in rows if r['kind']==kind]
    require(len(selected)==1,'Exactly one original '+kind+' required')
    return selected[0]


SUMMARY_KEYS={'sequence','exchange_count','accepted','rejected','last_accepted_ordinal',
    'original_payload_bytes','chain_sha256','checkpoint_count','postprefix_raw_reconstructable'}


def summary(row):return {key:row[key]for key in SUMMARY_KEYS}


def validate_original_file_identity(expected,final):
    """Join an original precreated append-only inode to its final owned seal."""
    require(type(expected)is dict and set(expected)=={'device','inode','mode','uid','nlink'}
        and expected['mode']=='0o600'and expected['nlink']==1
        and final['identity']['mode']=='0o444'
        and all(final['identity'][key]==expected[key]for key in ('device','inode','uid','nlink')),
        'Original private file inode/owner/final seal differs')
    return dict(path=final['path'],sha256=final['sha256'],original_inode=expected['inode'],
                original_device=expected['device'],final_owned_seal_verified=True)


def audit_prefix_ledger(wire,rows,subject,rom_sha,entry):
    header=unique_kind(wire,'tail_ledger_header')
    seed=hashlib.sha256(canonical(dict(schema='robotron-all-exchange-tail-ledger-v1',
        subject=subject,loaded_rom_sha256=rom_sha))).digest()
    require(wire[0]is header and header['subject']==subject and header['loaded_rom_sha256']==rom_sha
        and header['seed_sha256']==seed.hex() and header['checkpoint_interval']==4096
        and header['max_checkpoints']==4096 and header['raw_prefix_frames']==1200
        and header['postprefix_raw_reconstructable']is False,'Original ledger seed/context differs')
    exchanges={r['sequence']:r for r in wire if r['kind']=='origin_exchange'}
    responses={r['sequence']:r for r in wire if r['kind']in
        ('before_authorizing_response','before_wrapped_response')and r['sequence']<=1200}
    snapshots={r['sequence']:r for r in rows if r['kind']=='snapshot'}
    apps={r['sequence']:r for r in rows if r['kind']=='input_applied'}
    require(sorted(exchanges)==sorted(responses)==sorted(snapshots)==sorted(apps)==list(range(1,1201)),
            'Full original startup pairs required for ledger reconstruction')
    accepted=rejected=0;last_ordinal=None;initial_ordinal=None
    for sequence in range(1,1201):
        exchange=exchanges[sequence];meta=codec.metadata(exchange['metadata'])
        require(meta['sequence']==sequence and all(meta[k]==v for k,v in subject.items()),
                'Original ledger metadata subject/sequence differs')
        snapshot=snapshots[sequence]
        measured=['sequence','event','slot','session','connection','status','score_hex','wave','reserves',
            'current_player','player_count','credit','mode','last_start','last_coin',
            'last_apply_ok','last_socket_ok','nonce','first_play_sequence']
        require(all(type(snapshot[k])is type(meta[k])and snapshot[k]==meta[k]for k in measured),
                'Original wire metadata differs from its actual producer snapshot')
        before,after=exchange['before'],exchange['after'];is_accepted=exchange['accepted']
        require(type(is_accepted)is bool and type(before['frames'])is type(after['frames'])is int
            and after['frames']==before['frames']+int(is_accepted)
            and (last_ordinal is None or before['frames']==last_ordinal),
            'Original prefix accepted-frame continuity differs')
        if initial_ordinal is None:initial_ordinal=before['frames']
        if sequence>1:
            previous=codec.decode_response(bytes.fromhex(responses[sequence-1]['response_hex']))
            require(meta['last_apply_ok']is meta['last_socket_ok']is True
                and meta['last_start']==previous['start']and meta['last_coin']==previous['coin'],
                'Original previous response/input echo differs')
        payload=bytes.fromhex(exchange['original_payload_hex']);codec.validate_payload(payload)
        action=bytes.fromhex(exchange['actual_action_hex']);codec.validate_action(action)
        response=bytes.fromhex(responses[sequence]['response_hex']);decoded=codec.decode_response(response)
        require(decoded['sequence']==sequence and decoded['action']==action and decoded['stop']is False
            and response.hex()==apps[sequence]['response_hex'],'Original prefix response/application differs')
        if meta['mode']=='legacy':
            require((decoded['start'],decoded['coin'])==(meta['planned_start'],meta['planned_coin']),
                    'Original ordinary post-start inputs changed')
        parts=[struct.pack('>I',sequence),payload,canonical(meta),action,response,
            canonical(dict(before=before,after=after,accepted=is_accepted,drain_receipt=None))]
        digest=hashlib.sha256(seed)
        for part in parts:digest.update(struct.pack('>I',len(part)));digest.update(part)
        seed=digest.digest();accepted+=int(is_accepted);rejected+=int(not is_accepted);last_ordinal=after['frames']
    anchor=dict(sequence=1200,exchange_count=1200,accepted=accepted,rejected=rejected,
        last_accepted_ordinal=last_ordinal,original_payload_bytes=1200*7597,chain_sha256=seed.hex(),
        checkpoint_count=1,postprefix_raw_reconstructable=False)
    checkpoints=[r for r in wire if r['kind']=='tail_ledger_checkpoint']
    require(checkpoints and checkpoints[0]['reason']=='startup_anchor'and summary(checkpoints[0])==anchor,
            'Independently recomputed original startup ledger anchor differs')
    closed=unique_kind(wire,'original_closed_prefix_verified')
    require(closed['ledger_anchor']==anchor and closed['footer']==rows[-1]and closed['events']==len(rows)
        and closed['dense_prefix_frames']==1200 and closed['continues_after_prefix']is True,
        'Original closed-prefix ledger/producer join differs')
    if entry.get('prefix_summary')is not None:
        require(all(closed[key]==value for key,value in entry['prefix_summary'].items()),
                'Original result prefix summary differs from its witness')
    if entry.get('files')is not None:
        final=entry['files']['producer.jsonl'];early=closed['trace']
        require(all(final[k]==early[k]for k in ('path','sha256','bytes'))
            and all(final['identity'][k]==early['identity'][k]for k in
                ('device','inode','bytes','mtime_ns','uid','nlink'))
            and early['identity']['mode']=='0o600'and final['identity']['mode']=='0o444'
            and final['identity']['ctime_ns']>=early['identity']['ctime_ns'],
            'Original closed startup trace changed beyond its owned final readonly seal')
    return dict(startup_anchor=anchor,initial_accepted_ordinal=initial_ordinal,
                raw_prefix_ledger_recomputed=True,postprefix_raw_reconstructable=False)


def audit_applied_tail(wire,lifecycle,entry,subject,permit,cohort_fingerprint,policy,window,*,selected_rows):
    """Verify original host drain, sparse accounting and actual Lua STOP join.

    Sparse tail hashes are reconciled, not independently recomputed: the raw
    tail is unavailable. Actual lifecycle/source and complete-game evidence
    must supply the independent application/completion checks.
    """
    require(type(permit)is dict,'Original host permit required')
    body={k:v for k,v in permit.items()if k!='identifier'}
    require(hashlib.sha256(canonical(body)).hexdigest()==permit['identifier']
        and body['schema']=='robotron-host-fixed-slot64-complete-cohort-drain-v1'
        and canonical(body['cohort_selection'])==canonical(policy['cohort_selection'])==canonical(COHORT_SELECTION)
        and body['count']==body['started']==64 and len(body['started_ids'])==64
        and body['cohort_sha256']==cohort_fingerprint and body['policy']==policy and body['admission']==window
        and body['quality_qualified']is False,'Original complete-cohort host permit changed')
    registrations=body['original_subjects']
    require(len(registrations)==32 and {r['slot']for r in registrations}==set(range(4096,4128)),
            'Original host permit does not cover all32')
    registration=next(r for r in registrations if r['slot']==subject['slot'])
    require(all(registration[k]==v for k,v in subject.items()),'Original registered STOP subject differs')
    before_stop=unique_kind(wire,'before_original_host_drained_STOP')
    receipt=before_stop['receipt'];sequence=entry['frames']
    require(type(selected_rows)is list and len(selected_rows)==2
        and all(r['client_slot']==subject['slot']and r['complete']is r['eligible']is r['known_start']is True
            for r in selected_rows),'Both originally selected complete slot games required')
    ordered=sorted(selected_rows,key=lambda r:(r['start_unix_s'],r['journal_game_id']))
    ids=[r['journal_game_id']for r in ordered]
    require(len(set(ids))==2 and ids[0]==registration['journal_game_id']
        and ordered[0]['terminal_confirmation']['next_journal_game_id']==ids[1]
        and set(ids)<=set(body['started_ids']),'STOP selected pair differs from original certified first/next game')
    require(type(sequence)is int and 1200<sequence<=0xffffffff
        and receipt==entry['host_stop_receipt']and receipt['sequence']==before_stop['sequence']==sequence
        and receipt['schema']=='robotron-consumed-two-game-slot-retirement-v1'
        and type(receipt['permit_identifier'])is str and re.fullmatch('[0-9a-f]{64}',receipt['permit_identifier'])
        and receipt['selected_rows_sha256']==hashlib.sha256(canonical(ordered)).hexdigest()
        and receipt['selected_game_ids']==ids and receipt['global_completion_claim']is False
        and receipt['consumed_before_send']is True
        and all(receipt[k]==v for k,v in subject.items())and receipt['nonce']==registration['nonce']
        and type(receipt['authorized_unix_ns'])is int and type(receipt['authorized_monotonic_ns'])is int
        and receipt['authorized_monotonic_ns']>0
        and receipt['authorized_unix_ns']>=max(window['open_unix_ns'],max(int(r['end_unix_s']*1e9)for r in ordered)),
        'Original slot STOP is not source-bound to both selected completed natural games')
    responses=[r for r in wire if r['kind']=='before_wrapped_response'and r['sequence']>1200]
    require(len(responses)==1 and responses[0]['sequence']==sequence,'Unexpected extra or missing original tail STOP')
    response=responses[0];raw=bytes.fromhex(response['response_hex']);decoded=codec.decode_response(raw)
    require(decoded['sequence']==sequence and decoded['stop']is decoded['latched']is True
        and decoded['nonce']==receipt['nonce'],'Original host STOP bytes differ')
    sent=[r for r in wire if r['kind']=='response_send_complete'and r['sequence']>1200]
    require(len(sent)==1 and sent[0]['sequence']==sequence
        and before_stop['proxy_event']<response['proxy_event']<sent[0]['proxy_event'],
        'Original STOP consumption/send ordering differs')
    require(entry['peer_EOF']is True,'Original peer EOF not recorded')
    eof=unique_kind(wire,'original_drained_peer_EOF')
    require(eof['receipt']==receipt and eof['ledger']==entry['final_ledger']
            and sent[0]['proxy_event']<eof['proxy_event'],'Original drained EOF/result join differs')
    require([r['kind']for r in lifecycle]==
        ['header','prefix_closed','stop_response','stop_applied','exit_requested','closed']
        and [r['event']for r in lifecycle]==list(range(1,7))
        and all(r['schema']=='robotron-full-tail-lifecycle-v2'
            and all(type(r[k])is type(v)and r[k]==v for k,v in subject.items())for r in lifecycle),
        'Original Lua lifecycle is incomplete, failed or foreign')
    first,prefix,received,applied,exiting,closed=lifecycle
    require(first['sequence']==0 and first['continuation_enabled']is True and first['trace_frame_limit']==1200
        and prefix['sequence']==1200 and prefix['failed']is prefix['machine_exit_requested']is False
        and prefix['trace_events']==entry['prefix_summary']['events']
        and all(prefix[k]==entry['footer'][k]for k in ('initialized_sequence','latched_sequence','first_play_sequence')),
        'Original Lua prefix closure differs from the actual startup trace')
    require(all(r['sequence']==sequence for r in (received,applied,exiting,closed))
        and received['response_hex']==applied['response_hex']==exiting['response_hex']==raw.hex()
        and received['nonce']==applied['nonce']==decoded['nonce']
        and applied['socket_ok']is applied['apply_ok']is exiting['apply_ok']is True
        and applied['debug_bypass']is applied['held_start_before_response']is False
        and (applied['start'],applied['coin'])==(decoded['start'],decoded['coin'])
        and closed['reason']=='drained_shutdown'and closed['failed']is False and closed['stop_received']is True,
        'Original Lua did not apply the exact successful host-authorized STOP')
    checkpoints=[r for r in wire if r['kind']=='tail_ledger_checkpoint']
    expected=[1200,*range(4096,sequence+1,4096),sequence]
    require(len(checkpoints)<=4096 and [r['sequence']for r in checkpoints]==expected,
            'Original sparse checkpoint sequence differs')
    initial=checkpoints[0]['last_accepted_ordinal']-checkpoints[0]['accepted']
    previous=None
    for index,row in enumerate(checkpoints,1):
        state=summary(row)
        for key in ('sequence','exchange_count','accepted','rejected','last_accepted_ordinal',
                    'original_payload_bytes','checkpoint_count'):
            require(type(state[key])is int and state[key]>=0,'Invalid original tail counter')
        require(state['exchange_count']==state['sequence']==state['accepted']+state['rejected']
            and state['original_payload_bytes']==state['sequence']*7597
            and state['last_accepted_ordinal']==initial+state['accepted']
            and state['checkpoint_count']==index and state['postprefix_raw_reconstructable']is False
            and type(state['chain_sha256'])is str and re.fullmatch('[0-9a-f]{64}',state['chain_sha256']),
            'Original sparse tail accounting differs')
        expected_reason='startup_anchor'if index==1 else 'drained_peer_EOF'if index==len(checkpoints)else 'periodic'
        require(row['reason']==expected_reason,'Original checkpoint reason differs')
        if previous:
            require(state['accepted']>=previous['accepted']and state['rejected']>=previous['rejected'],
                    'Original tail acceptance counters reversed')
            if state['sequence']==previous['sequence']:
                require(state['chain_sha256']==previous['chain_sha256'],'Final same-frame ledger digest differs')
        previous=state
    require(previous==entry['final_ledger']==eof['ledger'],'Original final ledger accounting differs')
    return dict(slot=subject['slot'],host_receipt=receipt,actual_response_hex=raw.hex(),
        final_ledger=previous,raw_startup_ledger_recomputed=True,tail_checkpoint_accounting_verified=True,
        raw_tail_ledger_recomputed=False,postprefix_raw_reconstructable=False,
        actual_Lua_STOP_application_joined=True,actual_peer_EOF_joined=True,
        selected_pair_complete_before_actual_STOP=True,global64_certificate_separately_verified=True,
        slot_permit_body_independently_rehashed=False,quality_qualified=False)


def audit_slot_prefix(slot,entry,job,result,starts,games,read,pin,*,expected_job_sha256):
    require(type(expected_job_sha256)is str and re.fullmatch("[0-9a-f]{64}",expected_job_sha256)and expected_job_sha256!="0"*64,"Explicit immutable root job SHA required")
    subject=dict(slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)])
    require(entry['actual_exit']==0 and entry['frames']>1200 and entry['handoff']is not None
        and birth(entry['pid'])!=entry['birth'],'Original slot exit/identity differs')
    actor_pin=pin(Path(job['output'])/'actors'/str(slot)/'original-actor.json')
    actor=read(actor_pin)
    require(actor['pid']==entry['pid']and actor['starttime_ticks']==entry['birth']
        and actor['proxy_port']==job['proxy_ports'][str(slot)]and actor['original_job']['sha256']==expected_job_sha256
        and all(actor[k]==v for k,v in subject.items()),'Original actor/session/port binding differs')
    raw_trace=read(entry['files']['producer.jsonl'],False)
    require(len(raw_trace)<=16*1024*1024,'Original prefix size differs')
    rows=games_audit.lines(raw_trace)
    require(len(rows)<=4096 and all(r.get('schema')=='robotron-full-policy-startup-trace-v2'and type(r.get('event'))is int for r in rows),'Original v2 producer schema differs')
    require([r['event']for r in rows]==list(range(1,len(rows)+1))
        and all(all(type(r[k])is type(v)and r[k]==v for k,v in subject.items())for r in rows),
        'Original full producer event/subject stream differs')
    chunks=[r for r in rows if r['kind']=='raw_ROM_chunk']
    require([r['offset']for r in chunks]==list(range(0,0x19000,128)),'Whole loaded CPU ROM chunks required')
    image=b''.join(bytes.fromhex(r['data_hex'])for r in chunks)
    require(len(image)==102400 and hashlib.sha256(image).hexdigest()==job['loaded_rom_sha256'],'Actual whole CPU ROM differs')
    snapshots={r['sequence']:r for r in rows if r['kind']=='snapshot'}
    apps={r['sequence']:r for r in rows if r['kind']=='input_applied'}
    require(sorted(snapshots)==sorted(apps)==list(range(1,1201))
        and all(a['apply_ok']is a['socket_ok']is True and a['debug_bypass']is False for a in apps.values()),
        'Original1200 successful input/exchange pairs required')
    footer=rows[-1]
    require(footer==entry['footer']and footer['kind']=='footer'and footer['sequence']==1200
        and footer['failed']is footer['machine_exit_requested']is False and footer['reason']=='prefix_complete'
        and rows[0]['continues_after_prefix']is True and not any(r['kind']=='fault'for r in rows),'Original complete footer differs')
    require(len([r for r in rows if r['kind']=='snapshot'])==len(snapshots)==1200
            and len([r for r in rows if r['kind']=='input_applied'])==len(apps)==1200,
            'Original producer snapshot/input duplicates are not permitted')
    wire=wire_rows(read(entry['files']['proxy.jsonl'],False))
    exchange_rows=[r for r in wire if r['kind']=='origin_exchange']
    exchanges={r['sequence']:r for r in exchange_rows}
    require(len(exchange_rows)==len(exchanges)==1200,'Dense exchanges outside prefix, missing or duplicated')
    response_rows=[r for r in wire if r['kind']in ('before_authorizing_response','before_wrapped_response')and r['sequence']<=1200]
    responses={r['sequence']:r for r in response_rows}
    require(len(response_rows)==len(responses)==1200,'Original prefix responses missing or duplicated')
    require(sorted(exchanges)==sorted(responses)==list(range(1,1201)),'Original1200 origin/action pairs required')
    for sequence,exchange in exchanges.items():
        payload=bytes.fromhex(exchange['original_payload_hex'])
        require(len(payload)==7597 and struct.unpack_from('>H',payload)[0]==1890 and payload[-4:]==bytes(4),
                'Original full preview-free1890 payload differs')
        before,after=exchange['before'],exchange['after']
        require(after['frames']-before['frames']==int(exchange['accepted'])
            and before['client_slot']==after['client_slot']==slot and after['eval_only']is True,
            'Original accepted ordinal or slot differs')
        response=bytes.fromhex(responses[sequence]['response_hex'])
        require(len(response)==48 and response[:4]==b'RSP2'and int.from_bytes(response[4:8],'big')==sequence
            and response[-6:]==bytes.fromhex(exchange['actual_action_hex'])
            and apps[sequence]['response_hex']==response.hex(),'Original action/application byte preservation differs')
        move,fire,source,advanced,level,difficulty=struct.unpack('>bbBBBB',response[-6:])
        require(-1<=move<=7 and -1<=fire<=7 and source in (0,4)and advanced==0 and level==1
                and difficulty==0x85,'Actual greedy wave1/difficulty5 action context differs')
    authorizations=[r for r in wire if r['kind']=='before_authorizing_response']
    readiness=[r for r in wire if r['kind']=='original_boot_coin_readiness']
    handoffs=[(i,r)for i,r in enumerate(wire)if r['kind']=='actual_policy_journal_handoff']
    require(len(authorizations)==len(readiness)==len(handoffs)==1,'Unique original first-start chain required')
    handoff_index,handoff=handoffs[0];state=entry['handoff'];jid=state['journal_game_id']
    require(jid in starts and jid in games and handoff['result']==state,'Original journal/handoff join differs')
    start=starts[jid];certificate=start['context']['startup_certificate'];identifier=certificate['identifier']
    body={k:v for k,v in certificate.items()if k!='identifier'}
    require(body['schema']=='robotron-prospective-startup-journal-certificate-v2','Original v2 certificate required')
    require(hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==identifier
        and handoff['certificate']==body and identifier==state['certificate_identifier'],
        'Original immutable journal certificate bytes differ')
    require(all(body[k]==v for k,v in subject.items())and body['policy']==result['policy_before']
        and body['admission']==result['_admission']and body['loaded_rom_sha256']==job['loaded_rom_sha256'],
        'Actual policy/window/ROM/subject join differs')
    application,gate,setup,initialized,origin=[body['evidence'][k]for k in
        ('application','gate','setup','initialization','origin_acceptance')]
    for record in (application,gate,setup):require(rows[record['event']-1]==record,'Raw application/gate/setup differs')
    authorize_sequence=authorizations[0]['sequence'];init_sequence=initialized['sequence']
    require(application['sequence']==authorize_sequence and authorize_sequence<=gate['sequence']<authorize_sequence+3
        and gate['sequence']<=setup['sequence']<init_sequence<footer['first_play_sequence']<=1200
        and application['event']<gate['event']<setup['event']<initialized['event']
        and gate['sequence']==footer['gate_sequence']and setup['sequence']==footer['setup_sequence']
        and 0<footer['initialized_sequence']<=init_sequence==footer['latched_sequence']==handoff['sequence'],
        'Actual original first-start phases are unordered or after play')
    raw_initializations=[r['sequence']for r in snapshots.values()if r['event']>setup['event']
        and r['wave']==1 and r['reserves']==2 and r['score_hex']=='00000000'
        and r['player_count']==r['current_player']==1]
    raw_first_play=[r['sequence']for r in snapshots.values()if r['wave']==1
                    and r['reserves']>0 and r['status']&1==0]
    require(raw_initializations and raw_first_play
        and min(raw_initializations)==footer['initialized_sequence']
        and min(raw_first_play)==footer['first_play_sequence'],
        'Original earliest raw initialization or first-play witness differs')
    require(application['nonce']==body['nonce']and application['start']==1 and application['coin']==0
        and application['held_start_before_response']is False
        and all(a['start']==0 for sequence,a in apps.items()if sequence<authorize_sequence),
        'First authorization did not precede the first physical START')
    require(gate['address']==0x9840 and gate['instruction_pc']==0x2715 and gate['instruction_hex']=='9740'
        and gate['a']==gate['data']==gate['last_start']==1 and setup['address']==0x9859
        and setup['instruction_pc']==0x2751 and setup['instruction_hex']=='9759'and setup['a']==setup['data']==127
        and all(r['nonce']==body['nonce']and r['dp']==0x98 and r['bank_entry']==1 and r['mask']==255
            and r['last_apply_ok']is r['last_socket_ok']is True for r in (gate,setup)),
        'Distinct accepted START gate/setup or actual inputs differ')
    raw_init=snapshots[init_sequence];exchange=exchanges[init_sequence]
    require(raw_init['event']==initialized['event']and raw_init['score_hex']=='00000000'
        and raw_init['wave']==1 and raw_init['reserves']==2 and raw_init['player_count']==raw_init['current_player']==1
        and raw_init['status']&1 and raw_init['first_play_sequence']==-1 and raw_init['nonce']==body['nonce'],
        'Actual one-player initialized snapshot before play differs')
    first=snapshots[footer['first_play_sequence']]
    require(first['status']&1==0 and first['wave']==1 and first['reserves']>0
        and first['player_count']==first['current_player']==1,'Actual first-play snapshot differs')
    require(origin['accepted']is True and origin['client_slot']==slot and origin['frame_sequence']==init_sequence
        and origin['accepted_frames']==exchange['after']['frames']and exchange['accepted']is True
        and origin['game_uid']==exchange['after']['game_uid']and origin['raw_payload_sha256']==
        hashlib.sha256(bytes.fromhex(exchange['original_payload_hex'])).hexdigest(),'Actual origin accepted-frame join differs')
    latch_index=next(i for i,r in enumerate(wire)if r['kind']=='before_wrapped_response'and r['sequence']==init_sequence)
    require(handoff_index<latch_index and bytes.fromhex(responses[init_sequence]['response_hex'])[8]&2,
            'Journal transition did not precede next action')
    ready=readiness[0]['readiness'];raw_ready=snapshots[authorize_sequence]
    require(readiness[0]['sequence']==authorize_sequence and ready['ready_sequence']==authorize_sequence
        and ready['ready_snapshot_event']==raw_ready['event']and ready['game_start_proven']is False
        and raw_ready['status']==243 and raw_ready['credit']>0
        and raw_ready['credit']&15<=9 and raw_ready['credit']>>4<=9
        and ready['clear']['event']<ready['initialized']['event']<ready['coin_applications'][0]['event']
        <ready['accepted_coin_STATUS']['event']<raw_ready['event'],'Original boot/coin readiness differs')
    require(raw_ready['score_hex']=='00000000'and raw_ready['wave']==raw_ready['reserves']==0
        and raw_ready['player_count']==2 and raw_ready['current_player']==0
        and raw_ready['mode']=='gated'and raw_ready['nonce']=='0'*64,'Original raw ready state differs')
    for record in [ready['clear'],ready['initialized'],ready['accepted_coin_STATUS'],*ready['coin_applications']]:
        require(rows[record['event']-1]==record,'Ready evidence does not match original raw prefix')
    require(ready['clear']['instruction_pc']==0xd137 and ready['clear']['instruction_hex']=='6f80'
        and ready['clear']['data']==0 and ready['initialized']['instruction_pc']==0xd184
        and ready['initialized']['instruction_hex']=='0359'and ready['initialized']['data']==255
        and ready['accepted_coin_STATUS']['instruction_pc']==0x79c4
        and ready['accepted_coin_STATUS']['instruction_hex']=='9759'and ready['accepted_coin_STATUS']['credit']==1,
        'Actual ROM boot/first accepted coin1 anchors differ')
    for record in (ready['clear'],ready['initialized'],ready['accepted_coin_STATUS']):
        require(record['address']==0x9859 and record['dp']==0x98 and record['bank_entry']==1
            and record['mask']==255 and record['last_start']==0 and record['nonce']=='0'*64
            and record['last_apply_ok']is record['last_socket_ok']is True,'Original boot/coin write context differs')
    require(ready['accepted_coin_STATUS']['data']==ready['accepted_coin_STATUS']['a']==243,
            'Actual accepted-coin STATUS write differs')
    for coin in ready['coin_applications']:
        response=bytes.fromhex(coin['response_hex'])
        require(coin['start']==0 and coin['coin']==1 and coin['socket_ok']is coin['apply_ok']is True
            and coin['held_start_before_response']is coin['debug_bypass']is False and coin['nonce']=='0'*64
            and len(response)==48 and response[:4]==b'RSP2'and response[8:10]==b'\0\1'
            and response[10:42]==bytes(32),'Actual original physical coin response/application differs')
    admission=body['admission']
    require(admission['open_unix_ns']<=body['lower_before_send_unix_ns']<=body['upper_after_receive_unix_ns']
        <admission['close_unix_ns']and admission['close_unix_ns']-admission['open_unix_ns']==21_540_000_000_000
        and canonical(body['policy']['cohort_selection'])==canonical(COHORT_SELECTION)
        and body['lower_monotonic_ns']<=exchange['after_original_action_monotonic_ns']<=body['upper_monotonic_ns']
        and abs((body['upper_after_receive_unix_ns']-body['lower_before_send_unix_ns'])
        -(body['upper_monotonic_ns']-body['lower_monotonic_ns']))<=50_000_000,'Actual host clock bracket differs')
    old,new=games[state['previous_journal_game_id']],games[jid]
    require(old['known_start']is old['complete']is old['eligible']is False
        and old['excluded_reason']=='startup_attachment'and old['start_reason']=='initial_attachment'
        and old['terminal_confirmation']is None and 'startup_certificate'not in old['start_context']
        and 'startup_certificate'not in old['end_context'],'Original unknown attachment was relabelled')
    require(old['journal_game_id']!=jid and old['game_uid']==new['game_uid']==origin['game_uid']
        and new['known_start']is True and new['start_reason']=='prospective_certified_first_start_v2'
        and new['start_context']['startup_certificate']==certificate and new['first_play_level']==1
        and new['client_slot']==start['client_slot']==slot,'Prospective first-start journal identity differs')
    require(new['complete']is new['eligible']is True and new['excluded_reason']==''
        and type(new['terminal_confirmation'])is dict,'Original certified full tail did not complete')
    return dict(slot=slot,session=subject['session'],connection=subject['connection'],
        original_actor=actor_pin,pid=entry['pid'],birth=entry['birth'],actual_exit=0,
        certificate_identifier=identifier,nonce=body['nonce'],client_id=origin['client_id'],game_uid=origin['game_uid'],
        journal_game_id=jid,previous_journal_game_id=old['journal_game_id'],authorizing_sequence=authorize_sequence,
        gate_sequence=gate['sequence'],setup_sequence=setup['sequence'],initialized_sequence=init_sequence,
        first_play_sequence=footer['first_play_sequence'],host_bracket_ms=(body['upper_monotonic_ns']-body['lower_monotonic_ns'])/1e6,
        original_snapshots=1200,original_exchanges=1200,original_applications=1200,
        original_files=entry['files'],complete_game_score_qualified=False,
        prefix_ledger=audit_prefix_ledger(wire,rows,subject,job['loaded_rom_sha256'],entry))
