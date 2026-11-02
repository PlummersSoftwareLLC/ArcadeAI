"""Actual bridge functions with tiny CPU Torch/NumPy and synthetic authority.

Root alone runs these fixtures. No production checkpoint, array, main module,
owner, listener or device is opened. Real temporary mmap arrays deliberately
have four rows; logical capacity labels exercise comparison branches, not6M
storage qualification. Kernel owner/service queries and producer authority are
explicit synthetic collaborators. No candidate module is imported.
"""
import ast
import copy
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
BRIDGE=HERE/'continuous_startup_bridge_v2.py'
BRIDGE_SHA='62e8fdce2221e084945594e35a965a6f7643887d56f8679894e307949a4c5096'
TOOLS=HERE.parent/'state-sources/restoration_manifest_tools_v1.py'
TOOLS_SHA='3ab7c6a018afce917bd1199ec9d09b5d3041936d638cdf17f91514006685faf7'
ENGINE_VERSION=28
CONFIG=Path('/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/config.py')
CONFIG_SHA='ef26db6aa19fe67ec9e1e15f8227b4e24bbc853b05d0ea00c450b290bf80b249'
ORIGINAL_BRIDGE=HERE/'continuous_startup_bridge_v1.py'
ORIGINAL_BRIDGE_SHA='ca6fc0b6406c88f79861b01717477dcbf5b2589940a1d761ef486dcd20fc0190'
_METRICS_CLASS=None


def pin(path):
    path=Path(path);raw=path.read_bytes();s=path.stat()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=dict(
        device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink))


def immutable(path,value):
    with Path(path).open('x')as out:
        out.write(json.dumps(value,indent=2,allow_nan=False)+'\n');out.flush();os.fchmod(out.fileno(),0o444);os.fsync(out.fileno())
    return pin(path)


def actual_functions(path,digest,names=None):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Actual selected function source changed')
    tree=ast.parse(raw)
    body=[n for n in tree.body if isinstance(n,ast.FunctionDef)and(names is None or n.name in names)]
    ns=dict(__file__=str(path),__name__='_synthetic_bridge_AST',__package__='_synthetic_bridge_package',
        copy=copy,hashlib=hashlib,json=json,math=__import__('math'),os=os,Path=Path,re=__import__('re'),
        stat=stat,sys=sys,time=time,importlib=__import__('importlib'),
        MODE='CONTINUOUS_TRAIN155_EVAL37_ONCE',TOOLS_SHA=TOOLS_SHA)
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path),'exec'),ns)
    return SimpleNamespace(**{k:v for k,v in ns.items()if callable(v)}),ns


@contextmanager
def module_bindings(selected):
    """Restore only synthetic names; preserve lazy Torch imports/registrations."""
    missing=object();before={name:sys.modules.get(name,missing)for name in selected}
    sys.modules.update(selected)
    try:yield
    finally:
        for name,previous in before.items():
            if previous is missing:sys.modules.pop(name,None)
            else:sys.modules[name]=previous


def actual_metrics_class(np):
    """Compile the entire actual dataclass and real tiny-ring factory, not API fields.

    The selected config module is never imported: only three literal window
    constants, _new_metric_ring and MetricsData definitions execute. Remaining
    method collaborators are deliberately unused. RL_CONFIG supplies only the
    two scalar dataclass defaults; real CPU NumPy owns the metric ring arrays.
    """
    global _METRICS_CLASS
    if _METRICS_CLASS is not None:return _METRICS_CLASS
    raw=CONFIG.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CONFIG_SHA:raise ValueError('Exact real MetricsData source required')
    tree=ast.parse(raw);names={'SCORE_1M_WINDOW_FRAMES','LEVEL_1M_WINDOW_FRAMES','EVAL_SCORE_1M_WINDOW_FRAMES'}
    body=[n for n in tree.body if (isinstance(n,ast.Assign)and any(isinstance(x,ast.Name)and x.id in names for x in n.targets))
        or(isinstance(n,ast.FunctionDef)and n.name=='_new_metric_ring')or(isinstance(n,ast.ClassDef)and n.name=='MetricsData')]
    module=ModuleType('_synthetic_actual_MetricsData');module.__dict__.update(np=np,deque=deque,Deque=Deque,
        Optional=Optional,dataclass=dataclass,field=field,threading=threading,time=time,
        RL_CONFIG=SimpleNamespace(epsilon_start=.1,expert_ratio_start=.1))
    with module_bindings({module.__name__:module}):
        exec(compile(ast.Module(body=body,type_ignores=[]),str(CONFIG),'exec'),module.__dict__)
    _METRICS_CLASS=module.MetricsData
    return _METRICS_CLASS


