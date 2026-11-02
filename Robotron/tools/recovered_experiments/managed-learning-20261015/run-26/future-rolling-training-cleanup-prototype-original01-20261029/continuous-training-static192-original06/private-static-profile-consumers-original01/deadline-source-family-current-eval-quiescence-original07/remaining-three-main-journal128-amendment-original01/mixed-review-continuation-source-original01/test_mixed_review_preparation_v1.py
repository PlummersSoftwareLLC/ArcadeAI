"""Actual current original-leg rejection and immutable review ABI regressions."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

import importlib.util
_spec=importlib.util.spec_from_file_location('_actual_launcher_review_preparer',Path(__file__).with_name('prepare_mixed_main_journal128_reviews_v1.py'))
p=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(p)


class DeadlineReviewPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h, read = p.dependencies()
        cls.read = staticmethod(read)
        cls.precommit = Path(os.environ['ROBOTRON_DEADLINE_REVIEW_TEST_PRECOMMIT'])
        cls.packet = cls.read(cls.h.pin(cls.precommit))
        cls.prepared = cls.read(cls.packet['native_prepared'])
        cls.study = cls.read(cls.prepared['study_precommit'])
        cls.wrapper = cls.read(cls.packet['capacity_preparation'])
        cls.original = cls.read(cls.prepared['original_manifest'])
        cls.old_review = cls.read(cls.packet['retained_R1']['precommit'])
        cls.amendment = cls.read(cls.packet['capacity_amendment'])
        cls.publication = cls.read(cls.packet['CPU_guard_publication'])

    def test_actual_four_original_jobs_and_review_sources(self):
        p.validate_manifest(self.prepared, self.study)
        sources = self.packet['sources']
        control = p.load('_test_deadline_review_controller', self.h.checked(sources['controller']))
        for leg in p.ORDER:
            h, read, pp, packet, case = p.selected(self.precommit, leg)
            job = read(case['native_job'])
            family = read(job['source_family_manifest'])
            self.assertEqual(case['reviewer'], family['reviewer'])
            self.assertEqual(case['leg'], job['leg'])
            config = dict(unit='robotron-deadline-review-interface-test.service',
                          output='/unused-original-review-test',argv=['/usr/bin/python3.12','-I','-B',case['reviewer']['path']],
                          properties=p.PROPERTIES,observation_s=2040,pins=[])
            # Exercise the actual controller's exact six-field/resource ABI.
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'config.json';path.write_text(json.dumps(config))
                self.assertEqual(control.checked_config(path),config)
                config['properties']=[v.replace('1980','600') for v in config['properties']]
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError): control.checked_config(path)

    def test_retained_R1_is_read_only_and_future_legs_create_no_review_artifacts(self):
        target=Path(self.packet['retained_R1']['qualification']['path'])
        before=self.h.pin(target)
        self.assertEqual(p.original_R1_verification(),self.packet['retained_R1']['qualification'])
        for method in (p.prepare_leg,p.qualify):
            with self.assertRaises(ValueError):method(self.precommit,'R1')
        self.assertEqual(self.h.pin(target),before)
        for leg in p.FUTURE:
            case=self.packet['cases'][p.ORDER.index(leg)]
            paths=[Path(case[key])for key in ('review_job_path','review_config_path','execution','report')]
            paths.append(Path(case['native_job']['path']).parent/'independent-review-prepared-original01.json')
            self.assertFalse(any(path.exists()for path in paths))
            with self.assertRaises((FileNotFoundError,ValueError)):p.prepare_leg(self.precommit,leg)
            self.assertFalse(any(path.exists()for path in paths))

    def test_no_report_or_unobserved_exit_can_qualify_any_leg(self):
        for leg in p.FUTURE:
            root = Path(self.packet['cases'][p.ORDER.index(leg)]['native_job']['path']).parent
            target = root/('root-'+leg+'-independent-qualified.json')
            with self.assertRaises((FileNotFoundError,ValueError)):
                p.qualify(self.precommit,leg)
            self.assertFalse(target.exists())

    def test_engineering_reordered_and_changed_denominators_are_rejected(self):
        mutations = [('prepared','engineering_only',True),('study','engineering_only',True),
                     ('study','no_retry',False),('study','horizon_ns',3599_000_000_000),
                     ('study','n_scored_per_leg',31),('study','promotion',True),
                     ('study','full_game_quality_qualified',True),('study','improvement_qualified',True),
                     ('prepared','ordered_legs',['C1','R1','R2','C2'])]
        for where,key,value in mutations:
            prepared=copy.deepcopy(self.prepared);study=copy.deepcopy(self.study)
            (prepared if where=='prepared' else study)[key]=value
            with self.assertRaises(ValueError,msg=(where,key)):
                p.validate_manifest(prepared,study)
        prepared=copy.deepcopy(self.prepared);prepared['cases'][0],prepared['cases'][1]=prepared['cases'][1],prepared['cases'][0]
        with self.assertRaises(ValueError): p.validate_manifest(prepared,self.study)
        p.validate_mixed_identity(self.wrapper,self.prepared,self.original,self.old_review,self.amendment)
        for name in ('R1qualification','R1row','commonstudy','futureorder','scientificflag'):
            wrapper=copy.deepcopy(self.wrapper);prepared=copy.deepcopy(self.prepared);amendment=copy.deepcopy(self.amendment)
            if name=='R1qualification':wrapper['original_R1_qualification']={}
            elif name=='R1row':prepared['cases'][0]['native_job']={}
            elif name=='commonstudy':prepared['study_precommit']={}
            elif name=='futureorder':amendment['future_legs']=['R2','C1','C2']
            else:amendment['scientific_fields_unchanged']=False
            with self.assertRaises(ValueError,msg=name):p.validate_mixed_identity(wrapper,prepared,self.original,self.old_review,amendment)
        p.validate_three_publication(self.publication)
        for key,value in (('schema','robotron-four-exact-native-guard-publication-v1'),('ordered_legs',p.ORDER),
                          ('old_exact_job_receipts_reused',True),('guards',self.publication['guards'][:2]),('status','FAIL')):
            publication=copy.deepcopy(self.publication);publication[key]=value
            with self.assertRaises(ValueError,msg=key):p.validate_three_publication(publication)


    def test_unknown_leg_and_default_invocation_are_inert(self):
        with self.assertRaises(ValueError):p.selected(self.precommit,'C3')
        result=subprocess.run(['/usr/bin/python3','-I','-B',str(Path(p.__file__))],
                              capture_output=True,text=True,timeout=10,check=True)
        self.assertEqual(result.stdout.strip(),'PLAN_ONLY_NO_READS_OR_ACTIONS')

    def test_actual_historical_six_descriptor_reader_positional_ABI(self):
        # Retained original R1 is a reader regression, never a new result.
        qualification=self.read(self.packet['retained_R1']['qualification'])
        owner=self.read(qualification['review_owner']);closure=self.read(qualification['review_closure'])
        archive=p.load('_test_deadline_review_historical_archive',self.h.checked(self.packet['sources']['archive']))
        fields=archive.archived_closure(closure,owner,self.read,exit_zero=True)
        self.assertEqual(fields['ExecMainStatus'],'0')
        self.assertEqual(fields['InvocationID'],owner['invocation_id'])


if __name__ == '__main__':unittest.main()
