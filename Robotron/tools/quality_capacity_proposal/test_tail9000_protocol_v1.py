"""New-window boundary and refusal tests with no real models or evaluations."""
import copy
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

from tail9000_test_support_v1 import campaign, ROOT
import audit_quality32_evidence_v2 as cohorts
import review_closed_quality32_v6 as reviewer
import test_audit_quality32_evidence_v2 as plan_fixtures
import test_tail9000_runtime_guard_fixtures_v1 as guard_fixtures
import test_quality32_acquisition_v3 as acquisition_fixtures


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ProtocolTests(unittest.TestCase):
    def test_new_evaluator_accepts9000_rejects9001_and_old_evaluator_still_refuses9000(self):
        old = load(ROOT.parents[1]/'profile03/Robotron/tools/run_frozen_sidecar.py', '_old_tail_ceiling')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); model = root/'synthetic.pt'; model.write_bytes(b'not a model')
            job = campaign.evaluator.Job(model, root/'unused', 'synthetic', 'cpu',
                cohort_s=5400, timeout_s=9000, mame=Path('/bin/true'), rompath=root)
            job.validate()
            for timeout in (9001, float('inf'), float('nan'), 5400):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    replace(job, timeout_s=timeout).validate()
            previous = old.Job(**vars(job))
            with self.assertRaises(ValueError):
                previous.validate()
            self.assertFalse(job.directory.exists())

    def test_old_or_mixed_leg_timeout_cannot_enter_new_four_leg_protocol(self):
        fixture = plan_fixtures.PlanTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.validate()
        original = copy.deepcopy(fixture.plan)
        for indices in ((0,), (1,), (2,), (3,), (0, 1, 2, 3)):
            fixture.plan = copy.deepcopy(original)
            for index in indices:
                leg = fixture.plan['legs'][index]
                leg['job']['timeout_s'] = 7200
                command = leg['command']; command[command.index('--timeout-s')+1] = '7200'
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                fixture.validate()

    def test_old_native_cap_or_observation_cap_refuses_scheduling(self):
        fixture = guard_fixtures.ObserverTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.guard.validate_config(fixture.config)
        for key, value in [('properties', [p.replace('36600', '29400') for p in fixture.config['properties']]),
                           ('observation_s', 30000)]:
            changed = copy.deepcopy(fixture.config); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                fixture.guard.validate_config(changed)

    def test_new_leg_lifetime_allows_longer_tail_but_keeps_300_second_overhead_bound(self):
        old = load(Path(reviewer.__file__).with_name('review_closed_quality32_v5.py'), '_old_leg_scope')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'source.pt'; source.write_bytes(b'synthetic')
            destination = root/'leg'; destination.mkdir(); (destination/'checkpoint.pt').write_bytes(source.read_bytes())
            spec = dict(role='reference', job=dict(directory=str(destination), checkpoint=str(source), gpu_uuid=campaign.GPU0_UUID))
            receipt = dict(source_checkpoint_path=str(source), checkpoint_path=str(destination/'checkpoint.pt'),
                runtime=dict(device='cuda', cuda_visible_devices=campaign.GPU0_UUID,
                    gpu_name='NVIDIA RTX PRO 2000 Blackwell', compute_capability=[12, 0]), elapsed_s=8400)
            record = dict(started_unix_s=10000, ended_unix_s=18401)
            reviewer.validate_leg_scope(receipt, spec, record, {})
            with self.assertRaises(ValueError): old.validate_leg_scope(receipt, spec, record, {})
            for elapsed in (9300, 9301):
                receipt['elapsed_s'] = elapsed; record['ended_unix_s'] = 10000+elapsed
                with self.subTest(elapsed=elapsed), self.assertRaises(ValueError):
                    reviewer.validate_leg_scope(receipt, spec, record, {})


class MeasurementTests(unittest.TestCase):
    def fixture(self):
        module = load(ROOT/'Scripts/dqn/managed_measurement.py', '_new_tail_measurement')
        now = [100.]
        agent = SimpleNamespace(training_enabled=False, behavior_locked=True, _training_lock=threading.RLock(),
            training_steps=0, optimized_samples=0, capture_inference_policy=lambda: {},
            install_inference_policy=lambda value: None, _pause_prefetch=lambda: None)
        metrics = SimpleNamespace(lock=threading.RLock(), training_enabled=False, measurement_active=False,
            measurement_generation=0, total_training_steps=0, total_optimized_samples=0, learner_frame_count=0)
        cohort = dict(started=65, count=63, pending=2, abandoned=0, complete=False,
            started_actor_slots=list(range(4096, 4128)))
        journal = SimpleNamespace(cohort_status=lambda *args: copy.deepcopy(cohort))
        measurement = module.ManagedMeasurement(agent, metrics, journal, clock=lambda: now[0],
            boundary_status=lambda generation: dict(ready=True, generation=generation, actor_slots=list(range(4096, 4128))))
        measurement.enter('synthetic-new-window', cohort_s=5400, timeout_s=9000)
        measurement.tick()
        return measurement, now, cohort

    def test_pending_games_remain_invalid_at_original9000_deadline(self):
        controller, now, cohort = self.fixture()
        for elapsed in (5400, 7200, 8999):
            now[0] = 100+elapsed; value = controller.tick()
            self.assertFalse(value['complete']); self.assertIsNone(value['valid'])
            self.assertEqual(value['pending'], 2); self.assertEqual(value['started'], 65)
        now[0] = 9100; value = controller.tick()
        self.assertTrue(value['complete']); self.assertFalse(value['valid'])
        self.assertEqual(value['reason'], 'whole_cohort_timeout')
        self.assertEqual((value['count'], value['pending'], value['started']), (63, 2, 65))

    def test_all_admitted_games_can_complete_after_old7200_limit_before_new_deadline(self):
        controller, now, cohort = self.fixture()
        now[0] = 8500
        cohort.update(count=65, pending=0, complete=True)
        value = controller.tick()
        self.assertTrue(value['complete']); self.assertTrue(value['valid'])
        self.assertEqual(value['started'], value['count'])


if __name__ == '__main__':
    unittest.main()
