"""New producer guards: real Lua5.4, private socket I/O and owned-child shutdown.

Memory/input devices and ROM observations are synthetic here. Actual MAME is a
separate original diagnostic, never substituted by these guards.
"""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gated_runtime', HERE/'run_gated_start_trace_v1.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class Lua:
    def run(self, source):
        library = Path('/usr/lib/aarch64-linux-gnu/liblua5.4.so.0.0.0')
        assert hashlib.sha256(library.read_bytes()).hexdigest() == '1efa98f498f9867b603cba7a8e8ad1d3b44a4070774043848cb8fda216d482d6'
        lib = ctypes.CDLL(str(library))
        lib.luaL_newstate.restype = ctypes.c_void_p
        lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        lib.lua_close.argtypes = [ctypes.c_void_p]
        lib.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
        lib.luaL_loadbufferx.restype = ctypes.c_int
        lib.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]
        lib.lua_pcallk.restype = ctypes.c_int
        lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
        lib.lua_tolstring.restype = ctypes.c_void_p
        state = lib.luaL_newstate()
        assert state
        try:
            lib.luaL_openlibs(state)
            raw = source.encode()
            status = lib.luaL_loadbufferx(state, raw, len(raw), b'@gated-producer-new-contract', b't')
            if not status:
                status = lib.lua_pcallk(state, 0, 1, 0, 0, None)
            length = ctypes.c_size_t()
            pointer = lib.lua_tolstring(state, -1, ctypes.byref(length))
            value = ctypes.string_at(pointer, length.value).decode() if pointer else ''
            if status:
                raise AssertionError(value)
            return value
        finally:
            lib.lua_close(state)


PRELUDE = '''
local M=assert(loadfile(HELPER))()
local memory_values={[0x9859]=128,[0x983F]=0,[0x9840]=1,[0x9851]=1}
local callbacks,lines={},{}
local removed,exits,chunks,requests=0,0,0,0
local start_value,coin_value=0,0
local memory={read_u8=function(self,address)
 if address==0x2751 or address==0x27a5 then return 0x97 end
 if address==0x2752 or address==0x27a6 then return 0x59 end
 return memory_values[address] or 0
end,install_write_tap=function(self,lo,hi,name,callback)
 assert(lo==hi);callbacks[lo]=callback
 return {remove=function()removed=removed+1 end}
end}
local cpu={state={CURPC={value=0x2751},PC={value=0x2753},DP={value=0x98},A={value=0x7f}}}
local g
local function response()
 local seq=g.sequence
 return string.pack(">c4I4BBc32","RSC1",seq,(seq>=768 and seq<771) and 1 or 0,
  (seq>=750 and seq<753) and 1 or 0,seq>=768 and string.rep("a",32) or string.rep("\\0",32))
end
g=M.new({slot=4096,session=string.rep("1",32),connection=string.rep("2",32),limit=1200,start_sequence=768,
 memory=memory,cpu=cpu,bank={entry=0},region={size=0x19000,bytewidth=1,bitwidth=8,
 read_u8=function(self,address)return address%256 end},
 start={set_value=function(self,v)start_value=v end},coin={set_value=function(self,v)coin_value=v end},
 send=function(data)requests=requests+1;local n=string.unpack(">I4",data);assert(n==#data-4);return true end,
 receive=function(n)assert(n==42);return response()end,
 write=function(line)assert(#line<=2048);lines[#lines+1]=line;if line:find('"kind":"raw_ROM_chunk"',1,true)then chunks=chunks+1 end;return true end,
 exit=function()exits=exits+1 end})
'''


def lua(code):
    source = PRELUDE.replace('HELPER', json.dumps(str(HERE/'gated_start_trace_v1.lua'))) + code
    return Lua().run(source)


def snapshot(protocol, sequence=None, **changes):
    seq = protocol.sequence + 1 if sequence is None else sequence
    start, coin = runtime.schedule(seq-1)
    row = dict(schema='robotron-gated-start-trace-v1', kind='snapshot', slot=4096,
        session=protocol.session, connection=protocol.connection, sequence=seq,
        status=127, score_hex='00000000', wave=0, reserves=0, credit=1,
        current_player=0, player_count=1, last_start=start, last_coin=coin,
        nonce=protocol.nonce.hex(), last_socket_ok=seq > 1, last_apply_ok=seq > 1,
        accepted_site_count=0, accepted_site_sequence=-1, initialized_sequence=-1, first_play_sequence=-1)
    row.update(changes)
    return (json.dumps(row)+'\n').encode()


def protocol():
    now = time.monotonic_ns()
    events = []
    p = runtime.Protocol('1'*32, '2'*32, now-1_000_000_000, now+60_000_000_000, events.append)
    return p, events


