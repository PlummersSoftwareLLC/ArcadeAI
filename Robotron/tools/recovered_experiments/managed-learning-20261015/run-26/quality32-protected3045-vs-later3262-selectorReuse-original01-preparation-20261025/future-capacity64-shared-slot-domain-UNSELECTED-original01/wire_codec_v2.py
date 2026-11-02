"""Explicit isolated full-observation startup envelope; no legacy downgrade.

The proxy strips only this envelope before forwarding the original v2 bytes to
the unchanged SocketServer. The action bytes are preserved inside a48-byte
response. No work occurs on import; this protocol is not used by main actors.
"""
import json
import re
import struct

HANDSHAKE = struct.Struct('>4s16s16sH')
REQUEST = struct.Struct('>4sIII')
RESPONSE = struct.Struct('>4sIBB32s6s')
V2_HEADER = struct.Struct('>HddBIBBBIBBB')
MAX_PAYLOAD = 2*1024*1024
MAX_META = 4096
PREFIX_FRAMES = 1200
MAX_SEQUENCE = (1 << 32)-1
META_KEYS = {'schema','slot','session','connection','sequence','event','status',
    'score_hex','wave','reserves','current_player','player_count','credit',
    'planned_start','planned_coin','mode','last_start','last_coin',
    'last_apply_ok','last_socket_ok','nonce','first_play_sequence'}


def require(value,message):
    if not value:
        raise ValueError(message)


def integer(value,low,high,name):
    require(type(value)is int and low<=value<=high,'Invalid '+name)
    return value


def hex_value(value,length,name,nonzero=False):
    require(type(value)is str and re.fullmatch('[0-9a-f]{%d}'%length,value)
            and (not nonzero or value!='0'*length),'Invalid '+name)
    return value


def decode_json(raw):
    require(type(raw)is bytes and 0<len(raw)<=MAX_META,'Metadata bound differs')
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate metadata key')
            result[key]=value
        return result
    def nonfinite(value):
        raise ValueError('Nonfinite metadata')
    result=json.loads(raw,object_pairs_hook=unique,parse_constant=nonfinite)
    require(type(result)is dict,'Metadata must be an object')
    return result


def metadata(value):
    require(type(value)is dict and set(value)==META_KEYS,'Exact startup metadata required')
    require(value['schema']=='robotron-full-startup-envelope-v2','Unknown startup schema')
    integer(value['slot'],4096,4159,'slot')
    integer(value['sequence'],1,MAX_SEQUENCE,'original sequence')
    integer(value['event'],0,4096,'producer event')
    for name in ['session','connection']:
        hex_value(value[name],32,name,True)
    hex_value(value['nonce'],64,'nonce')
    hex_value(value['score_hex'],8,'raw score')
    for name in ['status','wave','reserves','current_player','player_count','credit']:
        integer(value[name],0,255,name)
    for name in ['planned_start','planned_coin','last_start','last_coin']:
        integer(value[name],0,1,name)
    for name in ['last_apply_ok','last_socket_ok']:
        require(type(value[name])is bool,'Invalid '+name)
    integer(value['first_play_sequence'],-1,1200,'first play')
    require(value['first_play_sequence']!=0,'First play must be positive or unknown')
    require(value['mode']in ['gated','authorized','latched','legacy'],'Invalid startup phase')
    require(value['first_play_sequence']<=value['sequence'],'First play is in the future')
    if value['sequence']<=PREFIX_FRAMES:
        require(value['event']>0,'Original startup trace event required')
    else:
        require(value['event']==0 and value['mode']=='legacy'and value['nonce']!='0'*64
                and value['first_play_sequence']>=1,'Only certified postprefix continuation allowed')
    require((value['mode']=='gated')==(value['nonce']=='0'*64),'Nonce and startup phase differ')
    require((value['mode']=='legacy')==(value['first_play_sequence']>=1),'Play and startup phase differ')
    return value


