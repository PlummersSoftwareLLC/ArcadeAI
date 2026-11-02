"""Synthetic/temp-only192M proposal fixtures; no real checkpoint/Torch import."""
import copy,hashlib,importlib.util,json,math,os,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fake192_capture',HERE/'capture192M_lineage_proposal.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Device:
    def __init__(self,name='cpu'):self.type=name
    def __str__(self):return self.type
class Tensor:
    def __init__(self,value=1.,shape=(),device='cpu',dtype='torch.float32'):
        self.value,self.shape,self.device,self.dtype=value,shape,Device(device),dtype
    def item(self):return self.value
    def numel(self):return math.prod(self.shape)
    def is_floating_point(self):return True
class Finite:
    def __init__(self,value):self.value=value
    def all(self):return self
    def item(self):return self.value
TORCH=SimpleNamespace(is_tensor=lambda x:isinstance(x,Tensor),isfinite=lambda x:Finite(math.isfinite(x.value)),
    cuda=SimpleNamespace(is_initialized=lambda:False),__version__='fakeCPU',get_num_threads=lambda:2,
    get_num_interop_threads=lambda:1)
def optimizer():
    return dict(state={i:dict(step=Tensor(1006997.),exp_avg=Tensor(shape=(2,3)),
        exp_avg_sq=Tensor(shape=(2,3))) for i in range(81)},param_groups=[dict(params=list(range(99)),
        lr=2.5e-5,betas=(.9,.999),eps=.00015,fused=True)])
class Evidence:
    def __init__(self):self.calls=[]
    def bind_stat(self,*args):self.calls.append('bind')
    def snapshot(self):return []
    def recheck(self):self.calls.append('recheck')
