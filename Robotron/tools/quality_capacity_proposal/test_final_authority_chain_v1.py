"""Actual archived source-proof positive; in-memory predicate refusal mutations.

No archived receipt, source, unit, model, game cohort or live process is changed.
Only the positive case performs fresh absence queries for the original units.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
import verify_final_authority_chain_v1 as authority
G=H.parents[1]
R=G/'logs/managed-learning-20261015/run-26'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader=load('_additive_CPU_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
        cls.archives=load('_additive_CPU_archives',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
        cls.control=load('_additive_CPU_control',H/'control_quality32_review_v1.py')
        cls.baseline=load('_additive_CPU_baseline',H/'verify_tail9000_chain_v1.py')
        path=R/'final-authority-bound-chain38-CPU-original01-preparation-20261020/next-fresh-quality-source-authority-and-window-scope.json'
        scope=cls.reader.read_pin(cls.reader.pin(path))
        cls.actual_bundle=dict(baseline_scope=scope['baseline_source_scope166'],normal13=scope['guard13'],
            close3=scope['guard_direct_close3'],bound38=scope['bound_chain38'])
        base=cls.reader.read_pin(cls.actual_bundle['baseline_scope'])
        cls.actual_selected=copy.deepcopy(base['selected_sources'])
        for old,(new,_) in authority.REPLACEMENTS.items():
            del cls.actual_selected[old];cls.actual_selected[new]=scope['new_scientific_source_bindings'][new]
        cls.pin_cache={}

    def setUp(self):
        self.bundle=copy.deepcopy(self.actual_bundle);self.selected=copy.deepcopy(self.actual_selected)
        self.overrides={};self.absent=lambda unit:True;self.input_failure=None

    def read(self,pin,as_json=True):
        if pin['path'] in self.overrides:
            value=self.overrides[pin['path']]
            if as_json:return copy.deepcopy(value)
            return value if isinstance(value,bytes) else (json.dumps(value)+'\n').encode()
        return self.reader.read_pin(pin,as_json=as_json)

    def mutate(self,pin,fn):
        value=self.read(pin);fn(value);self.overrides[pin['path']]=value;return value

    def check_input(self,pin):
        if pin['path']==self.input_failure:return False
        path=Path(pin['path']);s=path.stat()
        stamp=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_nlink)
        cached=self.pin_cache.get(pin['path'])
        if cached is None or cached[0]!=stamp:
            cached=(stamp,self.reader.pin(path));self.pin_cache[pin['path']]=cached
        return cached[1]==pin

    def run_authority(self):
        return authority.validate(self.bundle,self.selected,self.read,self.archives.archived_closure,
            self.absent,self.archives.duration_seconds,self.check_input,self.baseline.validate)

    def refuse(self):
        with self.assertRaises((ValueError,KeyError,TypeError)):self.run_authority()

    def normal(self):return self.read(self.bundle['normal13'])
    def bound(self):return self.read(self.bundle['bound38'])

    def test_actual_originals_rejoin220_tests_and_all36_unit_absences(self):
        self.absent=lambda unit:self.control.show(unit).get('LoadState')=='not-found'
        result=self.run_authority()
        self.assertEqual((result['baseline_tests'],result['added_tests'],result['total_source_tests']),(166,54,220))
        self.assertEqual(result['original_CPU_units'],36)
        self.assertEqual(result['selected_sources'],self.actual_selected)
        self.assertFalse(result['candidate_captured'] or result['quality_qualified'])

    def test_missing_original_proof_cannot_select_new_guard(self):
        del self.bundle['normal13'];self.refuse()

    def test_old_guard_cannot_be_relabelled_as_fixed_source(self):
        self.selected['quality32_runtime_guard_v6.py']['sha256']='0'*64;self.refuse()

    def test_unchanged_reviewer_cannot_be_replaced(self):
        self.selected['review_closed_quality32_v6.py']['sha256']='f'*64;self.refuse()

    def test_old_and_new_observers_cannot_both_be_selected(self):
        base=self.read(self.bundle['baseline_scope'])
        self.selected['quality32_runtime_guard_v5.py']=base['selected_sources']['quality32_runtime_guard_v5.py']
        self.refuse()

    def test_boolean_test_count_does_not_replace_actual_count(self):
        self.mutate(self.bundle['normal13'],lambda x:x.update(total_actual_tests=True));self.refuse()

    def test_missing_normal_producer_group_is_not_pooled_away(self):
        self.mutate(self.bundle['normal13'],lambda x:x['groups'].pop());self.refuse()

    def test_nonzero_original_CPU_cannot_be_relabelled_PASS(self):
        pin=self.normal()['groups'][0]['closure']
        self.mutate(pin,lambda x:x.update(original_exit=1));self.refuse()

    def test_missing_original_archive_descriptor_is_refused(self):
        pin=self.normal()['groups'][0]['closure']
        self.mutate(pin,lambda x:x['full_original_archives'].pop());self.refuse()

    def test_reused_original_CPU_owner_is_refused(self):
        self.mutate(self.bundle['normal13'],lambda x:x['groups'][1].update(owner=x['groups'][0]['owner']))
        self.refuse()

    def test_selected_worker_command_must_match_actual_archive(self):
        plan=self.read(self.normal()['prospective_plan']);pin=plan['configs']['A']
        self.mutate(pin,lambda x:x['argv'].__setitem__(-1,'B'));self.refuse()

    def test_original_console_must_match_reported_PASS(self):
        self.mutate(self.bundle['normal13'],lambda x:x['groups'][0]['result'].update(unjoined_marker='tampered'))
        self.refuse()

    def test_live_original_unit_blocks_acquisition_authority(self):
        owner=self.read(self.normal()['groups'][0]['owner'])
        self.absent=lambda unit:unit!=owner['unit'];self.refuse()

    def test_changed_prospective_input_blocks_authority(self):
        self.input_failure=self.selected['quality32_runtime_guard_v6.py']['path'];self.refuse()

    def test_new_source_must_be_bound_to_actual_test_inputs(self):
        proof=self.bound();pin=proof['plan'];name=self.selected['prepare_quality32_campaign_v5.py']['path']
        self.mutate(pin,lambda x:x.update(input_fullpins=[e for e in x['input_fullpins'] if e['path']!=name]))
        self.refuse()

    def test_missing_bound_source_test_group_is_refused(self):
        self.mutate(self.bundle['bound38'],lambda x:x['groups'].pop('campaign9'));self.refuse()

    def test_captured_candidate_cannot_be_presented_as_prospective_authority(self):
        self.mutate(self.bundle['bound38'],lambda x:x.update(actual_candidate_captured=True));self.refuse()

    def test_scientific_review_retry_cannot_be_copy_fix_evidence(self):
        self.mutate(self.bundle['close3'],lambda x:x.update(original_scientific_review_retried=True));self.refuse()

if __name__=='__main__':
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-additive-final-authority-CPU-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),successful=result.wasSuccessful(),
        actual_source_authority_positive_uses_original_archives=True,actual_quality_run=False,
        actual_candidate_captured=False,numerical_runtime_imported=False)),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun==18 and not result.skipped else 1)
