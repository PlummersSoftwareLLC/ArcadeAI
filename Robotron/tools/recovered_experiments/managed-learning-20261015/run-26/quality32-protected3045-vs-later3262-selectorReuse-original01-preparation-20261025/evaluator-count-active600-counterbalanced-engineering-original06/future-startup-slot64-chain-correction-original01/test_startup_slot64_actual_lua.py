"""Real Lua 5.4 CPU checks of the isolated actual startup adapter.

Run with python3 -B -m unittest -v test_startup_slot64_actual_lua.py.
No MAME, Torch, GPU, policy, process-control or real journal writes. Lua receives
bounded machine/ROM/control/io mocks. This tests client contract behavior; it
does not certify a real ROM startup or a native 64-actor run.
"""
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
OLD = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/full_startup_wire_v2.lua')
ADAPTER = HERE / 'full_startup_wire_slot64_v2.lua'
ENTRY = HERE / 'full-tail-observation-slot64-main.lua'
OLD_SHA = '58296fa89f7be658be1abf79ab41b537b511f80a5d4c98e1a17a10c5bbfbf100'
ADAPTER_SHA = '366bb60cb18e2d4961c1c2142e929f5ddd88acd2b55343d4d2523cc4160823b6'
ENTRY_SHA = 'ccdbf67bd7dc8f7b8e7a8f8ab23f6eb73214bd5d21837fe660986ed04c9ac324'


class Lua:
    def __init__(self):
        name = ctypes.util.find_library('lua5.4')
        if not name:
            raise RuntimeError('The actual Lua 5.4 shared library is required')
        self.lib = ctypes.CDLL(name)
        self.lib.luaL_newstate.restype = ctypes.c_void_p
        self.lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        self.lib.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                            ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.luaL_loadbufferx.restype = ctypes.c_int
        self.lib.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_longlong, ctypes.c_void_p]
        self.lib.lua_pcallk.restype = ctypes.c_int
        self.lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                          ctypes.POINTER(ctypes.c_size_t)]
        self.lib.lua_tolstring.restype = ctypes.c_char_p
        self.lib.lua_close.argtypes = [ctypes.c_void_p]

    def run(self, source, execute=True):
        state = self.lib.luaL_newstate()
        if not state:
            raise RuntimeError('Lua state allocation failed')
        self.lib.luaL_openlibs(state)
        try:
            raw = source.encode()
            code = self.lib.luaL_loadbufferx(state, raw, len(raw), b'actual-adapter-peer-fixture', b't')
            if code == 0 and execute:
                code = self.lib.lua_pcallk(state, 0, 0, 0, 0, None)
            error = None if code == 0 else self.lib.lua_tolstring(state, -1, None).decode(errors='replace')
            return code, error
        finally:
            self.lib.lua_close(state)


PREAMBLE = r'''
local data={ROBOTRON_FULL_STARTUP_TRACE="mock_trace",ROBOTRON_FULL_TAIL_LIFECYCLE="mock_lifecycle",
ROBOTRON_FULL_STARTUP_SLOT=__SLOT__,ROBOTRON_FULL_STARTUP_SESSION=__SESSION__,
ROBOTRON_FULL_STARTUP_CONNECTION=__CONNECTION__}
local rows,taps,exits=0,0,0
os.getenv=function(k)return data[k]end
io.open=function(name,mode)
 assert((name=="mock_trace" or name=="mock_lifecycle") and mode=="a")
 return {write=function(self,line)assert(type(line)=="string" and #line<=2048);rows=rows+1;return self end,
 flush=function()return true end,close=function()return true end}
end
local memory={read_u8=function(self,address)return address%256 end,
 install_write_tap=function(self,a,b,name,fn)
 assert(a==b and type(fn)=="function");taps=taps+1;return {remove=function()end}end}
local region={size=__ROM_SIZE__,bytewidth=1,bitwidth=8,read_u8=function(self,address)return address%256 end}
manager={machine={devices={[":maincpu"]={spaces={program=memory}}},
 memory={banks={[":mainbank"]={entry=1}},regions={[":maincpu"]=region}},exit=function()exits=exits+1 end}}
local control={set_value=function()end}
local module=(function()
'''
POSTAMBLE = r'''
end)()
local a=module.attach({p1_start=control,coin_1=control},
 {eval_mode=__EVAL__,debug_bypass_frames=__DEBUG__,force_action_frames=__FORCE__})
assert(a.slot==tonumber(data.ROBOTRON_FULL_STARTUP_SLOT) and a.installed==true and a.failed==false
 and taps==5 and exits==0 and rows==802,"full unmodified attach/install contract")
'''
FRAME = r'''
a:begin(1);a:plan(1,0,0)
local payload=string.pack(">I2",1890)..string.rep("\0",7591)..string.pack(">I4",0)
local request=a:envelope(payload,1)
assert(#request>7597)
local function response(source,advanced,level,difficulty,sequence,flags)
 local action=string.pack(">bbBBBB",-1,-1,source or 0,advanced or 0,level or 1,difficulty or 0x85)
 return string.pack(">c4I4BBc32c6","RSP2",sequence or 1,flags or 0,0,string.rep("\0",32),action)
end
'''


