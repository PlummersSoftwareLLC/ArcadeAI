"""Review the one prepared32-actor pilot after its original owned closure.

Default mode does nothing. Execution writes a new evidence archive and review;
it never launches/signals a process, changes training, or publishes a policy.
An absent closed-context file rejects before runtime queries or output creation.
"""
import argparse
import fcntl
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import types
import urllib.request

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
PROTECTOR=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
PROTECTOR_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
PILOT_PLAN_SHA='800f44678a4147ad0a257c2f68c4903e27d8391cea4f0b18f56db99146021275'
PACKAGE_SHA='a2082d2a9ca76e70bb7faedd0b8b56b97f72d5983ef3856ab54a6e69172a12d1'
CURRENT_PLAN_SHA='df13710948498d18420655a4ae6b1229c68873614236dce65ddf5d009ac29e3d'
CURRENT_CANDIDATE_SHA='4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
SLOTS=list(range(4096,4128))
SOURCE_FILES=('tools/run_frozen_sidecar.py','tools/sidecar_boot.py','tools/confirmed_terminal_evidence.py',
    'Scripts/main.lua','Scripts/robotron_socket_wait.c')+tuple('Scripts/dqn/'+name+'.py' for name in
    ('config','model','actor_tags','socket_server','game_journal','managed_measurement','inference_actor',
     'nstep_buffer','rejected_gap_telemetry'))


def require(value,message):
    if not value:raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def protector():
    require(digest(PROTECTOR)==PROTECTOR_SHA,'Exact immutable evidence reader changed')
    name='_pilot_closed_protector_'+str(time.time_ns())
    spec=importlib.util.spec_from_file_location(name,PROTECTOR)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def duration_seconds(value):
    units={'us':1e-6,'ms':1e-3,'s':1,'min':60,'h':3600,'d':86400}
    pattern=r'(\d+(?:\.\d+)?)(us|ms|min|s|h|d)'
    require(isinstance(value,str) and re.sub(pattern,'',value).strip()=='','Invalid archived duration')
    tokens=re.findall(pattern,value);require(bool(tokens),'Missing archived duration')
    return sum(float(number)*units[unit] for number,unit in tokens)


def validate_scope(plan,receipt,package):
    job=plan['job'];directory=Path(job['directory'])
    require(type(job['actors']) is int and job['actors']==32 and job['actor_slots']==SLOTS
        and job['inference_max_batch_size']==16 and job['cohort_s']==2400 and job['timeout_s']==4800
        and job['port']==9999 and job['gpu_uuid']=='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',
        'Only the original prepared32-slot/16-batch pilot is allowed')
    require(receipt['job']==job and receipt['label']==job['label'] and receipt['source_checkpoint_path']==job['checkpoint']
        and receipt['checkpoint_sha256']==plan['checkpoint']['sha256']
        and Path(receipt['checkpoint_path'])==directory/'checkpoint.pt',
        'Original planned job/checkpoint copy differs')
    require(math.isclose(receipt['close_ts']-receipt['start_ts'],2400,abs_tol=1e-6)
        and type(receipt['elapsed_s']) in (int,float) and math.isfinite(receipt['elapsed_s'])
        and 0<receipt['elapsed_s']<5100,'Original window or bounded runtime differs')
    require(all(type(receipt[key]) in (int,float) and math.isfinite(receipt[key])
        for key in ('ended_unix_s','timeout_snapshot_unix_s'))
        and receipt['ended_unix_s']-receipt['elapsed_s']<=receipt['start_ts']<=receipt['close_ts']
        <=receipt['timeout_snapshot_unix_s']<=receipt['ended_unix_s'],
        'Original admission, elapsed and cleanup clocks disagree')
    require(receipt['runtime']['device']=='cuda'
        and receipt['runtime']['cuda_visible_devices']==job['gpu_uuid']
        and receipt['runtime']['gpu_name']=='NVIDIA RTX PRO 2000 Blackwell'
        and receipt['runtime']['compute_capability']==[12,0], 'Actual physical private GPU differs')
    expected={name:package['files'][name] for name in SOURCE_FILES}
    require(receipt['source_hashes']==receipt['ended_source_hashes']==expected,
        'Actual loaded/ended sources differ from all declared runtime sources')


