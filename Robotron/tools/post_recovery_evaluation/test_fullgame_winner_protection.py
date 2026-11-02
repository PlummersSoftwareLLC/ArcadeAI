"""Header/numerical boundaries and unchanged publisher fixtures; no real winner."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from . import protect_fullgame_winner as w


class ProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=w.pipeline();cls.h=cls.p.helpers()
        old=cls.p.read(cls.h.pin(cls.p.PARENT/'independent-campaign-assessment-original01/assessment.json'))
        cls.header=dict(schema='robotron-recovered-round-fullgame-study-assessment-v1',status='FOUR_ORIGINAL_COMPLETE_GAME_LEGS_QUALIFIED',
            full_game_quality_qualified=True,effective_complete_game_minimum=64,promotion=False,
            causal_learning_speed_gain_established=False,useful_throughput_gain_established=False,original_quota64_decision=old['decision'])

    def test_historical_numeric_header_is_only_an_engineering_gate_fixture(self):
        w.validate_assessment_header(copy.deepcopy(self.header),self.p)

    def test_screening_failure_incomplete_or_pooled_claim_cannot_authorize_protection(self):
        for fault in ('screen','failed','not_qualified','floor50','promotion','learning_speed','throughput','pooling','one_candidate','median','63_games','old_reference_roles'):
            report=copy.deepcopy(self.header);d=report['original_quota64_decision']
            if fault=='screen':report['schema']='robotron-round-screen-study-independent-assessment-v1'
            elif fault=='failed':report['status']='FAILED'
            elif fault=='not_qualified':report['full_game_quality_qualified']=False
            elif fault=='floor50':report['effective_complete_game_minimum']=50
            elif fault=='promotion':report['promotion']=True
            elif fault=='learning_speed':report['causal_learning_speed_gain_established']=True
            elif fault=='throughput':report['useful_throughput_gain_established']=True
            elif fault=='pooling':d['candidate_pool_used']=True
            elif fault=='one_candidate':d['independent_candidates']['C2']['passed']=False
            elif fault=='median':d['independent_candidates']['C2']['median_preserved']=False
            elif fault=='63_games':d['per_leg']['C2']['count']=63
            else:d['reference_roles']=['PREVIOUS_C1','PREVIOUS_C2']
            with self.subTest(fault=fault),self.assertRaises(ValueError):w.validate_assessment_header(report,self.p)

    def test_engineering_job_cannot_verify_or_execute_publication(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'engineering-job.json';pin=self.h.put(path,dict(schema='robotron-recovered-fullgame-winner-protection-job-v1',engineering_only=True))
            with self.assertRaisesRegex(ValueError,'Production original winner-protection'):w.verify(self.p.read(pin),pin)
            args=SimpleNamespace(job=path,job_sha256=pin['sha256'],source_sha256=self.h.pin(Path(w.__file__).resolve())['sha256'],publish=True)
            with self.assertRaisesRegex(ValueError,'Engineering or foreign jobs'):w.execute(args)

    def fixture(self,root):
        source=root/'original-source.bin';source.write_bytes(b'ENGINEERING ONLY: tiny publication fixture\n');source.chmod(0o444)
        destination=root/'protected';destination.mkdir()
        job=dict(label='engineering-fixture',destination=str(destination));jp=dict(path=str(root/'fixture-job.json'),sha256='0'*64)
        checked=dict(candidate_source=self.h.pin(source),evidence_sha256={str(source):self.h.pin(source)['sha256']},
            assessment=dict(all_candidate_gates_passed=True),engineering_fixture_only=True)
        module=w.publication_module(self.p,self.h)
        return module,job,jp,checked,source,destination

    def test_unchanged_atomic_publisher_copies_fixture_readonly_and_never_overwrites(self):
        with tempfile.TemporaryDirectory()as directory:
            module,job,jp,checked,source,destination=self.fixture(Path(directory));calls=[]
            def fixture_verify(*args):calls.append(True);return copy.deepcopy(checked)
            module.verify=fixture_verify
            result=module.publish(job,jp,None);final=Path(result['protected_checkpoint']);metadata=final.with_name(final.name+'.json')
            self.assertEqual(final.read_bytes(),source.read_bytes());self.assertEqual(len(calls),2)
            self.assertEqual(final.stat().st_mode & 0o777,0o444);self.assertEqual(metadata.stat().st_mode & 0o777,0o444)
            self.assertEqual(final.stat().st_nlink,1);self.assertEqual(metadata.stat().st_nlink,1)
            self.assertFalse(list(destination.glob('*.partial')))
            with self.assertRaisesRegex(ValueError,'Never overwrite or retry'):module.publish(job,jp,None)
            self.assertEqual(len(calls),2)

    def test_changed_verification_evidence_before_linking_leaves_no_published_fixture(self):
        with tempfile.TemporaryDirectory()as directory:
            module,job,jp,checked,source,destination=self.fixture(Path(directory));calls=[]
            def fixture_verify(*args):
                calls.append(True);value=copy.deepcopy(checked)
                if len(calls)==2:value['evidence_sha256']['changed']='f'*64
                return value
            module.verify=fixture_verify
            with self.assertRaisesRegex(ValueError,'Original evidence changed while copying'):module.publish(job,jp,None)
            self.assertEqual(list(destination.iterdir()),[])

    def test_failed_verification_cannot_create_a_protected_fixture(self):
        with tempfile.TemporaryDirectory()as directory:
            module,job,jp,checked,source,destination=self.fixture(Path(directory))
            def fail(*args):raise ValueError('Original scope invalid')
            module.verify=fail
            with self.assertRaisesRegex(ValueError,'Original scope invalid'):module.publish(job,jp,None)
            self.assertEqual(list(destination.iterdir()),[])


if __name__=='__main__':unittest.main()
