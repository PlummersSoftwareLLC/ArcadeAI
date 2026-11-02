"""CPU checks for exact coverage routing and allocator-pool accounting."""
import subprocess
import sys
import unittest
from pathlib import Path

from benchmark_cuda_graph_coverage import pool_usage,SHAPES,BUDGET_BYTES,WALL_BUDGET_S
import test_cuda_graph_inference_prototype as fixture_module
from test_cuda_graph_inference_prototype import Tensor


class CoverageTests(unittest.TestCase):
    def test_pool_accounting_ignores_unrelated_allocator_segments(self):
        pools={1:(7,1),50:(7,2)}
        segments=[dict(segment_pool_id=(7,1),total_size=100,allocated_size=20,active_size=30),
            dict(segment_pool_id=[7,1],total_size=200,allocated_size=40,active_size=50),
            dict(segment_pool_id=(7,2),total_size=70,allocated_size=10,active_size=15),
            dict(segment_pool_id=(0,0),total_size=9000,allocated_size=8000,active_size=8100)]
        actual=pool_usage(segments,pools)
        self.assertEqual(actual['1']['reserved_bytes'],300)
        self.assertEqual(actual['1']['allocated_bytes'],60)
        self.assertEqual(actual['1']['active_bytes'],80)
        self.assertEqual(actual['1']['segments'],2)
        self.assertEqual(actual['50']['reserved_bytes'],70)

    def test_all128_actual_shapes_use_exact_slot_without_padding(self):
        fixture=fixture_module.RoutingOwnershipTests();bank=fixture.bank()
        seen=[]
        for size in SHAPES:
            inputs,outputs=Tensor([0]*size,cuda=True),Tensor([0]*size,cuda=True)
            def replay(size=size,inputs=inputs,outputs=outputs):
                seen.append(size);outputs.values[:]=[value*3 for value in inputs.values]
            bank.slots[size]=(type('Graph',(),{'replay':staticmethod(replay)})(),inputs,outputs)
        for size in reversed(SHAPES):
            actual,info=bank.call(Tensor([2]*size))
            self.assertEqual(info['bucket'],size)
            self.assertEqual(actual.values,[6]*size)
        self.assertEqual(seen,list(reversed(SHAPES)))
        self.assertEqual(fixture.compiled_calls,[])
        _,info=bank.call(Tensor([2]*129))
        self.assertEqual(info['route'],'compiled')
        self.assertEqual(fixture.compiled_calls,[129])

    def test_coverage_limits_are_explicit(self):
        self.assertEqual(SHAPES,tuple(range(1,129)))
        self.assertEqual(BUDGET_BYTES,10*(1<<30))
        self.assertLess(WALL_BUDGET_S,300)

    def test_import_creates_no_cuda_context_or_torch_import(self):
        script=Path(__file__).with_name('benchmark_cuda_graph_coverage.py')
        source="import runpy,sys;sys.path.insert(0,sys.argv[1]);runpy.run_path(sys.argv[2]);assert 'torch' not in sys.modules;assert 'numpy' not in sys.modules"
        subprocess.run([sys.executable,'-c',source,str(script.parent),str(script)],check=True,timeout=5)


if __name__=='__main__':unittest.main()
