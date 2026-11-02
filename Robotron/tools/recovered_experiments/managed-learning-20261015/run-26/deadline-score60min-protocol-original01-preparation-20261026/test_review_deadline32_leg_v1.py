"""Actual historical source-context joins into selected4260; no native outcomes."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_deadline_real_reviewer',HERE/'review_deadline32_leg_v1.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
OLD=HERE.parent/'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/evaluator-count-active600-counterbalanced-engineering-original06/future-startup-slot64-chain-correction-original01/cold-prefix-preparation05-original01/job.json'
DERIVATION=HERE/'observer-bound4260-family-original01/source-derivation-direct-historical-v2.json'


def read(pin,as_json=True):
    raw=Path(pin['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Actual test context pin differs')
    return json.loads(raw) if as_json else raw


class Tests(unittest.TestCase):
    def fixture(self):
        old=json.loads(OLD.read_text());family=read(old['source_family_manifest'])
        raw=DERIVATION.read_bytes();pin=dict(path=str(DERIVATION),sha256=hashlib.sha256(raw).hexdigest())
        family['main_observer']=json.loads(raw)['selected_sources'];family['observer_bound4260_derivation']=pin
        return family

    def test_full_real_historical_context_to_selected4260(self):
        result=review.validate_protocol_provenance(self.fixture(),read)
        self.assertTrue(result['all_historical_derivations_and_retained_function_AST_verified'])
        bridge=result['observer4260_historical_to_selected_bridge']
        self.assertTrue(bridge['health_and_protocol_algorithms_unchanged'])
        self.assertNotEqual(bridge['historical_sources']['worker']['sha256'],bridge['selected_bounded4260_sources']['worker']['sha256'])

    def test_wrong_historical_or_selected_node_and_bounds_scope_rejected(self):
        family=self.fixture();proof=read(family['coalescing_observer_component_CPU']);historical=read(proof['component_family'])
        for damage in ('historical','selected','bounds','extra_source_change'):
            f=copy.deepcopy(family);h=copy.deepcopy(historical)
            if damage=='historical':h['main_observer']=copy.deepcopy(f['main_observer'])
            elif damage=='selected':f['main_observer']=copy.deepcopy(h['main_observer'])
            def altered(pin,as_json=True):
                value=read(pin,as_json)
                if damage=='bounds' and pin['path']==str(DERIVATION):value['bounds']['observer_cpu_cores']=3
                if damage=='extra_source_change' and not as_json and pin['path']==family['main_observer']['worker']['path']:
                    value+=b'\n# Unselected functional-source alteration\n'
                return value
            with self.subTest(damage=damage),self.assertRaises(AssertionError):
                review.validate_observer4260_derivation(h,f,altered)

    def test_actual_controller_reduced_pin_shape_is_preserved(self):
        path=HERE/'control_deadline32_leg_v1.py'
        control=review.load(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()),'_deadline_actual_control_pin_test')
        pin=control.pin(HERE/'deadline_score_report_v1.py')
        self.assertEqual(set(pin['identity']),{'device','inode','mode','uid','nlink'})
        self.assertTrue(review.validate_controller_pins(dict(pins=[pin]),control))
        bad=copy.deepcopy(pin);bad['identity']['mtime_ns']=Path(pin['path']).stat().st_mtime_ns
        with self.assertRaises(AssertionError):review.validate_controller_pins(dict(pins=[bad]),control)


if __name__=='__main__':unittest.main()
