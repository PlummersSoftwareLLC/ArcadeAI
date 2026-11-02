"""Private systemd integration of the unchanged handoff recovery/watch sources.

The fixture has192 /usr/bin/sleep children, a native listener stand-in and
heartbeat files. Only named fixture units/private control files are mutated.
No model, replay, production process, production control or production cgroup
is changed. Intentional controller exit23 is an expected injected loss.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
import time


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
H = RUN/'profile06-production-continuity-main-inputs-original01-preparation-20261021'
PREFIX = 'robotron-profile06-cgroup-recovery-fixture-original'


def require(value,message):
    if not value:
        raise RuntimeError(message)


def load(path,name):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait(predicate,seconds,message):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.03)
    raise RuntimeError(message)


def fixture_owner(linux,unit):
    require(unit.startswith(PREFIX) and unit.endswith('.service'),'Only an exact private fixture unit is allowed')
    value = linux.show(unit)
    owner = dict(pid=int(value['MainPID']),starttime_ticks=linux.process_start(int(value['MainPID'])),
                 unit=unit,invocation_id=value['InvocationID'],cgroup=value['ControlGroup'])
    linux.live_owner(owner)
    return owner


def write_mutable(path,value):
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,path)


def fixture_main(work):
    linux = load(work.parent/'sources/handoff_linux_v1.py','_private_linux')
    group = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    unit = Path(group).name
    require(unit.startswith(PREFIX) and unit.endswith('-fleet.service'),'Private original fixture scope required')
    owner = fixture_owner(linux,unit)
    require(owner['pid'] == os.getpid(),'The private main must own its actual fixture unit')
    stop = threading.Event()
    children = []
    def listener():
        count = 0
        while not stop.wait(.03):
            count += 1
            write_mutable(work/'listener-heartbeat.json',dict(count=count,monotonic_s=time.monotonic()))
    thread = threading.Thread(target=listener,name='RecoveryFixtureAccept',daemon=True)
    try:
        for _ in range(192):
            children.append(subprocess.Popen(['/usr/bin/sleep','300']))
        thread.start()
        actors = [dict(slot=i,pid=child.pid,starttime_ticks=linux.process_start(child.pid),
                       mask=sorted(os.sched_getaffinity(child.pid))) for i,child in enumerate(children)]
        require(len({v['pid'] for v in actors}) == 192,'Distinct original192 fixture actors required')
        listener_birth = dict(owner=owner,tid=thread.native_id,
            starttime_ticks=linux.starttime(Path('/proc/self/task',str(thread.native_id),'stat')),
            comm=Path('/proc/self/task',str(thread.native_id),'comm').read_text().strip())
        linux.publish(work/'fixture-ready.json',dict(owner=owner,actors=actors,listener=listener_birth))
        count = 0
        while not (work/'fixture-release.json').exists():
            count += 1
            write_mutable(work/'main-heartbeat.json',dict(count=count,monotonic_s=time.monotonic()))
            require(all(child.poll() is None for child in children),'An original fixture actor exited')
            time.sleep(.03)
        linux.publish(work/'fixture-completed.json',dict(original192_retained=True,owner=owner,
            actors=actors,listener_birth=listener_birth,main_heartbeat_count=count))
    finally:
        stop.set()
        if thread.ident is not None:
            thread.join(2)
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            child.wait(timeout=3)
    return 0


def injected_controller(job):
    linux = load(job['backend_source']['path'],'_private_controller_linux')
    linux.checked(job['backend_source'])
    require(job['schema'] == 'robotron-private-handoff-recovery-fixture-v1','Only a private failure injection is supported')
    work = Path(job['work'])
    require(work.parent == H/'current-cgroup-save-recovery-kernel-original01',
            'Private immutable test preparation root required')
    prepared = json.loads(linux.checked(job['prepared']))
    base = json.loads(linux.checked(prepared['original_main']))
    fleet = json.loads(linux.checked(prepared['original_fleet']))
    listener = json.loads(linux.checked(prepared['original_listener']))
    linux.live_owner(json.loads(linux.checked(job['rescue_owner'])))
    output = Path(job['output'])
    output.mkdir(mode=0o700)
    now = time.monotonic()
    state = dict(schema='robotron-owned-handoff-recovery-state-v1',case=job['case'],controller_pid=os.getpid(),
        controller_starttime_ticks=linux.process_start(os.getpid()),stage='private_failure_injection',
        stage_started_monotonic_s=now,stage_deadline_monotonic_s=now+25,original_owner=base['owner'],
        original_fleet=prepared['original_fleet'],original_listener=prepared['original_listener'],
        control_path=job['control_path'],expected_owned_control=linux.full_pin(job['control_path']),
        base_control_archive=job['base_control_archive'],listener_child='/sys/fs/cgroup'+base['owner']['cgroup']+
        '/listener-'+job['case'],accept_held=False,fleet_frozen=False,original_stop_sent=False,replacement=None,poststop={})
    write_mutable(output/'recovery-state.json',state)
    birth = wait(lambda: (work/'rescue-output/original-controller-birth.json').exists(),15,
                 'The real independent watch did not capture the original controller')
    captured = json.loads((work/'rescue-output/original-controller-birth.json').read_bytes())
    require(captured['pid'] == os.getpid() and captured['starttime_ticks'] == state['controller_starttime_ticks'],
            'Independent watch captured another controller')
    variant = job['variant']
    if variant == 'lost_controller_with_listener_fleet_and_control_holds':
        require(base['owner'] == {k:fleet[k] for k in base['owner']},'This fixture shares its private main/fleet unit')
        owner = base['owner']
        linux.live_owner(owner)
        require(owner['unit'].startswith(PREFIX),'Refuse a production owner')
        control = json.loads(linux.checked(job['base_control_archive']))
        control['measurement'] = dict(label=job['case']+'-drain',checkpoint=None,cohort_s=3600,timeout_s=7200)
        linux.atomic_owned_replace(job['control_path'],state['expected_owned_control'],
            (json.dumps(control,indent=2)+'\n').encode(),suffix=job['case'])
        child = Path(state['listener_child'])
        require(not child.exists() and child.parent.name == owner['unit'],'Only an unused private child is allowed')
        state.update(accept_held=True,fleet_frozen=True)
        # Keep the old control PIN deliberately: recovery must cover the real
        # crash window between atomic publication and its next state update.
        write_mutable(output/'recovery-state.json',state)
        child.mkdir()
        (child/'cgroup.type').write_text('threaded\n')
        (child/'cgroup.freeze').write_text('1\n')
        (child/'cgroup.threads').write_text(str(listener['tid'])+'\n')
        wait(lambda: 'frozen 1' in (child/'cgroup.events').read_text(),3,'Private listener did not freeze')
        require(set(map(int,(child/'cgroup.threads').read_text().split())) == {listener['tid']},'Foreign child task')
        root = child.parent
        (root/'cgroup.freeze').write_text('1\n')
        wait(lambda: 'frozen 1' in (root/'cgroup.events').read_text(),3,'Private fleet did not freeze')
        before = (work/'main-heartbeat.json').read_bytes()
        time.sleep(.12)
        require((work/'main-heartbeat.json').read_bytes() == before,'Frozen fixture heartbeat advanced')
        linux.publish(work/'injection.json',dict(variant=variant,private_listener_and_fleet_kernel_frozen=True,
            main_heartbeat_stopped=True,original192_actors=fleet['original192_actors'],controller=captured,
            intentionally_stale_control_pin=True,production_changed=False))
    else:
        require(variant == 'lost_controller_during_exact_replacement_save_publication_pause','Unknown private variant')
        replacement = job['replacement']
        require(replacement['unit'].startswith(PREFIX) and replacement != base['owner'],
                'A distinct private replacement is required')
        linux.live_owner(replacement)
        linux.checked(job['poststop_adapter'])
        poststop = load(job['poststop_adapter']['path'],'_actual_selected_cgroup_save')
        state.update(original_stop_sent=True,replacement=replacement,poststop={})
        adapter = SimpleNamespace(linux=linux,startup_save_paused_owner=None)
        def record_hold():
            state['poststop']=dict(startup_save_paused_owner=adapter.startup_save_paused_owner)
            write_mutable(output/'recovery-state.json',state)
        adapter.b=SimpleNamespace(state=record_hold)
        with poststop.startup_save_pause(adapter,replacement):
            root=Path('/sys/fs/cgroup'+replacement['cgroup'])
            require((root/'cgroup.freeze').read_text().strip()=='1' and
                    dict(line.split() for line in (root/'cgroup.events').read_text().splitlines()).get('frozen')=='1',
                    'The exact private kernel cgroup is not frozen')
            before=(work/'main-heartbeat.json').read_bytes()
            time.sleep(.12)
            require((work/'main-heartbeat.json').read_bytes()==before,'Kernel-frozen fixture heartbeat advanced')
            linux.publish(work/'injection.json',dict(variant=variant,exact_private_replacement_kernel_frozen=True,
                replacement=replacement,main_heartbeat_stopped=True,controller=captured,
                actual_selected_startup_save_pause=True,owned_descendant_children=192,
                no_process_stop_or_continue_signal=True,production_changed=False))
            os._exit(23)  # Intentional loss inside the real hold; finally must not run.
    os._exit(23)  # Expected injected loss; no local finally or manual recovery.


def root_run(preparation,number,variant,retired=None):
    require(preparation == H/'current-cgroup-save-recovery-kernel-original01' and number == '01',
            'One new private preparation directory is required')
    require(variant == 'lost_controller_during_exact_replacement_save_publication_pause' and retired is not None,'Only the new private committed cgroup-save case is selected')
    require(not preparation.exists(),'Do not retry the original private case')
    preparation.mkdir(mode=0o700)
    sources = preparation/'sources'
    sources.mkdir()
    for name in ('handoff_linux_v1.py','handoff_recovery_v1.py','handoff_poststop_v1.py','prove_handoff_recovery_v1.py'):
        raw = (Path(__file__).parent/name).read_bytes()
        with (sources/name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(),0o444)
            os.fsync(stream.fileno())
    linux = load(sources/'handoff_linux_v1.py','_root_private_linux')
    controller_source = GAME/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
    require(hashlib.sha256(controller_source.read_bytes()).hexdigest() ==
            '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','Use original C218')
    c = load(controller_source,'_root_C218_private_recovery')
    work = preparation/'work'
    work.mkdir(mode=0o700)
    case = 'scorecarry-profile06-cgroup-recovery-original'+number+'-20261021'
    unit_base = PREFIX+number+'-20261021'
    threads,results,configs = [],{},{}
    def launch(role,argv,tasks=128):
        config = dict(unit=unit_base+'-'+role+'.service',output=str(preparation/(role+'-execution')),argv=argv,
            properties=['CPUQuota=200%','MemoryMax=4G','RuntimeMaxSec=180','MemorySwapMax=0',
                        'TasksMax='+str(tasks),'TimeoutStopSec=5','SendSIGKILL=no'],
            pins=[c.pin(path) for path in sources.glob('*.py')],observation_s=240)
        path = preparation/(role+'-config.json')
        c.publish(path,config)
        configs[role] = path
        c.launch(path)
        def observe():
            results[role] = c.observe(path)
        thread = threading.Thread(target=observe,name='ObservePrivate-'+role,daemon=True)
        threads.append(thread)
        thread.start()
        return config['unit']
    original_fixture = None
    emergency = False
    try:
        fleet_unit = launch('fleet',['/usr/bin/python3.12','-I','-B',str(sources/'prove_handoff_recovery_v1.py'),
                                    '--fixture-main','--work',str(work)],tasks=256)
        wait(lambda: (work/'fixture-ready.json').exists(),20,'The original private fixture did not start')
        original_fixture = json.loads((work/'fixture-ready.json').read_bytes())
        current = original_fixture['owner']
        require(fixture_owner(linux,fleet_unit) == current,'Original fixture birth differs')
        base_owner = current if retired is None else retired['owner']
        listener = original_fixture['listener'] if retired is None else retired['listener']
        base = linux.publish(work/'original-main.json',dict(owner=base_owner))
        fleet = linux.publish(work/'original-fleet.json',dict(current,original192_actors=original_fixture['actors']))
        listener_pin = linux.publish(work/'original-listener.json',listener)
        prepared = linux.publish(work/'prepared.json',dict(original_main=base,original_fleet=fleet,
                                                         original_listener=listener_pin))
        private_model = work/'Robotron/models_dqn'
        private_model.mkdir(parents=True)
        control = private_model/'learning_control.json'
        base_bytes = b'{"experiment":"private-recovery-only","lr_scale":0.25}\n'
        control.write_bytes(base_bytes)
        base_control = linux.publish(work/'base-control.json',base_bytes)
        rescue_source = linux.full_pin(sources/'handoff_recovery_v1.py')
        fixture_source = linux.full_pin(sources/'prove_handoff_recovery_v1.py')
        backend = linux.full_pin(sources/'handoff_linux_v1.py')
        controller_unit = unit_base+'-controller.service'
        rescue_job = dict(schema='robotron-score-carry-independent-rescue-job-v1',case=case,
            unit=unit_base+'-rescue.service',controller_unit=controller_unit,output=str(work/'rescue-output'),
            owner_path=str(work/'rescue-owner.json'),ready_path=str(work/'rescue-ready.json'),
            controller_source=fixture_source,recovery_source=rescue_source,backend_source=backend,prepared=prepared,
            live_job_path=str(work/'live-job.json'),live_output=str(work/'live-output'))
        rescue_pin = linux.publish(work/'rescue-job.json',rescue_job)
        launch('rescue',['/usr/bin/python3.12','-I','-B',rescue_source['path'],'--watch','--job',rescue_pin['path'],
                         '--expected-job-sha256',rescue_pin['sha256']])
        wait(lambda: (work/'rescue-ready.json').exists(),15,'Actual independent rescue did not become ready')
        live_job = dict(schema='robotron-private-handoff-recovery-fixture-v1',case=case,variant=variant,
            work=str(work),output=str(work/'live-output'),prepared=prepared,backend_source=backend,
            recovery_source=rescue_source,poststop_adapter=linux.full_pin(sources/'handoff_poststop_v1.py'),
            rescue_owner=linux.full_pin(work/'rescue-owner.json'),base_control_archive=base_control,
            base_control_sha256=base_control['sha256'],control_path=str(control),replacement=current if retired else None)
        live_pin = linux.publish(work/'live-job.json',live_job)
        launch('controller',['/usr/bin/python3.12','-I','-B',fixture_source['path'],'--execute','--job',live_pin['path'],
                             '--expected-job-sha256',live_pin['sha256']])
        wait(lambda: (work/'rescue-output/result.json').exists(),25,'Actual watch has not finished the injected loss')
        rescue = json.loads((work/'rescue-output/result.json').read_bytes())
        require(rescue['status'] == 'ORIGINAL_CONTROLLER_LOST_OR_DEADLINE_EXPIRED'
                and rescue['controller_was_live_at_deadline'] is False,'Actual controller loss was not observed')
        recovery = rescue['recovery']
        require(recovery['errors'] == [] and recovery['restart_retry'] is False,'Real recovery did not succeed')
        expected = 'PRESTOP_ORIGINAL_RESOURCES_RESTORED' if retired is None else 'SAME_REPLACEMENT_HANDLE_OBSERVATION_PENDING'
        require(recovery['status'] == expected,'Actual recovery took another path')
        require(control.read_bytes() == base_bytes,'Private base control was not restored')
        before = json.loads((work/'main-heartbeat.json').read_bytes())['count']
        wait(lambda: json.loads((work/'main-heartbeat.json').read_bytes())['count'] > before,3,
             'Original fixture heartbeat did not resume')
        require(fixture_owner(linux,fleet_unit) == current,'Recovery replaced its original fixture process')
        root = Path('/sys/fs/cgroup'+current['cgroup'])
        require((root/'cgroup.type').read_text().strip() == 'domain'
                and (root/'cgroup.freeze').read_text().strip() == '0'
                and not any(path.is_dir() for path in root.iterdir()),'A private kernel hold remains')
        for actor in original_fixture['actors']:
            require(linux.process_start(actor['pid']) == actor['starttime_ticks']
                    and sorted(os.sched_getaffinity(actor['pid'])) == actor['mask'],'An original192 fixture actor changed')
        linux.publish(work/'fixture-release.json',dict(validated=True))
        for thread in threads:
            thread.join(15)
        require(not any(thread.is_alive() for thread in threads),'An original fixture lifecycle remains pending')
        require(results['fleet']['original_exit'] == results['rescue']['original_exit'] == 0
                and results['controller']['original_exit'] == 23
                and all(v['lifecycle_complete'] for v in results.values()),'Original fixture exits/lifecycles differ')
        checker = load(GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_private_archive_checker')
        reader = load(GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_private_pin_reader')
        read = lambda entry,as_json=True: reader.read_pin(entry,as_json=as_json)
        closures = {}
        for role in configs:
            directory = preparation/(role+'-execution')
            closure = linux.full_pin(directory/'root-original-result-and-owned-release.json')
            owner = json.loads((directory/'root-original-identity.json').read_bytes())
            checker.archived_closure(json.loads(linux.checked(closure)),owner,read,exit_zero=role != 'controller')
            require(linux.show(owner['unit'])['LoadState'] == linux.show(owner['timer'])['LoadState'] == 'not-found',
                    'An original private service/timer remains loaded')
            closures[role] = closure
        result = linux.publish(preparation/'root-independent-readback.json',dict(status='ACTUAL_ORIGINAL_WATCH_RECOVERY_INTEGRATION_PASS',
            variant=variant,original_fixture=original_fixture,original_exits=dict(fleet=0,rescue=0,controller=23),
            actual_watch_recovery=linux.full_pin(work/'rescue-output/result.json'),original_closures=closures,
            all18_original_descriptors_verified=True,original192_child_PIDs_and_affinities_preserved=True,
            private_heartbeat_resumed=True,emergency_cleanup_used=False,production_changed=False,
            model_replay_or_numerical_restore_tested=False,scope='Private192 sleep-child fixture. Actual unchanged recovery/watch, systemd births, cgroup holds and exact-owner save-publication cgroup-freeze/rescue path. No actual Robotron model/replay or MAME.',
            source_pins={path.name:linux.full_pin(path) for path in sources.glob('*.py')}))
        print(json.dumps(result),flush=True)
        return original_fixture
    except BaseException as error:
        linux.publish(preparation/'root-failure-preserved.json',dict(error=repr(error),original_outcomes_preserved=True,
            production_changed=False))
        raise
    finally:
        if original_fixture is not None and not (work/'fixture-release.json').exists():
            emergency = True
            owner = original_fixture['owner']
            if linux.process_start(owner['pid']) == owner['starttime_ticks']:
                linux.live_owner(owner)
                root = Path('/sys/fs/cgroup'+owner['cgroup'])
                require(root.name.startswith(PREFIX),'Emergency cleanup must stay in the original private unit')
                child = root/('listener-'+case)
                if child.exists():
                    for tid in map(int,(child/'cgroup.threads').read_text().split()):
                        require(Path('/proc',str(owner['pid']),'task',str(tid)).exists(),'Foreign child task')
                        (root/'cgroup.threads').write_text(str(tid)+'\n')
                    (child/'cgroup.freeze').write_text('0\n')
                    child.rmdir()
                (root/'cgroup.freeze').write_text('0\n')
                linux.publish(work/'fixture-release.json',dict(validated=False,emergency_cleanup=True))
            linux.publish(preparation/'emergency-cleanup-used.json',dict(used=True,proof_invalid=True))
        for thread in threads:
            thread.join(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-main',action='store_true')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256')
    parser.add_argument('--work',type=Path)
    parser.add_argument('--run-root',action='store_true')
    parser.add_argument('--preparation',type=Path)
    parser.add_argument('--number')
    parser.add_argument('--variant',choices=['lost_controller_with_listener_fleet_and_control_holds',
        'lost_controller_during_exact_replacement_save_publication_pause'])
    parser.add_argument('--retired-fixture',type=Path)
    args = parser.parse_args()
    if args.fixture_main:
        return fixture_main(args.work)
    if args.execute:
        require(hashlib.sha256(args.job.read_bytes()).hexdigest() == args.expected_job_sha256,'Pinned fixture job required')
        return injected_controller(json.loads(args.job.read_bytes()))
    if args.run_root:
        require(args.preparation and args.number and args.variant,'One selected original private case required')
        require(args.retired_fixture == Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/handoff-recovery-integration-CPU-original01-preparation-20261019/root-independent-readback.json'), 'Exact immutable retired fixture input required')
        require(hashlib.sha256(args.retired_fixture.read_bytes()).hexdigest() == 'c466015bd089b8fe0f49bae00c02ad209d9f8b0ee929b514145dd151defb362c', 'Retired original fixture input changed')
        retired = json.loads(args.retired_fixture.read_bytes())['original_fixture']
        require(not Path('/proc',str(retired['owner']['pid'])).exists(), 'Retired fixture original must remain absent')
        root_run(args.preparation,args.number,args.variant,retired)
        return 0
    print('PLAN_ONLY: no reads, outputs or runtime actions')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
