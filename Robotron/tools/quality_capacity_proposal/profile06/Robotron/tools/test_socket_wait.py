"""Exercise the actual Lua socket exchange with deterministic host clocks.

The standalone system Lua VM is only a test harness. The production helper
does not link Lua or access MAME's Lua state.
"""
import ctypes
import ctypes.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "Scripts" / "main.lua"


class SocketWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = ctypes.util.find_library("lua5.4")
        if not library:
            raise unittest.SkipTest("A standalone Lua 5.4 library is needed for Lua protocol tests")
        cls.lua = ctypes.CDLL(library)
        cls.lua.luaL_newstate.restype = ctypes.c_void_p
        cls.lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
        cls.lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        cls.lua.luaL_loadstring.restype = ctypes.c_int
        cls.lua.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]
        cls.lua.lua_pcallk.restype = ctypes.c_int
        cls.lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        cls.lua.lua_tolstring.restype = ctypes.c_char_p
        cls.lua.lua_close.argtypes = [ctypes.c_void_p]
        source = SCRIPT.read_text()
        cls.source = source
        cls.configuration = source[source.index("-- Host socket wait configuration."):
                                   source.index("-- End host socket wait configuration.")]
        cls.exchange = source[source.index("local function process_frame_via_socket("):
                              source.index("local function determine_meta_commands(")]

    def run_lua(self, source, execute=True):
        state = self.lua.luaL_newstate()
        self.assertTrue(state)
        try:
            self.lua.luaL_openlibs(state)
            result = self.lua.luaL_loadstring(state, source.encode())
            if result == 0 and execute:
                result = self.lua.lua_pcallk(state, 0, 0, 0, 0, None)
            if result:
                self.fail(self.lua.lua_tolstring(state, -1, None).decode(errors="replace"))
        finally:
            self.lua.lua_close(state)

    def exchange_test(self, body, *, enabled=True, helper=True, clock=True, preload=False):
        prefix = r'''
local wall, cpu, waits, reads, writes, frames = 0, 0, 0, 0, {}, 77
local events = {}
local enabled, helper_ready, clock_ready = ENABLED, HELPER, CLOCK
local preload_active = PRELOAD
os.getenv = function(name)
    if name == "ROBOTRON_SOCKET_WAIT_US" then return enabled and "200" or "0" end
    if name == "ROBOTRON_HOST_WAIT_LIB" then return "/fake/hostwait.so" end
    if name == "ROBOTRON_SOCKET_WAIT_ACTIVE" then return preload_active and "select-v1" or nil end
end
os.clock = function()
    -- Enabled tests freeze CPU time: an accidental os.clock deadline cannot
    -- pass merely because the simulated host thread is sleeping.
    if not enabled or not helper_ready or not clock_ready then cpu = cpu + 0.0001 end
    return cpu
end
emu = clock_ready and {
    osd_ticks = function() return wall * 1000000000 end,
    osd_ticks_per_second = function() return 1000000000 end
} or {}
package.loadlib = function(path, entry)
    assert(not preload_active, "preload backend must not depend on Lua dynamic loading")
    assert(path == "/fake/hostwait.so" and entry == "robotron_socket_wait")
    if not helper_ready then return nil, "missing helper" end
    return function() waits = waits + 1; wall = wall + 0.0002 end
end
'''.replace("ENABLED", str(enabled).lower()).replace("HELPER", str(helper).lower()).replace("CLOCK", str(clock).lower()).replace("PRELOAD", str(preload).lower())
        harness = r'''
unpack = table.unpack
SOCKET_READ_TIMEOUT_S = 0.01
ACTION_RX_BUFFER = ""
local previews = false
trace_log = function() end
set_preview_stream_enabled = function(flag) previews = flag end
close_socket = function()
    current_socket = nil
    ACTION_RX_BUFFER = ""
    set_preview_stream_enabled(false)
    PREVIEW_HUD_ENABLED = false
end
open_socket = function() error("unexpected reconnect") end
current_socket = {
    write = function(self, payload) writes[#writes + 1] = payload end,
    read = function(self, need)
        reads = reads + 1
        assert(reads < 1000, "socket deadline used CPU time while sleeping")
        assert(frames == 77, "emulated frame advanced inside socket exchange")
        local event = events[1]
        if preload_active and enabled and clock_ready then
            -- The native select shim waits for readiness inside read(), and
            -- returns immediately if bytes are already available.
            if not event or event[1] > wall then
                wall = math.min(wall + 0.0002, event and event[1] or math.huge)
            end
        end
        local observed_time = (enabled and helper_ready and clock_ready) and wall or cpu
        if event and observed_time >= event[1] then
            local chunk = string.sub(event[2], 1, need)
            event[2] = string.sub(event[2], need + 1)
            if #event[2] == 0 then table.remove(events, 1) end
            return chunk
        end
        return ""
    end
}
'''
        self.run_lua(prefix + self.configuration + harness + self.exchange + body)

    def test_whole_script_still_compiles_in_lua54(self):
        self.run_lua(self.source, execute=False)

    def test_immediate_full_packet_does_not_sleep_or_advance_frame(self):
        self.exchange_test(r'''
events = {{0, string.pack("bbBBBB", -1, 7, 0xC1, 1, 2, 0x85)}}
local move, fire, ok = process_frame_via_socket("state", 77)
assert(ok and move == -1 and fire == 7)
assert(waits == 0 and wall == 0 and frames == 77)
assert(START_ADVANCED and START_LEVEL_MIN == 2 and SERVER_IS_EVAL and SERVER_DIFFICULTY == 5)
assert(last_action_source == 1 and previews and PREVIEW_HUD_ENABLED)
assert(#writes == 1 and string.unpack(">I4", writes[1]) == 5 and string.sub(writes[1], 5) == "state")
frames = frames + 1 -- the caller can advance once only after the exchange
assert(frames == 78)
''')

    def test_split_packet_accumulates_across_empty_reads_before_settle(self):
        self.exchange_test(r'''
local packet = string.pack("bbBBBB", 2, 3, 1, 0, 1, 5)
events = {{0, string.sub(packet, 1, 3)}, {0.001, string.sub(packet, 4, 5)},
          {0.002, string.sub(packet, 6)}}
local move, fire, ok = process_frame_via_socket("s", 77)
assert(ok and move == 2 and fire == 3 and SERVER_DIFFICULTY == 5)
assert(waits > 0 and wall >= 0.002 and wall < 0.003)
assert(#ACTION_RX_BUFFER == 0 and frames == 77)
''')

    def test_read_timeout_uses_wall_time_and_closes_partial_packet_connection(self):
        self.exchange_test(r'''
local messages = {}
print = function(message) messages[#messages + 1] = message end
CLIENT_SLOT = 17
events = {{0, string.char(2, 3)}}
local move, fire, ok = process_frame_via_socket("s", 77)
assert(not ok and move == -1 and fire == -1 and current_socket == nil)
assert(wall >= 0.01 and wall <= 0.0103 and cpu == 0)
assert(#ACTION_RX_BUFFER == 0 and frames == 77)
assert(#messages == 1 and string.find(messages[1], "[SOCKET ACTION TIMEOUT]", 1, true))
assert(string.find(messages[1], "slot=17 count=1 suppressed=0 partial_bytes=2", 1, true))
assert(string.find(messages[1], "clock=host_wall", 1, true))
''')

    def test_timeout_log_is_independent_of_trace_and_rate_limits_cumulative_count(self):
        self.exchange_test(r'''
local messages = {}
print = function(message) messages[#messages + 1] = message end
os.time = function() return 1700000000 + math.floor(wall) end
DEBUG_STARTUP_TRACE = false
CLIENT_SLOT = 9
events = {{0, string.char(1, 2)}}
local test_transport = current_socket
local move, fire, ok = process_frame_via_socket("first", 77)
assert(not ok and move == -1 and fire == -1 and #messages == 1 and current_socket == nil)
current_socket = test_transport -- a new simulated connection, for log-rate testing
move, fire, ok = process_frame_via_socket("second", 77)
assert(not ok and move == -1 and fire == -1 and #messages == 1 and current_socket == nil)
wall = 31
events = {{31, string.char(1)}}
current_socket = test_transport
move, fire, ok = process_frame_via_socket("third", 77)
assert(not ok and move == -1 and fire == -1 and #messages == 2 and current_socket == nil)
assert(string.find(messages[1], "slot=9 count=1 suppressed=0 partial_bytes=2", 1, true))
assert(string.find(messages[2], "slot=9 count=3 suppressed=1 partial_bytes=1", 1, true))
assert(#ACTION_RX_BUFFER == 0 and frames == 77)
''', preload=True)

    def test_readiness_wait_uses_wall_time_without_loading_lua_module(self):
        self.exchange_test(r'''
events = {{0.001, string.pack("bbBBBB", 2, 3, 1, 0, 1, 5)}}
local move, fire, ok = process_frame_via_socket("s", 77)
assert(ok and move == 2 and fire == 3 and SERVER_DIFFICULTY == 5)
assert(waits == 0 and wall >= 0.001 and wall < 0.0011 and cpu == 0 and frames == 77)
assert(string.find(socket_wait_description, "readiness wait", 1, true))
''', preload=True)

    def test_readiness_timeout_does_not_use_cpu_time(self):
        self.exchange_test(r'''
local move, fire, ok = process_frame_via_socket("s", 77)
assert(not ok and move == -1 and fire == -1 and current_socket == nil)
assert(waits == 0 and wall >= 0.01 and wall <= 0.0103 and cpu == 0 and frames == 77)
''', preload=True)

    def test_active_readiness_shim_rejects_missing_host_clock(self):
        self.run_lua(r'''
os.getenv = function(name)
    if name == "ROBOTRON_SOCKET_WAIT_US" then return "200" end
    if name == "ROBOTRON_SOCKET_WAIT_ACTIVE" then return "select-v1" end
end
emu = {}
local ok, failure = pcall(function()
''' + self.configuration + r'''
end)
assert(not ok and string.find(failure, "requires a host wall clock", 1, true))
''')

    def test_tail_arriving_just_before_settle_deadline_is_not_parsed_as_legacy(self):
        for options in ({}, {"preload": True}, {"enabled": False}, {"helper": False}, {"clock": False}):
            for prefix in (3, 5):
                with self.subTest(prefix=prefix, options=options):
                    self.exchange_test(r'''
local packet = string.pack("bbBBBB", 2, 3, 1, 0, 1, 5)
events = {{0, string.sub(packet, 1, PREFIX)}, {0.00295, string.sub(packet, PREFIX + 1)}}
local move, fire, ok = process_frame_via_socket("s", 77)
assert(ok and move == 2 and fire == 3 and SERVER_DIFFICULTY == 5)
assert(#events == 0 and #ACTION_RX_BUFFER == 0)
if enabled and helper_ready and clock_ready and not preload_active then assert(wall >= 0.003 and wall <= 0.0033) end
assert(frames == 77)
'''.replace("PREFIX", str(prefix)), **options)

    def test_three_and_five_byte_legacy_settle_use_wall_time(self):
        for length in (3, 5):
            with self.subTest(length=length):
                self.exchange_test(r'''
local packet = string.pack("bbBBB", 1, 4, 2, 1, 6)
events = {{0, string.sub(packet, 1, LENGTH)}}
local move, fire, ok = process_frame_via_socket("s", 77)
assert(ok and move == 1 and fire == 4)
assert(wall >= 0.003 and wall <= 0.0033 and cpu == 0)
assert(frames == 77)
'''.replace("LENGTH", str(length)))

    def test_buffered_packets_are_consumed_once_without_new_wait(self):
        self.exchange_test(r'''
ACTION_RX_BUFFER = string.pack("bbBBBB", 0, 1, 1, 0, 1, 5)
    .. string.pack("bbBBBB", 2, 3, 1, 0, 1, 5)
local a, b, ok = process_frame_via_socket("one", 77)
assert(ok and a == 0 and b == 1 and #ACTION_RX_BUFFER == 6)
a, b, ok = process_frame_via_socket("two", 77)
assert(ok and a == 2 and b == 3 and #ACTION_RX_BUFFER == 0)
assert(waits == 0 and reads == 0 and #writes == 2)
''')

    def test_default_missing_helper_and_missing_clock_keep_busy_fallback(self):
        for options in ({"enabled": False}, {"helper": False}, {"clock": False}):
            with self.subTest(options=options):
                self.exchange_test(r'''
local move, fire, ok = process_frame_via_socket("s", 77)
assert(not ok and move == -1 and fire == -1 and current_socket == nil)
assert(waits == 0 and wall == 0 and cpu >= 0.01 and cpu < 0.011)
assert(frames == 77)
''', **options)

    def test_read_and_write_exceptions_close_connection_and_return_neutral(self):
        for operation in ("read", "write"):
            with self.subTest(operation=operation):
                self.exchange_test(r'''
local closed = false
close_socket = function() closed = true end
current_socket.OPERATION = function() error("injected transport error") end
local move, fire, ok = process_frame_via_socket("s", 77)
assert(not ok and move == -1 and fire == -1 and closed and frames == 77)
'''.replace("OPERATION", operation))


if __name__ == "__main__":
    unittest.main()
