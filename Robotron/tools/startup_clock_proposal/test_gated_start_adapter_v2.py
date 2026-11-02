"""New full adapter-initialization guard after retained original0-frame failure.

Only the one-value environment helper changed. This scope executes the actual
from_environment body in Lua5.4 with explicit MAME/transport shims. It does not
rerun the original8, corrected2, or clock9 methods and does not invoke MAME.
"""
from pathlib import Path
import importlib.util
import json
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('consumed_Lua_VM_definitions',HERE/'test_gated_start_trace_v1.py')
definitions=importlib.util.module_from_spec(spec)
spec.loader.exec_module(definitions)

PRELUDE='''
local M=assert(loadfile(HELPER_PATH))()
local fields_set,files_opened,file_closed,socket_closed,removes,writes=0,0,0,0,0,0
local frame_cb,stop_cb
local env={ROBOTRON_GATED_TRACE_PATH="private_trace",ROBOTRON_GATED_TRACE_ADDRESS="127.0.0.1:19997",
 ROBOTRON_GATED_TRACE_SLOT="4096",ROBOTRON_GATED_TRACE_SESSION=string.rep("1",32),
 ROBOTRON_GATED_TRACE_CONNECTION=string.rep("2",32)}
os.getenv=function(k)return env[k]end
io.open=function(path,mode)
 assert(path=="private_trace" and mode=="a");files_opened=files_opened+1
 return {write=function(self,line)writes=writes+1;return self end,flush=function()end,
 close=function()file_closed=file_closed+1 end}
end
local start={set_value=function(self,v)assert(v==0);fields_set=fields_set+1 end}
local coin={set_value=function(self,v)assert(v==0);fields_set=fields_set+1 end}
local port={fields={["1 Player Start"]=start,["Coin 1"]=coin}}
local memory={read_u8=function(self,addr)return addr==0x9859 and 128 or 0 end,
 install_write_tap=function()return {remove=function()removes=removes+1 end}end}
manager={machine={devices={[":maincpu"]={spaces={program=memory},state={}}},
 memory={regions={[":maincpu"]={size=0x19000,bytewidth=1,bitwidth=8,read_u8=function(self,n)return n%256 end}},
 banks={[":mainbank"]={entry=0}}},ioport={ports={p1=port}},exit=function()error("unexpected machine exit")end}}
local ticks=0
emu={osd_ticks=function()ticks=ticks+1;return ticks end,osd_ticks_per_second=function()return 1000000 end,
 file=function(mode)
 assert(mode=="rw")
 return {open=function(self,addr)assert(addr=="socket.127.0.0.1:19997");return nil end,
 write=function(self,data)assert(type(data)=="string" and #data>4)end,
 read=function(self,n)assert(n==42);return string.pack(">c4I4BBc32","RSC1",1,0,0,string.rep("\\0",32))end,
 close=function()socket_closed=socket_closed+1 end}
 end,
 add_machine_frame_notifier=function(fn)frame_cb=fn;return {owned=true}end,
 add_machine_stop_notifier=function(fn)stop_cb=fn;return {owned=true}end}
'''


def run(code):
    return definitions.Lua().run(PRELUDE.replace('HELPER_PATH',json.dumps(str(HERE/'gated_start_trace_v2.lua')))+code)


class AdapterInitializationContract(unittest.TestCase):
    def test_actual_adapter_environment_slot_and_first_exchange(self):
        self.assertEqual(run('''
local gate=M.from_environment()
assert(gate.slot==4096 and gate.installed and writes==801 and files_opened==1)
assert(type(frame_cb)=="function" and type(stop_cb)=="function")
frame_cb()
assert(gate.sequence==1 and gate.last_apply_ok and gate.last_socket_ok and not gate.failed)
stop_cb()
assert(gate.closed and removes==5 and socket_closed==1 and file_closed==1)
assert(writes==804 and fields_set==6)
return "PASS"
'''),'PASS')

    def test_missing_environment_rejected_before_open_or_input(self):
        self.assertEqual(run('''
env.ROBOTRON_GATED_TRACE_PATH=nil
assert(not pcall(M.from_environment))
assert(files_opened==0 and fields_set==0 and frame_cb==nil)
return "PASS"
'''),'PASS')

    def test_missing_or_ambiguous_hardware_fields_never_apply_input(self):
        for change in ['port.fields["1 Player Start"]=nil',
                       'manager.machine.ioport.ports.p2={fields={["1 Player Start"]={set_value=function()error("never apply")end}}}']:
            with self.subTest(change=change):
                self.assertEqual(run(change+'''
assert(not pcall(M.from_environment))
assert(fields_set==0 and frame_cb==nil and writes==0)
return "PASS"
'''),'PASS')


if __name__=='__main__':
    unittest.main(verbosity=2)
