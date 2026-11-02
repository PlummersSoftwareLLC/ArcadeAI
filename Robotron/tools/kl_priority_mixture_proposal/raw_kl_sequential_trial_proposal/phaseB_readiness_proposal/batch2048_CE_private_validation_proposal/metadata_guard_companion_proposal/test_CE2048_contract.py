"""Stdlib synthetic metadata guards; no tensor, numerical or runtime proof."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
BUNDLE=HERE.parent
manifest=json.loads((BUNDLE/'preparation-manifest.json').read_bytes())
assert hashlib.sha256((BUNDLE/'preparation-manifest.json').read_bytes()).hexdigest()=='9a1b0189a6dc5ae552bd16404d745227202a9da24c9dfd7e4654725fce8914c7'

def module(name):
    path=BUNDLE/(name+'.py')
    expected=next(p for p in manifest['files'] if p['path']==str(path))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected['sha256']
    spec=importlib.util.spec_from_file_location('_CE2048_guard_'+name,path)
    result=importlib.util.module_from_spec(spec);sys.modules[spec.name]=result
    spec.loader.exec_module(result)
    return result

worker=module('cuda_trace_worker')
parent=module('cuda_trace_parent')

class MetadataTensor:
    """Small row labels with a virtual shape, explicitly not a tensor."""
    def __init__(self,rows,tail=(),dtype='float32'):
        self.rows=tuple(rows);self.shape=(len(self.rows),*tail);self.dtype=dtype
    def __getitem__(self,key):return MetadataTensor(self.rows[key],self.shape[1:],self.dtype)
    def numpy(self):return self.rows
    def tolist(self):return list(self.rows)
    def detach(self):return self
    def cpu(self):return self

def payload():
    return dict(inputs={k:MetadataTensor(range(4096),(11128,) if k in ('states','next_states') else ()) for k in worker.INPUT_NAMES},
        draw=dict(indices=MetadataTensor(range(10000,14096)),small_batch_fields=dict(actor_kind=list(range(4096)))),rng=object())

def pressure_context():
    path=BUNDLE.parents[1]/'training.py'
    expected='90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4'
    text=path.read_text();assert hashlib.sha256(text.encode()).hexdigest()==expected
    f=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='replay_pressure_reached')
    metrics=SimpleNamespace(lock=threading.RLock(),frame_count=905164910,learner_frame_count=452630871,
        measurement_frame_count=7550388,loaded_frame_count=905164910,loaded_measurement_frame_count=7550388,loaded_optimized_samples=7387004928)
    cfg=SimpleNamespace(min_replay_to_train=500000,batch_size=2048,baseline_batch_size=512,max_samples_per_frame=8)
    namespace=dict(metrics=metrics,RL_CONFIG=cfg)
    exec(compile(ast.Module(body=[f],type_ignores=[]),'<exact-held-pressure>','exec'),namespace)
    class Eligible:
        def __len__(self):return 6000000
    agent=SimpleNamespace(training_steps=2156883,optimized_samples=7387004928,loaded_training_steps=2156883,memory=Eligible())
    clocks=dict(training_steps=agent.training_steps,optimized_samples=agent.optimized_samples,frame_count=metrics.frame_count,learner_frame_count=metrics.learner_frame_count)
    return SimpleNamespace(agent=agent,metrics=metrics,cfg=cfg,frame_credit_ledger=[],loaded=dict(clocks=clocks),
        expected=dict(measurement_frame_count=7550388),training=SimpleNamespace(replay_pressure_reached=namespace['replay_pressure_reached']))

def observer_context(count=4,rows=2048,diagnostics=12):
    calls=[]
    values=(1.0,MetadataTensor(range(rows)),0.0,MetadataTensor(range(diagnostics)))
    if count==5:values=values+(MetadataTensor(range(rows)),)
    def loss(*args,**kwargs):calls.append('loss');return values
    agent=SimpleNamespace(compiled_training_loss=loss,compiled_training_loss_diagnostics=loss,memory=SimpleNamespace(active_forward=None),
        optimizer=SimpleNamespace(param_groups=[dict(lr=2.5e-5)]),grad_scaler=SimpleNamespace(step=lambda *a:None,update=lambda *a:None),
        _learning_optimizer_exposure=SimpleNamespace(finish=lambda *a:None))
    ctx=SimpleNamespace(agent=agent,torch=SimpleNamespace(float32='float32',nn=SimpleNamespace(utils=SimpleNamespace(clip_grad_norm_=lambda *a:0))),
        science=SimpleNamespace(cpu=lambda ctx,value:value,finite=lambda ctx,value:True))
    return ctx,calls,MetadataTensor([1,2,3])

class CE2048Contracts(unittest.TestCase):
    def test_default_parent_reads_no_helpers_and_does_not_launch(self):
        with patch.object(parent,'read_lock',side_effect=AssertionError('no helpers')),contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(parent.main([]),0)
        value=json.loads(stream.getvalue());self.assertEqual(value['batch_rows'],2048)
        self.assertEqual(value['role_attempts'],dict(ce18=18,resume=0,restart_ce=0));self.assertFalse(value['launch'])

    def test_subset_preserves_exact_order_and_source_objects(self):
        original=payload();selected=worker.fixed_subset(original)
        for key,value in original['inputs'].items():
            self.assertEqual(value.shape[0],4096)
            self.assertEqual(selected['inputs'][key].rows,value.rows[:2048])
            self.assertEqual(selected['inputs'][key].shape,(2048,*value.shape[1:]))
        self.assertEqual(selected['draw']['indices'].rows,tuple(range(10000,12048)))
        self.assertEqual(selected['draw']['small_batch_fields']['actor_kind'],list(range(2048)))
        self.assertEqual(original['draw']['small_batch_fields']['actor_kind'],list(range(4096)))
        self.assertIs(selected['rng'],original['rng'])

    def test_subset_refuses_wrong_original_shapes(self):
        for key in worker.INPUT_NAMES:
            source=payload();source['inputs'][key]=MetadataTensor(range(2048))
            with self.subTest(key=key),self.assertRaises(RuntimeError):worker.fixed_subset(source)

    def test_subset_refuses_misaligned_draw_indices_and_actor_rows(self):
        source=payload();source['draw']['indices']=MetadataTensor(range(4095))
        with self.assertRaises(RuntimeError):worker.fixed_subset(source)
        source=payload();source['draw']['small_batch_fields']['actor_kind'].pop()
        with self.assertRaises(RuntimeError):worker.fixed_subset(source)

    def test_eighteen_actual_pressure_predicate_boundaries_no_nineteenth(self):
        ctx=pressure_context()
        for ordinal in range(1,19):
            row=worker.grant_frame_credit(ctx,ordinal);self.assertEqual(row['synthetic_frames'],256)
            self.assertFalse(ctx.training.replay_pressure_reached(ctx.agent))
            ctx.agent.training_steps+=1;ctx.agent.optimized_samples+=2048
            self.assertTrue(ctx.training.replay_pressure_reached(ctx.agent))
        self.assertEqual(ctx.metrics.frame_count,905164910+4608)
        self.assertEqual(ctx.metrics.learner_frame_count,452630871)
        with self.assertRaises(RuntimeError):worker.grant_frame_credit(ctx,19)

    def test_ledger_refuses_rollback_and_wrong_ordinals(self):
        ctx=pressure_context()
        with self.assertRaises(RuntimeError):worker.grant_frame_credit(ctx,2)
        self.assertFalse(ctx.frame_credit_ledger)
        ctx.metrics.loaded_optimized_samples+=1
        with self.assertRaises(RuntimeError):worker.grant_frame_credit(ctx,1)
        self.assertFalse(ctx.frame_credit_ledger)

    def test_real_observer_accepts_four_ce_outputs_and_joins_same_ce_vector(self):
        for diagnostic in (False,True):
            ctx,calls,schedule=observer_context();observer=worker.StepObservers(ctx).install()
            try:
                method=ctx.agent.compiled_training_loss_diagnostics if diagnostic else ctx.agent.compiled_training_loss
                result=method(schedule)
                self.assertEqual(len(result),4);self.assertEqual(calls,['loss'])
                self.assertEqual(observer.forward['ce'],observer.forward['priority'])
                self.assertEqual(observer.forward['diagnostic'],diagnostic)
                self.assertIs(ctx.agent.memory.active_forward,observer.forward)
                with self.assertRaises(RuntimeError):method(schedule)
            finally:observer.close()

    def test_real_observer_rejects_kl_five_output_and_wrong_ce_geometry(self):
        for options in [dict(count=5),dict(rows=4096),dict(diagnostics=19)]:
            ctx,calls,schedule=observer_context(**options);observer=worker.StepObservers(ctx).install()
            try:
                with self.subTest(options=options),self.assertRaises(RuntimeError):ctx.agent.compiled_training_loss(schedule)
                self.assertEqual(calls,['loss'])
            finally:observer.close()

    def test_actual_phase_environment_is_ce2048_in_all_roles(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(parent,'_BASE',SimpleNamespace(configure_environment=lambda *a:{})))
            stack.enter_context(patch.object(Path,'is_file',return_value=True))
            stack.enter_context(patch.object(Path,'is_symlink',return_value=False))
            stack.enter_context(patch.object(parent,'digest',return_value='a'*64))
            layout=parent.Layout(Path('/synthetic/output'),'fixture')
            for role in parent.VARIANTS:
                env=parent.configure_environment(layout,role)
                self.assertEqual(env['DQN_BATCH_SIZE'],'2048');self.assertEqual(env['DQN_PER_PRIORITY_METRIC'],'ce')

if __name__=='__main__':unittest.main()
