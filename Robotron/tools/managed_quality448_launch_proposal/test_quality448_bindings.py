"""Authored unexecuted stdlib contracts for changed immutable launch bindings."""
from contextlib import redirect_stdout
import copy
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import root_quality448_carrier as carrier


class ChangedBindingContracts(unittest.TestCase):
    def test_default_does_not_read_plan_candidate_helpers_or_runtime(self):
        with patch.object(carrier,'prepare',side_effect=AssertionError('no materialization')), \
                patch.object(carrier,'launch',side_effect=AssertionError('no launch')), \
                patch.object(carrier,'sha',side_effect=AssertionError('no data read')), \
                patch.object(carrier,'call',side_effect=AssertionError('no command')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(carrier.main([]),0)
        self.assertIn('PLAN_ONLY',out.getvalue())

    def test_exact_canonical_argv_is_required_before_append_launch(self):
        original=carrier.default_argv()
        self.assertEqual(carrier.launch_argv(original),original+['--launch']);self.assertNotIn('--launch',original)
        for kind in ('cohort','checkpoint','diagnostics','extra-launch'):
            changed=list(original)
            if kind=='cohort':changed[changed.index('--cohort-s')+1]='600'
            if kind=='checkpoint':changed[changed.index('--candidate-checkpoint')+1]='/other.pt'
            if kind=='diagnostics':changed.remove('--game-boundary-diagnostics')
            if kind=='extra-launch':changed.append('--launch')
            with self.subTest(kind=kind),self.assertRaisesRegex(RuntimeError,'canonical profile'):
                carrier.launch_argv(changed)

    def cpu_fixture(self):
        class FakePath:
            def __init__(self,name):self.name=name
            def __str__(self):return self.name
            def stat(self):return SimpleNamespace(st_size=200<<20,st_mode=0o444)
        candidate,reference=FakePath('/candidate.pt'),FakePath('/reference.pt')
        args=SimpleNamespace(candidate_sha256='c'*64,candidate_bytes=200<<20,
            root_job=Path('/job.json'),root_job_sha256='j'*64,cpu_proof=Path('/proof.json'),cpu_proof_sha256='p'*64,
            cpu_completion=Path('/completion.json'),cpu_completion_sha256='d'*64)
        job=dict(schema='robotron-managed-candidate-checkpoint-CPU-job-v1',verifier_sha256=carrier.CPU_WRAPPER_SHA,
            candidate=dict(tag='fresh3-448M',target_learner_frames=carrier.TARGET),
            source=dict(path=str(candidate),sha256=args.candidate_sha256,bytes=args.candidate_bytes),verification_copy=dict(path='/copy.pt'))
        proof=dict(schema='robotron-managed-candidate-checkpoint-CPU-result-v1',status='PASS',root_job=copy.deepcopy(job),
            job_file=dict(sha256=args.root_job_sha256),script=dict(sha256=carrier.CPU_WRAPPER_SHA),
            sha256=args.candidate_sha256,bytes=args.candidate_bytes,path='/copy.pt',clocks=dict(learner_frame_count=carrier.TARGET))
        completion=dict(status='PASS',original_exec_code=1,original_exit=0,original_result='success',
            original_terminal_archived_before_release=True,owned_unit_released=True,original_pid=123,original_invocation='a'*32,
            job_sha256=args.root_job_sha256,cpu_verification=str(args.cpu_proof),cpu_verification_sha256=args.cpu_proof_sha256)
        def invoke():
            values=[(job,dict(path=str(args.root_job),sha256=args.root_job_sha256)),
                    (proof,dict(path=str(args.cpu_proof),sha256=args.cpu_proof_sha256)),
                    (completion,dict(path=str(args.cpu_completion),sha256=args.cpu_completion_sha256))]
            with patch.object(carrier,'CANDIDATE',candidate),patch.object(carrier,'REFERENCE',reference), \
                    patch.object(carrier,'pinned_json',side_effect=values), \
                    patch.object(carrier,'sha',side_effect=lambda path:args.candidate_sha256 if path is candidate else carrier.REFERENCE_SHA):
                return carrier.inputs(args)
        return args,job,proof,completion,invoke

    def test_authentic_job_proof_and_matching_original_cpu_completion_join(self):
        args,job,proof,completion,invoke=self.cpu_fixture()
        bound,actual=invoke();self.assertEqual(actual,job)
        self.assertEqual(bound['cpu_proof']['sha256'],args.cpu_proof_sha256)
        self.assertEqual(bound['candidate_sha256'],args.candidate_sha256)

    def test_unrelated_cpu_success_or_report_job_mismatch_cannot_launch(self):
        for kind in ('completion-job','completion-report','completion-path','not-released','not-archived','proof-job'):
            args,job,proof,completion,invoke=self.cpu_fixture()
            if kind=='completion-job':completion['job_sha256']='other'
            if kind=='completion-report':completion['cpu_verification_sha256']='other'
            if kind=='completion-path':completion['cpu_verification']='/other.json'
            if kind=='not-released':completion['owned_unit_released']=False
            if kind=='not-archived':completion['original_terminal_archived_before_release']=False
            if kind=='proof-job':proof['job_file']['sha256']='other'
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):invoke()

    def readiness_fixture(self):
        actors=[dict(pid=1000+index,starttime_ticks=2000+index,slot=index,mask=list(range(72))) for index in range(192)]
        health=dict(actors=actors,source_hashes={('/source/%02d'%index):'s'*64 for index in range(60)},
            control_hashes={'/control/a':'a'*64,'/control/b':'b'*64})
        bound=dict(candidate_sha256='c'*64,candidate_bytes=200<<20,job=dict(sha256='j'*64),cpu_proof=dict(sha256='p'*64))
        resources={name:True for name in ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free',
            'no_competing_helpers','no_private_cgroup_tmpfs_processes','no_pending_save','capture_and_CPU_units_released',
            'commands_UID_cwd_exe_checked','held_environment_checked','unit_files_checked')}
        resources.update(gpu0_uuid=carrier.GPU0,gpu1_uuid=carrier.GPU1,GPU0_free_bytes=14*(1<<30))
        value=dict(schema='robotron-quality448-exclusive-readiness-v1',status='PASS',observed_unix_s=999,
            candidate=dict(source=str(carrier.CANDIDATE),sha256='c'*64,bytes=200<<20,root_job_sha256='j'*64,cpu_proof_sha256='p'*64),
            main_owner=dict(pid=4140916,starttime_ticks=31570251,invocation_id='cf4f26d3c5b84d9ab1302ded3a073519'),
            fleet_owner=dict(pid=2258189,starttime_ticks=26614335,invocation_id='5ade9b2810524877921946df11ea597e'),
            inference_worker=dict(tid=4142023,starttime_ticks=31574570,mask=list(range(72))),actors=copy.deepcopy(actors),
            source_hashes=copy.deepcopy(health['source_hashes']),control_hashes=copy.deepcopy(health['control_hashes']),
            resources=resources,unit_files={'/unit':'u'*64},environment_sha256='e'*64)
        def invoke():
            with patch.object(carrier,'pinned_json',return_value=(health,{})),patch.object(carrier,'sha',return_value='u'*64), \
                    patch.object(carrier.time,'time',return_value=1000):carrier.readiness_contract(value,bound)
        return value,invoke

    def test_fresh_observed_owner_candidate_sources_resources_readiness_joins(self):
        value,invoke=self.readiness_fixture();invoke()

    def test_copied_fresh_file_cannot_rescue_stale_or_contradictory_readiness(self):
        for kind in ('time','candidate','main','thread','actor','source','gpu','helpers'):
            value,invoke=self.readiness_fixture()
            if kind=='time':value['observed_unix_s']=700
            if kind=='candidate':value['candidate']['sha256']='other'
            if kind=='main':value['main_owner']['starttime_ticks']+=1
            if kind=='thread':value['inference_worker']['starttime_ticks']+=1
            if kind=='actor':value['actors'][0]['pid']+=10000
            if kind=='source':value['source_hashes']['/source/00']='other'
            if kind=='gpu':value['resources']['GPU0_free_bytes']-=1
            if kind=='helpers':value['resources']['no_competing_helpers']=False
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):invoke()


if __name__=='__main__':
    unittest.main()
