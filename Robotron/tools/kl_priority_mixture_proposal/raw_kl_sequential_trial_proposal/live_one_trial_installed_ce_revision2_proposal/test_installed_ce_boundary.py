"""Authored stdlib boundary regressions; root alone may execute them."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from . import deadline_guard as metadata
from . import run_raw_kl_transition as adapter


class InstalledCEBoundaryContracts(unittest.TestCase):
    def base(self):
        def fingerprint(path, maximum=None):
            return metadata.pin(path, maximum or metadata.LIMIT)[0]
        def pin(value, maximum=None):
            self.assertEqual(fingerprint(value['path'], maximum), value)
            return value
        def sync(directory):
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try: os.fsync(fd)
            finally: os.close(fd)
        return NS(Runtime=object, MAX_SOURCE=4 << 20, fingerprint=fingerprint,
            identity=metadata.identity, pin=pin, read_json=lambda value: json.loads(Path(value['path']).read_text()),
            publish=metadata.publish, fsync_directory=sync, validate_python_binding=mock.Mock())

    def writable(self, root, name, value=None, mode=0o644):
        path = root / name
        path.write_text(json.dumps(value if value is not None else {'historical': name}) + '\n')
        path.chmod(mode)
        return self.base().fingerprint(path)

    def metadata_inputs(self, root):
        checkpoint=dict(path='/historical/boot.pt',sha256='b'*64,bytes=275185944)
        boot_value=dict(status='PASS',phase_metadata_verified=True,sha256=checkpoint['sha256'],
            bytes=checkpoint['bytes'],clocks=dict.fromkeys(adapter.CLOCKS,10))
        boot = self.writable(root, 'boot.json', boot_value)
        record_value=dict(metric='ce',action='start',phase_id='known-ce',root_precommit_sha256='c'*64,
            checkpoint=checkpoint)
        record=self.writable(root,'record.json',record_value,mode=0o444)
        context = dict(model_package={'unchanged': 'current-source-pins'},
            archived_control=self.writable(root, 'control.json', mode=0o664),
            archived_trainer_unit=self.writable(root, 'unit.json'),
            provenance=[self.writable(root, 'provenance.json', mode=0o664)])
        return dict(record=record,boot_checkpoint=checkpoint,boot_verification=boot,
            expected=adapter.expected_start(record_value,record,boot_value)),context

    def test_literal_PLAN_has_no_job_reads_helper_imports_or_actions(self):
        with mock.patch.object(adapter, 'load_v4', side_effect=AssertionError('helper import')), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('read')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(adapter.main([]), 0)

    def test_real_writable_boot_and_all_context_archives_become_consumed_independent444(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); base = self.base(); phase, context = self.metadata_inputs(root)
            old_phase, old_context = copy.deepcopy(phase), copy.deepcopy(context)
            new_phase, new_context, evidence = adapter.phase_metadata(base, phase, context, root / 'archives')
            self.assertEqual(phase, old_phase); self.assertEqual(context, old_context)
            self.assertEqual(new_context['model_package'], context['model_package'])
            consumed = [new_phase['boot_verification'], new_context['archived_control'],
                new_context['archived_trainer_unit'], *new_context['provenance']]
            self.assertEqual(len(consumed), len(evidence))
            self.assertEqual({value['path'] for value in consumed},
                {row['archive']['path'] for row in evidence.values()})
            for row in evidence.values():
                before, archived = row['original'], row['archive']
                self.assertEqual(base.fingerprint(before['path']), before)
                self.assertEqual(archived['sha256'], before['sha256'])
                self.assertEqual(archived['identity']['mode'], '0o444')
                self.assertEqual(archived['identity']['nlink'], 1)
                self.assertNotEqual(archived['identity']['inode'], before['identity']['inode'])

    def test_archive_changed_source_symlink_hardlink_and_existing_destination_refuse(self):
        for kind in ('changed', 'symlink', 'hardlink', 'existing'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); base = self.base(); original = self.writable(root, 'input.json')
                source = Path(original['path']); target = root / 'archive.json'
                if kind == 'changed': source.write_text('{"different":true}')
                elif kind == 'symlink': source.rename(root/'real'); source.symlink_to(root/'real')
                elif kind == 'hardlink': os.link(source, root/'alias.json'); original=base.fingerprint(source)
                else: target.write_bytes(b'held')
                with self.assertRaises((RuntimeError, AssertionError, OSError)):
                    adapter.archive_metadata(base, original, target)
                if kind == 'existing': self.assertEqual(target.read_bytes(), b'held')

    def test_metadata_copy_does_not_admit_truncated_pt_or_replace_checkpoint_copier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); base = self.base(); original = self.writable(root, 'truncated.pt')
            with self.assertRaisesRegex(RuntimeError, 'model bytes'):
                adapter.archive_metadata(base, original, root/'archive.json')
            self.assertFalse((root/'archive.json').exists())

    def cpu_runtime(self, root):
        base = self.base(); phase, context = self.metadata_inputs(root)
        runtime = adapter.runtime_class(base).__new__(adapter.runtime_class(base))
        runtime.output=root; runtime.cpu_attempts={}; runtime.verification_failed=False
        runtime.job=dict(experiment='held', verifier=dict(script=dict(sha256='s'*64), python='/never-execute-python'),
            insurance_verification={})
        runtime.phase_sources=lambda label: ({}, context)
        runtime.metrics=NS(block_restore_signals=contextlib.nullcontext)
        source=dict(path='/opaque-latest.pt', sha256='a'*64, bytes=275185944)
        copied=dict(source, path='/opaque-readonly.pt')
        acquisition=dict(client_count=192, clock_floor=dict.fromkeys(adapter.CLOCKS, 11))
        return runtime, base, phase, context, source, copied, acquisition

    def test_real_cpu_phase_consumes_archives_and_returns444_report_for_next_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); runtime,base,phase,context,source,copied,acquisition=self.cpu_runtime(root)
            def child(argv, **kwargs):
                job=json.loads(Path(argv[argv.index('--job')+1]).read_text())
                consumed=[job['phase_snapshot']['boot_verification'],
                    job['source_control_context']['archived_control'], job['source_control_context']['archived_trainer_unit'],
                    *job['source_control_context']['provenance']]
                self.assertTrue(all(value['identity']['mode']=='0o444' for value in consumed))
                self.assertNotEqual(job['phase_snapshot']['boot_verification']['path'], phase['boot_verification']['path'])
                output=Path(job['output_directory']); output.mkdir()
                self.writable(output,'cpu-verification.json',dict(status='PASS',root_job=job,
                    phase_metadata_verified=True,sha256=source['sha256'],clocks=acquisition['clock_floor']))
                return NS(returncode=0)
            with mock.patch.object(adapter.subprocess,'run',side_effect=child) as numerical:
                result,proof=runtime.cpu_phase('newest','newest_stopped',{},source,copied,phase,acquisition,'retired')
            numerical.assert_called_once()
            self.assertEqual(result['identity']['mode'],'0o444')
            self.assertEqual(result['path'],str(root/'newest/cpu-report-readonly.json'))
            original=base.fingerprint(root/'newest/cpu-output/cpu-verification.json')
            self.assertEqual(original['identity']['mode'],'0o644')
            self.assertEqual(result['sha256'],original['sha256'])
            self.assertNotEqual(result['identity']['inode'],original['identity']['inode'])
            self.assertEqual(runtime.cpu_attempts,{'retired':'passed'})
            next_phase=dict(phase,boot_verification=result)
            next_phase,_,_=adapter.phase_metadata(base,next_phase,context,root/'next-boot-metadata')
            self.assertEqual(next_phase['boot_verification']['sha256'],result['sha256'])
            self.assertNotEqual(next_phase['boot_verification']['identity']['inode'],result['identity']['inode'])
            # Same actual method handles the next startup: its input is the
            # new readonly newest report, and its output must also be archived.
            startup_acquisition=dict(acquisition,client_count=0)
            with mock.patch.object(adapter.subprocess,'run',side_effect=child):
                startup_pin,_=runtime.cpu_phase('startup','startup',{},source,copied,
                    dict(phase,boot_verification=result),startup_acquisition,'startup:unique')
            self.assertEqual(startup_pin['identity']['mode'],'0o444')
            self.assertEqual(startup_pin['path'],str(root/'startup/cpu-report-readonly.json'))
            self.assertEqual(base.fingerprint(root/'startup/cpu-output/cpu-verification.json')['identity']['mode'],'0o644')
            with self.assertRaisesRegex(RuntimeError,'already attempted'):
                runtime.cpu_phase('again','newest_stopped',{},source,copied,phase,acquisition,'retired')

    def test_archive_failure_prevents_child_and_failed_child_is_never_retried(self):
        for kind in ('archive', 'child'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); runtime,base,phase,context,source,copied,acquisition=self.cpu_runtime(root)
                if kind=='archive': Path(context['archived_control']['path']).write_text('{"changed":true}')
                with mock.patch.object(adapter.subprocess,'run',return_value=NS(returncode=1)) as numerical:
                    with self.assertRaises((RuntimeError,AssertionError)):
                        runtime.cpu_phase('one','newest_stopped',{},source,copied,phase,acquisition,'retired')
                    if kind=='archive': numerical.assert_not_called();self.assertEqual(runtime.cpu_attempts,{})
                    else:
                        self.assertEqual(runtime.cpu_attempts,{'retired':'started'})
                        self.assertTrue(runtime.verification_failed)
                        with self.assertRaisesRegex(RuntimeError,'already attempted'):
                            runtime.cpu_phase('two','newest_stopped',{},source,copied,phase,acquisition,'retired')
                        numerical.assert_called_once()

    def installed(self, metric='ce'):
        game=Path('/game'); record_pin=dict(path='/current-phase.json',sha256='r'*64)
        boot=dict(status='PASS',phase_metadata_verified=True,sha256='b'*64,bytes=275185944,
            clocks=dict.fromkeys(adapter.CLOCKS,10))
        checkpoint=dict(path='/game/models_dqn/robotron_dqn_latest.pt',sha256=boot['sha256'],bytes=boot['bytes'])
        record=dict(metric=metric,action='start',phase_id='current-phase',root_precommit_sha256='c'*64,
            checkpoint=checkpoint)
        phase=dict(record=record_pin,boot_checkpoint=checkpoint,boot_verification=dict(path='/boot-proof.json'),
            expected=adapter.expected_start(record,record_pin,boot))
        job=dict(mode='activate_kl' if metric=='ce' else 'return_ce',sources=[],running_phase=phase,
            completed_dormant_capture=None,before=dict(bindings=dict(source_hashes={
                str(game/'Scripts/dqn'/name):value for name,value in adapter.CANDIDATE.items()})))
        base=NS(read_json=lambda value: record if value==record_pin else boot)
        env=dict(DQN_PER_PRIORITY_METRIC=metric,DQN_PRIORITY_PHASE_RECORD=record_pin['path'],
            DQN_PRIORITY_PHASE_RECORD_SHA256=record_pin['sha256'])
        return job,base,game,env,record,boot

    def test_authentic_installed_CE_and_KL_phases_require_no_source_transaction(self):
        for metric in ('ce','kl'):
            with self.subTest(metric=metric):
                job,base,game,env,_,_=self.installed(metric)
                adapter.validate_installed_phase(job,base,game,env)
                self.assertEqual(job['sources'],[])

    def test_missing_source_reinstall_wrong_phase_old_boot_or_capture_flag_refuses(self):
        for kind in ('source','reinstall','phase','boot','flag'):
            with self.subTest(kind=kind):
                job,base,game,env,record,boot=self.installed()
                if kind=='source': job['before']['bindings']['source_hashes'].pop(str(game/'Scripts/dqn/priority_phase.py'))
                elif kind=='reinstall': job['sources']=[dict(destination='/game/Scripts/dqn/priority_phase.py',before=None)]
                elif kind=='phase': env['DQN_PER_PRIORITY_METRIC']='kl'
                elif kind=='boot': boot['sha256']='d'*64
                else: env[adapter.FLAGS[0]]='/old-capture'
                with self.assertRaises((RuntimeError,KeyError)):
                    adapter.validate_installed_phase(job,base,game,env)

    def test_actual_stopped_activation_uses_CE_phase_CPU_not_legacy_7d(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); base=self.base(); job,_,_,_,_,_=self.installed()
            base.Runtime=type('Legacy',(),{'stopped_checkpoint':lambda *args: self.fail('legacy 7d must not run')})
            base.SettingsLifecycle=NS(key=lambda owner:'retired')
            source=dict(path='/game/models_dqn/robotron_dqn_latest.pt',sha256='a'*64,bytes=275185944)
            base.exclusive_copy=mock.Mock(return_value=(source,dict(source,path='/opaque-readonly.pt')))
            base.fingerprint=lambda *args:source
            runtime=adapter.runtime_class(base).__new__(adapter.runtime_class(base))
            owner=dict(pid=11,starttime_ticks=12);runtime.retired_owner=owner;runtime.cpu_attempts={};runtime.output=root
            runtime.job=dict(job,model_dir='/game/models_dqn',experiment='held');runtime.static=mock.Mock();runtime.absence=mock.Mock()
            runtime.floor=dict.fromkeys(adapter.CLOCKS,15)
            proof=dict(clocks=dict.fromkeys(adapter.CLOCKS,16),saved_priority_metric_phase=dict(metric='ce',valid=True,phase_id='current-phase'))
            runtime.cpu_phase=mock.Mock(return_value=(dict(path='/readonly-CE-proof.json'),proof))
            checkpoint=runtime.stopped_checkpoint(owner,'newest')
            call=runtime.cpu_phase.call_args.args
            self.assertEqual(call[1],'newest_stopped');self.assertEqual(call[5],job['running_phase'])
            self.assertEqual(call[6]['client_count'],192);self.assertEqual(call[6]['clock_floor'],runtime.floor)
            self.assertEqual(checkpoint['verification']['path'],'/readonly-CE-proof.json')
            record=adapter.start_record('activate_kl','next-separate-kl','e'*64,'/game/models_dqn',source,proof)
            self.assertEqual((record['action'],record['metric'],record['previous_metric']),('start','kl','ce'))
            self.assertEqual(runtime.cpu_attempts,{'retired':'passed'})

    def test_new_KL_start_never_accepts_unknown_or_prior_KL_as_CE_predecessor(self):
        source=dict(path='/latest.pt',sha256='a'*64,bytes=275185944)
        for previous in (None,dict(metric='kl',valid=True),dict(metric='ce',valid=False)):
            with self.subTest(previous=previous), self.assertRaisesRegex(RuntimeError,'valid CE predecessor'):
                adapter.start_record('activate_kl','new-phase','b'*64,'/models',source,
                    dict(saved_priority_metric_phase=previous))


if __name__ == '__main__': unittest.main()