def archived_closure(closure,owner,read,*,exit_zero):
    """Verify archived actual identity/outcome before its exact owned release."""
    code=closure.get('original_exit')
    require(type(code) is int and 0<=code<=255 and (not exit_zero or code==0)
        and closure.get('original')==owner and closure.get('lifecycle_complete') is True
        and closure.get('unit_released') is True and closure.get('original_archived_before_release') is True
        and closure.get('payload_retried',False) is False,'Original service closure differs or was retried')
    released=closure.get('owned_release',[])
    require(len(released)==2 and {row['unit'] for row in released}=={owner['unit'],owner['timer']}
        and all(row.get('confirmed_absent') is True for row in released),'Both original owned units must be released')
    archives=closure.get('native_archives',closure.get('full_original_archives',[]))
    expected=[]
    for unit in (owner['unit'],owner['timer']):
        expected.extend([['systemctl','--user','show',unit],['systemctl','--user','cat',unit],
            ['journalctl','--user','--unit',unit,'--no-pager']])
    require(len(archives)==6 and [row['argv'] for row in archives]==expected,
        'All six original native descriptors must precede release')
    for index,row in enumerate(archives):
        require(row.get('timed_out') is False and type(row.get('exit')) is int
            and row['exit'] in ((0,1) if index==4 else (0,)),
            'Unknown original descriptor outcome')
        read(row['stdout'],False);read(row['stderr'],False)
    fields=dict(line.split('=',1) for line in read(archives[0]['stdout'],False).decode().splitlines() if '=' in line)
    wanted=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],MainPID='0',
        ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus=str(code),NRestarts='0',
        Result='success' if code==0 else 'exit-code')
    require(all(fields.get(key)==value for key,value in wanted.items()),
        'Archived original native identity or actual exit differs')
    require(type(owner['pid']) is int and owner['pid']>0 and type(owner['starttime_ticks']) is int
        and owner['starttime_ticks']>0 and owner.get('observed_live') is True,
        'Original live birth identity required')
    timer=dict(line.split('=',1) for line in read(archives[3]['stdout'],False).decode().splitlines() if '=' in line)
    require(timer.get('Id')==owner['timer'],'Archived original timer ID differs')
    if archives[4]['exit']==1:
        require(timer.get('LoadState')=='not-found','Failed timer cat needs an honestly absent original timer')
    else:
        require(timer.get('LoadState')=='loaded' and timer.get('InvocationID')==owner['timer_invocation_id']
            and timer.get('Unit')==owner['unit'],'Unknown or replaced original timer')
    return fields


