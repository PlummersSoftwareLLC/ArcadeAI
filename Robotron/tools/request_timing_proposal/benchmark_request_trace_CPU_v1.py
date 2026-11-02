"""Original CPU-only diagnostic-overhead investigation. Default is inert.

Exact source extraction only: no production module, Torch, MAME, GPU or network
imports. A NumPy tensor shim and bounded artificial model delay are explicit.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import random
import statistics
import sys
import threading
import time
import types

H = Path(__file__).resolve().parent
G = H.parents[1]
READER = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA = 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def publish(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, allow_nan=False, separators=(',', ':'))
        stream.write('\n'); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())


def checked_module(reader, name, entry):
    return reader.checked_module(name, entry)


def classes(socket_source, agent_source, trace, np):
    socket_nodes = [n for n in ast.parse(socket_source).body if isinstance(n, ast.ClassDef)
                    and n.name in ('_InferenceRequest', 'AsyncInferenceBatcher')]
    require(len(socket_nodes) == 2, 'Exact two batcher classes required')
    scope = dict(threading=threading, queue=queue, time=time, _request_trace=trace)
    exec(compile(ast.Module(body=socket_nodes, type_ignores=[]), '<CPU-extracted-batcher>', 'exec'), scope)
    method = next(n for n in ast.walk(ast.parse(agent_source)) if isinstance(n, ast.FunctionDef) and n.name == 'act_batch')
    method_scope = dict(_request_trace=trace, random=random.Random(123), np=np,
        torch=types.SimpleNamespace(from_numpy=lambda a: a), NUM_FIRE=9, NUM_MOVE=9,
        NUM_JOINT=81, split_joint_action=lambda j: divmod(j, 9))
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<CPU-extracted-act-batch>', 'exec'), method_scope)
    class Agent:
        act_batch = method_scope['act_batch']
        def __init__(self, delay):
            self.delay = delay
            self.calls = self.requests = 0
        def _safe_epsilon_action(self, state):
            return 2, 3, True
        def _infer_q_joint(self, states, return_cpu):
            if self.delay:
                time.sleep(self.delay)
            rows = np.tile(np.arange(81, dtype=np.float32), (len(states), 1))
            return types.SimpleNamespace(numpy=lambda: rows)
    return scope['AsyncInferenceBatcher'], Agent


def percentile(values, q):
    return sorted(values)[max(0, __import__('math').ceil(len(values)*q)-1)]


def one_block(block, baseline, proposed, trace, np, plan):
    mode, workers, delay = block['mode'], block['workers'], block['model_delay_s']
    Batcher, Agent = baseline if mode == 'original' else proposed
    agent = Agent(delay)
    batcher = Batcher(agent, max_batch_size=128, max_wait_ms=1., request_timeout_ms=3000.)
    # A fixed CPU observation vector per simulated actor. The exact extracted
    # act_batch performs the same NumPy batch packing and CPU action reduction.
    states = [np.full(11128, i/32., dtype=np.float32) for i in range(workers)]
    latencies, mismatches, failures = [[] for _ in range(workers)], [], []
    recorder = trace.Recorder(max_requests=4096, sample_every=64)
    def request(slot, turn):
        # Deterministic 10% epsilon-only requests, with all nine fire locks.
        # These are 0/1 controls, not the production random policy at epsilon .1.
        epsilon = 1. if (turn+slot) % 10 == 0 else 0.
        fire = (turn+slot) % 9
        expected = (2 if epsilon else 8, fire, bool(epsilon))
        start = time.perf_counter_ns()
        action = batcher.infer(states[slot], epsilon, locked_fire=fire)
        elapsed = time.perf_counter_ns() - start
        require(action == expected, 'CPU shim action changed')
        return elapsed
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # Warm the same batcher and worker threads before timing/capture.
        barrier = threading.Barrier(workers)
        def warm(slot):
            barrier.wait(timeout=5)
            for turn in range(8):
                request(slot, turn)
        for future in [pool.submit(warm, slot) for slot in range(workers)]:
            future.result(timeout=10)
        barrier = threading.Barrier(workers+1)
        def measured(slot):
            barrier.wait(timeout=5)
            for turn in range(plan['requests_per_worker']):
                try:
                    latencies[slot].append(request(slot, turn))
                except Exception as error:
                    failures.append(dict(slot=slot, turn=turn, error=repr(error)))
        try:
            with trace.capture(recorder) if mode == 'sparse64' else nullcontext():
                futures = [pool.submit(measured, slot) for slot in range(workers)]
                started = time.perf_counter_ns()
                barrier.wait(timeout=5)
                for future in futures:
                    future.result(timeout=20)
                elapsed = time.perf_counter_ns() - started
        finally:
            batcher.stop()
    values = [n for row in latencies for n in row]
    result = dict(**block, elapsed_ns=elapsed, completed=len(values), failures=failures,
        requests_per_s=len(values)/(elapsed/1e9), p50_request_ms=percentile(values,.5)/1e6,
        p95_request_ms=percentile(values,.95)/1e6, p99_request_ms=percentile(values,.99)/1e6,
        mean_request_ms=statistics.mean(values)/1e6,
        raw_request_ns=latencies, action_mismatches=mismatches)
    if mode == 'sparse64':
        snapshot = recorder.snapshot()
        result['trace'] = snapshot
        result['trace_analysis'] = trace.analyze(snapshot)
        require(not any(snapshot[k] for k in ('errors','capacity_drops','event_drops')), 'Trace capture loss')
        require(result['trace_analysis']['outcomes'] == {'returned': len(snapshot['rows'])}, 'Nonterminal sampled requests')
        require(not any(result['trace_analysis']['partition_residual_ns']), 'Partition residual')
    require(not failures and len(values) == workers*plan['requests_per_worker'], 'Incomplete block')
    return result


def run(plan_path, plan_sha):
    require(hashlib.sha256(READER.read_bytes()).hexdigest()==READER_SHA, 'Immutable reader changed')
    spec=importlib.util.spec_from_file_location('_CPU_trace_benchmark_reader', READER)
    reader=importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
    pin=reader.pin(plan_path); require(pin['sha256']==plan_sha, 'Precommitted plan changed')
    plan=reader.read_pin(pin)
    require(plan['schema']=='robotron-request-phase-CPU-overhead-plan-v1' and plan['requests_per_worker']==96,
        'Exact bounded CPU plan required')
    require(plan['workers']==[8,32] and plan['model_delays_s']==[0., .0008] and plan['controls']==['disabled','sparse64'],
        'Exact four CPU cells and two controls required')
    require(plan['max_throughput_loss']==.05 and plan['max_p95_increase']==.05, 'Prospective development gate changed')
    require(reader.pin(__file__)==plan['runner'], 'Runner changed')
    trace=checked_module(reader, 'request_phase_trace_v1', plan['trace'])
    builder=checked_module(reader, '_CPU_trace_source_builder', plan['builder'])
    sources={name:reader.read_pin(p,as_json=False).decode() for name,p in plan['sources'].items()}
    copied={name:builder.instrument(name,s) for name,s in sources.items()}
    require(all(builder.stripped_tree(sources[n])==builder.stripped_tree(copied[n]) for n in sources),
        'Operational AST changed')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='', 'Explicit CPU isolation required')
    import numpy as np
    baseline=classes(sources['socket_server.py'],sources['agent.py'],trace,np)
    proposed=classes(copied['socket_server.py'],copied['agent.py'],trace,np)
    output=Path(plan['output']);output.mkdir(mode=0o700)
    records=[]
    for workers in plan['workers']:
        for delay in plan['model_delays_s']:
            for control in plan['controls']:
                for position,mode in enumerate(['original',control,control,'original']):
                    block=dict(index=len(records),workers=workers,model_delay_s=delay,
                        control=control,position=position,mode=mode)
                    result=one_block(block,baseline,proposed,trace,np,plan)
                    path=output/('block-%02d.json'%block['index']);publish(path,result)
                    records.append(reader.pin(path))
                    print(json.dumps({k:result[k] for k in ['index','workers','model_delay_s','mode','completed','requests_per_s','p95_request_ms']}),flush=True)
    cells=[]
    raw=[reader.read_pin(pin) for pin in records]
    for workers in plan['workers']:
        for delay in plan['model_delays_s']:
            for control in plan['controls']:
                group=[r for r in raw if r['workers']==workers and r['model_delay_s']==delay and r['control']==control]
                a=[r for r in group if r['mode']=='original'];b=[r for r in group if r['mode']==control]
                throughput=statistics.median(r['requests_per_s'] for r in b)/statistics.median(r['requests_per_s'] for r in a)
                p95=statistics.median(r['p95_request_ms'] for r in b)/statistics.median(r['p95_request_ms'] for r in a)
                cells.append(dict(workers=workers,model_delay_s=delay,control=control,
                    throughput_ratio=throughput,p95_ratio=p95,
                    development_gate_pass=throughput>=.95 and p95<=1.05))
    # Ordinary instrumentation failures must not escape into valid actions.
    fault_results=[]
    for clock_kind in ['exception','nonfinite']:
        def fault():
            if clock_kind=='exception': raise OSError('injected diagnostic clock fault')
            return float('nan')
        recorder=trace.Recorder(sample_every=1,clock=fault)
        Batcher,Agent=proposed;batcher=Batcher(Agent(0.),max_wait_ms=0.,request_timeout_ms=3000.)
        with trace.capture(recorder):
            try:
                action=batcher.infer(np.zeros(11128,dtype=np.float32),0.,locked_fire=4)
                require(action==(8,4,False),'Diagnostic clock fault changed action')
            finally: batcher.stop()
        snapshot=recorder.snapshot();require(snapshot['errors']>0,'Clock fault was not counted')
        fault_results.append(dict(clock_kind=clock_kind,action=action,snapshot=snapshot))
    require('torch' not in sys.modules and not any(k in sys.modules for k in ('dqn.agent','dqn.socket_server')),
        'Forbidden production or Torch import')
    summary=dict(schema='robotron-request-phase-CPU-overhead-result-v1',plan=pin,records=records,cells=cells,
        all_cells_pass=all(c['development_gate_pass'] for c in cells),fault_results=fault_results,
        elapsed_scope='CPU NumPy tensor shim and artificial sleep only; four fixed cells, one ABBA per cell/control.',
        production_measurement=False,production_deployed=False,quality_gain_verified=False,
        learning_speed_gain_verified=False,selected_for_production=False,
        limitations=['Concurrent real training/evaluation and the bounded CPU quota can affect host timing.',
            'Two observations per role per cell do not establish statistical confidence.',
            'No GPU, MAME, replay learner, socket handler or real model kernel was measured.',
            'Passing this development gate alone cannot authorize deployment or establish speed gains.'])
    publish(output/'summary.json',summary)
    print(json.dumps(dict(status='CPU_ONLY_OVERHEAD_COMPLETE',all_cells_pass=summary['all_cells_pass'],summary=reader.pin(output/'summary.json'))),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--plan');parser.add_argument('--plan-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, imports of production modules, outputs, process control or measurement');return
    require(args.plan and args.plan_sha256,'Explicit exact plan required')
    run(args.plan,args.plan_sha256)


if __name__=='__main__': main()
