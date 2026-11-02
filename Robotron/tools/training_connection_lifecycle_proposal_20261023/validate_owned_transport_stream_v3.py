"""CPU integration contracts for complete mixed transport streams; no live reads."""
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
    job=json.loads(raw);assert job['schema']=='robotron-owned-transport-stream-v3-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_mixed_test_h',job['helpers']);reader=load('_mixed_test_r',job['reader'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    p=load('_mixed_test_p',job['primitives']);cap=load('_mixed_test_cap',job['cap'])
    proc=load('_mixed_test_proc',job['proc']);subject=load('_mixed_test_subject',job['subject'])
    base=load('_mixed_test_base',job['base_collector']);binding=reader.read_pin(job['binding'])
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    natural_manifest=read(job['natural_report']);natural=[];origins=read(job['natural_cursors'])
    for pin in natural_manifest['samples']:
        record=read(pin);chunks=[]
        for event in record['events']:
            if event['kind']=='original_actor_log_appended':chunks.extend(dict(chunk,raw=read(chunk['raw'],False))for chunk in event['chunks'])
        natural.append(dict(index=record['index'],observed_unix_s=record['observed_unix_s'],
            API_begin_unix_s=record['API_begin_unix_s'],API_end_unix_s=record['API_end_unix_s'],
            tcp_begin_unix_s=record['tcp']['begin_unix_s'],tcp_end_unix_s=record['tcp']['end_unix_s'],
            raw_API=read(record['API'],False),raw_tcp=read(record['tcp']['selected_raw'],False),
            raw_fds=read(record['latest_fd_view'],False),log_chunks=chunks))
    def natural_cursors(index):
        current=copy.deepcopy(origins)
        for sample in natural[:index]:cap.append_logs(p,binding,current,sample)
        return current
    quiet_report=read(job['quiet_report']);quiet=[base.unpacked(read(pin))for pin in quiet_report['samples']]
    quiet_cursors=read(job['quiet_cursors']);proc_cursors=read(job['proc_cursors'])
    before=base.unpacked(read(job['original_before']));failed=base.unpacked(read(job['original_rejection']))
    after=copy.deepcopy(failed);stamp=failed['observed_unix_s']+.2
    after.update(index=561,observed_unix_s=stamp,API_begin_unix_s=stamp-.02,API_end_unix_s=stamp-.015,
        tcp_begin_unix_s=stamp-.01,tcp_end_unix_s=stamp-.005,raw_tcp=before['raw_tcp'],log_chunks=[])
    API=json.loads(after['raw_API']);delta=stamp-.01-API['ts'];API['ts']+=delta
    for row in API['client_rows']:row['connected_seconds']+=delta
    after['raw_API']=json.dumps(API,allow_nan=False).encode();proc_fixture=[before,failed,after]
    def stream(cursors,prior=()):return subject.Stream(p,cap,proc,binding,cursors,p.LUA_SHA,prior)
    def finish(observer,samples):
        phases=[observer.observe(sample)for sample in samples];return observer.close(),phases
    negatives=[];quiet_summary=None;cap_summary=None;proc_summary=None
    class Contracts(unittest.TestCase):
        def test_original_quiet600_matches_all_original_phases(self):
            nonlocal quiet_summary
            quiet_summary,phases=finish(stream(quiet_cursors),quiet)
            self.assertEqual(phases,[status['phase']for status in quiet_report['actual_status']])
            self.assertEqual(quiet_summary['samples'],600);self.assertEqual(quiet_summary['budget']['groups'],0)
        def test_original597_gap_remains_a_sticky_failure(self):
            observer=stream(origins);index=None
            with self.assertRaises(ValueError):
                for sample in natural:index=sample['index'];observer.observe(sample)
            self.assertEqual(index,17);self.assertIsNotNone(observer.failed)
            with self.assertRaises(ValueError):observer.observe(natural[18])
            negatives.append('whole_original597_gap_no_later_rescue')
        def test_separate_original579_cap_suffix_retains_all_five_exact_groups(self):
            nonlocal cap_summary
            cap_summary,phases=finish(stream(natural_cursors(18)),natural[18:])
            expected=read(job['prior_cap_report'])['original_valid_suffix_summary']
            self.assertEqual(cap_summary['groups'],expected['groups']);self.assertEqual(cap_summary['samples'],579)
            self.assertEqual(cap_summary['budget']['cap_overlap_groups'],2)
            self.assertEqual(cap_summary['budget']['normal_reconnects'],3)
        def test_original_proc_failure_without_after_evidence_still_cannot_close(self):
            observer=stream(proc_cursors);self.assertTrue(observer.observe(before)['accepted'])
            self.assertFalse(observer.observe(failed)['accepted'])
            with self.assertRaises(ValueError):observer.close()
            with self.assertRaises(ValueError):observer.observe(after)
            negatives.append('original_proc_tail_missing_no_requalification')
        def test_explicit_synthetic_after_routes_to_owned_repeat_proof(self):
            nonlocal proc_summary
            proc_summary,phases=finish(stream(proc_cursors),proc_fixture)
            self.assertEqual([phase['accepted']for phase in phases],[True,False,True])
            self.assertEqual(proc_summary['budget']['proc_repeat_groups'],1)
            self.assertEqual(proc_summary['budget']['cap_overlap_groups'],0)
            self.assertEqual(proc_summary['groups'][0]['slot'],176)
        def test_mixed_proofs_carry_across_leg_boundaries_without_budget_reset(self):
            first,_=finish(stream(natural_cursors(18)),natural[18:301])
            observer=stream(natural_cursors(301),first['case_groups']);second,_=finish(observer,natural[301:])
            third,_=finish(stream(proc_cursors,second['case_groups']),proc_fixture)
            self.assertEqual(len(third['groups']),1);self.assertEqual(len(third['case_groups']),6)
            self.assertEqual(third['budget']['total_exception_groups'],3)
            self.assertEqual(third['budget']['cap_overlap_groups'],2);self.assertEqual(third['budget']['proc_repeat_groups'],1)
        def test_unknown_peers_and_conflicting_repeats_never_become_accepted(self):
            foreign=b' 999: 0D01A8C0:DAD0 8301A8C0:270E 01 00000000:00000000 00:00000000 00000000 1001 0 999999999 1\n'
            for name,index in [('unknown_peer_at_baseline',0),('unknown_peer_with_repeat',1)]:
                data=copy.deepcopy(proc_fixture);data[index]['raw_tcp']+=foreign;observer=stream(proc_cursors)
                with self.assertRaises(ValueError):
                    for sample in data:observer.observe(sample)
                    observer.close()
                self.assertIsNotNone(observer.failed);negatives.append(name)
            data=copy.deepcopy(proc_fixture);lines=data[1]['raw_tcp'].splitlines(keepends=True);fields=lines[-1].split()
            fields[4]=b'00000001:00000000';lines[-1]=b' '.join(fields)+b'\n';data[1]['raw_tcp']=b''.join(lines)
            observer=stream(proc_cursors)
            with self.assertRaises(ValueError):
                for sample in data:observer.observe(sample)
            self.assertIsNotNone(observer.failed);negatives.append('conflicting_repeat_body')
        def test_both_exception_kinds_share_one_count_and_time_ceiling(self):
            caps,_=finish(stream(natural_cursors(18)),natural[18:])
            repeats,_=finish(stream(proc_cursors),proc_fixture)
            cap_base=next(group for group in caps['groups']if group['kind']=='overlap');proc_base=repeats['groups'][0]
            def synthetic_group(original,number,span):
                value=copy.deepcopy(original);begin=1e9+number*3;end=begin+span
                value.update(begin_unix_s=begin,end_unix_s=end,window_s=end-begin,charged_s=end-begin)
                for marker in value.get('caps',[]):marker['marker_offset']+=number*100000
                for event in value.get('original_repeat_events',[]):
                    event.update(index=number,observed_unix_s=begin+.01)
                return value
            for name,ncap,nproc,span in [('shared_time_over600',200,101,2),('shared_count_over1024',600,425,.1)]:
                groups=[synthetic_group(cap_base,index,span)for index in range(ncap)]
                groups +=[synthetic_group(proc_base,index,span)for index in range(ncap,ncap+nproc)]
                cap.closed_budget(p,groups[:ncap]);proc.closed_budget(p,groups[ncap:])
                with self.assertRaises(ValueError):subject.closed_budget(p,cap,proc,groups)
                negatives.append(name)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=dict(status='MIXED_TRANSPORT_STREAM_CPU_CONTRACTS_PASS_NOT_LIVE_OR_NATIVE_SELECTED',tests=result.testsRun,
        negative_checks=negatives,actual_quiet600=quiet_summary,actual_separate_cap579_suffix=cap_summary,
        explicitly_synthetic_after_proc_stream=proc_summary,whole_original597_stays_invalid=True,
        original_failed600_stays_invalid=True,fixtures='Mixed-case carry and proc after-sample are explicit synthetic diagnostic compositions, never a scientific case.',
        limits=subject.LIMITS,source_sha256=args.source_sha256,job_sha256=args.job_sha256,
        production_changed=False,scientific_guard_selected=False,quality_qualified=False,created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negatives))),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
