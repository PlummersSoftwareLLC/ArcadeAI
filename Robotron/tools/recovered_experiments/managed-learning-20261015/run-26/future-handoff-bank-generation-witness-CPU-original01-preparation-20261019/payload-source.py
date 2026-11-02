"""Bounded private adversarial bank-persistence witness tests; stdlib only."""
import argparse
import copy
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile


def header(dtype, shape):
    body = repr(dict(descr=dtype, fortran_order=False, shape=shape)).encode()
    padding = (-10-len(body)-1) % 64
    body += b' '*padding + b'\n'
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(body)) + body


def npy(dtype, shape, values):
    code = {'<f8':'d', '<i4':'i', '<i8':'q'}[dtype]
    return header(dtype, shape) + struct.pack('<'+code*len(values), *values)


def make_bank(witness, root, bank, *, bad_score=False):
    directory = root/bank
    generation = directory/'generations'/('gen-'+'a'*32)
    generation.mkdir(parents=True)
    metadata = dict(ep_score=npy('<f8', (2,), [math.inf if bad_score else 100., 200.]),
        ep_len=npy('<i4', (2,), [2, 1]), ep_game=npy('<i8', (2,), [1, 2]),
        ep_level=npy('<i4', (2,), [3, 4]))
    for name, value in dict(stale_age=1, stale_age_normal=1, stride=64, state_size=11128,
                            captured_adds=22, mutation_generation=7).items():
        metadata[name] = npy('<i8', (), [value])
    with zipfile.ZipFile(generation/(bank+'_meta.npz'), 'w') as archive:
        for name, value in metadata.items():
            archive.writestr(name+'.npy', value)
    for name, dtype in witness.FIELDS.items():
        shape = (128, 11128) if name in ('states','next_states') else (128,)
        prefix = header(dtype, shape)
        with (generation/(bank+'_'+name+'.npy')).open('wb') as stream:
            stream.write(prefix)
            stream.truncate(len(prefix) + math.prod(shape)*int(dtype[-1]))
    selector = dict(schema='robotron-bank-generation-v1', bank=bank,
                    generation=generation.name, previous=None, mutation_generation=7)
    (directory/'CURRENT.json').write_text(json.dumps(selector))
    return directory


def snapshot(timestamp, elapsed):
    total = dict(attempts_started=5, outcomes_recorded=5, applied=5, amp_skipped=0, unavailable=0)
    return dict(ts=timestamp, pipeline_snapshot_age_s=.1, pipeline_read_error='',
        bank_persistence_read_error='', training_enabled=False, measurement_active=True,
        managed_measurement=dict(active=True, phase='warming', generation=2, label='test-pause'),
        frame_count=2000, learner_frame_count=1000, measurement_frames=1000,
        training_steps=7, optimized_samples=3584,
        host_pipeline=dict(available=True, generation=1, elapsed_s=elapsed,
            learning_exposure=dict(optimizer=dict(enabled=True, available=True, process_id=123,
                epoch=1, total=total, unclassified_started_total=0),
                replay=dict(enabled=True, process_id=123, epoch=1, accepted_total=22,
                    accepted_learner_total=14, accepted_by_source_total=dict(dqn=14, expert=8)))),
        bank_persistence=dict(writer_active=False, write_failures=0, last_error=None,
            revision=dict(hof=7, ephof=7), saved_revision=dict(hof=7, ephof=7),
            dirty=dict(hof=False, ephof=False), output=dict(active=None)))


