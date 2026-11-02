"""Inactive guards for a bounded wait on a still-old API epoch.

Only the last two original C1 samples are observations. Every later sample in
these tests is explicitly synthetic engineering data, never a runtime witness
or a rescue of the original failed scientific cohort.
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def guard_suite(modules,original,binding,cursors):
    p,old,candidate=(modules[k]for k in ('primitives','original','candidate'))
    rejected_cases=[]

    def observer(module=candidate):
        return module.Stream(p,binding,cursors,p.LUA_SHA)

    def json_change(sample,key,function):
        value=json.loads(sample[key]);function(value)
        sample[key]=json.dumps(value,allow_nan=True).encode()+(b'\n'if sample[key].endswith(b'\n')else b'')

    def later_sample(delta,*,fresh=True,reuse_CID=False):
        """EXPLICIT SYNTHETIC fixture preserving observed endpoints/identities."""
        sample=copy.deepcopy(original[-1])
        sample['index']=original[-1]['index']+round(delta/.2)
        for key in ('API_begin_unix_s','API_end_unix_s','tcp_begin_unix_s',
                    'tcp_end_unix_s','observed_unix_s'):sample[key]+=delta
        sample['log_chunks']=[]
        api=json.loads(sample['raw_API'])
        api['ts']+=delta
        for row in api['client_rows']:
            row['connected_seconds']+=delta
            if row['client_slot']==61 and fresh:
                row['client_id']=31 if reuse_CID else 1000000
                row['connected_seconds']=api['ts']-(original[-1]['API_end_unix_s']-.05)
        sample['raw_API']=json.dumps(api,allow_nan=False).encode()
        for key in ('raw_fds','raw_tcp'):
            value=json.loads(sample[key])
            for stamp in ('begin_unix_s','end_unix_s'):value[stamp]+=delta
            sample[key]=json.dumps(value,allow_nan=False).encode()+b'\n'
        return sample

    def data():return copy.deepcopy(original)+[later_sample(.2)]

    class Guards(unittest.TestCase):
        def reject(self,name,mutation):
            samples=data();mutation(samples)
            stream=observer()
            expected={
                'missing_cap':'incomplete original stream',
                'changed_cap':'incomplete original stream',
                'wrong_log_inode':'Wrong actor/log origin',
                'wrong_log_actor':'Wrong actor/log origin',
                'actor_birth':'Original process birth changed',
                'trainer_birth':'Original process birth changed',
                'stale_API':'Stale/future original API',
                'stale_FD':'Stale/slow/future FD census',
                'skipped_index':'Skipped, reordered or delayed original stream sample',
                'gap_above_half_second':'Skipped, reordered or delayed original stream sample',
                'unrecognized_epoch':'Old/new connection epochs',
                'duplicate_CID':'Unknown slot or duplicate client ID',
                'malformed_TCP':'Exact fixed-query request bytes required',
            }.get(name,'Only full192 or single duplicate193'if name.startswith('client_count_')else None)
            self.assertIsNotNone(expected,name)
            with self.assertRaises((ValueError,KeyError,TypeError,IndexError))as failure:
                for sample in samples:stream.observe(sample)
                stream.close()
            self.assertRegex(str(failure.exception),expected)
            self.assertIsNotNone(stream.failed)
            with self.assertRaises(ValueError):stream.observe(later_sample(.4))
            rejected_cases.append(name)

        def test_original_source_rejects_the_exact_original_last_two_samples(self):
            stream=observer(old)
            stream.observe(copy.deepcopy(original[0]))
            with self.assertRaisesRegex(ValueError,'Old/new connection epochs'):
                stream.observe(copy.deepcopy(original[1]))
            self.assertIsNotNone(stream.failed)

        def test_new_source_only_waits_and_never_accepts_the_original_mismatch(self):
            stream=observer()
            self.assertTrue(stream.observe(copy.deepcopy(original[0]))['accepted'])
            phase=stream.observe(copy.deepcopy(original[1]))
            self.assertFalse(phase['accepted'])
            self.assertTrue(phase['overlap_pending'])
            self.assertEqual(phase['phase'],'awaiting_original_evidence')
            self.assertIsNone(stream.failed)
            self.assertEqual(stream.groups,[])
            with self.assertRaises(ValueError):stream.close()
            self.assertIsNotNone(stream.failed)

        def test_synthetic_fresh_coherent_API_completes_with_all_original_predicates(self):
            stream=observer()
            phases=[stream.observe(sample)for sample in data()]
            self.assertFalse(phases[1]['accepted'])
            self.assertTrue(phases[2]['accepted'])
            result=stream.close()
            self.assertEqual(result['samples'],3)
            self.assertEqual(len(result['groups']),1)
            group=result['groups'][0]
            self.assertEqual(group['kind'],'normal_reconnect')
            self.assertEqual([a['slot']for a in group['actors']],[61])
            self.assertEqual(group['actors'][0]['before_client_id'],31)
            self.assertEqual(group['actors'][0]['after_client_id'],1000000)
            self.assertEqual(len(group['caps']),1)
            self.assertLessEqual(group['window_s'],2)
            self.assertFalse(result['quality_qualified'])

        def test_synthetic_reused_CID_requires_a_distinct_fresh_connection_epoch(self):
            stream=observer()
            for sample in copy.deepcopy(original)+[later_sample(.2,reuse_CID=True)]:
                stream.observe(sample)
            group=stream.close()['groups'][0]
            actor=group['actors'][0]
            self.assertEqual(actor['before_client_id'],actor['after_client_id'])
            self.assertGreater(actor['after_connection_epoch']-actor['before_connection_epoch'],1.5)

        def test_unresolved_old_API_hits_the_same_two_second_deadline_without_rescue(self):
            stream=observer()
            for sample in copy.deepcopy(original):stream.observe(sample)
            with self.assertRaisesRegex(ValueError,'fixed evidence window'):
                for step in range(1,11):
                    phase=stream.observe(later_sample(step*.2,fresh=False))
                    self.assertFalse(phase['accepted'])
            self.assertIsNotNone(stream.failed)
            with self.assertRaises(ValueError):stream.observe(later_sample(2.2))
            self.assertEqual(stream.groups,[])

        def test_delayed_synthetic_coherence_within_deadline_keeps_every_sample(self):
            stream=observer()
            for sample in copy.deepcopy(original):stream.observe(sample)
            for step in range(1,8):
                self.assertFalse(stream.observe(later_sample(step*.2,fresh=False))['accepted'])
            self.assertTrue(stream.observe(later_sample(1.6))['accepted'])
            result=stream.close()
            self.assertEqual(result['samples'],10)
            self.assertLessEqual(result['groups'][0]['window_s'],2)

        def test_missing_or_changed_cap_and_wrong_log_identity_never_certify(self):
            self.reject('missing_cap',lambda samples:samples[1].update(log_chunks=[]))
            def no_marker(samples):
                chunk=samples[1]['log_chunks'][0]
                chunk['raw']=chunk['raw'].replace(b'[WAVECAP]',b'[NOT_CAP]')
            self.reject('changed_cap',no_marker)
            self.reject('wrong_log_inode',lambda samples:samples[1]['log_chunks'][0].update(inode=1))
            self.reject('wrong_log_actor',lambda samples:samples[1]['log_chunks'][0].update(actor_pid=1))

        def test_unsupported_client_counts_still_reject(self):
            for count in (191,194,195):
                with self.subTest(count=count):
                    self.reject('client_count_'+str(count),lambda samples,count=count:
                        json_change(samples[1],'raw_API',lambda api:api.update(client_count=count)))

        def test_actor_and_trainer_birth_changes_still_reject(self):
            for who in ('actor','trainer'):
                def mutation(samples,who=who):
                    def change(view):
                        subject=view['actors']['61']if who=='actor'else view['trainer']
                        subject['starttime_ticks']+=1
                    json_change(samples[1],'raw_fds',change)
                with self.subTest(who=who):self.reject(who+'_birth',mutation)

        def test_stale_API_FD_and_skipped_samples_still_reject(self):
            self.reject('stale_API',lambda samples:json_change(samples[1],'raw_API',lambda api:api.update(ts=api['ts']-2)))
            self.reject('stale_FD',lambda samples:json_change(samples[1],'raw_fds',lambda view:view.update(
                begin_unix_s=view['begin_unix_s']-2,end_unix_s=view['end_unix_s']-2)))
            self.reject('skipped_index',lambda samples:samples[1].update(index=samples[1]['index']+1))
            self.reject('gap_above_half_second',lambda samples:samples[1].update(
                observed_unix_s=samples[0]['observed_unix_s']+.51))

        def test_foreign_API_epoch_cannot_use_the_old_cached_epoch_wait(self):
            def mutation(samples):
                def change(api):
                    row=next(r for r in api['client_rows']if r['client_slot']==61)
                    row['connected_seconds']=50
                json_change(samples[1],'raw_API',change)
            self.reject('unrecognized_epoch',mutation)

        def test_duplicate_CID_and_malformed_TCP_are_not_accepted_as_pending_health(self):
            self.reject('duplicate_CID',lambda samples:json_change(samples[1],'raw_API',lambda api:
                api['client_rows'][0].update(client_id=api['client_rows'][1]['client_id'])))
            self.reject('malformed_TCP',lambda samples:json_change(samples[1],'raw_tcp',lambda tcp:
                tcp.update(request_base64='not-base64')))

        def test_all_original_limits_remain_identical(self):
            self.assertEqual(candidate.LIMITS,old.LIMITS)
            self.assertEqual(candidate.LIMITS['max_window_s'],2)
            self.assertEqual(candidate.LIMITS['max_sample_gap_s'],.5)
            self.assertEqual(candidate.LIMITS['max_API_age_s'],1)
            self.assertEqual(candidate.LIMITS['max_fd_age_s'],1.25)

    return unittest.defaultTestLoader.loadTestsFromTestCase(Guards),rejected_cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-guards',action='store_true')
    parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256')
    args=parser.parse_args()
    if not args.run_guards or args.job is None or not args.job_sha256:
        parser.error('Explicit --run-guards and exact pinned job required')
    raw=args.job.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        name='await_API_engineering_'+name
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        spec.loader.exec_module(module)
        return module
    helper=load('helper',job['sources']['helper'])
    for entry in job['inputs']:assert helper.pin(entry['path'])==entry
    assert helper.pin(Path(__file__).resolve())==job['runner']
    reader=load('reader',job['sources']['reader'])
    read=lambda pin:reader.read_pin(pin)
    modules={name:load(name,job['sources'][name])for name in ('primitives','original','candidate','collector')}
    original=[modules['collector'].unpacked(read(pin))for pin in job['original_samples']]
    binding,cursors=read(job['binding']),read(job['cursors'])
    main_observations=[]
    def main_health(label):
        result=subprocess.run(['/usr/bin/python3.12','-I','-B',job['main_monitor']['path']],
                              capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        value=json.loads(result.stdout)
        assert value['client_count']==192 and value['held_inputs']==197 and value['autosave_age_s']<=360
        main_observations.append(helper.put(Path(job['directory'])/(label+'-main-health.json'),value))
    main_health('before')
    suite,rejected=guard_suite(modules,original,binding,cursors)
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    main_health('after')
    for entry in job['inputs']:assert helper.pin(entry['path'])==entry
    assert 'torch'not in sys.modules
    report=dict(schema='robotron-await-old-API-epoch-original-CPU-guards-v1',
                original_job=helper.pin(args.job),successful=result.wasSuccessful(),
                tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                negative_cases=rejected,negative_cases_count=len(rejected),
                unittest_output=output.getvalue(),main_observations=main_observations,
                all_selected_inputs_unchanged=True,only_original_samples=[p['path']for p in job['original_samples']],
                all_later_samples_explicitly_synthetic=True,original_case_remains_invalid=True,
                engineering_only=True,quality_qualified=False,full_health_runtime_verified=False,
                numerical_runtime_imported=False,production_changed=False)
    pin=helper.put(Path(job['report']),report)
    print(json.dumps(dict(successful=result.wasSuccessful(),tests_run=result.testsRun,
                         negative_cases=len(rejected),report=pin,quality_qualified=False)),flush=True)
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':
    raise SystemExit(main())
