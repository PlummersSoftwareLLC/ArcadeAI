"""Focused authored stdlib guards; no application/model execution."""
import contextlib
import copy
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock
from . import run_forward_ce_repair as repair
from ..live_one_trial_controller_proposal import deadline_guard as metadata

CLOCKS = ('training_steps','optimized_samples','learner_frame_count','frame_count')


class RepairContracts(unittest.TestCase):
    def fixture(self):
        owner = dict(pid=489266, starttime_ticks=33093660, unit='owned.service', invocation_id='a'*32, cgroup='/owned')
        pin = lambda name: dict(path='/'+name, sha256=name, bytes=20, identity=dict(mode='0o444', nlink=1, uid=os.getuid()))
        original = dict(model_dir='/game/models_dqn', startup_tag='failed-startup')
        failed = dict(status='FAILED', mode='activate_kl', manual_recovery_required=True,
            qualification_pass=False, failed_new_owner_stopped=owner)
        source = pin('latest'); source['path']='/game/models_dqn/robotron_dqn_latest.pt'
        copied = dict(source, path='/readonly.pt')
        cpu = dict(source=source, verification_copy=copied, clock_floor={key:10 for key in CLOCKS},
            phase_snapshot=dict(purpose='newest_stopped', owner=owner, observed_clients=0,
                expected_phase=dict(metric='kl', valid=True, phase_id='failed-kl'), sources={}))
        proof = dict(status='PASS', phase_metadata_verified=True, root_job=cpu, sha256=source['sha256'], bytes=20,
            saved_priority_metric_phase=dict(metric='kl', valid=True), clocks={key:11 for key in CLOCKS})
        release = dict(status='PASS', original_exit=0, original_archived_before_release=True, unit_released=True, sha256=source['sha256'])
        job = dict(schema=repair.SCHEMA, activation_job=pin('activation'), activation_result=pin('failed'),
            newest_CPU_job=pin('cpu'), newest_CPU_report=pin('proof'), newest_CPU_release=pin('release'),
            repair_intent=pin('intent'), phase_id='new-ce', startup_tag='new-ce-startup')
        intent = dict(schema='robotron-raw-kl-forward-CE-repair-intent-v1', mode='return_ce', phase_id='new-ce',
            original_failed_activation=job['activation_result'], no_trial_retry=True,
            newest_checkpoint={key:source[key] for key in ('path','sha256','bytes')})
        values = dict(activation=original, failed=failed, cpu=cpu, proof=proof, release=release, intent=intent)
        base = NS(read_json=lambda value: values[value['sha256']], pin=mock.Mock(), MAX_SOURCE=4<<20)
        adapter = NS(CLOCKS=CLOCKS, triple=lambda value: {key:value[key] for key in ('path','sha256','bytes')})
        return job, base, adapter, values

    def test_default_PLAN_never_reads_jobs_imports_helpers_or_starts(self):
        with mock.patch.object(repair, 'load', side_effect=AssertionError('import')), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('read')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(repair.main([]), 0)

    def test_valid_separate_newest_client0_proof_is_consumed_without_CPU_rerun(self):
        job, base, adapter, values = self.fixture()
        self.assertEqual(repair.validate(job, base, adapter)[-1], values['failed']['failed_new_owner_stopped'])
        self.assertEqual(values['failed']['status'], 'FAILED')

    def test_writable_bootproof_wrong_client_or_old_checkpoint_is_not_relabelled(self):
        for kind in ('writable','clients','stale','failed_exit'):
            with self.subTest(kind=kind):
                job, base, adapter, values = self.fixture()
                if kind=='writable': job['newest_CPU_report']['identity']['mode']='0o644'
                elif kind=='clients': values['cpu']['phase_snapshot']['observed_clients']=192
                elif kind=='stale': values['proof']['clocks']['training_steps']=9
                else: values['release']['original_exit']=1
                with self.assertRaises(RuntimeError): repair.validate(job, base, adapter)

    def test_failed_startup_job_cannot_substitute_for_actual_newest_purpose(self):
        job, base, adapter, values = self.fixture(); values['cpu']['phase_snapshot']['purpose']='startup'
        with self.assertRaisesRegex(RuntimeError,'newest-stopped'): repair.validate(job, base, adapter)

    def test_real_0644_report_gets_independent_byteexact444_archive_without_chmod_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); original=root/'original.json'; original.write_bytes(b'{"status":"PASS"}\n'); original.chmod(0o644)
            fingerprint=lambda path,limit=None: metadata.pin(path,limit or metadata.LIMIT)[0]
            def sync(path):
                fd=os.open(path,os.O_DIRECTORY)
                try: os.fsync(fd)
                finally: os.close(fd)
            base=NS(MAX_JSON=2<<20, identity=metadata.identity, fingerprint=fingerprint,
                pin=lambda value,limit=None: self.assertEqual(fingerprint(value['path'],limit),value),fsync_directory=sync)
            before=fingerprint(original); archived=repair.archive_report(base,before,root/'archived.json')
            self.assertEqual(archived['sha256'],before['sha256']);self.assertEqual(archived['identity']['mode'],'0o444')
            self.assertNotEqual(archived['identity']['inode'],before['identity']['inode'])
            self.assertEqual(fingerprint(original),before)

    def test_archive_never_replaces_an_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source';source.write_bytes(b'{}');target=root/'held';target.write_bytes(b'held')
            fingerprint=lambda path,limit=None: metadata.pin(path,limit or metadata.LIMIT)[0]
            base=NS(pin=lambda *a:None,MAX_JSON=2<<20,identity=metadata.identity)
            with self.assertRaises(FileExistsError): repair.archive_report(base,fingerprint(source),target)
            self.assertEqual(target.read_bytes(),b'held')

    def runtime(self,fail=False):
        order=[]
        def call(name,value=None):
            def run(*a,**kw):
                order.append(name)
                if fail and name=='startupCPU':raise RuntimeError('first CE startup CPU failure')
                return value
            return run
        host=NS(paused=[],pause=call('pause'),unit=lambda unit:dict(MainPID='0'))
        runtime=NS(absence=call('absence'),host=host,job=dict(before={},bank_spec={},trainer_unit='owned'),
            banks=NS(stopped_state=call('banks',{}),assert_unchanged=call('headers')),
            expected_sources=lambda phase:{}, start_phase=call('CEstart',dict(pid=9)),
            ready_transport=lambda phase,banks,actors:call('healthy192' if actors else 'zeroReady',{})(),
            raw_api=lambda:dict(client_count=0),startup_snapshot=call('startupCPU',dict(phase_CPU={})),
            inspect=call('inspect'),output=Path('/unused'),current_checkpoint={},start_request=None,record_pin={},cpu_attempts={})
        base=NS(publish=lambda *a:{},resume_all=lambda host:call('resume',dict(failures=[]))())
        adapter=NS(zero_replay=lambda *a:None)
        return runtime,base,adapter,order

    def test_newest_CE_start_then_startupCPU_and_archive_precede_first_resume(self):
        runtime,base,adapter,order=self.runtime()
        with mock.patch.object(repair,'archive_report',side_effect=lambda *a:order.append('archive') or {}):
            result=repair.restore(runtime,base,adapter)
        self.assertEqual(result['status'],'READY_CE_FORWARD_REPAIR')
        self.assertLess(order.index('CEstart'),order.index('startupCPU'))
        self.assertLess(order.index('archive'),order.index('resume'))
        self.assertFalse(result['trial_retried']);self.assertTrue(result['original_trial_failed'])

    def test_first_CE_startupCPU_failure_is_preserved_and_all_actor_undo_attempted(self):
        runtime,base,adapter,order=self.runtime(fail=True)
        result=repair.restore(runtime,base,adapter)
        self.assertEqual(result['status'],'FAILED');self.assertEqual(order.count('CEstart'),1)
        self.assertEqual(order[-1],'resume');self.assertEqual(order.count('resume'),1)


if __name__=='__main__':unittest.main()
