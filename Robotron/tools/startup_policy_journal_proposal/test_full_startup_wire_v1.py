"""New full-wire source/codec/Lua guards; no real model or emulator.

Execute the actual transformed response reader and new Lua adapter in Lua5.4,
using synthetic memory/control/socket devices. Original observations and action
bytes are checked independently across the Python/Lua boundary.
"""
from pathlib import Path
import copy
import importlib.util
import json
import struct
import sys
import tempfile
import unittest


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]
codec=load('_new_full_startup_codec',HERE/'wire_codec_v1.py')
builder=load('_new_full_startup_builder',HERE/'prepare_full_startup_lua_v1.py')
definitions=load('_consumed_Lua_VM_definitions_only',
    GAME/'tools/startup_clock_proposal/test_gated_start_trace_v1.py')
ORIGINAL=GAME/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/main.lua'
PAYLOAD=struct.pack('>HddBIBBBIBBB',1890,0.0,0.0,0,0,0,0,0,20000,0,0,255)+bytes(1890*4)+bytes(4)
ACTION=struct.pack('>bbBBBB',-1,-1,0,0,1,0x85)


def metadata():
    return dict(schema='robotron-full-startup-envelope-v1',slot=4096,session='1'*32,
        connection='2'*32,sequence=1,event=802,status=243,score_hex='00000000',wave=0,reserves=0,
        current_player=0,player_count=2,credit=1,planned_start=0,planned_coin=0,mode='gated',
        last_start=0,last_coin=0,last_apply_ok=False,last_socket_ok=False,nonce='0'*64,first_play_sequence=-1)


PRELUDE=r'''
local helper=assert(loadfile(HELPER_PATH))()
local fields_start,fields_coin,exits,removes=0,0,0,0
local file_lines,socket_writes,callbacks={},{},{}
local memory_values={[0x9859]=243,[0x983F]=0,[0x9840]=2,[0x9851]=1}
local env={ROBOTRON_FULL_STARTUP_TRACE="private_trace",ROBOTRON_FULL_STARTUP_SLOT="4096",
 ROBOTRON_FULL_STARTUP_SESSION=string.rep("1",32),ROBOTRON_FULL_STARTUP_CONNECTION=string.rep("2",32)}
os.getenv=function(key)return env[key]end
io.open=function(path,mode)
 assert(path=="private_trace" and mode=="a")
 return {write=function(self,line)file_lines[#file_lines+1]=line;return self end,flush=function()end}
end
local memory={read_u8=function(self,addr)
 if addr==0x2715 or addr==0x2751 then return 0x97 end
 if addr==0x2716 then return 0x40 end
 if addr==0x2752 then return 0x59 end
 return memory_values[addr]or 0
end,install_write_tap=function(self,lo,hi,name,fn)
 assert(lo==hi);callbacks[lo]=fn;return {remove=function()removes=removes+1 end}
end}
local state={CURPC={value=0x2715},PC={value=0x2717},DP={value=0x98},A={value=1}}
manager={machine={devices={[":maincpu"]={spaces={program=memory},state=state}},
 memory={banks={[":mainbank"]={entry=1}},regions={[":maincpu"]={size=0x19000,bytewidth=1,bitwidth=8,
 read_u8=function(self,n)return n%256 end}}},exit=function()exits=exits+1 end}}
local controls={p1_start={set_value=function(self,v)fields_start=v end},coin_1={set_value=function(self,v)fields_coin=v end}}
local _startup=helper.attach(controls,{eval_mode=1,debug_bypass_frames=0,force_action_frames=0})
local response_bytes=""
local write_failure=false
local current_socket={write=function(self,data)
 if write_failure then error("original transport write failed")end
 socket_writes[#socket_writes+1]=data
end,read=function(self,n)
 local take=math.min(n,7,#response_bytes)
 local chunk=response_bytes:sub(1,take);response_bytes=response_bytes:sub(take+1)
 return chunk
end}
local ACTION_RX_BUFFER=""
local SOCKET_READ_TIMEOUT_S=0.1
local socket_idle_wait=nil
local ticks=0
local function socket_time_now()ticks=ticks+0.001;return ticks end
local function trace_log()end
local function log_socket_receive_timeout()end
local function set_preview_stream_enabled()end
local function open_socket()error("unexpected reconnect")end
local function close_socket()_startup:fail("original_socket_closed");current_socket=nil end
local unpack=table.unpack
local function hex(s)return(s:gsub(".",function(c)return string.format("%02x",string.byte(c))end))end
local payload=string.pack(">HddBIBBBIBBB",1890,0,0,0,0,0,0,0,20000,0,0,255)
 ..string.rep("\0",1890*4)..string.pack(">I4",0)
_startup:protect("connected",current_socket)
'''


