import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import watch_learning_window_v2 as window
from .test_learning_window import sample


class BalancedWindowTests(unittest.TestCase):
    def test_in_flight_snapshot_is_retained_and_same_owner_repolled(self):
        busy=sample();counter=busy['host_pipeline']['learning_exposure']['optimizer']
        counter['available']=False;counter['total']['attempts_started']+=1
        normal=sample();lineage=window.exposure(normal)
        with tempfile.TemporaryDirectory() as name, \
             patch.object(window,'owner',return_value=dict(pid=123)) as identity, \
             patch.object(window,'api',side_effect=[busy,normal]) as query, \
             patch.object(window.time,'sleep'):
            actual=window.observe(dict(pid=123),Path(name),lineage)
            self.assertTrue(window.exposure(actual)['optimizer']['available'])
            self.assertEqual(query.call_count,2);self.assertEqual(identity.call_count,2)
            rejected=json.loads((Path(name)/'unaccepted-000000.json').read_text())
            self.assertEqual(rejected['reason'],'in_flight_optimizer_attempt')
            self.assertFalse(window.exposure(rejected['raw_API'])['optimizer']['available'])

    def test_real_unavailable_optimizer_outcome_is_fatal(self):
        bad=sample();counter=window.exposure(bad)['optimizer'];counter['available']=False
        counter['total']['unavailable']=1
        with patch.object(window,'owner',return_value=dict(pid=123)), \
             patch.object(window,'api',return_value=bad) as query:
            with self.assertRaisesRegex(AssertionError,'Unclassified optimizer outcome'):
                window.observe(dict(pid=123))
            self.assertEqual(query.call_count,1)

    def test_epoch_change_in_unavailable_snapshot_is_fatal(self):
        original=sample();bad=sample();counter=window.exposure(bad)['optimizer']
        counter['epoch']=2;counter['available']=False;counter['total']['attempts_started']+=1
        with patch.object(window,'owner',return_value=dict(pid=123)), \
             patch.object(window,'api',return_value=bad):
            with self.assertRaisesRegex(AssertionError,'epoch changed'):
                window.observe(dict(pid=123),expected_lineage=window.exposure(original))

    def test_transient_request_failure_does_not_restart_owner(self):
        with patch.object(window,'owner',return_value=dict(pid=123)) as identity, \
             patch.object(window,'api',side_effect=[OSError('temporary'),sample()]), \
             patch.object(window.time,'sleep'):
            self.assertEqual(window.observe(dict(pid=123))['client_count'],1)
            self.assertEqual(identity.call_count,2)

    def test_no_acceptable_sample_after_bound_is_a_retained_failure(self):
        busy=sample();counter=window.exposure(busy)['optimizer']
        counter['available']=False;counter['total']['attempts_started']+=1
        with patch.object(window,'owner',return_value=dict(pid=123)), \
             patch.object(window,'api',return_value=busy), \
             patch.object(window.time,'monotonic',side_effect=[0,31]):
            with self.assertRaisesRegex(TimeoutError,'30s'):
                window.observe(dict(pid=123))


if __name__=='__main__':
    unittest.main()
