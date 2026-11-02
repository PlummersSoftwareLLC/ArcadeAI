"""Bounded CPU contracts over original transport windows; no live socket/actions."""
import argparse
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
    job=json.loads(raw)
    assert job['schema']=='robotron-owned-cap-transport-certificate-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    output=Path(job['output']);output.mkdir(mode=0o700)
    def checked(pin):
        p=Path(pin['path']);raw=p.read_bytes()
        assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256']
        return p
    def load(name,pin):
        spec=importlib.util.spec_from_file_location(name,checked(pin))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    reader=load('_certificate_reader',job['reader'])
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    candidate=load('_owned_cap_certificate',job['candidate'])
    binding=read(job['binding']);report=read(job['trace_report']);initial_cursors=read(job['trace_initial_log_cursors'])
    fixtures=[]
    for selection in job['windows']:
        first,last=selection['first_index'],selection['last_index']
        cursors=copy.deepcopy(initial_cursors)
        for event in report['event_observations']:
            if event['index']>=first:continue
            record=read(event['observation'])
            for change in record['events']:
                if change['kind']=='original_actor_log_appended':
                    for chunk in change['chunks']:
                        cursor=cursors[str(chunk['slot'])]
                        assert cursor['offset']==chunk['offset']
                        payload=read(chunk['raw'],False);assert len(payload)==chunk['bytes']
                        cursor['offset']+=len(payload)
        samples=[]
        for index in range(first,last+1):
            record=read(report['samples'][index]);chunks=[]
            for event in record['events']:
                if event['kind']=='original_actor_log_appended':
                    chunks.extend([dict(chunk,raw=read(chunk['raw'],False)) for chunk in event['chunks']])
            samples.append(dict(index=index,observed_unix_s=record['observed_unix_s'],
                API_begin_unix_s=record['API_begin_unix_s'],API_end_unix_s=record['API_end_unix_s'],
                tcp_begin_unix_s=record['tcp']['begin_unix_s'],tcp_end_unix_s=record['tcp']['end_unix_s'],
                raw_API=read(record['API'],False),raw_tcp=read(record['tcp']['selected_raw'],False),
                raw_fds=read(record['latest_fd_view'],False),log_chunks=chunks))
        fixtures.append(dict(samples=samples,cursors=cursors,expected_slot=selection['slot']))
    certificates=[];negative_checks=[]
    def cert(fixture):
        return candidate.certify(binding,fixture['cursors'],candidate.LUA_SHA,fixture['samples'])
    def change_json(sample,key,function):
        value=json.loads(sample[key]);function(value)
        sample[key]=(json.dumps(value,separators=(',',':'),allow_nan=True)+'\n').encode()
    class Contracts(unittest.TestCase):
        def rejected(self,name,mutation):
            fixture=copy.deepcopy(fixtures[0]);mutation(fixture)
            with self.assertRaises((ValueError,KeyError,TypeError,IndexError)):
                cert(fixture)
            negative_checks.append(name)

        def test_original_two_complete_windows_and_one_cumulative_budget(self):
            for fixture in fixtures:
                result=cert(fixture)
                self.assertEqual(result['slot'],fixture['expected_slot'])
                self.assertEqual(result['overlap_samples'],1)
                self.assertFalse(result['quality_qualified'])
                self.assertTrue(result['all_nontransport_main_checks_still_required'])
                certificates.append(result)
            total=candidate.closed_budget(certificates)
            self.assertEqual(total['episodes'],2)
            self.assertLess(total['total_charged_s'],2)

        def test_omitted_partial_reordered_and_long_capture_windows_reject(self):
            self.rejected('omitted_before',lambda f:f['samples'].pop(0))
            self.rejected('omitted_after',lambda f:f['samples'].pop())
            self.rejected('omitted_middle',lambda f:f['samples'].pop(1))
            self.rejected('reordered_samples',lambda f:f['samples'].reverse())
            self.rejected('future_capture_clock',lambda f:f['samples'][1].update(observed_unix_s=f['samples'][1]['observed_unix_s']+3))

        def test_original_failed_API_cannot_use_unrelated_transport_evidence(self):
            for index,pin in enumerate(job['failed_original_APIs']):
                raw=read(pin,False)
                self.rejected('failed_original_API_'+str(index),lambda f,raw=raw:f['samples'][-2].update(raw_API=raw))

        def test_missing_wrong_or_skipped_log_evidence_rejects(self):
            self.rejected('no_cap_bytes',lambda f:[s.update(log_chunks=[])for s in f['samples']])
            def mutate_chunk(f,key,value):
                chunk=next(c for sample in f['samples'] for c in sample['log_chunks'] if candidate.CAP in c['raw'])
                chunk[key]=value(chunk[key])
            for key,function in [('inode',lambda x:x+1),('device',lambda x:x+1),
                                 ('path',lambda x:x+'.foreign'),('offset',lambda x:x+1),
                                 ('raw',lambda x:x.replace(candidate.CAP,b'not-a-cap'))]:
                self.rejected('bad_cap_'+key,lambda f,key=key,function=function:mutate_chunk(f,key,function))
            with self.assertRaises(ValueError):
                candidate.certify(binding,fixtures[0]['cursors'],'0'*64,fixtures[0]['samples'])
            negative_checks.append('wrong_held_Lua_source')

        def test_changed_actor_or_trainer_birth_and_missing_FD_owner_reject(self):
            slot=str(fixtures[0]['expected_slot'])
            for name,mutate in [
                ('actor_pid',lambda x:x['actors'][slot].update(pid=x['actors'][slot]['pid']+1)),
                ('actor_birth',lambda x:x['actors'][slot].update(starttime_ticks=x['actors'][slot]['starttime_ticks']+1)),
                ('trainer_pid',lambda x:x['trainer'].update(pid=x['trainer']['pid']+1)),
                ('trainer_birth',lambda x:x['trainer'].update(starttime_ticks=x['trainer']['starttime_ticks']+1)),
                ('missing_slot',lambda x:x['actors'].pop('0')),
                ('missing_target_sockets',lambda x:x['actors'][slot].update(socket_fds={}))]:
                self.rejected(name,lambda f,mutate=mutate:change_json(f['samples'][-1],'raw_fds',mutate))

        def test_unknown_real_TCP_shape_peers_and_socket_ownership_reject(self):
            foreign=b' 999: 0D01A8C0:DAD0 8301A8C0:270E 01 00000000:00000000 00:00000000 00000000 1001 0 999999999 1\n'
            self.rejected('unknown_remote_TCP_peer',lambda f:f['samples'][-2].update(raw_tcp=f['samples'][-2]['raw_tcp']+foreign))
            local=foreign.replace(b'0D01A8C0',b'8301A8C0')
            self.rejected('unowned_local_TCP_peer',lambda f:f['samples'][-2].update(raw_tcp=f['samples'][-2]['raw_tcp']+local))
            def remove_reverse_owner(f):
                sample=f['samples'][-1];table=candidate.tcp(sample['raw_tcp']);view=json.loads(sample['raw_fds'])
                slot=str(f['expected_slot']);owned=set(view['actors'][slot]['socket_fds'].values())
                client=next(row for row in table if row['state']=='01'and row['inode']in owned and int(row['peer'][9:],16)==9998)
                reverse=next(row for row in table if row['local']==client['peer']and row['peer']==client['local']and row['state']=='01')
                view['trainer']['socket_fds']={k:v for k,v in view['trainer']['socket_fds'].items()if v!=reverse['inode']}
                sample['raw_fds']=json.dumps(view).encode()
            self.rejected('missing_trainer_reverse_socket',remove_reverse_owner)

        def test_191_194_unknown_slot_duplicate_ID_and_stale_connection_reject(self):
            def missing(API):
                API['client_rows']=[row for row in API['client_rows']if row['client_slot']!=0];API['client_count']=len(API['client_rows'])
            self.rejected('API191',lambda f:change_json(f['samples'][0],'raw_API',missing))
            def extra(API):
                row=copy.deepcopy(API['client_rows'][0]);row['client_id']=999999;API['client_rows'].append(row);API['client_count']=len(API['client_rows'])
            self.rejected('API194',lambda f:change_json(f['samples'][-2],'raw_API',extra))
            self.rejected('foreign_slot',lambda f:change_json(f['samples'][-2],'raw_API',lambda x:x['client_rows'][0].update(client_slot=999)))
            self.rejected('duplicate_CID',lambda f:change_json(f['samples'][-2],'raw_API',lambda x:x['client_rows'][0].update(client_id=x['client_rows'][1]['client_id'])))
            def stale(API):
                for row in API['client_rows']:
                    if row['client_slot']==fixtures[0]['expected_slot']:row['connected_seconds']=100
            self.rejected('new_API_epoch_not_fresh',lambda f:change_json(f['samples'][-1],'raw_API',stale))

        def test_stale_or_future_API_and_FD_captures_reject(self):
            self.rejected('stale_API',lambda f:change_json(f['samples'][-2],'raw_API',lambda x:x.update(ts=x['ts']-10)))
            self.rejected('future_API',lambda f:change_json(f['samples'][-2],'raw_API',lambda x:x.update(ts=x['ts']+10)))
            self.rejected('stale_FD',lambda f:change_json(f['samples'][-2],'raw_fds',lambda x:x.update(begin_unix_s=x['begin_unix_s']-10,end_unix_s=x['end_unix_s']-10)))
            self.rejected('future_FD',lambda f:change_json(f['samples'][-2],'raw_fds',lambda x:x.update(begin_unix_s=x['begin_unix_s']+10,end_unix_s=x['end_unix_s']+10)))

        def test_duplicate_raw_JSON_and_malformed_TCP_reject(self):
            self.rejected('duplicate_JSON_key',lambda f:f['samples'][-2].update(raw_API=f['samples'][-2]['raw_API'].replace(b'{',b'{"client_count":193,',1)))
            self.rejected('incomplete_TCP_bytes',lambda f:f['samples'][-2].update(raw_tcp=f['samples'][-2]['raw_tcp'].rstrip(b'\n')))

        def test_cumulative_budget_rejects_reuse_count_time_and_reordering(self):
            first=cert(fixtures[0]);second=cert(fixtures[1])
            for name,values in [('reused_cap',[first,first]),('reordered_legs',[second,first]),
                                ('too_many_episodes',[first]*(candidate.LIMITS['max_episodes']+1))]:
                with self.assertRaises(ValueError):candidate.closed_budget(values)
                negative_checks.append(name)
            generated=[]
            for index in range(301):
                value=copy.deepcopy(first);value['begin_unix_s']=first['begin_unix_s']+index*3
                value['end_unix_s']=value['begin_unix_s']+2;value['charged_s']=2.
                value['cap']['offset']+=index*1000;generated.append(value)
            with self.assertRaises(ValueError):candidate.closed_budget(generated)
            negative_checks.append('whole_case_total_time')

    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():return 1
    assert 'torch' not in sys.modules
    for pin in [job['candidate'],job['reader'],job['binding'],job['trace_report']]:checked(pin)
    report=dict(schema='robotron-owned-cap-certificate-CPU-report-v1',
        status='ORIGINAL_TRANSPORT_CERTIFICATE_CONTRACTS_PASS_NOT_INTEGRATED',tests=result.testsRun,
        actual_original_windows=certificates,negative_checks=negative_checks,
        selected_component_limits=dict(candidate.LIMITS),source_sha256=args.source_sha256,
        job_sha256=args.job_sha256,candidate=job['candidate'],production_runtime_changed=False,
        new_scientific_guard_selected=False,old_failed_study_requalified=False,quality_qualified=False,
        limits=['Pure transport certificate on authenticated original trace windows and synthetic rejection mutations.',
                'All physical-census/source/control/recipe/pipeline/bank checks remain external and mandatory.',
                'No live collector/runtime/reviewer integration, scientific adoption or new policy comparison tested.'],
        created_unix_s=time.time())
    with (output/'report.json').open('x')as stream:
        json.dump(report,stream,separators=(',',':'),allow_nan=False);stream.write('\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],tests=result.testsRun,
        original_windows=len(certificates),negative_checks=len(negative_checks),report=str(output/'report.json'))),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