def run_lua(code):
    proposed,_=builder.build(ORIGINAL.read_text(),HERE/'full_startup_wire_v1.lua')
    start=proposed.index('local function process_frame_via_socket(')
    end=proposed.index('local function determine_meta_commands(',start)
    script=PRELUDE.replace('HELPER_PATH',json.dumps(str(HERE/'full_startup_wire_v1.lua')))
    return definitions.Lua().run(script+proposed[start:end]+code)


class FullStartupWireContract(unittest.TestCase):
    def test_full_chunk_compiles_and_reverse_restores_original_source(self):
        source,proof=builder.build(ORIGINAL.read_text(),HERE/'full_startup_wire_v1.lua')
        self.assertTrue(proof['reverse_restores_original_bytes'])
        self.assertIn('local function serialize_frame(',source)
        self.assertEqual(source.count('sock:write(string.pack(">H", handshake_u16))'),1)
        self.assertLess(source.index('sock:write(string.pack(">H", handshake_u16))'),
                        source.index('_startup:protect("connected", sock)'))
        with tempfile.TemporaryDirectory(prefix='robotron-full-startup-source-')as directory:
            path=Path(directory)/'proposed.lua';path.write_text(source)
            self.assertEqual(definitions.Lua().run('local f=assert(loadfile('+json.dumps(str(path))+'));return "PASS"'),'PASS')

    def test_native_Lua_fragmented_response_preserves_full_observation_bytes(self):
        result=run_lua(r'''
_startup:protect("begin",1);local start,coin=_startup:protect("plan",1,0,0)
assert(start==0 and coin==0)
response_bytes=string.pack(">c4I4BBc32c6","RSP1",1,0,0,string.rep("\0",32),string.pack(">bbBBBB",-1,-1,0,0,1,0x85))
local move,fire,ok=process_frame_via_socket(payload,0)
assert(move==-1 and fire==-1 and ok and SERVER_IS_EVAL and SERVER_DIFFICULTY==5)
start,coin=_startup:protect("inputs",ok,false,false)
controls.p1_start:set_value(start);controls.coin_1:set_value(coin)
_startup:protect("applied",start,coin,ok,true);_startup:protect("finish",1)
return hex(socket_writes[1])..":"..hex(socket_writes[2])
''')
        handshake,packet=[bytes.fromhex(v)for v in result.split(':')]
        self.assertEqual(codec.decode_handshake(handshake),dict(slot=4096,session='1'*32,connection='2'*32))
        size,=struct.unpack('>I',packet[:4]);self.assertEqual(size,len(packet)-4)
        raw,meta=codec.decode_request(packet[4:])
        self.assertEqual(raw,PAYLOAD)
        self.assertEqual(meta,metadata())

    def test_native_Lua_authorized_gate_delayed_setup_latch_and_legacy_action(self):
        self.assertEqual(run_lua(r'''
local nonce=string.rep("a",32)
for sequence=1,6 do
 if sequence==5 then
  memory_values[0xBDEC]=2;memory_values[0xBDED]=1;memory_values[0x983F]=1
 end
 if sequence==6 then memory_values[0x9859]=0 end
 _startup:protect("begin",sequence)
 local planned=sequence<=3 and 1 or 0
 _startup:protect("plan",sequence,planned,0)
 local flags=sequence<=3 and 1 or(sequence>=5 and 2 or 0)
 local base=sequence==6 and string.pack(">bbBBBB",7,3,4,0,1,0x85)or string.pack(">bbBBBB",-1,-1,0,0,1,0x85)
 response_bytes=string.pack(">c4I4BBc32c6","RSP1",sequence,flags,0,nonce,base)
 local move,fire,ok=process_frame_via_socket(payload,sequence-1)
 assert(ok)
 if sequence==6 then assert(move==7 and fire==3 and _startup.mode=="legacy")end
 local start,coin=_startup:protect("inputs",ok,false,false)
 controls.p1_start:set_value(start);controls.coin_1:set_value(coin)
 _startup:protect("applied",start,coin,ok,true)
 if sequence==3 then
  assert(callbacks[0x9840](0x9840,1,255)==nil);memory_values[0x9840]=1
 end
 if sequence==4 then
  state.CURPC.value=0x2751;state.PC.value=0x2753;state.A.value=127
  assert(callbacks[0x9859](0x9859,127,255)==nil);memory_values[0x9859]=127
 end
 _startup:protect("finish",sequence)
end
assert(_startup.gate_sequence==3 and _startup.setup_sequence==4 and _startup.initialized_sequence==5)
assert(_startup.first_play_sequence==6 and fields_start==0 and fields_coin==0)
_startup:close("contract");assert(removes==5 and not _startup.failed)
return "PASS"
'''),'PASS')

    def test_native_Lua_partial_legacy_or_failed_write_never_applies_START(self):
        for setup in ['response_bytes=string.pack(">bbBBBB",-1,-1,0,0,1,0x85)',
                      'write_failure=true']:
            with self.subTest(setup=setup):
                self.assertEqual(run_lua(r'''
_startup:protect("begin",1);_startup:protect("plan",1,1,0)
'''+setup+r'''
local move,fire,ok=process_frame_via_socket(payload,0)
assert(not ok)
assert(not pcall(function()_startup:protect("inputs",ok,false,false)end))
assert(fields_start==0 and fields_coin==0 and _startup.failed and exits>=1)
return "PASS"
'''),'PASS')

    def test_native_Lua_reconnect_or_foreign_latch_rejected(self):
        self.assertEqual(run_lua(r'''
assert(not pcall(function()_startup:protect("connected",current_socket)end))
assert(_startup.failed and fields_start==0 and exits>=1)
return "PASS"
'''),'PASS')
        self.assertEqual(run_lua(r'''
_startup:protect("begin",1);_startup:protect("plan",1,1,0)
response_bytes=string.pack(">c4I4BBc32c6","RSP1",1,2,0,string.rep("a",32),string.pack(">bbBBBB",-1,-1,0,0,1,0x85))
local move,fire,ok=process_frame_via_socket(payload,0)
assert(not ok and _startup.failed and fields_start==0 and exits>=1)
return "PASS"
'''),'PASS')

    def test_request_lengths_metadata_duplicate_and_sequence_rejected(self):
        good=codec.encode_request(PAYLOAD,metadata())
        changes=[b'BAD!'+good[4:],good[:-1],good+b'X',
                 good[:4]+struct.pack('>I',2)+good[8:]]
        for bad in changes:
            with self.subTest(prefix=bad[:16]),self.assertRaises(ValueError):codec.decode_request(bad)
        for update in [dict(slot=True),dict(sequence=0),dict(sequence=1201),dict(nonce='bad'),dict(extra=1)]:
            value=metadata();value.update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):codec.encode_request(PAYLOAD,value)
        with self.assertRaises(ValueError):codec.decode_json(b'{"slot":4096,"slot":4097}')
        with self.assertRaises(ValueError):codec.decode_json(b'{"slot":NaN}')
        with self.assertRaises(ValueError):codec.encode_request(PAYLOAD[:-1],metadata())

    def test_handshake_response_identity_and_forced_eval_context(self):
        self.assertEqual(codec.decode_handshake(codec.encode_handshake(4096,'1'*32,'2'*32))['slot'],4096)
        response=codec.encode_response(1,ACTION,start=1,nonce='a'*64)
        self.assertEqual(len(response),48)
        self.assertEqual(response[-6:],ACTION)
        self.assertEqual(codec.decode_response(response)['nonce'],'a'*64)
        for bad in [ACTION,response[:-1],b'BAD!'+response[4:],response[:8]+b'\x04'+response[9:]]:
            with self.subTest(raw=bad),self.assertRaises(ValueError):codec.decode_response(bad)
        with self.assertRaises(ValueError):codec.encode_response(1,ACTION,start=1)
        with self.assertRaises(ValueError):codec.encode_response(1,ACTION,latched=True)
        with self.assertRaises(ValueError):codec.encode_handshake(4095,'1'*32,'2'*32)
        with self.assertRaises(ValueError):codec.encode_response(1,struct.pack('>bbBBBB',-1,-1,0,0,1,5))


if __name__=='__main__':
    unittest.main(verbosity=2)
