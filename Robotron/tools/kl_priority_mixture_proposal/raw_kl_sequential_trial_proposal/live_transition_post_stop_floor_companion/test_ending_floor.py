"""Authored/unexecuted metadata and real-transition-body guards; no model/runtime."""
import contextlib
import copy
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch

from . import run_raw_kl_transition as adapter
from ..sequential_trial_precommit_proposal.horizon_observer_proposal import horizon_observer as horizon
from ..sequential_trial_precommit_proposal.horizon_observer_proposal import test_horizon_observer as fixtures


def pin(path,sha='a'*64,inode=10):
    return dict(path=path,sha256=sha,bytes=275181008,identity=dict(device=1,inode=inode,
        bytes=275181008,mtime_ns=1,ctime_ns=2,mode='0o444',uid=adapter.os.getuid(),nlink=1))


def metadata_case():
    observer=fixtures.job_at();raw=fixtures.api_at(100,learner=8000000,physical=6000000)
    decision=horizon.HorizonObserver(observer).observe(raw,observer['owner'],dict(ok=True),fixtures.clock(100))
    source=pin('/models/managed-checkpoints/one_candidate.pt');copied=pin('/root-proof/candidate.pt',inode=11)
    boot=dict(path='/models/robotron_dqn_latest.pt',sha256='b'*64,bytes=275181008)
    acquisition=dict(schema='robotron-owned-phase-snapshot-acquisition-v1',purpose='candidate',experiment='trial',
        owner_before=observer['owner'],owner_after=observer['owner'],model_dir='/models',
        source_checkpoint=adapter.triple(source),tag='one_candidate',clock_floor=adapter.four(raw),
        phase_record_sha256='c'*64,boot_checkpoint=boot,client_count=0,stopped_absence=None)
    def historical(path,archive):
        actual=pin(path);actual['identity'].update(mtime_ns=1,ctime_ns=2)
        return dict(actual_pin=actual,archive=pin(archive,inode=12))
    acquisition['completed_slot_transition']=dict(before=None,
        request=historical('/models/managed_save.request.json','/request-archive'),
        after=historical('/models/managed_save.request.json.completed','/completed-archive'),
        before_unix_s=1,request_unix_s=2,after_unix_s=3)
    records={
        '/observer-job':observer,
        '/activation':dict(status='READY',manual_recovery_required=False,qualification_pass=False,
            owner=copy.deepcopy(observer['owner']),trial_core=dict(sha256=observer['trial_core_sha256']),
            boot_four_clocks=copy.deepcopy(observer['boot_four_clocks']),healthy192_monotonic_s=observer['healthy192_monotonic_s'],
            start_request=dict(path='/start-request'),before_resume_api_PIN=dict(path='/before-resume')),
        '/start-request':copy.deepcopy(observer['start_request']),
        '/before-resume':copy.deepcopy(observer['before_resume_api']),
        '/request-archive':dict(tag='one_candidate'),'/completed-archive':dict(tag='one_candidate'),
        '/decision':decision,
        '/insurance':dict(clocks=copy.deepcopy(observer['boot_four_clocks']),root_job=dict(insurance=dict(trainer=copy.deepcopy(observer['owner']),tag='early_insurance'))),
        '/candidate-acquisition':acquisition}
    job=dict(mode='return_ce',model_dir='/models',experiment='trial',startup_tag='newCE_startup',
        helper_pins=dict(ancestor_adapter=dict(path=str(adapter.ANCESTOR),sha256=adapter.ANCESTOR_SHA),
            horizon=dict(path=str(adapter.HORIZON),sha256=adapter.HORIZON_SHA)),
        insurance_verification=dict(path='/insurance'),
        running_phase=dict(expected=dict(root_precommit_sha256=observer['trial_core_sha256']),
            record=dict(sha256='c'*64),boot_checkpoint=boot),
        ending_proof=dict(observer_job=dict(path='/observer-job'),
            activation_receipt=dict(path='/activation',sha256=observer['activation_receipt_sha256']),
            decision=dict(path='/decision'),candidate=dict(source=source,verification_copy=copied,
                acquisition=dict(path='/candidate-acquisition'))))
    base=SimpleNamespace(MAX_SOURCE=1<<20,Runtime=type('MockBaseRuntime',(),{}),pin=lambda *args:None,
        read_json=lambda value:copy.deepcopy(records[value['path']]),
        load_module=lambda *args:horizon)
    return job,base,records


