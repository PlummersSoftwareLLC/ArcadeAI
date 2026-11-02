"""Offline exact-source Lua5.4 capture comparison. No MAME/native actor action.

Uses deterministic synthetic snapshot bytes. Actual MAME snapshot/render cost,
socket/network/server/browser cost and live FPS are outside this CPU benchmark.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'main-lua-selected-preview30-candidate.lua'
CANDIDATE = HERE / 'main-lua-preview-fast-final-v3.lua'


def main():
    old = PARENT.read_text(); new = CANDIDATE.read_text()
    assert hashlib.sha256(old.encode()).hexdigest() == '507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab'
    proof = json.loads((HERE / 'exact-source-transform-definitions-v3.json').read_text())
    assert hashlib.sha256(new.encode()).hexdigest() == proof['candidate_sha256']
    reverse = new
    for before, after in reversed(proof['exact_replacements']):
        assert reverse.count(after) == 1
        reverse = reverse.replace(after, before, 1)
    assert reverse == old
    def capture_section(source):
        marker = 'local PREVIEW_RLE_BLACK128' if 'local PREVIEW_RLE_BLACK128' in source else 'local function rle_compress_rgb565_words(blob)'
        start = source.index(marker)
        end = source.index('local function frame_done_callback()', start)
        return source[start:end] + '\nreturn capture_game_preview\n'
    raw_old = ('local function old_convert(src, vw, vh, tw, th)\n' +
               proof['old_capture_conversion'].replace('local blob = table.concat(out)', 'return table.concat(out)') +
               '\nend\nreturn old_convert\n')
    raw_new = proof['selected_conversion_helper'] + '\nreturn preview_rgb565_bytes\n'
    rle = old[old.index('local function rle_compress_rgb565_words(blob)'):old.index('local function capture_game_preview()')]
    rle += '\nreturn rle_compress_rgb565_words\n'
    new_rle_source = capture_section(new).replace('return capture_game_preview', 'return rle_compress_rgb565_words')
    libpath = '/lib/aarch64-linux-gnu/liblua5.4.so.0'
    lua = ctypes.CDLL(libpath)
    lua.luaL_newstate.restype = ctypes.c_void_p
    lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lua.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
    lua.luaL_loadbufferx.restype = ctypes.c_int
    lua.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_longlong, ctypes.c_void_p]
    lua.lua_pcallk.restype = ctypes.c_int
    lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    lua.lua_tolstring.restype = ctypes.c_void_p
    lua.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lua.lua_close.argtypes = [ctypes.c_void_p]
    state = lua.luaL_newstate(); assert state
    def result_string():
        size = ctypes.c_size_t(); pointer = lua.lua_tolstring(state, -1, ctypes.byref(size))
        return ctypes.string_at(pointer, size.value).decode() if pointer else '<non-string Lua value>'
    def load_buffer(raw, name):
        raw = raw.encode()
        code = lua.luaL_loadbufferx(state, raw, len(raw), name.encode(), b't')
        assert code == 0, result_string()
    try:
        lua.luaL_openlibs(state)
        # Syntax-check the complete real files without executing any MAME code.
        for source, name in ((old, 'full-parent507'), (new, 'full-candidate756')):
            load_buffer(source, name); lua.lua_settop(state, 0)
        harness = '''
assert(_VERSION == "Lua 5.4")
local old_source = OLD_SOURCE
local new_source = NEW_SOURCE
local old_convert = assert(load(OLD_RAW, "exact-old-preview-conversion", "t", _G))()
local new_convert = assert(load(NEW_RAW, "new-preview-conversion", "t", _G))()
local rle = assert(load(RLE_SOURCE, "unchanged-real-RLE", "t", _G))()
local new_rle = assert(load(NEW_RLE_SOURCE, "actual-new-RLE", "t", _G))()
local function pixels(w, h, kind, phase)
    local out = {}; local seed = 0x12345678 + phase
    for y = 0, h - 1 do
        for x = 0, w - 1 do
            local px = 0xFF000000
            if kind == "noise" then
                seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
                px = seed
            elseif (kind == "sparse" or kind == "moving_sparse") and (x + phase*7) % 73 < 11 and (y + phase*3) % 59 < 12 then
                px = (x % 2 == 0) and 0xFFFA73B1 or 0x12345678
            elseif kind == "pairs" then
                px = (((y*w+x)//2)%2==0) and 0xFF000000 or 0xFFFA73B1
            end
            out[#out + 1] = string.pack("=I4", px)
        end
    end
    return table.concat(out)
end
local function capture_function(source, fixture)
    local ticks = 0
    local frame_index=0
    local env = setmetatable({PREVIEW_CAPTURE_ENABLED=true, preview_stream_enabled=true,
        PREVIEW_MIN_INTERVAL_S=1/30, last_preview_capture_time_s=-1000000,
        PREVIEW_MAX_WIDTH=fixture.tw, PREVIEW_MAX_HEIGHT=fixture.th,
        preview_source_w=0, preview_source_h=0, preview_target_w=0, preview_target_h=0,
        PREVIEW_TRY_RLE=true, PREVIEW_RLE_MIN_SAVINGS_BYTES=256,
        PREVIEW_MAX_BYTES=4*1024*1024, PREVIEW_FORMAT_RGB565=1, PREVIEW_FORMAT_RGB565_RLE=3,
        clear_pending_preview=function() error("unexpected clear") end,
        socket_time_now=function() ticks=ticks+0.1; return ticks end,
        manager={machine={video={snapshot_size=function() return fixture.w,fixture.h end,
                                snapshot_pixels=function() frame_index=(frame_index%#fixture.frames)+1; return fixture.frames[frame_index] end}}}}, {__index=_G})
    return assert(load(source, "exact-capture-section", "t", env))(), env
end
local function bench(fn, repeats)
    collectgarbage("collect")
    local started=os.clock()
    for i=1,repeats do fn() end
    return (os.clock()-started)*1000/repeats
end
local definitions = {
    {name="native_black292x240",w=292,h=240,tw=292,th=240,kind="black",repeats=24},
    {name="native_sparse292x240",w=292,h=240,tw=292,th=240,kind="sparse",repeats=24},
    {name="native_noise292x240",w=292,h=240,tw=292,th=240,kind="noise",repeats=16},
    {name="resize584x480_to292x240",w=584,h=480,tw=292,th=240,kind="sparse",repeats=12},
    {name="native_odd17x13",w=17,h=13,tw=17,th=13,kind="noise",repeats=100},
    {name="native_one_pixel",w=1,h=1,tw=1,th=1,kind="noise",repeats=100},
    {name="native_moving_sparse4",w=292,h=240,tw=292,th=240,kind="moving_sparse",repeats=24,moving=true},
    {name="native_alternating_two_word_runs",w=292,h=240,tw=292,th=240,kind="pairs",repeats=16},
    {name="native_changing_noise4",w=292,h=240,tw=292,th=240,kind="noise",repeats=16,moving=true},
}
local edge_assertions=0
for _,n in ipairs({1,2,7,8,15,16,31,32,63,64,127,128,129,255,256,257,511,512,513}) do
    for _,word in ipairs({"\\0\\0", "ab"}) do
        local blob=string.rep(word,n)
        assert(rle(blob)==new_rle(blob), "RLE constant boundary differs:"..n)
        edge_assertions=edge_assertions+1
    end
end
local results={}
for _,fixture in ipairs(definitions) do
    fixture.frames={}
    for phase=0,(fixture.moving and 3 or 0) do
        fixture.frames[#fixture.frames+1]=pixels(fixture.w,fixture.h,fixture.kind,phase)
    end
    fixture.src=fixture.frames[1]
    for _,src in ipairs(fixture.frames) do
        local expected=old_convert(src,fixture.w,fixture.h,fixture.tw,fixture.th)
        local observed=new_convert(src,fixture.w,fixture.h,fixture.tw,fixture.th)
        assert(expected==observed,"moving raw bytes differ")
        assert(rle(expected)==new_rle(observed),"moving RLE bytes differ")
    end
    local raw_old=old_convert(fixture.src,fixture.w,fixture.h,fixture.tw,fixture.th)
    local raw_new=new_convert(fixture.src,fixture.w,fixture.h,fixture.tw,fixture.th)
    assert(raw_old==raw_new, "RGB565 bytes differ: "..fixture.name)
    assert(#raw_old==fixture.tw*fixture.th*2)
    local old_capture,old_env=capture_function(old_source,fixture)
    local new_capture,new_env=capture_function(new_source,fixture)
    for frame=1,#fixture.frames do
        old_capture();new_capture()
        assert(old_env.pending_preview_blob==new_env.pending_preview_blob,"moving capture wire bytes differ")
        assert(old_env.pending_preview_fmt==new_env.pending_preview_fmt,"moving capture format differs")
    end
    assert(old_env.pending_preview_blob and new_env.pending_preview_blob, "capture silently failed")
    assert(old_env.pending_preview_blob==new_env.pending_preview_blob, "wire preview blob differs: "..fixture.name)
    assert(old_env.pending_preview_w==new_env.pending_preview_w and old_env.pending_preview_h==new_env.pending_preview_h)
    assert(old_env.pending_preview_fmt==new_env.pending_preview_fmt)
    local old_raw_ms=bench(function() old_convert(fixture.src,fixture.w,fixture.h,fixture.tw,fixture.th) end,fixture.repeats)
    local new_raw_ms=bench(function() new_convert(fixture.src,fixture.w,fixture.h,fixture.tw,fixture.th) end,fixture.repeats)
    local rle_ms=bench(function() rle(raw_old) end,fixture.repeats)
    local old_total_ms=bench(old_capture,fixture.repeats)
    local new_total_ms=bench(new_capture,fixture.repeats)
    results[#results+1]=string.format("%s\t%d\t%d\t%d\t%.9f\t%.9f\t%.9f\t%.9f\t%.9f",fixture.name,#raw_old,#old_env.pending_preview_blob,old_env.pending_preview_fmt,old_raw_ms,new_raw_ms,rle_ms,old_total_ms,new_total_ms)
end
return _VERSION.."\\n"..table.concat(results,"\\n")
'''
        for marker, value in (('OLD_SOURCE', capture_section(old)), ('NEW_SOURCE', capture_section(new)),
                              ('OLD_RAW', raw_old), ('NEW_RAW', raw_new), ('RLE_SOURCE', rle), ('NEW_RLE_SOURCE', new_rle_source)):
            # Lua long-string delimiter is absent in these exact source slices.
            assert ']====]' not in value
            harness = harness.replace(marker, '[====[' + value + ']====]', 1)
        load_buffer(harness, 'offline-capture-benchmark')
        started = time.time()
        code = lua.lua_pcallk(state, 0, 1, 0, 0, None)
        assert code == 0, result_string()
        text = result_string(); lines = text.splitlines()
        assert lines[0] == 'Lua 5.4'
        records = []
        for line in lines[1:]:
            fields = line.split('\t'); assert len(fields) == 9, repr(fields)
            keys = ['old_convert_ms', 'new_convert_ms', 'unchanged_RLE_ms', 'old_capture_ms', 'new_capture_ms']
            row = dict(name=fields[0], raw_bytes=int(fields[1]), wire_preview_bytes=int(fields[2]), format=int(fields[3]))
            row.update({key: float(value) for key, value in zip(keys, fields[4:])})
            row['capture_speedup'] = row['old_capture_ms'] / row['new_capture_ms']
            records.append(row)
        output = dict(schema='robotron-offline-exact-Lua54-preview-capture-benchmark-v1', actual_lua='Lua 5.4',
            lua_library=libpath, elapsed_s=time.time()-started, cases=records,
            actual_source_syntax_both_pass=True, raw_and_compressed_preview_byte_equality_all_cases=True,
            exact_whole_source_allowed_delta_verified=True, no_real_MAME_GPU_model_or_live_action=True,
            limitation='Synthetic native snapshot strings. Actual MAME snapshot/render, transport, server decode and browser cost excluded; no live30FPS claim.')
        destination = HERE / 'actual-Lua54-preview-capture-CPU-benchmark-final-v3.json'
        with destination.open('x') as stream:
            json.dump(output, stream, sort_keys=True, indent=2); stream.write('\n')
        destination.chmod(0o444)
        print(json.dumps(output, indent=2))
    finally:
        lua.lua_close(state)


if __name__ == '__main__':
    main()
