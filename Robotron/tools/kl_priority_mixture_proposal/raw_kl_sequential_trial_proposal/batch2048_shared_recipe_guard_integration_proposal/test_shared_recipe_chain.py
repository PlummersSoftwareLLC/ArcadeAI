"""Authored, unexecuted stdlib guards. All process/unit/affinity I/O is synthetic.
These tests exercise the actual new Runtime.inspect -> Host.describe ->
LiveHost._inspect -> metrics.Host.bindings, rather than a mirrored recipe formula.
"""
import ast
import copy
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
Q = GAME / 'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
ORIGINAL = Q / 'batch2048_one_trial_execution_release_reviewed2_proposal/run_CE_batch_transition.py'
TRAINER = 'robotron-managed-fixture-trainer.service'
FLEET = 'robotron-managed-fixture-fleet.service'
CG = '/user.slice/fixture/' + TRAINER
FCG = '/user.slice/fixture/' + FLEET
OWNER = dict(pid=12345, starttime_ticks=456, invocation_id='a'*32, unit=TRAINER, cgroup=CG)
WORKER = dict(trainer=OWNER, thread=dict(tid=12346, starttime_ticks=457))
ACTORS = [dict(pid=13000+i, slot=i, starttime_ticks=500+i) for i in range(2)]
LOG = '/fixture/trainer.log'
MASK = list(range(72))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def record_pin():
    return dict(path='/fixture/new-phase.json', sha256='b'*64, bytes=123,
        identity=dict(device=1, inode=2, bytes=123, mtime_ns=1, ctime_ns=1,
                      mode='0o444', uid=os.getuid(), nlink=1))


