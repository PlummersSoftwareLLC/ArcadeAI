"""Authored stdlib metadata guards; execution is deferred until quality closure."""
import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
Q=HERE.parent
ORIGINAL=Q/'batch2048_one_trial_execution_release_reviewed2_proposal'
SPEC=importlib.util.spec_from_file_location('_shared_recipe_control_metadata',HERE/'run_one_trial.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)


class SharedRecipeControlContracts(unittest.TestCase):
    def test_exact_local_helper_sources_and_wrong_original_guard_rejected(self):
        activation=dict(helper_pins=copy.deepcopy(M.SHARED_RECIPE_HELPERS))
        M.validate_shared_recipe_helpers(activation)
        for key,pin in activation['helper_pins'].items():
            path=Path(pin['path'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),pin['sha256'])
            self.assertEqual(path.stat().st_size,pin['bytes'])
            self.assertEqual(len(pin['sha256']),64)
        for changed in ('live_host','metrics','identity','protection','missing'):
            bad=copy.deepcopy(activation)
            if changed=='missing':del bad['helper_pins']['metrics']
            else:bad['helper_pins'][changed]['sha256']='0'*64
            with self.subTest(changed=changed),self.assertRaises(RuntimeError):M.validate_shared_recipe_helpers(bad)
        old=copy.deepcopy(activation)
        old['helper_pins']['live_host']['path']=str(Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/parallel_state_fill_trial.py'))
        with self.assertRaises(RuntimeError):M.validate_shared_recipe_helpers(old)

    def test_real_read_trial_checks_helpers_before_core_or_arming_reads(self):
        class ReachedCore(Exception):pass
        self_pin=dict(path=str(HERE/'run_one_trial.py'),sha256='a'*64)
        job_pin=dict(path='/fixture/new-trial02-job.json',sha256='b'*64)
        core_pin=dict(path='/fixture/new-trial02-core.json',sha256='c'*64)
        activation_pin=dict(path='/fixture/new-trial02-activation.json',sha256='d'*64)
        trial=dict(schema=M.SCHEMA,sources=dict(controller=self_pin,adapter=dict(path=str(M.ADAPTER),sha256=M.ADAPTER_SHA),
            horizon=dict(path=str(M.HORIZON),sha256=M.HORIZON_SHA)),
            deadlines=dict(latch_s=3240,stop_intent_s=3310,owner_ceiling_s=3600),
            observation_budget_bytes=M.JOURNAL_BYTES,activation_job=activation_pin,trial_core=core_pin,boot_id='future-fixture')
        activation=dict(mode='activate_batch2048',trial_core=core_pin,boot_id='future-fixture',helper_pins=copy.deepcopy(M.SHARED_RECIPE_HELPERS))
        seen=[]
        def read(pin):
            seen.append(pin['path'])
            if pin==job_pin:return trial
            if pin==activation_pin:return activation
            if pin==core_pin:raise ReachedCore
            raise AssertionError('Unexpected metadata/armed/process access: '+str(pin))
        deadline=SimpleNamespace(pin=lambda path:(self_pin if str(path)==M.__file__ else job_pin,b''),read_pin=read)
        args=SimpleNamespace(job=Path(job_pin['path']),expected_controller_sha256=self_pin['sha256'],expected_job_sha256=job_pin['sha256'])
        with self.assertRaises(ReachedCore):M.read_trial(args,deadline)
        self.assertEqual(seen,[job_pin['path'],activation_pin['path'],core_pin['path']])
        seen.clear();activation['helper_pins']['metrics']['path']='/old/inference_worker_affinity.py'
        with self.assertRaisesRegex(RuntimeError,'Exact selected shared-recipe'):M.read_trial(args,deadline)
        self.assertEqual(seen,[job_pin['path'],activation_pin['path']])

    def test_reverse_exact_controller_deadline_and_literal_defaults(self):
        before=(ORIGINAL/'run_one_trial.py').read_text();after=(HERE/'run_one_trial.py').read_text()
        tree=ast.parse(after)
        added=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_shared_recipe_helpers')
        reduced=after.replace(ast.get_source_segment(after,added)+'\n\n\n','')
        reduced=''.join(line for line in reduced.splitlines(True) if not line.startswith('SHARED_RECIPE_HELPERS = '))
        reduced=reduced.replace('    validate_shared_recipe_helpers(activation)\n','')
        reduced=reduced.replace(str(M.ADAPTER),str(ORIGINAL/'run_CE_batch_transition.py')).replace(M.ADAPTER_SHA,'479b4b4da50de7c78cb94a730a12a4603e3e6c2281fffac1533a5a4a22822202')
        self.assertEqual(reduced,before)
        self.assertEqual((HERE/'deadline_guard.py').read_bytes(),(ORIGINAL/'deadline_guard.py').read_bytes())
        self.assertEqual(M.RELEASE_VALIDATOR_SHA,'c01e71f00345f64996b469ff7b7a257a2e73e7d8e016914bc8225d3647df321f')
        spec=importlib.util.spec_from_file_location('_shared_recipe_deadline_metadata',HERE/'deadline_guard.py')
        deadline=importlib.util.module_from_spec(spec);spec.loader.exec_module(deadline)
        for module in (M,deadline):
            with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('default read')),mock.patch.object(module,'execution_readiness',side_effect=AssertionError('default helper import')),mock.patch('builtins.print'):
                self.assertEqual(module.main([]),0)


if __name__=='__main__':unittest.main()
