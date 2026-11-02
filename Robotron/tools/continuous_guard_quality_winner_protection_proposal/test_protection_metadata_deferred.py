"""UNEXECUTED: finite injected metadata tests, not a publication/quality run.

At future root execution only, authenticate three local source/data files,
extract actual loader/provenance/review functions and load the real pure f157
checker. Every target file/source/import/profile/time/scoring dependency is an
explicit strict fake. No publish/copy action or actual checkpoint is accessed.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import types
import unittest

DIRECTORY = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/continuous_guard_quality_winner_protection_proposal')
SOURCE = DIRECTORY/'protect_quality_winner_reviewed2.py'
CHECKER = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/continuous_guard_same_lr25_continuation_proposal/effective_provenance.py')
DATA = DIRECTORY/'closed-metadata-fixture-inputs.json'
ALLOW = {
    SOURCE: ('b68e071fbb01dba50e905ea96968e164913b04b1453c1ffe2b9cec719a47e730',16572),
    CHECKER: ('f157895d90707fc725bda2381c9422c6e9ac22ab924597551d0d4d1f2d973556',18564),
    DATA: ('5458be5daf2c1280acf90dd86df0a43a3d5c4d16f42d518d4aaa2059087ec901',314827),
}


def sealed_input(path):
    if path not in ALLOW:
        raise AssertionError('Unknown bootstrap path')
    digest,size = ALLOW[path]
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before = os.fstat(stream.fileno()); raw = stream.read(size+1)
        def same(value):
            return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,
                    value.st_ctime_ns,value.st_mode,value.st_uid,value.st_nlink)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 1001
                or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o444
                or same(before) != same(os.fstat(stream.fileno())) or same(before) != same(path.lstat())
                or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest):
            raise AssertionError('Exact closed source/data changed')
    return raw


class Harness:
    def __init__(self, inputs, target_nodes, checker):
        self.inputs = copy.deepcopy(inputs); self.real_checker = checker
        self.unexpected = []; self.calls = []; self.source_calls = []; self.loaded = []
        self.source_override = None; self.loader_available = True; self.module_path_override = None
        self.modules = {}; self.directory = '/synthetic-closed-protection-campaign'
        self.pins = copy.deepcopy(inputs['source_pins'])
        self.by_source = {p['path']:p for p in self.pins}
        self.profile_pin = copy.deepcopy(inputs['provenance']['native_profile'])
        self.profile = copy.deepcopy(inputs['native_profile'])
        self.plan = copy.deepcopy(inputs['actual_plan'])
        self.plan['output_directory'] = self.directory
        for role,entry in self.plan['checkpoints'].items():
            entry['snapshot'] = self.directory+'/checkpoints/'+role+'.pt'
        self.receipts = []
        for spec in self.plan['legs']:
            index,role = spec['index'],spec['role']
            legdir = self.directory+'/%02d-%s' % (index,role)
            spec['receipt_path'] = legdir+'/receipt.json'
            spec['job']['directory'] = legdir
            spec['job']['checkpoint'] = self.plan['checkpoints'][role]['snapshot']
            # Only these runtime envelopes and terminal states are synthetic.
            # No game row, score, status or winner from the running campaign is read.
            local = {key:index*100+offset for offset,key in enumerate(
                ('module','function','code','globals','RL_CONFIG'),1)}
            effective = dict(selection=copy.deepcopy(self.plan['effective_implementation']),
                runtime_code_sha256=self.profile['runtime_code_sha256'],
                python_version=self.profile['python_version'],python_cache_tag=self.profile['python_cache_tag'],
                verified_before_serving=True,verified_after_cleanup=True,verification_error=None,
                verification_count=3,local_identity_before=local,local_identity_after=copy.deepcopy(local))
            self.receipts.append(dict(effective_implementation=effective))
        self.report = dict(outcome='qualified_improvement',qualified_improvement=True,
            candidate_checks=[dict(index=2,mean_pass=True,median_pass=True),
                              dict(index=4,mean_pass=True,median_pass=True)],
            pooled_reference=dict(count=100,mean=100.0,median=100.0))
        self.status = dict(state='finished',outcome=self.report['outcome'],legs=[
            dict(index=s['index'],role=s['role'],state='finished',returncode=0) for s in self.plan['legs']])
        self.summary = dict(self.report,stop_signal=None)
        self.sync_files()
        harness = self
        class ClosedPath:
            def __init__(self,value): self.value = str(value)
            def __str__(self): return self.value
            def __truediv__(self,other): return ClosedPath(str(PurePosixPath(self.value)/str(other)))
            def __eq__(self,other): return str(self) == str(other)
            @property
            def parent(self): return ClosedPath(str(PurePosixPath(self.value).parent))
            def resolve(self,strict=False):
                if self.value != harness.directory and self.value not in harness.by_source:
                    harness.fail('resolve',self.value)
                return self
            def read_bytes(self): return harness.read_file(self.value)
        self.Path = ClosedPath
        def fake_now(zone):
            if zone != 'synthetic-UTC': self.fail('timezone',zone)
            return types.SimpleNamespace(isoformat=lambda: '2000-01-01T00:00:00+00:00')
        self.namespace = dict(__name__='_protection_metadata_fixture',Path=ClosedPath,
            hashlib=hashlib,json=json,datetime=types.SimpleNamespace(now=fake_now),
            timezone=types.SimpleNamespace(utc='synthetic-UTC'),
            source_record=self.source_record,sys=types.SimpleNamespace(modules=self.modules),
            importlib=types.SimpleNamespace(util=types.SimpleNamespace(
                spec_from_file_location=self.spec,module_from_spec=self.module)),
            campaign=types.SimpleNamespace(ORDER=('reference','candidate','reference','candidate'),
                evaluator=types.SimpleNamespace(sha256=lambda path: hashlib.sha256(self.read_file(str(path))).hexdigest()),
                check_precommit=self.precommit,assess_campaign=self.assess),
            CAMPAIGN_PIN=self.pins[0],CHECKER_PIN=self.pins[1],READER_PIN=self.pins[2],
            SUPPORT_PINS={p['path']:p for p in self.pins[3:]},
            METADATA=types.SimpleNamespace(read=self.metadata),
            CHECKER=types.SimpleNamespace(CLOSED={'native_profile':self.profile_pin},
                check_selection=self.selection,check_runtime=self.runtime))
        exec(compile(ast.Module(body=target_nodes,type_ignores=[]),str(SOURCE),'exec'),self.namespace)

    def fail(self,*value):
        self.unexpected.append(value)
        raise AssertionError('Unplanned target dependency; no host fallback: '+repr(value))

    def source_record(self,path,expected,*,expected_mode=0o444):
        key = str(path)
        if key not in self.by_source: self.fail('source',key)
        pin = self.by_source[key]
        if pin['sha256'] != expected or int(pin['identity']['mode'],8) != expected_mode:
            self.fail('source expected identity/mode',key,expected,expected_mode)
        self.source_calls.append((key,expected_mode))
        result = copy.deepcopy(pin)
        if self.source_override is not None:
            result = self.source_override(result,len(self.source_calls))
        return result

    def metadata(self,pin):
        if pin != self.profile_pin: self.fail('metadata',pin)
        return copy.deepcopy(self.profile)

    def guard_source(self,pin):
        selection = self.inputs['actual_plan']['effective_implementation']
        exact = [selection[k] for k in ('canonical_base_socket','guard_manifest','installer',
                                       'effective_helper','companion_evaluator')]
        if pin not in exact: self.fail('guard source',pin)
        return pin

    def selection(self,selection,reader):
        return self.real_checker.check_selection(selection,reader,source_reader=self.guard_source)

    def runtime(self,effective,selection,reader):
        return self.real_checker.check_runtime(effective,selection,reader,source_reader=self.guard_source)

    def spec(self,name,path):
        if str(path) not in self.by_source: self.fail('loader path',str(path))
        if not self.loader_available: return None
        def execute(module): self.loaded.append((name,str(path)))
        return types.SimpleNamespace(name=name,path=str(path),loader=types.SimpleNamespace(exec_module=execute))

    def module(self,spec):
        return types.SimpleNamespace(__file__=self.module_path_override or spec.path)

    def read_file(self,path):
        if path not in self.files: self.fail('file',path)
        return self.files[path]

    def precommit(self,plan):
        if plan != self.plan: self.fail('precommit wrong plan')
        self.calls.append('precommit')

    def assess(self,plan,records):
        if plan != self.plan or records != self.status['legs']: self.fail('assessment inputs')
        self.calls.append('assess')
        return copy.deepcopy(self.report)

    def sync_files(self):
        encode = lambda value: json.dumps(value,sort_keys=True,allow_nan=False).encode()
        plan_raw = encode(self.plan); self.plan_sha = hashlib.sha256(plan_raw).hexdigest()
        for value in (self.status,self.summary):
            value.update(plan_path=self.directory+'/plan.json',plan_sha256=self.plan_sha)
        self.files = {self.directory+'/plan.json':plan_raw,
            self.directory+'/status.json':encode(self.status),self.directory+'/summary.json':encode(self.summary)}
        for spec,receipt in zip(self.plan['legs'],self.receipts):
            self.files[spec['receipt_path']] = encode(receipt)

    def evidence(self):
        return {path:hashlib.sha256(raw).hexdigest() for path,raw in self.files.items()}

    def provenance(self):
        return self.namespace['guard_provenance'](self.plan,self.plan['legs'],self.evidence())


class ProtectionMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = sealed_input(SOURCE)
        selected = {'load_checked','guard_provenance','digest','review'}
        cls.nodes = [node for node in ast.parse(raw,str(SOURCE)).body
                     if isinstance(node,ast.FunctionDef) and node.name in selected]
        if {node.name for node in cls.nodes} != selected or len(cls.nodes) != 4:
            raise AssertionError('Actual selected function set differs')
        cls.inputs = json.loads(sealed_input(DATA))
        cls.checker = types.ModuleType('_real_f157_checker_fixture')
        cls.checker.__file__ = str(CHECKER)
        exec(compile(sealed_input(CHECKER),str(CHECKER),'exec'),cls.checker.__dict__)

    def setUp(self): self.environments = []

    def fresh(self):
        harness = Harness(self.inputs,self.nodes,self.checker)
        self.environments.append(harness)
        return harness

    def tearDown(self):
        # These assertions cannot be swallowed by expected target ValueErrors.
        for harness in self.environments: self.assertEqual(harness.unexpected,[])

    def test_actual_loader_has_one_exact_module_and_no_fallback(self):
        h = self.fresh(); pin = h.pins[0]; path = h.Path(pin['path'])
        module,actual = h.namespace['load_checked']('_one_selected',path,pin['sha256'])
        self.assertEqual(actual,pin)
        self.assertIs(h.modules['_one_selected'],module)
        self.assertEqual(h.loaded,[('_one_selected',pin['path'])])
        self.assertEqual(h.source_calls,[(pin['path'],0o444)]*2)
        with self.assertRaises(ValueError): h.namespace['load_checked']('_one_selected',path,pin['sha256'])
        self.assertEqual(len(h.loaded),1)

    def test_loader_missing_or_changed_dependency_refuses_without_retry(self):
        h = self.fresh();pin=h.pins[0];h.loader_available=False
        with self.assertRaises(ValueError): h.namespace['load_checked']('_missing',h.Path(pin['path']),pin['sha256'])
        self.assertEqual(h.loaded,[])
        h = self.fresh();pin=h.pins[0]
        def change_after(pin,count):
            if count == 2: pin['identity']['inode'] += 1
            return pin
        h.source_override=change_after
        with self.assertRaises(ValueError): h.namespace['load_checked']('_changed',h.Path(pin['path']),pin['sha256'])
        self.assertEqual(len(h.loaded),1)
        h = self.fresh();pin=h.pins[0];h.module_path_override=h.pins[1]['path']
        with self.assertRaises(ValueError): h.namespace['load_checked']('_wrong_path',h.Path(pin['path']),pin['sha256'])
        self.assertEqual(len(h.loaded),1)

    def test_four_original_runtime_joins_use_real_checker_and_actual_modes(self):
        h=self.fresh();result=h.provenance()
        self.assertEqual(result['effective_implementation'],h.plan['effective_implementation'])
        stable=result['stable_effective_implementation']
        self.assertEqual(stable['runtime_code_sha256'],'c11562ba189bdadc1ce3f70f0e3ecdaa92d4f2201dbb239e3a129f95564d1ef4')
        self.assertEqual(stable['python_version'],h.profile['python_version'])
        self.assertEqual(stable['python_cache_tag'],h.profile['python_cache_tag'])
        self.assertIs(result['canonical_source_hashes_are_base_provenance'],True)
        rows=result['effective_implementation_receipts']
        self.assertEqual([r['index'] for r in rows],[1,2,3,4])
        self.assertEqual([r['role'] for r in rows],['reference','candidate','reference','candidate'])
        self.assertEqual([r['receipt_sha256'] for r in rows],
            [h.evidence()[s['receipt_path']] for s in h.plan['legs']])
        self.assertEqual(h.source_calls,[(p['path'],int(p['identity']['mode'],8)) for p in h.pins])
        self.assertEqual([mode for _,mode in h.source_calls],[0o444,0o444,0o444,0o664,0o664])

    def test_wrong_native_profile_or_receipt_provenance_is_rejected(self):
        mutations=[
            lambda h: h.receipts[1]['effective_implementation'].__setitem__('runtime_code_sha256','f'*64),
            lambda h: h.receipts[2]['effective_implementation'].__setitem__('python_cache_tag','foreign'),
            lambda h: h.receipts[3]['effective_implementation'].__setitem__('verified_after_cleanup',False),
            lambda h: h.receipts[0]['effective_implementation'].__setitem__('verification_count',1),
            lambda h: h.receipts[0]['effective_implementation']['local_identity_after'].__setitem__('code',999),
            lambda h: h.receipts[0]['effective_implementation']['selection'].__setitem__('function','foreign'),
            lambda h: h.profile.__setitem__('runtime_code_sha256','f'*64),
        ]
        for index,mutate in enumerate(mutations):
            with self.subTest(case=index):
                h=self.fresh();mutate(h);h.sync_files()
                with self.assertRaises(ValueError): h.provenance()
        h=self.fresh();evidence=h.evidence();evidence[h.plan['legs'][0]['receipt_path']]='f'*64
        with self.assertRaises(ValueError): h.namespace['guard_provenance'](h.plan,h.plan['legs'],evidence)
        h=self.fresh()
        with self.assertRaises(ValueError): h.namespace['guard_provenance'](h.plan,h.plan['legs'][:3],h.evidence())

    def test_real_review_preserves_assessment_and_returns_effective_metadata(self):
        h=self.fresh();result=h.namespace['review'](h.directory)
        self.assertEqual(h.calls,['precommit','assess','precommit'])
        self.assertEqual(result['assessment'],h.report)
        self.assertEqual(result['plan_sha256'],h.plan_sha)
        self.assertEqual(result['evaluator_source_hashes'],h.plan['evaluator_source_hashes'])
        self.assertEqual(result['execution_source_hashes'],h.plan['execution_source_hashes'])
        self.assertEqual(result['effective_implementation'],h.plan['effective_implementation'])
        self.assertEqual(len(result['effective_implementation_receipts']),4)
        self.assertEqual(result['effective_implementation_provenance']['native_profile'],h.profile_pin)
        h=self.fresh();h.summary['qualified_improvement']=False;h.sync_files()
        with self.assertRaises(ValueError): h.namespace['review'](h.directory)


if __name__ == '__main__':
    unittest.main()
