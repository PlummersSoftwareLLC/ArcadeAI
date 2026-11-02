"""Exercise actual frozen entry/restore using bounded in-memory collaborators."""
import importlib.util
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

spec=importlib.util.spec_from_file_location('_deadline_lifecycle',Path(__file__).with_name('deadline_measurement_lifecycle_v2.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Agent:
    def __init__(self):
        self.training_enabled=False;self.behavior_locked=False;self._prefetch_paused=False
        self._training_lock=threading.Lock();self.training_steps=10;self.optimized_samples=40960
        self.memory=None;self.installs=0
    def _pause_prefetch(self):self._prefetch_paused=True
    def _resume_prefetch(self):self._prefetch_paused=False
    def capture_inference_policy(self):return {'unchanged_policy':True}
    def install_inference_policy(self,value):
        if value!={'unchanged_policy':True}:raise ValueError('Unexpected policy')
        self.installs+=1


class Tests(unittest.TestCase):
    def fixture(self):
        agent=Agent();metrics=SimpleNamespace(lock=threading.Lock(),training_enabled=False,
            measurement_active=False,measurement_generation=0,measurement_label='',ratchet_frozen=False,
            total_training_steps=10,total_optimized_samples=40960,learner_frame_count=3000000000)
        calls=[]
        def cohort(*args):
            calls.append(args);return dict(complete=False,valid=True,abandoned=0,pending=0)
        journal=SimpleNamespace(cohort_status=cohort)
        boundary=dict(ready=False,active=True,generation=1,requested_generation=1,clients=32,expected=32,
            acknowledged=32,actor_slots=module.SLOTS,pending_client_ids=[],replay_pending_client_ids=[])
        value=module.DeadlineMeasurementLifecycle(agent,metrics,journal,boundary_status=lambda _:dict(boundary),clock=lambda:100)
        return value,agent,metrics,boundary,calls

    def test_partial_raw_ready_keeps_frozen_tick_warming_and_clock_validation(self):
        value,agent,metrics,boundary,calls=self.fixture();value.enter('new-deadline-leg')
        boundary.update(ready=True,clients=3,expected=3,acknowledged=3,actor_slots=module.SLOTS[:3])
        self.assertIsNone(value.admit_when_ready())
        self.assertEqual(value.origin.phase,'warming');self.assertIsNone(value.origin.start_ts)
        self.assertEqual(value.origin.status()['boundary']['clients'],3)
        self.assertFalse(value.origin.status()['boundary']['ready'])
        self.assertTrue(boundary['ready'])  # Raw callback is never mutated.
        self.assertEqual(calls,[])
        metrics.total_training_steps+=1
        with self.assertRaisesRegex(ValueError,'Entry barrier failed'):value.admit_when_ready()
        self.assertEqual(value.origin.status()['reason'],'training_or_learner_clock_moved')

    def test_real_entry_and_restore_without_complete_game_judgment(self):
        value,agent,metrics,boundary,calls=self.fixture();value.enter('new-deadline-leg')
        self.assertTrue(metrics.measurement_active);self.assertTrue(agent.behavior_locked)
        self.assertIsNone(value.admit_when_ready());boundary['ready']=True
        window=value.admit_when_ready()
        self.assertEqual(window,dict(open_unix_ns=100000000000,close_unix_ns=400000000000,generation=1,experiment='new-deadline-leg'))
        for _ in range(5):value.admit_when_ready();value.guard()
        self.assertEqual(len(calls),1)  # Historical completion tick is never repeated.
        value.mark_sealed({'path':'/source-only-fixture/seal','sha256':'a'*64})
        result=value.exit(all_original_threads_stopped=True)
        self.assertTrue(result['metric_sealed']);self.assertFalse(result['measurement_active_after'])
        self.assertFalse(result['owns_mode_after']);self.assertFalse(agent.behavior_locked)
        self.assertFalse(result['frozen_entry_controller_before_restore']['complete'])
        self.assertEqual(agent.installs,2)

    def test_actual_boundary_and_frozen_clock_guard_remain_strict(self):
        value,agent,metrics,boundary,calls=self.fixture();value.enter('new-deadline-leg');boundary['ready']=True;value.admit_when_ready()
        for key,bad in [('clients',31),('expected',31),('acknowledged',31),('active',False),('requested_generation',2),('actor_slots',module.SLOTS[:-1]),('pending_client_ids',[1])]:
            old=boundary[key];boundary[key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):value.guard()
            boundary[key]=old
        metrics.total_training_steps+=1
        with self.assertRaises(ValueError):value.guard()

    def test_failed_unsealed_scope_restores_but_never_fabricates_result(self):
        value,agent,metrics,boundary,calls=self.fixture();value.enter('new-deadline-leg')
        with self.assertRaises(ValueError):value.exit(all_original_threads_stopped=False)
        result=value.exit(all_original_threads_stopped=True)
        self.assertFalse(result['metric_sealed']);self.assertIsNone(result['original_cutoff_seal'])
        self.assertFalse(result['frozen_entry_controller_before_restore']['complete'])


if __name__=='__main__':unittest.main()
