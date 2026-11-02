"""Private capacity proposal guards; CPU fixtures, no real GPU/MAME launches."""
from dataclasses import asdict, replace
import hashlib
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from Robotron.tools import run_frozen_sidecar as sidecar
from Robotron.tools import test_frozen_sidecar as fixtures
from Robotron.tools import test_compare_sidecar_measurements as receipt_fixtures
from Robotron.tools import compare_sidecar_measurements as backend


PARENT = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/'
              'confirmed_game_boundary_proposal/quality_integration_reviewed4')


class CapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SidecarIsolationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixtures.SidecarIsolationTests.tearDownClass.__func__(cls)

    def setUp(self):
        fixtures.SidecarIsolationTests.setUp(self)

    def test_default_plan_matches_parent_and_preserves_numerical_sources(self):
        name = '_capacity_parent_sidecar'
        spec = importlib.util.spec_from_file_location(name, PARENT/'Robotron/tools/run_frozen_sidecar.py')
        parent = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: parent}):
            spec.loader.exec_module(parent)
            arguments = asdict(self.job)
            arguments.pop('actors')
            self.assertEqual(self.job.plan(), parent.Job(**arguments).plan())
        manifest = json.loads((PARENT/'runtime-source-package.json').read_bytes())
        for relative, digest in manifest['files'].items():
            if relative == 'Scripts/dqn/socket_server.py':
                def remaining_ast(source):
                    tree = ast.parse(source)
                    tree.body = [node for node in tree.body if not (
                        isinstance(node, ast.FunctionDef)
                        and node.name == '_continuous_play_score_dip')]
                    return ast.dump(tree)
                original = (PARENT/'Robotron'/relative).read_text()
                corrected = (sidecar.GAME/relative).read_text()
                self.assertEqual(remaining_ast(original), remaining_ast(corrected))
                self.assertNotEqual(original, corrected)
            elif relative.startswith('Scripts/'):
                self.assertEqual(hashlib.sha256((sidecar.GAME/relative).read_bytes()).hexdigest(), digest)

    def test_only_explicit_supported_integer_counts(self):
        for count in (0, 1, 15, 17, 31, 33, 64, True, 16.0, 32.0, '32', None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                replace(self.job, actors=count).validate()
        for count in (16, 32):
            job = replace(self.job, actors=count)
            job.validate()
            self.assertEqual(job.actor_slots, tuple(range(4096, 4096+count)))

    def test_32_actor_plan_keeps_confirmed_terminals_and_batch_limit_16(self):
        a, b = self.job.plan(), replace(self.job, actors=32).plan()
        self.assertEqual({k for k in a if a[k] != b[k]}, {'actors', 'actor_slots'})
        self.assertEqual(b['actor_slots'], list(range(4096, 4128)))
        self.assertEqual(b['inference_max_batch_size'], 16)
        self.assertEqual(b['completion_policy'], 'confirmed_reset_reserves_v1')
        self.assertTrue(b['game_boundary_diagnostics'])
        self.assertFalse(b['replay_enabled'])

    def test_32_cli_plan_does_not_create_job_or_import_torch(self):
        code = (
            'import sys\nfrom Robotron.tools.run_frozen_sidecar import main\n'
            'result=main(sys.argv[1:])\nassert "torch" not in sys.modules\n'
            'raise SystemExit(result)\n')
        command = [sys.executable, '-B', '-c', code,
                   '--checkpoint', str(self.checkpoint), '--job-dir', str(self.job.directory),
                   '--label', 'capacity32-plan', '--device', 'cpu', '--actors', '32',
                   '--mame', '/bin/true', '--rompath', str(self.root),
                   '--boot-assets', str(self.boot_assets)]
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=20)
        self.assertEqual(json.loads(result.stdout)['actors'], 32)
        self.assertFalse(self.job.directory.exists())

    def test_exact_32_slot_boundary_rejects_missing_extra_duplicate_and_error(self):
        required = sidecar.slots_for_actors(32)
        server = Mock(inference_only_error=None)
        base = dict(ready=True, clients=32, actor_slots=list(required))
        server.measurement_boundary_status.return_value = base
        self.assertTrue(sidecar.fixed_boundary(server, 7, required)['ready'])
        for bad in (dict(base, clients=16), dict(base, actor_slots=list(sidecar.SLOTS)),
                    dict(base, actor_slots=list(required[:-1])+[9999]),
                    dict(base, actor_slots=list(required[:-1])+[required[0]]),
                    dict(base, actor_slots=list(reversed(required))), dict(base, ready=False)):
            with self.subTest(bad=bad):
                server.measurement_boundary_status.return_value = bad
                self.assertFalse(sidecar.fixed_boundary(server, 7, required)['ready'])
        server.measurement_boundary_status.return_value = base
        server.inference_only_error = 'original disconnect'
        self.assertFalse(sidecar.fixed_boundary(server, 7, required)['ready'])

    def test_boundary_declaration_cannot_select_other_slots_or_counts(self):
        server = Mock(inference_only_error=None)
        for slots in (range(16), range(4096, 4113), [4096]*32,
                      [float(i) for i in range(4096, 4128)]):
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                sidecar.fixed_boundary(server, 1, slots)
        server.measurement_boundary_status.assert_not_called()

    def test_32_owned_fleet_has_independent_private_boot_and_socket_paths(self):
        calls = []
        job = replace(self.job, actors=32)
        def spawn(command, **kwargs):
            process = fixtures.FakeProcess(30000+len(calls))
            calls.append((command, kwargs, process))
            return process
        fleet = sidecar.PrivateFleet(job, Path('/tmp/capacity-test-shim.so'), popen=spawn)
        fleet.launch()
        try:
            self.assertEqual(tuple(fleet.processes), job.actor_slots)
            self.assertEqual(len(calls), 32)
            for slot, (_, arguments, _) in zip(job.actor_slots, calls):
                self.assertEqual(arguments['env']['ROBOTRON_CLIENT_SLOT'], str(slot))
                self.assertEqual(arguments['env']['ROBOTRON_SOCKET_ADDRESS'], '127.0.0.1:9999')
                self.assertEqual(arguments['env']['ROBOTRON_EVAL_MODE'], '1')
                self.assertEqual(arguments['cwd'], job.directory/'actors'/str(slot))
                copied = arguments['cwd']/'nvram/robotron/nvram'
                original = self.boot_assets/'nvram/robotron/nvram'
                self.assertEqual(copied.read_bytes(), original.read_bytes())
                self.assertNotEqual(copied.stat().st_ino, original.stat().st_ino)
        finally:
            fleet.stop()
        self.assertTrue(all(process.terminated for _, _, process in calls))
        self.assertTrue(all(arguments['stdout'].closed for _, arguments, _ in calls))

    def test_32_partial_spawn_failure_retires_only_owned_processes(self):
        owned = []
        def spawn(*args, **kwargs):
            if len(owned) == 20:
                raise OSError('fixture launch failure at high slot')
            process = fixtures.FakeProcess(31000+len(owned))
            owned.append(process)
            return process
        fleet = sidecar.PrivateFleet(replace(self.job, actors=32),
            Path('/tmp/capacity-test-shim.so'), popen=spawn)
        with self.assertRaisesRegex(OSError, 'high slot'):
            fleet.launch()
        self.assertEqual(len(owned), 20)
        self.assertTrue(all(process.terminated for process in owned))
        self.assertEqual(fleet.streams, [])

    def test_timeout_and_backend_evidence_cover_all_32_slots(self):
        job = replace(self.job, actors=32)
        fleet = sidecar.PrivateFleet(job, Path('/tmp/capacity-test-shim.so'),
            popen=lambda *args, **kwargs: fixtures.FakeProcess(32000))
        fleet.launch()
        try:
            for slot in job.actor_slots:
                path = job.directory/'actors'/str(slot)/'console.log'
                path.write_text('[robotron-socket-wait] pid=32000 fd=8 port=9999 interval_us=1000\n')
            path.write_text(path.read_text()+'[SOCKET ACTION TIMEOUT] unix_s=123456\n')
            evidence = fleet.backend_evidence()
            self.assertEqual(tuple(evidence), job.actor_slots)
            self.assertTrue(all(row['matching_activation'] for row in evidence.values()))
            self.assertEqual(fleet.timeout_logs()[4127], 1)
            self.assertEqual(set(fleet.timeout_logs()), set(job.actor_slots))
            with self.assertRaisesRegex(ValueError, 'slot'):
                sidecar.mame_spec(self.job, 4127, Path('/tmp/capacity-test-shim.so'))
        finally:
            fleet.stop()


