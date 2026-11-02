"""CPU-only behavioral fixtures for prepared sources; no Torch/model/GPU import."""
import ast
import copy
from collections import defaultdict
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[3]
spec=importlib.util.spec_from_file_location('learning_exposure_proposed',HERE/'proposed/learning_exposure.py')
ex=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ex;spec.loader.exec_module(ex)


def methods(path,names):
    tree=ast.parse(path.read_text())
    return [n for cls in tree.body if isinstance(cls,ast.ClassDef) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]


def replay_type(folder):
    tree=ast.parse((HERE/folder/'replay_buffer.py').read_text())
    selected={'add','clear','flush','_restore_from_arrays','_try_adopt_mmap_directory','_storage_specs',
        '_sanitize_interesting_after_load_locked','_rebuild_interesting_bank_locked','get_learning_exposure_snapshot'}
    nodes=[next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SumTree')]
    nodes+=methods(HERE/folder/'replay_buffer.py',selected)
    namespace=dict(np=np,threading=threading,time=time,os=os,RL_CONFIG=SimpleNamespace(),ACTOR_KIND_COUNT=3,
        ACTOR_DQN=0,ACTOR_EPSILON=1,ACTOR_EXPERT=2,_native_propagate=None,_native_batch_update=None,
        _native_gather_fp16_rows=None,exposure_disabled_snapshot=ex.disabled_snapshot)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(HERE/folder), 'exec'),namespace)
    return type('TinyReplay',(),{n.name:namespace[n.name] for n in nodes[1:]}),namespace['SumTree']


def replay(folder='proposed',enabled=True):
    cls,tree=replay_type(folder);m=cls();m.lock=threading.Lock();m.capacity=3;m.state_size=2;m.alpha=.7
    for name,dtype,shape in [('states',np.float16,(3,2)),('next_states',np.float16,(3,2)),
        ('actions',np.int64,(3,)),('rewards',np.float32,(3,)),('dones',np.float32,(3,)),
        ('horizons',np.int32,(3,)),('is_expert',np.uint8,(3,)),('actor_kind',np.uint8,(3,)),('interesting',np.float32,(3,))]:
        setattr(m,name,np.zeros(shape,dtype=dtype))
    m.tree=tree(3);m.size=0;m._n_expert=0;m._n_actor=np.zeros(3,dtype=np.int64);m._n_interesting=0
    m._interesting_bank=np.full(4,-1,dtype=np.int64);m._interesting_bank_ptr=0;m._interesting_bank_count=0
    m._adds_total=0;m._mmap_dir=None;m._progress_bar=lambda *args:None
    m._insert_exposure=ex.ReplayInsertExposure() if enabled else None
    return m


def add(m,source='dqn',state=(1,2),expert=None):
    kind={'dqn':0,'epsilon':1,'expert':2,'eval':0}.get(source,0)
    expert=int(source=='expert') if expert is None else expert
    kwargs=dict(actor_kind=kind)
    if hasattr(m,'get_learning_exposure_snapshot'):kwargs['source_actor']=source
    m.add(state,1,.5,(2,3),False,expert=expert,**kwargs)


class Device:
    type='cuda'
    def __init__(self,index=0):self.index=index
    def __eq__(self,other):return isinstance(other,Device) and self.index==other.index
    def __hash__(self):return hash(self.index)


class Tensor:
    ndim=0;dtype='torch.float32';requires_grad=False
    def __init__(self,device=None):self.device=device or Device()
    def item(self):raise AssertionError('extra item/synchronization')
    def __float__(self):raise AssertionError('Tensor float would synchronize')
    cpu=to=clone=detach=item


class Adam:
    def __init__(self):self.param_groups=[dict(fused=True)];self._step_supports_amp_scaling=True
    def step(self):pass


class Scaler:
    def __init__(self,optimizer,tensor):
        self._enabled=True
        self._per_optimizer_states=defaultdict(lambda:(_ for _ in ()).throw(AssertionError('state autovivified')))
        self._per_optimizer_states[id(optimizer)]=dict(stage=SimpleNamespace(name='UNSCALED'),found_inf_per_device={tensor.device:tensor})


def captured(scaler,optimizer,device=Device()):
    return ex.capture_amp_found_inf(scaler,optimizer,device,is_tensor=lambda x:isinstance(x,Tensor),
        adam_type=Adam,scaler_type=Scaler,torch_version=ex.SUPPORTED_TORCH)


