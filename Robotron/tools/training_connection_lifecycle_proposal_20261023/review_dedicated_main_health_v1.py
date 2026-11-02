"""Independent original dedicated-worker scope and native/source/protocol joins.

Caller must separately validate the native game/runtime context and replay every
raw main observation. This helper alone never qualifies a cohort or a policy.
"""
from pathlib import Path
import time

def require(value,message):
    if not value:raise ValueError(message)

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def verify(native,native_pin,native_owner,native_argv,lifecycle_pin,protocol,family,prior_groups,read,h):
    sources=family['main_observer']
    require(set(sources)=={'client','worker','protocol','controller','reviewer'}and sources['reviewer']==h.pin(__file__),
        'Exact independently selected observer source family required')
    for pin in sources.values():h.checked(pin)
    control=h.load('_dedicated_review_control',h.checked(sources['controller']))
    archive=h.load('_dedicated_review_archives',h.checked(family['native_closure']))
    life=read(lifecycle_pin);root=Path(native['output'])/'main-health-scope';output=Path(native['output'])/'main-observations'
    require(lifecycle_pin['path']==str(root/'native-observer-lifecycle.json')and life['schema']=='robotron-native-dedicated-observer-lifecycle-v1'
        and life['native_job']==native_pin and life['success']is True and life['actual_controller_exit']==0
        and life['all_owned_worker_and_controller_processes_reaped']is True and life['original_scope_released']is True,
        'Original native observer did not close successfully')
    expected_paths=dict(worker_job=root/'job.json',worker_config=root/'controller-config.json',
        worker_owner=root/'execution-original01/root-original-identity.json',worker_closure=root/'execution-original01/root-original-result-and-owned-release.json',
        worker_outcome=output/'outcome.json',controller_child=root/'original-controller-child.json')
    for key,path in expected_paths.items():require(life[key]['path']==str(path),'Original observer artifact escaped: '+key)
    wj=read(life['worker_job']);cfg=read(life['worker_config']);owner=read(life['worker_owner']);closure=read(life['worker_closure']);outcome=read(life['worker_outcome']);child=read(life['controller_child'])
    parent=wj['parent']
    require(parent==life['parent']==outcome['parent']==child['parent']and parent['pid']==native_owner['pid']
        and parent['birth']==native_owner['starttime_ticks']and parent['unit']==native_owner['unit']
        and parent['invocation_id']==native_owner['invocation_id']and parent['argv']==native_argv
        and parent['source']==native['runtime']and parent['job']==native_pin,
        'Worker did not belong to this exact original native parent/source/job')
    require(wj['schema']=='robotron-dedicated-main-health-job-v1'and wj['native_job']==native_pin
        and wj['native_protocol']==native['main_health_protocol']and wj['source_family']==native['source_family_manifest']
        and wj['health_job']==protocol['health_job']and read(wj['prior_groups'])==prior_groups
        and wj['unit_runtime_s']==9660 and wj['original_attempt']==1 and wj['no_retry']is True and wj['poll_s']==.2
        and wj['output']==str(output)and wj['observer_unit']==cfg['unit']
        and wj['parent_started_monotonic_s']==life['native_started_monotonic_s']
        and wj['deadline_monotonic_s']==life['native_deadline_monotonic_s']==life['native_started_monotonic_s']+native['wall_limit_s'],
        'Original worker protocol/context/health/budget/deadline differs')
    require(wj['protocol_source']==sources['protocol']and outcome['protocol_source']==sources['protocol']
        and outcome['worker_source']==sources['worker']and outcome['job']==life['worker_job']and outcome['nonce']==wj['nonce']
        and outcome['success']is True and outcome['error']is None and outcome['signals_received']==[]
        and outcome['all_writer_threads_stopped']is True and outcome['failure_report']is None,
        'Original observer outcome failed, changed or lost writer/source binding')
    expected_argv=['/usr/bin/python3.12','-I','-B',sources['worker']['path'],'--execute','--job',life['worker_job']['path'],
        '--job-sha256',life['worker_job']['sha256'],'--source-sha256',sources['worker']['sha256']]
    require(cfg['argv']==expected_argv and cfg['properties']==['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=9660',
        'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']and cfg['observation_s']==9720,
        'Exact original independently scoped observer argv/resources required')
    control.checked_config(life['worker_config']['path'])
    fields=archive.archived_closure(closure,owner,read,exit_zero=True)
    expected=dict(Id=cfg['unit'],InvocationID=owner['invocation_id'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',
        RuntimeMaxUSec='2h 41min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual observer resource scope differs')
    actual='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(root/'execution-original01/tmp')+' '+' '.join(expected_argv)
    require(actual+' ; ignore_errors=no ;'in fields['ExecStart'],'Actual original worker command differs')
    for pin in cfg['pins']:require(control.pin(pin['path'])==pin,'Original observer scoped input changed')
    for pin in [life['worker_job'],native_pin,native['runtime'],native['main_health_protocol'],native['source_family_manifest'],wj['prior_groups'],*sources.values()]:
        require(any(entry['path']==pin['path']and entry['sha256']==pin['sha256']for entry in cfg['pins']),
            'Required original observer launch pin missing')
    for unit in [owner['unit'],owner['timer']]:require(control.show(unit)['LoadState']=='not-found','Original observer unit remains')
    require(birth(owner['pid'])!=owner['starttime_ticks']and birth(child['pid'])!=child['birth'],'Original observer/controller birth remains')
    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+owner['unit']
    require(not Path('/sys/fs/cgroup'+cgroup).exists()and parent['cgroup']!=cgroup,'Observer did not own/release its separate allocation')
    require(outcome['owner']==dict(pid=owner['pid'],starttime_ticks=owner['starttime_ticks'],unit=owner['unit'],invocation_id=owner['invocation_id'],cgroup=cgroup,uid=parent['uid']),
        'Original worker owner differs from the actual scope')
    controller_argv=['/usr/bin/python3.12','-I','-B',sources['controller']['path'],'--execute','--config',life['worker_config']['path'],
        '--expected-source-sha256',sources['controller']['sha256']]
    require(child['argv']==controller_argv,'Original native-owned observer controller command differs')
    require(outcome['closed_report']['path']==str(output/'closed-full-health-report.json')and outcome['ended_monotonic_s']<wj['deadline_monotonic_s'],
        'Original observer closed past its path/deadline')
    closed=read(outcome['closed_report'])
    require(closed['health_job']==protocol['health_job']and closed['writer']['all_original_samples_persisted']is closed['writer']['thread_stopped']is True
        and closed['guard_ended_monotonic_s']<=outcome['ended_monotonic_s']
        and int(fields['ExecMainStartTimestampMonotonic'])/1e6<=closed['guard_started_monotonic_s']
        and outcome['ended_monotonic_s']<=int(fields['ExecMainExitTimestampMonotonic'])/1e6<=time.monotonic(),
        'Original observer capture/writer/outcome interval differs')
    return dict(lifecycle=lifecycle_pin,worker_job=life['worker_job'],worker_closure=life['worker_closure'],worker_outcome=life['worker_outcome'],
        closed_report=outcome['closed_report'],initial=outcome['initial'],own_CPU2_actual_scope_verified=True,
        actual_source_parent_protocol_deadline_and_original_release_verified=True,caller_native_games_and_all_raw_replay_still_required=True,quality_qualified=False)
