"""Small CUDA ownership checks; does not construct a model or change services."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np
import torch

try:
    from .native_sumtree import gather_fp16_rows, NATIVE_GATHER_AVAILABLE
except ImportError:
    from native_sumtree import gather_fp16_rows, NATIVE_GATHER_AVAILABLE


class TinyReplay:
    state_size = 16
    def __init__(self):
        self.samples = 0
        self.source_checks = 0
        self.lock = threading.Lock()

    def __len__(self):
        return 128

    def sample(self, size, beta):
        assert 0.0 <= beta <= 1.0
        with self.lock:
            self.samples += 1
            sample = self.samples
        # This value deliberately changes if fp32 bank states are cast to fp16.
        precise = np.float32(sample + 0.000123)
        return (
            np.full((size, 16), precise, np.float32),
            np.arange(size, dtype=np.int64),
            np.linspace(-1, 1, size, dtype=np.float32),
            np.full((size, 16), -precise, np.float32),
            np.arange(size, dtype=np.float32) % 2,
            np.full(size, 3, np.int32),
            np.arange(size, dtype=np.uint8) % 2,
            np.full(size, 2, np.uint8),
            np.arange(size, dtype=np.int64) + 128,
            np.linspace(0.5, 1.0, size, dtype=np.float32),
        )

    def sample_into(self, size, states_out, next_states_out, beta):
        batch = list(self.sample(size, beta))
        ring_count = size // 2
        indices = np.arange(ring_count, dtype=np.int64)
        for field, output in ((0, states_out), (3, next_states_out)):
            ring = batch[field][:ring_count].astype(np.float16)
            bank = batch[field][ring_count:].copy()
            ring.flags.writeable = bank.flags.writeable = False
            ring_before, bank_before = ring.copy(), bank.copy()
            if gather_fp16_rows(ring, indices, out=output[:ring_count]) is None:
                np.copyto(output[:ring_count], ring)
            np.copyto(output[ring_count:], bank)
            assert np.array_equal(ring, ring_before), "Direct gather mutated its source ring"
            assert np.array_equal(bank, bank_before), "Direct fill mutated its fp32 bank source"
            self.source_checks += 2
        batch[0], batch[3] = states_out, next_states_out
        return tuple(batch)


def load_prefetch(path):
    spec = importlib.util.spec_from_file_location("robotron_prefetch_cuda_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_batch(prepared):
    prepared.wait_on_current_stream()
    field_indices = (0, 1, 2, 3, 4, 5, 6, 9)
    dtypes = (
        torch.float32, torch.long, torch.float32, torch.float32,
        torch.float32, torch.float32, torch.bool, torch.float32,
    )
    for actual, field, dtype in zip(prepared.tensors, field_indices, dtypes):
        assert actual.device.type == "cuda"
        assert actual.dtype == dtype
        expected = torch.from_numpy(prepared.batch[field]).to(dtype=dtype)
        assert torch.equal(actual.cpu(), expected), f"Replay field {field} differs"
    assert prepared.transfer_ms >= 0.0
    assert prepared._slot.host[0].is_pinned()
    assert prepared._slot.host[3].is_pinned()
    value = prepared.batch[0][-1, 0]
    assert float(np.float16(value)) != float(value), "Fixture lacks fp32 precision"


def run(module_path, rounds, direct_state_fill=False):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this test")
    module = load_prefetch(module_path)
    torch.cuda.set_device(0)
    enabled = threading.Event()
    enabled.set()
    memory = TinyReplay()
    pipeline = module.ReplayPrefetcher(
        memory, 8, lambda: 0.4, "cuda:0", use_amp=True,
        depth=2, enabled_fn=enabled.is_set,
        direct_state_fill=direct_state_fill,
    )
    held = []
    slow = torch.cuda.Stream()
    saw_pending_release = False
    try:
        first = pipeline.get(timeout=10)
        second = pipeline.get(timeout=10)
        assert first is not None and second is not None
        held = [first, second]
        check_batch(first)
        check_batch(second)
        time.sleep(0.02)
        assert memory.samples == 2, "Producer exceeded the two-slot pool"
        for _ in range(rounds):
            device_ptr = first.tensors[0].data_ptr()
            host_ptr = first._slot.host[0].data_ptr()
            expected = torch.from_numpy(first.batch[0].copy())
            with torch.cuda.stream(slow):
                # Joining the same batch from a second stream must be refused;
                # check_batch already joined the default compute stream.
                try:
                    first.wait_on_current_stream()
                except RuntimeError as exc:
                    assert "one CUDA stream" in str(exc)
                else:
                    raise AssertionError("Cross-stream lease was accepted")
            # Use a fresh lease for the delayed consumer: release the old one
            # first so it cannot carry a previously selected consumer stream.
            first.release()
            first = pipeline.get(timeout=10)
            assert first is not None
            held[0] = first
            assert first.tensors[0].data_ptr() == device_ptr
            assert first._slot.host[0].data_ptr() == host_ptr
            expected = torch.from_numpy(first.batch[0].copy())
            count = memory.samples
            with torch.cuda.stream(slow):
                first.wait_on_current_stream()
                # One SM spins briefly; no network/model benchmark is involved.
                torch.cuda._sleep(100_000_000)
                delayed_read = first.tensors[0].clone()
                first.release()
            if not first._slot.released.query():
                saw_pending_release = True
                assert memory.samples == count, "Staging reused before consumer completion"
            next_batch = pipeline.get(timeout=10)
            assert next_batch is not None
            slow.synchronize()
            assert torch.equal(delayed_read.cpu(), expected), "Released slot was overwritten during CUDA reads"
            assert next_batch.tensors[0].data_ptr() == device_ptr
            assert next_batch._slot.host[0].data_ptr() == host_ptr
            first = next_batch
            held[0] = first
            check_batch(first)

        assert saw_pending_release, "Test did not exercise an outstanding CUDA release event"
        enabled.clear()
        assert pipeline.invalidate(timeout=5)
        assert not first.is_current and not second.is_current
        first.release()
        second.release()
        held = []
        assert pipeline.get(timeout=0.1) is None, "Invalidated/paused queue returned data"
        enabled.set()
        resumed = pipeline.get(timeout=10)
        assert resumed is not None and resumed.is_current
        held = [resumed]
        check_batch(resumed)
        assert pipeline.close(timeout=5)
        assert not resumed.is_current
        resumed.release()
        held = []
    finally:
        for batch in held:
            batch.release()
        pipeline.close(timeout=5)
        torch.cuda.synchronize()
    return {
        "passed": True,
        "device": torch.cuda.get_device_name(0),
        "rounds": rounds,
        "direct_state_fill": direct_state_fill,
        "direct_state_batches": pipeline.direct_state_batches,
        "native_gather_available": NATIVE_GATHER_AVAILABLE,
        "readonly_source_checks": memory.source_checks,
        "checks": [
            "all replay fields and CUDA dtypes", "pinned host storage",
            "fp32 bank precision under AMP", "two-slot bound",
            "host/device allocation reuse", "delayed CUDA consumer lifetime",
            "single consumer stream restriction", "epoch invalidation",
            "pause/resume", "close with a live lease",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", default=str(Path(__file__).with_name("prefetch.py")))
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--direct-state-fill", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.module, args.rounds, args.direct_state_fill), indent=2))
