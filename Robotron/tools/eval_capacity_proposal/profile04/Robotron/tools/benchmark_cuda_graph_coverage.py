#!/usr/bin/env python3
"""Default-plan-only, bounded GPU0 coverage probe for exact batches 1..128.

New output directory required. No training/source/control changes, no padding,
pool sharing, runtime capture, or GB300 visibility. External timeout: 300s.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sys
import threading
import time

from benchmark_cuda_graph_inference import (ExactGraphBank,COMPILE_OPTIONS,digest,
    validate_plan,graph_state,DOCS)
from benchmark_sidecar_inference import (GAME,GPU0_UUID,Plan,canonical_uuid,
    configure_environment,require_idle_gpu,parity,timing_summary)

SHAPES=tuple(range(1,129))
BUDGET_BYTES=10*(1<<30)
WALL_BUDGET_S=285


def pool_usage(segments, pool_ids):
    """Account actual allocator segments by graph pool, without reading tensors."""
    result={str(shape):dict(pool_id=list(pool),reserved_bytes=0,allocated_bytes=0,active_bytes=0,segments=0)
            for shape,pool in pool_ids.items()}
    by_pool={tuple(pool):result[str(shape)] for shape,pool in pool_ids.items()}
    for segment in segments:
        record=by_pool.get(tuple(segment.get("segment_pool_id",())))
        if record is not None:
            record["reserved_bytes"]+=int(segment["total_size"])
            record["allocated_bytes"]+=int(segment["allocated_size"])
            record["active_bytes"]+=int(segment["active_size"])
            record["segments"]+=1
    return result


def description(plan):
    return dict(checkpoint=str(plan.checkpoint),directory=str(plan.directory),gpu_uuid=GPU0_UUID,
        shapes=list(SHAPES),padding=False,private_pool_per_shape=True,internal_cudagraphs=False,
        compile_dynamic=True,grad_context="no_grad",weights_inputs="float32",autocast=False,
        cpu_threads=2,compile_threads=2,repetitions=plan.repetitions,memory_budget_bytes=BUDGET_BYTES,
        internal_wall_budget_s=WALL_BUDGET_S,external_timeout_s=300,training=False,mame=False,GB300=False)


def run(plan,refresh):
    validate_plan(plan,refresh)
    require_idle_gpu(plan)
    configure_environment(plan)
    os.environ["TORCH_EXTENSIONS_DIR"]=str(plan.directory/"extensions")
    plan.directory.mkdir(parents=True)
    started=time.monotonic(); captured=[]; progress_rows=[]
    def progress(event,**fields):
        row=dict(event=event,pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-started,**fields)
        progress_rows.append(row)
        with (plan.directory/"progress.jsonl").open("a") as out:out.write(json.dumps(row)+"\n")
        if event!="captured" or fields.get("shape",0)%16==0 or fields.get("shape")==1:
            print(json.dumps(row),flush=True)
    progress("start")
    try:
        sys.path.insert(0,str(GAME/"Scripts"))
        import numpy as np
        import torch
        import torch._dynamo as dynamo
        from dqn.inference_actor import InferenceActor
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        if torch.cuda.device_count()!=1 or canonical_uuid(torch.cuda.get_device_properties(0).uuid)!=canonical_uuid(GPU0_UUID):
            raise RuntimeError("Physical device visibility is not GPU0 only")
        free,total=torch.cuda.mem_get_info()
        if free<BUDGET_BYTES+(1<<30):raise RuntimeError("GPU0 has less than budget plus1GiB free headroom")
        # The allocator enforces this in addition to per-shape reserved checks.
        # Library/driver allocations are outside this allocator budget.
        torch.cuda.set_per_process_memory_fraction(BUDGET_BYTES/total,0)
        actor=InferenceActor(plan.checkpoint,device="cuda:0",inference_backend="eager")
        actor.infer_net.requires_grad_(True)
        source=np.load(plan.states,mmap_mode="r",allow_pickle=False)
        if source.dtype!=np.float32 or source.shape!=(128,actor.state_size):raise ValueError("Exact real128-row stacked sample required")
        array=np.array(source,copy=True)
        provenance=json.loads(plan.states.with_suffix(".json").read_text())
        import hashlib
        if not np.isfinite(array).all() or hashlib.sha256(array.tobytes()).hexdigest()!=provenance["sha256"]:
            raise ValueError("Archived real-state sample differs from its provenance")
        cpu=torch.from_numpy(array);empty=torch.zeros_like(cpu)
        changed,_,changed_sha,_=actor._read_checkpoint(refresh)
        changed_gpu={key:value.to("cuda:0") for key,value in changed.items()}
        original_gpu={key:value.to("cuda:0") for key,value in actor._original_policy.items()}
        torch.cuda.synchronize()
        dynamo.config.suppress_errors=False;dynamo.config.error_on_recompile=False
        for name,value in (("recompile_limit",64),("cache_size_limit",64),("accumulated_recompile_limit",1024),("accumulated_cache_size_limit",1024)):
            if hasattr(dynamo.config,name):setattr(dynamo.config,name,value)
        compiled=torch.compile(actor.infer_net.q_values_joint,dynamic=True,options=COMPILE_OPTIONS)
        progress("warm_start")
        warm_started=time.monotonic()
        with torch.no_grad(),torch.autocast("cuda",enabled=False):
            for size in SHAPES:
                for sample in (cpu,empty):compiled(sample[:size].to("cuda:0")).cpu()
                if time.monotonic()-started>WALL_BUDGET_S:raise TimeoutError("Startup warmup exceeded bounded wall budget")
        state=graph_state(torch)
        if state["graph_break"] or state["unimplemented"]:raise RuntimeError("Startup compilation contains graph breaks/unsupported paths")
        dynamo.config.error_on_recompile=True
        warm_s=time.monotonic()-warm_started
        progress("warm_complete",warm_s=warm_s,compile_state=state)
        capture_started=time.monotonic()
        def on_capture(size,bank):
            reserved,allocated=torch.cuda.memory_reserved(),torch.cuda.memory_allocated()
            captured.append(dict(bank.capture_history[-1],allocated_bytes=allocated,reserved_bytes=reserved,
                pool_id=list(bank.slots[size][0].pool()),capture_elapsed_s=time.monotonic()-capture_started))
            progress("captured",**captured[-1])
            if time.monotonic()-started>WALL_BUDGET_S:raise TimeoutError("Capture exceeded bounded wall budget")
        bank=ExactGraphBank(torch,actor.infer_net,compiled,cpu.to("cuda:0"),lock=actor._sync_lock,
            capture_sizes=SHAPES,reserve_budget_bytes=BUDGET_BYTES,capture_callback=on_capture)
        capture_s=time.monotonic()-capture_started
        private_pools={size:slot[0].pool() for size,slot in bank.slots.items()}
        pools=pool_usage(torch.cuda.memory_snapshot(),private_pools)
        if len(set(private_pools.values()))!=len(SHAPES):raise RuntimeError("Graph pools are shared")
        if not all(record["reserved_bytes"]>0 for record in pools.values()):raise RuntimeError("Private pool memory accounting is incomplete")
        report=dict(schema="robotron-exact-cuda-graph-coverage-v1",status="complete",plan=description(plan),
            checkpoint_sha256=actor.checkpoint_sha256,refresh_checkpoint_sha256=changed_sha,
            checkpoint_metadata=actor.checkpoint_metadata,numeric_policy=actor.numeric_policy,
            runtime_context="torch.no_grad/autocast disabled/requires_grad=True; existing dynamic compiled kernels",
            torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),
            sample_sha256=digest(plan.states),real_sample_provenance=provenance,compile_guard=bank.guard,
            warm_s=warm_s,capture_s=capture_s,capture_count=len(captured),capture_memory_growth=captured,
            private_pools=pools,private_pool_reserved_bytes=sum(row["reserved_bytes"] for row in pools.values()),
            initial_free_bytes=free,total_device_bytes=total,memory_budget_bytes=BUDGET_BYTES,
            all_parameter_buffer_storage_signature=bank.pointers,per_shape={},timings={},ownership={},docs=DOCS)
        def signature(q):return hashlib.sha256(q.numpy().tobytes()).hexdigest()
        original_q={};retained=[]
        progress("parity_start",checkpoint="32M")
        for size in SHAPES:
            expected,_=bank.call(cpu[:size],use_graph=False)
            actual,_=bank.call(cpu[:size])
            original_q[size]=expected
            report["per_shape"][str(size)]={"original32M":dict(parity(expected.tolist(),actual.tolist()),
                bit_identical=signature(expected)==signature(actual),compiled_sha256=signature(expected),graph_sha256=signature(actual))}
            retained.append((actual,signature(actual)))
            blank_expected,_=bank.call(empty[:size],use_graph=False);blank_actual,_=bank.call(empty[:size])
            report["per_shape"][str(size)]["original32M_empty"]=dict(parity(blank_expected.tolist(),blank_actual.tolist()),
                bit_identical=signature(blank_expected)==signature(blank_actual))
        progress("parity_complete",checkpoint="32M")
        bank.refresh(changed_gpu)
        progress("parity_start",checkpoint="16M_refresh")
        for size in SHAPES:
            expected,_=bank.call(cpu[:size],use_graph=False);actual,_=bank.call(cpu[:size])
            report["per_shape"][str(size)]["refreshed16M"]=dict(parity(expected.tolist(),actual.tolist()),
                bit_identical=signature(expected)==signature(actual),changed_from32M=signature(actual)!=signature(original_q[size]))
            blank_expected,_=bank.call(empty[:size],use_graph=False);blank_actual,_=bank.call(empty[:size])
            report["per_shape"][str(size)]["refreshed16M_empty"]=dict(parity(blank_expected.tolist(),blank_actual.tolist()),
                bit_identical=signature(blank_expected)==signature(blank_actual))
        bank.refresh(original_gpu)
        progress("parity_start",checkpoint="32M_restore")
        for size in SHAPES:
            restored,_=bank.call(cpu[:size]);expected,_=bank.call(cpu[:size],use_graph=False)
            report["per_shape"][str(size)]["restored32M"]=dict(parity(expected.tolist(),restored.tolist()),
                bit_identical=signature(expected)==signature(restored),matches_original32M=signature(restored)==signature(original_q[size]))
            blank_expected,_=bank.call(empty[:size],use_graph=False);blank_actual,_=bank.call(empty[:size])
            report["per_shape"][str(size)]["restored32M_empty"]=dict(parity(blank_expected.tolist(),blank_actual.tolist()),
                bit_identical=signature(blank_expected)==signature(blank_actual))
        for size in (32,50,64,128):
            measurements={name:{phase:[] for phase in ("input_host_ms","dispatch_host_ms","readback_host_ms","service_host_ms","full_call_host_ms")} for name in ("compiled","graph")}
            for repeat in range(plan.repetitions):
                for route in (("compiled","graph") if repeat%2==0 else ("graph","compiled")):
                    before=time.perf_counter();_,timing=bank.call(cpu[:size],use_graph=route=="graph")
                    timing["full_call_host_ms"]=(time.perf_counter()-before)*1000
                    for phase in measurements[route]:measurements[route][phase].append(timing[phase])
            report["timings"][str(size)]={name:{phase:timing_summary(values) for phase,values in fields.items()} for name,fields in measurements.items()}
        # Deterministic arbitrary replay order, independent of Torch/live RNG.
        order=list(SHAPES);random.Random(20261016).shuffle(order)
        diagnostics=[]
        for size in (1,32,50,64,128):
            q,route=bank.call(cpu[:size],return_cpu=False)
            diagnostics.append((q,signature(q.detach().cpu()),route["route"]))
        for size in order:bank.call(cpu.flip(0)[:size])
        report["ownership"].update(retained_all_shape_CPU_outputs=all(signature(q)==saved for q,saved in retained),
            diagnostic_GPU_outputs_use_compiled=all(route=="compiled" for q,saved,route in diagnostics),
            diagnostic_GPU_outputs_preserved=all(signature(q.detach().cpu())==saved for q,saved,route in diagnostics),
            arbitrary_replay_order=order,private_pool_count=len(set(private_pools.values())))
        published=threading.Event();consumed=threading.Event();errors=[]
        def delayed_consumer():
            try:
                q,_=bank.call(cpu[:50]);saved=signature(q);published.set()
                if not consumed.wait(10) or signature(q)!=saved:raise RuntimeError("Delayed CPU result changed or serialized caller blocked")
            except BaseException as error:errors.append(repr(error));published.set()
        worker=threading.Thread(target=delayed_consumer,daemon=True);worker.start()
        if not published.wait(10):raise RuntimeError("Serving thread failed to publish")
        for size in order:bank.call(cpu.flip(0)[:size])
        consumed.set();worker.join(timeout=10)
        if worker.is_alive() or errors:raise RuntimeError("Concurrent serialized call failed: "+repr(errors))
        report["ownership"]["two_thread_serialized_delayed_consumer"]=True
        report["end_compile_guard"]=graph_state(torch)
        report["all_parameter_buffer_storage_preserved"]=bank.storage_pointers()==bank.pointers
        report["all_final_weights_restored"]=all(torch.equal(value.cpu(),actor._original_policy[key]) for key,value in actor.infer_net.state_dict().items())
        report["memory"]=dict(allocated_bytes=torch.cuda.memory_allocated(),reserved_bytes=torch.cuda.memory_reserved(),
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
        report["elapsed_s"]=time.monotonic()-started
        if report["elapsed_s"]>WALL_BUDGET_S:raise TimeoutError("Validation exceeded bounded wall budget")
        phases=("original32M","refreshed16M","restored32M","original32M_empty","refreshed16M_empty","restored32M_empty")
        report["acceptance"]=dict(all128_shapes_bit_identical=all(v[phase]["bit_identical"] for v in report["per_shape"].values() for phase in phases),
            all_joint_and_held_fire_match=all(v[phase]["greedy_agreement"]==v[phase]["locked_fire_agreement"]==1 for v in report["per_shape"].values() for phase in phases),
            all_refresh_changes_and_restores=all(v["refreshed16M"]["changed_from32M"] and v["restored32M"]["matches_original32M"] for v in report["per_shape"].values()),
            no_runtime_recompile=bank.guard==graph_state(torch),within_memory_budget=torch.cuda.max_memory_reserved()<=BUDGET_BYTES)
        report["limitation"]="Single isolated GPU0 prototype, archived states, no GB300 performance/training overlap or live integration. Fullcall is Python lock/context/transfer/dispatch/readback/guard only, excluding socket/replay/epsilon/actiondecode. Host times are not GPU kernel times."
        require_idle_gpu(plan);bank.close();actor.close()
        report["source_hashes"]={str(p.relative_to(GAME)):digest(p) for p in (Path(__file__),Path(__file__).with_name("benchmark_cuda_graph_inference.py"),GAME/"Scripts/dqn/agent.py",GAME/"Scripts/dqn/model.py",GAME/"Scripts/dqn/config.py",GAME/"Scripts/dqn/inference_actor.py")}
        (plan.directory/"result.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
        progress("complete",acceptance=report["acceptance"])
        return report
    except BaseException as error:
        # CPU evidence survives even if CUDA capture itself failed. Do not try
        # more CUDA work or a reduced/fallback coverage run in this process.
        failure=dict(status="incomplete",error=repr(error),captured_shapes=[x["shape"] for x in captured],
            capture_memory_growth=captured,elapsed_s=time.monotonic()-started,plan=description(plan))
        (plan.directory/"incomplete.json").write_text(json.dumps(failure,indent=2)+"\n")
        raise


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
    if args.execute:run(plan,refresh)
    else:print(json.dumps(dict(mode="plan_only",plan=description(plan)),indent=2))


if __name__=="__main__":main()
