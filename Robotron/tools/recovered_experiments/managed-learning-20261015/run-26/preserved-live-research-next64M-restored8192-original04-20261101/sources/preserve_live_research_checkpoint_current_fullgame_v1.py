"""Preserve one stable autosave generation during a long frozen comparison.

CPU only; never selects/restores a policy or constructs replay/inference actors.
The live writer uses atomic rename. An open original file descriptor therefore
retains its generation even if the latest pathname advances during acquisition.
This is not an exact-dose endpoint or a full-replay recovery snapshot.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def born(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def acquire(job,h):
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''and not os.environ.get('LD_PRELOAD')
    assert born(job['main_owner']['pid'])==job['main_owner']['birth']
    pair=json.loads(h.checked(job['active_fixed_pair']).read_text())
    assert pair['schema']=='robotron-protectedb231-vs-postreboot1c-fullgame-fixed-pair-v1'
    assert job['active_fixed_pair']['sha256']=='2a8408a7608bd56cda6b8497e0227c083c323b4a5ed45f11939ba2a1626d1983'
    assert pair['ordered_legs']==['R1','C1','R2','C2']
    assert pair['roles']['reference']['policy']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
    assert pair['roles']['candidate']['policy']['sha256']=='77f9f42fbdd67c0d5081229710140931422292d83ee437cc08de64c188fe7228'
    baseline=json.loads(h.checked(job['previous_preservation_report']).read_text())
    assert baseline['status']=='PASS_CPU_PRESERVED_UNQUALIFIED_RESEARCH_CHECKPOINT'
    base=baseline['saved_clocks']
    assert job['minimum_saved_learner_frames']==base['learner_frame_count']+64_000_000
    props=dict(x.split('=',1)for x in subprocess.check_output(['systemctl','--user','show','robotron-trainer.service'],text=True,timeout=10).splitlines()if'='in x)
    assert props['MainPID']==str(job['main_owner']['pid']) and props['InvocationID']==job['main_owner']['invocation_id']
    assert job['minimum_additional_learner_frames']==64_000_000
    root,pins=h.package_inputs(job['source_package']);source=Path(job['source_checkpoint'])
    assert source==G/'models_dqn/robotron_dqn_latest.pt'
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    probe=source.stat();probe_identity=(probe.st_dev,probe.st_ino,probe.st_size,probe.st_mtime_ns)
    header=torch.load(source,map_location='cpu',mmap=True,weights_only=False)
    assert header['learner_frame_count']>=job['minimum_saved_learner_frames'], 'Published generation below milestone; no copy made'
    current_probe=source.stat();assert (current_probe.st_dev,current_probe.st_ino,current_probe.st_size,current_probe.st_mtime_ns)==probe_identity
    del header
    output=Path(job['output']);assert not output.exists();output.mkdir(mode=0o700)
    target=output/'preserved-unqualified-policy.pt';digest=hashlib.sha256()
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as incoming,target.open('xb')as outgoing:
        before=os.fstat(incoming.fileno())
        assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==probe_identity
        assert stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_uid==os.geteuid()
        while True:
            chunk=incoming.read(8<<20)
            if not chunk:break
            digest.update(chunk);outgoing.write(chunk)
        after=os.fstat(incoming.fileno())
        assert(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
        outgoing.flush();os.fsync(outgoing.fileno());os.fchmod(outgoing.fileno(),0o444)
    parent_fd=os.open(output,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(parent_fd)
    finally:os.close(parent_fd)
    copied=h.pin(target);assert copied['bytes']==before.st_size and copied['sha256']==digest.hexdigest()
    current=source.stat();same_generation=(current.st_dev,current.st_ino)==(before.st_dev,before.st_ino)
    sys.path.insert(0,str(root/'Scripts'))
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='2'
    import torch
    from dqn.model import RainbowNet
    saved=torch.load(target,map_location='cpu',mmap=True,weights_only=False)
    assert saved['state_size']==11128 and not saved.get('engineering_only_policy')
    clocks={k:saved[k]for k in ('training_steps','learner_frame_count','optimized_samples','frame_count')}
    assert all(type(v)is int and v>base[k]for k,v in clocks.items())
    deltas={k:v-base[k]for k,v in clocks.items()}
    assert deltas['learner_frame_count']>=job['minimum_additional_learner_frames']
    assert clocks['learner_frame_count']>=job['minimum_saved_learner_frames']
    assert type(saved['measurement_frame_count'])is int and saved['measurement_frame_count']>=0
    model=RainbowNet(saved['state_size']).cpu();schema={};states={}
    for name in ('online_state_dict','target_state_dict'):
        values=saved[name];assert values
        assert all(bool(torch.isfinite(t).all())for t in values.values()if torch.is_tensor(t)and torch.is_floating_point(t))
        loaded=model.load_state_dict(values,strict=False)
        assert not loaded.unexpected_keys and set(loaded.missing_keys)<={'support'}
        states[name]=dict(tensors=len(values),elements=sum(t.numel()for t in values.values()),finite_and_CPU_shape_load=True)
    assert len(list(model.parameters()))==99
    optimizer=torch.optim.Adam(model.parameters(),lr=1e-5);optimizer.load_state_dict(saved['optimizer_state_dict']);steps=[]
    for parameter,state in optimizer.state.items():
        assert parameter.shape==state['exp_avg'].shape==state['exp_avg_sq'].shape
        assert bool(torch.isfinite(state['exp_avg']).all())and bool(torch.isfinite(state['exp_avg_sq']).all())
        step=state['step'];value=float(step)if torch.is_tensor(step)else step
        assert type(value)in(int,float)and math.isfinite(value)and value>0;steps.append(value)
    assert len(steps)==81
    lrs=[group['lr']for group in optimizer.param_groups];assert all(type(v)in(int,float)and math.isfinite(v)and v>0 for v in lrs)
    scaler=saved.get('grad_scaler_state_dict');assert isinstance(scaler,dict)
    assert all(not isinstance(v,float)or math.isfinite(v)for v in scaler.values())
    phase=saved['priority_metric_phase'];assert phase['schema']=='robotron-priority-metric-phase-v1'and phase['metric']=='ce'and phase['valid']is True
    assert not torch.cuda.is_initialized();h.checked(copied);h.checked(job['active_fixed_pair'])
    for pin in pins:h.checked(pin)
    assert born(job['main_owner']['pid'])==job['main_owner']['birth']
    return dict(status='PASS_CPU_PRESERVED_UNQUALIFIED_RESEARCH_CHECKPOINT',checkpoint=copied,
        opened_source_generation=dict(path=str(source),device=before.st_dev,inode=before.st_ino,bytes=before.st_size,
            mtime_ns=before.st_mtime_ns,sha256=digest.hexdigest(),latest_path_same_generation_after_copy=same_generation,
            opened_descriptor_content_stable=True),
        active_fixed_pair=job['active_fixed_pair'],previous_preservation_report=job['previous_preservation_report'],saved_clocks=clocks,additional_clocks_since_previous_preservation=deltas,
        minimum_observed_additional_learner_frames=job['minimum_additional_learner_frames'],exact_dose_endpoint=False,
        measurement_frame_count=saved['measurement_frame_count'],model_parameters=99,model_states=states,
        initialized_Adam_states=len(steps),raw_Adam_step_min=min(steps),raw_Adam_step_max=max(steps),
        raw_Adam_float32_saturation=min(steps)==max(steps)==16777216,inherited_optimizer_lrs=lrs,
        scaler_preserved=True,priority_phase_id=phase['phase_id'],CPU_only=True,CUDA_initialized=False,
        replay_constructed_or_copied=False,inference_batch_and_greedy_action_qualification_still_required=True,
        full_game_quality_qualification_still_required=True,selected_for_a_test=False,
        live_model_or_active_pair_or_protected_policy_modified=False,quality_qualified=False,promotion=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    h=load('_research_preservation_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    jp=h.pin(args.job);assert jp['sha256']==args.job_sha256
    job=json.loads(h.checked(jp).read_text());assert job['runtime']==h.pin(__file__)
    try:report=acquire(job,h)
    except Exception:report=dict(status='FAIL_RESEARCH_CHECKPOINT_PRESERVATION',error=traceback.format_exc(),quality_qualified=False,promotion=False)
    report.update(original_job=jp,source=job['runtime'],observed_unix_s=time.time())
    pin=h.put(job['report'],report);print(json.dumps(dict(status=report['status'],report=pin,error=report.get('error'))),flush=True)
    return 0 if report['status']=='PASS_CPU_PRESERVED_UNQUALIFIED_RESEARCH_CHECKPOINT'else 1


if __name__=='__main__':raise SystemExit(main())
