"""CPU integration for the guarded launcher with same-instance capabilities."""
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import startup_probe_launch_v4 as launch
import startup_probe_runtime_v4 as adapter
import startup_probe_watchdog_v1 as watchdog
import startup_probe_core_v2 as core
assert hashlib.sha256((HERE/'startup_probe_watchdog_v1.py').read_bytes()).hexdigest()==launch.EXPECTED['watchdog']
assert hashlib.sha256((HERE/'startup_probe_core_v2.py').read_bytes()).hexdigest()==launch.EXPECTED['core']


def file_pin(path):
    path=Path(path);before=path.stat();raw=path.read_bytes();after=path.stat()
    assert adapter.fd_identity(before)==adapter.fd_identity(after)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=adapter.fd_identity(after))


def publish(path,raw):
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return file_pin(path)


def checked_read(entry,as_json=True):
    if 'path' not in entry:return {}
    if file_pin(entry['path'])!=entry:raise ValueError('fixture artifact full pin differs')
    if entry['identity']['mode']!='0o444':raise ValueError('fixture immutable artifact required')
    raw=Path(entry['path']).read_bytes()
    return json.loads(raw) if as_json else raw


def matched_reconciliation():
    raw=dict(status='MATCHED_DIAGNOSTIC_PREFIX_ONLY',matched_frames=65536,accepted_frames=65536,
        rejected_frames=0,actor_slots=16,raw_ROM_start_acceptance_proven=False,start_eligibility_changed=False,
        protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False)
    tap=dict(status='MATCHED_PASSIVE_TAP_CONTENT_ONLY',raw_prefix_reconciliation=dict(raw),
        actor_slots=16,matched_inputs=65536,original_runtime_outcome_verified=False,
        raw_ROM_start_acceptance_proven=False,start_eligibility_changed=False,protocol_selected=False,
        quality_qualified=False,learning_speed_gain_verified=False,
        slots={str(slot):dict(inputs=4096,status_writes=0,writes_before_first_input=0,
            common_restart_write_observations=0,START1_write_observations=[],
            captured_loaded_span_matches_pinned_ROM=True,full_loaded_ROM_image_verified=False,
            first_start_certified=False,admission_clock_ordering_verified=False) for slot in core.SLOTS},
        input_sha256=dict(server='0'*64,**{kind:{str(slot):'0'*64 for slot in core.SLOTS}
                                          for kind in ['lua','tap','console']}))
    return dict(raw,tap_provenance=tap)


def coordinator_result(reconciliation=None):
    runtime=types.SimpleNamespace(prepare=lambda:None,start=lambda:None,check=lambda:None,
        snapshot=lambda:dict(closed=True,failed=False,faults=0,rows=65536,pending=0,
            counts={slot:4096 for slot in core.SLOTS},epochs={slot:1 for slot in core.SLOTS}),
        cleanup=lambda:[],collect=lambda:matched_reconciliation() if reconciliation is None else reconciliation,
        audit=lambda:dict(valid=True,all_owned_actors_absent=True,sources_unchanged=True,
            checkpoint_unchanged=True,main_healthy=True,runtime_timeouts=0),
        release=lambda:[],publish=lambda value:None)
    return core.execute(runtime,launch.SETTINGS)


def capture_files(root,tap,*,inventory_change=None):
    retained={}
    raw=b'original synthetic server input\n'
    retained['server']=publish(root/'server-prefix-readonly.jsonl',raw)
    tap['input_sha256']['server']=hashlib.sha256(raw).hexdigest()
    for slot in core.SLOTS:
        for label,kind in [('Lua','lua'),('tap','tap'),('console','console')]:
            raw=('original synthetic '+label+' '+str(slot)+'\n').encode()
            retained[label+'-'+str(slot)]=publish(root/(label+'-'+str(slot)+'-prefix-readonly.jsonl'),raw)
            tap['input_sha256'][kind][str(slot)]=hashlib.sha256(raw).hexdigest()
    for name,(filename,sha) in adapter.ROM_INPUTS.items():
        raw=(adapter.GAME/'roms/robotron'/filename).read_bytes()
        assert len(raw)==4096 and hashlib.sha256(raw).hexdigest()==sha
        retained[name]=publish(root/('bound-'+name+'-input.bin'),raw)
    if inventory_change is not None:inventory_change(retained)
    return publish(root/'original-prefix-capture-inventory.json',
        (json.dumps(dict(retained=retained,errors=[],original_producer_modes_unchanged=True))+'\n').encode())


class Clock:
    def __init__(self):self.value=100
    def __call__(self):return self.value
    def sleep(self,seconds):self.value+=seconds


def owner():
    unit='robotron-startup-prefix-private-launch-CPU-fixture.service'
    return dict(unit=unit,invocation_id='a'*32,pid=900001,starttime_ticks=55,
        cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+unit,
        cgroup_identity=dict(device=33,inode=99),start_monotonic_us=101000000,observed_live=True)


def terminal(code='1',status='0',end=104):
    o=owner()
    return dict(Id=o['unit'],InvocationID=o['invocation_id'],NRestarts='0',MainPID='0',ExecMainPID=str(o['pid']),
        ExecMainStartTimestampMonotonic=str(o['start_monotonic_us']),ExecMainExitTimestampMonotonic=str(int(end*1e6)),
        ExecMainCode=code,ExecMainStatus=status,SubState='exited' if code=='1' else 'failed',
        Result='success' if code=='1' and status=='0' else 'exit-code' if code=='1' else 'signal' if code=='2' else 'core-dump')


