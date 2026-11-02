"""UNEXECUTED stdlib closed-metadata guards, not a capture or numerical proof.

Authentic closed corrected22 b5 success supplies the unchanged release/identity/
archive shape. Only its unit-cat text is substituted in memory to describe the
prospective capture command. No actual capture output/model is opened.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import unittest

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'live_lr_recipe_continuation_proposal'
RUN=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
SUCCESS=RUN/'LR25-continuation-22-corrected-metadata-guards-original01-root-execution-20261018/root-original-result-and-owned-release.json'
SUCCESS_SHA='ce485ed9dd03a924fdf209d4537f7bb76715e38768aa2dd0fc373628ca964bb4'
FAILED=RUN/'LR25-continuation-22-metadata-guards-original01-root-execution-20261018/root-original-result-and-owned-release.json'
FAILED_SHA='f108e64585413ad36fd78623cd023339bbfa3beb366d30a290a2f03eef3d414b'
BINDER_SHA='888f05060527f79ece09892394543ae07375bd3c400374bdb3fd320ac576b774'


def closed_json(path,expected):
    if path.suffix!='.json':raise AssertionError('Only closed JSON metadata allowed')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise AssertionError('Closed metadata changed')
    return json.loads(raw)


def archived(pin):
    path=Path(pin['path'])
    if path.suffix in ('.pt','.pth','.npy','.npz'):raise AssertionError('No model/tensor referents')
    before=path.lstat();raw=path.read_bytes();after=path.lstat()
    def identity(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    if not(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and
        stat.S_IMODE(before.st_mode)==0o444 and len(raw)==pin['bytes'] and len(raw)<=4<<20 and
        hashlib.sha256(raw).hexdigest()==pin['sha256'] and identity(before)==identity(after) and
        all(identity(before)[k]==v for k,v in pin['identity'].items())):
        raise AssertionError('Closed raw archive changed')
    return raw.decode('utf-8','surrogateescape')


def synthetic_pin(path,letter):
    return dict(path=path,sha256=letter*64,bytes=100,identity=dict(device=1,inode=1,bytes=100,
        mtime_ns=1,ctime_ns=1,mode='0o444',uid=1001,nlink=1))


class GCAwareCaptureMetadataContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=HERE/'quality_bindings.py';raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=BINDER_SHA:raise AssertionError('Selected binder changed')
        spec=importlib.util.spec_from_file_location('_gcaware_capture_metadata_guard',path)
        cls.B=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.B)
        cls.success=closed_json(SUCCESS,SUCCESS_SHA)
        cls.failed=closed_json(FAILED,FAILED_SHA)
        cls.texts={}
        # Read only the explicit closed six-group streams and release readbacks.
        leaves=[]
        for row in cls.success['full_original_archives']:leaves.extend((row['stdout'],row['stderr']))
        for row in cls.success['owned_release']:
            for key in ('stop','final'):
                leaves.extend((row[key]['stdout'],row[key]['stderr']))
        for p in leaves:cls.texts[(p['path'],p['sha256'])]=archived(p)

    def fixture(self):
        released=copy.deepcopy(self.success)
        case=dict(output_directory='/synthetic/future-first-capture')
        case_pin=synthetic_pin('/synthetic/future-case.json','b')
        result_pin=synthetic_pin(case['output_directory']+'/result.json','a')
        command=['/synthetic/ft-python','-Xgil=0','-I','-B',str(self.B.SELECTOR),'--execute',
            '--case',case_pin['path'],'--expected-case-sha256',case_pin['sha256'],
            '--output',case['output_directory'],'--expected-source-sha256',self.B.SELECTOR_SHA]
        cat_pin=released['full_original_archives'][1]['stdout']
        selected=dict(self.texts)
        # Deliberate adapter: the authentic closed unit ran stdlib tests. Only
        # this mock text substitutes its ExecStart with an exact future capture.
        selected[(cat_pin['path'],cat_pin['sha256'])]='[Service]\nExecStart='+shlex.join(command)+'\n'
        def reader(p):
            key=(p['path'],p['sha256'])
            if key not in selected:raise AssertionError('Unexpected archive read; no host fallback')
            return selected[key]
        return released,result_pin,case_pin,case,selected,reader

    def call(self,fixture):
        r,result_pin,case_pin,case,selected,reader=fixture
        return self.B.check_root_capture(r,result_pin,case_pin,case,reader)

    def test_authentic_closed_b5_success_and_unchanged_legacy_success(self):
        f=self.fixture();self.call(f)
        self.assertEqual(f[0]['original'],self.success['original'])
        self.assertEqual(f[0]['full_original_archives'],self.success['full_original_archives'])
        legacy=list(self.fixture());legacy[0]['schema']='robotron-root-retained-original-result-and-release-v1'
        self.call(legacy)
        self.assertEqual(str(self.B.SELECTOR),str(OLD/'capture_candidate.py'))
        self.assertEqual(str(self.B.PHASE),str(OLD/'verify_recipe_phase_snapshot.py'))
        self.assertEqual(str(self.B.OBSERVER),str(OLD/'observer.py'))

    def test_gcaware_flags_status_types_and_missing_fields_refuse(self):
        changes=[('status','ORIGINAL_AUDIT_NONZERO_ARCHIVED_AND_RELEASED'),('lifecycle_complete',False),
            ('all_six_original_archive_commands_succeeded',False),('error','archive failure'),('payload_retried',True),
            ('audit_success',False),('unit_released',False),('original_archived_before_release',False),
            ('original_exec_code',True),('original_exit',0.0),('original_result','exit-code')]
        for key,value in changes:
            f=list(self.fixture());f[0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.call(f)
        for key in ('status','lifecycle_complete','all_six_original_archive_commands_succeeded','error','payload_retried'):
            f=list(self.fixture());del f[0][key]
            with self.subTest(missing=key),self.assertRaises(KeyError):self.call(f)
        f=list(self.fixture());f[0]['schema']='unknown-pretend-success'
        with self.assertRaises(ValueError):self.call(f)

    def test_authentic_original_nonzero_and_gc_exception_are_never_success(self):
        f=list(self.fixture());f[0]=copy.deepcopy(self.failed)
        self.assertEqual(f[0]['original_exit'],1)
        with self.assertRaises(ValueError):self.call(f)
        f=list(self.fixture());f[0]['original_exit']=2
        with self.assertRaises(ValueError):self.call(f)
        f=list(self.fixture());f[0]['all_six_original_archive_commands_succeeded']=False
        f[0]['full_original_archives'][4]['exit']=1
        with self.assertRaises(ValueError):self.call(f)

    def test_actual_six_commands_identity_chronology_and_stop0_stay_strict(self):
        mutations=(lambda r:r['full_original_archives'].pop(),
            lambda r:r['full_original_archives'][4].update(exit=1),
            lambda r:r['full_original_archives'][0]['argv'].append('--foreign'),
            lambda r:r['original'].update(observed_live=False),
            lambda r:r['original'].update(invocation_id='f'*32),
            lambda r:r['owned_release'][0]['stop'].update(exit=5),
            lambda r:r['owned_release'].reverse(),
            lambda r:r['full_original_archives'][0].update(unix_s=r['owned_release'][1]['stop']['unix_s']+1))
        for i,mutate in enumerate(mutations):
            f=list(self.fixture());mutate(f[0])
            with self.subTest(i=i),self.assertRaises((ValueError,KeyError)):self.call(f)
        f=list(self.fixture());p=f[0]['owned_release'][0]['final']['stdout']
        f[4][(p['path'],p['sha256'])]='LoadState=loaded\n'
        with self.assertRaises(ValueError):self.call(f)

    def test_payload_projection_and_exact_original_capture_command_remain_bound(self):
        f=list(self.fixture());result=f[1]
        payload={k:result[k] for k in ('path','sha256','bytes')}
        payload['identity']={k:result['identity'][k] for k in ('device','inode','mode','uid','nlink')}
        f[0]['payload_result']=payload;self.call(f)
        for field,value in (('path','/synthetic/other/result.json'),('sha256','f'*64),('bytes',101)):
            bad=list(self.fixture());bad[0]['payload_result']=copy.deepcopy(payload);bad[0]['payload_result'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.call(bad)
        f=list(self.fixture());p=f[0]['full_original_archives'][1]['stdout']
        f[4][(p['path'],p['sha256'])]=f[4][(p['path'],p['sha256'])].replace(self.B.SELECTOR_SHA,'e'*64)
        with self.assertRaises(ValueError):self.call(f)
        f=list(self.fixture());f[2]['path']='/synthetic/unrelated-case.json'
        with self.assertRaises(ValueError):self.call(f)

    def test_finite_reversals_and_required_auditor_asset_closure(self):
        preservation=json.loads((HERE/'source-preservation.json').read_bytes())
        for item in preservation['source_reversals']:
            old=Path(item['base']['path']).read_bytes()
            self.assertEqual(hashlib.sha256(old).hexdigest(),item['base']['sha256'])
            value=(HERE/item['filename']).read_text()
            self.assertEqual(hashlib.sha256(value.encode()).hexdigest(),item['selected_sha256'])
            for change in reversed(item['replacements']):
                self.assertEqual(value.count(change['after']),1)
                value=value.replace(change['after'],change['before'],1)
            self.assertEqual(value.encode(),old)
        self.assertEqual(hashlib.sha256((HERE/'template-audit-source.py').read_bytes()).hexdigest(),
            '2576d4449b12d6b4a3b17898ab9938c6ff8c762829f61a29e3d510f73d585c21')
        self.assertTrue((HERE/'README.txt').read_text().startswith('UNSELECTED'))


if __name__=='__main__':unittest.main()
