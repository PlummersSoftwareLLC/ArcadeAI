"""Actual running-projection coalescence guards; no raw-health claims."""
import argparse
import copy
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time
from unittest.mock import patch

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def check(protocol,old,root,h,sample):
    assert sys.version_info[:2]==(3,14)and not sys._is_gil_enabled()
    jp,job,owner,template=sample;events=[]
    def value(index,state='running'):
        v=copy.deepcopy(template);v['state']=state;v['latest']['index']=index;v['observed_samples']=index+1;return v
    def fixture(name):
        d=root/name;d.mkdir(mode=0o700);p=d/'live.json';protocol.publish_live(p,value(0,'starting'));protocol.publish_live(p,value(0));return p
    def delta(before):return {k:v-before[k]for k,v in protocol.publication_stats().items()}
    path=fixture('running-reader-busy');before=h.pin(path);stats=protocol.publication_stats()
    fd=os.open(path.with_name(path.name+'.lock'),os.O_RDWR)
    try:
        fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB);start=time.monotonic()
        assert protocol.publish_live(path,value(1))is False
        elapsed=time.monotonic()-start;assert elapsed<.1
        assert h.pin(path)==before and not path.with_name(path.name+'.'+str(os.getpid())+'.tmp').exists()
        assert delta(stats)==dict(attempts=1,published=0,coalesced_busy_reader=1,errors=0)
        # Coalescing does not make stale cached control acceptable.
        current=protocol.decode(path.read_bytes())
        assert protocol.validate_live(current,jp,job,owner,100.1)==current
        try:protocol.validate_live(current,jp,job,owner,100.6)
        except ValueError:pass
        else:raise AssertionError('Coalescing weakened500ms freshness')
    finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
    assert protocol.publish_live(path,value(2))is True
    assert protocol.checked_read(path,os.geteuid(),mode=0o644)==value(2)
    events.append(dict(group='busy_running_projection_coalesced_without_touching_published_file',elapsed_s=elapsed,stats=delta(stats),stale500ms_still_rejected=True))
    required=[]
    for state in ('starting','closed','failed'):
        path=fixture('required-'+state);before=h.pin(path);fd=os.open(path.with_name(path.name+'.lock'),os.O_RDWR)
        try:
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB);start=time.monotonic()
            try:protocol.publish_live(path,value(1,state))
            except ValueError as error:assert str(error)=='Bounded original live lock wait exceeded'
            else:raise AssertionError('Required terminal/start publication was coalesced')
            assert .1<=time.monotonic()-start<1 and h.pin(path)==before
            tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
            assert json.loads(tmp.read_bytes())==value(1,state)
            required.append(dict(state=state,preserved_tmp=h.pin(tmp),original_projection_unchanged=True))
        finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
    events.append(dict(group='all3_required_starting_closed_failed_publications_keep100ms_failure_and_bytes',cases=required))
    for case in ('lock_mode','unknown_stage'):
        path=fixture('unexpected-'+case);stats=protocol.publication_stats();tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp');lock=path.with_name(path.name+'.lock')
        if case=='lock_mode':
            lock.chmod(0o644)
            try:protocol.publish_live(path,value(1))
            except ValueError:pass
            else:raise AssertionError('Unknown lock failure was coalesced')
            assert json.loads(tmp.read_bytes())==value(1)
        else:
            fd=os.open(lock,os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB);original=protocol._try_running_publish_lock
            @contextmanager
            def changed(*args,**kw):
                with original(*args,**kw)as acquired:yield acquired
                tmp.write_bytes(b'changed-owned-inode')
            try:
                with patch.object(protocol,'_try_running_publish_lock',changed):
                    try:protocol.publish_live(path,value(1))
                    except ValueError as error:assert str(error)=='Owned staged live projection identity changed'
                    else:raise AssertionError('Changed staged inode was deleted')
                assert tmp.read_bytes()==b'changed-owned-inode'
            finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
        assert delta(stats)==dict(attempts=1,published=0,coalesced_busy_reader=0,errors=1)
        events.append(dict(group='unknown_failure_preserves_bytes_and_is_not_coalesced',case=case,stats=delta(stats),preserved_tmp=h.pin(tmp)))
    processes=[]
    for label,codec in [('old',old),('new',protocol)]:
        path=fixture('process-'+label);pp=h.pin(codec.__file__);stats=protocol.publication_stats()
        argv=[sys.executable,'-Xgil=0','-I','-B',str(Path(__file__).resolve()),'--reader','--protocol',pp['path'],'--protocol-sha256',pp['sha256'],'--path',str(path)]
        child=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert select.select([child.stdout],[],[],5)[0];held_line=child.stdout.readline();held=json.loads(held_line)
        assert held['pid']==child.pid and held['birth']==birth(child.pid)
        start=time.monotonic();error=None;returned=None
        try:
            try:returned=codec.publish_live(path,value(1))
            except ValueError as exc:assert label=='old'and str(exc)=='Bounded original live lock wait exceeded';error=repr(exc)
            else:assert label=='new'and returned is False
            elapsed=time.monotonic()-start
        finally:child.stdin.write('RELEASE\n');child.stdin.flush();stdout,stderr=child.communicate(timeout=5)
        assert child.returncode==0 and not stderr and birth(child.pid)!=held['birth']
        assert json.loads(stdout)['read']==value(0)
        if label=='new':
            assert delta(stats)==dict(attempts=1,published=0,coalesced_busy_reader=1,errors=0)
            assert protocol.publish_live(path,value(2))is True
            protocol.publish_live(path,value(2,'closed'))
            assert set(v.name for v in path.parent.iterdir())=={'live.json','live.json.lock'}
        processes.append(dict(codec=label,argv=argv,reader=held,actual_exit=0,birth_absent=True,stdout=held_line+stdout,stderr=stderr,publisher_error=error,publisher_returned=returned,elapsed_s=elapsed))
    events.append(dict(group='actual_cross_process_old_timeout_new_counted_coalescence_and_required_close',processes=processes))
    path=fixture('concurrent-running');stats=protocol.publication_stats();errors=[];retained=[];reads=[]
    def writer():
        try:
            for index in range(1,5001):
                retained.append(index);protocol.publish_live(path,value(index))
        except BaseException as error:errors.append(repr(error))
    thread=threading.Thread(target=writer);thread.start();deadline=time.monotonic()+40
    try:
        while thread.is_alive():
            assert time.monotonic()<deadline
            v=protocol.checked_read(path,os.geteuid(),mode=0o644);index=v['latest']['index']
            assert v==value(index)and(not reads or index>=reads[-1]);reads.append(index)
    finally:thread.join(timeout=5)
    assert not thread.is_alive()and not errors and retained==list(range(1,5001))and reads
    counts=delta(stats);assert counts['attempts']==counts['published']+counts['coalesced_busy_reader']==5000 and counts['errors']==0
    protocol.publish_live(path,value(5000,'closed'))
    assert protocol.checked_read(path,os.geteuid(),mode=0o644)==value(5000,'closed')
    assert set(v.name for v in path.parent.iterdir())=={'live.json','live.json.lock'}
    events.append(dict(group='5000_running_attempts_with_monotonic_whole_messages_and_required_final_close',counts=counts,reads=len(reads),retained_synthetic_observation_count=len(retained),actual_raw_health_replay_performed=False,
        retained_fixture_observations=h.put(root/'retained-synthetic-observation-indices.json',retained),reader_indices=h.put(root/'running-projection-reader-indices.json',reads)))
    path=fixture('cost-running');cost=[]
    for label,codec in [('A1',old),('B1',protocol),('B2',protocol),('A2',old)]:
        begin=time.monotonic_ns();cpu=time.thread_time_ns()
        for _ in range(1000):codec.publish_live(path,value(0));assert codec.checked_read(path,os.geteuid(),mode=0o644)==value(0)
        cost.append(dict(arm=label,publications_and_reads=1000,thread_CPU_ns=time.thread_time_ns()-cpu,wall_ns=time.monotonic_ns()-begin))
    events.append(dict(group='descriptive_ABBA1000_running_publication_and_read_cost',cost=cost,native_performance_gain_claim=False))
    return dict(events=events,groups=len(events),all_children_and_threads_joined=True,original_reader_and_raw_validity_rules_unchanged=True,
        coalescing_only_running_control_projections=True,required_terminal_and_start_publications_unchanged=True,
        actual_native_observer_raw_health_integration_verified=False,quality_qualified=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--reader',action='store_true');p.add_argument('--protocol',type=Path);p.add_argument('--protocol-sha256');p.add_argument('--path',type=Path);a=p.parse_args()
    if not a.reader:print('PLAN_ONLY');return
    assert sys.version_info[:2]==(3,14)and not sys._is_gil_enabled()and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    assert hashlib.sha256(a.protocol.read_bytes()).hexdigest()==a.protocol_sha256
    s=importlib.util.spec_from_file_location('_actual_paused_reader',a.protocol);codec=importlib.util.module_from_spec(s);s.loader.exec_module(codec);decode=codec.decode
    def paused(raw):
        print(json.dumps(dict(pid=os.getpid(),birth=birth(os.getpid()))),flush=True)
        assert select.select([sys.stdin],[],[],5)[0]and sys.stdin.readline().strip()=='RELEASE'
        return decode(raw)
    codec.decode=paused;v=codec.checked_read(a.path,os.geteuid(),mode=0o644)
    print(json.dumps(dict(read=v)),flush=True)

if __name__=='__main__':main()
