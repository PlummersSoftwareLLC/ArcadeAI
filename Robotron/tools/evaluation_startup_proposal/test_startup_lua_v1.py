"""CPU Lua contracts only: no emulator, numerical modules, banks or live sockets."""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
ORIGINAL = GAME / 'tools/quality_capacity_proposal/profile04/Robotron/Scripts/main.lua'
ORIGINAL_SHA = '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf'
HELPER = HERE / 'startup_prefix_v1.lua'
LIBRARY = Path('/usr/lib/aarch64-linux-gnu/liblua5.4.so.0.0.0')
LIBRARY_SHA = '1efa98f498f9867b603cba7a8e8ad1d3b44a4070774043848cb8fda216d482d6'
spec = importlib.util.spec_from_file_location('_startup_lua_source_builder_v1', HERE / 'prepare_startup_lua_v1.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class Lua:
    def __init__(self):
        if hashlib.sha256(LIBRARY.read_bytes()).hexdigest() != LIBRARY_SHA:
            raise ValueError('CPU Lua runtime bytes differ')
        self.lib = ctypes.CDLL(str(LIBRARY))
        self.lib.luaL_newstate.restype = ctypes.c_void_p
        self.lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        self.lib.lua_close.argtypes = [ctypes.c_void_p]
        self.lib.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
                                           ctypes.c_char_p, ctypes.c_char_p]
        self.lib.luaL_loadbufferx.restype = ctypes.c_int
        self.lib.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_ssize_t, ctypes.c_void_p]
        self.lib.lua_pcallk.restype = ctypes.c_int
        self.lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
        self.lib.lua_tolstring.restype = ctypes.c_void_p

    def text(self, state):
        length = ctypes.c_size_t()
        pointer = self.lib.lua_tolstring(state, -1, ctypes.byref(length))
        if pointer is None:
            raise ValueError('Lua result was not text')
        return ctypes.string_at(pointer, length.value).decode()

    def run(self, source, *, compile_only=False):
        state = self.lib.luaL_newstate()
        if not state:
            raise MemoryError('Lua CPU state allocation failed')
        try:
            self.lib.luaL_openlibs(state)
            raw = source.encode()
            status = self.lib.luaL_loadbufferx(state, raw, len(raw), b'@isolated-startup-contract', b't')
            if status:
                raise ValueError(self.text(state))
            if compile_only:
                return None
            status = self.lib.lua_pcallk(state, 0, 1, 0, 0, None)
            if status:
                raise ValueError(self.text(state))
            return self.text(state)
        finally:
            self.lib.lua_close(state)


