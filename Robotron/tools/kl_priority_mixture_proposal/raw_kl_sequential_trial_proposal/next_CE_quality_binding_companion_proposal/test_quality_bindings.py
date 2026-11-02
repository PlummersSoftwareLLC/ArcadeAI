"""Authored metadata-only contracts. No runtime/model helpers are imported."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
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
    record = pin('phase-record',dict(metric='ce',checkpoint=boot_checkpoint))
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
    summary = pin('previous-summary',dict(plan_sha256=M.PREDECESSOR_PLAN_SHA,outcome='not_improved'))
    summary['path']=str(M.PREDECESSOR_PLAN.parent/'summary.json')
    closure_job = pin('closure-job',dict(schema='robotron-trial02-quality-owned-closure-job-v1',
        binding_job={'sha256':'3b16c36da91c63fd4fb218f1fed3c1c5a5fe8caff73534d880aeaeccfe4c81fe'},terminal_summary=summary))
    closure = pin('closure',dict(status='PASS_ORIGINAL_QUALITY_ARCHIVED_OWNED_CLEANUP_COMPLETE',owned_cleanup_complete=True,
        main192_and_resources_healthy=True,original_execution=dict(exec_code=1,exit_status=0,result='success',archived_before_release=True),
        root_job=closure_job,accepted_quality_outcome='not_improved'))
    reference = dict(path=next(iter(M.REFERENCES)),sha256=next(iter(M.REFERENCES.values())),bytes=275181008)
    metadata = pin('protected-reference',dict(schema='robotron-protected-quality-winner-v1',protected_checkpoint=reference['path'],
        checkpoint_sha256=reference['sha256'],assessment={'qualified_improvement':True}))
    values[reference['path']+'.json'] = values.pop(metadata['path']); metadata['path']=reference['path']+'.json'; reference['metadata']=metadata
    release = pin('freeze-release',dict(schema='robotron-quality-campaign-root-source-freeze-release-v1',source_freeze_released=True,
        actual_plan_sha256=M.PREDECESSOR_PLAN_SHA,campaign_outcome='not_improved',actual_quality_cleanup={k:closure[k] for k in ('path','sha256','bytes')},
        protected_incumbent={k:reference[k] for k in ('path','sha256','bytes')}))
    values[str(M.FREEZE_RELEASE)]=values.pop(release['path']);release.update(path=str(M.FREEZE_RELEASE),sha256=M.FREEZE_RELEASE_SHA)
    anchor = dict(main_owner=owner,fleet_owner=owner,inference_worker={'tid':101,'starttime_ticks':202,'mask':list(range(72))},
        actors=[dict(pid=1000+i,starttime_ticks=2000+i,slot=i,mask=list(range(72))) for i in range(192)],
        source_hashes={**{str(M.GAME/'Scripts/dqn'/k):v for k,v in M.CANDIDATE_SOURCES.items()},**{'other-source-'+str(i):'e'*64 for i in range(56)}},
        control_hashes={'control1':'e'*64,'control2':'f'*64},unit_files={},environment_sha256='f'*64)
    baseline = pin('baseline',dict(anchor,status='PASS'))
    predecessor = pin('predecessor',dict(evaluator_source_hashes=M.EVALUATOR,execution_source_hashes=M.EXECUTION))
    values[str(M.PREDECESSOR_PLAN)]=values.pop(predecessor['path']); predecessor.update(path=str(M.PREDECESSOR_PLAN),sha256=M.PREDECESSOR_PLAN_SHA)
    binding = dict(schema=M.SCHEMA,experiment='best10M-fresh3-eps10-cap8-nosmooth',candidate=candidate,reference=reference,
        evidence=dict(capture_result=pin('capture-result',capture),phase_cpu_job=cpu_pin,phase_cpu_report=pin('cpu-report',proof),
            phase_cpu_completion=pin('cpu-completion',completion)),current_ce_phase=phase,runtime_baseline=baseline,runtime_anchor=anchor,
        previous_campaign=dict(closure=closure,source_freeze_release=release),predecessor_quality_plan=predecessor,
        campaign=dict(output_directory=str(M.GAME/'logs/managed-learning-20261015/new-CE-quality'),
            preview_directory=str(M.GAME/'logs/managed-learning-20261015/run-26/new-CE-preview'),
            execution_directory=str(M.GAME/'logs/managed-learning-20261015/run-26/new-CE-execution'),
            unit='robotron-quality-future-CE',reference_label='actual-protected-reference',candidate_label='new-CE-candidate',hypothesis='Frozen CE policy quality.'))
    return binding,values


class LiveCEBindingContracts(unittest.TestCase):
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

    def test_reference_selection_follows_actual_previous_outcome(self):
        binding,values=fixture();reference=binding['reference'];closure=values[binding['previous_campaign']['closure']['path']]
        path,sha=list(M.REFERENCES.items())[1];reference.update(path=path,sha256=sha);reference['metadata']['path']=path+'.json'
        metadata=dict(schema='robotron-protected-quality-winner-v1',protected_checkpoint=path,checkpoint_sha256=sha,
            plan_sha256=M.PREDECESSOR_PLAN_SHA,assessment={'qualified_improvement':True})
        with self.assertRaises(ValueError):M.check_reference(reference,metadata,closure)
        closure['accepted_quality_outcome']='qualified_improvement';M.check_reference(reference,metadata,closure)
        metadata['assessment']['qualified_improvement']=False
        with self.assertRaises(ValueError):M.check_reference(reference,metadata,closure)

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
