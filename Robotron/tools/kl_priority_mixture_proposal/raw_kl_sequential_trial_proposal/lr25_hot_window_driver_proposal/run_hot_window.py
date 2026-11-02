"""UNSELECTED root-owned hot LR window; no owner/actor/CPU lifecycle.

Default PLAN has no reads. Future explicit root job requires fresh .5 entry CPU,
closed current quality and readiness. This driver saves a barrier and one .25
endpoint, seals the exact CPU job/context, restores only original control bytes,
and leaves the single retained numeric execution to root. No model restoration.
"""
import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import traceback
import urllib.request

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
Q=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
SCHEMA='robotron-root-lr25-hot-window-driver-job-v1'
CURRENT_PLAN='fdb13f963f7433d8dcd816934fe266f327760a7953d47a1208f752f284d5fe85'
CURRENT_BINDING='25bde9295865770d9a0317ad32a65efa464abb3f71ec3d68f8adc0c8978eeb5b'
FOUNDER='9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1'
CLOCKS=('training_steps','optimized_samples','frame_count','learner_frame_count')
SOURCE_NAMES=('__init__.py','model.py','config.py','learning_control.py','agent.py','training.py','loss_kernel.py','priority_phase.py')
MODEL_NAMES=('model.py','config.py','learning_control.py','__init__.py')
STRICT_SHA='0854f1437510a4264bc922d241e76350ee3209963bd4f28ce9b8a826e6cb159b'
CPU_SHA='d73b7381adc6405af41cdfcaa910ec1f444bc66935616f6f94e6e804faad0b5f'
ORIGINAL_STRICT_SHA='7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
HELD=dict(batch_size=4096,baseline_batch_size=512,epsilon=.1,expert_ratio=.1,n_step=3,
    max_samples_per_frame=8,c51_target_smoothing=0,learning_control_lr_scale=.25,lr_gear='climb',
    lr_anchor_step=0.,optimizer_lr=1.25e-5,optimizer_eps=1.5e-4,fused=True,gamma=.995,
    num_atoms=51,v_min=-10.,v_max=50.)