@contextmanager
def real_chain(mode='activate_batch2048'):
    """Only the I/O endpoints and unrelated constructor proofs are replaced."""
    adapter = load(HERE/'run_CE_batch_transition.py', '_fixture_recipe_adapter')
    live = load(HERE/'helpers/parallel_state_fill_trial.py', '_fixture_recipe_live')
    metrics = live.metrics
    owned = load(Q/'batch2048_phase_lifecycle_integration_reviewed3_proposal/owned_lifecycle.py', '_fixture_owned_binding')
    boundary = adapter.boundary()
    spec = boundary.direction(mode, boundary.PROFILE_BINDING)
    env = dict(metrics.ENV_RECIPE, DQN_BATCH_SIZE=str(spec['before_batch_size']),
        DQN_PER_PRIORITY_METRIC='ce', ROBOTRON_RUN_DIR='/fixture/run',
        ROBOTRON_DQN_MODEL_DIR=str(GAME/'models_dqn'), CUDA_VISIBLE_DEVICES='1')
    state = dict(env=env, worker=copy.deepcopy(WORKER), actor_mask=MASK[:], inference_mask=MASK[:], cgroup=CG)

    class FixturePath(type(Path())):
        def read_bytes(self):
            if str(self) == '/proc/12345/environ':
                return ('\0'.join(k+'='+v for k,v in state['env'].items())+'\0').encode()
            raise AssertionError('Unexpected fixture read: '+str(self))
        def read_text(self, *args, **kwargs):
            if str(self) == '/proc/12345/cgroup': return '0::'+state['cgroup']+'\n'
            if str(self) == '/proc/14000/stat': return 'fixture-stat'
            raise AssertionError('Unexpected fixture read: '+str(self))
        def resolve(self, strict=False):
            if str(self) in ('/proc/12345/fd/1', '/proc/12345/fd/2'): return FixturePath(LOG)
            return FixturePath(super().resolve(strict=strict))
        def stat(self, *args, **kwargs):
            if str(self) == LOG: return types.SimpleNamespace(st_mode=stat.S_IFREG|0o644, st_dev=1, st_ino=2)
            return super().stat(*args, **kwargs)

    trainer = dict(MainPID='12345', ActiveState='active', KillSignal='2', SendSIGKILL='no',
        TimeoutStopUSec='4min', ControlGroup=CG, FragmentPath='/fixture/trainer.service', DropInPaths='', Restart='no')
    fleet = dict(MainPID='14000', ActiveState='active', Wants=TRAINER, Requires='', BindsTo='', PartOf='',
        FragmentPath='/fixture/fleet.service', DropInPaths='')
    base = types.SimpleNamespace(Runtime=object, fingerprint=lambda *a: None, read_json=lambda *a: None,
        publish=lambda *a: None, MAX_SOURCE=1<<20, binding_matches=owned.binding_matches,
        SettingsLifecycle=lambda *a: types.SimpleNamespace(check=lambda: None),
        load_module=lambda path,name: live if path.endswith('parallel_state_fill_trial.py') else types.SimpleNamespace())
    pins = {key:dict(path=str(path)) for key,path in dict(live_host=HERE/'helpers/parallel_state_fill_trial.py',
        metrics=HERE/'helpers/inference_worker_affinity.py',identity=GAME/'tools/cpu_affinity_pilot.py',
        protection=GAME/'tools/protect_quality_winner.py',bank_state=Path('/fixture/bank.py')).items()}
    job = dict(batch_boundary=spec,timeouts=dict(ready_s=600),helper_pins=pins,
        trainer_unit=TRAINER,fleet_unit=FLEET,original_dropin=dict(path='/fixture/dropin',content_base64=None),
        current_completed_request=None,settings_lifecycle={},model_dir=str(GAME/'models_dqn'))
    with ExitStack() as stack:
        stack.enter_context(patch.object(adapter,'phase_early_module',return_value=types.SimpleNamespace(ReadonlyMetadataBase=lambda b:b)))
        stack.enter_context(patch.object(adapter,'insurance_context',return_value=dict(owner=OWNER,clock_floor=dict.fromkeys(adapter.CLOCKS,1))))
        stack.enter_context(patch.object(adapter,'validate_ending',return_value=None))
        stack.enter_context(patch.object(live.LiveHost,'_dropin_bytes',return_value=None))
        runtime = adapter.runtime_class(base)(job,Path('/fixture/output'))
        runtime.static=lambda:None
        runtime.exclusive=lambda:None
        stack.enter_context(patch.object(live,'Path',FixturePath))
        stack.enter_context(patch.object(metrics,'Path',FixturePath))
        stack.enter_context(patch.object(live.LiveHost,'no_sidecars',return_value=None))
        stack.enter_context(patch.object(live.LiveHost,'unit',side_effect=lambda name:copy.deepcopy(trainer if name==TRAINER else fleet)))
        stack.enter_context(patch.object(live.LiveHost,'actor_stopped',return_value=False))
        stack.enter_context(patch.object(metrics.Host,'no_sidecars',return_value=None))
        stack.enter_context(patch.object(metrics.Host,'thread_identity',side_effect=lambda:copy.deepcopy(state['worker'])))
        stack.enter_context(patch.object(metrics.Host,'mask',side_effect=lambda binding:state['inference_mask']))
        stack.enter_context(patch.object(metrics,'discover_fleet_actors',side_effect=lambda cg:(copy.deepcopy(ACTORS),set())))
        stack.enter_context(patch.object(metrics,'file_digest',return_value='c'*64))
        stack.enter_context(patch.object(metrics.identity,'stat_fields',return_value=dict(starttime_ticks=700)))
        stack.enter_context(patch.object(metrics.subprocess,'run',return_value=types.SimpleNamespace(stdout=FCG+'\n')))
        stack.enter_context(patch.object(adapter.os,'sched_getaffinity',side_effect=lambda pid:state['actor_mask']))
        runtime.job['before']=runtime.host.describe()
        runtime.job['actor_masks']={str(a['pid']):MASK[:] for a in ACTORS}
        runtime.job['worker_mask']=MASK[:]
        runtime.expected_sources=lambda phase:runtime.job['before']['bindings']['source_hashes']
        runtime.record_pin=record_pin()
        yield adapter,runtime,live,metrics,state


