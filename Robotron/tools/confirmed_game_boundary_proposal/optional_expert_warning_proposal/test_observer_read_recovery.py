"""Stable immutable reads and recovery of never-attempted original reviews."""
import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import watch_confirmed_quality_audits_reviewed4 as watcher

HERE=Path(watcher.__file__).parent
PREP=HERE.parents[1]/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018'


def real_job():
    old_path=PREP/'audit-bindings-reviewed3/watcher-job.json'
    job=json.loads(old_path.read_bytes())
    job['failed_polling_predecessor']=dict(
        owner=json.loads((PREP/'audit-observer-reviewed3-execution/root-original-live-owner.json').read_bytes()),
        job=watcher.pin(old_path),source=watcher.pin(HERE/'watch_confirmed_quality_audits_reviewed3.py'),
        result=watcher.pin(PREP/'audit-bindings-reviewed3/observer/result.json'),
        archive=watcher.pin(PREP/'audit-observer-reviewed3-execution/native-terminal-archive/root-original-result-and-owned-release.json'))
    return job


class StableReadTests(unittest.TestCase):
    def test_real_relatime_update_does_not_invalidate_unchanged_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'evidence';path.write_bytes(b'unchanged evidence');path.chmod(0o444)
            now=time.time_ns();os.utime(path,ns=(now-86400*10**9,now))
            before=path.stat();value=watcher.pin(path);after=path.stat()
            self.assertNotEqual(before.st_atime_ns,after.st_atime_ns)
            self.assertEqual(watcher.stable_identity(before),watcher.stable_identity(after))
            self.assertEqual(value,watcher.pin(path))

    def test_all_recorded_original_pins_retain_the_same_ABI_and_digest(self):
        for entry in real_job()['pins']:
            with self.subTest(path=entry['path']):self.assertEqual(watcher.pin(entry['path']),entry)

    def test_symlink_is_not_immutable_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'original';path.write_bytes(b'data')
            link=Path(temp)/'link';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'symlink'):watcher.pin(link)

    def test_content_replacement_or_permissions_change_during_read_is_rejected(self):
        for change in ('content','replacement','permission'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'evidence';path.write_bytes(b'original')
                actual_open=Path.open
                class Reader:
                    def __enter__(self):
                        self.stream=actual_open(path,'rb');return self
                    def __exit__(self,*args):self.stream.close()
                    def fileno(self):return self.stream.fileno()
                    def read(self):
                        raw=self.stream.read()
                        if change=='content':
                            with actual_open(path,'wb') as target:target.write(b'changed!')
                        elif change=='replacement':
                            other=Path(temp)/'new'
                            with actual_open(other,'wb') as target:target.write(b'original')
                            other.replace(path)
                        else:path.chmod(0o400)
                        return raw
                with patch.object(Path,'open',lambda *args,**kwargs:Reader()),self.assertRaises(ValueError):
                    watcher.pin(path)

    def test_every_content_identity_field_participates(self):
        from types import SimpleNamespace
        names=('st_dev','st_ino','st_mode','st_nlink','st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns')
        original=SimpleNamespace(**dict.fromkeys(names,1),st_atime_ns=1)
        for name in names:
            changed=copy.deepcopy(original);setattr(changed,name,2)
            with self.subTest(name=name):self.assertNotEqual(watcher.stable_identity(original),watcher.stable_identity(changed))
        original.st_atime_ns=2
        self.assertEqual(watcher.stable_identity(original),watcher.stable_identity(SimpleNamespace(**dict.fromkeys(names,1))))

    def test_scientific_and_original_owner_predicates_are_AST_identical(self):
        def functions(path):
            return {node.name:ast.dump(node) for node in ast.parse(path.read_bytes()).body if isinstance(node,ast.FunctionDef)}
        old=functions(HERE/'watch_confirmed_quality_audits_reviewed3.py');new=functions(Path(watcher.__file__))
        for name in ('select_ready','validate_review','validate_reference_supplement','original_owner','publish'):
            with self.subTest(name=name):self.assertEqual(old[name],new[name])


class PredecessorTests(unittest.TestCase):
    def validate(self,job):
        with patch.object(watcher,'original_owner',return_value=True),patch.object(
                watcher.subprocess,'check_output',return_value='LoadState=not-found\n'):
            return watcher.validate_failed_predecessor(job)

    def replacement(self,job,key,value,temp):
        path=Path(temp)/key;path.write_text(json.dumps(value));job['failed_polling_predecessor'][key]=watcher.pin(path)

    def test_actual_original_failure_has_no_remaining_audit_attempts(self):
        job=real_job();before=copy.deepcopy(job)
        self.assertEqual(self.validate(job),job['failed_polling_predecessor']);self.assertEqual(job,before)

    def test_failed_poller_must_be_terminal(self):
        with patch.object(watcher,'original_owner',return_value=False),self.assertRaises(ValueError):
            watcher.validate_failed_predecessor(real_job())

    def test_any_original_remaining_attempt_or_other_failure_forbids_handoff(self):
        for change in ('attempt','other_failure','training','promotion','extra_audit'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                job=real_job();result=json.loads(Path(job['failed_polling_predecessor']['result']['path']).read_bytes())
                if change=='attempt':result['attempted'].append(2)
                elif change=='other_failure':result['error']="ValueError('Original audit failed')"
                elif change=='extra_audit':result['audits'].append(copy.deepcopy(result['audits'][0]))
                else:result['training_touched' if change=='training' else 'promotion']=True
                self.replacement(job,'result',result,temp)
                with self.assertRaises(ValueError):self.validate(job)

    def test_changed_cohort_or_audit_configuration_is_not_recoverable(self):
        for name in ('owner','plan','configs','reference_supplement'):
            job=real_job();job[name]=dict(job[name]);job[name]['changed']=True
            with self.subTest(name=name),self.assertRaises(ValueError):self.validate(job)

    def test_original_failed_outcome_must_not_be_rewritten_as_success(self):
        for name,value in (('original_exit',0),('unit_released',True),('failed_tombstone_retained',False),
                           ('timer_and_service_signaled',True),('remaining_original_audits_attempted',[2])):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                job=real_job();archive=json.loads(Path(job['failed_polling_predecessor']['archive']['path']).read_bytes())
                archive[name]=value;self.replacement(job,'archive',archive,temp)
                with self.assertRaises(ValueError):self.validate(job)

    def test_existing_remaining_unit_is_never_adopted_or_retried(self):
        with patch.object(watcher,'original_owner',return_value=True),patch.object(
                watcher.subprocess,'check_output',return_value='LoadState=loaded\n'),self.assertRaises(ValueError):
            watcher.validate_failed_predecessor(real_job())

    def test_existing_attempt_intent_blocks_recovery_before_child_launch(self):
        actual_glob=Path.glob
        def glob(path,pattern):
            return iter([path/'leg02-original-attempt.json']) if pattern=='leg0[234]-*' else actual_glob(path,pattern)
        with patch.object(Path,'glob',glob),self.assertRaises(ValueError):self.validate(real_job())


if __name__=='__main__':unittest.main()
