"""CPU readiness contracts on immutable captured rows; no old study is rescued."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import time
import unittest
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-initial-owned-readiness-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(pin,name):
        assert hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest()==pin['sha256']
        s=importlib.util.spec_from_file_location(name,pin['path'])
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
    h=load(job['helpers'],'_initial_h');reader=load(job['reader'],'_initial_reader')
    def read(pin):return reader.read_pin(pin)
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    subject=load(job['subject'],'_initial_subject');old=load(job['original'],'_initial_old')
    engine=load(job['engine'],'_initial_engine');base=load(job['collector'],'_initial_collector')
    selected=read(job['actual_capture_job'])
    selected['initial_readiness_protocol']=dict(schema='robotron-bounded-initial-owned-readiness-v1',max_wait_s=2.,max_samples=11)
    modules=engine.dependencies(selected,h)
    p=modules['indexed_join'].bind(modules['primitives']);cap=modules['transport'];proc=modules['proc_repeat']
    binding=read(selected['binding']);cursors=read(job['initial_cursors']);uid=selected['binding']['identity']['uid']
    capture=read(job['actual_capture_report'])
    # These are ORIGINAL indices390/391/... in a NEW collect-only diagnostic.
    # This is a transport-component subwindow, not a requalified native cohort.
    real=[base.unpacked(read(capture['samples'][i]))for i in range(389,397)]
    initial=real[1:]  # actual conflicting row390, then actual clean391
    failed=read(job['failed2700_health'])
    failed_sample=base.unpacked(read(failed['samples'][0]))
    negative=[];bootstrap=None;post_baseline=None
    def stream(prior=()):
        return subject.Stream(p,cap,proc,binding,cursors,p.LUA_SHA,prior,expected_uid=uid)
    def jsonchange(sample,key,fn):
        value=json.loads(sample[key]);fn(value);sample[key]=json.dumps(value,separators=(',',':')).encode()
    def rawchange(sample,index,value):
        lines=sample['raw_tcp'].splitlines(keepends=True)
        positions=[i for i,line in enumerate(lines)if len(line.split())>=10 and line.split()[9]==b'359713499']
        assert len(positions)==2
        i=positions[-1];fields=lines[i].split();fields[index]=value
        lines[i]=b' '.join(fields)+b'\n';sample['raw_tcp']=b''.join(lines)
    def shifted(sample,offset,index):
        value=copy.deepcopy(sample)
        for key in ['observed_unix_s','API_begin_unix_s','API_end_unix_s','tcp_begin_unix_s','tcp_end_unix_s']:value[key]+=offset
        value['index']=index
        def API(a):
            a['ts']+=offset
            for row in a['client_rows']:row['connected_seconds']+=offset
        jsonchange(value,'raw_API',API)
        jsonchange(value,'raw_fds',lambda f:f.update(begin_unix_s=f['begin_unix_s']+offset,end_unix_s=f['end_unix_s']+offset))
        return value
    def synthetic_prior(group,count,span,before):
        result=[]
        begin=before-count*span-1
        for i in range(count):
            value=copy.deepcopy(group);start=begin+i*span;end=start+span
            value.update(begin_unix_s=start,end_unix_s=end,window_s=end-start,charged_s=end-start)
            for event in value['original_repeat_events']:
                event.update(index=10000+i,observed_unix_s=start+span/2)
            result.append(value)
        return result
    class Contracts(unittest.TestCase):
        def reject_initial(self,name,change):
            value=copy.deepcopy(initial[0]);change(value);s=stream()
            with self.assertRaises((ValueError,KeyError,TypeError)):s.observe(value)
            with self.assertRaises(ValueError):s.observe(initial[1])
            negative.append(name)
        def test_01_real_unfiltered_initial_repeat_waits_for_real_clean_baseline(self):
            nonlocal bootstrap
            s=stream();fingerprints=[hashlib.sha256(json.dumps(x,default=str,sort_keys=True).encode()).hexdigest()for x in initial]
            first=s.observe(initial[0]);self.assertFalse(first['accepted']);self.assertTrue(first['readiness_pending'])
            self.assertIsNone(s.baseline)
            second=s.observe(initial[1]);self.assertTrue(second['accepted']);self.assertFalse(second['overlap_pending'])
            for sample in initial[2:]:s.observe(sample)
            closed=s.close();self.assertEqual(closed['samples'],7)
            self.assertEqual(closed['initial_readiness']['first_qualified_baseline_index'],391)
            self.assertEqual(closed['initial_readiness']['unaccepted_samples'],1)
            self.assertEqual(closed['budget']['initial_readiness_groups'],1)
            bootstrap=closed['groups'][0]
            self.assertEqual([r['index']for r in bootstrap['observations']],[390,391])
            self.assertEqual(bootstrap['observations'][0]['original_repeats'][0]['actual_changed_field_indices'],[4,5])
            self.assertEqual(bootstrap['charged_s'],initial[1]['observed_unix_s']-initial[0]['observed_unix_s'])
            self.assertEqual(fingerprints,[hashlib.sha256(json.dumps(x,default=str,sort_keys=True).encode()).hexdigest()for x in initial])
        def test_02_post_baseline_protocol_and_real_proc_certificate_remain_identical(self):
            nonlocal post_baseline
            a=old.Stream(p,cap,proc,binding,cursors,p.LUA_SHA);b=stream()
            for sample in real:self.assertEqual(a.observe(sample),b.observe(sample))
            expected=a.close();actual=b.close();self.assertEqual(expected['groups'],actual['groups'])
            for key,value in expected['budget'].items():self.assertEqual(value,actual['budget'][key])
            self.assertEqual(actual['budget']['initial_readiness_groups'],0)
            post_baseline=actual['groups'][0]
        def test_03_failed2700_single_sample_has_no_baseline_and_stays_invalid(self):
            s=stream();value=s.observe(failed_sample)
            self.assertFalse(value['accepted']);self.assertIsNone(s.baseline)
            with self.assertRaises(ValueError):s.close()
            with self.assertRaises(ValueError):s.observe(initial[1])
            negative.append('failed2700_not_requalified')
        def test_04_unknown_ownership_body_API_logs_and_freshness_reject_immediately(self):
            for count in [191,193,194]:
                self.reject_initial('API'+str(count),lambda v,count=count:jsonchange(v,'raw_API',lambda a:a.update(client_count=count)))
            self.reject_initial('trainer_birth',lambda v:jsonchange(v,'raw_fds',lambda f:f['trainer'].update(starttime_ticks=1)))
            self.reject_initial('actor_birth',lambda v:jsonchange(v,'raw_fds',lambda f:f['actors']['176'].update(starttime_ticks=1)))
            self.reject_initial('missing_FD',lambda v:jsonchange(v,'raw_fds',lambda f:f['trainer']['socket_fds'].update({'180':1})))
            self.reject_initial('stale_FD',lambda v:jsonchange(v,'raw_fds',lambda f:f.update(begin_unix_s=1,end_unix_s=1)))
            self.reject_initial('stale_API',lambda v:jsonchange(v,'raw_API',lambda a:a.update(ts=a['ts']-10)))
            self.reject_initial('logs_or_cap',lambda v:v['log_chunks'].append(dict(raw=b'[WAVECAP]')))
            for name,index,value in [('UID',7,b'0'),('inode',9,b'999999999'),('refcount',10,b'4'),
                                     ('bad_timer',5,b'05:00000000'),('same_ordinal',0,b'727:')]:
                self.reject_initial(name,lambda v,index=index,value=value:rawchange(v,index,value))
            foreign=b' 999: 0D01A8C0:DAD0 8301A8C0:270E 01 00000000:00000000 00:00000000 00000000 1001 0 999999999 1\n'
            self.reject_initial('unknown_peer',lambda v:v.update(raw_tcp=v['raw_tcp']+foreign))
            self.reject_initial('missing_reverse',lambda v:v.update(raw_tcp=b'\n'.join(
                line for line in v['raw_tcp'].splitlines()if b'359713499'not in line)+b'\n'))
        def test_05_pending_timeout_gap_and_logical_epoch_do_not_wait_out_invalid_state(self):
            s=stream()
            for i in range(11):s.observe(shifted(initial[0],i*.2,390+i))
            with self.assertRaises(ValueError):s.observe(shifted(initial[0],2.2,401))
            with self.assertRaises(ValueError):s.observe(initial[1])
            negative.append('two_second_eleven_sample_pending_limit')
            for name,change in [
                ('gap',lambda v:v.update(observed_unix_s=initial[0]['observed_unix_s']+1)),
                ('CID',lambda v:jsonchange(v,'raw_API',lambda a:next(r for r in a['client_rows']if r['client_slot']==176).update(client_id=999999))),
                ('epoch',lambda v:jsonchange(v,'raw_API',lambda a:next(r for r in a['client_rows']if r['client_slot']==176).update(connected_seconds=.01)))]:
                s=stream();s.observe(initial[0]);value=copy.deepcopy(initial[1]);change(value)
                with self.assertRaises(ValueError):s.observe(value)
                with self.assertRaises(ValueError):s.observe(initial[1])
                negative.append(name)
        def test_06_readiness_is_charged_to_the_original_count_and_time_budgets(self):
            s=stream()
            for sample in initial[:2]:s.observe(sample)
            group=s.close()['groups'][0]
            a=old.Stream(p,cap,proc,binding,cursors,p.LUA_SHA)
            for sample in real:a.observe(sample)
            procgroup=a.close()['groups'][0]
            # Explicit synthetic metadata fixtures exercise shared limits only.
            # They are never raw observations, accepted cohorts or published proofs.
            prior=synthetic_prior(procgroup,1024,.2,group['begin_unix_s'])
            with self.assertRaises(ValueError):subject.closed_budget(p,cap,proc,[*prior,group])
            prior=synthetic_prior(procgroup,300,2.,group['begin_unix_s'])
            with self.assertRaises(ValueError):subject.closed_budget(p,cap,proc,[*prior,group])
            damaged=copy.deepcopy(group);damaged['charged_s']=0
            with self.assertRaises(ValueError):subject.closed_budget(p,cap,proc,[damaged])
            with self.assertRaises(ValueError):subject.closed_budget(p,cap,proc,[group,group])
            negative.extend(['shared_count_no_reset','shared_time_no_reset','readiness_not_free','readiness_no_reuse'])
        def test_07_new_engine_requires_explicit_protocol_and_matching_uid_source(self):
            wrong=copy.deepcopy(selected);wrong.pop('initial_readiness_protocol')
            with self.assertRaises(ValueError):engine.dependencies(wrong,h)
            with self.assertRaises(ValueError):subject.Stream(p,cap,proc,binding,cursors,p.LUA_SHA,expected_uid=0)
            negative.extend(['no_implicit_protocol_selection','no_unknown_UID'])
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=dict(schema='robotron-initial-owned-readiness-CPU-contract-report-v1',
        status='REAL_CAPTURED_INITIAL_READINESS_AND_UNCHANGED_POST_BASELINE_CONTRACTS_PASS',
        tests=result.testsRun,negative_checks=negative,actual_diagnostic_subwindow_indices=list(range(390,397)),
        actual_readiness_record=bootstrap,actual_ordinary_proc_certificate=post_baseline,
        synthetic_fixtures_only='Deadline shifts and shared-budget metadata are synthetic; raw positive window is captured original390..396.',
        old2700_requalified=False,old_failed_study_retried=False,full_engine_live_validation_pending=True,
        native_integration_pending=True,scientific_guard_selected=False,quality_qualified=False,
        production_changed=False,created_unix_s=time.time())
    h.put(output/'report.json',report)
    print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negative))),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