def validate_main_samples(binding,manifest,samples,pilot_start_s,pilot_end_s,healthy):
    """Cover the original service interval, retaining exposure identities."""
    require(manifest.get('schema')=='robotron-main192-pilot-observations-v1'
        and manifest.get('status')=='PASS' and manifest.get('configuration_changed') is False
        and manifest.get('main_owner')==binding['owner'],'Main guard scope or result differs')
    require(len(samples)>=2,'Continuous main observations required')
    held_digest=hashlib.sha256(json.dumps(binding['held_hashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    previous=None;identities=None
    for sample in samples:
        monotonic=sample['monotonic_s'];unix=sample['unix_s']
        require(type(monotonic) in (int,float) and math.isfinite(monotonic)
            and type(unix) in (int,float) and math.isfinite(unix)
            and sample.get('main_owner')==binding['owner']
            and sample.get('original192_actors_verified') is True
            and sample.get('held_hashes_sha256')==held_digest,'Main source/actor/owner witness differs')
        api=sample['API'];healthy(api,binding['baseline_API_value'],binding['experiment'],unix)
        save=sample['autosave']
        require(type(save['mtime_ns']) is int and type(save['bytes']) is int and save['bytes']>0
            and type(save['age_s']) in (int,float) and math.isfinite(save['age_s'])
            and 0<=save['age_s']<=360
            and math.isclose(unix-save['mtime_ns']/1e9,save['age_s'],abs_tol=1),
            'Main checkpoint freshness evidence differs')
        exposure=api['host_pipeline']['learning_exposure']
        require(all(exposure[name].get('enabled') is True and exposure[name].get('available') is True
            for name in ('optimizer','replay')), 'Main exposure accounting unavailable')
        current=tuple((name,exposure[name]['process_id'],exposure[name]['instance_monotonic_ns'],
            exposure[name]['epoch']) for name in ('optimizer','replay'))
        if identities is None:identities=current
        require(current==identities and all(identity[1]==binding['owner']['pid'] for identity in current),
            'Main optimizer/replay process or epoch changed')
        require(exposure['optimizer']['total']['unavailable']==0,'Unclassified optimizer outcome')
        if previous:
            require(0<monotonic-previous['monotonic_s']<=30
                and 0<unix-previous['unix_s']<=30,'Main observation gap exceeded30 seconds')
            require(all(api[key]>=previous['API'][key] for key in
                ('frame_count','learner_frame_count','optimized_samples','training_steps')),
                'Main work clocks regressed')
        previous=sample
    require(samples[0]['monotonic_s']<=pilot_start_s and samples[-1]['monotonic_s']>=pilot_end_s,
        'Main observations do not cover original pilot birth through exit')
    require(samples[-1]['API']['training_steps']>samples[0]['API']['training_steps']
        and samples[-1]['API']['learner_frame_count']>samples[0]['API']['learner_frame_count'],
        'Main learner did not make progress through pilot')


def validate_preceding_decision(status,decision,metadata,incumbent):
    require(status.get('state')=='finished' and status.get('plan_sha256')==CURRENT_PLAN_SHA
        and status.get('outcome') in ('qualified_improvement','not_improved','invalid','incomplete'),
        'The entire original quality campaign must be terminal')
    qualified=status['outcome']=='qualified_improvement'
    require(decision.get('schema')=='robotron-quality-disposition-before-capacity-pilot-v1'
        and decision.get('plan_sha256')==CURRENT_PLAN_SHA
        and decision.get('native_outcome')==status['outcome']
        and decision.get('qualified_improvement') is qualified
        and decision.get('scientific_outcome_changed') is False,
        'The independent pilot cannot rescue or reinterpret the preceding quality result')
    if qualified:
        require(metadata and metadata.get('schema')=='robotron-confirmed-terminal-protected-winner-polling-recovery-v1'
            and metadata['assessment']['qualified_improvement'] is True
            and metadata['checkpoints']['candidate']['sha256']==CURRENT_CANDIDATE_SHA
            and metadata['root_protection_job']['sha256']==
                'f40c6c6d41f846fbab6238a545719453debd3e1cf2b7e9aaf0497dd6430a460c'
            and metadata['root_protection_job']==decision['protected_winner_job'],
            'A qualified winner must be independently protected before capacity testing')
        require(incumbent and incumbent['sha256']==CURRENT_CANDIDATE_SHA
            and str((GAME/incumbent['checkpoint']).resolve())==metadata['protected_checkpoint']
            and decision.get('winner_adopted_before_pilot') is True,
            'The confirmed winner must be adopted as the next reference first')
    else:
        require(metadata is None and decision.get('protected_winner_metadata') is None
            and decision.get('winner_adopted_before_pilot') is False,
            'An unsuccessful or incomplete comparison cannot publish a winner')


def verify_cleanup(owner,actor_owners,gpu_uuid,lease_path):
    """Queries only; the lease is acquired temporarily after original release."""
    require(set(actor_owners)=={str(slot) for slot in SLOTS}
        and len({row['pid'] for row in actor_owners.values()})==32,'Every original private actor identity required')
    for identity in [owner,*actor_owners.values()]:
        require(type(identity['pid']) is int and identity['pid']>0
            and type(identity['starttime_ticks']) is int and identity['starttime_ticks']>0
            and identity.get('observed_live') is True,
            'Exact original private process birth required')
        require(not Path('/proc',str(identity['pid'])).exists(),'An original private PID still exists; no signal or adoption')
    require(owner.get('cgroup') and not Path('/sys/fs/cgroup'+owner['cgroup']).exists(),
        'Original pilot cgroup remains')
    for name in ('tcp','tcp6'):
        for line in Path('/proc/net',name).read_text().splitlines()[1:]:
            fields=line.split()
            require(not (fields[3]=='0A' and int(fields[1].rsplit(':',1)[1],16)==9999),
                'Private evaluator port remains in use')
    with Path(lease_path).open('rb') as stream:
        before=os.fstat(stream.fileno())
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            require((before.st_dev,before.st_ino)==(Path(lease_path).stat().st_dev,Path(lease_path).stat().st_ino),
                'Canonical private GPU lease was replaced')
            result=subprocess.run(['nvidia-smi','--id='+gpu_uuid,'--query-compute-apps=pid',
                '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
            require(result.returncode==0 and not result.stdout.strip(),
                'Private GPU compute processes remain or query failed')
        finally:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def review(job,job_pin,reader):
    # This is deliberately first: live/missing pilot context cannot trigger a
    # runtime query, a lease acquisition, or creation of an evidence directory.
    context_pin=reader.pin(job['closed_context_path']);context=reader.read_pin(context_pin)
    require(context.get('schema')=='robotron-capacity-pilot-closed-context-v1','Exact closed-context schema required')
    require(all(context[key]['path']==path for key,path in job['runtime_paths'].items())
        and context['console_path']==job['console_path'], 'Only the original future runtime artifact paths are allowed')
    output=Path(job['output']);require(not output.exists(),'Never overwrite or retry an original pilot review')
    output.mkdir(mode=0o700);artifacts={};evidence={job_pin['path']:job_pin['sha256'],str(PROTECTOR):PROTECTOR_SHA}
    def read(entry,as_json=True):
        value=reader.read_pin(entry,as_json=as_json);evidence[entry['path']]=entry['sha256'];return value
    def capture(path):
        path=Path(path);before=reader.pin(path);raw=path.read_bytes()
        require(hashlib.sha256(raw).hexdigest()==before['sha256'],'Closed artifact changed before capture')
        name=f'{len(artifacts):03d}-'+path.name
        with (output/name).open('xb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        artifacts[str(path)]=dict(copy=name,sha256=before['sha256']);evidence[str(path)]=before['sha256']
        return raw
    report=dict(schema='robotron-single-capacity-pilot-independent-review-v1',valid=False,
        artifacts=artifacts,root_job=job_pin,closed_context=context_pin,quality_qualified=False,
        capacity_speedup_verified=False,learning_speed_gain_verified=False,promotion=False)
    try:
        read(context_pin);capture(Path(__file__));capture(job_pin['path']);capture(context_pin['path'])
        plan=read(job['pilot_plan']);require(job['pilot_plan']['sha256']==PILOT_PLAN_SHA,'Original pilot plan differs')
        owner=read(context['pilot_owner']);closure=read(context['pilot_closure'])
        require(owner['unit']==plan['unit'] and owner['timer']==plan['timer'],'Original planned pilot owner differs')
        fields=archived_closure(closure,owner,read,exit_zero=True)
        require(duration_seconds(fields['RuntimeMaxUSec'])==5100 and fields['MemoryMax']==str(8<<30)
            and duration_seconds(fields['CPUQuotaPerSecUSec'])==12
            and fields['Restart']=='no' and fields['SendSIGKILL']=='no','Original resource/restart policy differs')
        ready=read(job['readiness_amendment'])
        for key,owner_key in (('preceding_native_closure','current_native_owner'),
                              ('preceding_observer_closure','current_review_observer')):
            archived_closure(read(context[key]),ready[owner_key],read,exit_zero=False)
            require(not Path('/proc',str(ready[owner_key]['pid'])).exists(),
                'An original preceding quality owner still exists')
        for entry in ready['prior_failed_observers']:
            value=read(entry);require(value['original_exit']==1 and value['failed_tombstone_retained'] is True
                and value['unit_released'] is False,'Historical failed observers must remain honestly retained')
        prior_status=json.loads(capture(job['preceding_campaign_status_path']))
        decision=read(context['preceding_quality_decision'])
        require(decision['native_status_sha256']==hashlib.sha256(
            Path(job['preceding_campaign_status_path']).read_bytes()).hexdigest(),'Prior final status changed')
        metadata=read(decision['protected_winner_metadata']) if decision.get('protected_winner_metadata') else None
        incumbent=read(context['incumbent_before_pilot'])['incumbent']
        validate_preceding_decision(prior_status,decision,metadata,incumbent)
        if metadata:
            read(decision['protected_winner_job'])
            require(digest(metadata['protected_checkpoint'])==CURRENT_CANDIDATE_SHA,'Protected winner bytes differ')
            evidence[metadata['protected_checkpoint']]=CURRENT_CANDIDATE_SHA
        package=read(plan['source_package']);require(plan['source_package']['sha256']==PACKAGE_SHA
            and package['source_count']==len(package['files'])==123,'Exact selected123-file package required')
        game=Path(package['root'])
        for relative,expected in package['files'].items():
            path=game/relative;require(path.resolve(strict=True).is_relative_to(game) and digest(path)==expected,
                'Selected capacity source changed');evidence[str(path)]=expected
        original_CPU=read(plan['original_CPU_closure']);CPU=read(plan['CPU_proof'])
        require(CPU['status']=='PASS' and CPU['tests_run']==88 and CPU['cuda_initialized'] is False
            and CPU['real_GPU_or_MAME_launched'] is False and original_CPU['original_exit']==0
            and original_CPU['unit_released'] is True and original_CPU['lifecycle_complete'] is True,
            'Original capacity CPU validation missing')
        selected=read(job['evidence_helpers_selection'])
        helpers=reader.checked_module('_pilot_evidence_'+str(time.time_ns()),selected['source'])
        auditor=reader.checked_module('_pilot_auditor_'+str(time.time_ns()),selected['original_auditor_helpers'])
        for entry in (selected['source'],selected['original_auditor_helpers']):evidence[entry['path']]=entry['sha256']
        helper_CPU=read(selected['CPU_report']);helper_control=read(selected['original_CPU_closure'])
        require(helper_CPU['status']=='PASS' and helper_CPU['tests_run']==104
            and helper_CPU['cuda_initialized'] is False and helper_CPU['real_GPU_or_MAME_launched'] is False
            and helper_control['original_exit']==0 and helper_control['unit_released'] is True
            and helper_control['lifecycle_complete'] is True,
            'Independent evidence helper tests missing')
        auditor.validate_optional_expert_proof()
        for entry in (auditor.OPTIONAL_EXPERT_PROOF,auditor.OPTIONAL_EXPERT_CLOSURE):read(entry)
        prefix='_pilot_package_'+str(time.time_ns());module=types.ModuleType(prefix)
        module.__path__=[str(game/'tools')];sys.modules[prefix]=module
        backend=importlib.import_module(prefix+'.compare_sidecar_measurements')
        boot=importlib.import_module(prefix+'.sidecar_boot')
        directory=Path(plan['job']['directory']);receipt=auditor.decode(capture(directory/'receipt.json'))
        validate_scope(plan,receipt,package)
        service_start=int(fields['ExecMainStartTimestampMonotonic'])/1e6
        service_end=int(fields['ExecMainExitTimestampMonotonic'])/1e6
        require(0<service_start<service_end and receipt['elapsed_s']<=service_end-service_start+1
            and service_end-service_start<=5280,'Original service duration cannot contain the saved pilot duration')
        require(auditor.decode(capture(directory/'plan.json'))==dict(plan['job'],checkpoint_sha256=plan['checkpoint']['sha256']),
            'Actual private native plan differs')
        read(plan['checkpoint'],False)
        require(Path(receipt['checkpoint_path']).stat().st_ino!=Path(plan['checkpoint']['path']).stat().st_ino,
            'Frozen checkpoint must be an independent copy')
        for name in ('games.jsonl','measurement_starts.jsonl'):capture(directory/'journal'/name)
        for slot in SLOTS:capture(directory/'actors'/str(slot)/'console.log')
        console=capture(context['console_path']).decode(errors='replace')
        boot_manifest=boot.load_snapshot(Path(plan['job']['boot_assets']))
        capture(Path(plan['job']['boot_assets'])/'manifest.json')
        require(receipt['boot_assets']==boot_manifest,'Original immutable boot snapshot differs')
        manifest_sha=digest(Path(plan['job']['boot_assets'])/'manifest.json')
        for slot in SLOTS:
            restored=receipt['boot_restores'][str(slot)]
            require(restored['manifest_sha256']==manifest_sha and restored['restored_paths']=={
                name:str(directory/'actors'/str(slot)/name) for name in boot_manifest['files']},
                'Original per-slot boot restore identity differs')
        require(digest(receipt['socket_wait']['library'])==receipt['socket_wait']['sha256'],'Private pacing binary changed')
        capture(receipt['socket_wait']['library'])
        games=helpers.original_games(receipt,directory,backend,auditor)
        logs=helpers.actor_logs(receipt,directory,auditor)
        console_review=helpers.console_lines(console,receipt,game,auditor,unused_expert_proof_validated=True)
        main=read(context['main_binding']);template=read(job['main_hold_template'])
        require(main['owner']==template['owner'] and main['actors']==template['actors']
            and set(main['held_hashes'])==set(template['held_hashes']) and len(main['actors'])==192,
            'Fresh main binding lost the original owner/actors/source coverage')
        slot=str(GAME/'models_dqn/managed_save.request.json.completed')
        require(all(value==(job['expected_completed_slot_sha256'] if path==slot else template['held_hashes'][path])
            for path,value in main['held_hashes'].items()), 'Main controls changed before the fixed capacity pilot')
        window=reader.checked_module('_pilot_main_guard_'+str(time.time_ns()),job['main_guard_source'])
        evidence[job['main_guard_source']['path']]=job['main_guard_source']['sha256']
        main['baseline_API_value']=read(main['baseline_API'])
        observation=read(context['main_observations']);samples=[read(entry) for entry in observation['samples']]
        validate_main_samples(main,observation,samples,service_start,service_end,window.healthy)
        actor_owners=read(context['actor_identities'])
        require(all(actor_owners[str(slot)]['pid']==receipt['socket_wait']['actors'][str(slot)]['pid'] for slot in SLOTS),
            'Cleanup identities are not the original recorded MAME actors')
        window.owner_and_files(main)
        current=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5))
        window.healthy(current,main['baseline_API_value'],main['experiment'],time.time())
        lease=Path(job['lease_path']);info=lease.lstat()
        require(str(lease)=='/dev/shm/robotron-snapshot-smoke-gpu0.lock'
            and lease.resolve(strict=True)==lease and info.st_uid==os.getuid() and info.st_nlink==1
            and dict(device=info.st_dev,inode=info.st_ino)==job['lease_identity'],
            'Original canonical GPU0 lease identity differs')
        verify_cleanup(owner,actor_owners,plan['job']['gpu_uuid'],lease)
        require(all(digest(path)==expected for path,expected in evidence.items()),'Closed original evidence changed during review')
        require(not any(name=='torch' or name.startswith('torch.') for name in sys.modules),'Review imported numerical runtime')
        report.update(valid=True,status='VALID_ONE_ORIGINAL32_ACTOR_RUNTIME_PILOT',statistics=games['statistics'],
            original_games=games,actor_logs=logs,classified_console_lines=console_review,
            original_native_exit=0,original_owned_closure_verified=True,main192_continuous_holds_verified=True,
            private_cleanup_verified=True,evidence_sha256=evidence,
            scope='One original protected845M standalone32-slot runtime pilot only; no causal capacity, learning or policy gain.')
    except Exception as error:
        report.update(status='REJECTED_OR_NEEDS_REVIEW',error=repr(error))
    with (output/'review.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(output,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY: no reads, queries, outputs, launches or policy changes');return 0
    require(args.job and args.job_sha256 and digest(__file__)==args.source_sha256,'Exact root source/job required')
    reader=protector();job_pin=reader.pin(args.job);require(job_pin['sha256']==args.job_sha256,'Review job SHA differs')
    job=reader.read_pin(job_pin);require(job['schema']=='robotron-original-capacity-pilot-review-job-v1','Wrong review job schema')
    result=review(job,job_pin,reader)
    print(json.dumps(dict(status=result['status'],valid=result['valid'],quality_qualified=False,promotion=False)))
    return 0 if result['valid'] else 2


if __name__=='__main__':raise SystemExit(main())
