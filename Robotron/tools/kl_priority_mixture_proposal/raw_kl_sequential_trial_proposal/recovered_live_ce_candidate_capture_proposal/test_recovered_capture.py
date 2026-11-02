"""Source-authored stdlib boundary guards; no author execution/import."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('recovered_capture_guards',HERE/'capture_live_CE_candidate.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Fixture:
    def __init__(self,root):
        self.root=root;self.files=m.Files(self);self.game=root/'Robotron';self.run=root/'run26'
        self.run.mkdir();(self.game/'models_dqn').mkdir(parents=True)
        self.owner=dict(pid=123,starttime_ticks=456,unit='trainer.service',invocation_id='a'*32,cgroup='/trainer.service')
        self.clocks=dict(training_steps=10,optimized_samples=40960,learner_frame_count=200,frame_count=400)
        boot=dict(path=str(self.game/'models_dqn/robotron_dqn_latest.pt'),sha256='b'*64,bytes=123)
        bp=self.publish(self.run/'boot.json',dict(status='PASS',sha256=boot['sha256'],bytes=boot['bytes'],clocks=self.clocks))
        intent=self.publish(self.run/'intent.json',{'recovery':'genuine synthetic fixture'})
        record=dict(action='start',metric='ce',previous_metric='ce',phase_id='new_CE',checkpoint=boot,root_precommit_sha256=intent['sha256'])
        rp=self.publish(self.run/'record.json',record)
        expected=dict(metric='ce',phase_id='new_CE',root_precommit_sha256=intent['sha256'],founder_phase_record_sha256=rp['sha256'],last_resume_record_sha256=None,started_from=dict(boot,clocks=self.clocks),valid=True)
        phase=dict(record=rp,boot_checkpoint=boot,boot_verification=bp,expected=expected)
        saved=dict(metric='ce',phase_id='new_CE',root_precommit_sha256=intent['sha256'],phase_record_sha256=rp['sha256'],last_resume_record_sha256=None,started_from=expected['started_from'],valid=True)
        cpu=dict(status='PASS',phase_metadata_verified=True,held_recipe_context={'batch_size':4096},root_job={'phase_snapshot':dict(owner=self.owner,observed_clients=0,phase_record=rp,expected_phase=expected)},saved_priority_metric_phase=saved)
        cp=self.publish(self.run/'startupCPU.json',cpu)
        actors=[{'pid':1000+i} for i in range(192)]
        original=dict(bindings=dict(actors=actors,source_hashes={'source.py':'held'},control_hashes={'control.json':'held'}),fleet={'MainPID':'42'},supervisor_start_ticks=7)
        anchor=copy.deepcopy(original);anchor['environment']=dict(DQN_BATCH_SIZE='4096',DQN_PER_PRIORITY_METRIC='ce',DQN_PRIORITY_PHASE_RECORD=rp['path'],DQN_PRIORITY_PHASE_RECORD_SHA256=rp['sha256'])
        activation=self.publish(self.run/'activation.json',dict(experiment='branch',before=original,actor_masks={str(a['pid']):list(range(72)) for a in actors},worker_mask=list(range(72)),fleet_unit='fleet.service'))
        self.repair=dict(activation_job=activation,startup_tag='startup',phase_id='new_CE',repair_intent=intent)
        jp=self.publish(self.run/'repair-job.json',self.repair)
        self.rec=dict(status='READY_CE_FORWARD_REPAIR',original_trial_failed=True,trial_retried=False,manual_recovery_required=False,recovery_target_batch_size=4096,qualification_pass=False,root_job=jp,owner=self.owner,startup=dict(phase=phase,phase_CPU_readonly_archive=cp),boot_checkpoint={'source':boot},healthy192={'binding':anchor},final_resume=dict(all_matching_actors_resumed=True,failures=[]))
        result=self.publish(self.run/'recovery.json',self.rec)
        release=dict(status='PASS',result=result,owner=self.owner,original_exit=0,original_exec_code=1,original_result='success',original_archived_before_release=True,unit_released=True,actual_startup_CPU=cp,owned_release=[dict(unit='repair.timer',returncode=0,final_LoadState='not-found'),dict(unit='repair.service',returncode=0,final_LoadState='not-found')])
        rel=self.publish(self.run/'repair-release.json',release)
        clean=self.publish(self.run/'cleanup.json',dict(status='PASS_ORIGINAL_QUALITY_ARCHIVED_OWNED_CLEANUP_COMPLETE',owned_cleanup_complete=True))
        fr=dict(status='PASS_ROOT_EXPLICIT_CURRENT_CE543M_SOURCE_FREEZE_RELEASE',source_freeze_released=True,owned_cleanup_complete=True,actual_owned_closure=clean,actual_plan_sha256='25aaded11bf956b715cc5fb58be1901d236a30444e74253594461f8d11c00d75',current_campaign='quality-448M-vs-CE543M-20261017',all69_original_owned_processes_absent=True,original_parent_exit=0,original_audit_exits_preserved=[0,2,0,0])
        self.job=dict(schema=m.SCHEMA,experiment='branch',model_dir=str(self.game/'models_dqn'),output_directory=str(self.run/'capture'),tag='candidate',startup_tag='startup',save_timeout_s=60,expected_owner=self.owner,root_release=dict(source_freeze_released=True,quality_cleanup=clean,freeze_release=self.publish(self.run/'freeze.json',fr)),recovery=dict(result=result,job=jp,release=rel),cpu_python='/verified/python')
    def write_bytes(self,path,data):
        with Path(path).open('xb') as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        return self.files.fingerprint(path)
    def publish(self,path,value):return self.write_bytes(path,(json.dumps(value,allow_nan=False)+'\n').encode())
    def changed_result(self,mutate,name):
        rec=copy.deepcopy(self.rec);mutate(rec);job=copy.deepcopy(self.job);job['recovery']['result']=self.publish(self.run/name,rec)
        release=self.files.read_json(job['recovery']['release']);release['result']=job['recovery']['result'];job['recovery']['release']=self.publish(self.run/('release-'+name),release)
        return job

class RecoveredCaptureContracts(unittest.TestCase):
    def fixture(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);return Fixture(Path(t.name))
    def test_actual_forward_repair_shape_and_CE_predecessor_not_old_READY_alias(self):
        f=self.fixture();c=m.recovery_context(f.job,f.files)
        self.assertEqual(c['recovery']['status'],'READY_CE_FORWARD_REPAIR');self.assertEqual(c['phase']['expected']['metric'],'ce');self.assertNotIn('healthy',f.rec);self.assertNotIn('startup_phase_proof',f.rec)
        for key,value in [('status','READY'),('trial_retried',True),('owner',dict(f.owner,pid=999))]:
            job=f.changed_result(lambda x,k=key,v=value:x.update({k:v}),key+'.json')
            with self.assertRaises(RuntimeError):m.recovery_context(job,f.files)
        rec=f.files.read_json(f.rec['startup']['phase']['record']);rec['previous_metric']='kl';bad=copy.deepcopy(f.job)
        rp=f.publish(f.run/'wrong-predecessor.json',rec)
        bad=f.changed_result(lambda x:x['startup']['phase'].update(record=rp),'wrong-phase.json')
        with self.assertRaises(RuntimeError):m.recovery_context(bad,f.files)
    def test_actual_c1ab_release_shape_reaches_recovery_before_output_or_request(self):
        f=self.fixture()
        class Reached(Exception):pass
        with patch.object(m,'GAME',f.game),patch.object(m,'RUN',f.run),patch.object(m,'recovery_context',side_effect=Reached):
            with self.assertRaises(Reached):m.run(f.job,{},None,None,None,f.files)
            self.assertFalse(Path(f.job['output_directory']).exists())
            wrong=f.files.read_json(f.job['root_release']['freeze_release']);wrong['original_audit_exits_preserved']=[0,0,0,0]
            job=copy.deepcopy(f.job);job['root_release']['freeze_release']=f.publish(f.run/'wrong-freeze.json',wrong)
            with self.assertRaises(RuntimeError):m.run(job,{},None,None,None,f.files)
        self.assertFalse((f.game/'models_dqn/managed_save.request.json').exists())
    def test_wrong_source_and_current_phase_environment_refuse(self):
        f=self.fixture()
        for kind in ('source_hashes','control_hashes'):
            job=f.changed_result(lambda x,k=kind:x['healthy192']['binding']['bindings'][k].update({'foreign':'new'}),kind+'.json')
            with self.assertRaises(RuntimeError):m.recovery_context(job,f.files)
        job=f.changed_result(lambda x:x['healthy192']['binding']['environment'].update(DQN_BATCH_SIZE='2048'),'wrong-env.json')
        with self.assertRaises(RuntimeError):m.recovery_context(job,f.files)
    def test_literal_default_and_original_capture_primitives_resource_tail_preserved(self):
        with patch.object(m,'load_module',side_effect=AssertionError('helper import')),patch.object(Path,'read_bytes',side_effect=AssertionError('read')):self.assertEqual(m.main([]),0)
        def function(path,name):
            s=path.read_text();n=next(n for n in ast.parse(s).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name);return ast.get_source_segment(s,n)
        old=HERE.parent/'live_ce_candidate_capture_helper_proposal/capture_live_CE_candidate.py'
        for name in ('four','triple','request_identity','publish_request','Files','Signals','CaptureRuntime','sealed'):
            self.assertEqual(function(old,name),function(HERE/'capture_live_CE_candidate.py',name))
        source=m.DEPENDENCIES['resources'][0];a=function(source,'current_ce_and_resources');a=a[a.index('    masks = '):]
        a=a.replace("activation_job['actor_masks']","context['actor_masks']").replace("activation_job['worker_mask']","context['worker_mask']").replace("activation_job['fleet_unit']","context['fleet_unit']").replace("activation['installed_sources']","binding['bindings']['source_hashes']")
        b=function(HERE/'capture_live_CE_candidate.py','current_ce_and_resources');self.assertEqual(a,b[b.index('    masks = '):])

if __name__=='__main__':unittest.main()
