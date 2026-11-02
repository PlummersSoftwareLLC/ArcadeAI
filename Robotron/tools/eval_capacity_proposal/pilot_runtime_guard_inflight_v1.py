"""CPU-only preflight, continuous main witnesses and one original pilot review.

Loaded only by the authenticated original-pilot controller. No work occurs on
import. Missing preceding quality closures reject before directories/queries.
"""
import copy
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
PROTECTOR=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
PROTECTOR_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
SLOTS=list(range(4096,4128))


def require(value,message):
    if not value:raise ValueError(message)


def process_start(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def unit_fields(unit):
    result=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=10)
    require(result.returncode==0,'Original unit observation failed')
    return dict(row.split('=',1) for row in result.stdout.splitlines() if '=' in row)


def read_API():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:return json.load(response)


def reader_module():
    require(hashlib.sha256(PROTECTOR.read_bytes()).hexdigest()==PROTECTOR_SHA,'Immutable evidence reader differs')
    spec=importlib.util.spec_from_file_location('_pilot_guard_reader_'+str(time.time_ns()),PROTECTOR)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def idle_GPU(review_job,plan):
    lease=Path(review_job['lease_path']);info=lease.lstat()
    require(str(lease)=='/dev/shm/robotron-snapshot-smoke-gpu0.lock' and lease.resolve(strict=True)==lease
        and info.st_uid==os.getuid() and info.st_nlink==1
        and dict(device=info.st_dev,inode=info.st_ino)==review_job['lease_identity'],
        'Canonical private GPU lease identity differs')
    for name in ('tcp','tcp6'):
        for line in Path('/proc/net',name).read_text().splitlines()[1:]:
            fields=line.split()
            require(not (fields[3]=='0A' and int(fields[1].rsplit(':',1)[1],16)==9999),
                'Private port9999 is still in use')
    with lease.open('rb') as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            value=subprocess.run(['nvidia-smi','--id='+plan['job']['gpu_uuid'],'--query-compute-apps=pid',
                '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
            require(value.returncode==0 and not value.stdout.strip(),'Private GPU users remain or query failed')
        finally:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def load_and_preflight(config,reader):
    require(set(config)=={'unit','output','argv','properties','pins','observation_s','guard_source','pilot_controller_job'},
        'Exact original controller config fields required')
    reader.read_pin(config['guard_source'],as_json=False)
    require(config['guard_source']==reader.pin(Path(__file__).resolve()),'Selected guard source differs')
    job=reader.read_pin(config['pilot_controller_job'])
    require(job['schema']=='robotron-original-capacity-pilot-control-job-v1','Exact pilot control job required')
    selected=reader.read_pin(job['reviewer_selection'])
    reviewer=reader.checked_module('_pilot_guard_review_'+str(time.time_ns()),selected['source'])
    review_job=reader.read_pin(selected['job']);ready=reader.read_pin(review_job['readiness_amendment'])
    def read(entry,as_json=True):return reader.read_pin(entry,as_json=as_json)
    preceding={}
    # These files cannot exist until the complete original current quality job
    # and current reviewed4 observer have ended and completed owned release.
    for key,owner_key in (('preceding_native_closure','current_native_owner'),
                          ('preceding_observer_closure','current_review_observer')):
        entry=reader.pin(review_job['runtime_paths'][key]);value=read(entry)
        owner=ready[owner_key];reviewer.archived_closure(value,owner,read,exit_zero=False)
        require(process_start(owner['pid']) is None,'A preceding original quality owner remains')
        require(owner.get('cgroup') and not Path('/sys/fs/cgroup'+owner['cgroup']).exists(),
            'A preceding quality cgroup remains')
        for unit in (owner['unit'],owner['timer']):require(unit_fields(unit).get('LoadState')=='not-found',
            'A preceding original unit remains; no adoption or retry')
        preceding[key]=entry
    decision_entry=reader.pin(job['preceding_quality_decision_path']);decision=read(decision_entry)
    status_raw=Path(review_job['preceding_campaign_status_path']).read_bytes();status=json.loads(status_raw)
    require(hashlib.sha256(status_raw).hexdigest()==decision['native_status_sha256'],'Original final quality status differs')
    state_raw=(GAME/'logs/managed-learning-20261015/state.json').read_bytes();state=json.loads(state_raw)
    metadata=read(decision['protected_winner_metadata']) if decision.get('protected_winner_metadata') else None
    reviewer.validate_preceding_decision(status,decision,metadata,state['incumbent'])
    if metadata:
        read(decision['protected_winner_job'])
        require(reader.digest(metadata['protected_checkpoint'])==reviewer.CURRENT_CANDIDATE_SHA,
            'Confirmed winner bytes differ')
    plan=read(review_job['pilot_plan']);require(review_job['pilot_plan']['sha256']==reviewer.PILOT_PLAN_SHA,
        'Original prepared pilot plan changed')
    package=read(plan['source_package']);require(plan['source_package']['sha256']==reviewer.PACKAGE_SHA
        and package['source_count']==len(package['files'])==123,'Exact private capacity package required')
    for relative,digest in package['files'].items():
        path=Path(package['root'])/relative
        require(path.resolve(strict=True).is_relative_to(Path(package['root'])) and reader.digest(path)==digest,
            'Private pilot sources changed')
    read(plan['checkpoint'],False)
    for entry in job['binary_inputs']:require(reader.pin(entry['path'])==entry,'Planned executable/ROM input changed')
    for proof_key,closure_key,tests in (('CPU_proof','original_CPU_closure',88),):
        proof=read(plan[proof_key]);control=read(plan[closure_key])
        require(proof['status']=='PASS' and proof['tests_run']==tests and proof['cuda_initialized'] is False
            and control['original_exit']==0 and control['unit_released'] and control['lifecycle_complete'],
            'Original capacity CPU proof failed')
    proof=read(selected['CPU_report']);control=read(selected['CPU_original_closure'])
    require(proof['status']=='PASS' and proof['tests_run']==selected['expected_tests']
        and proof['tests_run']>=143 and selected['accounting_policy']=='single_inflight_optimizer_v1'
        and proof['cuda_initialized'] is False
        and control['original_exit']==0 and control['unit_released'] and control['lifecycle_complete'],
        'Original full-reviewer CPU proof failed')
    helper=read(review_job['evidence_helpers_selection'])
    read(helper['source'],False);read(helper['original_auditor_helpers'],False)
    helper_proof=read(helper['CPU_report']);helper_control=read(helper['original_CPU_closure'])
    require(helper_proof['status']=='PASS' and helper_proof['tests_run']==104
        and helper_proof['cuda_initialized'] is False and helper_control['original_exit']==0
        and helper_control['unit_released'] and helper_control['lifecycle_complete'],
        'Original independent evidence-helper CPU proof failed')
    template=read(review_job['main_hold_template']);main=dict(schema='robotron-main192-capacity-pilot-binding-v1',
        owner=template['owner'],actors=template['actors'],held_hashes=copy.deepcopy(template['held_hashes']),
        experiment=template['experiment'])
    main['held_hashes'][str(GAME/'models_dqn/managed_save.request.json.completed')]=review_job['expected_completed_slot_sha256']
    window=reader.checked_module('_pilot_guard_main_'+str(time.time_ns()),review_job['main_guard_source'])
    window.owner_and_files(main);baseline=read_API()
    window.healthy(baseline,baseline,main['experiment'],time.time())
    original=unit_fields(main['owner']['unit'])
    require(original.get('MainPID')==str(main['owner']['pid'])
        and original.get('InvocationID')==main['owner']['invocation_id'] and original.get('NRestarts')=='0',
        'Original main service invocation differs')
    for unit in (plan['unit'],plan['timer']):require(unit_fields(unit).get('LoadState')=='not-found',
        'Future pilot unit or timer already exists; never retry')
    bindings=Path(review_job['closed_context_path']).parent
    require(not bindings.exists() and not Path(config['output']).exists()
        and not Path(plan['job']['directory']).exists() and not Path(review_job['output']).exists(),
        'Future pilot/binding/execution/review directory exists; no historical adoption')
    reviewer.validate_prior_invalid_runtime(job['prior_invalid_runtime'],read)
    inputs=dict(job=job,selected=selected,review_job=review_job,reader=reader,reviewer=reviewer,
        plan=plan,preceding=preceding,decision=decision,state_raw=state_raw,main=main,baseline=baseline,window=window)
    guard=MainGuard(config,inputs);guard.validate_config(config)
    idle_GPU(review_job,plan)
    return guard


class MainGuard:
    def __init__(self,config,inputs):
        self.config=copy.deepcopy(config)
        for key,value in inputs.items():setattr(self,key,value)
        self.binding_dir=Path(self.review_job['closed_context_path']).parent
        self.samples=[];self.last_sample=None;self.identity=None;self.actors=None
        self.failed=None;self.stop_attempted=False;self.finished=False;self.main_manifest=None
        self.requested_stop=None
        self.progress={}
        self.exposure_previous=None
        self.pending_since=None
        self.rejected_observations=[]
        self.observation_attempt=None
        self.clock=time.time;self.monotonic=time.monotonic

    def validate_config(self,config):
        plan=self.plan;props=[value for value in plan['service_properties']
            if value.split('=',1)[0] not in ('Type','RemainAfterExit','Restart')]
        require(config['unit']==plan['unit'] and config['output']==str(Path(self.review_job['console_path']).parent)
            and config['argv']==plan['command'] and config['properties']==props
            and type(config['observation_s']) is int and config['observation_s']==6500
            and config['pins']==self.job['launch_pins'],'Original command/resources/windows differ')

    def save(self,path,value):
        path=Path(path);raw=value if isinstance(value,bytes) else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
        with path.open('xb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
        return self.reader.pin(path)

    def prepare_bindings(self):
        self.binding_dir.mkdir(mode=0o700);(self.binding_dir/'main-samples').mkdir(mode=0o700)
        (self.binding_dir/'main-rejections').mkdir(mode=0o700)
        self.main['baseline_API']=self.save(self.binding_dir/'baseline-API.raw.json',self.baseline)
        self.main_entry=self.save(self.review_job['runtime_paths']['main_binding'],self.main)
        self.decision_entry=self.save(self.review_job['runtime_paths']['preceding_quality_decision'],self.decision)
        self.incumbent_entry=self.save(self.review_job['runtime_paths']['incumbent_before_pilot'],self.state_raw)
        self.held_sha=hashlib.sha256(json.dumps(self.main['held_hashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.sample()

    def sample(self):
        self.observation_attempt=dict(unix_s=self.clock(),monotonic_s=self.monotonic(),
            API=None,autosave=None,main_owner=self.main['owner'])
        try:
            return self._sample()
        except Exception as error:
            self.failed=self.failed or repr(error)
            witness=dict(schema='robotron-rejected-main-observation-v1',error=repr(error),
                accounting_policy='single_inflight_optimizer_v1',attempt=self.observation_attempt,
                original_private_owner=self.identity,main_touched=False)
            self.rejected_observations.append(self.save(self.binding_dir/'main-rejections'/
                f'{len(self.rejected_observations):04d}.json',witness))
            raise

    def validate_exposure(self,api,monotonic):
        exposure=api['host_pipeline']['learning_exposure']
        baseline=self.baseline['host_pipeline']['learning_exposure']
        for name in ('optimizer','replay'):
            current=exposure[name]
            require(current.get('enabled') is True and all(type(current.get(key)) is int
                for key in ('process_id','instance_monotonic_ns','epoch'))
                and current['process_id']==self.main['owner']['pid']
                and current['instance_monotonic_ns']>0 and current['epoch']>=0
                and all(current[key]==baseline[name][key] for key in
                    ('process_id','instance_monotonic_ns','epoch')),'Main exposure identity or epoch changed')
        require(exposure['replay'].get('available') is True
            and type(exposure['replay'].get('accepted_learner_total')) is int
            and exposure['replay']['accepted_learner_total']>=0,'Replay exposure unavailable or malformed')
        optimizer=exposure['optimizer']
        require(optimizer.get('schema')=='robotron-optimizer-exposure-v1','Optimizer exposure schema differs')
        fields=('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
        for bucket in ('total','since_epoch'):
            counts=optimizer[bucket]
            require(all(type(counts.get(key)) is int and counts[key]>=0 for key in fields),
                'Optimizer exposure counters must be nonnegative integers')
            require(counts['outcomes_recorded']==counts['applied']+counts['amp_skipped']+counts['unavailable']
                and counts['unavailable']==0,'Optimizer outcomes inconsistent or unclassified')
        total=optimizer['total'];current=optimizer['since_epoch']
        pending=total['attempts_started']-total['outcomes_recorded']
        require(pending in (0,1) and current['attempts_started']-current['outcomes_recorded']==pending
            and all(current[key]<=total[key] for key in fields) and current['outcomes_recorded']>0
            and type(optimizer.get('unclassified_started_total')) is int
            and optimizer['unclassified_started_total']==pending,'Optimizer in-flight accounting inconsistent')
        require(type(optimizer.get('available')) is bool and optimizer['available']==(pending==0),
            'Optimizer availability contradicts its counters')
        previous=self.exposure_previous or baseline
        for bucket in ('total','since_epoch'):
            require(all(optimizer[bucket][key]>=previous['optimizer'][bucket][key] for key in fields),
                'Optimizer exposure counters regressed')
        require(exposure['replay']['accepted_learner_total']>=previous['replay']['accepted_learner_total'],
            'Replay accepted exposure regressed')
        if pending:
            # Aggregate counters cannot identify which ticket remains pending.
            # Advancing attempt numbers alone cannot clear a stranded outcome.
            if self.pending_since is None:self.pending_since=monotonic
            require(monotonic-self.pending_since<60,'Optimizer snapshots did not drain for60 seconds')
        else:self.pending_since=None
        self.exposure_previous=copy.deepcopy(exposure)

    def _sample(self):
        self.window.owner_and_files(self.main)
        api=read_API();self.observation_attempt['API']=copy.deepcopy(api)
        save=(GAME/'models_dqn/robotron_dqn_latest.pt').stat()
        unix=self.clock();monotonic=self.monotonic()
        self.observation_attempt.update(unix_s=unix,monotonic_s=monotonic,
            autosave=dict(mtime_ns=save.st_mtime_ns,bytes=save.st_size,age_s=unix-save.st_mtime_ns/1e9))
        self.window.healthy(api,self.baseline,self.main['experiment'],unix)
        age=unix-save.st_mtime_ns/1e9
        require(save.st_size>0 and math.isfinite(age) and 0<=age<=360,'Main autosave stale, future or empty')
        if self.last_sample:
            previous=self.last_sample
            require(0<monotonic-previous['monotonic_s']<=30 and 0<unix-previous['unix_s']<=30,
                'Main observation gap exceeded30 seconds')
            require(all(api[key]>=previous['API'][key] for key in
                ('frame_count','learner_frame_count','optimized_samples','training_steps')),'Main work clocks regressed')
        exposure=api['host_pipeline']['learning_exposure']
        self.validate_exposure(api,monotonic)
        progress=dict(applied=exposure['optimizer']['total']['applied'],learner=api['learner_frame_count'],
            accepted=exposure['replay']['accepted_learner_total'])
        for name,count in progress.items():
            require(type(count) is int and count>=0,'Invalid main progress counter: '+name)
            previous=self.progress.get(name)
            require(previous is None or count>=previous[0],'Main progress counter regressed: '+name)
            if previous is None or count>previous[0]:self.progress[name]=(count,monotonic)
            else:require(monotonic-previous[1]<60,'Main made no '+name+' progress for60 seconds')
        sample=dict(monotonic_s=monotonic,unix_s=unix,main_owner=self.main['owner'],
            original192_actors_verified=True,held_hashes_sha256=self.held_sha,API=api,
            autosave=dict(mtime_ns=save.st_mtime_ns,bytes=save.st_size,age_s=age))
        self.samples.append(self.save(self.binding_dir/'main-samples'/f'{len(self.samples):04d}.json',sample))
        self.last_sample=sample

    def before_scheduling(self):
        require(self.failed is None and self.requested_stop is None,'Main guard failed or controller stopped before scheduling')
        self.sample()

    def record_birth(self,identity):
        forbidden={self.main['owner']['pid'],*(owner['pid'] for owner in self.main['actors'])}
        require(self.identity is None and identity.get('unit')==self.plan['unit']
            and identity.get('timer')==self.plan['timer'] and identity.get('pid') not in forbidden
            and identity.get('cgroup','').endswith('/'+self.plan['unit']) and identity.get('observed_live') is True,
            'One exact live original pilot birth required')
        self.identity=identity
        self.owner_entry=self.save(self.review_job['runtime_paths']['pilot_owner'],identity)

    def capture_actors(self):
        path=Path(self.plan['job']['directory'])/'status.json'
        if not path.exists():return
        status=json.loads(path.read_bytes());actors=status.get('actor_pids',{})
        if set(actors)!={str(slot) for slot in SLOTS}:return
        if self.actors is not None:
            require(actors=={key:value['pid'] for key,value in self.actors.items()},'Original private actor PIDs changed')
            return
        owners={key:dict(pid=pid,starttime_ticks=process_start(pid),observed_live=True) for key,pid in actors.items()}
        if not all(value['starttime_ticks'] for value in owners.values()):return
        require(len({value['pid'] for value in owners.values()})==32,'Duplicate private actor PIDs')
        self.actor_entry=self.save(self.review_job['runtime_paths']['actor_identities'],owners)
        self.actors=owners

    def interrupt_original(self):
        if self.identity is None or self.stop_attempted:return
        self.stop_attempted=True;owner=self.identity
        event=dict(original=owner,reason=self.failed,signal='SIGINT',signal_sent=False,main_touched=False)
        self.save(Path(self.config['output'])/'root-owned-guard-stop-intent.json',event)
        descriptor=None
        try:
            current=unit_fields(owner['unit'])
            require(current.get('InvocationID')==owner['invocation_id'] and current.get('NRestarts')=='0'
                and current.get('MainPID')==str(owner['pid']) and process_start(owner['pid'])==owner['starttime_ticks'],
                'Owned pilot identity changed; no signal authorized')
            descriptor=os.pidfd_open(owner['pid'])
            require(process_start(owner['pid'])==owner['starttime_ticks'],'Pilot changed before pidfd signal')
            signal.pidfd_send_signal(descriptor,signal.SIGINT);event['signal_sent']=True
        except (ProcessLookupError,ValueError,OSError) as error:event['error']=repr(error)
        finally:
            if descriptor is not None:os.close(descriptor)
            self.save(Path(self.config['output'])/'root-owned-guard-stop-result.json',event)

    def on_tick(self,fields,identity):
        if self.finished:return
        if self.requested_stop is not None and self.failed is None:
            self.failed=f'Original controller stop requested: signal{self.requested_stop}'
        try:
            self.capture_actors()
            if self.failed is None and self.monotonic()-self.last_sample['monotonic_s']>=10:self.sample()
        except Exception as error:
            if self.failed is None:self.failed=repr(error)
        if self.failed is not None and fields.get('MainPID') not in (None,'0'):self.interrupt_original()

    def finish_main_observation(self):
        if self.finished:return
        if self.failed is None:
            try:self.sample()
            except Exception as error:self.failed=repr(error)
        self._finish()

    def _finish(self):
        if self.actors is None:
            self.actor_entry=self.save(self.review_job['runtime_paths']['actor_identities'],{})
        manifest=dict(schema='robotron-main192-pilot-observations-v1',status='PASS' if self.failed is None else 'FAILED',
            configuration_changed=False if self.failed is None else None,controller_changed_learning=False,
            main_owner=self.main['owner'],samples=self.samples,error=self.failed,
            accounting_policy='single_inflight_optimizer_v1',rejected_observations=self.rejected_observations,
            progress_guard='Applied optimizer, learner frames and accepted learner inserts must advance within60 seconds')
        self.main_manifest=self.save(self.review_job['runtime_paths']['main_observations'],manifest)
        self.finished=True

    def preserve_incomplete_observation(self,error):
        if self.finished:return
        self.failed=self.failed or error or 'Original observation/release incomplete';self._finish()

    def close_and_review(self,result):
        require(result['lifecycle_complete'] is True and result['unit_released'] is True and self.finished,
            'Original pilot must close before independent review')
        context=dict(schema='robotron-capacity-pilot-closed-context-v1',pilot_owner=self.owner_entry,
            pilot_closure=self.reader.pin(self.review_job['runtime_paths']['pilot_closure']),
            main_binding=self.main_entry,main_observations=self.main_manifest,actor_identities=self.actor_entry,
            preceding_quality_decision=self.decision_entry,incumbent_before_pilot=self.incumbent_entry,
            console_path=self.review_job['console_path'],**self.preceding)
        closed=self.save(self.review_job['closed_context_path'],context)
        self.save(Path(self.config['output'])/'root-original-independent-review-attempt.json',
            dict(attempt=1,retry=False,context=closed,source=self.selected['source'],job=self.selected['job']))
        try:
            report=self.reviewer.review(self.review_job,self.selected['job'],self.reader)
        except Exception as error:
            report=dict(valid=False,status='REVIEW_FAILED_OR_NEEDS_REVIEW',error=repr(error),quality_qualified=False,promotion=False)
        self.save(Path(self.config['output'])/'root-controller-result.json',dict(original_native_exit=result['original_exit'],
            lifecycle_complete=True,original_review=report['status'],valid=report['valid'],main_guard_error=self.failed,
            original_attempt=1,retry=False,pilot_rerun=False,capacity_speedup_verified=False,quality_qualified=False,promotion=False))
        return report


def prepare(config,config_pin):
    reader=reader_module()
    # Authenticate the exact already-read config, including its guard and job.
    require(reader.pin(config_pin['path'])['sha256']==config_pin['sha256'],'Controller config changed')
    guard=load_and_preflight(config,reader)
    guard.prepare_bindings()
    return guard
