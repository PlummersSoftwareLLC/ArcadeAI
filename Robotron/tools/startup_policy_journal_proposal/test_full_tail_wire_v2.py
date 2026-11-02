"""New v2 wire/authority/native-Lua continuation contract; no actual game/model.

Only fixture/VM definitions from consumed modules are imported. None of their
test methods or original readers runs. Stop replies here are synthetic: the
separate host drain authority must validate the actual complete cohort.
"""
from pathlib import Path
import importlib.util
import json
import struct
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


codec=load('_tail_wire_codec_v2',HERE/'wire_codec_v2.py')
builder=load('_tail_source_builder_v2',HERE/'prepare_full_startup_lua_v2.py')
authority=load('_tail_startup_authority_v2',HERE/'startup_handoff_v2.py')
wire_defs=load('_consumed_wire_fixture_definitions_only',HERE/'test_full_startup_wire_v1.py')
journal_defs=load('_consumed_journal_fixture_definitions_only',HERE/'test_startup_handoff_v1.py')
ORIGINAL=GAME/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/main.lua'
ACTION=struct.pack('>bbBBBB',7,3,4,0,1,0x85)
PAYLOAD=wire_defs.PAYLOAD


def metadata(**changes):
    value=wire_defs.metadata();value['schema']='robotron-full-startup-envelope-v2';value.update(changes)
    return value


PRELUDE=wire_defs.PRELUDE.replace('os.getenv=function(key)return env[key]end',
    'env.ROBOTRON_FULL_TAIL_LIFECYCLE="private_lifecycle"\nos.getenv=function(key)return env[key]end')
old='''io.open=function(path,mode)
 assert(path=="private_trace" and mode=="a")
 return {write=function(self,line)file_lines[#file_lines+1]=line;return self end,flush=function()end}
end'''
new='''local lifecycle_lines={}
local trace_file_closed,life_file_closed=false,false
io.open=function(path,mode)
 assert((path=="private_trace" or path=="private_lifecycle")and mode=="a")
 local target=path=="private_trace"and file_lines or lifecycle_lines
 return {write=function(self,line)
  assert(not(path=="private_trace"and trace_file_closed or path=="private_lifecycle"and life_file_closed))
  target[#target+1]=line;return self
 end,flush=function()end,close=function(self)
  if path=="private_trace"then trace_file_closed=true else life_file_closed=true end
  return true
 end}
end'''
assert old in PRELUDE
PRELUDE=PRELUDE.replace(old,new)

STEPS=r'''
local nonce=string.rep("a",32)
local function step(sequence,stop)
 if sequence==5 then
  memory_values[0x9859]=127;memory_values[0xBDEC]=2;memory_values[0xBDED]=1
  memory_values[0x983F]=1
 end
 if sequence==8 then memory_values[0x9859]=0 end
 _startup:protect("begin",sequence)
 local planned=sequence<=3 or sequence==1200 or sequence==1201
 local start_plan=planned and 1 or 0
 local coin_plan=sequence>=1200 and planned and 1 or 0
 _startup:protect("plan",sequence,start_plan,coin_plan)
 local flags=(sequence<=3 and 1 or 0)|(sequence>=7 and 2 or 0)
 if sequence>=1200 then flags=2|start_plan end
 if stop then flags=flags|4 end
 response_bytes=string.pack(">c4I4BBc32c6","RSP2",sequence,flags,coin_plan,nonce,
  string.pack(">bbBBBB",7,3,4,0,1,0x85))
 local move,fire,ok=process_frame_via_socket(payload,sequence-1)
 assert(ok and move==7 and fire==3)
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
'''


def run_lua(code,steps=False):
    proposed,_=builder.build(ORIGINAL.read_text(),HERE/'full_startup_wire_v2.lua')
    start=proposed.index('local function process_frame_via_socket(')
    end=proposed.index('local function determine_meta_commands(',start)
    script=PRELUDE.replace('HELPER_PATH',json.dumps(str(HERE/'full_startup_wire_v2.lua')))
    return wire_defs.definitions.Lua().run(script+proposed[start:end]+(STEPS if steps else '')+code)


