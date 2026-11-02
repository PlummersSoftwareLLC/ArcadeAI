"""Authored stdlib/temp-file mocks only; author has not imported/run them."""
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


class OfflineLoopContracts(unittest.TestCase):
    def fixture(self):
        retained=dict(attempts=[dict(index=index) for index in range(1,9)])
        return SimpleNamespace(manifest=dict(retained_inputs=retained),lock={},rows=[],attempted_forward_indices=[],
            parent=SimpleNamespace(bind_inputs=lambda _:retained,SOURCE_LOCK_SHA256='source'),
            torch=SimpleNamespace(cuda=SimpleNamespace(max_memory_allocated=lambda _:0,max_memory_reserved=lambda _:0)),
            variant='recompute8')

    def test_finite_mismatch_continues_all8_without_replacement_or_qualification(self):
        ctx=self.fixture()
        def one(context,item):
            index=item['index'];context.attempted_forward_indices.append(index)
            return dict(index=index,comparison_pass=index!=3,interpretation_requires_review=index==3)
        with patch.object(worker,'reconstruct_one',side_effect=one) as operation:
            result=worker.recompute8(ctx)
        self.assertEqual(operation.call_count,8)
        self.assertEqual(ctx.attempted_forward_indices,list(range(1,9)))
        self.assertFalse(result['comparison_pass']);self.assertFalse(result['qualification_pass'])
        self.assertTrue(result['interpretation_requires_review'])

    def test_structural_fault_keeps_completed_prefix_and_no_fewer_rows_success(self):
        ctx=self.fixture()
        def one(context,item):
            context.attempted_forward_indices.append(item['index'])
            if item['index']==3:raise RuntimeError('structural fault')
            return dict(index=item['index'],comparison_pass=True,interpretation_requires_review=False)
        with patch.object(worker,'reconstruct_one',side_effect=one):
            with self.assertRaisesRegex(RuntimeError,'structural'):worker.recompute8(ctx)
        self.assertEqual([row['index'] for row in ctx.rows],[1,2])
        self.assertEqual(ctx.attempted_forward_indices,[1,2,3])

    def forward_fixture(self,finite=True):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);events=[]
        @contextmanager
        def forbidden(_):yield dict(optimizer_step=0,scaler_step=0,scaler_update=0)
        def save(_ctx,path,value):
            events.append('saved');Path(path).write_text('retained raw before interpretation')
            return dict(path=str(path),sha256='raw',bytes=1)
        ctx=SimpleNamespace(attempted_forward_indices=[],agent=SimpleNamespace(device='cuda:0'),
            torch=SimpleNamespace(float16='float16',autocast=lambda **_:nullcontext(),cuda=SimpleNamespace(synchronize=lambda _:events.append('sync'))),
            science=SimpleNamespace(rng_state=lambda _:dict(state='after'),finite=lambda *_:finite),
            conditional=SimpleNamespace(forbidden_offline_updates=forbidden,save_payload=save))
        payload=dict(actual=dict(ce='original'),inputs=dict(weights='original-emitted-weights'))
        item=dict(payload=dict(path='original-payload'),receipt=dict(path='original-row'))
        return ctx,root,events,payload,item

    def test_nonfinite_full_raw_is_durable_before_fatal_interpretation(self):
        ctx,root,events,payload,item=self.forward_fixture(finite=False)
        outputs=(0,'ce',0,'diagnostics',tuple(range(10)))
        with self.assertRaisesRegex(RuntimeError,'Nonfinite conditional'):
            worker.forward_and_retain(ctx,lambda *_:outputs,[],None,payload,item,{},1,{},root)
        self.assertEqual(events,['sync','saved'])
        self.assertTrue((root/'conditional-recomputed.pt').exists())
        self.assertEqual(ctx.attempted_forward_indices,[1])

    def test_wrong_ABI_is_retained_and_duplicate_forward_cannot_retry(self):
        ctx,root,events,payload,item=self.forward_fixture()
        with self.assertRaisesRegex(RuntimeError,'ABI differs'):
            worker.forward_and_retain(ctx,lambda *_:(1,2,3,4),[],None,payload,item,{},1,{},root)
        self.assertTrue((root/'conditional-recomputed.pt').exists())
        with self.assertRaisesRegex(RuntimeError,'Duplicate'):
            worker.forward_and_retain(ctx,lambda *_:self.fail('second call'),[],None,payload,item,{},1,{},root)

    def test_source_import_closure_has_no_synthetic_training_or_replay_execution(self):
        tree=ast.parse(Path(worker.__file__).read_text())
        modules={node.args[0].value for node in ast.walk(tree) if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute) and node.func.attr=='import_module'
            and node.args and isinstance(node.args[0],ast.Constant)}
        self.assertEqual(modules,{'dqn.config','dqn.model','dqn.offline_loss_kernel'})
        self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
            and node.func.attr in ('backward','train_step','sample_with_metadata','observe_steps','copy_fixture')
            for node in ast.walk(tree)))


