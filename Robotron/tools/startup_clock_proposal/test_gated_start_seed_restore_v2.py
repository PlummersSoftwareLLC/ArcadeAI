"""Distinct initialized-seed integration contract; no emulator or old test rerun."""
from pathlib import Path
import copy
import importlib.util
import json
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('gated_seed_runtime',HERE/'run_gated_start_seeded_trace_v2.py')
runtime=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
GAME=HERE.parents[1]
SEED=GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1'


def job():
    manifest=json.loads((SEED/'manifest.json').read_bytes())
    return dict(boot_seed=dict(directory=str(SEED),identity=manifest['identity'],
        module=runtime.pin(GAME/'tools/sidecar_boot.py'),
        inputs=[runtime.pin(SEED/name)for name in ['manifest.json',*manifest['files']]]))


def private(path):
    for name in ['cfg','ini','nvram']:
        (path/name).mkdir(mode=0o700)
    return path


class SeedRestoreContract(unittest.TestCase):
    def test_actual_seed_copy_private_mutability_and_original_preservation(self):
        selected=job()
        with tempfile.TemporaryDirectory(prefix='robotron-new-seed-integration-')as directory:
            output=private(Path(directory).resolve())
            proof=runtime.restore_seed(selected,output)
            self.assertEqual(proof['identity']['mode'],'0o444')
            result=json.loads(Path(proof['path']).read_bytes())
            self.assertEqual(result['identity'],selected['boot_seed']['identity'])
            self.assertEqual(len(result['private_files_before_MAME']),3)
            for before in result['private_files_before_MAME']:
                self.assertEqual(before['identity']['mode'],'0o600')
                self.assertEqual(runtime.pin(before['path']),before)
                relative=Path(before['path']).relative_to(output)
                self.assertEqual(before['sha256'],runtime.pin(SEED/relative)['sha256'])
            # MAME may update only these new private copies. The original
            # initialized seed and normal restore helper must stay unchanged.
            (output/'nvram/robotron/nvram').write_bytes(bytes(1024))
            for original in [selected['boot_seed']['module'],*selected['boot_seed']['inputs']]:
                self.assertEqual(runtime.pin(original['path']),original)

    def test_wrong_identity_incomplete_or_corrupt_binding_rejected_before_copy(self):
        original=job()
        variants=[]
        changed=copy.deepcopy(original);changed['boot_seed']['identity']='0'*64;variants.append(changed)
        changed=copy.deepcopy(original);changed['boot_seed']['inputs'][0]['sha256']='0'*64;variants.append(changed)
        changed=copy.deepcopy(original);changed['boot_seed']['inputs'].pop();variants.append(changed)
        for selected in variants:
            with self.subTest(selected=selected),tempfile.TemporaryDirectory(prefix='robotron-seed-rejection-')as directory:
                output=private(Path(directory).resolve())
                with self.assertRaises(ValueError):
                    runtime.restore_seed(selected,output)
                self.assertFalse([p for p in output.rglob('*')if p.is_file()])

    def test_existing_private_asset_is_never_overwritten(self):
        selected=job()
        with tempfile.TemporaryDirectory(prefix='robotron-seed-no-overwrite-')as directory:
            output=private(Path(directory).resolve())
            sentinel=output/'cfg/robotron.cfg'
            sentinel.write_bytes(b'EXISTING_PRIVATE_ASSET')
            before=runtime.pin(sentinel)
            with self.assertRaises(FileExistsError):
                runtime.restore_seed(selected,output)
            self.assertEqual(runtime.pin(sentinel),before)
            self.assertFalse((output/'original-initialized-boot-restore.json').exists())
            self.assertFalse(list((output/'nvram').rglob('*')))


if __name__=='__main__':
    unittest.main(verbosity=2)
