#!/usr/bin/env python3
"""One NEWEST-only CE4096 recovery of the original failed socket maintenance.

Literal PLAN default. Distinct operation, no retry of f007, no source rollback.
"""
import argparse
import base64
import copy
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time
import traceback

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=GAME/'logs/managed-learning-20261015/run-26'
HELPER=R/'accepted-newgame-healthy-CE-maintenance-source-preparation-20261017/run_healthy_ce_maintenance.py'
HELPER_SHA='f007ad2723fd5fe5b2fd4c0c95723e23b931c60c0938b63114f73e1f71c4b1ae'
FAILURE=R/'accepted-newgame-maintenance-failed-reconnect-root-evidence-20261017/root-failed-maintenance-evidence-manifest.json'
FAILURE_SHA='c80cb82f332fb680989b5d6fd7f607f180e90bfa2956a3b195a8aa6cf24b7c07'
FAILED_JOB_SHA='a7efb0e1f69580adbfb10989e4986fb83eabbc76b5dff31d045727b2c0d20990'
FAILED_RESULT_SHA='4b69a18fc7b7a2ad83c54142d0c0712092616f1052f1b78ba255cc53177d5207'
SCHEMA='robotron-accepted-newgame-failed-maintenance-forward-recovery-job-v1'
MAX_INCREMENT=4<<20


def require(value,message):
    if not value:raise RuntimeError(message)


