"""Source-authored stdlib contracts only; no runtime/model/numerical fixtures."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import run_raw_kl_transition as adapter


def identity(value):
    return dict(device=value.st_dev,inode=value.st_ino,bytes=value.st_size,mtime_ns=value.st_mtime_ns,
        ctime_ns=value.st_ctime_ns,mode=oct(value.st_mode&0o777),uid=value.st_uid,nlink=value.st_nlink)


def fingerprint(path,limit=None):
    path=Path(path);before=identity(path.stat());data=path.read_bytes()
    if limit is not None:assert len(data)<=limit
    assert identity(path.stat())==before
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),identity=before)


def exclusive_copy(source,destination):
    source=Path(source);destination=Path(destination);before=fingerprint(source)
    with destination.open('xb') as out:out.write(source.read_bytes());out.flush();os.fsync(out.fileno())
    destination.chmod(0o444);assert fingerprint(source)==before
    return before,fingerprint(destination)


def fake_base():
    return SimpleNamespace(identity=identity,exclusive_copy=exclusive_copy,fsync_directory=lambda p:None,
        fingerprint=fingerprint,read_json=lambda p:json.loads(Path(p['path']).read_text()),publish=lambda p,v:None,
        Runtime=type('UnusedRuntime',(),{}))


def raw_api(pid=123,clients=0):
    replay=dict(available=True,process_id=pid,instance_monotonic_ns=99,epoch=1,epoch_reason='loaded',
        accepted_by_source_total=dict(dqn=0,epsilon=0,expert=0,eval=0,unattributed=0),accepted_total=0,accepted_learner_total=0)
    return dict(training_steps=10,optimized_samples=100,learner_frame_count=1000,frame_count=2000,client_count=clients,
        host_pipeline=dict(learning_exposure=dict(optimizer=dict(process_id=pid),replay=replay)))


class TransitionContracts(unittest.TestCase):
    def test_literal_default_does_not_load_or_read_helpers(self):
        with (patch.object(adapter,'load_v4',side_effect=AssertionError('no helper')),
                patch.object(Path,'read_bytes',side_effect=AssertionError('no reads')),
                contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(adapter.main([]),0)

    def test_expected_environment_removes_both_capture_flags_and_binds_static_record(self):
        before=dict(DQN_RECOMPUTED_CE_CAPTURE_DIR='/old/completed8',DQN_EXECUTED_CE_TRACE_DIR='/old',DQN_BATCH_SIZE='4096')
        expected=adapter.selected_environment(before,'ce',dict(path='/owned/new.json',sha256='a'*64))
        self.assertTrue(all(x not in expected for x in adapter.FLAGS));self.assertEqual(expected['DQN_BATCH_SIZE'],'4096')
        self.assertEqual(expected['DQN_PER_PRIORITY_METRIC'],'ce');self.assertEqual(before['DQN_EXECUTED_CE_TRACE_DIR'],'/old')
        with self.assertRaises(RuntimeError):adapter.selected_environment(before,'hot',{})

    def test_new_phase_uses_newest_boot_and_never_reuses_older_kl_founder(self):
        checkpoint=dict(path='/models/robotron_dqn_latest.pt',sha256='b'*64,bytes=300000000)
        proof=dict(clocks=dict(training_steps=10,optimized_samples=100,learner_frame_count=1000,frame_count=2000),
            saved_priority_metric_phase=dict(metric='kl',phase_id='original_KL',valid=True))
        record=adapter.start_record('return_ce','NEW_CE','c'*64,'/models',checkpoint,proof)
        expected=adapter.expected_start(record,dict(sha256='d'*64),proof)
        self.assertEqual((record['metric'],record['action'],record['previous_metric']),('ce','start','kl'))
        self.assertEqual(expected['started_from'],dict(checkpoint,clocks=proof['clocks']))
        self.assertIsNone(expected['last_resume_record_sha256']);self.assertEqual(record['checkpoint'],checkpoint)
        with self.assertRaises(RuntimeError):adapter.start_record('return_ce','original_KL','c'*64,'/models',checkpoint,proof)

    def test_invalid_or_absent_kl_predecessor_refuses_normal_return_without_retry(self):
        checkpoint=dict(path='/models/latest.pt',sha256='b'*64,bytes=1)
        for previous in (None,dict(metric='kl',phase_id='old',valid=False),dict(metric='ce',phase_id='old',valid=True)):
            with self.subTest(previous=previous),self.assertRaises(RuntimeError):
                adapter.start_record('return_ce','new','c'*64,'/models',checkpoint,dict(saved_priority_metric_phase=previous))

    def test_fresh_physical_all_source_zero_is_distinct_from_learner_only(self):
        value=raw_api();self.assertEqual(adapter.zero_replay(value,123)['replay']['accepted_total'],0)
        value['host_pipeline']['learning_exposure']['replay']['accepted_by_source_total']['expert']=1
        with self.assertRaises(RuntimeError):adapter.zero_replay(value,123)
        value=raw_api(pid=99)
        with self.assertRaises(RuntimeError):adapter.zero_replay(value,123)


class AtomicRequestContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.model=self.root/'models';self.model.mkdir();self.archive=self.root/'archive.json';self.base=fake_base();self.registered=[]

    def test_request_is_sealed_archived_and_registered_before_visibility(self):
        actual_link=os.link
        def link(source,destination,**kwargs):
            self.assertEqual(len(self.registered),1)
            self.assertEqual(self.archive.read_bytes(),Path(source).read_bytes())
            self.assertEqual(Path(source).stat().st_mode&0o777,0o444)
            self.assertFalse(Path(destination).exists());return actual_link(source,destination,**kwargs)
        with patch.object(adapter.os,'link',side_effect=link):
            pending=adapter.publish_request(self.base,self.model,self.archive,'startup_A',self.registered.append)
        request=self.model/'managed_save.request.json'
        self.assertEqual(json.loads(request.read_text()),dict(tag='startup_A'))
        self.assertEqual(request.stat().st_nlink,1);self.assertTrue(pending['publication']['published'])
        self.assertEqual(list(self.model.glob('.managed-phase-request-*')),[])

    def test_immediate_consumer_rename_does_not_require_request_path_to_survive(self):
        actual_link=os.link
        def consume(source,destination,**kwargs):
            actual_link(source,destination,**kwargs);os.replace(destination,str(destination)+'.completed')
        with patch.object(adapter.os,'link',side_effect=consume):
            pending=adapter.publish_request(self.base,self.model,self.archive,'startup_A',self.registered.append)
        self.assertFalse((self.model/'managed_save.request.json').exists())
        kind=adapter.runtime_class(self.base);runtime=kind.__new__(kind)
        runtime.job=dict(model_dir=str(self.model));runtime.pending=pending
        runtime.request_guard()
        completed=fingerprint(self.model/'managed_save.request.json.completed')
        self.assertEqual(adapter.request_identity(completed['identity']),adapter.request_identity(pending['pin']['identity']))

    def test_no_overwrite_of_request_that_appears_at_publication(self):
        actual_link=os.link
        def competing(source,destination,**kwargs):
            Path(destination).write_text('{"tag":"unowned"}\n');return actual_link(source,destination,**kwargs)
        with patch.object(adapter.os,'link',side_effect=competing),self.assertRaises(FileExistsError):
            adapter.publish_request(self.base,self.model,self.archive,'startup_A',self.registered.append)
        self.assertEqual(json.loads((self.model/'managed_save.request.json').read_text())['tag'],'unowned')
        self.assertFalse(self.registered[0]['publication']['published'])

    def test_same_bytes_replaced_inode_is_not_the_owned_request(self):
        pending=adapter.publish_request(self.base,self.model,self.archive,'startup_A',self.registered.append)
        path=self.model/'managed_save.request.json';replacement=self.model/'replacement'
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o444);os.replace(replacement,path)
        kind=adapter.runtime_class(self.base);runtime=kind.__new__(kind);runtime.job=dict(model_dir=str(self.model));runtime.pending=pending
        with self.assertRaises(RuntimeError):runtime.request_guard()

    def test_failed_preparation_is_registered_without_exposing_partial_request(self):
        sentinel=OSError('archive-failure')
        self.base.exclusive_copy=lambda *a:(_ for _ in ()).throw(sentinel)
        with self.assertRaises(OSError) as seen:adapter.publish_request(self.base,self.model,self.archive,'startup_A',self.registered.append)
        self.assertIs(seen.exception,sentinel);self.assertEqual(len(self.registered),1)
        self.assertFalse(self.registered[0]['publication']['published']);self.assertFalse((self.model/'managed_save.request.json').exists())

    def test_missing_request_cannot_adopt_same_tag_at_foreign_completed_inode(self):
        pending=adapter.publish_request(self.base,self.model,self.archive,'startup_A',self.registered.append)
        request=self.model/'managed_save.request.json';data=request.read_bytes()
        foreign=self.model/'foreign';foreign.write_bytes(data);foreign.chmod(0o444);request.unlink()
        completed=Path(str(request)+'.completed');os.replace(foreign,completed)
        kind=adapter.runtime_class(self.base);runtime=kind.__new__(kind)
        runtime.job=dict(model_dir=str(self.model));runtime.pending=pending
        with self.assertRaises(RuntimeError):runtime.request_guard()

    def test_current_completed_slot_is_separate_from_historical_early_insurance(self):
        slot=self.model/'managed_save.request.json.completed'
        slot.write_text('{"tag":"candidate_after_early_insurance"}\n');slot.chmod(0o444)
        kind=adapter.runtime_class(self.base);runtime=kind.__new__(kind)
        runtime.job=dict(model_dir=str(self.model));runtime.pending=None;runtime.current_completed=fingerprint(slot)
        runtime.insurance=dict(historical_completed_tag='distinct_early_insurance')
        runtime.request_guard()
        replacement=self.model/'replacement';replacement.write_bytes(slot.read_bytes());replacement.chmod(0o444)
        os.replace(replacement,slot)
        with self.assertRaises(RuntimeError):runtime.request_guard()

    def test_published_request_allows_only_old_slot_or_its_own_concurrent_completion(self):
        slot=self.model/'managed_save.request.json.completed';slot.write_text('{"tag":"early"}\n');slot.chmod(0o444)
        before=fingerprint(slot)
        pending=adapter.publish_request(self.base,self.model,self.archive,'startup_A',self.registered.append)
        kind=adapter.runtime_class(self.base);runtime=kind.__new__(kind)
        runtime.job=dict(model_dir=str(self.model));runtime.pending=pending;runtime.current_completed=before
        runtime.request_guard()
        original=self.base.fingerprint
        def complete_between_reads(path,limit=None):
            observed=original(path,limit)
            if Path(path).name=='managed_save.request.json':os.replace(path,slot)
            return observed
        with patch.object(self.base,'fingerprint',side_effect=complete_between_reads):
            # The runtime factory captured its fingerprint at class construction.
            changed_kind=adapter.runtime_class(self.base);changed=changed_kind.__new__(changed_kind)
            changed.job=runtime.job;changed.pending=pending;changed.current_completed=before
            changed.request_guard()


class ReadinessAndEvidenceContracts(unittest.TestCase):
    def readiness(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        latest=root/'robotron_dqn_latest.pt';latest.write_bytes(b'opaque-checkpoint-not-loaded')
        stdout=root/'trainer.stdout';stdout.write_text('Loaded v28 model from '+str(latest)+'\nLoaded model from: '+str(latest)+'\n')
        data=stdout.read_bytes();info=stdout.stat();calls=[]
        proof=dict(stdout=dict(path=str(stdout),device=info.st_dev,inode=info.st_ino),start_byte=0,end_byte=len(data),
            sha256=hashlib.sha256(data).hexdigest(),counts=dict(HOF=dict(episodes=2,transitions=3),EPHOF=dict(episodes=4,transitions=5)))
        raw=raw_api();raw['managed_experiment']='held';raw['host_pipeline']['inference_graphs']=dict(ready=True)
        raw['host_pipeline']['learning_exposure']['optimizer']['total']=dict(outcomes_recorded=1)
        row=dict(exposure=dict(optimizer=dict(process_id=123),replay=dict(process_id=123)))
        base=fake_base();base.boot_log_proof=adapter.load_v4().boot_log_proof
        kind=adapter.runtime_class(base);runtime=kind.__new__(kind)
        runtime.job=dict(readiness_timeout_s=600,experiment='held',baseline_csv={},bank_spec={})
        runtime.current_checkpoint=dict(source=fingerprint(latest),clocks=adapter.four(raw))
        runtime.static=lambda:None;runtime.trainer_id=lambda:dict(pid=123);runtime.raw_api=lambda:raw
        runtime.inspect=lambda phase:dict(bindings=dict(logs=[]))
        runtime.host=SimpleNamespace(bank_load_proof=lambda current:copy.deepcopy(proof))
        runtime.metrics=SimpleNamespace(compact_api=lambda value:copy.deepcopy(row),exposure_key=lambda value:value,api_issues=lambda *args:[])
        runtime.banks=SimpleNamespace(assert_unchanged=lambda *args:calls.append('headers'),
            verify_maps=lambda *args:calls.append('maps') or dict(persistent_maps=9))
        banks=dict(banks=dict(hof=dict(counts=proof['counts']['HOF']),ephof=dict(counts=proof['counts']['EPHOF'])))
        return runtime,banks,calls

    def test_real_ready_transport_reaches_qualified_load_header_and_nine_map_checks(self):
        runtime,banks,calls=self.readiness();proof=runtime.ready_transport('after',banks,actors=False)
        self.assertEqual(calls,['headers','maps'])
        self.assertEqual(proof['bank_load_proof']['model_boot']['agent_load_paths'],[runtime.current_checkpoint['source']['path']])
        self.assertEqual(proof['mapped_ring']['persistent_maps'],9)

    def test_real_ready_transport_refuses_failed_disk_header_gate_before_map_acceptance(self):
        runtime,banks,calls=self.readiness()
        runtime.banks.assert_unchanged=lambda *args:(_ for _ in ()).throw(RuntimeError('selected generation changed'))
        with self.assertRaisesRegex(RuntimeError,'generation changed'):runtime.ready_transport('after',banks,actors=False)
        self.assertEqual(calls,[])

    def test_source_failure_evidence_calls_each_entry_and_retains_only_hash_classification(self):
        entries=[dict(destination='/held/a.py'),dict(destination='/held/b.py'),dict(destination='/held/c.py')];seen=[]
        values={'/held/a.py':b'new','/held/b.py':None,'/held/c.py':b'foreign'}
        def observed(entry):seen.append(entry);return values[entry['destination']]
        sources=SimpleNamespace(entries=entries,observed=observed,
            staged={'/held/a.py':(b'old',b'new'),'/held/b.py':(None,b'new'),'/held/c.py':(b'old',b'new')})
        result=adapter.source_state(sources)
        self.assertEqual(seen,entries);self.assertEqual([x['classification'] for x in result],['known','known','unknown'])
        self.assertTrue(result[0]['matches_after']);self.assertTrue(result[1]['matches_before'])
        self.assertEqual(result[2]['sha256'],hashlib.sha256(b'foreign').hexdigest())
        json.dumps(result)  # Byte bodies cannot silently enter the failure receipt.


class FailureUndoContracts(unittest.TestCase):
    def case(self,problem):
        calls=[];actors=[dict(pid=i) for i in range(1,193)];resumed=[]
        class Host:
            known_trainer=object();paused=[]
            def begin_transition_logs(self,*args):pass
            def pause(self,*args):self.paused=list(actors)
            def wait_paused(self):pass
            def signal_actor(self,actor,sig):
                resumed.append(actor['pid'])
                if problem=='undo' and actor['pid']==1:raise OSError('SIGCONT failure')
            def unit(self,*args):return dict(MainPID='123')
        host=Host();host.paused=[]
        class Sources:
            entries=[dict(destination='/held/agent.py')]
            staged={'/held/agent.py':(b'before',b'after')}
            def stage(self):pass
            def reconcile(self,phase,*args):
                calls.append(('sources',phase))
                if problem in ('install','undo'):raise OSError('partial known installation')
            def observed(self,entry):return b'after'
        class Runtime:
            job=dict(mode='activate_kl',before=dict(bindings=dict(actors=actors)),trainer_unit='owned-test.service')
            output=Path('/private/fake-output');start_request=None;cpu_attempts={};pending=None
            metrics=SimpleNamespace(block_restore_signals=contextlib.nullcontext)
            banks=SimpleNamespace(stopped_state=lambda x:{})
            def __init__(self):self.host=host;self.job=dict(self.job,bank_spec={})
            def initial(self):return dict(bindings=dict(logs=[]),trainer_stdout={})
            def trainer_id(self):return dict(pid=123)
            def stop_owned(self,*args):calls.append(('stop',bool(self.start_request)));return dict(pid=123)
            def stopped_checkpoint(self,*args):return dict(source={},verification={},clocks={})
            def absence(self):pass
            def start_phase(self):self.start_request=dict(path='/owned/start');calls.append(('start',True));return dict(pid=123)
            def ready_transport(self,*args,**kwargs):return {}
            def raw_api(self):return raw_api()
            def startup_snapshot(self,*args):raise OSError('poststart phase evidence failure')
        base=SimpleNamespace(publish=lambda path,value:dict(path=str(path)),resume_all=adapter.load_v4().resume_all)
        runtime=Runtime();result,primary=adapter.transition(runtime,Sources(),base)
        return result,primary,calls,resumed,host

    def test_partial_install_always_attempts_all192_undo_without_starting_mixed_source(self):
        result,primary,calls,resumed,host=self.case('install')
        self.assertEqual(result['status'],'FAILED');self.assertTrue(result['manual_recovery_required'])
        self.assertEqual(resumed,list(range(1,193)));self.assertNotIn(('start',True),calls)
        self.assertEqual([x for x in calls if x[0]=='sources'],[('sources','after')])

    def test_poststart_fault_stops_only_adopted_new_owner_and_never_retries_start(self):
        result,primary,calls,resumed,host=self.case('startup')
        self.assertEqual(calls.count(('start',True)),1);self.assertEqual(calls.count(('stop',True)),1)
        self.assertEqual(resumed,list(range(1,193)));self.assertIn('failed_new_owner_stopped',result)
        self.assertEqual([x for x in calls if x[0]=='sources'],[('sources','after')])

    def test_one_undo_failure_keeps_suffix_attempts_and_unresolved_actor(self):
        result,primary,calls,resumed,host=self.case('undo')
        self.assertEqual(resumed,list(range(1,193)));self.assertEqual(host.paused,[dict(pid=1)])
        self.assertEqual(result['final_resume']['failures'][0]['pid'],1)
        self.assertTrue(result['manual_recovery_required'])


if __name__=='__main__':unittest.main()