def encode_handshake(slot,session,connection):
    integer(slot,4096,4159,'slot')
    hex_value(session,32,'session',True);hex_value(connection,32,'connection',True)
    return HANDSHAKE.pack(b'RSG2',bytes.fromhex(session),bytes.fromhex(connection),slot)


def decode_handshake(raw):
    require(type(raw)is bytes and len(raw)==HANDSHAKE.size,'Exact startup handshake required')
    magic,session,connection,slot=HANDSHAKE.unpack(raw)
    require(magic==b'RSG2','Unknown startup handshake')
    require(encode_handshake(slot,session.hex(),connection.hex())==raw,'Malformed startup handshake')
    return dict(slot=slot,session=session.hex(),connection=connection.hex())


def validate_payload(raw):
    expected=V2_HEADER.size+1890*4+4
    require(type(raw)is bytes and len(raw)==expected,'Exact preview-free v2 payload required')
    require(struct.unpack_from('>H',raw)[0]==1890,'Original observation count differs')
    require(struct.unpack_from('>I',raw,expected-4)[0]==0,'Preview must stay disabled')


def encode_request(payload,meta):
    validate_payload(payload);metadata(meta)
    raw=json.dumps(meta,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    require(len(raw)<=MAX_META,'Metadata bound differs')
    return REQUEST.pack(b'RSG2',meta['sequence'],len(payload),len(raw))+payload+raw


def decode_request(raw):
    require(type(raw)is bytes and REQUEST.size<=len(raw)<=REQUEST.size+MAX_PAYLOAD+MAX_META,
            'Startup envelope bound differs')
    magic,sequence,payload_size,meta_size=REQUEST.unpack_from(raw)
    require(magic==b'RSG2' and payload_size<=MAX_PAYLOAD and 0<meta_size<=MAX_META
            and len(raw)==REQUEST.size+payload_size+meta_size,'Malformed startup envelope lengths')
    payload=raw[REQUEST.size:REQUEST.size+payload_size]
    meta=metadata(decode_json(raw[REQUEST.size+payload_size:]))
    require(sequence==meta['sequence'],'Envelope sequence differs from metadata')
    validate_payload(payload)
    return payload,meta


def validate_action(raw):
    require(type(raw)is bytes and len(raw)==6,'Exact original v2 action required')
    move,fire,source,advanced,level,difficulty=struct.unpack('>bbBBBB',raw)
    require(-1<=move<=7 and -1<=fire<=7 and source in (0,4)
            and advanced==0 and level==1 and difficulty==0x85,
            'Original action differs from greedy forced-eval wave1/difficulty5')


def encode_response(sequence,action,*,start=0,coin=0,nonce='0'*64,latched=False,stop=False):
    integer(sequence,1,MAX_SEQUENCE,'response sequence');validate_action(action)
    integer(start,0,1,'START');integer(coin,0,1,'coin');hex_value(nonce,64,'nonce')
    require(type(latched)is bool,'Explicit latch state required')
    require(type(stop)is bool,'Explicit stop state required')
    require(not start or nonce!='0'*64,'START requires nonzero authorization')
    require(not latched or nonce!='0'*64,'Latch requires prior authorization')
    require(sequence<=PREFIX_FRAMES or latched,'Continuation requires retained startup latch')
    require(not stop or (latched and sequence>PREFIX_FRAMES),'Stop requires postprefix certified play')
    return RESPONSE.pack(b'RSP2',sequence,start|(2 if latched else 0)|(4 if stop else 0),coin,bytes.fromhex(nonce),action)


def decode_response(raw):
    require(type(raw)is bytes and len(raw)==RESPONSE.size,'Exact48-byte response required')
    magic,sequence,flags,coin,nonce,action=RESPONSE.unpack(raw)
    require(magic==b'RSP2'and flags<=7,'Invalid response magic/flags')
    value=dict(sequence=sequence,action=action,start=flags&1,coin=coin,
               nonce=nonce.hex(),latched=bool(flags&2),stop=bool(flags&4))
    require(encode_response(**value)==raw,'Malformed response')
    return value
