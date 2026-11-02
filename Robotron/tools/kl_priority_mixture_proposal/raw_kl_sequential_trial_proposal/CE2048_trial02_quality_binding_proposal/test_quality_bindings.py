"""Authored stdlib metadata/producer-route guards. Unexecuted by the author.

All fixture owners, checkpoint hashes and terminal values below are synthetic.
No fixture represents a future real candidate or returned owner.
"""
import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

b=module(HERE/'quality_bindings.py','_CE2048_quality_binding_guards')
a=module(HERE/'audit_completed_leg.py','_CE2048_quality_auditor_guards')
OWNER=dict(pid=101,starttime_ticks=102,unit='fixture.service',invocation_id='a'*32,cgroup='/fixture.service')

def pin(path,sha='f'*64,size=275200000,inode=11):
    return dict(path=path,sha256=sha,bytes=size,identity=dict(device=1,inode=inode,bytes=size,
        mtime_ns=1,ctime_ns=1,mode='0o444',uid=os.getuid(),nlink=1))

def phase():
    return dict(record=pin('/fixture/phase.json','c'*64,10),boot_checkpoint=dict(path='/fixture/latest.pt',sha256='d'*64,bytes=275200000),
        expected=dict(metric='ce',valid=True,phase_id='fixture',root_precommit_sha256='e'*64,
            founder_phase_record_sha256='c'*64,last_resume_record_sha256=None,started_from=dict(path='/fixture/latest.pt',sha256='d'*64,bytes=275200000,clocks=dict.fromkeys(b.CLOCKS,10))))

