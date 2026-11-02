"""CPU parity, read-only provenance and asynchronous lifetime tests."""

import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"

import numpy as np

from .benchmark import bank_generation, copy_pool
from .parallel_replay import FieldFill, ParallelFill, fill_sequential
from Robotron.Scripts.dqn.replay_buffer import _fill_state_rows


def make_fields(width=7, indices=None, bank_indices=None):
    indices = np.array([4, 0, 4, 2], np.int64) if indices is None else indices
    bank_indices = np.array([1, 0, 1], np.int64) if bank_indices is None else bank_indices
    fields = []
    for sign in (1, -1):
        ring = (np.arange(5 * width).reshape(5, width) * sign / 10).astype(np.float16)
        bank = np.full((2, width), np.float32(sign * 1.000123), np.float32)
        for source in (ring, bank):
            source.flags.writeable = False
        fields.append(FieldFill(np.empty((len(indices) + len(bank_indices), width), np.float32),
                                ring, indices, ((bank, bank_indices),)))
    return tuple(fields)


def oracle(field):
    return np.concatenate([field.ring[field.indices].astype(np.float32)] +
                          [source[indices].astype(np.float32) for source, indices in field.banks])


class ParallelParityTests(unittest.TestCase):
    def test_duplicates_vector_tails_bank_precision_and_source_immutability(self):
        with ParallelFill() as pool:
            for width in (1, 7, 31, 111, 11128):
                fields = make_fields(width)
                sources = [source for field in fields for source in (field.ring, field.banks[0][0])]
                originals = [source.tobytes() for source in sources]
                expected = [oracle(field) for field in fields]
                for method in (fill_sequential, pool.fill, pool.fill):
                    result = method(fields)
                    for actual, field, wanted in zip(result, fields, expected):
                        self.assertIs(actual, field.output)
                        np.testing.assert_array_equal(actual.view(np.uint32), wanted.view(np.uint32))
                    self.assertEqual(originals, [source.tobytes() for source in sources])
                    self.assertTrue(all(not source.flags.writeable for source in sources))
                self.assertTrue(np.any(expected[0][-3:] != expected[0][-3:].astype(np.float16).astype(np.float32)))

    def test_empty_banks_empty_ring_and_empty_batch(self):
        empty = np.empty(0, np.int64)
        with ParallelFill() as pool:
            for ring_indices, bank_indices in ((np.array([4, 0], np.int64), empty),
                                               (empty, np.array([1, 0], np.int64)), (empty, empty)):
                fields = make_fields(indices=ring_indices, bank_indices=bank_indices)
                for actual, field in zip(pool.fill(fields), fields):
                    np.testing.assert_array_equal(actual, oracle(field))
            fields = tuple(FieldFill(np.empty((2, 7), np.float32), field.ring,
                                     np.array([4, 0], np.int64), ()) for field in fields)
            for actual, field in zip(pool.fill(fields), fields):
                np.testing.assert_array_equal(actual, oracle(field))

    def test_nonfinite_signed_zero_and_subnormal_values(self):
        values = np.array([0., -0., np.inf, -np.inf, np.nan, 2**-24, 65504.], np.float16)
        ring = np.tile(values, (3, 1)); ring.flags.writeable = False
        bank = np.array([[np.nan, np.inf, -np.inf, -0., 1.000123, 1e-40, -1e-40]], np.float32)
        bank.flags.writeable = False
        fields = tuple(FieldFill(np.empty((4, 7), np.float32), ring, np.array([2, 0], np.int64),
                                 ((bank, np.array([0, 0], np.int64)),)) for _ in range(2))
        before = (ring.tobytes(), bank.tobytes())
        with ParallelFill() as pool:
            for actual, field in zip(pool.fill(fields), fields):
                expected = oracle(field)
                np.testing.assert_array_equal(actual, expected)
                finite = np.isfinite(expected)
                np.testing.assert_array_equal(actual.view(np.uint32)[finite], expected.view(np.uint32)[finite])
                np.testing.assert_array_equal(np.signbit(actual), np.signbit(expected))
        self.assertEqual(before, (ring.tobytes(), bank.tobytes()))

    def test_actual_numpy_fallback_with_noncontiguous_fp32_source(self):
        fields = make_fields()
        alternate = np.arange(70, dtype=np.float32).reshape(5, 14)[:, ::2]
        alternate.flags.writeable = False
        fields = tuple(FieldFill(field.output, alternate, field.indices, field.banks) for field in fields)
        with ParallelFill() as pool:
            for actual, field in zip(pool.fill(fields), fields):
                np.testing.assert_array_equal(actual, oracle(field))

    def test_global_rng_unchanged(self):
        before = np.random.get_state()
        with ParallelFill() as pool:
            pool.fill(make_fields())
        after = np.random.get_state()
        for expected, actual in zip(before, after):
            np.testing.assert_array_equal(actual, expected)

    def test_invalid_outputs_and_cross_field_aliases_rejected_before_workers(self):
        calls = []
        with ParallelFill(lambda *args: calls.append(args)) as pool:
            fields = make_fields()
            read_only = fields[0].output.copy(); read_only.flags.writeable = False
            wrong = (read_only, np.empty((7, 7), np.float16), np.empty((7, 14), np.float32)[:, ::2],
                     np.empty((8, 7), np.float32), fields[1].banks[0][0])
            for output in wrong:
                with self.assertRaises(ValueError):
                    pool.fill((FieldFill(output, fields[0].ring, fields[0].indices, fields[0].banks), fields[1]))
            with self.assertRaisesRegex(ValueError, "alias each other"):
                pool.fill((fields[0], FieldFill(fields[0].output, fields[1].ring, fields[1].indices, fields[1].banks)))
            source = np.empty((7, 7), np.float32)
            alias_fields = (FieldFill(source, fields[0].ring, fields[0].indices, fields[0].banks),
                            FieldFill(fields[1].output, source, fields[1].indices, fields[1].banks))
            with self.assertRaisesRegex(ValueError, "alias any source"):
                pool.fill(alias_fields)
        self.assertEqual(calls, [])


