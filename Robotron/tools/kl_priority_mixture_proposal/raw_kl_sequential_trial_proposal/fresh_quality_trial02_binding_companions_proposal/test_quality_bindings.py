"""Source-authored stdlib guards; root alone executes. No real PT/runtime use."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from . import quality_bindings as b
from . import root_quality_carrier as c
from . import audit_completed_leg as a


OWNER = dict(pid=101,starttime_ticks=102,unit='owned.service',invocation_id='a'*32,cgroup='/owned.service')


class QualityBindingContracts(unittest.TestCase):
    def cpu(self):
        size=275192165
        def pin(path,inode):
            return dict(path=path,sha256='f'*64,bytes=size,identity=dict(device=1,inode=inode,bytes=size,
                mtime_ns=1,ctime_ns=1,mode='0o444',uid=os.getuid(),nlink=1))
        source=pin(str(b.CANDIDATE),11);copied=pin('/owned/copy.pt',12)
        job=dict(schema='robotron-phase-snapshot-checkpoint-CPU-job-v1',verifier_sha256=b.PHASE_SHA,
            strict_phase_base_sha256=b.STRICT_SHA,original_strict_base_sha256=b.BASE_SHA,
            source=source,verification_copy=copied,clock_floor=dict.fromkeys(b.CLOCKS,10),
            phase_snapshot=dict(purpose='candidate',expected_phase=dict(metric='kl',valid=True)))
        proof=dict(schema='robotron-phase-snapshot-checkpoint-CPU-result-v1',status='PASS',phase_metadata_verified=True,
            script=dict(sha256=b.PHASE_SHA),strict_phase_base=dict(sha256=b.STRICT_SHA),original_strict_base=dict(sha256=b.BASE_SHA),
            root_job=copy.deepcopy(job),sha256='f'*64,bytes=size,path=copied['path'],source_before=b.flat(source),
            verification_copy=b.flat(copied),actual_restore_or_optimizer_step=False,actual_quality_qualification=False,
            clocks=dict.fromkeys(b.CLOCKS,11),job_file=dict(path='/owned/phase-job.json',sha256='e'*64))
        completion=dict(exit_code=0,argv=['/venv/python','-Xgil=0','-I','-B',str(b.PHASE),'--execute',
            '--job','/owned/phase-job.json','--expected-job-sha256','e'*64,'--expected-verifier-sha256',b.PHASE_SHA])
        candidate=dict(tag=b.TAG,path=str(b.CANDIDATE),sha256='f'*64,bytes=size)
        return job,proof,completion,candidate

    def test_default_carrier_and_auditor_do_not_import_helpers_read_or_act(self):
        with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('read')), \
                mock.patch.object(c,'configure',side_effect=AssertionError('configure')), \
                mock.patch.object(a,'configure',side_effect=AssertionError('configure')), \
                mock.patch.object(c.subprocess,'run',side_effect=AssertionError('action')), \
                context_stdout():
            self.assertEqual(c.main([]),0);self.assertEqual(a.main([]),0)

    def test_authentic_inline_phase_report_and_readonly_copy_shape(self):
        b.check_cpu(*self.cpu())

    def test_early_startup_wrong_tag_or_generic_CPU_never_substitutes_candidate(self):
        for kind in ('purpose','tag','generic','rootjob','alias','writable','exit'):
            with self.subTest(kind=kind):
                job,proof,completion,candidate=self.cpu()
                if kind=='purpose':job['phase_snapshot']['purpose']='startup';proof['root_job']=copy.deepcopy(job)
                elif kind=='tag':candidate['tag']='early-insurance'
                elif kind=='generic':proof['schema']='robotron-managed-candidate-checkpoint-CPU-result-v1'
                elif kind=='rootjob':proof['root_job']['clock_floor']['training_steps']=9
                elif kind=='alias':job['verification_copy']['identity']['inode']=11
                elif kind=='writable':job['verification_copy']['identity']['mode']='0o644'
                else:completion['exit_code']=1
                with self.assertRaises(ValueError):b.check_cpu(job,proof,completion,candidate)

    def test_inline_CPU_exact_flags_digest_and_no_duplicate_or_foreign_args(self):
        for kind in ('append','digest','u','order'):
            with self.subTest(kind=kind):
                args=list(self.cpu());command=args[2]['argv']
                if kind=='append':command += ['--job','/foreign.json']
                elif kind=='digest':command[command.index('--expected-job-sha256')+1]='d'*64
                elif kind=='u':command.insert(4,'-u')
                else:command[1:3]=list(reversed(command[1:3]))
                with self.assertRaises(ValueError):b.check_cpu(*args)

    def selection(self):
        h=b.load_horizon()  # pinned pure stdlib source; no application/runtime imports
        identity=dict(process_id=101,instance_monotonic_ns=3,epoch=1,epoch_reason='restore')
        def raw(learner,accepted):
            counts=dict(attempts_started=1,outcomes_recorded=1,applied=1,amp_skipped=0,unavailable=0)
            return dict(training_steps=11,optimized_samples=4096,learner_frame_count=learner,frame_count=100,
                host_pipeline=dict(learning_exposure=dict(
                    optimizer=dict(identity,schema='robotron-optimizer-exposure-v1',enabled=True,available=True,
                        total=counts,since_epoch=counts,unclassified_started_total=0),
                    replay=dict(identity,schema='robotron-replay-insert-exposure-v1',enabled=True,available=True,
                        accepted_total=accepted,accepted_learner_total=0,accepted_by_source_total=dict(
                            dqn=0,epsilon=0,expert=0,eval=accepted,unattributed=0)))))
        phase=dict(record=dict(path='/record.json',sha256='c'*64),boot_checkpoint=dict(path='/latest.pt',sha256='d'*64,bytes=1),expected=dict(metric='kl'))
        observer=dict(schema=h.SCHEMA,policy=h.POLICY,owner=OWNER,start_request=dict(boot_id='boot',monotonic_s=100,unix_s=1000),
            healthy192_monotonic_s=110,boot_four_clocks=dict(training_steps=10,optimized_samples=4000,learner_frame_count=100,frame_count=100),
            trial_core_sha256='e'*64,activation_receipt_sha256='f'*64,before_resume_api=raw(100,0))
        current=raw(8000100,6000000);norm=h.normalise(current)
        decision=dict(schema='robotron-raw-kl-horizon-observation-v1',state='LATCH',candidate_requests_allowed=1,
            qualification_pass=False,boot_id='boot',observed_monotonic_s=200,elapsed_s=100,first_eligible_observation=current,
            progress=dict(learner_frames=8000000,physical_accepted=6000000,optimizer_total=norm['optimizer']))
        durability=dict(boot_id='boot',completed_monotonic_s=201,elapsed_s=101)
        early=dict(schema='robotron-live8-maintenance-checkpoint-CPU-result-v1',status='PASS',mode='insurance',script=dict(sha256=b.BASE_SHA),
            root_job=dict(mode='insurance',verifier_sha256=b.BASE_SHA,insurance=dict(trainer=OWNER,tag='distinct-early')),
            insurance_trigger=dict(client_count=192),clocks=dict(training_steps=10,optimized_samples=4000,learner_frame_count=100,frame_count=100))
        floor={k:max(early['clocks'][k],norm['clocks'][k]) for k in b.CLOCKS}
        cpu=dict(source=dict(path=str(b.CANDIDATE),sha256='a'*64,bytes=1),clock_floor=floor,
            phase_snapshot=dict(owner=OWNER,phase_record=phase['record'],boot_checkpoint=phase['boot_checkpoint'],expected_phase=phase['expected']))
        acquisition=dict(tag=b.TAG,purpose='candidate',owner_before=OWNER,owner_after=OWNER,clock_floor=floor,
            source_checkpoint=cpu['source'])
        trial=dict(status='COMPLETE',qualification_pass=False,manual_recovery_required=False)
        activation=dict(status='READY',manual_recovery_required=False,owner=OWNER,boot_four_clocks=observer['boot_four_clocks'],startup_phase_proof=dict(phase=phase))
        return trial,activation,observer,decision,durability,acquisition,cpu,early,h

    def test_both_horizons_use_physical_all_five_including_eval_not_learner_only(self):
        args=self.selection();b.check_selection(*args)
        self.assertEqual(args[-1].normalise(args[3]['first_eligible_observation'])['learner_accepted'],0)

    def test_each_horizon_cutoff_epoch_and_authentic_early192_are_required(self):
        for kind in ('learner','physical','late','epoch','early'):
            with self.subTest(kind=kind):
                args=list(self.selection());decision=args[3]
                if kind=='learner':decision['progress']['learner_frames']-=1
                elif kind=='physical':decision['progress']['physical_accepted']-=1
                elif kind=='late':args[4].update(completed_monotonic_s=3340.01,elapsed_s=3240.01)
                elif kind=='epoch':decision['first_eligible_observation']['host_pipeline']['learning_exposure']['replay']['epoch']=2
                else:args[7]['insurance_trigger']['client_count']=0
                with self.assertRaises(ValueError):b.check_selection(*args)

    def returned(self):
        owner=dict(OWNER,pid=202,starttime_ticks=203,invocation_id='b'*32)
        ce=dict(status='READY',mode='return_ce',qualification_pass=False,manual_recovery_required=False,owner=owner,
            startup_phase_proof=dict(phase=dict(expected=dict(metric='ce',valid=True))),
            boot_checkpoint=dict(clocks=dict.fromkeys(b.CLOCKS,30)),
            healthy=dict(api=dict(client_count=192,training_enabled=True,exposure=dict(optimizer=dict(process_id=202)))),
            final_resume=dict(failures=[]))
        return dict(retired_owner=OWNER),ce,dict.fromkeys(b.CLOCKS,20)

    def test_real_return_shape_without_invented_phase_record_fields(self):
        b.check_return(*self.returned())

    def test_stale_latest_wrong_CE_owner_phase_or_failed_undo_refuses(self):
        for kind in ('stale','owner','phase','undo'):
            with self.subTest(kind=kind):
                trial,ce,clocks=self.returned()
                if kind=='stale':ce['boot_checkpoint']['clocks']['training_steps']=19
                elif kind=='owner':ce['healthy']['api']['exposure']['optimizer']['process_id']=999
                elif kind=='phase':ce['startup_phase_proof']['phase']['expected']['metric']='kl'
                else:ce['final_resume']['failures']=['actual failure']
                with self.assertRaises(ValueError):b.check_return(trial,ce,clocks)

    def test_empty_journal_only_is_pinned_and_valid_original_terminal(self):
        show='LoadState=loaded\nMainPID=0\nExecMainPID=101\nInvocationID='+'a'*32+'\nNRestarts=0\nExecMainCode=1\nExecMainStatus=0\nResult=success\n'
        execution=dict(owner=OWNER,show='show',cat='cat',journal='journal',archived_before_release=True,released=True)
        journal=mock.Mock(return_value=b'')
        b.terminal(execution,lambda p:show if p=='show' else 'actual unit cat',journal)
        journal.assert_called_once_with('journal')
        with self.assertRaises(ValueError):b.terminal(execution,lambda p:show.replace('ExecMainPID=101','ExecMainPID=999'),journal)

    def test_readonly_PIN_rejects_writable_or_mutated_metadata_without_PT(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'small.json';path.write_bytes(b'{}');path.chmod(0o444)
            pin=dict(path=str(path),sha256=__import__('hashlib').sha256(b'{}').hexdigest(),bytes=2,identity=b.identity(path.stat()))
            self.assertEqual(b.read(pin),{})
            path.chmod(0o644)
            with self.assertRaises(ValueError):b.read(pin)
            empty=Path(directory)/'journal.txt';empty.write_bytes(b'');empty.chmod(0o444)
            ep=dict(path=str(empty),sha256=__import__('hashlib').sha256(b'').hexdigest(),bytes=0,identity=b.identity(empty.stat()))
            self.assertEqual(b.read_bytes(ep,allow_empty=True),b'')
            with self.assertRaises(ValueError):b.read_bytes(ep)

    def complete_binding(self):
        """One full decoder join using injected tiny metadata only; no app/model IO."""
        trial,activation,observer,decision,durability,acquisition,selected,early,h=self.selection()
        cpu,proof,completion,candidate=self.cpu();cpu['phase_snapshot'].update(selected['phase_snapshot'])
        cpu['phase_snapshot']['purpose']='candidate';cpu['clock_floor']=selected['clock_floor']
        phase=activation['startup_phase_proof']['phase']
        phase['expected'].update(valid=True,phase_id='trial02',root_precommit_sha256='4'*64)
        cpu['phase_snapshot']['expected_phase']=phase['expected']
        proof.update(root_job=copy.deepcopy(cpu),clocks={k:v+1 for k,v in cpu['clock_floor'].items()})
        acquisition['source_checkpoint']={k:cpu['source'][k] for k in ('path','sha256','bytes')}
        store={};counter=[30]
        def pin(path,sha=None,mode='0o444'):
            counter[0]+=1
            return dict(path=path,sha256=sha or ('%064x'%counter[0]),bytes=1,identity=dict(device=1,
                inode=counter[0],bytes=1,mtime_ns=1,ctime_ns=1,mode=mode,uid=os.getuid(),nlink=1))
        def put(path,value,sha=None):
            p=pin(path,sha);store[path]=value;return p
        outerpin=pin('/owned/outer.json','1'*64);corepin=pin('/owned/core.json','4'*64)
        actpin=pin('/owned/activation.json','2'*64);actjobpin=pin('/owned/activation-job.json','3'*64)
        cpupin=pin('/owned/phase-job.json','e'*64)
        earlypin=put('/owned/early-readonly.json',early,'8'*64)
        historical=dict(earlypin,path='/original/writable-early.json',identity=dict(earlypin['identity'],inode=999,mode='0o664'))
        startpin=put('/owned/start.json',dict(observer['start_request'],trial_core=corepin,phase_record=phase['record']))
        activation.update(start_request=startpin,trial_core=corepin)
        observer.update(trial_core_sha256=corepin['sha256'],activation_receipt_sha256=actpin['sha256'])
        trial.update(root_job=outerpin,retired_owner=OWNER,early_insurance=historical,
            candidate=dict(source=cpu['source'],verification_copy=cpu['verification_copy'],
                acquisition=put('/owned/acquisition.json',acquisition)))
        cpu['phase_snapshot']['acquisition']=trial['candidate']['acquisition'];proof['root_job']=copy.deepcopy(cpu)
        store[cpupin['path']]=cpu;store[actpin['path']]=activation
        evidence=dict(phase_cpu_job=cpupin,phase_cpu_report=put('/owned/report.json',proof),
            phase_cpu_completion=put('/owned/completion.json',completion),activation=actpin,
            observer=put('/owned/observer.json',observer),decision=put('/owned/decision.json',decision),
            early_insurance=earlypin,outer_job=outerpin,activation_job=actjobpin,trial_core=corepin)
        durability['event']=evidence['decision'];evidence['durability']=put('/owned/durability.json',durability)
        trial.update(activation=actpin,observer=evidence['observer'],decision=dict(event=evidence['decision'],durability=evidence['durability']))
        _,ce,_=self.returned();ce['ending']=dict(candidate_CPU=evidence['phase_cpu_report'])
        boot=dict(path='/owned/latest.pt',sha256='b'*64,bytes=275192165)
        ce['boot_checkpoint']=dict(source=boot,clocks={k:v+1 for k,v in proof['clocks'].items()})
        recordpin=put('/owned/CErecord.json',dict(metric='ce',action='start',previous_metric='kl',root_precommit_sha256='a'*64))
        ce['startup_phase_proof']['phase'].update(record=recordpin,boot_checkpoint=boot)
        ce['start_request']=put('/owned/CEstart.json',dict(phase_record=recordpin,trial_core=dict(sha256='a'*64)))
        ce['startup_phase_proof']['phase_CPU']=put('/owned/CEcpu.json',dict(status='PASS',phase_metadata_verified=True,
            script=dict(sha256=b.PHASE_SHA),root_job=dict(phase_snapshot=dict(purpose='startup',owner=ce['owner'])),
            saved_priority_metric_phase=dict(metric='ce',phase_record_sha256=recordpin['sha256'])))
        evidence['ce_return']=put('/owned/CEreturn.json',ce);trial['CE_return']=evidence['ce_return']
        evidence['trial_result']=put('/owned/trial-result.json',trial)
        evidence['deadline_result']=put('/owned/deadline-result.json',dict(status='RETIRED',adopted=dict(owner=OWNER),
            absence=dict(elapsed_s=200,proof=dict(state='ABSENT'))))
        evidence['owned_cleanup']=put('/owned/cleanup.json',dict(status='PASS',owned_cleanup_complete=True))
        controller=dict(OWNER,pid=301,unit='controller.service');deadline=dict(OWNER,pid=302,unit='deadline.service')
        outer=dict(activation_job=actjobpin,trial_core=corepin,candidate_tag=b.TAG,early_insurance=dict(tag='distinct-early'),
            sources=dict(controller=dict(path='/owned/controller.py',sha256='d'*64)))
        store[outerpin['path']]=outer;store[actjobpin['path']]=dict(mode='activate_kl',phase_id='trial02',trial_core=corepin,verifier=dict(python='/venv/python'))
        store[corepin['path']]=dict(status='FINAL_PRECOMMITTED_ROOT_AUTHORIZED',activation_authorized=True,mode='activate_kl',phase_id='trial02')
        launch=dict(trainer=dict(expected=OWNER,fields=dict(ControlGroup=OWNER['cgroup'])),
            controller=dict(expected=controller,fields=dict(ControlGroup=controller['cgroup'],ExecStart=' '.join((outerpin['path'],outerpin['sha256'],'/owned/controller.py','d'*64)))),
            deadline=dict(expected=deadline,fields=dict(ControlGroup=deadline['cgroup'])))
        launchpin=put(str(b.ACTUAL_LAUNCH_IDENTITIES),launch,b.ACTUAL_LAUNCH_IDENTITIES_SHA)
        executions={}
        for name,owner in (('trial_controller',controller),('deadline',deadline)):
            show='LoadState=loaded\nMainPID=0\nExecMainPID='+str(owner['pid'])+'\nInvocationID='+owner['invocation_id']+'\nNRestarts=0\nExecMainCode=1\nExecMainStatus=0\nResult=success\n'
            executions[name]=dict(owner=owner,show=put('/owned/'+name+'.show',show),cat=put('/owned/'+name+'.cat','unit cat'),
                journal=put('/owned/'+name+'.journal',''),archived_before_release=True,released=True)
        anchor=dict(main_owner=ce['owner'],fleet_owner=OWNER,inference_worker=dict(tid=401,starttime_ticks=402,mask=list(range(72))),
            actors=[dict(pid=1000+i,starttime_ticks=i+1,slot=i,mask=list(range(72))) for i in range(192)],
            source_hashes={str(b.GAME/'Scripts/dqn'/n):v for n,v in b.CANDIDATE_SOURCES.items()},
            control_hashes={'one':'a'*64,'two':'b'*64},unit_files={'/owned/unit':'c'*64},environment_sha256='d'*64)
        anchor['source_hashes'].update({'/owned/source'+str(i):'a'*64 for i in range(56)})
        baseline=put('/owned/baseline.json',dict(status='PASS',**anchor))
        old=dict(b.EVALUATOR);old['Scripts/dqn/config.py']='f2794754a14e9f13c82b613aa131698246a08dc9021c18f1b78fda7c4b484498'
        predecessor=put(str(b.PREDECESSOR_PLAN),dict(evaluator_source_hashes=old,execution_source_hashes=b.EXECUTION),b.PREDECESSOR_PLAN_SHA)
        binding=dict(schema=b.SCHEMA,experiment='best10M-fresh3-eps10-cap8-nosmooth',candidate=candidate,evidence=evidence,
            runtime_baseline=baseline,runtime_anchor=anchor,original_executions=executions,actual_launch_identities=launchpin,
            predecessor_quality_plan=predecessor,campaign=dict(output_directory=str(b.GAME/'logs/managed-learning-20261015/future-test'),
                preview_directory=str(b.GAME/'logs/managed-learning-20261015/run-26/future-preview'),
                execution_directory=str(b.GAME/'logs/managed-learning-20261015/run-26/future-exec'),unit='robotron-quality-future-test',
                reference_label='ref',candidate_label='candidate',hypothesis='declared hypothesis'))
        return binding,store,h

    def test_whole_shared_binding_joins_real_shapes_and_rejects_foreign_parent_or_reanchor(self):
        binding,store,h=self.complete_binding()
        def run():return b.validate(binding,reader=lambda p:store[p['path']],text_reader=lambda p:store[p['path']],
            journal_reader=lambda p:store[p['path']],horizon=h)
        self.assertEqual(run()['ce_return']['status'],'READY')
        binding['original_executions']['trial_controller']['owner']=dict(OWNER,pid=999)
        with self.assertRaises(ValueError):run()

    def test_original_auditor_row_tail_and_stats_body_is_unchanged(self):
        original=(Path(a.__file__).with_name('template-audit-source.py')).read_text();current=Path(a.__file__).read_text()
        begin='        legdir = directory /';end='\n\ndef configure('
        old=original[original.index(begin):original.index('\n\ndef main(',original.index(begin))]
        new=current[current.index(begin):current.index(end,current.index(begin))]
        new=new.replace('Candidate receipt clock differs from actual first-candidate phase CPU proof','Candidate receipt clock differs from actual448 generic CPU proof')
        self.assertEqual(new,old)

    def test_no_null_or_extra_evidence_template_can_execute(self):
        with self.assertRaises((ValueError,TypeError,KeyError)):
            b.validate(dict(schema=b.SCHEMA,experiment='best10M-fresh3-eps10-cap8-nosmooth'))


def context_stdout():
    import contextlib
    return contextlib.redirect_stdout(io.StringIO())


if __name__=='__main__':unittest.main()
