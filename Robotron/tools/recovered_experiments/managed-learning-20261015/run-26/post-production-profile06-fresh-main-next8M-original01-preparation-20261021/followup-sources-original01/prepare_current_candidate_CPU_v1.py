"""Prepare, never execute, strict CPU verification of one actual current capture.

The unchanged strict verifier reads the normal canonical tagged producer and a
separate readonly CPU copy. A distinct captured readonly archive is reserved for
evaluation. No producer chmod, model load, save request, restart or promotion.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'
MODEL=G/'models_dqn'
L=P.parent/'profile06-production-continuity-main-inputs-original01-preparation-20261021/live-original01'
VERIFIER=G/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
VERIFIER_SHA='14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
TEMPLATE_SHA='9664ab3dfd17e49b5d49e1481139ef846b035d606e79b89ee37cfdfc5cfb9275'
BOOT_SHA='8cc9e90014cf8aa3a2bffd0d7fc4943cfe0301cd44d7b6f9a40e83d0ae28f764'
PROVENANCE_SHA='13263bca33e612195d79d2fa28e20ba6910294b2ef72f5520280916b4dd8644e'
CONTROL_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
READER=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'


def require(value,message):
    if not value:raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def checked(entry,name,reader):
    reader.read_pin(entry,as_json=False)
    spec=importlib.util.spec_from_file_location(name+str(time.time_ns()),entry['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    reader.read_pin(entry,as_json=False);return module


def prepare(root,root_pin,reader):
    require(root['schema']=='robotron-current-window-candidate-CPU-preparation-v1','Exact current CPU preparation required')
    read=reader.read_pin;read(root_pin)
    expected=dict(provenance_source=PROVENANCE_SHA,CPU_template=TEMPLATE_SHA,CPU_controller=CONTROL_SHA,
        linux_source='3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2',
        main_guard='f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
        archive_checker='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
    for key,sha in expected.items():require(root[key]['sha256']==sha,'Exact preparation input changed: '+key);read(root[key],as_json=False)
    require(Path(root['provenance_source']['path'])==Path(__file__).with_name('current_window_provenance_v1.py')
        and Path(root['CPU_template']['path'])==L/'startup/CPU-job.json'
        and Path(root['CPU_controller']['path'])==G/'tools/quality_capacity_proposal/control_quality32_review_v1.py',
        'Current provenance/template/controller paths differ')
    provenance=checked(root['provenance_source'],'_current_capture_provenance_',reader)
    runtime=checked(root['archive_checker'],'_current_capture_archives_',reader)
    linux=checked(root['linux_source'],'_current_capture_linux_',reader)
    guard=checked(root['main_guard'],'_current_capture_main_guard_',reader)
    proof=provenance.review(root,lambda e,as_json=True:read(e,as_json=as_json),reader.pin,
        runtime.archived_closure,linux.process_start,linux.show)
    window=proof['window_view'];original=proof['normal_producer'];candidate=proof['evaluation_candidate'];floor=proof['clock_floor']
    linux.live_owner(window['owner']);guard.owner_and_files(proof['main_after'])
    require(reader.pin(original['path'])==original and original['identity']['mode']=='0o664'
        and reader.pin(candidate['path'])==candidate and candidate['identity']['mode']=='0o444',
        'Normal producer/readonly evaluation candidate changed')
    template=read(root['CPU_template']);phase=template['phase_snapshot']
    require(template['verifier_sha256']==VERIFIER_SHA and phase['boot_checkpoint']['sha256']==BOOT_SHA
        and phase['owner']==window['owner'] and phase['purpose']=='startup' and phase['observed_clients']==0
        and phase['phase_record']==window['phase']['record'],'Actual current8cc9 boot/owner/startup template differs')
    for pair in phase['sources'].values():
        for entry in pair.values():require(reader.pin(entry['path'])==entry,'Actual source/archive identity changed')
    for entry in template['source_control_context']['model_package'].values():
        require(reader.pin(entry['path'])==entry,'Actual installed numerical model source changed')
    control_bytes=(MODEL/'learning_control.json').read_bytes()
    require(control_bytes==read(template['source_control_context']['archived_control'],as_json=False),
        'Current numerical learning recipe differs from the verified boot')
    command=subprocess.run(['systemctl','--user','cat',window['owner']['unit']],capture_output=True,timeout=10)
    require(command.returncode==0,'Current trainer unit could not be observed');unit=command.stdout
    require(unit==read(template['source_control_context']['archived_trainer_unit'],as_json=False),'Current trainer unit differs from boot')
    destination=Path(root['destination'])
    require(destination==P/'candidate-CPU-original01' and not destination.exists()
        and root['CPU_unit']=='robotron-profile06-production-next8M-candidate-CPU-original01-20261021.service',
        'One fresh distinct current candidate CPU scope required')
    require(digest(VERIFIER)==VERIFIER_SHA,'Original strict CPU verifier changed')
    destination.mkdir(mode=0o700)
    def save(name,value):return linux.publish(destination/name,value)
    proof_pin=save('actual-original-current-capture-provenance.json',proof)
    copied=destination/'candidate-readonly-copy.pt'
    with Path(original['path']).open('rb') as source,copied.open('xb') as target:
        shutil.copyfileobj(source,target,1<<20);target.flush();os.fsync(target.fileno());os.fchmod(target.fileno(),0o444)
    copy_pin=reader.pin(copied)
    require(copy_pin['sha256']==original['sha256']==candidate['sha256'] and copy_pin['bytes']==original['bytes']==candidate['bytes']
        and len({(entry['identity']['device'],entry['identity']['inode']) for entry in [original,candidate,copy_pin]})==3
        and reader.pin(original['path'])==original and reader.pin(candidate['path'])==candidate,
        'Normal producer/evaluation archive/independent CPU copy failed')
    job=copy.deepcopy(template);job.update(experiment=window['experiment'],source=original,verification_copy=copy_pin,
        clock_floor=floor,output_directory=str(destination/'verification'))
    context=job['source_control_context'];context['archived_control']=save('actual-learning-control.json',control_bytes)
    context['archived_trainer_unit']=save('actual-trainer-unit.txt',unit)
    context['provenance']=[root_pin,root['window_plan'],root['window_job'],root['window_owner'],root['window_closure'],
        proof['original_window_result'],proof['original_window_latch'],proof['original_capture_result'],
        proof['original_capture_job'],proof['original_watch_result'],proof['original_publication'],proof_pin]
    phase=job['phase_snapshot'];phase.update(owner=window['owner'],observed_clients=192,purpose='candidate')
    record=read(phase['phase_record']);require(record['action']=='resume' and record['checkpoint']==phase['boot_checkpoint'],
        'Actual current resume checkpoint differs')
    acquisition=dict(schema='robotron-owned-phase-snapshot-acquisition-v1',purpose='candidate',experiment=window['experiment'],
        model_dir=str(MODEL),owner_before=window['owner'],owner_after=window['owner'],client_count=192,
        source_checkpoint={key:original[key] for key in ['path','sha256','bytes']},clock_floor=floor,
        phase_record_sha256=phase['phase_record']['sha256'],boot_checkpoint=phase['boot_checkpoint'],tag=window['tag'],
        completed_slot_transition=proof['phase_CPU_transition'],stopped_absence=None)
    phase['acquisition']=save('acquisition.json',acquisition);jp=save('candidate-CPU-job.json',job)
    controller=checked(root['CPU_controller'],'_current_capture_CPU_controller_',reader)
    config=dict(unit=root['CPU_unit'],output=str(destination/'controller-execution'),
        argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(VERIFIER),'--execute','--job',jp['path'],
            '--expected-job-sha256',jp['sha256'],'--expected-verifier-sha256',VERIFIER_SHA],
        properties=['CPUQuota=200%','MemoryMax=4G','RuntimeMaxSec=180','MemorySwapMax=0','TasksMax=128',
            'TimeoutStopSec=5','SendSIGKILL=no'],pins=[controller.pin(path) for path in [VERIFIER,Path(jp['path']),copied,
                Path(root['CPU_controller']['path']),Path(root_pin['path']),Path(root['provenance_source']['path'])]],observation_s=240)
    config_pin=save('CPU-controller-config.json',config);controller.checked_config(config_pin['path'])
    result=dict(status='PREPARED_NOT_EXECUTED',root_job=root_pin,original_normal_producer=original,
        candidate=candidate,verification_copy=copy_pin,CPU_job=jp,CPU_controller_config=config_pin,clock_floor=floor,
        current_window_provenance=proof_pin,original_window_exit0_verified=True,normal_producer_mode_preserved=True,
        actual_boot_checkpoint_sha256=BOOT_SHA,phase_record_sha256=phase['phase_record']['sha256'],
        numerical_model_loaded=False,optimizer_step=False,CPU_verified=False,quality_qualified=False,promotion=False)
    save('preparation.json',result);require('torch' not in sys.modules,'Preparation imported a numerical runtime');return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:print('PLAN_ONLY: no reads, copies, requests or runtime actions');return 0
    require(args.job and digest(__file__)==args.expected_source_sha256 and digest(args.job)==args.expected_job_sha256,
        'Exact original source/job required')
    require(digest(READER)==READER_SHA,'Original reader changed')
    spec=importlib.util.spec_from_file_location('_current_candidate_CPU_reader',READER)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader);entry=reader.pin(args.job)
    report=prepare(reader.read_pin(entry),entry,reader);print(json.dumps(dict(status=report['status'],CPU_job=report['CPU_job'],CPU_verified=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())
