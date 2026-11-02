"""Actual combined followup authorization plus in-memory refusal contracts."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest

H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
import prepare_tail9000_followup_v3 as followup
G=H.parents[1]
R=G/'logs/managed-learning-20261015/run-26'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=load('profile06_followup_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
        cls.runtime=load('profile06_followup_archives',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
        cls.control=load('profile06_followup_control',H/'control_quality32_review_v1.py')
        cls.actual=cls.r.read_pin(cls.r.pin(R/'profile06-followup12-CPU-original01-preparation-20261020/source-selection-packet.json'))

    def setUp(self):
        self.pre=copy.deepcopy(self.actual);self.overrides={};self.shown={}
        self.reader=types.SimpleNamespace(pin=self.r.pin,read_pin=self.read,checked_module=self.r.checked_module)
        self.ctl=types.SimpleNamespace(show=lambda unit:self.shown[unit] if unit in self.shown else self.control.show(unit))

    def read(self,pin,as_json=True):
        if pin['path'] in self.overrides:
            value=self.overrides[pin['path']]
            return copy.deepcopy(value) if as_json else value
        return self.r.read_pin(pin,as_json=as_json)

    def mutate(self,pin,fn):
        value=self.read(pin);fn(value);self.overrides[pin['path']]=value

    def authorize(self):return followup.authorize(self.pre,self.reader,self.ctl,self.runtime)
    def refuse(self):
        with self.assertRaises((ValueError,KeyError)):self.authorize()

    def test_actual_combined_source_and_closed_invalid_original_rejoin_without_capture(self):
        value=self.authorize()
        self.assertEqual(value['source_authority']['bound_integration_tests'],113)
        self.assertEqual(value['source_authority']['full_handler_variants'],56)
        self.assertEqual(value['preceding_quality']['native_outcome'],'invalid')
        self.assertFalse(value['quality_qualified'] or value['candidate_captured'])

    def test_changed_authority_refused_before_import(self):
        self.pre['chain_authority_source']['sha256']='0'*64;self.refuse()

    def test_unbound_old_campaign_preparer_cannot_enter_new_followup(self):
        sources=self.pre['selected_sources'];sources['prepare_quality32_campaign_v5.py']=sources.pop('prepare_quality32_campaign_v7.py')
        self.refuse()

    def test_authority_self_tests_cannot_be_missing_a_case(self):
        proof=self.read(self.pre['chain_authority_CPU_readback'])
        self.mutate(proof['actual_tests'],lambda value:value.update(tests=17));self.refuse()

    def test_nonzero_original_authority_CPU_cannot_authorize_followup(self):
        proof=self.read(self.pre['chain_authority_CPU_readback'])
        self.mutate(proof['original_closure'],lambda value:value.update(original_exit=1));self.refuse()

    def test_original_authority_console_cannot_be_replaced(self):
        proof=self.read(self.pre['chain_authority_CPU_readback'])
        self.overrides[proof['consoles']['stdout']['archive']['path']]=b'{"status":"PASS"}\n';self.refuse()

    def test_changed_current_predecessor_gate_refused_before_import(self):
        self.pre['closed_predecessor_gate_source']['sha256']='f'*64;self.refuse()

    def test_unclosed_current_scientific_study_blocks_followup(self):
        bundle=self.read(self.pre['preceding_quality_bundle'])
        self.mutate(bundle['disposition'],lambda value:value.update(quality_campaign_closed=False));self.refuse()

    def test_original_current_predecessor_unit_must_still_be_absent(self):
        bundle=self.read(self.pre['preceding_quality_bundle']);owner=self.read(bundle['native_owner'])
        self.shown[owner['unit']]=dict(Id=owner['unit'],LoadState='loaded');self.refuse()

    def test_default_entry_is_inert(self):
        result=subprocess.run([sys.executable,'-I','-B',followup.__file__],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0);self.assertTrue(result.stdout.startswith('PLAN_ONLY:'));self.assertEqual(result.stderr,'')

    def test_wrong_precommit_SHA_refused_before_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'tested-followup-precommit.json';path.write_text('{}\n');path.chmod(0o444)
            with self.assertRaisesRegex(ValueError,'Exact tested root precommit'):followup.run('CPU',path,'0'*64)

    def test_authority_refusal_precedes_window_read_or_metadata_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);pre=copy.deepcopy(self.pre)
            pre.update(schema='robotron-supervised-quality32-followup-precommit-v1',
                protocol_id='prospective-tail9000-joint-profile06-v1',preparer=self.r.pin(followup.__file__),
                quality_precommit=dict(same_fixed_admission_s=5400,same_whole_cohort_timeout_s=9000),
                CPU_controller=self.r.pin(H/'control_quality32_review_v1.py'),
                archive_checker=self.r.pin(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),
                window_job=dict(path=str(root/'must-not-read-window.json')),CPU_preparation=str(root/'must-not-create-output'))
            pre['chain_authority_source']['sha256']='0'*64
            path=root/'tested-followup-precommit.json';path.write_text(json.dumps(pre));path.chmod(0o444)
            with self.assertRaisesRegex(ValueError,'Exact tested combined source authority'):
                followup.run('CPU',path,self.r.pin(path)['sha256'])
            self.assertFalse((root/'must-not-create-output').exists())


if __name__=='__main__':
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='';time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(name.startswith('dqn.') for name in sys.modules)
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        actual_candidate_captured=False,actual_quality_run=False,scientific_review_rerun=False,
        numerical_runtime_imported=False,source_selected_for_science=False)),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun==12 and not result.skipped else 1)
