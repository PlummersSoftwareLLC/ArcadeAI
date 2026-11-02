"""CPU-only STOP/EOF/park contracts; fake sockets and events, no runtime proof."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=G/'tools/startup_policy_journal_proposal'
PROXY=PREP=None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


class Event:
    def __init__(self,set_value=False,wait_result=True):
        self.set_value=set_value;self.wait_result=wait_result;self.waits=[]
    def set(self):self.set_value=True
    def is_set(self):return self.set_value
    def wait(self,timeout):self.waits.append(timeout);return self.wait_result


class Socket:
    def __init__(self,data=b''):self.data=data;self.timeouts=[];self.sent=[]
    def settimeout(self,value):self.timeouts.append(value)
    def setsockopt(self,*args):pass
    def recv(self,count):
        out,self.data=self.data[:count],self.data[count:];return out
    def sendall(self,data):self.sent.append(data)


class ParkTests(unittest.TestCase):
    def make(self,bound=22200,*,shutdown=True,wait_result=True,extra=b''):
        stop=Event(wait_result=wait_result)
        server=SimpleNamespace(shutdown_event=Event(shutdown))
        kwargs=dict(slot=4096,session='1'*32,connection='2'*32,trace_path=Path('/never-read'),
            trace_identity=dict(device=1,inode=2,mode='0o600',uid=1001,nlink=1),
            rom_sha256='3'*64,policy_reader=lambda:None,admission_reader=lambda:None,
            frame_parser=lambda _:None,emit=lambda row:None,stop_event=stop,drain_reader=lambda:None)
        proxy=PROXY.StartupProxy(server,parked_origin_timeout_s=bound,**kwargs)
        proxy.find_client=lambda:None
        proxy.trace=SimpleNamespace(loaded_rom=lambda:None,verify_closed_unchanged=lambda:None,closed_pin={'synthetic':True})
        proxy.stop_receipt={'synthetic':True}
        proxy.ledger=SimpleNamespace(finalize=lambda receipt:dict(receipt=receipt))
        proxy.stop_sent.set()
        peer=Socket(struct.pack('>H',(1<<14)|(4096<<1))+PROXY.codec.encode_handshake(**proxy.subject)+extra)
        return proxy,peer,Socket(),stop

    def test_declared_long_park_uses_one_event_wait_after_peer_EOF(self):
        proxy,peer,origin,stop=self.make();proxy.serve(peer,origin)
        self.assertEqual(stop.waits,[22200]);self.assertTrue(proxy.peer_eof.is_set())
        self.assertIsNone(proxy.error);self.assertEqual(peer.timeouts,[5,30]);self.assertEqual(origin.timeouts,[5])

    def test_minimum_bound_is_explicit_and_retains_same_shutdown_path(self):
        proxy,peer,origin,stop=self.make(120);proxy.serve(peer,origin)
        self.assertEqual(stop.waits,[120]);self.assertIsNone(proxy.error)

    def test_unbounded_or_wrongly_typed_lifetimes_fail_before_any_socket(self):
        for value in [None,True,False,119,22201,22200.0,'22200',float('inf')]:
            with self.subTest(value=value),self.assertRaises(ValueError):self.make(value)

    def test_owner_timeout_is_a_failure_with_no_retry(self):
        proxy,peer,origin,stop=self.make(wait_result=False)
        with self.assertRaises(ValueError):proxy.serve(peer,origin)
        self.assertEqual(stop.waits,[22200]);self.assertIsNotNone(proxy.error)

    def test_origin_must_actually_stop_before_bridge_release(self):
        proxy,peer,origin,stop=self.make(shutdown=False)
        with self.assertRaises(ValueError):proxy.serve(peer,origin)
        self.assertIsNotNone(proxy.error)

    def test_post_STOP_bytes_fail_before_origin_parking(self):
        proxy,peer,origin,stop=self.make(extra=b'x')
        with self.assertRaises(ValueError):proxy.serve(peer,origin)
        self.assertEqual(stop.waits,[]);self.assertFalse(proxy.peer_eof.is_set())

    def test_only_declared_proxy_edits_exist_and_active_transport_is_unchanged(self):
        raw=Path(PROXY.__file__).read_bytes();self.assertEqual(raw.decode(),PREP.prepared_source())
        restored=raw.decode()
        for old,new in reversed(PREP.EDITS):restored=restored.replace(new,old,1)
        self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),PREP.PARENT_SHA)
        self.assertIn('peer.settimeout(5);origin.settimeout(5)',raw.decode())


def main():
    global PROXY,PREP
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--source',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    if args.source is None or args.output is None:parser.error('--source and --output required')
    sys.path.insert(0,str(HERE))
    PREP=load('_parked_proxy_prepare',Path(__file__).with_name('prepare_parked_proxy_v1.py'))
    PROXY=load('_future_slot_retirement_proxy',args.source)
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ParkTests))
    assert 'torch'not in sys.modules
    h=load('_parked_proxy_test_helpers',HERE/'run_full_policy_startup_v3.py')
    report=dict(status='PASS'if result.wasSuccessful()else'FAIL',tests_run=result.testsRun,
        failures=[dict(test=str(test),traceback=trace)for test,trace in result.failures],
        errors=[dict(test=str(test),traceback=trace)for test,trace in result.errors],log=log.getvalue(),
        source=h.pin(args.source),test_source=h.pin(Path(__file__)),generator=h.pin(Path(PREP.__file__)),
        synthetic_sockets_events_and_already_STOP_sent_fixture=True,
        physical_MAME_GPU_live_native_or_scientific_qualification=False,live_controls_changed=False,promotion=False)
    pin=h.put(args.output,report)
    print(json.dumps(dict(status=report['status'],tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),report=pin)))
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':raise SystemExit(main())
