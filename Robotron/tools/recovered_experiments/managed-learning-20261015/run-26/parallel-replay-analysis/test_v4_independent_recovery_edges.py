"""Independent stdlib fixture review; never uses real services or signals."""
import tempfile
from pathlib import Path
import unittest
from Robotron.tools import parallel_state_fill_trial as trial
from Robotron.tools.test_parallel_state_fill_trial import FakeLive,fake_plan


class IndependentRecoveryEdges(unittest.TestCase):
    def test_primary_start_fails_before_pid_and_fallback_still_requires_banks(self):
        for missing in (False,True):
            with self.subTest(fallback_missing=missing),tempfile.TemporaryDirectory() as directory:
                host=FakeLive();plan=fake_plan(host,Path(directory)/'unused')
                host.flag=host.configured_flag='1'
                host.dropin_expected=b'[Service]\nEnvironment=DQN_PARALLEL_STATE_FILL=1\n'
                host.restart_in_progress=True
                original_start=host.start;starts=[]
                def start():
                    starts.append(1)
                    if len(starts)==1:
                        host.active=False
                        host.events.append(('start_failed_before_pid',))
                        raise trial.metrics.GuardFailure('primary start failed with PID0')
                    original_start()
                host.start=start
                if missing:
                    def no_banks(current):raise trial.metrics.GuardFailure('fallback positive bank proof missing')
                    host.bank_load_proof=no_banks
                status={};trial.recover(host,plan,status)
                attempts=status['recovery']['serial_replacements']
                self.assertEqual([row['path'] for row in attempts],['primary','fallback'])
                self.assertIn('PID0',attempts[0]['startup_error'])
                self.assertEqual(attempts[1]['bank_verified'],not missing)
                self.assertEqual(sum(event[0]=='arm_transition' for event in host.events),2)
                self.assertEqual(len(starts),2)
                if missing:self.assertIn('bank proof missing',attempts[1]['error'])
                else:self.assertIn('bank_load_proof',attempts[1])
                self.assertTrue(status['recovery']['manual_recovery_required'])
                self.assertEqual(status['state'],'failed')
                self.assertEqual(status['decision']['outcome'],'invalid')
                self.assertFalse(status['decision']['automatic_promotion'])
                self.assertTrue(all(not actor['stopped'] for actor in host.actor_states.values()))

    def test_positive_bank_proof_with_fault_scan_failure_remains_invalid_manual(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();plan=fake_plan(host,Path(directory)/'unused')
            host.flag=host.configured_flag='1'
            host.dropin_expected=b'[Service]\nEnvironment=DQN_PARALLEL_STATE_FILL=1\n'
            host.restart_in_progress=True
            def unreadable():raise trial.metrics.GuardFailure('owned recovery fault increment unreadable')
            host.transition_log_events=unreadable
            status={};trial.recover(host,plan,status)
            attempt=status['recovery']['serial_replacements'][0]
            self.assertIn('bank_load_proof',attempt)
            self.assertFalse(attempt['bank_verified'])
            self.assertIn('unreadable',attempt['log_read_error'])
            self.assertTrue(status['recovery']['manual_recovery_required'])
            self.assertEqual(status['decision']['outcome'],'invalid')
            self.assertTrue(all(not actor['stopped'] for actor in host.actor_states.values()))


if __name__=='__main__':unittest.main()
