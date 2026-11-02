"""Launch one validated original window; observe and close the same handles.

No action by default. A new baseline is selected only after actual CPU/source
authority and current main/reference checks pass. Observation never relaunches.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'
EXECUTION=P/'window-execution-original01'


def require(value,message):
    if not value:raise ValueError(message)


def observer(plan):
    entry=plan['observer_source'];require(hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256'],
        'Original observer source changed')
    spec=importlib.util.spec_from_file_location('_selected_prospective_window',entry['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def launch(plan,plan_pin):
    w=observer(plan);w.validate_plan(plan)
    require(not Path(plan['job_path']).exists() and not w.OUT.exists() and not EXECUTION.exists()
        and not(P/'root-window-selection-before-baseline.json').exists(),'Original window already selected; never retry')
    context=w.Context(plan);l=context.l;c=context.control
    binding=context.authority()
    require(c.show(w.UNIT)['LoadState']==c.show(w.TIMER)['LoadState']=='not-found','Original service/timer names already exist')
    EXECUTION.mkdir(mode=0o700);(EXECUTION/'tmp').mkdir(mode=0o700)
    l.publish(P/'root-window-selection-before-baseline.json',dict(plan=plan_pin,owner=plan['owner'],reference=plan['reference'],
        observer_source=plan['observer_source'],launcher_source=plan['launcher_source'],CPU=plan['window_CPU'],
        original_attempt=1,no_retry=True,baseline_selected=False))
    wire,api=context.api();baseline_mono=time.monotonic()
    context.guard.healthy(api,context.reader.read_pin(binding['baseline_API']),binding['experiment'],time.time())
    normal=context.counter.normalise(api)
    require(normal['optimizer_identity']['process_id']==normal['replay_identity']['process_id']==plan['owner']['pid'],
        'Baseline exposure belongs to another main')
    baseline=l.publish(P/'baseline-API.raw.json',wire)
    witness=l.publish(P/'baseline-API-witness.json',context.raw.witness_fields(api,baseline))
    job=dict(schema='profile06-production-next8M-window-job-v1',authorized=True,plan=plan_pin,output=str(w.OUT),
        observer_source=plan['observer_source'],baseline_API=baseline,baseline_monotonic_s=baseline_mono,
        baseline_normalized=normal,original_attempt=1,no_retry=True)
    jp=l.publish(Path(plan['job_path']),job)
    selection=l.publish(P/'root-original-window-selection.json',dict(plan=plan_pin,job=jp,baseline_API=baseline,
        baseline_witness=witness,baseline_monotonic_s=baseline_mono,baseline_learner_frames=normal['clocks']['learner_frame_count'],
        baseline_accepted=normal['learner_accepted'],reference=plan['reference'],recipe_changed=False,
        quality_qualified=False,promotion=False,learning_speed_gain_verified=False))
    argv=['/usr/bin/python3.12','-I','-B',plan['observer_source']['path'],'--execute','--job',jp['path'],
        '--expected-job-sha256',jp['sha256']]
    properties=['Type=exec','RemainAfterExit=yes','Restart=no','WorkingDirectory='+str(G.parent),
        'StandardOutput=append:'+str(EXECUTION/'stdout.txt'),'StandardError=append:'+str(EXECUTION/'stderr.txt'),
        'CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=5700','TasksMax=128',
        'TimeoutStopSec=5','SendSIGKILL=no']
    actual=['systemd-run','--user','--unit='+w.UNIT,'--on-active=3s','--timer-property=AccuracySec=100ms']
    actual+=['--property='+value for value in properties]
    actual+=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(EXECUTION/'tmp')]+argv
    l.publish(EXECUTION/'root-launch-intent.json',dict(unit=w.UNIT,timer=w.TIMER,argv=argv,actual_argv=actual,
        job=jp,selection=selection,properties=properties,original_attempt=1,no_retry=True))
    require(time.monotonic()-baseline_mono<15,'Original baseline too old before one scheduling attempt')
    scheduled=c.command(EXECUTION,'root-scheduling-carrier',actual)
    require(scheduled['exit']==0 and scheduled['timed_out'] is False,'Original scheduling outcome uncertain; never retry')
    timer_show=c.command(EXECUTION,'original-launch-timer-show',['systemctl','--user','show',w.TIMER])
    timer_cat=c.command(EXECUTION,'original-launch-timer-cat',['systemctl','--user','cat',w.TIMER])
    fields=c.fields(timer_show);timer_context=dict(unit=w.UNIT,timer=w.TIMER,timer_invocation_id=fields['InvocationID'])
    require(c.timer_state(fields,timer_context)=='original_loaded' and timer_cat['exit']==0,'Original timer birth incomplete')
    l.publish(EXECUTION/'root-original-timer-launch-archive.json',dict(**timer_context,timer_show=timer_show,timer_cat=timer_cat))
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        shown=c.show(w.UNIT);pid=int(shown.get('MainPID','0'))
        if pid:
            tick=l.process_start(pid)
            command=[part.decode() for part in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if part]
            again=c.show(w.UNIT)
            require(command==argv and shown['InvocationID']==again['InvocationID'] and again['MainPID']==str(pid)
                and shown['NRestarts']=='0' and l.process_start(pid)==tick,'Original observer birth differs')
            require(context.runtime.duration_seconds(shown['CPUQuotaPerSecUSec'])==2 and shown['MemoryMax']==str(4<<30)
                and shown['MemorySwapMax']=='0' and shown['TasksMax']=='128'
                and context.runtime.duration_seconds(shown['RuntimeMaxUSec'])==5700
                and context.runtime.duration_seconds(shown['TimeoutStopUSec'])==5 and shown['SendSIGKILL']=='no',
                'Actual original observer resource bounds differ')
            owner=dict(pid=pid,starttime_ticks=tick,unit=w.UNIT,invocation_id=shown['InvocationID'],cgroup=shown['ControlGroup'],
                timer=w.TIMER,timer_invocation_id=timer_context['timer_invocation_id'],observed_live=True)
            l.live_owner(owner);op=l.publish(EXECUTION/'root-original-live-owner.json',owner)
            c.command(EXECUTION,'original-first-observed-show',['systemctl','--user','show',w.UNIT])
            return dict(status='ORIGINAL_VALIDATED_WINDOW_LAUNCHED',owner=op,job=jp,selection=selection,
                baseline_learner_frames=normal['clocks']['learner_frame_count'],baseline_accepted=normal['learner_accepted'])
        time.sleep(.03)
    raise RuntimeError('Original observer birth not captured; preserve the same handles, never relaunch')


def close_if_terminal(context,owner):
    l=context.l;c=context.control;terminal=EXECUTION/'terminal'
    completed=terminal/'root-original-result-and-owned-release.json'
    if completed.exists():return json.loads(l.checked(l.full_pin(completed)))
    shown=c.show(owner['unit'])
    require(shown['InvocationID']==owner['invocation_id'] and shown['NRestarts']=='0','Original observer unit identity changed')
    if shown.get('MainPID')==str(owner['pid']):l.live_owner(owner);return None
    require(shown.get('MainPID')=='0' and shown['ExecMainPID']==str(owner['pid'])
        and l.process_start(owner['pid'])!=owner['starttime_ticks'],'Original observer terminal identity differs')
    group=Path('/sys/fs/cgroup'+owner['cgroup'])
    if group.exists() and (group/'cgroup.procs').read_text().strip():
        return dict(status='ORIGINAL_TERMINAL_CARRIERS_PENDING',lifecycle_complete=False,unit_released=False,
            original=owner,original_exec_code=int(shown['ExecMainCode']),original_exit=int(shown['ExecMainStatus']) if shown['ExecMainCode']=='1' else None)
    terminal.mkdir(mode=0o700);archives=[]
    for kind,unit in [('service',owner['unit']),('timer',owner['timer'])]:
        invocation=owner['invocation_id' if kind=='service' else 'timer_invocation_id']
        for action in ['show','cat','journal']:
            argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+invocation] if action=='journal' else ['systemctl','--user',action,unit]
            archives.append(c.command(terminal,'original-'+kind+'-'+action,argv))
    code=int(shown['ExecMainCode']);status=int(shown['ExecMainStatus'])
    result=dict(original=owner,original_exec_code=code,original_exit=status if code==1 else None,
        original_signal=status if code!=1 else None,original_result=shown['Result'],full_original_archives=archives,
        timer_launch_archive=l.full_pin(EXECUTION/'root-original-timer-launch-archive.json'),
        original_archived_before_release=True,payload_retried=False,owned_release=[],unit_released=False,lifecycle_complete=False)
    l.publish(terminal/'root-original-terminal-archive.json',result)
    require(all(row['exit']==0 and not row['timed_out'] for row in archives[:4]+archives[5:])
        and archives[4]['exit'] in (0,1) and not archives[4]['timed_out'],'Original six terminal descriptors incomplete')
    if code!=1:
        result['status']='ORIGINAL_SIGNAL_PRESERVED_NO_RESTART_OR_RELEASE'
        l.publish(completed,result);return result
    c.original_terminal(c.show(owner['unit']),owner);timer_context={k:owner[k] for k in ['unit','timer','timer_invocation_id']}
    for kind in ['timer','service']:
        release={};result['owned_release'].append(release);c.release_original(terminal,kind,owner,timer_context,release)
    require(all(row['confirmed_absent'] for row in result['owned_release']),'Original exact release incomplete')
    result.update(status='ORIGINAL_WINDOW_ARCHIVED_AND_OWNED_RELEASED',unit_released=True,lifecycle_complete=True)
    context.runtime.archived_closure(result,owner,lambda e,as_json=True:context.reader.read_pin(e,as_json=as_json),exit_zero=False)
    l.publish(completed,result);return result


def verify_inflight_main(context,binding,plan,status):
    l=context.l;slot=str(G/'models_dqn/managed_save.request.json.completed')
    require(status['state']=='capture_inflight' and status['both_horizons'] is True
        and time.time()-status['observed_unix_s']<300,'Unbound or stale capture transition')
    latch=json.loads(l.checked(status['latch']));require(latch['status']=='LATCH' and latch['progress']['both_horizons'] is True,
        'Actual first-eligible latch missing')
    capture_job=json.loads(l.checked(status['capture_job']));context.capture.validate_scope(capture_job)
    require(capture_job['owner']==plan['owner'] and capture_job['latch']==status['latch']
        and capture_job['source']==plan['capture_source'],'Capture transition has foreign owner/source')
    l.live_owner(binding['owner'])
    for actor in binding['actors']:
        require(l.process_start(actor['pid'])==actor['starttime_ticks'] and sorted(os.sched_getaffinity(actor['pid']))==actor['mask'],
            'Original actor changed during authorized capture')
    for path,digest in binding['held_hashes'].items():
        if path!=slot:require(l.full_pin(path)['sha256']==digest,'Held input changed during capture')
    request=G/'models_dqn/managed_save.request.json'
    if request.exists():require(json.loads(request.read_bytes())==dict(tag=plan['capture_tag']),'Foreign request during capture')


def observe(plan):
    w=observer(plan);context=w.Context(plan);l=context.l
    selection=json.loads(l.checked(l.full_pin(P/'root-original-window-selection.json')))
    job=json.loads(l.checked(selection['job']));owner=json.loads(l.checked(l.full_pin(EXECUTION/'root-original-live-owner.json')))
    closure=close_if_terminal(context,owner);live=closure is None
    status_path=w.OUT/'status.json';status=json.loads(status_path.read_bytes()) if status_path.exists() else None
    result_path=w.OUT/'result.json';result=json.loads(l.checked(l.full_pin(result_path))) if result_path.exists() else None
    binding=copy.deepcopy(context.reader.read_pin(plan['binding']))
    if result is not None and result['status']=='CAPTURED_FIRST_BOTH_HORIZONS':
        slot=str(G/'models_dqn/managed_save.request.json.completed');after=result['completed_slot_transition']['after']['actual_pin']
        require(l.full_pin(after['path'])==after and l.full_pin(result['checkpoint']['path'])==result['checkpoint'],
            'Original captured candidate/completion slot changed')
        binding['held_hashes'][slot]=after['sha256'];context.guard.owner_and_files(binding)
    elif status is not None and status['state']=='capture_inflight':verify_inflight_main(context,binding,plan,status)
    else:context.guard.owner_and_files(binding)
    l.live_owner(plan['owner']);wire,api=context.api()
    context.guard.healthy(api,context.reader.read_pin(job['baseline_API']),binding['experiment'],time.time())
    require(l.full_pin(plan['reference']['path'])==plan['reference'],'Protected reference changed')
    age=time.time()-(G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime;require(0<=age<=360,'Latest normal autosave stale')
    if live:classification='SAME_ORIGINAL_WINDOW_LIVE'
    else:classification='SAME_ORIGINAL_WINDOW_TERMINAL_CLOSED' if closure['lifecycle_complete'] else 'SAME_ORIGINAL_WINDOW_TERMINAL_PRESERVED'
    summary=dict(classification=classification,observed_unix_s=time.time(),owner=owner,status=status,
        status_age_s=time.time()-status_path.stat().st_mtime if status else None,original_exit=None if live else closure['original_exit'],
        original_result=result,main=dict(owner=plan['owner'],clients=api['client_count'],learner_frames=api['learner_frame_count'],
            training_steps=api['training_steps'],optimized_samples=api['optimized_samples'],fleet_fps=api['fps'],autosave_age_s=age),
        held_inputs=len(binding['held_hashes']),original192_verified=True,quality_qualified=False,promotion=False,
        learning_speed_gain_verified=False)
    with (P/'root-window-observations.jsonl').open('a') as stream:stream.write(json.dumps(summary,allow_nan=False)+'\n')
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group()
    group.add_argument('--launch',action='store_true');group.add_argument('--observe',action='store_true')
    parser.add_argument('--plan',type=Path);parser.add_argument('--expected-plan-sha256');args=parser.parse_args(argv)
    if not(args.launch or args.observe):print('PLAN_ONLY: no reads, queries or runtime actions');return 0
    require(args.plan and hashlib.sha256(args.plan.read_bytes()).hexdigest()==args.expected_plan_sha256,'Exact immutable window plan required')
    plan=json.loads(args.plan.read_bytes());require(Path(plan['launcher_source']['path'])==Path(__file__).resolve(),
        'Use the selected original launcher source')
    w=observer(plan);context=w.Context(plan);pin=context.l.full_pin(args.plan)
    require(pin['identity']['mode']=='0o444','Original window plan must be sealed')
    print(json.dumps(launch(plan,pin) if args.launch else observe(plan),allow_nan=False));return 0


if __name__=='__main__':raise SystemExit(main())
