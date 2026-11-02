"""Actual CPU Lua54 contracts with MAME memory/register/tap interface shims."""
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]
HELPER=HERE/'startup_acceptance_tap_v1.lua'
LIBRARY=Path('/usr/lib/aarch64-linux-gnu/liblua5.4.so.0.0.0')
LIBRARY_SHA='1efa98f498f9867b603cba7a8e8ad1d3b44a4070774043848cb8fda216d482d6'
ROM3=GAME/'roms/robotron/2084_rom_3b_3005-15.a4'
ROM10=GAME/'roms/robotron/2084_rom_10b_3005-22.a7'


class Lua:
    def __init__(self):
        if hashlib.sha256(LIBRARY.read_bytes()).hexdigest()!=LIBRARY_SHA:raise ValueError('Exact CPU Lua54 library required')
        self.lib=ctypes.CDLL(str(LIBRARY))
        self.lib.luaL_newstate.restype=ctypes.c_void_p
        self.lib.luaL_openlibs.argtypes=[ctypes.c_void_p];self.lib.lua_close.argtypes=[ctypes.c_void_p]
        self.lib.luaL_loadbufferx.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p]
        self.lib.luaL_loadbufferx.restype=ctypes.c_int
        self.lib.lua_pcallk.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ssize_t,ctypes.c_void_p]
        self.lib.lua_pcallk.restype=ctypes.c_int
        self.lib.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t)]
        self.lib.lua_tolstring.restype=ctypes.c_void_p
    def text(self,state):
        count=ctypes.c_size_t();pointer=self.lib.lua_tolstring(state,-1,ctypes.byref(count))
        if pointer is None:raise ValueError('Lua contract returned no text')
        return ctypes.string_at(pointer,count.value).decode()
    def run(self,source):
        state=self.lib.luaL_newstate()
        if not state:raise MemoryError('Lua CPU state allocation failed')
        try:
            self.lib.luaL_openlibs(state);raw=source.encode()
            if self.lib.luaL_loadbufferx(state,raw,len(raw),b'@isolated-acceptance-tap-contract',b't'):raise ValueError(self.text(state))
            if self.lib.lua_pcallk(state,0,1,0,0,None):raise ValueError(self.text(state))
            return self.text(state)
        finally:self.lib.lua_close(state)