class LifetimeTests(unittest.TestCase):
    def test_worker_exception_waits_for_other_writer_then_owner_retires(self):
        fields = make_fields()
        writing, release, failure, returned = (threading.Event() for _ in range(4))
        errors = []
        failing = [True]

        def fill(output, ring, indices, banks):
            if failing[0] and output is fields[0].output:
                if not writing.wait(3):
                    raise TimeoutError("Sibling did not start")
                failure.set()
                raise LookupError("Injected field error")
            if failing[0]:
                writing.set()
                if not release.wait(3):
                    raise TimeoutError("Test did not release sibling")
            return _fill_state_rows(output, ring, indices, banks)

        with ParallelFill(fill) as pool:
            def invoke():
                try:
                    pool.fill(fields)
                except BaseException as error:
                    errors.append(error)
                finally:
                    returned.set()
            caller = threading.Thread(target=invoke)
            caller.start()
            try:
                self.assertTrue(failure.wait(3))
                self.assertFalse(returned.wait(.03), "Error escaped while sibling owned the destination")
            finally:
                release.set(); caller.join(3)
            self.assertFalse(caller.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], LookupError)
            np.testing.assert_array_equal(fields[1].output, oracle(fields[1]))
            with self.assertRaisesRegex(RuntimeError, "closed"):
                pool.fill(fields)

    def test_partial_submission_failure_drains_first_writer(self):
        writing, release, returned = (threading.Event() for _ in range(3))
        errors = []
        def fill(*args):
            writing.set()
            if not release.wait(3):
                raise TimeoutError("Test did not release writer")
            return _fill_state_rows(*args)
        with ParallelFill() as pool:
            pool.fill(make_fields())
            pool._fill_fn = fill
            submit = pool._executor._publish
            calls = [0]
            def submit_once(*args):
                calls[0] += 1
                if calls[0] == 2:
                    if not writing.wait(3):
                        raise TimeoutError("First published writer did not start")
                    raise RuntimeError("Injected submit error")
                return submit(*args)
            def invoke():
                try:
                    pool.fill(make_fields())
                except BaseException as error:
                    errors.append(error)
                finally:
                    returned.set()
            with patch.object(pool._executor, "_publish", submit_once):
                caller = threading.Thread(target=invoke)
                caller.start()
                try:
                    self.assertTrue(writing.wait(3))
                    self.assertFalse(returned.wait(.03))
                finally:
                    release.set(); caller.join(3)
                self.assertFalse(caller.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertEqual(str(errors[0]), "Injected submit error")

    def test_real_invalid_index_error_is_propagated(self):
        fields = make_fields()
        bad = FieldFill(fields[0].output, fields[0].ring, np.array([99, 0, 0, 0], np.int64), fields[0].banks)
        with ParallelFill() as pool:
            with self.assertRaises(IndexError):
                pool.fill((bad, fields[1]))
            np.testing.assert_array_equal(fields[1].output, oracle(fields[1]))

    def test_close_is_idempotent_and_rejects_new_work(self):
        pool = ParallelFill()
        pool.fill(make_fields())
        pool.close(); pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            pool.fill(make_fields())


class ReadOnlyPoolTests(unittest.TestCase):
    def write_bank(self, path, bank, value, lengths=(2, 0, 1), stride=4):
        path.mkdir(parents=True)
        states = np.full((len(lengths) * stride, 7), -9999., np.float32)
        for episode, length in enumerate(lengths):
            states[episode * stride:episode * stride + length] = value
        for field in ("states", "next_states"):
            np.save(path / f"{bank}_{field}.npy", states)
        np.savez(path / f"{bank}_meta.npz", ep_len=np.array(lengths), stride=stride)

    def test_current_pinned_across_pointer_update_and_padding_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first, second = "gen-" + "a" * 32, "gen-" + "b" * 32
            for generation, value in ((first, 1.000123), (second, 2.000321)):
                self.write_bank(base / "generations" / generation, "hof", value)
            pointer = base / "CURRENT.json"
            def publish(generation):
                pointer.write_text(json.dumps(dict(schema="robotron-bank-generation-v1", bank="hof", generation=generation)))
            publish(first)
            pinned, metadata = bank_generation(base, "hof")
            publish(second)
            before = {file.name: file.read_bytes() for file in pinned.iterdir()}
            arrays, provenance = copy_pool(pinned, "hof", np.random.default_rng(151), 128)
            self.assertEqual(metadata["pointer"]["generation"], first)
            self.assertEqual(provenance["valid_rows"], 3)
            for value in arrays.values():
                self.assertTrue(np.all(value == np.float32(1.000123)))
                self.assertFalse(value.flags.writeable)
            self.assertEqual(before, {file.name: file.read_bytes() for file in pinned.iterdir()})

    def test_invalid_current_never_falls_back_to_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for generation in ("../elsewhere", "gen-" + "z" * 32, "gen-" + "a" * 32):
                (base / "CURRENT.json").write_text(json.dumps(dict(schema="robotron-bank-generation-v1", bank="hof", generation=generation)))
                with self.assertRaises(ValueError):
                    bank_generation(base, "hof")

    def test_empty_or_invalid_bank_geometry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for lengths in ((0, 0), (5, 1), (-1, 1)):
                path = Path(directory) / str(lengths)
                self.write_bank(path, "hof", 1., lengths=lengths)
                with self.assertRaises(ValueError):
                    copy_pool(path, "hof", np.random.default_rng(1), 10)

    def test_ring_metadata_uses_valid_size_not_write_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for field in ("states", "next_states"):
                np.save(path / f"{field}.npy", np.arange(35, dtype=np.float16).reshape(5, 7))
            np.save(path / "_meta.npy", np.array([0., 5., 1.]))
            arrays, metadata = copy_pool(path, "ring", np.random.default_rng(1), 32)
            self.assertEqual(metadata["valid_rows"], 5)
            self.assertEqual(arrays["states"].shape, (32, 7))


if __name__ == "__main__":
    unittest.main(verbosity=2)
