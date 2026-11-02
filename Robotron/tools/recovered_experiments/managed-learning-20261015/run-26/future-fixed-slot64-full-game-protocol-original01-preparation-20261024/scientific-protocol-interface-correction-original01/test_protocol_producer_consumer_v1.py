"""Original mismatch replay and synthetic startup stopped before any worker/policy."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true'); p.add_argument('--job')
    p.add_argument('--job-sha256'); p.add_argument('--source-sha256'); a = p.parse_args()
    if not a.execute: print('PLAN_ONLY'); return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == a.source_sha256
    raw = Path(a.job).read_bytes(); assert hashlib.sha256(raw).hexdigest() == a.job_sha256
    job = json.loads(raw); assert job['schema'] == 'robotron-quota64-protocol-interface-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''

    def load(name, pin):
        path = Path(pin['path']); assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module); return module

    h = load('_interface_h', job['helpers']); reader = load('_interface_r', job['reader'])
    for pin in job['inputs']: h.checked(pin)
    read = lambda pin: reader.read_pin(pin)
    native = load('_interface_native', job['native'])
    preparer = load('_interface_preparer', job['preparer'])
    original = read(job['original_native_job'])
    protocol = read(original['main_health_protocol']); family = read(original['source_family_manifest'])
    output = Path(job['output']); output.mkdir(mode=0o700)
    negatives = []; startup = None

    class Contracts(unittest.TestCase):
        def test_01_native_predicate_is_extracted_without_any_relaxation(self):
            tree = ast.parse(h.checked(job['original_native_source']).read_text())
            statements = [node for node in ast.walk(tree) if isinstance(node, ast.Expr)
                          and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                          and node.value.func.id == 'require' and len(node.value.args) > 1
                          and isinstance(node.value.args[1], ast.Constant)
                          and node.value.args[1].value == 'Exact prospective main-health engine/dependencies/family/binding required']
            self.assertEqual(len(statements), 1)
            tree = ast.parse(h.checked(job['native']).read_text())
            helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'validate_main_health_contract')
            self.assertEqual(ast.dump(helper.body[1]), ast.dump(statements[0]))

        def test_02_actual_original_protocol_fails_and_corrected_builder_passes(self):
            self.assertEqual(protocol['schema'], 'robotron-native-dedicated-main-health-protocol-v5')
            with self.assertRaisesRegex(ValueError, 'Exact prospective main-health'): native.validate_main_health_contract(original, protocol, family)
            negatives.append('exact-original-protocol-mismatch')
            correct = preparer.make_main_health_protocol(protocol['prior_case'], protocol['health_job'])
            self.assertEqual(correct, dict(protocol, schema='robotron-native-quota64-dedicated-main-health-protocol-v1'))
            native.validate_main_health_contract(original, correct, family)

        def test_03_binding_source_and_observer_mismatches_still_fail(self):
            correct = preparer.make_main_health_protocol(protocol['prior_case'], protocol['health_job'])
            cases = []
            wrong = copy.deepcopy(correct); wrong['health_job']['binding'] = {}; cases.append(('binding', wrong, family))
            wrong = copy.deepcopy(correct); wrong['health_job']['sources'].pop('transport'); cases.append(('missing-source', wrong, family))
            wrong = copy.deepcopy(correct); wrong['health_job']['sources']['transport']['sha256'] = '0' * 64; cases.append(('source-sha', wrong, family))
            wrong = copy.deepcopy(family); wrong['runtime'] = {}; cases.append(('family-runtime', correct, wrong))
            for key in ('main_prefix_validator', 'main_health_finalizer'):
                wrong = copy.deepcopy(family); wrong[key]['sha256'] = '0' * 64; cases.append((key, correct, wrong))
            wrong = copy.deepcopy(family); wrong['main_observer'].pop('worker'); cases.append(('observer-missing', correct, wrong))
            wrong = copy.deepcopy(family); wrong['main_observer']['worker']['sha256'] = '0' * 64; cases.append(('observer-sha', correct, wrong))
            for label, candidate_protocol, candidate_family in cases:
                with self.assertRaisesRegex(ValueError, 'Exact prospective main-health'):
                    native.validate_main_health_contract(original, candidate_protocol, candidate_family)
                negatives.append(label)

        def test_04_unbound_sources_require_policy_clocks_after_the_failed3041_case(self):
            expected = dict(learner_frame_count=3041579470, training_steps=11979944,
                            optimized_samples=47494055936, frame_count=5918642727)
            self.assertEqual(native.NEW_CANDIDATE_CLOCK_FLOOR, expected)
            self.assertEqual(preparer.NEW_CANDIDATE_CLOCK_FLOOR, expected)
            self.assertEqual(native.PAIR_SHA, '0' * 64); self.assertEqual(preparer.PAIR_SHA, '0' * 64)
            with self.assertRaisesRegex(ValueError, 'UNBOUND'): native.validate_job({})
            negatives.append('unbound-cannot-launch')

        def test_05_actual_new_native_initialization_reaches_only_injected_no_worker_stop(self):
            nonlocal startup
            saved = native.PAIR_SHA, native.CAPACITY_PROOF_SHA, copy.deepcopy(native.POLICIES), native.load
            called = []

            class NoPrivateWork(Exception): pass
            class Client:
                @staticmethod
                def DedicatedMainHealth(*args, **kwargs):
                    called.append('before-worker-policy-Torch-MAME')
                    raise NoPrivateWork('EXPLICIT_SYNTHETIC_STOP_BEFORE_ANY_WORKER_POLICY_TORCH_OR_MAME')

            try:
                native.PAIR_SHA = 'a' * 64; native.CAPACITY_PROOF_SHA = job['capacity']['sha256']
                native.POLICIES['candidate'] = dict(sha256='f' * 64,
                    clocks={key: value + 1 for key, value in native.NEW_CANDIDATE_CLOCK_FLOOR.items()})
                data = copy.deepcopy(original)
                data.update(output=str(output / 'explicit-synthetic-native-initialization'),
                            runtime=job['native'], quality_pair_precommit=dict(sha256=native.PAIR_SHA))
                synthetic_family = dict(family, runtime=job['native'])
                fp = h.put(output / 'explicit-synthetic-family.json', synthetic_family)
                pp = h.put(output / 'corrected-protocol-same-original-health-inputs.json',
                           preparer.make_main_health_protocol(protocol['prior_case'], protocol['health_job']))
                data.update(source_family_manifest=fp, main_health_protocol=pp)
                data['inputs'] += [fp, pp, job['native'], job['preparer']]
                jp = h.put(output / 'explicit-synthetic-native-job.json', data)
                original_loader = native.load
                def controlled_load(name, path):
                    if name == '_compiled32_dedicated_main_health_client': return Client
                    return original_loader(name, path)
                native.load = controlled_load
                self.assertEqual(native.run(data, jp, h), 1)
                result_pin = h.pin(Path(data['output']) / 'result.json'); result = read(result_pin)
                self.assertEqual(called, ['before-worker-policy-Torch-MAME'])
                self.assertEqual(result['errors'], ["NoPrivateWork('EXPLICIT_SYNTHETIC_STOP_BEFORE_ANY_WORKER_POLICY_TORCH_OR_MAME')"])
                self.assertEqual(result['original_slots'], {}); self.assertEqual(result['main_samples'], [])
                self.assertIsNone(result['main_observer_lifecycle']); self.assertIsNone(result['policy_before'])
                self.assertTrue(result['original_lease_released']); self.assertTrue(result['immutable_inputs_unchanged'])
                startup = result_pin
                self.assertNotIn('torch', sys.modules)
            finally:
                native.PAIR_SHA, native.CAPACITY_PROOF_SHA, native.POLICIES, native.load = saved

        def test_06_preparer_checks_exact_native_contract_before_persisting_job(self):
            tree = ast.parse(h.checked(job['preparer']).read_text())
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'prepare')
            calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
            contract = next(node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == 'validate_main_health_contract')
            publish = next(node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == 'put'
                           and node.args and isinstance(node.args[0], ast.BinOp)
                           and isinstance(node.args[0].right, ast.Constant) and node.args[0].right.value == 'job.json')
            self.assertLess(contract.lineno, publish.lineno)
            self.assertTrue(any(isinstance(node.func, ast.Name) and node.func.id == 'make_main_health_protocol' for node in calls))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    for pin in job['inputs']: h.checked(pin)
    report = h.put(output / 'report.json', dict(
        status='PASS_ORIGINAL_PROTOCOL_REJECTION_CORRECTED_PRODUCER_AND_NATIVE_PRE_WORKER_INITIALIZATION' if result.wasSuccessful() else 'FAIL_PRESERVED_NO_RETRY',
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), targeted_rejections=negatives,
        explicit_synthetic_native_prefix=startup, original_failure_closeout=job['failure_closeout'],
        actual_new_worker_or_Torch_or_policy_or_MAME_launched=False, original_failed_case_requalified=False,
        quality_qualified=False, production_changed=False, created_unix_s=time.time()))
    print(json.dumps(dict(report=report, passed=result.wasSuccessful())), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
