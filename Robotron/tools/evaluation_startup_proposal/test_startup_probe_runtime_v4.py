"""CPU adapter contracts with controlled capabilities; no real device or emulator."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import startup_probe_runtime_v4 as adapter
import reconcile_acceptance_tap_v2 as strict_tap
import startup_probe_core_v2 as core
GAME=adapter.GAME
if hashlib.sha256((HERE/'startup_probe_core_v2.py').read_bytes()).hexdigest()!=adapter.EXPECTED['core']:
    raise ValueError('Exact tested coordinator source required')
SETTINGS=dict(slots=list(core.SLOTS),frames=4096,max_wall_s=300,poll_s=0.25)


def pin(path):
    path=Path(path);raw=path.read_bytes();s=path.stat()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=adapter.fd_identity(s))


def schema_job(game):
    run=game/'logs/managed-learning-20261015/run-26';run.mkdir(parents=True,exist_ok=True)
    jobdir=run/'preparation';jobdir.mkdir(exist_ok=True)
    return dict(schema='robotron-private-startup-runtime-job-v2',output=str(run/'original-probe'),
        package=dict(sha256=adapter.PACKAGE_SHA),checkpoint={},predecessor={},main={},
        binary_inputs=[dict(path='/usr/games/mame'),dict(path=str(game/'roms/robotron.zip'))]+[
            dict(path=str(game/'roms/robotron'/filename),sha256=sha,bytes=4096)
            for filename,sha in adapter.ROM_INPUTS.values()],
        boot_assets=str(game/'logs/managed-learning-20261015/sidecar-boot-assets-v1'),boot_identity='a'*64,
        sessions={str(s):format(s,'032x') for s in adapter.SLOTS},affinity=[0,1],
        lease=dict(path='/dev/shm/robotron-snapshot-smoke-gpu0.lock',device=32,inode=757),
        external_guard_permit_path=str(jobdir/'original-live-guard-permit.json'),
        sources={**{k:dict(sha256=v,**({'path':str(HERE/('reconcile_acceptance_tap_v2.py' if k=='tap_join' else 'startup_server_prefix_v2.py'))} if k in ('tap_join','raw_matcher') else {})) for k,v in adapter.EXPECTED.items()},
                 'runtime':dict(path=str(HERE/'startup_probe_runtime_v4.py'))})


def matching():
    return dict(status='MATCHED_DIAGNOSTIC_PREFIX_ONLY',matched_frames=65536,accepted_frames=65536,
        rejected_frames=0,actor_slots=16,raw_ROM_start_acceptance_proven=False,start_eligibility_changed=False,
        protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False)


def footer(bound_slot,bound_session,**changes):
    row=dict(schema='robotron-ROM-start-tap-v1',kind='footer',slot=bound_slot,session=bound_session,sequence=4099,
        reason='capacity',inputs_observed=4096,writes_observed=0,faults=0,failed=False,logging_failed=False,
        last_input_frame=4095,capacity_reached=True,raw_provenance_only=True,
        real_ROM_start_acceptance_proven=False,start_eligibility_changed=False)
    row.update(changes)
    return (json.dumps(row,separators=(',',':'))+'\n').encode()


class Process:
    def __init__(self):self.events=[];self.alive=True;self.pid=99999999
    def poll(self):return None if self.alive else 0
    def terminate(self):self.events.append('terminate');self.alive=False
    def wait(self,timeout):self.events.append('wait');return 0
    def kill(self):self.events.append('kill');self.alive=False


class FakeSystem:
    def __init__(self):
        self.events=[];self.failure=None;self.runtime=None;self.reader=types.SimpleNamespace(pin=pin)
        self.helper_failure=False;self.launch_failure=False;self.defer_slot=None;self.defer_checks=0;self.checks=0
    def authenticate(self,r):
        self.runtime=r;self.events.append('authenticate')
        if self.failure=='authenticate':raise ValueError('missing authenticated predecessor')
    def acquire(self,r):
        self.events.append('acquire')
        if self.failure=='acquire':raise OSError('fake lease busy')
    def bootstrap(self,r):
        self.events.append('bootstrap')
        if self.failure=='bootstrap':raise RuntimeError('fake compile failed')
        r.output.mkdir();r.owns_output=True;r.selected=types.SimpleNamespace(label='CPU-private-prefix')
        server=types.SimpleNamespace(running=True,shutdown_event=threading.Event())
        server.stop=lambda:self.events.append('server_stop') or []
        r.server=server
        r.controller=types.SimpleNamespace(enter=lambda *a,**k:self.events.append('enter'),
            exit=lambda:self.events.append('exit'))
        r.worker=types.SimpleNamespace(start=lambda:self.events.append('worker_start'),is_alive=lambda:True)
        def launch():
            self.events.append('fleet_launch')
            if self.launch_failure:
                child=Process();r.owned_handles.append(child)
                raise OSError('fake birth inspection failed after Popen')
        r.fleet=types.SimpleNamespace(launch=launch,stop=lambda:self.events.append('fleet_stop') or [])
        def cleanup(*args):
            self.events.append('frozen_cleanup')
            if self.helper_failure:raise ValueError('fake timeout evidence failure')
            return dict(actor_timeout_logs={s:0 for s in adapter.SLOTS}),[]
        def fallback(*args):self.events.append('fallback_cleanup');return []
        r.frozen=types.SimpleNamespace(cleanup_with_timeout_evidence=cleanup,cleanup_job=fallback,mame_spec=None)
        r.original_spec=lambda *a:None
        class Recorder:
            def __init__(self,sessions,write,limit):
                self.lock=threading.RLock();self.closed=self.failed=False;self.faults=self.rows=0
                self.counts={s:0 for s in sessions};self.epochs={s:1 for s in sessions};self.clients={}
                write('synthetic-server-prefix\n')
        system=self
        class Capture:
            def __enter__(self):system.events.append('capture_enter')
            def __exit__(self,*a):system.events.append('capture_exit')
        def reconcile(lua,server,sessions,limit):
            assert set(lua)==set(adapter.SLOTS) and all(v==b'synthetic-Lua-prefix\n' for v in lua.values())
            assert server==b'synthetic-server-prefix\n' and limit==4096
            self.events.append('reconcile');return matching()
        r.trace=types.SimpleNamespace(Recorder=Recorder,capture=lambda *a:Capture(),reconcile=reconcile)
        def tap_reconcile(lua,server,taps,consoles,sessions,rom3,rom10,limit):
            assert set(lua)==set(taps)==set(consoles)==set(sessions)==set(adapter.SLOTS)
            assert all(value==b'synthetic-console\n' for value in consoles.values())
            assert all(json.loads(value)['inputs_observed']==4096 for value in taps.values())
            assert limit==4096 and rom3.startswith(b'fake-ROM:') and rom10.startswith(b'fake-ROM:')
            self.events.append('tap_reconcile')
            return dict(status='MATCHED_PASSIVE_TAP_CONTENT_ONLY',raw_prefix_reconciliation=matching(),
                actor_slots=16,matched_inputs=65536,original_runtime_outcome_verified=False,
                raw_ROM_start_acceptance_proven=False,start_eligibility_changed=False,
                protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False)
        r.tap_join=types.SimpleNamespace(COMMON=strict_tap.COMMON,KEYS=strict_tap.KEYS,reconcile=tap_reconcile)
        (r.output/'actors').mkdir(mode=0o700)
        for slot in adapter.SLOTS:
            p=r.output/'actors'/str(slot);p.mkdir(mode=0o700)
            (p/'startup-prefix.jsonl').write_bytes(b'synthetic-Lua-prefix\n')
            (p/'startup-acceptance.jsonl').write_bytes(b'')
            (p/'console.log').write_bytes(b'synthetic-console\n')
            r.actor_outputs[slot]=dict(directory=str(p),lua=str(p/'startup-prefix.jsonl'),
                tap=str(p/'startup-acceptance.jsonl'),console=str(p/'console.log'),
                session=r.job['sessions'][str(slot)],directory_identity=adapter.fd_identity(p.stat()))
    def binary_bytes(self,r,filename,sha):
        self.events.append('binary-'+filename)
        return b'fake-ROM:'+filename.encode(),dict(path='CPU-fixture/'+filename,sha256=sha)
    def check(self,r):
        self.events.append('check')
        r.recorder.counts={s:4096 for s in adapter.SLOTS};r.recorder.rows=65536;r.recorder.closed=True
        self.checks+=1
        for slot in adapter.SLOTS:
            if slot==self.defer_slot and self.checks<=self.defer_checks:continue
            path=r.output/'actors'/str(slot)/'startup-acceptance.jsonl'
            raw=footer(slot,r.job['sessions'][str(slot)])
            if path.read_bytes()!=raw:path.write_bytes(raw)
    def audit(self,r):
        self.events.append('audit')
        return dict(valid=True,all_owned_actors_absent=True,sources_unchanged=True,
                    checkpoint_unchanged=True,main_healthy=True,runtime_timeouts=0)
    def release(self):self.events.append('release');return []
    def spawn(self,r,argv,kwargs):self.events.append('spawn');return Process()


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='startup-runtime-CPU-')
        self.root=Path(self.temp.name).resolve()
        self.pending_runtimes=[]
        self.capability_patches=[patch.object(adapter.subprocess,'run',side_effect=AssertionError('real query forbidden')),
            patch.object(adapter.subprocess,'Popen',side_effect=AssertionError('real Popen forbidden')),
            patch.object(adapter.socket,'socket',side_effect=AssertionError('real socket forbidden'))]
        for item in self.capability_patches:item.start()
    def tearDown(self):
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):
            for runtime in self.pending_runtimes:
                if not runtime.cleanup_done:runtime.cleanup()
        for item in reversed(self.capability_patches):item.stop()
        self.temp.cleanup()
    def runtime(self,system=None,name='private-output'):
        job=dict(output=str(self.root/name),sessions={str(s):format(s,'032x') for s in adapter.SLOTS})
        return adapter.Runtime(job,system=system if system is not None else FakeSystem())
    def execute(self,r):
        # Patch the same module/capability instance actually used by Runtime.
        # Any accidental real actor or socket creation fails the CPU contract.
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder), \
             patch.object(adapter.subprocess,'Popen',side_effect=AssertionError('real Popen forbidden in CPU contracts')), \
             patch.object(adapter.socket,'socket',side_effect=AssertionError('real socket forbidden in CPU contracts')):
            return core.execute(r,SETTINGS,stopped=r.stop_event.is_set)

    def test_constructor_has_no_capability_calls_or_output_creation(self):
        system=FakeSystem();r=self.runtime(system)
        self.assertEqual(system.events,[]);self.assertFalse(r.output.exists())
        self.assertIs(r.system,system);self.assertEqual(r.owned_handles,[])

    def test_same_injected_system_runs_complete_actual_adapter_lifecycle(self):
        r=self.runtime();result=self.execute(r)
        self.assertTrue(result['valid']);self.assertEqual(r.system.events[:3],['authenticate','acquire','bootstrap'])
        self.assertLess(r.system.events.index('capture_enter'),r.system.events.index('worker_start'))
        self.assertLess(r.system.events.index('worker_start'),r.system.events.index('fleet_launch'))
        self.assertLess(r.system.events.index('frozen_cleanup'),r.system.events.index('capture_exit'))
        self.assertLess(r.system.events.index('capture_exit'),r.system.events.index('reconcile'))
        self.assertLess(r.system.events.index('audit'),r.system.events.index('release'))
        self.assertTrue((r.output/'result.json').exists())
        self.assertEqual(json.loads((r.output/'result.json').read_bytes())['status'],'MATCHED_DIAGNOSTIC_PREFIX_ONLY')
        self.assertEqual(len(list(r.output.glob('Lua-*-prefix-readonly.jsonl'))),16)

    def test_failed_authentication_never_acquires_lease_or_bootstraps(self):
        r=self.runtime();r.system.failure='authenticate';result=self.execute(r)
        self.assertFalse(result['valid']);self.assertNotIn('acquire',r.system.events)
        self.assertNotIn('bootstrap',r.system.events);self.assertFalse(r.output.exists())

    def test_acquire_and_bootstrap_failures_release_and_preserve_failure(self):
        for phase in ('acquire','bootstrap'):
            r=self.runtime();r.system.failure=phase;result=self.execute(r)
            self.assertFalse(result['valid']);self.assertIn('release',r.system.events)
            self.assertNotIn('fleet_launch',r.system.events)

    def test_registered_handle_is_cleaned_when_launch_birth_check_fails(self):
        r=self.runtime();r.system.launch_failure=True;result=self.execute(r)
        self.assertFalse(result['valid']);self.assertEqual(len(r.owned_handles),1)
        self.assertEqual(r.owned_handles[0].events,['terminate','wait'])
        self.assertFalse(r.owned_handles[0].alive);self.assertEqual(r.system.events.count('fleet_launch'),1)

    def test_real_spawn_registers_handle_before_birth_inspection_failure(self):
        r=self.runtime();system=adapter.System();process=Process()
        context=dict(directory=str(self.root),tap=str(self.root/'tap'),lua=str(self.root/'lua'),
                     session=r.job['sessions']['4096'])
        r.actor_outputs[4096]=context
        with patch.object(adapter.subprocess,'Popen',return_value=process) as launch, \
             patch.object(adapter,'process_start',return_value=None):
            with self.assertRaisesRegex(ValueError,'live birth'):
                system.spawn(r,['/usr/games/mame'],dict(cwd=self.root,env={'ROBOTRON_CLIENT_SLOT':'4096',
                    'ROBOTRON_STARTUP_ACCEPTANCE_PATH':context['tap'],
                    'ROBOTRON_STARTUP_DIAGNOSTIC_PATH':context['lua'],
                    'ROBOTRON_STARTUP_DIAGNOSTIC_SESSION':context['session']}))
        launch.assert_called_once();self.assertEqual(r.owned_handles,[process]);self.assertEqual(r.births,{})
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):r.cleanup()
        self.assertEqual(process.events,['terminate','wait']);self.assertFalse(process.alive)

    def test_timeout_helper_failure_still_invokes_full_fallback_cleanup(self):
        r=self.runtime();r.system.helper_failure=True;result=self.execute(r)
        self.assertFalse(result['valid']);self.assertIn('fallback_cleanup',r.system.events)
        self.assertIn('capture_exit',r.system.events);self.assertIn('release',r.system.events)

    def test_missing_prefix_does_not_prevent_other_original_copies(self):
        r=self.runtime()
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):
            r.prepare();r.start();r.cleanup()
        missing=r.output/'actors/4096/startup-prefix.jsonl';missing.unlink()
        with self.assertRaises(ValueError):r.collect()
        inventory=json.loads((r.output/'original-prefix-capture-inventory.json').read_bytes())
        self.assertEqual(len(inventory['retained']),50)
        self.assertIn('console-4111',inventory['retained']);self.assertIn('tap-4096',inventory['retained']);self.assertTrue(inventory['errors'])
        self.assertFalse((r.output/'original-prefix-reconciliation.json').exists())

    def test_original_prefix_mode_and_bytes_are_unchanged(self):
        r=self.runtime();r.output.mkdir();r.owns_output=True;r.cleanup_done=True
        path=r.output/'producer.jsonl';path.write_bytes(b'{"n":1}\n');before=pin(path)
        raw,entry=r.copy_original(path,'readonly.jsonl',1024)
        self.assertEqual(raw,b'{"n":1}\n');self.assertEqual(before,pin(path))
        self.assertEqual(entry['identity']['mode'],'0o444')

    def test_symlink_hardlink_foreign_and_oversized_prefixes_fail(self):
        r=self.runtime();r.output.mkdir();r.owns_output=True;r.cleanup_done=True
        path=r.output/'producer';path.write_bytes(b'1234')
        with self.assertRaises(ValueError):r.copy_original(path,'too-big',1)
        link=r.output/'symlink';link.symlink_to(path)
        with self.assertRaises(ValueError):r.copy_original(link,'linked-copy',100)
        hard=r.output/'hardlink';os.link(path,hard)
        with self.assertRaises(ValueError):r.copy_original(hard,'hard-copy',100)
        foreign=self.root/'foreign';foreign.write_bytes(b'x')
        with self.assertRaises(ValueError):r.copy_original(foreign,'foreign-copy',100)

    def test_flat_publication_paths_and_precleanup_copy_are_enforced(self):
        r=self.runtime();r.output.mkdir();r.owns_output=True;path=r.output/'original';path.write_bytes(b'x')
        with self.assertRaises(ValueError):r.copy_original(path,'copy',100)
        with self.assertRaises(ValueError):r.publish_bytes('../escape',b'x')

    def test_mame_spec_changes_only_owned_actor_diagnostic_environment(self):
        r=self.runtime();r.output.mkdir();r.owns_output=True;selected=object();r.selected=selected;environment={'ROBOTRON_CLIENT_SLOT':'4096','unchanged':'value'}
        r.original_spec=lambda job,slot,library:(['/usr/games/mame'],environment,r.output/'actors'/str(slot))
        argv,after,path=r.mame_spec(selected,4096,'shim')
        self.assertEqual(environment,{'ROBOTRON_CLIENT_SLOT':'4096','unchanged':'value'})
        self.assertEqual(after['ROBOTRON_STARTUP_DIAGNOSTIC_SESSION'],r.job['sessions']['4096'])
        self.assertEqual(after['ROBOTRON_STARTUP_DIAGNOSTIC_LIMIT'],'4096')
        self.assertEqual(after['ROBOTRON_STARTUP_DIAGNOSTIC_PATH'],str(path/'startup-prefix.jsonl'))
        self.assertEqual(after['ROBOTRON_STARTUP_ACCEPTANCE_PATH'],str(path/'startup-acceptance.jsonl'))
        self.assertEqual(path.stat().st_mode&0o777,0o700)
        with self.assertRaises(ValueError):r.mame_spec(object(),4096,'shim')
        with self.assertRaises(ValueError):r.mame_spec(selected,0,'shim')

    def test_existing_Lua_trace_is_not_reused(self):
        r=self.runtime();r.output.mkdir();r.owns_output=True;selected=object();r.selected=selected;private=r.output/'actors/4096';private.mkdir(parents=True)
        (private/'startup-prefix.jsonl').write_bytes(b'old')
        r.original_spec=lambda *a:([],{},private)
        with self.assertRaises(ValueError):r.mame_spec(selected,4096)
        self.assertEqual((private/'startup-prefix.jsonl').read_bytes(),b'old')

    def test_snapshot_is_a_copy(self):
        r=self.runtime()
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):r.prepare();r.start()
        before=r.snapshot();before['counts'][4096]=100
        self.assertEqual(r.recorder.counts[4096],0)
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):r.cleanup()

    def test_real_system_check_releases_recorder_lock_before_controller_tick(self):
        r=self.runtime();system=adapter.System();r.output.mkdir();r.owns_output=True
        r.system.reader=types.SimpleNamespace(pin=pin)
        # A non-reentrant lock plus an independent callback thread exercises the
        # server's client-lock -> recorder-lock order without risking a hang.
        lock=threading.Lock();events=[]
        r.recorder=types.SimpleNamespace(lock=lock,closed=False,failed=False,faults=0,rows=0,
            counts={s:0 for s in adapter.SLOTS},epochs={s:1 for s in adapter.SLOTS},clients={})
        def tick():
            def callback():
                acquired=lock.acquire(timeout=1)
                events.append(acquired)
                if acquired:lock.release()
            thread=threading.Thread(target=callback);thread.start();thread.join(2)
            self.assertFalse(thread.is_alive());self.assertEqual(events,[True])
            return dict(phase='warming',valid=None)
        r.controller=types.SimpleNamespace(tick=tick)
        r.frozen=types.SimpleNamespace(check_protocol=lambda *a:None)
        r.config=r.actor=r.checkpoint_signature=r.checkpoint=None
        r.server=types.SimpleNamespace(running=True,inference_only_error=None)
        r.worker=types.SimpleNamespace(is_alive=lambda:True)
        r.fleet=types.SimpleNamespace(exited=lambda:False)
        r.births={s:dict(pid=900000+s,starttime_ticks=5,mask=[0,1]) for s in adapter.SLOTS}
        system.guard_owner=dict(pid=800000,starttime_ticks=5)
        with patch.object(adapter,'process_start',return_value=5), \
             patch.object(adapter.os,'sched_getaffinity',return_value={0,1}), \
             patch.object(system,'health',side_effect=lambda *a:events.append('health')):
            system.check(r)
        boundary=json.loads(next(r.output.glob('boundary-*.json')).read_bytes())
        self.assertEqual(boundary['before']['counts'],boundary['after']['counts'])
        self.assertIn('no atomic simultaneity',boundary['scope'])
        self.assertEqual(events,[True,'health'])

    def test_real_bootstrap_orders_environment_before_imports_and_binds_private_resources(self):
        r=self.runtime();system=adapter.System();events=[];root=self.root/'source'
        r.job.update(checkpoint=dict(path=str(self.root/'protected.pt'),sha256='a'*64),
            boot_assets=str(self.root/'boot'),boot_identity='b'*64)
        system.root=root
        names=['tools/run_frozen_sidecar.py','Scripts/dqn/config.py','Scripts/dqn/inference_actor.py',
               'Scripts/dqn/socket_server.py','Scripts/dqn/managed_measurement.py','Scripts/startup_server_prefix_v2.py']
        system.package=dict(file_pins={n:dict(path=str(root/n)) for n in names})
        def read_pin(entry,as_json=False):events.append(('read',entry['path']));return b'fake'
        system.reader=types.SimpleNamespace(read_pin=read_pin,checked_module=lambda *a:frozen)
        class Job:
            def __init__(self,*args):
                self.args=args;self.directory=args[1];self.boot_assets=args[12]
            def validate(self,**kwargs):
                self.checked=kwargs;assert not self.directory.exists()
        def configure(selected):events.append('configure')
        def copy_checkpoint(selected):events.append('copy');return r.output/'checkpoint.pt','a'*64
        actor=types.SimpleNamespace(checkpoint_metadata={n:0 for n in
            ('learner_frame_count','frame_count','measurement_frame_count')},training_steps=7,optimized_samples=9)
        def build_actor(*args):events.append('build_actor');return actor
        def fleet(*args,**kwargs):
            events.append('fleet');self.assertIs(kwargs['popen'].__self__,r)
            self.assertEqual(kwargs['expected_boot_identity'],'b'*64)
            return types.SimpleNamespace()
        original_spec=lambda *a:None
        frozen=types.SimpleNamespace(GAME=root,Job=Job,
            boot_module=lambda:types.SimpleNamespace(load_snapshot=lambda *a:dict(identity='b'*64)),
            configure_environment=configure,copy_checkpoint=copy_checkpoint,checkpoint_identity=lambda *a:'signature',
            build_inference_actor=build_actor,fixed_boundary=lambda *a:dict(ready=True),
            mame_spec=original_spec,PrivateFleet=fleet)
        config=types.SimpleNamespace(__file__=str(root/'Scripts/dqn/config.py'),
            RL_CONFIG=types.SimpleNamespace(),metrics=types.SimpleNamespace(),game_settings=types.SimpleNamespace())
        def server(*args,**kwargs):
            self.assertIs(args[2],actor);self.assertIs(kwargs['replay_enabled'],False)
            return types.SimpleNamespace(async_buffer=None,inference_batcher=types.SimpleNamespace(max_batch_size=16),
                game_journal=object(),start=lambda:events.append('unexpected_server_start'))
        controller=object()
        modules={
            'torch':types.SimpleNamespace(set_num_threads=lambda n:events.append(('threads',n)),
                set_num_interop_threads=lambda n:events.append(('interop',n))),
            'dqn.config':config,
            'dqn.inference_actor':types.SimpleNamespace(__file__=str(root/'Scripts/dqn/inference_actor.py'),InferenceActor=object()),
            'dqn.socket_server':types.SimpleNamespace(__file__=str(root/'Scripts/dqn/socket_server.py'),SocketServer=server),
            'dqn.managed_measurement':types.SimpleNamespace(__file__=str(root/'Scripts/dqn/managed_measurement.py'),
                ManagedMeasurement=lambda *a,**k:controller),
            'startup_server_prefix_v2':types.SimpleNamespace(__file__=str(root/'Scripts/startup_server_prefix_v2.py')),
            'build_socket_wait':types.SimpleNamespace(build=lambda *a:'library')}
        def fake_import(name):
            self.assertIn('configure',events);self.assertIn('copy',events)
            events.append(('import',name));return modules[name]
        r.system=system
        system.reader.pin=pin
        # Even a mistaken dependency lookup cannot fall through to actual GPU,
        # subprocess, socket, or numerical modules in this CPU contract.
        with patch.object(adapter.sys,'path',list(sys.path)), \
             patch.object(adapter.importlib,'import_module',side_effect=fake_import), \
             patch.object(adapter.subprocess,'run',side_effect=AssertionError('real process query forbidden')), \
             patch.object(adapter.subprocess,'Popen',side_effect=AssertionError('real Popen forbidden')), \
             patch.object(adapter.socket,'socket',side_effect=AssertionError('real socket forbidden')):
            system.bootstrap(r)
        self.assertTrue(r.owns_output);self.assertEqual(r.selected.checked,dict(require_boot_assets=True))
        self.assertEqual(r.selected.args[3:12],('cuda',adapter.GPU,9999,240,300,1000,
            Path('/usr/games/mame'),adapter.GAME/'roms',2))
        self.assertEqual(r.selected.args[13:],('inductor',True,'confirmed_reset_reserves_v1',16))
        self.assertIs(r.controller,controller);self.assertIs(r.original_spec,original_spec)
        self.assertIs(frozen.mame_spec.__self__,r);self.assertFalse(r.worker.is_alive())
        self.assertFalse(config.metrics.training_enabled);self.assertEqual(config.RL_CONFIG.inference_batch_max_size,16)
        self.assertEqual(config.game_settings.difficulty,5);self.assertEqual(config.game_settings.start_level_min,1)
        self.assertEqual(config.game_settings.epsilon_pct,0);self.assertEqual(config.game_settings.expert_pct,0)

    def test_interruption_before_start_never_launches_fleet(self):
        r=self.runtime()
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):r.prepare()
        r.stop_event.set()
        with self.assertRaises(ValueError):r.start()
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):r.cleanup()
        self.assertNotIn('fleet_launch',r.system.events)

    def test_schema_binds_future_permit_path_without_circular_hash(self):
        game=self.root/'Game';job=schema_job(game)
        with patch.object(adapter,'GAME',game):
            self.assertEqual(adapter.checked_job(job),Path(job['output']))
        self.assertIsInstance(job['external_guard_permit_path'],str)
        self.assertNotIn('external_guard_permit',job)

    def test_schema_rejects_weak_package_sources_sessions_lease_or_output(self):
        game=self.root/'Game';job=schema_job(game)
        variants=[]
        bad=copy.deepcopy(job);bad['package']['sha256']='0'*64;variants.append(bad)
        bad=copy.deepcopy(job);bad['sources']['core']['sha256']='0'*64;variants.append(bad)
        bad=copy.deepcopy(job);bad['sessions']['4096']=bad['sessions']['4097'];variants.append(bad)
        bad=copy.deepcopy(job);bad['lease']['inode']=True;variants.append(bad)
        bad=copy.deepcopy(job);bad['output']=str(Path(job['output'])/'nested');variants.append(bad)
        with patch.object(adapter,'GAME',game):
            for value in variants:
                with self.assertRaises(ValueError):adapter.checked_job(value)

    def test_real_system_refuses_incomplete_job_before_any_device_or_process_call(self):
        r=adapter.Runtime(dict(output=str(self.root/'never-created')))
        with patch.object(adapter.subprocess,'run',side_effect=AssertionError('no process query')), \
             patch.object(adapter.socket,'socket',side_effect=AssertionError('no socket')), \
             patch.object(adapter.os,'open',side_effect=AssertionError('no lease open')):
            with self.assertRaises(ValueError):r.prepare()
        self.assertFalse(r.output.exists());self.assertIsNone(r.system.lease_fd)

    def test_module_default_entry_has_no_launch_branch(self):
        # The real entry is a library-only message. Run just that exact AST node
        # with __name__=__main__; no source bootstrap or capability is available.
        import ast,io
        from contextlib import redirect_stdout
        tree=ast.parse((HERE/'startup_probe_runtime_v4.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.If) and '__name__' in ast.unparse(n.test))
        stream=io.StringIO()
        with redirect_stdout(stream):exec(compile(ast.Module(body=[node],type_ignores=[]),'<library-entry>','exec'),{'__name__':'__main__'})
        self.assertIn('LIBRARY_ONLY',stream.getvalue())

    def started(self,name='private-output',system=None):
        r=self.runtime(system,name)
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):
            r.prepare();r.start()
        self.pending_runtimes.append(r)
        return r

    def test_server_completion_waits_for_all16_tap_tails_before_cleanup(self):
        system=FakeSystem();system.defer_slot=4096;system.defer_checks=1
        r=self.started(system=system)
        system.check(r);first=r.snapshot()
        self.assertEqual(first['rows'],65536);self.assertFalse(first['closed'])
        self.assertEqual(sum(x['complete'] for x in r.tap_observations.values()),15)
        self.assertFalse(r.cleanup_done)
        system.check(r);self.assertTrue(r.snapshot()['closed'])

    def test_same_actual_runtime_executes_a_deferred_tail_without_early_cleanup(self):
        system=FakeSystem();system.defer_slot=4100;system.defer_checks=2
        r=self.runtime(system);result=self.execute(r)
        self.assertTrue(result['valid']);self.assertEqual(system.checks,3)
        self.assertEqual(system.events.count('fleet_launch'),1)
        self.assertEqual(system.events.count('tap_reconcile'),1)
        self.assertLess(system.events.index('tap_reconcile'),system.events.index('release'))
        self.assertEqual(len(r.tap_observations),16)

    def test_partial_last_line_stays_pending_until_its_original_newline_arrives(self):
        r=self.started();r.system.check(r)
        path=Path(r.actor_outputs[4096]['tap']);raw=path.read_bytes();path.write_bytes(raw[:-1])
        self.assertFalse(r.snapshot()['closed'])
        path.write_bytes(raw);self.assertTrue(r.snapshot()['closed'])

    def test_missing_then_created_tap_is_pending_but_a_seen_tap_cannot_disappear(self):
        r=self.started();r.system.check(r)
        path=Path(r.actor_outputs[4096]['tap']);raw=path.read_bytes();path.unlink()
        self.assertFalse(r.snapshot()['closed'])
        path.write_bytes(raw);self.assertTrue(r.snapshot()['closed'])
        path.unlink()
        with self.assertRaisesRegex(ValueError,'disappeared'):
            r.snapshot()

    def test_faulty_session_counts_and_close_footer_cannot_complete_snapshot(self):
        cases=[dict(faults=1),dict(failed=True),dict(inputs_observed=4095),dict(last_input_frame=4094),
               dict(session='f'*32),dict(reason='machine_stop'),dict(sequence=4098)]
        for n,changes in enumerate(cases):
            r=self.started(name='footer-'+str(n));r.system.check(r)
            Path(r.actor_outputs[4096]['tap']).write_bytes(footer(4096,r.job['sessions']['4096'],**changes))
            with self.assertRaises(ValueError):r.snapshot()

    def test_finished_tap_append_replacement_and_truncation_are_not_adopted(self):
        for n,kind in enumerate(['append','replace','truncate']):
            r=self.started(name='identity-'+str(n));r.system.check(r);self.assertTrue(r.snapshot()['closed'])
            path=Path(r.actor_outputs[4096]['tap'])
            if kind=='append':
                with path.open('ab') as stream:stream.write(b'{}\n')
            elif kind=='truncate':path.write_bytes(b'')
            else:
                replacement=path.with_name('replacement');replacement.write_bytes(path.read_bytes())
                os.replace(replacement,path)
            with self.assertRaises(ValueError):r.snapshot()

    def test_duplicate_tail_fields_fault_event_and_oversized_tail_rejected(self):
        for n,raw in enumerate([footer(4096,format(4096,'032x')).replace(b'{',b'{"failed":false,',1),
                                b'{"kind":"fault"}\n',b'x'*2049+b'\n']):
            r=self.started(name='malformed-'+str(n));r.system.check(r)
            Path(r.actor_outputs[4096]['tap']).write_bytes(raw)
            with self.assertRaises(ValueError):r.snapshot()

    def test_tail_file_and_directory_symlinks_or_mode_changes_rejected(self):
        r=self.started();r.system.check(r)
        path=Path(r.actor_outputs[4096]['tap']);real=path.with_name('moved');path.rename(real);path.symlink_to(real)
        with self.assertRaises(ValueError):r.snapshot()
        path.unlink();real.rename(path)
        Path(r.actor_outputs[4096]['directory']).chmod(0o755)
        with self.assertRaises(ValueError):r.snapshot()

    def test_snapshot_disk_reads_do_not_own_recorder_lock(self):
        r=self.started();r.system.check(r);lock=threading.Lock();r.recorder.lock=lock;calls=[]
        original=r.tap_tail
        def witness(slot):
            acquired=lock.acquire(timeout=0.1);self.assertTrue(acquired)
            if acquired:lock.release()
            calls.append(slot);return original(slot)
        with patch.object(r,'tap_tail',side_effect=witness):self.assertTrue(r.snapshot()['closed'])
        self.assertEqual(calls,list(adapter.SLOTS))

    def test_missing_raw_tap_and_console_files_preserve_all_other_originals(self):
        r=self.started()
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):r.cleanup()
        for slot,name in [(4096,'startup-prefix.jsonl'),(4097,'startup-acceptance.jsonl'),(4098,'console.log')]:
            (r.output/'actors'/str(slot)/name).unlink()
        with self.assertRaises(ValueError):r.collect()
        inventory=json.loads((r.output/'original-prefix-capture-inventory.json').read_bytes())
        self.assertEqual(len(inventory['retained']),48)
        self.assertEqual(len(inventory['errors']),3)
        self.assertIn('tap-4096',inventory['retained']);self.assertIn('console-4096',inventory['retained'])
        self.assertIn('ROM3',inventory['retained']);self.assertIn('Lua-4111',inventory['retained'])

    def test_partial_bootstrap_still_inventories_every_prefix_and_binary_error(self):
        r=self.runtime();r.output.mkdir();r.owns_output=True;r.cleanup_done=True
        with self.assertRaises(ValueError):r.collect()
        inventory=json.loads((r.output/'original-prefix-capture-inventory.json').read_bytes())
        self.assertEqual(set(inventory['retained']),{'ROM3','ROM10'})
        self.assertGreaterEqual(len(inventory['errors']),50)

    def test_original_oversize_prefix_retained_bounded_and_explicitly_invalid(self):
        r=self.runtime();r.output.mkdir();r.owns_output=True;r.cleanup_done=True
        path=r.output/'oversized';path.write_bytes(b'123456');original=pin(path)
        with self.assertRaisesRegex(ValueError,'capped prefix retained'):
            r.copy_original(path,'oversized-readonly',3)
        self.assertEqual((r.output/'oversized-readonly.oversize-prefix.bin').read_bytes(),b'123')
        record=json.loads((r.output/'oversized-readonly.oversize-original-identity.json').read_bytes())
        self.assertFalse(record['complete']);self.assertTrue(record['truncated'])
        self.assertIsNone(record['source_full_sha256']);self.assertEqual(pin(path),original)

    def test_bound_ROM_binary_bytes_preserve_normal_permissions_and_detect_mismatch(self):
        game=self.root/'Game';path=game/'roms/robotron/chip';path.parent.mkdir(parents=True)
        path.write_bytes(b'R'*4096);entry=pin(path);r=self.runtime();r.job['binary_inputs']=[entry]
        system=adapter.System();system.reader=types.SimpleNamespace(pin=pin)
        with patch.object(adapter,'GAME',game):
            raw,observed=system.binary_bytes(r,'chip',entry['sha256'])
            self.assertEqual((raw,observed),(b'R'*4096,entry));self.assertEqual(pin(path),entry)
            path.write_bytes(b'S'*4096)
            with self.assertRaises(ValueError):system.binary_bytes(r,'chip',entry['sha256'])

    def test_checker_cannot_promote_partial_content_or_claim_runtime_or_quality(self):
        for n,changes in enumerate([dict(matched_inputs=4),dict(actor_slots=15),
                                   dict(original_runtime_outcome_verified=True),dict(quality_qualified=True)]):
            r=self.runtime(name='invalid-checker-'+str(n))
            original=r.system.bootstrap
            def bootstrap(runtime,original=original,changes=changes):
                original(runtime);join=runtime.tap_join.reconcile
                runtime.tap_join.reconcile=lambda *a,**k:dict(join(*a,**k),**changes)
            r.system.bootstrap=bootstrap
            result=self.execute(r)
            self.assertFalse(result['valid']);self.assertIn('release',r.system.events)
            self.assertTrue((r.output/'original-prefix-capture-inventory.json').exists())
            self.assertFalse((r.output/'original-passive-tap-content-reconciliation.json').exists())

    def test_never_arriving_tap_uses_original_coordinator_deadline_and_still_collects(self):
        system=FakeSystem();system.defer_slot=4096;system.defer_checks=1000;r=self.runtime(system)
        clock=iter(range(0,10000,25))
        with patch.object(adapter.signal,'signal',return_value=signal_placeholder):
            result=core.execute(r,SETTINGS,clock=lambda:next(clock),sleep=lambda seconds:None)
        self.assertFalse(result['valid']);self.assertTrue(any('deadline' in e['message'] for e in result['errors']))
        self.assertIn('release',system.events)
        self.assertTrue((r.output/'tap-4096-prefix-readonly.jsonl').exists())

    def test_real_collect_joins_actual_Lua_all16x4096_without_runtime_certification(self):
        fixture_path=HERE/'test_reconcile_acceptance_tap_v2.py'
        spec=importlib.util.spec_from_file_location('_runtime_v2_actual_join_fixture',fixture_path)
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        fixture.Tests.setUpClass()
        sessions={slot:format(slot,'032x') for slot in adapter.SLOTS}
        data=fixture.Tests.make_fixture(sessions,4096,4096)
        binaries={filename:(data[name.lower()],pin(GAME/'roms/robotron'/filename))
                  for name,(filename,sha) in adapter.ROM_INPUTS.items()}
        for failure in [False,True]:
            r=self.started(name='actual-join-'+str(failure))
            with patch.object(adapter.signal,'signal',return_value=signal_placeholder):r.cleanup()
            (r.output/'server-prefix.jsonl').write_bytes(data['server_prefix'])
            for slot in adapter.SLOTS:
                p=r.output/'actors'/str(slot)
                (p/'startup-prefix.jsonl').write_bytes(data['lua_prefixes'][slot])
                (p/'startup-acceptance.jsonl').write_bytes(data['tap_prefixes'][slot])
                console=data['actor_consoles'][slot]
                if failure and slot==4096:
                    console+=b'ROBOTRON_STARTUP_ACCEPTANCE_TAP_FAILURE:stream_close_error\n'
                (p/'console.log').write_bytes(console)
            r.trace=fixture.Tests.trace;r.tap_join=strict_tap
            r.system.binary_bytes=lambda runtime,filename,sha:binaries[filename]
            if failure:
                with self.assertRaisesRegex(ValueError,'console'):r.collect()
                inventory=json.loads((r.output/'original-prefix-capture-inventory.json').read_bytes())
                self.assertEqual(len(inventory['retained']),51)
                self.assertIn(b'stream_close_error',(r.output/'console-4096-prefix-readonly.jsonl').read_bytes())
                self.assertFalse((r.output/'original-passive-tap-content-reconciliation.json').exists())
            else:
                result=r.collect();self.assertEqual(result['tap_provenance']['matched_inputs'],65536)
                self.assertFalse(result['tap_provenance']['original_runtime_outcome_verified'])
                self.assertFalse(result['tap_provenance']['raw_ROM_start_acceptance_proven'])

    def test_schema_rejects_legacy125_and_missing_ROM_or_adjacent_matcher_binding(self):
        game=self.root/'Game';job=schema_job(game);variants=[]
        bad=copy.deepcopy(job);bad['schema']='robotron-private-startup-runtime-job-v1';variants.append(bad)
        bad=copy.deepcopy(job);bad['binary_inputs'].pop();variants.append(bad)
        bad=copy.deepcopy(job);bad['sources']['raw_matcher']['path']=str(self.root/'wrong.py');variants.append(bad)
        bad=copy.deepcopy(job);bad['package']['sha256']='c56d84a5edc4da8b1e0cc7c775fbbe09ec7a6704048e42b870b96addde9ddbc5';variants.append(bad)
        with patch.object(adapter,'GAME',game):
            for value in variants:
                with self.assertRaises(ValueError):adapter.checked_job(value)


signal_placeholder=object()
if __name__=='__main__':
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(name.startswith('dqn.') for name in sys.modules)
    print(json.dumps(dict(schema='robotron-private-startup-runtime-CPU-contracts-v2',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual runtime-adapter control flow with fake capability instance, fake process/server/model resources and real temporary prefix files; no actual process/device query, listener, model or emulator.',
        production_changed=False,external_guard_present=False,launch_selected=False,
        protocol_selected=False,real_ROM_start_proven=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
