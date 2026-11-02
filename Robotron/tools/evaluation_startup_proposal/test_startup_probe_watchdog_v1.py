"""CPU watchdog contracts; the actual process-capability instance is replaced."""
import ast
import copy
import io
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import startup_probe_watchdog_v1 as w

FORBIDDEN=set(range(1,194))


def owner():
    unit='robotron-startup-prefix-private-CPU-fixture.service'
    return dict(unit=unit,invocation_id='a'*32,pid=900001,starttime_ticks=55,
        cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+unit,
        cgroup_identity=dict(device=33,inode=99),start_monotonic_us=101000000,observed_live=True)


class Clock:
    def __init__(self,value=100):self.value=value
    def __call__(self):return self.value


class Processes:
    def __init__(self):
        self.owner=owner();self.ids=[900001,900002];self.births={900001:55,900002:66}
        self.groups={pid:self.owner['cgroup'] for pid in self.ids}
        self.identity=dict(self.owner['cgroup_identity']);self.opened=[];self.closed=[];self.signals=[]
        self.fields_count=0;self.after_open=None;self.on_fields=None;self.sent=threading.Event()
        self.live=dict(Id=self.owner['unit'],InvocationID='a'*32,NRestarts='0',
            ControlGroup=self.owner['cgroup'],ExecMainPID='900001',MainPID='900001',
            ExecMainStartTimestampMonotonic='101000000')
    def fields(self,unit):
        self.fields_count+=1
        assert unit==self.owner['unit']
        if self.on_fields:self.on_fields(self.fields_count)
        return dict(self.live)
    def start(self,pid):return self.births.get(pid)
    def group(self,pid):return self.groups[pid]
    def group_identity(self,group):assert group==self.owner['cgroup'];return dict(self.identity)
    def members(self,group):assert group==self.owner['cgroup'];return list(self.ids)
    def open(self,pid):
        self.opened.append(pid)
        if self.after_open:self.after_open(pid)
        return pid+10
    def close(self,fd):self.closed.append(fd)
    def send(self,fd,signum):self.signals.append((fd,signum));self.sent.set()


class DormantThread:
    def __init__(self,**kwargs):self.kwargs=kwargs;self.started=False
    def start(self):self.started=True
    def join(self,timeout):pass
    def is_alive(self):return False


