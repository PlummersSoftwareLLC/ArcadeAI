"""CPU-only same-architecture stationary policy for finite MAME engineering.

Never loads or changes the learner. A new separately identified checkpoint
emits greedy joint action80 (neutral movement and fire), so real games can end
naturally while testing startup, full-game selection and per-slot retirement.
This checkpoint must never be selected for learning quality or promotion.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not os.environ.get('LD_PRELOAD')
    assert hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256
    job=json.loads(args.job.read_text());assert job['engineering_only']is True and job['joint_action']==80
    h=load('_idle_engineering_policy_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h.checked(job['runtime']);parent=h.checked(job['parent_checkpoint'])
    root,package_pins=h.package_inputs(job['source_package']);sys.path.insert(0,str(root/'Scripts'))
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):
        os.environ[key]='2'
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    from dqn.model import RainbowNet,NUM_JOINT,NUM_FIRE,action_index_to_wire_dir
    from dqn.inference_actor import InferenceActor
    assert NUM_JOINT==81 and NUM_FIRE==9 and action_index_to_wire_dir(8)==-1
    saved=torch.load(parent,map_location='cpu',mmap=True,weights_only=False)
    assert saved['state_size']==11128
    model=RainbowNet(saved['state_size']).cpu().eval()
    loaded=model.load_state_dict(saved['online_state_dict'],strict=False)
    assert not loaded.unexpected_keys and set(loaded.missing_keys)<={'support'}
    shapes={k:list(v.shape)for k,v in model.state_dict().items()}
    assert model.use_dist and model.use_dueling and model.use_action_context
    parameters=len(list(model.parameters()))
    # Optimizer state only covers parameters that have received updates. The
    # complete model shape/key contract, rather than that count, binds scope.
    parent_shapes={k:list(v.shape)for k,v in saved['online_state_dict'].items()}
    assert set(parent_shapes)<=set(shapes)and set(shapes)-set(parent_shapes)<={'support'}
    assert all(shapes[k]==v for k,v in parent_shapes.items())
    with torch.no_grad():
        for parameter in model.parameters():parameter.zero_()
        embedding=model.joint_action_embedding
        embedding.weight[80,0]=1
        scorer=model.joint_adv_scorer
        assert len(scorer)==4 and isinstance(scorer[0],torch.nn.Linear)
        assert isinstance(scorer[1],torch.nn.LayerNorm)and isinstance(scorer[3],torch.nn.Linear)
        scorer[0].weight[0,-embedding.embedding_dim]=1
        scorer[1].weight.fill_(1)
        scorer[3].weight[-1,0]=10
    assert {k:list(v.shape)for k,v in model.state_dict().items()}==shapes
    checks=[];generator=torch.Generator().manual_seed(20261101)
    with torch.inference_mode():
        for batch in range(1,17):
            for kind in ('zero','uniform'):
                x=torch.zeros(batch,saved['state_size'])if kind=='zero'else torch.rand(batch,saved['state_size'],generator=generator)
                q=model.q_values_joint(x)
                assert q.shape==(batch,81)and bool(torch.isfinite(q).all())and bool((q.argmax(1)==80).all())
                margin=float((q[:,80]-q[:,:80].max(1).values).min())
                assert margin>1
                checks.append(dict(batch=batch,fixture=kind,joint_action=80,minimum_Q_margin=margin))
    state={k:v.detach().cpu().clone()for k,v in model.state_dict().items()}
    saved['online_state_dict']=state
    saved['target_state_dict']={k:v.clone()for k,v in state.items()}
    saved['engineering_only_policy']=dict(schema='robotron-idle-action80-engineering-policy-v1',joint_action=80,
        movement_index=8,fire_index=8,wire_movement=-1,wire_fire=-1,parent_checkpoint=job['parent_checkpoint'],
        inherited_clocks_are_synthetic_engineering_labels=True,quality_or_training_or_promotion_use_forbidden=True)
    target=Path(job['checkpoint_output']);assert target.is_absolute()and not target.exists()
    assert target.parent==args.job.parent and target.name=='idle-engineering-only.pt'
    with target.open('xb')as stream:
        torch.save(saved,stream);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o444)
    checkpoint=h.pin(target);assert checkpoint['sha256']!=job['parent_checkpoint']['sha256']
    actor=InferenceActor(target,device='cpu',inference_backend='eager')
    assert actor.memory is actor.optimizer is None
    actual=[]
    try:
        for batch in range(1,17):
            states=torch.rand(batch,saved['state_size'],generator=generator).numpy()
            actions=actor.act_batch(states,[0.0]*batch)
            assert actions==[(8,8,False)]*batch
            actual.append(dict(batch=batch,greedy_loaded_actions=[[int(m),int(f),bool(a)]for m,f,a in actions]))
    finally:actor.close()
    assert not torch.cuda.is_initialized()
    h.checked(job['parent_checkpoint'])
    for pin in package_pins:h.checked(pin)
    report=h.put(Path(job['report']),dict(status='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY',original_job=h.pin(args.job),
        checkpoint=checkpoint,parent_checkpoint=job['parent_checkpoint'],source_package=job['source_package'],
        model_shapes_unchanged=True,parameters=parameters,
        inherited_optimizer_state_entries=len(saved['optimizer_state_dict']['state']),
        complete_parent_tensor_shapes=parent_shapes,joint_action=80,wire_directions=[-1,-1],
        direct_model_checks=checks,loaded_InferenceActor_checks=actual,
        clocks={k:saved[k]for k in ('training_steps','learner_frame_count','optimized_samples','frame_count')},
        inherited_clocks_are_synthetic_engineering_labels=True,CUDA_initialized=False,
        numerical_thread_environment={k:os.environ[k]for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')},
        torch_threads=torch.get_num_threads(),torch_interop_threads=torch.get_num_interop_threads(),
        learner_or_protected_policy_or_selected_candidate_changed=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY',report=report,checkpoint=checkpoint)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