class ToyAgent(SimpleNamespace):pass
class ToyMemory(SimpleNamespace):pass
ToyAgent.__module__='_synthetic_held_agent'
ToyMemory.__module__='_synthetic_held_replay'


class Harness:
    def __init__(self,root,torch,np,tools,ns):
        self.root=Path(root);self.torch=torch;self.np=np;self.tools=tools;self.ns=ns
        self.root.mkdir(mode=0o700,exist_ok=True)
        online=torch.nn.Linear(2,2);target=torch.nn.Linear(2,2)
        with torch.no_grad():
            online.weight.copy_(torch.tensor([[1.,2.],[3.,4.]]));online.bias.copy_(torch.tensor([.1,.2]))
        target.load_state_dict(online.state_dict())
        optimizer=torch.optim.Adam(online.parameters(),lr=3.125e-6)
        scaler=torch.amp.GradScaler('cpu',init_scale=128.,growth_interval=2)
        # Initialize real tiny Adam moments/scaler BEFORE the synthetic held
        # agent/exposure exists; no production optimizer or counters are used.
        loss=online(torch.ones((1,2))).sum();scaler.scale(loss).backward();scaler.step(optimizer);scaler.update()
        optimizer.zero_grad(set_to_none=True)
        self.optimizer_observation=dict(enabled=True,available=False,process_id=os.getpid(),epoch=1,
            epoch_reason='optimizer_restore_begin',unclassified_started_total=0,
            total=dict(attempts_started=0,outcomes_recorded=0,applied=0,amp_skipped=0,unavailable=0))
        self.replay_observation=dict(enabled=True,available=True,process_id=os.getpid(),epoch=1,
            epoch_reason='directory_adopt_begin',accepted_total=0)
        self.memory=ToyMemory(lock=threading.Lock(),_insert_exposure=SimpleNamespace(snapshot=lambda:copy.deepcopy(self.replay_observation)))
        self.agent=ToyAgent(online_net=online,target_net=target,optimizer=optimizer,grad_scaler=scaler,
            training_steps=100,optimized_samples=409600,baseline_batch_size=512,last_target_update_samples=400000,
            lr_anchor_step=0.,lr_gear='climb',state_size=2,loaded_training_steps=100,loaded_optimized_samples=409600,
            _training_lock=threading.RLock(),_continuous_startup_held=True,training_enabled=False,memory=self.memory,
            _learning_optimizer_exposure=SimpleNamespace(snapshot=lambda:copy.deepcopy(self.optimizer_observation)))
        self.metrics=actual_metrics_class(np)()
        # Real Agent.load assigns the two dynamic measurement frame anchors.
        # It does NOT create measurement_active: that flag belongs to actual
        # ManagedMeasurement.enter, which continuous MAIN never calls.
        for name,value in dict(training_enabled=False,frame_count=1000,learner_frame_count=500,
            measurement_frame_count=17,total_training_steps=100,expert_ratio=.1,epsilon=.1,
            loaded_frame_count=1000,loaded_measurement_frame_count=17,loaded_optimized_samples=409600).items():
            setattr(self.metrics,name,value)
        self.cfg=SimpleNamespace(single_frame_state_size=2,frame_stack=1)
        self.resume=immutable(self.root/'resume.json',dict(SYNTHETIC_only=True))
        phase=dict(schema='robotron-priority-metric-phase-v1',metric='ce',valid=True,phase_id='SYNTHETIC',
            phase_record_sha256='a'*64,last_resume_record_sha256='b'*64,priority_update_calls=90,ring_rows_submitted=4000)
        self.actual_phase=dict(phase,last_resume_record_sha256=self.resume['sha256'])
        self.agent._priority_phase=SimpleNamespace(snapshot=lambda:copy.deepcopy(self.actual_phase))
        self.manifest=dict(checkpoint_payload={k:tools.typed_tree(v,torch)for k,v in dict(
            online_state_dict=online.state_dict(),target_state_dict=target.state_dict(),
            optimizer_state_dict=optimizer.state_dict(),grad_scaler_state_dict=scaler.state_dict()).items()},
            saved_scalars=ns['live_scalars'](self.agent,self.metrics,self.cfg,28),priority_metric_phase=phase)
        self.make_replay()

    def make_replay(self):
        np=self.np;tools=self.tools;ring=self.root/'ring';ring.mkdir()
        specs={};arrays={};scalar={}
        for name in('states','next_states','actions','rewards','dones','horizons','is_expert','actor_kind','interesting','priorities'):
            dtype=('<f2'if name in('states','next_states')else'<i8'if name=='actions'else'<i4'if name=='horizons'
                else'|u1'if name in('is_expert','actor_kind')else'<f8'if name=='priorities'else'<f4')
            shape=(4,2)if name in('states','next_states')else(4,)
            path=ring/(name+'.npy');a=np.lib.format.open_memmap(path,mode='w+',dtype=dtype,shape=shape)
            a[:]=np.arange(a.size).reshape(shape)+1;a.flush();del a
            a=np.load(path,mmap_mode='r+',allow_pickle=False);s=path.stat()
            row=dict(path=str(path),dtype=a.dtype.str,shape=list(a.shape),identity=dict(device=s.st_dev,inode=s.st_ino,
                size=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,nlink=s.st_nlink))
            arrays[name]=row
            if name!='priorities':setattr(self.memory,name,a);specs[name]=(name,a.dtype,shape)
            if name not in('states','next_states'):scalar[name]=dict(payload=tools.ndarray_payload(a,np))
        self.memory._storage_specs=lambda:specs;self.memory._mmap_dir=str(ring);self.memory.capacity=self.memory.size=6000000
        self.memory._continuous_exact_resume_consumed=True
        self.memory.tree=SimpleNamespace(capacity=4,data_ptr=2,max_priority=5.,tree=np.r_[np.zeros(4),np.arange(4,dtype='<f8')+1])
        self.memory._adds_total=0
        stopped=dict(ring=dict(directory=dict(path=str(ring)),meta=dict(size=6000000,ptr=2,max_priority=5.),arrays=arrays),banks={})
        payload={}
        for name in('hof','ephof'):
            directory=self.root/name;directory.mkdir();setattr(self.memory,'_'+name+'_dir',str(directory))
            lengths=[2,1];stride=3;meta=dict(ep_len=lengths,ep_score=[100.,200.],ep_game=[11,12],ep_level=[1,2],
                scalars=dict(stride=stride,stale_age=10,stale_age_normal=20))
            for field,values,dtype in(('ep_len',lengths,'<i4'),('ep_score',meta['ep_score'],'<f8'),
                ('ep_game',meta['ep_game'],'<i8'),('ep_level',meta['ep_level'],'<i4')):
                setattr(self.memory,name+'_'+field,np.array(values,dtype=dtype))
            setattr(self.memory,name+'_ep_count',2);setattr(self.memory,name+'_total',3);setattr(self.memory,'_'+name+'_stride',stride)
            setattr(self.memory,'_'+name+'_last_admit_add',-10);setattr(self.memory,'_'+name+'_last_normal_admit_add',-20)
            fields={}
            for field in('states','next_states','actions','rewards','dones','horizons','is_expert','actor_kind'):
                dtype=('<i8'if field=='actions'else'<i4'if field=='horizons'else'|u1'if field in('is_expert','actor_kind')else'<f4')
                shape=(6,2)if field in('states','next_states')else(6,)
                value=np.arange(__import__('math').prod(shape),dtype=dtype).reshape(shape)
                setattr(self.memory,name+'_'+field,value)
                fields[field]=dict(valid_prefix=tools.bank_valid_prefix_payload(value,lengths,stride,np))
            stopped['banks'][name]=dict(directory=dict(path=str(directory)),metadata=meta,counts=dict(episodes=2,transitions=3))
            payload[name]=dict(fields=fields)
        self.manifest.update(ring_and_banks=stopped,ring_scalar_payload=scalar,
            ring_priorities=dict(payload=scalar['priorities']['payload']),bank_payload=payload)

    def payload(self):
        with patch.dict(os.environ,DQN_PRIORITY_PHASE_RECORD_SHA256=self.resume['sha256']):
            return self.ns['compare_payload'](self.agent,self.metrics,self.cfg,self.manifest,self.tools,self.torch)

    def replay(self):return self.ns['compare_loaded_replay'](self.memory,self.manifest,self.tools,self.np)

    def prepare_full_call(self):
        ns=self.ns;fake=SimpleNamespace(pid=os.getpid(),birth=777,unit='SYNTHETIC-held.service',
            invocation_id='1'*32,cgroup='/SYNTHETIC-only',uid=os.getuid())
        self.owner=vars(fake);checkpoint=self.root/'SYNTHETIC-checkpoint.bin';checkpoint.write_bytes(b'SYNTHETIC_NOT_A_MODEL')
        cp=pin(checkpoint);original=immutable(self.root/'synthetic-original-CPU-job.json',dict(SYNTHETIC_only=True))
        self.manifest.update(schema='robotron-stopped-full-training-state-restoration-manifest-v1',status='VERIFIED_STOPPED_STATE',
            owner=dict(pid=1,starttime_ticks=2),checkpoint=cp,original_job=original,manifest_tools=pin(TOOLS))
        mp=immutable(self.root/'manifest.json',self.manifest)
        report=immutable(self.root/'report.json',dict(status='PASS',restoration_manifest=mp,original_job=original))
        authority=immutable(self.root/'authority.json',dict(schema='robotron-root-closed-stopped-full-state-startup-authority-v1',
            CPU_report=report,restoration_manifest=mp,original_CPU_exit=0,all_original_CPU_resources_closed=True,old_trainer_and_population_closed=True))
        temp_source=self.root/'synthetic-extra-source.py';temp_source.write_text('# synthetic source\n');temp_source.chmod(0o444)
        output=self.root/'held';job=dict(schema='robotron-continuous-main-before-update-startup-hold-job-v1',
            mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',original_attempt=1,no_retry=True,unit=self.owner['unit'],
            source_pins=[pin(BRIDGE),pin(Path(__file__).resolve()),pin(temp_source)],restoration_manifest=mp,
            stopped_CPU_report=report,stopped_state_authority=authority,checkpoint=cp,resume_record=self.resume,
            output_directory=str(output),release_path=str(output/'ROOT-release.json'))
        jp=immutable(self.root/'job.json',job);self.job=job;self.jobpin=jp;self.temp_source=temp_source;self.output=output
        self.environment=dict(ROBOTRON_CONTINUOUS_TRAINING_MODE='1',ROBOTRON_CONTINUOUS_STARTUP_HOLD='1',
            CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',
            ROBOTRON_CONTINUOUS_STARTUP_JOB=jp['path'],ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256=jp['sha256'],
            DQN_PRIORITY_PHASE_RECORD_SHA256=self.resume['sha256'],DQN_PRIORITY_PHASE_RECORD=self.resume['path'])
        self.checkpoint=checkpoint
        return self

    def run_full(self,fault=None):
        original_publish=self.ns['publish'];calls=[];owner_calls=[]
        def unit_owner(_unit):
            owner_calls.append(1)
            if fault=='old_owner':return dict(self.owner,pid=1,birth=2)
            if fault=='changed_owner'and len(owner_calls)>=3:return dict(self.owner,birth=778)
            return copy.deepcopy(self.owner)
        def publish(path,value):
            result=original_publish(path,value);calls.append(path.name)
            if path.name=='verified-held-before-first-update.json':
                if fault=='timeout':return result
                release=dict(schema='robotron-root-continuous-startup-one-use-release-v1',owner=self.owner,
                    original_job=self.jobpin,held_report=result,checkpoint=self.job['checkpoint'],allow_training=True)
                if fault=='foreign_release_owner':release['owner']=dict(self.owner,birth=999)
                elif fault=='wrong_report':release['held_report']=dict(result,sha256='f'*64)
                elif fault=='wrong_job':release['original_job']=dict(self.jobpin,sha256='f'*64)
                elif fault=='wrong_checkpoint':release['checkpoint']=dict(self.job['checkpoint'],sha256='f'*64)
                elif fault=='deny_training':release['allow_training']=False
                elif fault=='attempt_before_release':self.optimizer_observation['total']['attempts_started']=1
                elif fault=='source_changed':
                    self.temp_source.chmod(0o644);self.temp_source.write_text('# changed synthetic source\n');self.temp_source.chmod(0o444)
                immutable(self.output/'ROOT-release.json',release)
            return result
        def sealed_timeout(_seconds):raise TimeoutError('Synthetic owned observation deadline; remain sealed')
        package=ModuleType('_synthetic_bridge_package');package.__path__=[]
        cfg=ModuleType('_synthetic_bridge_package.config');cfg.__file__=str(Path(__file__).resolve());cfg.RL_CONFIG=self.cfg
        agent_module=ModuleType('_synthetic_held_agent');agent_module.__file__=str(Path(__file__).resolve());agent_module.ENGINE_VERSION=28
        replay_module=ModuleType('_synthetic_held_replay');replay_module.__file__=str(Path(__file__).resolve())
        main_module=ModuleType('dqn.main');main_module.__file__=str(Path(__file__).resolve())
        bridge_module=ModuleType('_synthetic_bridge_AST');bridge_module.__file__=str(BRIDGE)
        modules={'_synthetic_bridge_package':package,'_synthetic_bridge_package.config':cfg,
            '_synthetic_held_agent':agent_module,'_synthetic_held_replay':replay_module,'_synthetic_bridge_AST':bridge_module,
            'dqn.main':main_module,'dqn.config':cfg}
        with module_bindings(modules),patch.dict(os.environ,self.environment,clear=True),\
             patch.dict(self.ns,unit_owner=unit_owner,publish=publish),\
             patch.object(time,'sleep',side_effect=sealed_timeout):
            self.ns['verify_restoration_and_wait'](self.agent,self.metrics,str(self.checkpoint))
        return calls


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import numpy as np
        cls.torch=torch;cls.np=np
        tools,unused=actual_functions(TOOLS,TOOLS_SHA)
        cls.tools=tools

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='synthetic-continuous-startup-CPU-')
        self.counter=0;self.root=Path(self.temp.name)
        unused,self.ns=actual_functions(BRIDGE,BRIDGE_SHA)
        self.agent_module=ModuleType('_synthetic_held_agent');self.agent_module.ENGINE_VERSION=28
        self.agent_patch=module_bindings({'_synthetic_held_agent':self.agent_module});self.agent_patch.__enter__()

    def tearDown(self):self.agent_patch.__exit__(None,None,None);self.temp.cleanup()

    def toy(self):
        self.counter+=1
        return Harness(self.root/str(self.counter),self.torch,self.np,self.tools,self.ns)

    def test_actual_zero_before_outcome_exposure_ABI_and_negative_work(self):
        h=self.toy()
        self.assertIsInstance(h.metrics,actual_metrics_class(self.np))
        self.assertFalse(hasattr(h.metrics,'measurement_active'))
        self.assertIs(h.metrics.ratchet_frozen,False)
        # Exact original source reproduces the real pre-hold startup failure.
        unused,original=actual_functions(ORIGINAL_BRIDGE,ORIGINAL_BRIDGE_SHA,{'require','no_training_attempts'})
        with self.assertRaises(AttributeError):original['no_training_attempts'](h.agent,h.metrics)
        self.ns['no_training_attempts'](h.agent,h.metrics)
        h.metrics.measurement_active=False
        self.ns['no_training_attempts'](h.agent,h.metrics)
        for fault in('available','attempt','outcome','unavailable','replay_insert','epoch','hold','metrics_enabled',
                     'measurement_active','ratchet_frozen'):
            h=self.toy()
            if fault=='available':h.optimizer_observation['available']=True
            elif fault=='attempt':h.optimizer_observation['total']['attempts_started']=1
            elif fault=='outcome':h.optimizer_observation['total']['outcomes_recorded']=1
            elif fault=='unavailable':h.optimizer_observation['total']['unavailable']=1
            elif fault=='replay_insert':h.replay_observation['accepted_total']=1
            elif fault=='epoch':h.replay_observation['epoch']=2
            elif fault=='hold':h.agent._continuous_startup_held=False
            elif fault=='measurement_active':h.metrics.measurement_active=True
            elif fault=='ratchet_frozen':h.metrics.ratchet_frozen=True
            else:h.metrics.training_enabled=True
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):self.ns['no_training_attempts'](h.agent,h.metrics)

    def test_actual_real_CPU_payload_Adam_scaler_phase_and_clock_equality(self):
        h=self.toy();self.assertEqual(h.payload(),h.manifest['saved_scalars'])
        for fault in('online','target','Adam','scaler','phase','clock','loaded_anchor','geometry'):
            h=self.toy()
            if fault in('online','target'):
                net=h.agent.online_net if fault=='online'else h.agent.target_net
                with self.torch.no_grad():net.weight[0,0]+=1
            elif fault=='Adam':next(iter(h.agent.optimizer.state.values()))['exp_avg'][0,0]+=1
            elif fault=='scaler':state=h.agent.grad_scaler.state_dict();state['scale']*=2;h.agent.grad_scaler.load_state_dict(state)
            elif fault=='phase':h.actual_phase['priority_update_calls']+=1
            elif fault=='clock':h.metrics.measurement_frame_count+=1
            elif fault=='loaded_anchor':h.agent.loaded_optimized_samples+=4096
            else:h.cfg.frame_stack=2
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):h.payload()

    def test_actual_NumPy_original_mapping_scalar_PRIORITIES_and_bank_equality(self):
        h=self.toy();result=h.replay()
        self.assertTrue(result['all_eight_scalar_replay_payloads_equal']);self.assertTrue(result['all_PER_leaf_priorities_equal'])
        for fault in('consumed','pointer','object','scalar','priorities','UID','length','bank_payload','age'):
            h=self.toy()
            if fault=='consumed':h.memory._continuous_exact_resume_consumed=False
            elif fault=='pointer':h.memory.tree.data_ptr+=1
            elif fault=='object':h.manifest['ring_and_banks']['ring']['arrays']['actions']['identity']['inode']+=1
            elif fault=='scalar':h.manifest['ring_scalar_payload']['interesting']['payload']['sha256']='f'*64
            elif fault=='priorities':h.memory.tree.tree[4]+=1
            elif fault=='UID':h.memory.hof_ep_game[0]+=1
            elif fault=='length':h.memory.ephof_ep_len[0]+=1
            elif fault=='bank_payload':h.memory.hof_states[0,0]+=1
            else:h.memory._hof_last_admit_add-=1
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):h.replay()

    def test_actual_complete_held_report_and_one_use_release_before_enable(self):
        h=self.toy().prepare_full_call();calls=h.run_full()
        self.assertEqual(calls,['verified-held-before-first-update.json','release-consumed.json'])
        self.assertTrue(h.agent.training_enabled);self.assertTrue(h.metrics.training_enabled)
        self.assertFalse(h.agent._continuous_startup_held)
        receipt=json.loads((h.output/'release-consumed.json').read_bytes())
        self.assertEqual(receipt['owner'],h.owner);self.assertEqual(receipt['original_job'],h.jobpin)
        self.assertTrue(receipt['no_optimizer_or_replay_work_before_release'])
        with self.assertRaises(RuntimeError):h.run_full()  # Existing original output is never reused.

    def test_actual_release_owner_source_work_and_timeout_fail_closed(self):
        for fault in('foreign_release_owner','wrong_report','wrong_job','wrong_checkpoint','deny_training',
                     'changed_owner','old_owner','attempt_before_release','source_changed','timeout',
                     'failed_stopped_report','unclosed_authority'):
            h=self.toy().prepare_full_call()
            if fault in('failed_stopped_report','unclosed_authority'):
                field='stopped_CPU_report'if fault=='failed_stopped_report'else'stopped_state_authority'
                value=json.loads(Path(h.job[field]['path']).read_bytes())
                if fault=='failed_stopped_report':value['status']='FAIL'
                else:value['old_trainer_and_population_closed']=False
                h.job[field]=immutable(h.root/('changed-'+field+'.json'),value)
                h.jobpin=immutable(h.root/'changed-job.json',h.job)
                h.environment.update(ROBOTRON_CONTINUOUS_STARTUP_JOB=h.jobpin['path'],
                    ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256=h.jobpin['sha256'])
            with self.subTest(fault=fault),self.assertRaises((RuntimeError,TimeoutError)):h.run_full(fault)
            self.assertFalse(h.agent.training_enabled);self.assertFalse(h.metrics.training_enabled)
            self.assertTrue(h.agent._continuous_startup_held)
            self.assertFalse((h.output/'release-consumed.json').exists())
            self.assertTrue(h.memory.lock.acquire(blocking=False));h.memory.lock.release()

    def test_actual_source_hold_order_precedes_workers_listeners_and_normalization(self):
        packet=json.loads((HERE/'prepared-continuous-before-update-startup-hold-metrics-ABI-v2-SOURCE-ONLY-NOT-QUALIFIED.json').read_bytes())
        for row in packet['source_files'].values():self.assertEqual(pin(row['path']),row)
        agent=Path(packet['source_files']['agent']['path']).read_text()
        main=Path(packet['source_files']['main']['path']).read_text()
        replay=Path(packet['source_files']['replay']['path']).read_text()
        self.assertLess(agent.index('self.training_enabled = not self._continuous_startup_held'),agent.index('self._prefetcher = ReplayPrefetcher('))
        self.assertLess(agent.index('self.training_enabled = not self._continuous_startup_held'),agent.index('self._train_thread = threading.Thread('))
        self.assertLess(main.index('verify_restoration_and_wait('),main.index('server = SocketServer('))
        self.assertIn('_continuous_exact_resume_consumed',replay)
        # Actual no-work guard remains decisive even if source order is correct.
        h=self.toy();h.optimizer_observation['unclassified_started_total']=1
        with self.assertRaises(RuntimeError):self.ns['no_training_attempts'](h.agent,h.metrics)


if __name__=='__main__':unittest.main()
