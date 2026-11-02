"""Unexecuted stdlib-only wrapper tests; never inspect checkpoints or run numerics."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

VERIFIER = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/live8-maintenance-checkpoint-CPU-verifier-proposal-20261017/verify_maintenance_checkpoint.py')
VERIFIER_SHA = '7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
if hashlib.sha256(VERIFIER.read_bytes()).hexdigest() != VERIFIER_SHA:
    raise RuntimeError('Wrapper test source pin changed')
spec = importlib.util.spec_from_file_location('_maintenance_guards_subject', VERIFIER)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

FLOOR = dict(training_steps=100, optimized_samples=409600, learner_frame_count=200000, frame_count=400000)
TRAINER = dict(pid=12345, starttime_ticks=900, unit='robotron-managed-fixture-trainer.service',
               invocation_id='a' * 32, cgroup='/user.slice/fixture/robotron-managed-fixture-trainer.service')
MODEL_DIR = Path('/explicit-fixture-models')
TAG = 'fixture-insurance'


def insurance_fixture():
    trigger = dict(FLOOR, client_count=192, measurement_active=False,
                   host_pipeline={'learning_exposure': {'optimizer': {'process_id': TRAINER['pid']}}})
    job = dict(mode='insurance', clock_floor=dict(FLOOR),
               source={'path': str(MODEL_DIR / 'managed-checkpoints' / (TAG + '.pt'))},
               insurance=dict(tag=TAG, trainer=dict(TRAINER), trigger_snapshot={'fixture': 'trigger'},
                              completed_request={'path': str(MODEL_DIR / 'managed_save.request.json.completed')}))
    values = dict(insurance_trigger_snapshot=trigger, insurance_completed_request={'tag': TAG})
    return job, values


def stopped_fixture(*, restarted=False):
    retired = dict(TRAINER)
    if restarted:
        retired.update(pid=12346, starttime_ticks=1000, invocation_id='b' * 32)
    latest = str(MODEL_DIR / 'robotron_dqn_latest.pt')
    job = dict(mode='stopped_latest', experiment='fixture-exp', clock_floor=dict(FLOOR),
               source={'path': latest}, verification_copy={'sha256': 'c' * 64, 'bytes': 275191013},
               stopped_latest=dict(old_trainer=retired, absence_receipt={'fixture': 'absence'},
                                   insurance_verification={'fixture': 'insurance'}))
    insurance = dict(schema=v.RESULT_SCHEMA, status='PASS', mode='insurance', clocks=dict(FLOOR),
                     root_job=dict(experiment='fixture-exp', insurance={'trainer': dict(TRAINER)},
                                   source_control_context={'model_dir': str(MODEL_DIR)}))
    values = dict(stopped_absence_receipt=dict(schema=v.ABSENCE_SCHEMA, trainer=retired,
        unit_main_pid=0, unit_active_state='inactive', old_process_absent=True,
        owned_cgroup_empty=True, latest_path=latest), insurance_CPU_verification=insurance)
    if restarted:
        job['stopped_latest']['owned_restart_lineage'] = {'fixture': 'lineage'}
        values['owned_restart_lineage'] = dict(schema=v.LINEAGE_SCHEMA, insured_trainer=dict(TRAINER),
            retired_trainer=retired, authorized_start_adopted=True, unknown_replacement_adopted=False,
            experiment='fixture-exp', model_dir=str(MODEL_DIR), source_phase='after',
            request_id='known-fixture-request', start_request={'fixture': 'request'})
        values['owned_restart_start_request'] = dict(schema=v.START_SCHEMA, insured_trainer=dict(TRAINER),
            unit=retired['unit'], cgroup=retired['cgroup'], experiment='fixture-exp',
            model_dir=str(MODEL_DIR), source_phase='after', owned_start_requested=True,
            request_id='known-fixture-request')
    return job, values


def metadata_reader(values):
    def read(pin, evidence, label):
        # Wrappers consume fixture metadata only; hashing itself is tested separately.
        evidence.setdefault('bound_files', {})
        return copy.deepcopy(values[label])
    return read


class MaintenanceWrapperGuards(unittest.TestCase):
    def test_01_default_plan_performs_no_reads_or_framework_import(self):
        forbidden = lambda *a, **k: (_ for _ in ()).throw(AssertionError('Default performed work'))
        before = set(sys.modules)
        output = io.StringIO()
        with mock.patch.object(v, 'fingerprint', side_effect=forbidden), \
             mock.patch.object(v, 'canonical', side_effect=forbidden), \
             mock.patch.object(v, 'numerical_setup', side_effect=forbidden), \
             mock.patch.object(v.importlib, 'import_module', side_effect=forbidden), \
             mock.patch.object(Path, 'read_text', side_effect=forbidden), \
             mock.patch.object(Path, 'read_bytes', side_effect=forbidden), contextlib.redirect_stdout(output):
            self.assertEqual(v.main([]), 0)
        self.assertIn('PLAN_ONLY', output.getvalue())
        self.assertFalse(any(n == 'torch' or n.startswith(('torch.', 'numpy', 'dqn')) for n in set(sys.modules) - before))

    def test_02_insurance_correct_slot_accepts_and_wrong_completed_tag_rejects(self):
        job, values = insurance_fixture()
        with mock.patch.object(v, 'pinned_json', side_effect=metadata_reader(values)), \
             mock.patch.object(v, 'exact_absence', side_effect=AssertionError('Insurance queried old owner')):
            evidence = {}
            v.check_mode(job, evidence, MODEL_DIR)
            self.assertEqual(evidence['insurance_trigger'], dict(FLOOR, client_count=192))
            values['insurance_completed_request']['tag'] = 'other-tag'
            with self.assertRaisesRegex(RuntimeError, 'Completed tag/source'):
                v.check_mode(job, {}, MODEL_DIR)

    def test_03_insurance_wrong_trigger_or_clock_floor_rejects(self):
        for defect in ('clock', 'clients', 'measurement', 'PID'):
            with self.subTest(defect=defect):
                job, values = insurance_fixture()
                trigger = values['insurance_trigger_snapshot']
                if defect == 'clock': trigger['training_steps'] += 1
                elif defect == 'clients': trigger['client_count'] = 191
                elif defect == 'measurement': trigger['measurement_active'] = True
                else: trigger['host_pipeline']['learning_exposure']['optimizer']['process_id'] += 1
                with mock.patch.object(v, 'pinned_json', side_effect=metadata_reader(values)):
                    with self.assertRaisesRegex(RuntimeError, 'Insurance floor/actual trigger/trainer'):
                        v.check_mode(job, {}, MODEL_DIR)

    def test_04_insurance_cannot_bind_moving_latest(self):
        job, values = insurance_fixture()
        job['source']['path'] = str(MODEL_DIR / 'robotron_dqn_latest.pt')
        with mock.patch.object(v, 'pinned_json', side_effect=metadata_reader(values)):
            with self.assertRaisesRegex(RuntimeError, 'Completed tag/source'):
                v.check_mode(job, {}, MODEL_DIR)

    def test_05_actual_small_file_wrong_SHA_rejects(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'metadata.json'
            path.write_bytes(b'{"owned_fixture":true}\n')
            observed = v.fingerprint(path)
            pin = dict(path=str(path), sha256='0' * 64, bytes=observed['bytes'],
                       identity={key: observed[key] for key in v.identity(path.stat())})
            with self.assertRaisesRegex(RuntimeError, 'Bound identity/SHA/bytes'):
                v.check_pin(pin, {}, 'fixture', metadata=True)

    def test_06_same_inode_root_copy_rejects(self):
        size = 275191013  # Metadata only; no large file or checkpoint is created.
        source = dict(path='/fixture/source.pt', sha256='a' * 64, bytes=size, device=1, inode=2,
                      uid=os.getuid(), nlink=1, mode='0o664')
        copied = dict(source, path='/fixture/copy.pt', mode='0o444')
        job = dict(source={'path': source['path'], 'bytes': size}, verification_copy={'bytes': size})
        with mock.patch.object(v, 'canonical', return_value=Path(source['path'])), \
             mock.patch.object(v, 'check_pin', side_effect=[source, copied]):
            with self.assertRaisesRegex(RuntimeError, 'independent, owned, single-link'):
                v.check_root_copy(job, {})

    def absence_case(self, *, start=None, members=''):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        proc, groups = root / 'proc', root / 'cgroups'
        proc.mkdir(); groups.mkdir()
        if start is not None:
            process = proc / str(TRAINER['pid']); process.mkdir()
            fields = ['S'] + ['0'] * 18 + [str(start)]
            (process / 'stat').write_text(str(TRAINER['pid']) + ' (fixture worker) ' + ' '.join(fields))
        group = groups / TRAINER['cgroup'].lstrip('/')
        group.mkdir(parents=True); (group / 'cgroup.procs').write_text(members)
        def path(value):
            if str(value) == '/proc': return proc
            if str(value) == '/sys/fs/cgroup': return groups
            raise AssertionError('Unexpected runtime path: ' + str(value))
        return temporary, mock.patch.object(v, 'Path', side_effect=path)

    def test_07_exact_old_PID_alive_rejects_without_signals(self):
        temporary, paths = self.absence_case(start=TRAINER['starttime_ticks'])
        with temporary, paths:
            with self.assertRaisesRegex(RuntimeError, 'Old trainer still alive'):
                v.exact_absence(TRAINER)

    def test_08_nonempty_cgroup_rejects_but_reused_PID_is_not_adopted(self):
        temporary, paths = self.absence_case(members='777\n')
        with temporary, paths:
            with self.assertRaisesRegex(RuntimeError, 'cgroup is nonempty'):
                v.exact_absence(TRAINER)
        temporary, paths = self.absence_case(start=TRAINER['starttime_ticks'] + 1)
        with temporary, paths:
            result = v.exact_absence(TRAINER)
            self.assertEqual(result['old_PID_state'], 'PID_reused_different_start')
            self.assertEqual(result['owned_cgroup_state'], 'present_empty')

    def test_09_unowned_restart_unknown_replacement_bad_request_or_floor_rejects(self):
        for defect in ('no_lineage', 'unowned', 'unknown', 'request', 'floor'):
            with self.subTest(defect=defect):
                job, values = stopped_fixture(restarted=True)
                if defect == 'no_lineage': del job['stopped_latest']['owned_restart_lineage']
                elif defect == 'unowned': values['owned_restart_lineage']['authorized_start_adopted'] = False
                elif defect == 'unknown': values['owned_restart_lineage']['unknown_replacement_adopted'] = True
                elif defect == 'request': values['owned_restart_start_request']['request_id'] = 'wrong'
                else: values['insurance_CPU_verification']['clocks']['frame_count'] += 1
                with mock.patch.object(v, 'pinned_json', side_effect=metadata_reader(values)), \
                     mock.patch.object(v, 'exact_absence', side_effect=AssertionError('Bad lineage reached absence')):
                    with self.assertRaises(RuntimeError): v.check_mode(job, {}, MODEL_DIR)

    def test_10_owned_lineage_brackets_copy_and_numeric_stub_and_late_fault_invalidates(self):
        for late_fault in (False, True):
            with self.subTest(late_fault=late_fault), tempfile.TemporaryDirectory() as temporary:
                job, values = stopped_fixture(restarted=True)
                output = Path(temporary) / 'output'
                job_record, self_record = {'fixture': 'job'}, {'fixture': 'source'}
                order = []
                def absence(trainer):
                    order.append(('absence', trainer['pid']))
                    if late_fault and len(order) == 5:
                        raise RuntimeError('Late retired owner became live')
                    return {'trainer': trainer, 'observed_absent': True}
                def copied(*args): order.append(('copy', None)); return Path('/fixture/no-load-copy.pt')
                def numerical(path, floor, evidence):
                    order.append(('numeric_stub', None)); evidence['clocks'] = dict(floor)
                def fingerprint(path):
                    return job_record if str(path).endswith('job.json') else self_record
                with mock.patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': ''}, clear=True), \
                     mock.patch.object(v, 'read_job', return_value=(job, job_record, self_record, output)), \
                     mock.patch.object(v, 'check_context', return_value=MODEL_DIR), \
                     mock.patch.object(v, 'pinned_json', side_effect=metadata_reader(values)), \
                     mock.patch.object(v, 'exact_absence', side_effect=absence), \
                     mock.patch.object(v, 'check_root_copy', side_effect=copied), \
                     mock.patch.object(v, 'validate_checkpoint', side_effect=numerical), \
                     mock.patch.object(v, 'fingerprint', side_effect=fingerprint), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = v.main(['--execute', '--job', str(Path(temporary) / 'job.json')])
                prefix = [('absence', 12345), ('absence', 12346), ('copy', None), ('numeric_stub', None)]
                self.assertEqual(order[:4], prefix)
                if late_fault:
                    self.assertEqual(code, 1)
                    self.assertFalse((output / 'cpu-verification.json').exists())
                    self.assertEqual(json.loads((output / 'verification-error.json').read_text())['status'], 'FAIL')
                else:
                    self.assertEqual(code, 0)
                    self.assertEqual(order, prefix + [('absence', 12345), ('absence', 12346)])
                    self.assertEqual(json.loads((output / 'cpu-verification.json').read_text())['status'], 'PASS')


if __name__ == '__main__':
    unittest.main(verbosity=2)
