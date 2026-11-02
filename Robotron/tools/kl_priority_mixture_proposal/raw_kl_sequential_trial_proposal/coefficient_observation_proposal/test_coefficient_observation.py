"""Authored CPU-only contracts; root alone runs. No Torch/model/CUDA imports.

Uses real NumPy CPU arrays and the held scalar-only OptimizerExposure. The
compiled-loss/optimizer numerical body is unchanged-source-checked, not executed.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest import mock

import numpy as np
from . import coefficient_observation as c

HERE = Path(__file__).parent
GAME = HERE.parents[3]


def exposure_module():
    name = '_coefficient_test_real_exposure'
    spec = importlib.util.spec_from_file_location(name, GAME/'Scripts/dqn/learning_exposure.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class DeviceTrap:
    def __getattribute__(self, name):
        raise AssertionError('Observer touched a device object: ' + name)


class CoefficientContracts(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory); sources = root/'source'; sources.mkdir()
        for name in c.SOURCE_NAMES:
            (sources/name).write_text('# Explicit tiny source-pin fixture\n')
        expected = dict(metric='ce', phase_id='fixture_phase', root_precommit_sha256='a'*64,
            founder_phase_record_sha256='b'*64, last_resume_record_sha256='c'*64,
            started_from=dict(path='/fixture/model.pt',sha256='d'*64,bytes=1,
                clocks=dict(training_steps=10,optimized_samples=40960,learner_frame_count=20,frame_count=40)), valid=True)
        record = dict(schema='robotron-coefficient-observation-root-record-v1',request_id='fixture_only',
            expected_phase=expected,source_hashes={n:hashlib.sha256((sources/n).read_bytes()).hexdigest() for n in c.SOURCE_NAMES})
        rp=root/'record.json'; rp.write_text(json.dumps(record));rp.chmod(0o444)
        exposure=exposure_module().OptimizerExposure();exposure.new_epoch('fixture_restore')
        owner=dict(pid=os.getpid(),starttime_ticks=100,unit='fixture.service',invocation_id='e'*32,cgroup='/fixture.service')
        cfg=NS(batch_size=4096,per_priority_metric='ce',use_torch_compile=True,compile_full_loss=True)
        obs=c.CoefficientObservation(root/'ce-coefficients-fixture',cfg,optimizer_exposure=exposure,
            runtime=dict(device='cuda:0',use_amp=True,fused_adam=True),source_directory=sources,
            record_path=rp,record_sha256=hashlib.sha256(rp.read_bytes()).hexdigest(),identity_fn=lambda:owner)
        phase=copy.deepcopy(expected);phase['phase_record_sha256']=phase.pop('founder_phase_record_sha256')
        agent=NS(training_steps=10,optimized_samples=40960,_priority_phase=NS(snapshot=lambda:copy.deepcopy(phase)),
            memory=NS(capacity=6000000,_ephof_base=7000000),_prefetcher=NS(_epoch=3))
        metrics=NS(lock=threading.Lock(),frame_count=40,learner_frame_count=20,measurement_frame_count=0)
        arrays=[DeviceTrap(),np.zeros(4096,dtype=np.int64),np.zeros(4096,dtype=np.float32),DeviceTrap(),
            np.zeros(4096,dtype=np.float32),np.ones(4096,dtype=np.int32),np.zeros(4096,dtype=np.uint8),
            np.zeros(4096,dtype=np.uint8),np.concatenate((np.arange(3072),6000000+np.arange(410),7000000+np.arange(614))).astype(np.int64),
            np.concatenate((np.full(901,.25),np.ones(2171),np.full(1024,.25))).astype(np.float32)]
        batch=tuple(arrays)
        metadata=dict(schema='robotron-replay-draw-observation-v1',capture_id=obs.capture_id,observer_error=None,
            capacity=6000000,alpha=.7,beta=1.,tree_total=100.,selected_per_raw_max_weight=10.,
            origin_boundaries=[('per',0,901),('interesting',901,1638),('recent',1638,3072),('hof',3072,3482),('ephof',3482,4096)],
            indices=batch[8].copy(),supplied_weights_float32=batch[9].copy(),
            small_batch_fields={n:batch[i].copy() for n,i in [('actions',1),('rewards',2),('dones',4),('horizons',5),('is_expert',6),('actor_kind',7)]},
            banks=dict(hof=dict(selected_slots=np.arange(410)),ephof=dict(selected_slots=np.arange(614))),
            unknown=dict(optimizer_outcome='not an executed learner attempt',full_states='omitted sampler statement'))
        lease=NS(_epoch=3,_owner=agent._prefetcher,is_current=True,_released=False,draw_metadata=metadata,release_calls=0)
        lease.release=lambda:setattr(lease,'release_calls',lease.release_calls+1)
        return obs,agent,metrics,exposure,batch,lease,phase

    def finish(self, fixture, found_inf=0., norm=.5):
        obs,agent,metrics,exposure,batch,lease,phase=fixture
        obs.begin(agent,batch,lease,metrics_context=metrics)
        ticket=exposure.begin();exposure.finish(ticket,'single_cuda_found_inf',found_inf)
        obs.outcome('single_cuda_found_inf',found_inf,ticket)
        ce=np.full(4096,2.,dtype=np.float32)
        obs.packed_cpu(agent,ce,weighted_loss=1.5,grad_norm=norm,bc_loss=.01,indices=batch[8],weights=batch[9])
        agent.training_steps+=1;agent.optimized_samples+=4096;metrics.frame_count+=2;metrics.learner_frame_count+=1
        obs.end(agent,result=1.5,staged=lease)
        return json.loads((obs.directory/'attempt-01.json').read_text()),json.loads((obs.directory/'final.json').read_text())

    def test_actual_CPU_owned_coefficients_CE_phase_clocks_and_genuine_admission(self):
        with tempfile.TemporaryDirectory() as d:
            f=self.fixture(d);row,final=self.finish(f);obs,agent,metrics,exposure,batch,lease,phase=f
            self.assertEqual(final['status'],'COMPLETE');self.assertEqual(row['optimizer_outcome'],'applied_admission')
            self.assertEqual(row['after']['frame_count'],42);self.assertEqual(row['after']['learner_frame_count'],21)
            self.assertEqual(row['weights_float32'],batch[9].tolist());self.assertEqual(row['actual']['ce_float32'],[2.]*4096)
            self.assertEqual(row['lease_exit']['epoch'],3);self.assertIsNone(obs.lease);self.assertIsNone(obs.metrics_context)
            self.assertFalse(final['parameter_gradients_observed']);self.assertFalse(final['actual_executed_target_observed'])
            self.assertLessEqual(sum(p.stat().st_size for p in obs.directory.iterdir()),c.TOTAL_BYTES)

    def test_natural_AMPskip_retained_complete_nonfinite_gradnorm_no_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            f=self.fixture(d);row,final=self.finish(f,1.,float('inf'))
            self.assertEqual(final['status'],'COMPLETE');self.assertEqual(row['optimizer_outcome'],'amp_skipped')
            self.assertEqual(row['actual']['grad_norm'],{'nonfinite':'inf'});self.assertFalse(f[0].want_draw())
            f[0].begin(f[1],f[4],f[5],metrics_context=f[2]);self.assertEqual(f[0].consumed,1)

    def test_real_pre_loss_positional_tuple_and_device_loss_arguments_are_never_accessed(self):
        with tempfile.TemporaryDirectory() as d:
            f=self.fixture(d);o,a,m,x,b,l,p=f;o.begin(a,b,l,metrics_context=m)
            o.pre_loss(a,tuple(DeviceTrap() for _ in range(8)),schedule=DeviceTrap(),diagnostic_due=False)
            o.loss(a,DeviceTrap(),weighted_loss=DeviceTrap(),bc_loss=DeviceTrap(),diagnostic_values=DeviceTrap())
            self.assertFalse(o.invalid);self.assertIn('lease_pre_loss',o.current)

    def test_actual_existing_host_bridge_finishes_ticket_then_records_packed_CPU_only(self):
        with tempfile.TemporaryDirectory() as d:
            f=self.fixture(d);obs,agent,metrics,exposure,batch,lease,phase=f;obs.begin(agent,batch,lease,metrics_context=metrics)
            tree=ast.parse((HERE/'training.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_train_step_impl')
            start=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.If) and any(isinstance(v,ast.Call)
                and isinstance(v.func,ast.Attribute) and v.func.attr=='finish' and len(v.args)>=2
                and isinstance(v.args[1],ast.Name) and v.args[1].id=='outcome_mode' for v in ast.walk(n)))
            stop=next(i for i,n in enumerate(fn.body) if i>start and isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='diagnostic_due')
            ticket=exposure.begin();host=np.concatenate((np.full(4096,2.,np.float32),np.array([1.5,.5,.01,0.],np.float32)))
            def observe(obj,method,*args,**kw):getattr(obj,method)(*args,**kw)
            env=dict(optimizer_exposure=exposure,outcome_ticket=ticket,outcome_mode='single_cuda_found_inf',host=host,outcome_host_index=4099,
                capture=obs,_capture_observe=observe,priority_timings=None,gpu_timing=None,B=4096,kl_priority=False,agent=agent,indices=batch[8],weights=batch[9])
            exec(compile(ast.Module(body=fn.body[start:stop],type_ignores=[]),'actual_host_bridge','exec'),env)
            self.assertTrue(ticket.finished);self.assertEqual(obs.current['actual']['ce_float32'],[2.]*4096)
            obs.end(agent,result=1.5,staged=lease);self.assertTrue(json.loads((obs.directory/'final.json').read_text())['observation_complete'])

    def test_wrong_draw_weights_small_fields_origins_or_bank_sentinels_reserve_first_then_refuse(self):
        for defect in ('weights','small','origins','bank'):
            with self.subTest(defect=defect),tempfile.TemporaryDirectory() as d:
                o,a,m,x,b,l,p=self.fixture(d)
                if defect=='weights':l.draw_metadata['supplied_weights_float32'][0]=.5
                elif defect=='small':l.draw_metadata['small_batch_fields']['actions'][0]=1
                elif defect=='origins':l.draw_metadata['origin_boundaries'][1]=('interesting',900,1638)
                else:l.draw_metadata['banks']['hof']['selected_slots'][0]=999
                with self.assertRaises(ValueError):o.begin(a,b,l,metrics_context=m)
                o.invalidate('begin',RuntimeError(defect));o.end(a,result=1.,staged=l)
                self.assertEqual(o.consumed,1);self.assertFalse(o.want_draw());self.assertEqual(json.loads((o.directory/'final.json').read_text())['status'],'INVALID')

    def test_stale_released_foreign_prefetch_owner_and_phase_mismatch_refuse(self):
        for defect in ('stale','released','owner','phase'):
            with self.subTest(defect=defect),tempfile.TemporaryDirectory() as d:
                o,a,m,x,b,l,p=self.fixture(d)
                if defect=='stale':l._epoch=2
                elif defect=='released':l._released=True
                elif defect=='owner':l._owner=NS(_epoch=3)
                else:p['last_resume_record_sha256']='f'*64
                with self.assertRaises(ValueError):o.begin(a,b,l,metrics_context=m)
                self.assertEqual(o.consumed,1)

    def test_exit_epoch_or_unfinished_ticket_and_unsupported_mode_invalidate(self):
        for defect in ('epoch','unfinished','unscaled'):
            with self.subTest(defect=defect),tempfile.TemporaryDirectory() as d:
                o,a,m,x,b,l,p=self.fixture(d);o.begin(a,b,l,metrics_context=m);ticket=x.begin()
                if defect!='unfinished':x.finish(ticket,'unscaled' if defect=='unscaled' else 'single_cuda_found_inf',0.)
                o.outcome('unscaled' if defect=='unscaled' else 'single_cuda_found_inf',0.,ticket)
                if defect=='epoch':x.new_epoch('unexpected')
                o.packed_cpu(a,np.ones(4096,np.float32),weighted_loss=1.,grad_norm=.2,bc_loss=.01,indices=b[8],weights=b[9]);o.end(a,result=1.,staged=l)
                self.assertFalse(json.loads((o.directory/'final.json').read_text())['observation_complete'])

    def test_CPU_arrays_are_copied_and_no_slot_alias_survives_end(self):
        with tempfile.TemporaryDirectory() as d:
            f=self.fixture(d);o,a,m,x,b,l,p=f;o.begin(a,b,l,metrics_context=m);old=o.current['draw']['indices'][0]
            l.draw_metadata['indices'][0]=55;self.assertEqual(o.current['draw']['indices'][0],old)
            o.invalidate('fixture_stop',RuntimeError());o.end(a,exception=RuntimeError('original'),staged=l)
            self.assertIsNone(o.current);self.assertIsNone(o.lease);self.assertIsNone(o.lease_owner)

    def test_original_sampler_error_is_not_replaced_or_resampled(self):
        with tempfile.TemporaryDirectory() as d:
            o,*_=self.fixture(d);error=RuntimeError('original sampler');memory=NS(sample_with_metadata=mock.Mock(side_effect=error),sample=mock.Mock())
            with self.assertRaises(RuntimeError) as caught:o.sample(memory,4096,1.)
            self.assertIs(caught.exception,error);memory.sample.assert_not_called();self.assertTrue(o.invalid)

    def test_original_wrapper_failure_releases_lease_even_if_all_observer_IO_fails(self):
        with tempfile.TemporaryDirectory() as d:
            o,a,m,x,b,l,p=self.fixture(d);a._recomputed_ce_capture=o;error=RuntimeError('original kernel')
            tree=ast.parse((HERE/'training.py').read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('train_step','_capture_observe')]
            import contextlib
            env=dict(nullcontext=contextlib.nullcontext)
            def impl(agent,prefetched_batch):
                env['_capture_observe'](o,'begin',a,b,l,metrics_context=m)
                raise error
            env['_train_step_impl']=impl;exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_wrapper','exec'),env)
            with mock.patch.object(o,'_write',side_effect=OSError('publication fails')):
                with self.assertRaises(RuntimeError) as caught:env['train_step'](a,l)
            self.assertIs(caught.exception,error);self.assertEqual(l.release_calls,1);self.assertTrue(o.invalid);self.assertEqual(o.consumed,1)

    def test_missing_packed_vector_or_nonfinite_CE_is_invalid_not_replaced(self):
        for nonfinite in (False,True):
            with self.subTest(nonfinite=nonfinite),tempfile.TemporaryDirectory() as d:
                o,a,m,x,b,l,p=self.fixture(d);o.begin(a,b,l,metrics_context=m);t=x.begin();x.finish(t,'single_cuda_found_inf',0.);o.outcome('single_cuda_found_inf',0.,t)
                if nonfinite:
                    ce=np.ones(4096,np.float32);ce[0]=np.nan
                    with self.assertRaises(ValueError):o.packed_cpu(a,ce,weighted_loss=1.,grad_norm=.1,bc_loss=.01,indices=b[8],weights=b[9])
                    o.invalidate('packed',ValueError('nonfinite'))
                o.end(a,result=1.,staged=l);self.assertEqual(json.loads((o.directory/'final.json').read_text())['status'],'INVALID');self.assertFalse(o.want_draw())

    def test_total_and_row_byte_bounds_refuse_before_file_publication(self):
        with tempfile.TemporaryDirectory() as d:
            o,*_=self.fixture(d)
            with self.assertRaises(ValueError):o._write('oversize.json','x'*c.ROW_BYTES,c.ROW_BYTES)
            self.assertFalse((o.directory/'oversize.json').exists());o.disk_bytes=c.TOTAL_BYTES
            with self.assertRaises(ValueError):o._write('over-total.json',{},c.SMALL_BYTES)
            self.assertFalse((o.directory/'over-total.json').exists())

    def test_root_record_requires_readonly_exact_digest(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'record.json';p.write_text('{}');digest=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):c.read_record(p,digest)
            p.chmod(0o444)
            with self.assertRaises(ValueError):c.read_record(p,'0'*64)

    def test_default_loss_optimization_packing_and_native_update_body_is_byte_unchanged(self):
        old=(GAME/'Scripts/dqn/training.py').read_text();new=(HERE/'training.py').read_text()
        extra='    if capture is not None and hasattr(capture, "packed_cpu"):\n        _capture_observe(capture, "packed_cpu", agent, td_errors,\n            weighted_loss=loss_val, grad_norm=gn, bc_loss=bc_loss_val, indices=indices, weights=weights)\n'
        self.assertEqual(new.count(extra),1);self.assertEqual(new.replace(extra,''),old)
        self.assertLess(new.index('optimizer_exposure.finish(outcome_ticket, outcome_mode'),new.index(extra))
        self.assertLess(new.index('loss_val, gn, bc_loss_val = map'),new.index(extra));self.assertLess(new.index(extra),new.index('agent.memory.update_priorities(indices, priority_errors)'))

    def test_defaultOFF_startup_has_no_observer_import_or_creation_and_flags_conflict_first(self):
        source=(HERE/'agent.py').read_text();tree=ast.parse(source);init=next(n for cl in tree.body if isinstance(cl,ast.ClassDef) and cl.name=='RainbowAgent' for n in cl.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
        nodes=[n for n in init.body if '_coefficient_directory' in ast.unparse(n) or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_capture_directory' for t in n.targets)]
        # Only the added branches and two environment reads, no agent/framework construction.
        with mock.patch.dict(os.environ,{},clear=True),mock.patch('builtins.__import__',side_effect=AssertionError('default imported observer')):
            exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_startup_guard','exec'),dict(os=os))
        with mock.patch.dict(os.environ,{'DQN_COEFFICIENT_OBSERVATION_DIR':'/new','DQN_EXECUTED_CE_TRACE_DIR':'/old'},clear=True):
            with self.assertRaises(ValueError):exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_startup_conflict','exec'),dict(os=os))


if __name__=='__main__':unittest.main()
