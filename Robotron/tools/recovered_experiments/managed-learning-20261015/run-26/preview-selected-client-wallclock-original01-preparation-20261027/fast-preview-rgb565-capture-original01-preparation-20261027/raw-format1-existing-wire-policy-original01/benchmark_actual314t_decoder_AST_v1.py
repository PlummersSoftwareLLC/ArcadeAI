"""Offline current-server AST decode timing on actual free-threaded3.14.

No server/Torch import, model, MAME, socket, controls or production mutation.
Current Lua5.4 RLE source encodes synthetic RGB565 fixtures; existing server pf3
and pf1 AST branches decode them. Encoded bytes intentionally differ.
"""
import ast
import ctypes
import hashlib
import json
from pathlib import Path
import random
import struct
import sys
import time

HERE = Path(__file__).resolve().parent
D = HERE.parent
SERVER = Path('/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py')


def main():
    assert sys.version_info[:2] == (3,14) and not sys._is_gil_enabled(), 'Actual free-threaded3.14 required'
    source = SERVER.read_bytes()
    assert hashlib.sha256(source).hexdigest() == 'b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516'
    parent = (D/'main-lua-preview-fast-final-v4.lua').read_text()
    target = (HERE/'main-lua-preview-fast-raw-format1-v1.lua').read_text()
    before = 'PREVIEW_TRY_RLE = env_flag("ROBOTRON_PREVIEW_RLE", true)'
    assert parent.count(before) == 1 and parent.replace(before,'PREVIEW_TRY_RLE = false',1) == target
    assert hashlib.sha256(target.encode()).hexdigest() == 'cbd8109f8d62f65c26c38ea91c73b3285fda0812895ee5e5fbf4e8565afedbd1'
    tree = ast.parse(source)
    parser = next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='parse_frame_data')
    namespace = {}
    branches = {}
    for fmt,name in ((3,'current_RLE_decode'),(1,'current_RAW_decode')):
        branch = next(node for node in ast.walk(parser) if isinstance(node,ast.If)
            and isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Name)
            and node.test.left.id=='pf' and isinstance(node.test.comparators[0],ast.Constant)
            and node.test.comparators[0].value==fmt)
        body = branch.body+[ast.Return(ast.Name('preview_pixels',ast.Load()))]
        function = ast.FunctionDef(name=name,args=ast.arguments(posonlyargs=[],
            args=[ast.arg('pixels'),ast.arg('expected_px')],kwonlyargs=[],kw_defaults=[],defaults=[]),
            body=body,decorator_list=[])
        module = ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
        branches[name] = ast.unparse(module)
        exec(compile(module,'<EXACT-current-server-AST-'+name+'>','exec'),namespace)
    decode = namespace['current_RLE_decode']; raw_decode = namespace['current_RAW_decode']

    lua = ctypes.CDLL('/lib/aarch64-linux-gnu/liblua5.4.so.0')
    lua.luaL_newstate.restype=ctypes.c_void_p;lua.luaL_openlibs.argtypes=[ctypes.c_void_p]
    lua.luaL_loadbufferx.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p]
    lua.lua_pcallk.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_longlong,ctypes.c_void_p]
    lua.lua_pushlstring.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t]
    lua.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t)]
    lua.lua_tolstring.restype=ctypes.c_void_p;lua.lua_settop.argtypes=[ctypes.c_void_p,ctypes.c_int]
    lua.lua_close.argtypes=[ctypes.c_void_p]
    state=lua.luaL_newstate();assert state;lua.luaL_openlibs(state)
    start=parent.index('local PREVIEW_RLE_BLACK128')
    end=parent.index('local function capture_game_preview()',start)
    rle_source=(parent[start:end]+'\nreturn rle_compress_rgb565_words\n').encode()
    def lua_string():
        count=ctypes.c_size_t();ptr=lua.lua_tolstring(state,-1,ctypes.byref(count));assert ptr
        return ctypes.string_at(ptr,count.value)
    def encode(raw):
        lua.lua_settop(state,0)
        assert lua.luaL_loadbufferx(state,rle_source,len(rle_source),b'EXACT-current0ad-RLE',b't')==0,lua_string()
        assert lua.lua_pcallk(state,0,1,0,0,None)==0,lua_string()
        lua.lua_pushlstring(state,raw,len(raw))
        assert lua.lua_pcallk(state,1,1,0,0,None)==0,lua_string()
        return lua_string()
    def pixels(kind,phase):
        rng=random.Random(0x12345678+phase);out=bytearray()
        for y in range(240):
            for x in range(292):
                word=0
                if kind=='noise':word=rng.getrandbits(16)
                elif kind=='sparse' and (x+phase*7)%73<11 and (y+phase*3)%59<12:
                    word=0xFB96 if x%2==0 else 0x32AF
                out.extend(struct.pack('>H',word))
        return bytes(out)
    def bench(function,frames,repeat=24):
        cpu=time.process_time_ns();wall=time.perf_counter_ns()
        for n in range(repeat):
            value=frames[n%len(frames)]
            assert function(value,140160) is not None
        return dict(cpu_ms_per_frame=(time.process_time_ns()-cpu)/repeat/1e6,
                    wall_ms_per_frame=(time.perf_counter_ns()-wall)/repeat/1e6)
    cases=[]
    try:
        for name,kind,count in (('static_black','black',1),('static_sparse','sparse',1),
                                ('moving_sparse4','sparse',4),('changing_noise4','noise',4)):
            frames=[pixels(kind,phase) for phase in range(count)]
            compressed=[encode(frame) for frame in frames]
            for raw,encoded in zip(frames,compressed):
                assert decode(encoded,len(raw))==raw_decode(raw,len(raw))==raw
            rle_ms=bench(decode,compressed);raw_ms=bench(raw_decode,frames)
            cases.append(dict(name=name,frames=count,raw_bytes=140160,
                RLE_bytes=[len(frame) for frame in compressed],RLE=rle_ms,RAW=raw_ms,
                CPU_ms_saved_per_frame=rle_ms['cpu_ms_per_frame']-raw_ms['cpu_ms_per_frame']))
        assert raw_decode(b'\x00',140160) is None
        assert decode(b'\xFF\x00',140160) is None
    finally:
        lua.lua_close(state)
    output=dict(schema='robotron-preview-actual314t-RLE-vs-RAW-AST-benchmark-v1',
        actual_python=sys.version,actual_executable=sys.executable,actual_free_threaded=not sys._is_gil_enabled(),
        server_source_SHA=hashlib.sha256(source).hexdigest(),decoded_RGB565_equality_all_cases=True,
        encoded_bytes_equality_required=False,cases=cases,exact_AST_branches=branches,
        actual_parent_Lua54_RLE_encoder=True,malformed_existing_guards_unchanged=True,
        exact_single_line_delta_verified=True,no_MAME_Torch_GPU_socket_control_or_model_reads=True,
        limit='Only existing pf3 expansion versus pf1 raw bytes. Payload receive/slicing, inference, MAME capture/render, browser and network costs excluded; no liveFPS qualification.',
        raw_image_bytes_per_second_at30=140160*30)
    destination=HERE/'actual314t-RLE-vs-RAW-decoder-AST-benchmark-original01.json'
    with destination.open('x') as stream:json.dump(output,stream,sort_keys=True,indent=2);stream.write('\n')
    destination.chmod(0o444)
    print(json.dumps(output,indent=2))


if __name__=='__main__':
    main()
