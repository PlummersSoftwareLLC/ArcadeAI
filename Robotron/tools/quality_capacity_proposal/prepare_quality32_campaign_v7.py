"""Prepare, never launch, one source-bound quality32 campaign after actual CPU PASS.

The final acquisition checks remain the existing tested component. All four
cohorts use the same fixed protocol; this file only assembles the original
observer/native/reviewer metadata and checks current main ownership.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=GAME/'tools/quality_capacity_proposal'
READER=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
SOURCES={
    'acquisition':(HERE/'quality32_acquisition_v4.py','2f8ad3d84b9033c892318d069e0c462bf3f07dd3d0e9e69211008f602153ba70'),
    'cohorts':(HERE/'audit_quality32_evidence_v4.py','f07ccdd098cbf879c7ff98ef26e92e525b7a0ea951c38641fa2b5c0571fa50e3'),
    'observer':(HERE/'quality32_runtime_guard_v8.py','738aafda0f064fd01e6311d1b02c687f551b912d838805ca0aa79247110bbe20'),
    'supervision':(HERE/'supervised_main_fleet_v1.py','38069c081a1e693977d8aaf0389e3979f29a97185f2adc8ce960d45f01f4188d'),
    'observations':(HERE/'supervised_main_observations_v1.py','7f7d481a3e20a239f5f1e1bc961872b47a707041743fe3f7c32363c99555988a'),
    'reviewer':(HERE/'review_closed_quality32_v8.py','fa7883223eca627e89663cede037e1787888080ce06b31fcf6f8462fadd28bdb'),
    'review_controller':(HERE/'control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'),
    'native_controller':(GAME/'tools/eval_capacity_proposal/control_original_pilot.py','db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9'),
    'runtime':(GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'),
    'main':(GAME/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py','f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3'),
}


def require(value,message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path,sha,name):
    require(digest(path)==sha,'Exact campaign preparation dependency changed')
    spec=importlib.util.spec_from_file_location(name+str(time.time_ns()),path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(digest(path)==sha,'Campaign preparation dependency changed during import')
    return module


def archive_safe_command(argv):
    # systemctl show's argv[]= rendering does not preserve quoting for spaces.
    # Use a token-only CLI hypothesis and retain its human explanation in root
    # metadata. Do not weaken the selected reviewer's exact command predicate.
    require(isinstance(argv,list) and argv and all(isinstance(value,str)
        and re.fullmatch(r'[A-Za-z0-9_./=,:+\-]+',value) is not None for value in argv),
        'Native command arguments must retain unambiguous original archive boundaries')
    return argv


def prepare(root,root_pin,reader):
    require(root['schema']=='robotron-quality32-supervised-campaign-preparation-job-v1',
            'Exact post-CPU original campaign preparation job required')
    def read(entry,as_json=True):return reader.read_pin(entry,as_json=as_json)
    read(root_pin)
    modules={name:load(path,sha,'_campaign_prepare_'+name) for name,(path,sha) in SOURCES.items()}
    acquisition,runtime,observer,controller,window=(modules[name] for name in
        ('acquisition','runtime','observer','native_controller','main'))
    evidence={key:root[key] for key in ('phase_cpu_job','phase_cpu_report','phase_cpu_closure','phase_cpu_config',
                                       'window_job','window_result','window_latch','source_package')}
    bundle={key:read(entry) for key,entry in evidence.items()}
    candidate=bundle['phase_cpu_job']['source'];reference=root['reference']
    expected=dict(owner=bundle['window_job']['owner'],experiment=bundle['window_job']['experiment'],
                  tag=bundle['window_job']['tag'])
    binding=dict(candidate=candidate,reference=reference,evidence=evidence,expected_window=expected)
    completion=dict(status='PASS',CPU_report=root['phase_cpu_report'],cpu_job=root['phase_cpu_job'],
        original_controller_release=root['phase_cpu_closure'],actual_candidate=candidate,
        quality_qualified=False,promotion=False)
    bundle['phase_cpu_completion']=completion
    # Authenticate all numerical/phase/first-horizon and actual successful CPU
    # invocation joins before publishing a completion or creating any output.
    acquisition.validate_snapshot(binding,bundle)
    acquisition.validate_window_policy(binding,bundle)
    acquisition.validate_CPU_authority(binding,bundle,read,runtime.archived_closure)
    require(reader.pin(candidate['path'])==candidate and candidate['identity']['mode']=='0o444'
            and candidate['identity']['nlink']==1,'Actual verified candidate changed')
    copied=bundle['phase_cpu_job']['verification_copy']
    require(reader.pin(copied['path'])==copied and reader.pin(reference['path'])==reference,
            'Actual CPU copy or protected reference changed')
    package=read(root['source_package'])
    modules['cohorts'].dependencies()
    main=copy.deepcopy(read(root['main_binding_template']))
    require(len(main['actors'])==192 and len(main['held_hashes'])==195
            and main['owner']==expected['owner'] and main['experiment']==expected['experiment']
            and main['actors']==bundle['window_job']['actors'],'Original main195/192 template differs')
    after=bundle['window_result']['completed_slot_transition']['after']['actual_pin']
    require(after['path']==str(GAME/'models_dqn/managed_save.request.json.completed')
            and reader.pin(after['path'])==after,'Actual capture completed-slot transition changed')
    main['held_hashes'][after['path']]=after['sha256']
    window.owner_and_files(main)
    raw_source=GAME/'tools/eval_capacity_proposal/raw_api_witness_v1.py'
    wire_module=load(raw_source,'9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0','_campaign_prepare_raw')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
        wire=response.read(wire_module.MAX_WIRE_BYTES+1)
    baseline=wire_module.parse_wire(wire)
    window.healthy(baseline,baseline,main['experiment'],time.time())
    parameters=root['campaign_parameters']
    command=archive_safe_command(observer.campaign_command(dict(campaign_parameters=parameters),binding))
    directory=Path(root['output'])
    units=(root['native_unit'],root['review_unit'],root['outer_unit'])
    require(len(set(units))==3 and all(re.fullmatch(r'robotron-[A-Za-z0-9_-]+\.service',value)
        for value in units),'Three distinct new original native/review/outer unit names required')
    require(directory.is_absolute() and directory.resolve()==directory and not directory.exists()
        and not Path(parameters['directory']).exists(),'New original campaign preparation/output required')
    for entry in root['binary_inputs']:
        require(reader.pin(entry['path'])==entry,'Selected executable, ROM or boot input changed')
    require(root['capacity_review']['path'].endswith('/independent-original32-pilot-review/review.json'),
            'Selected closed original capacity review required')
    capacity=read(root['capacity_review'])
    require(capacity['valid'] is True and capacity['status']=='VALID_ONE_ORIGINAL32_ACTOR_RUNTIME_PILOT',
            'Original32 runtime review must pass')
    require(len(root['preceding_originals'])==2
            and len({read(item['owner'])['unit'] for item in root['preceding_originals']})==2,
            'Both distinct preceding original native and outer owners required')
    for item in root['preceding_originals']:
        owner=read(item['owner']);runtime.archived_closure(read(item['closure']),owner,read,exit_zero=True)
    directory.mkdir(mode=0o700)
    def save(name,value):return window.publish(directory/name,value)
    evidence['phase_cpu_completion']=save('CPU-completion.json',completion)
    main['baseline_API']=save('baseline-API.raw.json',wire)
    fleet_transition=read(root['main_fleet_transition'])
    transition_main=read(fleet_transition['current_main_binding'])
    require(all(transition_main[key]==main[key] for key in ('owner','actors','experiment')),
            'Current fleet lineage differs from the precommitted capture main')
    policy,initial_census=modules['supervision'].make_policy(main,fleet_transition['fleet'])
    main['supervision_policy']=save('prospective-main-supervision-policy.json',policy)
    modules['observations'].validate_binding(main,policy,modules['supervision'])
    save('prospective-main-supervision-initial-census.json',modules['observations'].pack(initial_census,modules['supervision']))
    main_pin=save('main-binding-before-native.json',main)
    binding['main_holds']={key:copy.deepcopy(main[key]) for key in ('owner','actors','held_hashes','experiment','supervision_policy')}
    # The normal acquisition entrypoint checks the emitted completion/PIN joins
    # as well as all original candidate/copy/reference bytes.
    acquired=acquisition.review_acquisition(binding,read,runtime.archived_closure)
    template_pin=save('prospective-binding-template.json',binding)
    source_pins={name:reader.pin(path) for name,(path,sha) in SOURCES.items()}
    paths=[root_pin['path'],main_pin['path'],template_pin['path'],*map(str,(item[0] for item in SOURCES.values())),str(raw_source)]
    paths.extend(entry['path'] for entry in evidence.values())
    paths.extend((candidate['path'],copied['path'],reference['path'],main['supervision_policy']['path'],root['main_fleet_transition']['path']))
    paths.extend(str(Path(package['root'])/relative) for relative in package['files'])
    paths.extend(entry['path'] for entry in root['binary_inputs'])
    launch_pins=[controller.pin(path) for path in dict.fromkeys(paths)]
    control_job=dict(schema='robotron-original-quality32-supervised-control-job-v1',
        main_supervision_policy=main['supervision_policy'],main_supervision_source=source_pins['supervision'],
        main_observation_source=source_pins['observations'],
        reviewer_source=source_pins['reviewer'],review_controller_source=source_pins['review_controller'],
        capacity_review=root['capacity_review'],preceding_originals=root['preceding_originals'],
        binding_template=template_pin,main_binding=main_pin,main_guard_source=source_pins['main'],
        binding_directory=str(directory/'runtime-bindings'),review_output=str(directory/'independent-original-quality32-review'),
        review_execution=str(directory/'independent-review-CPU-execution'),review_unit=root['review_unit'],
        binary_inputs=root['binary_inputs'],lease_path=root['lease_path'],lease_identity=root['lease_identity'],
        launch_pins=launch_pins,campaign_parameters=parameters,
        hypothesis_description=root['hypothesis_description'])
    control_job_pin=save('original-quality32-control-job.json',control_job)
    config=dict(unit=root['native_unit'],output=str(directory/'native-execution'),argv=command,
        properties=['CPUQuota=1200%','MemoryMax=12G','MemorySwapMax=0','RuntimeMaxSec=36600','TasksMax=512',
            'TimeoutStopSec=120','KillMode=mixed','SendSIGKILL=no'],pins=launch_pins,observation_s=37200,
        guard_source=source_pins['observer'],pilot_controller_job=control_job_pin)
    config_pin=save('original-native-controller-config.json',config)
    outer_argv=['/usr/bin/python3.12','-I','-B',source_pins['native_controller']['path'],'--execute','--config',
        config_pin['path'],'--config-sha256',config_pin['sha256'],'--source-sha256',source_pins['native_controller']['sha256']]
    outer_plan=save('original-outer-launch-plan.json',dict(unit=root['outer_unit'],
        output=str(directory/'outer-controller-execution'),argv=outer_argv,
        properties=['CPUQuota=200%','MemoryMax=1G','MemorySwapMax=0','RuntimeMaxSec=37800','TasksMax=256',
            'TimeoutStopSec=180','KillMode=mixed','SendSIGKILL=no'],
        no_retry=True,original_attempt=1,guard_source=source_pins['observer'],native_config=config_pin))
    result=dict(status='PREPARED_NOT_LAUNCHED',root_job=root_pin,acquisition=acquired,
        binding_template=template_pin,main_binding=main_pin,native_controller_config=config_pin,
        outer_launch_plan=outer_plan,CPU_completion=evidence['phase_cpu_completion'],
        quality_qualified=False,promotion=False,actual_runtime_changed=False,learning_speed_gain_verified=False)
    save('campaign-preparation.json',result)
    require('torch' not in sys.modules,'Campaign metadata preparation imported numerical runtime')
    return result


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if '--execute' not in argv:
        print('PLAN_ONLY: no reads, queries, outputs, launches or promotion');return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--job-sha256',required=True);parser.add_argument('--source-sha256',required=True)
    args=parser.parse_args(argv)
    require(digest(__file__)==args.source_sha256,'Exact preparation source SHA required')
    reader=load(READER,READER_SHA,'_campaign_prepare_reader');entry=reader.pin(args.job)
    require(entry['sha256']==args.job_sha256,'Original preparation job SHA differs')
    result=prepare(reader.read_pin(entry),entry,reader)
    print(json.dumps(dict(status=result['status'],native_config=result['native_controller_config'],promotion=False)))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
