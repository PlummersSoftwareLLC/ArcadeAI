"""Small source/exec tests. Only a temporary Python fake can be executed.

For actual shell/exec tests the helper has ONE asserted literal transformation:
MAME_EXECUTABLE points to the fake. Temporary census/manifest pins name this
fixture explicitly. No runtime test switch exists in the selected helper.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE_SHA = 'bfff44be287802cc226470050594bf4231051db4f35f087ddaca2bb3be69becc'


def pin(path):
    s = path.lstat()
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                              mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                              mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def put(path, value, mode=0o444):
    raw = value if isinstance(value, bytes) else (json.dumps(value) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(mode)
    return pin(path)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (HERE / 'exec_role_bound_mame_v1.py').read_bytes()
        assert hashlib.sha256(cls.source).hexdigest() == SOURCE_SHA
        spec = importlib.util.spec_from_file_location('_actual_role_bound_source', HERE / 'exec_role_bound_mame_v1.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.actual = json.loads((HERE / 'prospective-slot163-manifest.json').read_bytes())
        cls.actual_census = json.loads(Path(cls.actual['role_census']['path']).read_bytes())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='role wrapper space $ literal ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.fake = self.root / 'fake mame $(no-shell)'
        put(self.fake, b'#!/usr/bin/python3.12\nimport os,json,sys\nfrom pathlib import Path\n'
            b'Path(os.environ["TEST_CAPTURE_PATH"]).write_text(json.dumps(dict(argv=sys.argv,environment=dict(os.environ),'
            b'pid=os.getpid(),parent=os.getppid(),affinity=sorted(os.sched_getaffinity(0)),'
            b'cgroup=Path("/proc/self/cgroup").read_text())))\n', 0o555)
        self.original_lua = self.root / 'original Lua ; literal.lua'
        self.target_lua = self.root / 'candidate Lua $(literal).lua'
        put(self.original_lua, Path(self.actual['original_lua']['path']).read_bytes())
        put(self.target_lua, Path(self.actual['target_lua']['path']).read_bytes())
        self.manifest = copy.deepcopy(self.actual)
        census = copy.deepcopy(self.actual_census)
        for key, actor in census['actual_snapshot']['actors'].items():
            actor['command'][0] = str(self.fake)
            at = actor['command'].index('-autoboot_script') + 1
            actor['command'][at] = str(self.original_lua)
            actor['command'] += ['-literal-fixture', "value with spaces ; $(touch SHOULD_NOT_EXIST) ' \" `literal`"]
            self.manifest['slots'][key]['expected_args'] = actor['command'][1:]
        self.manifest['role_census'] = put(self.root / 'actual role census.json', census)
        self.manifest['original_lua'] = pin(self.original_lua)
        self.manifest['target_lua'] = pin(self.target_lua)
        original = b"MAME_EXECUTABLE = '/usr/games/mame'"
        replacement = ('MAME_EXECUTABLE = ' + repr(str(self.fake))).encode()
        self.assertEqual(self.source.count(original), 1)
        fixture_source = self.source.replace(original, replacement)
        self.assertEqual(fixture_source.replace(replacement, original), self.source)
        self.helper_pin = put(self.root / 'helper with literal $.py', fixture_source)

    def environment(self, slot, capture):
        value = dict(self.manifest['slots'][str(slot)]['expected_environment'])
        value.pop('LD_PRELOAD', None)
        value.pop('ROBOTRON_SOCKET_WAIT_PORT', None)
        value.update(PATH='/usr/bin:/bin', TEST_CAPTURE_PATH=str(capture),
                     UNRELATED_LITERAL="spaces $ ` ; ' \" preserved", PYTHONDONTWRITEBYTECODE='1')
        return value

    def execute_fake(self, slot=163, changes=None, wrong_sha=False):
        manifest_pin = put(self.root / ('manifest ' + str(len(list(self.root.glob('manifest*')))) + '.json'), self.manifest)
        wrapper = (HERE / 'mame-with-slot163-preview-role-bound-v1.sh').read_text()
        actual_helper = str(HERE / 'exec_role_bound_mame_v1.py')
        actual_manifest = str(HERE / 'prospective-slot163-manifest.json')
        replacements = {actual_helper: shlex.quote(self.helper_pin['path']),
                        actual_manifest: shlex.quote(manifest_pin['path']),
                        SOURCE_SHA: '0' * 64 if wrong_sha else self.helper_pin['sha256'],
                        hashlib.sha256((HERE / 'prospective-slot163-manifest.json').read_bytes()).hexdigest(): manifest_pin['sha256']}
        for old, new in replacements.items():
            self.assertEqual(wrapper.count(old), 1)
            wrapper = wrapper.replace(old, new)
        path = self.root / ('entry ' + str(len(list(self.root.glob('entry*')))) + '.sh')
        put(path, wrapper.encode(), 0o555)
        capture = self.root / ('captured ' + str(len(list(self.root.glob('captured*')))) + '.json')
        environment = self.environment(slot, capture)
        if changes:
            environment.update(changes)
        args = self.manifest['slots'][str(slot)]['expected_args']
        child = subprocess.Popen(['/bin/bash', str(path), *args], env=environment,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = child.communicate(timeout=15)
        return child, stdout, stderr, json.loads(capture.read_text()) if capture.exists() else None

    def test_actual_selected_manifest_and_pure_exact_delta(self):
        self.module.validate_manifest(self.actual)
        for slot in (163, 164, 0):
            row = self.actual['slots'][str(slot)]
            original = dict(row['expected_environment'])
            original.pop('LD_PRELOAD'); original.pop('ROBOTRON_SOCKET_WAIT_PORT')
            original['UNRELATED_LITERAL'] = 'sentinel ; $(literal)'
            command, environment = self.module.prepare_launch(self.actual, row['expected_args'], original)
            baseline = dict(original, LD_PRELOAD=self.actual['wait_library']['path'], ROBOTRON_SOCKET_WAIT_PORT='9998')
            expected = [self.module.MAME_EXECUTABLE, *row['expected_args']]
            if slot == 163:
                expected[expected.index('-autoboot_script') + 1] = self.actual['target_lua']['path']
                baseline['ROBOTRON_EVAL_MODE'] = '1'
            self.assertEqual(command, expected)
            self.assertEqual(environment, baseline)

    def test_actual_shell_exec_fake_selected_preserves_process_and_literal_args(self):
        child, stdout, stderr, recorded = self.execute_fake()
        self.assertEqual((child.returncode, stdout, stderr), (0, '', ''))
        self.assertEqual(recorded['pid'], child.pid)
        self.assertEqual(recorded['parent'], os.getpid())
        self.assertEqual(recorded['affinity'], sorted(os.sched_getaffinity(0)))
        self.assertEqual(recorded['cgroup'], Path('/proc/self/cgroup').read_text())
        expected = [str(self.fake), *self.manifest['slots']['163']['expected_args']]
        expected[expected.index('-autoboot_script') + 1] = str(self.target_lua)
        self.assertEqual(recorded['argv'], expected)
        self.assertEqual(recorded['environment']['ROBOTRON_EVAL_MODE'], '1')
        self.assertEqual(recorded['environment']['UNRELATED_LITERAL'], "spaces $ ` ; ' \" preserved")
        self.assertEqual(recorded['environment']['LD_PRELOAD'], self.actual['wait_library']['path'])
        self.assertEqual(recorded['environment']['ROBOTRON_SOCKET_WAIT_PORT'], '9998')
        self.assertFalse((self.root / 'SHOULD_NOT_EXIST').exists())

    def test_actual_shell_unselected_matches_original_wrapper_fake_exec(self):
        child, stdout, stderr, actual = self.execute_fake(164)
        self.assertEqual((child.returncode, stdout, stderr), (0, '', ''))
        original = (HERE / 'original-mame-with-socket-wait.sh').read_text()
        self.assertEqual(original.count('/usr/games/mame'), 1)
        path = self.root / 'original wrapper fake only.sh'
        put(path, original.replace('/usr/games/mame', shlex.quote(str(self.fake))).encode(), 0o555)
        capture = self.root / 'baseline capture.json'
        environment = self.environment(164, capture)
        completed = subprocess.run(['/bin/bash', str(path), *self.manifest['slots']['164']['expected_args']],
                                   env=environment, capture_output=True, text=True, timeout=15)
        self.assertEqual((completed.returncode, completed.stdout, completed.stderr), (0, '', ''))
        baseline = json.loads(capture.read_text())
        self.assertEqual(actual['argv'], baseline['argv'])
        for record in (actual, baseline):
            record['environment'].pop('TEST_CAPTURE_PATH')
        self.assertEqual(actual['environment'], baseline['environment'])
        self.assertEqual(actual['environment']['ROBOTRON_EVAL_MODE'], '0')

    def test_unknown_slot_argv_conflict_extra_control_and_wrong_role_fail(self):
        row = self.actual['slots']['163']; environment = dict(row['expected_environment'])
        for changes in ({'ROBOTRON_CLIENT_SLOT': '192'}, {'ROBOTRON_CLIENT_SLOT': '0163'},
                        {'ROBOTRON_EVAL_MODE': '2'}, {'ROBOTRON_UNBOUND_FLAG': '1'},
                        {'ROBOTRON_SOCKET_WAIT_US': '0'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.module.prepare_launch(self.actual, row['expected_args'], dict(environment, **changes))
        with self.assertRaises(ValueError):
            self.module.prepare_launch(self.actual, row['expected_args'] + ['--different'], environment)

    def test_manifest_unknown_duplicate_missing_conflicting_fields_fail(self):
        for change in ('extra', 'missing_slot', 'role', 'CID', 'second_override', 'args'):
            value = copy.deepcopy(self.actual)
            if change == 'extra': value['unknown'] = True
            if change == 'missing_slot': del value['slots']['191']
            if change == 'role': value['slots']['163']['eval'] = False
            if change == 'CID': value['slots']['163']['connection_id'] = value['slots']['162']['connection_id']
            if change == 'second_override': value['slots']['164']['action'] = 'override'
            if change == 'args': value['slots']['163']['expected_args'] += ['--different']
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.module.validate_manifest(value)
        with self.assertRaises(ValueError): self.module.strict_json(b'{"slots":{},"slots":{}}')
        with self.assertRaises(ValueError): self.module.strict_json(b'{"x":NaN}')

    def test_source_pin_replacement_symlink_and_manifest_sha_fail(self):
        source = self.root / 'source'; entry = put(source, b'small source')
        self.assertEqual(self.module.read_bytes_pin(entry), b'small source')
        source.chmod(0o644); source.write_bytes(b'changed data')
        with self.assertRaises(ValueError): self.module.read_bytes_pin(entry)
        link = self.root / 'symlink'; link.symlink_to(source)
        wrong = dict(pin(source), path=str(link))
        with self.assertRaises(ValueError): self.module.read_bytes_pin(wrong)
        with self.assertRaises(ValueError):
            self.module.read_manifest(str(HERE / 'prospective-slot163-manifest.json'), '0' * 64)

    def test_actual_shell_failures_never_exec_fake(self):
        child, _, _, record = self.execute_fake(changes={'ROBOTRON_EVAL_MODE': '2'})
        self.assertNotEqual(child.returncode, 0); self.assertIsNone(record)
        child, _, _, record = self.execute_fake(wrong_sha=True)
        self.assertNotEqual(child.returncode, 0); self.assertIsNone(record)
        child, _, _, record = self.execute_fake(changes={'ROBOTRON_SOCKET_WAIT_US': '0'})
        self.assertNotEqual(child.returncode, 0); self.assertIsNone(record)

    def test_wrapper_only_changes_final_exec_and_has_no_real_test_switch(self):
        original = (HERE / 'original-mame-with-socket-wait.sh').read_bytes()
        target = (HERE / 'mame-with-slot163-preview-role-bound-v1.sh').read_bytes()
        prefix = original[:original.index(b'exec env LD_PRELOAD=')]
        self.assertTrue(target.startswith(prefix))
        self.assertIn(b' "$@"\n', target)
        self.assertNotIn(b'eval ', target)
        self.assertNotIn(b'--fake', target)
        self.assertNotIn(b'--test', target)
        self.assertIn(b"os.execve(command[0], command, environment)", self.source)
        self.assertNotIn(b'os.kill(', self.source)


if __name__ == '__main__':
    unittest.main()
