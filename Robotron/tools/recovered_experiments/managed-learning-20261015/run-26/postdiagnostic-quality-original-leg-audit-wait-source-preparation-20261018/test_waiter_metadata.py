"""Deferred six-case metadata fixture; root alone may execute after capture closes.

Only exact closed source/package files are read. The real waiter validate body
and its exact release-report block execute later inside a strict fake namespace.
No waiter run(), control, subprocess, proc/status/model access or host fallback.
These cases do not prove real host timing, name ownership or a full wait cycle.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path as SourcePath, PurePosixPath
import re
import stat
import textwrap
import unittest


HERE = SourcePath(__file__).resolve().parent
TARGET = HERE / 'wait_then_audit.py'
TARGET_SHA = '11fe56352b32c8e3b24818794d5e04db17c94ed04e67e1c9041c6cd6fe7b86c8'
PACK = SourcePath('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/postdiagnostic_ce_quality_binding_proposal')
MANIFEST = PACK / 'preparation-manifest.json'
MANIFEST_SHA = '045f2ac9bcaf065c3dde018fb7e753852022e7c46b4ab664e3aa5b40e9e65e19'
CONTROL = SourcePath('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_audit_control_gc_repair_proposal/control_audit_reviewed3.py')
CONTROL_SHA = 'b5a50047e1a2981a41732c756bf908c6b9b935c58d1d0503c0df494e6f863aee'
LIMIT = 4 << 20


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def full_identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def closed_source(path, expected=None):
    """Closed allowlisted source only; never follow nested metadata pointers."""
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
        assert before.st_uid == os.getuid() and before.st_nlink == 1
        assert 0 < before.st_size <= LIMIT
        raw = stream.read(LIMIT + 1)
        assert full_identity(before) == full_identity(os.fstat(stream.fileno())) == full_identity(path.lstat())
    digest = hashlib.sha256(raw).hexdigest()
    if expected is not None:
        assert digest == expected
    return raw, dict(path=str(path), sha256=digest, bytes=len(raw), identity=full_identity(before))


class UnexpectedAccess(AssertionError):
    pass


class ClosedIO:
    """Every read/path query is explicit; there is no real Path fallback."""
    def __init__(self, records):
        self.records = copy.deepcopy(records)
        self.unexpected = []
        self.directories = set()
        self.fresh = set()
        self.native_path = None
        self.pinned_payload_faults = {}
        self.action_calls = []

    def fail(self, operation, value):
        self.unexpected.append((operation, str(value)))
        raise UnexpectedAccess('Unplanned fake operation: ' + repr(self.unexpected[-1]))

    def path_type(self):
        io = self
        class ClosedPath(PurePosixPath):
            def resolve(self, strict=False):
                if str(self) not in io.directories | io.fresh:
                    io.fail('resolve', self)
                return self

            def exists(self):
                if str(self) in io.fresh:
                    return False
                if str(self) in io.directories:
                    return True
                io.fail('exists', self)

            def is_dir(self):
                if str(self) in io.directories:
                    return True
                if str(self) in io.fresh:
                    return False
                io.fail('is_dir', self)
        return ClosedPath

    def read_file(self, path, readonly=True, status_replacement=False):
        key = str(path)
        if key not in self.records or status_replacement:
            self.fail('read_file', path)
        if not readonly and key != self.native_path:
            self.fail('mutable_read', path)
        raw, pin = self.records[key]
        assert hashlib.sha256(raw).hexdigest() == pin['sha256'] and len(raw) == pin['bytes']
        return raw, copy.deepcopy(pin)

    def pinned(self, pin):
        raw, actual = self.read_file(pin['path'])
        if actual != pin:
            raise RuntimeError('Fixture immutable metadata PIN differs')
        # An explicit decoded-metadata ABI fault is injected only AFTER the
        # real closed fixture bytes/PIN were authenticated. This tests the
        # consuming ABI, not cryptographic acceptance of forged host bytes.
        return self.pinned_payload_faults.get(pin['path'], raw)

    def forbidden_action(self, *args, **kwargs):
        self.action_calls.append((args, kwargs))
        self.fail('action', args)

    def launch(self, *args, **kwargs):
        self.forbidden_action(*args, **kwargs)

    def observe(self, *args, **kwargs):
        self.forbidden_action(*args, **kwargs)


def extracted_namespace(source, io):
    """Root's later run compiles only real pure constants/functions, not imports."""
    tree = ast.parse(source)
    constants = {'GAME', 'RUN', 'PACK', 'CONTROL', 'CONTROL_SHA', 'MANIFEST_SHA',
                 'AUDITOR_SHA', 'OBSERVER', 'OBSERVER_SHA', 'SCHEMA', 'LIMIT'}
    functions = {'require', 'decode', 'minimal', 'validate'}
    body = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(n, ast.Name) and n.id in constants for n in node.targets):
            body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            body.append(node)
    assert {n.name for n in body if isinstance(n, ast.FunctionDef)} == functions
    namespace = dict(Path=io.path_type(), re=re, json=json, read_file=io.read_file,
                     pinned=io.pinned, control=io, __name__='_closed_waiter_fixture')
    namespace['launch'] = namespace['observe'] = io.forbidden_action
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                 '<exact-sealed-waiter-pure-functions>', 'exec'), namespace)
    start = "        # Preserve the original payload and every raw lifecycle outcome even\n"
    stop = "        report_path=Path(flags['--output'])/'review-receipt.json'\n"
    assert source.count(start) == source.count(stop) == 1
    block = source.split(start, 1)[1].split(stop, 1)[0]
    block = start + block
    return_line = "        return 0 if released['original_exit']==0 else 2\n"
    assert source.count(return_line) == 1
    function = 'def release_report(released,released_pin,result,config,leg):\n'
    function += textwrap.indent(textwrap.dedent(block), '    ')
    function += '    ' + return_line.strip() + '\n'
    exec(compile(function, '<exact-sealed-waiter-release-report-seam>', 'exec'), namespace)
    return namespace


