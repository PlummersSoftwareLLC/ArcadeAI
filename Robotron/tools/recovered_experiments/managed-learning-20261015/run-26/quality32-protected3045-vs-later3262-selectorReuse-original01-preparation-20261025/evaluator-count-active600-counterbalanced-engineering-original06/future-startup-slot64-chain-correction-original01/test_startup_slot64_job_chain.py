"""CPU-only actual native-validator integration, never executes a native run."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = module('_job_chain_test_guard', HERE / 'startup_slot64_chain_v1.py')

    def fixture(self, role, root):
        case = '01-A1-control' if role == 'A32' else '02-B1-capacity64'
        job = json.loads((HERE.parent / case / 'job.json').read_bytes())
        # A future nonexistent output is mandatory; all real original files stay untouched.
        job['output'] = str(Path(root) / role / 'future-output')
        Path(job['output']).parent.mkdir()
        return self.guard.bind_future_job(job)

    def test_actual_new_A32_and_B64_native_validators_accept_new_bound_chain(self):
        with tempfile.TemporaryDirectory() as root:
            for role in ('A32', 'B64'):
                with self.subTest(role=role):
                    job = self.fixture(role, root)
                    native = module('_actual_native_' + role, HERE / role / 'run_evaluator_count_active600_v2.py')
                    self.assertEqual(native.validate_job(job), Path(job['output']))
                    self.assertEqual(job['lua']['path'], str(HERE / 'full-tail-observation-slot64-main.lua'))

    def test_actual_new_native_validator_refuses_old_chain_before_outputs(self):
        with tempfile.TemporaryDirectory() as root:
            job = self.fixture('B64', root)
            job.pop('startup_lua_chain')
            native = module('_native_old_chain_refusal', HERE / 'B64/run_evaluator_count_active600_v2.py')
            with self.assertRaises(KeyError):
                native.validate_job(job)
            self.assertFalse(Path(job['output']).exists())

    def test_old_Lua_entry_cannot_be_selected_under_new_chain_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            job = self.fixture('B64', root)
            original = json.loads((HERE.parent / '02-B1-capacity64/job.json').read_bytes())
            job['lua'] = original['lua']
            with self.assertRaises(AssertionError):
                self.guard.validate_job(job)

    def test_nested_adapter_must_be_present_as_exact_immutable_input(self):
        with tempfile.TemporaryDirectory() as root:
            job = self.fixture('B64', root)
            adapter = job['startup_lua_chain']['adapter']['path']
            job['inputs'] = [item for item in job['inputs'] if item['path'] != adapter]
            with self.assertRaises(AssertionError):
                self.guard.validate_job(job)

    def test_declared_guard_pin_cannot_disagree_with_actual_source(self):
        with tempfile.TemporaryDirectory() as root:
            job = self.fixture('B64', root)
            job['startup_lua_chain']['guard']['sha256'] = '0' * 64
            with self.assertRaises(AssertionError):
                self.guard.validate_job(job)

    def test_external_slot_and_changed_geometry_remain_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            job = self.fixture('B64', root)
            job['actor_slots'][-1] = 4160
            with self.assertRaises(AssertionError):
                self.guard.validate_job(job)

    def test_existing_original_output_cannot_be_rebound(self):
        original = json.loads((HERE.parent / '02-B1-capacity64/job.json').read_bytes())
        with self.assertRaises(AssertionError):
            self.guard.bind_future_job(original)

    def test_actual_native_actor_constructor_writes_new_entry_for_all64_slots(self):
        with tempfile.TemporaryDirectory() as root:
            job = self.fixture('B64', root)
            native = module('_native_actual_boot_chain', HERE / 'B64/run_evaluator_count_active600_v2.py')
            output = Path(job['output'])
            (output / 'actors').mkdir(parents=True)
            actors, streams, errors = {}, [], []
            # Use the real selected constructor and boot writer; only external
            # MAME/socket/seed/witness services are bounded CPU stand-ins.
            bridge = SimpleNamespace(StartupProxy=lambda *a, **kw: SimpleNamespace())
            witness = lambda stream: SimpleNamespace(emit=lambda value: None)
            seed = SimpleNamespace(restore_seed=lambda job, private: {'CPU_fixture_only': True})
            fake_socket = SimpleNamespace(setsockopt=lambda *a: None, bind=lambda *a: None,
                                          listen=lambda *a: None, settimeout=lambda *a: None)
            try:
                with patch.object(native.socket, 'socket', return_value=fake_socket):
                    native.prepare_actor_resources(job=job, output=output, server=None, h=None,
                        seed=seed, bridge=bridge, BoundedWitness=witness, bridge_stop=None,
                        policy_reader=None, admission=None, parse_frame_data=None,
                        drain_reader=None, actors=actors, streams=streams, errors=errors)
                self.assertEqual(set(actors), set(range(4096, 4160)))
                for slot in actors:
                    boot = (output / 'actors' / str(slot) / 'boot.lua').read_text()
                    self.assertIn(json.dumps(job['lua']['path']), boot)
                    self.assertNotIn('full-tail-wire-v2-contract-original01-preparation-20261022', boot)
                    self.assertFalse(actors[slot]['worker_started'])
                self.assertEqual(errors, [])
            finally:
                for stream in streams:
                    stream.close()


if __name__ == '__main__':
    unittest.main()
