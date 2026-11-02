"""Prepare one actual captured candidate's original CPU job; default is inert.

Requires the selected first-both8M capture and its actual original exit0 closure.
Copies bytes and binds provenance; it never loads a model, launches a verifier,
requests a checkpoint, changes learning, evaluates or publishes a policy.

This revision selects the actual verified score-carry849 startup template and
its newest-state boot. It does not reinterpret the historical6000 boot template.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
MODEL=GAME/'models_dqn'
HERE=GAME/'tools/quality_capacity_proposal'
READER=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
WINDOW_SHA='f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3'
RUNTIME_SHA='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'
CONTROL_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
VERIFIER_SHA='14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
TEMPLATE_SHA='c698577984011ec4942862e1d1951089def565a774a2d4f4742d24fd8103f2f5'
BOOT_SHA='1524f26e9fd1819b20ddaca7dc9315f9ae0a864836767ba93889abc2a6265fa8'
REFERENCE_SHA='4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')


def require(value,message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def checked(path,sha,name):
    require(digest(path)==sha,'Exact preparation dependency changed')
    spec=importlib.util.spec_from_file_location(name+str(time.time_ns()),path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(digest(path)==sha,'Preparation dependency changed during import')
    return module


def validate_capture(window,result,latch,trigger):
    require(window['schema']=='robotron-post-production-continuity-window-v1' and window['authorized'] is True
            and len(window['actors'])==192 and window['policy']==dict(learner_frames=8000000,
                accepted_dqn_epsilon=8000000,poll_s=1,maximum_observation_gap_s=30,
                maximum_API_age_s=5,no_applied_optimizer_s=60,one_capture_only=True),
            'Exact authorized192 first-both8M policy required')
    require(result['status']=='CAPTURED_FIRST_BOTH_HORIZONS' and result['owner']==window['owner']
            and result['tag']==window['tag'] and result['CPU_verified'] is False
            and result['quality_qualified'] is False and result['promotion'] is False,
            'Only one original unverified capture may prepare its CPU job')
    progress=result['progress']
    require(progress['both_horizons'] is True and all(type(progress[k]) is int and progress[k]>=0
            for k in ('learner_frames','learner_accepted','applied_updates','amp_skips','logical_samples'))
            and progress['learner_frames']>=8000000 and progress['learner_accepted']>=8000000
            and progress['applied_updates']>0 and latch['status']=='LATCH' and latch['progress']==progress
            and latch['job_experiment']==window['experiment'], 'Both original horizons and applied progress required')
    require(trigger['client_count']==192 and trigger['managed_experiment']==window['experiment']
            and trigger['training_enabled'] is True and trigger['measurement_active'] is False,
            'Original acquisition API scope differs')
    require(all(type(trigger[k]) is int and trigger[k]>0 for k in CLOCKS),
            'Exactly four positive actual acquisition clocks required')
    require(window['quality_precommit']['reference_sha256']==REFERENCE_SHA
            and window['quality_precommit']['all_slots']==list(range(4096,4128))
            and window['quality_precommit']['source_package']['sha256']==
                '9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e',
            'Selected1059 reference and32-slot package required')
    require(Path(result['checkpoint']['path'])==MODEL/'managed-checkpoints'/(window['tag']+'.pt'),
            'Canonical selected original checkpoint path required')
    return {key:trigger[key] for key in CLOCKS}


def validate_window_command(fields,owner,window_pin,source_pin):
    argv=['/usr/bin/python3.12','-I','-B',source_pin['path'],'--execute','--job',window_pin['path'],
          '--job-sha256',window_pin['sha256']]
    match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
    require(match is not None,'Original window command archive malformed')
    observed=shlex.split(match[1]);prefix=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH',
        'CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1']
    require(observed[:7]==prefix and len(observed)==8+len(argv)
            and observed[7].startswith('TMPDIR=/') and observed[8:]==argv
            and fields['Id']==owner['unit'], 'Original successful owner did not run selected window/job/source')


def prepare(root_job,root_pin,reader):
    require(root_job['schema']=='robotron-quality32-original-candidate-CPU-preparation-v2',
            'Exact original candidate CPU preparation job required')
    require(root_job['window_source']['sha256']==WINDOW_SHA
            and root_job['CPU_template']['sha256']==TEMPLATE_SHA
            and root_job['CPU_controller']['path']==str(HERE/'control_quality32_review_v1.py')
            and root_job['CPU_controller']['sha256']==CONTROL_SHA,
            'Exact source-bound original template, window and bounded CPU controller required')
    def read(entry,as_json=True):
        return reader.read_pin(entry,as_json=as_json)
    read(root_pin);read(root_job['window_source'],False);read(root_job['CPU_controller'],False)
    window=read(root_job['window_job']);owner=read(root_job['window_owner']);closure=read(root_job['window_closure'])
    runtime=checked(GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',RUNTIME_SHA,'_CPU_prepare_runtime_')
    fields=runtime.archived_closure(closure,owner,read,exit_zero=True)
    validate_window_command(fields,owner,root_job['window_job'],root_job['window_source'])
    observer=checked(Path(root_job['window_source']['path']),WINDOW_SHA,'_CPU_prepare_window_')
    require(observer.process_start(owner['pid']) is None,'Original window owner still exists')
    require(observer.process_start(window['owner']['pid'])==window['owner']['starttime_ticks'],
            'Original main owner changed since capture')
    out=Path(window['output']);result_pin=reader.pin(out/'result.json');result=read(result_pin)
    latch_pin=reader.pin(out/'first-durable-both-horizons.json');latch=read(latch_pin)
    trigger=read(result['trigger_API'])
    require(latch['API']==result['trigger_API'],'Original latch and capture trigger differ')
    floor=validate_capture(window,result,latch,trigger)
    require(window['counter_module']['sha256']=='11380275b544eb7196d33d92b1fbe28a1ae057404120419a2cfa447410c7e430',
            'Exact original exposure-accounting validator required')
    read(window['counter_module'],False)
    counters=checked(Path(window['counter_module']['path']),window['counter_module']['sha256'],'_CPU_prepare_counters_')
    baseline=counters.normalise(read(window['baseline_API']))
    current=counters.normalise(trigger)
    require(all(value[kind]['process_id']==window['owner']['pid'] for value in (baseline,current)
                for kind in ('optimizer_identity','replay_identity')),
            'Original baseline/trigger exposure belongs to another trainer')
    require(observer.progress(current,baseline,baseline)==result['progress'],
            'Actual trigger/baseline exposure disagrees with original declared horizons')
    original=result['checkpoint'];require(reader.pin(original['path'])==original
        and original['identity']['mode']=='0o444' and original['identity']['nlink']==1,
        'Readonly original captured bytes changed')
    transition=result['completed_slot_transition'];after=transition['after']
    require(after['actual_pin']['path']==str(MODEL/'managed_save.request.json.completed')
            and reader.pin(after['actual_pin']['path'])==after['actual_pin'],
            'Actual original completed-slot transition changed')
    after_raw=read(after['archive'],False);request_raw=read(transition['request']['archive'],False)
    require(hashlib.sha256(after_raw).hexdigest()==after['actual_pin']['sha256']
            and json.loads(after_raw)==json.loads(request_raw)==dict(tag=window['tag'])
            and hashlib.sha256(request_raw).hexdigest()==transition['request']['actual_pin']['sha256'],
            'Original request/archive/completed-slot bytes differ')
    require(not (MODEL/'managed_save.request.json').exists(),'Foreign managed save request pending')
    for path,expected in window['held_hashes'].items():
        if path==after['actual_pin']['path']:
            continue
        require(digest(path)==expected,'Original held window input changed')
    template=read(root_job['CPU_template'])
    require(template['verifier_sha256']==VERIFIER_SHA
            and template['phase_snapshot']['boot_checkpoint']['sha256']==BOOT_SHA
            and template['phase_snapshot']['owner']==window['owner']
            and template['phase_snapshot']['purpose']=='startup'
            and template['phase_snapshot']['observed_clients']==0,
            'Actual verified1524 score-carry boot/owner/startup template differs')
    # Historical live numerical-source identities may be writable by the owner;
    # compare the full established PIN rather than weaken or chmod production.
    for pair in template['phase_snapshot']['sources'].values():
        for entry in pair.values():require(reader.pin(entry['path'])==entry,'Original numerical source identity changed')
    for entry in template['source_control_context']['model_package'].values():
        require(reader.pin(entry['path'])==entry,'Original model package identity changed')
    control_bytes=(MODEL/'learning_control.json').read_bytes()
    require(control_bytes==read(template['source_control_context']['archived_control'],False),
            'Actual learning recipe differs from verified template')
    unit=subprocess.run(['systemctl','--user','cat',window['owner']['unit']],capture_output=True,check=True,timeout=10).stdout
    require(unit==read(template['source_control_context']['archived_trainer_unit'],False),
            'Actual trainer unit differs from verified template')
    destination=Path(root_job['destination'])
    require(destination.is_absolute() and destination.resolve()==destination and not destination.exists()
            and re.fullmatch(r'robotron-[A-Za-z0-9_-]+\.service',root_job['CPU_unit']) is not None,
            'New owned CPU preparation and distinct selected unit required')
    verifier=GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
    require(digest(verifier)==VERIFIER_SHA,'Original strict CPU verifier changed')
    destination.mkdir(mode=0o700)
    def save(name,value):return observer.publish(destination/name,value)
    copied=destination/'candidate-readonly-copy.pt'
    with Path(original['path']).open('rb') as source,copied.open('xb') as target:
        shutil.copyfileobj(source,target);target.flush();os.fchmod(target.fileno(),0o444);os.fsync(target.fileno())
    copy_pin=reader.pin(copied)
    require(copy_pin['sha256']==original['sha256'] and copy_pin['bytes']==original['bytes']
            and (copy_pin['identity']['device'],copy_pin['identity']['inode'])!=
                (original['identity']['device'],original['identity']['inode'])
            and reader.pin(original['path'])==original,'Independent readonly CPU copy failed')
    job=copy.deepcopy(template)
    job.update(experiment=window['experiment'],source=original,verification_copy=copy_pin,clock_floor=floor,
               output_directory=str(destination/'verification'))
    context=job['source_control_context']
    context['archived_control']=save('actual-learning-control.json',control_bytes)
    context['archived_trainer_unit']=save('actual-trainer-unit.txt',unit)
    context['provenance']=[root_pin,root_job['window_job'],root_job['window_owner'],root_job['window_closure'],
        result_pin,latch_pin,result['trigger_API'],reader.pin(out/'request-publication.json')]
    phase=job['phase_snapshot'];phase.update(owner=window['owner'],observed_clients=192,purpose='candidate')
    require(window['phase']['record']==phase['phase_record'],'Current original phase record changed')
    record=read(phase['phase_record']);require(record['action']=='resume'
        and record['checkpoint']==phase['boot_checkpoint'],'Actual historical resume checkpoint differs')
    acquisition=dict(schema='robotron-owned-phase-snapshot-acquisition-v1',purpose='candidate',
        experiment=window['experiment'],model_dir=str(MODEL),owner_before=window['owner'],owner_after=window['owner'],
        client_count=192,source_checkpoint={key:original[key] for key in ('path','sha256','bytes')},clock_floor=floor,
        phase_record_sha256=phase['phase_record']['sha256'],boot_checkpoint=phase['boot_checkpoint'],
        tag=result['tag'],completed_slot_transition=transition,stopped_absence=None)
    phase['acquisition']=save('acquisition.json',acquisition)
    job_pin=save('candidate-CPU-job.json',job)
    controller=reader.checked_module('_quality32_CPU_prepare_control_'+str(time.time_ns()),root_job['CPU_controller'])
    config=dict(unit=root_job['CPU_unit'],output=str(destination/'controller-execution'),
        argv=[str(GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(verifier),
            '--execute','--job',job_pin['path'],'--expected-job-sha256',job_pin['sha256'],
            '--expected-verifier-sha256',VERIFIER_SHA],
        properties=['CPUQuota=200%','MemoryMax=4G','RuntimeMaxSec=180','MemorySwapMax=0','TasksMax=128',
            'TimeoutStopSec=5','SendSIGKILL=no'],pins=[controller.pin(path) for path in
                (verifier,Path(job_pin['path']),copied,Path(root_job['CPU_controller']['path']),Path(root_pin['path']))],
        observation_s=240)
    config_pin=save('CPU-controller-config.json',config);controller.checked_config(config_pin['path'])
    report=dict(status='PREPARED_NOT_EXECUTED',root_job=root_pin,candidate=original,verification_copy=copy_pin,
        CPU_job=job_pin,CPU_controller_config=config_pin,clock_floor=floor,original_window_exit0_verified=True,
        actual_boot_checkpoint_sha256=BOOT_SHA,phase_record_sha256=phase['phase_record']['sha256'],
        numerical_model_loaded=False,optimizer_step=False,CPU_verified=False,quality_qualified=False,promotion=False)
    save('preparation.json',report)
    require('torch' not in sys.modules,'Metadata preparation imported numerical runtime')
    return report


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if '--execute' not in argv:
        print('PLAN_ONLY: no reads, copies, queries, outputs, requests or launches');return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--job-sha256',required=True);parser.add_argument('--source-sha256',required=True)
    args=parser.parse_args(argv)
    require(digest(__file__)==args.source_sha256,'Exact preparation source SHA required')
    reader=checked(READER,READER_SHA,'_CPU_prepare_reader_');entry=reader.pin(args.job)
    require(entry['sha256']==args.job_sha256,'Original root job SHA differs')
    report=prepare(reader.read_pin(entry),entry,reader)
    print(json.dumps(dict(status=report['status'],CPU_job=report['CPU_job'],CPU_verified=False)))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