class ExposureProposalTests(unittest.TestCase):
    def test_default_flag_no_Torch_and_no_default_output_change(self):
        self.assertFalse(ex.exposure_enabled({}))
        self.assertFalse(ex.exposure_enabled({'DQN_LEARNING_EXPOSURE_COUNTERS':'garbage'}))
        self.assertTrue(ex.exposure_enabled({'DQN_LEARNING_EXPOSURE_COUNTERS':'1'}))
        a,b=replay('before',False),replay('proposed',False)
        for tag in ['dqn','epsilon','expert','eval','dqn']:
            add(a,tag);add(b,tag)
        for name in a._storage_specs():np.testing.assert_array_equal(getattr(a,name),getattr(b,name))
        np.testing.assert_array_equal(a.tree.tree,b.tree.tree)
        self.assertEqual(a._adds_total,b._adds_total)
        self.assertFalse(b.get_learning_exposure_snapshot()['enabled'])
        self.assertFalse(any(name=='torch' or name.startswith('torch.') for name in sys.modules))

    def test_accepted_only_after_success_wrap_expert_eval_unknown_and_snapshot_copy(self):
        m=replay()
        for tag in ['dqn','epsilon','expert','eval',None,'dqn']:add(m,tag)
        s=m.get_learning_exposure_snapshot()
        self.assertEqual((m.size,s['accepted_total'],s['accepted_learner_total']),(3,6,3))
        self.assertEqual(s['accepted_by_source_total'],dict(dqn=2,epsilon=1,expert=1,eval=1,unattributed=1))
        with self.assertRaises(ValueError):add(m,'dqn',state=[1,2,3])
        self.assertEqual(m.get_learning_exposure_snapshot()['accepted_total'],6)
        s['accepted_by_source_total']['dqn']=999
        self.assertEqual(m.get_learning_exposure_snapshot()['accepted_learner_total'],3)

    def test_post_nstep_maturation_counts_rows_not_wire_calls(self):
        spec=importlib.util.spec_from_file_location('nstep_fixture',GAME/'Scripts/dqn/nstep_buffer.py')
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        n=module.NStepReplayBuffer(3,.995);m=replay()
        self.assertEqual(n.add([1,2],0,1,[2,3],False,actor='dqn'),[])
        self.assertEqual(n.add([1,2],0,1,[2,3],False,actor='epsilon'),[])
        self.assertEqual(m.get_learning_exposure_snapshot()['accepted_learner_total'],0)
        for row in n.add([1,2],0,1,[2,3],True,actor='epsilon'):add(m,row[7])
        self.assertEqual(m.get_learning_exposure_snapshot()['accepted_learner_total'],3)
        eval_n=module.NStepReplayBuffer(3,.995)
        for row in eval_n.add([1,2],0,1,[2,3],True,actor='eval'):add(m,row[7])
        self.assertEqual(m.get_learning_exposure_snapshot()['accepted_learner_total'],3)
        self.assertEqual(m.get_learning_exposure_snapshot()['accepted_by_source_total']['eval'],1)

    def test_clear_flush_preserve_process_totals_but_invalidate_burnin_epoch(self):
        m=replay();add(m);a=m.get_learning_exposure_snapshot();m.clear();b=m.get_learning_exposure_snapshot()
        self.assertEqual((b['epoch'],b['accepted_learner_total'],b['accepted_learner_since_epoch']),(1,1,0))
        add(m,'epsilon');m.flush();c=m.get_learning_exposure_snapshot()
        self.assertEqual((c['epoch'],c['accepted_learner_total'],c['accepted_learner_since_epoch']),(2,2,0))
        self.assertEqual(a['instance_monotonic_ns'],c['instance_monotonic_ns'])
        self.assertNotEqual(replay().get_learning_exposure_snapshot()['instance_monotonic_ns'],c['instance_monotonic_ns'])

    def test_restore_rows_are_not_admissions_and_failed_partial_restore_invalidates(self):
        m=replay();add(m);arch={name:np.array(getattr(m,name),copy=True) for name in m._storage_specs()}
        arch['priorities']=np.ones(3)
        self.assertTrue(m._restore_from_arrays(arch,0,1,time.time(),'fixture',False,saved_n=3))
        s=m.get_learning_exposure_snapshot()
        self.assertEqual((s['epoch'],s['accepted_total'],s['accepted_learner_since_epoch']),(1,1,0))
        bad=dict(arch,states=np.zeros((3,99)))
        self.assertFalse(m._restore_from_arrays(bad,0,1,time.time(),'fixture',False))
        self.assertEqual(m.get_learning_exposure_snapshot()['epoch'],1)
        bad=dict(arch);bad.pop('next_states')
        with self.assertRaises(KeyError):m._restore_from_arrays(bad,0,1,time.time(),'fixture',False)
        self.assertEqual(m.get_learning_exposure_snapshot()['epoch'],2)

    def test_directory_adoption_resets_epoch_only_after_validation(self):
        m=replay();add(m)
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(m._try_adopt_mmap_directory(directory,0,3,1,time.time(),False))
            self.assertEqual(m.get_learning_exposure_snapshot()['epoch'],0)
            for name in m._storage_specs():np.save(Path(directory)/(name+'.npy'),getattr(m,name))
            np.save(Path(directory)/'priorities.npy',np.ones(3,dtype=np.float64))
            self.assertTrue(m._try_adopt_mmap_directory(directory,0,3,1,time.time(),False))
            s=m.get_learning_exposure_snapshot()
            self.assertEqual((s['epoch'],s['accepted_total'],s['accepted_learner_since_epoch']),(1,1,0))

    def test_found_inf_reference_survives_scaler_registry_clear_without_device_ops(self):
        o=Adam();t=Tensor();s=Scaler(o,t);state=s._per_optimizer_states
        got,mode=captured(s,o)
        self.assertIs(got,t);self.assertEqual(mode,'single_cuda_found_inf')
        s._per_optimizer_states={}
        self.assertIs(got,t);self.assertEqual(len(state),1)
        counter=ex.OptimizerExposure()
        for value in [0,1,0]:counter.finish(counter.begin(),mode,value)
        q=counter.snapshot()
        self.assertEqual((q['total']['applied'],q['total']['amp_skipped'],q['total']['unavailable']),(2,1,0))

    def test_missing_malformed_multidevice_or_optimizer_state_is_unavailable_untouched(self):
        mutations=[lambda s,o,t:s._per_optimizer_states.clear(),
            lambda s,o,t:s._per_optimizer_states.update({999:{}}),
            lambda s,o,t:s._per_optimizer_states[id(o)].update(stage=SimpleNamespace(name='STEPPED')),
            lambda s,o,t:s._per_optimizer_states[id(o)].update(found_inf_per_device={}),
            lambda s,o,t:s._per_optimizer_states[id(o)]['found_inf_per_device'].update({Device(1):Tensor(Device(1))}),
            lambda s,o,t:setattr(t,'ndim',1),lambda s,o,t:setattr(t,'dtype','torch.float16'),
            lambda s,o,t:setattr(t,'requires_grad',True),lambda s,o,t:o.param_groups[0].update(fused=False)]
        for mutate in mutations:
            o=Adam();t=Tensor();s=Scaler(o,t);mutate(s,o,t)
            keys=list(s._per_optimizer_states);got,reason=captured(s,o)
            with self.subTest(reason=reason):self.assertIsNone(got);self.assertNotEqual(reason,'single_cuda_found_inf')
            self.assertEqual(list(s._per_optimizer_states),keys)
        o=Adam();s=Scaler(o,Tensor());s._enabled=False
        self.assertEqual(captured(s,o),(None,'scaler_disabled'))

    def test_applied_not_parameter_steps_invalid_values_failure_epochs_and_duplicate_ticket(self):
        c=ex.OptimizerExposure()
        for value in [float('nan'),-1,2,None,Tensor(),True]:c.finish(c.begin(),'single_cuda_found_inf',value)
        c.finish(c.begin(),'optimizer_exception');c.finish(c.begin(),'readback_exception')
        old=c.begin();c.new_epoch('load_begin');c.finish(old,'unscaled')
        token=c.begin();c.finish(token,'unscaled');c.finish(token,'unscaled')
        s=c.snapshot()
        self.assertEqual(s['total']['attempts_started'],10)
        self.assertEqual(s['total']['outcomes_recorded'],10)
        self.assertEqual(s['total']['unavailable'],8)
        self.assertEqual(s['prior_epoch_outcomes_total'],1)
        self.assertEqual(s['since_epoch']['applied'],1)
        self.assertEqual(s['unclassified_started_total'],0)
        s['total']['applied']=999;self.assertEqual(c.snapshot()['total']['applied'],2)

    def test_thread_safe_counter_snapshot_and_bounded_state(self):
        c=ex.OptimizerExposure()
        def writer():
            for i in range(200):c.finish(c.begin(),'single_cuda_found_inf',i%2)
        threads=[threading.Thread(target=writer) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        s=c.snapshot();self.assertEqual(s['total']['outcomes_recorded'],400)
        self.assertEqual(s['total']['applied']+s['total']['amp_skipped'],400)
        self.assertFalse(any(isinstance(v,list) for v in c.__dict__.values()))

    def test_actual_agent_step_preserves_eval_tag_and_disabled_add_signature(self):
        def step(folder):
            node=methods(HERE/folder/'agent.py',{'step'})[0]
            namespace=dict(RL_CONFIG=SimpleNamespace(),NUM_JOINT=81,combine_action=lambda a,b:9*a+b)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_step','exec'),namespace)
            return namespace['step']
        for enabled in [False,True]:
            m=replay(enabled=enabled)
            m.actor_kind_from_name=lambda actor,expert=0:2 if expert else 1 if actor=='epsilon' else 0
            a=SimpleNamespace(memory=m)
            for tag in ['dqn','epsilon','expert','eval']:
                step('proposed')(a,[1,2],(1,2),1,[2,3],False,actor=tag)
            if enabled:
                q=m.get_learning_exposure_snapshot()
                self.assertEqual(q['accepted_learner_total'],2)
                self.assertEqual(q['accepted_by_source_total']['eval'],1)
        calls=[]
        class Memory:
            def actor_kind_from_name(self,*args):return 0
            def add(self,*args,**kwargs):calls.append((args,kwargs))
            tree=SimpleNamespace(data_ptr=2);capacity=3
        a=SimpleNamespace(memory=Memory())
        for folder in ['before','proposed']:step(folder)(a,[1,2],(1,2),1,[2,3],False,actor='eval')
        self.assertEqual(calls[0],calls[1])
        self.assertNotIn('source_actor',calls[1][1])

    def test_pending_outcome_is_unavailable_and_existing_raw_CSV_retains_counter_JSON(self):
        c=ex.OptimizerExposure();c.finish(c.begin(),'unscaled')
        pending=c.begin();self.assertFalse(c.snapshot()['available'])
        c.finish(pending,'single_cuda_found_inf',0);self.assertTrue(c.snapshot()['available'])
        spec=importlib.util.spec_from_file_location('existing_reporting',GAME/'Scripts/dqn/run_telemetry.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        payload=dict(available=False,learning_exposure=dict(optimizer=c.snapshot(),replay=replay().get_learning_exposure_snapshot()))
        fields=module.pipeline_report_fields(dict(pipeline=payload,bank={},age_s=0))
        import json
        self.assertEqual(json.loads(fields['pipeline_snapshot_json'])['learning_exposure'],payload['learning_exposure'])
        self.assertFalse(any('exposure' in key for key in fields if key!='pipeline_snapshot_json'))

    def test_training_retains_math_schedules_optimizer_order_and_single_cpu_readback(self):
        def fn(folder):
            tree=ast.parse((HERE/folder/'training.py').read_text())
            return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_train_step_impl')
        old,new=fn('before'),fn('proposed')
        def calls(node):
            wanted={'scale','backward','unscale_','clip_grad_norm_','step','update','cpu'}
            return [ast.unparse(n.func) for n in sorted(ast.walk(node),key=lambda n:(getattr(n,'lineno',0),getattr(n,'col_offset',0))) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in wanted]
        self.assertEqual(calls(old),calls(new))
        for text in ['agent.training_steps += 1','agent.optimized_samples =','agent.update_target()','agent._sync_inference(force=False)']:
            a=ast.unparse(old);b=ast.unparse(new);self.assertEqual(a[a.index(text):].split('\n')[0],b[b.index(text):].split('\n')[0])
        proposed=(HERE/'proposed/training.py').read_text()
        self.assertLess(proposed.index('host[B+9:B+15]'),proposed.index('agent.optimized_samples ='))
        self.assertLess(proposed.index('scalars.extend([\n                (joint_tp_a'),proposed.index('scalars.append(outcome_tensor)'))
        self.assertEqual(proposed.count('packed.cpu().numpy()'),1)
        helper=ast.parse((HERE/'proposed/learning_exposure.py').read_text())
        cap=next(n for n in helper.body if isinstance(n,ast.FunctionDef) and n.name=='capture_amp_found_inf')
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr in {'item','cpu','to','clone','detach','sum','get_scale','synchronize'} for n in ast.walk(cap)))


if __name__=='__main__':unittest.main()
