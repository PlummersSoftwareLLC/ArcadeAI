"""Bounded CPU contracts for unselected physical/recipe/async-write integration."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-owned-cap-health-contracts-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        p=Path(pin['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_health_test_h',job['sources']['helpers'])
    for pin in job['sources'].values():h.checked(pin)
    health=load('_health_test_guard',job['sources']['health']);sup=load('_health_test_sup',job['sources']['supervision'])
    p=load('_health_test_p',job['sources']['primitives']);collector=load('_health_test_collector',job['sources']['collector'])
    main=json.loads(h.checked(job['binding']).read_bytes());policy=json.loads(h.checked(main['supervision_policy']).read_bytes())
    baseline=json.loads(h.checked(main['baseline_API']).read_bytes());snapshot=json.loads(h.checked(job['census']).read_bytes())
    API=p.decode(h.checked(job['original_API']).read_bytes());now=API['ts']+.1
    output=Path(job['output']);output.mkdir(mode=0o700);negatives=[];proof=None
    original_window=Path(job['sources']['window']['path']).read_bytes();original_sup=Path(job['sources']['supervision']['path']).read_bytes()
    companion=Path(job['sources']['health']['path']).read_bytes()
    class Contracts(unittest.TestCase):
        def test_exact_single_predicate_source_specialization(self):
            nonlocal proof
            proof=health.verify_sources(original_window,original_sup,companion)
            for name,raw in [('pipeline_error_removed',companion.replace(b"pipe[kind]['errors']==0",b"True")),
                             ('recipe_lr_changed',companion.replace(b"api['lr']==6.25e-6",b"api['lr']==1e-5"))]:
                with self.assertRaises(ValueError):health.verify_sources(original_window,original_sup,raw)
                negatives.append(name)
        def test_original_full192_physical_census_and_all_static_invariants(self):
            health.physical(sup,policy,snapshot)
            mutations={
                'missing_actor':lambda s:s['actors'].pop('152'),
                'foreign_slot':lambda s:s['actors'].update({'999':copy.deepcopy(s['actors']['152'])}),
                'changed_actor_birth':lambda s:s['actors']['152'].update(starttime_ticks=1),
                'changed_actor_PID':lambda s:s['actors']['152'].update(pid=1),
                'false_previous_probe':lambda s:s['previous_birth_probes'].update({'152':1}),
                'missing_probe':lambda s:s['previous_birth_probes'].pop('152'),
                'slow_census':lambda s:s.update(monotonic_s=s['collection_started_monotonic_s']+6),
                'changed_trainer_birth':lambda s:s['owners']['trainer']['process'].update(starttime_ticks=1),
                'changed_trainer_unit':lambda s:s['owners']['trainer'].update(stdout=s['owners']['trainer']['stdout'].replace('NRestarts=0','NRestarts=1'))}
            for key in sup.STATIC:
                mutations['actor_static_'+key]=lambda s,key=key:s['actors']['152'].update({key:None})
                mutations['owner_static_'+key]=lambda s,key=key:s['owners']['trainer']['process'].update({key:None})
            for name,mutation in mutations.items():
                data=copy.deepcopy(snapshot);mutation(data)
                with self.assertRaises((ValueError,TypeError,KeyError)):health.physical(sup,policy,data)
                negatives.append(name)
        def test_original_API_count_does_not_bypass_recipe_pipeline_or_bank(self):
            health.sample(p,API,baseline,main['experiment'],now)
            mutations={
                'count191':lambda a:a.update(client_count=191),
                'count194':lambda a:a.update(client_count=194),
                'recipe_lr':lambda a:a.update(lr=1e-5),
                'recipe_measurement':lambda a:a.update(measurement_active=True),
                'recipe_training':lambda a:a.update(training_enabled=False),
                'recipe_experiment':lambda a:a.update(managed_experiment='foreign'),
                'API_stale':lambda a:a.update(ts=a['ts']-10),
                'pipeline_stale':lambda a:a.update(pipeline_snapshot_age_s=6),
                'pipeline_generation':lambda a:a['host_pipeline'].update(generation=-1),
                'pipeline_unavailable':lambda a:a['host_pipeline'].update(available=False),
                'pipeline_read':lambda a:a.update(pipeline_read_error='failure'),
                'bank_read':lambda a:a.update(bank_persistence_read_error='failure'),
                'bank_write':lambda a:a['bank_persistence'].update(write_failures=1)}
            for key in ('inference','actor_refresh','target_refresh','learner_priority'):
                mutations['pipeline_'+key]=lambda a,key=key:a['host_pipeline'][key].update(errors=1)
            for name,mutation in mutations.items():
                data=copy.deepcopy(API);mutation(data)
                with self.assertRaises(ValueError):health.sample(p,data,baseline,main['experiment'],now)
                negatives.append(name)
            later=copy.deepcopy(API);later['training_steps']-=1
            with self.assertRaises(ValueError):health.sample(p,later,baseline,main['experiment'],now,API)
            negatives.append('learner_clock_regression')
        def test_autosave_freshness_stays_mandatory(self):
            metadata=dict(bytes=275000000,mtime_ns=int((now-10)*1e9));health.autosave(metadata,now)
            for name,mutation in [('stale_autosave',lambda x:x.update(mtime_ns=int((now-361)*1e9))),
                ('future_autosave',lambda x:x.update(mtime_ns=int((now+1)*1e9))),('empty_autosave',lambda x:x.update(bytes=0))]:
                data=copy.deepcopy(metadata);mutation(data)
                with self.assertRaises(ValueError):health.autosave(data,now)
                negatives.append(name)
        def test_original_raw_bytes_roundtrip_and_hash_rejection(self):
            raw=b'\x00original\xff\n'
            self.assertEqual(collector.decode(collector.encode(raw)),raw)
            broken=collector.encode(raw);broken['sha256']='0'*64
            with self.assertRaises(ValueError):collector.decode(broken)
            negatives.append('encoded_original_hash_mismatch')
        def test_actual_writer_queue_continues_while_first_persistence_waits(self):
            entered=threading.Event();release=threading.Event();folder=output/'writer-contract';folder.mkdir()
            class WaitingHelper:
                @staticmethod
                def put(path,value):
                    entered.set();assert release.wait(timeout=3)
                    return h.put(path,value)
            writer=collector.Writer(WaitingHelper,folder)
            try:
                writer.submit(dict(transport=dict(index=0),explicit_synthetic_payload='first'))
                self.assertTrue(entered.wait(timeout=1))
                for index in range(1,5):writer.submit(dict(transport=dict(index=index),explicit_synthetic_payload='queued'))
                self.assertEqual(len(writer.records),0);self.assertEqual(writer.pending.qsize(),4)
            finally:release.set()
            closure=writer.close();self.assertTrue(closure['thread_stopped']);self.assertEqual(len(writer.records),5)
            self.assertEqual([json.loads(h.checked(pin).read_bytes())['transport']['index']for pin in writer.records],list(range(5)))
            with self.assertRaises(ValueError):writer.submit(dict(transport=dict(index=5)))
            negatives.append('submit_after_writer_close')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    report=dict(status='ORIGINAL_CPU_NONTRANSPORT_AND_ASYNC_WRITER_CONTRACTS_PASS_NOT_LIVE_VALIDATED',
        tests=result.testsRun,negative_checks=negatives,source_proof=proof,job_sha256=args.job_sha256,
        source_sha256=args.source_sha256,scientific_guard_selected=False,quality_qualified=False,production_changed=False,
        created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negatives))),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
