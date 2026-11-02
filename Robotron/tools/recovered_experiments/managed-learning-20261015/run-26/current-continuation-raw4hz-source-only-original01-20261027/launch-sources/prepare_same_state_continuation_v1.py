"""DATA ONLY. Default inert; writes exclusive phase/command metadata, never runs it.

Root supplies the immutable actual stop result and independently reviewed stop
closure. No checkpoint/tensor body is opened and no source is installed here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
C = G / 'logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027'
LIVE = C / 'live-original01'
PYTHON = '/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python'
TAG = 'managed-run-26-continuation-raw4hz-original01-20261027'
TRAINER = 'robotron-' + TAG + '-trainer.service'
FLEET = 'robotron-' + TAG + '-fleet.service'
VERIFIER_SHA = '08c165ed917b8633ab658a8efbc915f81e37adff21c1330cd5806cd3148f4051'
VERIFIER = G / 'tools/lr125_phase_cpu_verifier_proposal_20261023/verify_recipe_phase_snapshot.py'
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
OLD = dict(pid=3615927, starttime_ticks=78856521,
    unit='robotron-managed-run-26-d3b365c9-trainer.service',
    invocation_id='8fdf9768e04641a1858114861ccde8aa',
    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-managed-run-26-d3b365c9-trainer.service')


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def small_pin(path):
    p = Path(path)
    require(p.is_absolute() and p.resolve(strict=True) == p, 'Canonical regular metadata required')
    before = p.lstat()
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 2_000_000
        and before.st_nlink == 1, 'Only bounded small regular metadata may be read')
    with p.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Metadata changed before read')
        raw = stream.read(2_000_001)
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Metadata changed during read')
    require(identity(p.lstat()) == identity(before), 'Metadata changed after read')
    return dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(before))


def read(pin):
    require(type(pin) is dict and set(pin) == {'path','sha256','bytes','identity'}, 'Full pin required')
    require(small_pin(pin['path']) == pin and pin['identity']['mode'] == '0o444'
        and pin['identity']['uid'] == os.getuid(), 'Owned immutable exact metadata required')
    value = json.loads(Path(pin['path']).read_text())
    require(small_pin(pin['path']) == pin, 'Metadata changed during parse')
    return value


def stat_checkpoint(pin):
    p = Path(pin['path'])
    require(p == G/'models_dqn/robotron_dqn_latest.pt' and p.resolve(strict=True) == p,
        'Only actual stopped canonical LATEST may boot')
    require(stat.S_ISREG(p.lstat().st_mode) and identity(p.lstat()) == pin['identity']
        and pin['bytes'] == pin['identity']['bytes'] and len(pin['sha256']) == 64,
        'Stopped checkpoint stat differs; no checkpoint body was opened')


def resume_record(saved, report):
    phase = report['saved_priority_metric_phase']
    require(report['status'] == 'PASS' and report['phase_metadata_verified'] is True
        and phase['valid'] is True and phase['metric'] == 'ce', 'Actual strict stopped CE PASS required')
    require(saved['checkpoint']['sha256'] == report['sha256']
        and saved['checkpoint']['bytes'] == report['bytes'], 'Stopped checkpoint/CPU bytes differ')
    require(all(type(saved['clocks'][k]) is int and saved['clocks'][k] > 0
        and saved['clocks'][k] == report['clocks'][k] for k in CLOCKS), 'Actual stopped clocks differ')
    return dict(schema='robotron-priority-metric-start-v1', phase_id=phase['phase_id'],
        metric='ce', action='resume', previous_metric='ce',
        checkpoint={k:saved['checkpoint'][k] for k in ('path','sha256','bytes')},
        model_dir=str(G/'models_dqn'), root_precommit_sha256=phase['root_precommit_sha256'])


def startup_delta(clocks, floor):
    require(all(type(clocks[k]) is int and type(floor[k]) is int for k in CLOCKS), 'Integer clocks required')
    require(all(clocks[k] == floor[k] for k in ('learner_frame_count','frame_count')),
        'Input frames advanced before actor admission')
    updates = clocks['training_steps'] - floor['training_steps']
    require(updates in (0,1) and clocks['optimized_samples'] - floor['optimized_samples'] == updates*4096,
        'Startup exceeded the actual zero-or-one batch path')
    return dict(startup_updates=updates, logical_samples=updates*4096, learner_frames=0, raw_frames=0)


def publish(path, value):
    p = Path(path)
    with p.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    return small_pin(p)


def prepare(spec):
    require(spec['schema'] == 'robotron-root-same-state-continuation-data-selection-v1', 'Explicit Root data selection required')
    stop = read(spec['actual_stop_result'])
    require(stop['status'] == 'CURRENT_TRAINER_STOPPED_AND_FULL_STATE_HOT_REPLAY_PRESERVED'
        and stop['trainer_stopped'] is True and stop['replacement_started'] is False
        and stop['source_install_performed'] is False, 'Successful stop-only result required')
    saved = stop['saved']
    require(type(saved['actual_original_CPU_exit']) is int and saved['actual_original_CPU_exit'] == 0
        and all(saved[k] is True for k in ('strict_phase_verified','newest_stopped_source',
        'replay_bank_consistency_verified')), 'Strict stopped CPU/replay/bank PASS required')
    report = read(saved['report'])
    require(report['script']['sha256'] == VERIFIER_SHA, 'Actual stopped report must use reviewed LR.125 verifier08c')
    cpu = read(saved['CPU_closure'])
    require(type(cpu['original_exit']) is int and cpu['original_exit'] == 0
        and cpu['lifecycle_complete'] is True and cpu['unit_released'] is True,
        'Original stopped CPU must have actual successful owned closure')
    closure = read(spec['root_stopped_and_install_authority'])
    require(closure['schema'] == 'robotron-root-stopped-source-install-authority-v1'
        and closure['original_trainer'] == OLD and closure['old_trainer_birth_absent'] is True
        and closure['exact_old_unit_closed'] is True
        and closure['actual_stop_result'] == spec['actual_stop_result']
        and closure['strict_CPU_replay_bank_PASS'] is True, 'Root exact stopped install authority required')
    require(read(saved['ring_and_banks'])['spec'] == dict(
        ring='/dev/shm/robotron_dqn_latest_replay', model_dir=str(G/'models_dqn'),
        capacity=6000000, state_size=11128, episode_capacity=192,
        bank_strides=dict(hof=1536,ephof=2048)), 'Actual six-million R3 geometry differs')
    stat_checkpoint(saved['checkpoint'])
    env = read(spec['original_trainer_environment'])['environment']
    require(env['DQN_BATCH_SIZE'] == '4096' and env['DQN_N_STEP'] == '3'
        and env['DQN_MAX_SAMPLES_PER_FRAME'] == '8'
        and env['CUDA_VISIBLE_DEVICES'] == 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1', 'Original recipe/GPU environment differs')
    require(not LIVE.exists(), 'Fresh RUN_DIR must not exist before phase preparation')
    record = resume_record(saved, report)
    LIVE.mkdir(mode=0o700)
    record_pin = publish(LIVE/'resume-phase-record.json', record)
    env = dict(env, ROBOTRON_RUN_DIR=str(LIVE), DQN_PRIORITY_PHASE_RECORD=record_pin['path'],
        DQN_PRIORITY_PHASE_RECORD_SHA256=record_pin['sha256'])
    args = ['systemd-run','--user','--unit='+TRAINER,'--working-directory='+str(G),
        '--property=Type=simple','--property=Restart=no','--property=KillMode=control-group',
        '--property=KillSignal=SIGINT','--property=SendSIGKILL=no','--property=TimeoutStopSec=240',
        '--property=StandardOutput=append:'+str(LIVE/'trainer-console.log'),'--property=StandardError=inherit']
    args += ['--setenv='+key+'='+value for key,value in sorted(env.items())]
    args += ['--',PYTHON,'-Xgil=0','Scripts/run_dqn.py']
    result = dict(schema='robotron-same-state-continuation-command-data-v1', commands_executed=False,
        root_selection=spec, actual_stop_result=spec['actual_stop_result'], resume_phase_record=record_pin,
        stopped_clocks=saved['clocks'], stopped_checkpoint=saved['checkpoint'],
        trainer_argv=args, startup_expected_clients=0, actual_new_trainer=None,
        startup_CPU_acquisition=None, startup_CPU_report=None, startup_CPU_closure=None,
        fresh_fleet_argv=None, actual_new_fleet=None,
        admission='Root must verify installed source pins, actual restore, unchanged ring/banks/maps, '
            '0-or-1 startup update and independent08c startup CPU/owned closure before fresh fleet.')
    return publish(LIVE/'prepared-command-data-NOT-EXECUTED.json', result)


def prepare_fleet_data(manifest_pin):
    path = C/'fresh-fleet-rolemap/exec_fresh_fleet_roles_v1.py'
    require(small_pin(path)['sha256'] == 'faa8e5f76564df21048f32a172105ddc59fc4f944c33be80019795991b922c25',
        'Reviewed fresh fleet helper differs')
    loader = importlib.util.spec_from_file_location('_fresh_roles_launch_data', path)
    helper = importlib.util.module_from_spec(loader); loader.loader.exec_module(helper)
    manifest = helper.read(manifest_pin)
    helper.validate_manifest(manifest)
    helper.verify_rendered_wrapper(manifest_pin, manifest)
    require(LIVE.is_dir(), 'Trainer data preparation must precede fleet data')
    args = ['systemd-run','--user','--unit='+FLEET,'--working-directory='+str(G),
        '--property=Type=simple','--property=Restart=no','--property=SendSIGKILL=no',
        '--property=StandardOutput=append:'+str(LIVE/'fleet-console.log'),'--property=StandardError=inherit']
    args += ['--setenv='+key+'='+value for key,value in sorted(manifest['parent_environment'].items())]
    args += ['--'] + manifest['parent_argv']
    return publish(LIVE/'prepared-fleet-command-data-NOT-EXECUTED.json', dict(
        schema='robotron-fresh192-fleet-command-data-v1', commands_executed=False,
        actual_manifest=manifest_pin, actual_installed_wrapper=small_pin(manifest['wrapper_path']),
        fleet_argv=args, actual_new_fleet=None,
        admission='Root must qualify startup08c CPU and old fleet positive closure before executing'))


def prepare_startup_CPU_data(spec):
    """Serialize actual zero-client acquisition into existing08c/C218 schemas."""
    require(spec['schema'] == 'robotron-root-actual-startup-CPU-data-selection-v1', 'Actual startup selection required')
    stop = read(spec['actual_stop_result']); saved = stop['saved']; boot = read(saved['report'])
    record = read(spec['resume_phase_record'])
    require(record == resume_record(saved, boot), 'Actual resume record differs from stopped source')
    acquire = read(spec['acquisition'])
    require(acquire['purpose'] == 'startup' and acquire['client_count'] == 0
        and acquire['owner_before'] == acquire['owner_after'] == spec['actual_new_owner']
        and acquire['clock_floor'] == saved['clocks'], 'Actual same-new-owner zero-client startup bracket required')
    require(acquire['source_checkpoint'] == {k:spec['source'][k] for k in ('path','sha256','bytes')}
        and acquire['boot_checkpoint'] == record['checkpoint']
        and acquire['phase_record_sha256'] == spec['resume_phase_record']['sha256'], 'Actual acquisition source/phase differs')
    template = read(spec['LR125_CPU_template'])
    require(template['verifier_sha256'] == VERIFIER_SHA, 'Use reviewed08c LR.125 template')
    context = read(spec['actual_source_control_context'])
    require(context['held_recipe_context'] == template['source_control_context']['held_recipe_context'],
        'Full LR.125 recipe must remain exactly the qualified recipe')
    pairs = read(spec['actual_phase_source_pairs'])
    expected = {k:boot['saved_priority_metric_phase'][k] for k in
        ('metric','phase_id','root_precommit_sha256','started_from','valid')}
    expected.update(founder_phase_record_sha256=boot['saved_priority_metric_phase']['phase_record_sha256'],
        last_resume_record_sha256=spec['resume_phase_record']['sha256'])
    directory = LIVE/'startup-CPU-original01'
    directory.mkdir(mode=0o700, exist_ok=False)
    job = dict(template, source=spec['source'], verification_copy=spec['verification_copy'],
        clock_floor=saved['clocks'], source_control_context=context,
        output_directory=str(directory/'output'), phase_snapshot=dict(purpose='startup',
        owner=spec['actual_new_owner'], observed_clients=0, phase_record=spec['resume_phase_record'],
        boot_checkpoint=record['checkpoint'], boot_verification=saved['report'], expected_phase=expected,
        acquisition=spec['acquisition'], sources=pairs))
    job_pin = publish(directory/'job.json', job)
    controller = G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
    require(small_pin(controller)['sha256'] == '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
        and small_pin(VERIFIER)['sha256'] == VERIFIER_SHA, 'Reviewed original controller/verifier changed')
    def reduced(p):
        value=small_pin(p)
        value['identity']={k:value['identity'][k] for k in ('device','inode','mode','uid','nlink')}
        return value
    config= dict(unit='robotron-'+TAG+'-startup-CPU-original01.service',output=str(directory/'execution'),
        argv=[PYTHON,'-Xgil=0','-I','-B',str(VERIFIER),'--execute','--job',job_pin['path'],
        '--expected-job-sha256',job_pin['sha256'],'--expected-verifier-sha256',VERIFIER_SHA],
        properties=['CPUQuota=200%','MemoryMax=4G','RuntimeMaxSec=180','MemorySwapMax=0',
        'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[reduced(p) for p in (controller,VERIFIER,Path(job_pin['path']))], observation_s=240)
    return publish(directory/'controller-config.json', config)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-data', action='store_true')
    parser.add_argument('--selection'); parser.add_argument('--selection-sha256')
    parser.add_argument('--prepare-fleet-data', action='store_true')
    parser.add_argument('--manifest'); parser.add_argument('--manifest-sha256')
    parser.add_argument('--prepare-startup-CPU-data', action='store_true')
    args=parser.parse_args()
    require(sum((args.prepare_data,args.prepare_fleet_data,args.prepare_startup_CPU_data)) <= 1,
        'Select one metadata preparation mode')
    if args.prepare_startup_CPU_data:
        pin=small_pin(args.selection)
        require(pin['sha256'] == args.selection_sha256, 'Actual startup selection SHA differs')
        print(json.dumps(prepare_startup_CPU_data(read(pin)), indent=2)); return
    if args.prepare_fleet_data:
        pin=small_pin(args.manifest)
        require(pin['sha256'] == args.manifest_sha256, 'Actual manifest SHA differs')
        print(json.dumps(prepare_fleet_data(pin), indent=2)); return
    if not args.prepare_data:
        print('INERT: no read of checkpoint, no install, no launch; --prepare-data writes exclusive metadata only')
        return
    pin=small_pin(args.selection)
    require(pin['sha256'] == args.selection_sha256, 'Root selection SHA differs')
    print(json.dumps(prepare(read(pin)), indent=2))


if __name__ == '__main__':
    main()
