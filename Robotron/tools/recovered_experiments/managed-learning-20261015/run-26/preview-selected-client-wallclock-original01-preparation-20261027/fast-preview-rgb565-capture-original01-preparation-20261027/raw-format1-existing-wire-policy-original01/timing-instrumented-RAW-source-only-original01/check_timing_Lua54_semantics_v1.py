"""Tiny offline Lua syntax/clocks/capture/socket checks, never MAME or live I/O."""
import ctypes
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    contract=json.loads((HERE/'exact-source-transform-and-phase-contract.json').read_text())
    parent=Path(contract['parent_path']).read_text();target=Path(contract['candidate_path']).read_text()
    assert hashlib.sha256(target.encode()).hexdigest()==contract['candidate_sha256']
    reverse=target
    for before,after in reversed(contract['exact_replacements']):
        assert reverse.count(after)==1;reverse=reverse.replace(after,before,1)
    assert reverse==parent
    def section(source,start,end):return source[source.index(start):source.index(end,source.index(start))]
    capture_old=section(parent,'local PREVIEW_RLE_BLACK128','local function frame_done_callback()')
    capture_new=section(target,'local PREVIEW_RLE_BLACK128','local function frame_done_callback()')
    socket_old=section(parent,'local function process_frame_via_socket','local function determine_meta_commands')
    socket_new=section(target,'local function process_frame_via_socket','local function determine_meta_commands')
    serialize_start='local function serialize_frame' if 'local function serialize_frame' in parent else 'function serialize_frame'
    assert section(parent,serialize_start,'local function process_frame_via_socket')==section(target,serialize_start,'local function process_frame_via_socket')
    harness=r'''
local helper=HELPER
local function environment(slot,kind)
    local clock={wall=0,cpu=0};local logs={}
    local env=setmetatable({CLIENT_SLOT=slot,socket_clock_kind=kind,preview_stream_enabled=true,
        socket_time_now=function()return clock.wall end,os={clock=function()return clock.cpu end},
        print=function(message)logs[#logs+1]=message end},{__index=_G})
    return env,clock,logs
end
local function helpers(env)
    return assert(load(helper..[[
return {mark=preview_profile_mark,finish=preview_profile_finish,frame=preview_profile_frame_begin,
stats=function()return preview_profile_stats end}
]],"actual-timing-helper","t",env))()
end
local env,clock,logs=environment(163,"host_wall")
local profile=helpers(env)
for frame=1,40 do
    clock.wall=frame*.2;clock.cpu=frame*.01
    profile.frame()
    local w,c=profile.mark();clock.wall=clock.wall+.002;clock.cpu=clock.cpu+.001
    profile.finish("snapshot_pixels",w,c)
end
assert(#logs==2,"expected one header plus one5s summary over8s")
assert(logs[1]:find("lua_version=") and logs[2]:find("snapshot_pixels_n=") and logs[2]:find("action_wait_n=0"))
assert(not logs[2]:find("slot=162"))
for _,case in ipairs({{162,"host_wall",0},{163,"process_cpu",1}}) do
    local e,c,l=environment(case[1],case[2]);local p=helpers(e)
    for frame=1,40 do c.wall=frame;p.frame();local w,cpu=p.mark();p.finish("convert",w,cpu) end
    assert(#l==case[3],"nonselected/fallback logging differs")
end
local pixels={}
for n=1,221 do pixels[n]=string.pack("=I4",(n*1234567)&0xFFFFFFFF) end
local src=table.concat(pixels)
local function capture(source)
    local e,c,l=environment(163,"host_wall")
    e.PREVIEW_CAPTURE_ENABLED=true;e.PREVIEW_MIN_INTERVAL_S=1/30;e.last_preview_capture_time_s=-1000000
    e.PREVIEW_MAX_WIDTH=0;e.PREVIEW_MAX_HEIGHT=0;e.preview_source_w=0;e.preview_source_h=0
    e.preview_target_w=0;e.preview_target_h=0;e.PREVIEW_TRY_RLE=false;e.PREVIEW_MAX_BYTES=2000000
    e.PREVIEW_FORMAT_RGB565=1;e.PREVIEW_FORMAT_RGB565_RLE=3
    e.clear_pending_preview=function()e.pending_preview_blob=nil end
    e.manager={machine={video={snapshot_size=function()c.wall=c.wall+.001;c.cpu=c.cpu+.0005;return 17,13 end,
        snapshot_pixels=function()c.wall=c.wall+.003;c.cpu=c.cpu+.002;return src end}}}
    local fn=assert(load(helper..source..[[
return {run=capture_game_preview,stats=function()return preview_profile_stats end}
]],"exact-capture-section","t",e))()
    fn.run()
    return e,fn.stats()
end
local a=select(1,capture(CAPTURE_OLD));local b,stats=capture(CAPTURE_NEW)
assert(a.pending_preview_blob==b.pending_preview_blob and #b.pending_preview_blob==442)
assert(a.pending_preview_w==b.pending_preview_w and a.pending_preview_h==b.pending_preview_h and a.pending_preview_fmt==b.pending_preview_fmt)
for _,name in ipairs({"snapshot_size","snapshot_pixels","convert","capture_total"}) do assert(stats[name][1]==1) end
local function exchange(source,kind)
    local e,c,l=environment(163,"host_wall");local writes={};local closed=0;local read_once=false
    e.ACTION_RX_BUFFER="";e.SOCKET_READ_TIMEOUT_S=3.5;e.unpack=table.unpack;e.trace_log=function()end
    e.log_socket_receive_timeout=function()end
    e.set_preview_stream_enabled=function(value)e.preview_stream_enabled=value end
    e.close_socket=function()closed=closed+1;e.current_socket=nil;e.preview_stream_enabled=false end
    e.open_socket=function()error("unexpected open")end
    e.current_socket={write=function(self,data)
        if kind=="write_error"then error("CPUfixturewrite")end
        writes[#writes+1]=data;c.wall=c.wall+.0003;c.cpu=c.cpu+.0001
    end,read=function(self,n)
        if kind=="timeout"then c.wall=c.wall+4;return nil end
        assert(not read_once);read_once=true;c.wall=c.wall+.002;c.cpu=c.cpu+.0001
        return string.pack("bbBBBB",2,3,0x44,0,1,0x85)
    end}
    local fn=assert(load(helper..source..[[
return {run=process_frame_via_socket,stats=function()return preview_profile_stats end}
]],"exact-exchange-section","t",e))()
    local result=table.pack(fn.run("literal payload\0bytes",7))
    return result,writes,closed,e,fn.stats()
end
for _,kind in ipairs({"success","write_error","timeout"})do
    local ar,aw,ac,ae=exchange(SOCKET_OLD,kind)
    local br,bw,bc,be,bs=exchange(SOCKET_NEW,kind)
    assert(ar.n==br.n and ac==bc and #aw==#bw)
    for n=1,ar.n do assert(ar[n]==br[n],"reply semantics changed")end
    for n=1,#aw do assert(aw[n]==bw[n],"encoded frame bytes changed")end
    assert(ae.ACTION_RX_BUFFER==be.ACTION_RX_BUFFER and ae.preview_stream_enabled==be.preview_stream_enabled)
    assert(bs.socket_write[1]==1)
    if kind~="write_error"then assert(bs.action_wait[1]==1)end
end
return "Lua5.4 syntax/helper window/slot/fallback/capture/socket checks PASS"
'''
    for marker,value in [('HELPER',contract['helper']),('CAPTURE_OLD',capture_old),('CAPTURE_NEW',capture_new),
                          ('SOCKET_OLD',socket_old),('SOCKET_NEW',socket_new)]:
        assert ']====]'not in value;harness=harness.replace(marker,'[====['+value+']====]',1)
    lua=ctypes.CDLL('/lib/aarch64-linux-gnu/liblua5.4.so.0')
    lua.luaL_newstate.restype=ctypes.c_void_p;lua.luaL_openlibs.argtypes=[ctypes.c_void_p]
    lua.luaL_loadbufferx.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p]
    lua.lua_pcallk.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_longlong,ctypes.c_void_p]
    lua.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t)]
    lua.lua_tolstring.restype=ctypes.c_void_p;lua.lua_settop.argtypes=[ctypes.c_void_p,ctypes.c_int]
    lua.lua_close.argtypes=[ctypes.c_void_p]
    state=lua.luaL_newstate();assert state;lua.luaL_openlibs(state)
    def result():
        n=ctypes.c_size_t();p=lua.lua_tolstring(state,-1,ctypes.byref(n));return ctypes.string_at(p,n.value).decode()if p else '<nonstring>'
    try:
        for text,name in [(parent,'RAW-parent-full-syntax'),(target,'profile-full-syntax')]:
            raw=text.encode();assert lua.luaL_loadbufferx(state,raw,len(raw),name.encode(),b't')==0,result();lua.lua_settop(state,0)
        raw=harness.encode();assert lua.luaL_loadbufferx(state,raw,len(raw),b'timing-semantics',b't')==0,result()
        assert lua.lua_pcallk(state,0,1,0,0,None)==0,result()
        observed=result()
    finally:lua.lua_close(state)
    report=dict(schema='robotron-RAW-phase-timing-Lua54-semantics-v1',actual_Lua_syntax=True,
        full_source_exact_delta=True,decoded_capture_bytes_equality=True,
        socket_write_bytes_and_reply_semantics_unchanged=True,selected_only_bounded_aggregation=True,
        fallback_header_only_no_abort=True,serialize_function_source_identical=True,
        mocked_exchange_cases=['success','write_error','timeout'],actual_Lua='systemlibLua5.4;notMAME',observed=observed,
        no_MAME_GPU_Torch_model_socket_or_production_log_actions=True)
    p=HERE/'actual-Lua54-phase-semantics-check-original01.json'
    with p.open('x')as f:json.dump(report,f,sort_keys=True,indent=2);f.write('\n')
    p.chmod(0o444);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
