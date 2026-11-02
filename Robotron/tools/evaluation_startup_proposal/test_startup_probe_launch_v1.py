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
import startup_probe_launch_v1 as launch
import startup_probe_watchdog_v1 as watchdog
import startup_probe_core_v1 as core
assert hashlib.sha256((HERE/'startup_probe_watchdog_v1.py').read_bytes()).hexdigest()==launch.EXPECTED['watchdog']
assert hashlib.sha256((HERE/'startup_probe_core_v1.py').read_bytes()).hexdigest()==launch.EXPECTED['core']


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
    def tearDown(self):self.temp.cleanup()
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
                return dict(status='CPU-fixture',valid=valid)
            modules=dict(runtime=types.SimpleNamespace(Runtime=factory),core=types.SimpleNamespace(execute=execute))
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
        plan=dict(schema='robotron-authenticated-private-startup-launch-v1',job=dict(path=str(prep/'job.json')),
            output=str(prep/'guard-execution'),probe_unit=owner()['unit'],guard_unit='robotron-startup-prefix-guard-CPU-fixture.service',
            guard_affinity=[0,1],sources={**{k:dict(sha256=v) for k,v in launch.EXPECTED.items()},
                'launcher':dict(path=str(HERE/'startup_probe_launch_v1.py'))})
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
        reconciliation=dict(status='MATCHED_DIAGNOSTIC_PREFIX_ONLY',matched_frames=65536,accepted_frames=65536,
            rejected_frames=0,actor_slots=16,raw_ROM_start_acceptance_proven=False,start_eligibility_changed=False,
            protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False)
        audit=dict(valid=True,all_owned_actors_absent=True,sources_unchanged=True,checkpoint_unchanged=True,main_healthy=True,runtime_timeouts=0)
        runtime=types.SimpleNamespace(prepare=lambda:None,start=lambda:None,check=lambda:None,
            snapshot=lambda:dict(closed=True,failed=False,faults=0,rows=65536,pending=0,
                counts={s:4096 for s in core.SLOTS},epochs={s:1 for s in core.SLOTS}),
            cleanup=lambda:[],collect=lambda:reconciliation,audit=lambda:audit,release=lambda:[],publish=lambda *a:None)
        result=core.execute(runtime,launch.SETTINGS);self.assertTrue(result['valid'])
        path=child/'result.json';path.write_text(json.dumps(result));path.chmod(0o444)
        def pin(p):
            p=Path(p);return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        def read_pin(entry,as_json=True):
            if 'path' not in entry:return {}
            raw=Path(entry['path']).read_bytes();return json.loads(raw) if as_json else raw
        system=launch.System();system.reader=types.SimpleNamespace(pin=pin,read_pin=read_pin)
        system.output=guard;system.job=dict(output=str(child));system.plan=dict(sources={},job={});system.entry={}
        system.main={};system.monitor=types.SimpleNamespace(verify_inputs=lambda *a:None)
        system.modules=dict(core=core,main_guard=types.SimpleNamespace(owner_and_files=lambda *a:None))
        system.cgroup_absent=lambda:True
        before={}
        for name in ['child-stdout.txt','child-stderr.txt']:
            p=guard/name;p.write_bytes(b'original console\n');before[name]=(p.read_bytes(),p.stat().st_mode&0o777)
        actual=system.audit();self.assertTrue(actual['valid'])
        for name,(raw,mode) in before.items():
            self.assertEqual((guard/name).read_bytes(),raw);self.assertEqual((guard/name).stat().st_mode&0o777,mode)
            self.assertEqual((guard/(name+'.readonly')).stat().st_mode&0o777,0o444)


if __name__=='__main__':
    time.sleep(2)
    with patch.object(launch.subprocess,'run',side_effect=AssertionError('real process/unit operation forbidden')), \
         patch.object(launch.os,'pidfd_open',side_effect=AssertionError('real process handle forbidden')), \
         patch.object(launch.signal,'pidfd_send_signal',side_effect=AssertionError('real signal forbidden')):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-authenticated-startup-launch-CPU-contracts-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual launcher orchestration with the same fake capability object and actual watchdog/signal-aware archive code; real schedule, permit, timeout and refused-predecessor paths with explicit capability substitution. No real scheduling, query, signal, model or GPU.',
        real_runtime_validated=False,real_probe_selected=False,production_changed=False,
        quality_gain_verified=False,learning_speed_gain_verified=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
