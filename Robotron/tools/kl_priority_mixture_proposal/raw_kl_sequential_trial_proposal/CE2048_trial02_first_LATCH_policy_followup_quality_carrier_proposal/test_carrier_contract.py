"""Authored, unexecuted stdlib carrier contracts; every runtime call is mocked."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('_ce2048_first_latch_followup_carrier_contract',HERE/'root_quality_carrier.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
ORIGINAL=HERE.parent/'CE2048_trial02_quality_carrier_proposal/root_quality_carrier.py'


def fixture():
    # Selection interface only; the separate binder authenticates all science,
    # original identities and phase CPU evidence. These are synthetic fixtures.
    pin=lambda name:dict(path='/fixture/'+name,sha256='a'*64,bytes=100)
    phase=dict(record=pin('new-returned-CE4096-phase.json'),expected={'metric':'ce'})
    anchor=dict(main_owner={'pid':100,'starttime_ticks':200,'unit':'new-ce.service','invocation_id':'b'*32},
        fleet_owner={'pid':101,'starttime_ticks':201,'unit':'fleet.service','invocation_id':'c'*32},
        inference_worker={'tid':102,'starttime_ticks':202,'mask':list(range(72))},
        actors=[dict(pid=1000+i,starttime_ticks=2000+i,slot=i,mask=list(range(72))) for i in range(192)],
        source_hashes={'/fixture/source'+str(i):'d'*64 for i in range(61)},
        control_hashes={'/fixture/control1':'e'*64,'/fixture/control2':'f'*64},
        unit_files={'/fixture/unit':'a'*64},environment_sha256='e'*64)
    evidence={name:pin(name+'.json') for name in
        ('phase_cpu_job','phase_cpu_report','phase_cpu_completion','trial_result','failed_return',
         'maintenance_result','maintenance_closure','maintenance_release','followup_precommit')}
    cfg=dict(experiment='authenticated-root-experiment',candidate=dict(path='/fixture/candidate.pt',tag='first-real-candidate',
        sha256='1'*64,bytes=275190000),reference=dict(path='/fixture/protected543.pt',sha256='2'*64,bytes=275192614),
        evidence=evidence,runtime_baseline=pin('baseline.json'),runtime_anchor=anchor,
        campaign=dict(reference_label='protected543',candidate_label='first-CE2048',hypothesis='Policy quality only.'))
    bundle=dict(cpu_job={'authenticated':'typed2048 job supplied by binder'},proof={'authenticated':'report'},
        completion={'authenticated':'inline original0'},trial={'status':'FAILED'},activation={'status':'READY'},
        failed_return={'status':'FAILED','mode':'return_batch4096'},
        maintenance={'status':'READY_CE_FORWARD_REPAIR','startup':{'phase':phase},
            'healthy192':{'api':{'client_count':192},'binding':{'environment':{'DQN_BATCH_SIZE':'4096'}}}},
        baseline=anchor,predecessor={})
    return cfg,bundle


class CE2048FollowupCarrierContracts(unittest.TestCase):
    def test_actual_inputs_keep_FAILED_trial_and_select_genuine_maintenance_shape(self):
        cfg,bundle=fixture();candidate=SimpleNamespace(stat=lambda:SimpleNamespace(st_size=cfg['candidate']['bytes'],st_mode=0o444))
        reference=SimpleNamespace(stat=lambda:SimpleNamespace(st_mode=0o444))
        def digest(path):return cfg['candidate']['sha256'] if path is candidate else cfg['reference']['sha256']
        with mock.patch.multiple(M,CFG=cfg,BUNDLE=bundle,BINDING_PIN={'root':'actual binding PIN'},
            CANDIDATE=candidate,REFERENCE=reference,REFERENCE_SHA=cfg['reference']['sha256']),mock.patch.object(M,'sha',side_effect=digest):
            bound,job=M.inputs(None)
        self.assertEqual(job,bundle['cpu_job'])
        for name in ('trial_result','failed_return','maintenance_result','maintenance_closure','maintenance_release','followup_precommit'):
            self.assertEqual(bound[name],cfg['evidence'][name])
        self.assertEqual(bound['current_ce_phase'],bundle['maintenance']['startup']['phase'])
        self.assertNotIn('live_ce_capture',bound);self.assertNotIn('original_executions',cfg)
        self.assertNotIn('capture_result',cfg['evidence']);self.assertNotIn('current_ce_phase',cfg)
        self.assertNotIn('ce_return',bundle);self.assertNotIn('ce_return',bound);self.assertNotIn('owned_cleanup',bound)
        self.assertEqual(bundle['trial']['status'],'FAILED');self.assertEqual(bundle['failed_return']['status'],'FAILED')

    def test_readiness_requires_owned_trial_units_and_actual_new_owner(self):
        cfg,bundle=fixture();candidate=Path(cfg['candidate']['path'])
        bound=dict(candidate_sha256=cfg['candidate']['sha256'],candidate_bytes=cfg['candidate']['bytes'],
            phase_cpu_job=cfg['evidence']['phase_cpu_job'],phase_cpu_proof=cfg['evidence']['phase_cpu_report'])
        resources={name:True for name in ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free',
            'no_competing_helpers','no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released',
            'commands_UID_cwd_exe_checked','held_environment_checked','unit_files_checked')}
        resources.update(gpu0_uuid=M.GPU0,gpu1_uuid=M.GPU1,GPU0_free_bytes=14*(1<<30))
        ready=dict(copy.deepcopy(cfg['runtime_anchor']),schema='robotron-CE2048-trial02-first-LATCH-policy-followup-exclusive-readiness-v1',
            status='PASS',observed_unix_s=1,resources=resources,candidate=dict(source=str(candidate),
                sha256=bound['candidate_sha256'],bytes=bound['candidate_bytes'],
                root_job_sha256=bound['phase_cpu_job']['sha256'],cpu_proof_sha256=bound['phase_cpu_proof']['sha256']))
        with (mock.patch.multiple(M,CFG=cfg,BUNDLE=bundle,CANDIDATE=candidate),mock.patch.object(M.time,'time',return_value=2),
            mock.patch.object(M,'sha',return_value='a'*64)):
            M.readiness_contract(ready,bound)
            for change in ('units','owner','legacy_schema'):
                bad=copy.deepcopy(ready)
                if change=='units':bad['resources']['owned_units_released']=False
                elif change=='owner':bad['main_owner']['pid']=620749
                else:bad['schema']='robotron-live-CE-exclusive-readiness-v1'
                with self.subTest(change=change),self.assertRaises(RuntimeError):M.readiness_contract(bad,bound)

    def test_real_launch_with_new_schema_reaches_only_own_unit_checks_and_one_schedule(self):
        cfg,bundle=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);preview=root/'preview';preview.mkdir();execution=root/'execution';output=root/'campaign'
            bound=dict(candidate_sha256=cfg['candidate']['sha256'],candidate_bytes=cfg['candidate']['bytes'])
            (preview/'default-plan.json').write_text('{}')
            (preview/'root-default-plan-source-review.json').write_text(json.dumps(dict(actual_inputs=bound,plan_sha256='plan-sha')))
            seen=[]
            def show(unit):
                seen.append(unit)
                if len(seen)<=2:return {},dict(LoadState='not-found')
                if unit.endswith('.timer'):return {},dict(ActiveState='active',SubState='waiting')
                return {},dict(MainPID='0')
            args=SimpleNamespace(plan_sha256='plan-sha',plan_review=root/'review.json',plan_review_sha256='review-sha',
                runtime_readiness=root/'readiness.json',runtime_readiness_sha256='readiness-sha')
            review=dict(status='PASS',plan_sha256='plan-sha',actual_inputs=bound)
            with (mock.patch.multiple(M,CFG=cfg,BUNDLE=bundle,D=preview,J=execution,OUT=output,U='robotron-quality-newtyped',
                    REFERENCE=Path(cfg['reference']['path']),CANDIDATE=Path(cfg['candidate']['path'])),
                mock.patch.object(M,'inputs',return_value=(bound,bundle['cpu_job'])),mock.patch.object(M,'sha',return_value='plan-sha'),
                mock.patch.object(M,'validate_plan'),mock.patch.object(M,'source_checks'),
                mock.patch.object(M,'pinned_json',side_effect=[(review,{}),({}, {})]),
                mock.patch.object(M,'readiness_contract'),mock.patch.object(M,'fast_runtime',return_value={'healthy':True}),
                mock.patch.object(M,'show',side_effect=show),
                mock.patch.object(M,'call',return_value=dict(returncode=0,stdout='',stderr='')) as schedule):
                (preview/'default-argv.json').write_text(json.dumps(M.default_argv()))
                result=M.launch(args)
            self.assertEqual(result['status'],'DURABLE_LAUNCH_SUBMITTED')
            self.assertEqual(seen,['robotron-quality-newtyped.service','robotron-quality-newtyped.timer',
                'robotron-quality-newtyped.timer','robotron-quality-newtyped.service'])
            schedule.assert_called_once();self.assertEqual(schedule.call_args.args[0][0],'systemd-run')
            self.assertEqual(schedule.call_args.args[0][-1],'--launch')

    def test_default_plan_and_preserved_protocol_lifecycle_bodies(self):
        raw=ORIGINAL.read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '73adaf9ea02a643208439810e30a071d317bf5956720f88e3e22b0ce4fced78b')
        def bodies(raw):
            text=raw.decode();return {node.name:ast.get_source_segment(text,node) for node in ast.parse(text).body
                if isinstance(node,ast.FunctionDef)}
        old,new=bodies(raw),bodies((HERE/'root_quality_carrier.py').read_bytes())
        for name in ('require','sha','write','call','show','pinned_json','default_argv','launch_argv','validate_plan',
            'source_checks','prepare','launch','observe','archive'):
            with self.subTest(function=name):self.assertEqual(old[name],new[name])
        self.assertEqual(len(M.BINDINGS_SHA),64)
        self.assertEqual(hashlib.sha256(M.BINDINGS_SOURCE.read_bytes()).hexdigest(),M.BINDINGS_SHA)
        binder_names={node.name for node in ast.parse(M.BINDINGS_SOURCE.read_text()).body if isinstance(node,ast.FunctionDef)}
        self.assertTrue({'identity','read','validate'}<=binder_names)
        with (mock.patch.object(M,'configure',side_effect=AssertionError('No configure')) as configure,
            mock.patch.object(M,'sha',side_effect=AssertionError('No file read')),
            mock.patch.object(M,'call',side_effect=AssertionError('No command')),contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(M.main([]),0)
        configure.assert_not_called();self.assertIn('PLAN_ONLY',output.getvalue())


if __name__=='__main__':unittest.main()
