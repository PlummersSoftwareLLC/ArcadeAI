"""Small synthetic/temp fixtures only. No future data, installed Torch or GPU."""
from contextlib import ExitStack, redirect_stdout
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value
helper = module('future_checkpoint_fixture', HERE/'verify_future_checkpoint_cpu.py')
DEPS = HERE.parents[1]/'run-23/collector4096-ABA-tools'
common = module('startup_common', DEPS/'startup_common.py')
sys.modules['startup_common'] = common
cpu = module('fixture_cpu_validation', DEPS/'startup_cpu_readonly.py')

class Tensor:
    def __init__(self, shape=(), value=0, dtype='torch.float32', device='cpu', finite=True):
        self.shape, self.value, self.dtype = tuple(shape), value, dtype
        self.device, self.finite = SimpleNamespace(type=device), finite
    def numel(self):
        result = 1
        for size in self.shape: result *= size
        return result
    def item(self): return self.value

TORCH = SimpleNamespace(is_tensor=lambda value: isinstance(value, Tensor),
    isfinite=lambda value: SimpleNamespace(all=lambda: value.finite))

def fixture():
    metadata = dict(engine_version=28, state_size=11128, single_frame_state_size=2782,
        frame_stack=4, baseline_batch_size=512, training_steps=1600, total_training_steps=1600,
        optimized_samples=6553600, learner_frame_count=228629100, frame_count=460000000,
        measurement_frame_count=7550388, last_target_update_samples=6500000,
        lr_anchor_step=0., lr_gear='climb', epsilon=.1, expert_ratio=.09999999999999998)
    networks = {kind:dict(support=Tensor((51,)), **{'p'+str(i):Tensor((i+1,)) for i in range(99)})
                for kind in ('online_state_dict','target_state_dict')}
    group = dict(params=list(range(99)), lr=.000025, betas=(.9,.999), eps=.00015,
        weight_decay=0, amsgrad=False, maximize=False, foreach=False, capturable=False,
        differentiable=False, fused=True, decoupled_weight_decay=False)
    optimizer = dict(state={i:dict(step=Tensor(value=1590),exp_avg=Tensor((i+1,)),exp_avg_sq=Tensor((i+1,)))
                            for i in range(81)},param_groups=[group])
    saved = dict(metadata,**networks,optimizer_state_dict=optimizer,grad_scaler_state_dict=dict(
        scale=65536.,growth_factor=2.,backoff_factor=.5,growth_interval=2000,_growth_tracker=1))
    signatures = {kind:{name:dict(shape=list(t.shape),dtype=t.dtype) for name,t in state.items()}
                  for kind,state in networks.items()}
    g=json.loads(json.dumps({k:v for k,v in group.items() if k!='params'}));g['parameter_count']=99
    previous=dict(metadata,training_steps=1000,total_training_steps=1000,optimized_samples=4096000,
        learner_frame_count=196632084,frame_count=392949008,last_target_update_samples=4000000)
    reference=dict(saved_metadata=previous,state_dict_signatures=signatures,sha256='a'*64,
                   optimizer=dict(groups=[g],step_values=[997.]))
    latest=dict(previous,training_steps=1250,total_training_steps=1250,optimized_samples=5120000,
        learner_frame_count=215606084,frame_count=430942215,last_target_update_samples=5100000)
    gate=dict(tag='fresh3-224M',target=228629023,experiment=helper.EXPERIMENT,checkpoint='/synthetic/candidate.pt',
        trigger_snapshot=dict(learner_frame_count=228629050,frame_count=459999999,
                              training_steps=1599,optimized_samples=6549504,client_count=192))
    return saved,reference,latest,gate

