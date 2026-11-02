#!/usr/bin/env python3
"""Inert by default; explicit future CPU-only192M lineage PROPOSAL capture.

Requires actual checkpoint+gate, explicit current runtime metadata/SHA and hidden
CUDA. No quality reads, promotion, final lineage, model/control/process writes.
"""
import argparse
from datetime import datetime,timezone
import hashlib,importlib.util,json,math,os,resource,stat,sys,tempfile,time
from pathlib import Path
RUN=Path(__file__).resolve().parent
CAMPAIGN=RUN.parents[1]
GAME=CAMPAIGN.parents[1]
GUARD_SHA="6a8dda64851bafdf765bc78140663e29488b0ba4e39c2e3a889a0ce3a1d51363"
PLAN_SHA="13fecf794902fc9d20c690be6b8bad39d4c0256bf6d3f153fc309ec8003e06aa"
REFERENCE_LINEAGE_SHA="4535f56d71a1fe3c3b6c3f148ae7ab9cc6f9846d6eaa3b420ede0e82bc6eda18"
EXPERIMENT="best10M-fresh3-eps10-cap8-nosmooth"
TARGET=196629023

def require(value, message):
    if not value:
        raise ValueError(message)

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()

def signature(state, torch):
    require(isinstance(state, dict) and state, "Missing state dictionary")
    require(all(isinstance(name, str) and torch.is_tensor(value) for name, value in state.items()),
            "State dictionary contains a non-tensor")
    require(all(value.device.type == "cpu" for value in state.values()), "Non-CPU network tensor")
    return {name: dict(shape=list(value.shape), dtype=str(value.dtype)) for name, value in state.items()}

def scalar(value, torch):
    if torch.is_tensor(value):
        require(value.device.type == "cpu" and value.numel() == 1, "Invalid scalar optimizer group value")
        return scalar(value.item(), torch)
    if isinstance(value, (tuple, list)):
        return [scalar(item, torch) for item in value]
    require(value is None or isinstance(value, (bool, int, float, str)), "Unsupported scalar metadata type")
    require(not isinstance(value, float) or math.isfinite(value), "Nonfinite scalar metadata")
    return value

def tensor_walk(value, torch):
    if torch.is_tensor(value):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from tensor_walk(item, torch)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from tensor_walk(item, torch)

def optimizer_info(value, torch):
    require(isinstance(value, dict) and isinstance(value.get("state"), dict)
            and isinstance(value.get("param_groups"), list), "Missing optimizer state")
    states = value["state"]
    require(len(states) == 81 and all(isinstance(row, dict) for row in states.values()), "Expected Adam81 states")
    tensors = list(tensor_walk(value, torch))
    require(all(item.device.type == "cpu" for item in tensors), "Non-CPU optimizer tensor")
    steps = []
    for row in states.values():
        step = row["step"]
        step = step.item() if torch.is_tensor(step) and step.numel() == 1 else step
        require(isinstance(step, (int, float)) and not isinstance(step, bool)
            and math.isfinite(step) and step >= 0, "Invalid Adam parameter step")
        steps.append(float(step))
        require(torch.is_tensor(row.get("exp_avg")) and torch.is_tensor(row.get("exp_avg_sq"))
            and row["exp_avg"].shape == row["exp_avg_sq"].shape, "Missing/mismatched Adam moments")
    groups = []
    parameter_ids = []
    for group in value["param_groups"]:
        require(isinstance(group.get("params"), list) and group["params"], "Missing optimizer group parameter IDs")
        parameter_ids.extend(group["params"])
        groups.append(dict({key: scalar(item, torch) for key, item in group.items() if key != "params"},
                           parameter_count=len(group["params"])))
    require(len(parameter_ids) == len(set(parameter_ids)) and set(states).issubset(parameter_ids),
            "Duplicate/unknown optimizer parameter IDs")
    return dict(state_count=len(states), step_values=sorted(set(steps)),
        minimum_parameter_step=min(steps), maximum_parameter_step=max(steps),
        groups=groups, all_tensors_CPU=True, tensor_count=len(tensors)), tensors