def timer():return dict(unit=owner()['unit'].removesuffix('.service')+'.timer',invocation_id='b'*32)


def archives(fields=None,absent_timer=False):
    fields=terminal() if fields is None else fields;t=timer();out=[]
    for index,(unit,inv) in enumerate([(owner()['unit'],owner()['invocation_id']),(t['unit'],t['invocation_id'])]):
        for action in ('show','cat','journal'):
            argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+inv] if action=='journal' else ['systemctl','--user',action,unit]
            if action=='show':
                value=fields if index==0 else dict(Id=t['unit'],LoadState='not-found') if absent_timer else dict(Id=t['unit'],LoadState='loaded',InvocationID=t['invocation_id'],Unit=owner()['unit'])
                raw=('\n'.join(k+'='+str(v) for k,v in value.items())+'\n').encode()
            else:raw=b'fake archived original content\n'
            out.append(dict(argv=argv,exit=1 if index==1 and action=='cat' and absent_timer else 0,
                timed_out=False,stdout=dict(raw=raw),stderr=dict(raw=b'')))
    return out


def read(entry,as_json=False):return json.loads(entry['raw']) if as_json else entry['raw']


class Processes:
    def __init__(self):self.signals=[];self.closed=[];self.sent=threading.Event()
    def fields(self,unit):return dict(terminal(),MainPID='900001',ControlGroup=owner()['cgroup'])
    def start(self,pid):return 55
    def group(self,pid):return owner()['cgroup']
    def group_identity(self,group):return owner()['cgroup_identity']
    def members(self,group):return [900001]
    def open(self,pid):return pid+10
    def send(self,fd,signum):self.signals.append((fd,signum));self.sent.set()
    def close(self,fd):self.closed.append(fd)


class DormantThread:
    def __init__(self,**kwargs):self.kwargs=kwargs
    def start(self):pass
    def join(self,timeout):pass
    def is_alive(self):return False


class Capabilities:
    def __init__(self,clock):
        self.clock=clock;self.proc=Processes();self.events=[];self.failure=None;self.output=None;self.owner=None
        self.timer=timer();self.forbidden=set(range(1,194));self.polls=0;self.guard=None;self.mode='normal'
        def factory(**kwargs):
            self.guard=watchdog.Watchdog(**kwargs,clock=self.clock);return self.guard
        self.modules=dict(watchdog=types.SimpleNamespace(Watchdog=factory))
    def authenticate(self,entry):
        self.events.append('authenticate')
        if self.failure=='authenticate':raise ValueError('original predecessor still live')
        self.output=Path('/synthetic-owned-output')
    def sample(self):return dict(raw_API='synthetic-only',main192_verified=True)
    def publish(self,kind,value):
        self.events.append(kind)
        if self.failure=='publish' and kind=='original-launch-result':raise OSError('original publication failed')
        return {'synthetic_kind':kind}
    def schedule(self):
        self.events.append('schedule');self.clock.value=102
        if self.failure=='schedule':raise OSError('partial original scheduling failure')
    def observe_birth(self):
        self.events.append('observe_birth')
        if self.failure=='birth':raise ValueError('original live birth missed')
        self.owner=owner();return self.owner
    def permit(self,o):
        self.events.append('permit')
        if self.failure=='permit':raise ValueError('original live permit failed')
    def poll(self):
        self.events.append('poll');self.polls+=1
        if self.failure=='poll':raise ValueError('unit invocation replaced; no signal authorized')
        if self.mode=='blocked':
            self.clock.value=431 if self.polls==1 else 436
            self.guard.last_good=self.clock.value;self.guard.tick()
            if self.polls==1:return None
            return terminal('2','9',self.clock.value)
        self.clock.value+=1;self.guard.observe();self.guard.tick()
        return None if self.polls==1 else terminal(end=self.clock.value)
    def cgroup_absent(self):return self.polls>=2
    def archive(self,fields):
        self.events.append('archive')
        if self.failure=='archive':raise ValueError('one original archive missing')
        return launch.verify_archives(owner(),timer(),archives(fields),read)
    def release(self):
        self.events.append('release')
        if self.failure=='release':raise ValueError('unknown/replaced original release refused')
        return [dict(unit=owner()['unit'],confirmed_absent=True),dict(unit=timer()['unit'],confirmed_absent=True)]
    def audit(self):
        self.events.append('audit')
        if self.failure=='audit':raise ValueError('original source changed')
        return dict(valid=True)


