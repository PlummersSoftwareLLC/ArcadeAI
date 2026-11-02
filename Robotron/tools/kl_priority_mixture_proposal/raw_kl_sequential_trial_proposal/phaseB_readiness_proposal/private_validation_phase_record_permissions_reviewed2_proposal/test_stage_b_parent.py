"""Source-authored stdlib-only private publication/phase ownership tests.

No real checkpoints, tensors, processes, systemd, GPU, imports or execution by
author. Root owns any future execution. All data below is tiny private text.
"""
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import cuda_trace_parent as parent


class ParentContracts(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='raw-kl-parent-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/'output';self.root.mkdir()
        self.layout=parent.Layout(self.root,'fixture_nonce',Path(self.temporary.name)/'tmpfs')
        for role in parent.VARIANTS:
            paths=self.layout.phase(role)
            paths['root'].mkdir();paths['models'].mkdir()
        self.directory=self.layout.phase('kl18')['root']
        self.target=self.directory/'post-step-checkpoint.pt'
        self.temp=Path(str(self.target)+'.tmp')
        self.identity=parent.storage_directory_identity(self.root)
        self.role_identity=parent.storage_directory_identity(self.directory)
        self.events=dict(ignored_enoent=0,last_path=None)

    def write_json(self,path,value,mode=0o444):
        with Path(path).open('x') as stream:json.dump(value,stream)
        Path(path).chmod(mode)

    def pin(self,path):
        return parent.stable_file(path,hashlib.sha256(Path(path).read_bytes()).hexdigest(),Path(path).stat().st_size)

    def entered(self):
        path=self.directory/'save-entered.json'
        if path.exists():path.unlink()
        self.write_json(path,dict(schema='robotron-raw-kl-stage-b-save-v1',variant='kl18',
            stage='entered',path=str(self.target)))

    def complete(self):
        if self.temp.exists():os.replace(self.temp,self.target)
        elif not self.target.exists():self.target.write_bytes(b'private-checkpoint-bytes')
        self.target.chmod(0o444)
        self.write_json(self.directory/'save-complete.json',dict(schema='robotron-raw-kl-stage-b-save-v1',
            variant='kl18',stage='complete',path=str(self.target),saved_checkpoint=self.pin(self.target)))

    def context(self):
        return parent.checkpoint_publication_state(self.layout,'kl18',self.role_identity,self.events)

    def count_with_disappearance(self,context,transition=lambda:None,path=None,error=errno.ENOENT):
        path=self.temp if path is None else path
        original=os.stat;seen=[]
        def stat_value(name,*args,**kwargs):
            if name==path.name and kwargs.get('dir_fd') is not None and not seen:
                seen.append(True);transition()
                raise OSError(error,os.strerror(error),str(path))
            return original(name,*args,**kwargs)
        with patch.object(parent.os,'stat',side_effect=stat_value):
            result=parent.owned_byte_count(self.root,self.identity,checkpoint_save=context)
        self.assertTrue(seen)
        return result

    def test_pending_entered_becomes_complete_and_renames_during_same_walk(self):
        (self.directory/'save-entered.json').write_bytes(b'')
        self.temp.write_bytes(b'private-checkpoint-bytes')
        context=self.context();self.assertFalse(context['initial_complete'])
        self.assertEqual(self.events['pending_marker_snapshots'],1)
        def finish():self.entered();self.complete()
        self.count_with_disappearance(context,finish)
        self.assertEqual(self.events['ignored_enoent'],1)
        self.assertEqual(self.events['completed_during_scan'],1)
        self.assertTrue(self.target.exists());self.assertFalse(self.temp.exists())

    def test_absent_entered_becomes_active_before_exact_temp_disappears(self):
        self.temp.write_bytes(b'fixture')
        context=self.context()
        def become_active():self.entered();self.temp.unlink()
        self.count_with_disappearance(context,become_active)
        self.assertEqual(self.events['ignored_enoent'],1)

    def test_pending_entered_never_authorizes_existing_temp_loss(self):
        (self.directory/'save-entered.json').write_bytes(b'partial')
        self.temp.write_bytes(b'fixture')
        with self.assertRaises(FileNotFoundError):self.count_with_disappearance(self.context(),self.temp.unlink)
        self.assertEqual(self.events['ignored_enoent'],0)

    def test_stale_absent_or_pending_entered_is_read_once_again_after_complete_appears(self):
        self.entered();self.complete()
        path=self.directory/'save-entered.json';real_lstat=Path.lstat;real_bounded=parent.bounded_json
        for first in ('absent','pending'):
            seen=[];parsed=[]
            def lstat(value,*args,**kwargs):
                if value==path and not seen:
                    seen.append(True)
                    if first=='absent':raise FileNotFoundError(errno.ENOENT,'stale first view',str(path))
                    return SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=os.getuid(),st_nlink=1,st_size=0)
                return real_lstat(value,*args,**kwargs)
            def bounded(record,**kwargs):
                parsed.append(record['path']);return real_bounded(record,**kwargs)
            with self.subTest(first=first),patch.object(Path,'lstat',lstat),patch.object(parent,'bounded_json',side_effect=bounded):
                result=parent.checkpoint_marker_snapshot(self.directory,self.events)
            self.assertTrue(result['entered_valid']);self.assertIsNotNone(result['completed'])
            self.assertEqual(parsed.count(str(path)),1)

    def test_complete_with_genuinely_missing_entered_is_still_refused(self):
        self.complete()
        with self.assertRaisesRegex(RuntimeError,'lacks validated entered'):
            parent.checkpoint_marker_snapshot(self.directory,self.events)

    def test_preexisting_complete_never_authorizes_later_stale_temp_loss(self):
        self.entered();self.complete();self.temp.write_bytes(b'stale')
        context=self.context();self.assertTrue(context['initial_complete'])
        with self.assertRaises(FileNotFoundError):self.count_with_disappearance(context,self.temp.unlink)

    def test_valid_entered_pending_complete_allows_exact_active_edge(self):
        self.entered();(self.directory/'save-complete.json').write_bytes(b'')
        self.temp.write_bytes(b'fixture')
        self.count_with_disappearance(self.context(),self.temp.unlink)
        self.assertEqual(self.events['ignored_enoent'],1)

    def test_completed_during_walk_requires_exact_final_fd_path_pin(self):
        self.temp.write_bytes(b'fixture');context=self.context()
        def wrong_final():
            self.entered();self.complete()
            # A replacement after completion cannot reuse the old inode PIN.
            self.target.unlink();self.target.write_bytes(b'replacement');self.target.chmod(0o444)
        with self.assertRaisesRegex(RuntimeError,'FD/path readonly binding'):
            self.count_with_disappearance(context,wrong_final)

    def test_foreign_temp_or_persistent_checkpoint_disappearance_is_fatal(self):
        self.entered()
        for name in ('other.pt.tmp','post-step-checkpoint.pt','post-step-checkpoint.pt.bak'):
            path=self.directory/name;path.write_bytes(b'fixture')
            with self.subTest(name=name),self.assertRaises(FileNotFoundError):
                self.count_with_disappearance(self.context(),path.unlink,path=path)

    def test_checkpoint_symlink_and_other_io_are_not_exempt(self):
        self.entered();self.temp.symlink_to(self.directory/'missing')
        with self.assertRaisesRegex(RuntimeError,'symlink'):
            parent.owned_byte_count(self.root,self.identity,checkpoint_save=self.context())
        self.temp.unlink();self.temp.write_bytes(b'fixture')
        for code in (errno.EACCES,errno.EIO,errno.ESTALE):
            with self.subTest(errno=code),self.assertRaises(OSError) as result:
                self.count_with_disappearance(self.context(),error=code)
            self.assertEqual(result.exception.errno,code)

    def test_marker_malformed_readonly_symlink_and_wrong_path_are_fatal(self):
        path=self.directory/'save-entered.json';path.write_bytes(b'{');path.chmod(0o444)
        with self.assertRaises(json.JSONDecodeError):self.context()
        path.unlink();path.symlink_to(self.directory/'missing')
        with self.assertRaises(RuntimeError):self.context()
        path.unlink();self.write_json(path,dict(schema='robotron-raw-kl-stage-b-save-v1',
            variant='kl18',stage='entered',path=str(self.target)+'.foreign'))
        with self.assertRaisesRegex(RuntimeError,'context differs'):self.context()

    def test_final_scan_has_no_checkpoint_exception(self):
        self.entered();self.temp.write_bytes(b'fixture')
        with self.assertRaises(FileNotFoundError):self.count_with_disappearance(None,self.temp.unlink)

    def test_checkpoint_copy_is_independent_and_never_chmods_source(self):
        source=Path(self.temporary.name)/'source.pt';source.write_bytes(b'checkpoint');source.chmod(0o444)
        before=source.stat();pin=self.pin(source)
        copied=parent.copy_checkpoint(pin,self.layout.phase('kl18')['models']/'robotron_dqn_latest.pt')
        self.assertNotEqual(copied['identity']['inode'],pin['identity']['inode'])
        self.assertEqual(copied['identity']['mode'],0o444)
        self.assertEqual(source.stat().st_ino,before.st_ino)
        self.assertEqual(source.stat().st_ctime_ns,before.st_ctime_ns)
        self.assertEqual(source.read_bytes(),b'checkpoint')

    def test_role_records_bind_independent_latest_then_newest_poststep_for_both_roles(self):
        source=Path(self.temporary.name)/'initial448.pt';source.write_bytes(b'initial448');source.chmod(0o444)
        source_pin=self.pin(source)
        manifest=self.root/'launch-manifest.json'
        self.write_json(manifest,dict(nonce='fixture_nonce',trained_fixture={'source':source_pin}))
        base=SimpleNamespace(json_exclusive=lambda path,value:self.write_json(path,value))
        initial=parent.prepare_role_inputs(base,self.layout,manifest,'kl18',[])
        self.assertEqual(parent.read_role_input(self.layout,'kl18',parent.digest(manifest)),initial)
        self.target.write_bytes(b'newest18');self.target.chmod(0o444)
        result=dict(status='OBSERVATIONS_COMPLETE',variant='kl18',actual_attempts=18,saved_checkpoint=self.pin(self.target))
        self.write_json(self.directory/'phase-result.json',result)
        for role,previous in (('resume',[result]),('return_ce',[result,dict(variant='resume')])):
            value=parent.prepare_role_inputs(base,self.layout,manifest,role,previous)
            self.assertEqual(parent.read_role_input(self.layout,role,parent.digest(manifest)),value)
            self.assertEqual(value['source'],result['saved_checkpoint'])
            self.assertNotEqual(value['latest']['sha256'],source_pin['sha256'])
            record=json.loads(Path(value['phase_record']['path']).read_text())
            self.assertEqual(record['action'],'resume' if role=='resume' else 'start')
            self.assertEqual(record['previous_metric'],'kl')
            self.assertEqual(record['metric'],'ce' if role=='return_ce' else 'kl')

    def test_real_writable_publisher_is_sealed_before_all_three_role_readers(self):
        source=Path(self.temporary.name)/'initial448.pt';source.write_bytes(b'initial448');source.chmod(0o444)
        manifest=self.root/'launch-manifest.json'
        self.write_json(manifest,dict(nonce='fixture_nonce',trained_fixture=dict(source=self.pin(source))))
        published=[];consumed=[];real_stable=parent.stable_file
        def writable_publisher(path,value):
            self.write_json(path,value,mode=0o644)
            published.append((str(path),stat.S_IMODE(Path(path).stat().st_mode)))
        def reader(path,*args,**kwargs):
            if Path(path).name=='phase-record.json':
                consumed.append(str(path));self.assertEqual(stat.S_IMODE(Path(path).stat().st_mode),0o444)
            return real_stable(path,*args,**kwargs)
        base=SimpleNamespace(json_exclusive=writable_publisher)
        initial=parent.prepare_role_inputs(base,self.layout,manifest,'kl18',[])
        self.assertEqual(parent.read_role_input(self.layout,'kl18',parent.digest(manifest)),initial)
        self.target.write_bytes(b'newest18');self.target.chmod(0o444)
        result=dict(status='OBSERVATIONS_COMPLETE',variant='kl18',actual_attempts=18,saved_checkpoint=self.pin(self.target))
        self.write_json(self.directory/'phase-result.json',result)
        with patch.object(parent,'stable_file',side_effect=reader):
            for role,previous in (('resume',[result]),('return_ce',[result,dict(variant='resume')])):
                value=parent.prepare_role_inputs(base,self.layout,manifest,role,previous)
                self.assertEqual(parent.read_role_input(self.layout,role,parent.digest(manifest)),value)
        self.assertEqual(len(published),6)
        self.assertTrue(all(mode==0o644 for _,mode in published))
        for role in parent.VARIANTS:
            for name in ('phase-record.json','role-input.json'):
                self.assertEqual(stat.S_IMODE((self.layout.phase(role)['root']/name).stat().st_mode),0o444)
        self.assertTrue(all(str(self.layout.phase(role)['root']/'phase-record.json') in consumed for role in ('resume','return_ce')))

    def test_failed_readonly_seal_retains_first_error_and_never_publishes_role_input(self):
        source=Path(self.temporary.name)/'initial448.pt';source.write_bytes(b'initial448');source.chmod(0o444)
        manifest=self.root/'launch-manifest.json'
        self.write_json(manifest,dict(nonce='fixture_nonce',trained_fixture=dict(source=self.pin(source))))
        base=SimpleNamespace(json_exclusive=lambda path,value:self.write_json(path,value,mode=0o644))
        sentinel=OSError(errno.EACCES,'owned metadata chmod failed')
        with patch.object(parent.os,'fchmod',side_effect=sentinel),self.assertRaises(OSError) as failure:
            parent.prepare_role_inputs(base,self.layout,manifest,'kl18',[])
        self.assertIs(failure.exception,sentinel)
        self.assertEqual(stat.S_IMODE((self.directory/'phase-record.json').stat().st_mode),0o644)
        self.assertFalse((self.directory/'role-input.json').exists())
        self.assertTrue((self.layout.phase('kl18')['models']/'robotron_dqn_latest.pt').exists())

    def test_completed_role_unknown_checkpoint_path_is_not_adopted(self):
        source=Path(self.temporary.name)/'foreign.pt';source.write_bytes(b'foreign');source.chmod(0o444)
        manifest=self.root/'launch-manifest.json';self.write_json(manifest,dict(nonce='fixture_nonce'))
        result=dict(variant='kl18',saved_checkpoint=self.pin(source))
        with self.assertRaisesRegex(RuntimeError,'newest private post-step'):
            parent.prepare_role_inputs(SimpleNamespace(),self.layout,manifest,'resume',[result])


if __name__=='__main__':
    unittest.main()
