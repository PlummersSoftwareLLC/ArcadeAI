"""Actual read-only followup authorization and in-memory refusal contracts."""
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
import prepare_tail9000_followup_v2 as followup
G=H.parents[1];R=G/'logs/managed-learning-20261015/run-26'

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=load('_followup2_CPU_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
        cls.runtime=load('_followup2_CPU_archives',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
        cls.control=load('_followup2_CPU_control',H/'control_quality32_review_v1.py')
        P=R/'final-authority-additive18-CPU-original01-preparation-20261020'
        scope=cls.r.read_pin(cls.r.pin(R/'final-authority-bound-chain38-CPU-original01-preparation-20261020/next-fresh-quality-source-authority-and-window-scope.json'))
        cls.actual=dict(chain_authority_source=cls.r.pin(H/'verify_final_authority_chain_v1.py'),
            source_authority_bundle=cls.r.pin(P/'source-authority-bundle.json'),
            chain_authority_CPU_readback=cls.r.pin(P/'root-original-additive18-independent-readback.json'),
            selected_sources=cls.r.read_pin(cls.r.pin(P/'selected-scientific-sources.json')),
            closed_predecessor_gate_source=cls.r.pin(G/'tools/evaluation_startup_proposal/startup_probe_core_v2.py'),
            main_guard_source=cls.r.pin(R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'),
            preceding_quality_bundle=scope['previous_science_closed_bundle'])

    def setUp(self):
        self.pre=copy.deepcopy(self.actual);self.overrides={};self.shown={}
        self.reader=types.SimpleNamespace(pin=self.r.pin,read_pin=self.read,checked_module=self.r.checked_module)
        self.ctl=types.SimpleNamespace(show=lambda unit:self.shown[unit] if unit in self.shown else self.control.show(unit))

    def read(self,pin,as_json=True):
        if pin['path'] in self.overrides:
            v=self.overrides[pin['path']]
            return copy.deepcopy(v) if as_json else (v if isinstance(v,bytes) else (json.dumps(v)+'\n').encode())
        return self.r.read_pin(pin,as_json=as_json)

    def mutate(self,pin,fn):
        v=self.read(pin);fn(v);self.overrides[pin['path']]=v

    def authorize(self):return followup.authorize(self.pre,self.reader,self.ctl,self.runtime)
    def refuse(self):
        with self.assertRaises((ValueError,KeyError)):self.authorize()

    def test_actual_source_authority_and_closed_failed_original_rejoin_without_capture(self):
        value=self.authorize()
        self.assertEqual(value['source_authority']['total_source_tests'],220)
        self.assertEqual(value['preceding_quality']['status'],'ORIGINAL_PREDECESSOR_CLOSED')
        self.assertFalse(value['quality_qualified'] or value['candidate_captured'])

    def test_changed_additive_authority_refused_before_import(self):
        self.pre['chain_authority_source']['sha256']='0'*64;self.refuse()

    def test_unbound_old_campaign_preparer_cannot_enter_new_followup(self):
        sources=self.pre['selected_sources'];sources['prepare_quality32_campaign_v4.py']=sources.pop('prepare_quality32_campaign_v5.py')
        self.refuse()

    def test_authority_self_tests_cannot_be_missing_one_case(self):
        self.mutate(self.pre['chain_authority_CPU_readback'],lambda v:v['actual_tests'].update(tests=17));self.refuse()

    def test_nonzero_original_authority_CPU_cannot_authorize_followup(self):
        proof=self.read(self.pre['chain_authority_CPU_readback'])
        self.mutate(proof['original_closure'],lambda v:v.update(original_exit=1));self.refuse()

    def test_original_authority_console_cannot_be_replaced(self):
        proof=self.read(self.pre['chain_authority_CPU_readback'])
        self.overrides[proof['consoles']['stdout']['path']]=b'{"successful":true}\n';self.refuse()

    def test_changed_predecessor_gate_refused_before_import(self):
        self.pre['closed_predecessor_gate_source']['sha256']='f'*64;self.refuse()

    def test_unclosed_preceding_scientific_study_blocks_followup(self):
        bundle=self.read(self.pre['preceding_quality_bundle'])
        self.mutate(bundle['disposition'],lambda v:v.update(quality_campaign_closed=False));self.refuse()

    def test_original_predecessor_unit_must_still_be_absent(self):
        bundle=self.read(self.pre['preceding_quality_bundle']);owner=self.read(bundle['native_owner'])
        self.shown[owner['unit']]=dict(Id=owner['unit'],LoadState='loaded');self.refuse()

    def test_default_entry_is_inert(self):
        r=subprocess.run([sys.executable,'-I','-B',followup.__file__],capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0);self.assertTrue(r.stdout.startswith('PLAN_ONLY:'));self.assertEqual(r.stderr,'')

    def test_wrong_precommit_SHA_refused_before_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'tested-followup-precommit.json';path.write_text('{}\n');path.chmod(0o444)
            with self.assertRaisesRegex(ValueError,'Exact tested root precommit'):
                followup.run('CPU',path,'0'*64)

    def test_authority_refusal_happens_before_window_read_or_assembly_output(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);pre=copy.deepcopy(self.pre)
            pre.update(schema='robotron-supervised-quality32-followup-precommit-v1',
                protocol_id='prospective-tail9000-final-copy-v1',preparer=self.r.pin(followup.__file__),
                quality_precommit=dict(same_fixed_admission_s=5400,same_whole_cohort_timeout_s=9000),
                source_package=dict(sha256='3ee43f9bd95fdda8f02abc048999a84513da71125dfd6b2e6558f45d2de6caf9'),
                CPU_controller=self.r.pin(H/'control_quality32_review_v1.py'),
                archive_checker=self.r.pin(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),
                window_job=dict(path=str(directory/'must-not-read-window.json')),
                CPU_preparation=str(directory/'must-not-create-output'))
            pre['chain_authority_source']['sha256']='0'*64
            path=directory/'tested-followup-precommit.json';path.write_text(json.dumps(pre));path.chmod(0o444)
            with self.assertRaisesRegex(ValueError,'Exact tested additive source authority'):
                followup.run('CPU',path,self.r.pin(path)['sha256'])
            self.assertFalse((directory/'must-not-create-output').exists())

if __name__=='__main__':
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='';time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-final-authority-followup2-CPU-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),successful=result.wasSuccessful(),
        actual_candidate_captured=False,actual_quality_run=False,scientific_review_rerun=False)),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun==12 and not result.skipped else 1)
