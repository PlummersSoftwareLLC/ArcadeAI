"""CPU regressions for normal final producers and immutable review authorities.

The inherited full-path reviewer uses synthetic cohorts and OS/service replies.
It never reviews the actual failed study, runs an emulator/model, or promotes.
"""
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1]/'logs/managed-learning-20261015/run-26/supervised-quality32-chain-CPU-original01-preparation-20261019/immutable'), str(HERE/'profile03')]
import quality32_runtime_guard_v6 as guard
import test_closed_quality32_full_path_v6 as fixtures


class NormalProducerReviewTests(fixtures.FullPathTests):
    copy_authorities = True

    def build(self, candidate_gain=True, mutation=None):
        job, entry, main = super().build(candidate_gain, mutation)
        context = self.reader.read_pin(self.reader.pin(job['closed_context_path']))
        destination = self.root/'authority-copies'
        destination.mkdir(mode=0o700)
        self.normal_producers = []
        for kind in ('status', 'summary'):
            # Change only this synthetic fixture, matching actual producer modes.
            path = self.directory/(kind+'.json')
            path.chmod(0o664)
            before = self.reader.pin(path)
            self.normal_producers.append(before)
            context[kind+'_final'] = (
                guard.capture_final_authority(self.reader,path,destination,kind)['copy']
                if self.copy_authorities else before)
            self.assertEqual(self.reader.pin(path),before)
        self.put(job['closed_context_path'],context)
        return job,entry,main

    def test_old_direct_normal_authority_pin_reproduces_original_reader_rejection(self):
        self.copy_authorities = False
        result,holds,cleanup = self.execute()
        self.assertFalse(result['valid'])
        self.assertIn('Immutable artifact identity differs',result['error'])
        holds.assert_not_called()
        cleanup.assert_not_called()
        self.assertTrue(all(self.reader.pin(p['path'])==p for p in self.normal_producers))

    def test_actual_new_guard_close_path_publishes_copies_before_context(self):
        source = Path(guard.__file__).read_text()
        ast.parse(source)
        start = source.index('        def close_and_review(')
        body = source[start:source.index('\n    return QualityGuard',start)]
        self.assertLess(body.index('capture_final_authority('),body.index('context = dict('))
        self.assertIn("status_final=authorities['status']['copy']",body)
        self.assertIn("summary_final=authorities['summary']['copy']",body)


class CopyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reader = fixtures.review.reader_module()
        self.destination = self.root/'copies'
        self.destination.mkdir(mode=0o700)

    def producer(self,kind='status',raw=b'{"exact": 1}\n',mode=0o664):
        path = self.root/(kind+'.json')
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def test_exact_bytes_and_normal_producer_full_identity_preserved(self):
        path = self.producer(raw=b'{ "x": [1, 2] }\n\n')
        before = self.reader.pin(path)
        result = guard.capture_final_authority(self.reader,path,self.destination,'status')
        self.assertEqual(self.reader.pin(path),before)
        self.assertEqual(result['original'],before)
        self.assertEqual(self.reader.read_pin(result['copy'],as_json=False),path.read_bytes())
        self.assertEqual(result['copy']['identity']['mode'],'0o444')
        self.assertNotEqual(result['copy']['identity']['inode'],before['identity']['inode'])

    def test_existing_copy_never_overwritten(self):
        path = self.producer()
        first = guard.capture_final_authority(self.reader,path,self.destination,'status')
        with self.assertRaises(FileExistsError):
            guard.capture_final_authority(self.reader,path,self.destination,'status')
        self.assertEqual(self.reader.pin(first['copy']['path']),first['copy'])

    def test_linked_or_noncanonical_source_refused(self):
        target = self.producer(kind='summary')
        link = self.root/'status.json'
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'Canonical'):
            guard.capture_final_authority(self.reader,link,self.destination,'status')
        link.unlink()
        os.link(target,link)
        with self.assertRaisesRegex(ValueError,'regular authority'):
            guard.capture_final_authority(self.reader,target,self.destination,'summary')

    def test_oversized_or_empty_source_refused_without_copy(self):
        for raw in (b'',b'x'*(2*1024*1024+1)):
            path = self.producer(raw=raw)
            with self.assertRaisesRegex(ValueError,'Bounded'):
                guard.capture_final_authority(self.reader,path,self.destination,'status')
            self.assertEqual(list(self.destination.iterdir()),[])

    def test_both_terminal_authority_kinds_are_copied_independently(self):
        for kind in ('status','summary'):
            path = self.producer(kind=kind)
            result = guard.capture_final_authority(self.reader,path,self.destination,kind)
            self.assertEqual(self.reader.read_pin(result['copy'],as_json=False),path.read_bytes())
        self.assertEqual(len(list(self.destination.iterdir())),2)


if __name__ == '__main__':
    time.sleep(2)
    suite = unittest.defaultTestLoader.loadTestsFromNames(
        ['NormalProducerReviewTests','CopyBoundaryTests'],module=sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(schema='robotron-final-authority-normal-producer-CPU-v1',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        successful=result.wasSuccessful(),original_scientific_review_rerun=False,
        actual_guard_selected=False,quality_qualified=False,learning_speed_gain_verified=False)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
