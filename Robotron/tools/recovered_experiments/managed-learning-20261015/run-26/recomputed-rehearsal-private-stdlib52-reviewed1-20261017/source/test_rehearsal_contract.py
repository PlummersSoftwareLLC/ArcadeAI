"""UNEXECUTED stdlib mock regressions; no Torch, NumPy, live or model inputs."""
import ast
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from . import cuda_trace_parent as parent
from . import cuda_trace_worker as worker


class RehearsalContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='robotron-rehearsal-mocks-')
        self.addCleanup(self.temporary.cleanup)
        self.output=Path(self.temporary.name)/'output'
        self.output.mkdir()

    def offline_context(self):
        events=[]
        class Optimizer:
            def register_step_pre_hook(self,hook):
                self.hook=hook
                return NS(remove=lambda:events.append('hook_removed'))
            def step(self):
                self.hook(self,(),{})
                events.append('real_optimizer_step')
        scaler=NS(step=lambda:events.append('real_scaler_step'),update=lambda:events.append('real_scaler_update'))
        ctx=NS(agent=NS(optimizer=Optimizer(),grad_scaler=scaler,device='owned-device'),
            paths={'root':self.output},torch=NS(float16='float16',
                autocast=lambda **kwargs:contextlib.nullcontext(),
                cuda=NS(synchronize=lambda device:events.append('sync'))),
            science=NS(rng_state=lambda ctx:{'post':'observed'},finite=lambda ctx,value:False))
        return ctx,events

    def test_offline_owned_adam_call_is_observed_rejected_and_guard_removed(self):
        ctx,events=self.offline_context()
        with self.assertRaisesRegex(RuntimeError,'optimizer_step'):
            with worker.forbidden_offline_updates(ctx):
                ctx.agent.optimizer.step()
        self.assertEqual(ctx.offline_update_guard_counts,dict(optimizer_step=1,scaler_step=0,scaler_update=0))
        self.assertEqual(events,['hook_removed'])

    def test_offline_scaler_calls_are_rejected_and_both_original_methods_restore(self):
        for name in ('step','update'):
            with self.subTest(name=name):
                ctx,events=self.offline_context()
                original=(ctx.agent.grad_scaler.step,ctx.agent.grad_scaler.update)
                with self.assertRaisesRegex(RuntimeError,'scaler_'+name):
                    with worker.forbidden_offline_updates(ctx):
                        getattr(ctx.agent.grad_scaler,name)()
                self.assertIs(ctx.agent.grad_scaler.step,original[0])
                self.assertIs(ctx.agent.grad_scaler.update,original[1])
                self.assertEqual(ctx.offline_update_guard_counts['scaler_'+name],1)
                self.assertEqual(events,['hook_removed'])

    def test_offline_nonfinite_outputs_and_full_expected_are_persisted_before_rejection(self):
        ctx,events=self.offline_context()
        sentinel=object()
        outputs=(sentinel,sentinel,sentinel,sentinel,tuple(sentinel for _ in range(10)))
        retained=[]
        path=self.output/'conditional-recomputed.pt'
        def save(context,destination,value):
            self.assertIs(value['raw_outputs'],outputs)
            self.assertEqual(value['expected_actual_capture'],{'ce':'original-observed'})
            self.assertEqual(value['source_capture_payload'],{'sha256':'original-payload'})
            retained.append(value)
            destination.write_bytes(b'full-returned-payload-stand-in')
            return {'path':str(destination)}
        with patch.object(worker,'save_payload',side_effect=save):
            with self.assertRaisesRegex(RuntimeError,'Nonfinite conditional'):
                worker.conditional_forward(ctx,lambda *args:outputs,[],None,
                    {'actual':{'ce':'original-observed'}},record={'sha256':'original-payload'},
                    row_record={},capture_record={},pre_rng={'pre':'original'})
        self.assertTrue(path.is_file())
        self.assertEqual(len(retained),1)
        self.assertEqual(events,['hook_removed','sync'])
        self.assertEqual(ctx.offline_update_guard_counts,dict(optimizer_step=0,scaler_step=0,scaler_update=0))

    def test_offline_wrong_output_abi_is_retained_before_rejection(self):
        ctx,_=self.offline_context()
        outputs=(object(),)
        seen=[]
        with patch.object(worker,'save_payload',side_effect=lambda ctx,path,value:seen.append(value) or {'saved':True}):
            with self.assertRaisesRegex(RuntimeError,'ABI differs'):
                worker.conditional_forward(ctx,lambda *args:outputs,[],None,{'actual':{}},
                    record={},row_record={},capture_record={},pre_rng={})
        self.assertIs(seen[0]['raw_outputs'],outputs)

    def exposure(self,*,applied=0,skipped=0,unavailable=0,started=0,recorded=0):
        return dict(process_id=123,instance_monotonic_ns=456,epoch=7,available=unavailable==0,
            total=dict(attempts_started=started,outcomes_recorded=recorded,
                       applied=applied,amp_skipped=skipped,unavailable=unavailable))

    def outcome_fixture(self,skip):
        before=dict(exposure=self.exposure(),persistent_finite=True,steps={'a':10.,'b':10.},
            online='old-online',moments='old-moments',scaler={'scale':1048576.},
            clocks={'training_steps':20,'optimized_samples':100000})
        after=copy.deepcopy(before)
        after['exposure']=self.exposure(applied=int(not skip),skipped=int(skip),started=1,recorded=1)
        after['clocks'].update(training_steps=21,optimized_samples=104096)
        if skip:
            after['scaler']['scale']=524288.
        else:
            after.update(steps={'a':11.,'b':10.},online='new-online',moments='new-moments')
        row=dict(actual_exposure_delta={name:after['exposure']['total'][name]-before['exposure']['total'][name]
            for name in before['exposure']['total']},outcome_available=True,
            optimizer_outcome='amp_skipped' if skip else 'applied_admission')
        return before,after,row

    def test_known_saved_scale_skip_is_retained_without_replacement(self):
        before,after,row=self.outcome_fixture(True)
        self.assertEqual(worker.optimizer_outcome(NS(),before,after,row)[0],'amp_skipped')

    def test_one_applied_admission_requires_actual_adam_and_logical_clock_progress(self):
        before,after,row=self.outcome_fixture(False)
        self.assertEqual(worker.optimizer_outcome(NS(),before,after,row)[0],'applied_admission')
        after['clocks']['optimized_samples']+=4096
        with self.assertRaisesRegex(RuntimeError,'clock must advance once'):
            worker.optimizer_outcome(NS(),before,after,row)

    def test_skip_with_changed_model_or_unavailable_outcome_fails(self):
        before,after,row=self.outcome_fixture(True)
        after['online']='unexpected-change'
        with self.assertRaisesRegex(RuntimeError,'Skip lacks'):
            worker.optimizer_outcome(NS(),before,after,row)
        before,after,row=self.outcome_fixture(True)
        after['exposure']['total']['unavailable']=1
        with self.assertRaisesRegex(RuntimeError,'unavailable or ambiguous'):
            worker.optimizer_outcome(NS(),before,after,row)

    def test_primary_training_exception_survives_close_sync_and_publication_failures(self):
        calls=[]
        primary=ValueError('actual-original-train-failure')
        directory=self.output/'capture/ce-recomputed-capture-private-one'
        directory.parent.mkdir()
        observer=NS(consumed=0,current=None,raw=None)
        lease=NS(is_current=True,draw_metadata={},_epoch=0,_released=False)
        def release():
            calls.append('release');lease._released=True
        lease.release=release
        def close(**kwargs):
            calls.append('close');raise OSError('secondary-close')
        producer=NS(get=lambda **kwargs:lease,close=close,produced_batches=1,direct_state_batches=1)
        def sync(device):
            calls.append('sync');raise OSError('secondary-sync')
        def publish(path,value):
            if path.name=='producer-cleanup.json':
                calls.append('cleanup-publication');raise OSError('secondary-publication')
        def train(*args):
            calls.append('train');raise primary
        ctx=NS(torch=NS(cuda=NS(synchronize=sync)),science=NS(make_private_replay=lambda ctx:object(),
            optimizer_observation=lambda ctx:{}),agent=NS(device='owned',_learning_optimizer_exposure=object(),
                grad_scaler=NS(get_scale=lambda:1048576.,state_dict=lambda:{'_growth_tracker':27})),
            paths={'root':directory.parent},cfg=NS(),runtime={},requires_grad={},
            training=NS(replay_pressure_reached=lambda agent:False,train_step=train,_beta_schedule=lambda frames:1.),
            loss=NS(TrainingLoss=lambda *args,**kwargs:object(),__file__='never-read'),
            native=NS(batch_update_status=lambda:{}),prefetch=NS(ReplayPrefetcher=lambda *args,**kwargs:producer),
            lock={'checkpoint':{'grad_scaler_scale':1048576.,'grad_scaler_growth_tracker':27}},
            metrics=NS(frame_count=0),parent=NS(SOURCE_LOCK_SHA256='mock-lock',digest=lambda path:'mock-source'))
        module=NS(RecomputedCECapture=lambda *args,**kwargs:observer,ATTEMPTS=8)
        with patch.dict(worker.os.environ,{'DQN_RECOMPUTED_CE_CAPTURE_DIR':str(directory)}), \
                patch.object(worker.importlib,'import_module',return_value=module), \
                patch.object(worker,'compile_loss',return_value=object()), \
                patch.object(worker,'write_json',side_effect=publish), \
                patch.object(worker,'print',side_effect=BrokenPipeError('secondary-log-failure'),create=True), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ValueError) as caught:
                worker.capture(ctx)
        self.assertIs(caught.exception,primary)
        self.assertEqual(calls,['train','release','close','sync','cleanup-publication'])
        self.assertEqual(len(ctx.capture_cleanup_errors),3)
        self.assertIn('actual-original-train-failure',ctx.capture_primary_failure['traceback'])

    def test_bootstrap_ownership_body_is_exact_frozen_warmup_body(self):
        source=parent.GAME/'tools/kl_priority_mixture_proposal/cuda_trace_validation_proposal/warmup_repeatability_proposal/cuda_trace_worker.py'
        def function(path,name):
            return next(node for node in ast.parse(path.read_text()).body
                        if isinstance(node,ast.FunctionDef) and node.name==name)
        self.assertEqual(ast.dump(function(source,'bootstrap')),ast.dump(function(Path(worker.__file__),'bootstrap')))


if __name__=='__main__':
    unittest.main()
