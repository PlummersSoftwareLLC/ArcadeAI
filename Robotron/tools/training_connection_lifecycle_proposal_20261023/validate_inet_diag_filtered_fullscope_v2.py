"""New kernel-socket format raw equivalence and explicit worst-scope scaling.

The48,332 generated observations and8,192 prior proof groups are synthetic
resource fixtures, never a real9600s observation, game cohort or health receipt.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-inet-diag-filtered-fullscope-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_indexed_health_h',job['helpers']);reader=load('_indexed_health_r',job['reader'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    engine=load('_indexed_health_engine',job['subject']);base=load('_indexed_health_base',job['base_collector'])
    def read(pin):return reader.read_pin(pin)
    selected=read(job['health_job']);real=read(job['real_report']);long=read(job['long_report'])
    real_expected=read(job['real_expected'])['independent_original_raw_replay'];long_expected=read(job['long_expected'])['actual_raw_replay']
    actual=[];scaling=None
    class Contracts(unittest.TestCase):
        def test_01_actual_client_full_raw_replay_matches_original_independent_kernel_format_review(self):
            started=time.monotonic()
            result=engine.replay(selected,real['samples'],read(job['real_cursors']),read,h,
                original_statuses=real['actual_status'])
            self.assertEqual(result,real_expected)
            actual.append(dict(name='real_inet_diag_client_original',samples=result['samples'],
                wall_s=time.monotonic()-started,exact_original_closed_engine4_replay=True,
                transport_budget=result['transport']['budget']))
            print(json.dumps(dict(progress='real_inet_diag_client_original',samples=result['samples'],wall_s=actual[-1]['wall_s'])),flush=True)
        def test_02_synthetic_maximum_sample_count_and_maximum_case_history_memory(self):
            nonlocal scaling
            seed=read(real['samples'][0]);sample=base.unpacked(seed);API=json.loads(sample['raw_API']);fd=json.loads(sample['raw_fds'])
            deep=seed['deep'];start=sample['observed_unix_s'];mono=deep['snapshot']['collection_started_monotonic_s']
            original_API_ts=API['ts'];original_ages=[row['connected_seconds']for row in API['client_rows']]
            first_frames=API['learner_frame_count'];first_steps=API['training_steps'];first_opt=API['optimized_samples']
            cap_group=long_expected['transport']['groups'][0]
            proc_group=read(job['legacy_proc_budget_fixture'])['actual_replay']['transport']['groups'][0]
            initial_group=read(job['readiness_component'])['actual_readiness_record']
            prior=[]
            # Explicitly synthetic worst-budget history, never current-source
            # runtime proofs:7168 normal caps,1020 proc-shaped records and four
            # maximal readiness records. New-format raw observations reject all
            # duplicate socket rows and start from a clean baseline at index0.
            for number in range(8192):
                begin=start-3*(8192-number)-10
                if number>=8188:
                    group=copy.deepcopy(initial_group)
                    originals=group['observations'];records=[]
                    for index in range(11):
                        record=copy.deepcopy(originals[-1]if index==10 else originals[0])
                        record.update(index=900000+number*100+index,observed_unix_s=begin+index*.2)
                        records.append(record)
                    end=begin+2.
                    group.update(first_index=records[0]['index'],last_index=records[-1]['index'],
                        begin_unix_s=begin,end_unix_s=end,window_s=end-begin,charged_s=end-begin,observations=records)
                else:
                    group=copy.deepcopy(cap_group if number<7168 else proc_group)
                    end=begin+.4
                    group.update(begin_unix_s=begin,end_unix_s=end,window_s=end-begin,
                        charged_s=0. if number<7168 else end-begin)
                    for marker in group.get('caps',[]):marker['marker_offset']+=number*100000
                    for event in group.get('original_repeat_events',[]):event.update(index=number,observed_unix_s=begin+.2)
                prior.append(group)
            socket_dump=json.loads(sample['raw_tcp'])
            assert socket_dump['schema']=='robotron-original-inet-diag-port9998-snapshot-v3'
            pins=[dict(explicit_synthetic_index=index)for index in range(48332)]
            def generated(pin):
                if 'explicit_synthetic_index'not in pin:return read(pin)
                index=pin['explicit_synthetic_index'];tick=start+index*.2
                if index%2048==0:
                    print(json.dumps(dict(progress='explicit_synthetic_resource_fixture',generated_index=index,actual_elapsed_s=time.monotonic()-started,actual_peak_resident_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)),flush=True)
                current_API=copy.deepcopy(API);current_API['ts']=tick+.03
                delta=current_API['ts']-original_API_ts
                for row,age in zip(current_API['client_rows'],original_ages):row['connected_seconds']=age+delta
                current_API.update(learner_frame_count=first_frames+index,training_steps=first_steps+index,
                    optimized_samples=first_opt+4096*index)
                current_fd=copy.deepcopy(fd);current_fd.update(begin_unix_s=tick+.031,end_unix_s=tick+.04)
                current_dump=copy.deepcopy(socket_dump);current_dump.update(begin_unix_s=tick+.026,end_unix_s=tick+.03)
                current=dict(sample,index=index,observed_unix_s=tick+.05,API_begin_unix_s=tick+.02,
                    API_end_unix_s=tick+.025,tcp_begin_unix_s=tick+.026,tcp_end_unix_s=tick+.03,
                    raw_tcp=json.dumps(current_dump,separators=(',',':'),allow_nan=False).encode()+b'\n',
                    raw_API=json.dumps(current_API,separators=(',',':'),allow_nan=False).encode(),
                    raw_fds=json.dumps(current_fd,separators=(',',':'),allow_nan=False).encode(),log_chunks=[])
                census=None
                if index%25==0:
                    census=copy.deepcopy(deep);snapshot=census['snapshot']
                    snapshot.update(collection_started_unix_s=tick,unix_s=tick+.01,
                        collection_started_monotonic_s=mono+index*.2,monotonic_s=mono+index*.2+.01)
                    census['checked_unix_s']=tick+.015;census['autosave']['mtime_ns']=int((tick-30)*1e9)
                return base.packed(current,census)
            initial_RSS=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;started=time.monotonic();CPU=time.process_time()
            result=engine.replay(selected,pins,read(job['real_cursors']),generated,h,prior_groups=prior)
            elapsed=time.monotonic()-started;used_CPU=time.process_time()-CPU;peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            self.assertEqual(result['samples'],48332);self.assertEqual(result['deep_samples'],1934)
            self.assertEqual(len(result['transport']['groups']),0);self.assertEqual(len(result['transport']['case_groups']),8192)
            self.assertEqual(result['transport']['initial_readiness']['unaccepted_samples'],0)
            self.assertEqual(result['transport']['initial_readiness']['first_qualified_baseline_index'],0)
            self.assertEqual(result['transport']['budget']['initial_readiness_groups'],4)
            self.assertEqual(result['transport']['budget']['total_exception_groups'],1024)
            self.assertLessEqual(result['transport']['budget']['total_charged_s'],600)
            self.assertLess(peak-initial_RSS,256*1024);self.assertLess(peak,512*1024)
            self.assertLess(elapsed,600)
            scaling=dict(samples=48332,synthetic_capture_span_s=result['original_capture_span_s'],
                prior_case_groups=8192,final_case_groups=8192,normal_prior_groups=7168,proc_prior_groups=1020,initial_readiness_groups=4,synthetic_pending_startup_samples=0,
                recomputed_budget=result['transport']['budget'],actual_elapsed_s=elapsed,actual_CPU_s=used_CPU,
                actual_before_peak_resident_KiB=initial_RSS,actual_peak_resident_KiB=peak,
                memory_growth_under256MiB=True,all_generated_records_explicitly_synthetic=True,
                real_native_observation=False,quality_qualified=False)
            print(json.dumps(dict(progress='synthetic48332_with8192_case_groups',**scaling)),flush=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    assert 'torch'not in sys.modules
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=dict(status='INET_DIAG_FILTERED_ORIGINAL_CLIENT_AND_SYNTHETIC48332_WITH8192_CASE_GROUPS_PASS_NOT_NATIVE_SELECTED',
        tests=result.testsRun,actual_original_replays=actual,explicit_synthetic_resource_scaling=scaling,
        join_equivalence_proof=job['join_equivalence'],source_equivalence_proof=job['source_equivalence'],initial_readiness_component=job['readiness_component'],inet_diag_capture_provenance=job['inet_diag_capture_provenance'],
        native_full_game_scope_execution_still_required=True,source_sha256=args.source_sha256,job_sha256=args.job_sha256,
        quality_qualified=False,scientific_guard_selected=False,production_changed=False,
        useful_training_throughput_gain_verified=False,created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
