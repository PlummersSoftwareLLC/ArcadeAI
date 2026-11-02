"""Synthetic/temp-only prospective root160 verifier contracts; no Torch/future data."""
import copy,importlib.util,json,math,os,sys,tempfile,unittest
from contextlib import contextmanager,ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('root160_verifier_fixture',HERE/'root_verify160M_lineage.py')
module=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(module)
class Tensor:
    def __init__(self,value=1.,shape=(),dtype='torch.float32',device='cpu'):
        self.value,self.shape,self.dtype,self.device=value,shape,dtype,SimpleNamespace(type=device)
    def item(self):return self.value
    def numel(self):return math.prod(self.shape)
TORCH=SimpleNamespace(is_tensor=lambda value:isinstance(value,Tensor))
class Root160Tests(unittest.TestCase):
    def test_actual_pinned_Adam_owner_geometry_not_merely_equal_paired_moments(self):
        online=dict(support=Tensor(shape=(51,)),**{'p'+str(i):Tensor(shape=(i+1,)) for i in range(99)})
        ids=list(range(99));states={i:dict(exp_avg=Tensor(shape=(i+1,)),exp_avg_sq=Tensor(shape=(i+1,))) for i in range(81)}
        module.check_moments(states,ids,online,list(online),TORCH.is_tensor)
        for broken in (dict(exp_avg=Tensor(shape=(4,)),exp_avg_sq=Tensor(shape=(4,))),
                       dict(exp_avg=Tensor(shape=(1,),dtype='torch.float16'),exp_avg_sq=Tensor(shape=(1,),dtype='torch.float16'))):
            states[0]=broken
            with self.subTest(broken=broken),self.assertRaisesRegex(ValueError,'online parameter'):
                module.check_moments(states,ids,online,list(online),TORCH.is_tensor)
    def test_unknown_Adam_owner_or_duplicate_group_ID_cannot_bind(self):
        online=dict(support=Tensor(shape=(51,)),**{'p'+str(i):Tensor(shape=(2,)) for i in range(99)})
        states={i:dict(exp_avg=Tensor(shape=(2,)),exp_avg_sq=Tensor(shape=(2,))) for i in range(81)}
        ids=list(range(99));ids[-1]=0
        with self.assertRaises(ValueError):module.check_moments(states,ids,online,list(online),TORCH.is_tensor)
        bad_ids=list(range(99));bad_ids[0]=False
        with self.assertRaises(ValueError):module.check_moments(states,bad_ids,online,list(online),TORCH.is_tensor)
        malformed=copy.deepcopy(states);malformed[True]=malformed.pop(1)
        with self.assertRaises(ValueError):module.check_moments(malformed,list(range(99)),online,list(online),TORCH.is_tensor)
        states[999]=states.pop(0)
        with self.assertRaises(ValueError):module.check_moments(states,list(range(99)),online,list(online),TORCH.is_tensor)
    def test_import_default_help_is_inert_and_no_Torch_is_imported(self):
        before=set(sys.modules)
        with patch.object(Path,'read_bytes',side_effect=AssertionError('future data opened')),patch.object(Path,'open',side_effect=AssertionError('file opened')):
            spec=importlib.util.spec_from_file_location('inert_root160',HERE/'root_verify160M_lineage.py')
            loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
            with patch('sys.argv',['root_verify160M_lineage.py']),patch('argparse.ArgumentParser.print_help'):loaded.main()
        self.assertFalse(any(name=='torch' or name.startswith('torch.') for name in set(sys.modules)-before))
    def test_missing_each_explicit_actual_SHA_stops_before_evidence_or_Torch(self):
        for key in ('proposal_sha256','checkpoint_sha256','runtime_metadata_sha256'):
            args=SimpleNamespace(verify=True,proposal=Path('/not-an-actual-proposal.json'),proposal_sha256='a'*64,
                checkpoint=Path('/not-an-actual-checkpoint.pt'),checkpoint_sha256='b'*64,
                runtime_metadata=Path('/not-an-actual-runtime.json'),runtime_metadata_sha256='c'*64,
                output=Path('/not-an-output.json'))
            setattr(args,key,'ROOT_FUTURE_SHA')
            with self.subTest(key=key),patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''),patch.object(Path,'open',side_effect=AssertionError('checkpoint/evidence opened')),self.assertRaises(ValueError):module.verify(args)
    def test_output_whitelist_excludes_state_controls_other_runs_and_overwrite(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(module,'HERE',Path(directory)/'proposal'):
            valid=Path(directory)/'fresh3-160M-checkpoint-lineage.json'
            self.assertEqual(module.output_path(valid),valid)
            for target in (Path(directory)/'state.json',Path(directory)/'learning_control.json',Path(directory).parent/'fresh3-160M-checkpoint-lineage.json'):
                with self.subTest(target=target),self.assertRaises(ValueError):module.output_path(target)
            valid.write_bytes(b'retain')
            with self.assertRaises(ValueError):module.output_path(valid)
            self.assertEqual(valid.read_bytes(),b'retain')
    def test_saved_logical_sample_and_Adam_exposure_are_distinct(self):
        before=dict(training_steps=10,optimized_samples=1000,learner_frame_count=20)
        after=dict(training_steps=14,optimized_samples=1000+4*4096,learner_frame_count=21)
        result=module.interval(before,after,[8.],[11.],'fake128to160','default',True)
        self.assertEqual((result['logical_updates_delta'],result['Adam_uniform_step_delta'],result['logical_minus_uniform_Adam_delta']),(4,3,1))
        for broken,steps in ((dict(after,optimized_samples=after['optimized_samples']+1),[11.]),(dict(after,training_steps=True),[11.]),(after,[float('inf')]),(after,[7.]),(after,[10.5])):
            with self.subTest(broken=broken,steps=steps),self.assertRaises(ValueError):module.interval(before,broken,[8.],steps,'fake','default',True)
    def test_scalar_CPU_metadata_and_recursive_tensor_walk_reject_invalid_values(self):
        cpu=Tensor(2.)
        self.assertEqual(module.scalar(cpu,TORCH),2.)
        self.assertEqual(list(module.tensor_walk({'a':[cpu,{'b':cpu}],'ignored':3},TORCH)),[cpu,cpu])
        for bad in (float('nan'),float('inf'),b'bytes',Tensor(shape=(2,))):
            with self.subTest(value=bad),self.assertRaises(ValueError):module.scalar(bad,TORCH)
        class ForbiddenGPU(Tensor):
            def item(self):raise AssertionError('GPU data was read')
        with self.assertRaises(ValueError):module.scalar(ForbiddenGPU(device='cuda'),TORCH)
    def test_exclusive_readonly_publication_and_changed_evidence_no_visibility(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'new-lineage.json'
            class Evidence:
                def recheck(self):self.checked=True
            evidence=Evidence();original_link=module.os.link
            def link(source,destination):
                self.assertTrue(evidence.checked)
                self.assertEqual(Path(source).stat().st_mode&0o777,0o444)
                return original_link(source,destination)
            with patch.object(module.os,'link',side_effect=link):module.publish(output,{'fixture':True},evidence)
            old=output.read_bytes();self.assertEqual(json.loads(old),{'fixture':True});self.assertEqual(output.stat().st_nlink,1)
            with self.assertRaises((FileExistsError,ValueError)):module.publish(output,{'changed':True},evidence)
            self.assertEqual(output.read_bytes(),old)
            class Changed:
                def recheck(self):raise ValueError('changed evidence')
            rejected=Path(directory)/'rejected.json'
            with self.assertRaisesRegex(ValueError,'changed'):module.publish(rejected,{},Changed())
            self.assertFalse(rejected.exists());self.assertEqual(list(Path(directory).iterdir()),[output])
    @contextmanager
    def full_fixture(self):
        """Run the real verifier flow on temp bytes and an explicit fake Torch module."""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game=root/'Robotron';run=game/'logs/fixture/run23';here=run/'proposal';here.mkdir(parents=True)
            candidate=game/'models_dqn/managed-checkpoints/fresh3-160M.pt';candidate.parent.mkdir(parents=True);candidate.write_bytes(b'fake weights, never Torch data')
            previous=dict(engine_version=28,state_size=11128,single_frame_state_size=2782,frame_stack=4,
                baseline_batch_size=512,training_steps=907399,optimized_samples=2269118464,total_training_steps=907399,
                learner_frame_count=132631504,frame_count=265431768,measurement_frame_count=7550388,
                last_target_update_samples=2268897280,lr_anchor_step=0.,lr_gear='climb',epsilon=.1,expert_ratio=.1)
            metadata=dict(previous,training_steps=1007399,total_training_steps=1007399,optimized_samples=2678718464,
                learner_frame_count=164629146,frame_count=330000000)
            network=dict(support=Tensor(shape=(51,)),**{'p'+str(i):Tensor(shape=(2,3)) for i in range(99)})
            raw_optimizer=dict(state={i:dict(step=Tensor(1006997.),exp_avg=Tensor(shape=(2,3)),
                exp_avg_sq=Tensor(shape=(2,3))) for i in range(81)},param_groups=[dict(params=list(range(99)),lr=2.5e-5,betas=(.9,.999),eps=.00015,fused=True)])
            saved=dict(metadata,online_state_dict=network,target_state_dict=copy.deepcopy(network),optimizer_state_dict=raw_optimizer)
            signatures={key:{name:dict(shape=list(value.shape),dtype=value.dtype) for name,value in saved[key].items()} for key in ('online_state_dict','target_state_dict')}
            groups=[dict(lr=2.5e-5,betas=[.9,.999],eps=.00015,fused=True,parameter_count=99)]
            optimizer=dict(state_count=81,step_values=[1006997.],minimum_parameter_step=1006997.,maximum_parameter_step=1006997.,groups=groups,all_tensors_CPU=True,tensor_count=243)
            reference=dict(proposal_only=False,PASS=True,checks=dict(CPU_only=True),root_verification=dict(status='PASS',CUDA_initialized=False),
                candidate=dict(sha256='a'*64,saved_metadata=previous,state_dict_signatures=signatures,
                    optimizer=dict(optimizer,step_values=[907002.],minimum_parameter_step=907002.,maximum_parameter_step=907002.)),branch_provenance=dict(compiler_and_instrumentation_chronology=[dict(compiler='historical rejected B retained')]))
            environment=dict(DQN_BATCH_SIZE='4096',DQN_COMPILE_MODE='default',DQN_LEARNING_EXPOSURE_COUNTERS='1',DQN_N_STEP='3',DQN_MAX_SAMPLES_PER_FRAME='8',DQN_C51_TARGET_SMOOTHING='0',DQN_STREAM_BANK_OUTPUT='1')
            runtime=dict(config=dict(batch_size=4096,baseline_batch_size=512,n_step=3,max_samples_per_frame=8.,c51_target_smoothing=0.,torch_compile_mode='default'),environment=environment)
            controls=dict(experiment='best10M-fresh3-eps10-cap8-nosmooth',lr_scale=.5,epsilon_ramp=dict(start=.1,end=.1))
            control_path=game/'models_dqn/learning_control.json';control_path.write_text(json.dumps(controls))
            runtime_path=run/'runtime.json';runtime_path.write_text(json.dumps(runtime));runtime_sha=module.sha(runtime_path)
            gate_path=run/'fresh3-160M-gate.json';gate=dict(tag='fresh3-160M',target=164629023,experiment=controls['experiment'],checkpoint=str(candidate));gate_path.write_text(json.dumps(gate))
            proposal=dict(schema='robotron-160M-checkpoint-lineage-v1',proposal_only=True,PASS=True,checks=dict(CPU_only=True),root_verification='PENDING independent root',limitations=[],
                counter_exposure_evidence=dict(available=False),candidate=dict(path=str(candidate),sha256=module.sha(candidate),stat=module.identity(candidate),saved_metadata=metadata,optimizer=optimizer,state_dict_signatures=signatures,checkpoint_tensor_count=443,tensor_devices=['cpu'],all_network_optimizer_tensors_finite=True),
                trigger_gate=dict(path=str(gate_path),sha256=module.sha(gate_path),record=gate),
                branch_provenance=dict(experiment=controls['experiment'],unchanged4096_after128M=True,compile_mode='default',exposure_counters_enabled=True,control_path=str(control_path),control_snapshot=controls,runtime_metadata_path=str(runtime_path),runtime_metadata_sha256=runtime_sha,recorded_runtime_recipe=runtime),
                actual_recorded_batch_exposure=dict(since128M=dict(recorded_batch_size=4096,logical_updates_delta=100000,optimized_samples_delta=409600000,learner_frames_delta=metadata['learner_frame_count']-previous['learner_frame_count'])))
            proposal_path=run/'proposed.json';proposal_path.write_text(json.dumps(proposal))
            source_hashes={};applied={}
            for name in ['agent.py','replay_buffer.py','training.py','learning_exposure.py',*['source'+str(i)+'.py' for i in range(16)]]:
                relative='Robotron/Scripts/dqn/'+name;q=root/relative;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(name.encode());source_hashes[relative]=module.sha(q)
                if name in ('agent.py','replay_buffer.py','training.py','learning_exposure.py'):applied[name]=source_hashes[relative]
            private={}
            for i in range(12):
                relative='Scripts/private'+str(i)+'.py';q=game/relative;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(relative.encode());private[relative]=module.sha(q)
            actual_analyzer=HERE.parent/'quality160M-preparation/analyze160M_guard.py'
            actual_spec=importlib.util.spec_from_file_location('real160_contract_for_fake_root',actual_analyzer)
            actual_contract=importlib.util.module_from_spec(actual_spec);actual_spec.loader.exec_module(actual_contract)
            loader_path=here/'fake_capture.py';loader_path.write_bytes(b'# fake capture source only')
            documents=dict(plan=dict(reference=dict(checkpoint=dict(sha256='a'*64),saved_clocks=previous),candidate=dict(checkpoint=str(candidate))),reference128M=reference,
                protected128_metadata=dict(sha256='a'*64,saved_checkpoint_metadata=previous),
                source20_private12=dict(PASS=True,pid=1436155,start_ticks=24126660,environment=environment,source_hashes=source_hashes,private12_hashes=private),
                counter_application=dict(PASS=True,reviewed_proposed_bytes_exact=True,guarded_source12_unchanged=True,applied_sources=applied),run23_environment=environment,runtime_metadata=runtime,
                root128_promotion=dict(PASS=True,new_incumbent=dict(sha256='a'*64)),
                root_plan_adoption=dict(status='ROOT_ADOPTED_PLAN_AND_ANALYZER_BEFORE_ACTUAL160M_BYTES',files={'analyze160M_guard.py':module.sha(actual_analyzer)}),
                root_capture_adoption=dict(status='ROOT_ADOPTED_PROSPECTIVE_CPU_CAPTURE_LOADER_BEFORE_ACTUAL160M',files={'capture160M_lineage_proposal.py':module.sha(loader_path)}),independent_loader_review=dict(PASS=True))
            records=dict(analyzer=dict(path=str(actual_analyzer),sha256=module.sha(actual_analyzer)),capture_loader=dict(path=str(loader_path),sha256=module.sha(loader_path)))
            for name,document in documents.items():
                q=runtime_path if name=='runtime_metadata' else here/(name+'.json')
                if name!='runtime_metadata':q.write_text(json.dumps(document))
                records[name]=dict(path=str(q),sha256=module.sha(q))
            manifest=dict(evidence=records,expected_process=dict(pid=1436155,start_ticks=24126660),checkpoint=str(candidate.relative_to(game)),gate=str(gate_path.relative_to(game)))
            manifest_path=here/'verification-precommit.json';manifest_path.write_text(json.dumps(manifest))
            class Evidence:
                def __init__(self):self.files={};self.stats={}
                def _path(self,path):return Path(path).absolute()
                def file(self,path,expected):
                    path=Path(path).absolute()
                    if module.sha(path)!=expected:raise ValueError('fake evidence byte changed')
                    self.files[str(path)]=expected;return path
                def json(self,path,expected=None):
                    path=Path(path).absolute();raw=path.read_bytes();digest=__import__('hashlib').sha256(raw).hexdigest()
                    if expected is not None and digest!=expected:raise ValueError('fake evidence byte changed')
                    self.files[str(path)]=digest;return json.loads(raw)
                def bind_stat(self,path,identity):self.stats[str(path)]=identity
                def recheck(self):
                    for path,expected in self.files.items():
                        if module.sha(path)!=expected:raise ValueError('fake evidence changed before publication')
                    for path,expected in self.stats.items():
                        if module.identity(path)!=expected:raise ValueError('fake identity changed')
                def snapshot(self):return [dict(path=path,sha256=value) for path,value in self.files.items()]
            contract=SimpleNamespace(Evidence=Evidence,META_KEYS=actual_contract.META_KEYS,lineage_identity=actual_contract.lineage_identity)
            fake_spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda mod:None))
            class Finite:
                def __init__(self,value):self.value=value
                def all(self):return self
                def item(self):return self.value
            torch=SimpleNamespace(is_tensor=TORCH.is_tensor,isfinite=lambda x:Finite(math.isfinite(x.value)),__version__='fake Torch namespace; installed Torch never imported',
                cuda=SimpleNamespace(is_initialized=lambda:False),set_num_threads=lambda n:None,set_num_interop_threads=lambda n:None,get_num_threads=lambda:2,load_calls=0,after_load=lambda:None)
            def load(path,*,map_location,weights_only):
                self.assertEqual(Path(path),candidate);self.assertEqual(map_location,'cpu');self.assertIs(weights_only,True)
                torch.load_calls+=1;torch.after_load();return saved
            torch.load=load
            args=SimpleNamespace(verify=True,proposal=proposal_path,proposal_sha256=module.sha(proposal_path),checkpoint=candidate,checkpoint_sha256=module.sha(candidate),runtime_metadata=runtime_path,runtime_metadata_sha256=runtime_sha,output=run/'fresh3-160M-checkpoint-lineage-fixture.json')
            f=SimpleNamespace(args=args,saved=saved,proposal=proposal,reference=reference,environment=environment,torch=torch,process=dict(pid=1436155,start_ticks=24126660),source_path=root/'Robotron/Scripts/dqn/agent.py')
            def sync_proposal():proposal_path.write_text(json.dumps(proposal));args.proposal_sha256=module.sha(proposal_path)
            f.sync_proposal=sync_proposal
            with ExitStack() as stack:
                for name,value in dict(HERE=here,GAME=game,REPO=root,PRECOMMIT_SHA=module.sha(manifest_path)).items():stack.enter_context(patch.object(module,name,value))
                stack.enter_context(patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''))
                stack.enter_context(patch.dict(sys.modules,torch=torch))
                stack.enter_context(patch.object(module.importlib.util,'spec_from_file_location',return_value=fake_spec))
                stack.enter_context(patch.object(module.importlib.util,'module_from_spec',return_value=contract))
                identity=stack.enter_context(patch.object(module,'process_identity',return_value=f.process));f.process_mock=identity
                env=stack.enter_context(patch.object(module,'process_environment',return_value=environment));f.environment_mock=env
                yield f
    def test_full_fake_independent_verification_preserves_history_and_no_API_reconciliation(self):
        with self.full_fixture() as f:
            result=module.verify(f.args)
            self.assertFalse(result['proposal_only']);self.assertEqual(result['root_verification']['status'],'PASS')
            self.assertEqual(f.torch.load_calls,1);self.assertGreaterEqual(f.process_mock.call_count,2)
            self.assertFalse(result['counter_exposure_evidence']['available'])
            chronology=result['branch_provenance']['compiler_and_instrumentation_chronology'][0]
            self.assertEqual((chronology['logical_updates_delta'],chronology['Adam_uniform_step_delta'],chronology['logical_minus_uniform_Adam_delta']),(100000,99995,5))
            self.assertEqual(result['branch_provenance']['prior128M_history']['compiler_and_instrumentation_chronology'],f.reference['branch_provenance']['compiler_and_instrumentation_chronology'])
            self.assertEqual(f.args.output.stat().st_mode&0o777,0o444)
            self.assertEqual(json.loads(f.args.output.read_bytes())['candidate']['sha256'],f.args.checkpoint_sha256)
    def test_full_fake_wrong_process_or_current_environment_fails_before_CPU_load(self):
        for mode in ('process','environment'):
            with self.subTest(mode=mode),self.full_fixture() as f:
                if mode=='process':f.process_mock.return_value=dict(f.process,start_ticks=f.process['start_ticks']+1)
                else:f.environment_mock.return_value=dict(f.environment,DQN_COMPILE_MODE='changed')
                with self.assertRaises(ValueError):module.verify(f.args)
                self.assertEqual(f.torch.load_calls,0);self.assertFalse(f.args.output.exists())
    def test_full_fake_actual_metadata_nonfinite_or_moment_drift_cannot_publish(self):
        for mode in ('metadata','nonfinite','moments','anchor','inventory'):
            with self.subTest(mode=mode),self.full_fixture() as f:
                if mode=='metadata':f.saved['optimized_samples']+=4096
                elif mode=='nonfinite':f.saved['online_state_dict']['p0'].value=float('inf')
                elif mode=='moments':
                    f.saved['optimizer_state_dict']['state'][0]['exp_avg'].shape=(3,2)
                    f.saved['optimizer_state_dict']['state'][0]['exp_avg_sq'].shape=(3,2)
                elif mode=='inventory':
                    f.proposal['candidate']['optimizer']['tensor_count']+=1;f.sync_proposal()
                else:
                    f.saved['lr_anchor_step']=False;f.proposal['candidate']['saved_metadata']['lr_anchor_step']=False;f.sync_proposal()
                with self.assertRaises(ValueError):module.verify(f.args)
                self.assertFalse(f.args.output.exists())
    def test_full_fake_postload_process_or_source_drift_cannot_publish(self):
        for mode in ('process','source'):
            with self.subTest(mode=mode),self.full_fixture() as f:
                if mode=='process':f.process_mock.side_effect=[f.process,dict(f.process,start_ticks=f.process['start_ticks']+1)]
                else:f.torch.after_load=lambda:f.source_path.write_bytes(b'changed after initial inventory verification')
                with self.assertRaises(ValueError):module.verify(f.args)
                self.assertEqual(f.torch.load_calls,1);self.assertFalse(f.args.output.exists())

if __name__=='__main__':unittest.main()
