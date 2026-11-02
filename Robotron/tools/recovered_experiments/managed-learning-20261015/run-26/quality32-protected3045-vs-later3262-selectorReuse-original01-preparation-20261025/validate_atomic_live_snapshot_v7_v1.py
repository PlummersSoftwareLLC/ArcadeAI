"""Bounded actual3.14 snapshot contracts, races, contention and cost evidence."""
import argparse
import ast
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

N=Path(__file__).resolve().parent
G=N.parents[3]
F=N/'future-live-projection-contention-original01-preparation-20261026/atomic-snapshot-live-reader-original01'
OLD=G/'tools/training_connection_lifecycle_proposal_20261023/dedicated_main_health_protocol_transient_live_v5.py'
NEW=F/'dedicated_main_health_protocol_atomic_snapshot_v7.py'

def load(name,path,digest=None):
    if digest:assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--reader',choices=['old','new']);p.add_argument('--path',type=Path);a=p.parse_args()
    if not(a.execute or a.reader):print('PLAN_ONLY');return 0
    assert sys.version_info[:2]==(3,14)and not sys._is_gil_enabled()and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    old=load('_snapshot_old',OLD,'f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10')
    new=load('_snapshot_new',NEW,'e9809b32a29bf49e9de152933e7939865d868c7a73b9e8e73cf58088b0a7cbb0')
    if a.reader:
        codec=old if a.reader=='old'else new;decode=codec.decode
        def paused(raw):
            print(json.dumps(dict(pid=os.getpid(),birth=birth(os.getpid()),decode_paused=True)),flush=True)
            assert select.select([sys.stdin],[],[],5)[0]and sys.stdin.readline().strip()=='RELEASE'
            return decode(raw)
        codec.decode=paused;value=codec.checked_read(a.path,os.geteuid(),mode=0o644)
        print(json.dumps(dict(read=value)),flush=True);return 0
    h=load('_snapshot_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    root=F/'CPU-contracts-and-contention-original01/output-original01';assert not root.exists();root.mkdir(mode=0o700)
    protocol=new;negative=[]
    contract=G/'tools/training_connection_lifecycle_proposal_20261023/validate_dedicated_main_health_component_v1.py'
    assert h.pin(contract)['sha256']=='412a0bba6dc1c68cafd31557cd0d7b35e69b6b5c2e77bf7de4c89072c51b75f3'
    node,=[v for v in ast.walk(ast.parse(contract.read_text()))if isinstance(v,ast.ClassDef)and v.name=='Contracts']
    ns=dict(protocol=protocol,negative=negative,root=root,copy=copy,unittest=unittest,tempfile=tempfile,Path=Path,os=os)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(contract),'exec'),ns)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ns['Contracts']))
    assert result.wasSuccessful()and result.testsRun==3 and len(negative)==38
    groups=['original3_contracts_and38_negative_checks'];interleaves=[];lock_rejections=[];mutations=[];processes=[]
    def fixture(name,value=None):
        directory=root/name;directory.mkdir(mode=0o700);path=directory/'live.json'
        new.publish_live(path,dict(sequence=0)if value is None else value);return path
    # Real atomic replacements before first fstat and after the fd byte read.
    real_fstat=os.fstat;real_read=os.read
    for mode in (0o644,0o444):
        for when in ('before_first_fstat','after_read'):
            path=fixture(oct(mode)+'-'+when);path.chmod(mode);inode=path.stat().st_ino;triggered=[False]
            def replace():
                triggered[0]=True;new.publish_live(path,dict(sequence=1));path.chmod(mode)
            def fs(fd):
                if real_fstat(fd).st_ino==inode and when=='before_first_fstat'and not triggered[0]:replace()
                return real_fstat(fd)
            def rd(fd,size):
                raw=real_read(fd,size)
                if real_fstat(fd).st_ino==inode and when=='after_read'and not triggered[0]:replace()
                return raw
            with patch.object(new.os,'fstat',fs),patch.object(new.os,'read',rd):
                if mode==0o644:assert new.checked_read(path,os.geteuid(),mode=mode)==dict(sequence=1)
                else:
                    try:new.checked_read(path,os.geteuid(),mode=mode)
                    except ValueError:pass
                    else:raise AssertionError('Strict immutable finish read accepted replacement')
            assert triggered[0];interleaves.append(dict(mode=oct(mode),when=when,live_reobserved=mode==0o644,strict444_refused=mode==0o444))
    groups.append('four_actual_replacement_interleaves_live644_and_unchanged_strict444')
    for case in ('mode','hardlink','nonempty','symlink','FIFO','missing'):
        path=fixture('lock-'+case);lock=path.with_name(path.name+'.lock')
        if case=='mode':lock.chmod(0o644)
        elif case=='hardlink':os.link(lock,lock.with_name('second'))
        elif case=='nonempty':lock.write_bytes(b'bad')
        elif case=='symlink':target=lock.with_name('target');lock.rename(target);lock.symlink_to(target)
        elif case=='FIFO':lock.unlink();os.mkfifo(lock,0o600)
        else:lock.unlink()
        try:new.checked_read(path,os.geteuid(),mode=0o644)
        except (ValueError,OSError)as error:lock_rejections.append(dict(case=case,error=repr(error)))
        else:raise AssertionError('Unknown lock metadata accepted: '+case)
    groups.append('all6_original_lock_metadata_negatives')
    for case in ('FIFO','directory','symlink','hardlink','mode','missing'):
        path=fixture('data-'+case)
        if case=='hardlink':os.link(path,path.with_name('second'))
        elif case=='mode':path.chmod(0o666)
        else:
            path.unlink()
            if case=='FIFO':os.mkfifo(path,0o644)
            elif case=='directory':path.mkdir(mode=0o755)
            elif case=='symlink':target=path.with_name('target');target.write_text('{}');path.symlink_to(target)
        started=time.monotonic()
        try:new.checked_read(path,os.geteuid(),mode=0o644)
        except (ValueError,OSError):pass
        else:raise AssertionError('Malformed live data accepted: '+case)
        assert time.monotonic()-started<1
    groups.append('nonblocking_FIFO_directory_symlink_hardlink_mode_and_missing_data_refusals')
    for case in ('rewrite','mode','link_churn','bad_replacement'):
        path=fixture('mutation-'+case);inode=path.stat().st_ino;triggered=[False]
        def mutate(fd,size):
            raw=real_read(fd,size)
            if real_fstat(fd).st_ino==inode and not triggered[0]:
                triggered[0]=True
                if case=='rewrite':path.write_text('{"sequence":9}')
                elif case=='mode':path.chmod(0o600)
                elif case=='link_churn':link=path.with_name('other');os.link(path,link);link.unlink()
                else:path.unlink();path.symlink_to(path.with_name('missing'))
            return raw
        with patch.object(new.os,'read',mutate):
            try:new.checked_read(path,os.geteuid(),mode=0o644)
            except (ValueError,OSError)as error:mutations.append(dict(case=case,error=repr(error)))
            else:raise AssertionError('Changed live bytes/identity accepted: '+case)
        assert triggered[0]
    groups.append('in_place_rewrite_mode_link_churn_and_foreign_replacement_refusals')
    path=fixture('bounded-replacements');original_check=new._live_file;attempts=[]
    def retire(s,uid,**kw):
        original_check(s,uid,**kw);attempts.append(s.st_ino);new.publish_live(path,dict(sequence=len(attempts)))
    with patch.object(new,'_live_file',retire):
        try:new.checked_read(path,os.geteuid(),mode=0o644)
        except ValueError as error:assert str(error)=='Bounded atomic live snapshot replacement attempts exceeded'
        else:raise AssertionError('Unlimited replacement reobservations accepted')
    assert len(attempts)==8;groups.append('exact8_bounded_reobservations_and_no_decode_of_retired_data')
    # Reader never needs flock. Publisher still enforces its original100ms limit.
    path=fixture('reader-no-flock')
    with patch.object(new.fcntl,'flock',side_effect=AssertionError('Reader must not acquire flock')):
        assert new.checked_read(path,os.geteuid(),mode=0o644)==dict(sequence=0)
    path=fixture('publisher-still-bounded');fd=os.open(path.with_name(path.name+'.lock'),os.O_RDWR)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);start=time.monotonic()
        try:new.publish_live(path,dict(sequence=1))
        except ValueError as error:assert str(error)=='Bounded original live lock wait exceeded'
        else:raise AssertionError('Publisher lock limit changed')
        assert .1<=time.monotonic()-start<1
    finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
    groups.append('reader_no_flock_and_original_publisher100ms_bound')
    for name,codec in [('old',old),('new',new)]:
        path=fixture('cross-process-'+name);argv=[sys.executable,'-Xgil=0','-I','-B',str(Path(__file__).resolve()),'--reader',name,'--path',str(path)]
        child=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert select.select([child.stdout],[],[],5)[0];held_line=child.stdout.readline();held=json.loads(held_line)
        assert held['pid']==child.pid and held['birth']==birth(child.pid)
        start=time.monotonic();error=None
        try:
            try:codec.publish_live(path,dict(sequence=1))
            except ValueError as exc:assert name=='old'and str(exc)=='Bounded original live lock wait exceeded';error=repr(exc)
            else:assert name=='new'
            elapsed=time.monotonic()-start
            tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
            if name=='old':assert elapsed>=.1 and tmp.exists()and json.loads(path.read_bytes())==dict(sequence=0)
            else:assert not tmp.exists()and json.loads(path.read_bytes())==dict(sequence=1)
        finally:child.stdin.write('RELEASE\n');child.stdin.flush();stdout,stderr=child.communicate(timeout=5)
        assert child.returncode==0 and not stderr and birth(child.pid)!=held['birth']
        assert json.loads(stdout)['read']==dict(sequence=0)
        processes.append(dict(codec=name,argv=argv,owner=held,actual_exit=0,birth_absent=True,
            original_stdout=held_line+stdout,original_stderr=stderr,publisher_error=error,publisher_elapsed_s=elapsed))
    groups.append('actual_separate_free_threaded_reader_pause_old_failure_new_publication_success')
    path=fixture('concurrent',dict(sequence=0,payload='x'*1024));errors=[];values=[]
    def writer():
        try:
            for index in range(1,5001):new.publish_live(path,dict(sequence=index,payload='x'*1024))
        except BaseException as error:errors.append(repr(error))
    thread=threading.Thread(target=writer);thread.start();deadline=time.monotonic()+40
    try:
        while thread.is_alive():
            assert time.monotonic()<deadline
            row=new.checked_read(path,os.geteuid(),mode=0o644)
            assert row['payload']=='x'*1024 and 0<=row['sequence']<=5000 and(not values or row['sequence']>=values[-1])
            values.append(row['sequence'])
    finally:thread.join(timeout=5)
    assert not thread.is_alive()and not errors and values
    assert new.checked_read(path,os.geteuid(),mode=0o644)['sequence']==5000
    groups.append('5000_atomic_publications_with_monotonic_valid_concurrent_reads')
    # Descriptive matched-read ABBA CPU costs; no native throughput claim.
    costs=[];path=fixture('cost',dict(sequence=0,payload='x'*3758))
    for label,codec in [('A1',old),('B1',new),('B2',new),('A2',old)]:
        begin=time.monotonic_ns();cpu=time.thread_time_ns()
        for _ in range(2000):assert codec.checked_read(path,os.geteuid(),mode=0o644)['sequence']==0
        costs.append(dict(arm=label,reads=2000,thread_CPU_ns=time.thread_time_ns()-cpu,elapsed_ns=time.monotonic_ns()-begin))
    groups.append('descriptive_ABBA2000_same_payload_read_costs')
    before={v.name:ast.dump(v,include_attributes=False)for v in ast.parse(OLD.read_text()).body if isinstance(v,ast.FunctionDef)}
    after={v.name:ast.dump(v,include_attributes=False)for v in ast.parse(NEW.read_text()).body if isinstance(v,ast.FunctionDef)}
    assert [k for k in before if before[k]!=after[k]]==['checked_read']
    assert new.LIVE_LOCK_WAIT_S==.1 and new.MAX_MESSAGE_BYTES==65536 and new.LIVE_SNAPSHOT_MAX_ATTEMPTS==8
    assert 'torch'not in sys.modules;groups.append('unchanged_publisher_strict444_decode_and_live_finish_validation_AST')
    report=h.put(root/'report.json',dict(schema='robotron-atomic-live-snapshot-v7-actual-CPU-contract-report-v1',
        source=h.pin(__file__),protocol=h.pin(NEW),parent_protocol=h.pin(OLD),interpreter=sys.version,free_threaded=True,
        groups=groups,groups_passed=len(groups),original_contract_methods=3,original_negative_checks=negative,
        interleaves=interleaves,original_lock_metadata_rejections=lock_rejections,mutation_rejections=mutations,
        bounded_reobservations=len(attempts),cross_process_regressions=processes,concurrent_publications=5000,
        concurrent_reads=len(values),concurrent_read_sequences=h.put(root/'concurrent-read-sequences.json',values),
        all_original_children_and_threads_joined=True,descriptive_ABBA_read_costs=costs,
        live_freshness_and_raw_gap_and_publisher_lock_bounds_unchanged=True,
        native_observer_integration_verified=False,native_launch_ready=False,quality_qualified=False,
        throughput_gain_verified=False,original_native_cause_proven=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,groups_passed=len(groups),passed=True)),flush=True);time.sleep(8);return 0

if __name__=='__main__':raise SystemExit(main())
