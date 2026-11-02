"""Explicit archive dependency adapter for the unchanged original observer predicates.

The actual family.native_closure remains the original native CONTROLLER pin.
Only archived_closure comes from the separately selected frozen archive source.
"""
PARENT_REVIEWER_SOURCE = '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score60min-protocol-original01-preparation-20261026/observer-bound4260-family-original01/review_main_health_deadline4260_v1.py'
ARCHIVE_SOURCE_PATH = '/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py'
ARCHIVE_SOURCE_SHA = '8efdb031e52b63e9679b5c1225787019ff86be1d99bf401535d8df53d22d1d9d'

"""Independent original dedicated-worker scope and native/source/protocol joins.

Caller must separately validate the native game/runtime context and replay every
raw main observation. This helper alone never qualifies a cohort or a policy.
"""
from pathlib import Path
import time

RAM_CONTROL_SHA='52372d96fdbfbd2955c260ef864d456e034c8cfe015aa776b4391b5b2e679f8c'

def require(value,message):
    if not value:raise ValueError(message)

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def verify(native,native_pin,native_owner,native_argv,lifecycle_pin,protocol,family,prior_groups,read,h,*,archive_pin):
    sources=family['main_observer']
    require(set(sources)=={'client','worker','protocol','controller','reviewer'}and sources['reviewer']==h.pin(PARENT_REVIEWER_SOURCE),
        'Exact independently selected observer source family required')
    for pin in sources.values():h.checked(pin)
    interpreter=family['main_observer_interpreter'];h.checked(interpreter)
    require(interpreter['path']=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','Exact free314 observer binary required')
    control=h.load('_dedicated_review_control',h.checked(sources['controller']))
    h.checked(family['native_closure'])  # Preserve its actual native-controller source role.
    require(archive_pin['path']==ARCHIVE_SOURCE_PATH and archive_pin['sha256']==ARCHIVE_SOURCE_SHA,
        'Exact separately selected original closure archive source required')
    archive=h.load('_dedicated_review_archives',h.checked(archive_pin))
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
    require(wj['health_job']['sources']['transport']['sha256']=='72edfb7c42106011e9551d59e1e43bba0ee8759b9e39402fd6b11dd4f5e7a0ad',
        'Exact CPU-guarded await-old-API-epoch transport required')
    parent=wj['parent']
    require(parent==life['parent']==outcome['parent']==child['parent']and parent['pid']==native_owner['pid']
        and parent['birth']==native_owner['starttime_ticks']and parent['unit']==native_owner['unit']
        and parent['invocation_id']==native_owner['invocation_id']and parent['argv']==native_argv
        and parent['source']==native['runtime']and parent['job']==native_pin,
        'Worker did not belong to this exact original native parent/source/job')
    require(wj['schema']=='robotron-dedicated-main-health-job-v1'and wj['native_job']==native_pin
        and wj['native_protocol']==native['main_health_protocol']and wj['source_family']==native['source_family_manifest']
        and wj['health_job']==protocol['health_job']and read(wj['prior_groups'])==prior_groups
        and wj['unit_runtime_s']==4260 and wj['original_attempt']==1 and wj['no_retry']is True and wj['poll_s']==.2
        and wj['output']==str(output)and wj['observer_unit']==cfg['unit']
        and wj['parent_started_monotonic_s']==life['native_started_monotonic_s']
        and wj['deadline_monotonic_s']==life['native_deadline_monotonic_s']==life['native_started_monotonic_s']+native['wall_limit_s'],
        'Original worker protocol/context/health/budget/deadline differs')
    require(wj['protocol_source']==sources['protocol']and outcome['protocol_source']==sources['protocol']
        and outcome['worker_source']==sources['worker']and outcome['job']==life['worker_job']and outcome['nonce']==wj['nonce']
        and outcome['success']is True and outcome['error']is None and outcome['signals_received']==[]
        and outcome['all_writer_threads_stopped']is True and outcome['failure_report']is None,
        'Original observer outcome failed, changed or lost writer/source binding')
    require(wj['worker_interpreter']==interpreter and outcome['interpreter']['binary']==interpreter
        and outcome['interpreter']['executable']==interpreter['path']
        and outcome['interpreter']['major_minor']==[3,14]and outcome['interpreter']['GIL_enabled']is False
        and outcome['interpreter']['version'].startswith('3.14.'),'Actual original observer free-threaded runtime differs')
    expected_argv=[interpreter['path'],'-Xgil=0','-I','-B',sources['worker']['path'],'--execute','--job',life['worker_job']['path'],
        '--job-sha256',life['worker_job']['sha256'],'--source-sha256',sources['worker']['sha256']]
    require(cfg['argv']==expected_argv and cfg['properties']==['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=4260',
        'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']and cfg['observation_s']==4320,
        'Exact original independently scoped observer argv/resources required')
    control.checked_config(life['worker_config']['path'])
    fields=archive.archived_closure(closure,owner,read,exit_zero=True)
    expected=dict(Id=cfg['unit'],InvocationID=owner['invocation_id'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',
        RuntimeMaxUSec='1h 11min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual observer resource scope differs')
    actual='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(root/'execution-original01/tmp')+' '+' '.join(expected_argv)
    require(actual+' ; ignore_errors=no ;'in fields['ExecStart'],'Actual original worker command differs')
    for pin in cfg['pins']:require(control.pin(pin['path'])==pin,'Original observer scoped input changed')
    for pin in [interpreter,life['worker_job'],native_pin,native['runtime'],native['main_health_protocol'],native['source_family_manifest'],wj['prior_groups'],family['main_live_control'],*sources.values()]:
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
    publication_stats=outcome['running_projection_publication_stats']
    require(set(publication_stats)=={'attempts','published','coalesced_busy_reader','errors'}
        and all(type(v)is int and v>=0 for v in publication_stats.values())
        and publication_stats['attempts']==publication_stats['published']+publication_stats['coalesced_busy_reader']==len(closed['samples'])==outcome['observed_samples']
        and publication_stats['published']>0 and publication_stats['errors']==0,
        'Every original raw observation must have one published or explicitly coalesced running projection')
    require(closed['health_job']==protocol['health_job']and closed['writer']['all_original_samples_persisted']is closed['writer']['thread_stopped']is True
        and closed['guard_ended_monotonic_s']<=outcome['ended_monotonic_s']
        and int(fields['ExecMainStartTimestampMonotonic'])/1e6<=closed['guard_started_monotonic_s']
        and outcome['ended_monotonic_s']<=int(fields['ExecMainExitTimestampMonotonic'])/1e6<=time.monotonic(),
        'Original observer capture/writer/outcome interval differs')
    require(family['main_live_control']['sha256']==RAM_CONTROL_SHA and wj['live_control_helper']==family['main_live_control']
        and outcome['live_control']==wj['live_control']and outcome['live_control_helper']==family['main_live_control'],
        'Original RAM source/job/outcome binding differs')
    h.checked(family['main_live_control']);storage=h.load('_RAM_control_review',h.checked(family['main_live_control']))
    RAM_review=storage.verify_release(wj['live_control'],life['live_control_release'],root/'live-control-archive',life['worker_job'],life['worker_owner'],life['worker_closure'],read,h)
    release=read(life['live_control_release']);intent=read(release['intent'])
    require({Path(item['original']['path']).name for item in intent['files']}=={'live.json','live.json.lock'},'Successful RAM worker must preserve exactly live data and lock')
    archived=next(item['archived']for item in intent['files']if Path(item['original']['path']).name=='live.json')
    codec=h.load('_RAM_closed_control_codec',h.checked(sources['protocol']));value=codec.decode(read(archived,False))
    require(set(value)==codec.LIVE_KEYS and value['job']==life['worker_job']and value['nonce']==wj['nonce']and value['parent']==wj['parent']
        and value['owner']==outcome['owner']and value['state']=='closed'and value['error']is None and value['outcome']==life['worker_outcome']
        and value['observed_samples']==len(closed['samples'])and value['latest']['index']==len(closed['samples'])-1
        and outcome['ended_monotonic_s']<=value['emitted_monotonic_s']<=int(fields['ExecMainExitTimestampMonotonic'])/1e6,
        'Archived original final RAM control differs from the closed worker')
    return dict(lifecycle=lifecycle_pin,worker_job=life['worker_job'],worker_closure=life['worker_closure'],worker_outcome=life['worker_outcome'],
        closed_report=outcome['closed_report'],initial=outcome['initial'],RAM_control_review=RAM_review,own_CPU2_actual_scope_verified=True,
        actual_source_parent_protocol_deadline_and_original_release_verified=True,caller_native_games_and_all_raw_replay_still_required=True,quality_qualified=False)
