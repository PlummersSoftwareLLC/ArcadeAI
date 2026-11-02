"""Original protocol guards plus real retired-inode and mutation fixtures."""
import argparse,ast,copy,hashlib,importlib.util,json,os,stat,subprocess,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def meta(s):
    return dict(device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,uid=s.st_uid,
        mode=oct(stat.S_IMODE(s.st_mode)),bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job')
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-live-atomic-snapshot-protocol-validation-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_snapshot_tests_h');protocol=load(job['protocol'],'_snapshot_tests_protocol')
    for pin in job['inputs']:h.checked(pin)
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if '='in line)
    assert fields['MainPID']==str(os.getpid()) and fields['InvocationID']==os.environ['INVOCATION_ID']
    for k,v in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no').items():assert fields[k]==v
    root=Path(job['output']);root.mkdir(mode=0o700);negative=[]
    # Execute the original nested Contracts class unchanged, with this protocol.
    original_tests=Path(job['original_contract_source']['path']).read_text()
    node,=[n for n in ast.walk(ast.parse(original_tests))if isinstance(n,ast.ClassDef)and n.name=='Contracts']
    namespace=dict(protocol=protocol,root=root,negative=negative,copy=copy,unittest=unittest,tempfile=tempfile,Path=Path,os=os)
    exec(compile(ast.Module(body=[node],type_ignores=[]),job['original_contract_source']['path'],'exec'),namespace)
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(namespace['Contracts']))
    assert tests.wasSuccessful() and tests.testsRun==3 and len(negative)==38
    records=[];real_fstat=os.fstat;real_read=os.read;old=dict(sequence=1,payload='original');new=dict(sequence=2,payload='replacement')
    cases=[(0o644,when,'none',True)for when in ('before_first_fstat','between_read_and_final_fstat')]
    cases +=[(0o444,when,'none',False)for when in ('before_first_fstat','between_read_and_final_fstat')]
    cases +=[(0o644,'between_read_and_final_fstat',change,False)for change in
        ('replacement_mode','replacement_hardlink','replacement_symlink','replacement_missing','replacement_directory','replacement_fifo','retired_bytes_mutated')]
    cases +=[(0o644,'no_replacement',change,False)for change in ('in_place_bytes','in_place_ctime')]
    cases +=[(0o644,'before_first_fstat','retired_ctime_later_changed',False)]
    for index,(mode,when,change,accepted)in enumerate(cases):
        directory=root/('case-%02d'%index);directory.mkdir(mode=0o700);path=directory/'message.json'
        protocol.publish_live(path,old);path.chmod(mode);writefd=os.open(path,os.O_RDWR if mode==0o644 else os.O_RDONLY)
        triggered=False;mutation_done=False;events=[]
        def replace(fd):
            nonlocal triggered
            assert not triggered;triggered=True;before=real_fstat(fd);data=os.pread(fd,65537,0)
            protocol.publish_live(path,new);path.chmod(mode)
            retired=real_fstat(fd);replacement=path.lstat()
            assert before.st_nlink==1 and retired.st_nlink==0 and replacement.st_nlink==1
            assert before.st_ino==retired.st_ino!=replacement.st_ino and protocol.decode(data)==old
            events.append(dict(before=meta(before),retired=meta(retired),replacement=meta(replacement)))
            if change=='replacement_mode':path.chmod(0o444)
            elif change=='replacement_hardlink':os.link(path,directory/'second-link.json')
            elif change=='replacement_symlink':
                target=directory/'target.json';os.rename(path,target);path.symlink_to(target)
            elif change=='replacement_missing':path.unlink()
            elif change in ('replacement_directory','replacement_fifo'):
                path.unlink()
                if change=='replacement_directory':path.mkdir()
                else:os.mkfifo(path,0o644)
            elif change=='retired_bytes_mutated':
                stamp=real_fstat(writefd);os.pwrite(writefd,b'{"bad":true}',0)
                os.utime(writefd,ns=(stamp.st_atime_ns,stamp.st_mtime_ns+1))
        def fstat_hook(fd):
            if when=='before_first_fstat'and not triggered:replace(fd)
            return real_fstat(fd)
        def read_hook(fd,size):
            nonlocal mutation_done
            value=real_read(fd,size)
            if when=='between_read_and_final_fstat'and not triggered:replace(fd)
            if not mutation_done and change in ('in_place_bytes','in_place_ctime','retired_ctime_later_changed'):
                mutation_done=True;before=real_fstat(writefd)
                if change=='in_place_bytes':
                    os.pwrite(writefd,b'{"bad":true}',0);os.utime(writefd,ns=(before.st_atime_ns,before.st_mtime_ns+1))
                else:os.fchmod(writefd,0o600);os.fchmod(writefd,mode)
                after=real_fstat(writefd);assert before.st_ctime_ns!=after.st_ctime_ns
                events.append(dict(mutation_before=meta(before),mutation_after=meta(after)))
            return value
        try:
            try:
                with patch.object(protocol.os,'fstat',fstat_hook),patch.object(protocol.os,'read',read_hook):
                    value=protocol.checked_read(path,os.geteuid(),mode=mode)
            except (ValueError,OSError)as error:
                assert not accepted,(index,repr(error));outcome=dict(accepted=False,error_type=type(error).__name__,error=str(error))
            else:
                assert accepted and value==old,(index,value);outcome=dict(accepted=True,original_snapshot=value)
            records.append(dict(index=index,mode=oct(mode),interleave=when,change=change,expected_accept=accepted,actual=outcome,events=events))
        finally:os.close(writefd)
    # Nonblocking opening rejects an actual FIFO without waiting for a writer.
    fifo=root/'source-fifo';os.mkfifo(fifo,0o644)
    try:protocol.checked_read(fifo,os.geteuid(),mode=0o644)
    except ValueError:negative.append('live:actual_source_FIFO')
    else:raise AssertionError('FIFO must be rejected')
    # Real concurrent publication, with no interleaving hooks and no read retries.
    concurrent=root/'concurrent-live.json';protocol.publish_live(concurrent,dict(sequence=0,payload='x'*1024))
    failures=[];sequences=[]
    def writer():
        try:
            for sequence in range(1,501):protocol.publish_live(concurrent,dict(sequence=sequence,payload='x'*1024))
        except BaseException as error:failures.append(repr(error))
    thread=threading.Thread(target=writer);thread.start();deadline=time.monotonic()+20
    while thread.is_alive():
        assert time.monotonic()<deadline and len(sequences)<100000
        value=protocol.checked_read(concurrent,os.geteuid(),mode=0o644)
        assert set(value)=={'sequence','payload'}and value['payload']=='x'*1024
        assert type(value['sequence'])is int and 0<=value['sequence']<=500
        assert not sequences or value['sequence']>=sequences[-1]
        sequences.append(value['sequence'])
    thread.join(timeout=1);assert not thread.is_alive()and not failures
    assert protocol.checked_read(concurrent,os.geteuid(),mode=0o644)['sequence']==500
    assert sequences
    transcript=h.put(root/'concurrent-read-sequences.json',sequences)
    report=dict(schema='robotron-live-atomic-snapshot-protocol-validation-report-v1',protocol=job['protocol'],source_provenance=job['source_provenance'],
        original_unchanged_contract_tests=tests.testsRun,original_negative_checks=negative[:38],additional_negative_checks=negative[38:],
        real_filesystem_interleaves_and_mutations=records,concurrent_publications=500,concurrent_reads=len(sequences),concurrent_read_sequences=transcript,
        concurrent_errors=failures,actual_writer_thread_joined=True,immutable_finish_original_strict_reader_retained=True,
        no_read_retries_or_health_sample_changes=True,production_changed=False,scientific_case=False,quality_qualified=False,created_unix_s=time.time())
    pin=h.put(root/'report.json',report);print(json.dumps(dict(report=pin,original_guards=38,real_cases=len(records),concurrent_reads=len(sequences))),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
