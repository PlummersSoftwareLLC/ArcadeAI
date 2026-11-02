"""Inert-by-default CPU overhead screen for the complete matched trace prototype.

Selected exact methods, CPU replay arrays, an index tree and a tensor shim.
No complete production module, real bank, Torch, GPU, MAME or socket workload.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import gc
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import sys
import threading
import time
import types

H=Path(__file__).resolve().parent;G=H.parents[1]
READER=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'


def require(ok,message):
    if not ok:raise ValueError(message)


def publish(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,separators=(',',':'),allow_nan=False)
        stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())


def fixture(reader,plan,*,proposed):
    # Separate module/class instances matter: each CPU Memory constructor
    # closes over its own Tests.Exposure class. Never overwrite that class to
    # switch modes in a shared fixture, which would contaminate the baseline.
    module=reader.checked_module('_matched_overhead_fixture_'+('proposed' if proposed else 'original'),plan['fixture'])
    if not proposed:
        originals={name:reader.read_pin(pin,as_json=False).decode() for name,pin in plan['sources'].items()}
        target=module.original if hasattr(module,'original') else module
        target.setup_sources=lambda:(originals,dict(socket_server=originals['socket_server.py'],
            agent=originals['agent.py'],exposure=originals['learning_exposure.py']))
    module.Tests.setUpClass()
    cls=module.Tests
    methods=[cls.Agent.act_batch,cls.classes['AsyncReplayBuffer']._consume,cls.Exposure.accepted]
    require(all(('_request_trace' in fn.__code__.co_names)==proposed for fn in methods),
        'Original/proposed fixture source scopes are mixed')
    return cls


def partition_analysis(snapshot,analyzer):
    rows=[]
    for frame in snapshot['frames']:
        for request in frame['inference']:
            rows.append(dict(request_id=len(rows),events=[[phase,stamp] for phase,stamp,metadata in request['events']]))
    return analyzer.analyze(dict(schema='robotron-host-request-phases-v1',clock='perf_counter_ns',
        sample_every=1,max_requests=4096,seen=len(rows),capacity_drops=0,event_drops=0,errors=0,rows=rows))


def cpu_stat():
    before=time.perf_counter_ns()
    lines=Path('/proc/self/cgroup').read_text().splitlines()
    unified=[line.split(':',2)[2] for line in lines if line.startswith('0::')]
    require(len(unified)==1,'One original unified CPU cgroup required')
    path=Path('/sys/fs/cgroup')/unified[0].lstrip('/')/'cpu.stat'
    raw=path.read_text();after=time.perf_counter_ns()
    fields={key:int(value) for key,value in (line.split() for line in raw.splitlines())}
    return dict(cgroup=unified[0],path=str(path),started_monotonic_ns=before,
        ended_monotonic_ns=after,raw=raw,fields=fields)


def block_run(block,baseline,proposed,trace,analyzer,plan):
    mode=block['mode'];cls=baseline if mode=='original' else proposed
    np=cls.np;workers=block['workers'];dimension=block['state_dimension']
    agent=cls.Agent()
    if dimension!=4:
        # Preserve the exact extracted ring.add implementation while sizing
        # these isolated CPU arrays to the real stacked state width.
        agent.memory.states=np.zeros((1024,dimension),dtype=np.float32)
        agent.memory.next_states=np.zeros((1024,dimension),dtype=np.float32)
    delay=block['model_delay_s']
    original_model=agent._infer_q_joint
    if delay:
        def delayed(self,states,return_cpu):
            time.sleep(delay);return original_model(states,return_cpu=return_cpu)
        agent._infer_q_joint=types.MethodType(delayed,agent)
    replay=cls.classes['AsyncReplayBuffer'](agent,batch_size=100,max_queue_size=64000)
    batcher=cls.classes['AsyncInferenceBatcher'](agent,max_batch_size=128,max_wait_ms=1.,request_timeout_ms=3000.)
    states=[np.full(dimension,slot/32.,dtype=np.float32) for slot in range(workers)]
    latencies=[[] for _ in range(workers)];failures=[]
    recorder=trace.Recorder(max_frames=2048,sample_every=128)
    def request(slot,turn,connection):
        epsilon=1. if (slot+turn)%10==0 else 0.
        fire=(slot+turn)%9
        expected=(2 if epsilon else 8,fire,bool(epsilon))
        started=time.perf_counter_ns()
        with trace.frame(connection) if mode!='original' else nullcontext():
            if mode!='original':
                trace.frame_mark('payload_complete');trace.frame_mark('parse_begin')
                trace.frame_mark('parse_end');trace.frame_mark('accepted_frame')
            replay.step_async(states[slot],(1,2),.25,states[slot],False,
                client_id=slot,actor='epsilon' if epsilon else 'dqn',horizon=3)
            if mode!='original':trace.frame_mark('inference_wait_begin')
            action=batcher.infer(states[slot],epsilon,locked_fire=fire)
            if mode!='original':
                trace.frame_mark('inference_wait_end');trace.frame_mark('action_write_completed')
        elapsed=time.perf_counter_ns()-started
        require(action==expected,'CPU shim action changed')
        return elapsed
    start_ns=end_ns=None
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            connections=[trace.connection(slot,slot) for slot in range(workers)]
            barrier=threading.Barrier(workers)
            def warm(slot):
                barrier.wait(timeout=5)
                for turn in range(8):request(slot,turn,connections[slot])
            for future in [pool.submit(warm,slot) for slot in range(workers)]:future.result(timeout=15)
            require(replay.barrier_async().wait(5),'Warm replay barrier did not finish')
            before=agent.memory._insert_exposure.snapshot()['accepted_total']
            barrier=threading.Barrier(workers+1)
            def measured(slot):
                barrier.wait(timeout=5)
                for turn in range(plan['requests_per_worker']):
                    try:latencies[slot].append(request(slot,turn,connections[slot]))
                    except Exception as error:failures.append(dict(slot=slot,turn=turn,error=repr(error)))
            with trace.capture(recorder) if mode=='sparse128' else nullcontext():
                futures=[pool.submit(measured,slot) for slot in range(workers)]
                cpu_before=cpu_stat()
                start_ns=time.perf_counter_ns();barrier.wait(timeout=5)
                for future in futures:future.result(timeout=25)
                require(replay.barrier_async().wait(5),'Measured replay barrier did not finish')
                end_ns=time.perf_counter_ns()
                cpu_after=cpu_stat()
            accepted=agent.memory._insert_exposure.snapshot()['accepted_total']-before
    finally:
        batcher.stop();replay.stop()
    values=[n for row in latencies for n in row]
    require(not failures and len(values)==workers*plan['requests_per_worker']==accepted,'Incomplete requests or replay insertion')
    def percentile(q):return sorted(values)[math.ceil(len(values)*q)-1]/1e6
    result=dict(**block,started_monotonic_ns=start_ns,ended_monotonic_ns=end_ns,
        elapsed_ns=end_ns-start_ns,completed=len(values),accepted_ring_adds=accepted,
        delivered_requests_per_s=accepted/((end_ns-start_ns)/1e9),
        p50_request_ms=percentile(.5),p95_request_ms=percentile(.95),p99_request_ms=percentile(.99),
        mean_request_ms=statistics.mean(values)/1e6,raw_request_ns=latencies,failures=failures,
        cpu_resource_before=cpu_before,cpu_resource_after=cpu_after)
    if mode=='sparse128':
        snapshot=recorder.snapshot();report=trace.validate_snapshot(snapshot)
        require(report['pending_routes']==report['incomplete_admitted_commands']==report['incomplete_handler_scopes']==0,'Censored matched trace')
        require(not any(report['capture_loss'].values()) and report['unmatched_inference']==0,'Matched trace loss')
        require(report['sampled_frames']==report['replay_commands']==report['accepted_ring_add_events']==report['inference_requests'],
            'One-frame/inference/insert linkage differs')
        partitions=partition_analysis(snapshot,analyzer)
        require(partitions['outcomes']=={'returned':report['sampled_frames']} and not any(partitions['partition_residual_ns']),
            'Matched inference partition differs')
        result.update(trace=snapshot,trace_analysis=report,inference_partition_analysis=partitions)
    return result


def run(plan_path,expected_sha256):
    require(hashlib.sha256(READER.read_bytes()).hexdigest()==READER_SHA,'Immutable reader changed')
    spec=importlib.util.spec_from_file_location('_matched_overhead_reader',READER)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    pin=reader.pin(plan_path);require(pin['sha256']==expected_sha256,'Exact precommitted plan required');plan=reader.read_pin(pin)
    require(plan['schema']=='robotron-matched-trace-CPU-overhead-plan-v2' and plan['requests_per_worker']==96,'Exact bounded CPU plan required')
    require(plan['workers']==[8,32] and plan['model_delays_s']==[0.,.0008] and plan['state_dimensions']==[4,11128]
        and plan['controls']==['disabled','sparse128'],'Exact eight workloads and controls required')
    require(plan['max_throughput_loss']==plan['max_p95_increase']==.05,'Prospective per-cell gate changed')
    require(reader.pin(__file__)==plan['runner'],'Runner changed')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','Explicit CPU isolation required')
    trace=reader.checked_module('matched_frame_trace_v2',plan['trace'])
    reader.checked_module('prepare_matched_trace_sources_v2',plan['builder'])
    analyzer=reader.checked_module('_matched_overhead_old_analyzer',plan['inference_analyzer'])
    baseline=fixture(reader,plan,proposed=False);proposed=fixture(reader,plan,proposed=True)
    output=Path(plan['output']);output.mkdir(mode=0o700);records=[]
    for dimension in plan['state_dimensions']:
        for workers in plan['workers']:
            for delay in plan['model_delays_s']:
                for control in plan['controls']:
                    for position,mode in enumerate(['original',control,control,'original']):
                        block=dict(index=len(records),state_dimension=dimension,workers=workers,
                            model_delay_s=delay,control=control,position=position,mode=mode)
                        result=block_run(block,baseline,proposed,trace,analyzer,plan)
                        path=output/('block-%02d.json'%len(records));publish(path,result);records.append(reader.pin(path))
                        print(json.dumps({k:result[k] for k in ['index','state_dimension','workers','model_delay_s','mode','completed','delivered_requests_per_s','p95_request_ms']}),flush=True)
                        gc.collect()
    raw=[reader.read_pin(pin) for pin in records];cells=[]
    for dimension in plan['state_dimensions']:
        for workers in plan['workers']:
            for delay in plan['model_delays_s']:
                for control in plan['controls']:
                    group=[row for row in raw if row['state_dimension']==dimension and row['workers']==workers
                        and row['model_delay_s']==delay and row['control']==control]
                    a=[row for row in group if row['mode']=='original'];b=[row for row in group if row['mode']==control]
                    throughput=statistics.median(row['delivered_requests_per_s'] for row in b)/statistics.median(row['delivered_requests_per_s'] for row in a)
                    p95=statistics.median(row['p95_request_ms'] for row in b)/statistics.median(row['p95_request_ms'] for row in a)
                    cells.append(dict(state_dimension=dimension,workers=workers,model_delay_s=delay,control=control,
                        throughput_ratio=throughput,p95_ratio=p95,development_gate_pass=throughput>=.95 and p95<=1.05))
    require('torch' not in sys.modules and not any(n in sys.modules for n in ('dqn.agent','dqn.socket_server','dqn.replay_buffer')),
        'Forbidden complete production or Torch import')
    summary=dict(schema='robotron-matched-trace-CPU-overhead-result-v2',plan=pin,records=records,cells=cells,
        all_cells_pass=all(row['development_gate_pass'] for row in cells),
        production_deployed=False,selected_for_production=False,quality_gain_verified=False,learning_speed_gain_verified=False,
        limitations=['CPU workflow simulation under a 200% quota while actual training and evaluation run.',
            'One emitted replay transition per frame; no actual socket parsing, n-step flush, HOF/elite or model GPU workload.',
            'Float32 CPU replay arrays with a synthetic index tree and tensor shim.',
            'Two observations per role per cell; no statistical confidence or live speed claim.',
            'Passing a development gate cannot establish integration readiness or authorize deployment.'])
    publish(output/'summary.json',summary)
    print(json.dumps(dict(status='MATCHED_CPU_OVERHEAD_V2_ORIGINAL_COMPLETE',all_cells_pass=summary['all_cells_pass'],summary=reader.pin(output/'summary.json'))),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--plan');parser.add_argument('--plan-sha256');args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no plan/source reads, payload, outputs, threads, production imports or process controls');return
    require(args.plan and args.plan_sha256,'Exact explicit plan required');run(args.plan,args.plan_sha256)


if __name__=='__main__':main()