class Tests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.proc=Processes();self.published=[]
        self.guard=w.Watchdog(sample=lambda:dict(raw_API='fake-bound-wire',main192=True),
            publish=lambda kind,value:self.published.append((kind,copy.deepcopy(value))),
            forbidden=FORBIDDEN,processes=self.proc,clock=self.clock)

    def armed(self):
        with patch.object(w.threading,'Thread',DormantThread):self.guard.start()
        self.clock.value=102;self.guard.bind(owner());return self.guard

    def terminal(self,code='1',status='0',end=110):
        return dict(self.proc.live,MainPID='0',ExecMainCode=code,ExecMainStatus=status,
            SubState='exited' if code=='1' else 'failed',ExecMainExitTimestampMonotonic=str(int(end*1e6)))

    def test_constructor_and_unstarted_tick_make_no_process_query_or_signal(self):
        self.guard.tick();self.assertEqual(self.proc.fields_count,0)
        self.assertEqual(self.proc.signals,[]);self.assertEqual(self.published,[])

    def test_start_brackets_scheduling_with_first_healthy_sample(self):
        with patch.object(w.threading,'Thread',DormantThread):self.guard.start()
        self.assertEqual(self.published[0][0],'main-sample')
        self.assertTrue(self.guard.witness_thread.started);self.assertTrue(self.guard.deadline_thread.started)
        self.assertIsNone(self.guard.owner)
        with self.assertRaises(ValueError):self.guard.start()

    def test_failed_initial_witness_does_not_start_threads(self):
        self.guard.sample=lambda:None
        with patch.object(w.threading,'Thread',side_effect=AssertionError('no worker allowed')):
            with self.assertRaises(ValueError):self.guard.start()
        self.assertIsNone(self.guard.witness_thread);self.assertIsNone(self.guard.deadline_thread)
        self.assertTrue(self.guard.failures);self.assertEqual(self.proc.signals,[])

    def test_bind_requires_live_birth_and_is_single_attempt(self):
        g=self.armed();self.assertEqual(g.owner,owner())
        with self.assertRaises(ValueError):g.bind(owner())
        self.assertEqual(self.proc.signals,[])

    def test_binding_accepts_post_start_witness_with_earlier_bracket(self):
        with patch.object(w.threading,'Thread',DormantThread):self.guard.start()
        self.clock.value=102;self.guard.observe();self.clock.value=103
        self.guard.bind(owner());self.assertEqual(self.guard.owner,owner())

    def test_stale_birth_outside_permit_window_is_refused(self):
        with patch.object(w.threading,'Thread',DormantThread):self.guard.start()
        self.clock.value=120;self.guard.observe()
        with self.assertRaises(ValueError):self.guard.bind(owner())
        self.assertIsNone(self.guard.owner);self.assertEqual(self.proc.signals,[])

    def test_deadline_enforces_term_then_kill_once_without_retry(self):
        g=self.armed();self.clock.value=431;g.last_good=431;g.tick()
        self.assertEqual(self.proc.signals,[(900011,signal.SIGTERM)])
        self.clock.value=435;g.last_good=435;g.tick();self.assertEqual(len(self.proc.signals),1)
        self.clock.value=436;g.last_good=436;g.tick();g.tick()
        self.assertEqual(self.proc.signals,[(900011,signal.SIGTERM),(900011,signal.SIGKILL),(900012,signal.SIGKILL)])
        self.assertEqual(self.proc.closed,[900011,900011,900012]);self.assertEqual(len(g.actions),2)
        self.assertTrue(any('330s' in x for x in g.failures))

    def test_main_coverage_expiry_stops_probe_and_cannot_be_rescued(self):
        g=self.armed();self.clock.value=111;g.tick()
        self.assertTrue(any('coverage expired' in x for x in g.failures))
        self.assertEqual(self.proc.signals[0][1],signal.SIGTERM)
        g.observe();self.assertTrue(g.failures)

    def test_delayed_observation_invalidates_even_if_evidence_is_healthy(self):
        def sample():self.clock.value+=7;return {'healthy':True}
        self.guard.sample=sample;self.assertIsNone(self.guard.observe())
        self.assertIsNone(self.guard.last_good);self.assertEqual(self.guard.samples,[])

    def test_main_observation_failure_and_interruption_are_retained(self):
        g=self.armed()
        def sample():raise RuntimeError('main trainer changed')
        g.sample=sample;self.assertIsNone(g.observe());g.interrupt('SIGTERM');g.tick()
        self.assertTrue(any('main trainer changed' in x for x in g.failures))
        self.assertTrue(any('SIGTERM' in x for x in g.failures));self.assertEqual(len(self.proc.signals),1)

    def test_blocked_witness_cannot_block_independent_deadline_worker(self):
        blocked=threading.Event();release=threading.Event();calls=[0]
        def sample():
            calls[0]+=1
            if calls[0]>1:blocked.set();release.wait(3)
            return {'fake_wire':calls[0]}
        self.guard.sample=sample
        with patch.object(w,'SAMPLE_S',0.005),patch.object(w,'POLL_S',0.005):
            try:
                self.guard.start();self.clock.value=102;self.guard.bind(owner())
                self.assertTrue(blocked.wait(1),'second witness never entered its controlled block')
                self.clock.value=500;self.guard.wake.set()
                self.assertTrue(self.proc.sent.wait(1),'deadline worker was blocked by main witness')
                self.assertEqual(self.proc.signals[0][1],signal.SIGTERM)
            finally:
                self.guard.stop_event.set();self.guard.wake.set();release.set()
                for thread in (self.guard.witness_thread,self.guard.deadline_thread):
                    if thread is not None:thread.join(2);self.assertFalse(thread.is_alive())

    def test_signal_refuses_reused_main_pid(self):
        self.proc.births[900001]=77
        with self.assertRaises(ValueError):w.signal_owned(owner(),FORBIDDEN,self.proc,signal.SIGTERM)
        self.assertEqual(self.proc.signals,[])

    def test_signal_refuses_foreign_or_replaced_unit_and_cgroup(self):
        for key,value in [('InvocationID','b'*32),('NRestarts','1'),('MainPID','900002'),('ControlGroup','/foreign')]:
            proc=Processes();proc.live[key]=value
            with self.assertRaises(ValueError):w.signal_owned(owner(),FORBIDDEN,proc,signal.SIGTERM)
            self.assertEqual(proc.signals,[])
        self.proc.identity['inode']=100
        with self.assertRaises(ValueError):w.signal_owned(owner(),FORBIDDEN,self.proc,signal.SIGTERM)
        self.assertEqual(self.proc.signals,[])

    def test_escalation_refuses_forbidden_or_duplicate_group_member_before_open(self):
        for ids in ([900001,1],[900001,900001],list(range(1000000,1000065))):
            self.proc.ids=ids
            with self.assertRaises(ValueError):w.signal_owned(owner(),FORBIDDEN,self.proc,signal.SIGKILL)
            self.assertEqual(self.proc.opened,[]);self.assertEqual(self.proc.signals,[])

    def test_pidfd_is_closed_when_birth_check_fails_after_open(self):
        self.proc.after_open=lambda pid:self.proc.births.update({pid:999})
        with self.assertRaises(ValueError):w.signal_owned(owner(),FORBIDDEN,self.proc,signal.SIGTERM)
        self.assertEqual(self.proc.opened,[900001]);self.assertEqual(self.proc.closed,[900011])
        self.assertEqual(self.proc.signals,[])

    def test_second_unit_identity_check_precedes_every_signal(self):
        def change(count):
            if count==2:self.proc.live['InvocationID']='b'*32
        self.proc.on_fields=change
        with self.assertRaises(ValueError):w.signal_owned(owner(),FORBIDDEN,self.proc,signal.SIGKILL)
        self.assertEqual(self.proc.signals,[]);self.assertEqual(self.proc.closed,[900011,900012])

    def test_escalation_can_clean_original_children_after_main_exit(self):
        self.proc.live['MainPID']='0';del self.proc.births[900001];self.proc.ids=[900002]
        result=w.signal_owned(owner(),FORBIDDEN,self.proc,signal.SIGKILL)
        self.assertEqual(result['sent'],[dict(pid=900002,starttime_ticks=66)])
        self.assertEqual(self.proc.signals,[(900012,signal.SIGKILL)]);self.assertFalse(result['main_touched'])

    def test_departed_process_is_retained_without_numeric_pid_signal(self):
        del self.proc.births[900002]
        result=w.signal_owned(owner(),FORBIDDEN,self.proc,signal.SIGKILL)
        self.assertEqual(result['departed'],[900002]);self.assertEqual(self.proc.signals,[(900011,signal.SIGKILL)])

    def test_actual_process_capabilities_use_bounded_show_and_pidfd_api(self):
        cap=w.Processes()
        with patch.object(w.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='Id=test.service\n')) as run:
            self.assertEqual(cap.fields('test.service'),dict(Id='test.service'))
            self.assertEqual(run.call_args.kwargs['timeout'],2)
        with patch.object(w.os,'pidfd_open',return_value=123) as opened, \
             patch.object(w.signal,'pidfd_send_signal') as sent,patch.object(w.os,'close') as closed:
            fd=cap.open(900001);cap.send(fd,signal.SIGTERM);cap.close(fd)
        opened.assert_called_once_with(900001);sent.assert_called_once_with(123,signal.SIGTERM);closed.assert_called_once_with(123)

    def test_whole_unit_coverage_requires_actual_start_and_exit_bracketing(self):
        def row(t):return dict(start_monotonic_s=t,end_monotonic_s=t,healthy=True,evidence={'wire':'fake'})
        good=[row(100),row(105),row(111)]
        self.assertTrue(w.coverage(good,101,110)['whole_unit_main_coverage'])
        for rows in ([row(102),row(111)],[row(100),row(109)],[row(100),row(111)],
                     [row(100),row(99),row(111)]):
            with self.assertRaises(ValueError):w.coverage(rows,101,110)
        bad=copy.deepcopy(good);bad[1]['healthy']=False
        with self.assertRaises(ValueError):w.coverage(bad,101,110)

    def test_finish_preserves_signal_exit_as_invalid_and_never_claims_archival(self):
        g=self.armed();self.clock.value=105;g.observe();self.clock.value=111
        result=g.finish(self.terminal(code='2',status='9'),cgroup_absent=True)
        self.assertFalse(result['valid']);self.assertEqual(result['terminal_fields']['ExecMainCode'],'2')
        self.assertEqual(result['terminal_fields']['ExecMainStatus'],'9');self.assertTrue(result['coverage']['whole_unit_main_coverage'])
        self.assertFalse(result['archives_verified']);self.assertFalse(result['units_released'])

    def test_finish_exit0_validates_only_watchdog_scope_and_is_single_attempt(self):
        g=self.armed();self.clock.value=105;g.observe();self.clock.value=111
        result=g.finish(self.terminal(),cgroup_absent=True)
        self.assertTrue(result['valid']);self.assertFalse(result['quality_qualified'])
        with self.assertRaises(ValueError):g.finish(self.terminal(),cgroup_absent=True)
        with self.assertRaises(ValueError):g.start()

    def test_terminal_coverage_gap_or_live_cgroup_cannot_pass(self):
        g=self.armed()
        with self.assertRaises(ValueError):g.finish(self.terminal(),cgroup_absent=False)
        self.clock.value=120;result=g.finish(self.terminal(end=119),cgroup_absent=True)
        self.assertFalse(result['valid']);self.assertFalse(result['coverage']['whole_unit_main_coverage'])

    def test_terminal_systemd_omission_of_departed_cgroup_is_honestly_accepted(self):
        g=self.armed();self.clock.value=105;g.observe();self.clock.value=111
        terminal=self.terminal();del terminal['ControlGroup']
        with self.assertRaises(ValueError):g.finish(terminal,cgroup_absent=False)
        result=g.finish(terminal,cgroup_absent=True)
        self.assertTrue(result['valid']);self.assertNotIn('ControlGroup',result['terminal_fields'])

    def test_default_library_entry_has_no_launch_branch(self):
        tree=ast.parse((HERE/'startup_probe_watchdog_v1.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.If) and '__name__' in ast.unparse(n.test))
        out=io.StringIO()
        with redirect_stdout(out):exec(compile(ast.Module(body=[node],type_ignores=[]),'<library-entry>','exec'),{'__name__':'__main__'})
        self.assertIn('LIBRARY_ONLY',out.getvalue())


if __name__=='__main__':
    time.sleep(2)
    # Any mistaken use of the real capabilities fails at the exact shared module
    # boundary. Tests of those wrappers explicitly substitute their own mocks.
    with patch.object(w.subprocess,'run',side_effect=AssertionError('real process/service query forbidden')), \
         patch.object(w.os,'pidfd_open',side_effect=AssertionError('real pidfd forbidden')), \
         patch.object(w.signal,'pidfd_send_signal',side_effect=AssertionError('real signal forbidden')):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-private-startup-watchdog-CPU-contracts-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual independent witness/deadline threads and signal/coverage code with the same injected fake process capability; real pidfd/service wrappers mocked at their shared module boundary. No real unit query, scheduling, process signal, numerical module or GPU.',
        launcher_integrated=False,real_runtime_validated=False,production_changed=False,
        real_ROM_start_proven=False,quality_gain_verified=False,learning_speed_gain_verified=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
