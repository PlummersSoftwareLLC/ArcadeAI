"""New registered-module integration scope after original8 fixture failure.

Only fixture definitions are imported; none of the eight consumed original
test methods is invoked. The proxy and authority sources are unchanged.
"""
from pathlib import Path
import importlib.util
import json
import sys
import unittest

HERE=Path(__file__).resolve().parent
path=HERE/'test_full_startup_proxy_v1.py'
spec=importlib.util.spec_from_file_location('_consumed_proxy_fixture_definitions',path)
definitions=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=definitions
spec.loader.exec_module(definitions)
# inspect.getsourcefile needs the actual fixture class's defining module.
sys.modules[definitions.base.__name__]=definitions.base
codec=definitions.codec


class RegisteredProxyIntegration(unittest.TestCase):
    def fixture(self):
        f=definitions.Fixture();self.addCleanup(f.close);return f

    def test_registered_journal_transaction_and_original_bytes_through_closed_admission(self):
        f=self.fixture();f.authorized();seen=[]
        def check(response):
            value=codec.decode_response(response)
            self.assertEqual(value['action'],definitions.ACTION)
            self.assertEqual(f.cs['frames'],5)
            self.assertTrue(value['latched'])
            self.assertTrue(f.journal.active[17]['known_start'])
            starts=[json.loads(line)for line in f.journal.measurement_starts_path.read_text().splitlines()]
            self.assertEqual(len(starts),1)
            self.assertEqual(starts[0]['journal_game_id'],f.journal.active[17]['journal_game_id'])
            seen.append(value)
        f.peer.before_send=check;f.initialized();self.assertEqual(len(seen),1)
        f.peer.before_send=lambda response:None
        certificate=next(row for row in f.logs if row['kind']=='actual_policy_journal_handoff')['certificate']
        self.assertEqual(certificate['evidence']['origin_acceptance']['accepted_frames'],5)
        self.assertEqual(certificate['evidence']['gate']['sequence'],3)
        self.assertEqual(certificate['evidence']['setup']['sequence'],4)
        self.assertEqual(certificate['evidence']['setup']['last_start'],0)
        old=json.loads(f.journal.games_path.read_text())
        self.assertFalse(old['known_start']);self.assertFalse(old['eligible']);self.assertFalse(old['complete'])
        self.assertEqual(old['score'],100);self.assertEqual(old['max_level'],88)
        self.assertNotEqual(old['journal_game_id'],f.journal.active[17]['journal_game_id'])
        self.assertEqual(old['game_uid'],f.journal.active[17]['game_uid'])
        self.assertIsNone(f.journal.active[17]['terminal_confirmation'])
        f.wall=f.window['close_unix_ns']+1
        f.frame.player_alive=True;f.frame.game_score=400
        f.step(mode='legacy',first_play_sequence=6,status=0,wave=1,reserves=2,
               current_player=1,player_count=1,planned_coin=1)
        self.assertEqual(codec.decode_response(f.peer.sent[-1])['coin'],1)
        for response in f.peer.sent:self.assertEqual(codec.decode_response(response)['action'],definitions.ACTION)
        status=f.journal.cohort_status('proxy-contract',999,1010)
        self.assertEqual((status['started'],status['count'],status['pending']),(1,0,1))

    def test_registered_origin_rejection_preserves_unknown_until_later_real_acceptance(self):
        f=self.fixture();f.authorized();f.origin.accept=False;f.initialized();f.no_handoff()
        self.assertFalse(codec.decode_response(f.peer.sent[-1])['latched'])
        f.origin.accept=True;f.initialized()
        receipt=next(row for row in f.logs if row['kind']=='actual_policy_journal_handoff')
        origin=receipt['certificate']['evidence']['origin_acceptance']
        self.assertEqual((origin['frame_sequence'],origin['accepted_frames']),(6,5))
        self.assertTrue(f.journal.active[17]['known_start'])
        self.assertEqual(len([r for r in f.logs if r['kind']=='actual_policy_journal_handoff']),1)
        f.journal.disconnect(17,lambda:f.context)
        rows=[json.loads(line)for line in f.journal.games_path.read_text().splitlines()]
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[1]['known_start']);self.assertFalse(rows[1]['complete']);self.assertFalse(rows[1]['eligible'])

    def test_registered_fixture_rejects_bad_ROM_chain_policy_deadline_and_actual_send(self):
        f=self.fixture();f.proxy.trace.expected_rom_sha256='a'*64
        with self.assertRaises(ValueError):f.step(planned_start=1)
        f.no_handoff();self.assertEqual(f.peer.sent,[])
        for change in ({'apply_ok':False},{'socket_ok':False},{'debug_bypass':True},
                       {'held_start_before_response':True}):
            f=self.fixture();f.authorized(change);sent=len(f.peer.sent)
            with self.subTest(application=change),self.assertRaises(ValueError):f.initialized()
            f.no_handoff();self.assertEqual(len(f.peer.sent),sent)
        for changed in ('policy','cutoff','duplicate_gate','play','nonce'):
            f=self.fixture();f.authorized();sent=len(f.peer.sent)
            if changed=='policy':f.policy['policy_load_id']='c'*64
            if changed=='cutoff':f.wall=f.window['close_unix_ns']
            if changed=='duplicate_gate':
                f.row('ROM_write',sequence=1,nonce='0'*64,address=0x9840,instruction_pc=0x2715,
                      dp=0x98,bank_entry=1)
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                if changed=='play':f.step(first_play_sequence=5)
                elif changed=='nonce':f.step(nonce='c'*64)
                else:f.initialized()
            f.no_handoff();self.assertEqual(len(f.peer.sent),sent)
        f=self.fixture()
        def failed_send(response):raise OSError('original send failed')
        f.peer.before_send=failed_send
        with self.assertRaises(OSError):f.step(planned_start=1)
        self.assertEqual(f.proxy.issuer.state,'failed');f.no_handoff()


if __name__=='__main__':unittest.main(verbosity=2)
