"""Unexecuted stdlib metadata guards; no project/runtime/numerical imports."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE=Path(__file__).with_name('validate_current_quality_release.py')
SPEC=importlib.util.spec_from_file_location('_strict_current_quality_metadata_guard',SOURCE)
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class StrictCurrentQualityGuards(unittest.TestCase):
    def changed(self,key,change):
        real=M._read
        fixed=json.loads(SOURCE.with_name('bindings.json').read_text())
        target=M.RELEASE if key=='release' else fixed[key]
        def read(pin):
            value=real(pin)
            if pin['path']==target['path']:
                value=copy.deepcopy(value);change(value)
            return value
        with mock.patch.object(M,'_read',side_effect=read):
            with self.assertRaises((ValueError,KeyError)):
                M.validate(M.RELEASE)

    def test_actual_readonly_metadata_chain_accepts_not_improved_without_activation(self):
        result=M.validate(M.RELEASE)
        self.assertEqual(result['status'],'PASS_STRICT_CURRENT_QUALITY_PREPARATION')
        self.assertEqual(result['original_audit_exits_preserved'],[2,0,2,0])
        self.assertEqual(result['original_R1_supplemental_exit_separate'],0)
        self.assertTrue(result['source_freeze_released'])
        self.assertTrue(result['owned_cleanup_complete'])
        self.assertFalse(result['candidate_promoted'])
        self.assertFalse(result['trial02_activated'])
        self.assertIsNone(result['actual_trial02'])
        fixed=json.loads(SOURCE.with_name('bindings.json').read_text())
        self.assertTrue({fixed[k]['path'] for k in ('plan','binding_job')}<=
            {pin['path'] for pin in result['checked_metadata_pins']})

    def test_old_winning_release_refuses_before_any_metadata_read(self):
        old=dict(path=str(M.RUN/'CE543M-quality-root-freeze-release-20261017/root-explicit-source-freeze-release.json'),
            sha256='c1abbbb5da36836830a367c6f4a165d890ee550120a79014d1d6aa8ca2191f2a',bytes=3184)
        with mock.patch.object(M,'_read',side_effect=AssertionError('Must not read old/current metadata')) as reader:
            with self.assertRaises(ValueError):M.validate(old)
            reader.assert_not_called()

    def test_required_release_booleans_missing_false_or_integer_refuse(self):
        for key in ('source_freeze_released','owned_cleanup_complete','narrow_reference_dispositions_preserved'):
            for value in (False,1,None):
                with self.subTest(key=key,value=value):self.changed('release',lambda x,k=key,v=value:x.__setitem__(k,v))
            with self.subTest(key=key,missing=True):self.changed('release',lambda x,k=key:x.pop(k))

    def test_wrong_parent_plan_or_binding_refuses(self):
        self.changed('release',lambda x:x['original_controller'].__setitem__('pid',620749))
        self.changed('all4_acceptance',lambda x:x['original_controller'].__setitem__('invocation_id','0'*32))
        for key in ('plan','binding_job'):
            with self.subTest(key=key):self.changed('release',lambda x,k=key:x[k].__setitem__('sha256','0'*64))

    def test_original_failed_audits_supplement_and_narrow_dispositions_preserved(self):
        self.changed('release',lambda x:x.__setitem__('original_audit_exits_preserved',[0,0,0,0]))
        self.changed('all4_acceptance',lambda x:x['legs'][0].__setitem__('original_audit_exit',0))
        self.changed('R1_supplemental_release',lambda x:x.__setitem__('supplemental_original_exit',2))
        self.changed('R1_supplemental_release',lambda x:x.__setitem__('supplemental_original_starttime_ticks',123))
        fixed=json.loads(SOURCE.with_name('bindings.json').read_text())
        real=M._read;target=fixed['legs'][2]['root_leg_acceptance']['path']
        def changed(pin):
            value=real(pin)
            if pin['path']==target:value=copy.deepcopy(value);value['original_failed_report_preserved']=False
            return value
        with mock.patch.object(M,'_read',side_effect=changed):
            with self.assertRaises(ValueError):M.validate(M.RELEASE)

    def test_resource_or_closure_pin_tamper_refuses(self):
        for key in ('original69_absent','main192_healthy','GPU0_free','parent_and_timer_not_found'):
            with self.subTest(key=key):self.changed('actual_owned_closure',lambda x,k=key:x.__setitem__(k,False))
        self.changed('after_resources',lambda x:x['observations']['API_summary'].__setitem__('client_count',191))
        self.changed('before_resources',lambda x:x['observations']['original69_absence'][0].__setitem__(
            'observed_start',x['observations']['original69_absence'][0]['expected_start']))
        self.changed('release',lambda x:x['actual_owned_closure'].__setitem__('sha256','0'*64))
        self.changed('exact_parent_timer_release',lambda x:x.__setitem__('original_exec_main_status',1))

    def test_real_tiny_readonly_json_hash_mode_and_full_identity_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'metadata.json';raw=b'{"value":1}\n';p.write_bytes(raw);p.chmod(0o444)
            pin=dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            self.assertEqual(M._read(pin),{'value':1})
            with self.assertRaises(ValueError):M._read(dict(pin,sha256='0'*64))
            s=p.stat();identity=dict(device=s.st_dev,inode=s.st_ino+1,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns,mode='0o444',uid=s.st_uid,nlink=s.st_nlink)
            with self.assertRaises(ValueError):M._read(dict(pin,identity=identity))
            p.chmod(0o644)
            with self.assertRaises(ValueError):M._read(pin)

    def test_default_plan_is_read_and_write_free(self):
        with (mock.patch.object(M,'_read',side_effect=AssertionError('No metadata read')) as read,
            mock.patch.object(M,'_publish',side_effect=AssertionError('No output')) as write,
            contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(M.main([]),0)
        read.assert_not_called();write.assert_not_called();self.assertIn('PLAN_ONLY',output.getvalue())


if __name__=='__main__':unittest.main()
