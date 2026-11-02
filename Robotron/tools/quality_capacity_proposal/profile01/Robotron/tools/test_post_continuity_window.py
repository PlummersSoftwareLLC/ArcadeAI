"""Horizon and counter guards; no live trainer/process/checkpoint operations."""
import contextlib
import copy
import io
import unittest
from unittest.mock import patch

import post_continuity_window as window


def sample():
    return dict(clocks=dict(training_steps=10,optimized_samples=40960,learner_frame_count=100,frame_count=200),
        optimizer_identity=dict(process_id=123,epoch=1),replay_identity=dict(process_id=123,epoch=1),
        optimizer=dict(applied=10,amp_skipped=0,unavailable=0),optimizer_since_epoch=dict(applied=10),
        categories=dict(dqn=50,epsilon=10,expert=5,eval=0,unattributed=0),learner_accepted=60)


class WindowGuards(unittest.TestCase):
    def test_both_original_horizons_are_required(self):
        before=sample()
        for frames,accepted,expected in [(8000000,7999999,False),(7999999,8000000,False),
                                          (8000000,8000000,True),(8000001,8000020,True)]:
            after=copy.deepcopy(before);after['clocks']['learner_frame_count']+=frames
            after['learner_accepted']+=accepted;after['categories']['dqn']+=accepted
            with self.subTest(frames=frames,accepted=accepted):
                self.assertIs(window.progress(after,before,before)['both_horizons'],expected)

    def test_owner_epoch_counter_regression_or_unavailable_fails(self):
        for mutate in [lambda a:a['optimizer_identity'].update(process_id=124),
                       lambda a:a['replay_identity'].update(epoch=2),
                       lambda a:a['clocks'].update(training_steps=9),
                       lambda a:a['optimizer'].update(applied=9),
                       lambda a:a['categories'].update(dqn=49),
                       lambda a:a['optimizer'].update(unavailable=1)]:
            before=sample();after=copy.deepcopy(before);mutate(after)
            with self.assertRaises(ValueError):window.progress(after,before,before)

    def test_every_pipeline_error_and_stale_sample_fails(self):
        before=dict(host_pipeline=dict(generation=0))
        api=dict(client_count=192,training_enabled=True,measurement_active=False,
            managed_experiment='synthetic',lr=1.25e-5,pipeline_read_error='',
            bank_persistence_read_error='',ts=999.0,pipeline_snapshot_age_s=.1,
            host_pipeline=dict(schema='robotron-host-pipeline-v1',available=True,generation=0),
            bank_persistence=dict(write_failures=0))
        for k in ['inference','actor_refresh','target_refresh','learner_priority']:
            api['host_pipeline'][k]=dict(errors=0)
        window.healthy(api,before,'synthetic',1000.0)
        for key in ['inference','actor_refresh','target_refresh','learner_priority']:
            after=copy.deepcopy(api);after['host_pipeline'][key]['errors']=1
            with self.subTest(key=key),self.assertRaises(ValueError):window.healthy(after,before,'synthetic',1000.0)
        for key,value in [('ts',994.0),('ts',1001.0),('pipeline_snapshot_age_s',float('nan'))]:
            after=copy.deepcopy(api);after[key]=value
            with self.assertRaises(ValueError):window.healthy(after,before,'synthetic',1000.0)

    def test_default_cli_has_no_reads_or_actions(self):
        with patch.object(window,'pin',side_effect=AssertionError('Unexpected read')), \
                patch.object(window,'run',side_effect=AssertionError('Unexpected run')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(window.main([]),0)
            self.assertIn('PLAN_ONLY',output.getvalue())


if __name__=='__main__':unittest.main()
