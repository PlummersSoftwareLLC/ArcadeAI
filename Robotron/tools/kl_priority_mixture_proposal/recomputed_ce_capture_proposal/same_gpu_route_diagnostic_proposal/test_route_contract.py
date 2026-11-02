"""Source-only authored stdlib route/temp-file contracts; not imported or executed by author."""
import ast
import copy
from contextlib import contextmanager,nullcontext
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import cuda_trace_parent as parent
from . import cuda_trace_worker as worker


class RetainedInputContracts(unittest.TestCase):
    def write(self,path,value,mode=0o644):
        path.write_text(json.dumps(value,sort_keys=True));path.chmod(mode)
        return dict(path=str(path),sha256=parent.digest(path),bytes=path.stat().st_size)

    def row(self,index):
        identity=dict(current=True,lease_epoch=2,owner_epoch_at_consumption=2)
        return dict(index=index,capture_complete=True,optimizer_outcome='applied_admission',
            actual_exposure_delta=dict(amp_skipped=0,applied=1,attempts_started=1,outcomes_recorded=1,unavailable=0),
            draw_capture_id='sealed-session',draw_batch_join_checked=True,staged_draw_join_checked=True,
            backend='original_compiled4_diagnostics' if index==7 else 'original_compiled4',
            prefetch=dict(identity,sample_ms=3.0,stage_host_ms=4.0),
            prefetch_begin=copy.deepcopy(identity),prefetch_pre_loss=copy.deepcopy(identity),prefetch_exit=copy.deepcopy(identity),
            before=dict(training_steps=100+index,optimized_samples=4096*(100+index)),
            after=dict(training_steps=101+index,optimized_samples=4096*(101+index)))

    def fixture(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);directory=root/'captures';directory.mkdir()
        data=dict(schema='robotron-actual-ce-observational-analysis-inputs-v1',population='live_consecutive_consumed_attempts',
            actual_target_entropy_or_KL_observed=False,attempts=[])
        for name in ('producer_manifest','acquisition_review','maintenance_root_job'):
            data[name]=self.write(root/(name+'.json'),{})
        data['maintenance_result']=self.write(root/'result.json',dict(status='COMPLETE',capture_complete=True,manual_recovery_required=False))
        context=dict(schema='robotron-recomputed-ce-capture-v1',loss_abi=4,loss_sha256='a'*64,attempts=8,capture_id='sealed-session')
        data['context']=self.write(directory/'context.json',context,0o444)
        rows=[]
        for index in range(1,9):
            payload=directory/('attempt-%02d.payload.pt'%index)
            payload.write_bytes(b'opaque bytes; these tests never torch.load');payload.chmod(0o444)
            payload_pin=dict(path=str(payload),sha256=parent.digest(payload),bytes=payload.stat().st_size)
            row=self.row(index);row['payload']=dict(payload_pin,tensor_bytes=1)
            data['attempts'].append(dict(receipt=self.write(directory/('attempt-%02d.json'%index),row,0o444),payload=payload_pin))
            rows.append(row)
        final=dict(status='EIGHT_INPUT_CE_CAPTURES_COMPLETE',complete=True,attempts_consumed=8,observer_errors=[],rows=rows)
        data['final']=self.write(directory/'final.json',final,0o444)
        lock=dict(original_loss_sha256='a'*64)
        self.rebind(root,data,lock)
        return root,directory,data,lock

    def rebind(self,root,data,lock):
        item=self.write(root/'input-binding.json',data)
        lock['retained_input_binding']=dict(source=item['path'],sha256=item['sha256'],bytes=item['bytes'])

    def test_all8_original_five_key_leases_and_diagnostic7_bind_without_payload_reads(self):
        root,directory,data,lock=self.fixture();original=parent.stable_file
        def metadata_only(path,*args,**kwargs):
            self.assertFalse(str(path).endswith('.payload.pt'))
            return original(path,*args,**kwargs)
        with patch.object(parent,'stable_file',side_effect=metadata_only):
            bound=parent.bind_inputs(lock)
        self.assertEqual([row['index'] for row in bound['attempts']],list(range(1,9)))
        self.assertEqual(bound['capture_id'],'sealed-session')
        self.assertEqual(bound['attempts'][6]['payload']['identity']['mode'],0o444)

    def test_wrong_route_session_epoch_or_substitute_outcome_is_rejected(self):
        for kind in ('route','session','epoch','unavailable','index'):
            with self.subTest(kind=kind):
                row=self.row(7)
                if kind=='route':row['backend']='original_compiled4'
                if kind=='session':row['draw_capture_id']='other'
                if kind=='epoch':row['prefetch_exit']['lease_epoch']=3
                if kind=='unavailable':row['actual_exposure_delta']['unavailable']=1
                if kind=='index':row['index']=8
                with self.assertRaises(RuntimeError):parent.row_contract(row,7,'sealed-session')

    def test_missing_or_extra_original_attempt_never_forms_complete_population(self):
        for count in (7,9):
            with self.subTest(count=count):
                root,directory,data,lock=self.fixture()
                data['attempts']=data['attempts'][:count] if count==7 else data['attempts']+[data['attempts'][-1]]
                self.rebind(root,data,lock)
                with self.assertRaisesRegex(RuntimeError,'manifest differs'):parent.bind_inputs(lock)

    def test_final_original_row_mismatch_is_fatal_not_a_partial_subset(self):
        root,directory,data,lock=self.fixture()
        final=json.loads((directory/'final.json').read_text());final['rows'][3]['after']['training_steps']+=1
        (directory/'final.json').chmod(0o644)
        data['final']=self.write(directory/'final.json',final,0o444);self.rebind(root,data,lock)
        with self.assertRaisesRegex(RuntimeError,'row/final/payload'):parent.bind_inputs(lock)

    def test_payload_symlink_writable_or_wrong_index_path_fails_closed(self):
        for kind in ('symlink','writable','path'):
            with self.subTest(kind=kind):
                root,directory,data,lock=self.fixture();record=data['attempts'][0]['payload'];path=Path(record['path'])
                if kind=='symlink':
                    outside=root/'outside';outside.write_bytes(path.read_bytes());path.unlink();path.symlink_to(outside)
                if kind=='writable':path.chmod(0o644)
                if kind=='path':record=dict(record,path=str(directory/'attempt-02.payload.pt'))
                with self.assertRaises(RuntimeError):parent.payload_metadata(record,directory,1)

    def test_changed_JSON_between_bracketed_reads_is_rejected(self):
        root,directory,data,lock=self.fixture();record=data['maintenance_result'];original=parent.stable_file
        def mutate_after_first(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            Path(path).write_text('{"status":"changed"}')
            return result
        with patch.object(parent,'stable_file',side_effect=mutate_after_first):
            with self.assertRaises(RuntimeError):parent.bounded_json(record)


def route_record(route, changed=False):
    return dict(index=1, route=route, status='OBSERVATIONS_COMPLETE', diagnostics=False,
        output_arity=4 if route=='original4' else 5, model_before=dict(online='PRE',target='PRE'),
        model_after=dict(online='PRE',target='PRE'), all_grads_none=True,
        update_guard_counts=dict(optimizer_step=0,scaler_step=0,scaler_update=0),
        rng_observations=dict(pre='recorded-PRE',post='changed' if changed else 'recorded-PRE',post_changed=changed))


class FixedDiagnosticContracts(unittest.TestCase):
    def context(self):
        retained=dict(attempts=[dict(index=index,receipt=dict(path='row'),payload=dict(path='payload')) for index in range(1,9)])
        return SimpleNamespace(manifest=dict(retained_inputs=retained),
            lock=dict(reconstruction_policy=dict(attempt_indices=[1],forward_routes=['original4','conditional5'])),
            parent=SimpleNamespace(bind_inputs=lambda _:retained,SOURCE_LOCK_SHA256='lock'),
            torch=SimpleNamespace(cuda=SimpleNamespace(max_memory_allocated=lambda _:0,max_memory_reserved=lambda _:0)),
            paths=dict(root=Path('never-written-root')),variant='route1',route_results=[],attempted_forward_routes=[],
            conditional=SimpleNamespace(save_payload=lambda _ctx,path,_value:dict(path=str(path))))

    def test_predeclared_first_index_rejects_other_policy_and_disordered_population(self):
        ctx=self.context()
        self.assertIs(worker.selected_item(ctx),ctx.manifest['retained_inputs']['attempts'][0])
        ctx.lock['reconstruction_policy']['attempt_indices']=[2]
        with self.assertRaisesRegex(RuntimeError,'Predeclared'):worker.selected_item(ctx)
        ctx=self.context();ctx.manifest['retained_inputs']['attempts'].reverse()
        with self.assertRaisesRegex(RuntimeError,'acquisition'):worker.selected_item(ctx)

    def test_substitute_payload_rejected_before_read_or_load(self):
        with self.assertRaisesRegex(RuntimeError,'substitute'):
            worker.load_selected(SimpleNamespace(),dict(index=2))

    def test_finite_mismatches_keep_exact_two_routes_and_separate_reference_directions(self):
        ctx=self.context();events=[]
        def run(context,payload,row,item,route):
            events.append(('forward',route,item['index']))
            context.attempted_forward_routes.append(route);context.route_results.append(route_record(route))
            return dict(ce=route+'-CE')
        def compare(_ctx,actual,expected):
            events.append(('compare',actual,expected))
            return dict(passed=False,tolerance=dict(rtol=2e-4,atol=2e-5)), 'full-mask'
        ctx.conditional.compare_ce=compare
        with patch.object(worker,'load_selected',return_value=(dict(actual=dict(ce='captured-actual-CE')),{})), \
                patch.object(worker,'run_route',side_effect=run) as forward:
            result=worker.route_diagnostic(ctx)
        self.assertEqual(forward.call_count,2)
        self.assertEqual(events,[('forward','original4',1),('forward','conditional5',1),
            ('compare','original4-CE','captured-actual-CE'),('compare','conditional5-CE','original4-CE')])
        self.assertFalse(result['comparison_pass']);self.assertFalse(result['qualification_pass'])
        self.assertTrue(result['interpretation_requires_review']);parent.result_contract(result,'route1')

    def test_second_route_fault_retains_first_without_third_forward_or_partial_success(self):
        ctx=self.context()
        def run(context,payload,row,item,route):
            context.attempted_forward_routes.append(route)
            if route=='conditional5':raise RuntimeError('second route runtime fault')
            context.route_results.append(route_record(route));return dict(ce='first')
        with patch.object(worker,'load_selected',return_value=({},{})),patch.object(worker,'run_route',side_effect=run) as forward:
            with self.assertRaisesRegex(RuntimeError,'second route'):worker.route_diagnostic(ctx)
        self.assertEqual(forward.call_count,2)
        self.assertEqual([value['route'] for value in ctx.route_results],['original4'])
        self.assertEqual(ctx.attempted_forward_routes,['original4','conditional5'])


class RawRetentionContracts(unittest.TestCase):
    def fixture(self,finite=True):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);events=[];saved=[]
        @contextmanager
        def forbidden(_):
            events.append('guard');yield dict(optimizer_step=0,scaler_step=0,scaler_update=0)
        def save(_ctx,path,value):
            events.append('saved');saved.append(value);path.write_text('durable raw fixture')
            return dict(path=str(path))
        ctx=SimpleNamespace(attempted_forward_routes=[],agent=SimpleNamespace(device='cuda:0'),
            torch=SimpleNamespace(float16='float16',autocast=lambda **_:nullcontext(),
                cuda=SimpleNamespace(synchronize=lambda _:events.append('sync'))),
            science=SimpleNamespace(rng_state=lambda _:dict(state='post'),finite=lambda *_:finite,cpu=lambda _,value:value),
            conditional=SimpleNamespace(forbidden_offline_updates=forbidden,save_payload=save))
        return ctx,root,events,saved,dict(actual=dict(ce='actual')),dict(payload=dict(path='payload'),receipt=dict(path='row'))

    def test_raw_original4_is_persisted_before_nonfinite_rejection(self):
        ctx,root,events,saved,payload,item=self.fixture(finite=False)
        with self.assertRaisesRegex(RuntimeError,'Nonfinite'):
            worker.forward_and_retain(ctx,lambda *_:(1,'ce',2,'diag'),[],None,payload,item,'original4',{},root)
        self.assertEqual(events,['guard','sync','saved']);self.assertTrue((root/'raw-outputs.pt').exists())
        self.assertEqual(saved[0]['raw_outputs'],(1,'ce',2,'diag'))
        self.assertEqual(ctx.attempted_forward_routes,['original4'])

    def test_raw_conditional5_is_persisted_before_auxiliary_ABI_rejection(self):
        ctx,root,events,saved,payload,item=self.fixture();ctx.attempted_forward_routes=['original4']
        with self.assertRaisesRegex(RuntimeError,'auxiliary ABI'):
            worker.forward_and_retain(ctx,lambda *_:(1,'ce',2,'diag',()),[],None,payload,item,'conditional5',{},root)
        self.assertTrue((root/'raw-outputs.pt').exists());self.assertEqual(len(saved),1)
        self.assertEqual(ctx.attempted_forward_routes,['original4','conditional5'])

    def test_full_two_route_forward_fixture_and_duplicate_call_refusal(self):
        ctx,root,events,saved,payload,item=self.fixture()
        for route,outputs in (('original4',(1,'ce4',2,'diag')),('conditional5',(1,'ce5',2,'diag',tuple(range(10))))):
            directory=root/route;directory.mkdir()
            actual,record,rng,calls=worker.forward_and_retain(ctx,lambda *_:outputs,[],None,payload,item,route,{},directory)
            self.assertEqual(actual['ce'],'ce4' if route=='original4' else 'ce5')
            self.assertEqual(calls,dict(optimizer_step=0,scaler_step=0,scaler_update=0))
        with self.assertRaisesRegex(RuntimeError,'Duplicate/out-of-order'):
            worker.forward_and_retain(ctx,lambda *_:self.fail('third forward'),[],None,payload,item,'conditional5',{},root)
        self.assertEqual(len(saved),2)

    def test_reverse_route_is_rejected_before_any_numeric_operation(self):
        ctx,root,events,saved,payload,item=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'out-of-order'):
            worker.forward_and_retain(ctx,lambda *_:self.fail('reverse forward'),[],None,payload,item,'conditional5',{},root)
        self.assertEqual(events,[]);self.assertEqual(saved,[])


