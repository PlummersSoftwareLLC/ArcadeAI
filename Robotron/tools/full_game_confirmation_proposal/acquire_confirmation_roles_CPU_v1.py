"""Fresh CPU-only immutable reference/candidate acquisition for full games.

No learner, replay or GPU is constructed. Preserve exact selected policy bytes
and saved clocks, validate full online/target/Adam payload finiteness, and run
the frozen profile06 InferenceActor on every supported batch size. Raw Adam
step saturation is reported separately from logical checkpoint clocks.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''and not os.environ.get('LD_PRELOAD')
    assert hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256
    job=json.loads(args.job.read_text());assert list(job['roles'])==['reference','candidate']
    h=load('_confirmation_CPU_role_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h.checked(job['runtime']);root,pins=h.package_inputs(job['source_package']);sys.path.insert(0,str(root/'Scripts'))
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='2'
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    from dqn.model import RainbowNet
    from dqn.inference_actor import InferenceActor
    reports={};generator=torch.Generator().manual_seed(20261101)
    for role,selected in job['roles'].items():
        parent=h.checked(selected['checkpoint']);directory=Path(job['output'])/role
        directory.mkdir(mode=0o700);target=directory/'frozen-policy.pt'
        with parent.open('rb')as src,target.open('xb')as dst:
            shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno());os.fchmod(dst.fileno(),0o444)
        copied=h.pin(target);assert copied['sha256']==selected['checkpoint']['sha256']
        saved=torch.load(target,map_location='cpu',mmap=True,weights_only=False)
        assert not saved.get('engineering_only_policy')and saved['state_size']==11128
        clocks={k:saved[k]for k in ('training_steps','learner_frame_count','optimized_samples','frame_count')}
        assert clocks==selected['expected_clocks']and all(type(v)is int and v>=0 for v in clocks.values())
        assert type(saved['measurement_frame_count'])is int and saved['measurement_frame_count']>=0
        model=RainbowNet(saved['state_size']).cpu().eval();schema={k:(list(v.shape),str(v.dtype))for k,v in model.state_dict().items()}
        for key in ('online_state_dict','target_state_dict'):
            state=saved[key]
            assert all(bool(torch.isfinite(t).all())for t in state.values()if torch.is_floating_point(t))
            loaded=model.load_state_dict(state,strict=False)
            assert not loaded.unexpected_keys and set(loaded.missing_keys)<={'support'}
        optimizer=saved['optimizer_state_dict'];steps=[]
        for state in optimizer['state'].values():
            assert all(bool(torch.isfinite(v).all())for v in state.values()if torch.is_tensor(v)and torch.is_floating_point(v))
            step=state['step'];assert torch.is_tensor(step)and step.ndim==0 and float(step)>=0;steps.append(float(step))
            assert state['exp_avg'].shape==state['exp_avg_sq'].shape
        assert len(steps)>0 and all(type(group['lr'])in(int,float)for group in optimizer['param_groups'])
        actor=InferenceActor(target,device='cpu',inference_backend='eager');checks=[]
        try:
            assert actor.memory is actor.optimizer is None
            assert {k:actor.checkpoint_metadata[k]for k in clocks}==clocks
            with torch.inference_mode():
                for batch in range(1,17):
                    states=torch.rand(batch,saved['state_size'],generator=generator)
                    q=actor._infer_q_joint(states,return_cpu=True)
                    assert q.shape==(batch,81)and bool(torch.isfinite(q).all())
                    actions=actor.act_batch(states.numpy(),[0.0]*batch)
                    assert len(actions)==batch and all(0<=m<9 and 0<=f<9 and a is False for m,f,a in actions)
                    assert [m*9+f for m,f,a in actions]==q.argmax(1).tolist()
                    checks.append(dict(batch=batch,q_min=float(q.min()),q_max=float(q.max()),all_greedy_actions_match=True))
        finally:actor.close()
        assert not torch.cuda.is_initialized();h.checked(selected['checkpoint'])
        reports[role]=dict(status='PASS_FRESH_CPU_ROLE_POLICY_AND_INFERENCE',source_checkpoint=selected['checkpoint'],checkpoint=copied,
            original_policy_authority=selected['authority'],clocks=clocks,measurement_frame_count=saved['measurement_frame_count'],
            state_size=saved['state_size'],model_parameters=len(list(model.parameters())),model_schema=schema,
            online_target_and_initialized_Adam_payloads_finite=True,optimizer_initialized_states=len(steps),
            raw_Adam_step_min=min(steps),raw_Adam_step_max=max(steps),raw_Adam_float32_saturation_reported=min(steps)==max(steps)==16777216,
            inherited_optimizer_learning_rates=[group['lr']for group in optimizer['param_groups']],CPU_batch_checks=checks,
            CPU_only=True,CUDA_initialized=False,engineering_policy_rejected=True,quality_qualified=False,promotion=False)
        h.put(directory/'CPU-policy-readback.json',reports[role])
        del actor,model,saved,optimizer,state;gc.collect()
    for pin in pins:h.checked(pin)
    result=h.put(Path(job['report']),dict(status='PASS_FRESH_REFERENCE_AND_CANDIDATE_CPU_ACQUISITION',original_job=h.pin(args.job),
        roles=reports,source_package=job['source_package'],same_frozen_schema=reports['reference']['model_schema']==reports['candidate']['model_schema'],
        no_prior_scores_used_as_fresh_reference=True,all_original_policy_bytes_preserved=True,
        CUDA_initialized=False,Main_or_replay_or_protected_or_selected_policy_modified=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS_FRESH_REFERENCE_AND_CANDIDATE_CPU_ACQUISITION',report=result,
        policies={k:v['checkpoint']['sha256']for k,v in reports.items()})),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
