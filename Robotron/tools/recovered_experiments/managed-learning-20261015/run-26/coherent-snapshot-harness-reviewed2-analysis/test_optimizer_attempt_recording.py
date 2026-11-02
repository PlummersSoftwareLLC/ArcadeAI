"""Stdlib-only failure/recording tests; no numerical imports or GPU access."""
import copy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from . import whole_agent_smoke_worker as worker
from .test_amp_attempt_classification import attempt_pair


class Array:
    def __init__(self,values):self.values=values
    def __ne__(self,value):return [item!=value for item in self.values]
    def tobytes(self):return repr(self.values).encode()


class Tensor:
    dtype='float32'
    def __init__(self,*values):self.values=list(values);self.shape=(len(values),)
    def detach(self):return self
    def cpu(self):return self
    def contiguous(self):return self
    def numpy(self):return Array(self.values)
    def __float__(self):return float(self.values[0])


class Parameter:
    pass


class OptimizerAttemptRecordingTests(unittest.TestCase):
    def context(self,path):
        agent=SimpleNamespace(_training_lock=threading.RLock(),training_enabled=False,
            _prefetcher=SimpleNamespace(get=Mock(return_value=SimpleNamespace(release=Mock()))),
            device='owned-cuda',training_steps=8,optimized_samples=64)
        metrics=SimpleNamespace(lock=threading.Lock(),training_enabled=False,
            frame_count=160,learner_frame_count=160)
        return SimpleNamespace(agent=agent,metrics=metrics,phase='capture',paths={'root':Path(path)},
            torch=SimpleNamespace(cuda=SimpleNamespace(synchronize=Mock())),
            module=SimpleNamespace(replay_pressure_reached=Mock(),train_step=Mock(return_value=.25)))

    def rows(self,path):
        return [json.loads(line) for line in (Path(path)/'optimizer-attempts.jsonl').read_text().splitlines()]

    def run_attempt(self,ctx,outcome,*,gradients=True,persistent=True):
        before,after=attempt_pair(outcome)
        checks=dict(persistent_finite=persistent,gradients_finite=gradients,
                    reported_grad_norm=.5 if gradients else float('nan'))
        return patch.multiple(worker,
            runtime_details=Mock(return_value={'effective_gil_enabled':True}),
            optimizer_observation=Mock(side_effect=[before,after]),
            attempt_checks=Mock(return_value=checks))

    def test_before_and_observed_rows_are_durable_before_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.context(temporary)
            original=worker.classify_optimizer_attempt
            def classify(*args,**kwargs):
                self.assertEqual([row['event'] for row in self.rows(temporary)],['before','observed'])
                self.assertEqual(self.rows(temporary)[1]['after'],args[1])
                return original(*args,**kwargs)
            with self.run_attempt(ctx,'applied'),patch.object(worker,'classify_optimizer_attempt',side_effect=classify):
                update=worker.update_once(ctx)
            self.assertTrue(update['applied'])
            self.assertEqual(update['outcome'],'applied')
            self.assertEqual([row['event'] for row in self.rows(temporary)],['before','observed','classified'])
            self.assertFalse(ctx.agent.training_enabled or ctx.metrics.training_enabled)

    def test_proven_skip_returns_false_for_outer_bounded_retry_and_retains_nonfinites(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.context(temporary)
            with self.run_attempt(ctx,'amp_skipped',gradients=False):
                update=worker.update_once(ctx)
            self.assertFalse(update['applied'])
            self.assertFalse(update['weights_changed'])
            row=self.rows(temporary)[-1]
            self.assertEqual(row['classification'],'amp_skipped')
            self.assertEqual(row['after_checks']['reported_grad_norm'],'nan')
            self.assertTrue(row['runtime']['effective_gil_enabled'])

    def test_applied_nonfinite_gradient_records_rejection_and_never_consumes_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.context(temporary)
            with self.run_attempt(ctx,'applied',gradients=False):
                with self.assertRaisesRegex(RuntimeError,'Applied update has nonfinite'):
                    worker.update_once(ctx)
            self.assertEqual([row['event'] for row in self.rows(temporary)],['before','observed','rejected'])
            self.assertIn('after',self.rows(temporary)[-1])
            self.assertFalse(ctx.agent.training_enabled or ctx.metrics.training_enabled)
            ctx.module.train_step.assert_called_once()

    def test_train_step_exception_records_after_evidence_but_never_classifies_or_retries(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.context(temporary)
            ctx.module.train_step.side_effect=RuntimeError('synthetic train failure')
            with self.run_attempt(ctx,'amp_skipped',gradients=False), \
                 patch.object(worker,'classify_optimizer_attempt') as classify:
                with self.assertRaisesRegex(RuntimeError,'synthetic train failure'):
                    worker.update_once(ctx)
                classify.assert_not_called()
            row=self.rows(temporary)[-1]
            self.assertEqual(row['event'],'rejected')
            self.assertIn('synthetic train failure',row['train_step_error'])
            self.assertIn('after',row)
            self.assertIsNone(row['loss'])
            self.assertFalse(ctx.agent.training_enabled or ctx.metrics.training_enabled)

    def test_none_loss_and_unavailable_exposure_are_rejected_with_observations(self):
        for mode in ('none','unavailable'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary:
                ctx=self.context(temporary)
                before,after=attempt_pair()
                if mode=='none':ctx.module.train_step.return_value=None
                else:after['exposure']['available']=False
                with self.run_attempt(ctx,'amp_skipped'), \
                     patch.object(worker,'optimizer_observation',side_effect=[before,after]):
                    with self.assertRaises(RuntimeError):worker.update_once(ctx)
                rows=self.rows(temporary)
                self.assertEqual([row['event'] for row in rows],['before','observed','rejected'])
                self.assertIn('after',rows[-1])
                ctx.module.train_step.assert_called_once()

    def test_after_observation_failure_keeps_before_and_original_train_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=self.context(temporary)
            before,_=attempt_pair()
            ctx.module.train_step.side_effect=RuntimeError('original train error')
            with self.run_attempt(ctx,'amp_skipped'), \
                 patch.object(worker,'optimizer_observation',side_effect=[before,RuntimeError('observer failure')]):
                with self.assertRaisesRegex(RuntimeError,'observer failure'):worker.update_once(ctx)
            row=self.rows(temporary)[-1]
            self.assertIn('before',row)
            self.assertIn('original train error',row['train_step_error'])
            self.assertIn('observer failure',row['error'])
            self.assertFalse(ctx.agent.training_enabled or ctx.metrics.training_enabled)

    def test_observer_normalizes_lazy_zero_slots_but_tracks_each_step_and_nonzero_moment(self):
        p,q=Parameter(),Parameter()
        model=SimpleNamespace(named_parameters=lambda:[('a',p),('b',q)],
                              state_dict=lambda:{'a':Tensor(1.,2.),'b':Tensor(3.)})
        optimizer=SimpleNamespace(param_groups=[{'params':[p,q]}],state={})
        ctx=SimpleNamespace(agent=SimpleNamespace(online_net=model,optimizer=optimizer,
            grad_scaler=SimpleNamespace(get_scale=lambda:65536.),
            _learning_optimizer_exposure=SimpleNamespace(snapshot=lambda:{'actual':'exposure'})),
            torch=SimpleNamespace(Tensor=Tensor),np=SimpleNamespace(any=any))
        empty=worker.optimizer_observation(ctx)
        optimizer.state[p]={'step':Tensor(0.),'exp_avg':Tensor(0.,0.),'exp_avg_sq':Tensor(0.,0.)}
        optimizer.state[q]={'step':Tensor(0.),'exp_avg':Tensor(0.),'exp_avg_sq':Tensor(0.)}
        self.assertEqual(worker.optimizer_observation(ctx),empty)
        optimizer.state[p]['step']=Tensor(5.)
        first=worker.optimizer_observation(ctx)
        optimizer.state[q]['step']=Tensor(1.)
        second=worker.optimizer_observation(ctx)
        self.assertEqual(max(first['adam_steps'].values()),max(second['adam_steps'].values()))
        self.assertNotEqual(first['adam_steps'],second['adam_steps'])
        optimizer.state[q]['exp_avg']=Tensor(.25)
        third=worker.optimizer_observation(ctx)
        self.assertNotEqual(second['adam_nonzero_state_sha256'],third['adam_nonzero_state_sha256'])
        self.assertEqual(third['exposure'],{'actual':'exposure'})

    def test_runtime_records_effective_gil_without_changing_it_or_importing_expert(self):
        ctx=SimpleNamespace(torch=SimpleNamespace(__version__='actual-torch',version=SimpleNamespace(cuda='actual-cuda')))
        with patch.object(worker.sys,'_is_gil_enabled',return_value=True,create=True) as gil, \
             patch.dict(worker.sys.modules,{'dqn.socket_server':SimpleNamespace(get_expert_action=None)}):
            details=worker.runtime_details(ctx)
            gil.assert_called_once_with()
        self.assertTrue(details['effective_gil_enabled'])
        self.assertFalse(details['expert_guidance_available'])
        self.assertFalse(details['expert_guidance_exercised'])
        self.assertEqual(details['torch'],'actual-torch')
        self.assertEqual(details['cuda'],'actual-cuda')


if __name__=='__main__':
    unittest.main()
