"""Authored, unexecuted stdlib controls; no Torch/PT/live-process work.

These exercise call budgets, durable-failure ordering, source factory and
proof joins. They cannot establish 4096 CUDA accuracy or feasibility.
"""
import ast
import contextlib
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import cuda_trace_parent as parent
from . import cuda_trace_worker as worker


class PriorityStatsContracts(unittest.TestCase):
    def test_small_negative_is_recorded_but_clamped_with_original_bound(self):
        worker.priority_statistics_contract([-1e-6, 2.0, 1.0, 1.0, 0.0, 1e-6, 1e-7], 0.0, 2.0)

    def test_material_negative_mass_and_negative_target_fail_closed(self):
        base=[0.1,2.0,0.0,0.0,0.0,1e-6,1e-7]
        for index,value in ((0,-1.1e-5),(4,-1e-7),(5,1.1e-5),(6,2e-6)):
            bad=list(base);bad[index]=value
            with self.subTest(index=index),self.assertRaises(RuntimeError):
                worker.priority_statistics_contract(bad,max(0.0,bad[0]),2.0)

    def test_nonfinite_fractional_or_impossible_counts_fail(self):
        base=[0.1,2.0,0.0,0.0,0.0,1e-6,1e-7]
        for index,value in ((0,float('nan')),(1,float('inf')),(2,.5),(3,4097.0)):
            bad=list(base);bad[index]=value
            with self.subTest(index=index),self.assertRaises(RuntimeError):
                worker.priority_statistics_contract(bad,.1,2.0)

    def test_clamp_extrema_cannot_disagree_with_same_forward_signed_stats(self):
        with self.assertRaises(RuntimeError):
            worker.priority_statistics_contract([-.000001,2.,1.,1.,0.,0.,0.],.01,2.)


class FactoryContracts(unittest.TestCase):
    def fixture(self):
        constants={name:False if name=='diagnostics' else 1 for name in worker.CONSTANT_NAMES}
        events=[]
        def constructor(label):
            def create(*args,**kwargs):
                events.append((label,args,kwargs));return SimpleNamespace(**constants)
            return create
        ctx=SimpleNamespace(original_loss=SimpleNamespace(TrainingLoss=constructor('original')),
            candidate=SimpleNamespace(TrainingLoss=constructor('candidate')),
            conditional=SimpleNamespace(compile_loss=lambda c,m:m),
            agent=SimpleNamespace(online_net=object(),target_net=object()))
        return ctx,dict(pre_context=dict(config={},kernel_constants=constants)),events

    def test_default_ce_omits_flag_and_kl_adds_only_true(self):
        ctx,payload,events=self.fixture()
        for route in worker.ROUTES:worker.make_kernel(ctx,payload,route)
        self.assertEqual([v[0] for v in events],['original','candidate','candidate'])
        self.assertEqual(events[0][2],dict(diagnostics=False))
        self.assertEqual(events[1][2],dict(diagnostics=False))
        self.assertEqual(events[2][2],dict(diagnostics=False,return_priorities=True))

    def test_captured_constant_mismatch_stops_before_compilation(self):
        ctx,payload,_=self.fixture();payload['pre_context']['kernel_constants']=dict(
            payload['pre_context']['kernel_constants'],gamma=99)
        with patch.object(ctx.conditional,'compile_loss',side_effect=AssertionError('no compile')):
            with self.assertRaisesRegex(RuntimeError,'constants differ'):
                worker.make_kernel(ctx,payload,'candidate_ce4')

    def test_predeclared_first_index_no_substitute(self):
        ctx=SimpleNamespace(manifest={'retained_inputs':{'attempts':[{'index':i} for i in range(1,9)]}},
            lock={'reconstruction_policy':{'attempt_indices':[1]},'stage_a':{'routes':list(worker.ROUTES)}})
        self.assertEqual(worker.selected_item(ctx),{'index':1})
        ctx.lock['reconstruction_policy']['attempt_indices']=[2]
        with self.assertRaises(RuntimeError):worker.selected_item(ctx)


