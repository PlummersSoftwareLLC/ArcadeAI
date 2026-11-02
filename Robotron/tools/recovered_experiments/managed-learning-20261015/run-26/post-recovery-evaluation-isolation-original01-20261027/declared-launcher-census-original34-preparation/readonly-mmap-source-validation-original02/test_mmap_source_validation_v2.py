"""NEW focused full-SHA/identity tests only; temporary regular files, no runtime queries."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().with_name('round_main_health_launcher_mmap_v2.py')
spec=importlib.util.spec_from_file_location('_mmap_full_source_tests',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_nonempty_and_empty_use_same_full_SHA_and_exact_identity(self):
        with tempfile.TemporaryDirectory()as directory:
            inputs={}
            for name,raw in (('nonempty',bytes(range(256))*65),('empty',b'')):
                path=Path(directory)/name;path.write_bytes(raw)
                inputs[str(path)]=dict(identity=m.file_identity(path),sha256=hashlib.sha256(raw).hexdigest())
            m.check_inputs(dict(inputs=inputs),full=True)

    def test_real_temporary_mutation_during_full_hash_is_refused(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'source';raw=b'ORIGINAL SOURCE';path.write_bytes(raw)
            case=dict(inputs={str(path):dict(identity=m.file_identity(path),sha256=hashlib.sha256(raw).hexdigest())})
            actual=hashlib.sha256
            def mutate_after_digest(data):
                result=actual(data)
                path.write_bytes(b'CHANGED! SOURCE')
                return result
            with patch.object(m.hashlib,'sha256',side_effect=mutate_after_digest),self.assertRaisesRegex(ValueError,'during full hash'):
                m.check_inputs(case,full=True)

    def test_wrong_SHA_identity_and_symbolic_path_still_refused(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'source';raw=b'FULL HASH';path.write_bytes(raw)
            identity=m.file_identity(path)
            with self.assertRaisesRegex(ValueError,'bytes changed'):
                m.check_inputs(dict(inputs={str(path):dict(identity=identity,sha256='0'*64)}),full=True)
            with self.assertRaisesRegex(ValueError,'identity changed'):
                m.check_inputs(dict(inputs={str(path):dict(identity=dict(identity,inode=identity['inode']+1),sha256=hashlib.sha256(raw).hexdigest())}),full=True)
            link=Path(directory)/'link';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'identity changed'):
                m.check_inputs(dict(inputs={str(link):dict(identity=identity,sha256=hashlib.sha256(raw).hexdigest())}),full=True)


if __name__=='__main__':unittest.main(verbosity=2)
