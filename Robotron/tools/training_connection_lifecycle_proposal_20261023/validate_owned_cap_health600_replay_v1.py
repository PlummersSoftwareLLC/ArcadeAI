"""Original live raw replay plus explicit synthetic rejection contracts; CPU only."""
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
    job=json.loads(raw);assert job['schema']=='robotron-owned-cap-health-independent-replay-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_replay_test_h',job['helpers']);reader=load('_replay_test_reader',job['reader'])
    for pin in [job['helpers'],job['reader'],job['replay'],job['collector']]:h.checked(pin)
    replay=load('_replay_test_subject',job['replay']);collector=load('_replay_test_pack',job['collector'])
    cache={}
    def read(pin):
        key=(pin['path'],pin['sha256'])
        if key not in cache:cache[key]=reader.read_pin(pin)
        return copy.deepcopy(cache[key])
    live_job=read(job['live_job']);report=read(job['live_report']);cursors=read(job['live_initial_cursors'])
    original_result=None;negatives=[]
    class Contracts(unittest.TestCase):
        def test_actual_original_fixed600_seconds_independently_replay(self):
            nonlocal original_result
            original_result=replay.review(live_job,report,cursors,read,h)
            self.assertGreaterEqual(original_result['samples'],1200)
            self.assertLessEqual(original_result['samples'],3001)
            counts=original_result['API_count_histogram']
            self.assertLessEqual(set(counts),{'192','193'})
            self.assertEqual(sum(counts.values()),original_result['samples'])
            if counts.get('193',0):self.assertGreaterEqual(original_result['transport']['budget']['overlap_groups'],1)
            self.assertFalse(original_result['quality_qualified'])
        def test_original_raw_replay_rejects_synthetic_missing_and_false_evidence(self):
            first=report['samples'][0]['path']
            def change_wire(record,key,function):
                value=json.loads(collector.decode(record['transport'][key]));function(value)
                record['transport'][key]=collector.encode(json.dumps(value,allow_nan=False).encode())
            mutations={
                'missing_physical_census':lambda r:r.update(deep=None),
                'changed_actor_birth':lambda r:r['deep']['snapshot']['actors']['152'].update(starttime_ticks=1),
                'changed_actor_affinity':lambda r:r['deep']['snapshot']['actors']['152'].update(affinity=[999]),
                'held_source_failure':lambda r:r['deep'].update(held_error='original failure',held197_checked_live=False),
                'stale_autosave':lambda r:r['deep']['autosave'].update(mtime_ns=1),
                'raw_API191':lambda r:change_wire(r,'raw_API',lambda a:a.update(client_count=191)),
                'bank_write_failure':lambda r:change_wire(r,'raw_API',lambda a:a['bank_persistence'].update(write_failures=1)),
                'FD_owner_birth_changed':lambda r:change_wire(r,'raw_fds',lambda f:f['actors']['152'].update(starttime_ticks=1)),
                'malformed_original_hash':lambda r:r['transport']['raw_API'].update(sha256='0'*64)}
            for name,mutation in mutations.items():
                def injected(pin):
                    value=read(pin)
                    if pin['path']==first:mutation(value)
                    return value
                with self.assertRaises((ValueError,KeyError,TypeError)):
                    replay.review(live_job,report,cursors,injected,h)
                negatives.append(name)
        def test_cached_flags_and_selected_sample_lists_cannot_replace_raw_review(self):
            for name,mutation in [
                ('cached_budget_modified',lambda r:r['transport']['budget'].update(groups=999)),
                ('raw_sample_skipped',lambda r:(r['samples'].pop(1),r['actual_status'].pop(1))),
                ('cached_phase_forged',lambda r:r['actual_status'][0]['phase'].update(accepted=False)),
                ('unclosed_writer',lambda r:r['writer'].update(thread_stopped=False))]:
                data=copy.deepcopy(report);mutation(data)
                with self.assertRaises((ValueError,KeyError,TypeError)):replay.review(live_job,data,cursors,read,h)
                negatives.append(name)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    output=Path(job['output']);output.mkdir(mode=0o700)
    receipt=dict(status='ORIGINAL_LIVE600_SECONDS_RAW_REPLAY_AND_NEGATIVE_CONTRACTS_PASS_NOT_NATIVE_INTEGRATED',
        tests=result.testsRun,negative_checks=negatives,original_independent_replay=original_result,
        live_report=job['live_report'],source_sha256=args.source_sha256,job_sha256=args.job_sha256,
        production_changed=False,scientific_guard_selected=False,quality_qualified=False,created_unix_s=time.time())
    h.put(output/'report.json',receipt)
    print(json.dumps(dict(status=receipt['status'],tests=result.testsRun,negative_checks=len(negatives),
        samples=original_result['samples'],deep_samples=original_result['deep_samples'])),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
