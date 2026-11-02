"""Authored/unexecuted stdlib guards for the narrow actual-proof release boundary."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


proof=module('_CE2048_release_guards',HERE/'execution_readiness.py')


class Fixture:
    """Synthetic metadata only; every model/checkpoint remains opaque/absent."""
    def __init__(self):
        self.values={};self.text={};self.calls=[]
        def save(name,value):
            pin=dict(path='/synthetic/'+name,sha256=hashlib.sha256(name.encode()).hexdigest(),bytes=len(name),identity={'synthetic':True})
            self.values[pin['path']]=value
            return pin
        self.save=save
        self.owner=dict(pid=9,starttime_ticks=123,invocation_id='a'*32,unit='robotron-private.service',output_directory='/synthetic/numeric')
        for key in ('numeric_manifest','numeric_lock','observed_numeric_owner','profile'):
            self.values[proof.FIXED[key]['path']]={}
        self.values[proof.FIXED['observed_numeric_owner']['path']]=self.owner
        self.values[proof.FIXED['numeric_lock']['path']]=dict(schema=proof.NUMERIC_SCHEMA,batch_rows=2048,stage_b=dict(
            priority_metric='ce',samples_per_attempt=2048,attempts=18,roles=list(proof.ROLES)))
        launch=dict(schema=proof.NUMERIC_SCHEMA,source_lock_sha256=proof.FIXED['numeric_lock']['sha256'],
            output=self.owner['output_directory'],parent={'pid':9,'start_ticks':'123'},parent_sha256='1327fb04709e211faaf5b26587ba7c83389b8f0542105abf18d042d33c877eb4',
            worker_sha256='d83aa9b778925d13520c762cfe5807b0af177183aa0950a4c07b7e4ea2878b8f')
        result=dict(schema=proof.NUMERIC_SCHEMA,status='OBSERVATIONS_COMPLETE',readiness_pass=True,qualification_pass=False,
            owned_cleanup_complete=True,actual_attempts=18,batch_rows=2048,priority_metric='ce',applied_outcomes=18,
            source_lock_sha256=proof.FIXED['numeric_lock']['sha256'],variants=[])
        for role in proof.ROLES:
            result['variants'].append(dict(variant=role,status='OBSERVATIONS_COMPLETE',readiness_pass=True,
                constructor_verified=True,phase_load_verified=True,qualification_pass=False,
                actual_attempts=18 if role=='ce18' else 0,applied_outcomes=18 if role=='ce18' else 0))
        self.numeric=dict(preparation_manifest=proof.FIXED['numeric_manifest'],source_lock=proof.FIXED['numeric_lock'],
            observed_owner=proof.FIXED['observed_numeric_owner'],launch_manifest=save('launch-copy.json',launch),result=save('result-copy.json',result))
        terminal=dict(original_owner=self.owner,ExecMainStatus=0,
            ExecMainCode=1,Result='success',NRestarts=0,unit_not_released_yet=True,
            children=[dict(variant=role,actual_returncode=0,token_released=True) for role in proof.ROLES],pins={})
        for name,key in [('result','result.json'),('launch_manifest','launch-manifest.json')]:
            terminal['pins']['/synthetic/numeric/'+key]=dict(path='/synthetic/numeric/'+key,sha256=self.numeric[name]['sha256'],bytes=self.numeric[name]['bytes'])
        terminal['whole_result']=self.numeric['result']
        self.numeric['original_terminal_archive']=dict(proof.FIXED['original_terminal_archive'],identity={'synthetic':True})
        self.values[self.numeric['original_terminal_archive']['path']]=terminal
        cleanup=dict(status='PASS_ORIGINAL_CE2048_PRIVATE_READINESS_ARCHIVED_OWNED_CLEANUP_COMPLETE',
            original_terminal_archive=self.numeric['original_terminal_archive'],original_owner=self.owner,
            original_parent_exit=0,original_three_child_exits=[0,0,0],whole_result=self.numeric['result'],
            source_lock_sha256=proof.FIXED['numeric_lock']['sha256'],qualification_pass=False,live_batch2048_activated=False,
            owned_release=[dict(unit='robotron-private.timer',actual_stop_returncode=0,final_load_state='not-found'),
                dict(unit='robotron-private.service',actual_stop_returncode=0,final_load_state='not-found')])
        for key in ('original_terminal_archived_before_release','owned_cleanup_complete','readiness_pass','main192_and_resources_healthy'):
            cleanup[key]=True
        self.numeric['owned_cleanup']=dict(proof.FIXED['owned_cleanup'],identity={'synthetic':True})
        self.values[self.numeric['owned_cleanup']['path']]=cleanup
        guards={}
        for role,fixed in proof.GUARDS.items():
            selected=['/usr/bin/python3.12','-I','-B',fixed['script']['path'],fixed['class_name'],'-v']
            self.values[fixed['future_argv']['path']]={'guard_argv':selected}
            self.values[fixed['manifest']['path']]={'files':[fixed['script']]}
            stdout=save(role+'-stdout.txt',None);stderr=save(role+'-stderr.txt',None)
            self.text[stdout['path']]=b'';self.text[stderr['path']]=('Ran %d tests in 0.01s\n\nOK\n'%fixed['methods']).encode()
            guards[role]=fixed['original_execution']
            self.values[guards[role]['path']]=dict(status='PASS',exit_code=0,guard_count=fixed['methods'],source_manifest=fixed['manifest'],
                argv=selected,started_unix_s=1,finished_unix_s=2,limits={'CUDA_VISIBLE_DEVICES':''},original_stdout=stdout,original_stderr=stderr)
        self.value=dict(schema=proof.SCHEMA,profile=proof.FIXED['profile'],numeric=self.numeric,guards=guards)
        self.prereq=save('execution-prerequisites.json',self.value)
    def read(self,pin):self.calls.append(pin['path']);return copy.deepcopy(self.values[pin['path']])
    def data(self,pin,**kwargs):return self.text[pin['path']]


class ExecutionReleaseContracts(unittest.TestCase):
    def test_literal_plan_and_missing_bindings_perform_no_reads_or_runtime(self):
        for name,flag in [('run_one_trial.py','--execute'),('deadline_guard.py','--execute'),('run_CE_batch_transition.py','--launch')]:
            value=module('_release_'+name.replace('.','_'),HERE/name)
            with patch.object(Path,'read_bytes',side_effect=AssertionError('unexpected read')):
                with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(value.main([]),0)
                with self.assertRaisesRegex(RuntimeError,'Explicit'):
                    value.main([flag])

    def test_whole_original_probe_and_exact_inline_guard_contract(self):
        fixture=Fixture()
        self.assertTrue(proof.validate(fixture.value,read=fixture.read,data=fixture.data)['readiness_pass'])
        changes=[('result','schema','robotron-raw-kl-stage-b-private-v1'),('result','readiness_pass',False),
            ('result','applied_outcomes',0),('original_terminal_archive','ExecMainStatus',1),
            ('owned_cleanup','main192_and_resources_healthy',False)]
        for target,key,new in changes:
            with self.subTest(target=target,key=key):
                fixture=Fixture();fixture.values[fixture.numeric[target]['path']][key]=new
                with self.assertRaises(RuntimeError):proof.validate(fixture.value,read=fixture.read,data=fixture.data)
        fixture=Fixture();fixture.values[fixture.numeric['result']['path']]['variants'].pop()
        with self.assertRaises(RuntimeError):proof.validate(fixture.value,read=fixture.read,data=fixture.data)
        fixture=Fixture();fixture.values[fixture.value['guards']['early']['path']]['guard_count']=13
        with self.assertRaises(RuntimeError):proof.validate(fixture.value,read=fixture.read,data=fixture.data)

    def test_final_original_core_and_new_return_intent_are_acyclic(self):
        fixture=Fixture();profile=copy.deepcopy(proof.FIXED['profile'])
        core=fixture.save('final-core.json',dict(status='FINAL_PRECOMMITTED_ROOT_AUTHORIZED',activation_authorized=True,
            mode='activate_batch2048',batch_profile=profile,execution_prerequisites=fixture.prereq))
        helper=dict(path=str(HERE/'execution_readiness.py'),sha256='f'*64,bytes=1,identity={'synthetic':True})
        fixture.text[helper['path']]=b'synthetic metadata-code sentinel'
        job=dict(mode='activate_batch2048',trial_core=core,batch_profile=profile,execution_prerequisites=fixture.prereq,
            helper_pins={'execution_readiness':helper})
        self.assertEqual(proof.validate_job(job,read=fixture.read,data=fixture.data),fixture.prereq)
        old_core=core;phase={'synthetic_actual_typed_phase':True}
        job.update(mode='return_batch4096',phase_early_insurance_result=phase,
            trial_core=fixture.save('return-core.json',dict(mode='return_batch4096',phase_early_insurance_result=phase,trial_core=old_core,execution_prerequisites=fixture.prereq)))
        self.assertEqual(proof.validate_job(job,read=fixture.read,data=fixture.data),fixture.prereq)
        fixture.values[old_core['path']]['activation_authorized']=False
        with self.assertRaises(RuntimeError):proof.validate_job(job,read=fixture.read,data=fixture.data)

    def test_real_readonly_metadata_reader_brackets_exact_file_and_refuses_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'proof.json';path.write_text('{"finite":true}');path.chmod(0o444)
            value=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size,
                identity=proof.identity(path.stat()))
            self.assertEqual(proof.read_json(value),{'finite':True})
            self.assertEqual(proof.read_json(proof.triple(value)),{'finite':True})
            path.chmod(0o644)
            with self.assertRaises(RuntimeError):proof.read_json(value)
            model=Path(directory)/'opaque.pt';model.write_bytes(b'not a model fixture');model.chmod(0o444)
            value.update(path=str(model),identity=proof.identity(model.stat()),bytes=model.stat().st_size)
            with self.assertRaisesRegex(RuntimeError,'nonmetadata'):proof.read_bytes(value)

    def test_release_does_not_change_owner_latch_deadline_or_numeric_bodies(self):
        def funcs(path):
            text=path.read_text();return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body
                if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        old=HERE.parent/'batch2048_one_trial_controller_proposal'
        for file,names in [('deadline_guard.py',('identity','pin','read_pin','publish','clock','process_start','show',
                'classify','ActionLock','request_stop','read_adoption','supervise')),
            ('run_one_trial.py',('durable_event','ReceiptJournal','registered_terminal','owned_cpu','physical_retirement',
                'require_deadline_retirement','inherit_retirement','ending_candidate','return_after_retirement'))]:
            before,after=funcs(old/file),funcs(HERE/file)
            for name in names:self.assertEqual(before[name],after[name])
        before=HERE.parent/'batch2048_phase_lifecycle_integration_reviewed3_proposal'/'owned_lifecycle.py'
        self.assertEqual(before.read_bytes(),(HERE/'owned_lifecycle.py').read_bytes())


if __name__=='__main__':unittest.main()
