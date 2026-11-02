"""Root-only synthetic contracts for selected frozen stop census methods; no imports of that source."""
import argparse, ast, copy, hashlib, json, os, stat, sys, types, unittest
from pathlib import Path


class Clock:
    def __init__(self):self.now=0
    def monotonic(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class Base:
    def __init__(self,shots):
        self.shots=shots;self.holds={};self.probe=None;self.owner={'pid':123};self.intents=[];self.released=[];self.events=[];self.api_calls=0;self.births={44:444};self.fail_event=False
    def candidates(self):
        assert 'HTTP'in self.holds or any(k.startswith('HTTP_CENSUS_')for k in self.holds),'raw census must be fenced'
        value=self.shots[0]
        if len(self.shots)>1:self.shots.pop(0)
        if isinstance(value,BaseException):raise value
        return copy.deepcopy(value)
    def hold(self,key,comm):
        assert comm=='Thread-1 (serve'and key not in self.holds and key not in self.intents
        self.intents.append(key);self.holds[key]={'key':key,'comm':comm}
    def release(self,key):self.released.append(key);del self.holds[key]
    def event(self,key,value):
        if self.fail_event:raise ValueError('synthetic publication failure')
        self.events.append((key,value))
    def api(self):
        self.api_calls+=1
        assert not self.holds,'API delegate must never run while fenced'
        return {'synthetic':True}


def row(tid,born=100,comm='Thread-9 (process_request_thread)'):
    return {tid:dict(tid=tid,starttime_ticks=born,comm=comm,wchan='poll_schedule_timeout')}


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(ARGS.source).absolute();raw=path.read_bytes();s=path.lstat()
        assert path.resolve()==path and stat.S_ISREG(s.st_mode)and stat.S_IMODE(s.st_mode)==0o444 and s.st_uid==os.getuid()and s.st_nlink==1 and len(raw)<128<<10
        assert hashlib.sha256(raw).hexdigest()==ARGS.source_sha256
        tree=ast.parse(raw);top={x.name:x for x in tree.body if isinstance(x,ast.FunctionDef)}
        selected=next(x for x in ast.walk(tree)if isinstance(x,ast.ClassDef)and x.name=='CurrentStop')
        methods=[x for x in selected.body if isinstance(x,ast.FunctionDef)and x.name in('candidates','api','uncached')]
        assert {x.name for x in methods}=={'candidates','api','uncached'}
        cls.clock=Clock();cls.old=types.SimpleNamespace(Stop=Base,birth=lambda pid,tid:None)
        cls.scope={'old':cls.old,'time':cls.clock,'Base':Base}
        body=[top['require'],top['settled_native_census'],ast.ClassDef(name='Selected',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])]
        exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path)+'::synthetic-census-only','exec'),cls.scope)
        cls.Selected=cls.scope['Selected'];cls.functions={x.name:hashlib.sha256(ast.dump(x,include_attributes=False).encode()).hexdigest()for x in[body[0],body[1],*methods]}
    def make(self,shots,probe=False):
        self.clock.now=0;h=self.Selected(shots)
        if probe:h.probe=object();h.census_probe={'tid':44,'starttime_ticks':444}
        self.old.birth=lambda pid,tid:h.births.get(tid)
        return h
    def clean(self,h):
        self.assertEqual(h.holds,{});self.assertEqual(h.intents,h.released);self.assertEqual(h.api_calls,0)
    def test_01_HTTP_workers_drain_without_name_exemption(self):
        h=self.make([row(90),row(91),{}]);self.assertEqual(h.candidates(),{});self.clean(h)
        self.assertGreater(self.clock.now,0);self.assertFalse(h.events[0][1]['HTTP_thread_name_exemptions'])
    def test_02_Timer_and_unknown_remain_blocking(self):
        for name in('Timer-90','Thread-90','unknown-native-producer'):
            with self.subTest(name=name):
                h=self.make([row(90,comm=name)])
                with self.assertRaisesRegex(ValueError,'did not drain'):h.candidates()
                self.clean(h);self.assertGreaterEqual(self.clock.now,10)
    def test_03_only_exact_owned_probe_birth_is_allowed(self):
        h=self.make([row(44,444,'Thread-44 (handle_client)')],True)
        self.assertEqual(set(h.candidates()),{44});self.clean(h)
        for snapshot in(row(45,444),row(44,445),row(44,444,'Timer-44')):
            h=self.make([snapshot],True)
            with self.assertRaises(ValueError):h.candidates()
            self.clean(h)
    def test_04_raw_census_error_releases_HTTP_hold(self):
        h=self.make([ValueError('synthetic census failure')])
        with self.assertRaisesRegex(ValueError,'census failure'):h.candidates()
        self.clean(h)
    def test_05_evidence_error_still_releases_HTTP_hold(self):
        h=self.make([{}]);h.fail_event=True
        with self.assertRaisesRegex(ValueError,'publication failure'):h.candidates()
        self.clean(h)
    def test_06_no_API_or_uncached_getter_inside_fence(self):
        h=self.make([{}]);h.hold('HTTP_CENSUS_9000','Thread-1 (serve')
        with self.assertRaisesRegex(ValueError,'No API'):h.api()
        with self.assertRaisesRegex(ValueError,'No uncached'):h.uncached('/api/now',100)
        h.release('HTTP_CENSUS_9000');self.clean(h)
    def test_07_unique_intents_and_permanent_HTTP_scope(self):
        h=self.make([{}]);h.candidates();h.candidates();self.clean(h)
        self.assertEqual(h.intents,['HTTP_CENSUS_0001','HTTP_CENSUS_0002'])
        h=self.make([row(90,comm='Timer-90')]);h.holds['HTTP']={'owned':True}
        self.assertEqual(set(h.candidates()),{90});self.assertEqual(h.intents,[]);self.assertIn('HTTP',h.holds)
    def test_08_birth_veto_and_no_nested_HTTP_fence(self):
        h=self.make([{}],True);h.births[44]=445
        with self.assertRaisesRegex(ValueError,'birth changed'):h.candidates()
        self.clean(h)
        for births in([444,445],[444,444,445]):
            with self.subTest(births=births):
                h=self.make([row(44,444,'Thread-44 (handle_client)')],True);sequence=iter(births)
                self.old.birth=lambda pid,tid:next(sequence)
                with self.assertRaisesRegex(ValueError,'birth changed'):h.candidates()
                self.clean(h)
        h=self.make([{}]);h.holds['HTTP_CENSUS_EXISTING']={}
        with self.assertRaisesRegex(ValueError,'Nested'):h.candidates()
        self.assertEqual(h.intents,[]);self.assertIn('HTTP_CENSUS_EXISTING',h.holds)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--source-sha256',required=True);p.add_argument('--report',type=Path,required=True);ARGS=p.parse_args()
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    report=dict(schema='robotron-synthetic-HTTP-fenced-census-contract-report-v1',status='PASS'if result.wasSuccessful()else'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),selected_source=dict(path=ARGS.source,sha256=ARGS.source_sha256),actual_function_AST=Contracts.functions if hasattr(Contracts,'functions')else{},real_proc_API_cgroup_or_stop_actions=False)
    with ARGS.report.open('x')as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    raise SystemExit(0 if result.wasSuccessful()else 1)
