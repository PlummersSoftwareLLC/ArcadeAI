"""Authored stdlib/private-temp contracts; unexecuted by author."""
from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import prepare_448_candidate as prep


class PreparationContracts(unittest.TestCase):
    def terminal(self, **changes):
        value=dict(InvocationID=prep.WATCHER['invocation_id'],ExecMainPID=str(prep.WATCHER['pid']),
            ControlGroup=prep.WATCHER['cgroup'],NRestarts='0',MainPID='0',SubState='exited',
            ActiveState='active',ExecMainCode='1',ExecMainStatus='0',Result='success')
        value.update(changes)
        return '\n'.join(key+'='+value for key,value in value.items())

    def api(self):
        return dict(client_count=192,training_enabled=True,measurement_active=False,
            managed_experiment=prep.EXPERIMENT,lr=2.5e-5,loss=1.0,grad_norm=.1,
            training_steps=100,optimized_samples=409600,learner_frame_count=prep.TARGET,frame_count=2*prep.TARGET,
            host_pipeline=dict(learning_exposure=dict(optimizer=dict(process_id=prep.TRAINER['pid']))))

    def test_default_is_literal_without_read_query_output_or_candidate_copy(self):
        with patch.object(prep,'prepare',side_effect=AssertionError('no preparation')), \
                patch.object(prep,'pin',side_effect=AssertionError('no file read')), \
                patch.object(prep,'command',side_effect=AssertionError('no runtime')), \
                patch.object(Path,'mkdir',side_effect=AssertionError('no output')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(prep.main([]),0)
        self.assertIn('PLAN_ONLY',out.getvalue())

    def test_identity_omits_atime_but_retains_content_and_owner_fields(self):
        value=SimpleNamespace(st_dev=1,st_ino=2,st_size=3,st_mtime_ns=4,st_ctime_ns=5,
            st_mode=stat.S_IFREG|0o664,st_uid=os.getuid(),st_nlink=2,st_atime_ns=6)
        original=prep.identity(value);value.st_atime_ns=999
        self.assertEqual(prep.identity(value),original)
        value.st_ctime_ns+=1;self.assertNotEqual(prep.identity(value),original)
        self.assertEqual(original['nlink'],2)  # Source aliasing is not rewritten.

    def test_create_only_json_publication_has_exact_pin_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'record.json';record=prep.write_json(path,dict(tag=prep.TAG))
            self.assertEqual(prep.pin(path),record);self.assertEqual(path.stat().st_nlink,1)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o444)
            with self.assertRaises(FileExistsError):prep.write_json(path,dict(tag='other'))
            self.assertEqual(json.loads(path.read_text()),dict(tag=prep.TAG))

    def test_empty_journal_can_be_archived_without_weakening_generic_pin_or_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'original-watcher-journal.txt'
            record=prep.write_bytes(path,b'',allow_empty_archive=True)
            self.assertEqual(record['bytes'],0)
            self.assertEqual(prep.pin(path,minimum=0),record)
            with self.assertRaises(RuntimeError):prep.pin(path)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o444)

    def test_live_status_zero_is_wait_not_original_success_and_never_probes_absence(self):
        text=self.terminal(MainPID=str(prep.WATCHER['pid']),SubState='running',ExecMainCode='0')
        with patch.object(prep,'command',return_value=text), \
                patch.object(prep,'proc_start',side_effect=AssertionError('running is not retired')):
            self.assertEqual(prep.terminal_watcher(),(None,None))

    def test_wrong_invocation_or_original_failure_reject_before_candidate(self):
        for change in (dict(InvocationID='f'*32),dict(ExecMainStatus='1',Result='exit-code')):
            with self.subTest(change=change),patch.object(prep,'command',return_value=self.terminal(**change)), \
                    patch.object(prep,'proc_start',side_effect=AssertionError('no further probe')):
                with self.assertRaises(RuntimeError):prep.terminal_watcher()

    def test_exact_owned_pid_still_present_is_not_terminal_absence(self):
        with patch.object(prep,'command',return_value=self.terminal()), \
                patch.object(prep,'proc_start',return_value=prep.WATCHER['starttime_ticks']):
            with self.assertRaisesRegex(RuntimeError,'still exists'):prep.terminal_watcher()

    def test_absent_or_reused_numeric_pid_accepts_only_original_terminal_identity(self):
        for start in (FileNotFoundError(),prep.WATCHER['starttime_ticks']+1):
            with self.subTest(start=start),patch.object(prep,'command',return_value=self.terminal()), \
                    patch.object(prep,'proc_start',side_effect=start if isinstance(start,Exception) else None,
                                 return_value=start if not isinstance(start,Exception) else None), \
                    patch.object(Path,'exists',return_value=False):
                value,_=prep.terminal_watcher();self.assertEqual(value['ExecMainStatus'],'0')

    def test_terminal_identity_excludes_volatile_accounting_only(self):
        value=prep.fields(self.terminal());value.update(MemoryCurrent='100',CPUUsageNSec='10')
        original=prep.terminal_identity(value);value['MemoryCurrent']='0'
        self.assertEqual(prep.terminal_identity(value),original)
        value['InvocationID']='e'*32;self.assertNotEqual(prep.terminal_identity(value),original)

    def test_api_requires_same_owner_recipe192_and_all_four_clock_floors(self):
        value=self.api();floor={name:value[name] for name in prep.CLOCKS};prep.check_api(value,floor)
        for kind in ('clients','owner','branch',*prep.CLOCKS):
            with self.subTest(kind=kind):
                changed=copy.deepcopy(value)
                if kind=='clients':changed['client_count']=191
                elif kind=='owner':changed['host_pipeline']['learning_exposure']['optimizer']['process_id']+=1
                elif kind=='branch':changed['managed_experiment']='different'
                else:changed[kind]-=1
                with self.assertRaises(RuntimeError):prep.check_api(changed,floor)

    def test_candidate_small_bound_refusal_preserves_writable_aliased_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'tagged.pt';alias=root/'latest.pt';dest=root/'copy.pt'
            source.write_bytes(b'private synthetic bytes, never a tensor load');source.chmod(0o664);os.link(source,alias)
            before=prep.pin(source)
            with self.assertRaisesRegex(RuntimeError,'bounds'):
                prep.independent_copy(source,dest)
            self.assertEqual(prep.pin(source),before);self.assertEqual(alias.read_bytes(),source.read_bytes())
            self.assertFalse(dest.exists());self.assertEqual(source.stat().st_nlink,2)


if __name__=='__main__':
    unittest.main()
