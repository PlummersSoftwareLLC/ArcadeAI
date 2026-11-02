"""Authored-only stdlib contracts; no numerical/application imports or units."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'live_one_trial_installed_ce_revision2_proposal/early_insurance.py'
PROFILE = HERE.parent / 'batch2048_profile_horizon_proposal/profile.json'


def load():
    spec = importlib.util.spec_from_file_location('_early_phase_contracts', HERE / 'early_phase_insurance.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class MemoryBase:
    MAX_JSON = MAX_SOURCE = 4 << 20

    def __init__(self):
        self.values = {}
        self.records = {}
        self.sequence = 100

    @staticmethod
    def identity(info):
        return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
            mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
            mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)

    @staticmethod
    def canonical(value):
        path = Path(value)
        if path.resolve(strict=True) != path:
            raise RuntimeError('Noncanonical path')
        return path

    def publish(self, path, value, *, mode='0o444'):
        path = str(path)
        if path in self.values:
            raise RuntimeError('Create only')
        raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
        self.sequence += 1
        pin = dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
            identity=dict(device=1, inode=self.sequence, bytes=len(raw),
                mtime_ns=self.sequence, ctime_ns=self.sequence, mode=mode,
                uid=os.getuid(), nlink=1))
        self.records[path] = pin
        self.values[path] = copy.deepcopy(value)
        return copy.deepcopy(pin)

    def fingerprint(self, path, limit=None):
        path = str(path)
        if path in self.records:
            return copy.deepcopy(self.records[path])
        data = Path(path).read_bytes()
        if limit is not None and len(data) > limit:
            raise RuntimeError('Too large')
        return dict(path=path, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
            identity=self.identity(Path(path).lstat()))

    def pin(self, pin, limit=None):
        if self.fingerprint(pin['path'], limit) != pin:
            raise RuntimeError('PIN changed')
        return Path(pin['path'])

    def read_json(self, pin):
        self.pin(pin)
        if pin['path'] in self.values:
            return copy.deepcopy(self.values[pin['path']])
        return json.loads(Path(pin['path']).read_text())


def fixture(module, base, root):
    owner = dict(pid=1001, starttime_ticks=2002, unit='robotron-managed-test-trainer.service',
        invocation_id='a' * 32, cgroup='/user.slice/robotron-managed-test-trainer.service')
    phase_record = base.publish(root / 'phase.json', dict(metric='ce', action='start'))
    boot = dict(path='/private/models/latest.pt', sha256='b' * 64, bytes=275192614)
    phase = dict(record=phase_record, boot_checkpoint=boot,
        boot_verification=base.publish(root / 'boot.json', dict(status='PASS')),
        expected=dict(metric='ce', phase_id='private2048', valid=True))
    source = base.publish(root / 'opaque-source.json', dict(opaque=True))
    copied = copy.deepcopy(source)
    copied['path'] = str(root / 'opaque-copy.pt')
    copied['identity']['inode'] += 100
    source['path'] = '/private/models/managed-checkpoints/early-only.pt'
    floor = dict(training_steps=20, optimized_samples=40960, learner_frame_count=500, frame_count=1000)
    acquisition = dict(schema='robotron-owned-phase-snapshot-acquisition-v1', purpose='candidate',
        owner_before=owner, owner_after=owner, client_count=192, source_checkpoint=module.triple(source),
        clock_floor=floor, phase_record_sha256=phase_record['sha256'], boot_checkpoint=boot,
        stopped_absence=None, tag='early-only')
    frozen = dict(source=source, verification_copy=copied,
        acquisition=base.publish(root / 'acquisition.json', acquisition))
    producer = base.publish(root / 'producer.json', dict(schema='robotron-root-batch2048-producer-observation-v1',
        owner=owner, source_checkpoint=module.triple(source), acquisition_sha256=frozen['acquisition']['sha256'],
        csv_scope='producer2048', profile_sha256=module.PROFILE['sha256']))
    profile = base.fingerprint(PROFILE)
    context = dict(held_recipe_context=base.read_json(profile)['held_recipe_context'])
    return SimpleNamespace(owner=owner, phase=phase, frozen=frozen, floor=floor,
        producer=producer, profile=profile, context=context, pairs={}, root=root)


def job_for(module, base, f):
    return module.phase_job(None, base, 'private-experiment', f.owner, f.phase, f.pairs,
        f.context, f.frozen, f.floor, f.profile, f.producer, f.root / 'cpu-output')


def proof_for(module, base, f, job_pin, verifier):
    job = base.read_json(job_pin)
    report = dict(status='PASS', schema=module.CPU_RESULT_SCHEMA, role='phase_snapshot',
        script=module.CPU_FAMILY['script'], strict_phase_base=module.CPU_FAMILY['strict_base'],
        root_job=job, job_file=job_pin, phase_metadata_verified=True,
        configured_batch_size=2048, actual_producer_batch_size=2048, producer_CSV_verified=True,
        sha256=job['source']['sha256'], bytes=job['source']['bytes'],
        saved_priority_metric_phase=dict(metric='ce', valid=True),
        clocks={k: v + 1 for k, v in f.floor.items()})
    original = base.publish(f.root / 'original-report.json', report, mode='0o644')
    report_pin = base.publish(f.root / 'readonly-report.json', report)
    cpu_owner = dict(pid=3003, starttime_ticks=4004, unit='robotron-private-phase-CPU.service',
        invocation_id='c' * 32, cgroup='/user.slice/robotron-private-phase-CPU.service')
    command = [verifier['python'], '-Xgil=0', '-I', '-B', '-u', module.CPU_FAMILY['script']['path'],
        '--execute', '--job', job_pin['path'], '--expected-job-sha256', job_pin['sha256'],
        '--expected-verifier-sha256', module.CPU_FAMILY['script']['sha256']]
    timer = cpu_owner['unit'].removesuffix('.service') + '.timer'
    execution = base.publish(f.root / 'intent.json', dict(kind=module.EXECUTION_KIND,
        unit=cpu_owner['unit'], timer=timer, command=command,
        argv=['systemd-run', '--user'] + command, job=job_pin))
    archives = {k: base.publish(f.root / (k + '.json'), dict(synthetic_archive=True))
        for k in ('terminal_show', 'terminal_cat', 'invocation_journal')}
    completion_value = dict(original_owner=cpu_owner, original_pid=cpu_owner['pid'],
        original_invocation=cpu_owner['invocation_id'], original_nrestarts=0,
        original_exec_code=1, original_exit=0, result='success', **archives)
    completion = base.publish(f.root / 'completion.json', completion_value)
    result = base.publish(f.root / 'release.json', dict(status='PASS', kind=module.EXECUTION_KIND,
        original_pid=cpu_owner['pid'], original_invocation=cpu_owner['invocation_id'],
        original_owner=cpu_owner, actual_unit=cpu_owner['unit'], original_exec_code=1,
        original_exit=0, original_result='success', original_archived_before_release=True,
        original_completion=completion, numeric_report_sha256=report_pin['sha256'],
        releases=[dict(unit=timer), dict(unit=cpu_owner['unit'])]))
    return dict(phase_cpu_report=report_pin, original_numeric_report=original,
        successful_execution=execution, successful_completion=completion, successful_result=result)


class EarlyPhaseContracts(unittest.TestCase):
    def test_literal_default_has_no_reads_processes_or_runtime_imports(self):
        m = load()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('read')), \
             patch.object(m.subprocess, 'run', side_effect=AssertionError('process')), \
             patch.object(m, 'load_collector', side_effect=AssertionError('collector')), \
             patch('builtins.print'):
            self.assertEqual(m.main(), 0)

    def test_snapshot_and_registration_lifetimes_are_preserved(self):
        new = ast.parse((HERE / 'early_phase_insurance.py').read_text())
        old = ast.parse(OLD.read_text())
        classes = lambda tree: {x.name: x for x in tree.body if isinstance(x, ast.ClassDef)}
        a, b = classes(new), classes(old)
        self.assertEqual(ast.dump(a['Snapshot']), ast.dump(b['Snapshot']))
        for name in ('register_request', 'adopt_cpu', 'registration', 'record_terminal',
                     'record_release', 'schedule', 'result', 'start'):
            n = next(x for x in a['EarlyPhaseInsurance'].body if isinstance(x, ast.FunctionDef) and x.name == name)
            o = next(x for x in b['EarlyInsurance'].body if isinstance(x, ast.FunctionDef) and x.name == name)
            self.assertEqual(ast.dump(n), ast.dump(o), name)

    def test_new_local_metadata_is444_create_only_and_original_is_unchanged(self):
        m = load()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); original = root / 'historical.json'
            original.write_text('{}\n'); original.chmod(0o644)
            before = original.stat()
            base = m.ReadonlyMetadataBase(MemoryBase())
            out = root / 'new.json'; pin = base.publish(out, dict(owner=1))
            self.assertEqual(pin['identity']['mode'], '0o444')
            self.assertEqual(base.read_json(pin), dict(owner=1))
            with self.assertRaises(FileExistsError): base.publish(out, {})
            self.assertEqual(original.stat(), before)

    def test_unresolved_collector_refuses_before_load_or_request(self):
        m = load()
        base = SimpleNamespace(load_module=lambda *a: self.fail('Loaded unresolved collector'))
        with patch.object(m, 'COLLECTOR_BINDING', None), self.assertRaisesRegex(RuntimeError, 'unresolved'):
            m.load_collector(base, {})

    def test_only_exact_raw_trigger_API_can_retain_nan(self):
        m = load()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); (root / 'snapshot').mkdir()
            base = m.ReadonlyMetadataBase(MemoryBase())
            raw = base.publish(root / 'snapshot/trigger-API.json', dict(raw=float('nan')))
            self.assertEqual(raw['identity']['mode'], '0o444')
            self.assertIn('NaN', Path(raw['path']).read_text())
            for path in [root / 'CPU-phase-job.json', root / 'result.json', root / 'trigger-API.json']:
                with self.assertRaises(ValueError): base.publish(path, dict(raw=float('nan')))
                self.assertFalse(path.exists())

    def test_dynamic_report_archive_uses_real_metadata_copier_not_global_registry(self):
        m = load()
        source = HERE.parent / 'batch2048_phase_lifecycle_integration_reviewed2_proposal/run_CE_batch_transition.py'
        tree = ast.parse(source.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'archive_metadata')
        namespace = dict(Path=Path, os=os, require=m.require)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        base = MemoryBase()
        def fsync_directory(path):
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        base.fsync_directory = fsync_directory
        base.exclusive_copy = lambda *args: self.fail('Unregistered dynamic report in global copy dispatcher')
        helper = SimpleNamespace(base=base, adapter=SimpleNamespace(archive_metadata=namespace['archive_metadata']))
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve(); original = root / 'actual-report.json'
            original.write_text('{"status":"PASS"}\n'); original.chmod(0o644)
            before = original.stat(); pin = base.fingerprint(original)
            copied = m.archive_phase_report(helper, pin, root / 'readonly-report.json')
            self.assertEqual(copied['identity']['mode'], '0o444')
            self.assertNotEqual(copied['identity']['inode'], pin['identity']['inode'])
            self.assertEqual(copied['sha256'], pin['sha256'])
            self.assertEqual(original.stat(), before)

    def test_real_phase_job_has_explicit2048_early_role_and_final_acquisition(self):
        m = load(); base = MemoryBase(); f = fixture(m, base, Path('/synthetic'))
        job = job_for(m, base, f)
        self.assertEqual(job['schema'], m.CPU_JOB_SCHEMA)
        self.assertEqual(job['phase_snapshot']['purpose'], 'candidate')
        self.assertEqual(job['phase_snapshot']['observed_clients'], 192)
        self.assertEqual(job['batch2048_context']['role'], 'early_insurance')
        self.assertEqual(job['phase_snapshot']['acquisition'], f.frozen['acquisition'])
        self.assertEqual(job['source_control_context']['held_recipe_context']['batch_size'], 2048)
        self.assertNotIn('mode', job)
        for path, key, value in [(f.frozen['acquisition']['path'], 'client_count', 0),
                                (f.frozen['acquisition']['path'], 'purpose', 'startup'),
                                (f.producer['path'], 'csv_scope', 'pretransition_baseline4096'),
                                (f.producer['path'], 'acquisition_sha256', 'd' * 64)]:
            saved = copy.deepcopy(base.values[path]); base.values[path][key] = value
            with self.assertRaises(RuntimeError): job_for(m, base, f)
            base.values[path] = saved

    def test_legacy_or_unverified_producer_report_is_not_accepted(self):
        m = load(); base = MemoryBase(); f = fixture(m, base, Path('/synthetic'))
        jp = base.publish(f.root / 'job.json', job_for(m, base, f))
        proof = proof_for(m, base, f, jp, dict(python='/venv/bin/python'))
        m.check_phase_report(base, proof['phase_cpu_report'], jp)
        path = proof['phase_cpu_report']['path']
        for key, value in [('schema', 'robotron-live8-maintenance-checkpoint-CPU-result-v1'),
                           ('actual_producer_batch_size', 4096), ('producer_CSV_verified', False),
                           ('phase_metadata_verified', False)]:
            saved = copy.deepcopy(base.values[path]); base.values[path][key] = value
            with self.assertRaises(RuntimeError): m.check_phase_report(base, proof['phase_cpu_report'], jp)
            base.values[path] = saved

    def test_genuine_phase_provenance_rejects_unknown_original_or_legacy_kind(self):
        m = load(); base = MemoryBase(); f = fixture(m, base, Path('/synthetic'))
        verifier = dict(python='/venv/bin/python'); jp = base.publish(f.root / 'job.json', job_for(m, base, f))
        proof = proof_for(m, base, f, jp, verifier)
        m.check_phase_provenance(base, verifier, jp, proof)
        for key, field, value in [('successful_execution', 'kind', 'insurance'),
                                   ('successful_completion', 'original_exit', 1),
                                   ('successful_result', 'original_archived_before_release', False)]:
            path = proof[key]['path']; saved = copy.deepcopy(base.values[path]); base.values[path][field] = value
            with self.assertRaises(RuntimeError): m.check_phase_provenance(base, verifier, jp, proof)
            base.values[path] = saved
        alias = copy.deepcopy(proof); alias['original_numeric_report'] = alias['phase_cpu_report']
        with self.assertRaises(RuntimeError): m.check_phase_provenance(base, verifier, jp, alias)

    def test_phase_floor_is_typed_and_never_eligible_candidate_or_old7d(self):
        m = load(); base = MemoryBase(); f = fixture(m, base, Path('/synthetic'))
        jp = base.publish(f.root / 'job.json', job_for(m, base, f))
        proof = proof_for(m, base, f, jp, dict(python='/venv/bin/python'))
        saved = base.publish(f.root / 'saved.json', dict(role='early_insurance', tag='early-only',
            trainer=f.owner, source=f.frozen['source'], acquisition=f.frozen['acquisition']))
        result = dict(schema=m.RESULT_SCHEMA, status='PASS', role='early_insurance', owner=f.owner,
            phase=f.phase, profile=f.profile, eligible_quality_candidate=False, legacy_7d_insurance=False,
            phase_cpu_job=jp, python='/venv/bin/python', cpu_provenance=proof,
            tag='early-only', saved_receipt=saved, phase_cpu_report=proof['phase_cpu_report'])
        rp = base.publish(f.root / 'result.json', result)
        floor = m.phase_insurance_floor(base, rp, f.owner, f.phase['record'], f.profile)
        self.assertEqual(floor['role'], 'early_insurance')
        self.assertFalse(floor['legacy_7d_insurance']); self.assertFalse(floor['eligible_quality_candidate'])
        self.assertEqual(floor['clock_floor'], {k: v + 1 for k, v in f.floor.items()})
        with self.assertRaises(RuntimeError): m.phase_insurance_floor(base, rp, dict(f.owner, pid=7), f.phase['record'], f.profile)

    def test_tick_only_dispatches_background_once_and_does_not_freeze(self):
        m = load(); h = m.EarlyPhaseInsurance.__new__(m.EarlyPhaseInsurance)
        import threading
        h._lock = threading.Lock(); h._result = dict(status='PENDING'); h.worker_started = False
        h.snapshot = SimpleNamespace(tick=lambda: dict(status='COMPLETE'), freeze=lambda **k: self.fail('Freeze on observer thread'))
        calls = []; h.spawn = lambda function: calls.append(function)
        self.assertEqual(h.tick()['status'], 'PENDING'); h.tick()
        self.assertEqual(calls, [h._background])

    def test_background_real_order_binds_final_acquisition_before_one_cpu(self):
        self.background_case(False)

    def test_first_cpu_failure_is_final_without_replacement(self):
        self.background_case(True)

    def background_case(self, fail):
        m = load(); base = MemoryBase()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); f = fixture(m, base, root); events = []
            h = m.EarlyPhaseInsurance.__new__(m.EarlyPhaseInsurance)
            import threading
            h._lock = threading.Lock(); h._result = dict(status='PENDING'); h.background_attempted = False
            h.base = base; h.output = root; h.owner = f.owner; h.phase = f.phase; h.profile = base.read_json(f.profile)
            h.pairs = f.pairs; h.context = f.context; h.spec = dict(tag='early-only', profile=f.profile,
                producer_expectation=base.publish(root / 'expectation.json', {}))
            h.runtime = SimpleNamespace(job=dict(experiment='private-experiment'))
            h.adapter = None; h.collector_spec = dict(scope='synthetic')
            h.source_pairs = base.publish(root / 'pairs.json', {})
            trigger = base.publish(root / 'trigger.json', dict(client_count=192))
            request = base.publish(root / 'request.json', dict(tag='early-only'))
            completed = base.publish(root / 'completed.json', dict(tag='early-only'))
            capture = base.publish(root / 'capture.json', dict(status='CAPTURED_ONLY'))
            def capture_live(spec, output): events.append('capture-live'); return capture
            def freeze(**kw):
                events.append('freeze-final-acquisition'); self.assertEqual(kw['purpose'], 'candidate'); return f.frozen
            def bind_capture(cap, source, acquisition, output):
                events.append('bind-final'); self.assertEqual(acquisition, f.frozen['acquisition']); return f.producer
            h.collector = SimpleNamespace(capture_live=capture_live, bind_capture=bind_capture)
            h.snapshot = SimpleNamespace(freeze=freeze, floor=f.floor, raw_pin=trigger,
                transition=dict(request=dict(archive=request), after=dict(archive=completed)))
            h.verifier = dict(python='/venv/bin/python', python_identity=dict(synthetic=True))
            def cpu(helper, jp, verifier, directory):
                events.append('one-retained-CPU')
                if fail: raise RuntimeError('First actual-like CPU failure')
                return proof_for(m, base, f, jp, verifier)
            h.executor = SimpleNamespace(run_once=cpu)
            with patch.object(m, 'check_python_identity', return_value=dict(scope='mock identity')):
                h._background()
            self.assertEqual(events, ['capture-live', 'freeze-final-acquisition', 'bind-final', 'one-retained-CPU'])
            self.assertEqual(h.result()['status'], 'FAILED' if fail else 'PASS')
            if not fail:
                self.assertNotIn('insurance_verification', h.result())
                self.assertEqual(h.result()['role'], 'early_insurance')
            with self.assertRaisesRegex(RuntimeError, 'One background'):
                h._background()
            self.assertEqual(events.count('one-retained-CPU'), 1)

    def test_python_identity_is_separate_from_successful_legacy_provenance(self):
        m = load(); base = MemoryBase()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve(); venv = root / 'venv'; (venv / 'bin').mkdir(parents=True)
            target = root / 'python-executable'; target.write_text('synthetic interpreter, never executed\n'); target.chmod(0o755)
            argv = venv / 'bin/python'; argv.symlink_to(target)
            cfg = venv / 'pyvenv.cfg'; cfg.write_text('synthetic=true\n')
            libs = []
            for package in ('torch', 'numpy'):
                folder = venv / 'lib/python3.14t/site-packages' / package; folder.mkdir(parents=True)
                for filename in ('__init__.py', 'version.py'):
                    path = folder / filename; path.write_text('# synthetic metadata, never imported\n'); libs.append(base.fingerprint(path))
            binding = dict(argv_path=str(argv), link_target=os.readlink(argv), link_identity=base.identity(argv.lstat()),
                executable=base.fingerprint(target), pyvenv_cfg=base.fingerprint(cfg), library_context=libs)
            verifier = dict(python=str(argv), python_identity=binding)
            result = m.check_python_identity(base, verifier, hash_executable=True)
            self.assertTrue(result['executable_hashed']); self.assertNotIn('successful_CPU_invocation', result)
            argv.unlink(); argv.symlink_to(cfg)
            with self.assertRaises(RuntimeError): m.check_python_identity(base, verifier, hash_executable=False)


if __name__ == '__main__':
    unittest.main()
