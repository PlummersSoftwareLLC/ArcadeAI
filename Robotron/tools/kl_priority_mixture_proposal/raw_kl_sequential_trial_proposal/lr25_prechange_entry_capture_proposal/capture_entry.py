"""One future .5 live192 entry snapshot and b2e CPU job; no CPU/control lifecycle."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import traceback

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
Q=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
SCHEMA='robotron-root-lr25-prechange-live192-entry-case-v1'
RESULT_SCHEMA='robotron-root-lr25-prechange-live192-entry-result-v1'
DRIVER_SHA='35c774c87827252ec623211110f887e98da6da728cb67b2cfa039f894f5a33b5'
DEPS={
    'driver':(Q/'lr25_hot_window_driver_reviewed2_proposal/run_hot_window.py',DRIVER_SHA),
    'ops':(RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py','d525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'),
    'capture':(Q/'recovered_live_ce_candidate_capture_proposal/capture_live_CE_candidate.py','7be0eaf012e208299548f131fd42651239740692d58b8a6d997a6eee6733e46c'),
    'snapshot':(Q/'live_one_trial_installed_ce_revision2_proposal/early_insurance.py','0112da455fd0c3c7b711cda2ff59f8575a637f2544ec37f9ad68ad2698b0dab4'),
    'observer':(Q/'lr25_hot_window_observer_proposal/hot_window_observer.py','f1faaa37da0fc91f943b00fccc96f1e1ff31fbfa741f00bcf30183a5e10f51ab'),
    'phase':(GAME/'tools/phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py','b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'),
}
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')
SOURCE_NAMES=('__init__.py','model.py','config.py','learning_control.py','agent.py','training.py','loss_kernel.py','priority_phase.py')
MODEL_NAMES=('model.py','config.py','learning_control.py','__init__.py')


def require(value,message):
    if not value:raise RuntimeError(message)


def fingerprint(path,limit=4<<20):
    path=Path(path);require(path.is_absolute() and path==path.resolve(strict=True),'Canonical input required')
    def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and
            0<before.st_size<=limit,'Owned bounded input required')
        raw=stream.read(limit+1)
        require(len(raw)==before.st_size and ident(before)==ident(os.fstat(stream.fileno()))==ident(path.lstat()),'Input changed')
    return raw,dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(before))


def pinned(pin,raw_only=False):
    raw,actual=fingerprint(pin['path']);require(actual==pin and actual['identity']['mode']=='0o444','Exact readonly metadata required')
    return raw if raw_only else json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite metadata: '+x)))


def load(name):
    path,sha=DEPS[name];require(isinstance(sha,str) and len(sha)==64,'Unsealed source dependency: '+name)
    raw,pin=fingerprint(path);require(pin['sha256']==sha and pin['identity']['mode']=='0o444','Dependency changed: '+name)
    spec=importlib.util.spec_from_file_location('_prechange_entry_'+name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    require(fingerprint(path)[0]==raw,'Dependency changed during load')
    return module


class EntryHealth:
    """Explicit reuse of pinned concrete IO; historical floor is not entry proof."""
    def __init__(self,driver,ops,files,observer,baseline,owner,env,resources,historical_floor):
        self.driver,self.ops,self.files,self.observer=driver,ops,files,observer
        self.baseline,self.owner,self.env,self.resources=baseline,owner,env,resources
        self.hashes=dict(baseline['source_hashes'],**baseline['control_hashes'])
        self.health_floor_clocks=copy.deepcopy(historical_floor)
        self.expected_exposure=observer.normalise(json.loads(pinned(baseline['actual_API'],raw_only=True)))

    def api(self):return self.driver.Driver.api(self)
    def check_process(self,expected):return self.driver.Driver.check_process(self,expected)
    def check_health(self,label,lr):return self.driver.Driver.check_health(self,label,lr)


def slot_guard(case,files):
    model=GAME/'models_dqn';slot=model/'managed_save.request.json.completed'
    require(not(model/'managed_save.request.json').exists() and not(model/'managed_save.request.json.failed').exists(),
        'Pending or failed managed request; entry never replaces it')
    require(case['completed_slot'] is not None and case['completed_slot']['path']==str(slot) and
        files.fingerprint(slot,4<<20)==case['completed_slot'],'Actual matched completion differs')


def validate(case,output,driver,files):
    fields={'schema','capture_authorized','source_freeze_release','runtime_baseline','readiness',
        'control_before','completed_slot','tag','output_directory','cpu_python'}
    require(set(case)==fields and case['schema']==SCHEMA and case['capture_authorized'] is True,'Explicit exact root capture case required')
    require(output==Path(case['output_directory']) and output.is_absolute() and output==output.resolve(strict=False) and
        output.parent==RUN and not output.exists(),'Fresh direct run26 output required')
    require(type(case['tag']) is str and 0<len(case['tag'])<=80 and all(c.isascii() and (c.isalnum() or c in '_-') for c in case['tag']),
        'Unique entry tag required')
    require(type(case['cpu_python']) is str and Path(case['cpu_python']).is_absolute(),'Root-verified numerical Python argv required')
    release=pinned(case['source_freeze_release']);baseline=pinned(case['runtime_baseline']);ready=pinned(case['readiness'])
    require(release['source_freeze_released'] is True and release['owned_cleanup_complete'] is True and
        release['plan']['sha256']==driver.CURRENT_PLAN and release['binding_job']['sha256']==driver.CURRENT_BINDING and
        type(release['released_unix_s']) in (int,float) and math.isfinite(release['released_unix_s']) and release['released_unix_s']>0,
        'Actual current complete quality release required')
    owner=baseline['main_owner'];maintenance=pinned(baseline['actual_maintenance']);phase=maintenance['startup']['phase']
    original_job=pinned(maintenance['root_job']);record=pinned(phase['record']);boot=pinned(phase['boot_verification'])
    historical=pinned(maintenance['startup']['phase_CPU_readonly_archive'])
    require(maintenance['status']=='READY_CE_FORWARD_REPAIR' and maintenance['owner']==owner and
        phase['record']['sha256']==driver.FOUNDER and phase['expected']['metric']=='ce' and phase['expected']['valid'] is True and
        phase['expected']['founder_phase_record_sha256']==driver.FOUNDER and record['metric']=='ce' and
        record['checkpoint']==phase['boot_checkpoint'] and record['root_precommit_sha256']==phase['expected']['root_precommit_sha256'] and
        boot['status']=='PASS' and boot['sha256']==phase['boot_checkpoint']['sha256'] and boot['bytes']==phase['boot_checkpoint']['bytes'],
        'Genuine unchanged maintenance CE phase/boot required')
    require(historical['status']=='PASS' and historical['phase_metadata_verified'] is True and
        historical['script']['sha256']==DEPS['phase'][1] and
        historical['strict_phase_base']['sha256']=='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8' and
        historical['root_job']['phase_snapshot']['purpose']=='startup' and
        historical['root_job']['phase_snapshot']['observed_clients']==0 and
        historical['root_job']['phase_snapshot']['owner']==owner and historical['root_job']['phase_snapshot']['expected_phase']==phase['expected'],
        'Historical startup CPU is only a truthful clock floor, never live192 entry proof')
    require(historical['root_job']['source_control_context']['held_recipe_context']==
        dict(driver.HELD,learning_control_lr_scale=.5,optimizer_lr=2.5e-5),'Exact historical .5 held recipe required')
    require(case['tag']!=original_job['startup_tag'],'Entry cannot reuse startup tag')
    target=GAME/'models_dqn/managed-checkpoints'/(case['tag']+'.pt')
    require(all(not Path(str(target)+suffix).exists() for suffix in ('','.tmp','.bak')),'Entry source/tmp/bak must be new')
    env=pinned(baseline['actual_selected_environment']);resources=pinned(baseline['actual_main192_resources'])
    control_path=GAME/'models_dqn/learning_control.json'
    require(case['control_before']['path']==str(control_path) and
        (env.get('ROBOTRON_DQN_CONTROL_PATH') or str(control_path))==str(control_path) and
        ((env.get('ROBOTRON_DQN_MODEL_DIR') or '').strip() or str(GAME/'models_dqn'))==str(GAME/'models_dqn'),
        'Actual held default model/control paths required')
    raw_control,control_pin=fingerprint(control_path)
    require(control_pin==case['control_before'] and baseline['control_hashes'][str(control_path)]==control_pin['sha256'],'Current .5 control changed')
    control=json.loads(raw_control,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite control: '+x)))
    require(set(control)<={'experiment','epsilon_ramp','reason','measurement','lr_scale'} and control['lr_scale']==.5 and
        control.get('measurement') is None and control['epsilon_ramp']['start']==control['epsilon_ramp']['end']==.1 and
        type(control['experiment']) is str and 0<len(control['experiment'])<=120 and
        all(c.isascii() and (c.isalnum() or c in '_-') for c in control['experiment']),'Exact current .5 held control required')
    require(len(baseline['source_hashes'])==61 and len(baseline['control_hashes'])==2 and len(baseline['unit_files'])==3 and
        len(baseline['actors'])==192 and env['DQN_BATCH_SIZE']=='4096' and env['DQN_PER_PRIORITY_METRIC']=='ce' and
        env['DQN_PRIORITY_PHASE_RECORD_SHA256']==driver.FOUNDER and env['DQN_PRIORITY_PHASE_RECORD']==phase['record']['path'],
        'Held CE4096 source/environment/192 scope differs')
    by_pid={x['pid']:x for x in baseline['actors']}
    require(resources['owner']==owner and all(resources['main'][k]==owner[k] for k in ('pid','starttime_ticks','cgroup')) and
        all(resources['fleet'][k]==baseline['fleet_owner'][k] for k in ('pid','starttime_ticks','cgroup')) and
        resources['worker']==baseline['inference_worker'] and len(resources['actors'])==192 and len(by_pid)==192 and
        {x['slot'] for x in baseline['actors']}==set(range(192)) and {x['pid'] for x in resources['actors']}==set(by_pid) and
        all(all(a[k]==by_pid[a['pid']][k] for k in ('pid','starttime_ticks','mask')) for a in resources['actors']),
        'Actual main/fleet/worker/original192 resource descriptors differ')
    require(ready['status']=='PASS' and 0<=time.time()-ready['observed_unix_s']<=180 and
        ready['observed_unix_s']>=release['released_unix_s'] and
        all(ready[k]==baseline[k] for k in ('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')) and
        ready['resources']['GPU0_free_bytes']>=14*(1<<30) and all(ready['resources'][k] is True for k in
        ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free','no_competing_helpers',
         'no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released')),'Genuine post-release fresh readiness required')
    require(all(type(historical['clocks'][k]) is int and historical['clocks'][k]>0 for k in CLOCKS),'Historical floor clocks invalid')
    slot_guard(case,files)
    return dict(baseline=baseline,owner=owner,phase=phase,env=env,resources=resources,control=control,
        raw_control=raw_control,startup_tag=original_job['startup_tag'],
        historical_floor={k:historical['clocks'][k] for k in CLOCKS},historical_report=historical)


def build_CPU_job(case,case_pin,context,frozen,floor,snapshot,before_pin,after_pin,files,ops,phase,output):
    directory=output/'metadata';directory.mkdir(mode=0o700);pairs={}
    for name in SOURCE_NAMES:
        current,archive=files.exclusive_copy(GAME/'Scripts/dqn'/name,directory/name)
        pairs[name]=dict(current=current,archive=archive)
    _,control=files.exclusive_copy(case['control_before']['path'],directory/'learning_control.json')
    unit=ops.command(['systemctl','--user','cat',context['owner']['unit']]);require(unit['returncode']==0,'Actual trainer unit cat failed')
    unit_pin=ops.write_bytes(directory/'trainer-unit.txt',unit['stdout'].encode('utf-8','surrogateescape'))
    held=copy.deepcopy(context['historical_report']['root_job']['source_control_context']['held_recipe_context'])
    require(held['learning_control_lr_scale']==.5 and held['optimizer_lr']==2.5e-5 and held['batch_size']==4096,'Held .5 CPU recipe differs')
    current_phase=context['phase']
    job=dict(schema=phase.SCHEMA,verifier_sha256=DEPS['phase'][1],strict_phase_base_sha256=phase.STRICT_SHA256,
        original_strict_base_sha256=phase.ORIGINAL_SHA256,experiment=context['control']['experiment'],
        source=frozen['source'],verification_copy=frozen['verification_copy'],clock_floor=floor,
        source_control_context=dict(game_root=str(GAME),model_dir=str(GAME/'models_dqn'),
            model_package={name:pairs[name]['current'] for name in MODEL_NAMES},archived_control=control,
            archived_trainer_unit=unit_pin,held_recipe_context=held,
            provenance=[case_pin,case['source_freeze_release'],case['runtime_baseline'],case['readiness'],before_pin,after_pin,snapshot.raw_pin]),
        output_directory=str(output/'entry-CPU-output'),phase_snapshot=dict(purpose='candidate',owner=context['owner'],
            observed_clients=192,phase_record=current_phase['record'],boot_checkpoint=current_phase['boot_checkpoint'],
            boot_verification=current_phase['boot_verification'],expected_phase=current_phase['expected'],
            acquisition=frozen['acquisition'],sources=pairs))
    base=phase.load_base();evidence=dict(bound_files={});model=base.check_context(job,evidence)
    phase.check_acquisition(job,base,evidence,model)  # Metadata/source only, no model/tensor load.
    return job


def run(case,case_pin,output,modules):
    driver,ops,capture,snapshot_module,observer,phase=(modules[k] for k in ('driver','ops','capture','snapshot','observer','phase'))
    files=capture.Files(ops);context=validate(case,output,driver,files)
    health=EntryHealth(driver,ops,files,observer,context['baseline'],context['owner'],context['env'],context['resources'],context['historical_floor'])
    raw,api=health.check_health(context['control']['experiment'],2.5e-5);slot_guard(case,files)
    output.mkdir(mode=0o700);files.fsync_directory(output.parent)
    result=dict(schema=RESULT_SCHEMA,status='STARTING',root_case=case_pin,root_precommit=case_pin,
        CPU_executed=False,qualification_pass=False,model_only=True,replay_RNG_actor_anchor=False)
    snapshot=runtime=None
    try:
        before=ops.publish(output/'before-capture-health.json',dict(owner=context['owner'],client_count=192,
            clocks=capture.four(api),observed_unix_s=time.time(),historical_floor=context['historical_floor']))
        local=dict(model_dir=str(GAME/'models_dqn'),experiment=context['control']['experiment'],tag=case['tag'],startup_tag=context['startup_tag'])
        runtime=capture.CaptureRuntime(ops,files,local,context['owner'],health.hashes)
        require(runtime.current_completed==case['completed_slot'],'Runtime cannot adopt a foreign completion')
        adapter=type('SnapshotPrimitives',(),{name:staticmethod(getattr(capture,name)) for name in ('four','triple','request_identity','publish_request')})
        snapshot=snapshot_module.Snapshot(adapter,files,runtime,dict(tag=case['tag'],save_timeout_s=60),output/'capture')
        files.raw_api=raw;files.api=api;floor=capture.four(api);snapshot.start(api,floor)
        while snapshot.state=='PENDING':time.sleep(.2);snapshot.tick()
        require(snapshot.state=='COMPLETE','First entry save failed: '+str(snapshot.error))
        frozen=snapshot.freeze(purpose='candidate',phase=context['phase'])
        after_raw,after_api=health.check_health(context['control']['experiment'],2.5e-5)
        ops.write_bytes(output/'after-capture-API.raw.json',after_raw)
        after=ops.publish(output/'after-capture-health.json',dict(owner=context['owner'],client_count=192,
            clocks=capture.four(after_api),observed_unix_s=time.time()))
        job=build_CPU_job(case,case_pin,context,frozen,floor,snapshot,before,after,files,ops,phase,output)
        runtime.request_guard();require(runtime.current_completed==snapshot.completed,'Final matched completion lost')
        health.check_health(context['control']['experiment'],2.5e-5)
        job_pin=ops.publish(output/'entry-CPU-job.json',job);require(job_pin['bytes']<=1<<20,'CPU job exceeds1MiB')
        completion=ops.publish(output/'capture-completion.json',dict(status='COMPLETE',tag=case['tag'],
            owner_before=snapshot.owner,owner_after=snapshot.owner_after,transition=snapshot.transition,request_publications=runtime.publications))
        result.update(status='CAPTURED_PENDING_ROOT_CPU',owner=context['owner'],current_phase=context['phase'],
            source=frozen['source'],verification_copy=frozen['verification_copy'],acquisition=frozen['acquisition'],trigger_API=snapshot.raw_pin,
            capture_completion=completion,cpu_job=job_pin,candidate_clocks=None,cpu_report=None,cpu_completion=None,
            cpu_argv=[case['cpu_python'],'-Xgil=0','-I','-B',str(DEPS['phase'][0]),'--execute','--job',job_pin['path'],
                '--expected-job-sha256',job_pin['sha256'],'--expected-verifier-sha256',DEPS['phase'][1]])
    except BaseException as error:
        result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),
            snapshot=None if snapshot is None else snapshot.result(),no_retry_or_control_change=True)
    ops.publish(output/'result.json',result);return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--case',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--expected-case-sha256');parser.add_argument('--expected-source-sha256');args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY_UNSELECTED: no reads/imports/requests/CPU/control/actions; future case unbound');return 0
    require(all((args.case,args.output,args.expected_case_sha256,args.expected_source_sha256)),'Explicit pinned case/source and new output required')
    _,source=fingerprint(Path(__file__).resolve());require(source['sha256']==args.expected_source_sha256 and source['identity']['mode']=='0o444','Exact sealed source required')
    raw,case_pin=fingerprint(args.case);require(case_pin['sha256']==args.expected_case_sha256 and case_pin['identity']['mode']=='0o444','Exact readonly case required')
    case=json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite case: '+x)))
    modules={name:load(name) for name in DEPS}
    return 0 if run(case,case_pin,args.output,modules)['status']=='CAPTURED_PENDING_ROOT_CPU' else 1


if __name__=='__main__':raise SystemExit(main())
