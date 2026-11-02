"""Exercise the candidate's actual accept loop with synthetic sockets; no network."""
import ast
import copy
import ipaddress
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parent
TREE = ast.parse((P/'socket_server_candidate.py').read_text())
CLS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
METHODS = {n.name:n for n in CLS.body if isinstance(n, ast.FunctionDef)}
PARSER = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == '_parse_allowed_training_peers')


def functions(names):
    nodes = [copy.deepcopy(PARSER), ast.ClassDef(name='Candidate', bases=[], keywords=[],
        body=[copy.deepcopy(METHODS[name]) for name in names] or [ast.Pass()], decorator_list=[])]
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    namespace = dict(ipaddress=ipaddress, os=os)
    exec(compile(module, str(P/'socket_server_candidate.py'), 'exec'), namespace)
    return namespace


class Peer:
    def __init__(self, fail_close=False):
        self.closed = 0; self.fail_close = fail_close

    def close(self):
        self.closed += 1
        if self.fail_close:
            raise OSError('synthetic close error')


class AdmissionTests(unittest.TestCase):
    def exercise(self, address, raw_peers, replay_enabled=True, fail_close=False):
        ns = functions(['_admit_training_peer', 'start'])
        candidate = ns['Candidate'](); candidate.replay_enabled = replay_enabled
        candidate._allowed_training_peers = ns['_parse_allowed_training_peers'](raw_peers)
        candidate._last_peer_rejection_log = 0
        candidate.host='127.0.0.1'; candidate.port=19997; candidate.shutdown_event=threading.Event()
        candidate.client_lock=threading.Lock(); candidate.clients={}; candidate.client_states={}
        events=[]; failures=[]; peer=Peer(fail_close)
        def allocated():
            events.append('allocate'); return 7
        def initialized(cid):
            events.append('init'); candidate.client_states[cid] = {}
        candidate._alloc_id=allocated; candidate._init_client=initialized
        candidate.handle_client=lambda sock,cid: events.append('handler')
        candidate._fail_inference_only=lambda reason:failures.append(reason)
        candidate.stop=lambda:events.append('stop')
        listener=SimpleNamespace(setsockopt=lambda *a:None, bind=lambda *a:None, listen=lambda *a:None,
                                 setblocking=lambda *a:None, accept=lambda:(peer,(address,12345)))
        selections=0
        def selected(*args):
            nonlocal selections
            selections+=1
            if selections==1:return [listener],[],[]
            candidate.running=False; return [],[],[]
        class Thread:
            def __init__(self,**kwargs): self.arguments=kwargs
            def start(self):events.append('thread_started')
        ns.update(socket=SimpleNamespace(AF_INET=2, SOCK_STREAM=1, SOL_SOCKET=1, SO_REUSEADDR=2,
                                         socket=lambda *a:listener),
                  select=SimpleNamespace(select=selected), threading=SimpleNamespace(Thread=Thread),
                  SERVER_CONFIG=SimpleNamespace(max_clients=128),
                  time=SimpleNamespace(monotonic=lambda:100, sleep=lambda value:None),
                  traceback=SimpleNamespace(print_exc=lambda:None), print=lambda *a,**k:None)
        candidate.start()
        self.assertEqual(failures, [])
        return candidate, peer, events

    def test_unconfigured_legacy_listener_still_accepts_remote_clients(self):
        candidate,peer,events=self.exercise('192.168.1.13',None)
        self.assertEqual(peer.closed,0); self.assertEqual(events,['allocate','init','thread_started','stop'])
        self.assertEqual(set(candidate.client_states),{7})

    def test_explicit_local_peers_reach_the_unchanged_handler_path(self):
        for address in ['127.0.0.1','192.168.1.131']:
            with self.subTest(address=address):
                candidate,peer,events=self.exercise(address,'127.0.0.1,192.168.1.131')
                self.assertEqual(peer.closed,0); self.assertIn('thread_started',events)

    def test_observed_extra_remote_peer_is_rejected_before_ids_states_or_handlers(self):
        candidate,peer,events=self.exercise('192.168.1.13','127.0.0.1,192.168.1.131')
        self.assertEqual(peer.closed,1); self.assertEqual(events,['stop'])
        self.assertEqual(candidate.clients,{}); self.assertEqual(candidate.client_states,{})

    def test_rejected_close_error_does_not_stop_or_admit_the_client(self):
        candidate,peer,events=self.exercise('192.168.1.13','127.0.0.1',fail_close=True)
        self.assertEqual(peer.closed,1); self.assertEqual(events,['stop'])
        self.assertEqual(candidate.client_states,{})

    def test_inference_only_listener_does_not_inherit_training_peer_restriction(self):
        candidate,peer,events=self.exercise('192.168.1.13','127.0.0.1',replay_enabled=False)
        self.assertEqual(peer.closed,0); self.assertIn('thread_started',events)

    def test_nonempty_malformed_or_wildcard_peer_settings_fail_closed(self):
        parser=functions([])['_parse_allowed_training_peers']
        for raw in ['*','0.0.0.0','127.0.0.1,','127.0.0.1,,192.168.1.131',
                    'dell','192.168.1.0/24','::1','224.0.0.1','255.255.255.255','x'*513]:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):parser(raw)
        self.assertIsNone(parser(' '))
        self.assertEqual(parser('127.0.0.1, 192.168.1.131'),frozenset(map(ipaddress.ip_address,['127.0.0.1','192.168.1.131'])))

    def test_actual_constructor_validates_before_any_worker_or_client_mutation(self):
        ns=functions(['__init__']); candidate=ns['Candidate'].__new__(ns['Candidate'])
        with patch.dict(os.environ,{'ROBOTRON_ALLOWED_TRAINING_PEERS':'0.0.0.0'}):
            with self.assertRaises(ValueError):candidate.__init__('127.0.0.1',19997,None)
        self.assertEqual(vars(candidate),{})
        class StopConstruction(Exception):pass
        class Sentinel(ns['Candidate']):
            def __setattr__(self,key,value):
                if key=='_last_peer_rejection_log':raise StopConstruction()
                object.__setattr__(self,key,value)
        candidate=Sentinel.__new__(Sentinel)
        with patch.dict(os.environ,{'ROBOTRON_ALLOWED_TRAINING_PEERS':'malformed'}):
            with self.assertRaises(StopConstruction):candidate.__init__('127.0.0.1',19997,None,replay_enabled=False)
        self.assertIsNone(candidate._allowed_training_peers)

    def test_every_existing_function_except_constructor_and_accept_loop_is_unchanged(self):
        original=ast.parse((P/'original-socket-server.readonly.txt').read_text())
        def all_functions(tree):
            return {node.name:ast.dump(node,include_attributes=False)
                    for node in ast.walk(tree) if isinstance(node,ast.FunctionDef)}
        before,after=all_functions(original),all_functions(TREE)
        self.assertEqual([name for name in before if before[name]!=after[name]],['__init__','start'])
        for name in ['parse_frame_data','handle_client','_init_client','_pack_action']:
            self.assertEqual(before[name],after[name])


if __name__ == '__main__':
    unittest.main(verbosity=2)