def receipt32(label='capacity32'):
    data = receipt_fixtures.sidecar(label)
    slots = list(sidecar.slots_for_actors(32))
    data['job'].update(actors=32, actor_slots=slots)
    data['boundary']['actor_slots'] = slots
    for index, row in enumerate(data['rows']):
        row['client_slot'] = slots[index % 32]
    for field in ('actor_timeout_logs', 'actor_cleanup_timeout_logs'):
        data[field] = {str(slot): 0 for slot in slots}
    data['boot_restores'] = {str(slot): dict(identity='boot', files={'nvram': {'sha256': 'test'}})
                             for slot in slots}
    data['socket_wait']['actors'] = {str(slot): dict(matching_activation=True) for slot in slots}
    receipt_fixtures.add_confirmed_fixture(data)
    return data


class CapacityReceiptTests(unittest.TestCase):
    def test_32_complete_receipt_retains_all_slots_minimum_and_tail(self):
        data = receipt32()
        leg = backend.validate_backend(data)
        self.assertEqual(len(leg['rows']), 50)
        self.assertEqual(leg['expected_actor_slots'], list(range(4096, 4128)))
        self.assertGreater(leg['rows'][-1]['end_unix_s'], leg['close_ts'])
        data['rows'].pop()
        data['count'] = data['started'] = 49
        with self.assertRaisesRegex(ValueError, 'At least 50'):
            backend.validate_backend(data)

    def test_32_profile_rejects_reduced_boundary_extra_rows_and_missing_high_slot(self):
        data = receipt32()
        data['boundary']['actor_slots'] = list(sidecar.SLOTS)
        with self.assertRaisesRegex(ValueError, 'Every declared'):
            backend.validate_backend(data)
        data = receipt32()
        data['rows'][0]['client_slot'] = 9999
        receipt_fixtures.add_confirmed_fixture(data)
        with self.assertRaisesRegex(ValueError, 'Every declared'):
            backend.validate_backend(data)
        data = receipt32()
        data['rows'][31]['client_slot'] = 4096
        receipt_fixtures.add_confirmed_fixture(data)
        with self.assertRaisesRegex(ValueError, 'missing expected actor'):
            backend.validate_backend(data)

    def test_32_backend_rejects_missing_boot_wait_timeout_and_new_compiled_shapes(self):
        for field in ('boot_restores', 'actor_timeout_logs'):
            data = receipt32()
            data[field].pop('4127')
            with self.subTest(field=field), self.assertRaises(ValueError):
                backend.validate_backend(data)
        data = receipt32()
        data['socket_wait']['actors'].pop('4127')
        with self.assertRaises(ValueError):
            backend.validate_backend(data)
        data = receipt32()
        data['job']['inference_max_batch_size'] = 32
        with self.assertRaisesRegex(ValueError, 'frozen protocol'):
            backend.validate_backend(data)

    def test_cross_profile_quality_comparison_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, 'backend differs: actors'):
            backend.compare_sidecars(receipt_fixtures.sidecar('base16'), receipt32(), iterations=100)
        result = backend.compare_sidecars(receipt32('reference32'), receipt32('candidate32'), iterations=100)
        self.assertTrue(result['backend_validated'])
        self.assertEqual(result['score_ratio'], 1)

    def test_32_original_bytes_are_mandatory_independent_of_checkpoint_option(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            data = receipt32()
            data['job']['directory'] = str(directory)
            receipt_fixtures.write_terminal_fixture(data, directory)
            proof = backend.validate_original_backend(data, directory, verify_checkpoint=False)
            self.assertEqual(proof['original_terminal_readback']['verified_games'], 50)
            path = directory/'journal/games.jsonl'
            path.write_bytes(path.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError, 'original journal bytes changed'):
                backend.validate_original_backend(data, directory, verify_checkpoint=False)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                backend.validate_original_backend(data, directory, verify_checkpoint=False)

    def test_32_readback_rejects_wrong_directory_and_missing_successor(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            data = receipt32()
            data['job']['directory'] = str(directory)
            receipt_fixtures.write_terminal_fixture(data, directory)
            data['job']['directory'] = '/different/private/job'
            with self.assertRaisesRegex(ValueError, 'Exact declared'):
                backend.validate_original_backend(data, directory)
            data['job']['directory'] = str(directory)
            data['terminal_successors'].pop(data['rows'][-1]['journal_game_id'])
            with self.assertRaises(ValueError):
                backend.validate_original_backend(data, directory)


if __name__ == '__main__':
    unittest.main()
