"""CPU contracts for actual gate-body archival and exact independent replay.

Uses the original real journal/quota authority; process/socket fixtures remain
synthetic. The new replay guard is exercised verbatim from the frozen source.
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import textwrap
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--directory',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    here=Path(__file__).parent
    old=load('_archival_original_closeout_tests',here/'test_slot_retirement_closeout_v1.py')
    base=load('_archival_original_gate_tests',here/'test_slot_quota_retirement_v1.py')
    base.GUARDS=base.load('_archival_original_guard_defs',base.P/'test_fixed_slot64_drain_and_audit_v1.py')
    modules={k:base.GUARDS.load(k,p,sha)for k,(p,sha)in base.GUARDS.SOURCES.items()}
    base.Fixture=modules['fixture'].fixture_type(modules)
    base.SOURCE=base.load('_archival_original_slot_authority',here/'slot_quota_retirement_v1.py')
    old.BASE=base;old.CHECK=load('_archival_full_body_closeout',args.directory/'slot_retirement_closeout_v2.py')
    wire=load('_archival_full_body_wire',args.directory/'audit_fullgame_slot_wire_v2.py')
    generator=load('_archival_body_generator',here/'prepare_slot_permit_archival_v1.py')
    assert Path(wire.__file__).read_text().count(generator.REPLAY_CHECKS)==1
    replay=compile(textwrap.dedent(generator.REPLAY_CHECKS),'<exact-independent-slot-body-replay>','exec')

    class ArchivalTests(old.CloseoutTests):
        def replay(self,case,record,receipt=None):
            fixture,drain,cohort,actors,payload,identifier=case;slot=4096
            rows=sorted([r for r in cohort['rows']if r['client_slot']==slot],key=lambda r:(r['start_unix_s'],r['journal_game_id']))
            registration=drain.original.registrations[slot]
            env=dict(slot_permit_record=record,receipt=receipt or actors[slot]['proxy'].stop_receipt,
                subject={k:registration[k]for k in ('slot','session','connection')},ordered=rows,
                ids=[r['journal_game_id']for r in rows],registration=registration,
                policy=drain.original.policy,window=drain.original.window,
                require=old.CHECK.require,hashlib=hashlib,canonical=old.CHECK.canonical)
            exec(replay,env)

        def test_archived_bodies_rehash_to_all32_original_consumed_commitments(self):
            case=self.setup_case();result=self.verify(case)
            for row in result['slots']:
                record=row['full_slot_permit'];receipt=row['STOP_receipt']
                self.assertEqual(hashlib.sha256(old.CHECK.canonical(record['body'])).hexdigest(),record['identifier'])
                self.assertEqual(record['identifier'],receipt['permit_identifier'])
            self.replay(case,result['slots'][0]['full_slot_permit'])

        def test_missing_changed_or_unconsumed_original_payload_cannot_be_archived(self):
            for damage in ('missing','changed','unconsumed'):
                with self.subTest(damage=damage):
                    case=self.setup_case();permit=case[1]._permits[4096]
                    if damage=='missing':del case[1]._permits[4096]
                    elif damage=='changed':permit.payload+=b' '
                    else:permit.used=False
                    with self.assertRaises((ValueError,KeyError)):self.verify(case)

        def test_independent_replay_rejects_forged_body_policy_pair_timing_or_count(self):
            for damage in ('hash','policy','pair','time','count'):
                with self.subTest(damage=damage):
                    case=self.setup_case();record=copy.deepcopy(self.verify(case)['slots'][0]['full_slot_permit'])
                    receipt=copy.deepcopy(case[3][4096]['proxy'].stop_receipt)
                    if damage=='hash':record['identifier']='f'*64
                    else:
                        if damage=='policy':record['body']['policy']['training_steps']+=1
                        elif damage=='pair':record['body']['selected_game_ids'].reverse()
                        elif damage=='time':record['body']['issued_unix_ns']=receipt['authorized_unix_ns']+1
                        else:record['body']['global_completed_at_issue']=1
                        record['identifier']=hashlib.sha256(old.CHECK.canonical(record['body'])).hexdigest()
                        receipt['permit_identifier']=record['identifier']
                    with self.assertRaises(ValueError):self.replay(case,record,receipt)

        def test_returned_archive_cannot_mutate_original_permit_objects(self):
            case=self.setup_case();result=self.verify(case)
            result['slots'][0]['full_slot_permit']['body']['global_expected_games']=1
            self.assertEqual(self.verify(case)['slots'][0]['full_slot_permit']['body']['global_expected_games'],64)

    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ArchivalTests))
    assert 'torch'not in sys.modules
    h=load('_archival_CPU_report_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    report=h.put(args.output,dict(status='PASS'if r.wasSuccessful()else'FAIL',tests_run=r.testsRun,log=stream.getvalue(),
        failures=[dict(test=str(t),traceback=v)for t,v in r.failures],errors=[dict(test=str(t),traceback=v)for t,v in r.errors],
        sources=dict(closeout=h.pin(Path(old.CHECK.__file__)),wire_audit=h.pin(Path(wire.__file__)),generator=h.pin(Path(generator.__file__)),test=h.pin(Path(__file__))),
        exact_independent_replay_guard_executed_verbatim=True,original_real_quota64_journal_and_authority_used=True,
        child_socket_and_ledger_fixtures_synthetic=True,actual_MAME_GPU_or_scientific_qualification=False,promotion=False))
    print(json.dumps(dict(status='PASS'if r.wasSuccessful()else'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),report=report)))
    return 0 if r.wasSuccessful()else 1


if __name__=='__main__':raise SystemExit(main())