def load_helper():
    require(hashlib.sha256(HELPER.read_bytes()).hexdigest()==HELPER_SHA,'Sealed healthy helper changed')
    spec=importlib.util.spec_from_file_location('_failed_maintenance_primitives',HELPER)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def validate(job,base,adapter,H):
    require(set(job)=={'schema','activation_authorized','failure_evidence','failed_result','failed_job','failed_startup_CPU',
        'newest_CPU_job','newest_CPU_report','newest_CPU_release','recovery_intent','phase_id','request_id','startup_tag',
        'output_directory','current_completed_request','settings_lifecycle','current_dropin'},'Exact17 recovery fields required')
    require(job['schema']==SCHEMA and job['activation_authorized'] is True,'Explicit separate recovery authorization required')
    require(job['failure_evidence']['path']==str(FAILURE) and job['failure_evidence']['sha256']==FAILURE_SHA,'Wrong original failure')
    evidence=H.immutable(base,job['failure_evidence']);failed=H.immutable(base,job['failed_result'])
    original=H.immutable(base,job['failed_job']);startup=H.immutable(base,job['failed_startup_CPU'])
    cpu=H.immutable(base,job['newest_CPU_job']);proof=H.immutable(base,job['newest_CPU_report'])
    released=H.immutable(base,job['newest_CPU_release']);intent=H.immutable(base,job['recovery_intent'])
    require(job['failed_job']['sha256']==FAILED_JOB_SHA and job['failed_result']['sha256']==FAILED_RESULT_SHA
        and evidence['result']['sha256']==FAILED_RESULT_SHA and evidence['original_parent_exit']==1
        and evidence['inline_CPU_original_exits']==dict(newest_stopped=0,startup=0)
        and failed['status']=='FAILED' and failed['root_job']['sha256']==FAILED_JOB_SHA
        and failed['manual_recovery_required'] is True and not failed['final_resume']['failures']
        and all(x=='passed' for x in failed['CPU_ledger'].values()),'Original FAILED parent/two CPU0 must remain preserved')
    owner=failed['failed_new_CE_retired'];spec=startup['root_job']['phase_snapshot'];fresh=cpu['phase_snapshot']
    require(startup['status']=='PASS' and startup['phase_metadata_verified'] is True
        and spec['purpose']=='startup' and spec['observed_clients']==0 and spec['owner']==owner
        and startup['held_recipe_context']['batch_size']==4096,'Actual failed-owner startup0 proof required')
    require(job['newest_CPU_job']['sha256']=='defbf8d1f1160b05766bdf2d5fa99a40c330b6a500a29a3994a74157d06c8eff'
        and job['newest_CPU_report']['sha256']=='bafd03847686875a4870886745baf37c38f295f8b737e8546332e98b889c7faa'
        and job['newest_CPU_release']['sha256']=='3e90385ae2883edd5a8076b2463b56dadf145f7cced5c51095214ddc290c2b5b',
        'Exact genuine new current stopped CPU family required; no numerical retry')
    require(proof['status']=='PASS' and proof['phase_metadata_verified'] is True and proof['root_job']==cpu
        and proof['sha256']==cpu['source']['sha256']==cpu['verification_copy']['sha256']
        and proof['bytes']==cpu['source']['bytes']==cpu['verification_copy']['bytes']
        and fresh['purpose']=='newest_stopped' and fresh['observed_clients']==0 and fresh['owner']==owner
        and cpu['source']['path']==str(GAME/'models_dqn/robotron_dqn_latest.pt')
        and cpu['source']['path']!=cpu['verification_copy']['path'],
        'ONE actual newest-stopped/client0 b2e proof required; original192 fleet is a separate fact')
    require(cpu['verifier_sha256']==adapter.PHASE_SHA and cpu['strict_phase_base_sha256']==adapter.STRICT_SHA
        and proof['held_recipe_context']['batch_size']==4096
        and proof['held_recipe_context']['learning_control_lr_scale']==.5
        and all(fresh[k]==spec[k] for k in ('boot_checkpoint','expected_phase'))
        and all(fresh['phase_record'][k]==spec['phase_record'][k] for k in ('sha256','bytes'))
        and all(fresh['boot_verification'][k]==spec['boot_verification'][k] for k in ('sha256','bytes'))
        and proof['saved_priority_metric_phase']['metric']=='ce' and proof['saved_priority_metric_phase']['valid'] is True
        and proof['saved_priority_metric_phase']['phase_id']==spec['expected_phase']['phase_id']
        and all(proof['clocks'][k]>=cpu['clock_floor'][k]>=startup['clocks'][k] for k in adapter.CLOCKS),
        'Fresh stopped proof must retain actual failed CE phase/.5 recipe and startup clocks')
    require(released['status']=='PASS' and released['original_exit']==0 and released['original_archived_before_release'] is True
        and released['unit_released'] is True and released['CPU_report']['sha256']==job['newest_CPU_report']['sha256'],
        'Genuine root retained newest CPU0 archive/release required')
    require(intent['schema']=='robotron-accepted-newgame-failed-maintenance-forward-recovery-intent-v1'
        and intent['failed_job']==job['failed_job'] and intent['failed_result']==job['failed_result']
        and intent['failure_evidence']==job['failure_evidence'] and intent['owner']==owner
        and intent['newest_checkpoint']==adapter.triple(cpu['source'])
        and intent['phase_id']==job['phase_id'] and intent['no_maintenance_retry'] is True
        and intent['no_rollback'] is True and intent['target_batch_size']==4096 and intent['target_lr_scale']==.5
        and intent['strict_runtime_s']==60 and intent['ready_s']==600,'Exact newest-bound separate recovery intent required')
    require(job['current_dropin']['path']==original['transition']['original_dropin']['path']
        and job['current_completed_request']['path']==str(GAME/'models_dqn/managed_save.request.json.completed')
        and job['settings_lifecycle']['initial']['path']==str(GAME/'models_dqn/game_settings.json'),
        'Exact existing91 override/completion/settings destinations required')
    cfg=copy.deepcopy(original['transition']);phase=dict(record=spec['phase_record'],boot_checkpoint=spec['boot_checkpoint'],
        boot_verification=spec['boot_verification'],expected=spec['expected_phase'])
    record=H.immutable(base,phase['record'])
    require(record['metric']=='ce' and record['action']=='start' and record['previous_metric']=='ce'
        and phase['expected']==adapter.expected_start(record,phase['record'],H.immutable(base,phase['boot_verification']))
        and job['phase_id']!=record['phase_id'],'Authentic current failed phase and NEW recovery phase required')
    cfg.update(mode='return_ce',sources=[],running_phase=phase,phase_id=job['phase_id'],request_id=job['request_id'],
        startup_tag=job['startup_tag'],trial_core=job['recovery_intent'],output_directory=job['output_directory'],
        current_completed_request=job['current_completed_request'],settings_lifecycle=job['settings_lifecycle'],
        original_dropin=job['current_dropin'])
    cfg['before']['bindings']['source_hashes'][str(H.SOCKET)]=H.AFTER_SHA
    cfg['before']['environment'].update(DQN_PER_PRIORITY_METRIC='ce',DQN_PRIORITY_PHASE_RECORD=phase['record']['path'],
        DQN_PRIORITY_PHASE_RECORD_SHA256=phase['record']['sha256'])
    cfg['verifier']['context']=copy.deepcopy(cpu['source_control_context'])
    require(cfg['before']['environment']['DQN_BATCH_SIZE']=='4096' and cfg['timeouts']==dict(ready_s=600,save_s=60,cpu_s=120)
        and cfg['before']['environment']['DQN_EXACT_GRAPH_CHECKPOINT']==str(GAME/'models_dqn/robotron_dqn_latest.pt'),
        'Existing4096/latest-only boot and original600s budget required')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',job['phase_id'] or '')
        and re.fullmatch(r'[A-Za-z0-9_-]{1,120}',job['request_id'] or '')
        and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',job['startup_tag'] or '')
        and job['startup_tag']!=original['transition']['startup_tag'],'NEW recovery start/save names required')
    require(base.fingerprint(H.SOCKET,base.MAX_SOURCE)['sha256']==H.AFTER_SHA,'Installed reviewed socket must remain4a; no source transaction')
    for value in (cpu['source'],cpu['verification_copy']):base.pin(value)
    return cfg,original,failed,startup,cpu,proof,owner


