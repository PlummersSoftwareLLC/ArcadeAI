"""Prepare one fresh exact-three capacity CPU guard; no launch or old writes."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import stat

LOCAL=Path(__file__).resolve().parent
PARENT_PREPARED={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/actual-closed-metadata-current-profile-guard-original04/prepared-CPU-NOT-LAUNCHED.json', 'sha256': '3d5025bbbfab85bba6ae6d901aff14391920a92afa95cc9ededbf1de681bdd7e', 'bytes': 8149, 'identity': {'device': 2304, 'inode': 85459713, 'bytes': 8149, 'mtime_ns': 1793317228520073492, 'ctime_ns': 1793317228520073492, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PARENT_CPU_JOB={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/actual-closed-metadata-current-profile-guard-original04/job.json', 'sha256': '84ef03c6c13c0b804a2f8271db0ac41855c4b5e62bb0a14861b8952d216a3313', 'bytes': 437179, 'identity': {'device': 2304, 'inode': 85459711, 'bytes': 437179, 'mtime_ns': 1793317228426664765, 'ctime_ns': 1793317228426664765, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PARENT_SHIM={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/closed-metadata-current-profile-guard-original04/closed_metadata_readiness_reuse_current_profile_v8.py', 'sha256': '235aafdb90a1ea5d776b92191f2b7f077bf9bc585ddf76dc03cb502f7b80c3e5', 'bytes': 27770, 'identity': {'device': 2304, 'inode': 85459692, 'bytes': 27770, 'mtime_ns': 1793317172827728702, 'ctime_ns': 1793317172827728702, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
AMENDMENT_PRODUCER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/remaining-three-main-journal128-amendment-original01/prepare_remaining_three_main_journal128_amendment_v1.py', 'sha256': '6ecf2d7ac03b58a514bcf3ea15c0297b2d4161e3595c3a17f7c19078337bd96a', 'bytes': 18465, 'identity': {'device': 2304, 'inode': 87556186, 'bytes': 18465, 'mtime_ns': 1793326293883632414, 'ctime_ns': 1793326483693411855, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
DRIVER_SHA='22600f1824636431398f0c267058ce0ef7a78061e482383628876e1af299c444'
SHIM_SHA='80897097f2c36c1364d2daad47fef1e7654da9573126e2778f0b6179b7c982b4'


def require(value,reason):
    if not value:raise ValueError(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prepare(amendment_path,amendment_sha256,output):
    parent_path=Path(PARENT_PREPARED['path'])
    def initial_identity():
        info=parent_path.lstat()
        require(stat.S_ISREG(info.st_mode)and not parent_path.is_symlink()
                and parent_path.resolve(strict=True)==parent_path,'Canonical ordinary parent metadata required')
        return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,mtime_ns=info.st_mtime_ns,
            ctime_ns=info.st_ctime_ns,mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)
    require(initial_identity()==PARENT_PREPARED['identity'],'Exact parent full8 metadata identity required')
    initial_raw=parent_path.read_bytes()
    require(initial_identity()==PARENT_PREPARED['identity']and len(initial_raw)==PARENT_PREPARED['bytes']
            and hashlib.sha256(initial_raw).hexdigest()==PARENT_PREPARED['sha256'],
            'Exact immutable parent preparation bytes required before helper load')
    initial=json.loads(initial_raw)
    helper=initial['helpers']
    require(hashlib.sha256(Path(helper['path']).read_bytes()).hexdigest()==helper['sha256'],
            'Exact original full8 CPU helper source required')
    h=load('_three_capacity_guard_prepare_helpers',Path(helper['path']))
    def read(value):return json.loads(h.checked(value).read_bytes())
    parent=read(PARENT_PREPARED);old=read(PARENT_CPU_JOB)
    require(parent['CPU_job']==PARENT_CPU_JOB and old['readiness_reuse_shim']==PARENT_SHIM,
            'Exact historical G12 metadata proof source graph required')
    selected=h.pin(Path(amendment_path).resolve())
    require(selected['sha256']==amendment_sha256,'Exact Root-selected new amendment metadata required')
    prepared=read(selected);mixed=read(prepared['mixed_manifest'])
    require(prepared['schema']=='robotron-prepared-unused-three-leg-main-journal128-amendment-v1'
            and prepared['source']==AMENDMENT_PRODUCER
            and [r['leg']for r in prepared['subjects']]==['C1','R2','C2']
            and [r['leg']for r in mixed['cases']]==['R1','C1','R2','C2']
            and mixed['original_R1_already_qualified']is True
            and mixed['any_capacity_amended_payload_launched']is False,
            'Exact three unused derived subjects with original R1 required')
    driver=h.pin(LOCAL/'qualify_three_capacity_jobs_cpu_v1.py')
    shim=h.pin(LOCAL/'closed_metadata_three_capacity_readiness_v1.py')
    require(DRIVER_SHA is not None and SHIM_SHA is not None
            and driver['sha256']==DRIVER_SHA and shim['sha256']==SHIM_SHA,
            'Final frozen CPU driver and capacity adapter required')
    output=Path(output).absolute()
    require(output==output.resolve()and output.parent==LOCAL and not output.exists(),
            'Fresh CPU metadata directory directly under selected guard sources required')
    small={v['path']:v for v in old['inputs']}
    large={v['path']:v for v in old['large_input_stat_attestations']}
    metadata={v['path']:v for v in old['allowed_model_directory_metadata']}
    models=Path('/home/dave/source/repos/ArcadeAI/Robotron/models_dqn')
    additions=[selected,prepared['mixed_manifest'],prepared['selected_amendment'],PARENT_PREPARED,
        PARENT_CPU_JOB,PARENT_SHIM,AMENDMENT_PRODUCER,driver,shim,h.pin(Path(__file__).resolve())]
    for row in mixed['cases'][1:]:
        job=read(row['native_job'])
        require(job['leg']==row['leg']and job['attempt']==1 and job['no_retry']is True
                and not Path(job['output']).exists()and not Path(job['prelaunch_family_guard_closeout']).exists(),
                'Each exact new native output and guard must remain unused')
        additions.extend([row['native_job'],row['runtime'],row['native_controller'],row['source_family'],
            row['unqualified_controller_config'],*job['inputs']])
    for value in additions:
        path=Path(value['path'])
        if path.suffix=='.pt'or path==Path('/usr/games/mame'):
            require(large.get(str(path))==value,'New guard cannot adopt a new large model/MAME input')
        elif path.is_relative_to(models):
            require(metadata.get(str(path))==value,'Exact five inherited small model-control pins only')
            if str(path)in small:require(small[str(path)]==value,'Conflicting selected metadata identity')
            small[str(path)]=value
        else:
            if str(path)in small:require(small[str(path)]==value,'An old held input was silently refreshed')
            small[str(path)]=value
    classifier_pin=read(old['closed_metadata_readiness_source_contract'])['metadata_guard_preparer']
    classifier=load('_three_capacity_exact_metadata_classifier',h.checked(classifier_pin))
    classifier.preflight_held_inputs([*small.values(),*large.values()])
    for value in small.values():h.checked(value)
    # Validate the complete exact job/family/config derivation before creating output.
    adapter=load('_three_capacity_prepare_adapter',Path(shim['path']))
    provisional=dict(old,prepared_manifest=prepared['mixed_manifest'],prepared_amendment=selected,
        parent_guard_CPU_job=PARENT_CPU_JOB,parent_readiness_reuse_shim=PARENT_SHIM,
        amendment_producer=AMENDMENT_PRODUCER)
    adapter.ClosedMetadataReadiness(provisional,h,lambda *args,**kwargs:None)
    output.mkdir(mode=0o700)
    unit='robotron-three-capacity-exact-CPU-'+prepared['mixed_manifest']['sha256'][:16]+'-original01-20261029.service'
    job=copy.deepcopy(old)
    job.update(schema='robotron-deadline32-three-capacity-jobs-CPU-guard-v1',unit=unit,
        output=str(output/'output-original01'),prepared_manifest=prepared['mixed_manifest'],prepared_amendment=selected,
        inputs=list(small.values()),large_input_stat_attestations=list(large.values()),
        source=driver,readiness_reuse_shim=shim,parent_guard_CPU_job=PARENT_CPU_JOB,
        parent_readiness_reuse_shim=PARENT_SHIM,amendment_producer=AMENDMENT_PRODUCER,
        original_attempt=1,no_retry=True,engineering_only=False,
        expected_actual_serialized_job_tests=6,expected_new_native_chain_tests=4,expected_negative_cases_per_leg=8)
    jp=h.put(output/'job.json',job)
    witness=read(job['interpreter_symlink_binding']);control=load('_three_capacity_CPU_controller',h.checked(parent['controller']))
    cfg=dict(unit=unit,output=str(output/'execution-original01'),
        argv=[witness['source_pin']['path'],'-Xgil=0','-I','-B',driver['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[control.pin(v['path'])for v in [jp,*small.values()]],observation_s=240)
    cp=h.put(output/'controller-config.json',cfg)
    require(control.checked_config(cp['path'])==cfg,'Exact original CPU controller serialization differs')
    return h.put(output/'prepared-three-CPU-NOT-LAUNCHED.json',dict(
        schema='robotron-round-three-capacity-CPU-preparation-v1',CPU_job=jp,config=cp,controller=parent['controller'],
        driver=driver,helpers=helper,archive=parent['archive'],reader=parent['reader'],source_preparer=h.pin(Path(__file__).resolve()),
        native_prepared_manifest=prepared['mixed_manifest'],prepared_capacity_amendment=selected,
        readiness_reuse_shim=shim,closed_metadata_readiness_authority=job['closed_metadata_readiness_authority'],
        closed_metadata_readiness_source_contract=job['closed_metadata_readiness_source_contract'],
        ordered_legs=['C1','R2','C2'],old_exact_job_receipts_reused=False,
        expected_actual_subject_tests=6,expected_unchanged_private_boundary_tests=4,
        engineering_only=False,CPU_scope_launched=False,scientific_launch_qualified=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--amendment',type=Path);p.add_argument('--amendment-sha256');p.add_argument('--output',type=Path)
    p.add_argument('--source-sha256');args=p.parse_args()
    if not args.prepare:print('SOURCE_ONLY_INERT_NO_ACTIONS');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Exact selected CPU preparer required')
    print(json.dumps(prepare(args.amendment,args.amendment_sha256,args.output)),flush=True)


if __name__=='__main__':main()
