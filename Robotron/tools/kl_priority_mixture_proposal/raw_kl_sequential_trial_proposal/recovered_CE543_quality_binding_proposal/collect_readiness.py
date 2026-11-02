"""Fresh explicit recovered-CE readiness. Default PLAN reads nothing and acts on nothing.

Read-only runtime queries occur only for a root-authenticated execute job. No unit,
actor, recipe, source, model, checkpoint request or canonical mutation is present.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
HERE=Path(__file__).parent
CARRIER_SHA='4f3a0444c071781a09349a2020d0575bd12f95c78e56f4b3efbcdeaaa15d658d'
CAPTURE=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/recovered_live_ce_candidate_capture_proposal/capture_live_CE_candidate.py'
CAPTURE_SHA='7be0eaf012e208299548f131fd42651239740692d58b8a6d997a6eee6733e46c'
CAPTURE_MANIFEST=CAPTURE.with_name('preparation-manifest.json')
CAPTURE_MANIFEST_SHA='832fdfc62398203a8fb0045635cdfb954309273bb3ddd2bf62d68315c1628af3'
SCHEMA='robotron-recovered-CE543-quality-readiness-job-v1'
CAPTURE_UNIT='robotron-live-ce-postRecovery-candidate02-capture-20261017'
CPU_UNIT='robotron-live-ce-postRecovery-candidate02-phase-cpu-20261017'


def require(ok,message):
    if not ok:raise RuntimeError(message)


def load(path,digest,name):
    path=Path(path)
    require(path.is_absolute() and path==path.resolve(strict=True)
        and stat.S_IMODE(path.stat().st_mode)==0o444
        and hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Sealed exact source required')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Source changed during import')
    return module


def collect(job,pin,carrier,capture,ops):
    require(set(job)=={'schema','binding_job','output_directory','fleet_descriptor'}
        and job['schema']==SCHEMA,'Exact root readiness job required')
    carrier.configure(SimpleNamespace(binding_job=Path(job['binding_job']['path']),
        binding_job_sha256=job['binding_job']['sha256'],expected_source_sha256=CARRIER_SHA))
    require(carrier.BINDING_PIN==job['binding_job'],'Exact binding full PIN differs')
    cfg,bundle=carrier.CFG,carrier.BUNDLE
    bound,_=carrier.inputs(None)
    out=Path(job['output_directory'])
    require(out.is_absolute() and out==out.resolve(strict=False) and out.parent==RUN and not out.exists(),
        'NEW direct run26 readiness output required')
    files=capture.Files(ops)
    capture_job=files.read_json(bundle['capture']['root_job'])
    context=capture.recovery_context(capture_job,files)
    require(context['recovery']['owner']==cfg['runtime_anchor']['main_owner'],'Recovered/current owner differs')
    prior_fleet=carrier.BINDINGS.read(job['fleet_descriptor'])
    out.mkdir(mode=0o700)
    def record(name,value):return ops.publish(out/(name+'.json'),value)
    resources,raw=capture.current_ce_and_resources(ops,context,record)
    ops.publish(out/'checked-resources.json',resources);ops.write_bytes(out/'fresh-raw-API.json',raw)
    anchor=cfg['runtime_anchor']
    require(resources['owner']==anchor['main_owner'],'Current CE owner changed')
    for actor in anchor['actors']:
        require(resources['actor_masks'][str(actor['pid'])]==actor['mask'],'Current actor mask changed')
    require(resources['main_mask']==resources['inference_mask']==anchor['inference_worker']['mask'],
        'Current main/inference masks differ')
    require(not (GAME/'models_dqn/managed_save.request.json').exists(),'Pending managed save remains')
    released={}
    # The new capture and CPU originals must already have root archive/release.
    # These fresh not-found observations prove their current absence; candidate
    # capture+CPU identity/original exit0 are independently bound by the binder.
    for name in (CAPTURE_UNIT,CPU_UNIT):
        for suffix in ('.timer','.service'):
            fields,raw_command=ops.show(name+suffix)
            require(fields['LoadState']=='not-found','Owned capture/CPU unit remains loaded')
            released[name+suffix]=raw_command
    ops.publish(out/'capture-and-CPU-units-not-found.json',released)
    for path,digest in anchor['unit_files'].items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,'Held unit source changed')
    memory=ops.command(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
    require(memory['returncode']==0,'GPU memory query failed')
    free={row.split(',')[0].strip():int(row.split(',')[1])*(1<<20) for row in memory['stdout'].splitlines() if row.strip()}
    require(free[carrier.GPU0]>=14*(1<<30),'GPU0 free margin below14GiB')
    ops.publish(out/'GPU-free-memory.json',memory)
    fleet=anchor['fleet_owner'];pid=fleet['pid']
    status=Path('/proc',str(pid),'status').read_text()
    require(next(line.split()[1:] for line in status.splitlines() if line.startswith('Uid:'))==[str(os.getuid())]*4
        and ops.process_start(pid)==fleet['starttime_ticks'],'Fleet owner/UID changed')
    observed=dict(owner=fleet,argv=[os.fsdecode(part) for part in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if part],
        cwd=os.readlink('/proc/'+str(pid)+'/cwd'),exe=os.readlink('/proc/'+str(pid)+'/exe'))
    require(observed=={key:prior_fleet[key] for key in observed},'Exact root-observed fleet command changed')
    ops.publish(out/'fleet-process-descriptor.json',observed)
    ready=dict(copy.deepcopy(anchor),schema='robotron-live-CE-exclusive-readiness-v1',status='PASS',
        observed_unix_s=time.time(),candidate=dict(source=cfg['candidate']['path'],sha256=cfg['candidate']['sha256'],
            bytes=cfg['candidate']['bytes'],root_job_sha256=bound['phase_cpu_job']['sha256'],cpu_proof_sha256=bound['phase_cpu_proof']['sha256']),
        resources=dict(gpu0_uuid=carrier.GPU0,gpu1_uuid=carrier.GPU1,GPU0_free_bytes=free[carrier.GPU0],
            GPU0_no_compute_owner=resources['GPU0_free'],GPU1_main_only=resources['sole_main_on_GPU1'],
            port9999_clear=resources['port9999_unused'],lease_free=resources['lease_unheld'],
            no_competing_helpers=resources['no_private_tmpfs_or_helpers'],
            no_private_cgroup_tmpfs_processes=resources['no_private_tmpfs_or_helpers'],no_pending_save=True,
            capture_and_CPU_units_released=True,commands_UID_cwd_exe_checked=True,held_environment_checked=True,unit_files_checked=True))
    current=carrier.fast_runtime(ready);carrier.readiness_contract(ready,bound)
    actual=ops.publish(out/'runtime-readiness.json',ready)
    ops.publish(out/'root-readiness-result.json',dict(status='PASS',root_job=pin,readiness=actual,current=current,
        binding_job=carrier.BINDING_PIN,candidate_quality_claim=False,launched=False))
    return dict(status='PASS',readiness=actual,current=current)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: explicit fresh recovered-CE readiness job required; no reads/imports/runtime/actions')
        return 0
    require(args.expected_source_sha256==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'Explicit exact readiness source required')
    sys.dont_write_bytecode=True
    capture=load(CAPTURE,CAPTURE_SHA,'_recovered_ce_capture_for_readiness')
    files=capture.Files(None)
    manifest=files.fingerprint(CAPTURE_MANIFEST,capture.MAX_JSON)
    require(manifest['sha256']==CAPTURE_MANIFEST_SHA and manifest['identity']['mode']=='0o444','Capture manifest differs')
    pin=files.fingerprint(args.job,capture.MAX_JSON)
    require(pin['sha256']==args.expected_job_sha256 and pin['identity']['mode']=='0o444','Exact readonly readiness job required')
    job=files.read_json(pin)
    carrier=load(HERE/'root_quality_carrier.py',CARRIER_SHA,'_recovered_ce_quality_readiness_carrier')
    path,digest=capture.DEPENDENCIES['resources']
    ops=load(path,digest,'_recovered_ce_quality_readiness_resources')
    print(json.dumps(collect(job,pin,carrier,capture,ops),allow_nan=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