PRELUDE = '''
local M = assert(loadfile(HELPER_PATH))()
local lines = {}
local writes, closes, reads = 0, 0, 0
local function writer(line) writes=writes+1; lines[#lines+1]=line; return true end
local r = M.new({slot=4096,limit=16,session=string.rep("a",32),write=writer,
    close_writer=function() closes=closes+1 end})
local values = {[0x9859]=0x80,[0xBDE4]=0,[0xBDE5]=0,[0xBDE6]=0,[0xBDE7]=0,[0xBDEC]=2,[0xBDED]=1}
local memory = {read_u8=function(self,addr) reads=reads+1; assert(values[addr]~=nil); return values[addr] end}
local payload = string.pack(">I2ddBI4BBBI4BBB",11128,0.0,0.0,0,0,0,0,1,20000,2,1,3)
    .. string.rep("\\0",11128*4) .. string.pack(">I4",0)
local response = string.pack("bbBBBB",4,6,4,0,1,0x85)
local function sample(frame)
    r:begin(frame,memory); r:exchange(payload); r:response(response); r:finish(4,6,1,1,true,true)
end
'''.replace('HELPER_PATH', json.dumps(str(HELPER)))


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua = Lua()
        cls.original = ORIGINAL.read_text()
        if hashlib.sha256(cls.original.encode()).hexdigest() != ORIGINAL_SHA:
            raise ValueError('Exact original frozen Lua required')
        cls.proposed = builder.build(cls.original, HELPER, ORIGINAL_SHA)

    def script(self, body):
        return self.lua.run(PRELUDE + body)

    def rows(self, body):
        return [json.loads(line) for line in self.script(body + '\nreturn table.concat(lines)\n').splitlines()]

    def test_both_full_sources_compile_and_strip_to_exact_original(self):
        self.lua.run(self.original, compile_only=True)
        self.lua.run(self.proposed, compile_only=True)
        self.assertEqual(builder.stripped(self.proposed), self.original)
        self.assertEqual(self.proposed.count(builder.BEGIN), 11)

    def test_wrong_original_source_and_duplicate_preparation_fail(self):
        with self.assertRaises(ValueError):
            builder.build(self.original + '\n', HELPER, ORIGINAL_SHA)
        with self.assertRaises(ValueError):
            builder.build(self.proposed, HELPER, hashlib.sha256(self.proposed.encode()).hexdigest())
        with self.assertRaises(ValueError):
            builder.build(self.original, Path('relative-helper.lua'), ORIGINAL_SHA)

    def test_raw_rom_wire_response_and_input_order_are_retained(self):
        rows = self.rows('r:connected(); sample(0); r:close("test")')
        self.assertEqual([x['kind'] for x in rows], ['header','connection','frame','footer'])
        row = rows[2]
        self.assertEqual((row['raw_status'], row['raw_score_hex'], row['raw_reserves'], row['raw_wave']),
                         (128,'00000000',2,1))
        self.assertEqual((row['epoch'],row['exchange'],row['frame']), (1,1,0))
        self.assertEqual((row['wire_n'],row['wire_score'],row['wire_start'],row['wire_lives']),
                         (11128,0,1,3))
        self.assertEqual(row['response_hex'],'040604000185')
        self.assertTrue(row['wire_observed'] and row['response_observed'] and row['apply_ok'] and row['socket_ok'])
        self.assertEqual((row['start_input'],row['coin_input'],row['move'],row['fire']), (1,1,4,6))
        self.assertEqual(rows[-1]['faults'],0)
        self.assertNotIn('known_start',row)

    def test_all_supported_action_lengths_retain_exact_binary_bytes(self):
        rows = self.rows('''r:connected()
        for i,action in ipairs({string.pack("bbB",-1,-1,0),string.pack("bbBBB",-1,8,4,0,1),response}) do
            r:begin(i-1,memory);r:exchange(payload);r:response(action);r:finish(-1,8,0,0,true,true)
        end
        r:close("test")''')
        self.assertEqual([r['response_hex'] for r in rows if r['kind']=='frame'],
                         ['ffff00','ff08040001','040604000185'])

    def test_boot_values_and_invalid_bcd_are_observations_not_admission(self):
        rows = self.rows('''values[0x9859]=0;values[0xBDE4]=0xFA;values[0xBDEC]=99;values[0xBDED]=171
        r:connected();sample(0);r:close("test")''')
        row = rows[2]
        self.assertEqual((row['raw_status'],row['raw_score_hex'],row['raw_reserves'],row['raw_wave']),
                         (0,'fa000000',99,171))
        self.assertTrue(all('eligible' not in x and 'known_start' not in x for x in rows))

    def test_capacity_stops_all_future_reads_and_writes(self):
        result = self.script('''r:connected()
        for i=0,15 do sample(i) end
        local oldreads,oldwrites=reads,writes
        for i=16,999 do sample(i);r:connected() end
        assert(r.closed and reads==oldreads and writes==oldwrites and closes==1)
        return table.concat(lines)''')
        rows = [json.loads(x) for x in result.splitlines()]
        self.assertEqual(sum(x['kind']=='frame' for x in rows),16)
        self.assertTrue(rows[-1]['capacity_reached'] and rows[-1]['captured_prefix_only'])
        self.assertEqual((rows[-1]['rows'],rows[-1]['attempts'],rows[-1]['faults']),(16,16,0))
        self.assertLessEqual(max(map(len,result.splitlines())),2048)

    def test_failed_reads_also_have_a_bounded_attempt_prefix(self):
        rows = self.rows('''r:connected()
        memory.read_u8=function()error("injected CPU read failure")end
        for i=0,999 do r:begin(i,memory);r:finish(4,6,1,1,true,true)end
        assert(r.closed and r.attempts==16 and writes<=r.max_events)
        ''')
        self.assertEqual(rows[-1]['kind'],'footer')
        self.assertGreater(rows[-1]['faults'],0)
        self.assertEqual(rows[-1]['rows'],0)

    def test_connection_spam_cannot_produce_unbounded_output(self):
        result = self.script('''for i=1,10000 do r:connected()end
        assert(r.closed and r.failed and writes<=r.max_events and closes==1)
        return table.concat(lines)''')
        rows=[json.loads(x) for x in result.splitlines()]
        self.assertEqual(len(rows),48)
        self.assertNotEqual(rows[-1]['kind'],'footer')

    def test_writer_failure_disables_observer_without_throwing(self):
        value = self.script('''r.write=function()error("injected writer failure")end
        r:connected();sample(0);r:close("test")
        assert(r.closed and r.failed and r.faults==1 and closes==1)
        return "preserved"''')
        self.assertEqual(value,'preserved')

    def test_zero_score_reconnect_and_duplicate_frames_remain_explicit(self):
        rows = self.rows('''r:connected();sample(0);r:connected();sample(1);sample(1);r:close("test")''')
        frames = [x for x in rows if x['kind']=='frame']
        self.assertEqual([(x['epoch'],x['exchange']) for x in frames],[(1,1),(2,1),(2,2)])
        self.assertEqual([x['wire_score'] for x in frames],[0,0,0])
        self.assertGreater(rows[-1]['faults'],0)

    def test_missing_response_and_failed_apply_are_not_silently_successful(self):
        rows = self.rows('''r:connected();r:begin(0,memory);r:exchange(payload)
        r:finish(-1,-1,0,0,false,false);r:close("test")''')
        self.assertFalse(rows[2]['response_observed'] or rows[2]['socket_ok'] or rows[2]['apply_ok'])
        self.assertNotIn('response_hex',rows[2])

    def test_parse_failure_read_abort_and_pending_exit_are_visible(self):
        rows = self.rows('''r:connected();r:begin(0,memory);r:exchange("bad")
        r:begin(1,memory);r:abort("frame_read_error")
        r:begin(2,memory);r:abort("serialize_error")
        r:begin(3,memory);r:close("machine_stop")''')
        self.assertGreaterEqual(rows[-1]['faults'],4)
        self.assertTrue(rows[-1]['pending_frame'])

    def test_bad_action_length_and_unmatched_exchange_are_faults(self):
        rows=self.rows('''r:connected();r:exchange(payload)
        r:begin(0,memory);r:exchange(payload);r:response("xx")
        r:close("test")''')
        self.assertGreaterEqual(rows[-1]['faults'],2)
        self.assertEqual(rows[-1]['rows'],0)

    def test_invalid_limits_slots_and_sessions_fail_before_capture(self):
        result=self.lua.run('''local M=assert(loadfile('''+json.dumps(str(HELPER))+'''))()
        for _,limit in ipairs({0,15,16385,1.5}) do
            assert(not pcall(M.new,{slot=4096,limit=limit,session=string.rep("a",32),write=function()return true end}))
        end
        assert(not pcall(M.new,{slot=8192,limit=16,session=string.rep("a",32),write=function()return true end}))
        assert(not pcall(M.new,{slot=4096,limit=16,session="bad",write=function()return true end}))
        return "invalid_options_rejected"''')
        self.assertEqual(result,'invalid_options_rejected')

    def test_actual_callback_keeps_original_actions_on_success_and_observer_fault(self):
        def callback(source):
            return source[source.index('function frame_callback()'):source.index('\nfunction on_mame_exit()')]
        setup='''
        local _startup_trace=r
        mem=memory;frame_counter=0;dead_frame_counter=0;last_save_time=os.time();SAVE_INTERVAL_S=300
        LEGACY_CORE_FEATURES=0;ZP1ENM_EMIT_COUNT=0;DEBUG_BYPASS_SOCKET_FOR_FRAMES=0;DEBUG_FORCE_ACTION_FRAMES=0
        current_socket={};trace_log=function()end;robotron_apply_start_wave_patch=function()end
        local applied={}
        controls={apply_action=function(self,move,fire,start,coin)
            applied={move,fire,start,coin};values[0x9859]=0x7f;return 2
        end}
        read_frame_observation=function()return {player_alive=0,score=0,replay_level=20000,num_lasers=2,
            wave_number=1,player_x16=100,player_y16=100,enemy_state={},obs={lane_summary_features={},
            local_grid_features={},pool_features={},num_humans=0}}end
        compute_frame_rewards=function()return{done=false,subj_reward=0,obj_reward=0}end
        determine_meta_commands=function()return 1,1 end
        capture_preview_payload=function()return{w=0,h=0,fmt=0}end
        rel_pos_x=function()return 0 end;rel_pos_y=function()return 0 end;wire_lives_track=function()return 3 end
        serialize_frame=function()return payload end
        difficulty_apply=function()end;wavecap_check=function()end
        process_frame_via_socket=function()
            _startup_trace:exchange(payload);_startup_trace:response(response);return 4,6,true
        end
        r:connected()
        '''
        results=[]
        for source,broken in ((self.original,False),(self.proposed,False),(self.proposed,True)):
            fault='r.write=function()error("injected")end\n' if broken else ''
            text=self.lua.run(PRELUDE+setup+callback(source)+fault+'''
            local result=frame_callback();r:close("test")
            return table.concat({tostring(result),frame_counter,prev_fire_cmd,prev_move_cmd,
                applied[1],applied[2],applied[3],applied[4],values[0x9859]},":").."|"..table.concat(lines)
            ''')
            result,raw=text.split('|',1);results.append(result)
            if source==self.proposed and not broken:
                row=next(json.loads(x) for x in raw.splitlines() if json.loads(x)['kind']=='frame')
                self.assertEqual(row['raw_status'],128)
                self.assertTrue(row['apply_ok'])
        self.assertEqual(results,['true:1:2:4:4:6:1:1:127']*3)


if __name__=='__main__':
    # Keep the original CPU service alive long enough to bracket its actual birth.
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-startup-lua-prefix-CPU-contracts-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='CPU Lua5.4 execution with synthetic memory/wire/control shims and exact original/proposed callback bodies; no real ROM, MAME, numerical modules or banks.',
        production_changed=False,protocol_selected=False,real_ROM_start_proven=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
