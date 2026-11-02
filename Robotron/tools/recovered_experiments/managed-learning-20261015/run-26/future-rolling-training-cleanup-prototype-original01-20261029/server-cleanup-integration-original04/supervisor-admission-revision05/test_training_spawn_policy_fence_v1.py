"""Unexecuted actual-method logic fixtures, not process/TCP or admission proof.

Root alone may run later. No process, socket, procfs, model or server calls.
The complete new candidate module is imported only during that future test run;
Popen, physical observations, clocks and API collaborators are synthetic.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import types
import unittest

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'owned_training_refill_join_candidate_v2.py'
SOURCE_SHA='1bfe8deec2834dd246e846f75afdcf2a1b1dc2872a87d3e6b81203f72b976966'


class Clock:
    def __init__(self):
        self.now=1000000000
    def monotonic_ns(self):
        self.now+=1
        return self.now
    def time(self):
        return 1700000000.0


class OriginalPopen:
    def __init__(self, pid=9001, code=None):
        self.pid,self.code=pid,code
        self.args=['/synthetic/wrapper','robotron']
    def poll(self):
        return self.code
    def wait(self,timeout=None):
        raise AssertionError('Observation/eligibility must not reap or control a process')


class Fixture:
    slot=37  # Exactly0..36 are EVAL; this is an unchanged TRAIN slot.
    ticket='a'*64
    def __init__(self):
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
        spec=importlib.util.spec_from_file_location('_prospective_spawn_policy_fixture',SOURCE)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.clock=Clock()
        self.module.time=self.clock
        self.module.subprocess=types.SimpleNamespace(Popen=OriginalPopen)
        self.module.secrets=types.SimpleNamespace(token_hex=lambda count:'b'*(count*2))
        self.roles={str(n):n<37 for n in range(192)}
        self.common=dict(ROBOTRON_RECOVERY_CONFIG='/synthetic/config.json',
            ROBOTRON_RECOVERY_CONFIG_SHA256='c'*64,LD_PRELOAD='/synthetic/wait.so',
            ROBOTRON_SOCKET_WAIT_PORT='9998',ROBOTRON_SOCKET_WAIT_US='125')
        self.server=dict(pid=123,birth=456,source_sha256='d'*64)
        self.join=self.module.OwnedTrainingRefillJoins(self.roles,
            launch_argv=['/synthetic/wrapper','robotron'],mame_argv=['/synthetic/mame','robotron'],
            controlled_environment=self.common,expected_server_stamp=self.server)
        terminal=dict(client_id=7,client_slot=self.slot,eval_only=False,
            journal_game_id='123:71',complete=True,eligible=True,known_start=True,
            boundary_reason='score_reset',score=150000123)
        self.previous_cleanup=dict(schema='robotron-prospective-connection-cleanup-receipt-v2',
            server_stamp=self.server,token='old:connection',server_cleanup_incarnation='old:server',
            client_id=7,client_slot=self.slot,eval_only=False,connection_ns=11,
            socket_endpoints=dict(server=['127.0.0.1',9998],peer=['127.0.0.1',44007]),
            terminal_receipt=terminal,terminal_line_sha256='e'*64,ready_for_external_join=True,
            replay_consumer_healthy=True,replay_admission_open=True,cleanup_error=None,
            measurement_active=False,measurement_generation=1)
        self.old_child=OriginalPopen(8001,0)
        self.join.records[self.slot]=dict(child=self.old_child,generation=1,retired=True,
            ticket=self.ticket,evidence={},retirement_proof=dict(actual_cleanup=copy.deepcopy(self.previous_cleanup),
                durable_terminal=terminal))
        self.fresh_cleanup=copy.deepcopy(self.previous_cleanup)
        self.fresh_active=dict(schema='robotron-prospective-connection-cleanup-receipt-v2',
            server_stamp=self.server,token='new:connection',server_cleanup_incarnation='old:server',
            client_id=8,client_slot=self.slot,eval_only=False,connection_ns=22,
            socket_endpoints=dict(server=['127.0.0.1',9998],peer=['127.0.0.1',44008]),
            original_handler_stopped=False,terminal_receipt=None,training_refill_candidate=False,
            measurement_active=False,measurement_generation=1,replay_admission_open=True,
            replay_consumer_healthy=True,cleanup_error=None)
        self.actor_generation=2
        self.module.actor=lambda pid:dict(pid=pid,birth=17,parent=self.module.os.getpid(),
            uid=self.module.os.getuid(),cgroup='/synthetic/owned',exe='/synthetic/mame',
            command=['/synthetic/mame','robotron'],environment=dict(self.common,
                ROBOTRON_CLIENT_SLOT=str(self.slot),ROBOTRON_ACTOR_ROUND=str(self.actor_generation),
                ROBOTRON_RETIRE_AFTER_GAME='1',ROBOTRON_EVAL_MODE='2'))
        self.module.cgroup=lambda pid:'/synthetic/owned'
        self.module.tcp_binding=lambda pid,endpoints:dict(inode=41,
            local=endpoints['peer'],remote=endpoints['server'])

    def read_terminal(self,cid,slot,jid):
        assert (cid,slot,jid)==(7,self.slot,'123:71')
        return dict(copy.deepcopy(self.fresh_cleanup),observed_monotonic_ns=self.clock.monotonic_ns())

    def read_active(self,cid,slot):
        assert (cid,slot)==(8,self.slot)
        return dict(copy.deepcopy(self.fresh_active),observed_monotonic_ns=self.clock.monotonic_ns())

    def prepare(self):
        return self.join.prepare_training_spawn(self.slot,2,self.ticket,self.read_terminal)


class Tests(unittest.TestCase):
    def test_policy_changes_before_consumption_refuse_and_preserve_unused_ticket(self):
        for changes in ({'measurement_active':True},{'measurement_generation':2},
                        {'replay_admission_open':False},{'replay_consumer_healthy':False},
                        {'cleanup_error':'consumer failed'},{'token':'different-connection'},
                        {'terminal_line_sha256':'f'*64}):
            with self.subTest(changes=changes):
                f=Fixture();f.fresh_cleanup.update(changes)
                with self.assertRaises(ValueError):f.prepare()
                self.assertEqual(f.join.records[f.slot]['ticket'],f.ticket)
                self.assertEqual(f.join.spawn_claims,{})
                self.assertEqual(f.join.pending_children,[])

    def test_fresh_policy_burns_once_without_claiming_spawn_order_or_actor_admission(self):
        f=Fixture();claim=f.prepare()
        self.assertIsNone(f.join.records[f.slot]['ticket'])
        self.assertEqual(claim['measurement_generation'],1)
        self.assertEqual(claim['scope'],'ELIGIBILITY_ONLY_NOT_ACTOR_ADMISSION_PROOF')
        self.assertFalse(claim['admission_proved'])
        self.assertFalse(claim['pre_spawn_or_actual_gate_release_order_proved'])
        self.assertTrue(claim['caller_pre_spawn_or_actual_gate_release_and_policy_fence_required'])
        self.assertNotIn('actor_unadmitted',claim)
        self.assertEqual(f.join.pending_children,[])
        with self.assertRaises(ValueError):f.prepare()
        self.assertIsNone(f.join.records[f.slot]['ticket'])

    def test_post_spawn_policy_change_keeps_original_child_for_quarantine(self):
        for changes in ({'measurement_active':True},{'measurement_generation':2},
                        {'replay_admission_open':False},{'replay_consumer_healthy':False},
                        {'cleanup_error':'consumer failed'}):
            with self.subTest(changes=changes):
                f=Fixture();claim=f.prepare();child=OriginalPopen()
                f.fresh_active.update(changes)
                with self.assertRaises(ValueError):
                    f.join.observe_original(f.slot,2,child,8,f.read_active,spawn_claim=claim)
                self.assertIs(f.join.pending_children[0]['child'],child)
                self.assertFalse(f.join.pending_children[0]['physical_tracking_complete'])
                self.assertTrue(f.join.pending_children[0]['requires_caller_admission_or_quarantine'])
                self.assertIs(f.join.records[f.slot]['child'],f.old_child)
                self.assertIsNone(f.join.records[f.slot]['ticket'])
                self.assertFalse(f.join.spawn_claims[f.slot]['observed'])

    def test_fresh_observation_is_physical_tracking_and_cannot_reuse_claim_for_another_child(self):
        f=Fixture();claim=f.prepare();child=OriginalPopen()
        value=f.join.observe_original(f.slot,2,child,8,f.read_active,spawn_claim=claim)
        self.assertTrue(value['physical_actor_connected_proved'])
        self.assertEqual(value['observation_scope'],'PHYSICAL_TRACKING_ONLY_ACTOR_MAY_ALREADY_BE_ACTING')
        self.assertFalse(value['admission_proved'])
        self.assertFalse(value['pre_spawn_or_actual_gate_release_order_proved'])
        self.assertTrue(value['requires_external_caller_admission_or_quarantine'])
        self.assertIs(f.join.records[f.slot]['child'],child)
        self.assertTrue(f.join.pending_children[0]['physical_tracking_complete'])
        self.assertTrue(f.join.spawn_claims[f.slot]['observed'])
        another=OriginalPopen(9002)
        with self.assertRaises(ValueError):
            f.join.observe_original(f.slot,2,another,8,f.read_active,spawn_claim=claim)
        self.assertIs(f.join.pending_children[1]['child'],another)
        self.assertIs(f.join.records[f.slot]['child'],child)

    def test_seal_expiry_or_wrong_claim_never_rearms_ticket_and_keeps_already_started_child(self):
        f=Fixture();f.join.seal()
        with self.assertRaises(ValueError):f.prepare()
        self.assertEqual(f.join.records[f.slot]['ticket'],f.ticket)
        for fault in ('sealed','expired','wrong_claim','retired_child'):
            with self.subTest(fault=fault):
                f=Fixture();claim=f.prepare();child=OriginalPopen()
                if fault=='sealed':f.join.seal()
                if fault=='expired':f.clock.now+=2_000_000_001
                if fault=='wrong_claim':claim['claim_nonce']='wrong'
                if fault=='retired_child':child.code=0
                with self.assertRaises(ValueError):
                    f.join.observe_original(f.slot,2,child,8,f.read_active,spawn_claim=claim)
                self.assertIsNone(f.join.records[f.slot]['ticket'])
                self.assertIs(f.join.pending_children[0]['child'],child)
                self.assertFalse(f.join.pending_children[0]['physical_tracking_complete'])

    def test_EVAL_and_budget_do_not_consume_train_ticket_and_initial_tracking_is_not_admission(self):
        f=Fixture()
        with self.assertRaises(ValueError):
            f.join.prepare_training_spawn(0,2,f.ticket,f.read_terminal)
        self.assertEqual(sum(f.join.roles.values()),37)
        self.assertEqual(len(f.join.roles)-sum(f.join.roles.values()),155)
        f.join.completed=[{}]*f.join.maximum_generations
        with self.assertRaises(ValueError):f.prepare()
        self.assertEqual(f.join.records[f.slot]['ticket'],f.ticket)
        f=Fixture();f.join.records.clear();f.actor_generation=1;f.join.seal()
        f.fresh_active['measurement_active']=True
        child=OriginalPopen()
        value=f.join.observe_original(f.slot,1,child,8,f.read_active)
        self.assertTrue(value['physical_actor_connected_proved'])
        self.assertFalse(value['admission_proved'])
        self.assertEqual(value['observation_scope'],'PHYSICAL_TRACKING_ONLY_ACTOR_MAY_ALREADY_BE_ACTING')


if __name__=='__main__':
    unittest.main()
