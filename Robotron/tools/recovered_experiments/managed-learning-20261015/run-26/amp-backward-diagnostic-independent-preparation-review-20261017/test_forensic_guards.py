"""Prepared stdlib/mock tests. DO NOT RUN during a fixed host trial window."""
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from . import forensic_parent as parent
from . import forensic_worker as worker


class Guards(unittest.TestCase):
    def test_default_dry_run_has_no_query_spawn_or_created_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'not-created'
            base=SimpleNamespace(validate_output=lambda value,**kwargs:value,BOUNDS={'bounded':True},
                                 GPU0_UUID='only-display',MAIN_GPU_UUID='forbidden-main',
                                 guard_live_resources=Mock(side_effect=AssertionError('live query')))
            lock={'source_files':{'old.py':{'sha256':'old'}}}
            with patch.object(parent,'read_lock',return_value=lock),patch.object(parent,'helpers',return_value=(base,None)), \
                 patch.object(parent,'launch',side_effect=AssertionError('launch called')), \
                 patch.object(parent.subprocess,'Popen',side_effect=AssertionError('spawn')), \
                 patch.object(parent.subprocess,'check_output',side_effect=AssertionError('query')), \
                 patch('sys.stdout',new_callable=io.StringIO) as stdout:
                self.assertEqual(parent.main(['--directory',str(output)]),0)
                result=json.loads(stdout.getvalue())
            self.assertEqual(result['status'],'DRY_RUN_ONLY')
            self.assertFalse(result['current_merged_snapshot_qualification'])
            self.assertFalse(output.exists())
            base.guard_live_resources.assert_not_called()

    def test_launch_requires_explicit_switch_and_command_is_isolated(self):
        with patch.object(parent,'launch',return_value={'status':'OBSERVATIONS_COMPLETE'}) as launch, \
             patch.object(parent,'describe') as describe,patch('sys.stdout',new_callable=io.StringIO):
            parent.main(['--directory','/private/owned','--launch'])
            launch.assert_called_once_with(Path('/private/owned'));describe.assert_not_called()
        self.assertEqual(parent.command(Path('/owned/manifest')),
            [parent.sys.executable,'-I','-B',str(parent.HERE/'forensic_worker.py'),'--manifest','/owned/manifest'])

    def test_real_archival_default_plan_imports_only_stdlib_and_has_no_live_calls(self):
        import sys,uuid
        lock=parent.read_lock();base,old=parent.helpers(lock)
        output=parent.GAME/'logs'/('forensic-dry-run-uncreated-'+uuid.uuid4().hex)
        with patch.object(parent,'helpers',return_value=(base,old)), \
             patch.object(base,'guard_live_resources',side_effect=AssertionError('live guard')), \
             patch.object(parent.subprocess,'Popen',side_effect=AssertionError('spawn')), \
             patch.object(parent.subprocess,'check_output',side_effect=AssertionError('query')):
            plan=parent.describe(output)
        self.assertEqual(plan['status'],'DRY_RUN_ONLY');self.assertEqual(len(plan['source_files']),54)
        self.assertFalse(output.exists())
        self.assertFalse(any(name.split('.')[0] in ('torch','numpy','dqn') for name in sys.modules))

    def test_module_loader_executes_verified_bytes_without_creating_pycache(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'old_helper.py';path.write_text('meaning=42\n')
            module=parent.checked_module(path,parent.digest(path),'_forensic_loader_test')
            self.assertEqual(module.meaning,42)
            self.assertFalse((path.parent/'__pycache__').exists())
            with self.assertRaises(RuntimeError):parent.checked_module(path,'wrong','_forensic_loader_rejected')

    def test_pinned_lock_rejects_drift_before_helpers_or_live_guards(self):
        with patch.object(parent,'digest',return_value='wrong'):
            with self.assertRaisesRegex(RuntimeError,'source lock changed'):parent.read_lock()

    def test_archival_copy_lock_and_import_contract_remain_fixed(self):
        lock=parent.read_lock()  # Only hashes small immutable source text.
        self.assertEqual(len(lock['source_files']),54)
        self.assertTrue(lock['fresh_scaler_per_amp_case'])
        self.assertEqual(lock['optimizer_steps_allowed'],0)
        self.assertEqual(lock['retries_allowed'],0)
        self.assertEqual([case['initial_scale'] for case in lock['case_order']],[65536,1,None])
        for source in lock['source_files'].values():
            self.assertIn('coherent-snapshot-reviewed2-failure-analysis/failed-run-copy/private',source['source'])
        import ast
        for module in (parent,worker):
            tree=ast.parse(Path(module.__file__).read_text())
            for node in tree.body:
                if isinstance(node,ast.Import):names=[alias.name for alias in node.names]
                elif isinstance(node,ast.ImportFrom):names=[node.module]
                else:continue
                self.assertFalse(any(name.split('.')[0] in ('torch','numpy','dqn') for name in names))

    def test_fixed_training_config_and_private_control_fields_exist_without_import(self):
        import ast
        lock=parent.read_lock()
        cfg=ast.parse(Path(lock['source_files']['config.py']['source']).read_text())
        definition=next(node for node in cfg.body if isinstance(node,ast.ClassDef) and node.name=='RLConfigData')
        names={node.target.id for node in definition.body if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name)}
        tree=ast.parse(Path(worker.__file__).read_text())
        used={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute) and
              isinstance(node.value,ast.Attribute) and isinstance(node.value.value,ast.Name) and
              node.value.value.id=='ctx' and node.value.attr=='cfg'}
        self.assertEqual(used-names,set())

    def test_safe_diagnostics_preserve_nonfinite_values_explicitly(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'evidence.json'
            worker.write_json(path,dict(native_gradient='separate tensor artifact',nan=float('nan'),inf=float('inf')))
            data=json.loads(path.read_text())
            self.assertEqual((data['nan'],data['inf']),('nan','inf'))
            with self.assertRaises(FileExistsError):worker.write_json(path,{})


class Boundaries(unittest.TestCase):
    def hooks(self):
        parameters=[object(),object()]
        optimizer=object()
        ctx=SimpleNamespace(agent=SimpleNamespace(online_net=SimpleNamespace(parameters=lambda:iter(parameters)),
                            optimizer=optimizer),training=SimpleNamespace(),layout=SimpleNamespace(scripts=Path('/private/Scripts')))
        return ctx,worker.CaseHooks(ctx,Path('/unexecuted/case'),True),parameters

    def test_exact_caller_code_and_private_filename_required(self):
        ctx,hooks,_=self.hooks()
        code=SimpleNamespace(co_filename='/private/Scripts/dqn/training.py')
        ctx.training._train_step_impl=SimpleNamespace(__code__=code)
        hooks.check_caller(SimpleNamespace(f_code=code))
        with self.assertRaises(RuntimeError):hooks.check_caller(SimpleNamespace(f_code=copy.copy(code)))
        code.co_filename='/live/production/training.py'
        with self.assertRaises(RuntimeError):hooks.check_caller(SimpleNamespace(f_code=code))

    def test_unscale_preserves_scaled_then_delegates_once_then_records_unscaled(self):
        ctx,hooks,_=self.hooks();order=[]
        hooks.original_unscale=lambda optimizer:order.append(('original',optimizer))
        with patch.object(hooks,'check_caller'),patch.object(worker,'gradients',side_effect=lambda ctx,path,stage:order.append(stage)):
            hooks.unscale(ctx.agent.optimizer)
            self.assertEqual(order,['scaled',('original',ctx.agent.optimizer),'unscaled'])
            with self.assertRaises(RuntimeError):hooks.unscale(ctx.agent.optimizer)
        self.assertEqual(hooks.calls['unscale'],1)

    def test_forbidden_steps_raise_and_do_not_delegate(self):
        _,hooks,_=self.hooks()
        for name in ('optimizer_step','scaler_step','scaler_update'):
            with self.assertRaises(worker.ForbiddenStep):hooks.forbid(name)(object())
            self.assertEqual(hooks.calls[name],1)

    def test_hook_restoration_keeps_inherited_and_existing_attributes_exact(self):
        class Scaler:
            def step(self):return 'original'
        _,hooks,_=self.hooks();scaler=Scaler();scaler.own='before'
        hooks.replace(scaler,'step',lambda:'forbidden');hooks.replace(scaler,'own','after')
        hooks.__exit__(None,None,None)
        self.assertNotIn('step',vars(scaler));self.assertEqual(scaler.step(),'original');self.assertEqual(scaler.own,'before')

    def test_preclip_abort_records_actual_locals_without_clipping_or_step(self):
        class Scalar:
            def __init__(self,value):self.value=value
            def detach(self):return self
            def float(self):return self
            def cpu(self):return self
            def __float__(self):return float(self.value)
        ctx,hooks,parameters=self.hooks()
        ctx.torch=SimpleNamespace(Tensor=Scalar)
        hooks.calls['unscale']=1
        def actual_training():
            weighted_loss=Scalar(.5)
            m_joint=Scalar(.25)
            outcome_mode='single_cuda_found_inf'
            outcome_tensor=Scalar(1.)
            hooks.clip(iter(parameters),1.)
        def caller(frame):self.assertIs(frame.f_code,actual_training.__code__)
        with patch.object(hooks,'check_caller',side_effect=caller), \
             patch.object(worker,'save_tensors',return_value={'artifact':'native'}) as native, \
             patch.object(worker,'tensor_stats',return_value={'all_finite':True}),patch.object(worker,'write_json'):
            try:actual_training()
            except worker.BoundaryReached as error:
                self.assertIs(error,hooks.sentinel);error.__traceback__=None
            else:self.fail('Did not abort before clip')
            self.assertEqual(hooks.boundary['loss'],.5)
            self.assertIn('weighted_loss',native.call_args.args[2])
        self.assertEqual(hooks.calls['boundary'],1)
        self.assertEqual(sum(hooks.calls[key] for key in ('optimizer_step','scaler_step','scaler_update')),0)

    def test_mismatched_parameters_fail_before_boundary_evidence(self):
        _,hooks,_=self.hooks();hooks.calls['unscale']=1
        with patch.object(hooks,'check_caller'),patch.object(worker,'gradients') as gradients:
            with self.assertRaisesRegex(RuntimeError,'parameter ownership'):hooks.clip([object()],1.)
            gradients.assert_not_called()
        self.assertEqual(hooks.calls['boundary'],0)

    def test_safety_failure_records_remaining_cases_without_another_backward(self):
        import threading
        ctx=SimpleNamespace(layout=SimpleNamespace(scripts=Path('/private/Scripts')),
                            agent=SimpleNamespace(_training_lock=threading.RLock()))
        training=SimpleNamespace(_train_step_impl=SimpleNamespace(__code__=SimpleNamespace(co_filename='/private/Scripts/dqn/training.py')))
        spec=SimpleNamespace(CASES=parent.CASES,SCHEMA=parent.SCHEMA,SEED=parent.SEED,LOCK_SHA=parent.LOCK_SHA)
        with patch.object(worker.importlib,'import_module',return_value=training), \
             patch.object(worker,'setup_inputs',return_value={}), \
             patch.object(worker,'run_case',side_effect=RuntimeError('no-step certificate failed')) as run:
            result=worker.observe(ctx,None,spec)
        self.assertEqual(run.call_count,1)
        self.assertEqual([row['status'] for row in result['cases']],
                         ['SAFETY_ERROR','NOT_RUN_AFTER_SAFETY_ERROR','NOT_RUN_AFTER_SAFETY_ERROR'])
        self.assertEqual(result['status'],'DIAGNOSTIC_ERROR')
        self.assertFalse(result['snapshot_qualified'])


if __name__=='__main__':
    unittest.main()
