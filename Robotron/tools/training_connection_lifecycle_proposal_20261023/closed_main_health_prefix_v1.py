"""Source-bound closed predecessor for a prospective four-leg health budget.

No action or import side effect. Require the exact original independent reviewer
job, native job, source family, pair and role, all six actual CPU descriptors,
resource scope and owned releases before reusing its already raw-recomputed
prefix. The current leg still requires its own unfiltered raw replay.
"""
import copy
import json
from pathlib import Path
import time

ORDER=('R1','C1','R2','C2')
CPU_CONTROLLER_SHA='94a398ac68abdbf26cf13b14bbec27d9692a3f250b3a892c70d8bfccbe662dca'
ARCHIVE_SHA='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'


def require(value,message):
    if not value:raise ValueError(message)


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def verified_groups(job,protocol,family,read,h):
    leg=job['quality_leg'];require(leg in ORDER,'Exact current quality leg required');index=ORDER.index(leg)
    predecessor=protocol['prior_case']
    if index==0:
        require(predecessor is None,'Fresh R1 cannot inherit historical transport evidence');return []
    require(type(predecessor)is dict and set(predecessor)=={'review_job','review_report','CPU_config','CPU_closure','CPU_owner'},
            'Exact closed original previous-leg evidence required')
    reviewer=family['leg_reviewer'];h.checked(reviewer)
    controller_pin=family['leg_CPU_controller'];archive_pin=family['native_closure']
    require(controller_pin['sha256']==CPU_CONTROLLER_SHA and archive_pin['sha256']==ARCHIVE_SHA,
            'Exact original660s CPU lifecycle and archive validators required')
    controller=h.load('_prefix_scope_'+str(time.monotonic_ns()),h.checked(controller_pin))
    archive=h.load('_prefix_archive_'+str(time.monotonic_ns()),h.checked(archive_pin))
    config=read(predecessor['CPU_config']);controller.checked_config(predecessor['CPU_config']['path'])
    review_job=read(predecessor['review_job']);report=read(predecessor['review_report'])
    owner=read(predecessor['CPU_owner']);closure=read(predecessor['CPU_closure'])
    fields=archive.archived_closure(closure,owner,read,exit_zero=True)
    expected=['/usr/bin/python3.12','-I','-B',reviewer['path'],'--observe','--job',
        predecessor['review_job']['path'],'--job-sha256',predecessor['review_job']['sha256'],
        '--expected-source-sha256',reviewer['sha256']]
    require(config['argv']==expected and config['observation_s']==720 and
        config['properties']==['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=660',
            'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],'Exact source-bound previous raw-review CPU job/resources required')
    wanted=dict(Id=config['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='11min',
        TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    require(all(fields.get(key)==value for key,value in wanted.items()),'Actual predecessor CPU resources/identity differ')
    actual='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(Path(config['output'])/'tmp')+' '+' '.join(expected)
    require(actual+' ; ignore_errors=no ;'in fields['ExecStart'],'Actual predecessor review argv differs')
    for entry in config['pins']:require(controller.pin(entry['path'])==entry,'Predecessor original scoped input changed')
    require(any(entry['path']==predecessor['review_job']['path']and entry['sha256']==predecessor['review_job']['sha256']
        for entry in config['pins']),'Original selected review job was not controller-pinned')
    for unit in (owner['unit'],owner['timer']):
        require(controller.show(unit)['LoadState']=='not-found','Predecessor original CPU unit remains')
        require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),
                'Predecessor original CPU cgroup remains')
    require(birth(owner['pid'])!=owner['starttime_ticks'],'Original predecessor review birth remains')
    require(report['valid']is report['full_game_score_verified']is True
        and report['quality_qualified']is report['promotion']is False
        and report['review_job']==predecessor['review_job']and report['quality_leg']==ORDER[index-1]
        and report['quality_pair_precommit']==job['quality_pair_precommit'],
        'Predecessor original game/raw-health review did not validate this same fresh pair/role')
    intent=read(report['original_intent']);native=read(review_job['native_job'])
    require(intent['source']==reviewer and intent['review_job']==predecessor['review_job']
        and intent['native_job']==review_job['native_job']
        and review_job['sources']['runtime']==family['runtime']
        and native['source_family_manifest']==job['source_family_manifest']
        and report['source_family_manifest']==job['source_family_manifest']
        and native['quality_pair_precommit']==job['quality_pair_precommit']
        and native['quality_leg']==ORDER[index-1],
        'Original previous reviewer/native/source family/pair join differs')
    require(report['main_health_case_roles']==list(ORDER[:index])
        and report['main_health_engine']==protocol['health_job']['sources']['full_health_engine'],
        'Previous raw-reviewed case prefix is missing a leg or changed engine')
    groups=report['main_health_raw_replay']['transport']['case_groups']
    return copy.deepcopy(groups)