class ForwardBackwardContracts(unittest.TestCase):
    def fixture(self,*,bad_output=False,bad_gradient=False,backward_error=False):
        events=[];parameter=SimpleNamespace(grad=None);target=SimpleNamespace(grad=None)
        class Loss:
            def backward(self):
                events.append('backward')
                if backward_error:raise RuntimeError('primary backward failure')
                parameter.grad='native-gradient'
        outputs=(Loss(),SimpleNamespace(shape=(4096,)),object(),SimpleNamespace(shape=(12,)))
        @contextlib.contextmanager
        def guards(ctx):
            calls=dict(optimizer_step=0,scaler_step=0,scaler_update=0)
            yield calls
        def save(ctx,path,value):
            events.append(Path(path).name);return dict(path=str(path),sha256='mock',bytes=1)
        def finite(ctx,value):
            events.append('finite-output' if value is outputs else 'finite-gradient')
            return not (bad_output if value is outputs else bad_gradient)
        net=lambda param:SimpleNamespace(named_parameters=lambda:[('weight',param)])
        ctx=SimpleNamespace(attempted_forward_routes=[],backward_routes=[],
            torch=SimpleNamespace(float16=object(),autocast=lambda **kw:contextlib.nullcontext(),
                cuda=SimpleNamespace(synchronize=lambda device:events.append('synchronize'))),
            science=SimpleNamespace(rng_state=lambda ctx:{'recorded':'rng'},finite=finite,cpu=lambda ctx,v:v),
            agent=SimpleNamespace(device='cuda:0',online_net=net(parameter),target_net=net(target)),
            conditional=SimpleNamespace(forbidden_offline_updates=guards,save_payload=save))
        kernel=lambda *args:outputs
        payload={'actual':{'ce':'captured-ce'}};item={'payload':{'path':'source.pt'},'receipt':{'path':'source.json'}}
        return ctx,kernel,payload,item,events

    def call(self,ctx,kernel,payload,item):
        return worker.one_forward_backward(ctx,kernel,[],object(),payload,item,'original4',{},Path('/uncreated/mock'))

    def test_raw_forward_precedes_interpretation_and_raw_gradient_precedes_finite(self):
        ctx,kernel,payload,item,events=self.fixture();values,raw,_,calls,_=self.call(ctx,kernel,payload,item)
        self.assertLess(events.index('raw-forward.pt'),events.index('finite-output'))
        self.assertLess(events.index('raw-preclip-gradients.pt'),events.index('finite-gradient'))
        self.assertEqual(ctx.attempted_forward_routes,['original4']);self.assertEqual(ctx.backward_routes,['original4'])
        self.assertEqual(values['gradients']['online']['weight'],'native-gradient')
        self.assertEqual(calls,dict(optimizer_step=0,scaler_step=0,scaler_update=0))

    def test_nonfinite_forward_is_retained_and_never_backpropagated(self):
        ctx,kernel,payload,item,events=self.fixture(bad_output=True)
        with self.assertRaisesRegex(RuntimeError,'Nonfinite output'):self.call(ctx,kernel,payload,item)
        self.assertIn('raw-forward.pt',events);self.assertNotIn('backward',events)
        self.assertEqual(ctx.attempted_forward_routes,['original4']);self.assertEqual(ctx.backward_routes,[])

    def test_nonfinite_gradient_is_retained_before_rejection(self):
        ctx,kernel,payload,item,events=self.fixture(bad_gradient=True)
        with self.assertRaisesRegex(RuntimeError,'Nonfinite unscaled gradients'):self.call(ctx,kernel,payload,item)
        self.assertIn('raw-preclip-gradients.pt',events);self.assertEqual(events.count('backward'),1)

    def test_backward_failure_counter_prevents_retry_and_preserves_forward(self):
        ctx,kernel,payload,item,events=self.fixture(backward_error=True)
        with self.assertRaisesRegex(RuntimeError,'primary backward failure'):self.call(ctx,kernel,payload,item)
        self.assertEqual(ctx.backward_routes,['original4']);self.assertIn('raw-forward.pt',events)
        self.assertIn('backward-failure.pt',events)
        with self.assertRaisesRegex(RuntimeError,'Duplicate/out-of-order'):self.call(ctx,kernel,payload,item)
        self.assertEqual(events.count('backward'),1)


