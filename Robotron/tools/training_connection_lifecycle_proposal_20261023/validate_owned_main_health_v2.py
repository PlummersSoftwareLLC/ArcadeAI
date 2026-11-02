"""Original ten-minute raw full-health replay and integration rejection contracts."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import time
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-owned-main-health-v2-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_health_v2_test_h',job['helpers']);reader=load('_health_v2_test_reader',job['reader'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    engine=load('_health_v2_test_engine',job['subject']);base=load('_health_v2_test_base',job['base_collector'])
    def read(pin):return reader.read_pin(pin)  # Deliberately no raw-record cache.
    selected=read(job['health_job']);original=read(job['original_collect_only_report']);cursors=read(job['original_cursors'])
    statuses=[dict(status,phase=status['phase']['original_phase'])for status in original['actual_status']]
    actual=None;negatives=[]
    class Contracts(unittest.TestCase):
        def test_original2999_samples116_censuses_and_natural_cap104_replay(self):
            nonlocal actual
            actual=engine.replay(selected,original['samples'],cursors,read,h,original_statuses=statuses)
            self.assertEqual(actual['samples'],2999);self.assertEqual(actual['deep_samples'],116)
            self.assertEqual(actual['API_count_histogram'],{'192':2999})
            groups=actual['transport']['groups'];self.assertEqual(len(groups),1)
            self.assertEqual(groups[0]['kind'],'normal_reconnect');self.assertEqual(groups[0]['actors'][0]['slot'],104)
            self.assertGreater(actual['original_capture_span_s'],599)
            self.assertLessEqual(actual['maximum_observation_gap_s'],.5)
            self.assertGreater(actual['final_learner_frames'],actual['first_learner_frames'])
            self.assertGreater(actual['final_training_steps'],actual['first_training_steps'])
            self.assertFalse(actual['quality_qualified'])
        def test_original_failed600_stays_incomplete_under_new_reviewer(self):
            failed=read(job['prior_failure']);initial=read(job['prior_failure_cursors'])
            with self.assertRaisesRegex(ValueError,'cannot close valid'):
                engine.replay(selected,failed['samples'],initial,read,h)
            negatives.append('old_failed_proc_observation_no_after_proof_stays_invalid')
        def test_full_health_is_required_before_transport_acceptance(self):
            first=original['samples'][0]['path']
            def changed_API(record):
                sample=record['transport'];value=json.loads(base.decode(sample['raw_API']))
                value['bank_persistence']['write_failures']=1;sample['raw_API']=base.encode(json.dumps(value).encode())
            mutations={
                'missing_physical_census':lambda r:r.update(deep=None),
                'changed_actor_UID':lambda r:r['deep']['snapshot']['actors']['104'].update(uids=[0]*4),
                'changed_actor_executable':lambda r:r['deep']['snapshot']['actors']['104'].update(executable=None),
                'stale_autosave':lambda r:r['deep']['autosave'].update(mtime_ns=1),
                'held_source_error':lambda r:r['deep'].update(held_error='failure',held197_checked_live=False),
                'bank_error_with_healthy_transport':changed_API}
            for name,mutation in mutations.items():
                def injected(pin):
                    value=read(pin)
                    if pin['path']==first:mutation(value)
                    return value
                with self.assertRaises((ValueError,TypeError,KeyError)):
                    engine.replay(selected,original['samples'],cursors,injected,h)
                negatives.append(name)
            bad=copy.deepcopy(statuses);bad[0]['phase']['accepted']=False
            with self.assertRaises(ValueError):engine.replay(selected,original['samples'],cursors,read,h,original_statuses=bad)
            negatives.append('cached_phase_flag_cannot_override_raw_replay')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts);result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():return 1
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=dict(status='ORIGINAL2999_FULL_HEALTH_AND_NATURAL_CAP104_REPLAY_CONTRACTS_PASS_NOT_NATIVE_SELECTED',
        tests=result.testsRun,negative_checks=negatives,actual_raw_replay=actual,
        original_collect_only_report=job['original_collect_only_report'],original_collect_only_status_unchanged=True,
        maximum_resident_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        full9000s_native_resource_memory_and_source_integration_still_pending=True,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,
        quality_qualified=False,scientific_guard_selected=False,production_changed=False,created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negatives),samples=actual['samples'])),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