class EndingMetadataContracts(unittest.TestCase):
    def test_latch_binds_actual_original_owner_origin_and_candidate_floor(self):
        job,base,records=metadata_case();ending=adapter.validate_ending(job,base)
        self.assertEqual(ending['state'],'LATCH')
        self.assertEqual(ending['floor'],adapter.four(records['/decision']['first_eligible_observation']))
        self.assertEqual(ending['candidate'],job['ending_proof']['candidate'])
        records['/candidate-acquisition']['client_count']=192
        self.assertEqual(adapter.validate_ending(job,base)['state'],'LATCH')
        # No candidate PT file exists; pure validation never opens/stat/hashes it.

    def test_owner_boot_core_or_latch_time_mismatch_refused(self):
        for issue in ('owner','boot','core','time','horizon','baseline'):
            job,base,records=metadata_case()
            if issue=='owner':records['/activation']['owner']['starttime_ticks']+=1
            if issue=='boot':records['/start-request']['boot_id']='other'
            if issue=='core':records['/activation']['trial_core']['sha256']='d'*64
            if issue=='time':records['/decision']['elapsed_s']=3241
            if issue=='horizon':records['/decision']['progress']['physical_accepted']-=1
            if issue=='baseline':records['/before-resume']['training_steps']+=1
            with self.subTest(issue=issue),self.assertRaises((RuntimeError,ValueError)):
                adapter.validate_ending(job,base)

    def test_candidate_must_be_distinct_owned_copy_and_exact_acquisition(self):
        for issue in ('alias','writable','tag','floor','phase','clients','absence','transition','completed_tag'):
            job,base,records=metadata_case();candidate=job['ending_proof']['candidate']
            if issue=='alias':candidate['verification_copy']['identity']['inode']=candidate['source']['identity']['inode']
            if issue=='writable':candidate['verification_copy']['identity']['mode']='0o644'
            if issue=='tag':records['/candidate-acquisition']['tag']='early_insurance'
            if issue=='floor':records['/candidate-acquisition']['clock_floor']['training_steps']-=1
            if issue=='phase':records['/candidate-acquisition']['phase_record_sha256']='d'*64
            if issue=='clients':records['/candidate-acquisition'].pop('client_count')
            if issue=='absence':records['/candidate-acquisition']['stopped_absence']={}
            if issue=='transition':records['/candidate-acquisition']['completed_slot_transition']['after_unix_s']=1
            if issue=='completed_tag':records['/completed-archive']['tag']='other'
            with self.subTest(issue=issue),self.assertRaises(RuntimeError):adapter.validate_ending(job,base)

    def test_incomplete_cannot_invent_a_candidate_and_activation_has_no_ending(self):
        job,base,records=metadata_case();event=records['/decision']
        event.update(state='INCOMPLETE',terminal_observation=event.pop('first_eligible_observation'))
        event.update(elapsed_s=3241,observed_monotonic_s=4241)
        event.pop('candidate_requests_allowed');job['ending_proof']['candidate']=None
        self.assertIsNone(adapter.validate_ending(job,base)['candidate'])
        event.update(elapsed_s=100,observed_monotonic_s=1100)
        with self.assertRaises(RuntimeError):adapter.validate_ending(job,base)
        event.update(elapsed_s=3241,observed_monotonic_s=4241)
        job['ending_proof']['candidate']={}
        with self.assertRaises(RuntimeError):adapter.validate_ending(job,base)
        job['mode']='activate_kl';job['ending_proof']=None
        self.assertIsNone(adapter.validate_ending(job,base))


