"""UNEXECUTED stdlib closed-metadata checks; no numerical/model/runtime work.

The actual immutable native0/reportPASS/wrapper1/FAIL tuple and its six archive
commands are used. Only future root review/publication JSON is an
in-memory fixture; no factual original is edited or relabelled on disk.
"""
import copy, hashlib, importlib.util, json, os, stat
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
RUN=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
D=RUN/'LR25-continuation-candidate-CPU-original01-root-execution-20261018'
BINDER_SHA='1f025fa31edbe280bf6c03aa78acd64c4fab4967b53cc0f821ae04f8589a74e5'
HELPER_SHA='755b2818db1c3a7dbfb33d005b17afb3791e5080ad23198ac422cc3e0360bb34'
PEER=RUN/'LR25-continuation-candidate-CPU-independent-saved-review-20261018/review-receipt.json'
PEER_SHA='2c8d13cc587c40b927f3776bb77526ecaf7480a7b098af40e07c749b7550c370'
RUNTIME_PEER=RUN/'LR25-continuation-candidate-CPU-launcher-format-and-lifecycle-independent-saved-review-20261018/review-receipt.json'
RUNTIME_PEER_SHA='fb04f42d89a018c61c872bb0fe290b0a16589af3bfcb0980d4a0a66af41374c9'