PRELUDE=r'''
local M = assert(loadfile(HELPER_PATH))()
os.execute = function() error("process operation forbidden") end
io.open = function() error("component output must use bound writer") end
local function unpack_hex(hex)
    local bytes = {}
    for i=1,#hex,2 do bytes[#bytes+1]=assert(tonumber(hex:sub(i,i+1),16)) end
    return bytes
end
local span = unpack_hex(ROM_SPAN)
local init = unpack_hex(ROM_INIT)
local function fixture(slot,session)
    local f={lines={},memory={},installs=0,removes=0,forwarded=0,reads=0,write_calls=0,region_reads=0}
    f.cpu={tag=":maincpu",state={PC={value=0x2753},CURPC={value=0x2751},DP={value=0x98},A={value=0x7f}}}
    f.bank={tag=":mainbank",entry=1}
    f.program={}
    for i,v in ipairs(span) do f.program[0x26c0+i-1]=v end
    f.ROM={}
    for i,v in ipairs(span) do f.ROM[0x126c0+i-1]=v end
    for i,v in ipairs(init) do f.ROM[0xd106+i-1]=v end
    f.ROM[0xd000],f.ROM[0xd001],f.ROM[0xd002]=0x7e,0xd1,0x06
    f.region={tag=":maincpu",size=0x19000,bytewidth=1,bitwidth=8,
        read_u8=function(self,address) f.region_reads=f.region_reads+1;return f.ROM[address] or 0 end,
        write_u8=function() error("ROM writes forbidden") end}
    f.space={data_width=8,shift=0,address_mask=65535,
        read_u8=function(self,address)
            f.reads=f.reads+1
            if f.bank.entry==1 and address<0x9000 then return f.program[address] or 0 end
            return f.memory[address] or 0
        end,
        write_u8=function() error("observer memory writes forbidden") end,
        install_write_tap=function(self,first,last,name,callback)
            assert(first==0x9859 and last==first and type(name)=="string")
            f.installs=f.installs+1;f.callback=callback
            return {remove=function() f.removes=f.removes+1 end}
        end}
    local function writer(line)
        f.write_calls=f.write_calls+1
        assert(#line<=2048)
        f.lines[#f.lines+1]=line
        return true
    end
    f.r=M.new({slot=slot or 4096,session=session or string.rep("a",32),cpu=f.cpu,
        bank=f.bank,space=f.space,region=f.region,write=writer})
    f.memory[0x9859]=255;f.memory[0x9851]=1;f.memory[0x983f]=1;f.memory[0x9840]=1
    f.memory[0xbdec]=2;f.memory[0xbded]=1
    function f:write(data,mask,offset)
        -- Mirrors the versioned handler: tap first, then next RAM handler.
        -- Explicit nil prevents MAME's optional-integer replacement branch.
        local returned=self.callback(offset or 0x9859,data,mask or 255)
        assert(returned==nil,"callback supplied a memory replacement")
        self.memory[0x9859]=data;self.forwarded=self.forwarded+1
        return returned
    end
    return f
end
local function input(f,frame,start)
    return f.r:input(frame,1,frame+1,start or 0,0,true,true)
end
local function output(f) return table.concat(f.lines) end
'''


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua=Lua();r3=ROM3.read_bytes();r10=ROM10.read_bytes()
        if hashlib.sha1(r3).hexdigest()!='06a8c8dd0b4726eb7f0bb0e89c8533931d75fc1c':raise ValueError('Exact local ROM3 required')
        if hashlib.sha1(r10).hexdigest()!='80f51d8e7ec62518afad7e56a47e0756f83f813c':raise ValueError('Exact local ROM10 required')
        cls.prelude=PRELUDE.replace('HELPER_PATH',json.dumps(str(HELPER))).replace('ROM_SPAN',json.dumps(r3[0x6c0:0x7b5].hex())).replace('ROM_INIT',json.dumps(r10[0x106:0x115].hex()))
    def run_lua(self,body):return self.lua.run(self.prelude+body)
    def rows(self,body):return [json.loads(line) for line in self.run_lua(body).splitlines()]

    def test_constructor_has_no_reads_installs_or_writer_calls(self):
        out=self.run_lua('local f=fixture();assert(f.installs==0 and f.reads==0 and f.region_reads==0 and f.write_calls==0);return "OK"')
        self.assertEqual(out,'OK')

    def test_real_Lua_header_retains_actual_region_bytes_and_register_bank_context(self):
        rows=self.rows('local f=fixture();assert(f.r:install());assert(f.r:close("test"));return output(f)')
        self.assertEqual([r['kind'] for r in rows],['header','installed','footer'])
        self.assertEqual(rows[0]['ROM_span_hex'],ROM3.read_bytes()[0x6c0:0x7b5].hex())
        self.assertEqual(rows[0]['initial_dp'],0x98);self.assertEqual(rows[0]['initial_bank_entry'],1)
        self.assertFalse(rows[0]['full_ROM_image_verified']);self.assertTrue(rows[0]['raw_provenance_only'])

    def test_all256_original_write_bytes_forward_unchanged_and_callback_returns_nil(self):
        rows=self.rows('''local f=fixture();assert(f.r:install());assert(input(f,0,1))
        for data=0,255 do f.cpu.state.A.value=data;f:write(data);assert(f.memory[0x9859]==data) end
        assert(f.forwarded==256);assert(f.r:close("test"));return output(f)''')
        writes=[r for r in rows if r['kind']=='status_write']
        self.assertEqual([r['data'] for r in writes],list(range(256)))
        self.assertEqual([r['previous_status'] for r in writes],[255]+list(range(255)))
        self.assertTrue(all(r['last_input_frame']==0 and r['last_start']==1 for r in writes))

    def test_raw_writer_distinguishes_START1_and_common_restart_instruction_sites(self):
        rows=self.rows('''local f=fixture();assert(f.r:install());assert(input(f,0,1));f:write(127)
        f.cpu.state.PC.value=0x27a7;f.cpu.state.CURPC.value=0x27a5;f:write(127)
        assert(f.r:close("test"));return output(f)''')
        writes=[r for r in rows if r['kind']=='status_write']
        self.assertEqual([(r['pc'],r['instruction_pc']) for r in writes],[(0x2753,0x2751),(0x27a7,0x27a5)])
        self.assertTrue(all(r['instruction_hex']=='9759' for r in writes))
        self.assertTrue(all('accepted_start' not in r for r in writes))

    def test_writes_before_first_input_keep_explicit_unknown_input_context(self):
        rows=self.rows('local f=fixture();assert(f.r:install());f:write(127);f.r:close("test");return output(f)')
        row=next(r for r in rows if r['kind']=='status_write')
        self.assertEqual(row['last_input_frame'],-1);self.assertEqual(row['inputs_observed'],0)
        self.assertFalse(row['last_apply_ok']);self.assertFalse(row['last_socket_ok'])

    def test_CPU_register_read_failure_preserves_original_byte_and_records_fault(self):
        rows=self.rows('''local f=fixture();assert(f.r:install());f.cpu.state.DP.value="broken"
        f:write(19);assert(f.memory[0x9859]==19);assert(f.r.failed);assert(not f.r:close("test"));return output(f)''')
        self.assertTrue(any(r['kind']=='fault' for r in rows));self.assertTrue(rows[-1]['failed'])

    def test_memory_read_exception_preserves_every_subsequent_original_byte(self):
        self.assertEqual(self.run_lua('''local f=fixture();assert(f.r:install())
        f.space.read_u8=function() error("controlled read failure") end
        for data=0,255 do f:write(data);assert(f.memory[0x9859]==data) end
        assert(f.r.failed and f.forwarded==256);return "OK"'''),'OK')

    def test_throwing_writer_and_false_or_integer_writer_return_never_replace_memory_data(self):
        self.assertEqual(self.run_lua('''for mode=1,3 do
        local f=fixture();assert(f.r:install());assert(input(f,0))
        f.r.write=function() if mode==1 then error("writer failure") elseif mode==2 then return false else return 1 end end
        for data=0,255 do f:write(data);assert(f.memory[0x9859]==data) end
        assert(f.r.failed and f.r.logging_failed and f.r.faults>0 and f.forwarded==256)
        assert(not f.r:close("test")) end;return "OK"'''),'OK')

    def test_unexpected_tap_offset_and_mask_fail_closed_without_overriding_write(self):
        self.assertEqual(self.run_lua('''for mode=1,2 do local f=fixture();assert(f.r:install())
        f:write(0x7f,mode==1 and 255 or 1,mode==1 and 0x9858 or 0x9859)
        assert(f.memory[0x9859]==127 and f.r.failed and not f.r.active) end;return "OK"'''),'OK')

    def test_STATUS_write_capacity_is_bounded_and_does_not_remove_tap_inside_callback(self):
        rows=self.rows('''local f=fixture();assert(f.r:install())
        for n=1,1024 do f:write(n%256) end
        assert(f.r.writes==513 and f.removes==0 and f.forwarded==1024)
        assert(not f.r:close("test"));assert(f.removes==1);return output(f)''')
        self.assertEqual(sum(r['kind']=='status_write' for r in rows),512)
        self.assertTrue(rows[-1]['failed']);self.assertEqual(rows[-1]['writes_observed'],513)
        self.assertLessEqual(len(rows),4620)

    def test_full4096_input_contexts_are_bounded_and_capacity_close_is_idempotent(self):
        rows=self.rows('''local f=fixture();assert(f.r:install())
        for frame=0,4095 do assert(input(f,frame,frame%2)) end
        assert(input(f,4096));assert(f.r.closed and f.removes==1)
        assert(f.r:close("test"));assert(f.removes==1);return output(f)''')
        inputs=[r for r in rows if r['kind']=='input'];self.assertEqual(len(inputs),4096)
        self.assertEqual(inputs[-1]['frame'],4095);self.assertTrue(rows[-1]['capacity_reached'])
        self.assertFalse(rows[-1]['real_ROM_start_acceptance_proven'])

    def test_input_frame_gap_reconnect_and_regressed_exchange_are_rejected(self):
        self.assertEqual(self.run_lua('''for mode=1,3 do local f=fixture();assert(f.r:install());assert(input(f,0))
        local ok
        if mode==1 then ok=f.r:input(2,1,2,0,0,true,true)
        elseif mode==2 then ok=f.r:input(1,2,2,0,0,true,true)
        else ok=f.r:input(1,1,0,0,0,true,true) end
        assert(not ok and f.r.failed);f:write(19);assert(f.memory[0x9859]==19) end;return "OK"'''),'OK')

    def test_input_result_flags_must_be_boolean_and_do_not_throw_into_original_flow(self):
        self.assertEqual(self.run_lua('''local f=fixture();assert(f.r:install())
        local ok,value=pcall(f.r.input,f.r,0,1,1,1,0,1,true)
        assert(ok and value==false and f.r.failed);f:write(127);assert(f.memory[0x9859]==127);return "OK"'''),'OK')

    def test_late_input_before_install_cannot_be_rescued_by_installing_afterward(self):
        self.assertEqual(self.run_lua('''local f=fixture();assert(not input(f,0))
        assert(not f.r:install());assert(f.installs==0 and f.r.failed);return "OK"'''),'OK')

    def test_wrong_CPU_bank_and_program_space_identity_refuse_installation(self):
        self.assertEqual(self.run_lua('''for mode=1,4 do local f=fixture()
        if mode==1 then f.cpu.tag=":othercpu" elseif mode==2 then f.bank.tag=":foreignbank"
        elseif mode==3 then f.space.data_width=16 else f.space.shift=1 end
        assert(not f.r:install() and f.installs==0 and f.r.failed) end;return "OK"'''),'OK')

    def test_wrong_region_shape_and_changed_critical_ROM_bytes_refuse_installation(self):
        self.assertEqual(self.run_lua('''for mode=1,4 do local f=fixture()
        if mode==1 then f.region.size=0x10000 elseif mode==2 then f.region.bytewidth=2
        elseif mode==3 then f.ROM[0x126fc]=0 else f.ROM[0xd10c]=0 end
        assert(not f.r:install() and f.installs==0 and f.r.failed) end;return "OK"'''),'OK')

    def test_ROM_reader_failure_is_logged_without_installing_a_partial_tap(self):
        self.assertEqual(self.run_lua('''local f=fixture();f.region.read_u8=function() error("region read failed") end
        assert(not f.r:install() and f.installs==0 and f.r.failed);return "OK"'''),'OK')

    def test_failed_install_record_leaves_callback_inert_and_original_writes_intact(self):
        self.assertEqual(self.run_lua('''local f=fixture();local writer=f.r.write
        f.r.write=function(line) if line:find('"kind":"installed"',1,true) then return false end;return writer(line) end
        assert(not f.r:install() and f.installs==1 and f.r.failed)
        f:write(127);assert(f.memory[0x9859]==127);assert(not f.r:close("test"));return "OK"'''),'OK')

    def test_repeat_install_is_refused_and_existing_callback_remains_passthrough(self):
        self.assertEqual(self.run_lua('''local f=fixture();assert(f.r:install());assert(not f.r:install())
        assert(f.installs==1 and f.r.failed);f:write(255);assert(f.memory[0x9859]==255)
        assert(not f.r:close("test"));assert(f.removes==1);return "OK"'''),'OK')

    def test_remove_exception_is_retained_and_not_retried_by_second_close(self):
        rows=self.rows('''local f=fixture();assert(f.r:install());local attempts=0
        f.r.handle.remove=function() attempts=attempts+1;error("controlled remove failure") end
        assert(not f.r:close("machine_stop"));assert(not f.r:close("test"));assert(attempts==1)
        f:write(19);assert(f.memory[0x9859]==19);return output(f)''')
        self.assertTrue(rows[-1]['failed']);self.assertTrue(any(r.get('reason')=='tap_remove_error' for r in rows))

    def test_slot_and_session_shape_are_rejected_before_any_resource_action(self):
        self.assertEqual(self.run_lua('''for mode=1,3 do
        local slot,session=4096,string.rep("a",32)
        if mode==1 then slot=0 elseif mode==2 then session="bad" else session=string.rep("G",32) end
        local ok=pcall(fixture,slot,session);assert(not ok) end;return "OK"'''),'OK')

    def test_disabled_component_has_no_writer_state_reads_or_tap_lifecycle(self):
        self.assertEqual(self.run_lua('''local r=M.disabled();assert(not r:install());assert(r:input(0,1,1,1,0,true,true))
        assert(r:close("machine_stop"));local s=r:status();assert(not s.enabled and s.closed and not s.failed and s.events==0);return "OK"'''),'OK')

    def test_active_bank_and_register_values_are_raw_observations_not_acceptance_claims(self):
        rows=self.rows('''local f=fixture();assert(f.r:install());assert(input(f,0,1));f.bank.entry=0
        f.cpu.state.DP.value=0x97;f:write(127);f.r:close("test");return output(f)''')
        row=next(r for r in rows if r['kind']=='status_write')
        self.assertEqual(row['bank_entry'],0);self.assertEqual(row['dp'],0x97);self.assertEqual(row['instruction_hex'],'0000')
        self.assertFalse(rows[-1]['real_ROM_start_acceptance_proven'])

    def test_all32_private_slots_keep_distinct_session_and_event_sequences(self):
        rows=self.rows('''local all={}
        for slot=4096,4127 do local f=fixture(slot,string.format("%032x",slot));assert(f.r:install());assert(input(f,0,1))
        f:write(127);assert(f.r:close("test"));all[#all+1]=output(f) end;return table.concat(all)''')
        self.assertEqual(len({r['slot'] for r in rows}),32);self.assertEqual(len({r['session'] for r in rows}),32)
        for slot in range(4096,4128):self.assertEqual([r['sequence'] for r in rows if r['slot']==slot],[1,2,3,4,5])


if __name__=='__main__':
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-passive-ROM-acceptance-tap-CPU-contracts-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual Lua54 callback/component with version-matched memory/register/bank/tap shims and actual local ROM startup bytes. All256 forwarded write values, logging/read failures and bounded contexts exercised; no real MAME userdata or runtime.',
        real_ROM_start_acceptance_proven=False,package_runtime_integration_present=False,
        current_cohort_altered=False,production_changed=False,protocol_selected=False,
        quality_gain_verified=False,learning_speed_gain_verified=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
