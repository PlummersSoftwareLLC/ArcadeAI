#!/usr/bin/env python3
"""Explicit bounded GPU0 smoke of reviewed agent/helper integration.

Default prints a plan. Only __new__ isolated agents are permitted: constructors,
replay/prefetch/optimizer creation, MAME and GB300 use are forbidden. Source hashes
are mandatory and must stay fixed. Run with an external 300-second timeout.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
from unittest import mock

from benchmark_cuda_graph_inference import digest,validate_plan,graph_state
from benchmark_sidecar_inference import (GAME,GPU0_UUID,Plan,canonical_uuid,
    configure_environment,require_idle_gpu,parity,timing_summary)


def validate_sources(candidate,agent_sha,helper_sha):
    helper=GAME/'Scripts/dqn/exact_inference_graphs.py'
    if not candidate.is_file() or not candidate.is_relative_to(GAME):
        raise ValueError('Candidate agent must be an existing Robotron source')
    if len(agent_sha)!=64 or len(helper_sha)!=64:
        raise ValueError('Exact reviewed agent/helper SHA256 values are required')
    if digest(candidate)!=agent_sha or digest(helper)!=helper_sha:
        raise ValueError('Candidate agent/helper source differs from reviewed hashes')
    return helper


def run(plan,refresh,candidate,agent_sha,helper_sha):
    helper=validate_sources(candidate,agent_sha,helper_sha)
    validate_plan(plan,refresh);require_idle_gpu(plan);configure_environment(plan)
    os.environ['TORCH_EXTENSIONS_DIR']=str(plan.directory/'extensions')
    os.environ['DQN_EXACT_GRAPH_BUDGET_BYTES']=str(10*(1<<30))
    plan.directory.mkdir(parents=True)
    began=time.monotonic()
    def progress(event,**fields):
        row=dict(event=event,pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-began,**fields)
        with (plan.directory/'progress.jsonl').open('a') as out:out.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    progress('start',candidate=str(candidate),agent_sha256=agent_sha,helper_sha256=helper_sha)
    try:
        sys.path.insert(0,str(GAME/'Scripts'))
        import numpy as np
        import torch
        import torch._dynamo as dynamo
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        if torch.cuda.device_count()!=1 or canonical_uuid(torch.cuda.get_device_properties(0).uuid)!=canonical_uuid(GPU0_UUID):
            raise RuntimeError('CUDA visibility is not exclusively physical GPU0')
        free,total=torch.cuda.mem_get_info()
        if free<11*(1<<30):raise RuntimeError('GPU0 lacks10GiB budget plus1GiB free margin')
        torch.cuda.set_per_process_memory_fraction((10*(1<<30))/total,0)
        name='dqn._exact_graph_smoke_candidate'
        spec=importlib.util.spec_from_file_location(name,candidate)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        if digest(candidate)!=agent_sha or digest(helper)!=helper_sha:raise RuntimeError('Reviewed source changed during import')
        checkpoints=[]
        for path in (plan.checkpoint,refresh):
            item=torch.load(path,map_location='cpu',weights_only=True)
            checkpoints.append(item['online_state_dict'])
        original,changed=checkpoints
        source=np.load(plan.states,mmap_mode='r',allow_pickle=False);array=np.array(source,copy=True)
        provenance=json.loads(plan.states.with_suffix('.json').read_text())
        if array.dtype!=np.float32 or array.shape!=(128,int(module.RL_CONFIG.state_size)) or hashlib.sha256(array.tobytes()).hexdigest()!=provenance['sha256']:
            raise ValueError('Real stacked-state sample differs from archived identity')
        real=torch.from_numpy(array);empty=torch.zeros_like(real)
        torch.backends.cuda.matmul.allow_tf32=True;torch.backends.cudnn.allow_tf32=True
        torch.set_float32_matmul_precision('high')
        def forbidden(*args,**kwargs):raise AssertionError('Forbidden full agent/replay/prefetch/optimizer construction')
        guards=[mock.patch.object(module.RainbowAgent,'__init__',new=forbidden),
            mock.patch.object(module.PrioritizedReplayBuffer,'__init__',new=forbidden),
            mock.patch.object(module.ReplayPrefetcher,'__init__',new=forbidden),
            mock.patch.object(torch.optim.Optimizer,'__init__',new=forbidden)]
        for guard in guards:guard.start()
        agent=module.RainbowAgent.__new__(module.RainbowAgent)
        agent.state_size=int(module.RL_CONFIG.state_size);agent.device=torch.device('cuda:0');agent.inference_device=agent.device
        agent.use_separate_inference=True;agent._training_lock=threading.RLock();agent._sync_lock=threading.RLock()
        agent._inference_stream=torch.cuda.Stream(device=agent.device,priority=-1);agent._sync_event=torch.cuda.Event()
        agent.online_net=module.RainbowNet(agent.state_size).to(agent.device).eval()
        agent.infer_net=module.RainbowNet(agent.state_size).to(agent.device).eval()
        agent.infer_net.load_state_dict(agent.online_net.state_dict(),strict=True)
        agent.training_enabled=False;agent.behavior_locked=False;agent.running=False;agent.memory=None;agent.optimizer=None
        agent._prefetcher=None;agent._pipeline_telemetry=None;agent._exact_inference_graphs=None
        agent._exact_graph_requested=True;agent._exact_graph_loaded=False;agent.baseline_batch_size=512
        agent.training_steps=368323;agent.optimized_samples=778166272
        agent.learner_frame_count=36632770;agent.frame_count=78718176
        agent.last_inference_sync=agent.training_steps;agent.last_inference_sync_samples=agent.optimized_samples
        clocks={key:getattr(agent,key) for key in ('training_steps','optimized_samples','learner_frame_count','frame_count')}
        agent.compiled_infer_q_joint=torch.compile(agent.infer_net.q_values_joint,dynamic=True,options={'triton.cudagraphs':False})
        compiled_identity=id(agent.compiled_infer_q_joint)
        def signature(q):return hashlib.sha256(q.detach().cpu().numpy().tobytes()).hexdigest()
        def rng():
            return dict(torch_cpu=signature(torch.get_rng_state()),torch_cuda=signature(torch.cuda.get_rng_state(0)),
                python=hashlib.sha256(repr(random.getstate()).encode()).hexdigest(),
                numpy=hashlib.sha256(repr(np.random.get_state()).encode()).hexdigest())
        startup_rng=rng()
        progress('actual_setup_start')
        graphs=agent._setup_exact_inference_graphs()
        setup_rng_unchanged=startup_rng==rng()
        progress('actual_setup_complete',snapshot=graphs.snapshot())
        # Capture precedes the real checkpoint copy, matching constructor/resume.
        startup_q=agent._run_inference(agent.compiled_infer_q_joint,real[:50],return_cpu=True)
        with agent._training_lock,torch.no_grad():agent.online_net.load_state_dict(original,strict=True)
        agent._sync_inference(force=True)
        with agent._training_lock:agent._validate_exact_inference_graphs()
        postload_rng_unchanged=startup_rng==rng()
        pointers=dict(graphs._signature)
        guard=graph_state(torch)
        rng_before=rng()
        report=dict(schema='robotron-agent-exactgraph-smoke-v1',status='complete',pid=os.getpid(),
            agent_path=str(candidate),agent_sha256=agent_sha,helper_sha256=helper_sha,
            checkpoint_sha256=digest(plan.checkpoint),refresh_sha256=digest(refresh),
            real_sample_provenance=provenance,torch=torch.__version__,cuda=torch.version.cuda,
            gpu=torch.cuda.get_device_name(0),startup_snapshot=graphs.snapshot(),clocks_before=clocks,
            setup_rng_unchanged=setup_rng_unchanged,postload_rng_unchanged=postload_rng_unchanged,
            phases={},ownership={},timings={},compile_guard=guard)
        initial_q={};retained=[]
        def phase(label):
            progress('phase_start',label=label)
            record={}
            for size in range(1,129):
                record[str(size)]={}
                for variant,data in (('real',real),('empty',empty)):
                    expected=agent._run_inference(agent.compiled_infer_q_joint,data[:size],return_cpu=True)
                    actual=agent._infer_q_joint(data[:size],return_cpu=True)
                    record[str(size)][variant]=dict(parity(expected.tolist(),actual.tolist()),
                        bit_identical=signature(expected)==signature(actual),Q_sha256=signature(actual))
                    if label=='32M' and variant=='real':
                        initial_q[size]=signature(actual);retained.append((actual,signature(actual)))
            report['phases'][label]=record
        phase('32M')
        report['loaded32M_actor_weights_match']=all(torch.equal(value.detach().cpu(),original[key]) for key,value in agent.infer_net.state_dict().items())
        report['startup_random_to_loaded32M_changes_output']=signature(startup_q)!=initial_q[50]
        with agent._training_lock,torch.no_grad():agent.online_net.load_state_dict(changed,strict=True)
        agent._sync_inference(force=True)
        with agent._training_lock:agent._validate_exact_inference_graphs()
        phase('16M_sync')
        report['synced16M_actor_weights_match']=all(torch.equal(value.detach().cpu(),changed[key]) for key,value in agent.infer_net.state_dict().items())
        online_before={key:signature(value) for key,value in agent.online_net.state_dict().items()}
        markers_before=(agent.last_inference_sync,agent.last_inference_sync_samples)
        agent.behavior_locked=True;agent.install_inference_policy(original)
        with agent._training_lock:agent._validate_exact_inference_graphs()
        report['install_preserves_online']=online_before=={key:signature(value) for key,value in agent.online_net.state_dict().items()}
        report['install_preserves_sync_markers']=markers_before==(agent.last_inference_sync,agent.last_inference_sync_samples)
        phase('32M_install_restore')
        with agent._training_lock,torch.no_grad():agent.online_net.load_state_dict(original,strict=True)
        agent.behavior_locked=False;agent._sync_inference(force=True)
        # This path must copy CPU inputs straight into a persistent graph slot;
        # calling Tensor.to(CUDA) for an intermediate input is forbidden here.
        old_to=torch.Tensor.to
        def no_cpu_to(self,*args,**kwargs):
            if not self.is_cuda:raise AssertionError('Graph route performed an intermediate CPU Tensor.to')
            return old_to(self,*args,**kwargs)
        with mock.patch.object(torch.Tensor,'to',new=no_cpu_to):
            direct=agent._infer_q_joint(real[:50],return_cpu=True)
        report['direct_CPU_to_static_copy']=signature(direct)==initial_q[50]
        order=list(range(1,129));random.Random(20261016).shuffle(order)
        diagnostics=[]
        for size in (1,32,50,64,128):
            q=agent._infer_q_joint(real[:size],return_cpu=False)
            diagnostics.append((q,signature(q)))
        for size in order:agent._infer_q_joint(real.flip(0)[:size],return_cpu=True)
        report['ownership'].update(retained_CPU_outputs=all(signature(q)==saved for q,saved in retained),
            GPU_diagnostic_outputs=all(signature(q)==saved for q,saved in diagnostics),arbitrary_order=order)
        ready=threading.Event();reuse=threading.Event();errors=[]
        def delayed():
            try:
                q=agent._infer_q_joint(real[:50],return_cpu=True);saved=signature(q);ready.set()
                if not reuse.wait(10) or signature(q)!=saved:raise RuntimeError('Delayed CPU output changed or caller blocked')
            except BaseException as error:errors.append(repr(error));ready.set()
        worker=threading.Thread(target=delayed,daemon=True);worker.start()
        if not ready.wait(10):raise RuntimeError('Serving thread did not publish')
        for size in order:agent._infer_q_joint(real.flip(0)[:size],return_cpu=True)
        reuse.set();worker.join(timeout=10)
        if worker.is_alive() or errors:raise RuntimeError(repr(errors))
        report['ownership']['serialized_two_thread_delayed_consumer']=True
        for size in (32,50,64,128):
            timed={'compiled':[],'graph':[]}
            for repeat in range(plan.repetitions):
                for route in (('compiled','graph') if repeat%2==0 else ('graph','compiled')):
                    before=time.perf_counter()
                    if route=='graph':agent._infer_q_joint(real[:size],return_cpu=True)
                    else:agent._run_inference(agent.compiled_infer_q_joint,real[:size],return_cpu=True)
                    timed[route].append((time.perf_counter()-before)*1000)
            report['timings'][str(size)]={key:timing_summary(values) for key,values in timed.items()}
        report['rng_unchanged']=rng_before==rng()
        report['clocks_unchanged']=clocks=={key:getattr(agent,key) for key in clocks}
        report['compiled_callable_unchanged']=id(agent.compiled_infer_q_joint)==compiled_identity
        with agent._sync_lock:graphs.check_storage()
        report['all_parameter_buffer_storage_preserved']=graphs._signature==pointers
        report['end_compile_guard']=graph_state(torch)
        report['validated_snapshot']=graphs.snapshot()
        report['final_online_and_infer_weights_restored']=all(torch.equal(value.detach().cpu(),original[key]) for net in (agent.online_net,agent.infer_net) for key,value in net.state_dict().items())
        # Deliberate CPU exception proves actual graph routing cannot report a
        # successful eager/compiled substitute. No CUDA error is injected.
        fallback_calls=[]
        def fallback(*args,**kwargs):fallback_calls.append(1);raise AssertionError('Unexpected fallback')
        def injected(*args,**kwargs):raise RuntimeError('deliberate graph smoke failure')
        with mock.patch.object(graphs,'replay_prepared',new=injected),mock.patch.object(graphs,'compiled',new=fallback),mock.patch.object(agent,'compiled_infer_q_joint',new=fallback),mock.patch.object(agent.infer_net,'q_values_joint',new=fallback):
            try:agent._infer_q_joint(real[:1],return_cpu=True)
            except module.ExactInferenceGraphError as error:
                report['expected_runtime_failure']=str(error)
                if 'deliberate graph smoke failure' not in str(error):
                    raise AssertionError('Injected replay failure was not reached: '+str(error)) from error
            else:raise AssertionError('Graph failure returned a successful action tensor')
        report['failure_has_no_fallback']=not fallback_calls
        report['failed_snapshot']=graphs.snapshot()
        agent._inference_stream.synchronize()
        report['constructors_forbidden_and_no_learner']=agent.memory is None and agent.optimizer is None and not any(t.name=='TrainWorker' for t in threading.enumerate())
        report['memory']=dict(peak_reserved_bytes=torch.cuda.max_memory_reserved(),peak_allocated_bytes=torch.cuda.max_memory_allocated())
        report['all_source_hashes_unchanged']=digest(candidate)==agent_sha and digest(helper)==helper_sha
        report['elapsed_s']=time.monotonic()-began
        report['acceptance']=dict(all_shapes_bit_identical=all(v['bit_identical'] for phase_records in report['phases'].values() for variants in phase_records.values() for v in variants.values()),
            all_actions_match=all(v['greedy_agreement']==v['locked_fire_agreement']==1 for phase_records in report['phases'].values() for variants in phase_records.values() for v in variants.values()),
            no_runtime_compile=guard==report['end_compile_guard'],
            all_refresh_changes_outputs=all(report['phases']['16M_sync'][str(n)]['real']['Q_sha256']!=initial_q[n] for n in range(1,129)),
            restores_all_shapes=all(report['phases']['32M_install_restore'][str(n)]['real']['Q_sha256']==initial_q[n] for n in range(1,129)),
            all_weight_copies_correct=report['loaded32M_actor_weights_match'] and report['synced16M_actor_weights_match'] and report['final_online_and_infer_weights_restored'],
            startup_real_load_takes_effect=report['startup_random_to_loaded32M_changes_output'],
            startup_rng_preserved=report['setup_rng_unchanged'] and report['postload_rng_unchanged'],
            ownership_preserved=all(report['ownership'][key] for key in ('retained_CPU_outputs','GPU_diagnostic_outputs','serialized_two_thread_delayed_consumer')),
            clocks_rng_storage_callable_preserved=all(report[key] for key in ('rng_unchanged','clocks_unchanged','compiled_callable_unchanged','all_parameter_buffer_storage_preserved','install_preserves_online','install_preserves_sync_markers')),
            direct_copy_no_fallback=report['direct_CPU_to_static_copy'] and report['failure_has_no_fallback'],
            all_sources_frozen=report['all_source_hashes_unchanged'])
        report['limitation']='IsolatedGPU0 __new__ wiring smoke only. No replay/optimizer/learner exists; producer lifecycle remains source/CPU review. No GB300 or live enable authorized.'
        require_idle_gpu(plan)
        (plan.directory/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        for guard in reversed(guards):guard.stop()
        progress('complete',acceptance=report['acceptance'])
        return report
    except BaseException as error:
        (plan.directory/'failure.json').write_text(json.dumps(dict(error=repr(error),utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-began))+'\n')
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--candidate-agent',type=Path,required=True)
    parser.add_argument('--agent-sha',required=True)
    parser.add_argument('--helper-sha',required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args(argv)
    plan=Plan((GAME/'models_dqn/managed-incumbents/fresh3-32M-confirmed.pt').resolve(),args.directory.resolve(),
        states=(GAME/'logs/managed-learning-20261015/run-05/sidecar-compile-inputs/bank-states-128.npy').resolve())
    refresh=(GAME/'models_dqn/managed-incumbents/fresh3-16M-confirmed.pt').resolve()
    candidate=args.candidate_agent.resolve()
    validate_plan(plan,refresh);validate_sources(candidate,args.agent_sha,args.helper_sha)
    if args.execute:run(plan,refresh,candidate,args.agent_sha,args.helper_sha)
    else:print(json.dumps(dict(mode='plan_only',gpu=GPU0_UUID,CPU_threads=2,external_timeout_s=300,constructor='RainbowAgent.__new__ only',candidate=str(candidate),output=str(plan.directory)),indent=2))


if __name__=='__main__':main()
