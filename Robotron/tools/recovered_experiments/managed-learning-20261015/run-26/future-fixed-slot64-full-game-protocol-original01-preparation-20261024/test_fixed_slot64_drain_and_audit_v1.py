"""Inactive engineering guards for actual quota64 journal/drain/audit objects.

Fixtures have synthetic policy, clocks and ROM. No scientific score or runtime
claim follows. Run only through the subsequently pinned original CPU scope,
after the current scientific sequence and every original scope have closed.
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
PROFILE=ROOT/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn'
HERE=Path(__file__).resolve().parent
SOURCES={
    'journal':(PROFILE/'game_journal.py','96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f'),
    'measurement':(PROFILE/'managed_measurement.py','9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6'),
    'startup':(ROOT/'tools/startup_policy_journal_proposal/startup_handoff_v2.py','d3670ee778682d3d2d40c069b0f56fe389c4b3b474c34e48b886fc89142e732e'),
    'view':(HERE/'fixed_slot_cohort_view_v1.py','494dcdbcb0ae30f95f4724435e6bf61c68bec3aa7fc3705e39636c0ba60ddbd0'),
    'drain':(HERE/'fixed_slot_cohort_drain_v1.py','ecd278045df06736ed59c16c6293e6a220968cfb89d38820ae9b2117be075f7b'),
    'audit':(HERE/'audit_fixed_slot64_games_v1.py','89405d07f20e1c43c51fdd7b7cf103418353d9740cbf040adee0f35b70de2c91'),
    'fixture':(HERE/'fixed_slot64_engineering_fixture_v1.py','75978ddc1476bf9f97052b8d0acdc55254d6f728882798ca218732e97015703b'),
}


def load(name,path,sha):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
        raise ValueError('Original engineering input changed: '+str(path))
    name='quota64_drain_audit_engineering_'+name
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def guard_suite(modules):
    Fixture=modules['fixture'].fixture_type(modules)
    audit,drain=modules['audit'],modules['drain']
    slots=list(range(4096,4128))

    class Guards(unittest.TestCase):
        def fixture(self):
            fixture=Fixture()
            self.addCleanup(fixture.close)
            return fixture

        def test_first_round_and_fast_third_never_authorize_early_stop(self):
            f=self.fixture()
            self.assertIsNone(f.gate.try_issue())
            f.complete_game(4096)
            f.complete_game(4096,score=99999999)
            f.complete_game(4096,score=99999999)
            f.controller.tick()
            self.assertIsNone(f.gate.try_issue())
            status=f.journal.cohort_status(f.controller.label,f.controller.start_ts,f.controller.close_ts)
            self.assertEqual(status['started'],33)
            self.assertFalse(status['closed'])
            self.assertGreaterEqual(len(status['retained_outside_cohort_ids']),2)

        def test_all_quotas_close_before_outer_horizon_with_all_tails_pending(self):
            f=self.fixture()
            for slot in slots:f.complete_game(slot)
            status=f.controller.tick()
            self.assertEqual(status['phase'],'draining')
            self.assertEqual((status['started'],status['count'],status['pending']),(64,32,32))
            self.assertLess(f.wall,f.window['close_unix_ns'])
            self.assertIsNone(f.gate.try_issue())
            self.assertEqual(len(f.gate.frozen_ids),64)

        def test_all64_actual_terminal_joins_allow_one_stop_per_original_slot(self):
            f=self.fixture()
            f.complete_all()
            self.assertLess(f.wall,f.window['close_unix_ns'])
            permit=f.gate.try_issue()
            body=json.loads(permit.payload)
            self.assertEqual(body['count'],64)
            self.assertEqual(body['cohort_selection'],drain.COHORT_SELECTION)
            self.assertFalse(body['quality_qualified'])
            self.assertEqual(len({r['journal_game_id']for r in body['original_subjects']}),32)
            receipts=[f.authorize(permit,slot)for slot in slots]
            self.assertEqual(len(receipts),32)
            self.assertEqual(len(permit.used_slots),32)
            with self.assertRaises(ValueError):f.authorize(permit,slots[0])
            self.assertEqual(f.gate.state,'failed')

        def test_abandoned_selected_member_cannot_be_replaced(self):
            f=self.fixture()
            f.journal.disconnect(slots[0]-4000,lambda:f.context)
            status=f.controller.tick()
            self.assertFalse(status['valid'])
            self.assertEqual(status['reason'],'abandoned_cohort_game')
            with self.assertRaises(ValueError):f.gate.try_issue()
            self.assertIsNone(f.gate.permit)

        def test_deadline_invalidates_missing_quota_without_stop_permission(self):
            f=self.fixture()
            f.advance(21600*1000000000)
            status=f.controller.tick()
            self.assertFalse(status['valid'])
            self.assertEqual(status['reason'],'whole_cohort_timeout')
            with self.assertRaises(ValueError):f.gate.try_issue()
            self.assertIsNone(f.gate.permit)

        def test_certificate_policy_selection_binding_cannot_change(self):
            f=self.fixture()
            f.policy['cohort_selection']['expected_games']=63
            with self.assertRaises(ValueError):f.gate.try_issue()
            self.assertEqual(f.gate.state,'failed')

        def test_independent_raw_audit_preserves64_zeroes_and_all_terminal_life_links(self):
            f=self.fixture()
            f.complete_all()
            args=f.closed_payloads()
            result=audit.review(**args)
            self.assertEqual(result['statistics']['count'],64)
            self.assertEqual(result['statistics']['score_sum'],99200)
            self.assertEqual(result['statistics']['mean'],1550)
            self.assertEqual(len(result['terminal_links']),64)
            self.assertEqual(len(result['rom_links']),64)
            self.assertEqual(sum(r['verified_lives']for r in result['life_links']),64)
            self.assertEqual(result['slot_admitted_counts'],{s:2 for s in slots})
            self.assertFalse(result['quality_qualified'])
            self.assertFalse(result['full_game_score_verified'])
            self.assertFalse(result['promotion'])

        def test_new_outside_starts_do_not_replace_members_or_race_terminal_stop(self):
            f=self.fixture()
            f.complete_all()
            # The terminal controller snapshot is frozen; a later outside game
            # may still reset before the host completes its32 STOP exchanges.
            f.complete_game(slots[0],score=99999999)
            permit=f.gate.try_issue()
            self.assertEqual(json.loads(permit.payload)['count'],64)
            f.complete_game(slots[1],score=88888888)
            self.assertTrue(f.authorize(permit,slots[0])['consumed_before_send'])
            result=audit.review(**f.closed_payloads())
            self.assertEqual(result['statistics']['score_sum'],99200)
            self.assertGreaterEqual(len(result['retained_outside_start_ids']),34)

        def test_snapshot_equivalence_only_accepts_append_only_outside_records(self):
            base=dict(started_ids=['run:1'],rows=[dict(score=0)],count=1,
                      retained_outside_cohort_ids=['run:2'])
            fresh=copy.deepcopy(base)
            fresh['retained_outside_cohort_ids'].append('run:3')
            self.assertTrue(drain.same_completed_membership(base,fresh))
            for damage in ('member','score','outside_delete','outside_reorder','outside_duplicate'):
                changed=copy.deepcopy(fresh)
                if damage=='member':changed['started_ids']=['run:9']
                elif damage=='score':changed['rows'][0]['score']=1
                elif damage=='outside_delete':changed['retained_outside_cohort_ids']=[]
                elif damage=='outside_reorder':changed['retained_outside_cohort_ids'].reverse()
                else:changed['retained_outside_cohort_ids'].append('run:3')
                with self.subTest(damage=damage):
                    self.assertFalse(drain.same_completed_membership(base,changed))

        def test_raw_membership_uses_occurrence_order_instead_of_finish_order(self):
            rows=[]
            for ordinal,slot in enumerate(slots*3,1):
                rows.append(dict(journal_game_id='123:'+str(ordinal),experiment='fixture',
                    known_start=True,measurement_active=True,client_slot=slot,start_unix_s=5.0,
                    score=99999999 if ordinal>64 else 0))
            first,counts,outside=audit.select_original_starts(rows,'fixture',0,100,source_is_start_order=True)
            other,other_counts,other_outside=audit.select_original_starts(
                list(reversed(rows)),'fixture',0,100,source_is_start_order=False)
            self.assertEqual(list(first),list(other))
            self.assertEqual(counts,other_counts)
            self.assertEqual(outside,other_outside)
            self.assertEqual(len(first),64)
            self.assertEqual(outside,[r['journal_game_id']for r in rows[64:]])
            with self.assertRaises(ValueError):
                audit.select_original_starts(list(reversed(rows)),'fixture',0,100,source_is_start_order=True)

        def test_missing_tail_life_or_start_and_changed_terminal_statistics_fail_audit(self):
            f=self.fixture()
            f.complete_all()
            original=f.closed_payloads()
            target=original['cohort']['started_ids'][0]
            for damage in ('game','life','start','terminal','statistics','selection','cohort_order'):
                args=copy.deepcopy(original)
                if damage in ('game','life','start','terminal'):
                    name={'game':'games.jsonl','life':'lives.jsonl','start':'measurement_starts.jsonl',
                          'terminal':'games.jsonl'}[damage]
                    rows=audit.lines(args['payloads'][name])
                    if damage=='terminal':
                        for row in rows:
                            if row['journal_game_id']==target:
                                row['terminal_confirmation']['previous_score']+=1
                    else:rows=[r for r in rows if r['journal_game_id']!=target]
                    args['payloads'][name]=b''.join(audit.canonical(r)+b'\n'for r in rows)
                elif damage=='statistics':args['cohort']['mean']+=1
                elif damage=='selection':args['policy']['cohort_selection']['games_per_slot']=1
                else:args['cohort']['started_ids'].reverse()
                with self.subTest(damage=damage),self.assertRaises(ValueError):audit.review(**args)

    return unittest.defaultTestLoader.loadTestsFromTestCase(Guards)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-guards',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.run_guards or args.output is None:
        parser.error('Explicit --run-guards and a new --output are required')
    if args.output.exists():raise FileExistsError(args.output)
    modules={name:load(name,*entry)for name,entry in SOURCES.items()}
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(guard_suite(modules))
    report=dict(schema='robotron-fixed-slot64-drain-audit-engineering-guards-v1',
                engineering_fixtures_only=True,quality_qualified=False,
                runtime_validity_verified=False,full_game_score_verified=False,
                tests_run=result.testsRun,successful=result.wasSuccessful(),
                failures=len(result.failures),errors=len(result.errors),
                source_sha256={name:entry[1]for name,entry in SOURCES.items()},
                unittest_output=stream.getvalue())
    with args.output.open('x')as handle:
        os.fchmod(handle.fileno(),0o444)
        json.dump(report,handle,indent=2,allow_nan=False)
        handle.write('\n');handle.flush();os.fsync(handle.fileno())
    print(json.dumps({k:report[k]for k in ('tests_run','successful','failures','errors',
                                        'engineering_fixtures_only','quality_qualified')}))
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':
    raise SystemExit(main())