class Tests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.caps=Capabilities(self.clock)
        self.temp=tempfile.TemporaryDirectory(prefix='startup-launch-CPU-');self.root=Path(self.temp.name)
        self.capability_patches=[patch.object(launch.subprocess,'Popen',side_effect=AssertionError('real Popen forbidden')),
            patch.object(adapter.socket,'socket',side_effect=AssertionError('real socket forbidden'))]
        for item in self.capability_patches:item.start()
    def tearDown(self):
        for item in reversed(self.capability_patches):item.stop()
        self.temp.cleanup()
    def execute(self):
        with patch.object(watchdog.threading,'Thread',DormantThread),patch.object(launch.signal,'signal',return_value=None):
            return launch.execute({'synthetic_plan':True},system=self.caps,clock=self.clock,sleep=self.clock.sleep)

    def test_default_entry_is_inert_without_plan_or_capability_reads(self):
        out=io.StringIO()
        with patch.object(launch,'load_plan',side_effect=AssertionError('no config read')), \
             patch.object(launch,'execute',side_effect=AssertionError('no scheduling')),redirect_stdout(out):
            self.assertEqual(launch.main([]),0)
        self.assertIn('PLAN_ONLY',out.getvalue())

    def test_complete_orchestration_uses_same_capability_instance_and_archive_before_release(self):
        result=self.execute();self.assertTrue(result['valid']);self.assertEqual(self.caps.events[0],'authenticate')
        self.assertLess(self.caps.events.index('main-sample'),self.caps.events.index('schedule'))
        self.assertLess(self.caps.events.index('observe_birth'),self.caps.events.index('permit'))
        self.assertLess(self.caps.events.index('archive'),self.caps.events.index('release'))
        self.assertLess(self.caps.events.index('release'),self.caps.events.index('audit'))
        self.assertTrue(result['watchdog']['coverage']['whole_unit_main_coverage'])
        self.assertFalse(result['quality_qualified']);self.assertFalse(result['real_ROM_start_proven'])

    def test_capability_instance_cannot_schedule_a_second_attempt(self):
        self.execute()
        with self.assertRaises(ValueError):self.execute()
        self.assertEqual(self.caps.events.count('schedule'),1)

    def test_refused_predecessor_cannot_start_witness_or_schedule(self):
        self.caps.failure='authenticate';result=self.execute()
        self.assertFalse(result['valid']);self.assertEqual(self.caps.events,['authenticate'])
        self.assertIsNone(self.caps.guard)

    def test_partial_scheduling_and_missed_birth_remain_invalid_without_retry_or_adoption(self):
        for phase in ['schedule','birth']:
            self.caps=Capabilities(self.clock);self.caps.failure=phase;result=self.execute()
            self.assertFalse(result['valid']);self.assertEqual(self.caps.events.count('schedule'),1)
            self.assertNotIn('permit',self.caps.events);self.assertNotIn('release',self.caps.events)
            self.assertTrue(result['unresolved_original_resources'])

    def test_failed_permit_still_retains_terminal_archives_before_owned_release(self):
        self.caps.failure='permit';result=self.execute()
        self.assertFalse(result['valid']);self.assertIn('archive',self.caps.events);self.assertIn('release',self.caps.events)
        self.assertIsNotNone(result['original_outcome']);self.assertIsNotNone(result['watchdog'])
        self.assertLess(self.caps.events.index('archive'),self.caps.events.index('release'))

    def test_failed_main_witness_stops_only_owned_probe_and_invalidates_result(self):
        calls=[0]
        def sample():
            calls[0]+=1
            if calls[0]>1:raise ValueError('main actor birth changed')
            return {'synthetic_initial_wire':True}
        self.caps.sample=sample;result=self.execute()
        self.assertFalse(result['valid']);self.assertTrue(self.caps.proc.signals)
        self.assertEqual(self.caps.proc.signals[0],(900011,signal.SIGTERM))
        self.assertTrue(any('main actor birth changed' in e for e in result['watchdog']['failures']))
        self.assertIn('archive',self.caps.events);self.assertIn('release',self.caps.events)

    def test_blocked_child_setup_is_deadlined_and_signal_exit_is_never_recast(self):
        self.caps.mode='blocked';result=self.execute()
        self.assertFalse(result['valid']);self.assertEqual(result['original_outcome']['exec_code'],2)
        self.assertEqual(result['original_outcome']['status'],9);self.assertFalse(result['original_outcome']['normal_exit'])
        self.assertEqual(self.caps.proc.signals,[(900011,signal.SIGTERM),(900011,signal.SIGKILL)])
        self.assertEqual(self.caps.events.count('archive'),1);self.assertEqual(self.caps.events.count('release'),1)
        self.assertFalse(result['watchdog']['valid'])

    def test_archive_failure_leaves_original_unreleased_and_never_retries_review(self):
        self.caps.failure='archive';result=self.execute()
        self.assertFalse(result['valid']);self.assertEqual(self.caps.events.count('archive'),1)
        self.assertNotIn('release',self.caps.events);self.assertTrue(result['unresolved_original_resources'])

    def test_release_or_audit_failure_cannot_be_reported_as_success(self):
        for phase in ['release','audit']:
            self.caps=Capabilities(self.clock);self.clock.value=100;self.caps.failure=phase;result=self.execute()
            self.assertFalse(result['valid']);self.assertIn('release refused' if phase=='release' else 'source changed',result['error'])
            self.assertEqual(self.caps.events.count('archive'),1);self.assertEqual(self.caps.events.count('release'),1)

    def test_publication_failure_invalidates_the_returned_result(self):
        self.caps.failure='publish';result=self.execute()
        self.assertFalse(result['valid']);self.assertIn('publication_error',result)

    def test_foreign_unit_during_observation_never_uses_numeric_pid_signal(self):
        self.caps.failure='poll';result=self.execute()
        self.assertFalse(result['valid']);self.assertEqual(self.caps.proc.signals,[])
        self.assertTrue(result['unresolved_original_resources']);self.assertNotIn('release',self.caps.events)

    def test_signal_aware_archives_preserve_normal_signal_and_core_dump_outcomes(self):
        for code,status in [('1','0'),('1','1'),('2','9'),('3','11')]:
            result=launch.verify_archives(owner(),timer(),archives(terminal(code,status)),read)
            self.assertEqual(result['original_outcome']['exec_code'],int(code))
            self.assertEqual(result['original_outcome']['status'],int(status))
            self.assertIs(result['original_outcome']['normal_exit'],code=='1')
            self.assertTrue(result['all_six_verified'])

    def test_archive_timer_gc_exception_requires_honest_absence_and_actual_cat_failure(self):
        good=archives(absent_timer=True);self.assertTrue(launch.verify_archives(owner(),timer(),good,read)['all_six_verified'])
        bad=archives();bad[4]['exit']=1
        with self.assertRaises(ValueError):launch.verify_archives(owner(),timer(),bad,read)
        bad=archives(absent_timer=True);bad[4]['exit']=0
        with self.assertRaises(ValueError):launch.verify_archives(owner(),timer(),bad,read)

    def test_archive_rejects_wrong_invocation_command_missing_descriptor_and_timeout(self):
        cases=[]
        bad=archives();bad[0]['stdout']['raw']=bad[0]['stdout']['raw'].replace(b'a'*32,b'c'*32);cases.append(bad)
        bad=archives();bad[5]['argv'][-1]='_SYSTEMD_INVOCATION_ID='+'c'*32;cases.append(bad)
        bad=archives();bad.pop();cases.append(bad)
        bad=archives();bad[2]['timed_out']=True;cases.append(bad)
        for rows in cases:
            with self.assertRaises(ValueError):launch.verify_archives(owner(),timer(),rows,read)

    def test_real_authentication_refuses_live_predecessor_before_any_launcher_process_query(self):
        system=launch.System();events=[]
        def predecessor(*args,**kwargs):events.append('closed_predecessor');raise ValueError('original campaign still live')
        modules=dict(runtime=types.SimpleNamespace(process_start=lambda *a:None),
            core=types.SimpleNamespace(verify_closed_predecessor=predecessor),closure=types.SimpleNamespace(archived_closure=object()),
            watchdog=types.SimpleNamespace(Processes=lambda:types.SimpleNamespace(fields=lambda *a:events.append('forbidden_query'))))
        with patch.object(launch,'load_plan',return_value=(object(),{},dict(predecessor={}),modules)):
            with self.assertRaises(ValueError):system.authenticate({'fake':True})
        self.assertEqual(events,['closed_predecessor']);self.assertIsNone(system.output)

    def test_child_entry_returns_nonzero_for_invalid_or_publication_failed_coordinator(self):
        for valid in [False,True]:
            calls=[];fake_runtime=types.SimpleNamespace(stop_event=threading.Event())
            def factory(job,entry):calls.append((job,entry));return fake_runtime
            def execute(runtime,settings,**kwargs):
                self.assertIs(runtime,fake_runtime);self.assertEqual(settings['max_wall_s'],300)
                value=coordinator_result();value['valid']=valid;return value
            modules=dict(runtime=types.SimpleNamespace(Runtime=factory),core=types.SimpleNamespace(execute=execute,configuration=core.configuration,matched=core.matched,runtime_audit=core.runtime_audit))
            with patch.object(launch,'load_plan',return_value=(object(),dict(job={'original':1}),{'fixture':True},modules)),redirect_stdout(io.StringIO()):
                self.assertEqual(launch.child({'plan':True}),0 if valid else 1)
            self.assertEqual(calls,[({'fixture':True},{'original':1})])

    def test_real_schedule_constructs_only_exact_bounded_private_unit_and_timer(self):
        system=launch.System();system.output=self.root;system.plan=dict(probe_unit=owner()['unit'],sources=dict(launcher=dict(sha256='c'*64)))
        system.entry=dict(path=str(self.root/'plan.json'),sha256='d'*64);system.job=dict(affinity=[0,1])
        system.proc=types.SimpleNamespace(fields=lambda unit:dict(Id=unit,LoadState='not-found'))
        system.reader=types.SimpleNamespace(read_pin=lambda p,as_json=False:p['raw']);records=[];published=[]
        system.publish=lambda kind,value:published.append((kind,value))
        def command(label,argv,timeout=10):
            records.append((label,argv))
            raw=('Id='+timer()['unit']+'\nLoadState=loaded\nUnit='+owner()['unit']+'\nInvocationID='+'b'*32+'\n').encode() if label=='launch-timer-show' else ('[Timer]\nUnit='+owner()['unit']+'\n').encode()
            return dict(exit=0,timed_out=False,stdout=dict(raw=raw),stderr=dict(raw=b''))
        system.command=command;system.schedule()
        argv=records[0][1]
        for value in ['--property=CPUQuota=1600%','--property=MemoryMax=32G','--property=RuntimeMaxSec=345','--property=SendSIGKILL=no','--property=CPUAffinity=0 1']:
            self.assertIn(value,argv)
        self.assertIn('--child',argv);self.assertEqual(system.timer,timer())
        with self.assertRaises(ValueError):system.schedule()
        self.assertEqual(len(records),3)

    def test_real_permit_binds_actual_job_and_both_original_owners_exclusively(self):
        system=launch.System();system.owner=owner();system.timer=timer();system.proc=Processes()
        system.modules=dict(watchdog=watchdog);system.guard_owner=dict(pid=999999,starttime_ticks=88,invocation_id='f'*32)
        system.plan=dict(job=dict(sha256='d'*64));path=self.root/'original-permit.json';system.job=dict(external_guard_permit_path=str(path))
        system.reader=types.SimpleNamespace(pin=lambda p:dict(path=str(p)));system.publish=lambda *a:None
        system.permit(owner());value=json.loads(path.read_bytes())
        self.assertEqual(value['job_sha256'],'d'*64);self.assertEqual(value['probe_owner'],owner())
        self.assertEqual(value['guard_owner'],system.guard_owner);self.assertEqual(path.stat().st_mode&0o777,0o444)
        with self.assertRaises(FileExistsError):system.permit(owner())

    def test_real_command_records_timeout_without_assuming_carrier_failure_or_retry(self):
        system=launch.System();system.output=self.root
        def pin(p):
            raw=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest())
        system.reader=types.SimpleNamespace(pin=pin)
        with patch.object(launch.subprocess,'run',side_effect=subprocess.TimeoutExpired(['fake'],1,output=b'partial',stderr=b'unknown outcome')) as run:
            result=system.command('carrier',['fake'],timeout=1)
        run.assert_called_once();self.assertIsNone(result['exit']);self.assertTrue(result['timed_out'])
        self.assertEqual(Path(result['stdout']['path']).read_bytes(),b'partial')
        self.assertEqual(Path(result['stderr']['path']).read_bytes(),b'unknown outcome')

    def release_system(self,*,foreign_timer=False,timer_race=False):
        system=launch.System();system.owner=owner();system.timer=timer();system.archives=archives(terminal('2','9'))
        system.reader=types.SimpleNamespace(read_pin=read);system.publish=lambda *a:None;events=[]
        def command(label,argv,timeout=10):
            events.append((label,argv));unit=argv[-1];code=0;err=b''
            if 'before-show' in label:
                value=dict(Id=unit,LoadState='loaded',InvocationID=('c' if foreign_timer else 'b')*32,Unit=owner()['unit']) if unit.endswith('.timer') else dict(terminal('2','9'),LoadState='loaded',ActiveState='failed')
            elif 'after-show' in label:
                value=dict(Id=unit,LoadState='not-found') if unit.endswith('.timer') else dict(terminal('2','9'),LoadState='loaded',ActiveState='failed')
            elif 'final-show' in label:value=dict(Id=unit,LoadState='not-found')
            else:
                value={}
                if timer_race and label=='release-timer-stop':code=5;err=('Unit '+unit+' not loaded.\n').encode()
            return dict(argv=argv,exit=code,timed_out=False,stdout=dict(raw=('\n'.join(k+'='+str(v) for k,v in value.items())+'\n').encode()),stderr=dict(raw=err))
        system.command=command;return system,events

    def test_real_release_preserves_signal_exit_and_resets_only_verified_failed_service(self):
        system,events=self.release_system();result=system.release()
        self.assertEqual({x['unit'] for x in result},{owner()['unit'],timer()['unit']})
        self.assertTrue(all(x['confirmed_absent'] for x in result))
        self.assertEqual(sum(label=='release-service-reset' for label,argv in events),1)
        self.assertEqual([argv for label,argv in events if label.endswith('-stop')],
            [['systemctl','--user','stop',timer()['unit']],['systemctl','--user','stop',owner()['unit']]])

    def test_real_release_accepts_exact_timer_gc_stop5_and_refuses_foreign_timer(self):
        system,events=self.release_system(timer_race=True);result=system.release()
        self.assertEqual(result[0]['stop']['exit'],5);self.assertTrue(result[0]['confirmed_absent'])
        system,events=self.release_system(foreign_timer=True)
        with self.assertRaises(ValueError):system.release()
        self.assertFalse(any(label.endswith('-stop') for label,argv in events))

    def test_real_release_revalidates_all_six_archives_before_any_unit_action(self):
        system,events=self.release_system();system.archives.pop()
        with self.assertRaises(ValueError):system.release()
        self.assertEqual(events,[])

    def test_real_birth_requires_post_env_child_argv_executable_and_original_affinity(self):
        system=launch.System();system.plan=dict(probe_unit=owner()['unit']);system.proc=Processes()
        system.job=dict(affinity=[0,1]);system.forbidden=set(range(1,194));system.modules=dict(watchdog=watchdog)
        python=self.root/'python';python.write_bytes(b'fake executable')
        system.child_argv=[str(python),'--child'];proc=self.root/'proc/900001';proc.mkdir(parents=True)
        (proc/'cmdline').write_bytes(b'/usr/bin/env\0');(proc/'exe').symlink_to(python)
        actual_path=Path
        def mapped_path(*args):
            return actual_path(self.root/'proc',*args[1:]) if args and args[0]=='/proc' else actual_path(*args)
        with patch.object(launch,'Path',side_effect=mapped_path),patch.object(launch.os,'sched_getaffinity',return_value={0,1}):
            self.assertIsNone(system.observe_birth());self.assertIsNone(system.owner)
            (proc/'cmdline').write_bytes(b'\0'.join(os.fsencode(x) for x in system.child_argv)+b'\0')
            self.assertEqual(system.observe_birth(),owner())
        self.assertEqual(system.owner,owner())

    def test_plan_schema_refuses_wrong_units_sources_affinity_and_output_scope(self):
        prep=launch.RUN/'CPU-shape-fixture'
        plan=dict(schema='robotron-authenticated-private-startup-launch-v2',job=dict(path=str(prep/'job.json')),
            output=str(prep/'guard-execution'),probe_unit=owner()['unit'],guard_unit='robotron-startup-prefix-guard-CPU-fixture.service',
            guard_affinity=[0,1],sources={**{k:dict(sha256=v) for k,v in launch.EXPECTED.items()},
                'launcher':dict(path=str(HERE/'startup_probe_launch_v4.py'))})
        self.assertEqual(launch.checked_plan(plan),plan)
        changes=[('probe_unit','robotron-managed-trainer.service'),('guard_unit',owner()['unit']),
            ('guard_affinity',[True]),('output',str(prep/'foreign-output'))]
        for key,value in changes:
            bad=copy.deepcopy(plan);bad[key]=value
            with self.assertRaises(ValueError):launch.checked_plan(bad)
        bad=copy.deepcopy(plan);bad['sources']['runtime']['sha256']='0'*64
        with self.assertRaises(ValueError):launch.checked_plan(bad)

    def test_real_audit_consumes_actual_coordinator_result_and_preserves_console_producer_modes(self):
        child=self.root/'child';child.mkdir();guard=self.root/'guard';guard.mkdir()
        reconciliation=matched_reconciliation()
        capture_files(child,reconciliation['tap_provenance'])
        audit=dict(valid=True,all_owned_actors_absent=True,sources_unchanged=True,checkpoint_unchanged=True,main_healthy=True,runtime_timeouts=0)
        runtime=types.SimpleNamespace(prepare=lambda:None,start=lambda:None,check=lambda:None,
            snapshot=lambda:dict(closed=True,failed=False,faults=0,rows=65536,pending=0,
                counts={s:4096 for s in core.SLOTS},epochs={s:1 for s in core.SLOTS}),
            cleanup=lambda:[],collect=lambda:reconciliation,audit=lambda:audit,release=lambda:[],publish=lambda *a:None)
        result=core.execute(runtime,launch.SETTINGS);self.assertTrue(result['valid'])
        path=child/'result.json';path.write_text(json.dumps(result));path.chmod(0o444)
        def pin(p):return file_pin(p)
        def read_pin(entry,as_json=True):
            if 'path' not in entry:return {}
            raw=Path(entry['path']).read_bytes();return json.loads(raw) if as_json else raw
        system=launch.System();system.reader=types.SimpleNamespace(pin=pin,read_pin=read_pin)
        system.output=guard;system.job=dict(output=str(child));system.plan=dict(sources={},job={});system.entry={}
        system.main={};system.monitor=types.SimpleNamespace(verify_inputs=lambda *a:None)
        system.modules=dict(core=core,runtime=adapter,main_guard=types.SimpleNamespace(owner_and_files=lambda *a:None))
        system.cgroup_absent=lambda:True
        before={}
        for name in ['child-stdout.txt','child-stderr.txt']:
            p=guard/name;p.write_bytes(b'original console\n');before[name]=(p.read_bytes(),p.stat().st_mode&0o777)
        actual=system.audit();self.assertTrue(actual['valid'])
        for name,(raw,mode) in before.items():
            self.assertEqual((guard/name).read_bytes(),raw);self.assertEqual((guard/name).stat().st_mode&0o777,mode)
            self.assertEqual((guard/(name+'.readonly')).stat().st_mode&0o777,0o444)

    def test_complete_tap_gate_accepts_full_content_but_does_not_certify_real_exit_or_start(self):
        result=coordinator_result();content=launch.checked_child_result(result,core)
        self.assertEqual((content['actor_slots'],content['matched_inputs']),(16,65536))
        self.assertFalse(content['actual_unit_outcome_verified']);self.assertFalse(content['real_ROM_start_proven'])

    def test_raw_only125_result_and_partial_tap_cannot_pass_new_gate(self):
        for change in [lambda raw:raw.pop('tap_provenance'),
                       lambda raw:raw['tap_provenance'].update(matched_inputs=4096),
                       lambda raw:raw['tap_provenance'].update(actor_slots=15),
                       lambda raw:raw['tap_provenance']['slots'].pop('4111')]:
            result=coordinator_result();change(result['reconciliation'])
            with self.assertRaises(ValueError):launch.checked_child_result(result,core)

    def test_each_slot_requires_complete_inputs_and_loaded_span_with_narrow_certification_scope(self):
        changes=[dict(inputs=4095),dict(inputs=True),dict(captured_loaded_span_matches_pinned_ROM=False),
                 dict(full_loaded_ROM_image_verified=True),dict(first_start_certified=True),
                 dict(admission_clock_ordering_verified=True),dict(status_writes=513),
                 dict(status_writes=True),dict(common_restart_write_observations=1)]
        for change in changes:
            result=coordinator_result();result['reconciliation']['tap_provenance']['slots']['4096'].update(change)
            with self.assertRaises(ValueError):launch.checked_child_result(result,core)

    def test_nested_runtime_acceptance_quality_speed_or_raw_mismatch_cannot_be_claimed(self):
        for key in ['original_runtime_outcome_verified','raw_ROM_start_acceptance_proven',
                    'start_eligibility_changed','protocol_selected','quality_qualified','learning_speed_gain_verified']:
            result=coordinator_result();result['reconciliation']['tap_provenance'][key]=True
            with self.assertRaises(ValueError):launch.checked_child_result(result,core)
        result=coordinator_result();result['reconciliation']['tap_provenance']['raw_prefix_reconciliation']['accepted_frames']=1
        with self.assertRaises(ValueError):launch.checked_child_result(result,core)
        result=coordinator_result();slot=result['reconciliation']['tap_provenance']['slots']['4096']
        slot.update(status_writes=1,START1_write_observations=[dict(real_ROM_start_acceptance_proven=True)])
        with self.assertRaises(ValueError):launch.checked_child_result(result,core)

    def test_digest_inventory_must_cover_exact_original_inputs_and_slots(self):
        changes=[lambda h:h.pop('console'),lambda h:h['tap'].pop('4096'),
                 lambda h:h['lua'].update({'9999':'a'*64}),lambda h:h.update(server='bad')]
        for change in changes:
            result=coordinator_result();change(result['reconciliation']['tap_provenance']['input_sha256'])
            with self.assertRaises(ValueError):launch.checked_child_result(result,core)

    def test_coordinator_error_attempt_capture_settings_or_quality_flags_invalidate_content(self):
        changes=[dict(valid=False),dict(capture_complete=False),dict(attempts=2),dict(attempts=True),
                 dict(errors=['failed capture']),dict(retried=True),dict(scientific_review_rerun=True),
                 dict(quality_qualified=True),dict(schema='old-or-unknown')]
        for change in changes:
            result=coordinator_result();result.update(change)
            with self.assertRaises(ValueError):launch.checked_child_result(result,core)
        result=coordinator_result();result['settings']['frames']=16
        with self.assertRaises(ValueError):launch.checked_child_result(result,core)

    def capture_system(self,name,change=None):
        root=self.root/name;root.mkdir()
        raw=matched_reconciliation();capture_files(root,raw['tap_provenance'],inventory_change=change)
        system=launch.System();system.job=dict(output=str(root));system.modules=dict(runtime=adapter)
        system.reader=types.SimpleNamespace(pin=file_pin,read_pin=checked_read)
        return system,raw['tap_provenance']

    def test_capture_audit_rejoins_all51_fullpins_and_exact_input_byte_digests(self):
        system,tap=self.capture_system('capture-valid')
        result=system.verify_capture_inputs(tap)
        self.assertEqual(result['original_input_count'],51)
        self.assertTrue(result['all_fullpins_and_input_digests_verified'])
        self.assertTrue(result['producer_modes_unchanged'])

    def test_capture_audit_refuses_missing_wrong_hash_path_or_weakened_full_identity(self):
        changes=[lambda d:d.pop('tap-4096'),lambda d:d['console-4096'].update(sha256='f'*64),
                 lambda d:d['Lua-4096'].update(path=str(self.root/'foreign-original')),
                 lambda d:d['tap-4096']['identity'].pop('ctime_ns')]
        for number,change in enumerate(changes):
            system,tap=self.capture_system('capture-bad-'+str(number),change)
            with self.assertRaises(ValueError):system.verify_capture_inputs(tap)

    def test_capture_audit_detects_changed_read_bytes_without_modifying_sealed_originals(self):
        system,tap=self.capture_system('capture-byte-mismatch')
        def altered(entry,as_json=True):
            raw=checked_read(entry,as_json=as_json)
            return b'wrong captured bytes' if str(entry.get('path','')).endswith('tap-4096-prefix-readonly.jsonl') else raw
        system.reader.read_pin=altered
        with self.assertRaises(ValueError):system.verify_capture_inputs(tap)

    def test_capture_audit_missing_original_does_not_accept_other_matching_records(self):
        system,tap=self.capture_system('capture-missing')
        def missing(entry,as_json=True):
            if str(entry.get('path','')).endswith('console-4100-prefix-readonly.jsonl'):
                raise FileNotFoundError('injected original capture missing')
            return checked_read(entry,as_json=as_json)
        system.reader.read_pin=missing
        with self.assertRaises(FileNotFoundError):system.verify_capture_inputs(tap)

    def test_child_extra_gate_returns_nonzero_if_coordinator_reports_raw_only_success(self):
        result=coordinator_result();result['reconciliation'].pop('tap_provenance')
        runtime=types.SimpleNamespace(stop_event=threading.Event())
        modules=dict(runtime=types.SimpleNamespace(Runtime=lambda *args:runtime),
            core=types.SimpleNamespace(execute=lambda *a,**k:result,configuration=core.configuration,
                matched=core.matched,runtime_audit=core.runtime_audit))
        output=io.StringIO()
        with patch.object(launch,'load_plan',return_value=(None,dict(job={}),{},modules)),redirect_stdout(output):
            self.assertEqual(launch.child({}),1)
        self.assertFalse(json.loads(output.getvalue())['valid'])

    def test_real_load_plan_binds_and_child_constructs_the_same_actual_v2_runtime_factory(self):
        special=dict(reader=launch.READER,
            main_guard=adapter.GAME/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
            closure=adapter.GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
            raw_api=adapter.GAME/'tools/eval_capacity_proposal/raw_api_witness_v1.py')
        names=dict(runtime='startup_probe_runtime_v4.py',core='startup_probe_core_v2.py',
            watchdog='startup_probe_watchdog_v1.py',tap_join='reconcile_acceptance_tap_v2.py',
            raw_matcher='startup_server_prefix_v2.py')
        sources={key:file_pin(special[key] if key in special else HERE/names[key]) for key in launch.EXPECTED}
        sources['launcher']=file_pin(HERE/'startup_probe_launch_v4.py')
        future=launch.RUN/('CPU-UNUSED-output-'+self.root.name)
        self.assertFalse(future.exists())
        job=dict(schema='robotron-private-startup-runtime-job-v2',output=str(future),
            package=dict(sha256=adapter.PACKAGE_SHA),checkpoint={},predecessor={},main={},
            binary_inputs=[dict(path='/usr/games/mame')]+[dict(path=str(adapter.GAME/'roms/robotron'/filename),
                sha256=sha,bytes=4096) for filename,sha in adapter.ROM_INPUTS.values()],
            boot_assets=str(adapter.GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1'),boot_identity='a'*64,
            sessions={str(slot):format(slot,'032x') for slot in core.SLOTS},affinity=[0,1],
            lease=dict(path='/dev/shm/robotron-snapshot-smoke-gpu0.lock',device=32,inode=757),
            external_guard_permit_path=str(self.root/'unused-permit.json'),
            sources={key:sources[key] for key in set(adapter.EXPECTED)|{'runtime'}})
        job_pin=publish(self.root/'CPU-job-shape.json',(json.dumps(job)+'\n').encode())
        plan=dict(schema='robotron-authenticated-private-startup-launch-v2',job=job_pin,
            output=str(self.root/'guard-execution'),probe_unit=owner()['unit'],
            guard_unit='robotron-startup-prefix-guard-CPU-real-loader.service',guard_affinity=[0,1],sources=sources)
        entry=publish(self.root/'CPU-plan-shape.json',(json.dumps(plan)+'\n').encode())
        reader,loaded_plan,loaded_job,modules=launch.load_plan(entry)
        self.assertEqual(Path(modules['runtime'].__file__).resolve(),HERE/'startup_probe_runtime_v4.py')
        self.assertEqual(modules['runtime'].EXPECTED['tap_join'],launch.EXPECTED['tap_join'])
        self.assertEqual(modules['runtime'].PACKAGE_SHA,adapter.PACKAGE_SHA)
        calls=[]
        def execute(runtime,settings,**kwargs):
            self.assertIs(type(runtime),modules['runtime'].Runtime)
            self.assertIs(type(runtime.system),modules['runtime'].System)
            self.assertIs(runtime.job,loaded_job);self.assertEqual(runtime.job_entry,job_pin)
            self.assertFalse(runtime.owns_output);calls.append(runtime)
            return coordinator_result()
        with patch.object(launch,'load_plan',return_value=(reader,loaded_plan,loaded_job,modules)), \
                patch.object(modules['core'],'execute',side_effect=execute),redirect_stdout(io.StringIO()):
            self.assertEqual(launch.child(entry),0)
        self.assertEqual(len(calls),1);self.assertFalse(future.exists())

    def test_v2_plan_refuses_old_runtime_or_missing_tap_checker_dependencies(self):
        prep=launch.RUN/'CPU-v2-negative-shape'
        plan=dict(schema='robotron-authenticated-private-startup-launch-v2',job=dict(path=str(prep/'job.json')),
            output=str(prep/'guard-execution'),probe_unit=owner()['unit'],
            guard_unit='robotron-startup-prefix-guard-CPU-fixture.service',guard_affinity=[0,1],
            sources={**{key:dict(sha256=sha) for key,sha in launch.EXPECTED.items()},
                     'launcher':dict(path=str(HERE/'startup_probe_launch_v4.py'))})
        variants=[]
        bad=copy.deepcopy(plan);bad['schema']='robotron-authenticated-private-startup-launch-v1';variants.append(bad)
        bad=copy.deepcopy(plan);bad['sources']['runtime']['sha256']='071ff5d4fa21fbd341e6aa9416527e3e24e035bc4b490860f31c05ab61353d4e';variants.append(bad)
        bad=copy.deepcopy(plan);bad['sources'].pop('tap_join');variants.append(bad)
        bad=copy.deepcopy(plan);bad['sources'].pop('raw_matcher');variants.append(bad)
        for bad in variants:
            with self.assertRaises(ValueError):launch.checked_plan(bad)

    def test_valid_content_cannot_rescue_nonzero_normal_or_signal_unit_exit(self):
        for code,status in [('1','1'),('2','9'),('3','11')]:
            self.clock=Clock();self.caps=Capabilities(self.clock)
            def poll(code=code,status=status):
                self.caps.events.append('poll');self.caps.polls+=1;self.clock.value=104
                self.caps.guard.observe();self.caps.guard.tick()
                return terminal(code,status,104)
            self.caps.poll=poll
            self.caps.cgroup_absent=lambda:True
            result=self.execute()
            self.assertFalse(result['valid']);self.assertEqual(result['original_outcome']['exec_code'],int(code))
            self.assertEqual(result['original_outcome']['status'],int(status))


if __name__=='__main__':
    time.sleep(2)
    with patch.object(launch.subprocess,'run',side_effect=AssertionError('real process/unit operation forbidden')), \
         patch.object(launch.os,'pidfd_open',side_effect=AssertionError('real process handle forbidden')), \
         patch.object(launch.signal,'pidfd_send_signal',side_effect=AssertionError('real signal forbidden')):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-authenticated-startup-launch-CPU-contracts-v2',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual launcher orchestration with the same fake capability object and actual watchdog/signal-aware archive code; real schedule, permit, timeout and refused-predecessor paths with explicit capability substitution. No real scheduling, query, signal, model or GPU.',
        real_runtime_validated=False,real_probe_selected=False,production_changed=False,
        quality_gain_verified=False,learning_speed_gain_verified=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
