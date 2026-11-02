import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from . import restore_reboot_ring_v1 as r


class RestoreRingTests(unittest.TestCase):
    def fixture(self, directory):
        source=directory/'source'; target=directory/'target'
        source.write_bytes(b'actual backup payload\0'*1000); source.chmod(0o444)
        target.write_bytes(bytes(source.stat().st_size))
        return dict(source=str(source), target=str(target), source_identity=r.regular(source),
                    target_identity=r.regular(target), sha256=hashlib.sha256(source.read_bytes()).hexdigest())

    def test_original_payload_is_copied_and_independently_reread(self):
        with tempfile.TemporaryDirectory()as root:
            row=self.fixture(Path(root)); guards=[]
            result=r.copy_verified(row,lambda:guards.append(True),lambda *unused:None)
            self.assertTrue(guards);self.assertTrue(result['full_destination_reread_verified'])
            self.assertEqual(Path(row['source']).read_bytes(),Path(row['target']).read_bytes())

    def test_changed_source_identity_rejects_before_writing(self):
        with tempfile.TemporaryDirectory()as root:
            row=self.fixture(Path(root));row['source_identity']['inode']+=1
            with self.assertRaisesRegex(ValueError,'backup source changed'):
                r.copy_verified(row,lambda:None,lambda *unused:None)
            self.assertEqual(set(Path(row['target']).read_bytes()),{0})

    def test_changed_destination_rejects_before_writing(self):
        with tempfile.TemporaryDirectory()as root:
            row=self.fixture(Path(root));row['target_identity']['inode']+=1
            with self.assertRaisesRegex(ValueError,'destination object changed'):
                r.copy_verified(row,lambda:None,lambda *unused:None)

    def test_checksum_mismatch_cannot_return_success(self):
        with tempfile.TemporaryDirectory()as root:
            row=self.fixture(Path(root));row['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'stream checksum'):
                r.copy_verified(row,lambda:None,lambda *unused:None)

    def test_guard_failure_stops_writes(self):
        with tempfile.TemporaryDirectory()as root:
            row=self.fixture(Path(root))
            def fail():raise ValueError('Trainer appeared')
            with self.assertRaisesRegex(ValueError,'Trainer appeared'):
                r.copy_verified(row,fail,lambda *unused:None)
            self.assertEqual(set(Path(row['target']).read_bytes()),{0})

    def test_meta_commit_is_after_every_verified_file(self):
        seen=[]
        result=r.restore_data_then_commit([1,2,3],lambda row:(seen.append(row)or row),lambda:seen.append('commit'))
        self.assertEqual(seen,[1,2,3,'commit']);self.assertEqual(result[0],[1,2,3])

    def test_any_file_failure_prevents_meta_commit(self):
        for failed in (1,2,3):
            seen=[]
            def copy(row):
                seen.append(row)
                if row==failed:raise ValueError('Original file failure')
            with self.assertRaises(ValueError):r.restore_data_then_commit([1,2,3],copy,lambda:seen.append('commit'))
            self.assertEqual(seen,list(range(1,failed+1)))

    def test_only_exact_metadata_shape_and_dtype_are_accepted(self):
        header=repr(dict(descr='<f8',fortran_order=False,shape=(3,))).encode()+b'\n'
        raw=b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+struct.pack('<3d',0,0,1)
        self.assertEqual(r.meta_values(raw),(0,0,1))
        with self.assertRaises(ValueError):r.meta_values(raw[:-1])
        with self.assertRaises(ValueError):r.meta_values(raw.replace(b'<f8',b'<i8'))


if __name__=='__main__':unittest.main()
