"""Review actual current-window/capture originals; return explicit internal views.

Views bridge metadata layouts only. They are never published as producer jobs,
receipts or journals. Original bytes, exits, lifecycle records and full8 pins
remain separate required evidence. No model loading or runtime mutation occurs.
"""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shlex
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'
WINDOW_PLAN_SHA='d237f4f48c5c0c38e5df87850c34e0b4eab50e756b23c8bb6816c62e99db3153'
WINDOW_JOB_SHA='67e758d3ba52a2db53458590f4ce0e718cc6eec9a7e00a0427b27d8de45179af'
WINDOW_SOURCE_SHA='57862f4b125941926ed481a9e6bbec554e820b69e4a140ec429e6ec59963a2c8'
CAPTURE_SHA='b967caf7f2be7ac577f472330d38ab5120fc7f79f6742b99cb1082ef9ee54341'
REFERENCE_SHA='c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
PACKAGE_SHA='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')
FULL8={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}


def require(value,message):
    if not value:raise ValueError(message)


def module(entry,name,read):
    read(entry,False)
    spec=importlib.util.spec_from_file_location(name+str(time.time_ns()),entry['path'])
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    read(entry,False);return result


def quality_policy(reference,package):
    require(reference['sha256']==REFERENCE_SHA and package['sha256']==PACKAGE_SHA,'Fixed next reference/package differs')
    return dict(reference=reference['path'],reference_sha256=REFERENCE_SHA,order=['reference','candidate','reference','candidate'],
        same_fixed_admission_s=5400,same_whole_cohort_timeout_s=9000,minimum_games=50,all_slots=list(range(4096,4128)),
        full_tails=True,max_attempts=1,extensions=False,individual_mean_ratio=1.05,individual_median_ratio=1.0,
        reference_pool='Both fresh reference cohorts only',no_historical_rows=True,automatic_promotion=False,
        source_package=package,completion_policy='confirmed_reset_reserves_v1',mandatory_original_terminal_journal_readback=True)


def common_owner(actual,original):
    require(all(actual.get(k)==original[k] for k in ('pid','starttime_ticks','unit','invocation_id')),
        'Original owner/birth/invocation differs')


def duration_seconds(value):
    units={'us':1e-6,'ms':1e-3,'s':1,'min':60,'h':3600,'d':86400}
    pattern=r'(\d+(?:\.\d+)?)(us|ms|min|s|h|d)'
    require(isinstance(value,str) and re.sub(pattern,'',value).strip()=='','Invalid archived duration')
    tokens=re.findall(pattern,value);require(bool(tokens),'Missing archived duration')
    return sum(float(number)*units[unit] for number,unit in tokens)


def resources(fields,seconds):
    require(duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
        and fields['MemorySwapMax']=='0' and duration_seconds(fields['RuntimeMaxUSec'])==seconds
        and fields['TasksMax']=='128' and duration_seconds(fields['TimeoutStopUSec'])==5
        and fields['Restart']==fields['SendSIGKILL']=='no','Actual original resource bounds differ')


def command(fields,config):
    expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
    match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
    require(match is not None and shlex.split(match[1])==expected,'Actual original argv differs')


def historical_slot(pair,expected_path,read):
    entry=pair['actual_pin'];raw=read(pair['archive'],False)
    require(set(entry['identity'])==FULL8 and entry['path']==str(expected_path)
        and entry['identity']['bytes']==entry['bytes'] and entry['identity']['uid']==1001
        and entry['identity']['nlink']==1 and entry['identity']['mode']=='0o664'
        and hashlib.sha256(raw).hexdigest()==entry['sha256'] and len(raw)==entry['bytes']
        and pair['archive']['path']!=entry['path'],'Original normal slot/archive identity differs')
    return raw