class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.candidate=self.root/'fake192.pt';self.candidate.write_bytes(b'fixture only, not a checkpoint')
        self.contract=module.load_contract()
        self.previous=dict(engine_version=28,state_size=11128,single_frame_state_size=2782,frame_stack=4,
            baseline_batch_size=512,training_steps=907399,optimized_samples=2269118464,total_training_steps=907399,
            learner_frame_count=132631504,frame_count=265431768,measurement_frame_count=7550388,
            last_target_update_samples=2268897280,lr_anchor_step=0.,lr_gear='climb',epsilon=.1,expert_ratio=.1)
        self.after=dict(self.previous,training_steps=1007399,total_training_steps=1007399,
            learner_frame_count=module.TARGET+123,frame_count=330000000,optimized_samples=2269118464+100000*4096)
        network=dict(support=Tensor(shape=(51,)),**{'p'+str(i):Tensor(shape=(2,3)) for i in range(99)})
        self.saved=dict(self.after,online_state_dict=network,target_state_dict=copy.deepcopy(network),optimizer_state_dict=optimizer())
        info,_=module.optimizer_info(optimizer(),TORCH);info['step_values']=[907002.]
        info['minimum_parameter_step']=info['maximum_parameter_step']=907002.
        self.reference=dict(proposal_only=False,PASS=True,root_verification=dict(status='PASS',CUDA_initialized=False),
            checks=dict(CPU_only=True),candidate=dict(sha256='a'*64,saved_metadata=self.previous,optimizer=info,
                state_dict_signatures={k:module.signature(self.saved[k],TORCH) for k in ('online_state_dict','target_state_dict')}))
        self.plan=dict(reference=dict(checkpoint=dict(path='fake128.pt',sha256='a'*64),saved_clocks=self.previous,
            lineage_path='fake128.json',lineage_sha256='b'*64),branch_and_exposure=dict(experiment=module.EXPERIMENT,
                batch_size=4096,compile_mode='default',exposure_counters=True))
        self.runtime=dict(config=dict(batch_size=4096,baseline_batch_size=512,n_step=3,max_samples_per_frame=8.,
            c51_target_smoothing=0.,torch_compile_mode='default'),environment=dict(DQN_BATCH_SIZE='4096',
            DQN_COMPILE_MODE='default',DQN_LEARNING_EXPOSURE_COUNTERS='1',DQN_N_STEP='3',DQN_MAX_SAMPLES_PER_FRAME='8',
            DQN_C51_TARGET_SMOOTHING='0',DQN_STREAM_BANK_OUTPUT='1'))
        self.controls=dict(experiment=module.EXPERIMENT,lr_scale=.5,epsilon_ramp=dict(start=.1,end=.1))
        self.gate=dict(tag='fresh3-192M',target=module.TARGET,experiment=module.EXPERIMENT,checkpoint=str(self.candidate))
        self.evidence=Evidence();self.before=self.contract.file_stat(self.candidate)
    def report(self):
        return module.proposed_report(TORCH,self.saved,self.candidate,module.sha(self.candidate),self.before,
            self.gate,self.root/'gate.json','c'*64,self.reference,self.plan,self.runtime,self.root/'runtime.json',
            'd'*64,self.controls,self.evidence,'fixture',time.monotonic(),self.contract)
    def test_full_proposal_uses_only128_reference_and_separate_clock_exposure(self):
        result=self.report();self.assertTrue(result['proposal_only']);self.assertTrue(result['PASS'])
        self.assertEqual(result['actual_recorded_batch_exposure']['since128M'],dict(recorded_batch_size=4096,
            logical_updates_delta=100000,optimized_samples_delta=409600000,learner_frames_delta=self.after['learner_frame_count']-self.previous['learner_frame_count']))
        self.assertEqual(result['actual_recorded_batch_exposure']['minimum_Adam_parameter_step_delta'],99995)
        self.assertFalse(result['counter_exposure_evidence']['available'])
        self.assertNotIn('protected64M',result);self.assertNotIn('prior96M',result)
        with self.assertRaisesRegex(ValueError,'FINAL root-verified'):self.contract.lineage_identity(result,self.candidate,self.previous)
        final=copy.deepcopy(result);final.update(proposal_only=False,root_verification=dict(status='PASS',CUDA_initialized=False))
        self.assertEqual(self.contract.lineage_identity(final,self.candidate,self.previous)['metadata'],self.after)
    def test_wrong_batch_or_nonmonotone_clocks_fail(self):
        self.saved['optimized_samples']+=2048
        with self.assertRaisesRegex(ValueError,'4096'):self.report()
        self.saved['optimized_samples']-=2048;self.saved['training_steps']=self.previous['training_steps'];self.saved['total_training_steps']=self.saved['training_steps']
        with self.assertRaisesRegex(ValueError,'exposure did not advance'):self.report()
    def test_gate_architecture_metadata_and_headers_are_strict(self):
        for key in ('engine_version','state_size','single_frame_state_size','frame_stack'):
            old=self.saved[key];self.saved[key]+=1
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'architecture metadata'):self.report()
            self.saved[key]=old
        self.saved['frame_count']=self.saved['learner_frame_count']-1
        with self.assertRaisesRegex(ValueError,'clock inconsistency'):self.report()
        self.saved['frame_count']=self.after['frame_count'];self.gate['experiment']='changed'
        with self.assertRaisesRegex(ValueError,'gate identity'):self.report()
    def test_fleet_target_clocks_cannot_regress_and_optimizer_LR_is_numeric_positive(self):
        self.saved['frame_count']=self.previous['frame_count']-1
        with self.assertRaisesRegex(ValueError,'clock inconsistency'):self.report()
        self.saved['frame_count']=self.after['frame_count']
        self.saved['last_target_update_samples']=self.previous['last_target_update_samples']-1
        with self.assertRaisesRegex(ValueError,'clock inconsistency'):self.report()
        self.saved['last_target_update_samples']=self.after['last_target_update_samples']
        for bad in (0.,-1.,True):
            self.saved['optimizer_state_dict']['param_groups'][0]['lr']=bad
            with self.subTest(LR=bad),self.assertRaisesRegex(ValueError,'Invalid optimizer LR'):self.report()

    def test_recorded_compiler_counter_batch_and_behavior_recipe_changes_fail(self):
        for field,new in [('DQN_COMPILE_MODE','max-autotune'),('DQN_LEARNING_EXPOSURE_COUNTERS','0'),('DQN_BATCH_SIZE','2048')]:
            old=self.runtime['environment'][field];self.runtime['environment'][field]=new
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'runtime compiler'):self.report()
            self.runtime['environment'][field]=old
        self.controls['lr_scale']=.25
        with self.assertRaisesRegex(ValueError,'Current branch'):self.report()
        self.controls['lr_scale']=.5;self.saved['lr_anchor_step']=1.
        with self.assertRaisesRegex(ValueError,'Saved LR lineage'):self.report()
    def test_LR_anchor_bool_nonfinite_and_wrong_lineage_are_rejected(self):
        for bad in (False,True,float('nan'),1.):
            self.saved['lr_anchor_step']=bad
            with self.subTest(anchor=bad),self.assertRaises(ValueError):self.report()

    def test_final_root_reference_and_actual_state_shapes_CPU_are_required(self):
        self.reference['proposal_only']=True
        with self.assertRaisesRegex(ValueError,'final root CPU128'):self.report()
        self.reference['proposal_only']=False;self.saved['online_state_dict']['p1'].shape=(7,)
        with self.assertRaisesRegex(ValueError,'signature differs'):self.report()
        self.saved['online_state_dict']['p1'].shape=(2,3);self.saved['target_state_dict']['p2'].device=Device('cuda')
        with self.assertRaisesRegex(ValueError,'Non-CPU network'):self.report()
    def test_Adam_pair_wrong_shape_dtype_owner_steps_and_group_fail(self):
        for change in ('shape','dtype','owner','step','group'):
            self.saved['optimizer_state_dict']=optimizer();opt=self.saved['optimizer_state_dict']
            if change=='shape':opt['state'][0]['exp_avg'].shape=opt['state'][0]['exp_avg_sq'].shape=(3,2)
            elif change=='dtype':opt['state'][0]['exp_avg'].dtype=opt['state'][0]['exp_avg_sq'].dtype='torch.float64'
            elif change=='owner':opt['state'][999]=opt['state'].pop(0)
            elif change=='step':opt['state'][0]['step']=Tensor(907001.)
            else:opt['param_groups'][0]['eps']=.001
            with self.subTest(change=change),self.assertRaises(ValueError):self.report()
    def test_nonfinite_tensor_or_changed_candidate_is_rejected(self):
        self.saved['optimizer_state_dict']['state'][0]['exp_avg'].value=float('inf')
        with self.assertRaisesRegex(ValueError,'Nonfinite CPU'):self.report()
        self.saved['optimizer_state_dict']['state'][0]['exp_avg'].value=1.;self.candidate.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed during CPU capture'):self.report()
    def test_bool_Adam_state_owner_cannot_alias_integer_parameter_ID(self):
        states=self.saved['optimizer_state_dict']['state']
        row=states.pop(1);states[True]=row
        with self.assertRaisesRegex(ValueError,'Unknown Adam moment owner'):self.report()

    def test_missing_or_changed_completed_history_rejects_before_192_payload_hash(self):
        game=self.root/'Game';run=self.root/'capture';campaign=self.root/'campaign'
        run.mkdir();candidate=game/'models_dqn/managed-checkpoints/fresh3-192M.pt'
        candidate.parent.mkdir(parents=True);candidate.write_bytes(b'synthetic future fixture only')
        gate=campaign/'run-23/fresh3-192M-gate.json';gate.parent.mkdir(parents=True);gate.write_bytes(b'{}')
        analyzer=run/'analyze192M_assessment.py';analyzer.write_bytes(b'# synthetic source, not imported')
        history=self.root/'missing-history.json'
        plan=dict(history=dict(complete=True,manifest_path=str(history),manifest_sha256='0'*64))
        plan_path=run/'quality192M-assessment-plan.json';plan_path.write_text(json.dumps(plan))
        contract=SimpleNamespace(Evidence=self.contract.Evidence,history_manifest=self.contract.history_manifest)
        actual_sha=module.sha
        def payload_guard(path):
            self.assertNotEqual(Path(path),candidate,'192 payload was hashed before completed-history validation')
            return actual_sha(path)
        with patch.multiple(module,RUN=run,GAME=game,CAMPAIGN=campaign,
                GUARD_SHA=hashlib.sha256(analyzer.read_bytes()).hexdigest(),
                PLAN_SHA=hashlib.sha256(plan_path.read_bytes()).hexdigest()),\
                patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''),\
                patch.object(module,'load_contract',return_value=contract),\
                patch.object(module,'sha',side_effect=payload_guard):
            output=run/'proposed-fresh3-192M-fixture.json'
            with self.assertRaises(FileNotFoundError):module.capture(output,self.root/'runtime.json','e'*64)
            history.write_text('{"complete":true}')
            with self.assertRaisesRegex(ValueError,'Changed pinned JSON'):
                module.capture(output,self.root/'runtime.json','e'*64)
            self.assertFalse(output.exists())
    def test_Adam_LR_value_may_follow_existing_schedule_without_geometry_change(self):
        self.saved['optimizer_state_dict']['param_groups'][0]['lr']=1e-5
        self.assertEqual(self.report()['candidate']['optimizer']['groups'][0]['lr'],1e-5)
    def test_import_help_and_missing_pair_are_Torch_free_and_inert(self):
        before=set(sys.modules)
        with patch.object(Path,'read_bytes',side_effect=AssertionError('future read')):
            spec=importlib.util.spec_from_file_location('inert192',HERE/'capture192M_lineage_proposal.py')
            loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
            with patch('sys.argv',['capture192']),patch('argparse.ArgumentParser.print_help'):loaded.main()
        with patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''),patch.object(module,'RUN',self.root),patch.object(module,'GAME',self.root),patch.object(module,'CAMPAIGN',self.root),patch.object(module,'load_contract',side_effect=AssertionError('loaded before pair')):
            with self.assertRaisesRegex(ValueError,'must both exist'):module.capture(self.root/'proposed-fresh3-192M-fixture.json',self.root/'runtime.json','e'*64)
        self.assertFalse(any(x=='torch' or x.startswith('torch.') for x in set(sys.modules)-before))
    def test_CUDA_runtime_pin_and_output_policy_precede_any_capture_read(self):
        with patch.object(module,'load_contract',side_effect=AssertionError('opened')):
            with patch.dict(os.environ,CUDA_VISIBLE_DEVICES='0'),self.assertRaisesRegex(ValueError,'CUDA_VISIBLE'):module.capture(self.root/'x.json',None,None)
            with patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''),self.assertRaisesRegex(ValueError,'runtime metadata'):module.capture(self.root/'x.json',None,None)
        with patch.object(module,'RUN',self.root):
            for name in ('state.json','fresh3-192M-checkpoint-lineage.json','proposed-other.json'):
                with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Only a new'):module.output_policy(self.root/name)
    def test_exclusive_readonly_proposal_publication_rechecks_before_visibility(self):
        target=self.root/'proposed-fresh3-192M-fixture.json'
        class E:
            def recheck(self):self.called=True
        evidence=E()
        with patch.object(module,'RUN',self.root):
            module.publish_proposal(target,{'proposal_only':True},evidence)
            self.assertTrue(evidence.called);self.assertEqual(target.stat().st_mode&0o777,0o444)
            old=target.read_bytes()
            with self.assertRaisesRegex(ValueError,'already exists'):module.publish_proposal(target,{'different':True},evidence)
            self.assertEqual(target.read_bytes(),old)
            class Changed:
                def recheck(self):raise ValueError('drift')
            other=self.root/'proposed-fresh3-192M-other.json'
            with self.assertRaisesRegex(ValueError,'drift'):module.publish_proposal(other,{},Changed())
            self.assertFalse(other.exists());self.assertEqual(list(self.root.glob('.lineage192-*')),[])
if __name__=='__main__':unittest.main()