class PostdiagnosticWaiterChangedSeams(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw, cls.target_pin = closed_source(TARGET, TARGET_SHA)
        cls.source = raw.decode()
        manifest_raw, cls.manifest_pin = closed_source(MANIFEST, MANIFEST_SHA)
        cls.manifest = json.loads(manifest_raw)
        assert isinstance(cls.manifest['files'], list) and len(cls.manifest['files']) == 16
        cls.records = {str(MANIFEST): (manifest_raw, cls.manifest_pin)}
        for expected in cls.manifest['files']:
            path = SourcePath(expected['path'])
            assert path.is_relative_to(PACK) and path.suffix in ('.py', '.json', '.txt', '.patch')
            content, actual = closed_source(path, expected['sha256'])
            assert actual == expected
            cls.records[str(path)] = (content, actual)
        control_raw, cls.control_pin = closed_source(CONTROL, CONTROL_SHA)
        cls.records[str(CONTROL)] = (control_raw, cls.control_pin)
        cls.records[str(TARGET)] = (raw, cls.target_pin)

    def setUp(self):
        self.io = ClosedIO(self.records)
        self.namespace = extracted_namespace(self.source, self.io)
        self.next_inode = 900000

    def tearDown(self):
        # This assertion runs outside target exception catches, so a negative
        # target verdict cannot swallow an unexpected mock access/action.
        self.assertEqual(self.io.unexpected, [])
        self.assertEqual(self.io.action_calls, [])

    def synthetic(self, path, value):
        raw = encoded(value)
        self.next_inode += 1
        pin = dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                   identity=dict(device=999, inode=self.next_inode, bytes=len(raw),
                                 mtime_ns=1, ctime_ns=1, mode='0o444', uid=os.getuid(), nlink=1))
        self.io.records[path] = (raw, pin)
        return pin

    def case(self):
        n = self.namespace
        run = str(n['RUN'])
        campaign = str(n['GAME'] / 'logs/managed-learning-20261015/quality-SYNTHETIC-postdiagnostic-fixture')
        wrapper, execution, audit = (run + '/SYNTHETIC-wait', run + '/SYNTHETIC-exec', run + '/SYNTHETIC-audit')
        self.io.directories.add(campaign)
        self.io.fresh.update((wrapper, execution, audit))
        owner = dict(unit='robotron-quality-SYNTHETIC-fixture.service', pid=12345,
                     starttime_ticks=10001, invocation_id='1' * 32,
                     cgroup='/SYNTHETIC/robotron-quality-SYNTHETIC-fixture.service')
        plan = dict(output_directory=campaign, legs=[dict(index=i, role=role)
                    for i, role in enumerate(('reference', 'candidate', 'reference', 'candidate'), 1)])
        native_path = campaign + '/plan.json'
        plan_pin = self.synthetic(run + '/SYNTHETIC-native-plan-readonly.json', plan)
        plan_raw, native_pin = copy.deepcopy(self.io.records[plan_pin['path']])
        native_pin['path'] = native_path
        self.next_inode += 1
        native_pin['identity']['inode'] = self.next_inode
        self.io.records[native_path] = (plan_raw, native_pin)
        self.io.native_path = native_path
        binding = self.synthetic(run + '/SYNTHETIC-binding.json', dict(schema='SYNTHETIC-NOT-A-REAL-BINDING'))
        pins = copy.deepcopy(self.manifest['files']) + [copy.deepcopy(self.manifest_pin),
                 copy.deepcopy(self.control_pin), copy.deepcopy(self.target_pin), binding]
        argv = ['/usr/bin/python3.12', '-I', '-B', str(n['PACK'] / 'audit_completed_leg.py'), '--execute',
                '--game', str(n['GAME']), '--campaign', campaign, '--plan-sha256', plan_pin['sha256'],
                '--source-sha256', n['AUDITOR_SHA'], '--binding-job', binding['path'],
                '--binding-job-sha256', binding['sha256'], '--leg', '2', '--output', audit]
        config = dict(unit='robotron-SYNTHETIC-fixture-leg02-audit.service', output=execution,
                      argv=argv, properties=['CPUQuota=100%', 'MemoryMax=512M', 'RuntimeMaxSec=60',
                      'MemorySwapMax=0', 'TasksMax=128', 'TimeoutStopSec=5'],
                      pins=[n['minimal'](p) for p in pins], observation_s=150)
        config_pin = self.synthetic(run + '/SYNTHETIC-audit-config.json', config)
        return dict(schema=n['SCHEMA'], quality_owner=owner, native_plan=plan_pin,
                    native_plan_path=native_path, leg=2, evaluator=dict(pid=23456, starttime_ticks=20002),
                    campaign_directory=campaign, auditor_argv=argv, audit_config=config_pin,
                    source_pins=pins, output_directory=wrapper)

    def release(self, exit_code=0):
        # Deliberately preserve a genuine timer-GC-shaped nonzero archive and
        # already-absent timer with no stop command. This is synthetic metadata,
        # not permission to classify an actual host timer or skip its proof.
        unit = 'robotron-SYNTHETIC-fixture-leg02-audit.service'
        timer = unit.removesuffix('.service') + '.timer'
        statuses = [dict(kind=kind, action=action, exit=code, timed_out=False)
                    for (kind, action), code in zip(
                    [('service', 'show'), ('service', 'cat'), ('service', 'journal'),
                     ('timer', 'show'), ('timer', 'cat'), ('timer', 'journal')], [0, 0, 0, 0, 1, 0])]
        return dict(schema='robotron-root-audit-original-result-and-GC-aware-owned-release-v1',
                    original=dict(unit=unit, observed_live=True), original_exec_code=1,
                    original_exit=exit_code, original_result='success' if exit_code == 0 else 'exit-code',
                    original_archived_before_release=True, lifecycle_complete=True, unit_released=True,
                    audit_success=exit_code == 0, payload_retried=False,
                    original_archive_status=statuses, all_six_original_archive_commands_succeeded=False,
                    owned_release=[dict(unit=timer, stop=None, confirmed_absent=True,
                                        classification='already_absent_with_original_launch_and_terminal_evidence'),
                                   dict(unit=unit, stop=dict(exit=0), confirmed_absent=True)])

    def report(self, release, result):
        return self.namespace['release_report'](release, dict(path='SYNTHETIC-closed-release.json'),
                  result, dict(unit=release['original']['unit']), dict(returncode=1))

    def test_current_family_validate_accepts_closed_list16_and_ordered_pins(self):
        case = self.case()
        owner, evaluator, plan, config, flags = self.namespace['validate'](case)
        self.assertEqual(owner, case['quality_owner'])
        self.assertEqual(evaluator, case['evaluator'])
        self.assertEqual(plan['legs'][1]['role'], 'candidate')
        self.assertEqual(flags['--source-sha256'], self.namespace['AUDITOR_SHA'])
        self.assertEqual(config['pins'], [self.namespace['minimal'](p) for p in case['source_pins']])

    def test_historical_dict13_manifest_is_refused(self):
        case = self.case()
        old = copy.deepcopy(self.manifest)
        old['files'] = {str(i): p for i, p in enumerate(old['files'][:13])}
        self.io.pinned_payload_faults[str(MANIFEST)] = encoded(old)
        with self.assertRaisesRegex(RuntimeError, 'All16 immutable'):
            self.namespace['validate'](case)

    def test_missing_current_owned_pin_is_refused(self):
        case = self.case()
        missing = str(PACK / 'README.txt')
        case['source_pins'] = [p for p in case['source_pins'] if p['path'] != missing]
        with self.assertRaisesRegex(RuntimeError, 'All16 immutable'):
            self.namespace['validate'](case)

    def test_GC_archive_failures_can_be_truthfully_complete(self):
        release, result = self.release(), {}
        self.assertEqual(self.report(release, result), 0)
        self.assertEqual([r['exit'] for r in result['audit_archive_status']], [0, 0, 0, 0, 1, 0])
        self.assertFalse(result['audit_all_six_archive_commands_succeeded'])
        self.assertIsNone(result['audit_owned_release'][0]['stop'])
        self.assertTrue(result['audit_lifecycle_complete'])
        self.assertTrue(result['audit_unit_released'])

    def test_original_audit_nonzero_is_preserved(self):
        release, result = self.release(2), {}
        release['owned_release'][0]['stop'] = dict(exit=5)
        release['owned_release'][0]['classification'] = 'timer_autoGC_race_stop5_preserved'
        self.assertEqual(self.report(release, result), 2)
        self.assertEqual(result['original_audit_exit'], 2)
        self.assertEqual(result['original_native_leg_exit'], 1)
        self.assertEqual(result['audit_owned_release'][0]['stop']['exit'], 5)
        self.assertEqual(result['original_audit_result_value'], 'exit-code')

    def test_incomplete_release_preserves_facts_and_refuses_without_action(self):
        release, result = self.release(2), {}
        release.update(lifecycle_complete=False, unit_released=False)
        release['owned_release'][1]['confirmed_absent'] = False
        with self.assertRaisesRegex(RuntimeError, 'incomplete or differs'):
            self.report(release, result)
        self.assertEqual(result['original_audit_exit'], 2)
        self.assertEqual(result['original_native_leg_exit'], 1)
        self.assertEqual([r['exit'] for r in result['audit_archive_status']], [0, 0, 0, 0, 1, 0])
        self.assertFalse(result['audit_lifecycle_complete'])
        self.assertFalse(result['audit_unit_released'])
        self.assertNotIn('status', result)


if __name__ == '__main__':
    unittest.main()