class PostStopOrderContracts(unittest.TestCase):
    def case(self,problem=None):
        job,base,records=metadata_case();ending=adapter.validate_ending(job,base)
        calls=[];owner=ending['owner'];actors=[dict(pid=1),dict(pid=2)]
        candidate_clocks=copy.deepcopy(ending['floor']);candidate_clocks['training_steps']+=1
        candidate_clocks['optimized_samples']+=4096;candidate_clocks['frame_count']+=10;candidate_clocks['learner_frame_count']+=10
        latest_clocks=copy.deepcopy(candidate_clocks)
        if problem=='stale_latest':latest_clocks=copy.deepcopy(ending['floor'])
        base.fingerprint=lambda *args:None;base.publish=lambda p,v:dict(path=str(p))
        records['/latest-CPU']=dict(clocks=latest_clocks)
        kind=adapter.runtime_class(base);runtime=kind.__new__(kind)
        runtime.job=dict(job,before=dict(bindings=dict(actors=actors)),trainer_unit=owner['unit'],bank_spec={},
            trial_core=dict(sha256='e'*64));runtime.output=Path('/fake-new-output')
        runtime.ending=ending;runtime.insured=owner;runtime.retired_owner=owner
        runtime.floor=copy.deepcopy(records['/insurance']['clocks']);runtime.cpu_attempts={};runtime.pending=None
        runtime.start_request=None;runtime.record={};runtime.record_pin={}
        runtime.metrics=SimpleNamespace(block_restore_signals=contextlib.nullcontext)
        runtime.static=lambda:None
        def absent():calls.append('absence')
        runtime.absence=absent
        sentinel=RuntimeError('candidate first CPU failed')
        def candidate_cpu(*args):
            calls.append('candidateCPU');runtime.cpu_attempts['candidate']='started'
            if problem=='candidate_fail':raise sentinel
            runtime.cpu_attempts['candidate']='passed';return dict(path='/candidate-CPU'),dict(clocks=candidate_clocks)
        runtime.cpu_phase=candidate_cpu
        class Host:
            known_trainer=object();paused=[]
            def begin_transition_logs(self,*args):pass
            def pause(self,*args):self.paused=list(actors)
            def signal_actor(self,actor,sig):calls.append('resume'+str(actor['pid']))
        runtime.host=Host()
        runtime.initial=lambda:dict(bindings=dict(logs=[]),trainer_stdout={})
        runtime.trainer_id=lambda:owner
        def stop(*args):calls.append('stop');return owner
        runtime.stop_owned=stop
        def latest(*args):
            calls.append('latestCPU')
            if not all(latest_clocks[key]>=runtime.floor[key] for key in adapter.CLOCKS):raise RuntimeError('latest predates candidate')
            return dict(source={},verification=dict(path='/latest-CPU'))
        runtime.stopped_checkpoint=latest
        runtime.banks=SimpleNamespace(stopped_state=lambda *a:{},assert_unchanged=lambda *a:None)
        runtime.ready_transport=lambda *a,**k:{}
        def start():calls.append('CEstart');runtime.start_request=dict(path='/new-CE-start');return owner
        runtime.start_phase=start
        runtime.raw_api=lambda:dict(fixtures.api_at(),client_count=192 if 'resumed' in calls else 0)
        # The real raw API helper fixture's process123 equals this owner.
        runtime.startup_snapshot=lambda raw:{}
        runtime.inspect=lambda phase:{};runtime.expected_sources=lambda phase:{}
        class Sources:
            entries=[];staged={}
            def stage(self):pass
            def reconcile(self,*args):pass
        def resume(host):
            for actor in host.paused:host.signal_actor(actor,None)
            host.paused=[];calls.append('resumed');return dict(failures=[])
        base.resume_all=resume
        result,primary=adapter.transition(runtime,Sources(),base)
        return result,primary,calls,runtime,sentinel,candidate_clocks

    def test_stop_candidate_latest_CE_order_and_stronger_floor(self):
        result,primary,calls,runtime,_,candidate=self.case()
        self.assertEqual(result['status'],'READY');self.assertIsNone(primary)
        self.assertLess(calls.index('stop'),calls.index('candidateCPU'))
        self.assertLess(calls.index('candidateCPU'),calls.index('latestCPU'))
        self.assertLess(calls.index('latestCPU'),calls.index('CEstart'))
        self.assertEqual(runtime.floor,candidate)

    def test_candidate_first_CPU_failure_is_fatal_no_latest_or_CE_or_retry(self):
        result,primary,calls,runtime,sentinel,_=self.case('candidate_fail')
        self.assertIs(primary,sentinel);self.assertEqual(result['status'],'FAILED')
        self.assertEqual(calls.count('candidateCPU'),1)
        self.assertNotIn('latestCPU',calls);self.assertNotIn('CEstart',calls)
        self.assertEqual(runtime.cpu_attempts['candidate'],'started')
        self.assertIn('resume1',calls);self.assertIn('resume2',calls)

    def test_latest_covering_latch_but_before_candidate_never_starts_CE(self):
        result,primary,calls,runtime,_,_=self.case('stale_latest')
        self.assertEqual(result['status'],'FAILED');self.assertIn('predates candidate',str(primary))
        self.assertEqual(calls.count('candidateCPU'),1);self.assertEqual(calls.count('latestCPU'),1)
        self.assertNotIn('CEstart',calls);self.assertTrue(result['manual_recovery_required'])


if __name__=='__main__':unittest.main()