class FullTailWireV2Contract(unittest.TestCase):
    def test_v2_codec_continuation_sequence_metadata_and_stop_bounds(self):
        for sequence in (1201,100000,0xffffffff):
            meta=metadata(sequence=sequence,event=0,mode='legacy',nonce='a'*64,first_play_sequence=8)
            packet=codec.encode_request(PAYLOAD,meta)
            self.assertEqual(codec.decode_request(packet),(PAYLOAD,meta))
            response=codec.encode_response(sequence,ACTION,start=1,coin=1,nonce='a'*64,latched=True,stop=True)
            self.assertEqual(codec.decode_response(response)['action'],ACTION)
            self.assertTrue(codec.decode_response(response)['stop'])
        for changes in [dict(event=10),dict(mode='gated',nonce='0'*64),dict(first_play_sequence=-1),
                        dict(sequence=0x100000000),dict(sequence=True)]:
            meta=metadata(sequence=1201,event=0,mode='legacy',nonce='a'*64,first_play_sequence=8)
            meta.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):codec.encode_request(PAYLOAD,meta)
        for sequence,kwargs in [(1200,dict(latched=True,stop=True)),(1201,dict(latched=False)),
                                (1201,dict(latched=False,stop=True))]:
            with self.assertRaises(ValueError):codec.encode_response(sequence,ACTION,nonce='a'*64,**kwargs)
        current=codec.encode_request(PAYLOAD,metadata())
        with self.assertRaises(ValueError):codec.decode_request(b'RSG1'+current[4:])
        with self.assertRaises(ValueError):codec.decode_handshake(wire_defs.codec.encode_handshake(4096,'1'*32,'2'*32))

    def test_real_journal_authority_v2_wire_schema_and_single_use(self):
        f=journal_defs.Fixture();self.addCleanup(f.close)
        f.authority=authority.StartupHandoff(f.journal,client_id=17,slot=4096,session='1'*32,
            connection='2'*32,expected_rom_sha256=journal_defs.hashlib.sha256(journal_defs.ROM).hexdigest(),
            policy_reader=lambda:f.policy,admission_reader=lambda:f.window,
            wall_ns=lambda:f.clock.wall,monotonic_ns=lambda:f.clock.mono)
        f.authority.loaded_rom(journal_defs.ROM)
        permit=f.issue();self.assertEqual(f.sent[0][:4],b'RSP2')
        self.assertEqual(json.loads(permit.payload)['schema'],'robotron-prospective-startup-journal-certificate-v2')
        f.apply(permit);self.assertEqual(f.journal.active[17]['start_reason'],'prospective_certified_first_start_v2')
        self.assertEqual(f.journal.active[17]['game_uid'],91)
        old=json.loads(f.journal.games_path.read_text());self.assertFalse(old['known_start']);self.assertFalse(old['eligible'])
        with self.assertRaises(ValueError):f.apply(permit)
        f=journal_defs.Fixture();self.addCleanup(f.close)
        a=authority.StartupHandoff(f.journal,client_id=17,slot=4096,session='1'*32,connection='2'*32,
            expected_rom_sha256=journal_defs.hashlib.sha256(journal_defs.ROM).hexdigest(),policy_reader=lambda:f.policy,
            admission_reader=lambda:f.window,wall_ns=lambda:f.clock.wall,monotonic_ns=lambda:f.clock.mono)
        a.loaded_rom(journal_defs.ROM)
        with self.assertRaises(ValueError):a.authorize(1201,ACTION,f.sent.append)
        self.assertEqual(f.sent,[]);f.no_transition()

    def test_complete_Lua_source_reversible_and_fragmented_v2_reply_preserves_payload(self):
        proposed,proof=builder.build(ORIGINAL.read_text(),HERE/'full_startup_wire_v2.lua')
        self.assertTrue(proof['reverse_restores_original_bytes'])
        with tempfile.TemporaryDirectory(prefix='robotron-new-tail-source-')as directory:
            path=Path(directory)/'proposed.lua';path.write_text(proposed)
            self.assertEqual(wire_defs.definitions.Lua().run('assert(loadfile('+json.dumps(str(path))+'));return "PASS"'),'PASS')
        result=run_lua(r'''
_startup:protect("begin",1);_startup:protect("plan",1,0,0)
response_bytes=string.pack(">c4I4BBc32c6","RSP2",1,0,0,string.rep("\0",32),string.pack(">bbBBBB",7,3,4,0,1,0x85))
local move,fire,ok=process_frame_via_socket(payload,0)
assert(ok and move==7 and fire==3)
local start,coin=_startup:protect("inputs",ok,false,false)
_startup:protect("applied",start,coin,ok,true);_startup:protect("finish",1)
return hex(socket_writes[1])..":"..hex(socket_writes[2])
''')
        hello,packet=[bytes.fromhex(x)for x in result.split(':')]
        self.assertEqual(codec.decode_handshake(hello)['slot'],4096)
        self.assertEqual(codec.decode_request(packet[4:]),(PAYLOAD,metadata()))

    def test_native_Lua_keeps_playing_after1200_and_closes_only_bounded_trace(self):
        result=run_lua(r'''
for sequence=1,1200 do step(sequence,false)end
local dense_count=#file_lines
assert(trace_file_closed and not life_file_closed and exits==0 and removes==5)
assert(fields_start==1 and fields_coin==1 and _startup.trace_closed and not _startup.closed)
assert(_startup.initialized_sequence==5 and _startup.latched_sequence==7 and _startup.first_play_sequence==8)
step(1201,false);assert(fields_start==1 and fields_coin==1 and exits==0)
assert(#file_lines==dense_count and #lifecycle_lines==2)
return hex(socket_writes[#socket_writes])
''',steps=True)
        payload,meta=codec.decode_request(bytes.fromhex(result)[4:])
        self.assertEqual(payload,PAYLOAD);self.assertEqual(meta['sequence'],1201)
        self.assertEqual(meta['event'],0);self.assertEqual(meta['mode'],'legacy')
        self.assertEqual(meta['first_play_sequence'],8)

    def test_native_Lua_controlled_stop_is_recorded_after_actual_input_application(self):
        result=run_lua(r'''
for sequence=1,1202 do step(sequence,false)end
assert(exits==0);step(1203,true)
assert(exits==1 and _startup.closed and not _startup.failed and life_file_closed)
return table.concat(lifecycle_lines,"")
''',steps=True)
        rows=[json.loads(line)for line in result.splitlines()]
        self.assertEqual([r['kind']for r in rows],['header','prefix_closed','stop_response','stop_applied','exit_requested','closed'])
        self.assertEqual(rows[1]['sequence'],1200);self.assertFalse(rows[1]['machine_exit_requested'])
        self.assertEqual(rows[2]['response_hex'],rows[3]['response_hex'])
        response=codec.decode_response(bytes.fromhex(rows[3]['response_hex']))
        self.assertTrue(response['stop']);self.assertEqual(response['action'],ACTION)
        self.assertEqual(rows[3]['sequence'],1203);self.assertTrue(rows[3]['apply_ok'])
        self.assertTrue(rows[-1]['stop_received'])

    def test_native_Lua_postprefix_legacy_response_still_records_failure(self):
        result=run_lua(r'''
for sequence=1,1200 do step(sequence,false)end
local dense_count=#file_lines
_startup:protect("begin",1201);_startup:protect("plan",1201,0,0)
response_bytes=string.pack(">c4I4BBc32c6","RSP1",1201,2,0,nonce,string.pack(">bbBBBB",7,3,4,0,1,0x85))
local move,fire,ok=process_frame_via_socket(payload,1200)
assert(not ok and _startup.failed and exits>=1 and #file_lines==dense_count)
return table.concat(lifecycle_lines,"")
''',steps=True)
        rows=[json.loads(line)for line in result.splitlines()]
        self.assertTrue(any(r['kind']=='fault'for r in rows));self.assertTrue(rows[-1]['failed'])

    def test_native_Lua_early_stop_and_missing_certified_play_fail_closed(self):
        self.assertEqual(run_lua(r'''
_startup:protect("begin",1);_startup:protect("plan",1,0,0)
response_bytes=string.pack(">c4I4BBc32c6","RSP2",1,4,0,string.rep("\0",32),string.pack(">bbBBBB",7,3,4,0,1,0x85))
local move,fire,ok=process_frame_via_socket(payload,0)
assert(not ok and _startup.failed and fields_start==0 and fields_coin==0 and exits>=1)
return "PASS"
'''),'PASS')
        self.assertEqual(run_lua(r'''
local failed=false
for sequence=1,1200 do
 _startup:protect("begin",sequence);_startup:protect("plan",sequence,0,0)
 response_bytes=string.pack(">c4I4BBc32c6","RSP2",sequence,0,0,string.rep("\0",32),string.pack(">bbBBBB",-1,-1,0,0,1,0x85))
 local move,fire,ok=process_frame_via_socket(payload,sequence-1);assert(ok)
 _startup:protect("inputs",ok,false,false);_startup:protect("applied",0,0,true,true)
 local good=pcall(function()_startup:protect("finish",sequence)end)
 if sequence<1200 then assert(good)else assert(not good);failed=true end
end
assert(failed and _startup.failed and exits>=1 and fields_start==0 and fields_coin==0)
return "PASS"
'''),'PASS')


if __name__=='__main__':unittest.main(verbosity=2)
