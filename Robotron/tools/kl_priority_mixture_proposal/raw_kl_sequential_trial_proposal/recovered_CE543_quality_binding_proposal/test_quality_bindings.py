"""Authored metadata-only contracts. No runtime/model helpers are imported."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('_live_ce_quality_metadata', HERE/'quality_bindings.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def fixture():
    values = {}
    def pin(label,value):
        p = dict(path='/metadata/'+label,sha256=hashlib.sha256(label.encode()).hexdigest(),bytes=100,
            identity=dict(device=1,inode=len(values)+1,bytes=100,mtime_ns=1,ctime_ns=1,mode='0o444',uid=os.getuid(),nlink=1))
        values[p['path']] = value
        return p
    clocks = {k:100 for k in M.CLOCKS}
    owner = dict(pid=100,starttime_ticks=200,unit='trainer.service',invocation_id='a'*32,cgroup='/owned/trainer')
    candidate = dict(tag='future-ce-candidate',path=str(M.GAME/'models_dqn/managed-checkpoints/future-ce-candidate.pt'),sha256='b'*64,bytes=275191999)
    source = pin('source',{}); source.update(path=candidate['path'],sha256=candidate['sha256'],bytes=candidate['bytes'])
    source['identity']['bytes'] = candidate['bytes']
    copied = copy.deepcopy(source); copied['path']='/verification/independent.pt'; copied['identity']['inode']+=100
    boot_checkpoint = dict(path=str(M.GAME/'models_dqn/robotron_dqn_latest.pt'),sha256='c'*64,bytes=275186072)
    boot = pin('boot-proof',dict(status='PASS',sha256=boot_checkpoint['sha256'],bytes=boot_checkpoint['bytes']))
    record = pin('phase-record',dict(metric='ce',previous_metric='ce',checkpoint=boot_checkpoint))
    expected = dict(metric='ce',valid=True,phase_id='genuine-ce-phase',root_precommit_sha256='d'*64,
        founder_phase_record_sha256=record['sha256'],last_resume_record_sha256=None,
        started_from=dict(boot_checkpoint,clocks=clocks))
    phase = dict(record=record,boot_checkpoint=boot_checkpoint,boot_verification=boot,expected=expected)
    acquisition = pin('acquisition',dict(schema='robotron-owned-phase-snapshot-acquisition-v1',purpose='candidate',
        client_count=192,owner_before=owner,owner_after=owner,tag=candidate['tag'],stopped_absence=None,
        source_checkpoint={k:candidate[k] for k in ('path','sha256','bytes')},clock_floor=clocks,
        phase_record_sha256=record['sha256'],boot_checkpoint=boot_checkpoint,completed_slot_transition={'actual':'retained by verifier'}))
    cpu = dict(schema='robotron-phase-snapshot-checkpoint-CPU-job-v1',verifier_sha256=M.PHASE_SHA,
        strict_phase_base_sha256=M.STRICT_SHA,original_strict_base_sha256=M.BASE_SHA,source=source,verification_copy=copied,
        clock_floor=clocks,phase_snapshot=dict(purpose='candidate',observed_clients=192,expected_phase=expected,
            owner=owner,phase_record=record,boot_checkpoint=boot_checkpoint,boot_verification=boot,acquisition=acquisition))
    cpu_pin = pin('cpu-job',cpu)
    saved = dict(metric='ce',valid=True,phase_id=expected['phase_id'],root_precommit_sha256=expected['root_precommit_sha256'],
        started_from=expected['started_from'],phase_record_sha256=record['sha256'],last_resume_record_sha256=None)
    proof = dict(schema='robotron-phase-snapshot-checkpoint-CPU-result-v1',status='PASS',phase_metadata_verified=True,
        script={'sha256':M.PHASE_SHA},strict_phase_base={'sha256':M.STRICT_SHA},original_strict_base={'sha256':M.BASE_SHA},
        root_job=cpu,sha256=candidate['sha256'],bytes=candidate['bytes'],path=copied['path'],source_before=M.flat(source),
        verification_copy=M.flat(copied),actual_restore_or_optimizer_step=False,actual_quality_qualification=False,
        job_file=cpu_pin,clocks=clocks,saved_priority_metric_phase=saved)
    completion = dict(argv=['/venv/bin/python','-Xgil=0','-I','-B',str(M.PHASE),'--execute','--job',cpu_pin['path'],
        '--expected-job-sha256',cpu_pin['sha256'],'--expected-verifier-sha256',M.PHASE_SHA],exit_code=0)
    trigger = pin('trigger-api',dict(clocks,client_count=192,training_enabled=True,measurement_active=False,
        managed_experiment='best10M-fresh3-eps10-cap8-nosmooth',host_pipeline={'learning_exposure':{'optimizer':{'process_id':owner['pid']}}}))
    capture_completion = pin('capture-completion',dict(status='COMPLETE',tag=candidate['tag'],owner_before=owner,
        owner_after=owner,transition=values[acquisition['path']]['completed_slot_transition']))
    capture = dict(status='CAPTURED_PENDING_CPU',source=source,verification_copy=copied,acquisition=acquisition,
        cpu_job=cpu_pin,current_phase=phase,owner=owner,trigger_API=trigger,capture_completion=capture_completion)
    def fixed(label,value,table,key):
        result=pin(label,value);path,digest=table[key]
        values[str(path)]=values.pop(result['path']);result.update(path=str(path),sha256=digest)
        return result
    summary=pin('previous-summary',{});summary['path']=str(M.PREDECESSOR_PLAN.parent/'summary.json')
    closure_job=pin('closure-job',dict(schema='robotron-CE543M-quality-owned-closure-job-v1',
        binding_job={'sha256':'f43719ed4dc60a4c275a7414995aa79d0f40062c76964200cf8700a8abe50dc3'},terminal_summary=summary))
    closure=fixed('closure',dict(status='PASS_ORIGINAL_QUALITY_ARCHIVED_OWNED_CLEANUP_COMPLETE',owned_cleanup_complete=True,
        main192_and_resources_healthy=True,original_execution=dict(exec_code=1,exit_status=0,result='success',archived_before_release=True),
        root_job=closure_job,accepted_quality_outcome='qualified_improvement'),M.PREVIOUS_PINS,'closure')
    reference=dict(path=next(iter(M.REFERENCES)),sha256=next(iter(M.REFERENCES.values())),bytes=275192614)
    metadata=pin('protected-reference',dict(schema='robotron-protected-quality-winner-v1',protected_checkpoint=reference['path'],
        checkpoint_sha256=reference['sha256'],plan_sha256=M.PREDECESSOR_PLAN_SHA,assessment={'qualified_improvement':True}))
    values[reference['path']+'.json']=values.pop(metadata['path']);metadata.update(path=reference['path']+'.json',sha256='b080f538f84e9c76739b9d142a2065a55d1292c3dbdcb01806003a14339956d5');reference['metadata']=metadata
    release=fixed('freeze-release',dict(source_freeze_released=True,owned_cleanup_complete=True,
        actual_plan_sha256=M.PREDECESSOR_PLAN_SHA,actual_owned_closure=M.triple(closure),qualification_pass=True),M.PREVIOUS_PINS,'source_freeze_release')
    publication=fixed('publication',dict(status='PASS_CREATE_ONLY_PROTECTED_CE543M_PUBLISHED',
        protected_checkpoint=M.triple(reference),metadata=M.triple(metadata),source_freeze_release=M.triple(release)),M.PREVIOUS_PINS,'publication')
    adoption=fixed('adoption',dict(status='PASS_CE543M_PROTECTED_WINNER_CANONICALLY_ADOPTED_GOAL_CONTINUES',
        protected_checkpoint='models_dqn/managed-incumbents/freshCE-543M-confirmed.pt',checkpoint_sha256=reference['sha256'],
        actual_publication=M.triple(publication),live_learner_restored=False,goal_remains_active=True),M.PREVIOUS_PINS,'adoption')
    anchor = dict(main_owner=owner,fleet_owner=owner,inference_worker={'tid':101,'starttime_ticks':202,'mask':list(range(72))},
        actors=[dict(pid=1000+i,starttime_ticks=2000+i,slot=i,mask=list(range(72))) for i in range(192)],
        source_hashes={**{str(M.GAME/'Scripts/dqn'/k):v for k,v in M.CANDIDATE_SOURCES.items()},**{'other-source-'+str(i):'e'*64 for i in range(56)}},
        control_hashes={'control1':'e'*64,'control2':'f'*64},unit_files={},environment_sha256='f'*64)
    recovery_job=fixed('repair-job',{},M.RECOVERY_PINS,'job')
    recovered=dict(status='READY_CE_FORWARD_REPAIR',original_trial_failed=True,trial_retried=False,manual_recovery_required=False,
        recovery_target_batch_size=4096,root_job=recovery_job,owner=owner,startup={'phase':copy.deepcopy(phase)},
        healthy192={'binding':{'bindings':{'actors':anchor['actors']}}},final_resume=dict(all_matching_actors_resumed=True,failures=[]))
    recovery_result=fixed('repair-result',recovered,M.RECOVERY_PINS,'result')
    recovery_release=fixed('repair-release',dict(status='PASS',owner=owner,result=M.triple(recovery_result),
        original_exec_code=1,original_exit=0,original_result='success',original_archived_before_release=True,unit_released=True),M.RECOVERY_PINS,'release')
    capture['root_job']=pin('capture-job',dict(recovery=dict(result=recovery_result,job=recovery_job,release=recovery_release),expected_owner=owner))
    baseline = pin('baseline',dict(anchor,status='PASS'))
    predecessor = pin('predecessor',dict(evaluator_source_hashes=M.EVALUATOR,execution_source_hashes=M.EXECUTION))
    values[str(M.PREDECESSOR_PLAN)]=values.pop(predecessor['path']); predecessor.update(path=str(M.PREDECESSOR_PLAN),sha256=M.PREDECESSOR_PLAN_SHA)
    binding = dict(schema=M.SCHEMA,experiment='best10M-fresh3-eps10-cap8-nosmooth',candidate=candidate,reference=reference,
        evidence=dict(capture_result=pin('capture-result',capture),phase_cpu_job=cpu_pin,phase_cpu_report=pin('cpu-report',proof),
            phase_cpu_completion=pin('cpu-completion',completion)),current_ce_phase=phase,runtime_baseline=baseline,runtime_anchor=anchor,
        previous_campaign=dict(closure=closure,source_freeze_release=release,publication=publication,adoption=adoption),predecessor_quality_plan=predecessor,
        campaign=dict(output_directory=str(M.GAME/'logs/managed-learning-20261015/new-CE-quality'),
            preview_directory=str(M.GAME/'logs/managed-learning-20261015/run-26/new-CE-preview'),
            execution_directory=str(M.GAME/'logs/managed-learning-20261015/run-26/new-CE-execution'),
            unit='robotron-quality-future-CE',reference_label='actual-protected-reference',candidate_label='new-CE-candidate',hypothesis='Frozen CE policy quality.'))
    return binding,values


class LiveCEBindingContracts(unittest.TestCase):
    def test_launch_actual_ce_schema_without_original_executions(self):
        binding,_=fixture();self.assertNotIn('original_executions',binding)
        spec=importlib.util.spec_from_file_location('_live_ce_launch_contract',HERE/'root_quality_carrier.py')
        carrier=importlib.util.module_from_spec(spec);spec.loader.exec_module(carrier)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);preview=root/'preview';preview.mkdir();execution=root/'execution';output=root/'campaign'
            bound=dict(candidate_sha256=binding['candidate']['sha256'],candidate_bytes=binding['candidate']['bytes'])
            (preview/'default-plan.json').write_text('{}')
            (preview/'root-default-plan-source-review.json').write_text(json.dumps(dict(actual_inputs=bound,plan_sha256='plan-sha')))
            seen=[]
            def show(unit):
                seen.append(unit)
                if len(seen)<=2:return dict(unit=unit),dict(LoadState='not-found')
                if unit.endswith('.timer'):return dict(unit=unit),dict(ActiveState='active',SubState='waiting')
                return dict(unit=unit),dict(MainPID='0')
            args=SimpleNamespace(plan_sha256='plan-sha',plan_review=root/'review.json',plan_review_sha256='review-sha',
                runtime_readiness=root/'ready.json',runtime_readiness_sha256='ready-sha')
            review=dict(status='PASS',plan_sha256='plan-sha',actual_inputs=bound)
            with mock.patch.multiple(carrier,CFG=binding,D=preview,J=execution,OUT=output,U='robotron-quality-ce-guard',
                    REFERENCE=Path(binding['reference']['path']),CANDIDATE=Path(binding['candidate']['path'])),\
                mock.patch.object(carrier,'inputs',return_value=(bound,{})),\
                mock.patch.object(carrier,'sha',return_value='plan-sha'),\
                mock.patch.object(carrier,'validate_plan'),mock.patch.object(carrier,'source_checks'),\
                mock.patch.object(carrier,'pinned_json',side_effect=[(review,{'review':'PIN'}),({}, {'ready':'PIN'})]),\
                mock.patch.object(carrier,'readiness_contract'),mock.patch.object(carrier,'fast_runtime',return_value={'healthy':True}),\
                mock.patch.object(carrier,'show',side_effect=show),\
                mock.patch.object(carrier,'call',return_value=dict(returncode=0,stdout='',stderr='')) as scheduled:
                (preview/'default-argv.json').write_text(json.dumps(carrier.default_argv()))
                result=carrier.launch(args)
            self.assertEqual(result['status'],'DURABLE_LAUNCH_SUBMITTED')
            self.assertEqual(seen,['robotron-quality-ce-guard.service','robotron-quality-ce-guard.timer',
                'robotron-quality-ce-guard.timer','robotron-quality-ce-guard.service'])
            scheduled.assert_called_once()
            self.assertEqual(scheduled.call_args.args[0][0],'systemd-run')
            self.assertEqual(scheduled.call_args.args[0][-1],'--launch')

    def test_complete_live_ce_shape_needs_no_trial_or_latch(self):
        binding,values=fixture(); result=M.validate(binding,reader=lambda p:values[p['path']])
        self.assertEqual(result['current_ce_phase'],binding['current_ce_phase'])
        self.assertNotIn('trial_result',binding['evidence'])

    def test_rejects_kl_or_generic_cpu_or_non192_scope(self):
        for change in ('kl','generic','client0'):
            binding,values=fixture();cpu=values[binding['evidence']['phase_cpu_job']['path']]
            if change=='kl':cpu['phase_snapshot']['expected_phase']['metric']='kl'
            elif change=='generic':cpu['schema']='robotron-maintenance-checkpoint-CPU-job-v1'
            else:cpu['phase_snapshot']['observed_clients']=0
            with self.subTest(change=change),self.assertRaises(ValueError):M.validate(binding,reader=lambda p:values[p['path']])

    def test_rejects_startup_snapshot_as_boot_proof(self):
        binding,values=fixture();values[binding['current_ce_phase']['boot_verification']['path']]['sha256']='9'*64
        with self.assertRaises(ValueError):M.validate(binding,reader=lambda p:values[p['path']])

    def test_rejects_capture_owner_or_training_discontinuity(self):
        for change in ('owner','paused','clients','wrong-trigger-floor'):
            binding,values=fixture();capture=values[binding['evidence']['capture_result']['path']]
            if change=='owner':capture['owner']=dict(capture['owner'],pid=999)
            elif change=='wrong-trigger-floor':values[capture['trigger_API']['path']]['training_steps']+=1
            else:values[capture['trigger_API']['path']]['training_enabled' if change=='paused' else 'client_count']=False if change=='paused' else 0
            with self.subTest(change=change),self.assertRaises(ValueError):M.validate(binding,reader=lambda p:values[p['path']])

    def test_reference_is_actual_published_and_adopted543(self):
        binding,values=fixture();reference=binding['reference'];closure=values[binding['previous_campaign']['closure']['path']]
        metadata=values[reference['metadata']['path']];M.check_reference(reference,metadata,closure)
        for change in ('old448','unqualified','unpublished'):
            r=copy.deepcopy(reference);m=copy.deepcopy(metadata);c=copy.deepcopy(closure)
            if change=='old448':r['path']=str(M.GAME/'models_dqn/managed-incumbents/fresh3-448M-confirmed.pt')
            elif change=='unqualified':c['accepted_quality_outcome']='not_improved'
            else:m['assessment']['qualified_improvement']=False
            with self.subTest(change=change),self.assertRaises(ValueError):M.check_reference(r,m,c)
        values[binding['previous_campaign']['adoption']['path']]['checkpoint_sha256']='9'*64
        with self.assertRaises(ValueError):M.validate(binding,reader=lambda p:values[p['path']])

    def test_actual_forward_recovery_shape_without_old_READY_alias(self):
        for change in ('old-ready','owner','phase','retry','boot-snapshot'):
            binding,values=fixture();capture=values[binding['evidence']['capture_result']['path']]
            job=values[capture['root_job']['path']];rec=values[job['recovery']['result']['path']]
            if change=='old-ready':rec['status']='READY'
            elif change=='owner':rec['owner']=dict(rec['owner'],pid=999)
            elif change=='phase':rec['startup']['phase']['expected']['phase_id']='foreign'
            elif change=='retry':rec['trial_retried']=True
            else:rec['startup']['phase']['boot_verification']['sha256']='8'*64
            with self.subTest(change=change),self.assertRaises(ValueError):M.validate(binding,reader=lambda p:values[p['path']])

    def test_original_failure_unknown_release_or_wrong_predecessor_refuses(self):
        for change in ('failed-original','no-release','foreign-plan'):
            binding,values=fixture();closure=values[binding['previous_campaign']['closure']['path']]
            if change=='failed-original':closure['original_execution']['exit_status']=1
            elif change=='no-release':binding['previous_campaign']['source_freeze_release']=None
            else:values[closure['root_job']['path']]['binding_job']['sha256']='9'*64
            with self.subTest(change=change),self.assertRaises(ValueError):M.validate(binding,reader=lambda p:values[p['path']])

    def test_exact_cpu_command_and_source_copy_join(self):
        for change in ('bad-job','alias','failed-cpu'):
            binding,values=fixture();cpu=values[binding['evidence']['phase_cpu_job']['path']];completion=values[binding['evidence']['phase_cpu_completion']['path']]
            if change=='bad-job':completion['argv'][9]='9'*64
            elif change=='alias':cpu['verification_copy']['identity']['inode']=cpu['source']['identity']['inode']
            else:completion['exit_code']=1
            with self.subTest(change=change),self.assertRaises(ValueError):M.validate(binding,reader=lambda p:values[p['path']])

    def test_real_reader_requires_independent_readonly_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'report.json';p.write_text('{"status":"PASS"}\n');os.chmod(p,0o644)
            def pin():return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,identity=M.identity(p.stat()))
            with self.assertRaises(ValueError):M.read(pin())
            os.chmod(p,0o444);self.assertEqual(M.read(pin()),{'status':'PASS'})
            stale=pin();os.chmod(p,0o644);p.write_text('{"status":"FAIL"}\n');os.chmod(p,0o444)
            with self.assertRaises(ValueError):M.read(stale)
            os.chmod(p,0o644);p.write_text('{"unused_optional_API_value":NaN}\n');os.chmod(p,0o444)
            with self.assertRaises(ValueError):M.read(pin())
            self.assertIn('unused_optional_API_value',M.read_api(pin()))

    def test_fresh_readiness_uses_recovery_resource_API_and_exact_unit_names(self):
        spec=importlib.util.spec_from_file_location('_recovered_ce_readiness_contract',HERE/'collect_readiness.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('default read')),mock.patch.object(module,'load',side_effect=AssertionError('default import')),mock.patch('builtins.print'):
            self.assertEqual(module.main([]),0)
        tree=ast.parse((HERE/'collect_readiness.py').read_text())
        collect=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='collect')
        calls=[n for n in ast.walk(collect) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertTrue(any(isinstance(n.func.value,ast.Name) and n.func.value.id=='capture' and n.func.attr=='recovery_context' for n in calls))
        self.assertTrue(any(isinstance(n.func.value,ast.Name) and n.func.value.id=='capture' and n.func.attr=='current_ce_and_resources' for n in calls))
        self.assertEqual(module.CAPTURE_UNIT,'robotron-live-ce-postRecovery-candidate02-capture-20261017')
        self.assertEqual(module.CPU_UNIT,'robotron-live-ce-postRecovery-candidate02-phase-cpu-20261017')
        self.assertEqual(module.CARRIER_SHA,hashlib.sha256((HERE/'root_quality_carrier.py').read_bytes()).hexdigest())
        binding,values=fixture();bundle=M.validate(binding,reader=lambda p:values[p['path']])
        class ReachedActualResources(Exception):pass
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);bound_pin={'actual':'binding full PIN'}
            carrier=SimpleNamespace(configure=lambda args:None,BINDING_PIN=bound_pin,CFG=binding,BUNDLE=bundle,
                inputs=lambda args:({},None),BINDINGS=SimpleNamespace(read=lambda pin:{}))
            context={'recovery':{'owner':binding['runtime_anchor']['main_owner']}}
            capture=SimpleNamespace(Files=lambda ops:SimpleNamespace(read_json=lambda pin:values[pin['path']]),
                recovery_context=mock.Mock(return_value=context),current_ce_and_resources=mock.Mock(side_effect=ReachedActualResources))
            job=dict(schema=module.SCHEMA,binding_job=dict(bound_pin,path='/actual/binding.json',sha256='a'*64),
                output_directory=str(root/'fresh'),fleet_descriptor={'actual':'fleet PIN'})
            carrier.BINDING_PIN=job['binding_job']
            with mock.patch.object(module,'RUN',root),self.assertRaises(ReachedActualResources):
                module.collect(job,{'job':'PIN'},carrier,capture,SimpleNamespace())
            capture.recovery_context.assert_called_once()
            self.assertIn('recovery',capture.recovery_context.call_args.args[0])
            self.assertNotIn('history',capture.recovery_context.call_args.args[0])
            capture.current_ce_and_resources.assert_called_once()
            self.assertIs(capture.current_ce_and_resources.call_args.args[1],context)

    def test_consumers_keep_original_scoring_and_default_has_no_reads(self):
        old=HERE.parent/'fresh_quality_trial02_binding_companions_proposal'
        before=(old/'audit_completed_leg.py').read_text();after=(HERE/'audit_completed_leg.py').read_text()
        start='        legdir = directory /';end='\n\ndef configure(args):'
        self.assertEqual(before[before.index(start):before.index(end)],after[after.index(start):after.index(end)])
        for name in ('root_quality_carrier.py','audit_completed_leg.py'):
            spec=importlib.util.spec_from_file_location('_default_ce_'+name[:-3],HERE/name);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('default read')),mock.patch('builtins.print'):
                self.assertEqual(module.main([]),0)
        old_tree=ast.parse((old/'root_quality_carrier.py').read_text());new_tree=ast.parse((HERE/'root_quality_carrier.py').read_text())
        for name in ('default_argv','launch_argv','validate_plan','source_checks'):
            a=next(n for n in old_tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in new_tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a),ast.dump(b))


if __name__ == '__main__':unittest.main()