def validate_capture_values(plan,binding,result,captured,capture_job,publication,watch,request_raw,before_raw,after_raw):
    owner=plan['owner'];tag=plan['capture_tag'];source=captured['source'];archive=captured['checkpoint']
    require(result['status']=='CAPTURED_FIRST_BOTH_HORIZONS' and result['owner']==owner
        and result['checkpoint']==archive and result['normal_producer']==source
        and result['CPU_verified'] is result['quality_qualified'] is result['promotion'] is False,
        'Original unverified single-window result differs')
    require(captured['status']=='ORIGINAL_CAPTURE_ARCHIVED_NORMAL_PRODUCER_PRESERVED'
        and captured['owner']==owner and captured['normal_producer_mode_preserved'] is True
        and captured['original_request_retried'] is False,'Original normal capture did not pass')
    require(capture_job['mode']=='production' and capture_job['owner']==owner and capture_job['tag']==tag
        and capture_job['source']==capture_job['controller_source']==plan['capture_source']
        and capture_job['main_binding']==plan['binding'] and capture_job['latch']==result['latch'],
        'Original production capture job differs')
    require(source['path']==str(G/'models_dqn/managed-checkpoints'/(tag+'.pt'))
        and source['identity']['mode']=='0o664' and archive['path']==str(P/'capture-original01/candidate-readonly.pt')
        and archive['identity']['mode']=='0o444' and source['sha256']==archive['sha256']
        and source['bytes']==archive['bytes']>(200<<20)
        and (source['identity']['device'],source['identity']['inode'])!=(archive['identity']['device'],archive['identity']['inode']),
        'Normal canonical producer and independent readonly candidate differ')
    require(publication['owner']==owner and publication['controller']==captured['controller']
        and publication['request']['path']==str(G/'models_dqn/managed_save.request.json')
        and set(publication['request']['identity'])==FULL8 and publication['request']['identity']['nlink']==1
        and publication['request']['identity']['mode']=='0o444'
        and publication['request']['sha256']==hashlib.sha256(request_raw).hexdigest()
        and publication['request']['bytes']==len(request_raw)
        and json.loads(request_raw)==json.loads(after_raw)==dict(tag=tag),'Actual exclusive request/completion bytes differ')
    before=captured['completed_slot_transition']['before'];after=captured['completed_slot_transition']['after']
    slot=str(G/'models_dqn/managed_save.request.json.completed')
    require(before is not None and before['actual_pin']['sha256']==binding['held_hashes'][slot]
        and hashlib.sha256(before_raw).hexdigest()==before['actual_pin']['sha256']
        and after['actual_pin']['sha256']==hashlib.sha256(after_raw).hexdigest()
        and result['completed_slot_transition']==captured['completed_slot_transition'],
        'Actual baseline/completed-slot transition differs')
    require(watch['status']=='ORIGINAL_CONTROLLER_EXIT_OBSERVED' and watch['controller_alive'] is False
        and watch['restart_retry'] is False and watch['recovery']==dict(status='NO_RECORDED_SAVE_HOLD',runtime_changed=False),
        'Independent original watch did not observe normal hold release')
    times=[publication['hold_started_unix_s'],publication['request_unix_s'],publication['hold_released_unix_s']]
    require(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in times)
        and times[0]<=times[1]<=times[2],'Original publication chronology differs')


