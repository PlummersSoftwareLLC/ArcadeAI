"""Explicit CPU contracts for derived timing, checkpoints and unchanged guards.

Default inert. The legacy tests run against the actual derived modules, with
only a horizon field added to the legacy audit fixture's job schema.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
C=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
LEGACY=G/'logs/managed-learning-20261015/run-26/deadline-score60min-protocol-original01-preparation-20261026'
REC=REP=AUD=NATIVE=CTL=OUTER=FIX=OLD_AUD=OLD_REPORT=H=MANIFEST=ORIGINAL_JOB=ORIGINAL_SELECTION=METADATA=None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def ready(horizon=600_000_000_000,offsets=(300_000_000_000,)):
    clock=FIX.Clock();rec=REC.DeadlineScoreRecorder(clock_ns=clock,horizon_ns=horizon,checkpoint_offsets_ns=offsets)
    rec.positively_retired_slots=set()
    for slot in REC.SLOTS:
        rec.bind(slot,FIX.member(slot));rec.observe(slot,FIX.sample(slot,clock.now))
    anchor=rec.arm(FIX.readiness())
    return rec,clock,anchor


def feed(rec,clock,stamp,sequence,before,score,skip=None,process_time=None):
    clock.now=stamp if process_time is None else process_time
    for slot in REC.SLOTS:
        if slot!=skip:rec.observe(slot,FIX.sample(slot,stamp,sequence=sequence,before=before,score=score))


@contextmanager
def subject(horizon=600_000_000_000):
    with tempfile.TemporaryDirectory(prefix='duration-CPU-fixture-',dir=C)as directory:
        root=Path(directory);job=deepcopy(ORIGINAL_JOB);selection=deepcopy(ORIGINAL_SELECTION)
        job.update(runtime=MANIFEST['sources']['native'],components=MANIFEST['components'],horizon_ns=horizon,
            output=str(root/'unused-native-output'),checkpoint_offsets_ns=[n for n in REC.CHECKPOINT_OFFSETS_NS if n<horizon])
        selection.update(screen_horizon_ns=horizon,checkpoint_offsets_ns=deepcopy(job['checkpoint_offsets_ns']),
            short_screen_is_promotion_evidence=False,
            private_protocol_sources=dict(runtime=job['runtime'],lua=job['lua']))
        yield root,job,selection


def bind_selection(root,job,selection):
    job['screen_selection']=H.put(root/'selection.json',selection)


class DurationContracts(unittest.TestCase):
    def test_all_supported_deadlines_and_real_score_audits(self):
        original_fixture=OLD_AUD.Tests._original_fixture
        for horizon in REC.SUPPORTED_HORIZONS_NS:
            with self.subTest(horizon=horizon):
                fake_core=SimpleNamespace(SLOTS=REC.SLOTS,DeadlineScoreRecorder=lambda **kw:REC.DeadlineScoreRecorder(horizon_ns=horizon,**kw))
                with patch.object(OLD_AUD,'core',fake_core):values=original_fixture(OLD_AUD.Tests())
                values[0]['horizon_ns']=horizon
                result=AUD.audit(*values)
                self.assertEqual(values[2]['deadline_monotonic_ns']-values[2]['anchor_monotonic_ns'],horizon)
                self.assertEqual(result['n_scored'],32)
                self.assertIn(f'{horizon//60_000_000_000}-MINUTE',REP.format_console(values[2]))

    def test_rejects_untyped_unknown_or_ambiguous_schedules(self):
        for horizon in (True,600.0,0,-1,1_200_000_000_000):
            with self.subTest(horizon=horizon),self.assertRaises(ValueError):REC.DeadlineScoreRecorder(horizon_ns=horizon)
        for offsets in ([300_000_000_000.0],[True],[300_000_000_000]*2,[600_000_000_000],[900_000_000_000,300_000_000_000]):
            with self.subTest(offsets=offsets),self.assertRaises(ValueError):REC.DeadlineScoreRecorder(horizon_ns=600_000_000_000,checkpoint_offsets_ns=offsets)

    def test_checkpoint_credits_last_before_target_not_future_score_and_final_continues(self):
        rec,clock,anchor=ready();target=anchor['anchor_monotonic_ns']+300_000_000_000
        feed(rec,clock,target-1,1202,10,200);feed(rec,clock,target+1,1203,11,999)
        clock.now=target+2;record=rec.take_checkpoints(clock.now)[0]
        self.assertEqual((record['n_scored'],record['mean_score']),(32,200))
        self.assertTrue(all(r['score_witness']['completed_exchange_ns']<=target<r['first_post_horizon_activity']['completed_exchange_ns']for r in record['rows']))
        self.assertTrue(record['repeated_looks_are_not_independent_games']);self.assertFalse(record['automatic_decision'])
        self.assertEqual(rec.take_checkpoints(clock.now),[])
        deadline=anchor['deadline_monotonic_ns'];feed(rec,clock,deadline-1,1204,12,1000)
        clock.now=deadline+2;final=rec.seal(clock.now,barrier=dict(deadline_monotonic_ns=deadline,no_new_origin_entries=True,inflight=0,closed_monotonic_ns=deadline+1))
        self.assertEqual((final['mean_score'],final['horizon_ns']),(1000,600_000_000_000))
        self.assertEqual(record['mean_score'],200)

    def test_exchange_at_target_can_commit_late_before_the_next_exchange(self):
        rec,clock,anchor=ready();target=anchor['anchor_monotonic_ns']+300_000_000_000
        feed(rec,clock,target,1202,10,200,process_time=target+5)
        feed(rec,clock,target+1,1203,11,999,process_time=target+6)
        clock.now=target+7;self.assertEqual(rec.take_checkpoints(clock.now)[0]['mean_score'],200)

    def test_missing_or_stale_members_cannot_be_discarded(self):
        rec,clock,anchor=ready();target=anchor['anchor_monotonic_ns']+300_000_000_000
        feed(rec,clock,target-1,1202,10,200);feed(rec,clock,target+1,1203,11,999,skip=4096)
        self.assertEqual(rec.take_checkpoints(clock.now),[])
        clock.now=target+25_000_000_001
        with self.assertRaises(ValueError):rec.take_checkpoints(clock.now)
        rec,clock,anchor=ready();target=anchor['anchor_monotonic_ns']+300_000_000_000
        feed(rec,clock,target-REC.MAX_AGE_NS-1,1202,10,200);feed(rec,clock,target+1,1203,11,999)
        with self.assertRaises(ValueError):rec.take_checkpoints(clock.now)

    def test_completed_first_game_needs_positive_retirement_without_future_traffic(self):
        rec,clock,anchor=ready();target=anchor['anchor_monotonic_ns']+300_000_000_000
        feed(rec,clock,target-2,1202,10,200);clock.now=target-1
        rec.observe(4096,FIX.terminal_sample(4096,clock.now,200,sequence=1203,before=11))
        feed(rec,clock,target+1,1203,11,999,skip=4096)
        self.assertEqual(rec.take_checkpoints(clock.now),[])
        rec.positively_retired_slots.add(4096)
        record=rec.take_checkpoints(clock.now)[0];row=record['rows'][0]
        self.assertEqual((row['score_at_horizon'],record['n_completed']),(200,1))
        self.assertTrue(row['positively_retired_without_future_traffic']);self.assertIsNone(row['first_post_horizon_activity'])

    def test_completion_after_target_is_not_a_completed_earlier_game(self):
        rec,clock,anchor=ready();target=anchor['anchor_monotonic_ns']+300_000_000_000
        feed(rec,clock,target-2,1202,10,200);clock.now=target+1
        rec.observe(4096,FIX.terminal_sample(4096,clock.now,200,sequence=1203,before=11))
        feed(rec,clock,target+1,1203,11,999,skip=4096)
        record=rec.take_checkpoints(clock.now)[0]
        self.assertFalse(record['rows'][0]['whole_game_complete']);self.assertEqual(record['n_completed'],0)
        self.assertEqual(rec._scores[4096]['status'],'completed')

    def test_mixed_horizons_are_rejected_by_report_and_auditor(self):
        values=OLD_REPORT.four();values['C1']['horizon_ns']=600_000_000_000
        with self.assertRaises(ValueError):REP.compare_four(values)
        audit_fixture=OLD_AUD.Tests().fixture();audit_fixture[0]['horizon_ns']=600_000_000_000
        with self.assertRaises(ValueError):AUD.audit(*audit_fixture)

    def test_actual_prebody_package_controller_and_display_accept_all_horizons(self):
        for horizon in REC.SUPPORTED_HORIZONS_NS:
            with self.subTest(horizon=horizon),subject(horizon)as(root,job,selection):
                bind_selection(root,job,selection);context=NATIVE.validate_completed_context(job,H)
                self.assertEqual((len(context['modules']),len(context['package_pins'])),(12,123))
                jp=H.put(root/'job.json',job);cfg=deepcopy(ORIGINAL_CONFIG)
                cfg.update(unit='robotron-duration-profile-S2-screen-r1-original01-20261031.service',output=str(root/'unused-controller-output'))
                cfg['argv'][4]=job['runtime']['path'];cfg['argv'][7]=jp['path'];cfg['argv'][9]=jp['sha256'];cfg['argv'][11]=job['runtime']['sha256']
                cfg['pins']=[CTL.pin(jp['path']),CTL.pin(job['runtime']['path'])]
                cp=H.put(root/'controller-config.json',cfg);self.assertEqual(CTL.checked_config(cp['path']),cfg)
                self.assertEqual(OUTER.screen_display(selection)['screen_minutes'],horizon//60_000_000_000)
                self.assertNotIn('torch',sys.modules)

    def test_runtime_rejects_mixed_sources_and_untyped_timing_before_any_body(self):
        for damage in ('float_horizon','float_offsets','old_recorder','mismatched_selection_horizon','float_selection_offsets','promotion_claim'):
            with self.subTest(damage=damage),subject()as(root,job,selection):
                if damage=='float_horizon':job['horizon_ns']=float(job['horizon_ns'])
                elif damage=='float_offsets':job['checkpoint_offsets_ns']=[float(n)for n in job['checkpoint_offsets_ns']]
                elif damage=='old_recorder':job['components']['recorder']=ORIGINAL_JOB['components']['recorder']
                elif damage=='mismatched_selection_horizon':selection['screen_horizon_ns']=3_600_000_000_000
                elif damage=='float_selection_offsets':selection['checkpoint_offsets_ns']=[float(n)for n in selection['checkpoint_offsets_ns']]
                else:selection['short_screen_is_promotion_evidence']=True
                bind_selection(root,job,selection)
                with self.assertRaises(ValueError):NATIVE.validate_completed_context(job,H)


def main():
    global REC,REP,AUD,NATIVE,CTL,OUTER,FIX,OLD_AUD,OLD_REPORT,H,MANIFEST,ORIGINAL_JOB,ORIGINAL_SELECTION,ORIGINAL_CONFIG,METADATA
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--source-manifest',type=Path);parser.add_argument('--source-manifest-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    raw=args.source_manifest.read_bytes();assert hashlib.sha256(raw).hexdigest()==args.source_manifest_sha256
    MANIFEST=json.loads(raw)
    H=load('_duration_test_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    METADATA=load('_duration_retirement_fixture_metadata',Path(__file__).with_name('retirement_test_metadata_v1.py'))
    sources={key:load('_duration_test_'+key,H.checked(pin))for key,pin in MANIFEST['sources'].items()}
    REC,REP,AUD,NATIVE,CTL,OUTER=[sources[k]for k in ('recorder','report','score_auditor','native','controller','outer')]
    sys.modules['deadline_score_recorder_v3']=REC
    FIX=load('_duration_legacy_recorder_tests',LEGACY/'test_deadline_score_recorder_v3.py')
    OLD_REPORT=load('_duration_legacy_report_tests',LEGACY/'test_deadline_score_report_v1.py');OLD_REPORT.report=REP
    OLD_AUD=load('_duration_legacy_audit_tests',LEGACY/'test_audit_deadline32_score_v1.py');OLD_AUD.core=REC;OLD_AUD.audit=AUD
    OLD_AUD.Tests._original_fixture=OLD_AUD.Tests.fixture
    def fixture_with_declared_horizon(self,*a,**kw):
        values=self._original_fixture(*a,**kw);values[0]['horizon_ns']=values[2]['horizon_ns'];METADATA.attach(values[1],values[2]);return values
    OLD_AUD.Tests.fixture=fixture_with_declared_horizon
    ORIGINAL_JOB=json.loads((C/'R1/job.json').read_text());ORIGINAL_SELECTION=json.loads((C/'selection.json').read_text());ORIGINAL_CONFIG=json.loads((C/'R1/controller-config.json').read_text())
    suite=unittest.TestSuite()
    for module in (FIX,OLD_REPORT,OLD_AUD):suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(DurationContracts))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    assert 'torch'not in sys.modules
    report=dict(status='PASS'if result.wasSuccessful()else'FAIL',tests_run=result.testsRun,
        failures=[dict(test=str(test),traceback=trace)for test,trace in result.failures],
        errors=[dict(test=str(test),traceback=trace)for test,trace in result.errors],
        log=stream.getvalue(),manifest=H.pin(args.source_manifest),test_source=H.pin(Path(__file__)),
        legacy_tests=[H.pin(LEGACY/name)for name in ('test_deadline_score_recorder_v3.py','test_deadline_score_report_v1.py','test_audit_deadline32_score_v1.py')],
        exact_source_profile_contexts_exercised=[600,900,1800,3600],Torch_imported=False,
        GPU_MAME_or_native_body_launched=False,live_current_sources_changed=False,
        statistical_error_control_or_rejection_rule_qualified=False,promotion=False)
    pin=H.put(args.output,report)
    print(json.dumps(dict(status=report['status'],tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),report=pin)))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
