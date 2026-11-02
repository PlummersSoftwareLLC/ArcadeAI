"""CPU contracts for collect-only raw-tail control; never starts a live collector."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-first-anomaly-tail-control-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_tail_test_h',job['helpers'])
    for key in ('subject','base_collector','transport','primitives','binding','original_before','original_rejection','original_cursors'):h.checked(job[key])
    subject=load('_tail_test_subject',job['subject']);base=load('_tail_test_pack',job['base_collector'])
    p=load('_tail_test_p',job['primitives']);transport=load('_tail_test_t',job['transport'])
    binding=json.loads(h.checked(job['binding']).read_bytes());origins=json.loads(h.checked(job['original_cursors']).read_bytes())
    before=base.unpacked(json.loads(h.checked(job['original_before']).read_bytes()))
    failed=base.unpacked(json.loads(h.checked(job['original_rejection']).read_bytes()))
    negatives=[];actual=None
    class Contracts(unittest.TestCase):
        def test_original_actual559_560_rejection_stays_sticky_while_synthetic_tail_is_collected(self):
            nonlocal actual
            original=transport.Stream(p,binding,origins,p.LUA_SHA);calls=[];clock=[0.]
            class Tracked:
                def observe(self,sample):calls.append(sample['index']);return original.observe(sample)
            observer=subject.DiagnosticTransport(Tracked(),lambda:clock[0])
            first=observer.observe(before);self.assertFalse(first['accepted']);self.assertTrue(first['original_phase']['accepted'])
            clock[0]=.2;rejected=observer.observe(failed)
            self.assertFalse(rejected['accepted']);self.assertEqual(observer.first['error'],"ValueError('Duplicate proc TCP row')")
            self.assertIsNotNone(original.failed)
            for index in range(1,7):
                sample=copy.deepcopy(failed);sample.update(index=failed['index']+index,observed_unix_s=failed['observed_unix_s']+.2*index)
                clock[0]=.2+.2*index;phase=observer.observe(sample);self.assertFalse(phase['accepted'])
            self.assertTrue(observer.tail_complete());self.assertEqual(calls,[559,560])
            actual=observer.close();self.assertEqual(actual['tail_samples'],6)
            self.assertFalse(actual['transport_accepted']);self.assertFalse(actual['health_qualified'])
            with self.assertRaises(ValueError):observer.observe(failed)
            negatives.append('observe_after_collect_only_close')
            with self.assertRaises(ValueError):original.observe(failed)
            negatives.append('strict_rejected_stream_stays_unrecoverable')
        def test_tail_cannot_finish_on_elapsed_clock_without_original_after_sample(self):
            class Rejected:
                def observe(self,sample):raise ValueError('original error')
            clock=[0.];observer=subject.DiagnosticTransport(Rejected(),lambda:clock[0]);observer.observe(failed)
            clock[0]=10.;self.assertFalse(observer.tail_complete())
            sample=dict(failed,observed_unix_s=failed['observed_unix_s']+.5);observer.observe(sample)
            self.assertFalse(observer.tail_complete());negatives.append('wait_without_sufficient_original_tail')
        def test_future_wall_clock_alone_cannot_finish_monotonic_tail(self):
            class Rejected:
                def observe(self,sample):raise ValueError('original error')
            clock=[0.];observer=subject.DiagnosticTransport(Rejected(),lambda:clock[0]);observer.observe(failed)
            sample=dict(failed,observed_unix_s=failed['observed_unix_s']+10);observer.observe(sample)
            self.assertFalse(observer.tail_complete());negatives.append('wall_clock_jump_without_monotonic_tail')
        def test_quiet_capture_never_becomes_a_health_verdict(self):
            class Quiet:
                def observe(self,sample):return dict(accepted=True,phase='original_full192')
            observer=subject.DiagnosticTransport(Quiet());self.assertFalse(observer.observe(before)['accepted'])
            self.assertFalse(observer.tail_complete());result=observer.close()
            self.assertIsNone(result['first_strict_rejection']);self.assertFalse(result['health_qualified'])
            self.assertFalse(result['quality_qualified']);negatives.append('quiet_capture_is_not_health_qualification')
        def test_other_transport_errors_are_preserved_without_acceptance_or_retry(self):
            calls=[]
            class Rejected:
                def observe(self,sample):calls.append(sample['index']);raise ValueError('unknown peer')
            observer=subject.DiagnosticTransport(Rejected());self.assertFalse(observer.observe(failed)['accepted'])
            self.assertEqual(observer.first['error'],"ValueError('unknown peer')")
            self.assertFalse(observer.observe(dict(failed,index=561))['accepted']);self.assertEqual(calls,[560])
            negatives.append('unknown_peer_is_not_reclassified_as_benign')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=dict(status='ORIGINAL_REJECTION_PRESERVED_COLLECT_ONLY_TAIL_CONTROL_CONTRACTS_PASS',tests=result.testsRun,
        negative_checks=negatives,original_before=job['original_before'],original_rejection=job['original_rejection'],
        wrapper_result=actual,tail_fixture='Six explicitly synthetic later timestamps on a copied original sample; not actual after-evidence and never a health certificate.',
        production_changed=False,scientific_guard_selected=False,health_qualified=False,quality_qualified=False,
        job_sha256=args.job_sha256,source_sha256=args.source_sha256,created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negatives))),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
