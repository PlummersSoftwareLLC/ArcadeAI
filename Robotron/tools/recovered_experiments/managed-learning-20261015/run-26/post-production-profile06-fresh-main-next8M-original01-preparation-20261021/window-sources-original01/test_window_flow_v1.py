"""Window flow contracts: private files and mocked HTTP/unit/process events."""
import ast
import contextlib
import copy
import importlib.util
import io
import itertools
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

HERE=Path(__file__).resolve().parent


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


w=load(HERE/'prospective_window_v1.py','_original_window_flow_target')
x=load(HERE/'launch_window_v1.py','_original_window_launch_target')
files=load(HERE.parent/'sources-original02/owned_candidate_capture_v1.py','_original_window_private_files')


def plan():
    return dict(schema='profile06-production-next8M-fixed-window-plan-v1',authorized=True,output=str(w.OUT),unit=w.UNIT,timer=w.TIMER,
        job_path=str(w.P/'window-job.json'),owner=dict(pid=3295795,starttime_ticks=64995335,invocation_id='160d2b4b1f6e4e2f8839790658a7d01c'),
        reference=dict(sha256='c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'),
        source_package=dict(sha256='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'),
        capture_source=dict(sha256='b967caf7f2be7ac577f472330d38ab5120fc7f79f6742b99cb1082ef9ee54341'),
        design=dict(sha256='bdb43d83e65b81722ed4b5c3369752cb4570290df6c39248d6aba251b6ca5c90'),
        horizons=dict(learner_frames=8_000_000,accepted_dqn_epsilon=8_000_000),cutoff_s=5400,observer_runtime_s=5700,
        capture_tag='profile06_LR25_next8M_01_20261021',dependencies={k:dict(sha256=v) for k,v in w.DEPENDENCY_SHA.items()},
        pause_source=dict(sha256='0756488a19bf653a068aec8c9d3def26605b06498718621e9dc9a8a634f37b3c'),
        capture_CPU=dict(sha256='967890e348a9e83090377e0bf2d78dbf2587ed27ad380e47368508dc43998a9e'),
        capture_kernel=dict(sha256='17ce2fe63a9d4a3bbac5b3c70dd74afaf87a87e3cc1576b6cd57b755d333f8b8'))


def sample(frames=0,accepted=0,applied=0):
    return dict(clocks=dict(training_steps=100+applied,optimized_samples=(100+applied)*4096,
        learner_frame_count=100+frames,frame_count=200+frames),
        optimizer_identity=dict(process_id=3295795,epoch=1),replay_identity=dict(process_id=3295795,epoch=1),
        optimizer=dict(applied=100+applied,amp_skipped=0,unavailable=0),optimizer_since_epoch=dict(applied=100+applied),
        categories=dict(dqn=80+accepted,epsilon=20,expert=0,eval=0,unattributed=0),learner_accepted=100+accepted)


