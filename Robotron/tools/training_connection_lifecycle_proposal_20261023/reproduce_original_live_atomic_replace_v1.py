"""Deterministically interleave the original reader/publisher on actual files."""
import argparse,hashlib,importlib.util,json,os,stat,subprocess,time
from pathlib import Path
from unittest.mock import patch

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def metadata(s):
    return dict(device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,uid=s.st_uid,
        mode=oct(stat.S_IMODE(s.st_mode)),bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job')
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-original-live-atomic-replace-reproduction-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_atomic_repro_h');codec=load(job['protocol'],'_atomic_repro_protocol')
    for pin in job['inputs']:h.checked(pin)
    unit=subprocess.run(['systemctl','--user','show',job['unit']],capture_output=True,text=True,check=True,timeout=5)
    fields=dict(line.split('=',1)for line in unit.stdout.splitlines()if '='in line)
    assert fields['MainPID']==str(os.getpid()) and fields['InvocationID']==os.environ['INVOCATION_ID']
    for key,value in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no').items():assert fields[key]==value
    root=Path(job['output']);root.mkdir(mode=0o700)
    old=dict(snapshot='original-valid-immutable-bytes',sequence=1)
    new=dict(snapshot='replacement-valid-immutable-bytes',sequence=2)
    real_fstat=os.fstat;real_read=os.read;records=[]
    for mode in (0o644,0o444):
        for interleave in ('before_first_fstat','between_read_and_final_fstat'):
            directory=root/(oct(mode)+'-'+interleave);directory.mkdir(mode=0o700)
            path=directory/'message.json';codec.publish_live(path,old);path.chmod(mode)
            events=[];triggered=False
            def replace(fd):
                nonlocal triggered
                assert not triggered;triggered=True
                before=real_fstat(fd);old_bytes=real_read(fd,codec.MAX_MESSAGE_BYTES+1);os.lseek(fd,0,os.SEEK_SET)
                codec.publish_live(path,new);path.chmod(mode)
                retired=real_fstat(fd);current=path.lstat()
                assert before.st_nlink==1 and retired.st_nlink==0 and current.st_nlink==1
                assert (before.st_dev,before.st_ino)==(retired.st_dev,retired.st_ino)!=(current.st_dev,current.st_ino)
                assert codec.decode(old_bytes)==old and path.read_bytes()!=old_bytes
                events.append(dict(before=metadata(before),retired=metadata(retired),replacement=metadata(current),
                    original_bytes_sha256=hashlib.sha256(old_bytes).hexdigest(),original_bytes_unchanged=True))
            def fstat_hook(fd):
                if not triggered:replace(fd)
                return real_fstat(fd)
            def read_hook(fd,size):
                value=real_read(fd,size)
                if not triggered:replace(fd)
                return value
            target='fstat'if interleave=='before_first_fstat'else'read'
            hook=fstat_hook if target=='fstat'else read_hook
            try:
                with patch.object(codec.os,target,hook):codec.checked_read(path,os.geteuid(),mode=mode)
            except ValueError as error:message=str(error)
            else:raise AssertionError('Original reader must reject the real retired-inode interleave')
            expected='Original owned bounded regular protocol file required'if target=='fstat'else'Protocol bytes changed during original read'
            assert message==expected and triggered and len(events)==1
            assert codec.checked_read(path,os.geteuid(),mode=mode)==new
            records.append(dict(mode=oct(mode),interleave=interleave,original_error=message,real_filesystem_events=events,
                current_published_file=h.pin(path),subsequent_unraced_read_succeeds=True))
    report=dict(schema='robotron-original-live-atomic-replace-reproduction-report-v1',cases=records,
        actual_os_replace_and_fd_metadata_verified=True,source_function_not_rewritten=True,
        hooks_control_interleaving_only=True,original_protocol=job['protocol'],
        first_error_matches_original_native_failure=True,retrospective_original_fstat_field_known=False,
        immutable_finish_reader_also_rejects_retired_inode=True,production_changed=False,
        scientific_case=False,quality_qualified=False,created_unix_s=time.time())
    pin=h.put(root/'report.json',report);print(json.dumps(dict(report=pin,cases=len(records))),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
