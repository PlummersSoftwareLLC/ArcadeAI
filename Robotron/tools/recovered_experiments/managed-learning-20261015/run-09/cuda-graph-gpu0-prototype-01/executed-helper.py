#!/usr/bin/env python3
"""Isolated GPU0 CUDA graph prototype; default is a read-only plan.

Never imports the training agent/replay or edits live sources. --execute must
run in a fresh process with an external timeout. No runtime graph capture or
silent fallback is permitted. GPU diagnostic returns use the compiled path.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

from benchmark_sidecar_inference import (GAME, GPU0_UUID, Plan, canonical_uuid,
    configure_environment, parity, require_idle_gpu, timing_summary)


EXACT_BATCHES = (32, 64, 128)
PROBE_BATCHES = (1, 31, 33, 50, 63, 65, 96, 127)
COMPILE_OPTIONS = {"triton.cudagraphs": False}
CHECKPOINT_SHA = "50a374d33250713ba205024f85aaed3e50b62db913c29b2c2fb8c28392f051af"
REFRESH_SHA = "b8db175280b8e5d49865d14c83dccfe90737dfcb33d13d219ff5bb38d9abf281"
DOCS = ["https://docs.pytorch.org/docs/2.14/notes/cuda.html#cuda-graphs",
        "https://docs.pytorch.org/docs/2.14/generated/torch.compile.html"]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bucket_size(rows, *, padding=False):
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 1:
        raise ValueError("A positive integer row count is required")
    if rows in EXACT_BATCHES:
        return rows
    if padding:
        return next((size for size in EXACT_BATCHES if size >= rows), None)
    return None


def graph_state(torch):
    counters = torch._dynamo.utils.counters
    return {name: dict(counters.get(name, {}))
            for name in ("stats", "graph_break", "unimplemented")}


class ExactGraphBank:
    """Prototype ownership boundary, independent of every live agent instance.

    Constructor captures all shapes serially before serving. All calls and
    in-place refreshes share one lock and inference stream. No captured output
    escapes to CUDA callers, and blocking CPU copies finish before lock release.
    Each capture uses its own private memory pool (no ordering assumption).
    """

    def __init__(self, torch, net, compiled, sample, *, lock=None):
        self.torch, self.net, self.compiled = torch, net, compiled
        self.lock = lock if lock is not None else threading.RLock()
        self.stream = torch.cuda.Stream(device=sample.device, priority=-1)
        self.slots = {}
        self.pointers = self.storage_pointers()
        self.closed = False
        self.error = None
        self.stream.wait_stream(torch.cuda.current_stream(sample.device))
        with self.lock, torch.no_grad(), torch.autocast("cuda", enabled=False):
            # All compiled shapes are already warm; this also warms libraries
            # on the exact dedicated stream used for capture and serving.
            for size in EXACT_BATCHES:
                with torch.cuda.stream(self.stream):
                    inputs = sample[:size].clone()
                    for _ in range(3):
                        compiled(inputs)
                self.stream.synchronize()
                graph = torch.cuda.CUDAGraph()
                with torch.cuda.graph(graph, stream=self.stream, capture_error_mode="global"):
                    outputs = compiled(inputs)
                self.slots[size] = (graph, inputs, outputs)
        self.stream.synchronize()
        self.guard = graph_state(torch)

    def storage_pointers(self):
        return {key: (value.data_ptr(), tuple(value.shape), tuple(value.stride()), str(value.dtype),str(value.device))
                for key, value in self.net.state_dict().items()}

    def check(self):
        if self.closed or self.error is not None:
            raise RuntimeError("CUDA graph bank closed or failed: " + str(self.error))
        if graph_state(self.torch) != self.guard:
            raise RuntimeError("Compilation state changed after startup capture")

    def call(self, states, *, return_cpu=True, padding=False, use_graph=True):
        t = self.torch
        with self.lock, t.no_grad(), t.autocast("cuda", enabled=False):
            self.check()
            try:
                caller = t.cuda.current_stream(states.device if states.is_cuda else "cuda:0")
                if states.is_cuda:
                    self.stream.wait_stream(caller)
                started = time.perf_counter()
                # GPU diagnostics always use the original compiled callable.
                size = bucket_size(int(states.shape[0]), padding=padding) if return_cpu and use_graph else None
                with t.cuda.stream(self.stream):
                    if size is None:
                        inputs = states.to("cuda:0")
                        inputs.record_stream(self.stream)
                    else:
                        graph, inputs, outputs = self.slots[size]
                        inputs[:len(states)].copy_(states)
                        if len(states) < size:
                            inputs[len(states):].zero_()
                    transferred = time.perf_counter()
                    if size is None:
                        outputs = self.compiled(inputs)
                    else:
                        graph.replay()
                    dispatched = time.perf_counter()
                    if return_cpu:
                        # A fresh CPU allocation, never a shared reusable buffer.
                        result = outputs[:len(states)].detach().cpu()
                    else:
                        result = outputs
                    finished = time.perf_counter()
                if not return_cpu:
                    caller.wait_stream(self.stream)
                    result.record_stream(caller)
                self.check()
                return result, dict(input_host_ms=(transferred-started)*1000,
                    dispatch_host_ms=(dispatched-transferred)*1000,
                    readback_host_ms=(finished-dispatched)*1000,
                    service_host_ms=(finished-started)*1000,
                    route="graph" if size else "compiled", bucket=size)
            except BaseException as error:
                self.error = repr(error)
                raise

    def refresh(self, state):
        t = self.torch
        with self.lock, t.no_grad():
            self.check()
            source = t.cuda.current_stream("cuda:0")
            ready, copied = t.cuda.Event(), t.cuda.Event()
            ready.record(source)
            with t.cuda.stream(self.stream):
                self.stream.wait_event(ready)
                self.net.load_state_dict(state, strict=True, assign=False)
                copied.record(self.stream)
            source.wait_event(copied)
            if self.storage_pointers() != self.pointers:
                self.error = "Parameter/buffer storage changed during refresh"
                raise RuntimeError(self.error)

    def close(self):
        with self.lock:
            self.stream.synchronize()
            self.closed = True


def validate_plan(plan, refresh):
    plan.validate()
    if plan.sample_rows != 128 or plan.states is None:
        raise ValueError("Require the explicit readonly 128-row real-bank sample")
    if digest(plan.checkpoint) != CHECKPOINT_SHA or digest(refresh) != REFRESH_SHA:
        raise ValueError("Only exact protected32M and protected16M refresh weights are allowed")


def description(plan):
    result=plan.description()
    result.update(warm_shapes=sorted(set(EXACT_BATCHES+PROBE_BATCHES)),
        intermediate_shapes=list(PROBE_BATCHES),static_capture_shapes=list(EXACT_BATCHES),
        warm_variants=["real_bank","empty"],compile_dynamic="both dynamic=True and dynamic=False",
        comparison_rule="Prototype only; reject padding action drift and require GB300 timing plus a fresh graph-backend whole-game reference before a production claim.")
    return result


def run(plan, refresh):
    validate_plan(plan, refresh)
    require_idle_gpu(plan)
    configure_environment(plan)
    os.environ["TORCH_EXTENSIONS_DIR"] = str(plan.directory / "extensions")
    plan.directory.mkdir(parents=True)
    def progress(event, **fields):
        row=dict(event=event,pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat(),**fields)
        with (plan.directory/"progress.jsonl").open("a") as out:
            out.write(json.dumps(row)+"\n")
        print(json.dumps(row),flush=True)
    progress("start")
    sys.path.insert(0, str(GAME / "Scripts"))
    import numpy as np
    import torch
    import torch._dynamo as dynamo
    from dqn.inference_actor import InferenceActor

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    if torch.cuda.device_count() != 1 or canonical_uuid(torch.cuda.get_device_properties(0).uuid) != canonical_uuid(GPU0_UUID):
        raise RuntimeError("CUDA visibility is not exclusively physical GPU0")
    actor = InferenceActor(plan.checkpoint, device="cuda:0", inference_backend="eager")
    # Match production main's infer_net flags and no_grad context, not the
    # sidecar adapter's requires_grad=False/inference_mode specialization.
    actor.infer_net.requires_grad_(True)
    source = np.load(plan.states, mmap_mode="r", allow_pickle=False)
    if source.dtype != np.float32 or source.shape != (128, actor.state_size):
        raise ValueError("Real-bank sample must be exactly128xstate_size float32")
    array = np.array(source, copy=True)
    if not np.isfinite(array).all():
        raise ValueError("Non-finite state sample")
    sample_provenance=json.loads(plan.states.with_suffix(".json").read_text())
    if hashlib.sha256(array.tobytes()).hexdigest()!=sample_provenance["sha256"]:
        raise ValueError("Archived real-state payload differs from its provenance")
    cpu = torch.from_numpy(array)
    samples = {"real_bank": cpu, "empty": torch.zeros_like(cpu)}
    refresh_state, _, refresh_hash, _ = actor._read_checkpoint(refresh)
    refresh_gpu = {name: value.to("cuda:0") for name, value in refresh_state.items()}
    original_gpu = {name: value.to("cuda:0") for name, value in actor._original_policy.items()}
    torch.cuda.synchronize()
    dynamo.config.suppress_errors = False
    dynamo.config.error_on_recompile = False
    for name, value in (("recompile_limit",64),("cache_size_limit",64),
                        ("accumulated_recompile_limit",1024),("accumulated_cache_size_limit",1024)):
        if hasattr(dynamo.config, name):
            setattr(dynamo.config, name, value)
    report = dict(schema="robotron-cuda-graph-prototype-v1", created_utc=datetime.now(timezone.utc).isoformat(),
        plan=description(plan), checkpoint_sha256=actor.checkpoint_sha256,
        refresh_checkpoint_sha256=refresh_hash, checkpoint_metadata=actor.checkpoint_metadata,
        base_numeric_policy=actor.numeric_policy, runtime_context="torch.no_grad, autocast disabled, infer_net requires_grad=True",
        backend_policies={name:dict(compiled=name!="eager",dynamic=name.startswith("dynamic"),
            explicit_cuda_graph=name.endswith("graph"),internal_cudagraphs=False) for name in
            ("eager","dynamic_compiled","static_compiled","dynamic_graph","static_graph")},
        torch=torch.__version__, cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(0),
        sample_sha256=digest(plan.states), copied_state_sha256=hashlib.sha256(array.tobytes()).hexdigest(),
        real_sample_provenance=sample_provenance,
        docs=DOCS, installed_graphs_source=str(Path(torch.__file__).parent/"cuda/graphs.py"),
        installed_graphs_source_sha256=digest(Path(torch.__file__).parent/"cuda/graphs.py"),
        timings={}, parity={}, refresh={}, ownership={}, compile={})
    began = time.monotonic()
    dynamic = torch.compile(actor.infer_net.q_values_joint, dynamic=True, options=COMPILE_OPTIONS)
    static = torch.compile(actor.infer_net.q_values_joint, dynamic=False, options=COMPILE_OPTIONS)
    funcs = {"dynamic":dynamic, "static":static}
    # Compile every context and shape before capture, never inside a graph.
    with torch.no_grad(), torch.autocast("cuda", enabled=False):
        for name, fn in funcs.items():
            progress("warm_start",backend=name)
            t0=time.monotonic()
            shapes = sorted(set(EXACT_BATCHES + PROBE_BATCHES)) if name=="dynamic" else EXACT_BATCHES
            for size in shapes:
                for data in samples.values():
                    fn(data[:size].to("cuda:0")).cpu()
            report["compile"][name+"_warm_s"] = time.monotonic()-t0
            progress("warm_complete",backend=name,elapsed_s=time.monotonic()-t0)
    if graph_state(torch)["graph_break"] or graph_state(torch)["unimplemented"]:
        raise RuntimeError("Graph breaks or unsupported compilation during startup")
    dynamo.config.error_on_recompile=True
    banks={}
    for name,fn in funcs.items():
        progress("capture_start",backend=name)
        t0=time.monotonic()
        banks[name]=ExactGraphBank(torch,actor.infer_net,fn,cpu.to("cuda:0"),lock=actor._sync_lock)
        report["compile"][name+"_capture_s"]=time.monotonic()-t0
        progress("capture_complete",backend=name,elapsed_s=time.monotonic()-t0)
    # Counter snapshot is process-global; both capture banks now fully ready.
    for bank in banks.values():
        bank.guard=graph_state(torch)
    report["compile"]["guard"]=graph_state(torch)
    progress("timing_start")

    def ordinary(fn,data):
        # Same input/readback stream as graph service, but eager or compiled.
        bank=banks["dynamic"]
        with bank.lock, torch.no_grad(), torch.autocast("cuda", enabled=False), torch.cuda.stream(bank.stream):
            started=time.perf_counter()
            inputs=data.to("cuda:0")
            transferred=time.perf_counter()
            q=fn(inputs)
            dispatched=time.perf_counter()
            q=q.detach().cpu()
            finished=time.perf_counter()
        return q,dict(input_host_ms=(transferred-started)*1000,dispatch_host_ms=(dispatched-transferred)*1000,
            readback_host_ms=(finished-dispatched)*1000,service_host_ms=(finished-started)*1000)

    for variant,data in samples.items():
        for size in EXACT_BATCHES:
            routes={"eager":lambda:ordinary(actor.infer_net.q_values_joint,data[:size]),
                "dynamic_compiled":lambda:ordinary(dynamic,data[:size]),
                "static_compiled":lambda:ordinary(static,data[:size]),
                "dynamic_graph":lambda:banks["dynamic"].call(data[:size]),
                "static_graph":lambda:banks["static"].call(data[:size])}
            baseline=routes["dynamic_compiled"]()[0]
            for route,call in routes.items():
                q,_=call()
                key=f"{variant}_{size}_{route}"
                report["parity"][key]=parity(baseline.tolist(),q.tolist())
                phases={name:[] for name in ("input_host_ms","dispatch_host_ms","readback_host_ms","service_host_ms")}
                # Alternate route order each repetition, rather than treating
                # separately-timed blocks as a controlled host comparison.
                report["timings"][key]=phases
            for repetition in range(plan.repetitions):
                for route in (list(routes) if repetition%2==0 else list(routes)[::-1]):
                    _,timing=routes[route]()
                    for phase in phases:
                        report["timings"][f"{variant}_{size}_{route}"][phase].append(timing[phase])
    for key,phases in report["timings"].items():
        report["timings"][key]={phase:timing_summary(values) for phase,values in phases.items()}
    for size in PROBE_BATCHES:
        expected,_=banks["dynamic"].call(cpu[:size],use_graph=False)
        for name,bank in banks.items():
            actual,timing=bank.call(cpu[:size],padding=True)
            report["parity"][f"padded_{size}_to_{bucket_size(size,padding=True)}_{name}"]=parity(expected.tolist(),actual.tolist())
            report["timings"][f"padded_{size}_{name}"]=timing
    for name,bank in banks.items():
        initial,_=bank.call(cpu[:64])
        saved=initial.clone()
        diagnostic,route=bank.call(cpu[:64],return_cpu=False)
        diagnostic_saved=diagnostic.detach().cpu().clone()
        bank.call(cpu.flip(0)[:64])
        report["ownership"][name]=dict(cpu_result_preserved=bool(torch.equal(initial,saved)),
            diagnostic_route=route["route"],diagnostic_result_preserved=bool(torch.equal(diagnostic.cpu(),diagnostic_saved)),
            independent_graph_pools=len({slot[0].pool() for slot in bank.slots.values()})==len(EXACT_BATCHES))
        originals={size:bank.call(cpu[:size])[0] for size in EXACT_BATCHES}
        bank.refresh(refresh_gpu)
        refreshed={size:bank.call(cpu[:size])[0] for size in EXACT_BATCHES}
        expected={size:bank.call(cpu[:size],use_graph=False)[0] for size in EXACT_BATCHES}
        eager_expected={size:ordinary(actor.infer_net.q_values_joint,cpu[:size])[0] for size in EXACT_BATCHES}
        bank.refresh(original_gpu)
        report["refresh"][name]={str(size):dict(changed_after_refresh=not bool(torch.equal(originals[size],refreshed[size])),
            refreshed_vs_compiled=parity(expected[size].tolist(),refreshed[size].tolist()),
            refreshed_vs_eager=parity(eager_expected[size].tolist(),refreshed[size].tolist()),
            restored_vs_initial=parity(originals[size].tolist(),bank.call(cpu[:size])[0].tolist()),
            all_parameter_buffer_storage_preserved=bank.storage_pointers()==bank.pointers) for size in EXACT_BATCHES}
        kept=[(bank.call(cpu[:size])[0],size) for size in (128,32,64)]
        copies=[q.clone() for q,size in kept]
        bank.call(cpu.flip(0)[:128])
        report["ownership"][name]["cross_bucket_results_preserved"]=all(torch.equal(q,copy) for (q,size),copy in zip(kept,copies))
    # Thread uses exactly the no_grad/autocast/stream context used at startup.
    errors=[]
    def serve_thread():
        try:
            for bank in banks.values():
                for size in EXACT_BATCHES:
                    bank.call(cpu[:size])
        except BaseException as error:
            errors.append(repr(error))
    worker=threading.Thread(target=serve_thread,daemon=True)
    worker.start(); worker.join(timeout=30)
    if worker.is_alive() or errors:
        raise RuntimeError("Cross-thread serving guard failed: "+repr(errors))
    # A delayed consumer must retain its own CPU result while another serving
    # thread reuses every graph's static GPU output buffer.
    published=threading.Event(); reused=threading.Event(); ownership_errors=[]
    def delayed_consumer():
        try:
            retained,_=banks["dynamic"].call(cpu[:64])
            expected=retained.clone(); published.set()
            if not reused.wait(10) or not torch.equal(retained,expected):
                ownership_errors.append("retained CPU output changed or second caller blocked")
        except BaseException as error: ownership_errors.append(repr(error)); published.set()
    consumer=threading.Thread(target=delayed_consumer,daemon=True);consumer.start()
    if not published.wait(10): raise RuntimeError("Delayed consumer failed to publish")
    for size in (128,32,64): banks["dynamic"].call(cpu.flip(0)[:size])
    reused.set();consumer.join(timeout=10)
    report["ownership"]["two_thread_delayed_consumer_preserved"]=not consumer.is_alive() and not ownership_errors
    if consumer.is_alive() or ownership_errors: raise RuntimeError(repr(ownership_errors))
    report["compile"]["end_guard"]=graph_state(torch)
    report["exact_final_weights"]=all(torch.equal(value.cpu(),actor._original_policy[key])
        for key,value in actor.infer_net.state_dict().items())
    report["memory"]={"allocated":torch.cuda.memory_allocated(),"reserved":torch.cuda.memory_reserved(),
        "peak_allocated":torch.cuda.max_memory_allocated(),"peak_reserved":torch.cuda.max_memory_reserved()}
    report["elapsed_s"]=time.monotonic()-began
    report["limitation"]="GPU0 isolated prototype only, no GB300/training-concurrency evidence or live integration. Padding and compiled kernels may change action ties; whole-game same-backend reference remains required. Host dispatch is enqueue time, not GPU kernel time."
    require_idle_gpu(plan)
    for bank in banks.values(): bank.close()
    actor.close()
    report["source_hashes"]={str(path.relative_to(GAME)):digest(path) for path in
        (Path(__file__),GAME/"Scripts/dqn/agent.py",GAME/"Scripts/dqn/model.py",GAME/"Scripts/dqn/config.py",GAME/"Scripts/dqn/inference_actor.py")}
    destination=plan.directory/"result.json"
    destination.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    progress("complete",elapsed_s=report["elapsed_s"])
    print(destination,flush=True)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,required=True)
    parser.add_argument("--repetitions",type=int,default=12)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args(argv)
    plan=Plan((GAME/"models_dqn/managed-incumbents/fresh3-32M-confirmed.pt").resolve(),args.directory.resolve(),
        repetitions=args.repetitions,states=(GAME/"logs/managed-learning-20261015/run-05/sidecar-compile-inputs/bank-states-128.npy").resolve())
    refresh=(GAME/"models_dqn/managed-incumbents/fresh3-16M-confirmed.pt").resolve()
    validate_plan(plan,refresh)
    if args.execute:
        try: run(plan,refresh)
        except BaseException as error:
            if plan.directory.is_dir():
                failure=dict(error=repr(error),created_utc=datetime.now(timezone.utc).isoformat())
                (plan.directory/"failure.json").write_text(json.dumps(failure)+"\n")
            raise
    else:
        print(json.dumps(dict(plan=description(plan),exact_batches=EXACT_BATCHES,padding_probes=PROBE_BATCHES,
            mode="plan_only",training=False,mame=False,docs=DOCS),indent=2))


if __name__=="__main__": main()