def group_geometry(groups):
    # LR follows the existing sample-clock schedule; its actual value is kept
    # in the report but need not stay numerically equal to the128M LR.
    return [{key: value for key, value in group.items() if key != "lr"} for group in groups]


def sha_string(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def load_contract():
    path=RUN/'analyze192M_assessment.py'
    require(sha(path)==GUARD_SHA,'Reviewed192M analyzer changed')
    spec=importlib.util.spec_from_file_location('lineage192_contract',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(module.PLAN_SHA==PLAN_SHA,'Reviewed192M plan pin changed')
    return module


def strict_moment_geometry(checkpoint,reference,torch):
    online=checkpoint['online_state_dict']
    pinned=reference['candidate']['state_dict_signatures']['online_state_dict']
    require(list(online)==list(pinned),'Online parameter order differs from pinned128M')
    names=[name for name in pinned if name!='support']
    optimizer=checkpoint['optimizer_state_dict']
    ids=[owner for group in optimizer['param_groups'] for owner in group['params']]
    require(len(names)==len(ids)==len(set(ids))==99 and all(type(x) is int for x in ids),
            'Cannot bind99 pinned online parameters to unique integer Adam IDs')
    parameters=dict(zip(ids,names,strict=True))
    require(all(type(owner) is int for owner in optimizer['state'])
        and set(optimizer['state']).issubset(parameters),'Unknown Adam moment owner')
    for owner,row in optimizer['state'].items():
        parameter=online[parameters[owner]]
        for key in ('exp_avg','exp_avg_sq'):
            value=row.get(key)
            require(torch.is_tensor(value) and value.shape==parameter.shape and value.dtype==parameter.dtype,
                    'Actual Adam moment differs from its pinned online parameter shape/dtype')


def exposure(before,after):
    deltas={key:after[key]-before[key] for key in ('training_steps','optimized_samples','learner_frame_count')}
    require(all(type(value) is int and value>0 for value in deltas.values()),'Saved192M exposure did not advance128M')
    require(deltas['optimized_samples']==4096*deltas['training_steps'],'Saved sample delta differs from4096*logical updates')
    return dict(recorded_batch_size=4096,logical_updates_delta=deltas['training_steps'],
        optimized_samples_delta=deltas['optimized_samples'],learner_frames_delta=deltas['learner_frame_count'])


def check_recipe(runtime,controls,plan):
    expected=plan['branch_and_exposure'];config=runtime['config'];env=runtime['environment']
    wanted=dict(batch_size=4096,baseline_batch_size=512,n_step=3,max_samples_per_frame=8.0,
                c51_target_smoothing=0.0,torch_compile_mode='default')
    require(all(config.get(k)==v for k,v in wanted.items()),'Recorded runtime recipe differs')
    wanted_env=dict(DQN_BATCH_SIZE='4096',DQN_COMPILE_MODE='default',DQN_LEARNING_EXPOSURE_COUNTERS='1',
                    DQN_N_STEP='3',DQN_MAX_SAMPLES_PER_FRAME='8',DQN_C51_TARGET_SMOOTHING='0',DQN_STREAM_BANK_OUTPUT='1')
    require(all(env.get(k)==v for k,v in wanted_env.items()),'Recorded runtime compiler/counter/branch environment differs')
    require(expected['experiment']==EXPERIMENT and expected['batch_size']==4096
        and expected['compile_mode']=='default' and expected['exposure_counters'] is True,
        'Plan branch recipe differs')
    require(controls['experiment']==EXPERIMENT and controls['lr_scale']==.5
        and controls['epsilon_ramp']['start']==controls['epsilon_ramp']['end']==.1,
        'Current branch/LR/epsilon controls differ')


def proposed_report(torch,checkpoint,candidate,candidate_sha,before_stat,gate,gate_path,gate_sha,
                    reference,plan,runtime,runtime_path,runtime_sha,controls,evidence,started,process_start,contract):
    ref=reference['candidate'];previous=ref['saved_metadata']
    require(reference.get('proposal_only') is False and reference.get('PASS') is True
        and reference.get('checks') and all(value is True for value in reference['checks'].values())
        and reference['root_verification']['status']=='PASS'
        and reference['root_verification']['CUDA_initialized'] is False,'Require final root CPU128M reference PASS')
    require(ref['sha256']==plan['reference']['checkpoint']['sha256']
        and previous==plan['reference']['saved_clocks'],'Pinned128M reference differs')
    metadata={key:scalar(checkpoint[key],torch) for key in previous}
    for key in contract.META_KEYS:
        require(type(metadata.get(key)) is int and metadata[key]>=0,'Invalid saved integer clock/metadata: '+key)
    for key in ('engine_version','state_size','single_frame_state_size','frame_stack'):
        require(metadata[key]==previous[key],'Saved architecture metadata differs: '+key)
    require(metadata['baseline_batch_size']==512 and metadata['training_steps']==metadata['total_training_steps']
        and metadata['frame_count']>=max(metadata['learner_frame_count'],previous['frame_count'])
        and metadata['measurement_frame_count']>=previous['measurement_frame_count']
        and previous['last_target_update_samples']<=metadata['last_target_update_samples']<=metadata['optimized_samples'],'Saved lineage clock inconsistency')
    require(metadata['learner_frame_count']>=TARGET,'Actual saved learner gate not reached')
    new_exposure=exposure(previous,metadata)
    require(metadata['epsilon']==previous['epsilon']==.1
        and math.isclose(metadata['expert_ratio'],previous['expert_ratio'],abs_tol=1e-12)
        and math.isclose(metadata['expert_ratio'],.1,abs_tol=1e-12),'Saved behavior controls differ')
    require(isinstance(metadata['lr_anchor_step'],(int,float)) and not isinstance(metadata['lr_anchor_step'],bool)
        and math.isfinite(metadata['lr_anchor_step']),'Invalid numeric saved LR anchor')
    require(all(metadata[k]==previous[k] for k in ('lr_gear','lr_anchor_step')),'Saved LR lineage differs')
    check_recipe(runtime,controls,plan)
    require(gate['tag']=='fresh3-192M' and gate['target']==TARGET and gate['experiment']==EXPERIMENT
        and Path(gate['checkpoint']).resolve()==candidate.resolve(),'Future gate identity/branch differs')
    signatures={key:signature(checkpoint[key],torch) for key in ('online_state_dict','target_state_dict')}
    require(signatures==ref['state_dict_signatures'],'Actual192M online/target signature differs from128M')
    optimizer,opt_tensors=optimizer_info(checkpoint['optimizer_state_dict'],torch)
    strict_moment_geometry(checkpoint,reference,torch)
    require(all(isinstance(group.get('lr'),(int,float)) and not isinstance(group['lr'],bool)
        and math.isfinite(group['lr']) and group['lr']>0 for group in optimizer['groups']),'Invalid optimizer LR')
    require(group_geometry(optimizer['groups'])==group_geometry(ref['optimizer']['groups']),
        'Adam group geometry differs from128M')
    require(all(value.is_integer() and 0<=value<=metadata['training_steps'] for value in optimizer['step_values'])
        and min(optimizer['step_values'])>=max(ref['optimizer']['step_values']),'Adam parameter steps invalid/backwards')
    networks=list(tensor_walk({key:checkpoint[key] for key in signatures},torch))
    require(all(not value.is_floating_point() or bool(torch.isfinite(value).all().item())
                for value in (*networks,*opt_tensors)),'Nonfinite CPU network/optimizer tensor')
    all_tensors=list(tensor_walk(checkpoint,torch));devices=sorted({str(x.device) for x in all_tensors})
    require(devices==['cpu'] and torch.cuda.is_initialized() is False,'CPU-only guard failed')
    require(contract.file_stat(candidate)==before_stat and sha(candidate)==candidate_sha,
        'Future candidate changed during CPU capture')
    evidence.bind_stat(candidate,before_stat)
    checks=dict(CPU_only=True,candidate_stable_during_read=True,final_root128_reference=True,
        online_target_keys_shapes_dtypes_match128M=True,Adam81=True,Adam_moments_bound_to99_online_parameter_geometry=True,
        Adam_group_geometry_matches128M=True,Adam_steps_monotone=True,all_network_optimizer_tensors_finite=True,
        saved_learner_gate_passed=True,saved_logical_equals_total=True,recorded_recipe_and_current_controls_match=True,
        unchanged4096_saved_exposure_consistent=True)
    return dict(schema='robotron-192M-checkpoint-lineage-v1',utc=utc(),proposal_only=True,
        root_verification='PENDING: root must independently verify and publish final lineage',PASS=True,checks=checks,
        candidate=dict(path=str(candidate.resolve()),sha256=candidate_sha,
            stat=dict(before_stat,mode=oct(stat.S_IMODE(candidate.stat().st_mode)),nlink=candidate.stat().st_nlink),
            saved_metadata=metadata,optimizer=optimizer,state_dict_signatures=signatures,tensor_devices=devices,
            checkpoint_tensor_count=len(all_tensors),all_network_optimizer_tensors_finite=True),
        protected128M=dict(path=plan['reference']['checkpoint']['path'],sha256=ref['sha256'],
            lineage_path=plan['reference']['lineage_path'],lineage_sha256=plan['reference']['lineage_sha256'],
            saved_metadata=previous,optimizer=ref['optimizer']),
        trigger_gate=dict(path=str(gate_path),sha256=gate_sha,record=gate,
            note='Trigger clocks retained verbatim; actual saved checkpoint metadata is authoritative.'),
        branch_provenance=dict(experiment=EXPERIMENT,unchanged4096_after128M=True,compile_mode='default',
            exposure_counters_enabled=True,control_path=str(GAME/'models_dqn/learning_control.json'),
            control_snapshot=controls,runtime_metadata_path=str(runtime_path),runtime_metadata_sha256=runtime_sha,
            recorded_runtime_recipe=runtime,
            scope='Current recorded recipe and controls plus exact saved4096 arithmetic corroborate this proposed branch. Root must independently check continuous management chronology; static metadata is not a per-update execution trace.'),
        actual_recorded_batch_exposure=dict(since128M=new_exposure,
            Adam_parameter_steps128M=ref['optimizer']['step_values'],Adam_parameter_steps192M=optimizer['step_values'],
            minimum_Adam_parameter_step_delta=min(optimizer['step_values'])-max(ref['optimizer']['step_values']),
            note='Logical/sample exposure and per-parameter Adam steps remain distinct; no full-interval AMP classification is inferred.'),
        counter_exposure_evidence=dict(available=False,
            reason='No API collection by proposal helper. Optional separately SHA-pinned/timestamped process+epoch evidence may be attached by independent root verification; it is not atomic candidate-time AMP reconciliation.'),
        capture_execution=dict(started_utc=started,finished_utc=utc(),elapsed_s=time.monotonic()-process_start,
            python=sys.version,torch=str(torch.__version__),CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'),
            torch_threads=torch.get_num_threads(),torch_interop_threads=torch.get_num_interop_threads(),
            CUDA_initialized=torch.cuda.is_initialized(),max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        limitations=['PROPOSAL ONLY; unchanged strict192M analyzer rejects it until independent root verification publishes proposal_only=false/root_verification PASS.',
            'Only128M->192M current-branch4096 exposure is asserted; earlier batch/compiler trajectory remains in the historical128M lineage, not relabeled.',
            'No quality/promotion/protection/final-lineage/state/control/process writes or evaluation launch. Static snapshots cannot prove every historical read.'],
        evidence=evidence.snapshot())


def output_policy(output):
    output=Path(output)
    require(output.resolve().parent==RUN.resolve() and output.name.startswith('proposed-fresh3-192M-')
        and output.suffix=='.json','Only a new proposed-fresh3-192M-*.json in quality192M-preparation may be written')
    require(not output.exists() and not output.is_symlink(),'Proposal output already exists')


def publish_proposal(output,report,evidence):
    output_policy(output);raw=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
    fd,name=tempfile.mkstemp(prefix='.lineage192-',suffix='.tmp',dir=RUN)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        evidence.recheck();output_policy(output)
        os.link(name,output);os.unlink(name)
        directory=os.open(RUN,os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        try:os.unlink(name)
        except FileNotFoundError:pass


def capture(output,runtime_metadata,runtime_sha):
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='',"Run with CUDA_VISIBLE_DEVICES='' before Torch")
    require(sha_string(runtime_sha) and runtime_metadata is not None,'Explicit root-pinned current runtime metadata/SHA required')
    output_policy(output)
    candidate=GAME/'models_dqn/managed-checkpoints/fresh3-192M.pt'
    gate_path=CAMPAIGN/'run-23/fresh3-192M-gate.json'
    require(candidate.is_file() and gate_path.is_file(),'Actual192M checkpoint and gate must both exist')
    started,process_start=utc(),time.monotonic();contract=load_contract();evidence=contract.Evidence()
    evidence.file(__file__,sha(__file__));evidence.file(RUN/'analyze192M_assessment.py',GUARD_SHA)
    plan=evidence.json(RUN/'quality192M-assessment-plan.json',PLAN_SHA)
    contract.history_manifest(plan,evidence)  # completed160 history before any192 payload access
    require(plan['candidate']['checkpoint']==str(candidate) and plan['candidate']['gate_report']==str(gate_path),
            'Plan future paths differ')
    reference=evidence.json(plan['reference']['lineage_path'],REFERENCE_LINEAGE_SHA)
    require(plan['reference']['lineage_sha256']==REFERENCE_LINEAGE_SHA,'Reference root lineage pin changed')
    protected=plan['reference']['checkpoint'];metadata=evidence.json(protected['metadata_path'],protected['metadata_sha256'])
    require(metadata['sha256']==protected['sha256'] and metadata['saved_checkpoint_metadata']==plan['reference']['saved_clocks'],
        'Protected128 metadata differs')
    gate=evidence.json(gate_path);gate_sha=evidence.files[str(gate_path.absolute())]
    runtime=evidence.json(runtime_metadata,runtime_sha)
    controls=evidence.json(GAME/'models_dqn/learning_control.json')
    evidence._path(candidate);before=contract.file_stat(candidate)
    require(0<before['size']<=512*1024*1024,'Future candidate exceeds bounded checkpoint size')
    candidate_sha=sha(candidate);evidence.file(candidate,candidate_sha);evidence.bind_stat(candidate,before)
    import torch
    require(torch.cuda.is_initialized() is False,'CUDA context already initialized')
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    checkpoint=torch.load(candidate,map_location='cpu',weights_only=True)
    require(isinstance(checkpoint,dict),'Checkpoint is not a dictionary')
    report=proposed_report(torch,checkpoint,candidate,candidate_sha,before,gate,gate_path,gate_sha,reference,
        plan,runtime,Path(runtime_metadata).resolve(),runtime_sha,controls,evidence,started,process_start,contract)
    evidence.recheck();publish_proposal(output,report,evidence)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',action='store_true')
    parser.add_argument('--output',type=Path,default=RUN/'proposed-fresh3-192M-checkpoint-lineage.json')
    parser.add_argument('--runtime-metadata',type=Path)
    parser.add_argument('--runtime-metadata-sha256')
    args=parser.parse_args()
    if not args.capture:parser.print_help();return
    try:result=capture(args.output,args.runtime_metadata,args.runtime_metadata_sha256)
    except (OSError,ValueError,KeyError,TypeError) as error:parser.exit(2,'192M lineage proposal rejected: '+str(error)+'\n')
    print(json.dumps(dict(output=str(args.output),PASS=result['PASS'],proposal_only=True,
        candidate_sha256=result['candidate']['sha256'],saved_metadata=result['candidate']['saved_metadata'],
        capture_execution=result['capture_execution'])))
if __name__=='__main__':main()
