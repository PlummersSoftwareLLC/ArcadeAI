"""Default inert. Prepare one CURRENT192 preserveRAM stop job; never pause, signal or launch.

An explicit prepare reads current ownership/API/source metadata and writes only
one new preparation directory. The resulting job is deliberately unauthorized.
ROOT must select a new exact job/envelope after its actual prebody qualification.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
HERE = Path(__file__).resolve().parent
SOURCES = HERE/'stop-sources'
HIST = RUN/'dashboard-JSON-production-continuity-main-inputs-original01-preparation-20261022'
CASE = 'scorecarry-previewflags-preserveRAM-original01-20261027'
CURRENT = HERE.parent
BINDING = CURRENT/'actual-fresh192-binding-original01/current-fresh192-main-binding.json'
BINDING_SHA = '0b1b8fb71122597412f83f39eaaa4739b4b5c71d148dad05981574b822233cff'
TEMPLATE = RUN/'deadline-score32-later-policy-firstSave-original01-preparation-20261026/candidate-CPU-preparation-original02/candidate-CPU-job.json'
TEMPLATE_SHA = '638cc9b600341e4774ff0a896351906b95993f403c11f9ad559913e63c092887'


def require(value, message):
    if not value:
        raise ValueError(message)


def module(path, name):
    path = Path(path)
    require(path.resolve(strict=True) == path and path.stat().st_mode & 0o777 == 0o444,
            'Freeze reviewed preparation implementation before use: '+str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def prepare(output):
    require(output.parent == HERE and output.name.startswith('stop-preparation-original')
            and len(output.name) == len('stop-preparation-original01')
            and output.name[-2:].isdigit() and not output.exists(), 'Fresh bounded preparation directory required')
    l = module(SOURCES/'current192_linux_stop_v1.py', '_current192_prepare_linux')
    guard = module(SOURCES/'current192_main_hold_guard_v1.py', '_current192_prepare_guard')
    require(l.full_pin(BINDING)['sha256'] == BINDING_SHA, 'Exact ROOT-adopted current192 binding required')
    main = json.loads(BINDING.read_bytes()); guard.owner_and_files(main); l.live_owner(main['owner'])
    policy = json.loads(l.checked(main['supervision_policy']))
    for key in ('fleet','supplemental0'): l.live_owner(policy[key])
    require(len(main['actors']) == 192 and main['eval_count'] == 37 and main['training_count'] == 155,
            'Actual current split-owner192 roles required')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=3) as response:
        wire = response.read(2_000_001)
    require(len(wire) <= 2_000_000, 'Bound current API response'); api = json.loads(wire)
    guard.healthy(api,main['baseline_API'],main['experiment'],time.time())
    rows = l.frame_map(api,set(range(192)))
    require(all(rows[int(slot)]['evaluation'] is role['eval'] for slot,role in main['actual_roles'].items()),
            'Actual192 role mapping changed before preparation')
    terminal_qualification = l.full_pin(CURRENT/'ROOT-closed-original-final-measurement-terminal-record-qualification-original01.json')
    require(terminal_qualification['sha256'] == '489e47f8b0c9ce52a685d0281278e64400334678e161db5fd3acb729571a80cb',
            'Exact ROOT closed-base terminal qualification required')
    control_bytes = l.CONTROL.read_bytes()
    l.validate_base_control(main,control_bytes,closed_base_measurement=terminal_qualification)
    require(l.full_pin(TEMPLATE)['sha256'] == TEMPLATE_SHA, 'Reviewed LR125 CPU template changed')
    current_phase = l.full_pin(CURRENT/'live-original01/resume-phase-record.json')
    phase = json.loads(l.checked(current_phase))
    boot_pin = l.full_pin(CURRENT/'stop-original01/newest_stopped/CPU-report-readonly.json')
    boot = json.loads(l.checked(boot_pin))
    startup_producer = l.full_pin(CURRENT/'live-original01/startup-CPU-original01/output/cpu-verification.json')
    require(startup_producer['sha256'] == 'c6421325c526d243b19b26bbd1fade85ba416cc31658652d78fe961f53aba7a1',
            'Exact actual startup producer report required; preserve its normal0664 mode')
    boot_startup = json.loads(l.checked(startup_producer))
    previous_API_pin = l.full_pin(CURRENT/'stop-original01/API-wires/0194.raw')
    require(previous_API_pin['sha256'] == '4154a75f9b963d435788f7e0e3add2b99fb01d7550dbbe2a72339d16307629a1',
            'Actual last no-input39507-save measurement counter evidence required')
    previous_API = json.loads(l.checked(previous_API_pin))
    clocks = ('training_steps','optimized_samples','learner_frame_count','frame_count')
    require(boot['status'] == boot_startup['status'] == 'PASS'
            and boot['sha256'] == phase['checkpoint']['sha256'] == boot_startup['actual_boot_checkpoint']['sha256']
                == '39507ee6bbb7ee6d2695d375fdbc25169a0090699e203ebc912ac296f75dcdb9'
            and all(boot['clocks'][k] == previous_API[k] == boot_startup['actual_boot_clocks'][k] for k in clocks)
            and previous_API['client_count'] == 0 and previous_API['training_enabled'] is False
            and type(previous_API['measurement_frames']) is int and previous_API['measurement_frames'] >= 0
            and api['measurement_frames'] == previous_API['measurement_frames'],
            'Actual39507 saved boot clocks/counter must agree; never use oldef618 or later startup+4096')
    require(current_phase['sha256'] == '1043c35fcb73f7a1af4472117e150b93cecf9f5f0af252c5c0207e4af1d9b371'
            and phase['action'] == 'resume' and main['owner']['pid'] == 1062324,
            'Actual current1062324 phase/owner differs')
    original_environment = {}
    for item in Path('/proc',str(main['owner']['pid']),'environ').read_bytes().split(b'\0'):
        if b'=' not in item: continue
        k,v = item.split(b'=',1); k,v = k.decode(),v.decode()
        if k.startswith(('DQN_','ROBOTRON_','CUDA_')) or k == 'PYTHONUNBUFFERED': original_environment[k] = v
    require(original_environment['DQN_PRIORITY_PHASE_RECORD'] == current_phase['path']
            and original_environment['DQN_PRIORITY_PHASE_RECORD_SHA256'] == current_phase['sha256']
            and original_environment['PYTHONUNBUFFERED'] == '1'
            and original_environment['CUDA_DEVICE_ORDER'] == 'PCI_BUS_ID',
            'Actual current transient-unit phase/unbuffered/GPU-order environment differs')
    l.live_owner(main['owner'])
    output.mkdir(mode=0o700); (output/'numerical-source-archives').mkdir()
    put = lambda name,value: l.publish(output/name,value)
    api_pin = put('preparation-current192-API.raw.json',wire)
    census = {}
    for task in Path('/proc',str(main['owner']['pid']),'task').iterdir():
        try: census[int(task.name)] = dict(tid=int(task.name),starttime_ticks=l.starttime(task/'stat'),
            comm=(task/'comm').read_text().strip(),wchan=(task/'wchan').read_text().strip(),
            cgroup=(task/'cgroup').read_text().strip())
        except FileNotFoundError: continue
    for tid,expected in l.CURRENT_NONINPUT_NATIVE.items():
        require(tid in census and (census[tid]['starttime_ticks'],census[tid]['comm']) == expected,
                'Current source-bound native role changed')
    census_pin = put('current-native-thread-census.json',dict(owner=main['owner'],tasks=census,
        source_bound_persistent_roles=l.CURRENT_NONINPUT_NATIVE,actual_freeze_or_signal=False))
    def accept(tid,filename):
        return put(filename,dict(owner=main['owner'],**census[tid],original_census=census_pin,
                                actual_cgroup_move_or_freeze=False))
    listener = accept(1062563,'current-game-accept-native.json')
    dashboard = accept(1062559,'current-dashboard-accept-native.json')
    producer_pins = {}
    for key,count in (('fleet',191),('supplemental0',1)):
        actors = [a for a in main['actors'] if main['actor_ownership'][str(a['slot'])] == key]
        require(len(actors) == count, 'Actual two-producer membership differs')
        producer_pins[key] = put('current-original-'+key+'.json',dict(policy[key],NRestarts='0',
            original_actors=actors,actual_actor_freeze_or_stop=False))
    p = module(SOURCES/'current192_poststop_only_v1.py','_current192_prepare_poststop')
    startup_pin = p.archive(l,startup_producer['path'],output/'current-owner-startup-CPU-readonly.json')
    startup_delta = p.startup_delta(boot_startup['clocks'],boot['clocks'])
    anchor = put('current-owner-actual-boot-anchor.json',dict(
        schema='robotron-current192-original-boot-anchor-v1',owner=main['owner'],
        original_boot_saved_clocks=dict(boot['clocks'],measurement_frame_count=previous_API['measurement_frames']),
        measurement_frame_count_evidence=previous_API_pin,inferred_replay_pressure_anchor=None,
        actual_startup_CPU=startup_pin,original_startup_producer=startup_producer,
        original_boot_checkpoint=phase['checkpoint'],**startup_delta))
    historic = json.loads((HIST/'prepared-inputs.json').read_bytes())
    prepared = put('prepared-inputs.json',dict(schema='robotron-current-fresh192-preserveRAM-stop-prepared-v1',
        status='PREPARED_CURRENT192_PRESERVERAM_STOP_ONLY_NOT_LAUNCHED',original_main=l.full_pin(BINDING),
        current_binding=l.full_pin(BINDING),original_listener=listener,original_dashboard_accept=dashboard,
        original_fleet=producer_pins['fleet'],original_supplemental0=producer_pins['supplemental0'],
        component_proofs=dict(original_boot_anchor=anchor),tested_bank_witness=historic['tested_bank_witness'],
        actual_current_API=api_pin,closed_base_measurement=terminal_qualification,
        actual_freeze_pause_signal_or_stop=False))
    template = copy.deepcopy(json.loads(TEMPLATE.read_bytes()))
    for name in template['phase_snapshot']['sources']:
        current = l.full_pin(GAME/'Scripts/dqn'/name)
        archived = p.archive(l,current['path'],output/'numerical-source-archives'/name)
        template['phase_snapshot']['sources'][name] = dict(current=current,archive=archived)
        if name in template['source_control_context']['model_package']:
            template['source_control_context']['model_package'][name] = current
    control = p.archive(l,l.CONTROL,output/'original-learning-control.json')
    require(control['sha256'] == hashlib.sha256(control_bytes).hexdigest(), 'Current base control changed while archiving')
    settings = p.archive(l,l.MODEL/'game_settings.json',output/'original-game-settings.json')
    unit = l.show(main['owner']['unit'])
    unit_text = l.subprocess.run(['systemctl','--user','cat',main['owner']['unit']],capture_output=True,timeout=15)
    require(unit_text.returncode == 0 and unit['InvocationID'] == main['owner']['invocation_id'], 'Exact current unit unavailable')
    unit_pin = put('original-trainer-unit.txt',unit_text.stdout)
    environment_pin = put('original-trainer-environment.json',dict(
        schema='robotron-current-trainer-environment-archive-v1',owner=main['owner'],environment=original_environment))
    template['experiment'] = main['experiment']
    template['source_control_context'].update(archived_control=control,archived_trainer_unit=unit_pin,
        provenance=[prepared,boot_pin,current_phase,terminal_qualification])
    template['phase_snapshot'].update(owner=main['owner'],phase_record=current_phase,
        boot_checkpoint=phase['checkpoint'],boot_verification=boot_pin,expected_phase=p.expected_phase(boot,current_phase))
    template_pin = put('current-LR125-phase-CPU-template.json',template)
    original_job = json.loads((RUN/'boundary-continuity-forward-recovery-original01-root-preparation-20261018/job.json').read_bytes())
    cfg = dict(schema='robotron-current-fresh192-preserveRAM-poststop-inputs-v1',case=CASE,
        original_owner=main['owner'],cpu_template=template_pin,boot_CPU_report=boot_pin,
        boot_checkpoint=phase['checkpoint'],original_phase_record=current_phase,
        boot_replay_snapshot=l.full_pin(CURRENT/'stop-original01/actual-stopped-ring-and-banks.json'),
        settings_archive=settings,python='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python',
        trainer_environment=environment_pin,
        verifier=l.full_pin(GAME/'tools/lr125_phase_cpu_verifier_proposal_20261023/verify_recipe_phase_snapshot.py'),
        cpu_controller=l.full_pin(GAME/'tools/quality_capacity_proposal/control_quality32_review_v1.py'),
        bank_helper=l.full_pin(original_job['bank_helper']['path']),bank_spec=original_job['bank_spec'],
        archive_checker=l.full_pin(GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),pins=[])
    require(cfg['bank_spec']['capacity'] == 6000000 and cfg['bank_spec']['episode_capacity'] == 192
            and cfg['bank_spec']['ring'] == '/dev/shm/robotron_dqn_latest_replay', 'No oldR16 replay authority')
    cfg['pins'] = [cfg[k] for k in ('cpu_template','boot_CPU_report','original_phase_record','settings_archive',
        'trainer_environment','verifier','cpu_controller','bank_helper','archive_checker','boot_replay_snapshot')]
    cfg_pin = put('poststop-inputs.json',cfg)
    from types import SimpleNamespace
    p.prepare(SimpleNamespace(job=dict(backend_source=l.full_pin(SOURCES/'current192_linux_stop_v1.py'),
        poststop_inputs=cfg_pin,prepared=prepared,case=CASE),owner=main['owner']))
    dependency = dict(reader=l.full_pin(GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'),
        raw_API=l.full_pin(GAME/'tools/eval_capacity_proposal/raw_api_witness_v1.py'),
        main_guard=l.full_pin(SOURCES/'current192_main_hold_guard_v1.py'),
        bank_shutdown_intent=l.full_pin(HIST/'sources-original01/bank_shutdown_intent_v1.py'),
        bank_witness=historic['tested_bank_witness'],socket_seal=l.full_pin(SOURCES/'current192_socket_seal_v2.py'))
    job = dict(schema='robotron-current-fresh192-preserveRAM-stop-job-v1',authorized=False,case=CASE,
        prepared=prepared,output=str(HERE/'stop-original01'),backend_source=l.full_pin(SOURCES/'current192_linux_stop_v1.py'),
        recovery_source=l.full_pin(SOURCES/'current192_stop_recovery_v1.py'),
        poststop_adapter=l.full_pin(SOURCES/'current192_poststop_only_v1.py'),poststop_inputs=cfg_pin,
        dependencies=dependency,base_control_archive=control,base_control_sha256=control['sha256'],
        closed_base_measurement=terminal_qualification,control_path=str(l.CONTROL),probe_endpoint=['127.0.0.1',9998],
        root_selection=None,rescue_owner=None,rescue_ready=None,rescue_job=None,rescue_command=None)
    job_pin = put('UNSELECTED-stop-live-job.json',job); guard.owner_and_files(main)
    return put('prepared-current192-stop-NOT-LAUNCH-QUALIFIED.json',dict(
        schema='robotron-current192-preserveRAM-stop-preparation-v1',job=job_pin,prepared=prepared,poststop_inputs=cfg_pin,
        original_owner=main['owner'],current192_unchanged=True,strict_LR125_context_constructor_checked=True,
        actual_pause_freeze_stop_or_model_body_load=False,actual_job_qualified=False,actual_rescue_owner=None,
        remaining='ROOT must qualify actual selected stop-only job/rescue/whole preserved192 continuation before any launch.'))


def execution_envelopes(preparation, root_selection, output):
    """Actual selected metadata only. ROOT separately launches the rescue."""
    l = module(SOURCES/'current192_linux_stop_v1.py', '_current192_envelope_linux')
    result = json.loads(l.checked(preparation))
    base_pin = result['job']; base = json.loads(l.checked(base_pin))
    selection = json.loads(l.checked(root_selection))
    require(selection['schema'] == 'robotron-root-fresh192-preserveRAM-stop-selection-v1'
            and selection['prepared_inputs'] == result['prepared']
            and selection['one_original_stop_only'] is True
            and selection['source_or_replacement_start_not_authorized'] is True
            and selection['source_and_guard_qualification_complete'] is True
            and selection['current_binding'] == json.loads(l.checked(result['prepared']))['current_binding']
            and selection['expected_source_count'] == len(json.loads(l.checked(selection['current_binding']))['held_hashes'])
            and selection['closed_base_measurement'] == base['closed_base_measurement'],
            'Actual ROOT stop-only selection/qualification required')
    for key in ('backend_source', 'poststop_adapter', 'recovery_source'):
        require(selection[key] == base[key] and l.full_pin(base[key]['path']) == base[key],
                'ROOT selected source differs: '+key)
    require(base['authorized'] is False and base['root_selection'] is None
            and output.parent == HERE and output.name == 'stop-execution-envelopes-original01'
            and not output.exists() and not (HERE/'stop-original01').exists(),
            'New exclusive original envelope scope required')
    output.mkdir(mode=0o700)
    put = lambda name, value: l.publish(output/name, value)
    controller_source = l.full_pin(HERE/'stop_and_preserve_current192_trainer_only_v1.py')
    controller_unit = 'robotron-'+CASE+'-controller.service'
    rescue_unit = 'robotron-'+CASE+'-rescue.service'
    rescue = dict(schema='robotron-current-fresh192-preserveRAM-stop-rescue-job-v1', case=CASE,
        unit=rescue_unit, controller_unit=controller_unit, output=str(output/'rescue-output'),
        owner_path=str(output/'rescue-owner.json'), ready_path=str(output/'rescue-ready.json'),
        controller_source=controller_source, recovery_source=base['recovery_source'],
        backend_source=base['backend_source'], prepared=base['prepared'],
        live_job_path=str(HERE/'stop-live-job.json'), live_output=base['output'])
    rescue_pin = put('rescue-job.json', rescue)
    rescue_argv = ['/usr/bin/python3.12', '-I', '-B', base['recovery_source']['path'],
        '--watch', '--job', rescue_pin['path'], '--expected-job-sha256', rescue_pin['sha256']]
    scope = module(SOURCES/'control_current192_rescue_scope_v1.py', '_current192_rescue_scope')
    resource = ['CPUQuota=200%', 'MemoryMax=4G', 'RuntimeMaxSec=2200', 'MemorySwapMax=0',
                'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no']
    config = dict(unit=rescue_unit, output=str(output/'rescue-execution'), argv=rescue_argv,
        properties=resource, observation_s=2260,
        pins=[scope.pin(q['path']) for q in (base['backend_source'], base['recovery_source'],
                                           controller_source, base['prepared'], rescue_pin)])
    rescue_config = put('rescue-controller-config.json', config)
    scope.checked_config(rescue_config['path'])
    return put('prepared-selected-envelopes-RESCUE-NOT-LAUNCHED.json', dict(
        schema='robotron-selected-current192-stop-envelopes-v1', preparation=preparation,
        base_job=base_pin, root_selection=root_selection, controller_source=controller_source,
        rescue_job=rescue_pin, rescue_command=rescue_argv, rescue_config=rescue_config,
        stop_controller_source=l.full_pin(SOURCES/'control_current192_stop_scope_v1.py'),
        rescue_controller_source=l.full_pin(SOURCES/'control_current192_rescue_scope_v1.py'),
        actual_rescue_owner=None, actual_stop_job=None, actual_stop_controller_config=None,
        actual_pause_or_launch_performed=False))


def finalize_stop_config(envelope):
    """After actual rescue readiness, bind its owner; never launch anything."""
    l = module(SOURCES/'current192_linux_stop_v1.py', '_current192_finalize_linux')
    selected = json.loads(l.checked(envelope))
    rescue = json.loads(l.checked(selected['rescue_job']))
    owner_pin = l.full_pin(Path(rescue['owner_path']))
    ready_pin = l.full_pin(Path(rescue['ready_path']))
    owner = json.loads(l.checked(owner_pin)); ready = json.loads(l.checked(ready_pin))
    l.live_owner(owner)
    require(ready['owner'] == owner and ready['case'] == CASE
            and ready['prepared_inputs_sha256'] == rescue['prepared']['sha256']
            and ready['recovery_source_sha256'] == rescue['recovery_source']['sha256'],
            'Actual original independent rescue not ready for this source scope')
    base = json.loads(l.checked(selected['base_job']))
    require(base['authorized'] is False and not (HERE/'stop-live-job.json').exists(),
            'Exactly one original actual stop job')
    job = dict(base, authorized=True, root_selection=selected['root_selection'],
        rescue_owner=owner_pin, rescue_ready=ready_pin, rescue_job=selected['rescue_job'],
        rescue_command=selected['rescue_command'])
    job_pin = l.publish(HERE/'stop-live-job.json', job)
    scope = module(selected['stop_controller_source']['path'], '_current192_stop_scope')
    argv = ['/usr/bin/python3.12', '-I', '-B', selected['controller_source']['path'],
            '--execute', '--job', job_pin['path'], '--expected-job-sha256', job_pin['sha256']]
    pins = [selected['controller_source'], job_pin, job['backend_source'], job['poststop_adapter'],
            job['recovery_source'], job['prepared'], job['root_selection'], owner_pin, ready_pin]
    config = dict(unit='robotron-'+CASE+'-controller.service',
        output=str(Path(envelope['path']).parent/'stop-execution'), argv=argv,
        properties=['CPUQuota=200%', 'MemoryMax=4G', 'RuntimeMaxSec=1800', 'MemorySwapMax=0',
                    'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
        pins=[scope.pin(q['path']) for q in pins], observation_s=1860)
    config_pin = l.publish(Path(envelope['path']).parent/'stop-controller-config.json', config)
    scope.checked_config(config_pin['path'])
    return l.publish(Path(envelope['path']).parent/'actual-stop-job-and-config-NOT-LAUNCHED.json', dict(
        schema='robotron-actual-current192-stop-ready-v1', envelope=envelope, actual_job=job_pin,
        actual_controller_config=config_pin, actual_rescue_owner=owner_pin,
        actual_stop_launched=False, same_original_rescue_required=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--plan-execution', action='store_true')
    parser.add_argument('--finalize-stop-config', action='store_true')
    parser.add_argument('--preparation', type=Path)
    parser.add_argument('--preparation-sha256')
    parser.add_argument('--root-selection', type=Path)
    parser.add_argument('--root-selection-sha256')
    parser.add_argument('--envelope', type=Path)
    parser.add_argument('--envelope-sha256')
    parser.add_argument('--expected-source-sha256')
    args = parser.parse_args()
    if not (args.prepare or args.plan_execution or args.finalize_stop_config):
        print('PLAN_ONLY: no reads, output, controls, signals or processes')
        return 0
    require(sum(map(bool, (args.prepare, args.plan_execution, args.finalize_stop_config))) == 1
            and args.expected_source_sha256 ==
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'Exact selected preparer source/output required')
    def input_pin(path, expected):
        l = module(SOURCES/'current192_linux_stop_v1.py', '_current192_CLI_pin')
        require(path is not None and expected is not None, 'Explicit actual metadata pin required')
        value = l.full_pin(path)
        require(value['sha256'] == expected, 'Actual metadata SHA differs')
        return value
    if args.prepare:
        require(args.output is not None, 'Explicit fresh preparation output required')
        result = prepare(args.output)
    elif args.plan_execution:
        require(args.output is not None, 'Explicit fresh envelope output required')
        result = execution_envelopes(input_pin(args.preparation, args.preparation_sha256),
            input_pin(args.root_selection, args.root_selection_sha256), args.output)
    else:
        result = finalize_stop_config(input_pin(args.envelope, args.envelope_sha256))
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