class CE2048QualityContracts(unittest.TestCase):
    def cpu(self,clients=192):
        ph=phase();source=pin(str(b.CANDIDATE));copied=pin('/fixture/copy.pt',inode=12)
        job=dict(schema=b.CPU_JOB_SCHEMA,verifier_sha256=b.PHASE_SHA,strict_phase_base_sha256=b.STRICT_SHA,
            original_strict_base_sha256=b.BASE_SHA,source=source,verification_copy=copied,clock_floor=dict.fromkeys(b.CLOCKS,10),
            batch2048_context=dict(role='candidate'),phase_snapshot=dict(purpose='candidate',owner=OWNER,observed_clients=clients,expected_phase=ph['expected']))
        saved=dict(ph['expected'],phase_record_sha256=ph['expected']['founder_phase_record_sha256'])
        proof=dict(schema=b.CPU_RESULT_SCHEMA,status='PASS',phase_metadata_verified=True,script=dict(sha256=b.PHASE_SHA),
            strict_phase_base=dict(sha256=b.STRICT_SHA),original_strict_base=dict(sha256=b.BASE_SHA),root_job=copy.deepcopy(job),
            sha256=source['sha256'],bytes=source['bytes'],path=copied['path'],source_before=b.flat(source),verification_copy=b.flat(copied),
            actual_restore_or_optimizer_step=False,actual_quality_qualification=False,configured_batch_size=2048,actual_producer_batch_size=2048,
            producer_CSV_verified=True,clocks=dict.fromkeys(b.CLOCKS,11),saved_priority_metric_phase=saved,
            job_file=dict(path='/fixture/cpu-job.json',sha256='e'*64))
        completion=dict(argv=['/fixture/python','-Xgil=0','-I','-B',str(b.PHASE),'--execute','--job',proof['job_file']['path'],
            '--expected-job-sha256',proof['job_file']['sha256'],'--expected-verifier-sha256',b.PHASE_SHA],exit_code=0)
        return job,proof,completion,dict(tag=b.TAG,path=str(b.CANDIDATE),sha256=source['sha256'],bytes=source['bytes'])

    def test_candidate_accepts_actual_zero_or192_without_coercion(self):
        for clients in (0,192):b.check_cpu(*self.cpu(clients))

    def test_candidate_rejects_legacy_wrong_role_alias_copy_and_unverified_producer(self):
        for kind in ('legacy','early','startup','count','alias','writable','producer','savedphase'):
            with self.subTest(kind=kind):
                job,proof,completion,candidate=self.cpu()
                if kind=='legacy':job['schema']='robotron-phase-snapshot-checkpoint-CPU-job-v1'
                elif kind=='early':job['batch2048_context']['role']='early_insurance'
                elif kind=='startup':job['phase_snapshot']['purpose']='startup'
                elif kind=='count':job['phase_snapshot']['observed_clients']=1
                elif kind=='alias':job['verification_copy']['identity']['inode']=11
                elif kind=='writable':job['verification_copy']['identity']['mode']='0o644'
                elif kind=='producer':proof['producer_CSV_verified']=False
                else:proof['saved_priority_metric_phase']['metric']='kl'
                proof['root_job']=copy.deepcopy(job)
                with self.assertRaises(ValueError):b.check_cpu(job,proof,completion,candidate)

    def test_original_inline_completion_exact_command_and_exit(self):
        for kind in ('extra','digest','exit','flag'):
            args=list(self.cpu());c=args[2]
            if kind=='extra':c['argv']+=['--job','/foreign.json']
            elif kind=='digest':c['argv'][-1]='0'*64
            elif kind=='exit':c['exit_code']=1
            else:c['argv'][1]='-u'
            with self.assertRaises(ValueError):b.check_cpu(*args)

    def early(self):
        job,proof,_,_=self.cpu();ph=phase();store={}
        def put(name,value):
            p=pin('/fixture/'+name,hashlib.sha256(name.encode()).hexdigest(),10,len(store)+100);store[p['path']]=value;return p
        profile=pin('/fixture/profile.json',size=10)
        job['batch2048_context']['role']='early_insurance';job['phase_snapshot'].update(phase_record=ph['record'])
        acq=put('early-acquisition.json',dict(purpose='candidate',client_count=192,tag='fixture-early',owner_before=OWNER,owner_after=OWNER))
        job['phase_snapshot']['acquisition']=acq
        jp=put('early-job.json',job);proof.update(root_job=copy.deepcopy(job),job_file=dict(path=jp['path'],sha256=jp['sha256']))
        report=put('early-report.json',proof)
        saved=put('early-saved.json',dict(role='early_insurance',tag='fixture-early',trainer=OWNER,source=job['source'],acquisition=acq))
        cpu_owner=dict(pid=301,starttime_ticks=302,unit='fixture-cpu.service',invocation_id='b'*32,cgroup='/fixture-cpu.service')
        completion=put('early-completion.json',dict(original_owner=cpu_owner,original_nrestarts=0,original_pid=301,original_invocation='b'*32,
            original_exec_code=1,original_exit=0,result='success'))
        command=['/fixture/python','-Xgil=0','-I','-B','-u',str(b.PHASE),'--execute','--job',jp['path'],
            '--expected-job-sha256',jp['sha256'],'--expected-verifier-sha256',b.PHASE_SHA]
        execution=put('early-execution.json',dict(kind='phase_early_insurance2048',unit=cpu_owner['unit'],timer='fixture-cpu.timer',
            command=command,argv=['systemd-run']+command,job=jp))
        result=put('early-result-review.json',dict(kind='phase_early_insurance2048',status='PASS',original_exec_code=1,original_exit=0,
            original_result='success',original_owner=cpu_owner,original_pid=301,original_invocation='b'*32,actual_unit=cpu_owner['unit'],
            original_archived_before_release=True,original_completion=completion,numeric_report_sha256=report['sha256'],
            releases=[dict(unit='fixture-cpu.timer'),dict(unit=cpu_owner['unit'])]))
        early=dict(schema=b.EARLY_SCHEMA,status='PASS',role='early_insurance',owner=OWNER,phase=ph,profile=profile,
            legacy_7d_insurance=False,eligible_quality_candidate=False,tag='fixture-early',python='/fixture/python',
            phase_cpu_job=jp,phase_cpu_report=report,saved_receipt=saved,frozen=dict(source=job['source'],verification_copy=job['verification_copy']),
            cpu_provenance=dict(phase_cpu_report=report,successful_execution=execution,successful_completion=completion,successful_result=result))
        return early,profile,store,proof

    def test_real_typed_early_retained_provenance_and_no_legacy_alias(self):
        early,profile,store,proof=self.early()
        self.assertEqual(b.check_early(early,profile,OWNER,phase()['record'],lambda p:store[p['path']]),proof)
        for key,value in [('legacy_7d_insurance',True),('eligible_quality_candidate',True),('role','candidate')]:
            bad=copy.deepcopy(early);bad[key]=value
            with self.assertRaises(ValueError):b.check_early(bad,profile,OWNER,phase()['record'],lambda p:store[p['path']])

    def test_early192_phase_original_exit_and_release_order_are_required(self):
        for kind in ('count','owner','exit','release'):
            early,profile,store,_=self.early()
            if kind=='count':store[early['phase_cpu_job']['path']]['phase_snapshot']['observed_clients']=0
            elif kind=='owner':early['owner']=dict(OWNER,pid=999)
            elif kind=='exit':store[early['cpu_provenance']['successful_completion']['path']]['original_exit']=1
            else:store[early['cpu_provenance']['successful_result']['path']]['releases'].reverse()
            with self.assertRaises(ValueError):b.check_early(early,profile,OWNER,phase()['record'],lambda p:store[p['path']])

    def selection(self):
        h=b.load_horizon();ph=phase();identity=dict(process_id=101,instance_monotonic_ns=3,epoch=1,epoch_reason='restore')
        def raw(learner,accepted):
            counts=dict(attempts_started=1,outcomes_recorded=1,applied=1,amp_skipped=0,unavailable=0)
            return dict(training_steps=11,optimized_samples=4096,learner_frame_count=learner,frame_count=100,
                host_pipeline=dict(learning_exposure=dict(optimizer=dict(identity,schema='robotron-optimizer-exposure-v1',enabled=True,
                    available=True,total=counts,since_epoch=counts,unclassified_started_total=0),
                    replay=dict(identity,schema='robotron-replay-insert-exposure-v1',enabled=True,available=True,accepted_total=accepted,
                        accepted_learner_total=0,accepted_by_source_total=dict(dqn=0,epsilon=0,expert=0,eval=accepted,unattributed=0)))))
        observer=dict(schema=h.SCHEMA,policy=h.POLICY,batch_size=2048,profile_binding=json.loads(h.PROFILE_BINDING_JSON),owner=OWNER,
            start_request=dict(boot_id='fixtureboot',monotonic_s=100,unix_s=1000),healthy192_monotonic_s=110,
            boot_four_clocks=dict(training_steps=10,optimized_samples=4000,learner_frame_count=100,frame_count=100),
            trial_core_sha256='e'*64,activation_receipt_sha256='f'*64,before_resume_api=raw(100,0))
        current=raw(8000100,6000000);normal=h.normalise(current)
        decision=dict(schema='robotron-ce-batch2048-horizon-observation-v1',state='LATCH',candidate_requests_allowed=1,
            qualification_pass=False,boot_id='fixtureboot',observed_monotonic_s=200,elapsed_s=100,first_eligible_observation=current,
            progress=dict(learner_frames=8000000,physical_accepted=6000000,optimizer_total=normal['optimizer']))
        durability=dict(boot_id='fixtureboot',completed_monotonic_s=201,elapsed_s=101)
        early=dict(clocks=dict(training_steps=10,optimized_samples=4000,learner_frame_count=100,frame_count=100))
        floor={k:max(early['clocks'][k],normal['clocks'][k]) for k in b.CLOCKS}
        cpu=dict(source=dict(path=str(b.CANDIDATE),sha256='a'*64,bytes=1),clock_floor=floor,
            phase_snapshot=dict(owner=OWNER,phase_record=ph['record'],boot_checkpoint=ph['boot_checkpoint'],expected_phase=ph['expected'],observed_clients=192))
        acquisition=dict(tag=b.TAG,purpose='candidate',owner_before=OWNER,owner_after=OWNER,client_count=192,clock_floor=floor,source_checkpoint=cpu['source'])
        trial=dict(status='COMPLETE',qualification_pass=False,manual_recovery_required=False,retired_owner=OWNER)
        activation=dict(status='READY',mode='activate_batch2048',manual_recovery_required=False,owner=OWNER,
            boot_four_clocks=observer['boot_four_clocks'],startup_phase_proof=dict(phase=ph))
        return trial,activation,observer,decision,durability,acquisition,cpu,early,h

    def test_real_horizon_all_five_physical_writes_and_both_thresholds(self):
        args=self.selection();b.check_selection(*args)
        self.assertEqual(args[-1].normalise(args[3]['first_eligible_observation'])['learner_accepted'],0)
        for kind in ('learner','physical','late','epoch','clients'):
            args=list(self.selection())
            if kind=='learner':args[3]['progress']['learner_frames']-=1
            elif kind=='physical':args[3]['progress']['physical_accepted']-=1
            elif kind=='late':args[4].update(completed_monotonic_s=3340.1,elapsed_s=3240.1)
            elif kind=='epoch':args[3]['first_eligible_observation']['host_pipeline']['learning_exposure']['replay']['epoch']=2
            else:args[5]['client_count']=0
            with self.assertRaises(ValueError):b.check_selection(*args)

    def returned(self):
        new=dict(OWNER,pid=202,starttime_ticks=203,invocation_id='b'*32)
        ce=dict(status='READY',mode='return_batch4096',qualification_pass=False,manual_recovery_required=False,owner=new,
            startup_phase_proof=dict(phase=dict(expected=dict(metric='ce',valid=True))),boot_checkpoint=dict(clocks=dict.fromkeys(b.CLOCKS,30)),
            healthy=dict(api=dict(client_count=192,training_enabled=True,exposure=dict(optimizer=dict(process_id=202))),
                binding=dict(environment=dict(DQN_BATCH_SIZE='4096'))),final_resume=dict(failures=[]))
        return dict(retired_owner=OWNER),ce,dict.fromkeys(b.CLOCKS,20)

    def test_dynamic_return_owner4096_and_wrong_generic_transition_shape_refuse(self):
        b.check_return(*self.returned())
        for kind in ('stale','batch','owner','generic','undo'):
            trial,ce,clocks=self.returned()
            if kind=='stale':ce['boot_checkpoint']['clocks']['training_steps']=19
            elif kind=='batch':ce['healthy']['binding']['environment']['DQN_BATCH_SIZE']='2048'
            elif kind=='owner':ce['owner']=OWNER
            elif kind=='generic':ce['transport_readiness']=ce.pop('healthy')
            else:ce['final_resume']['failures']=['fixture failure']
            with self.assertRaises((ValueError,KeyError)):b.check_return(trial,ce,clocks)

    def test_actual_selected_local_return_produces_healthy_and_exact_step_order(self):
        source=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_shared_recipe_control_integration_proposal/run_one_trial.py')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),'849770e0fc31ac7049b8fa8226572478f6c183e4370c952295a49ac5684f252b')
        controller=module(source,'_actual_CE2048_return_route_guard');calls=[];new=self.returned()[1]['owner'];healthy=self.returned()[1]['healthy']
        def note(name,value=None):calls.append(name);return value
        banks=NS(stopped_state=lambda spec:note('banks',{}),assert_unchanged=lambda *args:note('banks-held'))
        runtime=NS(output=Path('/fixture'),job=dict(bank_spec={}),banks=banks,
            absence=lambda:note('absence'),post_stop_ending=lambda owner:note('candidate',{}),
            stopped_checkpoint=lambda owner,label:note('newest',{}),expected_sources=lambda phase:{},
            start_phase=lambda:note('start',new),ready_transport=lambda *args,actors:note('ready192' if actors else 'ready0',healthy),
            raw_api=lambda:dict(client_count=0),startup_snapshot=lambda raw:note('startupCPU',{}),inspect=lambda phase:note('inspect'),
            start_request=pin('/fixture/return-start.json','e'*64,10),cpu_attempts={})
        base=NS(publish=lambda *args:dict(path='/fixture/API.json'),resume_all=lambda host:note('resume',dict(failures=[])))
        runtime.host=NS();adapter=NS(RESULT_SCHEMA='fixture',zero_replay=lambda *args:None)
        result=controller.return_after_retirement(adapter,base,runtime,OWNER)
        self.assertEqual(result['status'],'READY');self.assertIs(result['healthy'],healthy);self.assertNotIn('transport_readiness',result)
        self.assertLess(calls.index('candidate'),calls.index('newest'));self.assertLess(calls.index('newest'),calls.index('start'))
        self.assertLess(calls.index('startupCPU'),calls.index('ready192'))
        tree=ast.parse(source.read_text());run=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='run')
        self.assertIn('return_after_retirement(',ast.get_source_segment(source.read_text(),run))

    def test_actual_activation_baseline_healthy_and_start_origin_predicate(self):
        core=pin('/fixture/core.json','e'*64,10);ph=phase()
        baseline=dict(training_steps=11,grad_norm=float('nan'),host_pipeline=dict(learning_exposure=dict(
            optimizer=dict(total=dict(applied=1)),replay=dict(accepted_total=0))))
        start=dict(boot_id='fixtureboot',monotonic_s=100,unix_s=1000,trial_core=core,phase_record=ph['record'])
        activation=dict(trial_core=core,startup_phase_proof=dict(phase=ph),healthy192_monotonic_s=110)
        observer=dict(trial_core_sha256=core['sha256'],start_request={k:start[k] for k in ('boot_id','monotonic_s','unix_s')},
            before_resume_api=copy.deepcopy(baseline),healthy192_monotonic_s=110)
        b.check_activation_origin(activation,observer,start,baseline)
        for kind in ('baseline','missing','healthy','start','core'):
            current=copy.deepcopy(observer)
            if kind=='baseline':current['before_resume_api']['host_pipeline']['learning_exposure']['optimizer']['total']['applied']=0
            elif kind=='missing':del current['before_resume_api']
            elif kind=='healthy':current['healthy192_monotonic_s']+=1
            elif kind=='start':current['start_request']['monotonic_s']+=1
            else:current['trial_core_sha256']='0'*64
            with self.assertRaises((ValueError,KeyError)):b.check_activation_origin(activation,current,start,baseline)

    def test_original_terminal_exit0_and_empty_invocation_journal(self):
        show='LoadState=loaded\nMainPID=0\nExecMainPID=101\nInvocationID='+'a'*32+'\nNRestarts=0\nExecMainCode=1\nExecMainStatus=0\nResult=success\n'
        execution=dict(owner=OWNER,show='show',cat='cat',journal='journal',archived_before_release=True,released=True)
        b.terminal(execution,lambda p:show if p=='show' else 'actual unit cat',lambda p:b'')
        with self.assertRaises(ValueError):b.terminal(execution,lambda p:show.replace('ExecMainStatus=0','ExecMainStatus=2'),lambda p:b'')

    def test_readonly_metadata_and_no_tensor_bodies(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'small.json';path.write_bytes(b'{}');path.chmod(0o444)
            p=pin(str(path),hashlib.sha256(b'{}').hexdigest(),2);p['identity']=b.identity(path.stat())
            self.assertEqual(b.read(p),{})
            path.chmod(0o644)
            with self.assertRaises(ValueError):b.read(p)
            target=Path(directory)/'opaque.pt';target.write_bytes(b'{}');target.chmod(0o444)
            p=pin(str(target),hashlib.sha256(b'{}').hexdigest(),2);p['identity']=b.identity(target.stat())
            with self.assertRaises(ValueError):b.read(p)

    def test_auditor_default_does_not_read_and_required_packaging_is_present(self):
        with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('read')),mock.patch.object(a,'configure',side_effect=AssertionError('configure')),mock.patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(a.main([]),0)
        self.assertEqual(a.BINDINGS_SHA,hashlib.sha256((HERE/'quality_bindings.py').read_bytes()).hexdigest())
        self.assertEqual(hashlib.sha256((HERE/'template-audit-source.py').read_bytes()).hexdigest(),a.TEMPLATE_SHA256)
        self.assertTrue((HERE/'README.txt').read_bytes())

    def test_original_row_math_and_classifier_functions_are_unchanged(self):
        old=HERE.parent/'fresh_quality_trial02_binding_companions_proposal/audit_completed_leg.py'
        def functions(path):
            text=path.read_text();return {x.name:ast.get_source_segment(text,x) for x in ast.parse(text).body if isinstance(x,ast.FunctionDef)}
        prior,current=functions(old),functions(HERE/'audit_completed_leg.py')
        for name,text in prior.items():
            self.assertEqual(text.replace('Protected448/actual first candidate differs','Protected543/actual first candidate differs'),current[name])

if __name__=='__main__':unittest.main()
