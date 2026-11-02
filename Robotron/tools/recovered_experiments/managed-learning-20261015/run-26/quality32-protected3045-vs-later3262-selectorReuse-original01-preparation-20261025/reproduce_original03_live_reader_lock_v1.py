"""CPU-only actual free-threaded reader/publisher contention mechanism.

Inject a paused decoder in a separate reader process. This tests a mechanism;
it does not establish why the original native reader held its lock too long.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

N=Path(__file__).resolve().parent
G=N.parents[3]
PROTOCOL=G/'tools/training_connection_lifecycle_proposal_20261023/dedicated_main_health_protocol_transient_live_v5.py'

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--reader',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if not(a.execute or a.reader):print('PLAN_ONLY');return 0
    assert sys.version_info[:2]==(3,14)and not sys._is_gil_enabled()and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()=='f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10'
    protocol=load('_actual_v5_contention',PROTOCOL)
    if a.reader:
        original_decode=protocol.decode
        def paused_decode(raw):
            print(json.dumps(dict(shared_lock_held_in_actual_decode=True,pid=os.getpid(),birth=birth(os.getpid()))),flush=True)
            assert select.select([sys.stdin],[],[],5)[0]
            assert sys.stdin.readline().strip()=='RELEASE'
            return original_decode(raw)
        protocol.decode=paused_decode
        value=protocol.checked_read(a.reader,os.geteuid(),mode=0o644)
        print(json.dumps(dict(original_read_value=value,free_threaded=True)),flush=True);return 0
    assert a.output and a.output.is_absolute()and not a.output.exists();a.output.mkdir(mode=0o700)
    h=load('_actual_v5_contention_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    path=a.output/'fixture-live.json';protocol.publish_live(path,dict(sequence=0));before=h.pin(path)
    argv=[sys.executable,'-Xgil=0','-I','-B',str(Path(__file__).resolve()),'--reader',str(path)]
    child=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    assert select.select([child.stdout],[],[],5)[0]
    held_line=child.stdout.readline();held=json.loads(held_line)
    assert held['pid']==child.pid and held['birth']==birth(child.pid)and held['shared_lock_held_in_actual_decode']is True
    started=time.monotonic();first_error=None;second_error=None
    try:
        try:protocol.publish_live(path,dict(sequence=1))
        except ValueError as error:
            assert str(error)=='Bounded original live lock wait exceeded';first_error=repr(error)
        else:raise AssertionError('Actual writer did not reject the paused actual reader')
        elapsed=time.monotonic()-started;assert .1<=elapsed<1
        assert h.pin(path)==before
        tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
        tmp_pin=h.pin(tmp);assert json.loads(h.checked(tmp_pin).read_bytes())==dict(sequence=1)
        try:protocol.publish_live(path,dict(sequence=2))
        except FileExistsError as error:second_error=repr(error)
        else:raise AssertionError('Preserved temporary bytes did not reject a second publish')
        assert h.pin(tmp)==tmp_pin and h.pin(path)==before
    finally:
        child.stdin.write('RELEASE\n');child.stdin.flush()
        stdout,stderr=child.communicate(timeout=5)
    assert child.returncode==0 and not stderr and birth(child.pid)!=held['birth']
    assert json.loads(stdout)['original_read_value']==dict(sequence=0)
    assert first_error and second_error and 'torch'not in sys.modules
    report=h.put(a.output/'report.json',dict(schema='robotron-original03-actual-v5-cross-process-lock-mechanism-v1',
        source=h.pin(__file__),protocol=h.pin(PROTOCOL),interpreter=sys.version,free_threaded=True,
        actual_reader_argv=argv,actual_reader=held,reader_actual_exit=0,reader_birth_absent=True,
        original_reader_stdout=held_line+stdout,original_reader_stderr=stderr,
        original_projection=before,preserved_temporary_projection=tmp_pin,
        actual_publish_error=first_error,actual_second_publish_error=second_error,actual_wait_elapsed_s=elapsed,
        actual_cross_process_shared_reader_blocks_exclusive_publisher=True,
        actual_original_timeout_and_preserved_tmp_collision_reproduced=True,
        original_data_and_modes_unchanged=True,controlled_decoder_pause_injected=True,
        original_native_cgroup_or_scheduling_cause_verified=False,
        future_protocol_selected=False,actual_GPU_MAME_or_training_started=False,
        failed_original03_retried=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,mechanism_reproduced=True)),flush=True);time.sleep(8);return 0

if __name__=='__main__':raise SystemExit(main())