class FutureCPU(unittest.TestCase):
    def test_inert_import_default_help(self):
        before=set(sys.modules)
        with patch.object(Path,'read_bytes',side_effect=AssertionError('runtime read')), \
             patch.object(Path,'read_text',side_effect=AssertionError('runtime read')):
            loaded=module('inert_future_cpu',HERE/'verify_future_checkpoint_cpu.py')
            with patch.object(sys,'argv',['fixture']),redirect_stdout(io.StringIO()): loaded.main()
            with patch.object(sys,'argv',['fixture','--help']),redirect_stdout(io.StringIO()),self.assertRaises(SystemExit): loaded.main()
        self.assertFalse(any(n=='torch' or n.startswith('torch.') for n in set(sys.modules)-before))

    def test_explicit_pins_checked_before_any_evidence_or_Torch(self):
        args=SimpleNamespace(role='224M',checkpoint_sha256='a'*64,gate_sha256='b'*64,
            precommit_sha256=helper.PRECOMMIT_SHA,output='/synthetic/output.json',prior_224_lineage=None,
            prior_224_lineage_sha256=None)
        for key in ('checkpoint_sha256','gate_sha256','precommit_sha256'):
            bad=copy.copy(args);setattr(bad,key,'FUTURE_ROOT_PIN')
            with patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''),patch.object(Path,'read_bytes',side_effect=AssertionError('read')), \
                 self.subTest(key=key),self.assertRaises(ValueError): helper.execute(bad)

    def test_complete443_geometry_scaler_and_actual_clock_proof(self):
        saved,ref,latest,gate=fixture()
        meta,facts=helper.validate_saved(saved,ref,latest,'224M',gate,cpu,TORCH)
        self.assertEqual(facts['finite_tensor_count'],443)
        self.assertEqual(meta['training_steps'],1600)
        self.assertNotEqual(meta['training_steps'],gate['trigger_snapshot']['training_steps'])
        self.assertEqual(facts['optimizer_parameter_steps'],[1590.])

    def test_reject_real_malformed_owner_moment_inventory_scaler_and_controls(self):
        for mutate in (
            lambda s:s['optimizer_state_dict']['state'].__setitem__(True,s['optimizer_state_dict']['state'].pop(1)),
            lambda s:s['optimizer_state_dict']['state'][0].update(exp_avg=Tensor((4,)),exp_avg_sq=Tensor((4,))),
            lambda s:s['online_state_dict']['p0'].__setattr__('finite',False),
            lambda s:s['target_state_dict'].pop('p0'),
            lambda s:s['grad_scaler_state_dict'].pop('scale'),
            lambda s:s['grad_scaler_state_dict'].update(_growth_tracker=True),
            lambda s:s.update(lr_anchor_step=False),
            lambda s:s.update(engine_version=True),
            lambda s:s.update(frame_count=2),
            lambda s:s.update(last_target_update_samples=1)):
            saved,ref,latest,gate=fixture();mutate(saved)
            with self.subTest(mutation=mutate),self.assertRaises((ValueError,KeyError)):helper.validate_saved(saved,ref,latest,'224M',gate,cpu,TORCH)

    def test_gate_role_target_checkpoint_and_saved_clocks_are_independent(self):
        saved,ref,latest,gate=fixture()
        for bad in (dict(gate,target=True),dict(gate,target=260629023),dict(gate,tag='fresh3-256M'),
                    dict(gate,checkpoint='/wrong.pt'),dict(gate,experiment='wrong')):
            with self.subTest(gate=bad),self.assertRaises(ValueError):helper.validate_gate(bad,'224M','/synthetic/candidate.pt')
        bad=copy.deepcopy(gate);bad['trigger_snapshot']['optimized_samples']=saved['optimized_samples']+1
        with self.assertRaises(ValueError):helper.validate_saved(saved,ref,latest,'224M',bad,cpu,TORCH)

    def test_logical_sample_Adam_and_replay_exposure_not_equated(self):
        saved,ref,_,_=fixture();delta=helper.exposure(ref['saved_metadata'],saved,[997.],[1590.])
        self.assertEqual((delta['logical_updates_delta'],delta['Adam_uniform_step_delta'],delta['logical_minus_uniform_Adam_delta']),(600,593.,7.))
        self.assertNotIn('AMP_skips',delta)
        for bad,steps in ((dict(saved,optimized_samples=saved['optimized_samples']+1),[1590.]),
                          (dict(saved,learner_frame_count=1),[1590.]),(saved,[996.]),(saved,[1600.5])):
            with self.subTest(bad=bad,steps=steps),self.assertRaises(ValueError):helper.exposure(ref['saved_metadata'],bad,[997.],steps)

    def test_bound_same_bytes_and_recheck_change(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'evidence.json';p.write_bytes(b'{"v":1}\n');retained={}
            raw=helper.read_pinned(dict(path=str(p),sha256=helper.digest(p.read_bytes())),retained)
            self.assertEqual(json.loads(raw),{'v':1});helper.recheck(retained)
            p.write_bytes(b'{"v":2}\n')
            with self.assertRaises(ValueError):helper.recheck(retained)

    def test_exclusive_readonly_atomic_publication_and_failed_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lineage.json';called=[]
            helper.publish(p,{'PASS':True},lambda:called.append(True))
            self.assertEqual(called,[True]);self.assertEqual(p.stat().st_mode&0o777,0o444)
            self.assertEqual(p.stat().st_nlink,1);old=p.read_bytes()
            with self.assertRaises(FileExistsError):helper.publish(p,{'PASS':False},lambda:None)
            self.assertEqual(p.read_bytes(),old)
            def changed():raise ValueError('changed history')
            with self.assertRaises(ValueError):helper.publish(Path(d)/'bad.json',{},changed)
            self.assertEqual(list(Path(d).iterdir()),[p])

    def test_full_fake_one_byte_read_one_CPU_load_and_history_before_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);here=root/'proposal';here.mkdir();candidate=root/'candidate.pt';candidate.write_bytes(b'synthetic checkpoint')
            saved,reference,latest,gate=fixture();gate['checkpoint']=str(candidate)
            env=dict(DQN_BATCH_SIZE='4096',DQN_COMPILE_MODE='default',DQN_LEARNING_EXPOSURE_COUNTERS='1',DQN_N_STEP='3',
                DQN_MAX_SAMPLES_PER_FRAME='8',DQN_C51_TARGET_SMOOTHING='0',DQN_STREAM_BANK_OUTPUT='1',DQN_EXACT_INFERENCE_GRAPHS='1',
                DQN_NATIVE_BATCH_UPDATE='1',DQN_INFERENCE_BATCH_WAIT_MS='1',DQN_REPLAY_PREFETCH='1',DQN_DIRECT_REPLAY_FILL='1',ROBOTRON_RUN_DIR=str(root))
            controls=dict(experiment=helper.EXPERIMENT,lr_scale=.5,epsilon_ramp=dict(start=.1,end=.1))
            first=dict(latest,training_steps=1200,total_training_steps=1200,optimized_samples=4915200,learner_frame_count=213664792,frame_count=427175631,last_target_update_samples=4800000)
            def anchor(meta,step):return dict(saved_metadata=meta,optimizer_parameter_steps=[step],cpu_only=True,cuda_initialized=False,
                optimizer_tensors_finite_CPU=True,optimizer_state_count=81,architecture_unchanged=True)
            actor_rows=[dict(pid=1000+i,start_ticks=99,slot=i) for i in range(192)]
            documents=dict(reference192M=dict(candidate=reference,PASS=True,proposal_only=False,root_verification=dict(status='PASS',CUDA_initialized=False),branch_provenance={}),
                protected192_metadata=dict(sha256=reference['sha256'],saved_checkpoint_metadata=reference['saved_metadata']),
                promotion192=dict(root_promoted=True,new_incumbent=dict(sha256=reference['sha256'])),run24_anchor=anchor(first,1196.),run25_anchor=anchor(latest,1246.),
                runtime=dict(environment=env),environment=env,controls=controls,
                actors=dict(trainer_pid=77,trainer_start_ticks=88,actors=actor_rows,supervisor_identities=[dict(pid=5000,start_ticks=99)]))
            source={};private={}
            for name,mapping,n in [('s',source,20),('p',private,12)]:
                for i in range(n):
                    p=root/(name+str(i)+'.py');p.write_bytes(b'# tiny source\n');mapping[p.name]=helper.digest(p.read_bytes())
            process_history=[]
            for index,name,wait in [(0,'run23_observation','1'),(1,'run24_observation','0.5'),(2,'run25_observation','1')]:
                e=dict(env,DQN_INFERENCE_BATCH_WAIT_MS=wait)
                documents[name]=dict(PASS=True,pid=75+index,start_ticks=86+index,environment=e,source_hashes=source,private12_hashes=private)
                process_history.append(dict(pid=75+index,start_ticks=86+index,collector_wait_ms=wait))
            paths={};evidence={}
            for name,doc in documents.items():
                p=root/(name+'.json');p.write_text(json.dumps(doc));paths[name]=p;evidence[name]=dict(path=str(p),sha256=helper.digest(p.read_bytes()))
            chronology=[dict(path=str(paths[k]),sha256=evidence[k]['sha256'],saved_metadata=documents[k]['saved_metadata']) for k in ('run24_anchor','run25_anchor')]
            p=root/'assessment_plan.json';p.write_text(json.dumps(dict(collector_resume_chronology=chronology)));evidence['assessment_plan']=dict(path=str(p),sha256=helper.digest(p.read_bytes()))
            for name in ('common','cpu_checks'):
                p=root/(name+'.py');p.write_bytes(b'# fake imported module\n');evidence[name]=dict(path=str(p),sha256=helper.digest(p.read_bytes()))
            gatepath=root/'gate.json';gatepath.write_text(json.dumps(gate))
            next_candidate=root/'candidate256.pt';next_candidate.write_bytes(b'synthetic checkpoint256')
            next_gate=dict(gate,tag='fresh3-256M',target=260629023,checkpoint=str(next_candidate),trigger_snapshot=dict(
                learner_frame_count=260629050,frame_count=519999999,training_steps=1999,optimized_samples=8187904,client_count=192))
            next_gatepath=root/'gate256.json';next_gatepath.write_text(json.dumps(next_gate))
            contract=dict(evidence=evidence,expected_main=dict(pid=77,start_ticks=88),controls=controls,
                collector_resume_chronology=chronology,completed_process_chronology=process_history,
                roles={'224M':dict(target=228629023,checkpoint=str(candidate),gate=str(gatepath)),
                       '256M':dict(target=260629023,checkpoint=str(next_candidate),gate=str(next_gatepath))})
            precommit=here/'future-cpu-precommit.json';precommit.write_text(json.dumps(contract));pin=helper.digest(precommit.read_bytes())
            args=SimpleNamespace(role='224M',checkpoint_sha256=None,gate_sha256=helper.digest(gatepath.read_bytes()),
                precommit_sha256=pin,output=str(root/'fresh3-224M-checkpoint-lineage.json'),prior_224_lineage=None,prior_224_lineage_sha256=None)
            reads=[];loads=[];original_read=Path.read_bytes
            def read(path):
                if str(path)=='/proc/77/cmdline':return b'python\0-Xgil=0\0Scripts/run_dqn.py\0'
                if path in (candidate,next_candidate):reads.append(path)
                return original_read(path)
            def load(stream,**kwargs):
                self.assertIsInstance(stream,io.BytesIO);self.assertIn(stream.read(),(b'synthetic checkpoint',b'synthetic checkpoint256'));loads.append(kwargs);return saved
            torch=SimpleNamespace(**vars(TORCH),load=load,set_num_threads=lambda n:None,set_num_interop_threads=lambda n:None,
                get_num_threads=lambda:2,cuda=SimpleNamespace(is_initialized=lambda:False),__version__='FAKE_NO_TORCH')
            identities={77:dict(pid=77,start_ticks=88),**{r['pid']:{k:r[k] for k in ('pid','start_ticks')} for r in actor_rows},5000:dict(pid=5000,start_ticks=99)}
            with ExitStack() as stack:
                for name,value in [('HERE',here),('RUN',root),('REPO',root),('GAME',root),('PRECOMMIT_SHA',pin)]:stack.enter_context(patch.object(helper,name,value))
                stack.enter_context(patch.object(helper,'load_module',side_effect=lambda name,path:common if name=='future_cpu_common' else cpu))
                stack.enter_context(patch.object(helper,'process_identity',side_effect=lambda pid:identities[pid]))
                stack.enter_context(patch.object(helper,'process_environment',return_value=env))
                stack.enter_context(patch.object(Path,'read_bytes',read));stack.enter_context(patch.dict(sys.modules,torch=torch));stack.enter_context(patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''))
                result=helper.execute(args)
                self.assertTrue(result['PASS']);self.assertEqual(len(reads),1);self.assertEqual(len(loads),1)
                report=json.loads(Path(args.output).read_bytes());self.assertFalse(report['counter_exposure_evidence']['available'])
                self.assertEqual(report['root_verification']['model_CPU_loads'],1)
                saved.update(training_steps=2000,total_training_steps=2000,optimized_samples=8192000,
                    learner_frame_count=260629100,frame_count=520000000,last_target_update_samples=8100000)
                for row in saved['optimizer_state_dict']['state'].values():row['step'].value=1987
                args256=SimpleNamespace(role='256M',checkpoint_sha256=None,gate_sha256=helper.digest(next_gatepath.read_bytes()),
                    precommit_sha256=pin,output=str(root/'fresh3-256M-checkpoint-lineage.json'),
                    prior_224_lineage=args.output,prior_224_lineage_sha256=result['sha256'])
                result256=helper.execute(args256)
                self.assertEqual(reads,[candidate,next_candidate]);self.assertEqual(len(loads),2)
                self.assertEqual(json.loads(Path(result256['path']).read_bytes())['actual_recorded_batch_exposure']['since224M']['logical_updates_delta'],400)
                paths['run24_anchor'].write_text('{}');args.output=str(root/'retry.json');reads.clear();loads.clear()
                # Output must remain fixed, so use the same fixed path after
                # preserving the prior publication outside this fake run.
                Path(result['path']).rename(root/'retained.json');args.output=result['path']
                with self.assertRaisesRegex(ValueError,'Changed pinned evidence'):helper.execute(args)
                self.assertEqual(reads,[]);self.assertEqual(loads,[])

if __name__=='__main__':unittest.main()
