"""Unexecuted stdlib guards using synthetic metadata; no application imports."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from . import horizon_observer2048 as helper


def api_at(elapsed=100, *, learner=0, physical=0, applied=1, skipped=0,
           inflight=0, epsilon=0, expert=0, evaluate=0, unattributed=0):
    categories = dict(dqn=physical-epsilon-expert-evaluate-unattributed,
        epsilon=epsilon, expert=expert, eval=evaluate, unattributed=unattributed)
    recorded = applied + skipped
    total = dict(attempts_started=recorded+inflight, outcomes_recorded=recorded,
        applied=applied, amp_skipped=skipped, unavailable=0)
    identity = dict(process_id=123, instance_monotonic_ns=1000,
        epoch=1, epoch_reason='synthetic_restore')
    optimizer = dict(identity, schema='robotron-optimizer-exposure-v1',
        enabled=True, available=recorded>0 and inflight==0, total=total,
        since_epoch=copy.deepcopy(total), unclassified_started_total=inflight)
    replay = dict(identity, schema='robotron-replay-insert-exposure-v1',
        enabled=True, available=True, accepted_total=physical,
        accepted_learner_total=categories['dqn']+categories['epsilon'],
        accepted_by_source_total=categories)
    return dict(training_steps=100+recorded,
        optimized_samples=409600+recorded*2048, frame_count=20000+physical,
        learner_frame_count=10000+learner, ts=100000+elapsed,
        pipeline_snapshot_age_s=0, pipeline_read_error='',
        host_pipeline=dict(learning_exposure=dict(optimizer=optimizer, replay=replay)))


def job_at(healthy_elapsed=90):
    return dict(schema=helper.SCHEMA, policy=copy.deepcopy(helper.POLICY),
        batch_size=2048, profile_binding=copy.deepcopy(helper.PROFILE_BINDING),
        owner=dict(pid=123, starttime_ticks=200,
            unit='robotron-managed-synthetic-trainer.service', invocation_id='a'*32,
            cgroup='/user.slice/synthetic.service'),
        start_request=dict(boot_id='synthetic-boot', monotonic_s=1000, unix_s=100000),
        healthy192_monotonic_s=1000+healthy_elapsed,
        boot_four_clocks=dict(training_steps=100, optimized_samples=409600,
            frame_count=20000, learner_frame_count=10000),
        trial_core_sha256='b'*64, activation_receipt_sha256='c'*64,
        before_resume_api=api_at(10, applied=0))


def clock(elapsed):
    return dict(boot_id='synthetic-boot', monotonic_s=1000+elapsed,
        wall_s=100000+elapsed)


def observe(observer, api, elapsed=100, owner=None):
    return observer.observe(api, observer.job['owner'] if owner is None else owner,
        dict(ok=True), clock(elapsed))


class Batch2048HorizonContracts(unittest.TestCase):
    def test_default_plan_reads_nothing_and_declares_unactivated_profile(self):
        with patch.object(helper, 'HorizonObserver', side_effect=AssertionError('no observer')), \
                patch('builtins.open', side_effect=AssertionError('no reads')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('no reads')), \
                contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(helper.main(), 0)
        plan = json.loads(stream.getvalue())
        self.assertEqual(plan['status'], 'PLAN_ONLY')
        self.assertEqual(plan['batch_size'], 2048)
        self.assertTrue(plan['policy_is_unactivated_proposal'])
        self.assertEqual(plan['profile_binding'], helper.PROFILE_BINDING)
        self.assertFalse(plan['actions'])

    def test_valid_exact_profile_is_independent_of_job_mutations(self):
        job = job_at()
        observer = helper.HorizonObserver(job)
        job['profile_binding']['value']['batch_size'] = 4096
        self.assertEqual(observer.job['profile_binding']['value']['batch_size'], 2048)
        profile = helper.PROFILE_BINDING['value']
        self.assertEqual(profile['priority_metric'], 'ce')
        self.assertEqual(profile['held_recipe_context']['baseline_batch_size'], 512)
        self.assertFalse(profile['LR_compensation'])
        self.assertEqual(profile['deliberate_recipe_changes'], ['DQN_BATCH_SIZE'])

    def test_missing_wrong_and_noninteger_batch_are_refused(self):
        for value in (None, 4096, 512, 2048.0, True, '2048'):
            job = job_at()
            if value is None:
                del job['batch_size']
            else:
                job['batch_size'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                helper.HorizonObserver(job)

    def test_profile_pin_value_and_extra_fields_cannot_drift(self):
        cases = []
        missing = job_at(); del missing['profile_binding']; cases.append(missing)
        for key, value in (('path', '/synthetic/foreign-profile.json'),
                           ('sha256', '0'*64), ('bytes', 1)):
            job = job_at(); job['profile_binding']['pin'][key] = value; cases.append(job)
        for key, value in (('batch_size', 4096), ('priority_metric', 'kl'),
                           ('LR_compensation', True)):
            job = job_at(); job['profile_binding']['value'][key] = value; cases.append(job)
        job = job_at(); job['profile_binding']['value']['held_recipe_context']['optimizer_lr'] *= 2; cases.append(job)
        job = job_at(); job['profile_binding']['extra'] = True; cases.append(job)
        for index, job in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                helper.HorizonObserver(job)

    def test_historical4096_schema_and_profileless_job_are_refused(self):
        job = job_at(); job['schema'] = 'robotron-raw-kl-horizon-job-v1'
        with self.assertRaises(ValueError):
            helper.HorizonObserver(job)
        del job['profile_binding']; del job['batch_size']
        with self.assertRaises(ValueError):
            helper.HorizonObserver(job)

    def test_both_thresholds_required_without_logical_sample_substitution(self):
        for learner, physical in ((8000000, 5999999), (7999999, 6000000)):
            api = api_at(learner=learner, physical=physical)
            api['optimized_samples'] = 999999999999
            api['training_steps'] = 999999999
            with self.subTest(learner=learner, physical=physical):
                event = observe(helper.HorizonObserver(job_at()), api)
                self.assertEqual(event['state'], 'CONTINUE')
        event = observe(helper.HorizonObserver(job_at()),
            api_at(learner=8000000, physical=6000000))
        self.assertEqual(event['state'], 'LATCH')
        self.assertEqual(event['candidate_requests_allowed'], 1)
        self.assertFalse(event['qualification_pass'])

    def test_physical_horizon_sums_all_five_sources_not_learner_only(self):
        event = observe(helper.HorizonObserver(job_at()), api_at(learner=8000000,
            physical=6000000, epsilon=500000, expert=2000000,
            evaluate=1000000, unattributed=1000000))
        self.assertEqual(event['state'], 'LATCH')
        self.assertEqual(event['progress']['physical_accepted'], 6000000)
        self.assertEqual(event['progress']['learner_accepted'], 2000000)

    def test_admitted_units_are2048_and_skips_are_not_admissions(self):
        event = observe(helper.HorizonObserver(job_at()), api_at(learner=8000000,
            physical=6000000, applied=2, skipped=3, inflight=1))
        self.assertEqual(event['state'], 'LATCH')
        self.assertEqual(event['progress']['admitted_samples_total'], 4096)
        self.assertEqual(event['progress']['optimizer_total']['amp_skipped'], 3)
        self.assertIn('admitted2048', event['progress']['admitted_samples_scope'])

    def test_full_exposure_epoch_owner_and_clock_discontinuity_refused(self):
        for group in ('optimizer', 'replay'):
            for key in helper.IDENTITY:
                api = api_at()
                value = api['host_pipeline']['learning_exposure'][group][key]
                api['host_pipeline']['learning_exposure'][group][key] = value+1 if type(value) is int else 'other'
                with self.subTest(group=group, key=key):
                    self.assertEqual(observe(helper.HorizonObserver(job_at()), api)['state'], 'INVALID')
        observer = helper.HorizonObserver(job_at())
        self.assertEqual(observe(observer, api_at(), owner={})['state'], 'INVALID')
        for field in helper.CLOCKS:
            observer = helper.HorizonObserver(job_at())
            observe(observer, api_at(100, learner=100, physical=100, applied=2))
            api = api_at(101, learner=100, physical=100, applied=2)
            api[field] -= 1
            with self.subTest(field=field):
                self.assertEqual(observe(observer, api, 101)['state'], 'INVALID')

    def test_original_cutoff_ceiling_freshness_and_first_latch_immutability(self):
        target = dict(learner=8000000, physical=6000000)
        exact = observe(helper.HorizonObserver(job_at(3230)), api_at(3240, **target), 3240)
        self.assertEqual(exact['state'], 'LATCH')
        late = observe(helper.HorizonObserver(job_at(3230)), api_at(3241, **target), 3241)
        self.assertEqual(late['state'], 'INCOMPLETE')
        ceiling = observe(helper.HorizonObserver(job_at(3590)), api_at(3600, **target), 3600)
        self.assertEqual(ceiling['state'], 'INVALID')
        self.assertIn('CE batch2048 owner', ceiling['reason'])
        gap = observe(helper.HorizonObserver(job_at(70)), api_at(100, **target), 100)
        self.assertEqual(gap['state'], 'INVALID')
        stale = api_at(100, **target); stale['ts'] -= 6
        self.assertEqual(observe(helper.HorizonObserver(job_at()), stale)['state'], 'CONTINUE')
        observer = helper.HorizonObserver(job_at())
        first = observe(observer, api_at(100, **target))
        first['candidate_requests_allowed'] = 99
        later = observer.observe(None, None, {}, clock(3600))
        self.assertEqual(later['state'], 'LATCH')
        self.assertEqual(later['candidate_requests_allowed'], 1)
        ending = helper.ending_deadline(job_at(), clock(3600), CE_owner_present=True)
        self.assertEqual(ending['state'], 'INVALID')

    def test_profile_file_pin_and_finite_replacements_reverse_exactly_to25d(self):
        here = Path(__file__).resolve().parent
        raw = (here/'profile.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), helper.PROFILE_BINDING['pin']['sha256'])
        self.assertEqual(len(raw), helper.PROFILE_BINDING['pin']['bytes'])
        self.assertEqual(json.loads(raw), helper.PROFILE_BINDING['value'])
        self.assertEqual(str(here/'profile.json'), helper.PROFILE_BINDING['pin']['path'])
        replacements = json.loads((here/'source-replacements.json').read_bytes())
        original = Path(replacements['original']['path']).read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),
            '25d70b4a3888dcba83ea9020c333cba32cfbd19c93b6e69037d6299b161fd7ec')
        source = (here/'horizon_observer2048.py').read_text()
        for entry in reversed(replacements['replacements']):
            self.assertEqual(source.count(entry['new']), entry['count'])
            source = source.replace(entry['new'], entry['old'])
        self.assertEqual(source.encode(), original)
        self.assertIn("admitted_samples_total=current['optimizer']['applied']*4096", original.decode())


if __name__ == '__main__':
    unittest.main()
