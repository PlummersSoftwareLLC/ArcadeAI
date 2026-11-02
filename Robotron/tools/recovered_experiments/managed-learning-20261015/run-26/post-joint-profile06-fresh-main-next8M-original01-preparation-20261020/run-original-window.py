"""One original prospective capture on the registered score-carry trainer.

Default is inert. --launch selects one fresh baseline and one bounded observer.
--observe reads the same original handles, and archives a terminal outcome
before releasing only its exact service/timer. No retry or quality promotion.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shlex
from pathlib import Path
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
P = R/'post-joint-profile06-fresh-main-next8M-original01-preparation-20261020'
CHAIN = R/'quality32-fresh-candidate-5400-9000-protocol-proposal-20261019/CPU-original02'
OLD = R/'quality32-1059-reference-next8M-window-original01-preparation-20261019'
REG = R/'quality1275-invalid-main-actor168-recovery-original01-20261019'
OUT = R/'post-joint-profile06-fresh-main-next8M-original01-20261020'
UNIT = 'robotron-post-joint-profile06-fresh-main-next8M-original01-20261020.service'
TIMER = UNIT.removesuffix('.service')+'.timer'


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path, sha, name):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, 'Selected source changed: '+str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dependencies():
    guard = load(R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
                 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', '_fresh_window_guard')
    reader = load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', '_fresh_window_reader')
    control = load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py',
                   '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', '_fresh_window_control')
    raw = load(G/'tools/eval_capacity_proposal/raw_api_witness_v1.py',
               '9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0', '_fresh_window_raw')
    return guard, reader, control, raw


def checked_CPU_proof(proof, source, tests_path, tests_sha, count, reader, control, runtime):
    read=lambda p,j=True:reader.read_pin(p,as_json=j)
    plan=read(proof['plan']);tests_source=proof['tests_source'];report=read(proof['actual_tests'])
    require(proof['source']==source==plan['source'] and proof['tests_source']==plan['tests_source']
        and tests_source['path']==str(tests_path) and tests_source['sha256']==tests_sha
        and proof['config']==plan['config'], 'Actual tested CPU source/config differs')
    require(report['status']=='PASS' and type(report['tests']) is int and report['tests']==count
        and all(type(report[k]) is int and report[k]==0 for k in ('failures','errors','skipped'))
        and report['actual_candidate_captured'] is False and report['actual_quality_run'] is False
        and report['numerical_runtime_imported'] is False and report['source_selected_for_science'] is False,
        'Complete original CPU scope required before any baseline')
    inputs={p['path']:p for p in plan['full_input_pins']}
    require(len(inputs)==len(plan['full_input_pins']) and all(reader.pin(p['path'])==p for p in inputs.values())
        and source in inputs.values() and tests_source in inputs.values(),'Actual CPU input/source/test membership differs')
    for name in ('stdout','stderr'):
        entry=proof['consoles'][name]
        require(entry['original']['sha256']==entry['archive']['sha256'],'Exact separate original CPU console copy required')
        raw=read(entry['archive'],False)
        if name=='stdout':
            require(raw.endswith(b'\n') and json.loads(raw.splitlines()[-1])==report,'Original CPU console/report differs')
    resources=reader.checked_module('_profile06_launcher_resources_'+str(time.time_ns()),
        dict_pin(reader,G/'tools/quality_capacity_proposal/verify_final_authority_chain_v1.py',
                 '2d1f5f24fcd6ebbf6ee1187e4fd1529bc319d5d5be607188a3f2a20da32bf563'))
    resources.cpu(proof['config'],proof['original_owner'],proof['original_closure'],inputs,
        ['/usr/bin/python3.12','-I','-B',tests_source['path']],read,runtime.archived_closure,
        lambda unit:control.show(unit)['LoadState']=='not-found',runtime.duration_seconds,set())
    return count


def dict_pin(reader,path,sha):
    value=reader.pin(path);require(value['sha256']==sha,'Exact launcher dependency source required');return value


def verify_followup_CPU(proof, source, reader, control, runtime):
    require(source['path']==str(G/'tools/quality_capacity_proposal/prepare_tail9000_followup_v3.py')
        and source['sha256']=='53cea9314773334c2535a76bb8c2f5b992d916e912875e933315fb7329142685',
        'Exact tested profile06 followup source required')
    require(proof['status']=='PROFILE06_ORIGINAL_FOLLOWUP12_PASS_ALL6_VERIFIED_EXACT_OWNED_RELEASED',
        'Actual original followup12 result required')
    return checked_CPU_proof(proof,source,G/'tools/quality_capacity_proposal/test_profile06_followup_v1.py',
        '80538d55babb225274c035b68213e246ee9af7acc7954420699cd125139603bd',12,reader,control,runtime)


def selected_chain(reader, control):
    pin=dict_pin(reader,P/'combined-source-selection.json',
        'd8279507723ef1df204425efed72f88fdcd897128add2f10193774a0af0558f2')
    packet=reader.read_pin(pin)
    require(packet['schema']=='robotron-joint-profile06-source-selection-v1'
        and packet['protocol_id']=='prospective-tail9000-joint-profile06-v1'
        and packet['source_package']['path']==str(G/'tools/quality_capacity_proposal/profile06/runtime-source-package.json')
        and packet['source_package']['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
        and packet['candidate_captured'] is False and packet['quality_qualified'] is False,
        'Exact complete combined source selection required')
    clarification=reader.read_pin(packet['clock_budget_clarification'])
    require(clarification['fixed_entry_based_timeout_s']==9000 and clarification['fixed_admission_s']==5400
        and clarification['nominal_difference_s']==3600,'Entry-based deadline/admission must remain unchanged')
    runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_profile06_window_archives')
    followup_source=packet['followup_source'];proof=reader.read_pin(packet['followup_CPU'])
    verify_followup_CPU(proof,followup_source,reader,control,runtime)
    tested=reader.read_pin(reader.read_pin(proof['plan'])['selection_packet'])
    require(all(packet.get(key)==value for key,value in tested.items()),'The launcher must select the exact tested followup packet')
    module=reader.checked_module('_profile06_window_followup_'+str(time.time_ns()),followup_source)
    value=module.authorize(packet,reader,control,runtime)
    require(value['source_authority']['status']=='COMBINED_PROFILE06_ORIGINAL_SOURCE_AND_CPU_CHAIN_VERIFIED'
        and value['source_authority']['bound_integration_tests']==113
        and value['source_authority']['full_handler_variants']==56
        and value['preceding_quality']['native_outcome']=='invalid'
        and value['quality_qualified'] is False and value['candidate_captured'] is False,
        'Actual combined source and current closed predecessor required before baseline')
    return pin,packet,runtime


def require_launcher_CPU(reader, control, runtime):
    proof=reader.read_pin(reader.pin(P/'launcher-CPU-original01/root-original-launcher-CPU-readback.json'))
    require(proof['status']=='PROFILE06_ORIGINAL_LAUNCHER19_PASS_ALL6_VERIFIED_EXACT_OWNED_RELEASED'
        and proof['source']==reader.pin(__file__)
        and proof['tests_source']==reader.pin(P/'test_window_launcher_v1.py'),
        'Actual original launcher19 is required before a baseline')
    checked_CPU_proof(proof,reader.pin(__file__),P/'test_window_launcher_v1.py',
        proof['tests_source']['sha256'],19,reader,control,runtime)


def launch():
    guard, reader, control, raw = dependencies()
    require(Path(__file__).resolve() == P/'run-original-window.py' and not (P/'job.json').exists()
            and not OUT.exists(), 'This exact original window is already consumed')
    require(control.show(UNIT)['LoadState'] == control.show(TIMER)['LoadState'] == 'not-found',
            'Original names already exist; do not launch again')
    state = json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    binding = reader.read_pin(state['current_main_binding'])
    require(binding['owner']['pid'] == 3170722 and binding['owner']['starttime_ticks'] == 52892579
            and binding['owner']['invocation_id'] == 'f2896a1cbb3c4a94a7568ab83120d21e', 'Current trainer differs')
    shown = control.show(binding['owner']['unit'])
    require(shown['MainPID'] == str(binding['owner']['pid']) and shown['InvocationID'] == binding['owner']['invocation_id']
            and shown['NRestarts'] == '0', 'Actual trainer service differs')
    guard.owner_and_files(binding)
    template = reader.read_pin(guard.pin(OLD/'job.json'))
    old_selection = reader.read_pin(guard.pin(OLD/'root-selection.json'))
    for entry in (old_selection['source'], old_selection['source_package'], old_selection['observer_integration_CPU'],
                  old_selection['observer_integration_closure'], state['current_boot_CPU_proof'],
                  state['current_resume_phase_record']):
        reader.read_pin(entry, as_json=False)
    require(guard.pin(old_selection['reference']['path']) == old_selection['reference'], 'Protected reference changed')
    counter = load(Path(template['counter_module']['path']), template['counter_module']['sha256'], '_fresh_window_counter')
    scope_pin, scope, runtime = selected_chain(reader, control)
    chain_pin = scope['chain']
    require_launcher_CPU(reader, control, runtime)
    execution = P/'execution'
    execution.mkdir(mode=0o700)
    (execution/'tmp').mkdir(mode=0o700)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        wire = response.read(raw.MAX_WIRE_BYTES+1)
    api = raw.parse_wire(wire)
    baseline_mono = time.monotonic()
    baseline_pin = guard.publish(P/'baseline-API.raw.json', wire)
    guard.healthy(api, reader.read_pin(binding['baseline_API']), binding['experiment'], time.time())
    normal = counter.normalise(api)
    require(normal['optimizer_identity']['process_id'] == normal['replay_identity']['process_id'] == binding['owner']['pid'],
            'Exposure belongs to another trainer')
    guard.publish(P/'baseline-API-witness.json', raw.witness_fields(api, baseline_pin))
    job = copy.deepcopy(template)
    job.update(owner=binding['owner'], actors=binding['actors'], held_hashes=binding['held_hashes'],
               experiment=binding['experiment'], output=str(OUT), tag='scorecarry849_LR25_joint_profile06_fresh_next8M_01_20261020',
               baseline_API=baseline_pin, baseline_monotonic_s=baseline_mono,
               phase=dict(record=state['current_resume_phase_record'], kind='resume',
                          saved_boot_CPU_proof=state['current_boot_CPU_proof']),
               activation_health=guard.pin(REG/'main-fleet-transition-independent-readback.json'),
               scope='One distinct prospective +8M learner-frame AND +8M accepted DQN/epsilon window after score-carry849 deployment. '
                     'Keep CE4096/LRscale.25/cap8 fixed. One capture, strict CPU with actual NEW boot/resume lineage, then fresh32 R/C/R/C '
                     'against protected1059. Fixed5400/9000,min50,all32,full tails,original ROM/runtime,independent5%mean/preserved median. '
                     'No reuse or retry of invalid1223/1275/1306/1390/1533 quality or their checkpoints; no causal learning-speed claim.')
    job['supervised_quality_chain'] = chain_pin
    job['joint_profile06_source_selection'] = scope_pin
    job['joint_profile06_source_authority'] = scope['actual_combined_authority']
    job['quality_precommit'].update(same_whole_cohort_timeout_s=9000, source_package=scope['source_package'])
    job['clock_budget_clarification'] = scope['clock_budget_clarification']
    job['future_main_supervision_limits'] = dict(max_missing_slots=1,recovery_s=45,total_recovery_s=120,
                                                max_recoveries=4,max_sample_gap_s=30,max_collection_s=5)
    job_pin = guard.publish(P/'job.json', job)
    selection = dict(schema='robotron-post-score-carry849-window-selection-v1', original_attempt=1, retry=False,
                     source=old_selection['source'], job=job_pin, reference=old_selection['reference'],
                     source_package=scope['source_package'], completed_CPU_chain=chain_pin,
                     completed_source_scope=scope_pin, clock_budget_clarification=scope['clock_budget_clarification'], binding=state['current_main_binding'],
                     boot_checkpoint=state['current_boot_checkpoint'], phase=job['phase'], activation_health=job['activation_health'],
                     fixed_policy=job['policy'], quality_precommit=job['quality_precommit'], recipe_changed=False,
                     baseline_learner_frames=normal['clocks']['learner_frame_count'], baseline_accepted=normal['learner_accepted'],
                     quality_qualified=False, learning_speed_gain_verified=False, promotion=False,
                     launcher=guard.pin(__file__),supervised_quality_chain=chain_pin)
    guard.publish(P/'root-selection.json', selection)
    argv = ['/usr/bin/python3.12', '-I', '-B', selection['source']['path'], '--execute', '--job', str(P/'job.json'),
            '--job-sha256', job_pin['sha256']]
    properties = ['Type=exec', 'RemainAfterExit=yes', 'Restart=no', 'WorkingDirectory='+str(G.parent),
                  'StandardOutput=append:'+str(execution/'stdout.txt'), 'StandardError=append:'+str(execution/'stderr.txt'),
                  'CPUQuota=100%', 'MemoryMax=512M', 'MemorySwapMax=0', 'RuntimeMaxSec=5600',
                  'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no']
    actual = ['systemd-run', '--user', '--unit='+UNIT, '--on-active=3s', '--timer-property=AccuracySec=100ms']
    actual += ['--property='+value for value in properties]
    actual += ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
               'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR='+str(execution/'tmp')]+argv
    guard.publish(execution/'root-launch-intent.json', dict(unit=UNIT,timer=TIMER,argv=argv,actual_argv=actual,
                  job=job_pin,original_attempt=1,no_retry=True))
    require(time.monotonic()-baseline_mono < 15, 'Baseline too old before one scheduling attempt')
    receipt = control.command(execution, 'root-scheduling-carrier', actual)
    require(receipt['exit'] == 0 and not receipt['timed_out'], 'Scheduling uncertain; preserve original handles, never retry')
    timer_show = control.command(execution, 'original-launch-timer-show', ['systemctl','--user','show',TIMER])
    timer_cat = control.command(execution, 'original-launch-timer-cat', ['systemctl','--user','cat',TIMER])
    timer_value = control.fields(timer_show)
    context = dict(unit=UNIT,timer=TIMER,timer_invocation_id=timer_value['InvocationID'])
    require(control.timer_state(timer_value,context) == 'original_loaded' and timer_cat['exit'] == 0, 'Timer birth incomplete')
    guard.publish(execution/'root-original-timer-launch-archive.json',dict(**context,timer_show=timer_show,timer_cat=timer_cat))
    deadline = time.monotonic()+15
    while time.monotonic() < deadline:
        shown = control.show(UNIT)
        pid = int(shown.get('MainPID','0'))
        if pid:
            start = guard.process_start(pid)
            actual_cli = [value.decode() for value in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if value]
            again = control.show(UNIT)
            require(actual_cli == argv and again['MainPID'] == str(pid) and shown['InvocationID'] == again['InvocationID']
                    and shown['NRestarts'] == '0' and start == guard.process_start(pid), 'Original observer birth differs')
            owner = dict(pid=pid,starttime_ticks=start,unit=UNIT,invocation_id=shown['InvocationID'],
                         cgroup=shown['ControlGroup'],timer=TIMER,timer_invocation_id=context['timer_invocation_id'],observed_live=True)
            guard.publish(execution/'root-original-live-owner.json',owner)
            control.command(execution,'original-first-observed-show',['systemctl','--user','show',UNIT])
            print(json.dumps(dict(status='ORIGINAL_WINDOW_LAUNCHED',owner=owner,job=job_pin,
                                  baseline_learner_frames=selection['baseline_learner_frames'],baseline_accepted=selection['baseline_accepted'])))
            return
        time.sleep(.03)
    raise RuntimeError('Original birth not captured; preserve handles, never retry')


def observe():
    guard, reader, control, raw = dependencies()
    selection = reader.read_pin(guard.pin(P/'root-selection.json'))
    reader.read_pin(selection['launcher'], as_json=False)
    job = reader.read_pin(selection['job'])
    owner = reader.read_pin(guard.pin(P/'execution/root-original-live-owner.json'))
    shown = control.show(owner['unit'])
    closed = P/'execution/terminal/root-original-result-and-owned-release.json'
    if closed.exists():
        closure = reader.read_pin(guard.pin(closed))
        require(closure['original'] == owner and closure['lifecycle_complete'] is True
                and control.show(UNIT)['LoadState'] == control.show(TIMER)['LoadState'] == 'not-found', 'Closed original identity differs')
        live = False
    else:
        require(shown['InvocationID'] == owner['invocation_id'] and shown['NRestarts'] == '0', 'Original observer identity changed')
        live = shown.get('MainPID') == str(owner['pid'])
        if live:
            require(guard.process_start(owner['pid']) == owner['starttime_ticks'], 'Original observer birth changed')
        else:
            control.original_terminal(shown,owner)
            out = P/'execution/terminal'
            out.mkdir(mode=0o700)
            archives = []
            for kind,unit in (('service',owner['unit']),('timer',owner['timer'])):
                for action in ('show','cat','journal'):
                    argv = ['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+owner[
                        'invocation_id' if kind == 'service' else 'timer_invocation_id']] if action == 'journal' else ['systemctl','--user',action,unit]
                    archives.append(control.command(out,'original-'+kind+'-'+action,argv))
            control.original_terminal(control.fields(archives[0]),owner)
            context = {key:owner[key] for key in ('unit','timer','timer_invocation_id')}
            control.timer_state(control.fields(archives[3]),context)
            closure = dict(original=owner,original_exec_code=int(shown['ExecMainCode']),original_exit=int(shown['ExecMainStatus']),
                           original_result=shown['Result'],full_original_archives=archives,original_archived_before_release=True,
                           timer_launch_archive=guard.pin(P/'execution/root-original-timer-launch-archive.json'),
                           payload_retried=False,owned_release=[],unit_released=False,lifecycle_complete=False)
            guard.publish(out/'root-original-terminal-archive.json',closure)
            require(all(row['exit'] == 0 and not row['timed_out'] for row in archives[:3]+archives[5:])
                    and archives[3]['exit'] == 0 and not archives[3]['timed_out']
                    and archives[4]['exit'] in (0,1) and not archives[4]['timed_out'], 'Original six descriptors incomplete')
            if archives[4]['exit'] != 0:
                record = control.command(out,'original-timer-GC-confirm-show',['systemctl','--user','show',TIMER])
                closure['timer_GC_confirmation'] = record
                require(control.timer_state(control.fields(record),context) == 'absent', 'Missing timer descriptor lacks GC evidence')
            control.original_terminal(control.show(UNIT),owner)
            for kind in ('timer','service'):
                row = {}
                closure['owned_release'].append(row)
                control.release_original(out,kind,owner,context,row)
            require(all(row['confirmed_absent'] for row in closure['owned_release']), 'Exact original release incomplete')
            closure.update(unit_released=True,lifecycle_complete=True,status='ORIGINAL_WINDOW_ARCHIVED_AND_OWNED_RELEASED')
            reviewer = load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
                            '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445', '_fresh_window_archive_checker')
            reviewer.archived_closure(closure,owner,lambda entry,as_json=True:reader.read_pin(entry,as_json=as_json),exit_zero=False)
            guard.publish(closed,closure)
    status = json.loads((OUT/'status.json').read_bytes()) if (OUT/'status.json').exists() else None
    result = reader.read_pin(guard.pin(OUT/'result.json')) if (OUT/'result.json').exists() else None
    transition = bool(live and status and status.get('both_horizons') and result is None)
    if result and result.get('status') == 'CAPTURED_FIRST_BOTH_HORIZONS':
        job['held_hashes'][str(G/'models_dqn/managed_save.request.json.completed')] = result['completed_slot_transition']['after']['actual_pin']['sha256']
        require(guard.pin(result['checkpoint']['path']) == result['checkpoint'], 'Captured checkpoint changed')
    if transition:
        require(status['learner_frames'] >= 8_000_000 and status['learner_accepted'] >= 8_000_000
                and time.time()-(OUT/'status.json').stat().st_mtime < 65
                and (OUT/'first-durable-both-horizons.json').exists(), 'Invalid in-flight capture transition')
        check_job = copy.deepcopy(job)
        check_job['held_hashes'].pop(str(G/'models_dqn/managed_save.request.json.completed'))
        # Validate remaining holds without treating the authorized request as foreign.
        require(guard.process_start(job['owner']['pid']) == job['owner']['starttime_ticks'], 'Trainer changed during capture')
        for path,sha in check_job['held_hashes'].items():
            require(guard.pin(path)['sha256'] == sha, 'Held file changed during capture')
        for actor in job['actors']:
            require(guard.process_start(actor['pid']) == actor['starttime_ticks']
                    and sorted(os.sched_getaffinity(actor['pid'])) == actor['mask'], 'Actor changed during capture')
    else:
        guard.owner_and_files(job)
    main = control.show(job['owner']['unit'])
    require(main['MainPID'] == str(job['owner']['pid']) and main['InvocationID'] == job['owner']['invocation_id']
            and main['NRestarts'] == '0', 'Main actual unit differs')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
        api = raw.parse_wire(response.read(raw.MAX_WIRE_BYTES+1))
    guard.healthy(api,reader.read_pin(job['baseline_API']),job['experiment'],time.time())
    require(guard.pin(selection['reference']['path']) == selection['reference'], 'Protected reference changed')
    age = time.time()-(G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
    require(0 <= age <= 360, 'Autosave stale')
    summary = dict(unix_s=time.time(),classification='ORIGINAL_WINDOW_LIVE' if live else 'ORIGINAL_WINDOW_TERMINAL_CLOSED',
                   owner=owner,window_status=status,status_age_s=time.time()-(OUT/'status.json').stat().st_mtime if status else None,
                   original_exit=None if live else closure['original_exit'],original_result=result,
                   main=dict(owner=job['owner'],client_count=api['client_count'],learner_frame_count=api['learner_frame_count'],
                             training_steps=api['training_steps'],optimized_samples=api['optimized_samples'],fleet_fps=api['fps'],autosave_age_s=age),
                   held_inputs=len(job['held_hashes']),original192_verified=True,quality_qualified=False,learning_speed_gain_verified=False)
    with (P/'root-live-observations.jsonl').open('a') as stream:
        stream.write(json.dumps(summary,allow_nan=False)+'\n')
    print(json.dumps(summary,allow_nan=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--launch',action='store_true')
    group.add_argument('--observe',action='store_true')
    args = parser.parse_args()
    if args.launch:
        launch()
    elif args.observe:
        observe()
    else:
        print('PLAN_ONLY: no reads or actions')