def runtime_for_absence(job,base,adapter,H,cfg,original,failed,startup,cpu,proof,owner,output):
    # This is an absence-only adoption of an explicitly retired owner, not a
    # fabricated healthy-before description. Historical entry remains labeled.
    entry=H.immutable(base,original['entry_CPU'])
    runtime=H.runtime_class(base,adapter)(cfg,output,entry)
    runtime.insured=copy.deepcopy(owner);runtime.floor=adapter.four(proof['clocks'])
    runtime.current_checkpoint=dict(source=cpu['source'],verification=job['newest_CPU_report'],clocks=proof['clocks'])
    runtime.recovery_saved_phase=copy.deepcopy(proof['saved_priority_metric_phase'])
    runtime.retired_owner=runtime.retirement_candidate=copy.deepcopy(owner);runtime.phase='after'
    runtime.host.trainer_cgroup=owner['cgroup'];runtime.host.owned_fleet_cgroup=cfg['before']['bindings']['fleet_cgroup']
    runtime.host.retired_trainers=[dict(pid=owner['pid'],starttime_ticks=owner['starttime_ticks'])]
    runtime.host.metric_host=runtime.metrics.Host(0,cfg['fleet_unit'])
    runtime.host.metric_host.configure_logs(cfg['before']['bindings']['logs'])
    runtime.host.begin_transition_logs(cfg['before']['bindings']['logs'],cfg['before']['trainer_stdout'])
    runtime.absence();runtime.static()
    for actor in cfg['before']['bindings']['actors']:
        require(runtime.metrics.identity.identify_process(actor['pid'],'mame')==actor
            and sorted(os.sched_getaffinity(actor['pid']))==cfg['actor_masks'][str(actor['pid'])],'Original actor identity/mask changed')
    # Same existing readonly nonblocking lease primitive as proven recovery.
    import fcntl
    lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');before=lease.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid(),'Existing owned lease required')
    runtime.lease_fd=os.open(lease,os.O_RDONLY|os.O_NOFOLLOW)
    require(base.identity(os.fstat(runtime.lease_fd))==base.identity(before),'Lease identity race')
    fcntl.flock(runtime.lease_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return runtime


class TransitionCoverage:
    """Read each appended byte ONCE, archive it, and hand over only covered EOF.

    Incomplete lines/tracebacks remain pending and cannot grant handover. No
    unclassified byte is advanced past a fresh EOF or a rearm operation.
    """
    def __init__(self,runtime,base,directory):
        self.runtime,self.base,self.directory=runtime,base,directory
        directory.mkdir(mode=0o700);self.sequence=0;self.records=[]
        self.cursors=copy.deepcopy(runtime.host.transition_logs.log_offsets)
        for value in self.cursors.values():
            require(value['partial']=='','Fresh transition cursor required')
            value['pending']=b'';value['covered']=value['offset']

    def scan(self):
        result=[];total=0
        for name,saved in self.cursors.items():
            with os.fdopen(os.open(name,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
                info=os.fstat(stream.fileno())
                require((info.st_dev,info.st_ino)==(saved['device'],saved['inode']) and info.st_size>=saved['offset'],'Transition log replaced/truncated')
                length=info.st_size-saved['offset'];require(length<=MAX_INCREMENT,'Transition increment exceeds4MiB')
                stream.seek(saved['offset']);payload=stream.read(length)
                require(len(payload)==length,'Transition short read')
                after=os.fstat(stream.fileno());path_info=Path(name).lstat()
                require((after.st_dev,after.st_ino)==(path_info.st_dev,path_info.st_ino)==(saved['device'],saved['inode'])
                    and after.st_size>=info.st_size and path_info.st_size>=info.st_size,'Transition inode/truncation race')
            total+=length;require(total<=32<<20,'Aggregate transition increment exceeds32MiB')
            if payload:
                self.sequence+=1;target=self.directory/('%06d.bin'%self.sequence)
                with target.open('xb') as output:output.write(payload);output.flush();os.fchmod(output.fileno(),0o444);os.fsync(output.fileno())
                self.base.fsync_directory(target.parent)
                record=dict(path=name,start_byte=saved['offset'],end_byte=saved['offset']+length,
                    device=saved['device'],inode=saved['inode'],sha256=hashlib.sha256(payload).hexdigest(),
                    pending_before_bytes=len(saved['pending']),pending_before_sha256=hashlib.sha256(saved['pending']).hexdigest(),
                    archive=self.base.fingerprint(target,MAX_INCREMENT))
                self.records.append(self.base.publish(self.directory/('%06d.json'%self.sequence),record));result.append(record)
                saved['offset']+=length;saved['pending']+=payload
            if not payload:continue
            require(len(saved['pending'])<=MAX_INCREMENT,'Unclassified transition pending bytes exceed4MiB')
            pending=saved['pending'];split=pending.rfind(b'\n')+1
            if not split:continue
            complete,tail=pending[:split],pending[split:];text=complete.decode('utf-8')
            exceptions=re.findall(r'^([A-Za-z_]*(?:Error|Exception)): (.*)$',text,re.MULTILINE)
            classification=dict(path=name,start_byte=saved['covered'],end_byte=saved['offset']-len(tail),
                sha256=hashlib.sha256(complete).hexdigest(),exceptions=exceptions,headers=text.count('Traceback (most recent call last):'))
            self.base.publish(self.directory/('parsed-%06d-%s.json'%(self.sequence,hashlib.sha256(name.encode()).hexdigest()[:12])),classification)
            require(all(kind=='TimeoutError' and message=='Batched inference request timed out'
                or kind=='RuntimeError' and message=='Inference batcher stopped before completion'
                for kind,message in exceptions),'Unrecognized transition exception')
            headers=text.count('Traceback (most recent call last):')
            if headers>len(exceptions):continue  # Keep the complete prefix too until its exact ending arrives.
            events=[]
            for marker in self.runtime.metrics.LOG_MARKERS:
                if marker not in text:continue
                compatible=marker in ('[SOCKET ACTION TIMEOUT]','Batched inference request timed out') or marker=='Traceback' and bool(exceptions)
                events.append(dict(path=name,marker=marker,intentional_restart_compatible=compatible))
            verdict=dict(path=name,start_byte=saved['covered'],end_byte=saved['offset']-len(tail),
                sha256=hashlib.sha256(complete).hexdigest(),events=events,classification_starts_at_previously_covered_boundary=True,partial_after=tail.decode('utf-8'))
            self.base.publish(self.directory/('classification-%06d-%s.json'%(self.sequence,hashlib.sha256(name.encode()).hexdigest()[:12])),verdict)
            require(all(e['intentional_restart_compatible'] for e in events),'Unrecognized restart log marker')
            saved['covered']=verdict['end_byte'];saved['pending']=tail
        return result

    def handover(self,reader):
        require(set(reader.log_offsets)==set(self.cursors),'Runtime/transition log set differs')
        proof={}
        for name,saved in self.cursors.items():
            require(not saved['pending'] and saved['covered']==saved['offset'],'Unclassified partial line/traceback prevents handover')
            require(all(reader.log_offsets[name][k]==saved[k] for k in ('device','inode')),'Runtime log identity differs')
            reader.log_offsets[name]=dict(device=saved['device'],inode=saved['inode'],offset=saved['covered'],partial='')
            self.runtime.host.transition_logs.log_offsets[name]=copy.deepcopy(reader.log_offsets[name])
            proof[name]=copy.deepcopy(reader.log_offsets[name])
        return proof


def reconnect_and_strict(runtime,base,H,banks,deadline,coverage):
    reader=runtime.host.metric_host
    original_log_errors=reader.log_errors;previous=None;plan=None;observations=[];handover=None
    try:
        # Only the single-read coverage classifier owns restart markers here.
        # Runtime offsets are not silently moved to a queried EOF.
        reader.log_errors=lambda:[]
        while time.monotonic()<deadline-60:
            runtime.inspect('after');require(runtime.host.metric_host is reader,'Reconnect runtime reader replaced')
            owner=runtime.trainer_id();coverage.scan()
            row=runtime.host.capture()
            if plan is None:
                identities={k:runtime.metrics.exposure_key(row['exposure'][k]) for k in ('optimizer','replay')}
                require(all(v['process_id']==owner['pid'] for v in identities.values()),'Reconnect exposure belongs to another owner')
                plan=dict(batch_size=4096,replay_cap=8,initial_snapshot=dict(csv=runtime.job['baseline_csv']),exposure_identity=identities)
            start=base.read_json(runtime.start_request);stamp=datetime.datetime.fromisoformat(row['csv']['utc'].replace('Z','+00:00'))
            require(stamp.tzinfo is not None and stamp.timestamp()<=row['observed_unix_s']+2,'Authentic CSV UTC required')
            current=stamp.timestamp()>=start['unix_s']
            issues=runtime.metrics.api_issues(row,plan,previous)
            allowed={'client_count'}|({'CSV_recipe'} if not current else set())
            observations.append(dict(row=row,post_start_CSV=current,issues=issues))
            base.publish(runtime.output/('reconnect-observation-%04d.json'%len(observations)),observations[-1])
            require(not [v for v in issues if v not in allowed],'Reconnect guards: '+repr(issues))
            require(not current or row['csv']['batch_size']==4096,'New producer row has wrong batch')
            if current and row['client_count']==192:
                coverage.scan()
                if all(not c['pending'] for c in coverage.cursors.values()):
                    handover=coverage.handover(reader);break
            previous=row;time.sleep(min(1,max(0,deadline-60-time.monotonic())))
        require(handover is not None,'Reconnect did not establish classified192/newCSV with60s remaining')
    finally:reader.log_errors=original_log_errors
    handover_pin=base.publish(runtime.output/'log-handover.json',dict(offsets=handover,segments=coverage.records,reconnect_observations=observations))
    start_strict=time.monotonic();strict=[];previous=None
    require(start_strict+60<=deadline,'Strict60s cannot extend original600s deadline')
    runtime.recovery_armed_logs=(reader,copy.deepcopy(runtime.job['before']['bindings']['logs']))
    while True:
        require(time.monotonic()<deadline,'Original600s readiness deadline expired')
        runtime.inspect('after');require(runtime.host.metric_host is reader,'Strict runtime reader replaced')
        runtime.trainer_id();coverage.scan();row=runtime.host.capture()
        stamp=datetime.datetime.fromisoformat(row['csv']['utc'].replace('Z','+00:00'))
        require(stamp.tzinfo is not None and start['unix_s']<=stamp.timestamp()<=row['observed_unix_s']+2,'Strict runtime requires genuine post-start CSV')
        issues=runtime.metrics.api_issues(row,plan,previous)
        strict.append(dict(observed_monotonic_s=time.monotonic(),row=row,issues=issues))
        base.publish(runtime.output/('strict-observation-%04d.json'%len(strict)),strict[-1])
        require(not issues,'Strict post-handover guards: '+repr(issues))
        if time.monotonic()-start_strict>=60:break
        previous=row;time.sleep(min(1,max(0,start_strict+60-time.monotonic())))
    strict_pin=base.publish(runtime.output/'strict-runtime60.json',dict(start_monotonic_s=start_strict,
        end_monotonic_s=time.monotonic(),original_deadline_monotonic_s=deadline,observations=strict,covered_segments=coverage.records))
    healthy=H.ready_with_budget(runtime,banks,actors=True,deadline=deadline)
    return dict(handover=handover_pin,strict_runtime=strict_pin,healthy192=healthy)


def recover(runtime,base,adapter,H):
    result=dict(status='RUNNING',schema='robotron-accepted-newgame-failed-maintenance-forward-recovery-result-v1',
        original_maintenance_failed=True,maintenance_retried=False,qualification_pass=False)
    try:
        runtime.absence();runtime.static();runtime.host.pause(dict(initial=runtime.job['before']))
        base.pin(runtime.current_checkpoint['source']);base.pin(runtime.current_checkpoint['verification'],base.MAX_JSON)
        banks=runtime.banks.stopped_state(runtime.job['bank_spec'])
        owner=H.start_repair_CE4096(runtime,adapter);start=base.read_json(runtime.start_request)
        deadline=start['monotonic_s']+600
        loaded=H.ready_with_budget(runtime,banks,actors=False,deadline=deadline)
        raw=runtime.raw_api();adapter.zero_replay(raw,owner['pid']);startup=runtime.startup_snapshot(raw)
        startup['phase_CPU_readonly_archive']=H.archive_report(base,startup['phase_CPU'],runtime.output/'CE-startup-CPU-readonly.json')
        raw=runtime.raw_api();require(raw['client_count']==0,'Actors admitted before startup0 proof');adapter.zero_replay(raw,owner['pid'])
        before=base.publish(runtime.output/'API-before-resume.json',raw);runtime.inspect('after');runtime.banks.assert_unchanged(banks,runtime.job['bank_spec'])
        runtime.host.metric_host.configure_logs(runtime.job['before']['bindings']['logs'])
        coverage=TransitionCoverage(runtime,base,runtime.output/'transition-coverage')
        resumed=base.resume_all(runtime.host);require(not resumed['failures'],'Original192 undo failed')
        reconnect=reconnect_and_strict(runtime,base,H,banks,deadline,coverage)
        result.update(status='READY_CE_FORWARD_RECOVERY',owner=owner,boot_checkpoint=runtime.current_checkpoint,
            phase_record=runtime.record_pin,start_request=runtime.start_request,loaded=loaded,startup=startup,
            before_resume_API=before,reconnect=reconnect,healthy192=reconnect['healthy192'],manual_recovery_required=False)
    except BaseException as error:
        result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),manual_recovery_required=True)
        if runtime.start_request is not None:
            try:
                if runtime.host.unit(runtime.job['trainer_unit'])['MainPID']!='0':
                    require(runtime.host.known_trainer is not None,'Unknown replacement; no stop authority')
                    for actor in runtime.job['before']['bindings']['actors']:
                        if actor not in runtime.host.paused:
                            with runtime.metrics.block_restore_signals():
                                runtime.host.paused.append(actor);runtime.host.signal_actor(actor,signal.SIGSTOP)
                    runtime.host.wait_paused();result['failed_recovery_CE_retired']=runtime.stop_owned()
            except BaseException as cleanup:result['stop_error']=repr(cleanup)
    finally:
        with runtime.metrics.block_restore_signals():result['final_resume']=base.resume_all(runtime.host)
        result['CPU_ledger']=runtime.cpu_attempts;result['owned_request_at_terminal']=runtime.pending
        if result['final_resume']['failures']:result['manual_recovery_required']=True
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:print('PLAN_ONLY: distinct newest-only failed-maintenance CE4096 recovery; no reads/actions');return 0
    require(args.job and args.expected_job_sha256 and args.expected_source_sha256,'Explicit root bindings required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Recovery source changed')
    H=load_helper();metadata=H.load(H.DEADLINE,H.DEADLINE_SHA,'_recovery_metadata')
    jp,_=metadata.pin(args.job);require(jp['sha256']==args.expected_job_sha256,'Root job changed')
    require(jp['identity']['mode']=='0o444' and jp['identity']['uid']==os.getuid() and jp['identity']['nlink']==1,'Immutable root job required')
    job=metadata.read_pin(jp)
    trial=H.load(H.TRIAL,H.TRIAL_SHA,'_recovery_trial_primitives');adapter=H.load(H.ADAPTER,H.ADAPTER_SHA,'_recovery_phase_primitives');base=adapter.load_v4()
    cfg,original,failed,startup,cpu,proof,owner=validate(job,base,adapter,H)
    output=Path(cfg['output_directory']);require(output.is_absolute() and output==output.resolve(strict=False)
        and output.is_relative_to(GAME/'logs') and output.parent.is_dir() and not output.exists(),'NEW recovery output required')
    output.mkdir(mode=0o700);roots=dict(output_directory=str(output),return_intent=dict(output_directory=str(output)))
    trial.bounded_copy_dispatch(base,roots,cfg);trial.raw_api_publication(base,metadata,roots,cfg)
    runtime=None
    try:
        runtime=runtime_for_absence(job,base,adapter,H,cfg,original,failed,startup,cpu,proof,owner,output)
        with runtime.metrics.interrupt_handlers():result=recover(runtime,base,adapter,H)
        result['root_job']=jp;base.publish(output/'result.json',result)
        return 0 if result['status']=='READY_CE_FORWARD_RECOVERY' and not result['manual_recovery_required'] else 1
    finally:
        if runtime is not None:runtime.close()


if __name__=='__main__':raise SystemExit(main())
