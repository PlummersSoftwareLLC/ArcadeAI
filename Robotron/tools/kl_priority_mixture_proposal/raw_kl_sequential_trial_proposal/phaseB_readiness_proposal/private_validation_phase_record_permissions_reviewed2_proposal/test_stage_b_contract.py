"""Unexecuted Stage B wrapper guards, not real constructor/CUDA coverage.

Stdlib cases exercise the exact held pressure predicate plus the new ledger.
Tiny CPU cases exercise only observers/state assertions with real CPU tensors;
the actual128-graph constructor/4096/fusedAMP/native route remains GPU-only.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('_stage_b_source',HERE/'cuda_trace_worker.py')
worker=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def pressure_context():
    """Run the actual source predicate, not a second pressure algorithm."""
    source=(HERE.parents[1]/'training.py').read_text()
    tree=ast.parse(source)
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='replay_pressure_reached')
    metrics=SimpleNamespace(lock=threading.RLock(),frame_count=905164910,learner_frame_count=452630871,
        measurement_frame_count=7550388,loaded_frame_count=905164910,
        loaded_measurement_frame_count=7550388,loaded_optimized_samples=7387004928)
    cfg=SimpleNamespace(min_replay_to_train=500000,batch_size=4096,baseline_batch_size=512,max_samples_per_frame=8)
    namespace=dict(metrics=metrics,RL_CONFIG=cfg)
    exec(compile(ast.Module(body=[function],type_ignores=[]),'<held-pressure-predicate>','exec'),namespace)
    memory=SimpleNamespace()
    class Eligible:
        def __len__(self):return 6000000
    agent=SimpleNamespace(training_steps=2156883,optimized_samples=7387004928,loaded_training_steps=2156883,memory=Eligible())
    clocks=dict(training_steps=agent.training_steps,optimized_samples=agent.optimized_samples,
        frame_count=metrics.frame_count,learner_frame_count=metrics.learner_frame_count)
    return SimpleNamespace(agent=agent,metrics=metrics,cfg=cfg,frame_credit_ledger=[],loaded=dict(clocks=clocks),
        expected=dict(measurement_frame_count=7550388),training=SimpleNamespace(replay_pressure_reached=namespace['replay_pressure_reached']))


class LedgerContracts(unittest.TestCase):
    def test_exact18_under_actual_cap_and_no19(self):
        ctx=pressure_context()
        for ordinal in range(1,19):
            row=worker.grant_frame_credit(ctx,ordinal)
            self.assertEqual(row['synthetic_frames'],512)
            self.assertFalse(ctx.training.replay_pressure_reached(ctx.agent))
            ctx.agent.training_steps+=1;ctx.agent.optimized_samples+=4096
            self.assertTrue(ctx.training.replay_pressure_reached(ctx.agent))
        self.assertEqual(ctx.metrics.frame_count,905164910+9216)
        self.assertEqual(ctx.metrics.learner_frame_count,452630871)
        with self.assertRaises(RuntimeError):worker.grant_frame_credit(ctx,19)

    def test_out_of_order_credit_does_not_mutate(self):
        ctx=pressure_context();before=ctx.metrics.frame_count
        with self.assertRaises(RuntimeError):worker.grant_frame_credit(ctx,2)
        self.assertEqual(ctx.metrics.frame_count,before)
        self.assertEqual(ctx.frame_credit_ledger,[])

    def test_anchor_mutation_fails_closed(self):
        for field in ('loaded_frame_count','loaded_optimized_samples','learner_frame_count','measurement_frame_count'):
            with self.subTest(field=field):
                ctx=pressure_context();setattr(ctx.metrics,field,getattr(ctx.metrics,field)+1)
                with self.assertRaises(RuntimeError):worker.grant_frame_credit(ctx,1)
                self.assertEqual(ctx.frame_credit_ledger,[])

    def test_unexpected_warmup_anchor_is_not_reset(self):
        for name in ('_replay_pressure_anchor','_replay_warmup_pending'):
            ctx=pressure_context();setattr(ctx.agent,name,(1,2,3))
            with self.assertRaises(RuntimeError):worker.grant_frame_credit(ctx,1)
            self.assertEqual(getattr(ctx.agent,name),(1,2,3))

    def test_no_saved_checkpoint_overwrite_or_tmp_bak_rescue(self):
        for suffix in ('','.tmp','.bak'):
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);target=root/('post-step-checkpoint.pt'+suffix);target.write_bytes(b'old')
                agent=SimpleNamespace(save=Mock())
                ctx=SimpleNamespace(paths=dict(root=root),variant='kl18',completed=[{}]*18,agent=agent)
                with self.assertRaises(RuntimeError):worker.save_post_checkpoint(ctx)
                agent.save.assert_not_called();self.assertFalse((root/'save-entered.json').exists())

    def test_default_import_has_no_numeric_module_dependency(self):
        tree=ast.parse((HERE/'cuda_trace_worker.py').read_text())
        imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
        names=[alias.name for node in imports if isinstance(node,ast.Import) for alias in node.names]
        self.assertNotIn('torch',names);self.assertNotIn('numpy',names)
        self.assertFalse(any(name.startswith('dqn') for name in names))

    def test_source_constructor_load_and_release_order(self):
        source=(HERE/'cuda_trace_worker.py').read_text();tree=ast.parse(source)
        body=ast.get_source_segment(source,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='construct_and_load'))
        self.assertLess(body.index('a.stop()'),body.index('a.load('))
        self.assertLess(body.index('require_loaded(ctx)'),body.index('graphs.slots.clear()'))
        self.assertIn('a._prefetcher=None',body)
        self.assertIn('ctx.agent_module.PrioritizedReplayBuffer=original',body)


class LeaseContracts(unittest.TestCase):
    def fixture(self):
        ctx=pressure_context();ctx.cfg.diagnostic_interval=20
        ctx.agent.memory=SimpleNamespace(batch=(None,)*8+([4,4,6000000],None),updates=[])
        ctx.agent._learning_optimizer_exposure=SimpleNamespace(snapshot=Mock(return_value=dict(total={})))
        ctx.np=SimpleNamespace(array_equal=lambda a,b:a==b)
        ctx.entered_attempts=[];ctx.producer_allowed=False;ctx.paths=dict(root=Path('/unexecuted'))
        ctx.training.train_step=Mock(return_value=None)
        prefetch=SimpleNamespace(_epoch=2,direct_state_fill=True)
        lease=SimpleNamespace(_owner=prefetch,_epoch=2,is_current=True,batch=ctx.agent.memory.batch,_released=False)
        def release():lease._released=True
        lease.release=Mock(side_effect=release)
        prefetch.get=Mock(return_value=lease)
        observers=SimpleNamespace(reset=Mock(),forward=None,finished=[])
        return ctx,prefetch,lease,observers

    def call(self,ctx,prefetch,observers,publication):
        with patch.object(worker,'grant_frame_credit',return_value={}),patch.object(worker,'state_snapshot',return_value={}),\
                patch.object(worker,'write_json',side_effect=publication):
            return worker.one_attempt(ctx,1,prefetch,observers)

    def test_stale_acquired_lease_is_released_without_actual_call(self):
        ctx,prefetch,lease,observers=self.fixture();lease.is_current=False
        with self.assertRaises(RuntimeError):self.call(ctx,prefetch,observers,lambda *_:None)
        lease.release.assert_called_once();ctx.training.train_step.assert_not_called()
        self.assertFalse(ctx.producer_allowed);self.assertEqual(ctx.entered_attempts,[])

    def test_entered_publication_failure_releases_and_preserves_exception(self):
        ctx,prefetch,lease,observers=self.fixture();original=OSError('proof disk failed')
        def publication(path,value):
            if path.name.endswith('entered.json'):raise original
        with self.assertRaises(OSError) as caught:self.call(ctx,prefetch,observers,publication)
        self.assertIs(caught.exception,original);lease.release.assert_called_once()
        ctx.training.train_step.assert_not_called();self.assertFalse(ctx.producer_allowed)

    def test_none_consumes_one_call_without_replacement_and_releases(self):
        ctx,prefetch,lease,observers=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'returned None'):self.call(ctx,prefetch,observers,lambda *_:None)
        ctx.training.train_step.assert_called_once();prefetch.get.assert_called_once()
        self.assertEqual(ctx.entered_attempts,[1]);self.assertTrue(lease._released)

    def test_kernel_exception_survives_report_and_release_failures(self):
        ctx,prefetch,lease,observers=self.fixture();original=ArithmeticError('original kernel')
        ctx.training.train_step.side_effect=original;lease.release.side_effect=OSError('release fault')
        def publication(path,value):
            if path.name.endswith('failure.json'):raise OSError('failure report fault')
        with self.assertRaises(ArithmeticError) as caught:self.call(ctx,prefetch,observers,publication)
        self.assertIs(caught.exception,original);self.assertFalse(ctx.producer_allowed)
        self.assertEqual(ctx.entered_attempts,[1]);ctx.training.train_step.assert_called_once()

    def test_get_failure_disables_producer_without_inventing_lease(self):
        ctx,prefetch,lease,observers=self.fixture();original=RuntimeError('producer original')
        prefetch.get.side_effect=original
        with self.assertRaises(RuntimeError) as caught:self.call(ctx,prefetch,observers,lambda *_:None)
        self.assertIs(caught.exception,original);self.assertFalse(ctx.producer_allowed)
        lease.release.assert_not_called();ctx.training.train_step.assert_not_called()


class TinyCPUContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        import torch
        cls.np=np;cls.torch=torch
        torch.set_num_threads(2)
        lock=json.loads((HERE/'source-lock.json').read_text())
        entry=lock['frozen_science_helpers'];path=Path(entry['source'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
        spec=importlib.util.spec_from_file_location('_stage_b_retained_science',path)
        cls.science=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.science)

    def context(self):return SimpleNamespace(torch=self.torch,np=self.np,science=self.science)

    def states(self):
        torch=self.torch
        before=dict(online=dict(p=torch.tensor([1.])),target=dict(p=torch.tensor([2.])),
            optimizer=dict(p=dict(step=torch.tensor(7.),exp_avg=torch.tensor([.2]),exp_avg_sq=torch.tensor([.3])),unused={}),
            scaler=dict(scale=1048576.),clocks=dict(training_steps=1))
        return before,self.science.cpu(self.context(),before)

    def test_applied_actual_slot_and_parameter_progress(self):
        before,after=self.states();torch=self.torch
        after['online']['p'].add_(.01);after['optimizer']['p']['step'].add_(1);after['optimizer']['p']['exp_avg'].add_(.1)
        result=worker.verify_progress(self.context(),before,after,dict(p=torch.tensor([1.]),unused=None),
            dict(attempts_started=1,outcomes_recorded=1,unavailable=0,applied=1,amp_skipped=0),0.,grad_norm=1.)
        self.assertEqual(result['outcome'],'applied');self.assertFalse(result['slots']['unused']['after_initialized'])
        self.assertEqual(result['slots']['p']['after_step'],8.)

    def test_skip_preserves_actual_state_with_nonfinite_preclip(self):
        before,after=self.states();after['scaler']['scale']/=2
        result=worker.verify_progress(self.context(),before,after,dict(p=self.torch.tensor([float('inf')]),unused=None),
            dict(attempts_started=1,outcomes_recorded=1,unavailable=0,applied=0,amp_skipped=1),1.,grad_norm=float("inf"))
        self.assertEqual(result['changed_online_parameters'],0);self.assertEqual(result['changed_adam_moment_slots'],0)

    def test_step_only_or_buffer_only_progress_does_not_count(self):
        for absent in ('moment','parameter'):
            before,after=self.states();after['optimizer']['p']['step'].add_(1)
            before['online']['buffer']=self.torch.tensor([3.]);after['online']['buffer']=self.torch.tensor([4.])
            if absent=='moment':after['online']['p'].add_(.01)
            else:after['optimizer']['p']['exp_avg'].add_(.1)
            with self.subTest(absent=absent),self.assertRaises(RuntimeError):
                worker.verify_progress(self.context(),before,after,dict(p=self.torch.tensor([1.]),unused=None),
                    dict(attempts_started=1,outcomes_recorded=1,unavailable=0,applied=1,amp_skipped=0),0.,grad_norm=1.)

    def test_applied_rejects_nonfinite_packed_norm_despite_finite_elements(self):
        before,after=self.states();after['online']['p'].add_(.1)
        after['optimizer']['p']['step'].add_(1);after['optimizer']['p']['exp_avg'].add_(.1)
        with self.assertRaises(RuntimeError):
            worker.verify_progress(self.context(),before,after,dict(p=self.torch.tensor([1.]),unused=None),
                dict(attempts_started=1,outcomes_recorded=1,unavailable=0,applied=1,amp_skipped=0),0.,grad_norm=float('inf'))

    def test_skip_adam_or_online_mutation_is_not_admission_proof(self):
        for changed in ('step','online'):
            before,after=self.states();after['scaler']['scale']/=2
            if changed=='step':after['optimizer']['p']['step'].add_(1)
            else:after['online']['p'].add_(1)
            with self.subTest(changed=changed),self.assertRaises(RuntimeError):
                worker.verify_progress(self.context(),before,after,dict(p=self.torch.tensor([1.]),unused=None),
                    dict(attempts_started=1,outcomes_recorded=1,unavailable=0,applied=0,amp_skipped=1),1.,grad_norm=float("inf"))

    def test_unavailable_or_found_inf_disagreement_rejected(self):
        before,after=self.states()
        for unavailable,found in ((1,0.),(0,1.)):
            with self.subTest(unavailable=unavailable,found=found),self.assertRaises(RuntimeError):
                worker.verify_progress(self.context(),before,after,dict(p=self.torch.tensor([1.]),unused=None),
                    dict(attempts_started=1,outcomes_recorded=1,unavailable=unavailable,applied=1,amp_skipped=0),found,grad_norm=1.)

    def test_applied_requires_finite_grad_and_exact_step(self):
        for bad in ('nonfinite','wrongstep','none_slot'):
            before,after=self.states();after['online']['p'].add_(.01)
            after['optimizer']['p']['step'].add_(2 if bad=='wrongstep' else 1)
            grad=self.torch.tensor([float('nan') if bad=='nonfinite' else 1.])
            gradients=dict(p=grad,unused=None)
            if bad=='none_slot':after['optimizer']['unused']=dict(step=self.torch.tensor(1.))
            with self.subTest(bad=bad),self.assertRaises(RuntimeError):
                worker.verify_progress(self.context(),before,after,gradients,
                    dict(attempts_started=1,outcomes_recorded=1,unavailable=0,applied=1,amp_skipped=0),0.,grad_norm=1.)

    def test_numpy_json_is_detached_primitive_with_exact_fp32_values(self):
        array=self.np.array([.1,.3],dtype=self.np.float32)
        value=json.loads(json.dumps(worker.safe(dict(vector=array))))
        self.assertEqual(value['vector'],array.tolist())
        array[0]=9.;self.assertNotEqual(value['vector'][0],float(array[0]))

    def test_native_adapter_rejects_reordered_indices_before_mutation(self):
        np=self.np;adapter=object.__new__(worker.FixedReplayAdapter)
        sentinel=6000000;original=np.array([4,4,sentinel,7],dtype=np.int64)
        adapter.ctx=self.context();adapter.batch=(None,)*8+(original,None)
        adapter.active_forward=dict(priority=np.array([.2,.4,.6,.8],dtype=np.float32))
        with self.assertRaises(RuntimeError):
            adapter.update_priorities(original[[0,3,2,1]],adapter.active_forward['priority'])

    def test_native_adapter_rejects_priority_vector_misjoin(self):
        np=self.np;adapter=object.__new__(worker.FixedReplayAdapter)
        original=np.array([4,4,6000000,7],dtype=np.int64)
        adapter.ctx=self.context();adapter.batch=(None,)*8+(original,None)
        adapter.active_forward=dict(priority=np.array([.2,.4,.6,.8],dtype=np.float32))
        with self.assertRaises(RuntimeError):adapter.update_priorities(original,np.array([1.,2.,3.,4.],dtype=np.float32))

    def observer_fixture(self,*,priority_requires_grad=False):
        torch=self.torch;ctx=self.context();net=torch.nn.Linear(1,1,bias=False)
        output=(net.weight.sum(),torch.ones(4096),torch.tensor(.25),torch.zeros(19),
            torch.ones(4096,requires_grad=priority_requires_grad))
        kernel=Mock(return_value=output)
        def finish(ticket,mode,found_inf=None):ticket.finished=True
        exposure=SimpleNamespace(finish=Mock(side_effect=finish))
        ctx.agent=SimpleNamespace(online_net=net,compiled_training_loss=kernel,
            compiled_training_loss_diagnostics=kernel,optimizer=SimpleNamespace(param_groups=[dict(lr=.001)]),
            grad_scaler=SimpleNamespace(step=Mock(),update=Mock()),_learning_optimizer_exposure=exposure,
            memory=SimpleNamespace(active_forward=None))
        ctx.current_ordinal=2  # No actual artifact-writing ordinals in this unit.
        return ctx,net,kernel,output

    def test_observers_preserve_single_forward_tuple_and_original_clip(self):
        ctx,net,kernel,output=self.observer_fixture();torch=self.torch
        original=torch.nn.utils.clip_grad_norm_
        with patch.object(torch.nn.utils,'clip_grad_norm_',wraps=original) as clip:
            observers=worker.StepObservers(ctx).install()
            try:
                args=(None,)*8+(torch.tensor([.1,.2,.3]),)
                returned=ctx.agent.compiled_training_loss(*args)
                self.assertIs(returned,output);kernel.assert_called_once_with(*args)
                self.assertEqual(observers.forward['actual_schedule'],args[-1].tolist())
                net.weight.grad=torch.full_like(net.weight,10.)
                torch.nn.utils.clip_grad_norm_(net.parameters(),1.)
                clip.assert_called_once()
                self.assertTrue(torch.equal(observers.gradients['weight'],torch.full_like(net.weight,10.)))
                self.assertLessEqual(float(net.weight.grad.abs().max()),1.)
                ticket=SimpleNamespace(epoch=3,finished=False)
                ctx.agent._learning_optimizer_exposure.finish(ticket,'single_cuda_found_inf',1.)
                self.assertEqual(observers.finished,[dict(mode='single_cuda_found_inf',found_inf=1.,ticket_epoch=3,ticket_finished=True)])
                ctx.agent.grad_scaler.step(ctx.agent.optimizer);ctx.agent.grad_scaler.update()
                self.assertEqual(observers.scaler_calls,dict(step=1,update=1))
            finally:observers.close()
        self.assertIs(torch.nn.utils.clip_grad_norm_,original)
        self.assertIs(ctx.agent.compiled_training_loss,kernel)

    def test_invalid_observer_priority_does_not_retry_forward(self):
        ctx,net,kernel,output=self.observer_fixture(priority_requires_grad=True)
        observers=worker.StepObservers(ctx).install()
        try:
            with self.assertRaisesRegex(RuntimeError,'detached FP32'):
                ctx.agent.compiled_training_loss(*(None,)*8,self.torch.tensor([.1,.2,.3]))
            self.assertEqual(kernel.call_count,1)
        finally:observers.close()


if __name__=='__main__':unittest.main()
