"""Tiny fixtures only: no original raw corpus, models, units or processes."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_fixture_reuse', HERE/'closed_metadata_readiness_reuse_v1.py')
reuse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse)


class Fixture:
    def __init__(self, root):
        self.root, self.calls, self.events = root, [], []
        self.pins = {}
        static = dict(pid=1, starttime_ticks=2, parent_pid=3, cgroup='owned', command=['literal'],
                      environment={'role':'fixed'}, affinity=[0], uids=[1], executable={'path':'pinned'})
        self.binding = dict(inputs=['247-fixed-source-identities'], slot_eval={'0':False},
            owners={k:dict(unit=k, invocation=k, process=copy.deepcopy(static)) for k in ('trainer','fleet')},
            exposure={k:dict(process_id=1, instance_monotonic_ns=2, epoch=1, epoch_reason='fixed') for k in ('optimizer','replay')})
        # Deliberately non-JSON: only actual previous semantic proof permits reuse.
        self.raws = [self.put('raw'+str(n), b'previously verified raw bytes') for n in range(2)]
        outcome = self.put('outcome', dict(samples=self.raws))
        case = self.put('case', self.binding)
        worker = self.put('worker', dict(case=case))
        life = self.put('life', dict(worker_job=worker, outcome=outcome))
        reviewer = self.put('reviewer', b'fixed reviewer source')
        self.result = dict(status='PASS',lifecycle=life,original_sources={'source':'fixed'},full_main_input_count=247)
        raw_review = self.put('review', self.result)
        self.subjects = [(leg,dict(leg=leg,literal='exact')) for leg in ('R1','C1','R2','C2')]
        self.context = dict(family=dict(native_launch_qualified=True, main_domain_hot_review=raw_review,
            round_observer_reviewer=reviewer, main_observer={'source':'fixed'}),main_binding=copy.deepcopy(self.binding))
        self.instance = reuse.ClosedMetadataReadiness.__new__(reuse.ClosedMetadataReadiness)
        self.instance.h = self
        self.instance.phase = lambda name,**data:self.events.append((name,data))
        self.instance.a = dict(raw_review=raw_review,raw_reviewer=reviewer,lifecycle=life,outcome=outcome)
        self.instance.raw, self.instance.samples = self.result, self.raws
        self.instance.subjects = self.subjects
        self.instance.counts = dict(semantics_reused_from_closed_metadata=0,raw_full_integrity_passes=0)

    def put(self, name, value):
        p = self.root/name
        b = value if isinstance(value,bytes) else json.dumps(value,sort_keys=True).encode()
        p.write_bytes(b)
        pin = dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=self.identity(p))
        self.pins[name] = pin
        return pin

    @staticmethod
    def identity(p):
        s=p.stat()
        return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                    ctime_ns=s.st_ctime_ns,mode=s.st_mode,uid=s.st_uid,nlink=s.st_nlink)

    def checked(self, pin):
        p=Path(pin['path']);self.calls.append(str(p))
        if self.identity(p)!=pin['identity'] or hashlib.sha256(p.read_bytes()).hexdigest()!=pin['sha256']:
            raise ValueError('Actual immutable raw/source identity or SHA differs')
        return p


class Tests(unittest.TestCase):
    def test_four_exact_subjects_each_freshly_hash_every_raw(self):
        with tempfile.TemporaryDirectory() as td:
            f=Fixture(Path(td))
            for _,subject in f.subjects:
                result=f.instance.validate_launch(subject,copy.deepcopy(f.context),f)
                self.assertEqual(result,f.result)
                result['status']='caller mutation'
            self.assertEqual(f.instance.counts,dict(semantics_reused_from_closed_metadata=4,raw_full_integrity_passes=4))
            for pin in f.raws:self.assertEqual(f.calls.count(pin['path']),4)
            self.assertEqual(f.result['status'],'PASS')

    def test_actual_subject_owner_epoch_role_and_source_negatives(self):
        with tempfile.TemporaryDirectory() as td:
            f=Fixture(Path(td))
            for damage in ('subject','owner','epoch','role','source','engineering'):
                subject=copy.deepcopy(f.subjects[0][1]);context=copy.deepcopy(f.context)
                if damage=='subject':subject['literal']='foreign'
                elif damage=='owner':context['main_binding']['owners']['fleet']['process']['starttime_ticks']+=1
                elif damage=='epoch':context['main_binding']['exposure']['replay']['epoch']+=1
                elif damage=='role':context['main_binding']['slot_eval']['0']=True
                elif damage=='source':context['family']['main_observer']={'source':'foreign'}
                else:context['family']['native_launch_qualified']=False
                with self.subTest(damage=damage),self.assertRaises(ValueError):f.instance.validate_launch(subject,context,f)
            self.assertEqual(f.instance.counts,dict(semantics_reused_from_closed_metadata=0,raw_full_integrity_passes=0))

    def test_raw_mutation_and_unqualified_authority_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f=Fixture(Path(td));Path(f.raws[0]['path']).write_bytes(b'changed raw bytes')
            with self.assertRaises(ValueError):f.instance.validate_launch(f.subjects[0][1],f.context,f)
            authority=f.put('bad-authority',dict(schema='robotron-closed-metadata-and-raw-readiness-predicate-reuse-authority-v1',metadata_closeout={'sha256':'unqualified'}))
            with self.assertRaisesRegex(ValueError,'Selected original reuse source differs'):
                reuse.ClosedMetadataReadiness(dict(closed_metadata_readiness_authority=authority),f,lambda *a,**kw:None)

    def test_actual_archive_callback_adapts_keyword_only_reader(self):
        tree=ast.parse((HERE/'closed_metadata_readiness_reuse_v1.py').read_text())
        owner=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        init=next(n for n in owner.body if isinstance(n,ast.FunctionDef)and n.name=='__init__')
        callback=next(n for n in init.body if isinstance(n,ast.FunctionDef)and n.name=='read_archive')
        calls=[]
        def keyword_only_reader(pin,*,as_json=True):
            calls.append((pin,as_json));return b'actual bytes' if not as_json else {'actual':'json'}
        env={'immutable':types.SimpleNamespace(read_pin=keyword_only_reader)}
        exec(compile(ast.Module(body=[callback],type_ignores=[]),'actual-callback','exec'),env)
        self.assertEqual(env['read_archive']('pin',False),b'actual bytes')
        self.assertEqual(env['read_archive']('pin'),{'actual':'json'})
        self.assertEqual(calls,[('pin',False),('pin',True)])


if __name__=='__main__':unittest.main()
