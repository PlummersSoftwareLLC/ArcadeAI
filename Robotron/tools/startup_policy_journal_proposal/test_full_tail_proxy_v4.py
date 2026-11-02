"""New bridge/ledger contract; actual journal/controller, synthetic wire peers.

The consumed drain module supplies fixture definitions only. No original test
method is run. ROM, policy, producer rows, accepted observations and EOF are
synthetic; this scope cannot validate a real MAME tail or quality score.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import full_startup_proxy_v4 as bridge
import tail_ledger_v1 as ledger
import wire_codec_v2 as codec
spec=importlib.util.spec_from_file_location('_consumed_host_drain_fixture_defs_only',HERE/'test_cohort_drain_v1.py')
defs=importlib.util.module_from_spec(spec);sys.modules[spec.name]=defs;spec.loader.exec_module(defs)
ACTION=struct.pack('>bbBBBB',3,6,4,0,1,0x85)
PAYLOAD=codec.V2_HEADER.pack(1890,0.,0.,0,0,0,0,0,20000,0,0,3)+bytes(1890*4)+bytes(4)


class FleetWithoutFirst(defs.Fixture):
    def certify(self,subject):
        if subject['slot']!=4096:super().certify(subject)


class Peer:
    def __init__(self):self.sent=[];self.incoming=b'';self.before_send=lambda raw:None
    def sendall(self,raw):self.before_send(raw);self.sent.append(raw)
    def recv(self,count):
        count=min(count,11);out,self.incoming=self.incoming[:count],self.incoming[count:];return out
    def settimeout(self,value):pass
    def setsockopt(self,*args):pass


class Origin:
    def __init__(self,f):self.f=f;self.sent=[];self.buffer=b'';self.accept=True
    def sendall(self,raw):
        if len(raw)==2:return  # original handshake in the served-state EOF fixtures
        assert raw==struct.pack('>I',len(PAYLOAD))+PAYLOAD
        self.sent.append(raw)
        if self.accept:
            self.f.cs['frames']+=1
            self.f.cs.update(game_score=self.f.frame.game_score,level_number=self.f.frame.level_number,
                player_alive=self.f.frame.player_alive,num_lasers=self.f.frame.num_lasers,lives=self.f.frame.lives)
            self.f.fleet.journal.observe(96,self.f.frame,self.f.cs,context=lambda:self.f.fleet.context)
        self.buffer=ACTION
    def recv(self,count):
        count=min(count,2);out,self.buffer=self.buffer[:count],self.buffer[count:];return out
    def settimeout(self,value):pass
    def setsockopt(self,*args):pass


class ReleaseAfterEOF:
    def __init__(self,server):self.server=server;self.released=False
    def is_set(self):return self.released
    def wait(self,timeout):
        self.server.shutdown_event.set();self.released=True;return True


class Fixture:
    def __init__(self):
        self.fleet=FleetWithoutFirst();self.subject=self.fleet.subjects[0]
        self.cs=dict(frames=0,game_uid=4097,client_slot=4096,eval_only=True,
            game_score=100,level_number=88,player_alive=True,num_lasers=255,lives=255)
        self.fleet.states[4096]=self.cs
        self.frame=defs.frame(game_score=100,level_number=88,player_alive=True,num_lasers=255,lives=255)
        self.fleet.journal.observe(96,self.frame,self.cs,context=lambda:self.fleet.context)
        self.server=SimpleNamespace(client_lock=threading.Lock(),client_states={96:self.cs},
            game_journal=self.fleet.journal,inference_only_error=None,shutdown_event=threading.Event(),
            _journal_context=lambda cs:copy.deepcopy(self.fleet.context))
        self.path=Path(self.fleet.temp.name)/'bound-original-producer-v2.jsonl';self.path.touch(mode=0o600)
        self.events=0
        self.row('header',frame_limit=1200,continues_after_prefix=True)
        for offset in range(0,0x19000,128):self.row('raw_ROM_chunk',offset=offset,data_hex=defs.ROM[offset:offset+128].hex())
        s=self.path.stat();identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(s.st_mode&0o777),uid=s.st_uid,nlink=s.st_nlink)
        self.logs=[];self.peer=Peer();self.origin=Origin(self)
        self.proxy=bridge.StartupProxy(self.server,**self.subject,trace_path=self.path,trace_identity=identity,
            rom_sha256=hashlib.sha256(defs.ROM).hexdigest(),policy_reader=lambda:self.fleet.policy,
            admission_reader=lambda:self.fleet.window,frame_parser=lambda raw:copy.copy(self.frame),
            emit=self.logs.append,stop_event=ReleaseAfterEOF(self.server),drain_reader=lambda:self.fleet.gate,
            wall_ns=lambda:self.fleet.wall,monotonic_ns=lambda:self.fleet.mono)
        self.proxy.cid=96

    def row(self,kind,**values):
        self.events+=1
        row=dict(schema='robotron-full-policy-startup-trace-v2',event=self.events,kind=kind,**self.subject,**values)
        with self.path.open('ab')as f:f.write((json.dumps(row,separators=(',',':'))+'\n').encode())
        return row

    def meta(self,**changes):
        seq=self.proxy.sequence+1;issuer=self.proxy.issuer
        data=dict(schema='robotron-full-startup-envelope-v2',**self.subject,sequence=seq,
            event=self.events+1 if seq<=1200 else 0,status=243,score_hex='00000000',wave=0,
            reserves=0,current_player=0,player_count=2,credit=1,planned_start=0,planned_coin=0,
            mode='gated',nonce='0'*64,first_play_sequence=-1,last_start=0,last_coin=0,
            last_apply_ok=True,last_socket_ok=True)
        if self.proxy.last_response:
            data.update(last_start=self.proxy.last_response[8]&1,last_coin=self.proxy.last_response[9])
        if issuer:data.update(nonce=issuer.nonce,mode='authorized')
        if self.proxy.handoff:
            data.update(mode='latched',status=127,wave=1,reserves=2,current_player=1,player_count=1)
        if seq>=8 and self.proxy.handoff:data.update(mode='legacy',status=0,first_play_sequence=8)
        data.update(changes);return data

    def step(self,**changes):
        meta=self.meta(**changes)
        if meta['sequence']<=1200:
            row={k:v for k,v in meta.items()if k not in ('schema','event',*self.subject)}
            self.row('snapshot',**row)
        self.proxy.process(self.peer,self.origin,codec.encode_request(PAYLOAD,meta))
        if meta['sequence']<=1200:
            response=codec.decode_response(self.peer.sent[-1])
            self.row('input_applied',sequence=meta['sequence'],nonce=response['nonce'],start=response['start'],
                coin=response['coin'],response_hex=self.peer.sent[-1].hex(),socket_ok=True,apply_ok=True,
                debug_bypass=False,held_start_before_response=False)
        self.fleet.advance(1_000_000);return meta

    def prefix(self):
        self.step(status=219,credit=0)
        boot=dict(nonce='0'*64,dp=0x98,mask=255,bank_entry=1,last_start=0,last_apply_ok=True,last_socket_ok=True)
        self.row('ROM_write',sequence=1,address=0x9859,instruction_pc=0xd137,instruction_hex='6f80',data=0,**boot)
        self.row('ROM_write',sequence=1,address=0x9859,instruction_pc=0xd184,instruction_hex='0359',data=255,**boot)
        self.step(planned_coin=1,credit=0)
        self.row('ROM_write',sequence=2,address=0x9859,instruction_pc=0x79c4,instruction_hex='9759',
            a=243,data=243,credit=1,**boot)
        self.step(planned_start=1)
        nonce=self.proxy.issuer.nonce
        tap=dict(nonce=nonce,dp=0x98,mask=255,bank_entry=1,last_apply_ok=True,last_socket_ok=True)
        self.row('ROM_write',sequence=4,address=0x9840,instruction_pc=0x2715,instruction_hex='9740',
            a=1,data=1,last_start=1,**tap)
        self.step(planned_start=1);self.step(planned_start=1);self.step()
        self.row('ROM_write',sequence=6,address=0x9859,instruction_pc=0x2751,instruction_hex='9759',
            a=127,data=127,last_start=0,**tap)
        self.frame=defs.frame()
        self.step(status=127,wave=1,reserves=2,current_player=1,player_count=1)
        self.frame.player_alive=True
        for seq in range(8,1201):self.step(planned_start=int(seq==1200),planned_coin=int(seq==1200))
        self.row('footer',reason='prefix_complete',sequence=1200,frame_limit=1200,failed=False,
            machine_exit_requested=False,initialized_sequence=7,latched_sequence=7,first_play_sequence=8,
            gate_sequence=4,setup_sequence=6)
        self.fleet.bindings[4096]=dict(self.subject,client_id=96,nonce=nonce,**{
            k:self.proxy.handoff[k]for k in ('journal_game_id','certificate_identifier')})

    def served_request(self,**changes):
        raw=codec.encode_request(PAYLOAD,self.meta(**changes))
        normal=struct.pack('>H',(1<<14)|(4096<<1))
        self.peer.incoming=normal+codec.encode_handshake(**self.subject)+struct.pack('>I',len(raw))+raw

    def close(self):self.fleet.close()


class OriginalFullTailProxyContract(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_actual32_journal_pending_tail_continues_past4096_and_stop_requires_final_host_permit(self):
        f=self.fixture();f.prefix();self.assertEqual(len(f.fleet.gate.registrations),32)
        f.fleet.closed();self.assertIsNone(f.fleet.gate.try_issue())
        prefix_size=f.path.stat().st_size;prefix_log_count=len(f.logs)
        for seq in range(1201,5001):
            f.step(planned_start=seq%2,planned_coin=seq%2)
            response=codec.decode_response(f.peer.sent[-1])
            self.assertFalse(response['stop']);self.assertEqual(response['action'],ACTION)
            self.assertEqual((response['start'],response['coin']),(seq%2,seq%2))
        self.assertEqual(f.path.stat().st_size,prefix_size)
        self.assertLess(len(f.logs)-prefix_log_count,5)
        self.assertEqual(f.proxy.ledger.summary()['exchange_count'],5000)
        self.assertEqual(len(f.origin.sent),5000)
        self.assertTrue(all(raw==struct.pack('>I',len(PAYLOAD))+PAYLOAD for raw in f.origin.sent))
        for slot in defs.SLOTS:f.fleet.complete_game(slot)
        f.fleet.controller.tick();permit=f.fleet.gate.try_issue();self.assertIsNotNone(permit)
        def before_send(raw):
            self.assertTrue(codec.decode_response(raw)['stop'])
            self.assertIn(4096,permit.used_slots)
        f.peer.before_send=before_send
        f.step(planned_start=1,planned_coin=1)
        self.assertTrue(f.proxy.stop_sent.is_set())
        self.assertEqual((f.peer.sent[-1][8]&1,f.peer.sent[-1][9]),(1,1))
        self.assertEqual(f.proxy.ledger.summary()['exchange_count'],5001)

    def test_only_drained_peer_EOF_finalizes_ledger_and_preserves_original_prefix(self):
        f=self.fixture();f.prefix();f.fleet.complete_all();f.fleet.gate.try_issue()
        f.served_request(planned_start=1,planned_coin=1)
        f.proxy.serve(f.peer,f.origin)
        self.assertTrue(f.proxy.peer_eof.is_set());self.assertIsNone(f.proxy.error)
        self.assertEqual(f.proxy.final_ledger['exchange_count'],1201)
        self.assertEqual(f.proxy.trace.verify_closed_unchanged(),f.proxy.prefix_summary['trace'])
        self.assertTrue(f.server.shutdown_event.is_set())
        final=f.logs[-1];self.assertEqual(final['kind'],'original_drained_peer_EOF')
        self.assertFalse(final['ledger']['postprefix_raw_reconstructable'])

    def test_unexpected_EOF_or_extra_after_STOP_remains_original_failure(self):
        for damage in ('pending_EOF','extra_after_STOP'):
            with self.subTest(damage=damage):
                f=self.fixture();f.prefix()
                if damage=='extra_after_STOP':f.fleet.complete_all();f.fleet.gate.try_issue()
                f.served_request()
                if damage=='extra_after_STOP':f.peer.incoming+=b'x'
                with self.assertRaises(ValueError):f.proxy.serve(f.peer,f.origin)
                self.assertIsNotNone(f.proxy.error);self.assertIsNone(f.proxy.final_ledger)
                self.assertFalse(f.proxy.peer_eof.is_set())
                self.assertEqual(f.logs[-1]['kind'],'original_proxy_failure')

    def test_closed_prefix_tamper_bad_footer_and_failed_previous_input_stop_before_forward(self):
        for damage in ('footer','mutated_closed','last_apply','last_start'):
            with self.subTest(damage=damage):
                f=self.fixture();f.prefix()
                if damage=='footer':
                    raw=f.path.read_text().replace('"reason":"prefix_complete"','"reason":"failed"');f.path.write_text(raw)
                if damage=='mutated_closed':
                    f.step(planned_start=1);f.path.write_bytes(f.path.read_bytes()+b'\n')
                    with self.assertRaisesRegex(ValueError,'changed'):f.proxy.trace.verify_closed_unchanged()
                    continue
                changes={'last_apply_ok':False}if damage=='last_apply'else {'last_start':0}if damage=='last_start'else {}
                before=len(f.origin.sent)
                with self.assertRaises(ValueError):f.step(**changes)
                self.assertEqual(len(f.origin.sent),before)

    def test_ledger_commits_original_bytes_rejections_and_STOP_before_finalization(self):
        subject=dict(slot=4096,session='1'*32,connection='2'*32);logs=[]
        a=ledger.TailLedger(subject,'a'*64,logs.append)
        changed=ledger.TailLedger(subject,'a'*64,lambda row:None)
        for seq in range(1,1202):
            meta=dict(subject,sequence=seq,nonce='b'*64)
            accepted=seq%3!=0;before={'frames':a.accepted};after={'frames':a.accepted+int(accepted)}
            receipt=dict(subject,nonce='b'*64,sequence=seq,consumed_before_send=True)if seq==1201 else None
            response=codec.encode_response(seq,ACTION,latched=True,nonce='b'*64,stop=receipt is not None)
            values=dict(payload=PAYLOAD,meta=meta,action=ACTION,response=response,before=before,after=after,
                accepted=accepted,drain_receipt=receipt)
            a.record(**values)
            altered=dict(values)
            if seq==1199:altered['payload']=PAYLOAD[:100]+b'\1'+PAYLOAD[101:]
            changed.record(**altered)
        self.assertNotEqual(a.summary()['chain_sha256'],changed.summary()['chain_sha256'])
        self.assertEqual((a.summary()['accepted'],a.summary()['rejected']),(801,400))
        self.assertEqual(len(logs),2)
        self.assertEqual(a.finalize(receipt)['original_payload_bytes'],1201*7597)
        with self.assertRaises(ValueError):a.finalize(receipt)
        with self.assertRaises(ValueError):changed.finalize(dict(receipt,sequence=1202))

    def test_witness_capacity_and_external_write_fail_without_silent_drop(self):
        for damage in ('rows','bytes','external'):
            with self.subTest(damage=damage),tempfile.TemporaryDirectory(prefix='robotron-original-bounded-tail-witness-')as d:
                path=Path(d)/'original.jsonl'
                with path.open('xb')as stream:
                    witness=ledger.BoundedWitness(stream,max_rows=1 if damage=='rows'else 5,
                        max_bytes=60 if damage=='bytes'else 1024)
                    witness.emit(dict(kind='first'))
                    before=path.read_bytes()
                    if damage=='external':
                        with path.open('ab')as other:other.write(b'{}\n')
                    with self.assertRaises(ValueError):witness.emit(dict(kind='second'))
                    self.assertEqual(path.read_bytes(),before+(b'{}\n'if damage=='external'else b''))


if __name__=='__main__':unittest.main(verbosity=2)
