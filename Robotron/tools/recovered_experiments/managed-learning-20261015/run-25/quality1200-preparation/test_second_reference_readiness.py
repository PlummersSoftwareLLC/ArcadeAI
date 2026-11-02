"""Synthetic operational-proof and inert-entry tests; no runtime observations."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('second_reference_readiness',HERE/'audit_reference1200_second_readiness.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)

class SecondReadinessTests(unittest.TestCase):
    def proof(self):
        return dict(pass_=True,receipt_sha256='a'*64,
            checkpoint_sha256='5076199285752a8748ce9566bc74c6b67210a03ae7f04f132f92b786dea102da',
            checks=dict(private_owned_processes_listener_released=True,
                private_GPU0_context_released=True,loaded_sources_unchanged=True),
            owned_union=dict(remaining=[],processes=[dict(pid=123,start_ticks=456)]))
    def audit(self):
        value=self.proof();value['pass']=value.pop('pass_');return value
    def test_default_help_and_bad_pins_observe_nothing(self):
        with patch.object(helper,'execute',side_effect=AssertionError('Observed runtime')),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(helper.main([]),0)
            with self.assertRaises(SystemExit) as result:helper.main(['--help'])
            self.assertEqual(result.exception.code,0)
            with self.assertRaises(SystemExit):helper.main(['--check'])
    def test_positive_proof_whitelists_only_operational_fields(self):
        audit=self.audit();audit['mean']='MUST_NOT_USE';audit['games']='MUST_NOT_USE'
        value=helper.prior_cleanup(audit,'a'*64)
        self.assertEqual(value['owned_processes'],[dict(pid=123,start_ticks=456)])
        self.assertNotIn('mean',value);self.assertNotIn('games',value)
    def test_partial_false_or_wrong_identity_proof_rejects(self):
        for kind in ('pass','emptychecks','GPU','receipt','model','remaining','noprocess','boolpid','boolticks'):
            audit=self.audit()
            if kind=='pass':audit['pass']=False
            elif kind=='emptychecks':audit['checks']={}
            elif kind=='GPU':audit['checks']['private_GPU0_context_released']=False
            elif kind=='receipt':audit['receipt_sha256']='b'*64
            elif kind=='model':audit['checkpoint_sha256']='b'*64
            elif kind=='remaining':audit['owned_union']['remaining']=[123]
            elif kind=='noprocess':audit['owned_union']['processes']=[]
            elif kind=='boolpid':audit['owned_union']['processes'][0]['pid']=True
            else:audit['owned_union']['processes'][0]['start_ticks']=True
            with self.subTest(kind=kind),self.assertRaises(AssertionError):helper.prior_cleanup(audit,'a'*64)

if __name__=='__main__':unittest.main()