class CompactPayloadContracts(unittest.TestCase):
    class Mask:
        def __init__(self,values):self.values=values
        def __and__(self,other):return CompactPayloadContracts.Mask([a and b for a,b in zip(self.values,other.values)])

    class Tensor:
        def __init__(self,values,shape,dtype='float32'):
            self.values=values;self.shape=shape;self.dtype=dtype;self.device=SimpleNamespace(type='cpu')
        def __ge__(self,other):return CompactPayloadContracts.Mask([value>=other for value in self.values])
        def __le__(self,other):return CompactPayloadContracts.Mask([value<=other for value in self.values])
        def __lt__(self,other):return CompactPayloadContracts.Mask([value<other for value in self.values])

    def fixture(self):
        tensor=self.Tensor
        torch=SimpleNamespace(Tensor=tensor,float32='float32',long='long',bool='bool',
            as_tensor=lambda value,dtype,device:tensor(value.values,value.shape,dtype),
            equal=lambda a,b:a.values==b.values and a.dtype==b.dtype and a.shape==b.shape,
            all=lambda mask:all(mask.values),get_float32_matmul_precision=lambda:'high',
            backends=SimpleNamespace(cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True)),
                cudnn=SimpleNamespace(allow_tf32=True,benchmark=True)))
        row=RetainedInputContracts().row(1);row['at_loss']=copy.deepcopy(row['before'])
        inputs={name:tensor([-.25,1.5] if name in ('states','next_states') else [0,80] if name=='actions' else [0,1],
            (4096,11128) if name in ('states','next_states') else (4096,),
            'long' if name=='actions' else 'bool' if name=='is_expert' else 'float32') for name in worker.INPUT_NAMES}
        pre=dict(config={},loss_sha256='loss4',use_amp=True,modes=dict(online=True,target=False),clocks=row['at_loss'],
            learner_device='cuda:0',schedule_device='cuda:0',input_devices=['cuda:0']*8,
            kernel_constants=dict(diagnostics=False),matmul_precision='high',tf32_matmul=True,tf32_cudnn=True,cudnn_benchmark=True)
        payload=dict(attempt=1,capture_id='sealed-session',nonfinite_copies=0,pre_context=pre,
            draw=dict(capture_id='sealed-session',schema='robotron-replay-draw-observation-v1',
                supplied_weights_float32=copy.deepcopy(inputs['weights']),
                small_batch_fields={name:copy.deepcopy(inputs[name]) for name in ('actions','rewards','dones','horizons','is_expert')}),
            outcome=copy.deepcopy(row),inputs=inputs,schedule=tensor([0,0,0],(3,)),actual=dict(ce=tensor([2,3],(4096,))))
        ctx=SimpleNamespace(torch=torch,context=dict(capture_id='sealed-session',config={}),
            lock=dict(original_loss_sha256='loss4'),science=SimpleNamespace(finite=lambda *_:True))
        return ctx,payload,row

    def test_compact_receipt_without_draw_and_signed_or_large_live_states_are_accepted(self):
        ctx,payload,row=self.fixture()
        self.assertNotIn('draw',row)
        self.assertEqual(payload['inputs']['states'].values,[-.25,1.5])
        worker.payload_contract(ctx,payload,row,1)

    def test_authentic_payload_draw_weight_or_small_field_mismatch_is_fatal(self):
        for kind in ('weights','actions'):
            with self.subTest(kind=kind):
                ctx,payload,row=self.fixture()
                if kind=='weights':payload['draw']['supplied_weights_float32'].values=[9,9]
                else:payload['draw']['small_batch_fields']['actions'].values=[1,2]
                with self.assertRaisesRegex(RuntimeError,'Consumed'):worker.payload_contract(ctx,payload,row,1)

    def test_raw_outcome_must_join_receipt_independent_of_its_missing_draw_vectors(self):
        ctx,payload,row=self.fixture();payload['outcome']['after']['training_steps']+=1
        with self.assertRaisesRegex(RuntimeError,'Raw outcome'):worker.draw_contract(payload,row,'sealed-session')


class PhaseResultContracts(unittest.TestCase):
    def fixture(self):
        calls=dict(optimizer_step=0,scaler_step=0,scaler_update=0)
        return dict(status='OBSERVATIONS_COMPLETE',variant='recompute8',qualification_pass=False,comparison_pass=True,
            interpretation_requires_review=False,optimizer_steps=0,explicit_worker_backward_calls=0,update_guard_counts=calls,
            grad_enabled=True,conditional_recomputed=True,executed_target_observed=False,actual_attempts_in_this_process=0,
            attempts=[dict(index=index,status='OBSERVATIONS_COMPLETE',qualification_pass=False,comparison_pass=True,
                interpretation_requires_review=False,ce_comparison=dict(passed=True,tolerance=dict(rtol=2e-4,atol=2e-5)),
                diagnostics=index==7,original_optimizer_outcome='applied_admission',update_guard_counts=copy.deepcopy(calls))
                for index in range(1,9)])

    def test_finite_mismatch_can_complete_only_with_truthful_all8_aggregate(self):
        result=self.fixture();result['attempts'][2]['comparison_pass']=False
        result['attempts'][2]['ce_comparison']['passed']=False;result['attempts'][2]['interpretation_requires_review']=True
        result.update(comparison_pass=False,interpretation_requires_review=True)
        parent.result_contract(result,'recompute8')
        result['comparison_pass']=True
        with self.assertRaisesRegex(RuntimeError,'Aggregate'):parent.result_contract(result,'recompute8')

    def test_missing_route_tolerance_change_or_qualification_cannot_pass(self):
        for kind in ('missing','route','tolerance','qualification'):
            with self.subTest(kind=kind):
                result=self.fixture()
                if kind=='missing':result['attempts'].pop()
                if kind=='route':result['attempts'][6]['diagnostics']=False
                if kind=='tolerance':result['attempts'][0]['ce_comparison']['tolerance']['atol']=2e-4
                if kind=='qualification':result['qualification_pass']=True
                with self.assertRaises(RuntimeError):parent.result_contract(result,'recompute8')


if __name__=='__main__':
    unittest.main()