class PreRestorationContracts(unittest.TestCase):
    def test_actual_restore_pre_reloads_both_models_modes_inputs_and_schedule_each_time(self):
        class Tensor:
            dtype='float32';shape=(1,);device=SimpleNamespace(type='cpu')
            def __init__(self,label):self.label=label
            def to(self,device):return ('device-input',self.label,device)
        class Net:
            def __init__(self):self.value=Tensor('initial');self.mode=None
            def state_dict(self):return dict(weight=self.value)
            def load_state_dict(self,value,strict):self.value=value['weight'];self.strict=strict
            def train(self,mode):self.mode=mode
            def parameters(self):return [SimpleNamespace(requires_grad=True,grad=None)]
        online,target=Net(),Net()
        def digest(_ctx,value):return value['weight'].label
        ctx=SimpleNamespace(torch=SimpleNamespace(Tensor=Tensor,is_grad_enabled=lambda:True),
            science=SimpleNamespace(digest_tree=digest),agent=SimpleNamespace(online_net=online,target_net=target,device='cuda:0'))
        ctx.reconstruction=SimpleNamespace(snapshot=lambda _:dict(online=online.value.label,target=target.value.label))
        payload=dict(online=dict(weight=Tensor('online-PRE')),target=dict(weight=Tensor('target-PRE')),
            pre_context=dict(modes=dict(online=True,target=False)),schedule=Tensor('captured-schedule'),
            inputs={name:Tensor(name) for name in worker.INPUT_NAMES})
        for _ in range(2):
            inputs,schedule,before=worker.restore_pre(ctx,payload)
            self.assertEqual(before,dict(online='online-PRE',target='target-PRE'))
            self.assertEqual((online.mode,target.mode),(True,False));self.assertTrue(online.strict and target.strict)
            self.assertEqual(inputs,[('device-input',name,'cuda:0') for name in worker.INPUT_NAMES])
            self.assertEqual(schedule,('device-input','captured-schedule','cuda:0'))
            online.value=Tensor('external-fixture-mutation');target.value=Tensor('external-fixture-mutation')

    def test_run_route_resets_rng_after_factory_and_before_each_forward(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        events=[];root=Path(temporary.name);state=dict(online='PRE',target='PRE')
        ctx=SimpleNamespace(paths=dict(root=root),agent=SimpleNamespace(online_net=SimpleNamespace(parameters=lambda:[]),
            target_net=SimpleNamespace(parameters=lambda:[]),device='cuda:0'),route_results=[],base=SimpleNamespace(GPU0_UUID='GPU0'),
            reconstruction=SimpleNamespace(snapshot=lambda _:copy.deepcopy(state)),
            science=SimpleNamespace(restore_rng=lambda _,value:events.append('restore-rng'),
                rng_state=lambda _:dict(state='PRE'),digest_tree=lambda _,value:json.dumps(value,sort_keys=True)),
            parent=SimpleNamespace(stable_file=lambda *_args:dict(path='payload',sha256='hash',bytes=1)))
        payload=dict(rng=dict(state='PRE'),pre_context=dict(learner_device='cuda:0'))
        item=dict(payload=dict(path='payload',sha256='hash',bytes=1),receipt={});row=dict(optimizer_outcome='applied_admission')
        def restore(*_):events.append('restore-pre');return [],None,copy.deepcopy(state)
        def factory(*_):events.append('factory');return 'not-called-kernel'
        def forward(*_):
            events.append('forward');return dict(ce='CE'),{},dict(state='PRE'),dict(optimizer_step=0,scaler_step=0,scaler_update=0)
        with patch.object(worker,'restore_pre',side_effect=restore),patch.object(worker,'make_kernel',side_effect=factory), \
                patch.object(worker,'forward_and_retain',side_effect=forward), \
                patch.object(worker.sys,'_is_gil_enabled',return_value=False,create=True):
            for route in worker.ROUTES:worker.run_route(ctx,payload,row,item,route)
        self.assertEqual(events,['restore-pre','factory','restore-rng','forward']*2)
        self.assertEqual([value['route'] for value in ctx.route_results],list(worker.ROUTES))

    def test_original_factory_has_no_trace_keyword_and_conditional_has_explicit_trace(self):
        constants={name:False if name=='diagnostics' else 1 for name in worker.CONSTANT_NAMES};seen=[]
        def constructor(label):
            def build(*args,**kwargs):seen.append((label,kwargs));return SimpleNamespace(**constants)
            return build
        ctx=SimpleNamespace(agent=SimpleNamespace(online_net='online',target_net='target'),
            original_loss=SimpleNamespace(TrainingLoss=constructor('original4')),
            offline=SimpleNamespace(TrainingLoss=constructor('conditional5')),
            conditional=SimpleNamespace(compile_loss=lambda _,module:module))
        payload=dict(pre_context=dict(config={},kernel_constants=constants))
        for route in worker.ROUTES:worker.make_kernel(ctx,payload,route)
        self.assertEqual(seen,[('original4',dict(diagnostics=False)),('conditional5',dict(diagnostics=False,trace_rows=True))])


class ResultContracts(unittest.TestCase):
    def fixture(self):
        return dict(status='OBSERVATIONS_COMPLETE',variant='route1',qualification_pass=False,comparison_pass=True,
            interpretation_requires_review=False,selected_original_index=1,forward_routes=list(worker.ROUTES),
            attempted_forward_routes=list(worker.ROUTES),actual_attempts_in_this_process=0,executed_target_observed=False,
            grad_enabled=True,explicit_worker_backward_calls=0,routes=[route_record(route) for route in worker.ROUTES],
            comparisons={name:dict(passed=True,tolerance=dict(rtol=2e-4,atol=2e-5)) for name in
                ('original4_vs_captured_actual','conditional5_vs_local_original4')})

    def test_result_requires_fixed_index_two_routes_original_tolerances_and_false_qualification(self):
        parent.result_contract(self.fixture(),'route1')
        for kind in ('index','qualification','partial','tolerance','updates','pre','rng'):
            with self.subTest(kind=kind):
                result=self.fixture()
                if kind=='index':result['selected_original_index']=2
                if kind=='qualification':result['qualification_pass']=True
                if kind=='partial':result['routes'].pop()
                if kind=='tolerance':result['comparisons']['original4_vs_captured_actual']['tolerance']['rtol']=.1
                if kind=='updates':result['routes'][0]['update_guard_counts']['optimizer_step']=1
                if kind=='pre':
                    result['routes'][1]['model_before']=dict(online='other',target='PRE')
                    result['routes'][1]['model_after']=dict(online='other',target='PRE')
                if kind=='rng':result['routes'][1]['rng_observations']['pre']='other'
                with self.assertRaises(RuntimeError):parent.result_contract(result,'route1')

    def test_completed_numeric_mismatch_or_post_rng_change_remains_review_only(self):
        result=self.fixture();result['comparisons']['conditional5_vs_local_original4']['passed']=False
        result['comparison_pass']=False;result['interpretation_requires_review']=True
        parent.result_contract(result,'route1')
        result=self.fixture();result['routes'][1]['rng_observations']['post_changed']=True
        result['interpretation_requires_review']=True;parent.result_contract(result,'route1')


if __name__=='__main__':
    unittest.main()