def suite(witness, work):
    class BankWitnessTests(unittest.TestCase):
        def setUp(self):
            self.directory = tempfile.TemporaryDirectory(dir=work)
            self.addCleanup(self.directory.cleanup)
            self.root = Path(self.directory.name)
            self.paths = {name: make_bank(witness, self.root, name) for name in ('hof','ephof')}
            self.banks = {name: witness.read_bank_generation(name, path) for name, path in self.paths.items()}
            self.before, self.after = snapshot(98, 10), snapshot(99, 12)

        def verify(self):
            return witness.validate_paused_bank_pair(self.before, self.after, self.banks,
                                                     expected_pid=123, now=100)

        def rejects(self):
            with self.assertRaises(ValueError):
                self.verify()

        def test_valid_pair_needs_independent_input_seal_and_reads_no_state_payload(self):
            original = witness.open_regular
            reads = []

            class HeaderOnly:
                def __init__(self, stream):
                    self.stream, self.total = stream, 0

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.stream.close()

                def fileno(self):
                    return self.stream.fileno()

                def read(self, count=-1):
                    self_test.assertTrue(0 <= count <= 65536)
                    self.total += count
                    self_test.assertLessEqual(self.total, 65546)
                    reads.append(count)
                    return self.stream.read(count)

            self_test = self

            def guarded(path):
                stream, info = original(path)
                return (HeaderOnly(stream), info) if Path(path).name.endswith('_states.npy') else (stream, info)

            with patch.object(witness, 'open_regular', side_effect=guarded):
                banks = {name: witness.read_bank_generation(name, path) for name, path in self.paths.items()}
            result = self.verify()
            self.assertTrue(reads)
            self.assertTrue(result['independent_sealed_input_witness_required'])
            self.assertFalse(result['production_handoff_ready'])
            self.assertEqual(banks['hof']['transitions'], 3)

        def test_dirty_RAM_bank_rejected(self):
            self.after['bank_persistence']['dirty']['hof'] = True
            self.rejects()

        def test_active_background_writer_rejected(self):
            self.before['bank_persistence']['writer_active'] = True
            self.rejects()

        def test_active_output_phase_rejected_even_if_writer_flag_false(self):
            self.after['bank_persistence']['output']['active'] = dict(phase='file_fsync')
            self.rejects()

        def test_failed_writer_rejected(self):
            self.after['bank_persistence']['write_failures'] = 1
            self.rejects()

        def test_stale_API_rejected(self):
            self.before['ts'] = 90
            self.rejects()

        def test_training_still_enabled_rejected(self):
            self.after['training_enabled'] = True
            self.rejects()

        def test_measurement_generation_changed_rejected(self):
            self.after['managed_measurement']['generation'] += 1
            self.rejects()

        def test_replay_insert_after_pause_rejected(self):
            self.after['host_pipeline']['learning_exposure']['replay']['accepted_total'] += 1
            self.rejects()

        def test_unfinished_optimizer_attempt_rejected(self):
            self.after['host_pipeline']['learning_exposure']['optimizer']['total']['attempts_started'] += 1
            self.rejects()

        def test_same_cached_bank_pipeline_sample_rejected(self):
            self.after['host_pipeline']['elapsed_s'] = self.before['host_pipeline']['elapsed_s']
            self.rejects()

        def test_RAM_saved_revision_does_not_match_disk_rejected(self):
            self.after['bank_persistence']['revision']['hof'] = 8
            self.after['bank_persistence']['saved_revision']['hof'] = 8
            self.rejects()

        def test_original_exposure_owner_changed_rejected(self):
            self.after['host_pipeline']['learning_exposure']['optimizer']['process_id'] = 456
            self.rejects()

        def test_truncated_state_array_rejected(self):
            path = self.paths['hof']/'generations'/('gen-'+'a'*32)/'hof_states.npy'
            with path.open('r+b') as stream:
                stream.truncate(path.stat().st_size-1)
            with self.assertRaises(ValueError):
                witness.read_bank_generation('hof', self.paths['hof'])

        def test_selector_path_escape_rejected(self):
            pointer = self.paths['hof']/'CURRENT.json'
            value = json.loads(pointer.read_text())
            value['generation'] = '../../outside'
            pointer.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                witness.read_bank_generation('hof', self.paths['hof'])

        def test_selector_metadata_revision_mismatch_rejected(self):
            pointer = self.paths['hof']/'CURRENT.json'
            value = json.loads(pointer.read_text())
            value['mutation_generation'] += 1
            pointer.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                witness.read_bank_generation('hof', self.paths['hof'])

        def test_nonfinite_episode_score_rejected(self):
            directory = self.root/'bad-score'
            directory.mkdir()
            path = make_bank(witness, directory, 'hof', bad_score=True)
            with self.assertRaises(ValueError):
                witness.read_bank_generation('hof', path)

        def test_symlinked_selected_array_rejected(self):
            path = self.paths['hof']/'generations'/('gen-'+'a'*32)/'hof_states.npy'
            destination = path.with_name('other.npy')
            path.rename(destination)
            path.symlink_to(destination)
            with self.assertRaises(ValueError):
                witness.read_bank_generation('hof', self.paths['hof'])

        def test_selector_changed_during_capture_rejected(self):
            original = witness.small_file
            pointer = self.paths['hof']/'CURRENT.json'
            calls = []

            def changed(path, maximum):
                if path == pointer:
                    calls.append(True)
                    if len(calls) == 2:
                        value = json.loads(pointer.read_text())
                        value['mutation_generation'] += 1
                        pointer.write_text(json.dumps(value))
                return original(path, maximum)

            with patch.object(witness, 'small_file', side_effect=changed), self.assertRaises(ValueError):
                witness.read_bank_generation('hof', self.paths['hof'])

        def test_wrong_array_dtype_rejected(self):
            path = self.paths['hof']/'generations'/('gen-'+'a'*32)/'hof_actions.npy'
            raw = path.read_bytes().replace(b"'<i8'", b"'<f8'", 1)
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                witness.read_bank_generation('hof', self.paths['hof'])

    return BankWitnessTests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--witness-source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('witness', args.witness_source)
    witness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(witness)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(suite(witness, args.work)))
    report = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), actual_bank_or_trainer_used=False,
        actual_checkpoint_or_optimizer_used=False, private_sparse_fixture_files_only=True,
        state_payload_reads_guarded_in_positive_case=True, production_handoff_ready=False)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
