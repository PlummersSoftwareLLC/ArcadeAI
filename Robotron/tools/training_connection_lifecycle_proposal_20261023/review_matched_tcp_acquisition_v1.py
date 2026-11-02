"""Verify every actual complete kernel table and both original acquisition arms."""
import argparse,base64,collections,hashlib,importlib.util,json,os,sys,time,zlib
from pathlib import Path
def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def unpack(value):
    assert value['encoding']=='zlib-base64'and 0<value['bytes']<=16<<20
    packed=base64.b64decode(value['base64'],validate=True);assert len(packed)==value['compressed_bytes']
    codec=zlib.decompressobj();raw=codec.decompress(packed,(16<<20)+1)
    assert codec.eof and not codec.unused_data and not codec.unconsumed_tail
    assert len(raw)==value['bytes']and hashlib.sha256(raw).hexdigest()==value['sha256'];return raw
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-matched-tcp-acquisition-independent-review-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_tcp_review_h');rd=load(job['reader'],'_tcp_review_r');arc=load(job['archive'],'_tcp_review_a');closer=load(job['closer'],'_tcp_review_c')
    def read(pin,as_json=True):return rd.read_pin(pin,as_json=as_json)
    for pin in job['inputs']:h.checked(pin)
    scope=closer.closeout(job['subject_directory'],h,arc,read,0);subject=read(job['subject_job']);report=read(job['subject_report'])
    assert report['precommitted_pairs']==report['actual_pairs']==subject['pairs']==2000 and len(report['records'])==4000
    assert report['main_before']['owner']==report['main_after']['owner']and report['main_before']['client_count']==report['main_after']['client_count']==192
    assert report['main_before']['held_inputs']==report['main_after']['held_inputs']==197 and report['quality_qualified']is report['observer_or_collector_fix_selected']is False
    summary={arm:dict(samples=0,repeat_samples=0,max_copies=1,more_than_two=0,total_read_wall_s=0.)for arm in ('original_buffered','explicit_os_read')}
    explicit_calls=collections.Counter();kernel_sizes=[];original_bytes=0
    for position,pin in enumerate(report['records']):
        index=position//2;order=['original_buffered','explicit_os_read']if index%2==0 else['explicit_os_read','original_buffered'];arm=order[position%2]
        row=read(pin);assert row['pair_index']==index and row['order']==order and row['arm']==arm
        assert row['original_io_source']==subject['original_io']==report['original_io']and row['all_original_rows_retained']
        full=unpack(row['complete_original_kernel_table']);selected=unpack(row['original_selected_table']);meta=row['original_tcp_meta']
        assert meta['full_proc_read_bytes']==len(full)and meta['full_proc_read_sha256']==hashlib.sha256(full).hexdigest()and meta['begin_unix_s']<=meta['end_unix_s']
        lines=full.splitlines(keepends=True);expected=[lines[0]];rows=[];identities=collections.defaultdict(list)
        for number,line in enumerate(lines[1:],1):
            fields=line.split();local,peer=fields[1].decode(),fields[2].decode()
            if int(local.split(':')[1],16)==9998 or int(peer.split(':')[1],16)==9998:
                expected.append(line);rows.append(dict(original_line_number=number,local=local,peer=peer,state=fields[3].decode(),inode=int(fields[9]),uid=int(fields[7])))
                if fields[3]==b'01':identities[tuple(fields[k].decode()for k in (1,2,3,7,9))].append(line.rstrip(b'\r\n').decode())
        assert b''.join(expected)==selected and rows==meta['selected_rows']
        repeated=[dict(identity=list(key),count=len(values),original_rows=values)for key,values in identities.items()if len(values)>1]
        assert repeated==row['repeated_connections']
        capture=row['read_metadata'];calls=capture['calls']
        if arm=='original_buffered':
            assert len(calls)==1 and calls[0]['kind']=='original_BufferedReader_read'and calls[0]['requested']==(16<<20)+1 and calls[0]['returned']==len(full)
        else:
            assert 2<=len(calls)<=512 and calls[-1]['returned']==0
            total=0
            for call in calls:
                assert call['kind']=='os.read'and call['requested']==(16<<20)+1-total and call['begin_monotonic_s']<=call['end_monotonic_s']
                total+=call['returned']
            assert total==len(full);explicit_calls[len(calls)]+=1
        stat=summary[arm];stat['samples']+=1;stat['repeat_samples']+=bool(repeated);maximum=max([1,*[x['count']for x in repeated]])
        stat['max_copies']=max(stat['max_copies'],maximum);stat['more_than_two']+=maximum>2;stat['total_read_wall_s']+=capture['read_wall_s']
        kernel_sizes.append(len(full));original_bytes+=len(full)
    assert summary==report['summary']and 'torch'not in sys.modules
    out=Path(job['output']);out.mkdir(mode=0o700)
    proof=h.put(out/'report.json',dict(schema='robotron-matched-tcp-acquisition-independent-review-v1',original_report=job['subject_report'],original_scope=scope,
        all4000_complete_kernel_tables_and_original_selected_rows_verified=True,all_explicit_read_calls_and_EOF_verified=True,explicit_read_call_count_histogram=dict(explicit_calls),
        original_kernel_bytes=original_bytes,kernel_size_min=min(kernel_sizes),kernel_size_max=max(kernel_sizes),summary=summary,
        diagnostic_does_not_cover_native_MAME_workload=True,neither_arm_quality_or_fix_qualified=True,original_copy_limit_unchanged=2,
        no_production_source_or_health_limit_change=True,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=proof,summary=summary,explicit_calls=dict(explicit_calls))),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