class ProofContracts(unittest.TestCase):
    def result(self):
        tolerance={'rtol':2e-3,'atol':2e-6};ce={'rtol':2e-4,'atol':2e-5}
        fields={name:dict(passed=True,tolerance=ce if name=='ce' else tolerance)
                for name in ('ce','weighted_loss','bc_loss','diagnostic_values','gradients')}
        rows=[dict(route=route,index=1,status='OBSERVATIONS_COMPLETE',diagnostics=False,
            output_arity=5 if route=='candidate_kl5' else 4,update_guard_counts=dict(
                optimizer_step=0,scaler_step=0,scaler_update=0),model_before={'PRE':'same'},model_after={'PRE':'same'},
            explicit_unscaled_backward_calls=1,gradients_retained=True,target_all_grads_none=True,
            rng_observations=dict(pre='same',post_changed=False),priority_guard=dict(passed=True)) for route in worker.ROUTES]
        return dict(status='OBSERVATIONS_COMPLETE',variant='stage_a',qualification_pass=False,
            stage_b_required_before_adoption=True,comparison_pass=True,interpretation_requires_review=True,
            selected_original_index=1,forward_routes=list(worker.ROUTES),attempted_forward_routes=list(worker.ROUTES),
            backward_routes=list(worker.ROUTES),explicit_worker_backward_calls=3,actual_attempts_in_this_process=0,
            routes=rows,comparisons=dict(original4_vs_captured_actual=dict(passed=False,tolerance=ce),
                candidate_ce4_vs_original4=dict(passed=True,fields=copy.deepcopy(fields)),
                candidate_kl5_vs_candidate_ce4=dict(passed=True,fields=copy.deepcopy(fields))))

    def test_internal_pass_never_rescues_historical_residual_or_adopts(self):
        result=self.result();parent.result_contract(result,'stage_a')
        self.assertFalse(result['comparisons']['original4_vs_captured_actual']['passed'])
        self.assertFalse(result['qualification_pass']);self.assertTrue(result['stage_b_required_before_adoption'])

    def test_missing_route_extra_forward_or_changed_tolerance_rejected(self):
        for mutation in ('missing','extra','tolerance','update','no_stage_b'):
            result=self.result()
            if mutation=='missing':result['routes'].pop()
            elif mutation=='extra':result['attempted_forward_routes'].append('original4')
            elif mutation=='tolerance':result['comparisons']['candidate_ce4_vs_original4']['fields']['ce']['tolerance']['rtol']=1.
            elif mutation=='update':result['routes'][0]['update_guard_counts']['optimizer_step']=1
            else:result['stage_b_required_before_adoption']=False
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):parent.result_contract(result,'stage_a')

    def test_new_worker_preserves_preimport_bootstrap_and_owned_lifecycle(self):
        lock=json.loads((parent.HERE/'source-lock.json').read_text())
        old=ast.parse(Path(lock['route_helpers']['source']).read_text());new=ast.parse(Path(worker.__file__).read_text())
        function=lambda tree,name:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        self.assertEqual(ast.dump(function(old,'bootstrap')),ast.dump(function(new,'bootstrap')))
        previous=ast.parse(Path(lock['guard_predecessor']['source']).read_text());current=ast.parse(Path(parent.__file__).read_text())
        for name in ('owned_byte_count','scan_quality_processes','helpers','command','run_variant','configure_environment'):
            self.assertEqual(ast.dump(function(previous,name)),ast.dump(function(current,name)),name)

    def test_no_optimizer_clip_sampler_or_extra_forward_in_stage_a_source(self):
        tree=ast.parse(Path(worker.__file__).read_text());names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):names.append(node.func.attr)
        self.assertEqual(names.count('backward'),1)
        self.assertFalse(set(names)&{'step','update','clip_grad_norm_','sample','sample_with_metadata'})


if __name__=='__main__':
    unittest.main()