class WindowFlowContracts(unittest.TestCase):
    def test_selected_production_plan_accepts_fixed_identity_and_bounds(self):
        w.validate_plan(plan())

    def test_plan_rejects_old_owner_reference_or_selected_capture(self):
        for field,key,value in [('owner','pid',3170722),('reference','sha256','0'*64),('capture_source','sha256','0'*64)]:
            p=plan();p[field][key]=value
            with self.subTest(field=field),self.assertRaises(ValueError):w.validate_plan(p)

    def test_plan_rejects_changed_horizons_scope_and_deadlines(self):
        for key,value in [('cutoff_s',5401),('observer_runtime_s',5800),('output','/tmp/window'),('capture_tag','another_tag')]:
            p=plan();p[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):w.validate_plan(p)
        p=plan();p['horizons']['accepted_dqn_epsilon']=7_999_999
        with self.assertRaises(ValueError):w.validate_plan(p)

    def test_plan_requires_original_counter_and_completed_capture_validation(self):
        for key in ['counter','controller','guard','linux','raw_API','archive_checker']:
            p=plan();p['dependencies'][key]['sha256']='0'*64
            with self.subTest(key=key),self.assertRaises(ValueError):w.validate_plan(p)
        p=plan();p['capture_kernel']['sha256']='0'*64
        with self.assertRaises(ValueError):w.validate_plan(p)

    def test_original_progress_function_AST_is_unchanged(self):
        old=(w.G/'tools/post_continuity_window.py').read_text();new=Path(w.__file__).read_text()
        find=lambda text:next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='progress')
        self.assertEqual(ast.dump(find(old),include_attributes=False),ast.dump(find(new),include_attributes=False))

    def test_progress_rejects_epoch_regression_and_unavailable_outcomes(self):
        for mutate in [lambda a:a['optimizer_identity'].update(epoch=2),lambda a:a['replay_identity'].update(process_id=1),
            lambda a:a['clocks'].update(training_steps=99),lambda a:a['optimizer'].update(unavailable=1),
            lambda a:a['categories'].update(dqn=1)]:
            baseline=sample();after=sample(100,100,1);mutate(after)
            with self.assertRaises(ValueError):w.progress(after,baseline,baseline)

    def test_existing_capture_tag_blocks_selection_before_training_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);model=root/'game/models_dqn/managed-checkpoints';model.mkdir(parents=True)
            (model/(plan()['capture_tag']+'.pt')).write_bytes(b'previous')
            with patch.object(w,'G',root/'game'),patch.object(w,'P',root/'proposal'),self.assertRaises(ValueError):
                w.require_unused_capture_paths(plan())

    def test_existing_capture_output_blocks_selection_before_training_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'capture-original01').mkdir()
            with patch.object(w,'P',root),patch.object(w,'G',root/'game'),self.assertRaises(ValueError):
                w.require_unused_capture_paths(plan())

    def exercise_run(self,root,values,*,capture_failure=False,healthy_failure=False,guard_failure=False,clock=None):
        output=root/'out';baseline_api=dict(normalized=sample());bp=files.publish(root/'baseline.json',baseline_api)
        binding=files.publish(root/'binding.json',dict(owner=plan()['owner'],experiment='synthetic',actors=[],held_hashes={}))
        p=plan();p.update(output=str(output),binding=binding,observer_source=files.full_pin(Path(w.__file__)))
        pp=files.publish(root/'plan.json',p);job=dict(schema='profile06-production-next8M-window-job-v1',output=str(output),plan=pp,
            observer_source=p['observer_source'],baseline_API=bp,baseline_monotonic_s=1000)
        calls=[];provider=iter(values)
        def api():
            value=next(provider)
            if isinstance(value,Exception):raise value
            item=dict(normalized=value);return json.dumps(item).encode(),item
        def healthy(*args):
            if healthy_failure:raise ValueError('injected unhealthy pipeline')
        def guarded(*args):
            if guard_failure:raise ValueError('injected original actor changed')
        def capture(job,latch,trigger):
            calls.append((latch,trigger))
            if capture_failure:raise RuntimeError('original capture controller exit7')
            return dict(checkpoint=files.publish(output/'candidate.pt',b'private candidate'),normal_producer_mode_preserved=True)
        fake=SimpleNamespace(l=SimpleNamespace(checked=files.checked,publish=files.publish),reader=SimpleNamespace(read_pin=lambda p:json.loads(files.checked(p))),
            counter=SimpleNamespace(normalise=lambda api:api['normalized']),capture=SimpleNamespace(mutable_state=files.mutable_state),
            guard=SimpleNamespace(owner_and_files=guarded,healthy=healthy),authority=lambda:json.loads(files.checked(binding)),
            api=api,capture_at_endpoint=capture)
        ticks=iter(clock) if clock is not None else itertools.count(1001,1)
        with patch.object(w,'OUT',output),patch.object(w,'Context',return_value=fake),patch.object(w.time,'monotonic',side_effect=lambda:next(ticks)),patch.object(w.time,'sleep'):
            code=w.run(job)
        result=json.loads((output/'result.json').read_bytes())
        return code,result,calls,output

    def test_full_window_latches_first_both_horizons_and_captures_once(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),[sample(7_999_999,8_000_000,1),sample(8_000_000,8_000_010,2),sample(9_000_000,9_000_000,3)])
            self.assertEqual(code,0);self.assertEqual(len(calls),1)
            self.assertEqual(result['progress']['learner_frames'],8_000_000)
            self.assertEqual(result['progress']['learner_accepted'],8_000_010)
            latch=json.loads((output/'first-durable-both-horizons.json').read_bytes())
            self.assertTrue(latch['progress']['both_horizons']);self.assertFalse(result['quality_qualified'])

    def test_accepted_horizon_is_required_even_after_frame_horizon(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),[sample(8_000_000,7_999_999,1),sample(8_000_100,8_000_000,2)])
            self.assertEqual(code,0);self.assertEqual(len(calls),1);self.assertEqual(result['progress']['learner_frames'],8_000_100)

    def test_nonzero_capture_failure_remains_failure_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),[sample(8_000_000,8_000_000,1)],capture_failure=True)
            self.assertEqual(code,1);self.assertEqual(len(calls),1);self.assertIn('exit7',result['error'])
            self.assertFalse(result['original_capture_retried']);self.assertTrue((output/'first-durable-both-horizons.json').exists())

    def test_pipeline_failure_prevents_capture_and_preserves_error(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),[sample(8_000_000,8_000_000,1)],healthy_failure=True)
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('unhealthy pipeline',result['error'])
            self.assertFalse((output/'first-durable-both-horizons.json').exists())

    def test_original_actor_change_prevents_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),[sample(8_000_000,8_000_000,1)],guard_failure=True)
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('actor changed',result['error'])

    def test_counter_owner_epoch_change_prevents_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            value=sample(8_000_000,8_000_000,1);value['replay_identity']['epoch']=2
            code,result,calls,output=self.exercise_run(Path(directory),[value])
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('epoch changed',result['error'])

    def test_stale_baseline_is_rejected_before_any_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),[],clock=[1031])
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('initial observation',result['error'])

    def test_observation_gap_is_not_treated_as_terminal_or_capture_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),[OSError('temporarily unavailable')],clock=[1001,1002,1033])
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('gap reached30s',result['error'])
            self.assertFalse(result['trainer_restarted'])

    def test_no_applied_updates_for60s_fails_without_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,output=self.exercise_run(Path(directory),itertools.repeat(sample(100,100,0)))
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('No applied optimizer outcome',result['error'])

    def test_duplicate_window_job_is_rejected_before_authority_or_scheduling(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);job=root/'job.json';job.write_text('{}');p=plan();p['job_path']=str(job)
            context=Mock(side_effect=AssertionError('Unexpected launch attempt'))
            fake=SimpleNamespace(validate_plan=lambda p:None,OUT=root/'out',Context=context)
            with patch.object(x,'observer',return_value=fake),patch.object(x,'EXECUTION',root/'execution'),self.assertRaises(ValueError):
                x.launch(p,{})
            context.assert_not_called()

    def test_failed_authority_selects_no_baseline_and_schedules_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=plan();p['job_path']=str(root/'job.json')
            control=SimpleNamespace(command=Mock(side_effect=AssertionError('Unexpected scheduler')))
            context=SimpleNamespace(l=object(),control=control,authority=Mock(side_effect=ValueError('original CPU proof invalid')))
            fake=SimpleNamespace(validate_plan=lambda p:None,OUT=root/'out',Context=lambda p:context)
            with patch.object(x,'observer',return_value=fake),patch.object(x,'EXECUTION',root/'execution'),patch.object(x,'P',root),self.assertRaises(ValueError):
                x.launch(p,{})
            self.assertEqual(list(root.iterdir()),[]);control.command.assert_not_called()

    def exercise_close(self,root,*,code=1,exit_status=7,cat_exit=0,live=False,foreign=False):
        execution=root/'execution';execution.mkdir();files.publish(execution/'root-original-timer-launch-archive.json',dict(scope='synthetic'))
        owner=dict(pid=999,starttime_ticks=999,unit='synthetic-window.service',timer='synthetic-window.timer',invocation_id='a'*32,
            timer_invocation_id='b'*32,cgroup='/not-a-real-window-fixture',observed_live=True)
        fields=dict(InvocationID='f'*32 if foreign else owner['invocation_id'],NRestarts='0',MainPID=str(owner['pid']) if live else '0',
            ExecMainPID=str(owner['pid']),ExecMainCode=str(code),ExecMainStatus=str(exit_status),Result='exit-code' if code==1 else 'signal')
        releases=[];live_calls=[]
        def command(out,label,argv):return dict(argv=argv,exit=cat_exit if label=='original-timer-cat' else 0,timed_out=False)
        def release(out,kind,original,timer_context,row):row.update(unit=original['timer' if kind=='timer' else 'unit'],confirmed_absent=True);releases.append(kind)
        context=SimpleNamespace(l=SimpleNamespace(checked=files.checked,full_pin=files.full_pin,publish=files.publish,process_start=lambda pid:None,
            live_owner=lambda selected:live_calls.append(selected)),control=SimpleNamespace(show=lambda unit:fields,command=command,
            original_terminal=lambda fields,owner:None,release_original=release),
            runtime=SimpleNamespace(archived_closure=Mock()),reader=SimpleNamespace(read_pin=lambda e,as_json=True:{}))
        with patch.object(x,'EXECUTION',execution):
            if cat_exit==2 or foreign:
                with self.assertRaises(ValueError):x.close_if_terminal(context,owner)
                return None,releases,live_calls,execution
            result=x.close_if_terminal(context,owner)
        return result,releases,live_calls,execution

    def test_terminal_nonzero_exit_is_preserved_before_owned_release(self):
        with tempfile.TemporaryDirectory() as directory:
            result,releases,_,execution=self.exercise_close(Path(directory),exit_status=7)
            self.assertEqual(result['original_exit'],7);self.assertEqual(releases,['timer','service'])
            self.assertTrue(result['lifecycle_complete']);self.assertFalse(result['payload_retried'])

    def test_signal_is_archived_without_normalizing_or_restarting(self):
        with tempfile.TemporaryDirectory() as directory:
            result,releases,_,execution=self.exercise_close(Path(directory),code=2,exit_status=15)
            self.assertIsNone(result['original_exit']);self.assertEqual(result['original_signal'],15)
            self.assertEqual(releases,[]);self.assertFalse(result['lifecycle_complete'])
            self.assertTrue((execution/'terminal/root-original-terminal-archive.json').exists())

    def test_unknown_timer_descriptor_failure_prevents_release(self):
        with tempfile.TemporaryDirectory() as directory:
            _,releases,_,execution=self.exercise_close(Path(directory),cat_exit=2)
            self.assertEqual(releases,[]);self.assertTrue((execution/'terminal/root-original-terminal-archive.json').exists())

    def test_live_original_is_only_observed_and_never_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result,releases,live_calls,execution=self.exercise_close(Path(directory),live=True)
            self.assertIsNone(result);self.assertEqual(releases,[]);self.assertEqual(len(live_calls),1)
            self.assertFalse((execution/'terminal').exists())

    def test_foreign_terminal_invocation_cannot_be_archived_or_released(self):
        with tempfile.TemporaryDirectory() as directory:
            _,releases,_,execution=self.exercise_close(Path(directory),foreign=True)
            self.assertEqual(releases,[]);self.assertFalse((execution/'terminal').exists())

    def test_production_capture_configs_pin_validated_wrapper_and_fixed_resources(self):
        context=w.Context.__new__(w.Context);p=plan();p['capture_source']=dict(path='/synthetic/capture.py',sha256='d'*64)
        p['dependencies']={key:dict(path='/synthetic/'+key,sha256=value) for key,value in w.DEPENDENCY_SHA.items()}
        for key in ['pause_source','design','capture_CPU','capture_kernel']:p[key]=dict(path='/synthetic/'+key,sha256='e'*64)
        context.plan=p;source_job=dict(controller_unit='synthetic-capture.service',rescue_unit='synthetic-rescue.service')
        context.l=SimpleNamespace(checked=lambda entry:json.dumps(source_job).encode())
        context.control=SimpleNamespace(pin=lambda path:dict(path=path))
        jp=dict(path='/synthetic/job.json',sha256='f'*64)
        for role,flag in [('capture','--capture'),('rescue','--watch')]:
            cfg=context.CPU_config(role,jp)
            self.assertEqual(cfg['argv'][3:5],['/synthetic/capture.py',flag]);self.assertEqual(cfg['argv'][-1],jp['sha256'])
            self.assertIn('RuntimeMaxSec=180',cfg['properties']);self.assertIn('SendSIGKILL=no',cfg['properties'])
            self.assertEqual(cfg['observation_s'],240)

    def test_both_default_CLIs_perform_no_reads_or_runtime_actions(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Unexpected file read')),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(w.main([]),0);self.assertEqual(x.main([]),0);self.assertEqual(output.getvalue().count('PLAN_ONLY'),2)