def review(root,read,pin,archived_closure,process_start,unit_fields):
    """Read one actually completed original window and both owned capture units."""
    require(root['window_plan']['sha256']==WINDOW_PLAN_SHA and root['window_job']['sha256']==WINDOW_JOB_SHA
        and root['window_source']['sha256']==WINDOW_SOURCE_SHA,'Exact fixed current window originals required')
    plan=read(root['window_plan']);job=read(root['window_job']);read(root['window_source'],False)
    require(job['schema']=='profile06-production-next8M-window-job-v1' and job['authorized'] is True
        and job['plan']==root['window_plan'] and job['observer_source']==plan['observer_source']==root['window_source']
        and Path(job['output'])==P/'window-original01' and plan['capture_source']['sha256']==CAPTURE_SHA
        and plan['reference']['sha256']==REFERENCE_SHA and plan['source_package']['sha256']==PACKAGE_SHA,
        'Original window job/plan/source/reference scope differs')
    owner=read(root['window_owner']);closure=read(root['window_closure'])
    require(owner['pid']==3416136 and owner['starttime_ticks']==65330980
        and owner['unit']==plan['unit'] and owner['invocation_id']=='3cc346fa3fb0464c845f6792ad8f9433',
        'Actual original window owner differs')
    fields=archived_closure(closure,owner,read,exit_zero=True)
    resources(fields,5700)
    config=dict(output=str(P/'window-execution-original01'),argv=['/usr/bin/python3.12','-I','-B',root['window_source']['path'],
        '--execute','--job',root['window_job']['path'],'--expected-job-sha256',root['window_job']['sha256']])
    command(fields,config)
    require(process_start(owner['pid']) is None and not Path('/sys/fs/cgroup'+owner['cgroup']).exists(),
        'Original window remains live or its cgroup remains')
    for unit in [owner['unit'],owner['timer']]:require(unit_fields(unit).get('LoadState')=='not-found','Original window unit not released')
    require(process_start(plan['owner']['pid'])==plan['owner']['starttime_ticks'],'Actual original main changed')
    binding=read(plan['binding']);require(binding['owner']==plan['owner'] and len(binding['actors'])==192
        and len(binding['held_hashes'])==196,'Exact original current192/196 binding required')
    output=Path(job['output']);result_pin=pin(output/'result.json');result=read(result_pin)
    latch_pin=pin(output/'first-durable-both-horizons.json');latch=read(latch_pin)
    require(result['latch']==latch_pin and latch['status']=='LATCH' and result['baseline_API']==job['baseline_API']
        and result['progress']==latch['progress'] and latch['progress']['both_horizons'] is True,
        'Original first durable endpoint differs')
    require(type(latch['observed_monotonic_s']) in (int,float) and math.isfinite(latch['observed_monotonic_s'])
        and 0<=latch['observed_monotonic_s']-job['baseline_monotonic_s']<=5400,'Original window cutoff differs')
    trigger=read(latch['API']);counter=module(plan['dependencies']['counter'],'_current_window_counter_',read)
    observer=module(root['window_source'],'_current_window_original_source_',read)
    baseline=counter.normalise(read(job['baseline_API']));current=counter.normalise(trigger)
    require(all(item[kind]['process_id']==plan['owner']['pid'] for item in [baseline,current]
        for kind in ['optimizer_identity','replay_identity']),'Original acquisition exposure owner differs')
    require(observer.progress(current,baseline,baseline)==result['progress'] and result['progress']['applied_updates']>0,
        'Actual original counters do not establish both horizons')
    require(trigger['client_count']==192 and trigger['managed_experiment']==binding['experiment']
        and trigger['training_enabled'] is True and trigger['measurement_active'] is False,'Actual original acquisition API differs')
    require(all(type(trigger[k]) is int and trigger[k]>0 for k in CLOCKS),'Four positive acquisition clocks required')
    captured=read(result['capture_result']);capture_job=read(result['capture_job']);watch=read(result['watch_result'])
    publication=read(captured['publication']);request_raw=read(publication['request_archive'],False)
    transition=captured['completed_slot_transition'];slot=G/'models_dqn/managed_save.request.json.completed'
    before_raw=historical_slot(transition['before'],slot,read);after_raw=historical_slot(transition['after'],slot,read)
    validate_capture_values(plan,binding,result,captured,capture_job,publication,watch,request_raw,before_raw,after_raw)
    require(pin(captured['source']['path'])==captured['source'] and pin(captured['checkpoint']['path'])==captured['checkpoint']
        and pin(slot)==transition['after']['actual_pin'] and not(G/'models_dqn/managed_save.request.json').exists(),
        'Actual original captured producer/archive/completion slot changed')
    capture_source=module(plan['capture_source'],'_current_owned_capture_',read);capture_source.validate_scope(capture_job)
    require(result['normal_producer_mode_preserved'] is True and result['capture_job']==pin(capture_job['job_path']),
        'Window/capture original job join differs')
    for role in ['capture','rescue']:
        entry=result['original_capture_lifecycles'][role];config=read(entry['config']);original=read(entry['owner']);closed=read(entry['closure'])
        original_fields=archived_closure(closed,original,read,exit_zero=True);command(original_fields,config);resources(original_fields,180)
        expected_unit=capture_job['controller_unit' if role=='capture' else 'rescue_unit']
        expected_argv=['/usr/bin/python3.12','-I','-B',plan['capture_source']['path'],
            '--capture' if role=='capture' else '--watch','--job',result['capture_job']['path'],
            '--expected-job-sha256',result['capture_job']['sha256']]
        require(config['unit']==original['unit']==expected_unit and config['argv']==expected_argv
            and process_start(original['pid']) is None,'Actual original capture/watch command or birth differs')
        for unit in [original['unit'],original['timer']]:require(unit_fields(unit).get('LoadState')=='not-found','Original capture/watch not released')
        common_owner(captured['controller'] if role=='capture' else read(publication['rescue_ready'])['owner'],original)
    original_state=read(publication['original_state_before_hold'])
    require(original_state['paused_owner']==original_state['save_owner']==plan['owner']
        and original_state['controller']==captured['controller'],'Actual durable state before kernel hold differs')
    ready=read(publication['rescue_ready']);birth=read(publication['original_watch_capture'])
    require(ready['job_sha256']==result['capture_job']['sha256'] and birth==captured['controller']
        and watch['original_controller']==captured['controller'],'Original independent watch birth differs')
    floor={key:trigger[key] for key in CLOCKS}
    # This separate annotation is an observed upper bound after completion,
    # derived from the original immutable result file's full8 mtime_ns. The
    # original nanoseconds and producer objects remain unchanged.
    after_time=result['capture_result']['identity']['mtime_ns']/1e9
    require(after_time>=publication['hold_released_unix_s']>=publication['request_unix_s']>=latch['observed_unix_s'],
        'Original first eligible latch/publication/completion chronology differs')
    normalized_transition=dict(before=transition['before'],request=dict(actual_pin=publication['request'],
        archive=publication['request_archive']),after=transition['after'],before_unix_s=publication['hold_started_unix_s'],
        request_unix_s=publication['request_unix_s'],after_unix_s=after_time)
    window_view=dict(schema='robotron-derived-current-window-evidence-view-v1',authorized=True,owner=plan['owner'],
        actors=binding['actors'],held_hashes=binding['held_hashes'],experiment=binding['experiment'],tag=plan['capture_tag'],
        output=str(output),counter_module=plan['dependencies']['counter'],baseline_API=job['baseline_API'],
        baseline_monotonic_s=job['baseline_monotonic_s'],policy=dict(learner_frames=8000000,accepted_dqn_epsilon=8000000,
            poll_s=1,maximum_observation_gap_s=30,maximum_API_age_s=5,no_applied_optimizer_s=60,one_capture_only=True),
        quality_precommit=quality_policy(plan['reference'],plan['source_package']),
        phase=dict(record=plan['resume_phase_record'],kind='resume',saved_boot_CPU_proof=plan['boot_CPU']))
    result_view=dict(result,tag=plan['capture_tag'],trigger_API=latch['API'],completed_slot_transition=normalized_transition)
    latch_view=dict(latch,job_experiment=binding['experiment'])
    main_after=copy.deepcopy(binding);main_after['held_hashes'][str(slot)]=transition['after']['actual_pin']['sha256']
    return dict(schema='robotron-original-current-window-provenance-review-v1',status='PASS_CURRENT_ORIGINAL_WINDOW_PROVENANCE_ONLY',
        window_view=window_view,result_view=result_view,latch_view=latch_view,trigger=trigger,clock_floor=floor,main_after=main_after,
        original_plan=root['window_plan'],original_window_job=root['window_job'],original_window_result=result_pin,
        original_window_latch=latch_pin,original_capture_result=result['capture_result'],original_capture_job=result['capture_job'],
        original_watch_result=result['watch_result'],original_publication=captured['publication'],
        original_slot_transition=transition,phase_CPU_transition=normalized_transition,
        completion_upper_bound_source=dict(pin=result['capture_result'],field='identity.mtime_ns',conversion='Python ns/1e9; independent upper bound'),
        normal_producer=captured['source'],evaluation_candidate=captured['checkpoint'],original_tests_or_captures_retried=False,
        views_are_original_producer_bytes=False,quality_qualified=False,promotion=False)


if __name__=='__main__':print('PLAN_ONLY: no reads, views, outputs or runtime actions')
