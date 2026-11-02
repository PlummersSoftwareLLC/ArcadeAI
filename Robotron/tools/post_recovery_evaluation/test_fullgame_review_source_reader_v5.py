"""Exact source identity and immutable-artifact boundaries for real review inputs."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import fullgame_review_pipeline_v6 as p
from . import fullgame_review_entry_v5 as entry

I=p.BASE/'post-recovery-evaluation-isolation-original01-20261027'


class SourceReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h=p.helpers();commit=p.read(cls.h.pin(I/'fullgame-admission-four-reviews-engineering-original01/precommitted-four-reviews.json'))
        cls.job_pin=commit['cases'][0]['review_job'];cls.job=p.read(cls.job_pin)

    def test_old_artifact_reader_rejects_actual_pinned_writable_runtime_source(self):
        pin=self.job['sources']['runtime'];self.assertEqual(pin['identity']['mode'],'0o664')
        with self.assertRaisesRegex(ValueError,'Immutable artifact identity differs'):p.read(pin,False)

    def test_all_eleven_actual_dependencies_pass_exact_raw_reads_and_actual_module_loads(self):
        reader=entry.ReviewReader(self.job,self.h)
        for key,pin in self.job['sources'].items():
            raw=reader.read_pin(pin,as_json=False);self.assertEqual(hashlib.sha256(raw).hexdigest(),pin['sha256'])
            module=p.load('_actual_review_declared_dependency_'+key,Path(pin['path']))
            if key=='runtime':self.assertTrue(callable(module.actor_command))
            elif key=='wire':self.assertTrue(callable(module.audit_slot_prefix))
            elif key=='games':self.assertTrue(callable(module.review))

    def test_wrong_source_pin_json_mode_or_undeclared_dependency_is_rejected(self):
        reader=entry.ReviewReader(self.job,self.h);pin=self.job['sources']['runtime']
        for fault in ('sha','inode','json','missing_source'):
            damaged=copy.deepcopy(pin)
            if fault=='sha':damaged['sha256']='f'*64
            elif fault=='inode':damaged['identity']['inode']+=1
            elif fault=='missing_source':
                job=copy.deepcopy(self.job);job['sources'].pop('games')
                with self.assertRaises(ValueError):entry.ReviewReader(job,self.h)
                continue
            with self.subTest(fault=fault),self.assertRaises(ValueError):reader.read_pin(damaged,as_json=(fault=='json'))

    def test_unsealed_non_source_artifact_still_rejected_and_sealed_json_preserved(self):
        reader=entry.ReviewReader(self.job,self.h)
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'not-a-source.json';path.write_text('{"valid":true}\n');path.chmod(0o664)
            with self.assertRaisesRegex(ValueError,'Immutable artifact identity differs'):reader.read_pin(self.h.pin(path))
            sealed=self.h.put(Path(directory)/'original.json',dict(valid=True,score=123))
            self.assertEqual(reader.read_pin(sealed),dict(valid=True,score=123))

    def test_changed_actual_source_is_rechecked_after_read(self):
        reader=entry.ReviewReader(self.job,self.h);pin=self.job['sources']['runtime'];actual=self.h.checked;calls=[]
        def checked(value):
            calls.append(value)
            if len(calls)==2:raise ValueError('Selected input differs after read')
            return actual(value)
        with patch.object(self.h,'checked',side_effect=checked),self.assertRaisesRegex(ValueError,'after read'):
            reader.read_pin(pin,as_json=False)

    def test_engineering_entry_refuses_before_actual_scientific_reviewer_load(self):
        args=SimpleNamespace(job=Path(self.job_pin['path']),job_sha256=self.job_pin['sha256'],
            expected_source_sha256=self.h.pin(Path(entry.__file__).resolve())['sha256'])
        with self.assertRaisesRegex(ValueError,'Engineering contexts cannot execute'):
            entry.execute(args)


if __name__=='__main__':unittest.main()
