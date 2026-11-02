"""New fuse tests only; real atomic files/fork/exec with a temporary Python fake.

Owner observations are explicitly injected CPU fixtures. No systemd query,
signal, installed wrapper, MAME, GPU, model or old8-test rerun occurs here.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SHA = 'b5fdc64b6777e6db2541f7c535be2fc49e47f5b565dcd714086cdb33d6041723'


def pin(path):
    s = path.lstat(); raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def put(path, value, mode=0o444):
    raw = value if isinstance(value, bytes) else (json.dumps(value) + '\n').encode()
    with path.open('xb') as stream: stream.write(raw)
    path.chmod(mode)
    return pin(path)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = HERE / 'exec_role_bound_mame_once_v2.py'
        assert hashlib.sha256(source.read_bytes()).hexdigest() == SHA
        spec = importlib.util.spec_from_file_location('_actual_once_fuse_v2', source)
        cls.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.m)
        cls.original = json.loads((HERE / 'STAGED_ONLY-slot163-single-use-permit.json').read_bytes())
        cls.base, cls.base_pin = cls.m.load_base(cls.original['base_helper']['path'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='one use fuse literal $ ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / 'claim directory'; self.directory.mkdir(mode=0o700)
        self.permit = copy.deepcopy(self.original)
        self.permit['claim_directory'] = dict(path=str(self.directory),
                identity=self.m.directory_identity(self.directory.lstat()))
        self.permit_pin = put(self.root / 'fixture permit.json', self.permit)
        self.manifest = self.base.read_manifest(self.permit['base_manifest']['path'],
                                                self.permit['base_manifest']['sha256'])
        self.observed = dict(CPU_fixture=True, direct_parent_verified=True)
        self.command = ['/temporary-fake-only']

    def test_actual_permit_full_context_and_strict_binding(self):
        value, manifest, _, selected = self.m.read_permit(self.base, self.permit_pin['path'],
                                                       self.permit_pin['sha256'], self.base_pin)
        self.assertEqual(value, self.permit); self.assertEqual(manifest, self.manifest)
        self.assertEqual(selected, self.permit_pin)
        self.assertEqual(list(self.directory.iterdir()), [])
        for key in ('scope', 'supervisor_owner', 'prior_actor', 'base_helper', 'unknown'):
            value = copy.deepcopy(self.permit)
            if key == 'scope': value[key] = 'rearm'
            elif key == 'unknown': value[key] = True
            elif key == 'base_helper': value[key]['sha256'] = '0' * 64
            elif key == 'prior_actor': value[key]['pid'] += 1
            else: value[key]['starttime_ticks'] += 1
            pp = put(self.root / ('bad-' + key + '.json'), value)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.m.read_permit(self.base, pp['path'], pp['sha256'], self.base_pin)

    def test_atomic_claim_is_irreversible_and_not_success_claim(self):
        self.m.reserve_once(self.permit, self.permit_pin, self.command, self.observed)
        path = self.directory / self.m.CLAIM_NAME
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt['original_permit'], self.permit_pin)
        self.assertEqual(receipt['status'], 'CONSUMED_RESERVATION_NOT_PROOF_OF_SUCCESSFUL_EXEC')
        self.assertFalse(receipt['additional_exec_attempts_allowed'])
        self.assertEqual(stat.S_IMODE(path.lstat().st_mode), 0o444)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            self.m.reserve_once(self.permit, self.permit_pin, self.command, self.observed)

    def test_failure_before_claim_does_not_claim_but_after_claim_never_rearms(self):
        def fail(): raise ValueError('fixture parent changed')
        with self.assertRaises(ValueError):
            self.m.dispatch(self.permit, self.permit_pin, self.command,
                            {'ROBOTRON_CLIENT_SLOT': '163'}, fail)
        self.assertEqual(list(self.directory.iterdir()), [])
        calls = []
        def changed_after_claim():
            calls.append(True)
            if len(calls) > 1: raise ValueError('fixture parent changed after reservation')
            return self.observed
        with self.assertRaises(ValueError):
            self.m.dispatch(self.permit, self.permit_pin, self.command,
                            {'ROBOTRON_CLIENT_SLOT': '163'}, changed_after_claim)
        self.assertTrue((self.directory / self.m.CLAIM_NAME).exists())
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            self.m.reserve_once(self.permit, self.permit_pin, self.command, self.observed)

    def test_exec_failure_and_durable_write_failure_consume_once(self):
        def failed_exec(*_): raise OSError('fixture exec failed')
        with self.assertRaises(OSError):
            self.m.dispatch(self.permit, self.permit_pin, self.command,
                            {'ROBOTRON_CLIENT_SLOT': '163'}, lambda: self.observed, failed_exec)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            self.m.reserve_once(self.permit, self.permit_pin, self.command, self.observed)
        second = self.root / 'second claim'; second.mkdir(mode=0o700)
        permit = copy.deepcopy(self.permit)
        permit['claim_directory'] = dict(path=str(second), identity=self.m.directory_identity(second.lstat()))
        with patch.object(self.m.os, 'fsync', side_effect=OSError('fixture fsync failed')):
            with self.assertRaises(OSError): self.m.reserve_once(permit, self.permit_pin, self.command, self.observed)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            self.m.reserve_once(permit, self.permit_pin, self.command, self.observed)

    def test_two_concurrent_claimants_execute_exactly_one_real_python_fake(self):
        log = self.root / 'fake exec count'
        fake = self.root / 'fake MAME only.py'
        put(fake, b'#!/usr/bin/python3.12\nimport os\n'
            b'fd=os.open(os.environ["FAKE_LOG"],os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)\n'
            b'os.write(fd,(str(os.getpid())+"\\n").encode());os.close(fd)\n', 0o555)
        start_read, start_write = os.pipe()
        children = []
        for _ in range(2):
            pid = os.fork()
            if pid == 0:
                os.close(start_write); os.read(start_read, 1); os.close(start_read)
                try:
                    self.m.dispatch(self.permit, self.permit_pin, [str(fake)],
                        {'ROBOTRON_CLIENT_SLOT': '163', 'FAKE_LOG': str(log)}, lambda: self.observed)
                except ValueError: os._exit(23)
                except BaseException: os._exit(24)
            children.append(pid)
        os.close(start_read); os.write(start_write, b'12'); os.close(start_write)
        outcomes = {pid: os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) for pid in children}
        self.assertEqual(sorted(outcomes.values()), [0, 23])
        lines = log.read_text().splitlines(); self.assertEqual(len(lines), 1)
        winner = int(lines[0]); self.assertIn(winner, children); self.assertEqual(outcomes[winner], 0)
        receipt = json.loads((self.directory / self.m.CLAIM_NAME).read_text())
        self.assertEqual(receipt['claimant_pid'], winner)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            self.m.reserve_once(self.permit, self.permit_pin, self.command, self.observed)

    def test_other191_passthrough_never_consumes_permit_or_checks_parent(self):
        called = []
        def forbidden_parent(): raise AssertionError('unselected parent probe must not run')
        def capture(*args): called.append(args)
        environment = {'ROBOTRON_CLIENT_SLOT': '164', 'LITERAL': 'unchanged ; $'}
        with self.assertRaisesRegex(AssertionError, 'execve returned'):
            self.m.dispatch(self.permit, self.permit_pin, self.command, environment,
                            forbidden_parent, capture)
        self.assertEqual(called, [(self.command[0], self.command, environment)])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_exact_parent_unit_birth_config_and_prior_actor_predicates(self):
        census = self.base.strict_json(self.base.read_bytes_pin(self.manifest['role_census']))
        observation = census['actual_snapshot']['owners']['fleet']
        _, _, actual_collector, _ = self.m.read_permit(self.base, self.permit_pin['path'],
                                                     self.permit_pin['sha256'], self.base_pin)
        class Collector:
            def unit_observation(_, owner): return copy.deepcopy(observation)
            validate_owner = staticmethod(actual_collector.validate_owner)
        owner = self.permit['supervisor_owner']; prior = self.permit['prior_actor']
        with patch.object(self.m.os, 'getppid', return_value=owner['pid']), \
                patch.object(self.m, 'process_birth', return_value=None):
            self.assertTrue(self.m.verify_parent(self.permit, Collector())['direct_parent_verified'])
            wrong = copy.deepcopy(self.permit); wrong['supervisor_process']['affinity'] = []
            with self.assertRaises(ValueError): self.m.verify_parent(wrong, Collector())
        with patch.object(self.m.os, 'getppid', return_value=owner['pid'] + 1):
            with self.assertRaises(ValueError): self.m.verify_parent(self.permit, Collector())
        with patch.object(self.m.os, 'getppid', return_value=owner['pid']), \
                patch.object(self.m, 'process_birth', return_value=prior['starttime_ticks']):
            with self.assertRaisesRegex(ValueError, 'still lives'):
                self.m.verify_parent(self.permit, Collector())
        observation = copy.deepcopy(observation)
        observation['stdout'] = observation['stdout'].replace(owner['invocation_id'], '0' * 32)
        with patch.object(self.m.os, 'getppid', return_value=owner['pid']):
            with self.assertRaises(ValueError): self.m.verify_parent(self.permit, Collector())

    def test_directory_identity_symlink_and_existing_arbitrary_claim_fail_closed(self):
        bad = copy.deepcopy(self.permit); bad['claim_directory']['identity']['inode'] += 1
        with self.assertRaises(ValueError): self.m.reserve_once(bad, self.permit_pin, self.command, self.observed)
        link = self.root / 'claim symlink'; link.symlink_to(self.directory)
        bad = copy.deepcopy(self.permit); bad['claim_directory']['path'] = str(link)
        with self.assertRaises(ValueError): self.m.reserve_once(bad, self.permit_pin, self.command, self.observed)
        (self.directory / self.m.CLAIM_NAME).symlink_to(self.root / 'never overwrite')
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            self.m.reserve_once(self.permit, self.permit_pin, self.command, self.observed)

    def test_entry_shell_syntax_frozen_composition_and_empty_staged_permit(self):
        wrapper = HERE / 'STAGED_ONLY-mame-with-slot163-single-use-fuse-v2.sh'
        result = subprocess.run(['/bin/bash', '-n', str(wrapper)], capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        original = Path(self.original['base_helper']['path']).parent / 'original-mame-with-socket-wait.sh'
        raw = original.read_bytes(); prefix = raw[:raw.index(b'exec env LD_PRELOAD=')]
        self.assertTrue(wrapper.read_bytes().startswith(prefix))
        self.assertIn(b' "$@"\n', wrapper.read_bytes())
        self.assertEqual(list(Path(self.original['claim_directory']['path']).iterdir()), [])
        self.assertEqual(hashlib.sha256(Path(self.original['base_helper']['path']).read_bytes()).hexdigest(), self.m.BASE_SHA)


if __name__ == '__main__':
    unittest.main()
