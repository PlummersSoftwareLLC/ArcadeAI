"""New accumulated-credit scope; all previous original outcomes stay unchanged.

Prior test modules supply fixture definitions only. No consumed test methods,
scientific cohorts or original readers are executed by this contract.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('_accumulated_credit_fixture_defs',HERE/'test_boot_ready_proxy_v2.py')
definitions=importlib.util.module_from_spec(spec);sys.modules[spec.name]=definitions
spec.loader.exec_module(definitions)
defs=definitions.defs
import full_startup_proxy_v3 as bridge
from boot_readiness_v2 import boot_readiness


class AccumulatedCreditContract(unittest.TestCase):
    def fixture(self):
        f=defs.Fixture();self.addCleanup(f.close)
        f.proxy=bridge.StartupProxy(f.server,**f.subject,trace_path=f.path,trace_identity=f.identity,
            rom_sha256=hashlib.sha256(defs.ROM).hexdigest(),policy_reader=lambda:f.policy,
            admission_reader=lambda:f.window,frame_parser=lambda raw:copy.copy(f.frame),
            emit=f.logs.append,stop_event=defs.threading.Event(),wall_ns=lambda:f.wall,
            monotonic_ns=lambda:f.mono)
        f.proxy.cid=17
        return f

    def boot_and_coin(self,f):
        # Helper only: no old test method is called, discovered or retried.
        definitions.BootReadyProxyContract.boot_and_coin(self,f)

    def ready(self):
        f=self.fixture();self.boot_and_coin(f)
        meta=f.step(status=243,player_count=2,credit=2)
        return f,meta,f.proxy.trace.rows(meta['event'])

    def test_positive_packed_BCD_accumulation_and_invalid_current_credit_rejection(self):
        f,meta,rows=self.ready()
        for credit in (1,2,9,0x10,0x99):
            changed=copy.deepcopy(rows);changed[-1]['credit']=credit
            with self.subTest(credit=credit):
                result=boot_readiness(changed,dict(meta,credit=credit))
                self.assertIsNotNone(result)
                self.assertFalse(result['game_start_proven'])
                self.assertEqual(result['accepted_coin_STATUS']['credit'],1)
        for credit in (0,-1,True,False,1.,'2',0x0a,0x1a,0xa0,0xff):
            with self.subTest(invalid=repr(credit)):
                self.assertIsNone(boot_readiness(rows,dict(meta,credit=credit)))
        changed=copy.deepcopy(rows);changed[-1]['credit']=3
        with self.assertRaises(ValueError):boot_readiness(changed,meta)

    def test_earliest_coin_provenance_preserved_with_later_legitimate_handler_writes(self):
        f,meta,rows=self.ready()
        first=next(i for i,r in enumerate(rows)if r['kind']=='ROM_write'and r['instruction_pc']==0x79c4)
        later=copy.deepcopy(rows[first]);later.update(event=meta['event']-1,sequence=meta['sequence']-1,credit=2)
        changed=copy.deepcopy(rows);changed.insert(-1,later)
        result=boot_readiness(changed,meta)
        self.assertEqual(result['accepted_coin_STATUS']['event'],rows[first]['event'])
        # A later valid-looking write must not rescue a wrong first credit.
        changed[first]['credit']=2;later['credit']=1
        with self.assertRaises(ValueError):boot_readiness(changed,meta)
        coin=next(i for i,r in enumerate(rows)if r['kind']=='input_applied'and r['coin']==1)
        initialized=next(i for i,r in enumerate(rows)if r['kind']=='ROM_write'and r['instruction_pc']==0xd184)
        variants=[(coin,'apply_ok',False),(coin,'socket_ok',False),(coin,'nonce','a'*64),
            (coin,'debug_bypass',True),(coin,'response_hex','00'*48),
            (first,'credit',2),(first,'bank_entry',0),(initialized,'instruction_hex','0000')]
        for index,key,value in variants:
            changed=copy.deepcopy(rows);changed[index][key]=value
            with self.subTest(index=index,key=key),self.assertRaises(ValueError):boot_readiness(changed,meta)
        changed=copy.deepcopy(rows);changed.pop(coin)
        self.assertIsNone(boot_readiness(changed,meta))

    def test_actual_proxy_credit2_authorization_then_journal_before_latched_action(self):
        f=self.fixture()
        f.step(planned_start=1,status=219,credit=187,wave=171,reserves=99,player_count=187)
        self.assertIsNone(f.proxy.issuer)
        self.boot_and_coin(f);sequence=f.proxy.sequence+1
        f.step(planned_start=1,status=243,player_count=2,credit=2)
        a=f.proxy.issuer;self.assertIsNotNone(a);self.assertEqual(a.sequence,sequence)
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
            self.assertEqual(f.cs['frames'],sequence+4)
            self.assertTrue(f.journal.active[17]['known_start'])
            self.assertTrue(defs.codec.decode_response(raw)['latched'])
            self.assertEqual(len(f.journal.measurement_starts_path.read_text().splitlines()),1)
        f.peer.before_send=before_send;f.initialized();f.peer.before_send=lambda raw:None
        self.assertTrue(f.proxy.handoff)
        old=json.loads(f.journal.games_path.read_text())
        self.assertFalse(old['eligible']);self.assertFalse(old['complete']);self.assertFalse(old['known_start'])
        self.assertEqual(old['game_uid'],f.journal.active[17]['game_uid'])
        for response in f.peer.sent:self.assertEqual(defs.codec.decode_response(response)['action'],defs.ACTION)
        f.wall=f.window['close_unix_ns']+1;f.frame.player_alive=True
        f.step(mode='legacy',first_play_sequence=f.proxy.sequence+1,status=0,wave=1,reserves=2,
               current_player=1,player_count=1)
        self.assertTrue(f.journal.active[17]['known_start'])

    def test_new_predicate_on_original_raw_prefix_is_only_counterfactual_readiness(self):
        run=defs.GAME/'logs/managed-learning-20261015/run-26'
        case=run/'boot-ready-full-policy-CPU-real-original01-preparation-20261022'
        proof=json.loads((case/'original-policy-loaded1200-ready-credit-pulse-mismatch-readback.json').read_bytes())
        self.assertEqual(proof['actual_runtime_exit'],1);self.assertEqual(proof['journal_handoff_count'],0)
        entry=proof['original_files']['producer.jsonl'];path=Path(entry['path'])
        raw=path.read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256'])
        rows=[json.loads(line)for line in raw.splitlines()]
        snapshots={row['sequence']:row for row in rows if row['kind']=='snapshot'}
        for sequence in (81,667,668,669):
            meta=snapshots[sequence]
            self.assertIsNone(boot_readiness(rows[:meta['event']],meta))
        for sequence,credit in ((787,2),(907,3),(1147,5)):
            meta=snapshots[sequence];self.assertEqual(meta['credit'],credit)
            result=boot_readiness(rows[:meta['event']],meta)
            self.assertIsNotNone(result);self.assertEqual(result['accepted_coin_STATUS']['sequence'],678)
            self.assertFalse(result['game_start_proven'])
        parent=(HERE/'full_startup_proxy_v2.py').read_text()
        source=(HERE/'full_startup_proxy_v3.py').read_text()
        self.assertEqual(source.replace('from boot_readiness_v2 import boot_readiness',
            'from boot_readiness_v1 import boot_readiness').replace("meta['status']==243 and meta['credit']>=1",
            "meta['status']==243 and meta['credit']==1"),parent)
        # Readiness over archived bytes never changes the original disposition.
        self.assertEqual(json.loads((case/'controller-original-result.json').read_bytes())['actual_exit'],1)


if __name__=='__main__':unittest.main(verbosity=2)
