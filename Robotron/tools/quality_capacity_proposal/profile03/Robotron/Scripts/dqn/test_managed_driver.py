import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from .managed_driver import ManagedMeasurementDriver, consume_save_request


class Agent:
    def __init__(self): self.saves=[]
    def save(self, path, **kwargs):
        Path(path).write_text('checkpoint')
        self.saves.append(path)


class Controller:
    def __init__(self, *args, **kwargs):
        self.entered=[];self.exits=0;self.fail=False;self.fail_restore=False
    def enter(self,label,**kwargs): self.entered.append(label)
    def tick(self): return dict(complete=True,valid=True,active=True,count=42)
    def status(self): return dict(complete=False,active=True,valid=None,
                                  label=self.entered[-1] if self.entered else None,
                                  started=3,pending=2,cohort=dict(rows=[dict(score=7)]))
    def exit(self):
        if self.fail_restore: raise RuntimeError('restore failed')
        self.exits+=1


class ManagedDriverTests(unittest.TestCase):
    def test_completed_request_is_not_repeated_after_process_restart(self):
        with tempfile.TemporaryDirectory() as root:
            agent=Agent();metrics=SimpleNamespace();server=SimpleNamespace(game_journal=None,measurement_boundary_status=None)
            driver=ManagedMeasurementDriver(agent,metrics,server,root,Controller)
            request=dict(label='test-policy',cohort_s=120,timeout_s=600)
            driver.update(request);driver.update(request);driver.update(request)
            self.assertEqual(driver.controller.entered,['test-policy'])
            self.assertEqual(driver.controller.exits,1)
            receipt=json.loads((Path(root)/'managed-measurements/test-policy.json').read_text())
            self.assertTrue(receipt['valid']);self.assertFalse(receipt['active'])
            resumed=ManagedMeasurementDriver(agent,metrics,server,root,Controller)
            resumed.update(request)
            self.assertEqual(resumed.controller.entered,[])

    def test_failed_restoration_never_publishes_success_or_marks_handled(self):
        with tempfile.TemporaryDirectory() as root:
            driver=ManagedMeasurementDriver(Agent(),SimpleNamespace(),SimpleNamespace(game_journal=None,measurement_boundary_status=None),root,Controller)
            request=dict(label='failed-restore')
            driver.update(request);driver.controller.fail_restore=True
            with self.assertRaisesRegex(RuntimeError,'restore failed'): driver.update(request)
            self.assertNotIn('failed-restore',driver.handled)
            self.assertFalse(driver.metrics.managed_measurement_status['valid'])
            self.assertFalse((Path(root)/'managed-measurements/failed-restore.json').exists())

    def test_cancelled_receipt_keeps_pending_cohort_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            driver=ManagedMeasurementDriver(Agent(),SimpleNamespace(),SimpleNamespace(game_journal=None,measurement_boundary_status=None),root,Controller)
            driver.update(dict(label='cancelled'))
            driver.update(None)
            receipt=json.loads((Path(root)/'managed-measurements/cancelled.json').read_text())
            self.assertFalse(receipt['valid'])
            self.assertEqual(receipt['reason'],'cancelled')
            self.assertEqual(receipt['pending'],2)
            self.assertEqual(receipt['cohort']['rows'],[dict(score=7)])

    def test_invalid_save_request_does_not_stop_training(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'managed_save.request.json'
            path.write_text(json.dumps(dict(tag='../wrong')))
            self.assertFalse(consume_save_request(Agent(),root))
            self.assertTrue(Path(str(path)+'.failed').exists())
            path.write_text(json.dumps(dict(tag='good')))
            agent=Agent();self.assertTrue(consume_save_request(agent,root))
            self.assertEqual(len(agent.saves),1)


if __name__=='__main__': unittest.main()
