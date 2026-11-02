"""CPU contracts using the unchanged real quota64 journal/controller/drain.

Synthetic policy/ROM/clocks; no MAME, GPU, live service or scientific job.
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024'
GUARDS=Fixture=SOURCE=None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


class SlotQuotaTests(unittest.TestCase):
    def fixture(self):
        fixture=Fixture();self.addCleanup(fixture.close)
        return fixture,SOURCE.SlotQuotaRetirement(fixture.gate)

    def issue_one(self):
        fixture,gate=self.fixture()
        fixture.complete_game(4096,score=1000);fixture.complete_game(4096,score=2000);fixture.controller.tick()
        self.assertIsNone(gate.try_issue())
        permit=gate.for_slot(4096).permit;self.assertIsNotNone(permit)
        return fixture,gate,permit

    def authorize(self,fixture,gate,permit,slot=4096,**changes):
        data={k:v for k,v in fixture.bindings[slot].items()if k in ('slot','session','connection','nonce')}
        data['sequence']=1201;data.update(changes)
        return gate.for_slot(slot).authorize_slot(permit,**data)

    def test_one_finished_game_cannot_satisfy_the_required_two(self):
        fixture,gate=self.fixture();self.assertIsNone(gate.try_issue())
        fixture.complete_game(4096,score=1000);fixture.controller.tick();self.assertIsNone(gate.try_issue())
        self.assertIsNone(gate.for_slot(4096).permit)

    def test_slot_retires_before_other_games_without_claiming_global_completion(self):
        fixture,gate,permit=self.issue_one();body=json.loads(permit.payload)
        self.assertEqual((body['global_expected_games'],body['global_completed_at_issue']),(64,2))
        self.assertEqual(len(body['selected_game_ids']),2);self.assertFalse(body['global_completion_claim'])
        receipt=self.authorize(fixture,gate,permit)
        self.assertTrue(receipt['consumed_before_send']);self.assertFalse(receipt['global_completion_claim'])
        self.assertIsNone(gate.permit);self.assertEqual(set(gate.slot_stop_receipts),{4096})
        self.assertIsNone(gate.for_slot(4097).permit)

    def test_slow_selected_tails_remain_required_after_an_early_slot_stops(self):
        fixture,gate=self.fixture()
        for slot in SOURCE.SLOTS:fixture.complete_game(slot,score=1000)
        fixture.controller.tick();self.assertIsNone(gate.try_issue())
        fixture.complete_game(4096,score=2000);fixture.controller.tick();self.assertIsNone(gate.try_issue())
        self.authorize(fixture,gate,gate.for_slot(4096).permit)
        for slot in SOURCE.SLOTS[1:]:fixture.complete_game(slot,score=2000)
        fixture.controller.tick();global_permit=gate.try_issue()
        self.assertIsNotNone(global_permit);body=json.loads(global_permit.payload)
        self.assertEqual((body['started'],body['count']),(64,64))
        self.assertEqual(len(set(body['started_ids'])),64)
        self.assertEqual(global_permit.used_slots,set())

    def test_all64_original_guard_and_32_distinct_stop_receipts_both_required(self):
        fixture,gate=self.fixture();fixture.complete_all();global_permit=gate.try_issue()
        for slot in SOURCE.SLOTS:self.authorize(fixture,gate,gate.for_slot(slot).permit,slot)
        self.assertEqual(set(gate.slot_stop_receipts),set(SOURCE.SLOTS))
        self.assertEqual(global_permit.used_slots,set())
        self.assertEqual(json.loads(global_permit.payload)['count'],64)
        ids=[jid for receipt in gate.slot_stop_receipts.values()for jid in receipt['selected_game_ids']]
        self.assertEqual(len(ids),len(set(ids)));self.assertEqual(set(ids),set(json.loads(global_permit.payload)['started_ids']))

    def test_duplicate_stop_permanently_invalidates_authority(self):
        fixture,gate,permit=self.issue_one();self.authorize(fixture,gate,permit)
        with self.assertRaises(ValueError):self.authorize(fixture,gate,permit)
        self.assertEqual(gate.state,'failed')
        with self.assertRaises(ValueError):gate.try_issue()

    def test_foreign_nonce_or_wrong_slot_view_cannot_consume_a_permit(self):
        for damage in ('nonce','slot'):
            with self.subTest(damage=damage):
                fixture,gate,permit=self.issue_one()
                data={k:v for k,v in fixture.bindings[4096].items()if k in ('slot','session','connection','nonce')};data['sequence']=1201
                if damage=='nonce':data['nonce']='e'*64
                else:data['slot']=4097
                with self.assertRaises(ValueError):gate.for_slot(4096).authorize_slot(permit,**data)
                self.assertEqual(gate.state,'failed');self.assertFalse(permit.used)

    def test_completed_rows_cannot_change_after_issue(self):
        fixture,gate,permit=self.issue_one();jid=json.loads(permit.payload)['selected_game_ids'][0]
        fixture.journal.measurement_games[jid]['result']['score']+=1
        with self.assertRaises(ValueError):self.authorize(fixture,gate,permit)
        self.assertEqual(gate.state,'failed')

    def test_rehashed_forged_payload_is_not_the_original_commitment(self):
        fixture,gate,permit=self.issue_one();body=json.loads(permit.payload);body['required_complete_games_this_slot']=1
        permit.payload=SOURCE.canonical(body);permit.identifier=hashlib.sha256(permit.payload).hexdigest()
        with self.assertRaises(ValueError):self.authorize(fixture,gate,permit)
        self.assertFalse(permit.used)

    def test_third_game_cannot_replace_an_invalid_selected_game(self):
        fixture,gate=self.fixture();fixture.complete_game(4096,score=1000);fixture.complete_game(4096,score=2000)
        fixture.complete_game(4096,score=99999999)
        selected=fixture.journal.cohort_status(fixture.controller.label,fixture.controller.start_ts,fixture.controller.close_ts)
        second=[r for r in selected['rows']if r['client_slot']==4096][1]
        fixture.journal.measurement_games[second['journal_game_id']]['mixed_experiment']=True
        fixture.controller.tick()
        with self.assertRaises(ValueError):gate.try_issue()
        self.assertIsNone(gate.for_slot(4096).permit)

    def test_changed_frozen_policy_or_expired_unfilled_quota_fails(self):
        fixture,gate,permit=self.issue_one();fixture.policy['optimized_samples']+=1
        with self.assertRaises(ValueError):self.authorize(fixture,gate,permit)
        fixture,gate=self.fixture();fixture.advance(fixture.window['close_unix_ns']-fixture.wall+1_000_000);fixture.controller.tick()
        with self.assertRaises(ValueError):gate.try_issue()
        self.assertEqual(gate.state,'failed')

    def test_only_the_original_source_bound_parent_can_be_wrapped(self):
        with self.assertRaises(ValueError):SOURCE.SlotQuotaRetirement(object())


def main():
    global GUARDS,Fixture,SOURCE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    GUARDS=load('_slot_quota_original_guard_defs',P/'test_fixed_slot64_drain_and_audit_v1.py')
    modules={key:GUARDS.load(key,path,sha)for key,(path,sha)in GUARDS.SOURCES.items()}
    Fixture=modules['fixture'].fixture_type(modules)
    SOURCE=load('_new_slot_quota_retirement',Path(__file__).with_name('slot_quota_retirement_v1.py'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SlotQuotaTests))
    assert 'torch'not in sys.modules
    h=load('_slot_retirement_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    report=dict(status='PASS'if result.wasSuccessful()else'FAIL',tests_run=result.testsRun,
        failures=[dict(test=str(test),traceback=trace)for test,trace in result.failures],
        errors=[dict(test=str(test),traceback=trace)for test,trace in result.errors],log=stream.getvalue(),
        source=h.pin(Path(__file__).with_name('slot_quota_retirement_v1.py')),test_source=h.pin(Path(__file__)),
        original_dependencies={key:h.pin(path)for key,(path,sha)in GUARDS.SOURCES.items()},
        same_original_quota64_global_guard_retained=True,global_used_slot_history_not_fabricated=True,
        native_integration_or_MAME_GPU_or_scientific_run_launched=False,live_controls_changed=False,promotion=False)
    pin=h.put(args.output,report)
    print(json.dumps(dict(status=report['status'],tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),report=pin)))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
