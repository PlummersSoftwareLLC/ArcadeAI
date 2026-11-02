"""CPU ownership/routing checks; real capture/parity is an explicit GPU0 probe."""
from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import benchmark_cuda_graph_inference as prototype
from benchmark_cuda_graph_inference import ExactGraphBank, bucket_size, EXACT_BATCHES


class Tensor:
    def __init__(self, values, *, cuda=False):
        self.values=list(values)
        self.shape=(len(values),81)
        self.is_cuda=cuda
        self.device="cuda:0" if cuda else "cpu"

    def __len__(self): return len(self.values)
    def __getitem__(self, value): return View(self,value)
    def to(self, device): return Tensor(self.values,cuda=True)
    def detach(self): return self
    def cpu(self): return Tensor(self.values)
    def record_stream(self, stream): pass


class View(Tensor):
    def __init__(self, owner, region):
        self.owner,self.region=owner,region
        super().__init__(owner.values[region],cuda=owner.is_cuda)
    def copy_(self, other): self.owner.values[self.region]=other.values
    def zero_(self): self.owner.values[self.region]=[0]*len(self.values)


class Stream:
    def wait_stream(self, other): pass


class FakeTorch:
    def __init__(self):
        self.cuda=self
        self.stream_object=Stream()
        self._dynamo=type("Dynamo",(),{"utils":type("Utils",(),{"counters":{}})})()
    def no_grad(self): return nullcontext()
    def autocast(self,*args,**kwargs): return nullcontext()
    def current_stream(self,*args): return self.stream_object
    def stream(self,*args): return nullcontext()


class RoutingOwnershipTests(unittest.TestCase):
    def bank(self):
        bank=ExactGraphBank.__new__(ExactGraphBank)
        bank.torch=FakeTorch(); bank.lock=threading.RLock(); bank.stream=Stream()
        bank.closed=False; bank.error=None; bank.guard={k:{} for k in ("stats","graph_break","unimplemented")}
        self.compiled_calls=[]
        def compiled(inputs):
            self.compiled_calls.append(len(inputs))
            return Tensor([x*3 for x in inputs.values],cuda=True)
        bank.compiled=compiled
        self.replays=[]
        bank.slots={}
        for size in EXACT_BATCHES:
            inputs,outputs=Tensor([9]*size,cuda=True),Tensor([0]*size,cuda=True)
            def replay(inputs=inputs,outputs=outputs,size=size):
                self.replays.append(size)
                outputs.values[:]=[x*3 for x in inputs.values]
            graph=type("Graph",(),{"replay":staticmethod(replay)})()
            bank.slots[size]=(graph,inputs,outputs)
        return bank

    def test_exact_graph_returns_independent_cpu_values(self):
        bank=self.bank()
        first,info=bank.call(Tensor(list(range(32))))
        self.assertEqual(info["route"],"graph")
        bank.call(Tensor([20]*32))
        self.assertEqual(first.values,[x*3 for x in range(32)])
        self.assertFalse(first.is_cuda)
        self.assertEqual(self.compiled_calls,[])

    def test_padding_clears_stale_tail_and_limits_output(self):
        bank=self.bank()
        result,info=bank.call(Tensor([2]*50),padding=True)
        self.assertEqual(info["bucket"],64)
        self.assertEqual(len(result),50)
        self.assertEqual(bank.slots[64][1].values[50:],[0]*14)

    def test_gpu_diagnostic_bypasses_static_graph(self):
        bank=self.bank()
        result,info=bank.call(Tensor([7]*32),return_cpu=False,padding=True)
        self.assertEqual(info["route"],"compiled")
        self.assertEqual(self.compiled_calls,[32])
        self.assertEqual(self.replays,[])
        self.assertTrue(result.is_cuda)

    def test_unsupported_exact_shape_routes_original_compiled(self):
        bank=self.bank()
        _,info=bank.call(Tensor([3]*50))
        self.assertEqual(info["route"],"compiled")
        self.assertEqual(self.compiled_calls,[50])

    def test_runtime_error_latches_and_no_retry(self):
        bank=self.bank()
        def broken(): raise RuntimeError("capture failed")
        bank.slots[32]=(type("Graph",(),{"replay":staticmethod(broken)})(),*bank.slots[32][1:])
        with self.assertRaisesRegex(RuntimeError,"capture failed"): bank.call(Tensor([0]*32))
        with self.assertRaisesRegex(RuntimeError,"closed or failed"): bank.call(Tensor([0]*32))
        self.assertEqual(self.compiled_calls,[])

    def test_bucket_policy_is_bounded(self):
        self.assertEqual(bucket_size(50,padding=True),64)
        self.assertIsNone(bucket_size(50))
        self.assertIsNone(bucket_size(129,padding=True))
        for bad in (True,False,0,-1,1.5):
            with self.assertRaises(ValueError): bucket_size(bad,padding=True)

    def test_import_is_plan_only_without_torch(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"unused"
            script=Path(__file__).with_name("benchmark_cuda_graph_inference.py")
            code="import sys,runpy;sys.path.insert(0,sys.argv[1]);m=runpy.run_path(sys.argv[2]);assert 'torch' not in sys.modules;assert 'numpy' not in sys.modules"
            subprocess.run([sys.executable,"-c",code,str(script.parent),str(script)],check=True,timeout=5)
            self.assertFalse(output.exists())

    def test_failure_artifact_preserves_original_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(prototype,"validate_plan"),mock.patch.object(prototype,"run",side_effect=ValueError("original failure")):
                with self.assertRaisesRegex(ValueError,"original failure"):
                    prototype.main(["--directory",directory,"--execute"])
            payload=(Path(directory)/"failure.json").read_text()
            self.assertTrue(payload.endswith("\n"))
            self.assertEqual(json.loads(payload)["error"],"ValueError('original failure')")


if __name__=="__main__": unittest.main()
