"""CPU replay/negative contracts for an unselected pure streaming reviewer."""
import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-owned-cap-stream-v3-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    output=Path(job['output']);output.mkdir(mode=0o700)
    def checked(pin):
        path=Path(pin['path']);raw=path.read_bytes()
        assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256']
        return path
    def load(name,pin):
        spec=importlib.util.spec_from_file_location(name,checked(pin))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    reader=load('_stream_reader',job['reader']);p=load('_stream_primitives',job['primitives'])
    candidate=load('_stream_candidate',job['candidate'])
    cache={}
    def read(pin,as_json=True):
        key=(pin['path'],pin['sha256'],as_json)
        if key not in cache:cache[key]=reader.read_pin(pin,as_json=as_json)
        return cache[key]
    binding=read(job['binding']);manifest=read(job['trace_report']);origins=read(job['trace_initial_log_cursors'])
    samples=[]
    for index,pin in enumerate(manifest['samples']):
        record=read(pin);assert record['index']==index;chunks=[]
        for event in record['events']:
            if event['kind']=='original_actor_log_appended':
                chunks.extend(dict(chunk,raw=read(chunk['raw'],False)) for chunk in event['chunks'])
        samples.append(dict(index=index,observed_unix_s=record['observed_unix_s'],
            API_begin_unix_s=record['API_begin_unix_s'],API_end_unix_s=record['API_end_unix_s'],
            tcp_begin_unix_s=record['tcp']['begin_unix_s'],tcp_end_unix_s=record['tcp']['end_unix_s'],
            raw_API=read(record['API'],False),raw_tcp=read(record['tcp']['selected_raw'],False),
            raw_fds=read(record['latest_fd_view'],False),log_chunks=chunks))
    def cursors_before(index):
        cursors=copy.deepcopy(origins)
        for sample in samples[:index]:candidate.append_logs(p,binding,cursors,sample)
        return cursors
    def stream(cursors=None,prior=()):
        return candidate.Stream(p,binding,cursors or origins,p.LUA_SHA,prior)
    def json_change(sample,key,function):
        value=json.loads(sample[key]);function(value);sample[key]=json.dumps(value,allow_nan=True).encode()
    actual_summary=None;actual_phases=None;negative_checks=[];synthetic_cases=[];trace_rejection=None

    class Contracts(unittest.TestCase):
        def rejected(self,name,mutation):
            data=copy.deepcopy(samples[206:210]);mutation(data)
            observer=stream(cursors_before(206))
            with self.assertRaises((ValueError,KeyError,TypeError,IndexError)):
                for sample in data:observer.observe(sample)
                observer.close()
            self.assertIsNotNone(observer.failed)
            with self.assertRaises(ValueError):observer.observe(samples[209])
            negative_checks.append(name)

        def test_complete_original597_trace_rejects_original_one_second_gap(self):
            nonlocal trace_rejection
            observer=stream();failed_index=None
            try:
                for sample in samples:
                    failed_index=sample['index'];observer.observe(sample)
                observer.close()
            except ValueError as error:
                trace_rejection=dict(index=failed_index,error=repr(error),
                    preceding_observation=manifest['samples'][failed_index-1],
                    rejected_observation=manifest['samples'][failed_index],
                    actual_gap_s=samples[failed_index]['observed_unix_s']-samples[failed_index-1]['observed_unix_s'],
                    whole_original_trace_valid=False,no_original_bytes_or_clocks_changed=True)
            self.assertIsNotNone(trace_rejection);self.assertEqual(failed_index,17)
            self.assertGreater(trace_rejection['actual_gap_s'],candidate.LIMITS['max_sample_gap_s'])
            self.assertIsNotNone(observer.failed)
            with self.assertRaises(ValueError):observer.observe(samples[18])
            negative_checks.append('whole_original_trace_gap17_rejected_no_later_recovery')

        def test_separate_valid_original_prefix_and_suffix_are_diagnostics_only(self):
            nonlocal actual_summary,actual_phases
            prefix=stream()
            for sample in samples[:17]:prefix.observe(sample)
            prefix_summary=prefix.close();self.assertEqual(prefix_summary['samples'],17)
            self.assertEqual(prefix_summary['groups'],[])
            observer=stream(cursors_before(18));phases=collections.Counter()
            for sample in samples[18:]:phases[observer.observe(sample)['phase']]+=1
            actual_summary=observer.close();actual_phases=dict(phases)
            self.assertEqual(actual_summary['samples'],579)
            self.assertEqual(len(actual_summary['groups']),5)
            self.assertEqual(actual_summary['budget']['normal_reconnects'],3)
            self.assertEqual(actual_summary['budget']['overlap_groups'],2)
            self.assertEqual([g['overlap_indices'] for g in actual_summary['groups'] if g['kind']=='overlap'],[[208],[479]])
            self.assertEqual([g['actors'][0]['slot'] for g in actual_summary['groups']],[140,125,152,20,58])
            self.assertFalse(actual_summary['quality_qualified'])
            with self.assertRaises(ValueError):observer.observe(samples[-1])
            negative_checks.append('observe_after_successful_close')

        def test_split_leg_budget_inherits_all_prior_evidence(self):
            first=stream(cursors_before(18))
            for sample in samples[18:301]:first.observe(sample)
            one=first.close()
            second=stream(first.cursors,one['case_groups'])
            for sample in samples[301:]:second.observe(sample)
            two=second.close()
            self.assertEqual(len(one['groups']),3);self.assertEqual(len(two['groups']),2)
            self.assertEqual(len(two['case_groups']),5)
            self.assertEqual(two['budget']['overlap_groups'],2)
            self.assertEqual(candidate.closed_budget(p,one['groups']+two['groups']),two['budget'])

        def test_both_original_overlap_certificates_retain_v1_actor_and_clock_facts(self):
            old=read(job['v1_report'])['actual_original_windows']
            for begin,end,expected in [(206,210,old[0]),(478,481,old[1])]:
                observer=stream(cursors_before(begin))
                for sample in samples[begin:end]:observer.observe(sample)
                group=observer.close()['groups'][0];actor=group['actors'][0]
                self.assertEqual(group['charged_s'],expected['charged_s'])
                for key in ('slot','actor_pid','actor_birth','before_client_id','after_client_id','old_socket','new_socket'):
                    self.assertEqual(actor[key],expected[key])

        def test_partial_close_rejection_is_sticky(self):
            observer=stream(cursors_before(206))
            for sample in samples[206:209]:observer.observe(sample)
            with self.assertRaises(ValueError):observer.close()
            with self.assertRaises(ValueError):observer.observe(samples[209])
            negative_checks.append('partial_close_then_later_recovery')

        def test_unproved_counts_skipped_reordered_and_changed_births_reject(self):
            def count(API,value):
                API['client_count']=value
            for value in [191,194,195]:
                self.rejected('unsupported_API'+str(value),lambda data,value=value:json_change(data[2],'raw_API',lambda x:count(x,value)))
            self.rejected('skipped_sample',lambda data:data.pop(1))
            self.rejected('reordered_samples',lambda data:data.reverse())
            self.rejected('missing_before',lambda data:data.pop(0))
            self.rejected('missing_after',lambda data:data.pop())
            self.rejected('actor_PID_change',lambda data:json_change(data[2],'raw_fds',lambda x:x['actors']['152'].update(pid=999999)))
            self.rejected('actor_birth_change',lambda data:json_change(data[2],'raw_fds',lambda x:x['actors']['152'].update(starttime_ticks=1)))
            self.rejected('trainer_birth_change',lambda data:json_change(data[2],'raw_fds',lambda x:x['trainer'].update(starttime_ticks=1)))

        def test_missing_false_stale_and_skipped_cap_bytes_reject(self):
            def no_marker(data):
                for sample in data:
                    for chunk in sample['log_chunks']:
                        chunk['raw']=chunk['raw'].replace(b'[WAVECAP]',b'[NOT_CAP]')
            self.rejected('no_valid_cap_marker',no_marker)
            self.rejected('wrong_log_inode',lambda data:data[1]['log_chunks'][0].update(inode=1))
            self.rejected('skipped_log_offset',lambda data:data[1]['log_chunks'][0].update(offset=1))
            self.rejected('wrong_log_actor',lambda data:data[1]['log_chunks'][0].update(actor_pid=1))
            self.rejected('stale_API',lambda data:json_change(data[2],'raw_API',lambda x:x.update(ts=x['ts']-10)))
            self.rejected('stale_FD',lambda data:json_change(data[2],'raw_fds',lambda x:x.update(begin_unix_s=x['begin_unix_s']-10,end_unix_s=x['end_unix_s']-10)))

        def test_unknown_peers_and_duplicate_client_identity_reject(self):
            foreign=b' 999: 0D01A8C0:DAD0 8301A8C0:270E 01 00000000:00000000 00:00000000 00000000 1001 0 999999999 1\n'
            self.rejected('unknown_remote_peer',lambda data:data[2].update(raw_tcp=data[2]['raw_tcp']+foreign))
            self.rejected('unknown_local_peer',lambda data:data[2].update(raw_tcp=data[2]['raw_tcp']+foreign.replace(b'0D01A8C0',b'8301A8C0')))
            self.rejected('duplicate_CID',lambda data:json_change(data[2],'raw_API',lambda x:x['client_rows'][0].update(client_id=x['client_rows'][1]['client_id'])))
            def reused_old(API):
                next(row for row in API['client_rows']if row['client_slot']==152 and row['client_id']==93)['connected_seconds']=.01
            self.rejected('old_CID_reallocated_to_fresh_unknown_epoch',lambda data:json_change(data[2],'raw_API',reused_old))

        def test_unchanged_samples_cannot_bypass_socket_or_epoch_validation(self):
            foreign=b' 999: 0D01A8C0:DAD0 8301A8C0:270E 01 00000000:00000000 00:00000000 00000000 1001 0 999999999 1\n'
            for name,position in [('unknown_socket_at_initial_baseline',0),('unknown_socket_during_stable_stream',1)]:
                data=copy.deepcopy(samples[:4]);data[position]['raw_tcp']+=foreign
                observer=stream()
                with self.assertRaises(ValueError):
                    for sample in data:observer.observe(sample)
                    observer.close()
                self.assertIsNotNone(observer.failed);negative_checks.append(name)
            data=copy.deepcopy(samples[:4])
            json_change(data[1],'raw_API',lambda API:API['client_rows'][0].update(connected_seconds=.01))
            observer=stream()
            with self.assertRaises(ValueError):
                for sample in data:observer.observe(sample)
                observer.close()
            self.assertIsNotNone(observer.failed);negative_checks.append('unchanged_socket_fresh_unknown_API_epoch')

        def test_original_cap_bytes_fragmented_across_two_synthetic_reads(self):
            data=copy.deepcopy(samples[206:210]);original=data[1]['log_chunks'][0]
            first=copy.deepcopy(original);second=copy.deepcopy(original)
            first['raw']=original['raw'][:10];first['bytes']=10;first['cap_markers']=0
            second['offset']+=10;second['raw']=original['raw'][10:];second['bytes']=len(second['raw'])
            second['lower_observed_unix_s']=data[1]['observed_unix_s']
            second['upper_observed_unix_s']=data[2]['observed_unix_s'];second['cap_markers']=0
            data[1]['log_chunks']=[first];data[2]['log_chunks'].insert(0,second)
            observer=stream(cursors_before(206))
            for sample in data:observer.observe(sample)
            result=observer.close();self.assertEqual(result['budget']['overlap_groups'],1)
            synthetic_cases.append('Original bytes divided into two explicitly synthetic read intervals; no bytes altered.')

        def test_concurrent_normal_and_overlap_reconnects_use_separate_owned_actor_proofs(self):
            data=copy.deepcopy(samples[206:210]);future=samples[480];future_view=json.loads(future['raw_fds'])
            future_tcp=p.tcp(future['raw_tcp']);base_view=json.loads(data[0]['raw_fds']);base_tcp=p.tcp(data[0]['raw_tcp'])
            old_inodes=set(base_view['actors']['58']['socket_fds'].values())
            old=next(row for row in base_tcp if row['state']=='01'and row['inode']in old_inodes and int(row['peer'][9:],16)==9998)
            old_server=next(row for row in base_tcp if row['local']==old['peer']and row['peer']==old['local']and row['state']=='01')
            new_inodes=set(future_view['actors']['58']['socket_fds'].values())
            new=next(row for row in future_tcp if row['state']=='01'and row['inode']in new_inodes and int(row['peer'][9:],16)==9998)
            new_server=next(row for row in future_tcp if row['local']==new['peer']and row['peer']==new['local']and row['state']=='01')
            cap=copy.deepcopy(samples[479]['log_chunks'][0]);cap['lower_observed_unix_s']=data[1]['API_begin_unix_s']
            cap['upper_observed_unix_s']=data[1]['observed_unix_s'];data[1]['log_chunks'].append(cap)
            def tcp_line(row):
                return f" 998: {row['local']} {row['peer']} {row['state']} 00000000:00000000 00:00000000 00000000 {row['uid']} 0 {row['inode']} 1\n".encode()
            for sample in data[2:]:
                view=json.loads(sample['raw_fds'])
                view['actors']['58']['socket_fds']={key:(new['inode']if value==old['inode']else value)
                    for key,value in view['actors']['58']['socket_fds'].items()}
                view['trainer']['socket_fds']={key:value for key,value in view['trainer']['socket_fds'].items()if value!=old_server['inode']}
                view['trainer']['socket_fds']['10000']=new_server['inode'];sample['raw_fds']=json.dumps(view).encode()
                lines=sample['raw_tcp'].splitlines(keepends=True);kept=[lines[0]]
                for line in lines[1:]:
                    fields=line.split();pair=(fields[1].decode(),fields[2].decode())
                    if pair not in [(old['local'],old['peer']),(old['peer'],old['local'])]:kept.append(line)
                sample['raw_tcp']=b''.join(kept)+tcp_line(new)+tcp_line(new_server)
                def changed(API):
                    row=next(row for row in API['client_rows']if row['client_slot']==58)
                    row.update(client_id=107,connected_seconds=.05)
                json_change(sample,'raw_API',changed)
            observer=stream(cursors_before(206))
            for sample in data:observer.observe(sample)
            result=observer.close();group=result['groups'][0]
            self.assertEqual({actor['slot']for actor in group['actors']},{58,152})
            reused=next(actor for actor in group['actors']if actor['slot']==58)
            self.assertEqual(reused['before_client_id'],reused['after_client_id'])
            self.assertGreater(reused['after_connection_epoch'],reused['before_connection_epoch'])
            self.assertEqual(group['overlap_indices'],[208]);self.assertEqual(result['budget']['overlap_groups'],1)
            synthetic_cases.append('Two source-recorded actor transitions at an explicitly synthetic common clock; normal slot58 reuses its CID with a fresh socket/epoch. Only one API193, never194.')

    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():return 1
    assert actual_summary is not None and 'torch'not in sys.modules
    for pin in [job['candidate'],job['primitives'],job['reader'],job['binding'],job['trace_report']]:checked(pin)
    report=dict(schema='robotron-owned-cap-stream-v3-CPU-report-v1',
        status='ORIGINAL_GAP_REJECTED_DIAGNOSTIC_SUFFIX_AND_CONTRACTS_PASS_NOT_LIVE_INTEGRATED',tests=result.testsRun,
        original_trace_rejection=trace_rejection,whole_original_trace_valid=False,
        original_valid_suffix_summary=actual_summary,original_valid_suffix_phase_counts=actual_phases,
        negative_checks=negative_checks,explicitly_synthetic_positive_cases=synthetic_cases,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,candidate=job['candidate'],primitives=job['primitives'],
        selected_component_limits=dict(candidate.LIMITS),production_runtime_changed=False,
        new_scientific_guard_selected=False,quality_qualified=False,
        limits=['The whole597 original trace correctly rejects at sample17 (1.003s sampling gap); this original trace never qualifies. Independent diagnostic streams0..16 and18..596 are separately checked; the latter includes all five caps. No sample filtering rescues the whole original trace.',
                'Fragmentation/concurrency positives are synthetic compositions, not new natural or real-TCP observations.',
                'Full live collector, physical/source/recipe/pipeline/bank/autosave integration and independent native reviewer remain required.'],created_unix_s=time.time())
    with(output/'report.json').open('x')as stream:
        json.dump(report,stream,separators=(',',':'),allow_nan=False);stream.write('\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],tests=result.testsRun,
        negative_checks=len(negative_checks),valid_diagnostic_suffix_samples=actual_summary['samples'],whole_original_trace_valid=False,
        budget=actual_summary['budget'],report=str(output/'report.json'))),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
