"""CPU exact-equivalence contracts and interleaved join-only cost measurement.

All original raw rows/FD owners are retained. This never qualifies a historical
trace or a policy and never collects from or changes a production process.
"""
import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import time
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-indexed-owned-socket-join-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_join_test_h',job['helpers']);reader=load('_join_test_reader',job['reader'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    p=load('_join_test_original',job['primitives']);subject=load('_join_test_subject',job['candidate'])
    fast=subject.bind(p);cap=load('_join_test_cap',job['cap']);proc=load('_join_test_proc',job['proc'])
    base=load('_join_test_base',job['base_collector']);binding=reader.read_pin(job['binding'])
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    counts=collections.Counter();sample_proofs=[];bench=[];negative=[];measurement=None
    def outcome(function,table,view):
        try:return ('returned',function(table,view))
        except ValueError as error:return ('rejected',str(error))
    def parity(table,view):
        old=outcome(p.full_join,table,view);new=outcome(fast.full_join,table,view)
        assert old==new,(old[0],new[0])
        outer_old=outcome(lambda t,v:cap.full_owned_join(p,t,v),table,view)
        outer_new=outcome(lambda t,v:cap.full_owned_join(fast,t,v),table,view)
        assert outer_old==outer_new
        return old[0],outer_old[0]
    class Contracts(unittest.TestCase):
        def test_all_other_original_primitives_are_the_exact_original_objects(self):
            for name,value in vars(p).items():
                if not name.startswith('__')and name!='full_join':self.assertIs(getattr(fast,name),value,name)
        def test_all4196_authentic_original_TCP_FD_views_have_exact_results_or_rejections(self):
            for name,key in [('cap597','natural_report'),('cap104_2999','long_report'),('real_proc600','real_report')]:
                manifest=read(job[key]);local=collections.Counter();begin=time.monotonic()
                for index,pin in enumerate(manifest['samples']):
                    record=read(pin)
                    if key=='natural_report':
                        raw_tcp=read(record['tcp']['selected_raw'],False);raw_fd=read(record['latest_fd_view'],False)
                        now=record['observed_unix_s']
                    else:
                        sample=base.unpacked(record);raw_tcp=sample['raw_tcp'];raw_fd=sample['raw_fds'];now=sample['observed_unix_s']
                    table,repeats=proc.original_tcp(p,raw_tcp);view=p.fd_view(raw_fd,binding,now)
                    kinds=parity(table,view);local['all']+=1;local['full_join_'+kinds[0]]+=1;local['outer_'+kinds[1]]+=1
                    if repeats:local['actual_repeated_row_views']+=1
                    if len(bench)<64 and kinds==('returned','returned'):bench.append((table,view))
                counts.update(local);sample_proofs.append(dict(name=name,samples=local['all'],outcomes=dict(local),wall_s=time.monotonic()-begin))
            self.assertEqual(counts['all'],4196);self.assertEqual(counts['actual_repeated_row_views'],1)
        def test_missing_extra_duplicate_and_ambiguous_ownership_equivalence(self):
            table,view=bench[0];joined=p.full_join(table,view);slot=next(iter(joined));pair=joined[slot]
            mutations={
                'missing_client':lambda t,v:t.remove(next(row for row in t if row==pair['client'])),
                'missing_server':lambda t,v:t.remove(next(row for row in t if row==pair['server'])),
                'duplicate_server':lambda t,v:t.append(copy.deepcopy(pair['server'])),
                'missing_actor_FD':lambda t,v:v['actors'][slot].update(socket_fds={'99':1}),
                'missing_trainer_FD':lambda t,v:v['trainer'].update(socket_fds={'99':1}),
                'wrong_server_inode':lambda t,v:next(row for row in t if row==pair['server']).update(inode=1),
                'wrong_reverse_endpoint':lambda t,v:next(row for row in t if row==pair['server']).update(peer='8301A8C0:FFFF'),
                'nonestablished_client':lambda t,v:next(row for row in t if row==pair['client']).update(state='06'),
                'shared_training_inode':lambda t,v:v['actors'][slot].update(socket_fds=copy.deepcopy(v['actors'][next(s for s in v['actors']if s!=slot)]['socket_fds']))}
            for name,mutation in mutations.items():
                t=copy.deepcopy(table);v=copy.deepcopy(view);mutation(t,v)
                self.assertEqual(parity(t,v),('rejected','rejected'));negative.append(name)
            foreign=dict(local='0D01A8C0:DAD0',peer='8301A8C0:270E',state='01',inode=999999999,uid=1001)
            t=copy.deepcopy(table)+[foreign];self.assertEqual(parity(t,view),('returned','rejected'));negative.append('unknown_extra_client_still_rejected_by_full_owned_guard')
            # A shared unrelated FD must remain permitted; rejecting it would add
            # a new constraint beyond the original join. Neither view is mutated.
            t=copy.deepcopy(table);v=copy.deepcopy(view)
            for actor in v['actors'].values():actor['socket_fds']['10000']=999999998
            self.assertEqual(parity(t,v),('returned','returned'))
        def test_no_input_mutation_and_interleaved_join_only_cost(self):
            nonlocal measurement
            inputs=copy.deepcopy(bench);frozen=json.dumps(inputs,sort_keys=True)
            batches=[]
            for order in [('original','indexed'),('indexed','original'),('original','indexed')]:
                timing={}
                for label in order:
                    function=p.full_join if label=='original'else fast.full_join
                    started=time.perf_counter_ns()
                    for table,view in inputs:function(table,view)
                    timing[label]=(time.perf_counter_ns()-started)/1e9
                batches.append(dict(order=order,seconds=timing))
            self.assertEqual(json.dumps(inputs,sort_keys=True),frozen)
            old=statistics.median(batch['seconds']['original']for batch in batches)
            new=statistics.median(batch['seconds']['indexed']for batch in batches)
            measurement=dict(samples_per_batch=len(inputs),batches=batches,median_original_s=old,
                median_indexed_s=new,indexed_over_original_elapsed_ratio=new/old,
                scope='Join lookup only, pre-parsed authentic views; not complete health replay or useful training throughput.')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=dict(status='INDEXED_JOIN_EXACT4196_ORIGINAL_VIEWS_AND_NEGATIVE_EQUIVALENCE_PASS_NOT_SELECTED',
        tests=result.testsRun,negative_checks=negative,actual_view_counts=dict(counts),actual_trace_proofs=sample_proofs,
        interleaved_join_cost=measurement,original_invalid_traces_stay_invalid=True,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,candidate=job['candidate'],
        quality_qualified=False,scientific_guard_selected=False,production_changed=False,
        useful_training_throughput_gain_verified=False,created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,
        negative_checks=len(negative),views=counts['all'],join_elapsed_ratio=measurement['indexed_over_original_elapsed_ratio'])),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
