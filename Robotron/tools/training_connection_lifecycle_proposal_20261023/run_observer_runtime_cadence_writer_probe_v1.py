"""CPU-only factorial diagnostic of actual health engine, runtime and cadence.

Durable-write bursts are an explicit stress test of headroom, not a claim about
the unobserved cause of the failed2739 study. No scientific games or promotion.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

def load(pin,name):
    path=Path(pin['path']);raw=path.read_bytes()
    assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def resource():
    cgroup=next(line.split(':',2)[2]for line in Path('/proc/self/cgroup').read_text().splitlines()if line.startswith('0::'))
    root=Path('/sys/fs/cgroup'+cgroup)
    return dict(pid=os.getpid(),birth=birth(os.getpid()),cgroup=cgroup,monotonic_s=time.monotonic(),unix_s=time.time(),
        process_cpu_s=time.process_time(),thread_cpu_s=time.thread_time(),cpu_stat=root.joinpath('cpu.stat').read_text(),
        cpu_max=root.joinpath('cpu.max').read_text(),python=sys.version,executable=sys.executable,
        GIL_enabled=getattr(sys,'_is_gil_enabled',lambda:True)())

def arm(job,jp,subject,h,parent_pin):
    root=Path(job['output'])/subject['id'];root.mkdir(mode=0o700)
    assert str(Path(sys.executable))==subject['executable']
    assert getattr(sys,'_is_gil_enabled',lambda:True)()==subject['GIL_enabled']
    worker=load(job['original_worker'],'_runtime_probe_parent_checks')
    codec=load(job['original_protocol'],'_runtime_probe_live_projection')
    engine=load(job['health_job']['sources']['full_health_engine'],'_runtime_probe_actual_engine')
    parent=json.loads(h.checked(parent_pin).read_bytes());worker.verify_parent(parent,h,unit_check=True)
    original=json.loads(h.checked(job['stress_record']).read_bytes())
    before=resource();assert before['cpu_max']=='200000 100000\n'
    directory=root/'health';directory.mkdir(mode=0o700);directory.joinpath('samples').mkdir(mode=0o700)
    stress=[];stress_errors=[];stress_started=threading.Event();gc_open={};gc_summary={str(i):dict(count=0,maximum_wall_s=0.)for i in range(3)}
    def gc_callback(phase,info):
        key=threading.get_ident()
        if phase=='start':gc_open[key]=(time.monotonic(),info['generation'])
        elif key in gc_open:
            when,generation=gc_open.pop(key);row=gc_summary[str(generation)];row['count']+=1
            row['maximum_wall_s']=max(row['maximum_wall_s'],time.monotonic()-when)
    guard=None;closed=None;failure=None;error=None;latest=None;timings=[];start=None
    def write_stress():
        try:
            assert stress_started.wait(timeout=10)
            for index,offset in enumerate(job['burst_offsets_s']):
                time.sleep(max(0.,start+offset-time.monotonic()));begin=resource();files=[]
                for item in range(job['writes_per_burst']):
                    pin=h.put(root/('durable-stress-%02d-%02d.json'%(index,item)),original)
                    assert pin['sha256']==job['stress_record']['sha256']
                    files.append(pin)
                stress.append(dict(index=index,offset_s=offset,before=begin,after=resource(),files=files))
        except BaseException as exception:stress_errors.append(repr(exception))
    thread=threading.Thread(target=write_stress,name='authentic-durable-record-stress')
    gc.callbacks.append(gc_callback)
    try:
        guard=engine.MainHealth(job['health_job'],directory,h)
        start=time.monotonic();thread.start();stress_started.set();next_unit=0.
        while time.monotonic()-start<job['arm_duration_s']:
            tick=time.monotonic();entry=dict(index=guard.collector.index,tick_monotonic_s=tick)
            try:
                begin=time.monotonic();worker.verify_parent(parent,h,unit_check=tick>=next_unit)
                entry['parent_check_s']=time.monotonic()-begin
                if tick>=next_unit:next_unit=tick+5
                begin=time.monotonic();latest=guard.observe();entry['observe_s']=time.monotonic()-begin
                begin=time.monotonic()
                codec.publish_live(root/'live.json',dict(schema='robotron-runtime-cadence-probe-projection-v1',
                    job=jp,parent=parent,owner=dict(pid=os.getpid(),birth=birth(os.getpid())),nonce=subject['nonce'],
                    state='running',error=None,latest=latest,observed_samples=guard.collector.index,
                    emitted_monotonic_s=time.monotonic(),emitted_unix_s=time.time(),outcome=None))
                entry['projection_s']=time.monotonic()-begin
            finally:entry['ended_monotonic_s']=time.monotonic();timings.append(entry)
            time.sleep(max(0.,tick+subject['poll_s']-time.monotonic()))
        closed=h.put(root/'closed-health.json',guard.close())
    except BaseException as exception:
        error=repr(exception)
        if guard is not None:
            failure=h.put(root/'failed-health.json',guard.preserve_failure(exception))
    finally:
        if gc_callback in gc.callbacks:gc.callbacks.remove(gc_callback)
        stress_started.set()
        if thread.ident is not None:thread.join(timeout=40)
    assert not thread.is_alive()and not stress_errors,stress_errors
    assert len(stress)==len(job['burst_offsets_s'])==6
    assert 'torch'not in sys.modules
    if guard is not None:assert not guard.collector.writer.thread.is_alive()
    pins=[]if closed is None and failure is None else json.loads(h.checked(closed or failure).read_bytes())['samples']
    observations=[];gaps=[];previous=None
    for pin in pins:
        row=json.loads(h.checked(pin).read_bytes())['transport'];observations.append(row['index'])
        if previous is not None:gaps.append(dict(index=row['index'],gap_s=row['observed_unix_s']-previous))
        previous=row['observed_unix_s']
    assert observations==list(range(len(pins)))
    report=h.put(root/'report.json',dict(schema='robotron-observer-runtime-cadence-writer-probe-arm-v1',
        arm=subject,before=before,after=resource(),parent=parent_pin,closed_health=closed,failed_health=failure,
        valid_closed_health=closed is not None,error=error,original_raw_samples=len(pins),
        maximum_gap_s=max((g['gap_s']for g in gaps),default=0),gap_violations=[g for g in gaps if g['gap_s']>.5],
        timings=timings,GC_summary=gc_summary,durable_write_bursts=stress,stress_errors=stress_errors,
        all_writer_threads_stopped=True,stress_is_not_observed_original_failure_workload=True,
        previous_failed_study_requalified=False,scientific_case=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,arm=subject['id'],valid_closed_health=closed is not None,error=error)),flush=True)
    return 0

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job')
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');p.add_argument('--arm')
    a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-observer-runtime-cadence-writer-factorial-probe-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''and job['arm_duration_s']==25
    assert job['writes_per_burst']==32 and job['burst_offsets_s']==[2,5,8,11,14,17]
    h=load(job['helpers'],'_runtime_probe_h');jp=h.pin(a.job)
    for pin in job['inputs']:h.checked(pin)
    root=Path(job['output'])
    if a.arm:
        subjects=[s for s in job['arms']if s['id']==a.arm];assert len(subjects)==1
        return arm(job,jp,subjects[0],h,h.pin(root/'original-parent.json'))
    root.mkdir(mode=0o700)
    original_worker=load(job['original_worker'],'_runtime_probe_worker')
    cgroup=resource()['cgroup'];unit=Path(cgroup).name;fields=original_worker.show(unit)
    assert fields['MainPID']==str(os.getpid())and fields['InvocationID']==os.environ['INVOCATION_ID']
    parent=h.put(root/'original-parent.json',dict(pid=os.getpid(),birth=birth(os.getpid()),uid=os.geteuid(),unit=unit,
        invocation_id=fields['InvocationID'],cgroup=cgroup,argv=[v.decode()for v in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]],job=jp,source=h.pin(__file__)))
    reports=[]
    for subject in job['arms']:
        argv=[subject['executable'],*subject['interpreter_options'],'-I','-B',str(Path(__file__).resolve()),'--execute',
            '--job',a.job,'--job-sha256',a.job_sha256,'--source-sha256',a.source_sha256,'--arm',subject['id']]
        with(root/(subject['id']+'-stdout.txt')).open('xb')as out,(root/(subject['id']+'-stderr.txt')).open('xb')as err:
            child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
        child_pin=h.put(root/(subject['id']+'-original-child.json'),dict(pid=child.pid,birth=birth(child.pid),argv=argv,parent=parent,cgroup=Path('/proc',str(child.pid),'cgroup').read_text()))
        actual_exit=child.wait(timeout=60)
        result=h.put(root/(subject['id']+'-original-exit.json'),dict(original_child=child_pin,actual_exit=actual_exit,
            original_attempt=1,no_retry=True,child_reaped=True,birth_absent=birth(child.pid)!=json.loads(h.checked(child_pin).read_bytes())['birth']))
        assert actual_exit==0,'Diagnostic arm controller failed; no retry or health success inferred'
        report=h.pin(root/subject['id']/'report.json');reports.append(dict(arm=subject['id'],report=report,child=child_pin,original_exit=result))
    assert 'torch'not in sys.modules
    rp=h.put(root/'report.json',dict(schema='robotron-observer-runtime-cadence-writer-factorial-probe-report-v1',
        status='ALL_FOUR_ORIGINAL_DIAGNOSTIC_ARMS_FINISHED_OUTCOMES_PRESERVED',job=jp,original_reports=reports,
        every_original_arm_once=True,health_failures_not_requalified=True,no_native_MAME_or_policy_run=True,
        stress_does_not_establish_previous_failure_cause=True,production_changed=False,quality_qualified=False,
        created_unix_s=time.time()))
    print(json.dumps(dict(report=rp,arms=len(reports))),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
