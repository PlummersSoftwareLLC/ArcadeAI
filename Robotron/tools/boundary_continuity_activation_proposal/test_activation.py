"""Pure phase and signal-ownership guards; no real processes or checkpoint I/O."""
import contextlib
import io
import signal
import unittest
from unittest.mock import patch

import activate


class ActivationGuards(unittest.TestCase):
    def test_default_cli_does_not_read_or_execute(self):
        with patch.object(activate, 'pin', side_effect=AssertionError('Unexpected read')), \
                patch.object(activate, 'Activation', side_effect=AssertionError('Unexpected activation')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(activate.main([]), 0)
            self.assertIn('PLAN_ONLY', output.getvalue())

    def test_resume_keeps_valid_phase_and_binds_newest_bytes(self):
        old = dict(metric='ce', valid=True, phase_id='synthetic-founder', root_precommit_sha256='a'*64)
        newest = dict(path='/synthetic/latest.pt', sha256='b'*64, bytes=1234)
        record = activate.resume_record(old, newest)
        self.assertEqual(record['action'], 'resume')
        self.assertEqual(record['checkpoint'], newest)
        self.assertEqual(record['phase_id'], old['phase_id'])
        self.assertEqual(record['root_precommit_sha256'], old['root_precommit_sha256'])
        for changed in (dict(old, metric='kl'), dict(old, valid=False)):
            with self.assertRaises(RuntimeError): activate.resume_record(changed, newest)

    def test_actor_signals_require_original_identity_and_affinity(self):
        actor = dict(pid=123, starttime_ticks=456, mask=[1,2])
        with patch.object(activate, 'starttime', return_value=456), \
                patch.object(activate.os, 'sched_getaffinity', return_value={1,2}), \
                patch.object(activate.os, 'kill') as send:
            activate.signal_actor(actor, signal.SIGSTOP)
            activate.signal_actor(actor, signal.SIGCONT)
            self.assertEqual(send.call_args_list[0].args, (123, signal.SIGSTOP))
            self.assertEqual(send.call_args_list[1].args, (123, signal.SIGCONT))
        for ticks, mask in ((None,{1,2}), (457,{1,2}), (456,{1})):
            with patch.object(activate, 'starttime', return_value=ticks), \
                    patch.object(activate.os, 'sched_getaffinity', return_value=mask), \
                    patch.object(activate.os, 'kill') as send:
                with self.assertRaises(RuntimeError): activate.signal_actor(actor, signal.SIGSTOP)
                send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
