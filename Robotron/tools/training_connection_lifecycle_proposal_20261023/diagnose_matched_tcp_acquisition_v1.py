"""Read-only matched TCP reader probe; never changes parser limits or runtime."""
import argparse,base64,builtins,collections,hashlib,importlib.util,json,os,subprocess,sys,time,zlib
from pathlib import Path
BOUND=(16<<20)+1
def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def encode(raw):
    compressed=zlib.compress(raw,1)
    return dict(encoding='zlib-base64',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),compressed_bytes=len(compressed),base64=base64.b64encode(compressed).decode())
def repetitions(raw):
    identities=collections.defaultdict(list)
    for line in raw.splitlines()[1:]:
        cells=line.split();assert len(cells)>=10
        if cells[3]==b'01'and(int(cells[1].split(b':')[1],16)==9998 or int(cells[2].split(b':')[1],16)==9998):
            key=tuple(cells[i].decode()for i in (1,2,3,7,9));identities[key].append(line.decode())
    return [dict(identity=list(key),count=len(rows),original_rows=rows)for key,rows in identities.items()if len(rows)>1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-matched-tcp-acquisition-diagnostic-job-v1'and job['pairs']==2000 and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_tcp_probe_h');io=load(job['original_io'],'_tcp_probe_original_io')
    for pin in job['inputs']:h.checked(pin)
    root=Path(job['output']);root.mkdir(mode=0o700);records=root/'records';records.mkdir(mode=0o700)
    def monitor():return json.loads(subprocess.check_output(['/usr/bin/python3.12','-I','-B',job['main_monitor']['path']],text=True,timeout=25))
    before=monitor();assert before['client_count']==192 and before['held_inputs']==197
    manifest=[];summary={arm:dict(samples=0,repeat_samples=0,max_copies=1,more_than_two=0,total_read_wall_s=0.)for arm in ('original_buffered','explicit_os_read')}
    started=time.monotonic();deadline=started+120
    for index in range(job['pairs']):
        assert time.monotonic()<deadline,'Precommitted matched TCP probe bound exceeded'
        arms=('original_buffered','explicit_os_read')if index%2==0 else('explicit_os_read','original_buffered')
        for arm in arms:
            captured=[]
            class Stream:
                def __init__(self,path,mode):
                    assert path=='/proc/net/tcp'and mode=='rb';self.calls=[]
                    self.stream=builtins.open(path,mode)if arm=='original_buffered'else None
                    self.fd=None if self.stream is not None else os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                def __enter__(self):return self
                def __exit__(self,*unused):
                    if self.stream is not None:self.stream.close()
                    else:os.close(self.fd)
                def read(self,size):
                    assert size==BOUND;t=time.monotonic()
                    if self.stream is not None:
                        data=self.stream.read(size);self.calls.append(dict(kind='original_BufferedReader_read',requested=size,returned=len(data),actual_lower_level_syscalls_not_instrumented=True))
                    else:
                        chunks=[];count=0
                        while count<size:
                            assert len(self.calls)<512 and time.monotonic()<deadline
                            call_begin=time.monotonic();chunk=os.read(self.fd,size-count)
                            self.calls.append(dict(kind='os.read',requested=size-count,returned=len(chunk),begin_monotonic_s=call_begin,end_monotonic_s=time.monotonic()))
                            if not chunk:break
                            chunks.append(chunk);count+=len(chunk)
                        assert self.calls[-1]['returned']==0,'Explicit original EOF required'
                        data=b''.join(chunks)
                    assert 0<len(data)<BOUND;captured.append(dict(raw=data,calls=self.calls,read_wall_s=time.monotonic()-t));return data
            # Replace only this fresh module's open dependency. Its pinned tcp
            # function body and its port selection/row construction stay exact.
            io.open=Stream
            meta,selected=io.tcp();capture,=captured;original=capture.pop('raw')
            assert meta['full_proc_read_bytes']==len(original)and meta['full_proc_read_sha256']==hashlib.sha256(original).hexdigest()
            repeated=repetitions(selected);stat=summary[arm];stat['samples']+=1;stat['repeat_samples']+=bool(repeated)
            maximum=max([1,*[row['count']for row in repeated]]);stat['max_copies']=max(stat['max_copies'],maximum);stat['more_than_two']+=maximum>2;stat['total_read_wall_s']+=capture['read_wall_s']
            rp=h.put(records/('%04d-%s.json'%(index,arm)),dict(schema='robotron-matched-tcp-original-acquisition-record-v1',pair_index=index,arm=arm,order=list(arms),original_io_source=job['original_io'],
                original_tcp_meta=meta,complete_original_kernel_table=encode(original),original_selected_table=encode(selected),read_metadata=capture,
                repeated_connections=repeated,all_original_rows_retained=True,no_health_qualification=True))
            manifest.append(rp)
        if index%250==0:
            stat=Path('/proc',str(before['owner']['pid']),'stat').read_text();assert int(stat.rsplit(')',1)[1].split()[19])==before['owner']['starttime_ticks']
    after=monitor();assert after['client_count']==192 and after['held_inputs']==197 and before['owner']==after['owner']
    for pin in job['inputs']:h.checked(pin)
    assert 'torch'not in sys.modules and all(v['samples']==2000 for v in summary.values())
    report=h.put(root/'report.json',dict(schema='robotron-matched-tcp-acquisition-diagnostic-report-v1',original_io=job['original_io'],records=manifest,summary=summary,
        precommitted_pairs=2000,actual_pairs=2000,alternating_original_arm_order=True,main_before=before,main_after=after,wall_s=time.monotonic()-started,
        exact_original_tcp_body_and_port_selection_reused=True,complete_original_kernel_bytes_retained=True,no_raw_row_filter_retry_or_normalization_added=True,
        original_copy_limit_unchanged=2,observer_or_collector_fix_selected=False,production_changed=False,scientific_case=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,summary=summary)),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