class SharedRecipeContracts(unittest.TestCase):
    def test_actual_activation_chain_before4096_after2048(self):
        with real_chain() as (adapter,runtime,live,metrics,state):
            original_recipe=copy.deepcopy(metrics.ENV_RECIPE)
            self.assertEqual(runtime.inspect('before')['environment']['DQN_BATCH_SIZE'],'4096')
            runtime.phase='after'
            state['env']=adapter.selected_environment(runtime.job['before']['environment'],runtime.job['batch_boundary'],runtime.record_pin)
            self.assertEqual(runtime.inspect('after')['environment']['DQN_BATCH_SIZE'],'2048')
            self.assertEqual(metrics.ENV_RECIPE,original_recipe)
            self.assertEqual(metrics.GAME,GAME)

    def test_actual_return_chain_before2048_after4096(self):
        with real_chain('return_batch4096') as (adapter,runtime,live,metrics,state):
            self.assertEqual(runtime.inspect('before')['environment']['DQN_BATCH_SIZE'],'2048')
            first=runtime.host.metric_host
            runtime.phase='after'
            state['env']=adapter.selected_environment(runtime.job['before']['environment'],runtime.job['batch_boundary'],runtime.record_pin)
            self.assertEqual(runtime.inspect('after')['environment']['DQN_BATCH_SIZE'],'4096')
            # _inspect created another real metrics.Host even when describe preserves its log reader.
            self.assertEqual(runtime.host.metric_host,first)

    def test_default4096_and_exact_integer_validation(self):
        with real_chain('return_batch4096') as (adapter,runtime,live,metrics,state):
            host=metrics.Host(12345,FLEET)
            with self.assertRaisesRegex(metrics.GuardFailure,'Trainer environment'):host.bindings()
            for value in (True,False,2048.0,4096.0,'2048',1024,None):
                with self.subTest(value=value),self.assertRaisesRegex(metrics.GuardFailure,'exact supported'):host.bindings(expected_batch_size=value)
            self.assertEqual(host.bindings(expected_batch_size=2048)['worker'],WORKER)

    def test_other_recipe_and_full_selected_environment_stay_strict(self):
        with real_chain() as (adapter,runtime,live,metrics,state):
            state['env']['DQN_N_STEP']='1'
            with self.assertRaisesRegex(metrics.GuardFailure,'Trainer environment'):runtime.inspect('before')
            state['env']['DQN_N_STEP']='3';state['env']['DQN_EXTRA_UNCOMMITTED']='1'
            with self.assertRaisesRegex(RuntimeError,'Unexpected selected recipe'):runtime.inspect('before')

    def test_phase_owner_cgroup_and_affinities_stay_strict(self):
        with real_chain() as (adapter,runtime,live,metrics,state):
            runtime.phase='foreign'
            with self.assertRaisesRegex(RuntimeError,'Unknown owned recipe phase'):runtime.inspect('before')
            runtime.phase='before';state['cgroup']='/wrong'
            with self.assertRaisesRegex(metrics.GuardFailure,'outside its service cgroup'):runtime.inspect('before')
            state['cgroup']=CG;runtime.host.adopt_initial(runtime.job['before'])
            state['worker']['trainer']['starttime_ticks']+=1
            with self.assertRaisesRegex(metrics.GuardFailure,'unknown replacement'):runtime.inspect('before')
            state['worker']=copy.deepcopy(WORKER);state['actor_mask']=[0]
            with self.assertRaisesRegex(RuntimeError,'actor mask drift'):runtime.inspect('before')
            state['actor_mask']=MASK[:];state['inference_mask']=[0]
            with self.assertRaisesRegex(RuntimeError,'Inference mask drift'):runtime.inspect('before')

    def test_plain_module_cache_is_not_recipe_or_dependency_authority(self):
        poison=types.SimpleNamespace(__file__='/foreign/cache.py',ENV_RECIPE={'DQN_BATCH_SIZE':'wrong'})
        with patch.dict(sys.modules,dict.fromkeys(('inference_worker_affinity','cpu_affinity_pilot','protect_quality_winner'),poison)):
            live=load(HERE/'helpers/parallel_state_fill_trial.py','_fixture_cache_live')
            self.assertIsNot(live.metrics,poison)
            self.assertIsNot(live.metrics.identity,poison)
            self.assertIsNot(live.protection,poison)
            self.assertEqual(Path(live.metrics.__file__).resolve(),HERE/'helpers/inference_worker_affinity.py')
            self.assertEqual(Path(live.metrics.identity.__file__).resolve(),GAME/'tools/cpu_affinity_pilot.py')
            self.assertEqual(Path(live.protection.__file__).resolve(),GAME/'tools/protect_quality_winner.py')
            self.assertEqual(live.metrics.ENV_RECIPE['DQN_BATCH_SIZE'],'4096')

    def test_local_metrics_unsealed_or_wrong_bytes_refuse_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p=d/'parallel_state_fill_trial.py';m=d/'inference_worker_affinity.py'
            p.write_bytes((HERE/'helpers/parallel_state_fill_trial.py').read_bytes())
            m.write_bytes((HERE/'helpers/inference_worker_affinity.py').read_bytes());m.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError,'owned readonly'):load(p,'_fixture_unsealed_live')
            m.write_bytes(m.read_bytes()+b'\n# drift\n');m.chmod(0o444)
            with self.assertRaisesRegex(RuntimeError,'identity or digest differs'):load(p,'_fixture_drifted_live')

    def test_existing_inspect_and_other_lifecycle_bodies_preserved(self):
        old=ORIGINAL.read_text();new=(HERE/'run_CE_batch_transition.py').read_text()
        def functions(text):
            tree=ast.parse(text)
            return {
                (n.name,n.col_offset):ast.get_source_segment(text,n)
                for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        a,b=functions(old),functions(new)
        for key in a:
            if key[0] not in ('runtime_class','__init__','main'):
                self.assertEqual(a[key],b[key],key)
        self.assertEqual(a[('inspect',8)],b[('inspect',8)])
        self.assertEqual((HERE/'helpers/test_fleet_actor_discovery.py').read_bytes(),(GAME/'tools/test_fleet_actor_discovery.py').read_bytes())
        self.assertNotIn('torch',sys.modules)
        self.assertNotIn('numpy',sys.modules)


if __name__=='__main__':unittest.main()
