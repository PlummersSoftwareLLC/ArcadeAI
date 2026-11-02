"""Root data-only assembly of the complete inherited stopped CPU job ABI.

Default inert. --prepare requires actual stopped authority and a separate Root
checkpoint-copy acquisition. It reads only source/metadata/control/unit bytes;
checkpoint paths are stat-only here. No candidate imports, runtime probes,
model/array loads, copies of model bodies, controls or launches.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
H=B/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01'
HERE=H/'state-sources'
VERIFIER=HERE/'verify_stopped_full_training_state_v2.py'
VERIFIER_SHA='560bdf7dc1045252949c02afebd3ae8f8d45f34f7809e7b2d4025145388a8f88'
CONTROLLER=HERE/'control_stopped_fullstate600_CPU_v1.py'
CONTROLLER_SHA='19338ee6d5ae925f5dadd390a4d3f98f23217b9faeb5ffc2bd25b8631d6d1dd7'
TEMPLATE=HERE/'Root-stopped-fullstate-v2-job-template-UNFILLED-NOT-LAUNCHABLE.json'
MODEL_NAMES=('model.py','config.py','learning_control.py','__init__.py')
HELD=dict(batch_size=4096,baseline_batch_size=512,epsilon=.1,expert_ratio=.1,n_step=3,
    max_samples_per_frame=8,c51_target_smoothing=0,learning_control_lr_scale=.0625,
    lr_gear='climb',lr_anchor_step=0.,optimizer_lr=3.125e-6,optimizer_eps=1.5e-4,
    fused=True,gamma=.995,num_atoms=51,v_min=-10.,v_max=50.)


def require(value,message):
    if not value:raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def metadata(path,*,immutable=True):
    path=Path(path)
    require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink(),
        'Canonical metadata/source required')
    before=path.stat()
    require(stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_nlink==1
        and 0<before.st_size<=4<<20 and(not immutable or stat.S_IMODE(before.st_mode)==0o444),
        'Owned bounded metadata/source required; model/array bodies forbidden')
    raw=path.read_bytes();require(identity(path.stat())==identity(before),'Metadata/source changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before)),raw


def read(value):
    actual,raw=metadata(value['path']);require(actual==value,'Selected metadata changed');return json.loads(raw)


def put(path,value):
    raw=value if isinstance(value,bytes)else(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return metadata(path)[0]


def model_stat(value,*,readonly=False):
    path=Path(value['path']);require(path.resolve(strict=True)==path and not path.is_symlink(),'Physical checkpoint path required')
    info=path.stat()
    require(stat.S_ISREG(info.st_mode)and info.st_uid==os.getuid()and info.st_nlink==1
        and 200<<20<=info.st_size<=400<<20 and info.st_size==value['bytes']
        and identity(info)==value['identity']and(not readonly or stat.S_IMODE(info.st_mode)==0o444),
        'Actual checkpoint/copy stat identity differs')


def prepare(args):
    own,_=metadata(Path(__file__).resolve());require(own['sha256']==args.source_sha256,'Exact Root assembler source required')
    selection_pin,raw=metadata(Path(args.selection));require(selection_pin['sha256']==args.selection_sha256,'Exact actual Root selection required')
    selection=json.loads(raw)
    require(selection['schema']=='robotron-root-actual-stopped-fullstate-CPU-inputs-v1','Actual stopped input selection required')
    template_pin,raw=metadata(TEMPLATE);job=json.loads(raw)
    verifier,_=metadata(VERIFIER);controller,_=metadata(CONTROLLER)
    require(verifier['sha256']==VERIFIER_SHA and controller['sha256']==CONTROLLER_SHA,'Selected verifier/controller changed')
    require(job['source']==verifier,'Exact current verifier template source required')
    authority=read(selection['stopped_authority']);seal=read(authority['bank_seal']);api=read(authority['final_API'])
    require(authority['schema']=='robotron-owned-stopped-training-preservation-authority-v1'
        and authority['owner']==job['owner']and type(authority['actual_exit'])is int and authority['actual_exit']==0
        and authority['original_scope_released']is True and api['client_count']==0 and api['client_rows']==[],
        'Actual stopped original/zero-input authority required')
    acq=read(selection['checkpoint_acquisition'])
    require(acq['schema']=='robotron-root-stopped-checkpoint-and-independent-copy-v1'
        and acq['stopped_authority']==selection['stopped_authority'],'Actual Root copy belongs to another stop')
    source,copied=acq['source_checkpoint'],acq['verification_copy'];model_stat(source);model_stat(copied,readonly=True)
    require(source['path']==str(G/'models_dqn/robotron_dqn_latest.pt')
        and source['sha256']==copied['sha256']and source['bytes']==copied['bytes']
        and(source['identity']['device'],source['identity']['inode'])!=(copied['identity']['device'],copied['identity']['inode']),
        'Actual independent current latest copy required; CPU will hash both bodies')
    prep=read(selection['stop_preparation']);stop_job=read(prep['job']);binding=read(stop_job['main_binding'])
    require(stop_job['trainer']==authority['owner']and stop_job['schema']=='robotron-owned-current-round-stop-job-v1',
        'Actual selected stop job differs')
    package={}
    for name in MODEL_NAMES:
        path=G/'Scripts/dqn'/name;value,_=metadata(path,immutable=False);expected=binding['inputs'][str(path)]
        require(value['sha256']==expected['sha256']and value['identity']==expected['identity'],
            'Actual source differs from selected stop247 domain: '+name)
        package[name]=value
    control_pin,control_raw=metadata(G/'models_dqn/learning_control.json',immutable=False);control=json.loads(control_raw)
    require(control['experiment']==api['managed_experiment']==binding['experiment']and control['lr_scale']==.0625
        and control['epsilon_ramp']['start']==control['epsilon_ramp']['end']==.1,'Actual final archived recipe differs')
    terminal=read(authority['terminal_archive']);cat=read(terminal['archives']['cat'])
    require(terminal['owner']==authority['owner']and cat['owner']==authority['owner']and cat['exit']==0
        and cat['argv']==['systemctl','--user','cat',authority['owner']['unit']],
        'Exact original archived trainer unit required')
    require(metadata(cat['stdout']['path'])[0]==cat['stdout'],'Original unit archive bytes changed')
    output=Path(args.output)
    require(output.is_absolute()and output.resolve(strict=False)==output and not output.exists()
        and output.parent.is_dir()and output.is_relative_to(H),'New actual Root CPU preparation directory required')
    output.mkdir(mode=0o700)
    archived_control=put(output/'actual-final-learning-control.json',control_raw)
    context=dict(game_root=str(G),model_dir=str(G/'models_dqn'),model_package=package,
        archived_control=archived_control,archived_trainer_unit=cat['stdout'],
        provenance=[selection['stop_preparation'],selection['stopped_authority'],authority['bank_seal'],
            stop_job['main_binding'],job['boot_CPU_report'],job['phase_record'],job['phase_anchor']],
        held_recipe_context=HELD)
    # b1.select_recipe_base uses only this CE selector. Old acquisition/read_job
    # are never called; no old owner/boot/purpose proof is fabricated here.
    job.update(schema='robotron-stopped-full-training-state-CPU-job-v1',source=verifier,
        experiment=api['managed_experiment'],clock_floor=seal['clock_floor'],source_checkpoint=source,
        verification_copy=copied,source_control_context=context,phase_snapshot=dict(expected_phase=dict(metric='ce')),
        stopped_authority=selection['stopped_authority'],output_directory=str(output/'runtime'))
    inputs=[own,template_pin,selection_pin,selection['checkpoint_acquisition'],selection['stop_preparation'],prep['job'],
        selection['stopped_authority'],authority['bank_seal'],authority['final_API'],authority['terminal_archive'],
        terminal['archives']['cat'],cat['stdout'],archived_control,verifier,controller,*package.values(),
        *job['dependencies'].values(),job['boot_CPU_report'],job['phase_record'],job['phase_anchor'],
        job['ring_storage_before'],job['ring_insert_anchor'],stop_job['main_binding']]
    job['inputs']=list({v['path']:v for v in inputs}.values())
    require(set(context)=={'game_root','model_dir','model_package','archived_control','archived_trainer_unit','provenance','held_recipe_context'}
        and set(package)==set(MODEL_NAMES)and job['phase_snapshot']=={'expected_phase':{'metric':'ce'}},
        'Complete exact inherited strict context/CE selector required')
    jp=put(output/'job.json',job)
    reduced=lambda v:dict(path=v['path'],sha256=v['sha256'],bytes=v['bytes'],identity={k:v['identity'][k]for k in('device','inode','mode','uid','nlink')})
    cfg=dict(unit=job['unit'],output=str(output/'execution-original01'),argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(VERIFIER),
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',VERIFIER_SHA],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=660,pins=[reduced(v)for v in[jp,*job['inputs']]])
    cp=put(output/'controller-config.json',cfg)
    require(metadata(G/'models_dqn/learning_control.json',immutable=False)[0]==control_pin,'Control changed during data preparation')
    return put(output/'prepared-actual-stopped-fullstate-CPU-NOT-LAUNCHED.json',dict(
        schema='robotron-actual-stopped-fullstate-CPU-data-preparation-v1',status='DATA_PREPARED_NOT_LAUNCHED',source=own,
        actual_selection=selection_pin,job=jp,config=cp,actual_model_bodies_read_or_copied_by_preparer=False,
        CE_selector_only_not_old_acquisition_proof=True,actual_CPU_or_restore_qualified=False,
        Root_controller_argv=['/usr/bin/python3.12','-I','-B',str(CONTROLLER),'--execute','--config',cp['path'],'--expected-source-sha256',CONTROLLER_SHA]))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--source-sha256')
    p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--output');a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a)),flush=True)
    else:print('PLAN_ONLY_NO_READS_IMPORTS_OUTPUTS_OR_ACTIONS')
