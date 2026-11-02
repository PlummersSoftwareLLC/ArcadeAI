"""Root-only port-gate contracts with FAKE sockets; no real bind/listen/connect."""
import argparse, ast, copy, errno, hashlib, json, os, stat, types, unittest
from pathlib import Path


class Clock:
    def __init__(self):self.value=0
    def now(self):return self.value
    def sleep(self,seconds):self.value+=seconds


class FakeNetwork:
    def __init__(self,ports,*,busy_attempts=(),busy_port=None,error=None,close_error=False,slow=False):
        self.ports=ports;self.busy_attempts=busy_attempts;self.busy_port=ports[-1]if busy_port is None else busy_port
        self.error=error;self.close_error=close_error;self.slow=slow;self.tries=0;self.created=[];self.bound=set();self.peak=0;self.clock=None
    def factory(self,family,kind):
        assert(family,kind)==(2,1)
        network=self
        class Probe:
            def __init__(self):self.options=[];self.address=None;self.close_called=False
            def setsockopt(self,*value):self.options.append(value)
            def bind(self,address):
                assert address[0]=='127.0.0.1'and address[1]in network.ports
                assert self.options==[(1,2,0)],'SO_REUSEADDR0 must precede every bind'
                self.address=address
                if address[1]==network.ports[0]:
                    assert network.bound==set(),'Every prior attempt must close all successful probes'
                    network.tries+=1
                if network.error is not None and address[1]==network.busy_port:raise network.error
                if (network.busy_attempts=='always'or network.tries in network.busy_attempts)and address[1]==network.busy_port:
                    raise OSError(errno.EADDRINUSE,'synthetic busy')
                assert address[1]not in network.bound;network.bound.add(address[1]);network.peak=max(network.peak,len(network.bound))
                if network.slow and address[1]==network.ports[-1]:network.clock.value=91
            def close(self):
                assert not self.close_called;self.close_called=True
                if self.address is not None:network.bound.discard(self.address[1])
                if network.close_error and self is network.created[0]:raise OSError(errno.EADDRINUSE,'synthetic close error, not a bind retry')
            def listen(self,*args):raise AssertionError('No listen is allowed')
            def connect(self,*args):raise AssertionError('No connect is allowed')
        probe=Probe();self.created.append(probe);return probe


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(ARGS.source).absolute();a=path.lstat();assert path.resolve()==path and stat.S_ISREG(a.st_mode)and stat.S_IMODE(a.st_mode)==0o444 and a.st_uid==os.getuid()and a.st_nlink==1 and 0<a.st_size<128<<10
        raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ARGS.source_sha256
        tree=ast.parse(raw);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='wait_for_job_ports')
        def forbidden(*args,**kwargs):raise AssertionError('A real socket/clock/sleep was not supplied; refuse all runtime operations')
        scope=dict(errno=errno,socket=types.SimpleNamespace(AF_INET=2,SOCK_STREAM=1,SOL_SOCKET=1,SO_REUSEADDR=2,socket=forbidden),time=types.SimpleNamespace(monotonic=forbidden,sleep=forbidden))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path)+'::FAKE-sockets-only','exec'),scope)
        cls.gate=staticmethod(scope['wait_for_job_ports']);cls.function_AST=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    def fixture(self,**settings):
        # These are fake-only values; NEVER target the live19998/20000 ports.
        slots=list(range(4096,4128));job=dict(actor_slots=slots,origin_port=33000,proxy_ports={str(slot):33001+i for i,slot in enumerate(slots)})
        ports=[job['origin_port'],*job['proxy_ports'].values()];clock=Clock();net=FakeNetwork(ports,**settings);net.clock=clock;notes=[]
        return job,clock,net,notes
    def run_gate(self,job,clock,net,notes):return self.gate(job,notify=lambda value:notes.append(copy.deepcopy(value)),socket_factory=net.factory,clock=clock.now,sleep=clock.sleep)
    def clean(self,net):self.assertTrue(all(p.close_called for p in net.created));self.assertEqual(net.bound,set())
    def test_01_all33_are_held_together_then_every_probe_is_closed(self):
        job,c,n,notes=self.fixture();result=self.run_gate(job,c,n,notes);self.clean(n)
        self.assertEqual((result['status'],result['tries'],n.peak),('PORTS_FREE_BEFORE_LAUNCH',1,33));self.assertEqual(result['ports'],n.ports)
        self.assertTrue(result['probe_sockets_released']);self.assertFalse(result['native_launch_started'])
    def test_02_busy_set_retries_after_cleanup_and_succeeds(self):
        job,c,n,notes=self.fixture(busy_attempts={1,2});result=self.run_gate(job,c,n,notes);self.clean(n)
        self.assertEqual(result['tries'],3);self.assertEqual(result['elapsed_s'],.5);self.assertEqual(n.peak,33)
        self.assertEqual([r['status']for r in notes],['WAITING_FOR_PORTS','WAITING_FOR_PORTS','PORTS_FREE_BEFORE_LAUNCH'])
        self.assertTrue(all(r['busy_port']==n.ports[-1]for r in notes[:-1]))
    def test_03_permanent_busy_has_one90s_deadline_and_no_launch(self):
        job,c,n,notes=self.fixture(busy_attempts='always',busy_port=33000)
        with self.assertRaises(TimeoutError):self.run_gate(job,c,n,notes)
        self.clean(n);self.assertEqual(c.value,90);self.assertEqual(notes[-1]['status'],'PORT_WAIT_TIMEOUT')
        self.assertTrue(all(r['deadline_monotonic_s']==90 and not r['native_launch_started']for r in notes))
    def test_04_unknown_OS_and_Python_errors_fail_without_retry(self):
        for error in(OSError(errno.EACCES,'synthetic denied'),RuntimeError('synthetic unknown failure')):
            job,c,n,notes=self.fixture(error=error)
            with self.assertRaises(type(error)):self.run_gate(job,c,n,notes)
            self.clean(n);self.assertEqual((n.tries,c.value),(1,0));self.assertEqual(notes[-1]['status'],'PORT_PROBE_FAILED')
    def test_05_even_close_error_attempts_all_cleanup_and_is_never_retried(self):
        job,c,n,notes=self.fixture(close_error=True)
        with self.assertRaises(OSError):self.run_gate(job,c,n,notes)
        self.clean(n);self.assertEqual(n.tries,1);self.assertEqual(len(n.created),33)
        self.assertEqual(notes[-1]['status'],'PORT_PROBE_CLEANUP_FAILED');self.assertIs(notes[-1]['probe_sockets_released'],False)
    def test_06_a_slow_whole_set_cannot_pass_after90s(self):
        job,c,n,notes=self.fixture(slow=True)
        with self.assertRaises(TimeoutError):self.run_gate(job,c,n,notes)
        self.clean(n);self.assertEqual(n.tries,1);self.assertEqual(notes[-1]['status'],'PORT_WAIT_TIMEOUT')
    def test_07_invalid_map_or_duplicate_or_bool_port_opens_no_socket(self):
        for fault in('missing_slot','duplicate','bool'):
            job,c,n,notes=self.fixture()
            if fault=='missing_slot':job['proxy_ports'].pop('4096')
            elif fault=='duplicate':job['proxy_ports']['4096']=job['origin_port']
            else:job['origin_port']=True
            with self.assertRaises(ValueError):self.run_gate(job,c,n,notes)
            self.assertEqual(n.created,[])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--source-sha256',required=True);p.add_argument('--report',type=Path,required=True);ARGS=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    report=dict(schema='robotron-fake-socket-screen-port-gate-CPU-contract-v1',status='PASS'if result.wasSuccessful()else'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),selected_source=dict(path=ARGS.source,sha256=ARGS.source_sha256),actual_function_AST=getattr(Contracts,'function_AST',None),real_socket_or_bind_or_listen_or_connect_or_proc_API_model_array_action=False,scope='Actual selected port-gate function with explicit fake sockets and clock. No native/gameplay/port-reservation credit.')
    with ARGS.report.open('x')as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    raise SystemExit(0 if result.wasSuccessful()and not result.skipped else 1)
