"""Capture actual fstat/lstat values at the prospective reader's first failure."""
import argparse,hashlib,importlib.util,inspect,json,os,stat,threading,time
from pathlib import Path

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def meta(s):return dict(dev=s.st_dev,ino=s.st_ino,nlink=s.st_nlink,size=s.st_size,uid=s.st_uid,mode=oct(stat.S_IMODE(s.st_mode)),mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-live-snapshot-retirement-order-diagnostic-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_retire_h');protocol=load(job['protocol'],'_retire_protocol')
    for pin in job['inputs']:h.checked(pin)
    root=Path(job['output']);root.mkdir(mode=0o700);path=root/'live.json';protocol.publish_live(path,dict(sequence=0,payload='x'*1024))
    original_require=protocol.require;failure=[];stop=threading.Event();writer_errors=[];published=[];reads=0
    def require(value,message):
        if not value:
            caller=inspect.currentframe().f_back
            local=caller.f_locals
            event=dict(message=message,monotonic_s=time.monotonic(),function=caller.f_code.co_name,
                metadata={key:meta(local[key])for key in ('before','after','replacement')if key in local})
            if 'fd'in local:
                event['fd_at_failure']=meta(os.fstat(local['fd']))
                data=os.pread(local['fd'],65537,0);event['fd_bytes_sha256']=hashlib.sha256(data).hexdigest();event['fd_value']=json.loads(data)
            if 'raw'in local:event['original_read_bytes_sha256']=hashlib.sha256(local['raw']).hexdigest()
            event['named_at_failure']=meta(path.lstat());failure.append(event);stop.set()
            del caller
        return original_require(value,message)
    protocol.require=require
    def writer():
        try:
            for sequence in range(1,5001):
                if stop.is_set():break
                protocol.publish_live(path,dict(sequence=sequence,payload='x'*1024));published.append(sequence)
        except BaseException as error:writer_errors.append(repr(error));stop.set()
    started=time.monotonic();thread=threading.Thread(target=writer);thread.start()
    while thread.is_alive()and not stop.is_set():
        assert time.monotonic()-started<25
        try:protocol.checked_read(path,os.geteuid(),mode=0o644)
        except ValueError:
            assert failure;break
        reads+=1
    thread.join(timeout=5);assert not thread.is_alive()and not writer_errors
    assert len(failure)<=1
    if failure:
        event=failure[0]
        assert event['message']=='Retired live snapshot lacks a distinct owned replacement'
        before,after,replacement=(event['metadata'][k]for k in ('before','after','replacement'))
        assert (after['dev'],after['ino'])==(replacement['dev'],replacement['ino'])and after['nlink']==0
        assert event['fd_bytes_sha256']==event['original_read_bytes_sha256']
    pin=h.put(root/'report.json',dict(schema='robotron-live-snapshot-retirement-order-diagnostic-report-v1',protocol=job['protocol'],
        first_failure=failure,completed_reads=reads,completed_publications=len(published),maximum_precommitted_publications=5000,
        original_require_failure_preserved=True,hooks_record_failure_only=True,metadata_not_fabricated=True,
        real_concurrent_os_replace=True,actual_writer_joined=True,kernel=list(os.uname()),wall_s=time.monotonic()-started,
        production_changed=False,scientific_case=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=pin,failure_reproduced=bool(failure),reads=reads,published=len(published))),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
