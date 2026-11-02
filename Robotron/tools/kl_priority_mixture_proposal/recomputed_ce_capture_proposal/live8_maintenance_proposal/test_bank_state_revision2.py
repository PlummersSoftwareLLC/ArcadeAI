"""Source-authored stdlib fixtures: tiny metadata/headers only, never large arrays."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zipfile

HERE = Path(__file__).resolve().parent
MODULE = HERE / 'bank_state_revision2.py'
EXPECTED_SHA = 'e0c69fb38f5fec86e117edf42b4ff1ce2ff44b82b979c5240116121a7a1ce54f'
if hashlib.sha256(MODULE.read_bytes()).hexdigest() != EXPECTED_SHA:
    raise RuntimeError('Bank helper source pin changed')
specification = importlib.util.spec_from_file_location('_live8_bank_state_fixture', MODULE)
b = importlib.util.module_from_spec(specification)
specification.loader.exec_module(b)


def npy(dtype, shape, values, *, fortran=False, version=1):
    header = repr(dict(descr=dtype, fortran_order=fortran, shape=tuple(shape))).encode('latin1')
    length_width = 2 if version == 1 else 4
    padding = (-8 - length_width - len(header) - 1) % 64
    encoded = header + b' ' * padding + b'\n'
    return b'\x93NUMPY' + bytes((version, 0)) + len(encoded).to_bytes(length_width, 'little') + encoded + struct.pack('<' + b.DTYPES[dtype][0] * len(values), *values)


def write_meta(path, *, stride=3, width=2, lengths=(2, 1), scores=(100., 90.), revision=1):
    rows = dict(ep_len=('<i4', (len(lengths),), lengths), ep_score=('<f8', (len(scores),), scores),
                ep_game=('<i8', (len(lengths),), tuple(range(len(lengths)))),
                ep_level=('<i4', (len(lengths),), (1,) * len(lengths)))
    scalars = dict(stale_age=1, stale_age_normal=2, stride=stride, state_size=width, captured_adds=12,
                   mutation_generation=revision)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for key, (dtype, shape, values) in rows.items(): archive.writestr(key + '.npy', npy(dtype, shape, values))
        for key, value in scalars.items(): archive.writestr(key + '.npy', npy('<i8', (), (value,)))


def make_bank(root, *, bank='hof'):
    root.mkdir()
    generation = root / 'generations' / ('gen-' + 'a' * 32)
    generation.mkdir(parents=True)
    current = dict(schema=b.BANK_SCHEMA, bank=bank, generation=generation.name, previous=None, mutation_generation=1)
    (root / 'CURRENT.json').write_text(json.dumps(current))
    write_meta(generation / (bank + '_meta.npz'))
    for name, (dtype, shape) in b.storage_specs(6, 2, bank=True).items():
        (generation / (bank + '_' + name + '.npy')).write_bytes(npy(dtype, shape, (0,) * (shape[0] * (shape[1] if len(shape) > 1 else 1))))
    return generation


class BankStateTests(unittest.TestCase):
    def test_header_inspection_never_reads_array_body(self):
        for version in (1, 2, 3):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'states.npy'
                raw = npy('<f2', (2, 3), (0,) * 6, version=version); path.write_bytes(raw)
                boundary = len(raw) - 12
                original = b.open_file
                class HeaderOnly:
                    def __init__(self, stream): self.stream = stream
                    def read(self, size=-1):
                        if size < 0 or self.stream.tell() + size > boundary: raise AssertionError('Read array body')
                        return self.stream.read(size)
                    def fileno(self): return self.stream.fileno()
                    def __enter__(self): return self
                    def __exit__(self, *args): self.stream.close()
                def bounded(value):
                    pathname, stream, before = original(value)
                    return pathname, HeaderOnly(stream), before
                with mock.patch.object(b, 'open_file', side_effect=bounded):
                    observed = b.array_header(str(path), '<f2', (2, 3))
                self.assertEqual(observed['data_bytes'], 12)
                self.assertEqual(observed['data_offset'], boundary)

    def test_object_fortran_shape_extent_and_truncation_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'tiny.npy'
            good = npy('<i4', (2,), (1, 2))
            for raw in (good[:-1], npy('<i4', (2,), (1, 2), fortran=True),
                        good.replace(b"'<i4'", b"'|O4'"), good[:5]):
                with self.subTest(raw=raw[:12]):
                    path.write_bytes(raw)
                    with self.assertRaises((RuntimeError, ValueError, SyntaxError)):
                        b.array_header(str(path), '<i4', (2,))
            path.write_bytes(good)
            with self.assertRaisesRegex(RuntimeError, 'geometry/dtype'): b.array_header(str(path), '<i4', (3,))

    def test_v2_source_preallocated_ring_extent_only_and_no_body_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'states.npy'
            raw = npy('<f2', (2, 3), (0,) * 6, version=2)
            boundary, data_bytes = len(raw) - 12, 12
            original = b.open_file
            class HeaderOnly:
                def __init__(self, stream): self.stream = stream
                def read(self, size=-1):
                    if size < 0 or self.stream.tell() + size > boundary:
                        raise AssertionError('Read array body or padding')
                    return self.stream.read(size)
                def fileno(self): return self.stream.fileno()
                def __enter__(self): return self
                def __exit__(self, *args): self.stream.close()
            def bounded(value):
                pathname, stream, before = original(value)
                return pathname, HeaderOnly(stream), before
            for extent in (len(raw), data_bytes + 4096):
                path.write_bytes(raw + bytes(extent-len(raw)))
                with mock.patch.object(b, 'open_file', side_effect=bounded):
                    result = b.array_header(str(path), '<f2', (2, 3), replay_preallocation=True)
                self.assertEqual(result['identity']['size'], extent)
            # Banks and priorities do not pass the preallocation switch.
            with self.assertRaisesRegex(RuntimeError, 'logical file length'):
                b.array_header(str(path), '<f2', (2, 3))
            for extent in (data_bytes+4095, data_bytes+4097, len(raw)-1):
                path.write_bytes((raw + bytes(max(0, extent-len(raw))))[:extent])
                with self.assertRaisesRegex(RuntimeError, 'logical file length'):
                    b.array_header(str(path), '<f2', (2, 3), replay_preallocation=True)

    def test_small_npz_counts_lengths_and_scalar_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'hof_meta.npz'; write_meta(path)
            result = b.bank_metadata(str(path), 3, 2, 192)
            self.assertEqual(result['counts'], dict(episodes=2, transitions=3))
            self.assertEqual(result['ep_len'], [2, 1])
            self.assertEqual(result['scalars']['mutation_generation'], 1)

    def test_bad_npz_lengths_nonfinite_scores_wrong_stride_or_members_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'hof_meta.npz'
            for kwargs in (dict(lengths=(4, 1)), dict(lengths=(-1, 1)), dict(scores=(float('nan'), 90.)), dict(stride=4)):
                with self.subTest(kwargs=kwargs):
                    write_meta(path, **kwargs)
                    with self.assertRaises(RuntimeError): b.bank_metadata(str(path), 3, 2, 192)
            write_meta(path)
            with zipfile.ZipFile(path, 'a') as archive: archive.writestr('unexpected.npy', npy('<i8', (), (0,)))
            with self.assertRaisesRegex(RuntimeError, 'members'): b.bank_metadata(str(path), 3, 2, 192)

    def test_current_selects_actual_generation_and_shape_revision_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'bank'; generation = make_bank(root)
            result = b.bank_state('hof', root, 3, 2, 192)
            self.assertEqual(result['generation']['path'], str(generation))
            self.assertEqual(result['counts'], dict(episodes=2, transitions=3))
            self.assertEqual(len(result['arrays']), 8)
            self.assertEqual(result['arrays']['states']['shape'], [6, 2])
            write_meta(generation / 'hof_meta.npz', revision=2)
            with self.assertRaisesRegex(RuntimeError, 'revision'): b.bank_state('hof', root, 3, 2, 192)

    def test_missing_selected_generation_or_symlink_never_falls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'bank'; generation = make_bank(root)
            target = Path(temporary) / 'target'; generation.rename(target); generation.symlink_to(target, target_is_directory=True)
            with self.assertRaises(RuntimeError): b.bank_state('hof', root, 3, 2, 192)
            generation.unlink()
            with self.assertRaises((RuntimeError, FileNotFoundError)): b.bank_state('hof', root, 3, 2, 192)

    def map_fixture(self, root, *, missing=False, wrong_inode=False, permissions='rw-s'):
        pid = 12345; proc = root / 'proc'; task = proc / str(pid); task.mkdir(parents=True)
        (task / 'stat').write_text(str(pid) + ' (fixture worker) ' + ' '.join(['S'] + ['0'] * 18 + ['99']))
        arrays, lines = {}, []
        names = [*b.BANK_FIELDS, 'interesting']
        for index, name in enumerate(names):
            path = root / (name + '.npy'); path.write_bytes(b'no-array-body-proof')
            info = b.file_identity(path.stat()); arrays[name] = dict(path=str(path), identity=info)
            if missing and index == 0: continue
            inode = info['inode'] + int(wrong_inode and index == 0)
            lines.append('1000-2000 ' + permissions + ' 00000000 %x:%x %d %s\n' %
                         (os.major(info['device']), os.minor(info['device']), inode, path))
        (task / 'maps').write_text(''.join(lines))
        def local_path(value): return proc if str(value) == '/proc' else Path(value)
        return pid, dict(schema=b.SCHEMA, ring=dict(arrays=arrays)), mock.patch.object(b, 'Path', side_effect=local_path)

    def test_nine_persistent_ring_maps_match_actual_private_dev_inode(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid, snapshot, paths = self.map_fixture(Path(temporary))
            with paths: result = b.verify_maps(pid, snapshot)
            self.assertEqual(result['starttime_ticks'], 99)
            self.assertEqual(len(result['map_count_by_field']), 9)
            self.assertTrue(all(count == 1 for count in result['map_count_by_field'].values()))

    def test_missing_wrong_inode_or_readonly_ring_map_rejects(self):
        for defect in (dict(missing=True), dict(wrong_inode=True), dict(permissions='r--s')):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                pid, snapshot, paths = self.map_fixture(Path(temporary), **defect)
                with paths:
                    with self.assertRaises(RuntimeError): b.verify_maps(pid, snapshot)

    def test_maps_pid_reuse_and_file_replacement_after_read_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid, snapshot, paths = self.map_fixture(Path(temporary))
            with paths, mock.patch.object(b, 'process_start', side_effect=[99, 100]):
                with self.assertRaisesRegex(RuntimeError, 'PID changed'): b.verify_maps(pid, snapshot)
            first = next(iter(snapshot['ring']['arrays'].values()))
            original = b.process_start; calls = []
            def mutation(current):
                calls.append(current)
                if len(calls) == 2: Path(first['path']).write_bytes(b'changed')
                return 99
            with paths, mock.patch.object(b, 'process_start', side_effect=mutation):
                with self.assertRaisesRegex(RuntimeError, 'file identity changed'): b.verify_maps(pid, snapshot)

    def test_real_ring_meta_pointer_size_max_read_and_required_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); ring = root / 'ring'; model = root / 'models'; ring.mkdir(); model.mkdir()
            meta = ring / '_meta.npy'; meta.write_bytes(npy('<f8', (3,), (0., 6000000., 1.)))
            spec = dict(ring=str(ring), model_dir=str(model), capacity=6000000, state_size=11128,
                        episode_capacity=192, bank_strides=dict(hof=1536, ephof=2048))
            # Only descriptor argument checks are stubbed for huge logical extents;
            # actual metadata parser/ptr-size checks run, no sparse267GB files.
            with mock.patch.object(b, 'array_header', side_effect=lambda path,dtype,shape,**options:dict(path=path,dtype=dtype,shape=list(shape),preallocation=options.get('replay_preallocation',False))), \
                 mock.patch.object(b, 'bank_state', return_value={'counts': {'episodes': 2, 'transitions': 3}}):
                result = b.stopped_state(spec)
                self.assertEqual(result['ring']['meta']['size'], 6000000)
                self.assertEqual(result['ring']['arrays']['states']['shape'], [6000000, 11128])
                self.assertEqual({name for name,value in result['ring']['arrays'].items() if value['preallocation']},
                                 set(b.BANK_FIELDS) | {'interesting'})
                self.assertEqual(b.assert_unchanged(result, spec), result)
                spec['bank_strides']['hof'] = 64
                self.assertEqual(result['spec']['bank_strides']['hof'], 1536)
                with self.assertRaisesRegex(RuntimeError, 'geometry'): b.stopped_state(spec)
                spec['bank_strides']['hof'] = 1536
                meta.write_bytes(npy('<f8', (3,), (1., 6000000., 1.)))
                with self.assertRaisesRegex(RuntimeError, 'identity changed'): b.assert_unchanged(result, spec)


if __name__ == '__main__':
    unittest.main(verbosity=2)
