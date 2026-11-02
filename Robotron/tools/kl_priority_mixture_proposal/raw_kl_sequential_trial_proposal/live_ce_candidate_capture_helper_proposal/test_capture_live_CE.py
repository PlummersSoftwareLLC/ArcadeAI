"""Focused stdlib guards; author has not imported or executed this suite."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('live_ce_capture_under_test',HERE/'capture_live_CE_candidate.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Ops:
    def __init__(self):
        self.files=m.Files(self);self.health_calls=0;self.changed_owner=False
    def write_bytes(self,path,data):
        with Path(path).open('xb') as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        return self.files.fingerprint(path)
    def publish(self,path,value):return self.write_bytes(path,(json.dumps(value,allow_nan=False)+'\n').encode())
    def show(self,unit):
        o=self.owner
        return dict(MainPID=str(o['pid']),InvocationID=o['invocation_id'],ControlGroup=o['cgroup'],ActiveState='active',SubState='running',Restart='no'),{}
    def process_start(self,pid):return self.owner['starttime_ticks']
    def command(self,argv):
        assert argv==['systemctl','--user','cat',self.owner['unit']]
        return dict(argv=argv,returncode=0,stdout='[Service]\nRestart=no\n',stderr='')
    def current_ce_and_resources(self,*args):
        self.health_calls+=1
        o=copy.deepcopy(self.owner)
        if self.health_calls>1 and self.changed_owner:o['pid']+=1
        return dict(owner=o,source_control_hashes=self.hashes),self.raw


class CaptureGuards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.game=self.root/'Robotron';self.run=self.root/'run26'
        self.run.mkdir();(self.game/'models_dqn/managed-checkpoints').mkdir(parents=True)
        (self.game/'Scripts/dqn').mkdir(parents=True)
        self.patchers=[mock.patch.object(m,'GAME',self.game),mock.patch.object(m,'RUN',self.run)]
        for p in self.patchers:p.start();self.addCleanup(p.stop)
        self.ops=Ops();self.files=self.ops.files
        self.owner=dict(pid=123,starttime_ticks=456,unit='test.service',invocation_id='a'*32,cgroup='/test.service')
        self.ops.owner=self.owner
        self.clocks=dict(training_steps=10,optimized_samples=40960,learner_frame_count=30000,frame_count=60000)
        api=dict(self.clocks,client_count=192,training_enabled=True,measurement_active=False,
            host_pipeline={'learning_exposure':{'optimizer':{'process_id':123}}},last_grad_norm=float('nan'))
        self.ops.raw=json.dumps(api).encode()
        self.ops.hashes={}
        for name in m.SOURCE_NAMES:
            p=self.game/'Scripts/dqn'/name;p.write_text('# small synthetic source\n')
            self.ops.hashes[str(p)]=self.files.fingerprint(p)['sha256']
        ctl=self.game/'models_dqn/learning_control.json';ctl.write_text(json.dumps({'experiment':'test','lr_scale':.5}))
        self.ops.hashes[str(ctl)]=self.files.fingerprint(ctl)['sha256']
        boot=self.ops.publish(self.run/'boot-proof.json',dict(status='PASS',sha256='b'*64,bytes=99,clocks=self.clocks))
        record=self.ops.publish(self.run/'record.json',dict(metric='ce'))
        phase=dict(record=record,boot_checkpoint=dict(path=str(self.game/'models_dqn/robotron_dqn_latest.pt'),sha256='b'*64,bytes=99),boot_verification=boot,
            expected=dict(metric='ce',phase_id='ce_phase',root_precommit_sha256='c'*64,founder_phase_record_sha256=record['sha256'],last_resume_record_sha256=None,
                started_from=dict(path=str(self.game/'models_dqn/robotron_dqn_latest.pt'),sha256='b'*64,bytes=99,clocks=self.clocks),valid=True))
        history={
            # Authentic187c outer job has no experiment; activation job owns it.
            'outer_job':self.ops.publish(self.run/'outer.json',{'schema':'synthetic-one-trial-job'}),
            'activation_job':self.ops.publish(self.run/'activation-job.json',{'experiment':'test'}),
            'activation':self.ops.publish(self.run/'activation.json',{}),
            'CE_return':self.ops.publish(self.run/'CE-return.json',dict(status='READY',owner=self.owner,manual_recovery_required=False,startup_phase_proof={'phase':phase})),
        }
        cleanup=self.ops.publish(self.run/'cleanup.json',dict(status='PASS_ORIGINAL_QUALITY_ARCHIVED_OWNED_CLEANUP_COMPLETE',owned_cleanup_complete=True))
        release=self.ops.publish(self.run/'release.json',dict(schema='robotron-quality-campaign-root-source-freeze-release-v1',status='PASS',source_freeze_released=True,actual_quality_cleanup=m.triple(cleanup)))
        self.job=dict(schema=m.SCHEMA,experiment='test',model_dir=str(self.game/'models_dqn'),output_directory=str(self.run/'capture-output'),tag='new-candidate',startup_tag='old-startup',save_timeout_s=60,
            expected_owner=self.owner,root_release=dict(source_freeze_released=True,quality_cleanup=cleanup,freeze_release=release),history=history,cpu_python='/root-verified/venv/bin/python')
        self.jp=self.ops.publish(self.run/'job.json',self.job)
        # The real Snapshot is stdlib only. No resource module, transition, torch or model import.
        self.snap=m.load_module(m.DEPENDENCIES['snapshot'][0],'real_snapshot_for_capture_fixture')
        self.metadata_checks=[]
        outer=self
        class Strict:
            MODEL_NAMES=('model.py','config.py','learning_control.py','__init__.py')
            HELD_RECIPE_CONTEXT={}
            def check_context(self,job,evidence):outer.metadata_checks.append(('context',job));return Path(job['source_control_context']['model_dir'])
        def check_acquisition(job,strict,evidence,model):
            assert job['phase_snapshot']['purpose']=='candidate' and job['phase_snapshot']['expected_phase']['metric']=='ce'
            outer.metadata_checks.append(('acquisition',job))
        self.phase=SimpleNamespace(SCHEMA='robotron-phase-snapshot-checkpoint-CPU-job-v1',STRICT_SHA256='d'*64,ORIGINAL_SHA256='e'*64,load_base=Strict,check_acquisition=check_acquisition)

    def consume(self,_):
        model=Path(self.job['model_dir']);request=model/'managed_save.request.json'
        if request.exists():
            (model/'managed-checkpoints/new-candidate.pt').write_bytes(b'synthetic fixture, never a Torch payload')
            os.replace(request,model/'managed_save.request.json.completed')

    def call(self):
        with mock.patch.object(m.time,'sleep',side_effect=self.consume):
            return m.run(self.job,self.jp,self.ops,self.snap,self.phase,self.files)

    def test_literal_plan_never_reads_or_loads_helpers(self):
        with mock.patch.object(m.Files,'fingerprint',side_effect=AssertionError('read')),mock.patch.object(m,'load_module',side_effect=AssertionError('load')):
            self.assertEqual(m.main([]),0)

    def test_small_owned_copy_readonly_independent_and_no_overwrite(self):
        p=self.root/'metadata.json';p.write_text('{"x":1}')
        a,b=self.files.exclusive_copy(p,self.root/'copied.json')
        self.assertEqual(a['sha256'],b['sha256']);self.assertNotEqual(a['identity']['inode'],b['identity']['inode']);self.assertEqual(b['identity']['mode'],'0o444')
        with self.assertRaises(FileExistsError):self.files.exclusive_copy(p,self.root/'copied.json')
        os.link(p,self.root/'alias.json')
        with self.assertRaises(RuntimeError):self.files.fingerprint(p)

    def test_immediate_completion_is_exact_original_request_inode(self):
        model=Path(self.job['model_dir']);seen=[];link=os.link
        def immediate(src,dst,**kw):
            link(src,dst,**kw);os.replace(dst,model/'managed_save.request.json.completed')
        with mock.patch.object(m.os,'link',side_effect=immediate):
            pending=m.publish_request(self.files,model,self.root/'request-archive.json','unique',seen.append)
        completed=self.files.fingerprint(model/'managed_save.request.json.completed')
        self.assertIs(pending,seen[0]);self.assertEqual(m.request_identity(completed['identity']),m.request_identity(pending['pin']['identity']))
        self.assertEqual(pending['archive']['identity']['mode'],'0o444');self.assertTrue(pending['publication']['published'])

    def test_whole_capture_wiring_emits_only_pending_cpu_and_authentic_nan(self):
        result=self.call();self.assertEqual(result['status'],'CAPTURED_PENDING_CPU');self.assertIsNone(result['candidate_clocks']);self.assertIsNone(result['cpu_verification'])
        self.assertEqual(Path(result['trigger_API']['path']).read_bytes(),self.ops.raw)
        self.assertEqual(result['current_phase']['expected']['started_from']['sha256'],'b'*64)
        self.assertNotEqual(result['current_phase']['boot_verification']['path'],str(self.run/'boot-proof.json'))
        job=self.files.read_json(result['cpu_job']);self.assertEqual(job['phase_snapshot']['observed_clients'],192);self.assertEqual(job['clock_floor'],self.clocks)
        self.assertEqual([x[0] for x in self.metadata_checks],['context','acquisition'])
        completion=self.files.read_json(result['capture_completion']);self.assertEqual(completion['status'],'COMPLETE');self.assertEqual(len(completion['request_publication']),1)
        self.assertFalse((Path(self.job['output_directory'])/'phase-CPU-output').exists())

    def test_freeze_release_refusal_happens_before_output_or_request(self):
        self.job['root_release']['source_freeze_released']=False
        with self.assertRaises(RuntimeError):self.call()
        self.assertFalse(Path(self.job['output_directory']).exists());self.assertFalse((Path(self.job['model_dir'])/'managed_save.request.json').exists())

    def test_foreign_completed_same_tag_does_not_substitute_request(self):
        runtime=m.CaptureRuntime(self.ops,self.files,self.job,self.owner,self.ops.hashes)
        adapter=SimpleNamespace(four=m.four,triple=m.triple,request_identity=m.request_identity,publish_request=m.publish_request)
        self.files.api=json.loads(self.ops.raw);self.files.raw_api=self.ops.raw
        s=self.snap.Snapshot(adapter,self.files,runtime,{'tag':'new-candidate','save_timeout_s':60},self.root/'snapshot')
        s.start(self.files.api,self.clocks)
        model=Path(self.job['model_dir']);(model/'managed_save.request.json').unlink()
        self.ops.publish(model/'managed_save.request.json.completed',{'tag':'new-candidate'})
        self.assertEqual(s.tick()['status'],'FAILED')
        with self.assertRaises(RuntimeError):s.freeze(purpose='candidate',phase={})
        with self.assertRaises(RuntimeError):s.start(self.files.api,self.clocks)

    def test_late_owner_change_retains_candidate_and_failure_without_cpu_job(self):
        self.ops.changed_owner=True
        with self.assertRaises(RuntimeError):self.call()
        out=Path(self.job['output_directory']);self.assertEqual(json.loads((out/'result.json').read_text())['status'],'FAILED')
        self.assertTrue((Path(self.job['model_dir'])/'managed-checkpoints/new-candidate.pt').exists());self.assertFalse((out/'phase-CPU-job.json').exists())

    def test_original_boot_proof_hash_mismatch_fails_without_cpu_job(self):
        ce=self.files.read_json(self.job['history']['CE_return']);ce['startup_phase_proof']['phase']['boot_verification']['sha256']='f'*64
        self.job['history']['CE_return']=self.ops.publish(self.run/'bad-CE-return.json',ce)
        with self.assertRaises(RuntimeError):self.call()
        self.assertFalse((Path(self.job['output_directory'])/'phase-CPU-job.json').exists())


if __name__=='__main__':unittest.main()