class ProducerContract(unittest.TestCase):
    def test_lua_full_prefix_and_raw_ROM_coverage(self):
        self.assertEqual(lua('''
g:install()
for i=1,1200 do
 if i==775 then memory_values[0xBDED]=1;memory_values[0xBDEC]=2 end
 if i==857 then memory_values[0x9859]=0 end
 g:step()
 if i==768 then assert(callbacks[0x9859](0x9859,0x7f,255)==nil) end
end
assert(chunks==800 and requests==1200 and removed==5 and exits==1)
assert(g.closed and not g.failed and g.accepted_site_count==1)
assert(g.initialized_sequence==775 and g.first_play_sequence==857)
assert(start_value==0 and coin_value==0 and #lines<4096)
local n=0
for _,line in ipairs(lines)do
 if line:find('"kind":"raw_ROM_chunk"',1,true)then
  assert(line:find('"offset":'..n..',',1,true));n=n+128
 end
end
assert(n==0x19000)
return "PASS"
'''), 'PASS')

    def test_lua_no_START_after_transport_or_setter_failure(self):
        for setup in ['g.send=function()return false end',
                      'g.receive=function()error("original read timeout")end',
                      'g.start.set_value=function(self,v)if v==1 then error("setter failure")end;start_value=v end']:
            with self.subTest(setup=setup):
                self.assertEqual(lua('g:install();g.sequence=767\n'+setup+'''
g:step()
assert(g.closed and g.failed and exits==1 and removed==5)
assert(start_value==0 and coin_value==0)
return "PASS"
'''), 'PASS')

    def test_lua_stale_premature_or_changed_nonce_rejected(self):
        responses = ["string.pack('>c4I4BBc32','RSC1',767,1,0,string.rep('a',32))",
                     "string.pack('>c4I4BBc32','RSC1',768,1,0,string.rep('\\0',32))",
                     "string.pack('>c4I4BBc32','RSC1',768,0,0,string.rep('a',32))",
                     "string.rep('x',41)"]
        for raw in responses:
            with self.subTest(raw=raw):
                self.assertEqual(lua('g:install();g.sequence=767;g.receive=function()return '+raw+''' end
g:step();assert(g.closed and g.failed and start_value==0 and coin_value==0)
return "PASS"
'''), 'PASS')

    def test_lua_common_restart_is_not_accepted_START_and_tap_errors_defer(self):
        self.assertEqual(lua('''
g:install();g.sequence=768
cpu.state.CURPC.value=0x27a5
assert(callbacks[0x9859](0x9859,0x7f,255)==nil and g.accepted_site_count==0)
cpu.state.CURPC.value=0x2751
assert(callbacks[0x9859](0x9859,0x7f,255)==nil and g.accepted_site_count==1)
g.writes=512
assert(callbacks[0x9859](0x9859,0x7f,255)==nil)
assert(g.failed and not g.closed and removed==0)
g:step();assert(g.closed and removed==5 and start_value==0)
return "PASS"
'''), 'PASS')

    def test_protocol_complete_nonce_join_is_still_uncertified(self):
        p, events = protocol()
        replies = []
        for seq in range(1,1201):
            changes = dict(accepted_site_count=1, accepted_site_sequence=768,
                           initialized_sequence=775, wave=1, reserves=2) if seq >= 775 else {}
            p.process(snapshot(p, **changes), replies.append)
        self.assertEqual(len(replies), 1200)
        self.assertEqual(runtime.RESPONSE.unpack(replies[767])[:4], (b'RSC1',768,1,0))
        self.assertEqual(runtime.RESPONSE.unpack(replies[749])[:4], (b'RSC1',750,0,1))
        self.assertFalse(p.bracket['game_start_certified'])
        self.assertFalse(p.bracket['journal_eligibility_changed'])
        self.assertEqual(sum(e['kind']=='clock_bracket' for e in events), 1)
        with self.assertRaises(ValueError):
            p.process(snapshot(p), replies.append)

    def test_protocol_rejects_foreign_or_repeated_frame_and_late_authorization(self):
        for change in [dict(session='9'*32), dict(connection='9'*32), dict(slot=True),
                       dict(sequence=2), dict(last_socket_ok=True), dict(nonce='f'*64),
                       dict(accepted_site_count=2), dict(last_start=1)]:
            p, _ = protocol()
            replies = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.process(snapshot(p, **change), replies.append)
            self.assertFalse(replies)
        p = runtime.Protocol('1'*32,'2'*32,1,2,lambda row: None)
        p.sequence=767
        replies=[]
        with self.assertRaises(ValueError):
            p.process(snapshot(p), replies.append)
        self.assertFalse(replies)

    def test_real_fragmented_socket_frame_and_truncated_EOF(self):
        host, peer = socket.socketpair()
        host.settimeout(2);peer.settimeout(2)
        p, _ = protocol()
        raw=snapshot(p)
        failures=[]
        def serve():
            try:
                p.process(runtime.read_frame(host), host.sendall)
            except BaseException as error:
                failures.append(error)
        worker=threading.Thread(target=serve)
        worker.start()
        try:
            packet=struct.pack('>I',len(raw))+raw
            for value in packet:
                peer.sendall(bytes([value]))
            self.assertEqual(len(runtime.recv_exact(peer,42)),42)
            worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertFalse(failures)
        finally:
            host.close();peer.close()
            worker.join(3)
        host, peer=socket.socketpair()
        try:
            peer.sendall(struct.pack('>I',10)+b'{}');peer.shutdown(socket.SHUT_WR)
            with self.assertRaises(ValueError):
                runtime.read_frame(host)
        finally:
            host.close();peer.close()

    def test_only_exact_owned_child_can_be_terminated_actual_signal_preserved(self):
        child=subprocess.Popen(['/usr/bin/python3.12','-I','-B','-c','import time;time.sleep(20)'])
        original=runtime.birth(child.pid)
        try:
            with self.assertRaises(ValueError):
                runtime.terminate_owned(child,original+1)
            self.assertIsNone(child.poll())
            self.assertEqual(runtime.terminate_owned(child,original),-15)
            self.assertEqual(child.returncode,-15)
        finally:
            if child.poll() is None:
                runtime.terminate_owned(child,original)


if __name__=='__main__':
    unittest.main(verbosity=2)
