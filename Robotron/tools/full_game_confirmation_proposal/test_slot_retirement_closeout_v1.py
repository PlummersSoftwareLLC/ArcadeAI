"""Actual original quota64 journal plus synthetic child/proxy closeout fixtures."""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE=CHECK=None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


class Event:
    def __init__(self,value=True):self.value=value
    def is_set(self):return self.value


class CloseoutTests(unittest.TestCase):
    def setup_case(self):
        fixture=BASE.Fixture();self.addCleanup(fixture.close)
        drain=BASE.SOURCE.SlotQuotaRetirement(fixture.gate);fixture.complete_all();permit=drain.try_issue()
        actors={}
        for slot in CHECK.SLOTS:
            subject={k:v for k,v in fixture.bindings[slot].items()if k in ('slot','session','connection','nonce')}
            receipt=drain.for_slot(slot).authorize_slot(drain.for_slot(slot).permit,**subject,sequence=1201)
            physical_subject={k:v for k,v in subject.items()if k!='nonce'}
            summary=dict(sequence=1201,synthetic=True)
            ledger=SimpleNamespace(closed=True,sequence=1201,subject=physical_subject,
                stop_receipt=CHECK.canonical(receipt),summary=lambda summary=summary:copy.deepcopy(summary))
            proxy=SimpleNamespace(stop_receipt=receipt,stop_sent=Event(),peer_eof=Event(),prefix_verified=Event(),
                sent_complete=Event(),error=None,sequence=1201,subject=physical_subject,
                issuer=SimpleNamespace(nonce=subject['nonce']),ledger=ledger,final_ledger=summary)
            actors[slot]=dict(child=SimpleNamespace(poll=lambda:0),proxy=proxy)
        cohort=fixture.journal.cohort_status(fixture.controller.label,fixture.controller.start_ts,fixture.controller.close_ts)
        return fixture,drain,cohort,actors,json.loads(permit.payload),permit.identifier

    def verify(self,case):
        fixture,drain,cohort,actors,payload,identifier=case
        return CHECK.validate(drain,cohort,actors,drain_payload=payload,drain_identifier=identifier)

    def test_all32_real_receipts_join_original_all64_guard(self):
        case=self.setup_case();r=self.verify(case)
        self.assertTrue(r['complete']);self.assertEqual((r['selected_games'],r['slot_retirements']),(64,32))
        self.assertEqual(case[1].permit.used_slots,set())

    def test_missing_actor_cannot_shrink_denominator(self):
        case=self.setup_case();del case[3][4096]
        with self.assertRaises(ValueError):self.verify(case)

    def test_nonzero_running_and_boolean_child_exits_rejected(self):
        for value in [None,1,-15,False,True]:
            with self.subTest(value=value):
                case=self.setup_case();case[3][4096]['child'].poll=lambda:value
                with self.assertRaises(ValueError):self.verify(case)

    def test_incomplete_STOP_EOF_prefix_and_ledger_rejected(self):
        for name in ('stop_sent','peer_eof','prefix_verified','sent_complete'):
            with self.subTest(name=name):
                case=self.setup_case();getattr(case[3][4096]['proxy'],name).value=False
                with self.assertRaises(ValueError):self.verify(case)
        case=self.setup_case();case[3][4096]['proxy'].ledger.closed=False
        with self.assertRaises(ValueError):self.verify(case)

    def test_changed_cohort_and_changed_global_payload_rejected(self):
        case=self.setup_case();case[2]['rows'][0]['score']+=1
        with self.assertRaises(ValueError):self.verify(case)
        case=self.setup_case();case[4]['count']=63
        with self.assertRaises(ValueError):self.verify(case)

    def test_fabricated_global_used_slots_rejected(self):
        case=self.setup_case();case[1].permit.used_slots.add(4096)
        with self.assertRaises(ValueError):self.verify(case)

    def test_missing_actual_consumption_rejected(self):
        case=self.setup_case();del case[1]._receipts[4096]
        with self.assertRaises(ValueError):self.verify(case)

    def test_receipt_identity_sequence_and_ledger_tampering_rejected(self):
        for damage in ('nonce','sequence','receipt','ledger'):
            with self.subTest(damage=damage):
                case=self.setup_case();p=case[3][4096]['proxy']
                if damage=='nonce':p.issuer.nonce='f'*64
                elif damage=='sequence':p.sequence+=1
                elif damage=='receipt':p.stop_receipt=dict(p.stop_receipt,global_completion_claim=True)
                else:p.final_ledger={'forged':True}
                with self.assertRaises(ValueError):self.verify(case)

    def test_original_global_certificate_is_mandatory(self):
        case=self.setup_case();case[1].original.permit=None
        with self.assertRaises(ValueError):self.verify(case)


def main():
    global BASE,CHECK
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    BASE=load('_retirement_closeout_original_fixture',Path(__file__).with_name('test_slot_quota_retirement_v1.py'))
    BASE.GUARDS=BASE.load('_retirement_closeout_original_guard_defs',BASE.P/'test_fixed_slot64_drain_and_audit_v1.py')
    modules={key:BASE.GUARDS.load(key,path,sha)for key,(path,sha)in BASE.GUARDS.SOURCES.items()}
    BASE.Fixture=modules['fixture'].fixture_type(modules)
    BASE.SOURCE=BASE.load('_retirement_closeout_slot_authority',Path(__file__).with_name('slot_quota_retirement_v1.py'))
    CHECK=load('_retirement_closeout_checked_source',Path(__file__).with_name('slot_retirement_closeout_v1.py'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CloseoutTests))
    assert 'torch'not in sys.modules
    h=load('_retirement_closeout_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    report=dict(status='PASS'if result.wasSuccessful()else'FAIL',tests_run=result.testsRun,log=stream.getvalue(),
        errors=[dict(test=str(t),traceback=trace)for t,trace in result.errors],failures=[dict(test=str(t),traceback=trace)for t,trace in result.failures],
        source=h.pin(Path(CHECK.__file__)),test_source=h.pin(Path(__file__)),slot_authority=h.pin(Path(BASE.SOURCE.__file__)),
        original_dependencies={k:h.pin(p)for k,(p,sha)in BASE.GUARDS.SOURCES.items()},
        synthetic_child_proxy_and_ledger_fixture=True,actual_MAME_GPU_native_or_scientific_qualification=False,promotion=False)
    pin=h.put(args.output,report);print(json.dumps(dict(status=report['status'],tests_run=result.testsRun,errors=len(result.errors),failures=len(result.failures),report=pin)))
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':raise SystemExit(main())