def pin(path):
    path=Path(path)
    if path.suffix in ('.pt','.pth','.npy','.npz'):raise AssertionError('No model/tensor referents')
    before=path.lstat();raw=path.read_bytes();after=path.lstat()
    def identity(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    if not(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.getuid() and
        stat.S_IMODE(before.st_mode)==0o444 and len(raw)<=4<<20 and identity(before)==identity(after)):
        raise AssertionError('Closed metadata/source changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def module(filename,sha,name):
    path=HERE/filename
    if pin(path)['sha256']!=sha:raise AssertionError('Selected metadata source changed')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value);return value


def synthetic(value,name):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
    return dict(path='/synthetic/unpublished/'+name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
        identity=dict(device=1,inode=1,bytes=len(raw),mtime_ns=1,ctime_ns=1,mode='0o444',uid=1001,nlink=1))


class KnownCPUMetadataReviewContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.B=module('quality_bindings.py',BINDER_SHA,'_known_CPU_metadata_binding_guard')
        cls.H=module('cpu_metadata_review.py',HELPER_SHA,'_known_CPU_metadata_review_guard')
        cls.pins={key:pin(path) for key,(path,sha) in cls.H.KNOWN.items()}
        for key,(path,sha) in cls.H.KNOWN.items():
            if cls.pins[key]['sha256']!=sha:raise AssertionError('Authentic known attempt changed: '+key)
        cls.original=cls.B.read(cls.pins['original_execution']);cls.release=cls.B.read(cls.pins['original_release'])
        cls.job=cls.B.read(cls.pins['job']);cls.report=cls.B.read(cls.pins['report']);cls.completion=cls.B.read(cls.pins['completion'])
        cls.numeric_peer_pin=pin(PEER)
        if cls.numeric_peer_pin['sha256']!=PEER_SHA:raise AssertionError('Closed numerical fact peer changed')
        cls.numeric_peer=cls.B.read(cls.numeric_peer_pin)
        cls.runtime_peer_pin=pin(RUNTIME_PEER)
        if cls.runtime_peer_pin['sha256']!=RUNTIME_PEER_SHA:raise AssertionError('Closed launcher fact peer changed')
        cls.runtime_peer=cls.B.read(cls.runtime_peer_pin)

    def fixture(self):
        H=self.H;mapping={};review=dict(schema=H.SCHEMA,status=H.STATUS,**copy.deepcopy(self.pins),validator_source=pin(HERE/'cpu_metadata_review.py'),
            original_wrapper=dict(exit_code=1,release_status='FAIL',semantic_error='AssertionError()',preserved=True),
            job_file_identity_join=dict(report_job_file=copy.deepcopy(self.report['job_file']),root_job_file=copy.deepcopy(self.pins['job']),exact=True),
            checks=dict(no_numeric_rerun=True,no_model_or_replay_reads=True,original_records_unchanged=True,
                root_review_does_not_override_gates=True,known_first_bad_assertion_only=True),independent_peers=[])
        # Both published fact peers are authentic, with explicit authored-code exclusions.
        for role,receipt in (('numerical_and_original_lifecycle',self.numeric_peer_pin),('known_launcher_metadata_failure',self.runtime_peer_pin)):
            review['independent_peers'].append(dict(role=role,receipt=receipt,
                covered_artifact_sha256={k:self.pins[k]['sha256'] for k in H.ROLES[role]},authorship_scope=H.SCOPES[role]))
        rp=synthetic(review,'future-root-review.json');mapping[rp['path']]=(rp,review)
        execution=dict(copy.deepcopy(self.original),metadata_review=rp)
        overrides={}
        def reader(p):
            if p['path'] in overrides:return copy.deepcopy(overrides[p['path']])
            if p['path'] in mapping:
                expected,value=mapping[p['path']]
                if p!=expected:raise AssertionError('Synthetic review PIN tampered')
                return copy.deepcopy(value)
            return self.B.read(p)
        def repin():
            value=synthetic(review,'future-root-review.json');mapping[value['path']]=(value,review);execution['metadata_review']=value
        return execution,review,reader,overrides,repin

    def check(self,f):
        execution,review,reader,overrides,repin=f
        return self.B.check_CPU_release(execution,self.pins['job'],self.pins['report'],self.pins['completion'],self.completion,
            reader,self.B.archive_text,lambda p:self.B.archived_bytes(p,allow_empty=True))

    def test_actual_closed_full_chain_and_flat_identity_join_preserve_original_failure(self):
        f=self.fixture();before=copy.deepcopy(self.original);release_before=copy.deepcopy(self.release)
        self.check(f)
        self.assertEqual(self.original,before);self.assertEqual(self.release,release_before)
        self.assertEqual(self.release['status'],'FAIL');self.assertEqual(self.release['semantic_error'],'AssertionError()')
        self.assertEqual(self.completion['exit_code'],0);self.assertEqual(self.report['status'],'PASS')
        self.assertNotEqual(self.report['job_file'],self.pins['job'])
        self.assertEqual(self.report['job_file'],dict(path=self.pins['job']['path'],sha256=self.pins['job']['sha256'],**self.pins['job']['identity']))

    def test_absent_review_unknown_original_source_failure_and_peer_scope_refuse(self):
        f=self.fixture();del f[0]['metadata_review']
        with self.assertRaises(ValueError):self.check(f)
        for key in ('original_execution','original_release','report','job','completion','launcher_source'):
            f=self.fixture();f[1][key]['sha256']='f'*64;f[4]()
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(f)
        f=self.fixture();f[1]['original_wrapper']['exit_code']=0;f[4]()
        with self.assertRaises(ValueError):self.check(f)
        f=self.fixture();f[1]['independent_peers'][0]['authorship_scope']='independent numerical implementation';f[4]()
        with self.assertRaises(ValueError):self.check(f)
        f=self.fixture();f[1]['independent_peers'][0]['covered_artifact_sha256'].pop('report');f[4]()
        with self.assertRaises(ValueError):self.check(f)

    def test_flat_full_identity_and_exact_augmented_copy_are_not_normalized(self):
        f=self.fixture();f[0]['unrelated_extra_field']=True
        with self.assertRaises(ValueError):self.check(f)
        f=self.fixture();f[0]['archived_before_release']=1
        with self.assertRaises(ValueError):self.check(f)
        f=self.fixture();f[1]['job_file_identity_join']['root_job_file']['identity']['inode']+=1;f[4]()
        with self.assertRaises(ValueError):self.check(f)
        f=self.fixture();f[1]['job_file_identity_join']['report_job_file']=copy.deepcopy(self.pins['job']);f[4]()
        with self.assertRaises(ValueError):self.check(f)

    def test_root_review_does_not_override_real_numerical_or_native_gates(self):
        for key,value in (('finite',dict(tensors=442)),('adam_group',dict(self.report['adam_group'],lr=2.5e-5)),('status','FAIL')):
            f=self.fixture();bad=copy.deepcopy(self.report);bad[key]=value;f[3][self.pins['report']['path']]=bad
            with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):self.check(f)
        f=self.fixture();bad=copy.deepcopy(self.release);bad['original_exit']=1;f[3][self.pins['original_release']['path']]=bad
        with self.assertRaises(ValueError):self.check(f)
        f=self.fixture();bad=copy.deepcopy(self.release);bad['semantic_error']='unrelated numerical fault';f[3][self.pins['original_release']['path']]=bad
        with self.assertRaises(ValueError):self.check(f)

    def test_grouped_six_command_exit_and_stop_chronology_still_gate_review(self):
        for group in ('service_show','service_cat','service_journal','timer_show','timer_cat','timer_journal'):
            f=self.fixture();archive=self.B.read(self.release['original_terminal_archive']);p=archive['full_original_archives'][group]['command']
            bad=self.B.read(p);bad['returncode']=1;f[3][p['path']]=bad
            with self.subTest(group=group),self.assertRaises(ValueError):self.check(f)
        for change in ('exit','time'):
            f=self.fixture();p=self.release['owned_release'][0]['stop'];bad=self.B.read(p)
            if change=='exit':bad['returncode']=5
            else:bad['started_unix_s']=0
            f[3][p['path']]=bad
            with self.subTest(change=change),self.assertRaises(ValueError):self.check(f)

    def test_existing_healthy_PASS_short_circuits_review_and_source_delta_reverses(self):
        f=self.fixture();execution=copy.deepcopy(self.original);healthy=copy.deepcopy(self.release)
        healthy.update(status='PASS',semantic_error=None)
        f[3][self.pins['original_release']['path']]=healthy
        with patch.object(self.B,'verified_known_CPU_metadata_review',side_effect=AssertionError('Healthy branch must remain unchanged')):
            self.B.check_CPU_release(execution,self.pins['job'],self.pins['report'],self.pins['completion'],self.completion,
                f[2],self.B.archive_text,lambda p:self.B.archived_bytes(p,allow_empty=True))
        preservation=json.loads((HERE/'source-preservation.json').read_bytes())
        for item in preservation['source_reversals']:
            old=Path(item['base']['path']).read_bytes();self.assertEqual(hashlib.sha256(old).hexdigest(),item['base']['sha256'])
            value=(HERE/item['filename']).read_text()
            for change in reversed(item['replacements']):
                self.assertEqual(value.count(change['after']),1);value=value.replace(change['after'],change['before'],1)
            self.assertEqual(value.encode(),old)
        self.assertEqual(hashlib.sha256((HERE/'template-audit-source.py').read_bytes()).hexdigest(),'2576d4449b12d6b4a3b17898ab9938c6ff8c762829f61a29e3d510f73d585c21')


if __name__=='__main__':unittest.main()
