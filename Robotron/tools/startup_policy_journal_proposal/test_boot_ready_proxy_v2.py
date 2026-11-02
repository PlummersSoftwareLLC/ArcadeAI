"""New boot-ready scope; no consumed original test methods are called."""
from pathlib import Path
import ast
import copy
import importlib.util
import json
import sys
import unittest
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('_boot_ready_fixture_defs',HERE/'test_full_startup_proxy_v1.py')
defs=importlib.util.module_from_spec(spec);sys.modules[spec.name]=defs;spec.loader.exec_module(defs)
sys.modules[defs.base.__name__]=defs.base
import full_startup_proxy_v2 as bridge
from boot_readiness_v1 import boot_readiness


class BootReadyProxyContract(unittest.TestCase):
    def fixture(self):
        f=defs.Fixture();self.addCleanup(f.close)
        f.proxy=bridge.StartupProxy(f.server,**f.subject,trace_path=f.path,trace_identity=f.identity,
            rom_sha256=defs.hashlib.sha256(defs.ROM).hexdigest(),policy_reader=lambda:f.policy,
            admission_reader=lambda:f.window,frame_parser=lambda raw:copy.copy(f.frame),
            emit=f.logs.append,stop_event=defs.threading.Event(),wall_ns=lambda:f.wall,
            monotonic_ns=lambda:f.mono)
        f.proxy.cid=17
        return f

    def boot_and_coin(self,f):
        f.step()
        common=dict(address=0x9859,dp=0x98,bank_entry=1,mask=255,last_start=0,
                    last_apply_ok=True,last_socket_ok=True,nonce='0'*64)
        f.row('ROM_write',sequence=f.proxy.sequence,instruction_pc=0xd137,
              instruction_hex='6f80',data=0,**common)
        f.step()
        f.row('ROM_write',sequence=f.proxy.sequence,instruction_pc=0xd184,
              instruction_hex='0359',data=255,**common)
        f.step(planned_coin=1)
        response=f.peer.sent[-1]
        f.row('input_applied',sequence=f.proxy.sequence,nonce='0'*64,response_hex=response.hex(),
            start=0,coin=1,socket_ok=True,apply_ok=True,debug_bypass=False,
            held_start_before_response=False)
        f.row('ROM_write',sequence=f.proxy.sequence+1,instruction_pc=0x79c4,
              instruction_hex='9759',data=243,a=243,credit=1,**common)
        f.step(status=243,player_count=2)

    def test_RAM_test_start_held_until_real_boot_coin_then_actual_journal_before_action(self):
        f=self.fixture()
        f.step(planned_start=1,status=219,credit=187,wave=171,reserves=99,player_count=187)
        self.assertIsNone(f.proxy.issuer)
        self.assertEqual(defs.codec.decode_response(f.peer.sent[-1])['start'],0)
        self.boot_and_coin(f)
        sequence=f.proxy.sequence+1
        f.step(planned_start=1,status=243,player_count=2)
        self.assertEqual(f.proxy.issuer.sequence,sequence)
        ready=[r for r in f.logs if r['kind']=='original_boot_coin_readiness']
        self.assertEqual(len(ready),1);self.assertFalse(ready[0]['readiness']['game_start_proven'])
        a=f.proxy.issuer
        f.row('input_applied',sequence=sequence,nonce=a.nonce,response_hex=a.response.hex(),start=1,
            coin=0,socket_ok=True,apply_ok=True,debug_bypass=False,held_start_before_response=False)
        f.step(planned_start=1,last_start=1)
        tap=dict(nonce=a.nonce,dp=0x98,mask=255,bank_entry=1,last_apply_ok=True,last_socket_ok=True)
        f.row('ROM_write',sequence=sequence+2,address=0x9840,instruction_pc=0x2715,
              instruction_hex='9740',a=1,data=1,last_start=1,**tap)
        f.step(planned_start=1,last_start=1)
        f.row('ROM_write',sequence=sequence+3,address=0x9859,instruction_pc=0x2751,
              instruction_hex='9759',a=127,data=127,last_start=0,**tap)
        f.step()
        f.frame=SimpleNamespace(game_score=0,level_number=1,player_alive=False,num_lasers=2,lives=1,
                                start_pressed=False,done=False)
        def before_send(raw):
            self.assertTrue(f.journal.active[17]['known_start'])
            self.assertTrue(defs.codec.decode_response(raw)['latched'])
            self.assertEqual(f.cs['frames'],sequence+4)
        f.peer.before_send=before_send;f.initialized()
        self.assertTrue(f.proxy.handoff)
        self.assertEqual(len(f.journal.measurement_starts_path.read_text().splitlines()),1)
        old=json.loads(f.journal.games_path.read_text())
        self.assertFalse(old['known_start']);self.assertFalse(old['complete']);self.assertFalse(old['eligible'])

    def test_raw_ready_chain_order_subject_instructions_coin_response_and_failure_rejections(self):
        f=self.fixture();self.boot_and_coin(f);meta=f.step(status=243,player_count=2)
        rows=f.proxy.trace.rows(meta['event'])
        self.assertIsNotNone(boot_readiness(rows,meta))
        def find(kind,**fields):
            return next(i for i,r in enumerate(rows)if r['kind']==kind and all(r.get(k)==v for k,v in fields.items()))
        clear=find('ROM_write',instruction_pc=0xd137)
        init=find('ROM_write',instruction_pc=0xd184)
        coin=find('input_applied',coin=1)
        credit=find('ROM_write',instruction_pc=0x79c4)
        mutations=[(clear,'instruction_hex','0000'),(init,'data',0),(credit,'dp',0),
            (credit,'credit',2),(coin,'apply_ok',False),(coin,'socket_ok',False),
            (coin,'debug_bypass',True),(coin,'nonce','a'*64),(coin,'response_hex','00'*48),
            (coin,'event',rows[init]['event']-1),(credit,'sequence',meta['sequence']),
            (clear,'session','3'*32)]
        for index,key,value in mutations:
            changed=copy.deepcopy(rows);changed[index][key]=value
            with self.subTest(index=index,key=key):
                try:result=boot_readiness(changed,meta)
                except ValueError:result=None
                self.assertIsNone(result)
        for index in (clear,init,coin,credit):
            changed=copy.deepcopy(rows);changed.pop(index)
            self.assertIsNone(boot_readiness(changed,meta))
        changed=copy.deepcopy(rows);changed.insert(credit,copy.deepcopy(rows[credit]))
        self.assertIsNone(boot_readiness(changed,meta))
        for key,value in [('status',219),('credit',187),('wave',1),('reserves',2),('player_count',1)]:
            self.assertIsNone(boot_readiness(rows,dict(meta,**{key:value})))

    def test_parent_proxy_exact_inverse_and_both_original_raw_phase_findings(self):
        parent=(HERE/'full_startup_proxy_v1.py').read_text()
        source=(HERE/'full_startup_proxy_v2.py').read_text();ast.parse(source)
        old='import wire_codec_v1 as codec\n';new=old+'from boot_readiness_v1 import boot_readiness\n'
        old2="and meta['planned_start']==1 and (meta['status']&128)!=0 and meta['credit']>=1"
        new2="and meta['planned_start']==1 and meta['status']==243 and meta['credit']==1"
        old3='        if can_start:\n            self.issuer=authority.StartupHandoff'
        new3="        readiness=boot_readiness(self.trace.rows(meta['event']),meta)if can_start else None\n        can_start=bool(can_start and readiness is not None)\n        if can_start:\n            self.emit(dict(kind='original_boot_coin_readiness',sequence=sequence,readiness=readiness))\n            self.issuer=authority.StartupHandoff"
        self.assertEqual(source.replace(new3,old3).replace(new2,old2).replace(new,old),parent)
        run=defs.GAME/'logs/managed-learning-20261015/run-26'
        failure=json.loads((run/'full-policy-startup-CPU-real-original01-preparation-20261022/original-policy-loaded1200-no-accepted-start-failure-readback.json').read_bytes())
        self.assertEqual(failure['actual_runtime_exit'],1)
        self.assertEqual(failure['authorization']['sequence'],81)
        self.assertIsNone(boot_readiness([],dict(failure['authorization_raw_snapshot'],mode='gated')))
        prior=json.loads((run/'gated-start-initialized-boot-real-original01-preparation-20261022/original-full1200-initialized-ROM-gate-setup-clock-independent-readback.json').read_bytes())
        self.assertTrue(prior['diagnostic_ROM_START_gate_setup_and_order_verified'])
        self.assertEqual(prior['accepted_ROM_START_player_count_gate']['sequence'],770)
        self.assertLess(failure['authorization']['sequence'],failure['later_boot_status_initialization']['sequence'])


if __name__=='__main__':unittest.main(verbosity=2)
