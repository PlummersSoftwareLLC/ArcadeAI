#!/usr/bin/env python3
"""Plan, or explicitly run, one isolated inference-only compile comparison.

Default: print a plan without importing Torch or creating files. GPU execution
requires --execute, an idle designated GPU0, and an external timeout (240s is
recommended). Never launch this while a private evaluator occupies GPU0.
--cpu-facts only loads the checkpoint on CPU and records eager parity inputs.
This helper does not edit the actor, start MAME, train, or touch live controls.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time


GAME = Path(__file__).resolve().parents[1]
GPU0_UUID = "GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0"
WARM_SHAPES = (1, 2, 4, 8, 16)
COMPILE_OPTIONS = {"triton.cudagraphs": False}


def canonical_uuid(value):
    return str(value).lower().removeprefix("gpu-").replace("-", "")


@dataclass(frozen=True)
class Plan:
    checkpoint: Path
    directory: Path
    gpu_uuid: str = GPU0_UUID
    repetitions: int = 12
    sample_rows: int = 128
    states: Path | None = None

    def validate(self):
        if not self.checkpoint.is_file():
            raise ValueError("An existing checkpoint is required")
        if self.directory != self.directory.resolve() or self.directory.exists():
            raise ValueError("Use a new absolute output directory")
        if self.directory == GAME or GAME.is_relative_to(self.directory) or self.directory.is_relative_to(GAME / "models_dqn"):
            raise ValueError("Keep benchmark output separate from live models and source")
        if self.gpu_uuid != GPU0_UUID:
            raise ValueError("This bounded helper only permits the designated GPU0; GB300 is excluded")
        if not 3 <= self.repetitions <= 30 or not 16 <= self.sample_rows <= 512:
            raise ValueError("Require repetitions3..30 and sample_rows16..512")
        if self.states is not None and not self.states.is_file():
            raise ValueError("The optional readonly .npy state sample must exist")

    def description(self):
        return dict(checkpoint=str(self.checkpoint), directory=str(self.directory),
                    gpu_uuid=self.gpu_uuid, repetitions=self.repetitions, sample_rows=self.sample_rows,
                    states=str(self.states) if self.states else None,
                    compile_threads=2, cpu_threads=2, external_timeout_s=240,
                    warm_shapes=list(WARM_SHAPES), intermediate_shapes=list(range(1, 17)),
                    warm_variants=["empty", "populated"], worker_thread_guard_probe=True,
                    compile_dynamic=True, compile_options=COMPILE_OPTIONS,
                    weights="float32", inputs="float32", autocast=False, tf32="production high",
                    training=False, replay=False, mame=False,
                    comparison_rule="A fresh compiled GPU0 whole-game baseline is required; never pool eager job03 with compiled candidate legs.")


def require_idle_gpu(plan):
    output = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid",
                                      "--format=csv,noheader,nounits"], text=True, timeout=5)
    competing = [line.strip() for line in output.splitlines()
                 if plan.gpu_uuid in line and int(line.split(",", 1)[0]) != os.getpid()]
    if competing:
        raise RuntimeError("GPU0 has an active compute owner; defer the benchmark: " + "; ".join(competing))


def configure_environment(plan, *, cpu=False):
    if "torch" in sys.modules or "numpy" in sys.modules:
        raise RuntimeError("Run this helper in a fresh process before numerical imports")
    os.environ["CUDA_VISIBLE_DEVICES"] = "" if cpu else plan.gpu_uuid
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "TORCHINDUCTOR_COMPILE_THREADS"):
        os.environ[name] = "2"
    for name, relative in dict(TORCHINDUCTOR_CACHE_DIR="inductor", TRITON_CACHE_DIR="triton",
                               CUDA_CACHE_PATH="cuda-cache", TORCH_HOME="torch-home",
                               ROBOTRON_DQN_MODEL_DIR="isolated-models", ROBOTRON_DQN_CONTROL_PATH="isolated-control.json",
                               ROBOTRON_RUN_DIR="isolated-report").items():
        os.environ[name] = str(plan.directory / relative)
    os.environ.pop("LD_PRELOAD", None)
    os.environ.pop("ROBOTRON_SOCKET_WAIT_ACTIVE", None)
    os.environ["ROBOTRON_TRAIN_GPU"] = os.environ["ROBOTRON_INFERENCE_GPU"] = "0"


def parity(eager, compiled, *, atol=1e-3, rtol=1e-3):
    if not eager or len(eager) != len(compiled) or any(len(a) != 81 or len(b) != 81 for a, b in zip(eager, compiled)):
        raise ValueError("Aligned nonempty81-action Q rows are required")
    if any(not math.isfinite(v) for group in (eager, compiled) for row in group for v in row):
        raise ValueError("Q values must be finite")
    differences, agree, locked, close, gaps, flipped_gaps = [], 0, 0, True, [], []
    for a, b in zip(eager, compiled):
        differences.extend(abs(x-y) for x, y in zip(a, b))
        close &= all(abs(x-y) <= atol + rtol * abs(x) for x, y in zip(a, b))
        joint_same = max(range(81), key=lambda i: a[i]) == max(range(81), key=lambda i: b[i])
        agree += joint_same
        top = sorted(a, reverse=True)
        gaps.append(top[0]-top[1])
        if not joint_same:
            flipped_gaps.append(gaps[-1])
        for fire in range(9):
            locked += max(range(9), key=lambda move: a[move*9+fire]) == max(range(9), key=lambda move: b[move*9+fire])
    return dict(rows=len(eager), atol=atol, rtol=rtol, q_allclose=bool(close),
                max_abs_error=max(differences), rms_error=math.sqrt(statistics.mean(v*v for v in differences)),
                greedy_agreement=agree/len(eager), locked_fire_agreement=locked/(9*len(eager)),
                eager_top_two_gap_min=min(gaps), eager_top_two_gap_median=statistics.median(gaps),
                flipped_joint_eager_gaps=flipped_gaps)


def timing_summary(values):
    ordered = sorted(values)
    return dict(calls=len(values), median_ms=statistics.median(values),
                p95_ms=ordered[min(len(ordered)-1, math.ceil(.95*len(ordered))-1)],
                minimum_ms=min(values), maximum_ms=max(values))


def _graphs(torch):
    return int(torch._dynamo.utils.counters.get("stats", {}).get("unique_graphs", 0))


def run(plan, *, cpu=False):
    plan.validate()
    if not cpu:
        require_idle_gpu(plan)
    configure_environment(plan, cpu=cpu)
    plan.directory.mkdir(parents=True)
    sys.path.insert(0, str(GAME / "Scripts"))
    import numpy as np
    import torch
    from dqn.inference_actor import InferenceActor

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    started = time.monotonic()
    actor = InferenceActor(plan.checkpoint, device="cpu" if cpu else "cuda:0")
    if not cpu and canonical_uuid(torch.cuda.get_device_properties(0).uuid) != canonical_uuid(plan.gpu_uuid):
        raise RuntimeError(f"Physical CUDA device identity differs from the designated GPU0: {torch.cuda.get_device_properties(0).uuid}")
    if plan.states:
        before = plan.states.stat()
        source = np.load(plan.states, mmap_mode="r", allow_pickle=False)
        if source.ndim != 2 or source.shape[1] != actor.state_size or source.shape[0] < plan.sample_rows:
            raise ValueError("Readonly states must contain the requested rows with the exact state size")
        array = np.array(source[:plan.sample_rows], dtype=np.float32, copy=True)
        after = plan.states.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise RuntimeError("Readonly state sample changed while copying")
        sample_kind = "explicit readonly .npy prefix; no live replay RNG used"
    else:
        array = np.random.default_rng(20261016).random((plan.sample_rows, actor.state_size), dtype=np.float32)
        sample_kind = "synthetic uniform populated states; parity does not establish game-policy equivalence"
    if not np.isfinite(array).all():
        raise ValueError("State sample contains non-finite values")
    arrays = {"empty": torch.zeros(16, actor.state_size), "populated": torch.from_numpy(array[:16])}
    pointers = {key: value.data_ptr() for key, value in actor.infer_net.state_dict().items()}
    result = dict(plan=plan.description(), sample_kind=sample_kind, checkpoint_sha256=actor.checkpoint_sha256,
                  checkpoint_metadata=actor.checkpoint_metadata, numeric_policy=actor.numeric_policy,
                  copied_state_sha256=hashlib.sha256(array.tobytes()).hexdigest(),
                  runtime_context="torch.inference_mode / autocast disabled",
                  torch=torch.__version__, created_utc=datetime.now(timezone.utc).isoformat())

    def call(fn, states):
        # Match the adapter's inference context, CPU validation, transfer,
        # output finite check and CPU readback; time the full serving cost.
        with actor._sync_lock, torch.inference_mode(), torch.autocast(actor.device.type, enabled=False):
            if not bool(torch.isfinite(states).all()):
                raise ValueError("Non-finite benchmark input")
            output = fn(states.to(actor.device))
            if output.shape != (len(states), 81) or not bool(torch.isfinite(output).all()):
                raise ValueError("Invalid benchmark Q output")
            return output.detach().cpu()

    eager_fn = actor.infer_net.q_values_joint
    if cpu:
        q = call(eager_fn, arrays["populated"])
        result.update(mode="cpu_facts", evaluated_rows=len(q), cuda_initialized=torch.cuda.is_initialized(),
                      q_min=float(q.min()), q_max=float(q.max()), q_mean=float(q.mean()),
                      q_sha256=hashlib.sha256(q.numpy().tobytes()).hexdigest(),
                      greedy_actions=actor.act_batch(array[:16], [0]*16),
                      cpu_action_and_q_internal_parity=parity(q.tolist(), actor._infer_q_joint(arrays["populated"], return_cpu=True).tolist()))
    else:
        import torch._dynamo as dynamo
        for name, value in (("recompile_limit", 64), ("cache_size_limit", 64),
                            ("accumulated_recompile_limit", 1024), ("accumulated_cache_size_limit", 1024)):
            if hasattr(dynamo.config, name):
                setattr(dynamo.config, name, value)
        compiled_fn = torch.compile(eager_fn, dynamic=True, options=dict(COMPILE_OPTIONS))
        warm_start = time.monotonic()
        warm = []
        for batch in WARM_SHAPES:
            for variant, tensor in arrays.items():
                t0 = time.monotonic()
                call(compiled_fn, tensor[:batch])
                warm.append(dict(batch=batch, variant=variant, wall_s=time.monotonic()-t0))
        warm_s = time.monotonic()-warm_start
        warm_graphs = _graphs(torch)
        for batch in range(1, 17):
            for tensor in arrays.values():
                call(compiled_fn, tensor[:batch])
        worker_error = []

        def worker_probe():
            try:
                for batch in range(1, 17):
                    call(compiled_fn, arrays["populated"][:batch])
            except BaseException as error:
                worker_error.append(repr(error))

        worker = threading.Thread(target=worker_probe, daemon=True)
        worker.start()
        worker.join(timeout=60)
        if worker.is_alive() or worker_error:
            raise RuntimeError("Serving-thread warm guard failed: " + repr(worker_error))
        guard_graphs = _graphs(torch)
        comparisons, timings = {}, {}
        for variant, tensor in arrays.items():
            for batch in WARM_SHAPES:
                eager_q = call(eager_fn, tensor[:batch])
                compiled_q = call(compiled_fn, tensor[:batch])
                comparisons[f"{variant}_{batch}"] = parity(eager_q.tolist(), compiled_q.tolist())
                for name, fn in (("eager", eager_fn), ("compiled", compiled_fn)):
                    # Inject only this isolated actor instance's Q dispatch.
                    # The timed call is its actual act_batch including NumPy
                    # conversion, epsilon/lock checks and CPU action decoding.
                    original_infer = actor._infer_q_joint
                    actor._infer_q_joint = lambda states, return_cpu=False, serve=fn: call(serve, states)
                    state_rows = tensor[:batch].numpy()
                    epsilons = [0]*batch
                    locked_fires = [None if i % 2 == 0 else i % 9 for i in range(batch)]
                    samples = []
                    try:
                        for _ in range(plan.repetitions):
                            t0 = time.perf_counter()
                            actor.act_batch(state_rows, epsilons, locked_fires)
                            samples.append((time.perf_counter()-t0)*1000)
                    finally:
                        actor._infer_q_joint = original_infer
                    timings[f"{variant}_{batch}_{name}"] = timing_summary(samples)
        sample_eager, sample_compiled = [], []
        for first in range(0, len(array), 16):
            tensor = torch.from_numpy(array[first:first+16])
            sample_eager.extend(call(eager_fn, tensor).tolist())
            sample_compiled.extend(call(compiled_fn, tensor).tolist())
        sample_parity = parity(sample_eager, sample_compiled)
        require_idle_gpu(plan)
        unchanged = all(torch.equal(value.detach().cpu(), actor._original_policy[key])
                        for key, value in actor.infer_net.state_dict().items())
        result.update(mode="gpu_eager_vs_compiled", gpu_name=torch.cuda.get_device_name(0),
                      warm_s=warm_s, warm_calls=warm,
                      graphs_after_warm=warm_graphs, graphs_after_shape_thread_probes=guard_graphs,
                      graphs_after_benchmark=_graphs(torch), timings=timings, parity_by_warm_shape=comparisons,
                      sample_parity=sample_parity, exact_model_values_preserved=unchanged,
                      compiled_numeric_policy=dict(actor.numeric_policy, execution="torch.compile", compiled=True,
                          dynamic=True, compile_options=COMPILE_OPTIONS, warm_shapes=list(WARM_SHAPES)),
                      memory=dict(allocated_bytes=torch.cuda.memory_allocated(0), reserved_bytes=torch.cuda.memory_reserved(0),
                                  max_allocated_bytes=torch.cuda.max_memory_allocated(0), max_reserved_bytes=torch.cuda.max_memory_reserved(0)))
    result.update(storage_preserved=all(value.data_ptr() == pointers[key] for key, value in actor.infer_net.state_dict().items()),
                  elapsed_s=time.monotonic()-started, inference_error=actor.inference_error,
                  limitation="Compiled and eager numerics can differ near action ties. Synthetic parity and speed do not replace fresh same-backend whole-game controls.")
    destination = plan.directory / "result.json"
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    actor.close()
    print(destination)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--gpu-uuid", default=GPU0_UUID)
    parser.add_argument("--repetitions", type=int, default=12)
    parser.add_argument("--sample-rows", type=int, default=128)
    parser.add_argument("--states", type=Path)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--execute", action="store_true")
    actions.add_argument("--cpu-facts", action="store_true")
    args = parser.parse_args(argv)
    plan = Plan(args.checkpoint.resolve(), args.directory.resolve(), args.gpu_uuid,
                args.repetitions, args.sample_rows, args.states.resolve() if args.states else None)
    plan.validate()
    if args.execute or args.cpu_facts:
        run(plan, cpu=args.cpu_facts)
    else:
        print(json.dumps(plan.description(), indent=2))


if __name__ == "__main__":
    main()