def fixture(source, *, slot='4159', session='a' * 32, connection='b' * 32,
            eval_mode=1, debug=0, force=0, rom_size=0x19000, body=''):
    before, after = PREAMBLE, POSTAMBLE
    values = {'__SLOT__': json.dumps(slot), '__SESSION__': json.dumps(session),
              '__CONNECTION__': json.dumps(connection), '__ROM_SIZE__': str(rom_size),
              '__EVAL__': str(eval_mode), '__DEBUG__': str(debug), '__FORCE__': str(force)}
    for key, value in values.items():
        before, after = before.replace(key, value), after.replace(key, value)
    return before + source + after + body


class ActualLuaSlot64(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua = Lua()
        cls.old_raw, cls.adapter_raw, cls.entry_raw = OLD.read_bytes(), ADAPTER.read_bytes(), ENTRY.read_bytes()
        for raw, expected in [(cls.old_raw, OLD_SHA), (cls.adapter_raw, ADAPTER_SHA), (cls.entry_raw, ENTRY_SHA)]:
            if hashlib.sha256(raw).hexdigest() != expected:
                raise RuntimeError('Peer fixture source bytes differ from the reviewed artifact')
        cls.old, cls.adapter, cls.entry = cls.old_raw.decode(), cls.adapter_raw.decode(), cls.entry_raw.decode()

    def succeeds(self, source, **kwargs):
        code, error = self.lua.run(fixture(source, **kwargs))
        self.assertEqual(code, 0, error)

    def rejects(self, source, expected, **kwargs):
        code, error = self.lua.run(fixture(source, **kwargs))
        self.assertNotEqual(code, 0, 'Invalid original input was accepted')
        self.assertIn(expected, error)

    def test_old_actual_failure_controls(self):
        for slot in ('4096', '4127'):
            with self.subTest(slot=slot):
                self.succeeds(self.old, slot=slot)
        for slot in ('4128', '4159'):
            with self.subTest(slot=slot):
                self.rejects(self.old, 'startup integer outside contract', slot=slot)

    def test_all64_actual_attach_install(self):
        for slot in range(4096, 4160):
            with self.subTest(slot=slot):
                self.succeeds(self.adapter, slot=str(slot))

    def test_slot_boundary_and_noninteger_fail_closed(self):
        for slot in ('4095', '4160', '-1', '4096.0', 'nan', 'invalid'):
            with self.subTest(slot=slot):
                self.rejects(self.adapter, 'startup integer outside contract', slot=slot)

    def test_fresh_identity_guards_retained(self):
        for values in ({'session': '0' * 32}, {'connection': '0' * 32},
                       {'session': 'a' * 31}, {'connection': 'g' * 32}):
            with self.subTest(values=values):
                self.rejects(self.adapter, 'fresh bound identity required', **values)

    def test_explicit_eval_and_no_debug_guards_retained(self):
        for values in ({'eval_mode': 0}, {'eval_mode': 2}, {'debug': 1}, {'force': 1}):
            with self.subTest(values=values):
                self.rejects(self.adapter, 'explicit evaluation without debug overrides required', **values)

    def test_actual_ROM_geometry_guard_retained(self):
        self.rejects(self.adapter, 'FULL_STARTUP_ADAPTER_FAILURE:install', rom_size=0x18fff)

    def test_forced_eval_response_contract(self):
        for action_source in (0, 4):
            with self.subTest(action_source=action_source):
                self.succeeds(self.adapter, body=FRAME + f'a:decode_response(response({action_source}),1);a:inputs(true,false,false)')
        for parameters in ('1,0,1,0x85', '0,1,1,0x85', '0,0,2,0x85', '0,0,1,0x84'):
            with self.subTest(parameters=parameters):
                self.rejects(self.adapter, 'actual forced-eval action context differs',
                             body=FRAME + f'a:decode_response(response({parameters}),1)')

    def test_sequence_and_early_stop_guards_retained(self):
        self.rejects(self.adapter, 'foreign or stale response', body=FRAME + 'a:decode_response(response(0,0,1,0x85,2),1)')
        self.rejects(self.adapter, 'shutdown before certified continuation', body=FRAME + 'a:decode_response(response(0,0,1,0x85,1,6),1)')
        self.rejects(self.adapter, 'invalid original frame sequence', body='a:begin(2)')

    def test_uncertified_continuation_and_prefix_are_rejected(self):
        self.rejects(self.adapter, 'continuation without certified first play',
                     body='a.trace_closed=true;a.mode="legacy";a.sequence=1200;a:begin(1201)')
        self.rejects(self.adapter, 'no certified play within prefix bound',
                     body='a.sequence=1200;a.input_recorded=true;a:finish(1200)')

    def test_actual_whole_entry_syntax_and_nested_path(self):
        code, error = self.lua.run(self.entry, execute=False)
        self.assertEqual(code, 0, error)
        paths = re.findall(r'_startup\s*=\s*assert\(loadfile\("([^"]+)"\)\)', self.entry)
        self.assertEqual(paths, [str(ADAPTER)])
        old_entry = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/full-tail-wire-v2-contract-original01-preparation-20261022/full-tail-observation-main.lua').read_text()
        old_paths = re.findall(r'_startup\s*=\s*assert\(loadfile\("([^"]+)"\)\)', old_entry)
        self.assertEqual(old_paths, [str(OLD)])
        self.assertNotEqual(old_paths, paths)


if __name__ == '__main__':
    unittest.main(verbosity=2)
