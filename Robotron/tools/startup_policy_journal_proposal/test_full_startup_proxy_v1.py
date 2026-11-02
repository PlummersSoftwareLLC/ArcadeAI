"""Original bridge contract: real selected GameJournal, synthetic origin/policy.

No neural model or emulator is loaded. The new transport, prefix identity and
journal ordering are exercised; previous contract methods are never invoked.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import socket
import stat
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import full_startup_proxy_v1 as bridge
import wire_codec_v1 as codec

GAME=HERE.parents[1]
path=GAME/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/game_journal.py'
spec=importlib.util.spec_from_file_location('_proxy_original_journal',path)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
ROM=bytes(0x19000)
ACTION=struct.pack('>bbBBBB',3,6,0,0,1,0x85)
PAYLOAD=codec.V2_HEADER.pack(1890,0.,0.,0,0,0,0,0,20000,0,0,3)+bytes(1890*4)+bytes(4)


class Peer:
    def __init__(self):
        self.sent=[]
        self.before_send=lambda response:None
    def sendall(self,response):
        self.before_send(response)
        self.sent.append(response)


class Origin:
    def __init__(self,fixture):
        self.f=fixture;self.sent=[];self.buffer=b'';self.accept=True;self.increment=1
        self.action=ACTION
    def sendall(self,raw):
        self.sent.append(raw)
        assert raw==struct.pack('>I',len(PAYLOAD))+PAYLOAD
        if self.accept:
            self.f.cs['frames']+=self.increment
            self.f.cs.update(game_score=self.f.frame.game_score,
                level_number=self.f.frame.level_number,player_alive=self.f.frame.player_alive,
                num_lasers=self.f.frame.num_lasers,lives=self.f.frame.lives)
            self.f.journal.observe(17,self.f.frame,self.f.cs,context=lambda:self.f.context)
        self.buffer=self.action
    def recv(self,count):
        count=min(count,2)
        result,self.buffer=self.buffer[:count],self.buffer[count:]
        return result


class Fixture:
    def __init__(self):
        self.temp=tempfile.TemporaryDirectory(prefix='robotron-new-full-proxy-')
        self.wall=1_000_000_000_000;self.mono=50_000_000_000
        self.subject=dict(slot=4096,session='1'*32,connection='2'*32)
        self.policy=dict(checkpoint_sha256='a'*64,policy_load_id='b'*64,
            measurement_active=True,measurement_generation=7,experiment='proxy-contract',
            training_enabled=False,replay_enabled=False,epsilon=0.,expert_ratio=0.,
            learner_frame_count=1741229950,training_steps=7128160,optimized_samples=27621148672)
        self.window=dict(open_unix_ns=self.wall-1_000_000_000,close_unix_ns=self.wall+10_000_000_000,
                         generation=7,experiment='proxy-contract')
        self.context=dict(experiment='proxy-contract',measurement_active=True,
            measurement_generation=7,epsilon=0.,expert_ratio=0.,difficulty=5,
            learner_frames=1741229950,training_steps=7128160,optimized_samples=27621148672)
        self.frame=SimpleNamespace(game_score=100,level_number=88,player_alive=True,
            num_lasers=255,lives=255,start_pressed=False,done=False)
        self.cs=dict(frames=0,game_uid=91,client_slot=4096,eval_only=True,
            game_score=100,level_number=88,player_alive=True,num_lasers=255,lives=255)
        self.journal=base.GameJournal(self.temp.name,clock=lambda:self.wall/1e9,
                                      completion_policy='confirmed_reset_reserves_v1')
        self.journal.observe(17,self.frame,self.cs,context=lambda:self.context)
        self.old=copy.deepcopy(self.journal.active[17])
        self.server=SimpleNamespace(client_lock=threading.RLock(),client_states={17:self.cs},
            game_journal=self.journal,inference_only_error=None,shutdown_event=threading.Event(),
            _journal_context=lambda cs:dict(self.context))
        self.path=Path(self.temp.name)/'original-trace.jsonl'
        self.path.touch(mode=0o600)
        self.events=0
        self.row('header',frame_limit=1200)
        for offset in range(0,0x19000,128):
            self.row('raw_ROM_chunk',offset=offset,data_hex=ROM[offset:offset+128].hex())
        s=self.path.stat()
        self.identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),
                           uid=s.st_uid,nlink=s.st_nlink)
        self.logs=[];self.peer=Peer();self.origin=Origin(self)
        self.proxy=bridge.StartupProxy(self.server,**self.subject,trace_path=self.path,
            trace_identity=self.identity,rom_sha256=hashlib.sha256(ROM).hexdigest(),
            policy_reader=lambda:self.policy,admission_reader=lambda:self.window,
            frame_parser=lambda raw:copy.copy(self.frame),emit=self.logs.append,
            stop_event=threading.Event(),wall_ns=lambda:self.wall,monotonic_ns=lambda:self.mono)
        self.proxy.cid=17

    def row(self,kind,**values):
        self.events+=1
        row=dict(schema='robotron-full-policy-startup-trace-v1',event=self.events,
                 kind=kind,**self.subject,**values)
        with self.path.open('ab')as stream:
            stream.write((json.dumps(row,separators=(',',':'))+'\n').encode())
        return row

    def meta(self,**changes):
        value=dict(schema='robotron-full-startup-envelope-v1',**self.subject,
            sequence=self.proxy.sequence+1,event=self.events+1,status=243,score_hex='00000000',
            wave=0,reserves=0,current_player=0,player_count=0,credit=1,
            planned_start=0,planned_coin=0,mode='gated',last_start=0,last_coin=0,
            last_apply_ok=True,last_socket_ok=True,nonce='0'*64,first_play_sequence=-1)
        if self.proxy.issuer:
            value.update(nonce=self.proxy.issuer.nonce,
                         mode='latched'if self.proxy.handoff else 'authorized')
        value.update(changes)
        return value

    def step(self,**changes):
        meta=self.meta(**changes)
        snapshot=dict(meta);snapshot.pop('schema');snapshot.pop('event')
        for key in self.subject:snapshot.pop(key)
        self.row('snapshot',**snapshot)
        self.proxy.process(self.peer,self.origin,codec.encode_request(PAYLOAD,meta))
        self.wall+=1_000_000;self.mono+=1_000_000
        return meta

    def authorized(self,application_changes=None):
        self.step(planned_start=1)
        a=self.proxy.issuer
        values=dict(sequence=1,nonce=a.nonce,response_hex=a.response.hex(),start=1,coin=0,
            socket_ok=True,apply_ok=True,debug_bypass=False,held_start_before_response=False)
        values.update(application_changes or {})
        self.row('input_applied',**values)
        self.step(planned_start=1,last_start=1)
        self.row('ROM_write',sequence=3,nonce=a.nonce,address=0x9840,instruction_pc=0x2715,
            instruction_hex='9740',dp=0x98,a=1,data=1,mask=255,bank_entry=1,last_start=1,
            last_apply_ok=True,last_socket_ok=True)
        self.step(planned_start=1,last_start=1)
        self.row('ROM_write',sequence=4,nonce=a.nonce,address=0x9859,instruction_pc=0x2751,
            instruction_hex='9759',dp=0x98,a=127,data=127,mask=255,bank_entry=1,last_start=0,
            last_apply_ok=True,last_socket_ok=True)
        self.step()
        self.frame=SimpleNamespace(game_score=0,level_number=1,player_alive=False,
            num_lasers=2,lives=1,start_pressed=False,done=False)

    def initialized(self):
        return self.step(status=127,wave=1,reserves=2,current_player=1,player_count=1)

    def no_handoff(self):
        assert self.proxy.handoff is None
        assert not self.journal.active[17]['known_start']
        assert not self.journal.measurement_starts_path.exists()

    def close(self):self.temp.cleanup()


class FullStartupProxyContract(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_origin_ack_then_distinct_journal_before_latch_and_full_tail_after_cutoff(self):
        f=self.fixture();f.authorized()
        def before_send(raw):
            response=codec.decode_response(raw)
            self.assertEqual(response['action'],ACTION)
            if response['latched']:
                self.assertEqual(f.cs['frames'],5)
                self.assertTrue(f.journal.active[17]['known_start'])
                self.assertEqual(len(f.journal.measurement_starts_path.read_text().splitlines()),1)
        f.peer.before_send=before_send;f.initialized();f.peer.before_send=lambda raw:None
        self.assertNotEqual(f.old['journal_game_id'],f.journal.active[17]['journal_game_id'])
        self.assertEqual(f.journal.active[17]['game_uid'],91)
        old=json.loads(f.journal.games_path.read_text());self.assertFalse(old['complete'])
        self.assertFalse(old['eligible']);self.assertEqual(old['score'],100)
        f.wall=f.window['close_unix_ns']+1;f.mono+=11_000_000_000
        f.frame.player_alive=True;f.frame.game_score=400
        f.step(mode='legacy',first_play_sequence=6,status=0,wave=1,reserves=2,
               current_player=1,player_count=1,planned_coin=1)
        final=codec.decode_response(f.peer.sent[-1]);self.assertEqual(final['coin'],1)
        self.assertEqual(final['action'],ACTION)
        self.assertEqual(len(f.origin.sent),6)
        self.assertEqual([r['kind']for r in f.logs].count('actual_policy_journal_handoff'),1)
        status=f.journal.cohort_status('proxy-contract',999,1010)
        self.assertEqual((status['started'],status['count'],status['pending']),(1,0,1))

    def test_neutral_reply_is_not_acceptance_wait_for_later_accepted_inactive_init(self):
        f=self.fixture();f.authorized();f.origin.accept=False;f.initialized();f.no_handoff()
        self.assertFalse(codec.decode_response(f.peer.sent[-1])['latched'])
        f.origin.accept=True;f.initialized()
        self.assertTrue(f.proxy.handoff);self.assertEqual(f.cs['frames'],5)
        cert=next(r for r in f.logs if r['kind']=='actual_policy_journal_handoff')['certificate']
        self.assertEqual(cert['evidence']['origin_acceptance']['frame_sequence'],6)
        self.assertEqual(cert['evidence']['origin_acceptance']['accepted_frames'],5)

    def test_unaccepted_start_or_invalid_origin_action_never_authorizes(self):
        f=self.fixture();f.origin.accept=False;f.step(planned_start=1)
        self.assertIsNone(f.proxy.issuer)
        self.assertEqual(codec.decode_response(f.peer.sent[-1])['start'],0)
        f.origin.accept=True;f.origin.action=struct.pack('>bbBBBB',3,6,2,0,1,0x85)
        with self.assertRaises(ValueError):f.step(planned_start=1)
        self.assertIsNone(f.proxy.issuer);f.no_handoff()

    def test_subject_sequence_nonce_and_play_before_handoff_rejected_before_forward(self):
        for changes in [dict(sequence=2),dict(session='3'*32),dict(mode='authorized')]:
            f=self.fixture();raw=codec.encode_request(PAYLOAD,f.meta(**changes))
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                f.proxy.process(f.peer,f.origin,raw)
            self.assertEqual(f.origin.sent,[]);f.no_handoff()
        for changes in [dict(nonce='3'*64),dict(first_play_sequence=2)]:
            f=self.fixture();f.step(planned_start=1);before=len(f.origin.sent)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                f.proxy.process(f.peer,f.origin,codec.encode_request(PAYLOAD,f.meta(**changes)))
            self.assertEqual(len(f.origin.sent),before);f.no_handoff()

    def test_trace_ROM_identity_event_and_gate_duplication_rejected(self):
        f=self.fixture();self.assertEqual(f.proxy.trace.loaded_rom(),ROM)
        f.path.rename(f.path.with_suffix('.preserved'));f.path.touch(mode=0o600)
        with self.assertRaises(ValueError):f.proxy.trace.loaded_rom()
        f=self.fixture();f.proxy.trace.expected_rom_sha256='a'*64
        with self.assertRaises(ValueError):f.step(planned_start=1)
        f.no_handoff()
        f=self.fixture();f.authorized()
        f.row('ROM_write',sequence=1,nonce='0'*64,address=0x9840,instruction_pc=0x2715,
              dp=0x98,bank_entry=1)
        with self.assertRaises(ValueError):f.initialized()
        f.no_handoff()
        f=self.fixture()
        with f.path.open('ab')as stream:stream.write(b'{"event":802,"event":802}\n')
        with self.assertRaises(ValueError):f.proxy.trace.rows(802)

    def test_ambiguous_origin_ordinal_or_error_blocks_transition(self):
        f=self.fixture();f.origin.increment=2
        with self.assertRaises(ValueError):f.step(planned_start=1)
        f.no_handoff();self.assertIsNone(f.proxy.issuer)
        f=self.fixture();f.server.inference_only_error='actual failure'
        with self.assertRaises(ValueError):f.step(planned_start=1)
        f.no_handoff();self.assertIsNone(f.proxy.issuer)

    def test_failed_apply_changed_policy_cutoff_and_failed_send_do_not_latch(self):
        f=self.fixture();f.authorized(dict(apply_ok=False))
        with self.assertRaises(ValueError):f.initialized()
        f.no_handoff()
        f=self.fixture();f.authorized();f.policy['policy_load_id']='c'*64
        with self.assertRaises(ValueError):f.initialized()
        f.no_handoff()
        f=self.fixture();f.authorized();f.wall=f.window['close_unix_ns'];f.mono+=10_000_000_000
        with self.assertRaises(ValueError):f.initialized()
        f.no_handoff()
        f=self.fixture()
        def failed_send(raw):raise OSError('actual failed send')
        f.peer.before_send=failed_send
        with self.assertRaises(OSError):f.step(planned_start=1)
        self.assertEqual(f.proxy.issuer.state,'failed');self.assertEqual(f.peer.sent,[]);f.no_handoff()

    def test_real_TCP_handshake_and_intentional_shutdown_guard(self):
        def tcp_pair():
            listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
            remote=socket.create_connection(listener.getsockname(),timeout=2)
            local,_=listener.accept();listener.close()
            self.addCleanup(local.close);self.addCleanup(remote.close)
            return local,remote
        f=self.fixture();peer,client=tcp_pair();origin,upstream=tcp_pair()
        client.sendall(struct.pack('>H',(1<<14)|(4096<<1))+codec.encode_handshake(**dict(f.subject,session='3'*32)))
        with self.assertRaises(ValueError):f.proxy.serve(peer,origin)
        self.assertIn('session handshake',f.proxy.error)
        for shutdown in (False,True):
            f=self.fixture();peer,client=tcp_pair();origin,upstream=tcp_pair()
            normal=struct.pack('>H',(1<<14)|(4096<<1))
            client.sendall(normal+codec.encode_handshake(**f.subject)+
                           (struct.pack('>I',codec.REQUEST.size)+bytes(codec.REQUEST.size))*1200)
            seen=[];f.proxy.process=lambda peer,origin,raw:seen.append(raw)
            # This isolates the owner-close guard; it does not simulate a MAME
            # receipt. The separate actual runtime must verify its exit/footer.
            f.proxy.stop_event=SimpleNamespace(is_set=lambda:False,wait=lambda timeout:True)
            if shutdown:f.server.shutdown_event.set()
            if shutdown:f.proxy.serve(peer,origin)
            else:
                with self.assertRaises(ValueError):f.proxy.serve(peer,origin)
                self.assertIn('Origin must stop',f.proxy.error)
            self.assertEqual(bridge.recv_exact(upstream,2),normal)
            self.assertEqual(len(seen),1200);self.assertTrue(f.proxy.sent_complete.is_set())


if __name__=='__main__':unittest.main(verbosity=2)
