"""Authored/unexecuted stdlib metadata guards; no models, runtime probes or unit operations."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
OLD = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/phase_snapshot_cpu_verifier_proposal')
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
W=load('_batch2048_wrapper_test',HERE/'verify_phase_snapshot_2048.py')
B=load('_batch2048_private_base_test',HERE/'strict_phase_base_2048.py')
def functions(path):
    source=path.read_text();lines=source.splitlines(keepends=True)
    return {n.name:''.join(lines[n.lineno-1:n.end_lineno]) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}

class Batch2048MetadataGuards(unittest.TestCase):
    def fixture(self, directory):
        owner=dict(pid=12345,starttime_ticks=67890,unit='robotron-managed-fixture-trainer.service',
            invocation_id='a'*32,cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-managed-fixture-trainer.service')
        def pin(name):return dict(path=str(Path(directory)/name),sha256='b'*64,bytes=1,identity={})
        profile_pin=pin('profile');profile_pin.update(path=str(W.PROFILE_PATH),sha256=W.PROFILE_SHA256,bytes=W.PROFILE_BYTES)
        observation_pin=pin('observation'); env_pin=pin('environment');unit_pin=pin('unit');csv_pin=pin('csv')
        Path(csv_pin['path']).write_text('batch_size,loss\n2048,1.25\n')
        source=dict(path='/fixture/checkpoint.pt',sha256='c'*64,bytes=275000000)
        job=dict(experiment='fixture_only',source=source,batch2048_context=dict(profile=profile_pin,role='candidate',producer_observation=observation_pin),
            phase_snapshot=dict(owner=copy.deepcopy(owner),purpose='candidate',observed_clients=192,acquisition=dict(sha256='d'*64),
                expected_phase=dict(metric='ce'),boot_verification=dict(producer_batch_size=4096)))
        profile=json.loads(W.PROFILE_PATH.read_text())
        shown=dict(MainPID=str(owner['pid']),ExecMainPID=str(owner['pid']),InvocationID=owner['invocation_id'],
            NRestarts='0',Restart='no',ControlGroup=owner['cgroup'],Environment='DQN_BATCH_SIZE=2048 DQN_PER_PRIORITY_METRIC=ce')
        unit=dict(argv=['systemctl','--user','show',owner['unit'],'--all'],returncode=0,
            stdout='\n'.join(k+'='+v for k,v in shown.items())+'\n',stderr='')
        observation=dict(schema='robotron-root-batch2048-producer-observation-v1',experiment='fixture_only',
            profile_sha256=W.PROFILE_SHA256,owner=copy.deepcopy(owner),source_checkpoint=copy.deepcopy(source),acquisition_sha256='d'*64,
            environment=env_pin,trainer_unit=unit_pin,csv=csv_pin,csv_scope='producer2048',csv_origin=None,producer_started_unix_s=200.,observed_unix_s=300.)
        values={profile_pin['path']:profile,observation_pin['path']:observation,env_pin['path']:{'DQN_BATCH_SIZE':'2048','DQN_PER_PRIORITY_METRIC':'ce'},unit_pin['path']:unit,csv_pin['path']:csv_pin}
        def immutable(pin,base,evidence,label,as_json=False):return copy.deepcopy(values[pin['path']])
        return job,values,observation,shown,immutable
    def check(self,job,immutable):
        evidence={}
        with patch.object(W,'immutable',side_effect=immutable):W.check_batch2048_context(job,B,evidence)
        return evidence
    def test_defaults_never_load_context_or_framework(self):
        with patch.object(W,'load_base',side_effect=AssertionError('base import')),patch.object(Path,'read_bytes',side_effect=AssertionError('input read')),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(W.main([]),0);self.assertEqual(B.main([]),0)
    def test_private_base_execute_and_abbreviation_refuse_before_input_reads(self):
        for flag in ('--execute','--exec'):
            with self.subTest(flag=flag),patch.object(B,'read_job',side_effect=AssertionError('job read')):
                with self.assertRaisesRegex(RuntimeError,'profile-bound'):B.main([flag])
    def test_numerical_phase_and_acquisition_function_bodies_remain_exact(self):
        old=functions(OLD/'strict_phase_base.py');new=functions(HERE/'strict_phase_base_2048.py')
        for name in ('finite_tree','validate_checkpoint','check_context','check_root_copy','check_mode','exact_absence'):
            self.assertEqual(new[name],old[name],name)
        old=functions(OLD/'verify_phase_snapshot.py');new=functions(HERE/'verify_phase_snapshot_2048.py')
        for name in ('check_acquisition','verify_phase','historical_archive','immutable'):
            self.assertEqual(new[name],old[name],name)
    def test_explicit2048_does_not_relabel_4096_boot_or_baseline512(self):
        with tempfile.TemporaryDirectory() as directory:
            job,_,_,_,immutable=self.fixture(directory);evidence=self.check(job,immutable)
            self.assertEqual(evidence['actual_producer_batch_size'],2048)
            self.assertEqual(B.HELD_RECIPE_CONTEXT['batch_size'],2048);self.assertEqual(B.HELD_RECIPE_CONTEXT['baseline_batch_size'],512)
            self.assertEqual(job['phase_snapshot']['boot_verification']['producer_batch_size'],4096)
    def test_wrong_profile_pin_or_recipe_refused(self):
        for wrong in ('path','sha256','recipe'):
            with self.subTest(wrong=wrong),tempfile.TemporaryDirectory() as directory:
                job,values,_,_,immutable=self.fixture(directory)
                if wrong=='recipe':values[str(W.PROFILE_PATH)]['held_recipe_context']['batch_size']=4096
                else:job['batch2048_context']['profile'][wrong]='wrong'
                with self.assertRaises(RuntimeError):self.check(job,immutable)
    def test_wrong_owner_acquisition_checkpoint_metric_and_profile_join_refused(self):
        for wrong in ('owner','acquisition','checkpoint','metric','profile'):
            with self.subTest(wrong=wrong),tempfile.TemporaryDirectory() as directory:
                job,_,observation,_,immutable=self.fixture(directory)
                if wrong=='owner':observation['owner']['pid']+=1
                elif wrong=='acquisition':observation['acquisition_sha256']='e'*64
                elif wrong=='checkpoint':observation['source_checkpoint']['sha256']='e'*64
                elif wrong=='metric':job['phase_snapshot']['expected_phase']['metric']='kl'
                else:observation['profile_sha256']='e'*64
                with self.assertRaises(RuntimeError):self.check(job,immutable)
    def test_actual_environment_and_unit_recipe_owner_restart_required(self):
        for wrong in ('environment','unitbatch','unitowner','restart','command'):
            with self.subTest(wrong=wrong),tempfile.TemporaryDirectory() as directory:
                job,values,observation,_,immutable=self.fixture(directory)
                if wrong=='environment':values[observation['environment']['path']]['DQN_BATCH_SIZE']='4096'
                else:
                    unit=values[observation['trainer_unit']['path']]
                    if wrong=='unitbatch':unit['stdout']=unit['stdout'].replace('DQN_BATCH_SIZE=2048','DQN_BATCH_SIZE=4096')
                    elif wrong=='unitowner':unit['stdout']=unit['stdout'].replace('MainPID=12345','MainPID=777')
                    elif wrong=='restart':unit['stdout']=unit['stdout'].replace('NRestarts=0','NRestarts=1')
                    else:unit['argv'].pop()
                with self.assertRaises(RuntimeError):self.check(job,immutable)
    def test_explicit_startup_baseline_is_historical_and_other_roles_never_use_it(self):
        for role,clients,purpose,valid in [('treatment_startup',0,'startup',True),('treatment_startup',192,'startup',False),
                ('candidate',0,'candidate',False),('early_insurance',192,'candidate',False),('newest_stopped',0,'newest_stopped',False)]:
            with self.subTest(role=role,clients=clients),tempfile.TemporaryDirectory() as directory:
                job,values,observation,_,immutable=self.fixture(directory)
                job['batch2048_context']['role']=role;job['phase_snapshot'].update(purpose=purpose,observed_clients=clients)
                observation['csv_scope']='pretransition_baseline4096';observation['csv']['identity']['mtime_ns']=50_000_000_000
                Path(observation['csv']['path']).write_text('batch_size,loss\n4096,1.25\n')
                origin_pin=dict(path=str(Path(directory)/'origin'),sha256='e'*64,bytes=1,identity={});observation['csv_origin']=origin_pin
                oldowner=copy.deepcopy(observation['owner']);oldowner['pid']-=1
                values[origin_pin['path']]=dict(schema='robotron-root-pretransition-batch2048-CSV-v1',scope='pretransition_baseline4096',
                    profile_sha256=W.PROFILE_SHA256,owner=oldowner,csv=copy.deepcopy(observation['csv']),captured_unix_s=100.,transition_started_unix_s=150.)
                if valid:
                    evidence=self.check(job,immutable);self.assertEqual(evidence['configured_batch_size'],2048)
                    self.assertFalse(evidence['producer_CSV_verified']);self.assertEqual(evidence['observed_CSV_batch_size'],4096)
                    self.assertIsNone(evidence['actual_producer_batch_size'])
                    values[origin_pin['path']]['transition_started_unix_s']=250.
                    with self.assertRaises(RuntimeError):self.check(job,immutable)
                else:
                    with self.assertRaises(RuntimeError):self.check(job,immutable)
    def test_actual_producer_csv_wrong_missing_or_ambiguous_batch_refused(self):
        for text in ('batch_size,loss\n4096,1\n','loss\n1\n','batch_size\n2048\n2048\n'):
            with self.subTest(text=text),tempfile.TemporaryDirectory() as directory:
                job,_,observation,_,immutable=self.fixture(directory);Path(observation['csv']['path']).write_text(text)
                with self.assertRaises(RuntimeError):self.check(job,immutable)

if __name__=='__main__':unittest.main()
