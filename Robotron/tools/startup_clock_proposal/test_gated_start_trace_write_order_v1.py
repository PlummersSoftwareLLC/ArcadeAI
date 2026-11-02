"""Distinct corrected ROM-write fixture and coincident-play rejection contract.

The original eight-method run remains exit1 (seven pass, one fixture failure).
Only helper definitions are loaded from it; none of its test methods run here.
The unchanged producer's tap returns nil; the simulated CPU must subsequently
apply its original STATUS write, just as MAME does. No production source repair
or original scientific confirmation rerun is involved.
"""
from pathlib import Path
import importlib.util
import unittest

spec=importlib.util.spec_from_file_location('consumed_producer_fixture_definitions',
    Path(__file__).with_name('test_gated_start_trace_v1.py'))
fixtures=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class WriteOrderContract(unittest.TestCase):
    def test_full_raw_prefix_with_original_CPU_write_after_nil_tap(self):
        self.assertEqual(fixtures.lua('''
g:install()
for i=1,1200 do
 if i==775 then memory_values[0xBDED]=1;memory_values[0xBDEC]=2 end
 if i==857 then memory_values[0x9859]=0 end
 g:step()
 if i==768 then
  assert(callbacks[0x9859](0x9859,0x7f,255)==nil)
  -- A nil tap return preserves the CPU's original write; it does not perform
  -- that write for the CPU. The original fixture omitted this line.
  memory_values[0x9859]=0x7f
 end
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

    def test_missing_CPU_write_exposes_same_frame_play_and_cannot_join_bracket(self):
        self.assertEqual(fixtures.lua('''
g:install()
for i=1,1200 do
 if i==775 then memory_values[0xBDED]=1;memory_values[0xBDEC]=2 end
 g:step()
 if i==768 then assert(callbacks[0x9859](0x9859,0x7f,255)==nil) end
end
-- This is the original faulty fixture: bit0 stays clear in STATUS128.
assert(g.initialized_sequence==775 and g.first_play_sequence==775)
return "PASS"
'''), 'PASS')
        protocol,_=fixtures.protocol()
        for _ in range(774):
            protocol.process(fixtures.snapshot(protocol),lambda raw: None)
        with self.assertRaisesRegex(ValueError,'before play'):
            protocol.process(fixtures.snapshot(protocol,accepted_site_count=1,
                accepted_site_sequence=768,initialized_sequence=775,first_play_sequence=775,
                wave=1,reserves=2),lambda raw: None)
        self.assertIsNone(protocol.bracket)


if __name__=='__main__':
    unittest.main(verbosity=2)
