"""Independent deadline32 firstSTART prefix and three-pair host-clock checks.

These stdlib functions never launch or modify a runtime. Postprefix raw frames
are not retained by this protocol; sparse digests cannot reconstruct them.
The firstSTART proof retains the original raw1200/ROM/input/nonce/journal joins.
No complete-game requirement is imposed by this separate deadline metric.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def dependencies():
    global games_audit,codec
    here=G/'tools/startup_policy_journal_proposal'
    expected={'audit_quality32_games_v1.py':'e106cb9d3a2131c34365daaf4638ccba97c94c02de00a4a33dfe4d7ce5876f9b',
              'wire_codec_v2.py':'94e95bc1f6fb8c2063393e57512f43acba57611da9d6e33ba94c857d967ca0f3'}
    for name,sha in expected.items():
        require(hashlib.sha256((here/name).read_bytes()).hexdigest()==sha,'Original wire-audit dependency changed')
    games_audit=load('_full_tail_wire_games_helpers_'+str(len(sys.modules)),here/'audit_quality32_games_v1.py')
    codec=load('_full_tail_wire_v2_codec_'+str(len(sys.modules)),here/'wire_codec_v2.py')
    for name,sha in expected.items():
        require(hashlib.sha256((here/name).read_bytes()).hexdigest()==sha,'Wire-audit dependency changed during import')


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
        'deadline_request_budget_begin','deadline_request_budget_complete','deadline_host_clock_sample',
        'deadline_host_clock_coherence','original_proxy_failure',
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


def audit_first_start_prefix(slot,entry,job,result,starts,games,read,pin,*,expected_job_sha256):
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
    audit_proxy_disposition(wire,entry,slot=slot)
    for kind in ('deadline_request_budget_begin','deadline_request_budget_complete'):
        budgets=[r for r in wire if r['kind']==kind]
        require(len(budgets)==1200 and [r['sequence']for r in budgets]==list(range(1,1201)),
            'Exactly one pre-header budget and completion per startup frame required')
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
        <admission['close_unix_ns']and admission['close_unix_ns']-admission['open_unix_ns']==job['startup_admission_duration_ns']
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
    # Deadline score is a separate estimand. The first game may remain active at D.
    # Never require or fabricate a complete-game50 quality qualification here.
    clock_proof=audit_clock_chain(wire,body,state)
    require(start['context']['startup_clock_handoff']==dict(
        certificate_identifier=identifier,witness=state['clock_handoff_sample'],
        coherence=state['clock_handoff_coherence']), 'Journal handoff clock witness differs')
    return dict(slot=slot,session=subject['session'],connection=subject['connection'],
        original_actor=actor_pin,pid=entry['pid'],birth=entry['birth'],actual_exit=0,
        certificate_identifier=identifier,nonce=body['nonce'],client_id=origin['client_id'],game_uid=origin['game_uid'],
        journal_game_id=jid,previous_journal_game_id=old['journal_game_id'],authorizing_sequence=authorize_sequence,
        gate_sequence=gate['sequence'],setup_sequence=setup['sequence'],initialized_sequence=init_sequence,
        first_play_sequence=footer['first_play_sequence'],host_bracket_ms=(body['upper_monotonic_ns']-body['lower_monotonic_ns'])/1e6,
        original_snapshots=1200,original_exchanges=1200,original_applications=1200,
        original_files=entry['files'],complete_game_score_qualified=False,
        prefix_ledger=audit_prefix_ledger(wire,rows,subject,job['loaded_rom_sha256'],entry),
        clock_proof=clock_proof,deadline_score_qualified=False)


CLOCK_PATH=G/'tools/startup_clock_cosampling_proposal_20261026/clock_cosampling_v1.py'
CLOCK_SHA='4846a6c74e9d07fb4ebe9c31be9920b539179915940b679928b323703874cab1'

def clock_component():
    raw=CLOCK_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==CLOCK_SHA,'Clock audit component differs')
    module=load('_deadline32_independent_clock_'+str(len(sys.modules)),CLOCK_PATH)
    require(CLOCK_PATH.read_bytes()==raw,'Clock component changed during audit import')
    return module

def audit_clock_chain(wire,body,handoff):
    """Replay all phase witnesses and causality from complete prefix wire rows."""
    clock=clock_component()
    phases=('before_authorization','after_accepted_frame','before_journal_handoff')
    samples=[r for r in wire if r['kind']=='deadline_host_clock_sample']
    proofs=[r for r in wire if r['kind']=='deadline_host_clock_coherence']
    require(len(samples)==3 and [r['phase']for r in samples]==list(phases)
        and len(proofs)==2 and [r['phase']for r in proofs]==list(phases[1:])
        and not any(r['kind']=='deadline_host_clock_failure'for r in wire),
        'Exactly three successful clock samples and two proofs required')
    subject={k:body[k]for k in ('slot','session','connection')}
    lower,upper,third=samples
    auth=unique_kind(wire,'before_authorizing_response')
    transition=unique_kind(wire,'actual_policy_journal_handoff')
    init=body['evidence']['origin_acceptance']['frame_sequence']
    exchange=next(r for r in wire if r['kind']=='origin_exchange'and r['sequence']==init)
    require(lower['sequence']==auth['sequence'] and upper['sequence']==third['sequence']==init,
            'Clock samples do not join original action sequences')
    selected={}
    for row in samples:
        require(row['subject']==subject and row['nonce']==body['nonce']
            and row['clock_component_sha256']==CLOCK_SHA,'Clock sample subject/source differs')
        witness=row['witness'];value=clock.validate_pair(witness);selected[row['phase']]=value
        budget=row['request_budget']
        begin=next(r for r in wire if r['kind']=='deadline_request_budget_begin'and r['sequence']==row['sequence'])
        end=next(r for r in wire if r['kind']=='deadline_request_budget_complete'and r['sequence']==row['sequence'])
        require(budget==begin['request_budget']==end['request_budget']
            and budget['schema']=='robotron-deadline32-absolute-request-budget-v1'
            and budget['sequence']==row['sequence'] and budget['budget_ns']==3_000_000_000
            and type(budget['start_monotonic_ns'])is int
            and budget['deadline_monotonic_ns']==budget['start_monotonic_ns']+3_000_000_000
            and witness['parent_deadline_mono_ns']==budget['deadline_monotonic_ns']
            and budget['start_monotonic_ns']<=witness['started_mono_ns']<=witness['completed_mono_ns']
            <=end['complete_monotonic_ns']<budget['deadline_monotonic_ns']
            and begin['proxy_event']<row['proxy_event']<end['proxy_event'],
            'Clock witness did not use original pre-header absolute action budget')
    require(upper['request_budget']==third['request_budget'], 'Handoff renewed accepted-frame budget')
    expected={p:clock.check_coherence(lower['witness'],r['witness'])for p,r in zip(phases[1:],samples[1:])}
    for row in proofs:
        require(row['subject']==subject and row['nonce']==body['nonce']
            and row['sequence']==init and row['clock_component_sha256']==CLOCK_SHA
            and row['request_budget']==upper['request_budget']
            and row['proof']==expected[row['phase']], 'Conservative clock replay differs')
    require(lower['proxy_event']<auth['proxy_event']<exchange['proxy_event']<upper['proxy_event']
        <proofs[0]['proxy_event']<third['proxy_event']<proofs[1]['proxy_event']<transition['proxy_event']
        and selected[phases[0]]['mono_after_ns']<=auth['host_monotonic_ns']
        and exchange['after_original_action_monotonic_ns']<=selected[phases[1]]['mono_before_ns']
        and selected[phases[1]]['mono_after_ns']<=selected[phases[2]]['mono_before_ns'],
        'Clock samples do not enclose authorization/actual accepted frame/handoff')
    require(body['host_clock_scheme']=='bounded-host-clock-cosample-v1'
        and body['host_clock_component_sha256']==CLOCK_SHA
        and body['host_clock_samples']=={p:r['witness']for p,r in zip(phases[:2],samples[:2])}
        and body['host_clock_coherence']==expected[phases[1]]
        and all(body[k]==v for k,v in expected[phases[1]]['certificate_clock_fields'].items())
        and handoff['clock_handoff_sample']==third['witness']
        and handoff['clock_handoff_coherence']==expected[phases[2]],
        'Immutable certificate/handoff clock fields differ')
    return dict(schema='robotron-deadline32-first-start-clock-audit-v1',
        clock_component_sha256=CLOCK_SHA,phases=list(phases),all_three_witnesses_replayed=True,
        issuance_maximum_error_ns=expected[phases[1]]['maximum_possible_error_ns'],
        handoff_maximum_error_ns=expected[phases[2]]['maximum_possible_error_ns'],
        unchanged_tolerance_ns=50_000_000,deadline_score_qualified=False)


def audit_proxy_disposition(wire,entry,*,slot):
    failures=[r for r in wire if r['kind']=='original_proxy_failure']
    require(len(failures)<=1,'Duplicate proxy failure/retirement')
    if not failures:return
    row=failures[0];boundary=entry.get('intentional_cleanup')
    require(type(boundary)is dict and type(row.get('intentional_cleanup_flag'))is bool
        and row['intentional_cleanup_flag']is True
        and type(row.get('error'))is str
        and row['error']=="DeadlineRetired('Selected deadline snapshot sealed; retire original slot "+str(slot)+"')"
        and type(row.get('sequence'))is int and row['sequence']>1200
        and type(row.get('observed_monotonic_ns'))is int
        and all(type(boundary.get(k))is int for k in ('begin_monotonic_ns','declared_monotonic_ns',
            'after_flags_monotonic_ns','score_sealed_monotonic_ns'))
        and boundary['score_sealed_monotonic_ns']<=boundary['begin_monotonic_ns']
        <=boundary['declared_monotonic_ns']<=boundary['after_flags_monotonic_ns']
        and row['cleanup_begin_monotonic_ns']==boundary['begin_monotonic_ns']
        and row['cleanup_declared_monotonic_ns']==boundary['declared_monotonic_ns']
        and row['observed_monotonic_ns']>=boundary['begin_monotonic_ns']
        and row.get('clock_error_evidence')is None,
        'Proxy fault lacks exact post-seal intentional retirement proof')
