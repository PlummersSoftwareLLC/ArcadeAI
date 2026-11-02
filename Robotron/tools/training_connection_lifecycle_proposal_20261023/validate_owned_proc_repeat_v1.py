"""CPU contracts for an unselected exact owned proc-repeat certificate.

The positive after-sample is explicitly synthetic. No old failed observation is
requalified and no live collection occurs in this contract job.
"""
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
    job=json.loads(raw);assert job['schema']=='robotron-owned-proc-repeat-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_proc_test_h',job['helpers'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    p=load('_proc_test_p',job['primitives']);transport=load('_proc_test_t',job['transport'])
    candidate=load('_proc_test_c',job['candidate']);base=load('_proc_test_base',job['base_collector'])
    binding=json.loads(h.checked(job['binding']).read_bytes())
    before=base.unpacked(json.loads(h.checked(job['original_before']).read_bytes()))
    failed=base.unpacked(json.loads(h.checked(job['original_rejection']).read_bytes()))
    after=copy.deepcopy(failed);stamp=failed['observed_unix_s']+.2
    after.update(index=failed['index']+1,observed_unix_s=stamp,API_begin_unix_s=stamp-.02,
        API_end_unix_s=stamp-.015,tcp_begin_unix_s=stamp-.01,tcp_end_unix_s=stamp-.005,
        raw_tcp=before['raw_tcp'],log_chunks=[])
    API=json.loads(after['raw_API']);delta=(stamp-.01)-API['ts'];API['ts']+=delta
    for row in API['client_rows']:row['connected_seconds']+=delta
    after['raw_API']=json.dumps(API,separators=(',',':'),allow_nan=False).encode()
    fixture=[before,failed,after];negatives=[];positive=None
    def certify(data,sha=None):return candidate.certify(p,transport,binding,sha or p.LUA_SHA,data)
    def change_json(sample,key,mutation):
        value=json.loads(sample[key]);mutation(value);sample[key]=json.dumps(value,allow_nan=True).encode()
    def change_last_duplicate(data,mutation):
        lines=data[1]['raw_tcp'].splitlines(keepends=True);cells=lines[-1].split();mutation(cells)
        lines[-1]=b' '.join(cells)+b'\n';data[1]['raw_tcp']=b''.join(lines)
    class Contracts(unittest.TestCase):
        def reject(self,name,mutation):
            data=copy.deepcopy(fixture);mutation(data)
            with self.assertRaises((ValueError,KeyError,TypeError)):certify(data)
            negatives.append(name)
        def test_original_duplicate_rows_are_retained_with_exact_multiplicity(self):
            with self.assertRaises(ValueError):p.tcp(failed['raw_tcp'])
            table,repeats=candidate.original_tcp(p,failed['raw_tcp'])
            self.assertEqual(len(table),386);self.assertEqual(sum(row['state']=='01'for row in table),385)
            self.assertEqual(len(repeats),1);self.assertEqual(len(repeats[0]['occurrences']),2)
            self.assertEqual([row['proc_ordinal']for row in repeats[0]['occurrences']],['713:','714:'])
            self.assertEqual(repeats[0]['connection']['inode'],359713499)
        def test_original_without_after_proof_stays_invalid(self):
            with self.assertRaises(ValueError):certify([before,failed])
            negatives.append('original_missing_after_sample')
            self.reject('ending_at_repeated_row',lambda data:data.__setitem__(2,dict(failed,index=561,observed_unix_s=failed['observed_unix_s']+.2)))
        def test_explicit_synthetic_after_proof_exercises_owned_stable_pair_logic(self):
            nonlocal positive
            positive=certify(fixture);self.assertEqual(positive['slot'],176)
            self.assertEqual(positive['owned_pair']['server']['inode'],359713499)
            self.assertEqual(positive['raw_API_counts_preserved'],[192,192,192])
            self.assertTrue(positive['raw_TCP_rows_preserved']);self.assertFalse(positive['quality_qualified'])
        def test_original_identity_time_source_and_epoch_checks_reject(self):
            for count in [191,193,194]:
                self.reject('unsupported_API'+str(count),lambda data,count=count:change_json(data[1],'raw_API',lambda a:a.update(client_count=count)))
            self.reject('actor_birth_changed',lambda data:change_json(data[1],'raw_fds',lambda f:f['actors']['176'].update(starttime_ticks=1)))
            self.reject('trainer_birth_changed',lambda data:change_json(data[1],'raw_fds',lambda f:f['trainer'].update(starttime_ticks=1)))
            self.reject('trainer_FD_owner_missing',lambda data:change_json(data[1],'raw_fds',lambda f:f['trainer']['socket_fds'].update({'180':1})))
            self.reject('stale_FD',lambda data:change_json(data[1],'raw_fds',lambda f:f.update(begin_unix_s=1,end_unix_s=1)))
            self.reject('stale_API',lambda data:change_json(data[1],'raw_API',lambda a:a.update(ts=a['ts']-10)))
            self.reject('fresh_unrecognized_CID_epoch',lambda data:change_json(data[1],'raw_API',lambda a:next(r for r in a['client_rows']if r['client_slot']==176).update(connected_seconds=.01)))
            self.reject('reordered_samples',lambda data:data.reverse())
            self.reject('skipped_index',lambda data:data[1].update(index=999))
            self.reject('observation_gap',lambda data:data[1].update(observed_unix_s=data[0]['observed_unix_s']+1))
            self.reject('concurrent_cap_bytes',lambda data:data[1]['log_chunks'].append(dict(raw=b'[WAVECAP]')))
            with self.assertRaises(ValueError):certify(fixture,'0'*64)
            negatives.append('wrong_held_Lua')
        def test_conflicting_missing_unknown_or_multiple_original_rows_reject(self):
            self.reject('same_identity_conflicting_queue_body',lambda data:change_last_duplicate(data,lambda fields:fields.__setitem__(4,b'00000001:00000000')))
            self.reject('conflicting_UID',lambda data:change_last_duplicate(data,lambda fields:fields.__setitem__(7,b'0')))
            self.reject('different_inode',lambda data:change_last_duplicate(data,lambda fields:fields.__setitem__(9,b'999999999')))
            self.reject('nonestablished_repeat',lambda data:change_last_duplicate(data,lambda fields:fields.__setitem__(3,b'06')))
            self.reject('same_proc_ordinal_reused',lambda data:change_last_duplicate(data,lambda fields:fields.__setitem__(0,b'713:')))
            self.reject('malformed_proc_ordinal',lambda data:change_last_duplicate(data,lambda fields:fields.__setitem__(0,b'bad:')))
            def extra_copy(data):
                line=data[1]['raw_tcp'].splitlines(keepends=True)[-1];fields=line.split();fields[0]=b'999:'
                data[1]['raw_tcp']+=b' '.join(fields)+b'\n'
            self.reject('third_copy_of_same_row',extra_copy)
            foreign=b' 999: 0D01A8C0:DAD0 8301A8C0:270E 01 00000000:00000000 00:00000000 00000000 1001 0 999999999 1\n'
            self.reject('unknown_remote_peer',lambda data:data[1].update(raw_tcp=data[1]['raw_tcp']+foreign))
            self.reject('unknown_local_peer',lambda data:data[1].update(raw_tcp=data[1]['raw_tcp']+foreign.replace(b'0D01A8C0',b'8301A8C0')))
            def missing_pair(data):
                lines=data[1]['raw_tcp'].splitlines(keepends=True)
                index=next(i for i,line in enumerate(lines[1:],1)
                    if line.split()[3]==b'01'and line.split()[1]!=b'8301A8C0:270E')
                del lines[index];data[1]['raw_tcp']=b''.join(lines)
            self.reject('missing_established_owned_pair',missing_pair)
        def test_case_budget_cannot_reuse_reorder_overcount_or_undercharge(self):
            certificate=certify(fixture);self.assertEqual(candidate.closed_budget(p,[certificate])['events'],1)
            for name,values in [('reused_window',[certificate,certificate]),('event_count_over1024',[certificate]*1025)]:
                with self.assertRaises(ValueError):candidate.closed_budget(p,values)
                negatives.append(name)
            altered=copy.deepcopy(certificate);altered['charged_s']=0
            with self.assertRaises(ValueError):candidate.closed_budget(p,[altered])
            negatives.append('whole_window_not_charged')
            altered=copy.deepcopy(certificate);altered.update(window_s=3,charged_s=3,end_unix_s=altered['begin_unix_s']+3)
            with self.assertRaises(ValueError):candidate.closed_budget(p,[altered])
            negatives.append('window_over2s')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    output=Path(job['output']);output.mkdir(mode=0o700)
    receipt=dict(status='OWNED_EXACT_PROC_REPEAT_CPU_CONTRACTS_PASS_SYNTHETIC_AFTER_ONLY_NOT_LIVE_INTEGRATED',
        tests=result.testsRun,negative_checks=negatives,explicit_synthetic_positive=positive,
        actual_original_before=job['original_before'],actual_original_rejection=job['original_rejection'],
        positive_limit='After-sample raw TCP is copied from the original before sample; API/timing are explicitly synthetic. Old failed original stays invalid; a live bounded after-sample is still required.',
        component_limits=candidate.LIMITS,source_sha256=args.source_sha256,job_sha256=args.job_sha256,
        production_changed=False,scientific_guard_selected=False,quality_qualified=False,created_unix_s=time.time())
    h.put(output/'report.json',receipt);print(json.dumps(dict(status=receipt['status'],tests=result.testsRun,negative_checks=len(negatives))),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
