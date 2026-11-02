"""Authored-only stdlib guards; private files/fakes, never a live hot change."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

HERE=Path(__file__).resolve().parent


def source_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


M=source_module('_hot_driver_contract_source',HERE/'run_hot_window.py')
F=source_module('_existing_hot_metadata_fixtures',M.Q/'lr25_hot_window_observer_proposal/test_hot_window_observer.py')


def pin(path,sha='a'*64):
    return dict(path=str(path),sha256=sha,bytes=100,identity=dict(device=1,inode=1,bytes=100,
        mtime_ns=1000,ctime_ns=1000,mode='0o444',uid=os.getuid(),nlink=1))


def fixture():
    """Synthetic decoded prerequisites; every consumed field is explicit."""
    owner=dict(pid=123,starttime_ticks=789,unit='robotron-managed-synthetic-trainer.service',invocation_id='b'*32,cgroup='/synthetic/trainer.service')
    fleet=dict(pid=321,starttime_ticks=987,unit='synthetic-fleet.service',invocation_id='d'*32,cgroup='/synthetic/fleet.service')
    boot=dict(path=str(M.GAME/'models_dqn/managed-checkpoints/synthetic-historical-boot.pt'),sha256='a'*64,bytes=100)
    record_pin=pin('/synthetic/current-CE-record.json',M.FOUNDER)
    boot_pin=pin('/synthetic/immutable-boot-CPU.json')
    expected=dict(metric='ce',valid=True,phase_id='synthetic_CE',root_precommit_sha256='c'*64,
        founder_phase_record_sha256=M.FOUNDER,last_resume_record_sha256=None,
        started_from=dict(boot,clocks={k:1 for k in M.CLOCKS}))
    phase=dict(record=record_pin,boot_checkpoint=boot,boot_verification=boot_pin,expected=expected)
    before=dict(experiment='synthetic_old',lr_scale=.5,epsilon_ramp=dict(start=.1,end=.1,anchor=1,duration=1))
    control_pin=pin(M.GAME/'models_dqn/learning_control.json')
    entry_source=dict(path=str(M.GAME/'models_dqn/managed-checkpoints/synthetic-entry.pt'),sha256='a'*64,bytes=100)
    entry_control_pin=pin('/synthetic/entry-control.json');acq_pin=pin('/synthetic/entry-acquisition.json')
    entry_pin=pin('/synthetic/entry-CPU.json')
    held=dict(M.HELD,learning_control_lr_scale=.5,optimizer_lr=2.5e-5)
    entry=dict(schema='robotron-phase-snapshot-checkpoint-CPU-result-v1',status='PASS',phase_metadata_verified=True,
        script=dict(sha256='b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'),
        strict_phase_base=dict(sha256='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'),
        held_recipe_context=held,sha256=entry_source['sha256'],bytes=entry_source['bytes'],clocks={k:1 for k in M.CLOCKS},
        saved_priority_metric_phase=dict(metric='ce',valid=True,phase_record_sha256=M.FOUNDER),
        root_job=dict(schema='robotron-phase-snapshot-checkpoint-CPU-job-v1',source=entry_source,
            phase_snapshot=dict(purpose='candidate',observed_clients=192,owner=owner,expected_phase=expected,acquisition=acq_pin),
            source_control_context=dict(held_recipe_context=held,archived_control=entry_control_pin)))
    release_pin=pin('/synthetic/new-current-quality-release.json')
    pre=dict(schema='robotron-live-CE-lr25-hot-change-precommit-v1',status='ROOT_PRECOMMITTED_AFTER_QUALITY_CLOSURE_AND_FREEZE_RELEASE',
        experiment='synthetic_future_lr25',owner=owner,current_phase=phase,entry_checkpoint=entry_source,entry_CPU=entry_pin,
        source_freeze_release=release_pin,quality_closed=True,lr_scale_before=.5,lr_scale_after=.25,
        optimizer_lr_before=2.5e-5,optimizer_lr_after=1.25e-5,no_weight_or_optimizer_reset=True,no_replay_clear=True)
    actors=[dict(pid=1000+i,starttime_ticks=2000+i,mask=[0],slot=i) for i in range(192)]
    worker=dict(tid=124,starttime_ticks=790,mask=[0])
    env=dict(DQN_BATCH_SIZE='4096',DQN_PER_PRIORITY_METRIC='ce',DQN_PRIORITY_PHASE_RECORD_SHA256=M.FOUNDER,
        DQN_PRIORITY_PHASE_RECORD=record_pin['path'])
    maintenance_pin=pin('/synthetic/current-maintenance.json');maintenance_job_pin=pin('/synthetic/current-maintenance-job.json')
    baseline=dict(main_owner=owner,fleet_owner=fleet,inference_worker=worker,actors=actors,
        source_hashes={'/synthetic/source-%d.py'%i:'f'*64 for i in range(61)},
        control_hashes={str(M.GAME/'models_dqn/learning_control.json'):'a'*64,'/synthetic/game_settings.json':'e'*64},
        unit_files={'/synthetic/unit-%d'%i:'f'*64 for i in range(3)},environment_sha256='e'*64,
        actual_maintenance=maintenance_pin,actual_API=pin('/synthetic/raw-before-API.json'))
    resources=dict(owner=owner,main=dict(owner),fleet=dict(fleet),worker=worker,
        actors=[dict(x,cgroup=fleet['cgroup']) for x in actors])
    ready=dict(status='PASS',observed_unix_s=100000.,**{k:baseline[k] for k in
        ('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')},
        resources=dict(GPU0_free_bytes=14*(1<<30),**{k:True for k in
        ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free','no_competing_helpers',
         'no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released')}))
    slot=pin(M.GAME/'models_dqn/managed_save.request.json.completed')
    job=dict(schema=M.SCHEMA,activation_authorized=True,precommit=pin('/synthetic/precommit.json'),
        runtime_baseline=pin('/synthetic/baseline.json'),readiness=pin('/synthetic/readiness.json'),
        control_before=control_pin,completed_slot=slot,startup_tag='genuine_synthetic_startup',
        tags=dict(barrier='unique_synthetic_barrier',endpoint='unique_synthetic_endpoint'),
        window=dict(policy=dict(F.helper.POLICY,cutoff_s=100),preparation_timeout_s=60),
        output_directory=str(M.RUN/'synthetic-future-driver-output'))
    decoded={record_pin['path']:dict(metric='ce',checkpoint=boot,root_precommit_sha256=expected['root_precommit_sha256']),
        boot_pin['path']:dict(status='PASS',sha256=boot['sha256'],bytes=boot['bytes']),
        maintenance_pin['path']:dict(status='READY_CE_FORWARD_REPAIR',owner=owner,root_job=maintenance_job_pin,startup=dict(phase=phase)),
        maintenance_job_pin['path']:dict(startup_tag=job['startup_tag']),entry_control_pin['path']:before,
        release_pin['path']:dict(source_freeze_released=True,owned_cleanup_complete=True,released_unix_s=1.,
            plan=dict(sha256=M.CURRENT_PLAN),binding_job=dict(sha256=M.CURRENT_BINDING)),
        acq_pin['path']:dict(purpose='candidate',client_count=192,owner_before=owner,owner_after=owner,
            completed_slot_transition=dict(request_unix_s=2.,after_unix_s=3.)),
        baseline['actual_API']['path']:json.dumps(F.api_at()).encode()}
    obj=M.Driver.__new__(M.Driver)
    obj.job=job;obj.pre=pre;obj.baseline=baseline;obj.readiness=ready;obj.owner=owner;obj.phase=phase;obj.entry=entry
    obj.health_floor_clocks=copy.deepcopy(entry['clocks'])
    obj.capture=SimpleNamespace(triple=lambda value:{k:value[k] for k in ('path','sha256','bytes')})
    obj.before=before;obj.before_pin=control_pin;obj.control_pin=control_pin;obj.env=env;obj.resources=resources
    obj.expected_completed=slot;obj.observer=F.helper;obj.out=Path(job['output_directory'])
    obj.check_health=Mock(return_value=None);obj.replace_control=Mock(side_effect=AssertionError('hotwrite must not happen'))
    existing={str(M.GAME/'models_dqn/managed_save.request.json.completed')}
    current={slot['path']:copy.deepcopy(slot)}
    obj.files=SimpleNamespace(fingerprint=lambda p,*_:copy.deepcopy(current[str(p)]))
    def reader(value,raw_only=False):return copy.deepcopy(decoded[value['path']])
    return obj,decoded,existing,current,reader


@contextlib.contextmanager
def validate_scope(reader,existing):
    with patch.object(M,'pinned',side_effect=reader),patch.object(M.time,'time',return_value=100000.), \
            patch.object(Path,'resolve',lambda self,strict=False:self), \
            patch.object(Path,'exists',lambda self:str(self) in existing), \
            patch.object(Path,'mkdir',side_effect=AssertionError('no writes before successful validation')):
        yield


class HotDriverMetadataContracts(unittest.TestCase):
    def test_default_PLAN_is_readfree_and_never_loads_a_helper(self):
        with patch.object(M,'fingerprint',side_effect=AssertionError('no reads')), \
                patch.object(M,'load',side_effect=AssertionError('no helper imports')), \
                patch.object(M.urllib.request,'urlopen',side_effect=AssertionError('no API')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(M.main([]),0)
        self.assertIn('PLAN_ONLY_UNSELECTED',output.getvalue())

    def test_copied_wrong_control_path_is_rejected_before_hotwrite(self):
        obj,decoded,existing,current,reader=fixture()
        with validate_scope(reader,existing):obj.validate()
        obj.job['control_before']=pin(M.GAME/'models_dqn/copied-control.json')
        obj.before_pin=copy.deepcopy(obj.job['control_before'])
        with validate_scope(reader,existing),self.assertRaisesRegex(RuntimeError,'actual held default model control'):
            obj.run()
        obj.replace_control.assert_not_called()

    def test_foreign_completed_pending_and_failed_reject_before_hotwrite(self):
        for fault in ('completion','pending','failed'):
            obj,decoded,existing,current,reader=fixture()
            if fault=='completion':current[obj.expected_completed['path']]['sha256']='b'*64
            else:existing.add(str(M.GAME/'models_dqn'/('managed_save.request.json'+('.failed' if fault=='failed' else ''))))
            with self.subTest(fault=fault),validate_scope(reader,existing),self.assertRaisesRegex(RuntimeError,'foreign/unmatched request or completion'):
                obj.run()
            obj.replace_control.assert_not_called()

    def test_phase_entry_and_precommit_mismatch_reject_before_hotwrite(self):
        for fault in ('phase','entry','precommit'):
            obj,decoded,existing,current,reader=fixture()
            if fault=='phase':obj.pre['current_phase']['record']['sha256']='b'*64
            elif fault=='entry':obj.pre['entry_checkpoint']=dict(obj.pre['entry_checkpoint'],path='/synthetic/foreign-entry.pt')
            else:obj.pre['schema']='foreign-precommit'
            with self.subTest(fault=fault),validate_scope(reader,existing),self.assertRaises(RuntimeError):obj.run()
            obj.replace_control.assert_not_called()

    def test_real_private_control_transaction_restores_bytes_and_refuses_foreign_change(self):
        # Load only the actual stdlib file-operation classes, not their entrypoints.
        ops=source_module('_private_hot_driver_ops',M.DEPENDENCIES['ops']['path'])
        capture=source_module('_private_hot_driver_files',M.DEPENDENCIES['capture']['path'])
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();control=root/'control.json';out=root/'new-output';out.mkdir()
            original=b'{"experiment":"private-before","lr_scale":0.5}\n';after=b'{"experiment":"private-after","lr_scale":0.25}\n'
            control.write_bytes(original)
            obj=M.Driver.__new__(M.Driver);obj.ops=ops;obj.files=capture.Files(ops);obj.out=out
            obj.job=dict(control_before=dict(path=str(control)));obj.control_pin=obj.files.fingerprint(control)
            obj.hashes={str(control):obj.control_pin['sha256']};obj.slot_guard=Mock(return_value=None)
            obj.replace_control(after,'private25');self.assertEqual(control.read_bytes(),after)
            obj.replace_control(original,'private50');self.assertEqual(control.read_bytes(),original)
            obj.replace_control(after,'private25-again');control.write_bytes(b'foreign-current-bytes\n')
            with self.assertRaisesRegex(RuntimeError,'Expected current control changed'):obj.replace_control(original,'must-not-restore')
            self.assertEqual(control.read_bytes(),b'foreign-current-bytes\n')
            self.assertFalse((out/'must-not-restore-intent.json').exists())

    def test_real_run_routes_max_four_floor_and_seals_context_before_restore(self):
        order=[]
        with tempfile.TemporaryDirectory() as temporary:
            obj=M.Driver.__new__(M.Driver);obj.out=Path(temporary)/'new-output';obj.files=SimpleNamespace(fsync_directory=lambda _:None)
            obj.validate=Mock(return_value=None);obj.owner=F.job_at()['owner'];obj.job_pin=pin('/synthetic/root-job.json')
            obj.phase=copy.deepcopy(F.job_at()['current_phase']);obj.control_pin=pin('/synthetic/active-control.json')
            B=F.api_at();B['pipeline_snapshot_age_s']=0
            latch=F.api_at(1,learner=8000000,fleet=9000000,dqn=6000000,applied=1,
                logical_steps=1,logical_samples=4096)
            obj.pre=dict(experiment=B['managed_experiment'],entry_CPU=pin('/synthetic/entry.json'))
            obj.entry=dict(clocks={k:B[k]-10 for k in M.CLOCKS})
            obj.before=dict(experiment='synthetic_original');obj.before_raw=b'original-control-bytes\n';obj.restored=False;obj.pending=None
            obj.job=dict(precommit=pin('/synthetic/precommit.json'),runtime_baseline=pin('/synthetic/runtime.json'),readiness=pin('/synthetic/readiness.json'),
                window=dict(preparation_timeout_s=60,policy=dict(F.helper.POLICY,cutoff_s=100)))
            values={}
            def publish(path,value):values[str(path)]=value;return pin(path)
            obj.ops=SimpleNamespace(publish=publish,write_bytes=publish)
            obj.files.fingerprint=lambda path,*_:pin(path)
            stage={'restored':False,'latched':False}
            def replace(raw,name):order.append(name);stage['restored']=name=='control50-restored';return pin(obj.out/name)
            obj.replace_control=replace
            def health(*_):
                api=copy.deepcopy(latch if stage['latched'] else B)
                if stage['restored']:api.update(managed_experiment='synthetic_original',lr=2.5e-5)
                return b'{}',api
            obj.check_health=health;obj.runtime=SimpleNamespace(trainer_id=lambda:obj.owner)
            def save(stage_name,raw,api,floor):
                order.append('save-'+stage_name)
                if stage_name=='endpoint':self.assertEqual(floor,{k:latch[k] for k in M.CLOCKS})
                return SimpleNamespace(),dict(synthetic_stage=stage_name)
            obj.save=save
            def context(*_):order.append('context25-sealed');return pin(obj.out/'CPU-job.json')
            obj.endpoint_context=context
            outcome=dict(status='LATCH_DURABLE',candidate_requests_allowed=1,observation=dict(first_eligible_observation=latch))
            def poll(*args,**kwargs):stage['latched']=True;return outcome
            def journal(**kw):return SimpleNamespace(root=kw['root'],emit=lambda event:None)
            obj.observer=SimpleNamespace(SCHEMA=F.helper.SCHEMA,RECIPE=F.helper.RECIPE,normalise=F.helper.normalise,
                validate_job=lambda *_:None,ReceiptJournal=journal,poll=poll,encoded=F.helper.encoded)
            with patch.object(M,'clock',return_value=F.clock()):result=obj.run()
            self.assertEqual(order,['control25','save-barrier','save-endpoint','context25-sealed','control50-restored'])
            self.assertEqual(result['status'],'CAPTURED_PENDING_ROOT_CPU');self.assertFalse(result['CPU_executed'])
            self.assertTrue(result['original_control_bytes_restored'])


if __name__=='__main__':unittest.main()