# Source/JSON only. The driver never loads a numerical verifier into its process.
DEPENDENCIES={
    'ops':dict(path=str(RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'),sha256='d525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'),
    'capture':dict(path=str(Q/'recovered_live_ce_candidate_capture_proposal/capture_live_CE_candidate.py'),sha256='7be0eaf012e208299548f131fd42651239740692d58b8a6d997a6eee6733e46c'),
    'snapshot':dict(path=str(Q/'live_one_trial_installed_ce_revision2_proposal/early_insurance.py'),sha256='0112da455fd0c3c7b711cda2ff59f8575a637f2544ec37f9ad68ad2698b0dab4'),
    'observer':dict(path=str(Q/'lr25_hot_window_observer_proposal/hot_window_observer.py'),sha256='f1faaa37da0fc91f943b00fccc96f1e1ff31fbfa741f00bcf30183a5e10f51ab'),
    'CPU':dict(path=str(Q/'lr25_phase_cpu_verifier_proposal/verify_phase_snapshot_lr25.py'),sha256=CPU_SHA),
    'strict':dict(path=str(Q/'lr25_phase_cpu_verifier_proposal/strict_phase_base_lr25.py'),sha256=STRICT_SHA),
}


def require(value,message):
    if not value:raise RuntimeError(message)


def fingerprint(path,limit=4<<20):
    path=Path(path)
    require(path.is_absolute() and path==path.resolve(strict=True),'Canonical input required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
        before=os.fstat(f.fileno())
        def identity(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,stat.S_IMODE(s.st_mode),s.st_uid,s.st_nlink)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and
            0<before.st_size<=limit,'Owned bounded input required')
        raw=f.read(limit+1)
        require(len(raw)==before.st_size and identity(before)==identity(os.fstat(f.fileno()))==identity(path.lstat()),'Input changed')
    observed=dict(device=before.st_dev,inode=before.st_ino,bytes=before.st_size,mtime_ns=before.st_mtime_ns,
        ctime_ns=before.st_ctime_ns,mode=oct(stat.S_IMODE(before.st_mode)),uid=before.st_uid,nlink=before.st_nlink)
    return raw,dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=observed)


def pinned(pin,*,raw_only=False):
    raw,actual=fingerprint(pin['path'])
    require(actual==pin and actual['identity']['mode']=='0o444','Exact full readonly prerequisite required')
    return raw if raw_only else json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite strict metadata: '+x)))


def load(key):
    pin=DEPENDENCIES[key];raw,actual=fingerprint(pin['path'])
    require(actual['sha256']==pin['sha256'] and stat.S_IMODE(Path(pin['path']).lstat().st_mode)==0o444,'Selected dependency changed')
    spec=importlib.util.spec_from_file_location('_root_hot_lr_'+key,pin['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    require(fingerprint(pin['path'])[0]==raw,'Dependency changed while loading')
    return module


def clock():
    return dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),monotonic_s=time.monotonic(),wall_s=time.time())


class Driver:
    def __init__(self,job,job_pin,ops,capture,snapshot,observer):
        self.job,self.job_pin,self.ops,self.capture,self.snapshot,self.observer=job,job_pin,ops,capture,snapshot,observer
        self.files=capture.Files(ops);self.out=Path(job['output_directory'])
        self.pre=pinned(job['precommit']);self.baseline=pinned(job['runtime_baseline']);self.readiness=pinned(job['readiness'])
        self.owner=self.pre['owner'];self.phase=self.pre['current_phase'];self.entry=pinned(self.pre['entry_CPU'])
        self.health_floor_clocks=copy.deepcopy(self.entry['clocks'])
        self.env=pinned(self.baseline['actual_selected_environment'])
        self.resources=pinned(self.baseline['actual_main192_resources'])
        self.before_raw,self.before_pin=fingerprint(job['control_before']['path'])
        require(all(self.before_pin[k]==job['control_before'][k] for k in self.before_pin),'Active before control differs')
        self.before=json.loads(self.before_raw);self.control_pin=copy.deepcopy(job['control_before'])
        self.hashes=dict(self.baseline['source_hashes'],**self.baseline['control_hashes'])
        self.expected_completed=copy.deepcopy(job['completed_slot'])
        self.pending=None;self.runtime=None;self.control_changed=False;self.restored=False;self.count=0

    def validate(self):
        job=self.job;pre=self.pre;baseline=self.baseline
        require(set(job)=={'schema','activation_authorized','precommit','runtime_baseline','readiness',
            'control_before','completed_slot','startup_tag','tags','window','output_directory'} and
            job['schema']==SCHEMA and job['activation_authorized'] is True,'Explicit root-authorized job required')
        require(self.out.is_absolute() and self.out==self.out.resolve(strict=False) and self.out.parent==RUN and not self.out.exists(),'NEW direct run26 output required')
        require(set(pre)=={'schema','status','experiment','owner','current_phase','entry_checkpoint','entry_CPU',
            'source_freeze_release','quality_closed','lr_scale_before','lr_scale_after','optimizer_lr_before',
            'optimizer_lr_after','no_weight_or_optimizer_reset','no_replay_clear'} and
            pre['schema']=='robotron-live-CE-lr25-hot-change-precommit-v1' and
            pre['status']=='ROOT_PRECOMMITTED_AFTER_QUALITY_CLOSURE_AND_FREEZE_RELEASE' and pre['quality_closed'] is True and
            pre['no_weight_or_optimizer_reset'] is True and pre['no_replay_clear'] is True and
            pre['lr_scale_before']==.5 and pre['lr_scale_after']==.25 and
            pre['optimizer_lr_before']==2.5e-5 and pre['optimizer_lr_after']==1.25e-5,'Exact hot-change precommit required')
        require(type(pre['experiment']) is str and 0<len(pre['experiment'])<=120 and
            all(c.isascii() and (c.isalnum() or c in '_-') for c in pre['experiment']),
            'Future experiment label must fit the exact CPU/observer schema BEFORE mutation')
        require(self.phase['expected']['founder_phase_record_sha256']==FOUNDER and self.phase['expected']['metric']=='ce' and
            self.phase['expected']['valid'] is True and self.phase['record']['sha256']==FOUNDER and baseline['main_owner']==self.owner,'Actual unchanged CE9b3 owner required')
        record=pinned(self.phase['record']);boot=pinned(self.phase['boot_verification'])
        maintenance=pinned(baseline['actual_maintenance']);maintenance_job=pinned(maintenance['root_job'])
        require(maintenance['status']=='READY_CE_FORWARD_REPAIR' and maintenance['owner']==self.owner and
            maintenance['startup']['phase']['expected']==self.phase['expected'] and
            maintenance['startup']['phase']['record']==self.phase['record'] and
            maintenance['startup']['phase']['boot_checkpoint']==self.phase['boot_checkpoint'] and
            job['startup_tag']==maintenance_job['startup_tag'],'Genuine current phase/startup tag required')
        original_boot=maintenance['startup']['phase']['boot_verification']
        require(boot['status']=='PASS' and boot['sha256']==self.phase['boot_checkpoint']['sha256'] and
            boot['bytes']==self.phase['boot_checkpoint']['bytes'] and
            all(original_boot[k]==self.phase['boot_verification'][k] for k in ('sha256','bytes')) and
            record['metric']=='ce' and record['checkpoint']==self.phase['boot_checkpoint'] and
            record['root_precommit_sha256']==self.phase['expected']['root_precommit_sha256'],'Actual unchanged phase/boot bytes differ')
        release=pinned(pre['source_freeze_release'])
        require(release['source_freeze_released'] is True and release['owned_cleanup_complete'] is True and
            release['plan']['sha256']==CURRENT_PLAN and release['binding_job']['sha256']==CURRENT_BINDING,
            'Actual current fdb13/25b closure/freeze release required; historical releases do not qualify')
        require(self.entry['schema']=='robotron-phase-snapshot-checkpoint-CPU-result-v1' and
            self.entry['root_job']['schema']=='robotron-phase-snapshot-checkpoint-CPU-job-v1' and
            self.entry['status']=='PASS' and self.entry['phase_metadata_verified'] is True and
            self.entry['script']['sha256']=='b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519' and
            self.entry['strict_phase_base']['sha256']=='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8' and
            self.entry['held_recipe_context']==dict(HELD,learning_control_lr_scale=.5,optimizer_lr=2.5e-5) and
            self.entry['root_job']['source_control_context']['held_recipe_context']==dict(HELD,learning_control_lr_scale=.5,optimizer_lr=2.5e-5) and
            self.entry['root_job']['phase_snapshot']['purpose']=='candidate' and
            self.entry['root_job']['phase_snapshot']['observed_clients']==192 and
            self.entry['root_job']['phase_snapshot']['owner']==self.owner and
            self.entry['root_job']['phase_snapshot']['expected_phase']==self.phase['expected'] and
            pre['entry_checkpoint']==self.capture.triple(self.entry['root_job']['source']) and
            self.entry['saved_priority_metric_phase']['metric']=='ce' and
            self.entry['saved_priority_metric_phase']['valid'] is True and
            self.entry['saved_priority_metric_phase']['phase_record_sha256']==FOUNDER and
            self.entry['sha256']==pre['entry_checkpoint']['sha256'] and self.entry['bytes']==pre['entry_checkpoint']['bytes'],
            'Fresh genuine live192 b2e/.5 entry CPU required')
        entry_control=pinned(self.entry['root_job']['source_control_context']['archived_control'])
        require(entry_control==self.before and self.entry['root_job']['source_control_context']['archived_control']['sha256']==self.before_pin['sha256'],
            'Fresh .5 entry control bytes/values differ from the actual before boundary')
        entry_acquisition=pinned(self.entry['root_job']['phase_snapshot']['acquisition'])
        require(entry_acquisition['purpose']=='candidate' and entry_acquisition['client_count']==192 and
            entry_acquisition['owner_before']==entry_acquisition['owner_after']==self.owner and
            entry_acquisition['completed_slot_transition']['request_unix_s']>=release['released_unix_s'],
            'Entry must be a genuine post-quality-release live request, not a historical owner proof')
        require(set(job['tags'])=={'barrier','endpoint'} and len(set(job['tags'].values()))==2 and
            all(type(tag) is str and 0<len(tag)<=80 and all(c.isascii() and (c.isalnum() or c in '_-') for c in tag)
                for tag in job['tags'].values()),'Two unique predeclared snapshot tags required')
        for tag in job['tags'].values():
            require(tag!=job['startup_tag'] and tag!=Path(pre['entry_checkpoint']['path']).stem and
                all(not Path(str(GAME/'models_dqn/managed-checkpoints'/(tag+'.pt'))+suffix).exists()
                    for suffix in ('','.tmp','.bak')),'All future stage tags/paths must be new BEFORE control mutation')
        require(self.before['lr_scale']==.5 and self.before.get('measurement') is None and
            self.before['epsilon_ramp']['start']==self.before['epsilon_ramp']['end']==.1 and
            pre['experiment']!=self.before['experiment'],'Only new label/.25 over exact held .5 control allowed')
        require(job['control_before']['path']==str(GAME/'models_dqn/learning_control.json') and
            (self.env.get('ROBOTRON_DQN_CONTROL_PATH') or str(GAME/'models_dqn/learning_control.json'))==job['control_before']['path'] and
            ((self.env.get('ROBOTRON_DQN_MODEL_DIR') or '').strip() or str(GAME/'models_dqn'))==str(GAME/'models_dqn'),
            'Only the actual held default model control path may be changed')
        require(len(baseline['actors'])==192 and len(baseline['source_hashes'])==61 and len(baseline['control_hashes'])==2 and
            len(baseline['unit_files'])==3 and self.env['DQN_BATCH_SIZE']=='4096' and self.env['DQN_PER_PRIORITY_METRIC']=='ce' and
            self.env['DQN_PRIORITY_PHASE_RECORD_SHA256']==FOUNDER and
            self.env['DQN_PRIORITY_PHASE_RECORD']==self.phase['record']['path'],'Actual4096/192 held maps required')
        expected_actors={x['pid']:x for x in baseline['actors']}
        require(self.resources['owner']==self.owner and self.resources['main']['pid']==self.owner['pid'] and
            self.resources['main']['starttime_ticks']==self.owner['starttime_ticks'] and
            self.resources['main']['cgroup']==self.owner['cgroup'] and
            all(self.resources['fleet'][k]==baseline['fleet_owner'][k] for k in ('pid','starttime_ticks','cgroup')) and
            self.resources['worker']==baseline['inference_worker'] and len(self.resources['actors'])==192 and
            {x['pid'] for x in self.resources['actors']}==set(expected_actors) and all(
            all(actor[key]==expected_actors[actor['pid']][key] for key in ('pid','starttime_ticks','mask'))
            for actor in self.resources['actors']),'Pinned process-resource descriptors do not join actual192 baseline')
        ready=self.readiness
        require(ready['status']=='PASS' and 0<=time.time()-ready['observed_unix_s']<=180 and
            ready['observed_unix_s']>=self.pre['entry_CPU']['identity']['mtime_ns']/1e9 and
            ready['observed_unix_s']>=entry_acquisition['completed_slot_transition']['after_unix_s'] and
            all(ready[k]==baseline[k] for k in ('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')) and
            ready['resources']['GPU0_free_bytes']>=14*(1<<30) and all(ready['resources'][k] is True for k in
            ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free','no_competing_helpers',
             'no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released')),'Fresh root entry/exclusive readiness required')
        require(set(job['window'])=={'policy','preparation_timeout_s'} and
            type(job['window']['preparation_timeout_s']) in (int,float) and math.isfinite(job['window']['preparation_timeout_s']) and
            job['window']['preparation_timeout_s']>0,'Future bounded preparation budget required')
        policy=job['window']['policy']
        require(set(policy)==set(self.observer.POLICY)|{'cutoff_s'} and all(type(policy[k]) is type(v) and policy[k]==v
            for k,v in self.observer.POLICY.items()) and type(policy['cutoff_s']) in (int,float) and
            math.isfinite(policy['cutoff_s']) and policy['cutoff_s']>0,'Exact future cutoff/policy required BEFORE control mutation')
        reference=pinned(baseline['actual_API'],raw_only=True)
        self.expected_exposure=self.observer.normalise(json.loads(reference))
        self.check_health(self.before['experiment'],2.5e-5)
        self.slot_guard()

    def publish(self,name,value):return self.ops.publish(self.out/name,value)

    def api(self):
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:raw=response.read((2<<20)+1)
        require(0<len(raw)<=2<<20,'Raw API exceeds bound')
        return raw,json.loads(raw)

    def check_process(self,expected):
        p=Path('/proc',str(expected['pid']));start=self.ops.process_start(expected['pid'])
        require(start==expected['starttime_ticks'],'Owned process incarnation changed')
        require([os.fsdecode(x) for x in (p/'cmdline').read_bytes().split(b'\0') if x]==expected['argv'] and
            os.readlink(p/'cwd')==expected['cwd'] and os.readlink(p/'exe')==expected['exe'] and
            sorted(os.sched_getaffinity(expected['pid']))==expected['mask'],'Owned command/cwd/exe/mask changed')
        status=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
        require([int(x) for x in status['Uid'].split()]==[os.getuid()]*4==expected['uid'] and
            expected['cgroup'] in [line.split(':',2)[2] for line in (p/'cgroup').read_text().splitlines()] and
            self.ops.process_start(expected['pid'])==start,'Owned UID/cgroup/start bracket changed')

    def check_health(self,label=None,lr=None):
        for owner in (self.owner,self.baseline['fleet_owner']):
            state,_=self.ops.show(owner['unit'])
            require(state['MainPID']==str(owner['pid']) and state['InvocationID']==owner['invocation_id'] and
                state['ControlGroup']==owner['cgroup'] and state['ActiveState']=='active' and state['SubState']=='running' and
                state['NRestarts']=='0' and self.ops.process_start(owner['pid'])==owner['starttime_ticks'],'Owner/fleet changed')
            if owner==self.owner:require(state['Restart']=='no','Trainer restart policy changed')
        for expected in [self.resources['main'],self.resources['fleet'],*self.resources['actors']]:self.check_process(expected)
        worker=self.baseline['inference_worker'];thread=Path('/proc',str(self.owner['pid']),'task',str(worker['tid']))
        require(thread.exists() and self.ops.process_start(worker['tid'])==worker['starttime_ticks'] and
            sorted(os.sched_getaffinity(worker['tid']))==worker['mask'],'Inference thread changed')
        thread_status=dict(line.split(':',1) for line in (thread/'status').read_text().splitlines() if ':' in line)
        require([int(x) for x in thread_status['Uid'].split()]==[os.getuid()]*4,'Inference UID changed')
        env=dict(os.fsdecode(x).split('=',1) for x in Path('/proc',str(self.owner['pid']),'environ').read_bytes().split(b'\0') if b'=' in x)
        selected={k:v for k,v in env.items() if k.startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_'))}
        require(selected==self.env,'Held selected environment changed')
        for path,sha in dict(self.hashes,**self.baseline['unit_files']).items():
            require(self.files.fingerprint(path,4<<20)['sha256']==sha,'Held source/control/unit changed: '+path)
        gpu=self.ops.command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'])
        require(gpu['returncode']==0 and [(int(x.split(',')[0]),x.split(',')[1].strip()) for x in gpu['stdout'].splitlines() if x.strip()]
            ==[(self.owner['pid'],self.ops.GPU_UUIDS[1])],'GPU0 not empty or main not sole GPU1 owner')
        memory=self.ops.command(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
        require(memory['returncode']==0 and dict((r.split(',')[0].strip(),int(r.split(',')[1])) for r in memory['stdout'].splitlines() if r.strip())
            [self.ops.GPU_UUIDS[0]]>=14*1024,'GPU0 free memory below held margin')
        for table in ('tcp','tcp6'):
            for line in Path('/proc/net',table).read_text().splitlines()[1:]:
                row=line.split();require(not(row[3]=='0A' and int(row[1].rsplit(':',1)[1],16)==9999),'Private9999 listener appeared')
        require(not any(p.is_dir() for p in Path('/dev/shm').glob('robotron-snapshot-smoke-*')),'Private tmpfs appeared')
        lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');before=lease.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid(),'Existing lease identity changed')
        fd=os.open(lease,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            require(self.ops.identity(os.fstat(fd))==self.ops.identity(before)==self.ops.identity(lease.lstat()),'Lease open race')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:os.close(fd)
        raw,api=self.api();pipeline=api['host_pipeline'];graphs=pipeline['inference_graphs']
        require(api['client_count']==192 and type(api['client_count']) is int and api['training_enabled'] is True and
            api['measurement_active'] is False and 0<=time.time()-api['ts']<=5 and
            0<=api['pipeline_snapshot_age_s']<=5 and not api['pipeline_read_error'] and
            graphs['ready'] is True and graphs['capture_count']==128 and graphs['validation_replay_count']==640 and
            graphs['postload_validations']>=1 and
            graphs['runtime_capture_count']==graphs['fallback_count']==0 and graphs['fatal_error'] is None and
            all(pipeline[k]['errors']==0 for k in ('inference','actor_refresh','target_refresh','learner_priority')),
            'Current API/graphs/four errors differs')
        current=self.observer.normalise(api)
        require(all(current[k]==self.expected_exposure[k] for k in ('optimizer_identity','replay_identity')) and
            current['optimizer']['unavailable']==0 and all(api[k]>=self.health_floor_clocks[k] for k in CLOCKS),'Exposure/authenticated health floor changed')
        if label is not None:require(api['managed_experiment']==label,'Managed label differs')
        if lr is not None:require(api['lr']==lr,'Scheduled LR differs')
        return raw,api

    def replace_control(self,raw,name):
        path=Path(self.job['control_before']['path']);expected=self.control_pin
        self.slot_guard()
        require(self.files.fingerprint(path)==expected,'Expected current control changed before transaction')
        self.publish(name+'-intent.json',dict(expected=expected,target_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
        fd,temp=tempfile.mkstemp(prefix='.root-hot-lr-',dir=path.parent);temporary=Path(temp);created=os.fstat(fd)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(raw);stream.flush();os.fchmod(stream.fileno(),int(expected['identity']['mode'],8));os.fsync(stream.fileno())
            require(self.files.fingerprint(path)==expected,'Current control changed across owned preparation')
            prepared=self.files.fingerprint(temporary)
            require((prepared['identity']['device'],prepared['identity']['inode'])==(created.st_dev,created.st_ino) and
                prepared['sha256']==hashlib.sha256(raw).hexdigest(),'Owned prepared control was replaced')
            os.replace(temporary,path);self.files.fsync_directory(path.parent)
            actual=self.files.fingerprint(path)
            require(actual['sha256']==hashlib.sha256(raw).hexdigest() and actual['bytes']==len(raw),'Control readback differs')
            self.control_pin=actual;self.hashes[str(path)]=actual['sha256']
            _,archive=self.files.exclusive_copy(path,self.out/(name+'-readonly.json'))
            self.publish(name+'-receipt.json',dict(before=expected,after=actual,archive=archive,completed_clock=clock()))
            return archive
        finally:
            # Only our still-unpublished private temporary, never request/control.
            if temporary.exists():
                info=temporary.lstat()
                require((info.st_dev,info.st_ino)==(created.st_dev,created.st_ino),'Foreign temporary path is never removed')
                temporary.unlink()

    def slot_guard(self):
        model=GAME/'models_dqn';slot=model/'managed_save.request.json.completed'
        require(not(model/'managed_save.request.json').exists() and not(model/'managed_save.request.json.failed').exists() and
            (self.files.fingerprint(slot,4<<20) if slot.exists() else None)==self.expected_completed,
            'No control transaction across foreign/unmatched request or completion')

    def save(self,stage,raw,api,floor):
        self.check_health(self.pre['experiment'],1.25e-5)
        slot=GAME/'models_dqn/managed_save.request.json.completed'
        actual=self.files.fingerprint(slot,4<<20) if slot.exists() else None
        require(actual==self.expected_completed,'Current completion changed before declared stage')
        request_job=dict(model_dir=str(GAME/'models_dqn'),experiment=self.pre['experiment'],
            startup_tag=self.job['startup_tag'],tag=self.job['tags'][stage])
        require(self.job['tags'][stage]!=Path(self.pre['entry_checkpoint']['path']).stem,'Entry tag cannot be reused')
        runtime=self.capture.CaptureRuntime(self.ops,self.files,request_job,self.owner,self.hashes)
        require(runtime.current_completed==self.expected_completed,'Constructor cannot adopt a foreign completion')
        adapter=type('SnapshotPrimitives',(),{name:staticmethod(getattr(self.capture,name))
            for name in ('four','triple','request_identity','publish_request')})
        self.runtime=runtime
        snapshot=self.snapshot.Snapshot(adapter,self.files,runtime,dict(tag=self.job['tags'][stage],save_timeout_s=60),self.out/stage)
        self.files.raw_api=raw;self.files.api=api
        snapshot.start(api,floor);self.pending=snapshot
        while snapshot.state=='PENDING':time.sleep(.2);snapshot.tick()
        require(snapshot.state=='COMPLETE','First '+stage+' save failed: '+str(snapshot.error))
        frozen=snapshot.freeze(purpose='candidate',phase=self.phase)
        runtime.request_guard();require(runtime.current_completed==snapshot.completed,'Actual matched completion lost')
        self.expected_completed=copy.deepcopy(snapshot.completed);self.pending=None
        self.check_health(self.pre['experiment'],1.25e-5)
        return snapshot,frozen

    def endpoint_context(self,snapshot,frozen,floor):
        directory=self.out/'endpoint-context';directory.mkdir(mode=0o700)
        pairs={}
        for name in SOURCE_NAMES:
            current,archive=self.files.exclusive_copy(GAME/'Scripts/dqn'/name,directory/name)
            pairs[name]=dict(current=current,archive=archive)
        _,control=self.files.exclusive_copy(self.control_pin['path'],directory/'learning_control.json')
        unit=self.ops.command(['systemctl','--user','cat',self.owner['unit']]);require(unit['returncode']==0,'Trainer cat failed')
        unit_pin=self.ops.write_bytes(directory/'trainer-unit.txt',unit['stdout'].encode('utf-8','surrogateescape'))
        context=dict(game_root=str(GAME),model_dir=str(GAME/'models_dqn'),model_package={n:pairs[n]['current'] for n in MODEL_NAMES},
            archived_control=control,archived_trainer_unit=unit_pin,held_recipe_context=HELD,
            provenance=[self.job_pin,self.job['precommit'],self.job['readiness'],self.job['runtime_baseline'],snapshot.raw_pin,
                snapshot.transition['request']['archive'],snapshot.transition['after']['archive'],self.phase['record'],self.phase['boot_verification']])
        spec=dict(purpose='candidate',owner=self.owner,observed_clients=192,phase_record=self.phase['record'],
            boot_checkpoint=self.phase['boot_checkpoint'],boot_verification=self.phase['boot_verification'],
            expected_phase=self.phase['expected'],acquisition=frozen['acquisition'],sources=pairs)
        cpu_job=dict(schema='robotron-lr25-phase-snapshot-checkpoint-CPU-job-v1',verifier_sha256=CPU_SHA,
            strict_phase_base_sha256=STRICT_SHA,original_strict_base_sha256=ORIGINAL_STRICT_SHA,experiment=self.pre['experiment'],
            source=frozen['source'],verification_copy=frozen['verification_copy'],clock_floor=floor,source_control_context=context,
            output_directory=str(self.out/'endpoint-CPU-output'),phase_snapshot=spec,
            lr25_context=dict(schema='robotron-live-CE-lr25-hot-control-context-v1',precommit=self.job['precommit'],entry_CPU=self.pre['entry_CPU']))
        self.runtime.request_guard();self.check_health(self.pre['experiment'],1.25e-5)
        result=self.publish('endpoint-CPU-job.json',cpu_job)
        require(result['bytes']<=1<<20,'Root phase CPU job exceeds frozen1MiB limit')
        return result

    def run(self):
        self.validate();self.out.mkdir(mode=0o700);self.files.fsync_directory(self.out.parent)
        self.publish('intent.json',dict(root_job=self.job_pin,owner=self.owner,precommit=self.job['precommit'],no_owner_stop=True,no_CPU_launch=True))
        result=dict(status='STARTING',root_job=self.job_pin,owner=self.owner,qualification_pass=False,CPU_executed=False)
        try:
            result['original_control_archive']=self.ops.write_bytes(self.out/'original-control-readonly.json',self.before_raw)
            new=dict(self.before,experiment=self.pre['experiment'],lr_scale=.25)
            self.replace_control((json.dumps(new,indent=2,allow_nan=False)+'\n').encode(),'control25');self.control_changed=True
            deadline=time.monotonic()+self.job['window']['preparation_timeout_s']
            while True:
                raw,api=self.check_health()
                if api['managed_experiment']==self.pre['experiment'] and api['lr']==1.25e-5:break
                require(time.monotonic()<deadline,'First .25 control refresh timed out');time.sleep(.2)
            barrier,barrier_frozen=self.save('barrier',raw,api,{k:max(api[k],self.entry['clocks'][k]) for k in CLOCKS})
            barrier_clock=clock();self.publish('barrier.json',dict(frozen=barrier_frozen,completed_clock=barrier_clock))
            require(time.monotonic()<=deadline,'First barrier exceeded preparation budget')
            while True:
                raw,api=self.check_health(self.pre['experiment'],1.25e-5);now=clock();current=self.observer.normalise(api)
                if current['unclassified']==0 and api['ts']-api['pipeline_snapshot_age_s']>=barrier_clock['wall_s']:
                    require(time.monotonic()<=deadline,'First B exceeded preparation budget');break
                require(time.monotonic()<deadline,'First post-barrier B timed out');time.sleep(.2)
            baseline_pin=self.ops.write_bytes(self.out/'raw-B-API.json',raw)
            window=dict(schema=self.observer.SCHEMA,experiment=self.pre['experiment'],owner=self.owner,recipe=self.observer.RECIPE,
                current_phase=self.phase,proofs=dict(root_precommit=self.job_pin,control_after=self.files.fingerprint(self.out/'control25-readonly.json'),
                entry_CPU=self.pre['entry_CPU'],barrier=self.files.fingerprint(self.out/'barrier.json')),
                barrier_completed_clock=barrier_clock,baseline=dict(api=baseline_pin,observed_clock=now),policy=self.job['window']['policy'])
            self.observer.validate_job(window,api);window_pin=self.publish('window-job.json',window)
            B=copy.deepcopy(api)
            journal=self.observer.ReceiptJournal(publish=lambda path,value:self.ops.write_bytes(path,self.observer.encoded(value)),get_clock=clock,root=self.out/'observations',job=window)
            journal.root.mkdir(mode=0o700)
            def evidence():
                self.check_health(self.pre['experiment'],1.25e-5)
                return dict(ok=True,owner=self.owner,actor_count=192,selected_control_sha256=self.control_pin['sha256'])
            outcome=self.observer.poll(window,baseline_api=api,get_owner=self.runtime.trainer_id,
                get_evidence=evidence,get_api=lambda:self.check_health(self.pre['experiment'],1.25e-5)[1],
                get_clock=clock,sleep=time.sleep,emit=journal.emit)
            outcome_pin=self.ops.write_bytes(self.out/'window-result-with-raw-API.json',self.observer.encoded(outcome))
            result.update(window_job=window_pin,window_result=outcome_pin,window_status=outcome['status'])
            if outcome['candidate_requests_allowed']==1:
                latch=outcome['observation']['first_eligible_observation'];raw,api=self.check_health(self.pre['experiment'],1.25e-5)
                floor={k:max(self.entry['clocks'][k],B[k],latch[k]) for k in CLOCKS}
                endpoint,frozen=self.save('endpoint',raw,api,floor)
                result.update(endpoint=frozen,endpoint_CPU_job=self.endpoint_context(endpoint,frozen,floor))
            self.check_health(self.pre['experiment'],1.25e-5)
            require(self.pending is None,'No matched pending completion; no restoration claim')
            self.replace_control(self.before_raw,'control50-restored');self.restored=True
            restored_deadline=time.monotonic()+self.job['window']['preparation_timeout_s']
            while True:
                _,restored=self.check_health()
                if restored['managed_experiment']==self.before['experiment'] and restored['lr']==2.5e-5:break
                require(time.monotonic()<restored_deadline,'Restored .5 control not yet visible');time.sleep(.2)
            result.update(status='CAPTURED_PENDING_ROOT_CPU' if 'endpoint' in result else
                ('NO_ELIGIBLE_CANDIDATE' if outcome['status']=='INCOMPLETE' else 'INVALID_WINDOW'),
                original_control_bytes_restored=True,CPU_must_run_separately=True,no_owner_stop_or_model_restore=True)
        except BaseException as error:
            result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),
                original_control_bytes_restored=self.restored,manual_control_review_required=True,
                observed_control_pin=self.control_pin,pending=None if self.pending is None else self.pending.result())
        self.publish('result.json',result)
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY_UNSELECTED: fresh root prerequisites/job/control/B/cutoff unbound; no reads/imports/actions')
        return 0
    require(args.job is not None and args.expected_job_sha256 and args.expected_source_sha256,'Explicit root job/source required')
    _,self_pin=fingerprint(Path(__file__).resolve());require(self_pin['sha256']==args.expected_source_sha256 and
        self_pin['identity']['mode']=='0o444','Driver source differs or is unsealed')
    raw,jp=fingerprint(args.job);require(jp['sha256']==args.expected_job_sha256 and stat.S_IMODE(args.job.lstat().st_mode)==0o444,'Readonly exact root job required')
    job=json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite job: '+x)))
    for key,pin in DEPENDENCIES.items():require(fingerprint(pin['path'])[1]['sha256']==pin['sha256'],'Dependency source differs: '+key)
    driver=Driver(job,jp,load('ops'),load('capture'),load('snapshot'),load('observer'))
    return 0 if driver.run()['status'] in ('CAPTURED_PENDING_ROOT_CPU','NO_ELIGIBLE_CANDIDATE') else 1


if __name__=='__main__':raise SystemExit(main())
