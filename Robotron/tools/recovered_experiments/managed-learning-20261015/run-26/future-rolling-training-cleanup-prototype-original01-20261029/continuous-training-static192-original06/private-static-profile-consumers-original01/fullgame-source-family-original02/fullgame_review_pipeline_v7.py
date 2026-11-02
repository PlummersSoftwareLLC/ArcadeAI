"""Source and closed-scope joins shared by recovered-round fullgame reviews.

Metadata only. This module never launches, retries, promotes, or changes main.
"""
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE=ROOT/'logs/managed-learning-20261015/run-26'
HERE=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
LOCAL=Path(__file__).resolve().parent
ORIGINAL=BASE/'future-fixed-slot64-full-game-protocol-original01-preparation-20261024'
PARENT=BASE/'quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024'
CPU_CONTROLLER=ORIGINAL/'extended-review-resources-original01/control_owned_health_CPU1980_v1.py'
CPU_CONTROLLER_SHA='f96b6a954834ed204a4c1207ea336ccc14f5b44242f853c7b61c0a8dad8128ff'
NUMERIC=ORIGINAL/'scientific-protocol-interface-correction-original01/assess_quality32_quota64_selected_original01_v2.py'
NUMERIC_SHA='6b6bdc1230c50db5b143c7f86f5e150b08f0e25dfb75a4615ab8d460b5623bf2'
ORDER=['R1','C1','R2','C2']
CPU_PROPERTIES=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=1980','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']


