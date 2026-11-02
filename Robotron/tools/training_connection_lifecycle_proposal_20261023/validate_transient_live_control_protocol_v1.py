"""Strict original guards, coordinated real publication, bounded locks and load."""
import argparse,ast,copy,fcntl,hashlib,importlib.util,json,os,stat,subprocess,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def meta(s):return dict(dev=s.st_dev,ino=s.st_ino,nlink=s.st_nlink,size=s.st_size,uid=s.st_uid,mode=oct(stat.S_IMODE(s.st_mode)),mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-transient-live-control-validation-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_serial_h');protocol=load(job['protocol'],'_serial_protocol')
    for pin in job['inputs']:h.checked(pin)
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if '='in line)
    assert fields['MainPID']==str(os.getpid())and fields['InvocationID']==os.environ['INVOCATION_ID']
    root=Path(job['output']);root.mkdir(mode=0o700);negative=[]
    node,=[n for n in ast.walk(ast.parse(Path(job['original_contract_source']['path']).read_text()))if isinstance(n,ast.ClassDef)and n.name=='Contracts']
    namespace=dict(protocol=protocol,root=root,negative=negative,copy=copy,unittest=unittest,tempfile=tempfile,Path=Path,os=os)
    exec(compile(ast.Module(body=[node],type_ignores=[]),job['original_contract_source']['path'],'exec'),namespace)
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(namespace['Contracts']))
    assert tests.wasSuccessful()and tests.testsRun==3 and len(negative)==38
    original_guards=list(negative);records=[];real_fstat=os.fstat;real_read=os.read
    for mode in (0o644,0o444):
        for when in ('before_first_fstat','between_read_and_final_fstat'):
            directory=root/(oct(mode)+'-'+when);directory.mkdir(mode=0o700);path=directory/'live.json'
            old=dict(sequence=1,payload='old');new=dict(sequence=2,payload='new')
            protocol.publish_live(path,old);path.chmod(mode);inode=path.stat().st_ino
            started=threading.Event();done=threading.Event();errors=[];events=[];child=None;triggered=False
            def writer():
                started.set()
                try:protocol.publish_live(path,new);path.chmod(mode)
                except BaseException as e:errors.append(repr(e))
                finally:done.set()
            def trigger(fd):
                nonlocal child,triggered
                assert not triggered;triggered=True;before=real_fstat(fd)
                child=threading.Thread(target=writer);child.start();assert started.wait(timeout=1)
                if mode==0o644:
                    time.sleep(.01);assert not done.is_set();after=real_fstat(fd)
                    assert protocol._lock_identity(before)==protocol._lock_identity(after)and after.st_nlink==1
                else:
                    assert done.wait(timeout=1);after=real_fstat(fd);assert after.st_nlink==0
                events.append(dict(before=meta(before),after=meta(after),publisher_blocked_by_live_reader=mode==0o644))
            def fstat_hook(fd):
                s=real_fstat(fd)
                if s.st_ino==inode and when=='before_first_fstat'and not triggered:trigger(fd)
                return real_fstat(fd)
            def read_hook(fd,size):
                value=real_read(fd,size)
                if real_fstat(fd).st_ino==inode and when=='between_read_and_final_fstat'and not triggered:trigger(fd)
                return value
            try:
                with patch.object(protocol.os,'fstat',fstat_hook),patch.object(protocol.os,'read',read_hook):
                    value=protocol.checked_read(path,os.geteuid(),mode=mode)
            except ValueError as error:
                assert mode==0o444;expected='Original owned bounded regular protocol file required'if when=='before_first_fstat'else'Protocol bytes changed during original read'
                assert str(error)==expected;result=dict(rejected=True,error=str(error))
            else:assert mode==0o644 and value==old;result=dict(accepted_original_snapshot=True)
            finally:
                if child is not None:child.join(timeout=1)
            assert child is not None and not child.is_alive()and done.is_set()and not errors
            assert protocol.checked_read(path,os.geteuid(),mode=mode)==new
            records.append(dict(mode=oct(mode),interleave=when,events=events,result=result,writer_joined=True))
    # Real lock tampering is rejected before reading the live payload.
    lock_guards=[]
    for case in ('mode','hardlink','nonempty','symlink','FIFO','missing'):
        directory=root/('lock-'+case);directory.mkdir(mode=0o700);path=directory/'live.json'
        protocol.publish_live(path,dict(ok=True));lock=path.with_name(path.name+'.lock')
        if case=='mode':lock.chmod(0o644)
        elif case=='hardlink':os.link(lock,directory/'second-lock')
        elif case=='nonempty':lock.write_bytes(b'bad')
        elif case=='symlink':target=directory/'real-lock';os.rename(lock,target);lock.symlink_to(target)
        elif case=='FIFO':lock.unlink();os.mkfifo(lock,0o600)
        else:lock.unlink()
        try:protocol.checked_read(path,os.geteuid(),mode=0o644)
        except (ValueError,OSError)as error:lock_guards.append(dict(case=case,error=repr(error)))
        else:raise AssertionError('Unknown lock accepted: '+case)
    timeouts=[]
    for action in ('read','publish'):
        directory=root/('blocked-'+action);directory.mkdir(mode=0o700);path=directory/'live.json';protocol.publish_live(path,dict(sequence=1))
        before=h.pin(path);lock=path.with_name(path.name+'.lock');fd=os.open(lock,os.O_RDWR)
        fcntl.flock(fd,fcntl.LOCK_EX if action=='read'else fcntl.LOCK_SH);start=time.monotonic()
        try:
            try:
                if action=='read':protocol.checked_read(path,os.geteuid(),mode=0o644)
                else:protocol.publish_live(path,dict(sequence=2))
            except ValueError as error:assert str(error)=='Bounded original live lock wait exceeded'
            else:raise AssertionError('Contended lock did not time out')
        finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
        elapsed=time.monotonic()-start;assert .1<=elapsed<1 and h.pin(path)==before
        timeouts.append(dict(action=action,elapsed_s=elapsed,original_message_unchanged=True))
    path=root/'concurrent-live.json';protocol.publish_live(path,dict(sequence=0,payload='x'*1024))
    errors=[];sequences=[]
    def concurrent_writer():
        try:
            for sequence in range(1,5001):protocol.publish_live(path,dict(sequence=sequence,payload='x'*1024))
        except BaseException as e:errors.append(repr(e))
    child=threading.Thread(target=concurrent_writer);child.start();deadline=time.monotonic()+25
    while child.is_alive():
        assert time.monotonic()<deadline
        value=protocol.checked_read(path,os.geteuid(),mode=0o644)
        assert value['payload']=='x'*1024 and type(value['sequence'])is int and 0<=value['sequence']<=5000
        assert not sequences or value['sequence']>=sequences[-1]
        sequences.append(value['sequence']);time.sleep(.0005)
    child.join(timeout=1);assert not child.is_alive()and not errors and sequences
    assert protocol.checked_read(path,os.geteuid(),mode=0o644)['sequence']==5000
    # Controlled filesystem mechanism: pause actual fsync before old replacement.
    # This proves possibility only, never attributes the historical native stall.
    original=load(job['original_protocol'],'_durable_control_original')
    mechanism=[]
    for codec,name in ((original,'original_durable_v4'),(protocol,'prospective_transient_v5')):
        directory=root/name;directory.mkdir(mode=0o700);path=directory/'live.json'
        codec.publish_live(path,dict(sequence=0));entered=threading.Event();release=threading.Event();completed=threading.Event();failures=[];timing=[]
        def paused_sync(fd):
            entered.set();assert release.wait(timeout=2)
        def publisher():
            start=time.monotonic()
            try:codec.publish_live(path,dict(sequence=1))
            except BaseException as error:failures.append(repr(error))
            finally:timing.append(time.monotonic()-start);completed.set()
        with patch.object(codec.os,'fsync',paused_sync):
            child=threading.Thread(target=publisher);child.start()
            if name=='original_durable_v4':
                assert entered.wait(timeout=1)and not completed.is_set()
                start=time.monotonic()
                try:codec.checked_read(path,os.geteuid(),mode=0o644)
                except ValueError as error:assert str(error)=='Bounded original live lock wait exceeded';reader_error=repr(error)
                else:raise AssertionError('Original fsync-held lock did not fail')
                assert .1<=time.monotonic()-start<1
                time.sleep(.5);assert not completed.is_set();release.set()
            else:
                assert completed.wait(timeout=1)and not entered.is_set()
                assert codec.checked_read(path,os.geteuid(),mode=0o644)==dict(sequence=1);reader_error=None
            child.join(timeout=1)
        assert not child.is_alive()and not failures and codec.checked_read(path,os.geteuid(),mode=0o644)==dict(sequence=1)
        if name=='original_durable_v4':assert timing[0]>.5
        mechanism.append(dict(codec=name,publication_wall_s=timing[0],fsync_entered=entered.is_set(),reader_error=reader_error,actual_thread_joined=True))
    # Active publisher must make no filesystem durability call; finish remains strict.
    pnodes={n.name:n for n in ast.parse(Path(job['protocol']['path']).read_text()).body if isinstance(n,ast.FunctionDef)}
    assert not any(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='fsync'for n in ast.walk(pnodes['publish_live']))
    pin=h.put(root/'report.json',dict(schema='robotron-transient-live-control-validation-report-v1',protocol=job['protocol'],source_provenance=job['source_provenance'],
        original_unchanged_contract_tests=3,original_negative_checks=original_guards,actual_interleaves=records,actual_lock_rejections=lock_guards,
        actual_read_and_publish_timeouts=timeouts,concurrent_publications=5000,concurrent_reads=len(sequences),concurrent_read_sequences=h.put(root/'concurrent-read-sequences.json',sequences),
        actual_writer_joined=True,concurrent_errors=errors,controlled_fsync_mechanism=mechanism,old_run_root_cause_not_proven=True,live_projection_ephemeral=True,immutable_durable_raw_and_outcome_unchanged=True,strict_original_file_checks_unchanged=True,health_game_and_raw_limits_unchanged=True,
        production_changed=False,scientific_case=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=pin,original_guards=38,interleaves=4,lock_rejections=6,lock_timeouts=2,publications=5000,reads=len(sequences))),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
