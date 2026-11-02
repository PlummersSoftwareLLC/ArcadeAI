"""Resume the latest tagged Robotron checkpoint after an ordinary process/host restart.

Verifies the CPU model, Adam state and persisted priority phase before GPU startup.
Creates a content-addressed immutable resume record for these exact saved bytes.
Does not change model weights, training controls or replay contents.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def immutable(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    if path.exists():
        assert path.read_bytes()==raw and path.stat().st_mode&0o777==0o444
    else:
        with path.open('xb')as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    assert path.resolve(strict=True)==path and not path.is_symlink()and path.stat().st_nlink==1
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))

def prepare(checkpoint,records,report=None):
    import torch
    import numpy as np
    torch.set_num_threads(2)
    before=checkpoint.stat();sha=digest(checkpoint)
    saved=torch.load(checkpoint,map_location='cpu',weights_only=False,mmap=True)
    assert saved['state_size']==11128
    phase=saved['priority_metric_phase']
    assert phase['schema']=='robotron-priority-metric-phase-v1'and phase['metric']=='ce'and phase['valid']is True
    assert re.fullmatch('[0-9a-f]{64}',phase['root_precommit_sha256'])
    sys.path.insert(0,str(G/'Scripts'))
    from dqn.config import RL_CONFIG
    from dqn.model import RainbowNet
    assert RL_CONFIG.batch_size==4096 and RL_CONFIG.n_step==3 and RL_CONFIG.max_samples_per_frame==12
    model=RainbowNet(saved['state_size'])
    summaries={}
    for key in ['online_state_dict','target_state_dict']:
        sd=saved[key]
        assert sd and all(torch.isfinite(t).all().item()for t in sd.values()if torch.is_floating_point(t))
        loaded=model.load_state_dict(sd,strict=False)
        assert not loaded.unexpected_keys and set(loaded.missing_keys)<={'support'}
        summaries[key]=dict(tensors=len(sd),elements=sum(t.numel()for t in sd.values()),strict_cpu_shape_load=True)
    optimizer=torch.optim.Adam(model.parameters(),lr=1e-5)
    optimizer.load_state_dict(saved['optimizer_state_dict'])
    assert optimizer.state
    steps=[]
    for parameter,state in optimizer.state.items():
        assert state['exp_avg'].shape==parameter.shape==state['exp_avg_sq'].shape
        assert torch.isfinite(state['exp_avg']).all().item()and torch.isfinite(state['exp_avg_sq']).all().item()
        step=state['step'].item()if torch.is_tensor(state['step'])else state['step']
        assert step>0;steps.append(step)
    records.mkdir(mode=0o700,parents=True,exist_ok=True)
    original=G/'models_dqn/robotron_dqn_latest.pt'
    assert digest(original)==sha
    spec=dict(schema='robotron-priority-metric-start-v1',phase_id=phase['phase_id'],metric='ce',action='resume',previous_metric='ce',checkpoint=dict(path=str(original),sha256=sha,bytes=before.st_size),model_dir=str(G/'models_dqn'),root_precommit_sha256=phase['root_precommit_sha256'])
    pin=immutable(records/('resume-'+sha+'.json'),spec)
    os.environ['DQN_PRIORITY_PHASE_RECORD']=pin['path'];os.environ['DQN_PRIORITY_PHASE_RECORD_SHA256']=pin['sha256']
    from dqn.priority_phase import PriorityPhase,require_checkpoint_phase
    actual=PriorityPhase('ce',str(original),str(G/'models_dqn'))
    require_checkpoint_phase(saved,'ce',actual);actual.before_load(str(original),saved);actual.finish_load(str(original));actual.require_ready('ce')
    assert actual.snapshot()['priority_update_calls']==phase['priority_update_calls']
    assert not torch.cuda.is_initialized()
    after=checkpoint.stat();assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
    meta=Path('/dev/shm/robotron_dqn_latest_replay/_meta.npy')
    replay=None if not meta.exists()else np.load(meta,allow_pickle=False).tolist()
    control=json.loads((G/'models_dqn/learning_control.json').read_bytes())
    result=dict(schema='robotron-power-recovery-checkpoint-CPU-verification-v1',checkpoint=spec['checkpoint'],resume_record=pin,phase_id=phase['phase_id'],priority_phase_preserved=True,saved_clocks={k:saved[k]for k in ['training_steps','optimized_samples','learner_frame_count','frame_count']},model=summaries,Adam_state_parameters=len(optimizer.state),Adam_step_min=min(steps),Adam_step_max=max(steps),saved_optimizer_lrs=[p['lr']for p in optimizer.param_groups],selected_lr_scale=control['lr_scale'],replay_meta=replay,CUDA_initialized=False,created_unix_s=time.time())
    result.update(prospective_cap=12,cap_changed_only_via_new_process_environment=True,
        rng_state_preserved_by_existing_checkpoint=False,full_rng_continuity_verified=False,
        full_replay_and_bank_integrity_verified_by_this_launcher=False,
        exact_full_state_continuity_qualified=False,learning_benefit_qualified=False)
    if report:immutable(report,result)
    print(json.dumps(result),flush=True)
    return pin

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--resume-cap12',action='store_true')
    parser.add_argument('--expected-source-sha256')
    parser.add_argument('--checkpoint',type=Path,default=G/'models_dqn/robotron_dqn_latest.pt')
    parser.add_argument('--records',type=Path,default=G/'models_dqn/resume-records')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if not(args.verify_only or args.resume_cap12):
        print('SOURCE_ONLY: no checkpoint, replay, CPU verification or trainer action');return
    assert args.verify_only != args.resume_cap12
    assert digest(Path(__file__).resolve())==args.expected_source_sha256
    assert os.environ.get('DQN_MAX_SAMPLES_PER_FRAME')=='12'
    assert os.environ.get('DQN_PRIORITY_METRIC','').strip().lower()=='ce'
    env=dict(os.environ)
    os.environ['CUDA_VISIBLE_DEVICES']=''
    pin=prepare(args.checkpoint.resolve(strict=True),args.records.resolve(),args.report)
    if args.verify_only:return
    env.update(DQN_PRIORITY_PHASE_RECORD=pin['path'],DQN_PRIORITY_PHASE_RECORD_SHA256=pin['sha256'],DQN_EXACT_GRAPH_CHECKPOINT=str(G/'models_dqn/robotron_dqn_latest.pt'))
    os.chdir(G)
    os.execvpe(sys.executable,[sys.executable,'-Xgil=0','Scripts/run_dqn.py'],env)

if __name__=='__main__':main()