def require(value,reason):
    if not value:raise ValueError(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def helpers():
    path=ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    import hashlib
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Actual helper changed')
    return load('_fullgame_pipeline_helpers',path)


def read(pin,as_json=True):
    path=ROOT/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    import hashlib
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Actual immutable reader changed')
    return load('_fullgame_pipeline_reader',path).read_pin(pin,as_json=as_json)


def cpu_controller(h):
    require(h.pin(CPU_CONTROLLER)['sha256']==CPU_CONTROLLER_SHA,'Original bounded CPU controller changed')
    return load('_fullgame_pipeline_CPU_controller',CPU_CONTROLLER)


def sources(h):
    before=read(h.pin(PARENT/'04-candidate/independent-review-job.json'))['sources']
    result=dict(before)
    result.update(runtime=h.pin(LOCAL/'run_fullgame_rounds_v7.py'),control=h.pin(LOCAL/'control_fullgame_rounds_v6.py'),
        main_health_engine=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-original01/continuous_static192_transport_v1.py')),main_prefix_validator=h.pin(LOCAL/'fullgame_round_contract_v7.py'),
        main_observer_reviewer=h.pin(LOCAL/'review_fullgame_round_observer_v7.py'))
    for pin in result.values():h.checked(pin)
    return result


def validate_packet(case,packet,config,h):
    subject=read(case['native_job']);native_config=read(packet['controller_config'])
    q=load('_fullgame_pipeline_leg_reviewer',LOCAL/'review_fullgame_rounds_v7.py')
    require(packet['schema']=='robotron-original-quota64-independent-leg-review-job-v1'
        and packet['native_job']==case['native_job']and packet['acceptance']==case['acceptance']
        and packet['sources']==sources(h)
        and packet['sources']['runtime']==subject['runtime']
        and packet['output']==str(Path(case['native_job']['path']).parent/'independent-quality-leg-review-original01'),
        'Exact original native/scope/source review packet required')
    q.validate_scope(subject,case['native_job'],read(case['acceptance']),native_config)
    native_control=load('_fullgame_pipeline_native_control',LOCAL/'control_fullgame_rounds_v6.py')
    for pin in native_config['pins']:require(native_control.pin(pin['path'])==pin,'Native controller input differs')
    job_pin=h.pin(Path(case['native_job']['path']).parent/'independent-review-job.json')
    reviewer=h.pin(LOCAL/'fullgame_review_entry_v6.py')
    require(config['argv']==['/usr/bin/python3.12','-I','-B',reviewer['path'],'--observe','--job',job_pin['path'],
        '--job-sha256',job_pin['sha256'],'--expected-source-sha256',reviewer['sha256']]
        and config['properties']==CPU_PROPERTIES and config['observation_s']==2040
        and config['output']==str(Path(case['native_job']['path']).parent/'independent-review-execution-original01'),
        'Exact original reviewer argv/resources/output required')
    return subject


def owned_scope(config_pin,h,*,native=False):
    config=read(config_pin);root=Path(config['output'])
    owner_pin=h.pin(root/'root-original-identity.json');closure_pin=h.pin(root/'root-original-result-and-owned-release.json')
    owner=read(owner_pin);closure=read(closure_pin)
    archive_path=ROOT/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
    require(h.pin(archive_path)['sha256']=='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','Actual original archive verifier changed')
    archive=load('_fullgame_pipeline_original_archive',archive_path)
    fields=archive.archived_closure(closure,owner,read,exit_zero=True)
    require(owner['unit']==config['unit']and closure['original']==owner,'Original scope belongs to another configuration')
    require(all(token in fields['ExecStart']for token in config['argv']),'Actual original argv/source differs')
    if native:
        reviewer=load('_fullgame_pipeline_closed_native_reviewer',LOCAL/'review_fullgame_rounds_v7.py')
        interval=reviewer.validate_native_fields(fields,config,owner,archive.duration_seconds)
    else:
        require(config['properties']==CPU_PROPERTIES and config['observation_s']==2040,'Exact declared CPU review bounds required')
        cpu_controller(h).checked_config(config_pin['path'])
        require(archive.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
            and fields['MemorySwapMax']=='0'and archive.duration_seconds(fields['RuntimeMaxUSec'])==1980
            and fields['TasksMax']=='128'and archive.duration_seconds(fields['TimeoutStopUSec'])==5
            and fields['SendSIGKILL']=='no'and fields['Restart']=='no'and fields['NRestarts']=='0',
            'Actual original CPU review resources differ')
        interval=tuple(int(fields[key])/1e6 for key in ('ExecMainStartTimestampMonotonic','ExecMainExitTimestampMonotonic'))
    require(0<interval[0]<=interval[1],'Actual original scope interval missing')
    proc=Path('/proc',str(owner['pid']),'stat')
    require(not proc.exists()or int(proc.read_text().rsplit(')',1)[1].split()[19])!=owner['starttime_ticks'],'Original scope birth remains')
    control=cpu_controller(h)
    require(all(control.show(unit)['LoadState']=='not-found'for unit in (owner['unit'],owner['timer'])),'Original unit/timer remains')
    observed=read(h.pin(root/'original-first-observed-show-command.json'))
    live=dict(line.split('=',1)for line in read(observed['stdout'],False).decode().splitlines()if'='in line)
    require(live['MainPID']==str(owner['pid'])and live['InvocationID']==owner['invocation_id']
        and live['ControlGroup'].startswith('/user.slice/')and not Path('/sys/fs/cgroup'+live['ControlGroup']).exists(),
        'Original cgroup/live ownership remains or differs')
    return dict(owner_pin=owner_pin,closure_pin=closure_pin,owner=owner,fields=fields,interval=interval)


def seal_controller_result(config_pin,path,h,*,native,observed_controller_exit):
    require(type(observed_controller_exit)is int and observed_controller_exit==0,'Actual original controller terminal exit0 required')
    closed=owned_scope(config_pin,h,native=native)
    expected='controller-original-result.json'if native else'independent-review-controller-original-result.json'
    config=read(config_pin)
    require(path==Path(config['output']).parent/expected,'Exact original controller result path required')
    return h.put(path,dict(actual_exit=observed_controller_exit,original_attempt=1,no_retry=True,
        closure=closed['closure_pin'],original_owner=closed['owner_pin'],original_config=config_pin,
        source=h.pin(Path(__file__).resolve())))


def numerical_decision(legs,reference_sha,candidate_sha,h):
    require(h.pin(NUMERIC)['sha256']==NUMERIC_SHA,'Original quota64 numerical reducer changed')
    require(len(legs)==4 and all(leg['cohort']['count']==64 for leg in legs),'Exactly64 actual complete games per leg required')
    identities=[tuple(leg[k])for leg in legs for k in ('native_identity','review_identity')]
    require(len(set(identities))==8,'Native/review scopes must all be independent')
    numeric=load('_fullgame_pipeline_original_quota64_numeric',NUMERIC)
    result=numeric.assess_validated_cohorts(legs,reference_sha,candidate_sha)
    return dict(original_quota64_decision=result,effective_complete_game_minimum=64,
        full_game_quality_qualified=result['all_candidate_gates_passed'],promotion=False,
        causal_learning_speed_gain_established=False,useful_throughput_gain_established=False)
