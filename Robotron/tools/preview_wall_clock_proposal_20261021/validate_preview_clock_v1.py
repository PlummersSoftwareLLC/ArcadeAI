"""Private CPU Lua preview checks; production Lua and actors remain untouched."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import time


def checked(entry):
    p = Path(entry['path'])
    raw = p.read_bytes()
    assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
    return raw


class Lua:
    def __init__(self, library):
        self.lib = ctypes.CDLL(str(library))
        lib = self.lib
        lib.luaL_newstate.restype = ctypes.c_void_p
        lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        lib.lua_close.argtypes = [ctypes.c_void_p]
        lib.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
                                       ctypes.c_char_p, ctypes.c_char_p]
        lib.luaL_loadbufferx.restype = ctypes.c_int
        lib.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_ssize_t, ctypes.c_void_p]
        lib.lua_pcallk.restype = ctypes.c_int
        lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
        lib.lua_tolstring.restype = ctypes.c_void_p
        lib.lua_pushnumber.argtypes = [ctypes.c_void_p, ctypes.c_double]
        self.callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
        lib.lua_pushcclosure.argtypes = [ctypes.c_void_p, self.callback_type, ctypes.c_int]
        lib.lua_setglobal.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    def text(self, state):
        size = ctypes.c_size_t()
        pointer = self.lib.lua_tolstring(state, -1, ctypes.byref(size))
        assert pointer, 'Lua did not return text'
        return ctypes.string_at(pointer, size.value).decode()

    def run(self, source, *, compile_only=False):
        state = self.lib.luaL_newstate()
        assert state
        callbacks = []
        try:
            self.lib.luaL_openlibs(state)
            def host_ticks(s):
                self.lib.lua_pushnumber(s, time.monotonic_ns())
                return 1
            def host_wait(s):
                time.sleep(1 / 60)
                return 0
            for name, function in [(b'_host_ticks', host_ticks), (b'_host_wait', host_wait)]:
                callback = self.callback_type(function)
                callbacks.append(callback)
                self.lib.lua_pushcclosure(state, callback, 0)
                self.lib.lua_setglobal(state, name)
            raw = source.encode()
            status = self.lib.luaL_loadbufferx(state, raw, len(raw), b'@private-preview-clock', b't')
            if status:
                raise ValueError(self.text(state))
            if compile_only:
                return
            status = self.lib.lua_pcallk(state, 0, 1, 0, 0, None)
            if status:
                raise ValueError(self.text(state))
            return self.text(state)
        finally:
            self.lib.lua_close(state)


def part(source, start, end):
    assert source.count(start) == source.count(end) == 1
    return source[source.index(start):source.index(end)]


def fixture(source, mode='wall'):
    environment = {
        'wall': '{ROBOTRON_SOCKET_WAIT_US="1000",ROBOTRON_SOCKET_WAIT_ACTIVE="select-v1"}',
        'legacy': '{}',
        'unsupported': '{ROBOTRON_SOCKET_WAIT_US="1000"}',
    }[mode]
    return '\n'.join([
        'local fixture_env=' + environment,
        'os.getenv=function(name) return fixture_env[name] end',
        'local fake_wall,fake_cpu=0,0; local real_cpu_clock=os.clock; local real_host_clock=false',
        'os.clock=function()return fake_cpu end',
        'emu={osd_ticks=function()if real_host_clock then return _host_ticks() end;return fake_wall*1e9 end,',
        'osd_ticks_per_second=function()return 1e9 end}',
        part(source, 'function env_number(', '-- Host socket wait configuration.'),
        part(source, '-- Host socket wait configuration.', 'local socket_receive_timeout_count'),
        part(source, 'PREVIEW_FORMAT_RGB565 =', 'function hud_draw_requested()'),
        'local captures=0; local image_w,image_h=1,1; local pixels=string.pack("=I4",0xff00ff00)',
        'manager={machine={video={snapshot_size=function()return image_w,image_h end,',
        'snapshot_pixels=function()captures=captures+1;return pixels end}}}',
        part(source, 'function clear_pending_preview()', 'local function frame_done_callback()'),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-private-preview-clock-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    output = Path(job['output'])
    output.mkdir(mode=0o700)
    original, candidate = [checked(job[k]).decode() for k in ('original', 'candidate')]
    assert original == checked(job['production']).decode()
    old = '    local now_s = os.clock()\n'
    new = '    local now_s = socket_time_now()\n'
    assert original.count(old) == 1 and candidate == original.replace(old, new, 1)
    assert candidate.replace(new, old, 1) == original
    library = Path(job['Lua_library']['path'])
    checked(job['Lua_library'])
    lua = Lua(library)
    lua.run(original, compile_only=True)
    lua.run(candidate, compile_only=True)
    cases = [dict(case='whole_sources_compile_single_call_difference', passed=True)]

    # Run the original capture, real RGB conversion, resizing and RLE routines.
    pixel_body = '''
    set_preview_stream_enabled(true)
    image_w,image_h=4,2
    pixels=string.pack("=I4I4I4I4I4I4I4I4",0,0,0,0,0,0xff00ff00,0,0xff0000ff)
    PREVIEW_MAX_WIDTH,PREVIEW_MAX_HEIGHT=2,1
    capture_game_preview()
    assert(pending_preview_w==2 and pending_preview_h==1)
    assert(pending_preview_fmt==PREVIEW_FORMAT_RGB565)
    assert(pending_preview_blob==string.pack(">I2I2",0x07e0,0x001f))
    set_preview_stream_enabled(false)
    local oldcaptures=captures;fake_wall,fake_cpu=10,10
    capture_game_preview()
    assert(captures==oldcaptures and pending_preview_blob==nil and pending_preview_w==0)
    set_preview_stream_enabled(true)
    image_w,image_h=64,64;PREVIEW_MAX_WIDTH,PREVIEW_MAX_HEIGHT=0,0
    pixels=string.rep(string.pack("=I4",0xffff0000),64*64)
    capture_game_preview()
    assert(pending_preview_fmt==PREVIEW_FORMAT_RGB565_RLE)
    assert(pending_preview_blob==string.rep(string.char(0xff)..string.pack(">I2",0xf800),32))
    return "pixels_resize_disable_RLE_unchanged"
    '''
    for source in (original, candidate):
        assert lua.run(fixture(source) + pixel_body) == 'pixels_resize_disable_RLE_unchanged'
    cases.append(dict(case='actual_RGB565_resize_RLE_and_disabled_capture', passed=True))

    schedule = '''
    set_preview_stream_enabled(true)
    for i=0,200 do fake_wall=i/100;capture_game_preview() end
    return tostring(captures)
    '''
    old_count, new_count = [int(lua.run(fixture(source) + schedule)) for source in (original, candidate)]
    assert old_count == 1 and 45 <= new_count <= 61
    cases.append(dict(case='host_wait_with_stationary_CPU_clock', original_captures=old_count,
                      candidate_captures=new_count, simulated_wall_seconds=2, passed=True))

    fallback = '''
    assert(socket_clock_kind=="process_cpu")
    set_preview_stream_enabled(true)
    local counts={}
    for i=0,200 do fake_wall=i;fake_cpu=i/100;capture_game_preview();counts[#counts+1]=captures end
    return table.concat(counts,",")
    '''
    for mode in ('legacy', 'unsupported'):
        assert lua.run(fixture(original, mode) + fallback) == lua.run(fixture(candidate, mode) + fallback)
    cases.append(dict(case='legacy_and_unsupported_clock_fallback_exact_schedule', passed=True))

    # The exact original clock selector calls the host-tick bridge; os.clock is real here.
    timing = '''
    os.clock=real_cpu_clock
    real_host_clock=true
    set_preview_stream_enabled(true)
    local begin=_host_ticks()/1e9;local cpu_begin=os.clock();local callbacks=0
    repeat capture_game_preview();callbacks=callbacks+1;_host_wait()
    until (_host_ticks()/1e9-begin)>=1.2
    return string.format("%d %.9f %.9f %d",captures,_host_ticks()/1e9-begin,os.clock()-cpu_begin,callbacks)
    '''
    trials = []
    for name, source in [('original', original), ('candidate', candidate)]:
        row = lua.run(fixture(source) + timing).split()
        count, wall, cpu, callbacks = int(row[0]), float(row[1]), float(row[2]), int(row[3])
        assert wall >= 1.2 and cpu < wall * .35 and callbacks >= 15
        trials.append(dict(source=name, captures=count, wall_seconds=wall,
                           process_CPU_seconds=cpu, callbacks=callbacks, captures_per_wall_second=count/wall))
    assert trials[0]['captures_per_wall_second'] < 10
    assert trials[1]['captures_per_wall_second'] > 10
    assert trials[1]['captures'] > trials[0]['captures'] * 2
    cases.append(dict(case='actual_Lua_CPU_clock_vs_host_wait_wall_clock', trials=trials, passed=True))

    assert checked(job['production']) == original.encode()
    report = dict(schema='robotron-private-preview-clock-CPU-report-v1',
                  status='FIVE_PRIVATE_LUA_CHECKS_PASS_SOURCE_UNAPPLIED', cases=cases,
                  original=job['original'], candidate=job['candidate'], Lua_library=job['Lua_library'],
                  job_sha256=args.job_sha256, source_sha256=args.source_sha256,
                  production_changed=False, production_actors_restarted=False,
                  actual_MAME_started=False, sockets_opened=False, CUDA_initialized=False,
                  production_preview_FPS_gain_measured=False, useful_training_throughput_gain_measured=False,
                  limits=['Actual extracted Lua routines and OS clocks with a private fake video source.',
                          'Host tick callback is a Python monotonic-clock bridge, not an actual MAME clock.',
                          'Production capture cost, preview delivery and useful learning throughput remain unmeasured.',
                          'Deployment deferred until evaluation freeze release and a properly owned actor handoff.'])
    with (output/'report.json').open('x') as stream:
        json.dump(report, stream, separators=(',', ':'), allow_nan=False)
        stream.write('\n');stream.flush();os.fchmod(stream.fileno(), 0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'], cases=len(cases), report=str(output/'report.json'))), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
