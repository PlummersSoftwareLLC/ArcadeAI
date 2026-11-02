"""Bounded CPU preparation contracts; live closure/input capabilities substituted."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import prepare_startup_probe_v4 as prep


def loaded(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


READER=loaded('_prepare_CPU_reader',prep.READER)


def publish(path,value):
    raw=value if type(value) is bytes else (json.dumps(value,separators=(',',':'))+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return READER.pin(path)


def main_template():
    return dict(schema='robotron-main192-capacity-pilot-binding-v1',
        owner=dict(pid=900000,starttime_ticks=1,unit='robotron-CPU-fixture.service',invocation_id='a'*32),
        actors=[dict(slot=slot,pid=900001+slot,starttime_ticks=1,mask=[0,1]) for slot in range(192)],
        held_hashes={'/CPU-fixture/source-'+str(n):'a'*64 for n in range(195)},
        experiment='CPU-fixture-only',baseline_API={})


class FakeSystem(prep.System):
    def __init__(self,root):
        super().__init__();self.root=root;self.events=[];self.failure=None
    def authenticate(self,request,entry):
        self.events.append('authenticate')
        if self.failure=='authenticate':raise ValueError('source authentication failure')
        # Exercise the real fixed-source reader, loader and all126 file pins.
        super().authenticate(request,entry)
    def closed(self,request):
        self.events.append('closed')
        if self.failure=='closed':raise ValueError('original predecessor still live')
        return dict(status='ORIGINAL_PREDECESSOR_CLOSED',native_outcome='not_improved',original_owner_count=3,
                    GPU_lease_acquired=False,scientific_outcome_changed=False)
    def capture(self,request):
        self.events.append('capture')
        if self.failure=='capture':raise ValueError('fresh main input rejected')
        binary=[dict(path='/usr/games/mame')]+[dict(path=str(prep.GAME/'roms/robotron'/name),sha256=sha,bytes=4096)
            for name,sha in self.modules['runtime'].ROM_INPUTS.values()]
        return dict(main=main_template(),first_API=b'{"original":"first"}\n',
            second_API=b'{"original":"second","unused_loss":NaN}\n',baseline={},observed_unix_s=time.time(),
            checkpoint=request['checkpoint'],checkpoint_metadata=request['checkpoint_metadata'],
            finite=dict(status='CPU-fixture-capability-only'),canonical_state={},
            canonical_bytes=b'{"incumbent":"CPU-fixture"}\n',held_inputs={},binary_inputs=binary,
            boot_identity='b'*64,lease=dict(path='/dev/shm/robotron-snapshot-smoke-gpu0.lock',device=32,inode=757))
    def revalidate(self,request,snapshot):
        self.events.append('revalidate')
        if self.failure=='revalidate':raise ValueError('late original input changed')
    def publish(self,name,raw):
        self.events.append('publish:'+name)
        if self.failure==name:raise OSError('publication failure: '+name)
        return super().publish(name,raw)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='startup-prepare-CPU-');self.root=Path(self.temp.name).resolve()
        # The outer bounded original supplies TMPDIR under its owned run-26 tree.
        self.assertTrue(self.root.is_relative_to(prep.RUN))
        self.input=publish(self.root/'checkpoint.bin',b'CPU-fixture-not-a-model')
        self.metadata=publish(self.root/'checkpoint-meta.json',{})
        self.request=dict(schema='robotron-private-startup-preparation-request-v1',
            preparation=str(self.root/'fresh-preparation'),probe_output=str(prep.RUN/('CPU-UNUSED-'+self.root.name)),
            tag='CPU-original-'+self.root.name,predecessor={},main_template={},checkpoint=self.input,
            checkpoint_metadata=self.metadata,finite_CPU={key:{} for key in ['report','job','owner','closure','config']},
            affinity=[0,1],guard_affinity=[0,1])
        self.patches=[patch.object(prep.subprocess,'run',side_effect=AssertionError('actual unit/process query forbidden')),
            patch.object(prep.subprocess,'Popen',side_effect=AssertionError('actual process forbidden')),
            patch.object(prep.urllib.request,'urlopen',side_effect=AssertionError('actual API/network query forbidden'))]
        for item in self.patches:item.start()
    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()
    def entry(self,request=None,name='request.json'):
        return publish(self.root/name,self.request if request is None else request)
    def run_prepare(self,system=None):
        system=FakeSystem(self.root) if system is None else system
        result=prep.prepare(self.request,self.entry(),system=system)
        return result,system

    def test_constructor_and_default_entry_do_not_read_query_or_create_outputs(self):
        system=prep.System();self.assertIsNone(system.reader);self.assertIsNone(system.preparation)
        source=(HERE/'prepare_startup_probe_v4.py').read_text()
        with patch.object(sys,'argv',['prepare_startup_probe_v4.py']), \
                patch.object(Path,'read_bytes',side_effect=AssertionError('source read forbidden')), \
                patch('builtins.print') as output:
            exec(compile(source,'<inert-preparation>','exec'),dict(__name__='__main__',__file__=str(HERE/'prepare_startup_probe_v4.py')))
        self.assertIn('PLAN_ONLY',output.call_args.args[0]);self.assertFalse(Path(self.request['preparation']).exists())

    def test_prepare_entry_requires_explicit_source_pin_before_request_read(self):
        source=(HERE/'prepare_startup_probe_v4.py').read_text()
        with patch.object(sys,'argv',['prepare_startup_probe_v4.py','--prepare','--request','never-read']), \
                patch.object(Path,'read_bytes',side_effect=AssertionError('request/source read before source argument')):
            with self.assertRaisesRegex(ValueError,'source SHA'):
                exec(compile(source,'<prepare-entry-pin>','exec'),dict(__name__='__main__',__file__=str(HERE/'prepare_startup_probe_v4.py')))

    def test_actual_fixed_loader_and_job_plan_publish_use_same_controlled_capability_instance(self):
        result,system=self.run_prepare()
        self.assertEqual(system.events[:3],['authenticate','closed','capture'])
        self.assertLess(system.events.index('revalidate'),system.events.index('publish:original-launch-plan.json'))
        self.assertEqual(result['status'],'PREPARED_NOT_SELECTED_NOT_EXECUTED')
        reader,plan,job,modules=system.modules['launcher'].load_plan(result['plan'])
        self.assertEqual(modules['runtime'].__file__,str(HERE/'startup_probe_runtime_v5.py'))
        self.assertEqual(job['package']['sha256'],prep.PACKAGE_SHA)
        self.assertEqual(len(set(job['sessions'].values())),16)
        self.assertFalse(Path(job['output']).exists());self.assertFalse(Path(job['external_guard_permit_path']).exists())
        self.assertEqual(Path(self.request['preparation']).stat().st_mode&0o777,0o700)
        self.assertFalse(result['GPU_idle_queried']);self.assertFalse(result['lease_opened_or_locked'])

    def test_original_live_predecessor_refusal_never_captures_or_publishes(self):
        system=FakeSystem(self.root);system.failure='closed'
        with self.assertRaisesRegex(ValueError,'still live'):self.run_prepare(system)
        self.assertEqual(system.events,['authenticate','closed']);self.assertFalse(Path(self.request['preparation']).exists())

    def test_source_authentication_failure_never_reaches_original_closure_or_input_queries(self):
        system=FakeSystem(self.root);system.failure='authenticate'
        with self.assertRaises(ValueError):self.run_prepare(system)
        self.assertEqual(system.events,['authenticate']);self.assertFalse(Path(self.request['preparation']).exists())

    def test_failed_input_capture_creates_no_job_or_plan(self):
        system=FakeSystem(self.root);system.failure='capture'
        with self.assertRaises(ValueError):self.run_prepare(system)
        self.assertEqual(system.events,['authenticate','closed','capture']);self.assertFalse(Path(self.request['preparation']).exists())

    def test_late_input_failure_preserves_originals_job_and_explicit_failure_without_plan(self):
        system=FakeSystem(self.root);system.failure='revalidate'
        with self.assertRaisesRegex(ValueError,'late original'):self.run_prepare(system)
        root=Path(self.request['preparation'])
        self.assertTrue((root/'original-runtime-job.json').exists())
        self.assertTrue((root/'main-baseline-API-original.bin').exists())
        self.assertFalse((root/'original-launch-plan.json').exists())
        self.assertFalse((root/'preparation-result.json').exists())
        self.assertEqual(json.loads((root/'preparation-failure-preserved.json').read_bytes())['status'],
                         'FAILED_ORIGINAL_PREPARATION_NO_RETRY')

    def test_same_capability_instance_cannot_prepare_a_second_original(self):
        result,system=self.run_prepare()
        with self.assertRaises(ValueError):prep.prepare(self.request,{},system=system)
        self.assertEqual(system.events.count('capture'),1)

    def test_existing_preparation_probe_and_noncanonical_paths_are_refused(self):
        variants=[]
        bad=copy.deepcopy(self.request);bad['preparation']=str(self.root);variants.append(bad)
        bad=copy.deepcopy(self.request);bad['probe_output']=str(self.root/'nested-probe');variants.append(bad)
        bad=copy.deepcopy(self.request);bad['preparation']='relative';variants.append(bad)
        bad=copy.deepcopy(self.request);bad['probe_output']=str(prep.RUN);variants.append(bad)
        for value in variants:
            with self.assertRaises(ValueError):prep.checked_request(value)

    def test_schema_tag_masks_and_finite_bundle_cannot_be_weakened(self):
        changes=[dict(schema='other'),dict(tag='../bad'),dict(tag=''),dict(affinity=[True]),
                 dict(guard_affinity=[]),dict(affinity=[1,0]),dict(finite_CPU={})]
        for change in changes:
            value=copy.deepcopy(self.request);value.update(change)
            with self.assertRaises(ValueError):prep.checked_request(value)
        value=copy.deepcopy(self.request);value['extra']=True
        with self.assertRaises(ValueError):prep.checked_request(value)

    def test_duplicate_nonfinite_nonobject_or_oversized_preparation_JSON_is_refused(self):
        for raw in [b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'[]',b'x'*(4*1024*1024+1)]:
            with self.assertRaises(ValueError):prep.decode(raw)

    def test_exact_wire_bytes_are_retained_even_with_unused_nonfinite_diagnostic(self):
        result,system=self.run_prepare();job=READER.read_pin(result['job']);main=READER.read_pin(job['main'])
        raw=READER.read_pin(main['baseline_API'],as_json=False)
        self.assertEqual(raw,b'{"original":"second","unused_loss":NaN}\n')
        self.assertEqual((Path(self.request['preparation'])/'main-first-API-original.bin').read_bytes(),b'{"original":"first"}\n')

    def test_duplicate_generated_sessions_fail_before_job_or_plan_publication(self):
        with patch.object(prep.os,'urandom',return_value=b'x'*16):
            with self.assertRaises(ValueError):self.run_prepare()
        root=Path(self.request['preparation'])
        self.assertFalse((root/'original-runtime-job.json').exists());self.assertFalse((root/'original-launch-plan.json').exists())
        self.assertTrue((root/'preparation-failure-preserved.json').exists())

    def test_publication_failure_retains_explicit_invalid_original_and_never_schedules(self):
        system=FakeSystem(self.root);system.failure='original-launch-plan.json'
        with self.assertRaises(OSError):self.run_prepare(system)
        root=Path(self.request['preparation']);self.assertTrue((root/'original-runtime-job.json').exists())
        self.assertTrue((root/'preparation-failure-preserved.json').exists());self.assertFalse((root/'preparation-result.json').exists())

    def test_real_source_authentication_refuses_changed_request_before_any_live_query(self):
        system=prep.System();entry=self.entry();changed=copy.deepcopy(self.request);changed['tag']='different'
        with self.assertRaises(ValueError):system.authenticate(changed,entry)
        self.assertIsNone(system.preparation)

    def test_real_closed_gate_refuses_incomplete_original_bundle_before_process_or_unit_query(self):
        system=prep.System();system.authenticate(self.request,self.entry())
        with patch.object(system,'fields',side_effect=AssertionError('unit query before metadata refused')), \
                patch.object(system.modules['runtime'],'process_start',side_effect=AssertionError('birth query before metadata refused')):
            with self.assertRaises(ValueError):system.closed(self.request)

    def test_main_template_requires_all192_distinct_typed_actor_slots_and195_hashes(self):
        prep.main_shape(main_template())
        changes=[lambda m:m['actors'].pop(),lambda m:m['held_hashes'].pop(next(iter(m['held_hashes']))),
                 lambda m:m['actors'][0].update(pid=True),lambda m:m['actors'][1].update(slot=True),
                 lambda m:m['actors'][1].update(pid=m['actors'][0]['pid']),
                 lambda m:m['actors'][0].update(mask=[True]),lambda m:m['actors'][0].update(mask=[1,0])]
        for change in changes:
            value=main_template();change(value)
            with self.assertRaises(ValueError):prep.main_shape(value)

    def test_real_capture_refuses_bad_roster_before_main_census_or_checkpoint_read(self):
        system=prep.System();events=[]
        system.reader=types.SimpleNamespace(read_pin=lambda *a,**k:b'{"schema":"invalid"}')
        system.modules=dict(runtime=object(),closure=object(),main_guard=types.SimpleNamespace(
            owner_and_files=lambda *a:events.append('forbidden-main-query')))
        with self.assertRaises(ValueError):system.capture(self.request)
        self.assertEqual(events,[])

    def progress_fixture(self):
        raw=(prep.RUN/'startup-probe-launch-v2-CPU-original01-preparation-20261020/post-registration-dashboard-API-original-wire.json').read_bytes()
        first=json.loads(raw);second=copy.deepcopy(first)
        for key in ['frame_count','learner_frame_count','optimized_samples','training_steps']:second[key]+=10
        pid=first['host_pipeline']['learning_exposure']['optimizer']['process_id']
        closure=loaded('_prepare_CPU_pure_closure_'+str(time.time_ns()),prep.GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
        return first,second,pid,closure

    def test_actual_exposure_validator_accepts_progressing_same_instance_API_pair(self):
        first,second,pid,closure=self.progress_fixture();prep.progressing(first,second,pid,closure)

    def test_stalled_regressed_epoch_switched_or_recipe_changed_API_pair_is_refused(self):
        first,second,pid,closure=self.progress_fixture()
        variants=[]
        bad=copy.deepcopy(second);bad['learner_frame_count']=first['learner_frame_count'];variants.append(bad)
        bad=copy.deepcopy(second);bad['training_steps']=-1;variants.append(bad)
        bad=copy.deepcopy(second);bad['lr']*=2;variants.append(bad)
        bad=copy.deepcopy(second);bad['host_pipeline']['learning_exposure']['replay']['epoch']+=1;variants.append(bad)
        bad=copy.deepcopy(second);bad['host_pipeline']['learning_exposure']['optimizer']['process_id']+=1;variants.append(bad)
        for value in variants:
            with self.assertRaises(ValueError):prep.progressing(first,value,pid,closure)

    def test_nonfinite_or_boolean_work_and_behavior_values_are_refused(self):
        first,second,pid,closure=self.progress_fixture()
        for key,value in [('frame_count',True),('lr',float('nan')),('epsilon',float('inf'))]:
            bad=copy.deepcopy(second);bad[key]=value
            with self.assertRaises(ValueError):prep.progressing(first,bad,pid,closure)

    def test_fresh_main_api_uses_original_template_recipe_and_exposure_identity(self):
        first,second,pid,closure=self.progress_fixture();current=copy.deepcopy(second)
        now=time.time();current['ts']=now;current['pipeline_snapshot_age_s']=0.0
        guard=loaded('_prepare_CPU_main_guard_'+str(time.time_ns()),prep.RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
        prep.anchored_main_api(current,first,current['managed_experiment'],now,guard)

    def test_stale_epoch_switched_or_preexisting_recipe_change_cannot_be_a_fresh_baseline(self):
        first,second,pid,closure=self.progress_fixture();now=time.time()
        second['ts']=now;second['pipeline_snapshot_age_s']=0.0
        guard=loaded('_prepare_CPU_main_guard_bad_'+str(time.time_ns()),prep.RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
        variants=[]
        bad=copy.deepcopy(second);bad['ts']=now-6;variants.append(bad)
        bad=copy.deepcopy(second);bad['epsilon']+=0.1;variants.append(bad)
        bad=copy.deepcopy(second);bad['host_pipeline']['learning_exposure']['replay']['epoch']+=1;variants.append(bad)
        for current in variants:
            with self.assertRaises(ValueError):prep.anchored_main_api(current,first,current['managed_experiment'],now,guard)

    def test_real_input_inventory_rejects_symlink_and_explicit_count_overflow(self):
        system=prep.System();root=self.root/'inputs';root.mkdir();(root/'a').write_bytes(b'a')
        self.assertEqual(system.inventory(root,maximum_files=1,maximum_directories=1),[root/'a'])
        (root/'b').write_bytes(b'b')
        with self.assertRaises(ValueError):system.inventory(root,maximum_files=1,maximum_directories=1)
        (root/'b').unlink();(root/'b').symlink_to(root/'a')
        with self.assertRaises(ValueError):system.inventory(root,maximum_files=3,maximum_directories=1)

    def real_revalidation(self):
        system=FakeSystem(self.root);system.authenticate(self.request,self.entry())
        snapshot=system.capture(self.request);system.modules['main_guard']=types.SimpleNamespace(owner_and_files=lambda *args:None)
        normal=self.root/'held-normal';normal.write_bytes(b'original-normal-mode')
        snapshot.update(held_inputs={str(normal):READER.pin(normal)},binary_inputs=[],
            canonical_state=READER.pin(prep.GAME/'logs/managed-learning-20261015/state.json'))
        system.fields=lambda unit:dict(Id=unit,LoadState='not-found')
        return system,snapshot,normal

    def test_real_revalidation_preserves_normal_inputs_and_refuses_late_change(self):
        system,snapshot,normal=self.real_revalidation();before=READER.pin(normal)
        prep.System.revalidate(system,self.request,snapshot);self.assertEqual(READER.pin(normal),before)
        normal.write_bytes(b'changed-normal-mode')
        with self.assertRaises(ValueError):prep.System.revalidate(system,self.request,snapshot)

    def test_expired_freshness_or_consumed_original_unit_names_refused(self):
        system,snapshot,normal=self.real_revalidation();snapshot['observed_unix_s']=time.time()-61
        with self.assertRaises(ValueError):prep.System.revalidate(system,self.request,snapshot)
        snapshot['observed_unix_s']=time.time();system.fields=lambda unit:dict(Id=unit,LoadState='loaded')
        with self.assertRaises(ValueError):prep.System.revalidate(system,self.request,snapshot)

    def finite_fixture(self):
        script=prep.GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
        job=dict(verifier_sha256=prep.FINITE_SHA,source=self.input,verification_copy=self.input)
        job_pin=dict(path='/CPU-fixture/job.json',sha256='a'*64)
        proof=dict(report=dict(path='report'),job=job_pin,owner=dict(path='owner'),closure=dict(path='closure'),config=dict(path='config'))
        report=dict(schema='robotron-phase-snapshot-checkpoint-CPU-result-v1',status='PASS',root_job=job,
            script=dict(path=str(script),sha256=prep.FINITE_SHA),source_before=self.input,verification_copy=self.input,
            cuda_initialized=False,actual_restore_or_optimizer_step=False,actual_quality_qualification=False,
            finite=dict(tensors=443,tensor_elements=68760333),adam_state_count=81,
            models={name:dict(strict_cpu_load=True,tensor_count=100) for name in ['online_state_dict','target_state_dict']})
        argv=[str(script),job_pin['path'],job_pin['sha256'],prep.FINITE_SHA]
        values=dict(report=report,**{job_pin['path']:job},owner=dict(unit='CPU-fixture.service'),closure={},
            config=dict(unit='CPU-fixture.service',argv=argv))
        def read(pin,as_json=True):
            return copy.deepcopy(values[pin['path']]) if pin['path'] in values else READER.read_pin(pin,as_json=as_json)
        reader=types.SimpleNamespace(read_pin=read,pin=READER.pin)
        def archived(closed,owner,read,exit_zero):
            self.assertTrue(exit_zero);return dict(ExecStart=' '.join(argv))
        closure=types.SimpleNamespace(archived_closure=archived)
        return proof,reader,closure,values

    def test_finite_proof_binds_actual_verifier_source_and_exact_checkpoint_digest(self):
        proof,reader,closure,values=self.finite_fixture()
        result=prep.finite_checkpoint(self.input,proof,reader,closure)
        self.assertEqual(result['checkpoint_sha256'],self.input['sha256']);self.assertFalse(result['numerical_module_imported'])

    def test_nonfinite_partial_wrong_model_checkpoint_or_GPU_scope_proof_refused(self):
        changes=[lambda v:v['report'].update(status='FAIL'),lambda v:v['report']['finite'].update(tensors=442),
                 lambda v:v['report'].update(adam_state_count=80),lambda v:v['report'].update(cuda_initialized=True),
                 lambda v:v['report']['models']['target_state_dict'].update(strict_cpu_load=False),
                 lambda v:v['report'].update(actual_restore_or_optimizer_step=True),
                 lambda v:v['report'].update(source_before=dict(sha256='f'*64,bytes=self.input['bytes']))]
        for change in changes:
            proof,reader,closure,values=self.finite_fixture();change(values)
            with self.assertRaises(ValueError):prep.finite_checkpoint(self.input,proof,reader,closure)

    def test_original_CPU_config_and_actual_archived_command_must_bind_job_source_hashes(self):
        proof,reader,closure,values=self.finite_fixture();values['config']['argv']=[]
        with self.assertRaises(ValueError):prep.finite_checkpoint(self.input,proof,reader,closure)
        proof,reader,closure,values=self.finite_fixture()
        closure.archived_closure=lambda *args,**kwargs:dict(ExecStart='different program')
        with self.assertRaises(ValueError):prep.finite_checkpoint(self.input,proof,reader,closure)


    def test_actual_new_loader_and_core_gate_rejoin_archived_predecessor_without_capture(self):
        # Allow only the closed-boundary unit reads; API remains forbidden.
        self.patches[0].stop();self.patches[1].stop()
        path=prep.RUN/'quality32-CE1059-vs-tail9000-fresh-main-next8M-original01-preparation-20261019/original-independent-review-rejection-root-cause-20261020/actual-original-closed-predecessor-bundle.json'
        self.request['predecessor']=READER.read_pin(READER.pin(path))
        prep.checked_request(self.request)
        entry=self.entry()
        caps=prep.System();caps.authenticate(self.request,entry)
        self.assertEqual(Path(caps.modules['core'].__file__).name,'startup_probe_core_v2.py')
        self.assertEqual(Path(caps.modules['runtime'].__file__).name,'startup_probe_runtime_v5.py')
        self.assertEqual(Path(caps.modules['launcher'].__file__).name,'startup_probe_launch_v5.py')
        result=caps.closed(self.request)
        self.assertEqual(result['status'],'ORIGINAL_PREDECESSOR_CLOSED')
        self.assertEqual(result['native_outcome'],'qualified_improvement')
        disposition=READER.read_pin(self.request['predecessor']['disposition'])
        self.assertFalse(disposition['quality_qualified'])
        self.assertIsNone(caps.preparation)
        self.assertFalse(Path(self.request['preparation']).exists())
        self.assertFalse(Path(self.request['probe_output']).exists())



if __name__=='__main__':
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(name.startswith('dqn.') for name in sys.modules)
    print(json.dumps(dict(schema='robotron-startup-probe-preparation-CPU-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual fixed-source authentication, v2 metadata loader and fresh job/plan output, with explicitly substituted original closure/live-input capabilities. Read-only exposure/finite-proof checks and temporary normal/immutable files; no actual service/device/network query, lease open, model or emulator.',
        actual_guard_or_probe_launched=False,real_preparation_selected=False,protocol_selected=False,
        real_ROM_start_proven=False,quality_qualified=False,learning_speed_gain_verified=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
