"""Exercise actual guard close-path wiring with explicit fake review scheduling.

Only synthetic temporary files are used. No real cohort, review, model, emulator,
device or service is queried, scheduled or promoted by these tests.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import quality32_runtime_guard_v6 as guard


class ClosePathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        path=guard.GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
            'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
        spec=importlib.util.spec_from_file_location('_close_path_reader_'+str(time.time_ns()),path)
        self.reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.reader)
        self.campaign=self.root/'synthetic-campaign';self.campaign.mkdir(mode=0o700)
        self.originals={}
        for kind in ('status','summary'):
            path=self.campaign/(kind+'.json')
            path.write_bytes(b'{ "synthetic": true, "spacing": [1, 2] }\n')
            path.chmod(0o664);self.originals[kind]=self.reader.pin(path)
        cls=guard.guard_class(types.SimpleNamespace(MainGuard=object))
        self.subject=object.__new__(cls)
        obj=self.subject;obj.reader=self.reader;obj.finished=True;obj.review_attempted=False;obj.failed=None
        obj.binding_dir=self.root/'binding';obj.binding_dir.mkdir(mode=0o700)
        obj.config=dict(output=str(self.root/'controller'))
        Path(obj.config['output']).mkdir(mode=0o700)
        obj.save=self.put
        obj.binding_entry=self.put(self.root/'binding-input.json',{})
        obj.owner_entry=self.put(self.root/'native-owner.json',{})
        obj.config_pin=self.put(self.root/'native-config.json',obj.config)
        obj.main_entry=self.put(self.root/'main.json',{})
        obj.main_manifest=self.put(self.root/'main-manifest.json',{})
        obj.birth_entry=self.put(self.root/'births.json',{})
        obj.actor_entry=self.put(self.root/'actors.json',{})
        closure=self.put(self.root/'native-closure.json',{})
        obj.review_job=dict(closed_context_path=str(obj.binding_dir/'closed-context.json'),
            runtime_paths=dict(pilot_closure=closure['path']))
        obj.job=dict(campaign_parameters=dict(directory=str(self.campaign)),
            review_output=str(self.root/'synthetic-review'),review_execution=str(self.root/'synthetic-execution'),
            review_unit='robotron-synthetic-close-path.service',
            reviewer_source=self.reader.pin(guard.REVIEWER),
            review_controller_source=self.reader.pin(HERE/'control_quality32_review_v1.py'),
            main_guard_source=self.put(self.root/'fake-main-guard.py',b'synthetic only'),
            lease_path='/synthetic/no-lease-read',lease_identity=dict(device=1,inode=1))
        self.selected=[];self.launched=[];self.observed=[]
        outer=self
        class FakeReviewControl:
            pin=staticmethod(outer.reader.pin)
            @staticmethod
            def checked_config(path):
                outer.selected.append(path)
                return outer.reader.read_pin(outer.reader.pin(path))
            @staticmethod
            def launch(path):outer.launched.append(path)
            @staticmethod
            def observe(path):
                outer.observed.append(path)
                out=Path(obj.job['review_execution']);out.mkdir(mode=0o700)
                report=Path(obj.job['review_output']);report.mkdir(mode=0o700)
                value=dict(lifecycle_complete=True,unit_released=True,original_exit=0)
                outer.put(out/'root-original-identity.json',dict(synthetic=True))
                outer.put(out/'root-original-result-and-owned-release.json',value)
                outer.put(report/'review.json',dict(valid=True,quality_qualified=False,promotion=False))
                return value
        def checked(name,entry):
            self.assertEqual(entry,obj.job['review_controller_source'])
            self.reader.read_pin(entry,as_json=False)
            return FakeReviewControl
        self.patches=[patch.object(self.reader,'checked_module',side_effect=checked),
            patch('subprocess.run',side_effect=AssertionError('No actual unit/query/scheduling in wiring test'))]
        for item in self.patches:item.start();self.addCleanup(item.stop)

    def put(self,path,value):
        raw=value if isinstance(value,bytes) else (json.dumps(value)+'\n').encode()
        with Path(path).open('xb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        return self.reader.pin(path)

    def test_actual_close_method_binds_immutable_copies_and_schedules_only_once(self):
        obj=self.subject
        result=obj.close_and_review(dict(lifecycle_complete=True,unit_released=True,original_exit=0))
        self.assertTrue(result['valid']);self.assertFalse(result['quality_qualified'])
        context=self.reader.read_pin(self.reader.pin(obj.review_job['closed_context_path']))
        for kind,before in self.originals.items():
            self.assertEqual(self.reader.pin(before['path']),before)
            entry=context[kind+'_final']
            self.assertEqual(entry['identity']['mode'],'0o444')
            self.assertNotEqual(entry['identity']['inode'],before['identity']['inode'])
            self.assertEqual(self.reader.read_pin(entry,as_json=False),Path(before['path']).read_bytes())
        self.assertEqual(len(self.launched),1);self.assertEqual(len(self.observed),1)
        self.assertTrue(obj.review_attempted)
        with self.assertRaisesRegex(ValueError,'one review attempt'):
            obj.close_and_review(dict(lifecycle_complete=True,unit_released=True,original_exit=0))
        self.assertEqual(len(self.launched),1)

    def test_unclosed_original_cannot_copy_authorities_or_schedule_review(self):
        for result in [dict(lifecycle_complete=False,unit_released=True,original_exit=0),
                       dict(lifecycle_complete=True,unit_released=False,original_exit=0)]:
            with self.assertRaisesRegex(ValueError,'Original native closure'):
                self.subject.close_and_review(result)
        self.assertEqual(list(self.subject.binding_dir.iterdir()),[])
        self.assertEqual(self.launched,[]);self.assertFalse(self.subject.review_attempted)

    def test_missing_original_binding_retains_failure_without_scheduling(self):
        self.subject.binding_entry=None
        result=self.subject.close_and_review(dict(lifecycle_complete=True,unit_released=True,original_exit=1))
        self.assertFalse(result['valid']);self.assertFalse(result['quality_qualified'])
        self.assertEqual(self.launched,[])
        saved=self.reader.read_pin(self.reader.pin(Path(self.subject.config['output'])/'root-controller-result.json'))
        self.assertEqual(saved['status'],'NO_PROSPECTIVE_BINDING_REVIEW_NOT_LAUNCHED')
        self.assertEqual(saved['original_native_exit'],1);self.assertFalse(saved['retry'])


if __name__=='__main__':
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClosePathTests))
    print(json.dumps(dict(schema='robotron-guard6-direct-close-path-CPU-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        actual_review_scheduling_substituted=True,original_scientific_review_rerun=False,
        actual_guard_selected=False,quality_qualified=False)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
